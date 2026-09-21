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
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

TOOLCHAIN = "/opt/agent-toolchain"
# THE HOOK AND THE RELAY ARE GONE, and nothing replaces them on the pod.
#
# They were a `post_tool` hook client and a stream tee that turned every
# tool call into a ReasoningStep in the old memory layer. Both are
# retired with it (archive/neo4j-agent-memory-2026-09-20/). Under Cognee
# the agent writes what it chooses through its MCP server and the harness
# writes the rest from its own process, so NO harness code runs on the
# pod at all -- which also retires the whole class of bug where the pod
# ran a version nobody could identify.
#
# `HOOK_PYTHON` survives because it is not about the hook: it is the
# pod's own interpreter, used to run small stdlib-only probes over SSH,
# and it is named explicitly because a bare script path is handed to sh.
HOOK_PYTHON = "/usr/bin/python3"

# Where the two scripts above come from. THE REPO, and only the repo.
#
# Until 2026-09-19 nothing in this codebase put them on the pod. `hook.py`
# got a `chmod 755` in provision_memory.sh -- which assumes it is already
# there -- and `provision.sh` says of the proxy, in as many words, "copied
# by the runner's setup". There was no runner setup. All three were hand
# scp'd during pod bring-up and their versions recorded, if at all, as
# prose in NOTES.md.
#
# The cost: the 2026-09-18/19 series wrote 993 reasoning steps of which 988
# held serialised tool input, and because the relay's version on that pod
# was never recorded and the pod is gone, WHICH copy was running cannot now
# be established. `install_host_scripts` makes that unanswerable question
# impossible to ask again -- the files are uploaded from here and their
# sha256 is read back off the host.
REPO_DIR = Path(__file__).resolve().parent.parent
HARNESS_DIR = REPO_DIR / "harness"


def host_scripts() -> dict[str, tuple[str, str]]:
    """{local source: (remote path, mode)}.

    A FUNCTION, not a module constant. It was one when `HOOK_PATH` and
    `RELAY_PATH` still existed and were rebound after import by the
    rehearsal -- a dict built at import time installed to `/opt/swarm/` on
    the operator's laptop while the agent read from the temp root, so the
    rehearsal tested nothing. Kept as a function because the same trap
    returns the moment anything here becomes path-dependent again.
    """
    return {
        # THE HOOK AND THE RELAY ARE GONE. They existed so that every tool
        # call wrote a ReasoningStep into the old layer, and the relay
        # existed on top of that because Vibe's `turnId` never changes
        # within a conversation turn -- getting that wrong once made 988
        # of 993 steps carry serialised tool JSON instead of reasoning.
        # Cognee's agents call `remember` themselves through its MCP
        # server, so there is no second writer to keep in step.
        "id_fix_proxy.py": ("/opt/swarm/id_fix_proxy.py", "755"),
        # The web-lookup MCP server, which BOTH arms get -- it is not part
        # of the treatment, and an arm missing it is an arm difference.
        # Found missing the same way as the other three: provision_web.sh
        # died with "File not found: /opt/swarm/web/server.py" because
        # nothing had ever put it there either.
        "web-tools/server.py": ("/opt/swarm/web/server.py", "755"),
        "web-tools/requirements.txt": ("/opt/swarm/web/requirements.txt", "644"),
    }


