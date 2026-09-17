"""One agent's workspace on the swarm host.

An agent gets a unix user, a home at mode 0700, and inside it exactly one
thing: the repo it was asked to work on. Nothing else about the system is
reachable to it -- no sibling agent's work, no orchestrator source, no fixture,
no answer key. That is the property the old design tried and failed to reach by
patching leaks one at a time (repo path echoed in MCP tool results, `PWD`
inherited from the operator's shell, all checkouts under one parent, absolute
paths replayed out of the memory graph). Here it holds because none of those
things exist on this host.

Everything is driven over SSH, because that is what the pod offers and it keeps
the host's own contents out of this process. Nothing here imports from
`orchestrator/` -- that package is the old batch harness and is not going to be
on the swarm host.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import shlex
import subprocess
import tarfile
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

TOOLCHAIN = "/opt/agent-toolchain"
# The post_tool hook client. Executable by agents, readable by agents, and
# carrying no secret -- it knows a port and its own label. Everything that
# needs a credential lives behind /opt/swarm, which is 0711: an agent can
# traverse to a path it is told about and cannot enumerate the directory.
HOOK_PATH = "/opt/swarm/hook.py"
# Named explicitly, the way render_config does it (`f"{sys.executable}
# {STEP_HOOK_SCRIPT} ..."`). harness/memory_step_hook.py has NO shebang -- it
# opens with its docstring -- so a bare `/opt/swarm/hook.py` is handed to sh,
# which reports `line 4: post_tool: command not found` on stderr and writes
# nothing usable to stdout.
#
# The hook fails open by design, so this is silent: run 12 wrote 0 steps with
# 0 errors while the agent made 85 tool calls, and the summary's own guard had
# to be the thing that noticed. `test -x hook.py` passes throughout -- the
# file IS executable, it just is not a shell script.
HOOK_PYTHON = "/usr/bin/python3"
# Tees Vibe's streamed entries so the agent's REASONING reaches the sidecar
# while the agent is still running -- see harness/reasoning_relay.py. Without
# it every ReasoningStep.thought is tool-argument JSON, and `search_steps`
# embeds thought+action, so the graph is searchable by what was typed rather
# than by why. Warm only: it is part of the memory path, and cold has none.
RELAY_PATH = "/opt/swarm/reasoning_relay.py"

# What the agent's Vibe talks to. The model is on the SAME host, so there is no
# proxy and no public URL in the agent's config -- and nothing for it to learn
# from. The old design routed through id_fix_proxy on the operator's machine,
# which is why the model endpoint had to be a RunPod public hostname at all.
MODEL_BASE_URL = "http://127.0.0.1:30000"

# `active_model` and `auto_compact_threshold` are TOP-LEVEL keys and must come
# before any [[table]] header: TOML attaches a bare key to whichever table
# precedes it, so putting them after [[providers]] makes them provider fields
# and Vibe silently falls back to its default `mistral` provider -- which then
# fails with "Missing MISTRAL_API_KEY". Cost one run to rediscover; the old
# harness has a comment saying exactly this at vibe_agent.py:350.
_CONFIG_TEMPLATE = """\
active_model = "swarm-model"
auto_compact_threshold = {auto_compact}
disabled_tools = ["web_search"]

[[providers]]
name = "local"
api_base = "{model_base}/v1"
api_style = "openai"
backend = "generic"

