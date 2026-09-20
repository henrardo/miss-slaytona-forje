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
# The post_tool hook client. Executable by agents, readable by agents, and
# carrying no secret -- it knows a port and its own label. Everything that
# needs a credential lives behind /opt/swarm, which is 0711: an agent can
# traverse to a path it is told about and cannot enumerate the directory.
# Overridable so the write path can be exercised off-pod. Vibe executes
# this string itself, so the harness's own path mapping does not apply to
# it -- pointing it at the pod's absolute path from a laptop gives a hook
# that can never run, and a hook that cannot run fails SILENTLY: the run
# exits 0 and the graph is empty, which looks exactly like an agent that
# made no tool calls.
HOOK_PATH = os.environ.get("MSF_HOOK_PATH", "/opt/swarm/hook.py")
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
RELAY_PATH = os.environ.get("MSF_RELAY_PATH",
                            "/opt/swarm/reasoning_relay.py")

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

    A FUNCTION, not a module constant, because `HOOK_PATH` and
    `RELAY_PATH` are rebound after import -- the rehearsal points them at
    its own tree, since Vibe executes those two commands itself and no
    path mapping can reach them. A dict built at import time would have
    installed to `/opt/swarm/` on the operator's laptop while the agent
    read from the temp root, and the rehearsal would have tested nothing.
    """
    return {
        "memory_step_hook.py": (HOOK_PATH, "755"),
        "reasoning_relay.py": (RELAY_PATH, "755"),
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
    return {
        "swarm/sidecar_main.py": ("/opt/swarm/swarm/sidecar_main.py", "700"),
        "orchestrator/__init__.py": ("/opt/swarm/orchestrator/__init__.py", "600"),
        "orchestrator/memory.py": ("/opt/swarm/orchestrator/memory.py", "600"),
        "orchestrator/step_memory.py": ("/opt/swarm/orchestrator/step_memory.py",
                                        "600"),
    }


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


def inline_references(files: dict[str, bytes]) -> dict[str, bytes]:
    """Append `references/` verbatim to SKILL.md, keeping the files too.

    WHY. AIP's progressive disclosure relocates detail out of the body and
    into `references/`, to be read on demand. Measured in experiment
    swarm-1789903474: the model NEVER reads them. Zero reference reads
    across all six attempts of both arms -- and not for want of directions.
    Vibe's own skill reply hands the agent the absolute base directory, the
    line "Relative paths in this skill are relative to this base
    directory", and a listing of all five files. It simply does not follow
    pointers.

    What that cost: v1's relocation "succeeded" (body 5159 -> 2224 tokens,
    5 files) and turned the procedure into 918 words in which 21 of 24
    steps said only "read the matching step in references/X.md and follow
    it". Attempt 2 ran on that table of contents. v2 and v3 kept their
    content inline only because their relocation passes FAILED, and attempt
    3 -- running on v2 -- produced a correct seven-item plan inside 14
    turns. The inline version demonstrably works and the relocated one
    demonstrably does not.

    WHAT THIS IS NOT. It is not a change to AIP, and not a cap on the
    author. The package stays exactly as AIP specifies -- the `references/`
    files are still written, still separate, still what gets validated,
    versioned and archived. This changes only the RENDERING handed to this
    model, at install time, and it is applied to warm in every attempt so
    it cannot skew one attempt against another.

    Idempotent, and a no-op when there is nothing to inline.
    """
    refs = sorted(r for r in files
                  if r.startswith("references/") and r.endswith(".md"))
    if not refs or "SKILL.md" not in files:
        return dict(files)
    body = files["SKILL.md"].decode("utf-8", "replace")
    if _INLINED_MARKER in body:
        return dict(files)
    parts = [body.rstrip(), "", _INLINED_MARKER, ""]
    for rel in refs:
        parts.append(f"### {rel}")
        parts.append("")
        parts.append(files[rel].decode("utf-8", "replace").strip())
        parts.append("")
    out = dict(files)
    out["SKILL.md"] = "\n".join(parts).encode("utf-8")
    return out


# Marks the appended block, so inlining twice is a no-op and so anyone
# reading a pod's SKILL.md can see at a glance that the tail is not the
# author's body.
_INLINED_MARKER = (
    "<!-- REFERENCE MATERIAL, INLINED AT INSTALL TIME. The files below are "
    "also present separately under references/ -- this copy exists because "
    "the model does not follow relative pointers. See "
    "agent_workspace.inline_references. -->")


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
    # Set by enable_memory() for warm agents; None means no relay in the
    # pipeline, which is what cold gets.
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
        memory_tools = {t for t in tools if "memor" in t.lower() or "step" in t.lower()
                        or "trace" in t.lower() or "graph" in t.lower()}
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

    def install_skill(self, files: dict[str, bytes], *, name: str,
                      version: int | None = None) -> dict[str, str]:
        """Install a whole AIP skill package where Vibe discovers it. Warm only.

        An AIP skill is a DIRECTORY, not a file: SKILL.md, `source/` with the
        bundled schema the validator resolves `schemaId` against, and
        optionally `scripts/`, `references/` and `assets/`. A procedure whose
        steps carry `script:` entries is useless if the scripts did not
        travel, and the failure is quiet -- the model reads a step it cannot
        perform and improvises.

        `$VIBE_HOME/skills/<name>/` is Vibe's own global skill path
        (GLOBAL_SKILLS_DIR in vibe/core/config/harness_files/_paths.py), and
        every agent already has its own VIBE_HOME -- so warm has a skill and
        cold has no directory to read one from. Same shape as the memory
        server: absent for cold, not gated.

        The tree is recreated, not overwritten. Vibe lists every skill it
        finds in the system prompt, so a stale version left beside the new
        one is offered to the agent as an alternative procedure, and a
        deleted file would otherwise live on forever.

        Everything is verified BY THE AGENT'S OWN USER, because that is the
        claim that matters: not "root wrote these bytes" but "the agent can
        read this file and execute that script". Returns
        {"dir": ..., "body": ...} -- hashes computed from the read-back, not
        from what was sent.

        `version` is recorded on the workspace so that every later report of
        "which skill did this attempt use" reads what is INSTALLED HERE
        rather than whichever version the local registry currently calls
        newest. Those two diverged silently: distillation bumped the
        registry between attempts while the pod kept the run's original
        directory, and the event log then credited results to a procedure
        the agent had never seen.
        """
        import posixpath
        if not files or "SKILL.md" not in files:
            # The tree is recreated below, so an empty package does not
            # fail to install -- it UNINSTALLS the skill and reports the
            # hash of nothing. Warm would then run the task with no
            # procedure at all while the log still named a version.
            raise ValueError(
                f"{self.label}: refusing to install a skill package with "
                f"{sorted(files)} in it. A skill is a directory containing "
                f"at least SKILL.md.")
        # The AUTHORED package is what identifies the version; the RENDERED
        # one is what the model reads. They differ only by the inlined
        # `references/` tail -- see inline_references() for why that tail
        # has to exist at all.
        canonical_body = files["SKILL.md"].decode("utf-8", "replace")
        canonical_digests = {rel: hashlib.sha256(data).hexdigest()
                             for rel, data in files.items()}
        files = inline_references(files)
        skills_root = f"{self.home}/.vibe/skills"
        target = f"{skills_root}/{name}"
        self.host.run_as(self.user, f"rm -rf {skills_root} && mkdir -p {target}",
                         check=False)
        for rel in sorted(files):
            dst = f"{target}/{rel}"
            parent = posixpath.dirname(dst)
            if parent != target:
                self.host.run_as(self.user, f"mkdir -p {shlex.quote(parent)}",
                                 check=False)
            # 0700/0600 rather than world-readable: the file is the agent's
            # own, and no other agent on this host has any business reading
            # another's procedure.
            self.host.put(files[rel], dst,
                          mode="700" if _is_script(rel) else "600",
                          owner=f"{self.user}:{self.user}")
        landed = self._skill_files_on_pod(target)

        missing = sorted(set(files) - set(landed))
        extra = sorted(set(landed) - set(files))
        differing = sorted(r for r in set(files) & set(landed)
                           if landed[r] != hashlib.sha256(files[r]).hexdigest())
        if missing or extra or differing:
            raise RuntimeError(
                f"{self.label}: the skill on the pod is not the skill that was "
                f"sent. missing={missing} unexpected={extra} "
                f"differing={differing}. The agent would run against an "
                f"unknown version."
            )
        for rel in sorted(files):
            if not _is_script(rel):
                continue
            ok = self.host.run_as(
                self.user,
                f"test -x {shlex.quote(target + '/' + rel)} && echo yes || echo no",
                check=False).stdout.strip()
            if not ok.endswith("yes"):
                raise RuntimeError(
                    f"{self.label}: skill script {rel!r} is not executable by "
                    f"the agent. An AIP step that runs it would fail, and the "
                    f"model would improvise around a step it cannot perform."
                )
        body = self.host.run_as(self.user, f"cat {target}/SKILL.md",
                                check=False).stdout
        # `body` identifies the VERSION, so it is hashed from the authored
        # text rather than the rendered one -- otherwise every install
        # would look like a mismatch against the version `propose`
        # accepted, and the run would print a version-mismatch warning on
        # every attempt. `body_rendered` is what the model actually read,
        # hashed from the read-back so it is evidence and not intent.
        # BOTH identity hashes are of the AUTHORED package, because both
        # answer "which version did this agent run against?" and the
        # rendering is not a version. That the rendering actually landed
        # byte-for-byte is already proved above, by the
        # missing/extra/differing check against the read-back -- so
        # reporting canonical here loses no integrity claim. The `*_rendered`
        # pair records what the model really read, hashed from the read-back
        # rather than from intent.
        shas = {"dir": _dir_sha(canonical_digests),
                "body": _body_sha(canonical_body),
                "dir_rendered": _dir_sha(landed),
                "body_rendered": _body_sha(body)}
        # Set only after every verification above has passed, so a failed
        # install leaves the previous version recorded rather than claiming
        # one that is not there.
        self.installed_skill_version = version
        self.installed_skill_sha = shas["body"]
        return shas

    def _skill_files_on_pod(self, target: str) -> dict[str, str]:
        """relative path -> sha256, as the AGENT sees them.

        Run as the agent user on purpose. Root can always read the files;
        whether the agent can is the actual question, and a directory the
        agent cannot traverse fails here rather than at the model's first
        attempt to use its own skill.
        """
        out = self.host.run_as(
            self.user,
            f"cd {shlex.quote(target)} && find . -type f -exec sha256sum {{}} + "
            f"2>/dev/null || true",
            check=False).stdout
        landed: dict[str, str] = {}
        for line in out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            digest, path = parts
            landed[path.removeprefix("./")] = digest
        return landed

    # ---- the distillation turn --------------------------------------------
    #
    # A SECOND, SEPARATE Vibe environment for the same agent: its own
    # VIBE_HOME, its own working directory, its own model endpoint.
    #
    # Separate VIBE_HOME because the neo4j-agent-memory MCP server lives
    # here and must not exist during an attempt -- that separation is the
    # whole reason KNOWN_ARM_DIFFERENCES is empty. It also has no skills
    # directory: a distiller that could invoke its own skill would be
    # reading its own output back as an instruction.
    #
    # Separate working directory because this Vibe has `write_file` and
    # `bash`. Pointed at the agent's checkout it would edit the code
    # between attempts, and the next grading run would score changes no
    # attempt made.
    #
    # Separate endpoint because distillation tokens are reported apart from
    # attempt tokens, and Vibe surfaces no per-call usage -- a third
    # counting proxy is the only place that number exists.

    @property
    def distill_home(self) -> str:
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
        self.assert_relay_delivers(sidecar_port)

    def assert_relay_delivers(self, sidecar_port: int) -> None:
        """Push one reasoning entry through the REAL relay and read it back.

        `assert_hook_runs` proves the hook can write a step. It does not
        prove the step will carry the model's reasoning, and those are
        different failures with identical symptoms: the relay never errors,
        it simply forwards nothing, `handle()` falls back to serialising the
        tool input, and `steps_written` climbs exactly as it should.

        That is what happened. Six pod runs on 2026-09-18/19 wrote 993 steps
        of which 988 held tool-argument JSON as their `thought`, so
        `search_steps` -- which embeds thought+action -- was searching a
        corpus of serialised arguments, and every skill from v25 to v45 was
        distilled from it. Nothing in the harness said a word.

        So: feed the relay one line of Vibe's own streaming format, as this
        agent's user, and require the sidecar's push counter to move. It
        exercises the relay binary that is actually on the host, over the
        loopback the hook uses, from the account Vibe runs as.
        """
        before = _sidecar_counter(self.host, sidecar_port, "reasoning_pushes")
        entry = json.dumps({
            "type": "reasoning",
            "turnId": "__probe__",
            "text": "probe: does the relay reach the sidecar",
        })
        self.host.run_as(
            self.user,
            f"printf %s\\\\n {shlex.quote(entry)} | "
            f"{HOOK_PYTHON} -u {RELAY_PATH} {sidecar_port} {self.label} "
            f">/dev/null",
            check=False, timeout=60)
        after = _sidecar_counter(self.host, sidecar_port, "reasoning_pushes")
        if after <= before:
            raise RuntimeError(
                f"{self.label}: the reasoning relay does not reach the "
                f"sidecar on :{sidecar_port} (pushes {before} -> {after}). "
                f"Every step would store its tool input as the agent's "
                f"thought, the graph would be searchable by what was typed "
                f"rather than by why, and nothing at run time would say so. "
                f"Check {RELAY_PATH} exists and is executable by "
                f"{self.user}.")
        # Leave no probe reasoning attached to the next real tool call.
        _sidecar_control(self.host, sidecar_port,
                         {"control": "note_turn", "agent": self.label,
                          "turn_id": "__probe_done__"})


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
        ])
        resume_arg = " --continue" if resume else ""
        vibe = (f"env {env} {TOOLCHAIN}/bin/vibe "
                f"--prompt {shlex.quote(prompt)}{resume_arg} "
                f"--auto-approve --trust --output streaming < /dev/null")
        workdir = cwd or self.repo_path
        # The relay belongs to the attempt path only. A distillation turn
        # writes nothing to the graph through a hook, so piping its stream
        # through the relay would forward reasoning to a sidecar that has
        # no trace to attach it to.
        if self.relay_port is None or cwd is not None:
            return f"cd {workdir} && {vibe}"
        # `pipefail` so the pipeline reports VIBE's exit code, not the
        # relay's -- `_ended_cleanly` keys on it, and a relay that always
        # exits 0 would make every attempt look like a clean stop.
        # `-u` so the relay does not buffer the stream behind Vibe.
        return (f"cd {workdir} && set -o pipefail && {vibe} "
                f"| {HOOK_PYTHON} -u {RELAY_PATH} {self.relay_port} {self.label}")

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


def _sidecar_control(host: "SwarmHost", port: int, request: dict) -> dict:
    """One control request to the sidecar, over the pod's own loopback.

    Runs `python3 -` on the host rather than forwarding a port: this is
    called during provisioning, before any tunnel exists, and the sidecar
    binds 127.0.0.1 on purpose.
    """
    script = (
        "import json,socket,sys\n"
        f"req={request!r}\n"
        "try:\n"
        f"    s=socket.create_connection(('127.0.0.1',{port}),timeout=10)\n"
        "    s.sendall((json.dumps(req)+'\\n').encode())\n"
        "    print(s.makefile().readline().strip())\n"
        "except Exception as e:\n"
        "    print(json.dumps({}))\n"
    )
    out = host.run(f"{HOOK_PYTHON} - <<'PYEOF'\n{script}\nPYEOF",
                   check=False, timeout=60).stdout or ""
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {}


def _sidecar_counter(host: "SwarmHost", port: int, field: str) -> int:
    try:
        return int(_sidecar_control(
            host, port, {"control": "summary"}).get(field) or 0)
    except (TypeError, ValueError):
        return 0