def host_modules() -> dict[str, tuple[str, str]]:
    """{REPO-relative source: (remote path, mode)}, for the harness code the
    pod runs as a process rather than as a hook.

    Separate from `host_scripts` only because these do not live under
    `harness/` -- the sidecar is the harness's own module and the two
    orchestrator files are imported by it, so copying them into `harness/`
    would fork them.

    THIS WAS THE UNFIXED HALF OF THE 2026-09-19 FAULT. `install_host_scripts`
    was added after nothing was found to be installing hook.py, the relay,
    the proxy or the web server -- but the sidecar was left out, so
    provision_memory.sh still died with

        can't open file '/opt/swarm/swarm/sidecar_main.py'

    on the first pod that had never been touched by hand. Every earlier pod
    had been hand-copied, which is precisely why no version of it could be
    established. Modes are 0700/0600 under a 0711 directory: the sidecar
    holds Neo4j credentials at runtime and no agent may read it.
    """
    # EMPTY UNDER COGNEE, and that is the point. These four files were the
    # sidecar and the memory layer it imported, and they had to travel
    # because the pod ran our code. Cognee's MCP server is installed by
    # provision_cognee.sh from PyPI into its own venv, so there is no
    # harness module on the pod at all -- which also retires the whole
    # class of bug where the pod ran a version nobody could identify.
    return {}


def install_host_scripts(host: "SwarmHost") -> dict[str, str]:
    """Put the harness's own scripts on the pod and verify what landed.

    Two separate guarantees, worth keeping apart:

      OVERWRITTEN EVERY RUN, from `harness/`. That is what makes a stale
      copy on a reused pod impossible -- by construction, not by checking.

      THE DIGEST IS READ BACK OFF THE HOST. That catches the write not
      landing: a refused path, a truncated transfer, a `put` that reported
      success and did nothing. Invisible otherwise, because the relay
      never errors -- it keeps running whatever was already there and
      forwards nothing, while `steps_written` climbs exactly as it should.

    Returns {remote path: sha256}. Raises on a mismatch.
    """
    digests: dict[str, str] = {}
    sources = [(HARNESS_DIR / name, remote, mode)
               for name, (remote, mode) in host_scripts().items()]
    sources += [(REPO_DIR / name, remote, mode)
                for name, (remote, mode) in host_modules().items()]
    for source, remote, mode in sources:
        data = source.read_bytes()
        want = hashlib.sha256(data).hexdigest()
        host.run(f"mkdir -p {os.path.dirname(remote)}", check=False)
        host.put(data, remote, mode=mode)
        got = (host.run(f"sha256sum {shlex.quote(remote)}", check=False)
               .stdout or "").split()[:1]
        if not got or got[0] != want:
            raise RuntimeError(
                f"{remote} does not match {source}: host says "
                f"{got[0] if got else 'nothing'}, repo says {want}. The pod "
                f"would run a version nobody can name.")
        digests[remote] = want
    # 0711: traversable, not listable. An agent reaches a path it is told
    # about and cannot enumerate the directory. Set AFTER the writes,
    # because mkdir -p above may have created it with the default mode.
    host.run("chmod 711 /opt/swarm", check=False)
    return digests

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