[[models]]
name = "{model}"
provider = "local"
alias = "swarm-model"
"""

# Written straight into config.toml rather than registered with `vibe mcp add`.
#
# Two reasons, both from vibe/core/config:
#
#  * `vibe mcp add` IS the OAuth path. persist_oauth_mcp_server() hardcodes
#    auth={"type": "oauth"} and its own error text says "`/mcp add` only
#    supports OAuth MCP servers". Pointing it at a no-auth loopback server
#    writes an [mcp_servers.auth] type = "oauth" block that makes Vibe start
#    an OAuth discovery the server knows nothing about.
#  * `--transport http` selects MCPHttp, Vibe's LEGACY SSE client
#    (models.py: MCPHttp / MCPStreamableHttp are separate models discriminated
#    on `transport`). FastMCP's `mcp serve --transport http` serves
#    streamable-HTTP at /mcp, so the legacy client issues a bare GET and the
#    server answers 406 Not Acceptable. Vibe's own default is
#    "streamable-http"; "http" is the odd one out.
#
# Together those two cost run 9: the agent registered ZERO memory tools
# (meta.json `tools {}`) and never made a single retrieval, while the step
# hook -- a completely separate path -- happily wrote 22 steps. The summary
# read "22 step(s) written, 0 injection(s), 0 error(s)", which looks like an
# agent that chose not to read rather than one that had nothing to read with.
#
# Omitting [mcp_servers.auth] entirely leaves _MCPHttpFields.auth at its
# default MCPStaticAuth, whose http_headers() is empty -- which is exactly
# right for a server on 127.0.0.1 that has no auth.
_MCP_SERVER_TEMPLATE = """
[[mcp_servers]]
name = "{name}"
transport = "streamable-http"
url = "{url}"
"""


@dataclass
class SwarmHost:
    """The machine the agents run on, reached over SSH.

    `identity` is the operator's key. The agents never see it: commands are
    run as root and then dropped to the agent's own user with `su -`, so an
    agent's process has no credential for this host.
    """

    host: str
    port: int
    identity: Path
    user: str = "root"

    # Where credentials live on the host: one root-only file, written once.
    #
    # NEVER pass a secret as a command argument. It is visible in `ps` to
    # anything on the host, it lands in shell history and logs, and -- the way
    # this was found -- subprocess.TimeoutExpired stringifies the whole argv,
    # so a single timeout printed a live OpenAI key and the Neo4j password
    # into a transcript. Commands that need credentials source this file
    # instead, and the file is mode 0600 root in a directory agents cannot
    # enumerate.
    ENV_FILE = "/opt/swarm/env"

    # Sockets for the multiplexed ssh masters. Not /tmp: a world-writable
    # directory lets anything on this machine pre-create the path. 0700 under
    # the operator's own home, created on first use.
    CONTROL_DIR = str(Path.home() / ".ssh" / "msf-control")

    def write_env_file(self, values: dict[str, str]) -> None:
        body = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in values.items())
        self.run(f"mkdir -p {os.path.dirname(self.ENV_FILE)}", check=False)
        self.put(body.encode(), self.ENV_FILE, mode="600")

    def run_with_env(self, command: str, **kw) -> subprocess.CompletedProcess:
        """Run a command with the host's credential file sourced.

        The secrets reach the process through the file, so they appear in no
        argv anywhere -- not here, not in `ps` on the host, not in an
        exception."""
        return self.run(f". {self.ENV_FILE} && {command}", **kw)

    def _ensure_control_dir(self) -> None:
        os.makedirs(self.CONTROL_DIR, mode=0o700, exist_ok=True)

    def argv(self, command: str) -> list[str]:
        """The ssh argv for `command`. One builder, so the blocking and the
        async paths cannot drift in flags -- `BatchMode` and `IdentitiesOnly`
        in particular decide whether a wedged key prompts or fails fast.

        MULTIPLEXING. Every call here pays a full TCP+TLS+auth handshake
        otherwise: measured 1.9-2.0s per round trip against this pod, against
        0.34-0.62s over a shared master. That matters most for
        `RemoteTraceBridge.set_trace`/`clear_trace`, which migrate_codebase
        calls synchronously around every attempt: ~4s per attempt that only
        the warm arm pays, and -- because it is sync on the event loop -- it
        stalls cold at the same time. Multiplexing removes most of it without
        changing when the calls happen, which matters because the post_tool
        hook asks the sidecar which trace the agent is on; a set_trace that
        lands after the first tool call attaches steps to the wrong trace.
        Residual after this: ~0.5s per attempt, warm only, under 0.5% of a
        ~200s attempt. Stated rather than engineered away.

        `%C` is a hash of (local host, remote host, port, user), so the path
        is unique per connection and two pods never share a master.

        `ControlMaster=auto` is the tolerant mode: if the socket is missing,
        stale, or its master has died, ssh falls back to opening a normal
        connection and re-establishes the master, rather than failing. That
        is the behaviour we want -- a dead master should cost one slow call,
        not a failed attempt.
        """
        self._ensure_control_dir()
        return [
            "ssh", "-i", str(self.identity),
            "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ControlMaster=auto",
            "-o", f"ControlPath={self.CONTROL_DIR}/cm-%C",
            "-o", "ControlPersist=120",
            "-p", str(self.port), f"{self.user}@{self.host}",
            command,
        ]

    def argv_as(self, agent_user: str, command: str) -> list[str]:
        return self.argv(f"su - {shlex.quote(agent_user)} -c {shlex.quote(command)}")

    def run(self, command: str, *, timeout: float = 600.0,
            check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.argv(command),
            capture_output=True, text=True, timeout=timeout, check=check,
        )

    def gpu_description(self) -> str:
        """What hardware this run actually used.

        Recorded because throughput differs enough between cards to change
        conclusions: measured on the same weights, single-stream decode was
        246 tok/s on a B200 and 183 tok/s on an H200, and 4-concurrent
        aggregate 544 vs 320. A run compared against one from different
        silicon is comparing the silicon.
        """
        out = self.run(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader",
            check=False, timeout=60).stdout.strip().splitlines()
        if not out:
            return "unknown GPU"
        names = [line.strip() for line in out if line.strip()]
        return f"{len(names)}x {names[0]}" if names else "unknown GPU"

    def run_as(self, agent_user: str, command: str, **kw) -> subprocess.CompletedProcess:
        """Run `command` as the agent, from its own home.

        `su - <user> -c` rather than `sudo -u`: it resets the environment to
        that user's login environment, so the agent does not inherit root's
        `PWD`, `OLDPWD`, `PATH` or anything else naming this host's layout.
        The old harness passed `dict(os.environ)` to Vibe and leaked the
        operator's repo root through `PWD` before the agent made a single tool
        call.
        """
        return self.run(f"su - {shlex.quote(agent_user)} -c {shlex.quote(command)}", **kw)

    def put(self, data: bytes, dst: str, *, mode: str = "600",
            owner: str | None = None) -> None:
        """Write bytes to a path on the host, via stdin -- no scp, no temp file
        on the operator's disk."""
        chown = f" && chown {shlex.quote(owner)} {shlex.quote(dst)}" if owner else ""
        proc = subprocess.run(
            [
                "ssh", "-i", str(self.identity),
                "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-p", str(self.port), f"{self.user}@{self.host}",
                f"cat > {shlex.quote(dst)} && chmod {mode} {shlex.quote(dst)}{chown}",
            ],
            input=data, capture_output=True, timeout=600.0,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"put {dst} failed: {proc.stderr.decode()[:400]}")