# THE DETERMINISTIC READ, as Vibe's own declarative hook config.
#
# `match = "bash"` is the tool the agents actually use: over the last forty
# runs, 4,767 `bash` calls against 9 `cognee_recall` calls. A hook on it fires
# whether or not the model thought to ask.
#
# `strict = false` (the default) on purpose: a hook that exits non-zero must
# not fail the tool call. The timeout is short for the same reason -- this runs
# inside the agent's clock, and warm paying latency cold does not is a
# confound in every number the run produces.
_HOOKS_TEMPLATE = """\
[[hooks]]
name = "cognee-on-failure"
type = "post_tool"
match = "bash"
command = "{command}"
timeout = 10.0
description = "On a failed command, append what earlier graded attempts \
did about that failure."
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


_FRONTMATTER_BOUNDARY = re.compile(r"^-{3,}\s*$", re.MULTILINE)

# AIP's own layout for runnable content. Mirrors
# orchestrator.skills.SCRIPT_DIRS; see _body_sha on why the duplication.
_SCRIPT_DIRS = ("scripts/",)


def _is_script(relative_path: str) -> bool:
    return relative_path.startswith(_SCRIPT_DIRS)




# Marks the appended block, so inlining twice is a no-op and so anyone
# reading a pod's SKILL.md can see at a glance that the tail is not the
# author's body.


def _dir_sha(file_digests: dict[str, str]) -> str:
    """One hash over a whole skill package, from path -> sha256 hex.

    Matches `orchestrator.skills.dir_sha`, which hashes the same pairs; a
    test holds the two together.
    """
    h = hashlib.sha256()
    for rel in sorted(file_digests):
        h.update(rel.encode())
        h.update(b"\0")
        h.update(file_digests[rel].encode())
        h.update(b"\n")
    return h.hexdigest()[:12]


def _body_sha(skill_text: str) -> str:
    """sha256 prefix of a SKILL.md's markdown body.

    The body, not the file: Vibe loads `SkillInfo.prompt`, so the
    frontmatter never reaches the model and cannot be part of the answer to
    "which version did this agent run against?".

    A deliberate duplicate of `orchestrator.skills.body_of` -- this module
    does not import from `orchestrator/`, which is not on the swarm host.
    `test_skill_body_split_matches_the_orchestrator` fails if the two drift.
    """
    parts = _FRONTMATTER_BOUNDARY.split(skill_text.lstrip("﻿"), 2)
    body = (parts[2] if len(parts) >= 3 else skill_text).strip()
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def repo_tarball(repo: Path, *, exclude: tuple[str, ...] = (".git", "__pycache__",
                                                            ".venv", "node_modules",
                                                            ".pytest_cache", "pytest_cache")) -> bytes:
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


def tree_tarball(file_contents: dict[str, bytes]) -> bytes:
    """A collected tree, as a tarball. The inverse of `_untar`.

    For archiving the tree an attempt produced. Takes the dict the grader
    is already given rather than re-reading the pod, so keeping every
    attempt's tree costs no round trip -- see `on_attempt_tree` in
    `migrate_codebase`.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in sorted(file_contents.items()):
            info = tarfile.TarInfo(name.removeprefix("/repo/"))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@dataclass
class AgentWorkspace:
    """One agent: its user, its home, its single visible repo."""

    # Filled by refresh(), which runs inside run_vibe -- see refresh().
    _cache: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Kept for the rehearsal's LocalWorkspace, which overrides
    # `_vibe_command` and still reads it. Nothing in production sets it:
    # there is no relay to pipe a stream through any more.
    relay_port: int | None = field(default=None, init=False, repr=False, compare=False)
    # The distiller's own endpoint, so its tokens are counted apart from
    # the attempt's. Set by enable_distillation.
    distill_base_url: str | None = field(default=None, init=False, repr=False,
                                         compare=False)
    # Which AIP version is on the pod for THIS agent right now, set by
    # install_skill. None means no skill installed, which is cold's normal
    # state and warm's state before the first install.
    installed_skill_version: int | None = field(default=None, init=False,
                                                repr=False, compare=False)
    installed_skill_sha: str | None = field(default=None, init=False,
                                            repr=False, compare=False)
    # What the `post_tool` hook reads out of its environment. Empty for
    # cold, which registers no hook, so an inherited variable cannot hand it
    # a path to the graph. Set by enable_memory().
    _hook_env: dict[str, str] = field(default_factory=dict, init=False,
                                      repr=False, compare=False)

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

    def checkout_is_writable(self) -> bool:
        """Can the agent actually edit its own source?

        Seven runs said no and nobody noticed: `fixture/` is chmod a-w to
        protect the ground truth and `repo_tarball` preserves modes, so every
        agent got a read-only checkout and recorded 13 graded attempts with
        zero edit/write_file calls. Checked per run and stamped onto every
        trace, so a distiller can exclude runs where editing was impossible.

        Tests stay read-only on purpose; this asks about source only.
        """
        out = self.host.run_as(
            self.user,
            f"find {self.repo_path} -name '*.py' -not -path '*/tests/*' "
            f"-not -path '*/.git/*' ! -writable | wc -l",
            check=False).stdout.strip()
        try:
            return int(out or "1") == 0
        except ValueError:
            return False

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
        # BY THE SERVER'S ALIAS, because the tool names changed with the
        # server. cognee publishes `recall`/`remember`/`search`, which Vibe
        # republishes as `cognee_*` -- none of them contain "memor",
        # "step", "trace" or "graph". The old filter matched exactly ONE of
        # them, `cognee_visualize_graph_ui`, so this gate would have passed
        # on a server that had lost every tool an agent could retrieve
        # with. Measured on the first pod run: "memory tools: 1 loaded".
        memory_tools = {t for t in tools
                        if t.startswith("cognee")
                        or any(k in t.lower() for k in
                               ("memor", "recall", "remember"))}
        if not memory_tools:
            raise RuntimeError(
                f"{self.label}: Vibe loaded no memory tools. It loaded "
                f"{sorted(tools) or 'nothing at all'}. The warm arm cannot "
                f"retrieve anything, so the run would measure nothing."
            )
        return memory_tools

    # ---- NO CHECKPOINT, NO ROLLBACK ---------------------------------------
    #
    # There were `init_history`/`checkpoint`/`restore_best` here, backed by a
    # bare git repo at `$HOME/.history`. They are gone.
    #
    # The operator never asked for them: "They should just continue on each
    # attempt. Never start from scratch. Never 'pick some random code you
    # can't test'." And they did harm -- keyed on `tests_passed`, which on
    # `fixtures/oapi` is 0 / ~310 / 445 and cannot see how much of the
    # migration exists, the restore fired twice in the 2026-09-18/19 series
    # and both times threw away an 8-surface migration (floor is 3) to
    # recover a 40- and a 55-surface tree that happened to import. Both hits
    # landed on warm, the arm under test.
    #
    # Attempts share one checkout, which is the point: attempt N+1 continues
    # N's work, including N's mistakes. An agent that leaves a syntax error
    # gets that error fed back to it and fixes it, which is what a developer
    # does. `ATTEMPT_DONE.broke_syntax` records when that happened.



    @property
    def distill_home(self) -> str:
        """The distiller's own VIBE_HOME.

        A PROPERTY, like `distill_dir` beside it, and it must stay one:
        every use is inside an f-string. As a plain method it interpolated
        its own bound-method repr, so `enable_distillation` tried to
        `mkdir -p "<bound method AgentWorkspace.distill_home of ...>"` and
        the first pod run died there, after provisioning, the model
        download and the whole preflight had been paid for.

        The rehearsal could not catch it: LocalHost.put writes through the
        local filesystem and happily created a directory with that repr as
        its name -- one turned up untracked in the repo root, which is the
        only trace the bug left for a fortnight.
        """
        return f"{self.home}/.vibe-distill"

    @property
    def distill_dir(self) -> str:
        return f"{self.home}/distill"

    def distill_skill_path(self) -> str:
        return f"{self.distill_dir}/SKILL.md"

    def enable_distillation(self, *, mcp_url: str, model_base_url: str) -> None:
        """Build the distiller's environment. Off the clock, once per run."""
        self.distill_base_url = model_base_url
        config = _CONFIG_TEMPLATE.format(
            model_base=model_base_url, model=self.model,
            auto_compact=self.auto_compact_threshold,
        ) + _MCP_SERVER_TEMPLATE.format(name="neo4j-agent-memory", url=mcp_url)
        self.host.run_as(self.user, f"mkdir -p {self.distill_home} {self.distill_dir}",
                         check=False)
        self.host.put(config.encode(), f"{self.distill_home}/config.toml",
                      mode="600", owner=f"{self.user}:{self.user}")
        # No hooks.toml in either location. Nothing writes to the graph
        # from a tool call any more, here least of all.
        self.host.run_as(
            self.user,
            f"rm -f {self.distill_home}/hooks.toml {self.distill_dir}/.vibe/hooks.toml",
            check=False)

    def clear_distilled(self) -> None:
        """Empty the distiller's directory, INCLUDING its output file.

        VIBE'S `write_file` REFUSES TO OVERWRITE: "File '...' already
        exists. Use edit to modify it."
        (vibe/core/tools/builtins/write_file.py). An earlier version of
        this seeded the current SKILL.md at the output path so the model
        could edit a copy -- which made every single distillation fail with
        that error, the file keep its old contents, and the proposal be
        rejected for still being version N. The model has the current text
        in its prompt; the path it writes to must not exist.

        Called before EVERY turn, including repairs: a repair turn would
        otherwise collide with the file the rejected turn just wrote.
        """
        self.host.run_as(
            self.user,
            f"rm -rf {self.distill_dir} && mkdir -p {self.distill_dir}",
            check=False)

    def read_distilled(self) -> str:
        """Whatever the distiller left behind. Empty string if nothing."""
        return self.host.run_as(
            self.user, f"cat {self.distill_skill_path()} 2>/dev/null || true",
            check=False).stdout

    async def run_distill(self, prompt: str, *, timeout_s: float,
                          resume: bool = False) -> tuple[int, str]:
        """One distillation turn, in the distiller's own environment."""
        proc = await self.invoke_vibe_async(
            prompt, resume=resume, timeout=timeout_s,
            vibe_home=self.distill_home, cwd=self.distill_dir)
        return proc.returncode, (proc.stdout or "")

    def setup_fingerprint(self) -> dict[str, Any]:
        """Everything about this agent's setup that must match the other arm.

        The experiment's whole claim is that warm and cold differ in ONE
        thing. That has been false twice without anyone noticing -- the
        `web` MCP server was registered for warm only, and warm's task
        prompt carried three extra numbered steps -- and each time the
        warm/cold token comparison from those runs was worthless. Reading
        the actual state of both agents is cheaper than re-running.

        Deliberately not the skill: that is the permitted difference, and it
        is checked separately by `has_skills_dir` and the hash comparison.
        """
        hooks = self.host.run_as(
            self.user,
            f"for f in {self.home}/.vibe/hooks.toml "
            f"{self.repo_path}/.vibe/hooks.toml; do "
            f"test -f $f && echo $f; done",
            check=False).stdout.split()
        config = self.host.run_as(
            self.user, f"cat {self.home}/.vibe/config.toml", check=False).stdout
        # MCP server names, not the whole config: the URLs legitimately
        # differ between agents (each arm has its own counting proxy) and
        # the model line carries the agent's own alias.
        servers = sorted(re.findall(r'^\s*name\s*=\s*"([^"]+)"', config,
                                    re.MULTILINE))
        return {
            "hook_files": sorted(p.rsplit("/.vibe/", 1)[-1] for p in hooks),
            "config_names": servers,
            "disabled_tools": sorted(re.findall(r'disabled_tools\s*=\s*\[([^\]]*)\]',
                                                config)),
            "tools": sorted(self.loaded_tools()),
        }

    def has_skills_dir(self) -> bool:
        """Does this agent have a skills directory at all?

        Asked of COLD every run. "Cold never sees a skill" is a claim about
        the machine, and the cheap way to be wrong about it is to change how
        skills are installed and not notice that the old path is still there.
        """
        out = self.host.run_as(
            self.user,
            f"test -d {self.home}/.vibe/skills && echo yes || echo no",
            check=False).stdout.strip()
        return out.endswith("yes")

    def loaded_skill_text(self, name: str) -> str | None:
        """What Vibe actually loaded, read off this agent's own transcript.

        Vibe injects the skill as a real `skill` tool call and result when
        the prompt begins `/<name>` (core/agent_loop/_loop.py:
        _inject_invoked_skill), and wraps it in `<skill_content name="...">`.
        Returns that result, or None if no skill was loaded -- which is the
        difference between "the agent ignored its procedure" and "the
        procedure never reached it", and those have opposite fixes.
        """
        marker = f'<skill_content name="{name}">'
        for msg in self._transcript_messages(newest_only=True):
            content = msg.get("content") or ""
            if msg.get("name") == "skill" and marker in content:
                return content
        return None

    def memory_tool_calls(self) -> int:
        """How many times this agent called a Cognee memory tool.

        REPLACES `loaded_skill_text`, which asked whether a skill FILE had
        reached the model. There is no file: the procedure lives in
        Cognee and warm reaches it with `recall`, so the equivalent
        question is whether the agent used the tools at all.

        Zero is a RESULT, not an error. The old layer's defining failure
        was 40 consecutive runs with zero agent-initiated memory calls
        while every check reported green -- so this is counted and
        printed rather than asserted, and a run where warm never
        consulted its memory is a finding about the model, not a broken
        harness.
        """
        calls = 0
        for msg in self._transcript_messages():
            name = msg.get("name") or ""
            if name.startswith("cognee") or name in ("remember", "recall"):
                calls += 1
            for tc in (msg.get("tool_calls") or []):
                fn = ((tc.get("function") or {}).get("name") or "")
                if fn.startswith("cognee") or fn in ("remember", "recall"):
                    calls += 1
        return calls

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

    @property
    def hook_journal(self) -> str:
        """Where the `post_tool` hook records what it did. Read by the harness
        after each attempt, and folded into that attempt's outcome document --
        so "the hook fired N times and recalled M characters" is countable
        rather than inferred."""
        return f"{self.home}/.vibe/cognee-journal.jsonl"

    def agent_path(self, path: str) -> str:
        """The same path as VIBE will see it.

        On the pod these are identical, and on the pod this is a no-op. The
        rehearsal runs the "pod" as a subtree of a temp directory and rewrites
        pod paths on the way through `host.run`; the hook command and the
        journal path do NOT go through `host.run` -- VIBE executes them -- so
        they have to be rewritten here instead.

        This exact class of bug already killed a rehearsal: `MSF_HOOK_PATH`
        pointed at an unmapped path, Vibe could not start the hook, and the
        rehearsal reported a working hook for as long as it was left alone.
        """
        return path

    def enable_hook(self, *, api_url: str, dataset: str,
                    node_sets: tuple[str, str]) -> None:
        """Register the deterministic read. Warm only.

        A Vibe `post_tool` hook on `bash`: when the agent's own command
        fails, it recalls what earlier graded attempts did about that failure
        and Vibe appends the result to the tool output the model sees.

        This exists because the voluntary half does not fire. Over the last
        forty runs the agents made 4,767 `bash` calls and 9 `cognee_recall`
        calls -- the server live, the tools registered, the model simply
        never reaching for them. A hook is not a nudge: it is the read
        happening whether or not the model thought of it.

        It costs one python start per FAILED bash call and nothing on a
        successful one, with an 8s ceiling on the whole hook, because this
        runs inside the agent's clock and warm paying latency cold does not
        is a confound in every number the run produces.
        """
        vibe_home = f"{self.home}/.vibe"
        hook = (HARNESS_DIR / "hooks" / "cognee_on_failure.py").read_bytes()
        self.host.put(hook, f"{vibe_home}/cognee_on_failure.py", mode="500",
                      owner=f"{self.user}:{self.user}")
        script = self.agent_path(f"{vibe_home}/cognee_on_failure.py")
        self.host.put(_HOOKS_TEMPLATE.format(
            command=f"{HOOK_PYTHON} {script}").encode(),
            f"{vibe_home}/hooks.toml", mode="400",
            owner=f"{self.user}:{self.user}")
        self._hook_env = {
            "COGNEE_API": api_url,
            "COGNEE_DATASET": dataset,
            "COGNEE_NODE_SET_WORKED": node_sets[0],
            "COGNEE_NODE_SET_FAILED": node_sets[1],
            "COGNEE_JOURNAL": self.agent_path(self.hook_journal),
        }

    def read_hook_journal(self, *, clear: bool = True) -> list[dict]:
        """One entry per `bash` call the hook saw, newest last."""
        import json

        raw = self.host.run_as(self.user, f"cat {self.hook_journal} 2>/dev/null",
                               check=False).stdout or ""
        if clear:
            self.host.run_as(self.user, f": > {self.hook_journal} 2>/dev/null",
                             check=False)
        out = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def enable_memory(self, *, mcp_url: str) -> None:
        """Give this agent the cognee MCP server. Warm only.

        HALF OF WARM'S TREATMENT. The other half -- the procedure and the
        retrieved context in its prompt, and the session trace written
        after each attempt -- runs in the orchestrator's own process
        through `cognee.agent_memory`, and reaches this agent as prompt
        text rather than as anything installed here.

        The MCP server is registered over HTTP, not stdio, and it already
        exists -- one process, run as root, shared by every warm agent. That is
        what keeps the Neo4j credential away from the agent entirely: Vibe
        echoes a stdio server's whole launch command into every tool result, so
        a stdio registration would put `--password=` in the model's context on
        every memory call, and a `#!` shim cannot hide it either because a
        script must be readable to be executed.

        Registered as `transport = "streamable-http"` by
        `_MCP_SERVER_TEMPLATE`, and that is the one detail not to
        simplify: Vibe's `http` transport selects its LEGACY SSE client,
        which issues a bare GET, and a streamable-HTTP server answers
        that with 406 Not Acceptable. The agent then registers ZERO
        memory tools while the config, the server and every log line look
        healthy. It cost a whole run once.
        """
        vibe_home = f"{self.home}/.vibe"
        blocks = _MCP_SERVER_TEMPLATE.format(name="cognee", url=mcp_url)
        self.host.put(blocks.encode(), f"{vibe_home}/mcp.part", mode="600",
                      owner=f"{self.user}:{self.user}")
        self.host.run(
            f"cat {vibe_home}/mcp.part >> {vibe_home}/config.toml && "
            f"rm -f {vibe_home}/mcp.part"
        )
        # NO HOOKS. This wrote a `hooks.toml` registering `post_tool`
        # and `post_agent` commands so that every tool call became a
        # ReasoningStep, then asserted both that the hook ran and that the
        # relay delivered reasoning rather than tool JSON. All three are
        # retired with the old memory layer: the agent calls `remember` on
        # its MCP server if it chooses to, and the writes the harness owns
        # happen in the orchestrator's process, so there is no hook to
        # register, no relay to verify, and no second writer to keep in
        # step with the first.



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

    def _vibe_command(self, prompt: str, *, resume: bool,
                      vibe_home: str | None = None,
                      cwd: str | None = None) -> str:
        """The remote command line, shared by the sync and async paths.

        `vibe_home`/`cwd` default to the ATTEMPT environment. The
        distillation turn passes its own, so it gets the memory MCP server
        and a scratch directory without the attempt path changing at all.
        """
        env = " ".join([
            f"VIBE_HOME={vibe_home or self.home + '/.vibe'}",
            f"PATH={self.venv}/bin:{TOOLCHAIN}/bin:/usr/local/bin:/usr/bin:/bin",
            f"VIRTUAL_ENV={self.venv}",
            # WHAT THE HOOK NEEDS, and nothing else: a loopback URL, a
            # dataset name, two node-set names and a path to write a
            # journal. No credential. Empty for cold, whose config
            # registers no hook at all -- so an inherited variable cannot
            # give it a path to the graph.
            *(f"{k}={shlex.quote(v)}" for k, v in
              sorted(self._hook_env.items())),
        ])
        resume_arg = " --continue" if resume else ""
        vibe = (f"env {env} {TOOLCHAIN}/bin/vibe "
                f"--prompt {shlex.quote(prompt)}{resume_arg} "
                f"--auto-approve --trust --output streaming < /dev/null")
        workdir = cwd or self.repo_path
        # NOTHING IS PIPED. Vibe's stream used to be teed through the
        # reasoning relay so that the sidecar saw the model's reasoning
        # rather than serialised tool input; both are gone, and the
        # stream is read in-process by `stream_entries`.
        return f"cd {workdir} && {vibe}"

    def _kill_remote_vibe(self) -> None:
        self.host.run(f"pkill -u {self.user} -f 'bin/vibe' || true",
                      check=False, timeout=60)

    async def invoke_vibe_async(self, prompt: str, *, resume: bool = False,
                                timeout: float = 1800.0,
                                vibe_home: str | None = None,
                                cwd: str | None = None
                                ) -> subprocess.CompletedProcess:
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
            *self.host.argv_as(self.user, self._vibe_command(
                prompt, resume=resume, vibe_home=vibe_home, cwd=cwd)),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        # DRAINED AS IT ARRIVES, not collected at the end.
        #
        # `proc.communicate()` buffers inside the coroutine, so cancelling
        # it on timeout discarded everything Vibe had already streamed.
        # Measured, run 10 attempt 3: the agent worked for 59 turns, took
        # the suite to 33/33 -- the only passing attempt in the run -- hit
        # the timeout, and ingested ZERO steps, because its whole stream
        # went out with the cancelled coroutine. The transcript on the pod
        # is no substitute: messages.jsonl carries role/content/tool_calls
        # and NO reasoning field, so recovering steps from it would write
        # actions with empty thoughts.
        #
        # Under the harder task this is the common case, not the edge case:
        # attempts that run out of clock are exactly the ones carrying the
        # failure information the distiller needs.
        chunks: list[bytes] = []
        err_chunks: list[bytes] = []

        async def drain(stream, into: list[bytes]) -> None:
            while True:
                block = await stream.read(65536)
                if not block:
                    return
                into.append(block)

        drains = asyncio.gather(drain(proc.stdout, chunks),
                                drain(proc.stderr, err_chunks))
        try:
            # NOT shielded. `wait_for(shield(f))` raises CancelledError
            # rather than TimeoutError when the timeout fires, and this
            # function's contract is that a timeout RETURNS a
            # CompletedProcess -- a CancelledError here is re-raised and
            # unwinds the whole agent loop instead of costing one attempt.
            # Shielding is also unnecessary: `chunks` is appended to as the
            # bytes arrive, so cancelling the drain cannot lose what it has
            # already collected.
            await asyncio.wait_for(drains, timeout=timeout)
            await proc.wait()
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            # Same contract as the sync path: an attempt the clock cuts is
            # still an attempt, and it is still graded on what the agent
            # achieved. Raising here would unwind agent_worker instead.
            drains.cancel()
            # suppress(Exception) is NOT enough: CancelledError derives from
            # BaseException, so awaiting a cancelled gather would raise
            # straight through this handler and be re-raised below as if the
            # caller had cancelled us -- turning a timed-out attempt back
            # into an unwound agent loop, the exact regression
            # test_timeout_returns_rather_than_raises exists to catch.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await drains
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            await asyncio.to_thread(self._kill_remote_vibe)
            if isinstance(exc, asyncio.CancelledError):
                raise
            partial = b"".join(chunks).decode(errors="replace")
            # A stream cut mid-line leaves a fragment that is not JSON;
            # `stream_entries` skips unparseable lines, so the completed
            # turns before it survive.
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout=partial,
                stderr=(b"".join(err_chunks).decode(errors="replace")
                        + f"\nvibe invocation timed out after {timeout:.0f}s"),
            )
        out, err = b"".join(chunks), b"".join(err_chunks)
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
                                                  ".pytest_cache", "pytest_cache", ".vibe")) -> dict[str, bytes]:
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
                                                            ".pytest_cache", "pytest_cache", ".vibe")
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