def repo_tarball(repo: Path, *, exclude: tuple[str, ...] = (".git", "__pycache__",
                                                            ".venv", "node_modules",
                                                            ".pytest_cache")) -> bytes:
    """The user's repo, as a tarball, built in memory.

    `.git` is excluded by default: the agent is asked to change code, not
    history, and a repo's history is the single richest source of information
    about things it was not asked to look at. The user's own working tree is
    never mutated -- this is a copy, and what comes back is a diff.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in sorted(repo.rglob("*")):
            rel = path.relative_to(repo)
            if any(part in exclude for part in rel.parts):
                continue
            if path.is_file() or path.is_dir():
                tar.add(path, arcname=str(rel), recursive=False)
    return buf.getvalue()


@dataclass
class AgentWorkspace:
    """One agent: its user, its home, its single visible repo."""

    # Filled by refresh(), which runs inside run_vibe -- see refresh().
    _cache: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Set by enable_memory() for warm agents; None means no relay in the
    # pipeline, which is what cold gets.
    relay_port: int | None = field(default=None, init=False, repr=False, compare=False)

    host: SwarmHost
    label: str                      # e.g. "warm-0"
    model: str
    auto_compact_threshold: int = 24000
    repo_name: str = "repo"
    # Which endpoint this agent's Vibe talks to. Defaults straight to the
    # model; a run that wants per-arm token accounting points each arm at its
    # own counting proxy on the same host instead, because Vibe never surfaces
    # per-call usage outside its own process.
    model_base_url: str = MODEL_BASE_URL

    @property
    def user(self) -> str:
        return f"agent-{self.label}"

    @property
    def home(self) -> str:
        return f"/home/{self.user}"

    @property
    def repo_path(self) -> str:
        return f"{self.home}/{self.repo_name}"

    def seed(self, tarball: bytes) -> None:
        """Put the repo in the agent's home, owned by the agent, and nothing
        else."""
        staging = f"/tmp/{self.user}-repo.tgz"
        self.host.put(tarball, staging, mode="600")
        self.host.run(
            f"rm -rf {self.repo_path} && mkdir -p {self.repo_path} && "
            f"tar -xzf {staging} -C {self.repo_path} && "
            f"chown -R {self.user}:{self.user} {self.repo_path} && "
            f"rm -f {staging}"
        )
        # Everything the original seed_repo does, and for the same reasons.
        # Each of these was lost when this class was written from scratch and
        # each had already been paid for once.
        self.host.run_as(
            self.user,
            # 1. RESTORE WRITE. The source repo may be chmod a-w on disk to
            #    protect it from agents with bash and --trust, and tar
            #    preserves mode -- so without this every agent gets a
            #    READ-ONLY checkout and cannot do the task at all. Measured
            #    here: `fastapi_mail/config.py` arrived -r--r--r--, agents
            #    burned 788s per attempt, and the only requirement anything
            #    ever scored was the one file that happened to be writable.
            f"cd {self.repo_path} && chmod -R u+w . && "
            # 2. ...except the test SOURCE, which is the oracle. An agent that
            #    edits the suite fixes nothing the grader sees, and read-only
            #    turns a misleading "String to replace not found" into an
            #    accurate permission error. Only *.py: four tests write
            #    attachment fixtures into tests/txt_files/, and locking the
            #    whole tree made the suite unpassable -- the real answer key
            #    scored 29/33 for that reason alone.
            f"find tests -name '*.py' -exec chmod a-w {{}} + 2>/dev/null; "
            # 3. A real checkout has a .gitignore. `git status` is most of what
            #    Vibe puts in its system prompt, so build junk showing as
            #    untracked reads to the agent as part of the codebase it was
            #    asked to migrate.
            f"printf '__pycache__/\\n*.pyc\\n.pytest_cache/\\n' > .gitignore && "
            # 4. git init AND a real seed commit. An empty commit leaves every
            #    file untracked, so `git status` tells the agent its whole repo
            #    is new and `diff()` reports the entire tree as an addition.
            #    Identity in the repo CONFIG, not inline on the commit: an
            #    agent that chooses to commit should not hit "Please tell me
            #    who you are".
            f"git init -q . 2>/dev/null; "
            f"git config user.email swarm@local && git config user.name swarm && "
            f"git add -A && git commit -q -m seed --no-verify || true",
            check=False,
        )

    def clear_session_logs(self) -> None:
        """Drop Vibe transcripts from earlier RUNS.

        Within a run the directory must persist -- that is what `--continue`
        resumes. Across runs it must not: otherwise a warm agent replays every
        message it has ever produced into the current run's trace, and
        `assistant_turns_total` counts turns from days ago as this attempt's.
        """
        self.host.run_as(
            self.user, f"rm -rf {self.home}/.vibe/logs/session/*", check=False)

    def loaded_tools(self) -> set[str]:
        """Tool names Vibe actually loaded, from the newest session's meta.json.

        Not the config, not `mcp add`'s exit code -- what reached the model.
        Registering a server and loading its tools are different events, and
        run 9 is what the gap between them looks like: config.toml listed the
        memory server, the process was up and answering, and the model was
        handed no memory tools at all, because the client spoke the wrong HTTP
        dialect and took a 406 in silence.

        The key is `tools_available`, a list of OpenAI function specs. There
        is also a `tools` key; it is NOT this, it stays `{}` in sessions where
        the agent demonstrably ran edit and bash, and reading it is how this
        check first came back empty against a working server.
        """
        out = self.host.run_as(
            self.user,
            "python3 -c \"import json,glob,os;"
            "f=sorted(glob.glob(os.path.expanduser('~/.vibe/logs/session/*/meta.json')),"
            "key=os.path.getmtime);"
            "m=json.load(open(f[-1])) if f else {};"
            "print(json.dumps(sorted(t['function']['name'] "
            "for t in m.get('tools_available') or [])))\"",
            check=False,
        ).stdout.strip()
        try:
            return set(json.loads(out or "[]"))
        except json.JSONDecodeError:
            return set()

    def assert_memory_tools_loaded(self) -> set[str]:
        """Make one cheap Vibe call and fail unless memory tools came with it.

        Off the run clock and before the agents start, because the alternative
        is discovering it in the summary: run 9 finished GATE ok, no errors,
        22 steps written -- and 0 retrievals, which reads as a model that
        chose not to use memory rather than one that was never given it.
        """
        self.invoke_vibe("Reply with the single word: ready", timeout=300.0)
        tools = self.loaded_tools()
        memory_tools = {t for t in tools if "memor" in t.lower() or "step" in t.lower()
                        or "trace" in t.lower() or "graph" in t.lower()}
        if not memory_tools:
            raise RuntimeError(
                f"{self.label}: Vibe loaded no memory tools. It loaded "
                f"{sorted(tools) or 'nothing at all'}. The warm arm cannot "
                f"retrieve anything, so the run would measure nothing."
            )
        return memory_tools

    def install_dependencies(self, install_command: str, *, timeout: float = 1800.0
                             ) -> subprocess.CompletedProcess:
        """Run the user's OWN install command in the agent's own venv.

        Nothing pinned here. The old harness installed a fixed
        `requirements-v2.txt` in three places because the task was always the
        same migration; for an arbitrary repo the install step is the user's to
        state, and if it fails that is a fact about their repo, reported as-is.
        """
        # The venv lives OUTSIDE the repo. Created inside it, every diff
        # carried the whole environment -- 564,661 lines on the first run --
        # and the agent's own `grep`/`find` walked thousands of site-packages
        # files that have nothing to do with its task.
        return self.host.run_as(
            self.user,
            f"python3 -m venv {self.venv} && cd {self.repo_path} && "
            f". {self.venv}/bin/activate && {install_command}",
            timeout=timeout, check=False,
        )

    @property
    def venv(self) -> str:
        return f"{self.home}/venv"

    def write_config(self, *, web_url: str | None = None) -> None:
        """Render config.toml. `web` is registered for EVERY agent, warm and
        cold, exactly as render_config does it -- see its docstring.

        It is not part of the comparison, it is a baseline capability the task
        requires: migrating email_check.py means replacing `EmailStr.validate`
        with the `email_validator` package, and the traceback never names
        another library, so a model without lookup plateaus at 2 of 3 files.
        Registering it for warm only -- which is what this file did until now
        -- makes it a second difference between the arms on top of memory, and
        every warm-vs-cold number measured that way is confounded.

        Published as `web_lookup`, deliberately not `web_search`: Vibe names
        MCP tools f"{alias}_{tool}" and `disabled_tools` kills the native
        `web_search` BY NAME after MCP registration, which would take this
        server's tool with it.
        """
        config = _CONFIG_TEMPLATE.format(
            model_base=self.model_base_url,
            model=self.model,
            auto_compact=self.auto_compact_threshold,
        )
        if web_url:
            config += _MCP_SERVER_TEMPLATE.format(name="web", url=web_url)
        vibe_home = f"{self.home}/.vibe"
        self.host.run(f"mkdir -p {vibe_home} && chown {self.user}:{self.user} {vibe_home}")
        self.host.put(config.encode(), f"{vibe_home}/config.toml",
                      mode="600", owner=f"{self.user}:{self.user}")

    def enable_memory(self, *, mcp_url: str, sidecar_port: int) -> None:
        """Give this agent the memory server and the per-step hook. Warm only.

        The MCP server is registered over HTTP, not stdio, and it already
        exists -- one process, run as root, shared by every warm agent. That is
        what keeps the Neo4j credential away from the agent entirely: Vibe
        echoes a stdio server's whole launch command into every tool result, so
        a stdio registration would put `--password=` in the model's context on
        every memory call, and a `#!` shim cannot hide it either because a
        script must be readable to be executed.

        `hooks.toml` is Vibe's own mechanism, not an injection point of ours:
        a `post_tool` hook may return `hook_specific_output.additional_context`
        and Vibe appends it to the tool output the model sees.
        """
        self.relay_port = sidecar_port
        vibe_home = f"{self.home}/.vibe"
        blocks = _MCP_SERVER_TEMPLATE.format(name="neo4j-agent-memory", url=mcp_url)
        self.host.put(blocks.encode(), f"{vibe_home}/mcp.part", mode="600",
                      owner=f"{self.user}:{self.user}")
        self.host.run(
            f"cat {vibe_home}/mcp.part >> {vibe_home}/config.toml && "
            f"rm -f {vibe_home}/mcp.part"
        )
        # Vibe's schema, not one of mine: the file is a `hooks` ARRAY and
        # `type` names the EVENT (vibe/core/hooks/config.py, _HooksTomlRoot +
        # HookConfig{name,type,command,match,timeout,strict,description}).
        #
        # This was first written as `[[post_tool]]` with `type = "command"`,
        # which parses as valid TOML, contributes no hooks, and reports
        # nothing: the run exits 0 and the graph stays empty -- indistinguish-
        # able from an agent that made no tool calls. The old harness had the
        # shape right and I invented a different one instead of copying it.
        command = f"{HOOK_PYTHON} {HOOK_PATH} {sidecar_port} {self.label}"
        hooks = "".join(
            "[[hooks]]\n"
            f'name = "memory-{event}"\n'
            f'type = "{event}"\n'
            f'command = "{command}"\n'
            + ('match = "*"\n' if event == "post_tool" else "")
            + "timeout = 20.0\n\n"
            for event in ("post_tool", "post_agent")
        )
        # BOTH locations. Vibe reads `<project_root>/.vibe/hooks.toml` for
        # every project root, and `$VIBE_HOME/hooks.toml` only when "user" is
        # among its configured sources (_harness_manager.py:136-142). Writing
        # only to VIBE_HOME produced a clean run with the hook never firing --
        # no error, no warning, just zero steps -- which is the same silent
        # shape as a broken MCP server.
        for target in (f"{vibe_home}/hooks.toml", f"{self.repo_path}/.vibe/hooks.toml"):
            self.host.run_as(self.user, f"mkdir -p {os.path.dirname(target)}", check=False)
            self.host.put(hooks.encode(), target, mode="600",
                          owner=f"{self.user}:{self.user}")
        self.assert_hook_runs(command)

    def assert_hook_runs(self, command: str) -> None:
        """Run the hook exactly as Vibe will and read what it writes.

        The hook fails open on purpose -- any exception becomes `{}` and exit
        0 -- so a hook that cannot run at all is indistinguishable from an
        agent that made no tool calls. That is not hypothetical: run 12
        recorded 0 steps and 0 errors while warm-0 made 85 tool calls and
        converged, and only the summary's own "the step hook wrote nothing"
        guard caught it.

        `test -x /opt/swarm/hook.py` cannot catch it. The file is executable;
        it simply has no shebang, so sh runs it and prints `command not
        found` to stderr. Checking that stdout parses as JSON and stderr is
        clean is what distinguishes the two.
        """
        probe = json.dumps({"hook_event_name": "post_tool", "tool_name": "__probe__",
                            "tool_input": {}, "tool_output_text": "", "tool_status": "ok"})
        r = self.host.run_as(
            self.user, f"printf %s {shlex.quote(probe)} | {command}", check=False)
        err = (r.stderr or "").strip()
        out = (r.stdout or "").strip()
        try:
            json.loads(out or "{}")
        except json.JSONDecodeError:
            raise RuntimeError(
                f"{self.label}: the step hook does not emit JSON. stdout={out[:200]!r} "
                f"stderr={err[:200]!r}. Every tool call would be dropped silently."
            ) from None
        if "command not found" in err or "Traceback" in err:
            raise RuntimeError(
                f"{self.label}: the step hook errored: {err[:300]!r}. It fails open, "
                f"so the run would record 0 steps and 0 errors."
            )

    # ---- orchestrator.vibe_agent.Workspace --------------------------------
    #
    # The attempt loop, the grading, the trace keying, observed_fix and every
    # event stay in migrate_codebase, unchanged. This class only answers the
    # six questions that have a different answer when the agent is on another
    # machine. An earlier version of swarm/run.py reimplemented the loop and
    # had already drifted -- its own cruder tests_passed and error_signature,
    # no observed_fix outcome text, no add_message -- which is a different
    # graph built a different way.

    async def run_vibe(self, task: str, *, timeout_s: float, resume: bool,
                          on_entry: Any | None) -> tuple[int, str]:
        # INVALIDATE FIRST. The cache is how the sync accessors avoid
        # blocking, so the one thing it must never do is answer a
        # post-attempt question with pre-attempt data: `collect_file_contents`
        # feeds the Daytona grader, and stale contents would grade the
        # PREVIOUS attempt's tree and attribute the verdict to this one.
        #
        # Clearing it here means every failure path is safe by construction
        # rather than by remembering to refresh on it. If the refresh below
        # never runs -- timeout, cancellation, a dead ssh -- the cache stays
        # None and the next reader falls back to `_ensure_cache`, which is
        # slow but correct. Nothing can read the previous attempt's state.
        self._cache = None
        proc = await self.invoke_vibe_async(task, resume=resume, timeout=timeout_s)
        # migrate_codebase reads snapshot/turns/tools/steps straight after
        # this returns. One concurrent, off-loop fetch here replaces five
        # blocking ones there. A timed-out attempt reaches this line too --
        # invoke_vibe_async returns a CompletedProcess rather than raising --
        # and it is still graded, so it still needs the refresh.
        try:
            await self.refresh()
        except Exception:
            self._cache = None  # partial state is worse than none
        if on_entry is not None:
            for entry in self.stream_entries(proc.stdout):
                try:
                    await on_entry(entry)
                except Exception:
                    pass
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def snapshot(self) -> dict[str, str]:
        """path -> sha256, for the "did anything change" check."""
        import hashlib
        return {p: hashlib.sha256(b).hexdigest()
                for p, b in self._ensure_cache()["tree"].items()}

    def collect_file_contents(self) -> dict[str, bytes]:
        return {f"/repo/{p}": b for p, b in self._ensure_cache()["tree"].items()}

    def assistant_turns_total(self) -> int:
        return self._transcript_count(lambda m: m.get("role") == "assistant")

    def steps_used(self) -> int:
        return self._transcript_count(
            lambda m: m.get("role") in ("user", "assistant"), newest_only=True)

    def tool_calls_total(self):
        from collections import Counter
        counts: Counter = Counter()
        for msg in self._transcript_messages():
            for tc in msg.get("tool_calls") or []:
                name = (tc.get("function") or {}).get("name")
                if name:
                    counts[name] += 1
        return counts

    def _transcript_messages(self, *, newest_only: bool = False) -> list[dict]:
        sessions = self._ensure_cache()["sessions"]
        if newest_only:
            sessions = sessions[:1]
        return [m for session in sessions for m in session]

    def _transcript_count(self, predicate, *, newest_only: bool = False) -> int:
        return sum(1 for m in self._transcript_messages(newest_only=newest_only)
                   if predicate(m))

    def _vibe_command(self, prompt: str, *, resume: bool) -> str:
        """The remote command line, shared by the sync and async paths."""
        env = " ".join([
            f"VIBE_HOME={self.home}/.vibe",
            f"PATH={self.venv}/bin:{TOOLCHAIN}/bin:/usr/local/bin:/usr/bin:/bin",
            f"VIRTUAL_ENV={self.venv}",
        ])
        resume_arg = " --continue" if resume else ""
        vibe = (f"env {env} {TOOLCHAIN}/bin/vibe "
                f"--prompt {shlex.quote(prompt)}{resume_arg} "
                f"--auto-approve --trust --output streaming < /dev/null")
        if self.relay_port is None:
            return f"cd {self.repo_path} && {vibe}"
        # `pipefail` so the pipeline reports VIBE's exit code, not the
        # relay's -- `_ended_cleanly` keys on it, and a relay that always
        # exits 0 would make every attempt look like a clean stop.
        # `-u` so the relay does not buffer the stream behind Vibe.
        return (f"cd {self.repo_path} && set -o pipefail && {vibe} "
                f"| {HOOK_PYTHON} -u {RELAY_PATH} {self.relay_port} {self.label}")

    def _kill_remote_vibe(self) -> None:
        self.host.run(f"pkill -u {self.user} -f 'bin/vibe' || true",
                      check=False, timeout=60)

    async def invoke_vibe_async(self, prompt: str, *, resume: bool = False,
                                timeout: float = 1800.0) -> subprocess.CompletedProcess:
        """`invoke_vibe`, but it yields the event loop while Vibe runs.

        THIS IS THE ONE THAT MATTERS FOR THE COMPARISON. The blocking version
        is a `subprocess.run` inside an `async def`, which pins the loop for
        the whole invocation -- minutes -- so the other agent's coroutine
        cannot run. Measured on run 12: `#running-req` was 0 or 1 across all
        1,032 scheduler samples and never 2, `#queue-req` was 0 throughout,
        and the KV cache sat at 2-6%, while the same endpoint served 4
        concurrent requests at 543 tok/s the moment anything asked it to.
        Warm and cold alternated rather than ran together, which is exactly
        what the README forbids: "blocking calls on the shared event loop
        leak warm's memory cost into cold's wall-clock".

        `create_subprocess_exec` rather than `to_thread`: a cancelled
        `to_thread` keeps the ssh process alive until `subprocess.run`'s own
        timeout expires -- so a cancelled agent would go on holding the model
        and its checkout -- and the default executor caps at 32 threads,
        which becomes a second invisible concurrency ceiling as swarm size
        grows. Here cancellation is explicit: kill the local ssh, then pkill
        the remote vibe, then re-raise.
        """
        proc = await asyncio.create_subprocess_exec(
            *self.host.argv_as(self.user, self._vibe_command(prompt, resume=resume)),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            # Same contract as the sync path: an attempt the clock cuts is
            # still an attempt, and it is still graded on what the agent
            # achieved. Raising here would unwind agent_worker instead.
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            await asyncio.to_thread(self._kill_remote_vibe)
            if isinstance(exc, asyncio.CancelledError):
                raise
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="",
                stderr=f"vibe invocation timed out after {timeout:.0f}s",
            )
        return subprocess.CompletedProcess(
            args=[], returncode=proc.returncode,
            stdout=out.decode(errors="replace"),
            stderr=err.decode(errors="replace"),
        )

    def invoke_vibe(self, prompt: str, *, resume: bool = False,
                    timeout: float = 1800.0) -> subprocess.CompletedProcess:
        """Blocking. Preflight only -- never from inside the event loop.

        No `--max-turns`: the agent ends its own invocation when it stops
        calling tools, exactly as it does when a person runs it. `--output
        streaming` because its entries are the only channel carrying the
        agent's reasoning with a `turn_id` attached.

        The repo's own `.venv` leads PATH, so `python` and `pytest` inside the
        agent's shell are the repo's, not the toolchain's. The toolchain is
        only how Vibe itself is launched.
        """
        # An attempt the clock cuts is still an attempt, and it still gets
        # graded on whatever the agent achieved. `subprocess.run(timeout=)`
        # RAISES, so letting that propagate kills the agent's whole loop --
        # measured: one cold agent hit its budget, the exception unwound
        # agent_loop, `gather(return_exceptions=True)` swallowed it, and the
        # run reported "0/0 converged, 0 attempts" while the sidecar had
        # recorded 33 steps.
        # stdin from /dev/null: Vibe calls get_prompt_from_stdin()
        # unconditionally and blocks on a non-TTY stdin that never reaches EOF,
        # which hangs every agent before its first LLM call.
        try:
            return self.host.run_as(
                self.user, self._vibe_command(prompt, resume=resume),
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # Kill the remote process too -- the local ssh dying leaves Vibe
            # running on the host, holding the model and the agent's repo.
            self._kill_remote_vibe()
            return subprocess.CompletedProcess(
                args=exc.cmd, returncode=1,
                stdout=(exc.stdout or b"").decode(errors="replace")
                if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=f"vibe invocation timed out after {timeout:.0f}s",
            )

    # ---- one round trip per attempt, off the event loop ------------------
    #
    # Each of these used to be its own blocking ssh call, made from inside a
    # coroutine. Measured against the live pod: assistant_turns_total 7.43s,
    # tool_calls_total 6.98s, steps_used 4.60s, snapshot 2.39s,
    # collect_file_contents 2.32s -- about 26s per attempt, and the whole
    # event loop is frozen for every second of it, so the OTHER agent is
    # stopped too. Over run 12's 19 attempts that is ~8 minutes of enforced
    # serialisation on top of the Vibe invocations themselves.
    #
    # The three transcript readers were the worst of it: `_transcript_
    # messages` did an `ls -1t` and then one `cat` per session file, three
    # times per attempt.
    #
    # The protocol cannot change -- `snapshot`, `collect_file_contents`,
    # `assistant_turns_total`, `tool_calls_total` and `steps_used` are sync
    # in orchestrator.vibe_agent.Workspace and shared with LocalWorkspace.
    # So the fetch moves instead of the signatures: migrate_codebase calls
    # three of them BEFORE `await run_vibe` and five AFTER, and the agent is
    # idle between one attempt ending and the next beginning, so a refresh at
    # the end of run_vibe serves both. The accessors become dictionary reads.

    _TRANSCRIPT_DUMP = (
        "python3 -c \"import glob,json,os;"
        "fs=sorted(glob.glob(os.path.expanduser('~/.vibe/logs/session/*/messages.jsonl')),"
        "key=os.path.getmtime,reverse=True);"
        "print(json.dumps([open(f).read() for f in fs]))\""
    )

    async def _run_as_async(self, command: str, *, timeout: float) -> str:
        proc = await asyncio.create_subprocess_exec(
            *self.host.argv_as(self.user, command),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            raise
        return out.decode(errors="replace")

    @staticmethod
    def _parse_sessions(raw: str) -> list[list[dict]]:
        try:
            bodies = json.loads(raw.strip() or "[]")
        except json.JSONDecodeError:
            return []
        sessions = []
        for body in bodies:
            msgs = []
            for line in body.splitlines():
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            sessions.append(msgs)
        return sessions

    async def refresh(self) -> None:
        """Pull the tree and every transcript once, concurrently, off-loop."""
        tree_raw, sessions_raw = await asyncio.gather(
            self._run_as_async(
                f"cd {self.repo_path} && tar -czf - . 2>/dev/null | base64 -w0",
                timeout=600.0),
            self._run_as_async(self._TRANSCRIPT_DUMP, timeout=300.0),
        )
        self._cache = {"tree": self._untar(tree_raw),
                       "sessions": self._parse_sessions(sessions_raw)}

    def _ensure_cache(self) -> dict:
        """Populate synchronously if nothing has refreshed yet.

        Only reachable before the first run_vibe. run.py primes it during
        setup, off the run clock, so in a real run this never blocks.
        """
        if self._cache is None:
            self._cache = {
                "tree": self._untar(self.host.run_as(
                    self.user,
                    f"cd {self.repo_path} && tar -czf - . 2>/dev/null | base64 -w0",
                    timeout=600.0, check=False).stdout),
                "sessions": self._parse_sessions(self.host.run_as(
                    self.user, self._TRANSCRIPT_DUMP, check=False).stdout),
            }
        return self._cache

    def prime(self) -> None:
        """Blocking refresh, for setup. Keeps attempt 1 off the slow path."""
        self._cache = None
        self._ensure_cache()

    def stream_entries(self, stdout: str) -> list[dict]:
        """Vibe's streamed history entries, one JSON object per line."""
        entries = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def tree(self, *, exclude: tuple[str, ...] = (".git", "__pycache__",
                                                  ".pytest_cache", ".vibe")) -> dict[str, bytes]:
        """The agent's current working tree, pulled back for grading.

        Grading runs in a Daytona sandbox driven from the operator's machine,
        not on this host: the sandbox is the one environment the agent has
        never touched, which is what makes its verdict ground truth rather
        than something the agent could arrange. Keeping it there also keeps
        DAYTONA_API_KEY off the swarm host entirely.
        """
        return self._untar(self.host.run_as(
            self.user, f"cd {self.repo_path} && tar -czf - . 2>/dev/null | base64 -w0",
            timeout=600.0, check=False,
        ).stdout, exclude=exclude)

    @staticmethod
    def _untar(listing: str, *, exclude: tuple[str, ...] = (".git", "__pycache__",
                                                            ".pytest_cache", ".vibe")
               ) -> dict[str, bytes]:
        import base64
        out: dict[str, bytes] = {}
        try:
            buf = io.BytesIO(base64.b64decode(listing))
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    rel = member.name.lstrip("./")
                    if any(part in exclude for part in Path(rel).parts):
                        continue
                    f = tar.extractfile(member)
                    if f is not None:
                        out[rel] = f.read()
        except (tarfile.TarError, ValueError, EOFError):
            return {}
        return out

    def diff(self) -> str:
        """What the agent changed, as a patch against what was seeded.

        The user's own working tree is never touched; this is what they apply
        if they want it. `git` is initialised at seed time purely to make this
        possible -- the seeded tarball deliberately excludes the user's real
        `.git`.
        """
        return self.host.run_as(
            self.user, f"cd {self.repo_path} && git add -A && git diff --cached",
            check=False,
        ).stdout

    def visible_paths(self) -> list[str]:
        """Everything outside its own home that this agent can read.

        A check, not a report: the design's one claim is that an agent sees
        only its repo, and this is what falsifies it. Run it, do not assume it.
        """
        probe = (
            "for p in /root /home /opt /workspace /tmp; do "
            "  ls $p >/dev/null 2>&1 && echo \"READABLE $p\"; "
            "done; true"
        )
        out = self.host.run_as(self.user, probe, check=False).stdout
        return [l.split(" ", 1)[1] for l in out.splitlines() if l.startswith("READABLE ")]
