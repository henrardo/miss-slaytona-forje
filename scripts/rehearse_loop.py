#!/usr/bin/env python3
"""Rehearse the whole warm loop locally, before any GPU is rented.

    scripts/rehearse_loop.py [--vibe PATH_TO_VIBE] [--keep]

WHY. Every plumbing bug this project has had was found on a rented GPU: a
hook with no shebang, an MCP client speaking the wrong HTTP dialect,
`tools` read instead of `tools_available`, a handler that raised inside its
own except clause, a read-only checkout that made thirteen graded attempts
meaningless. None of them needed a 119B model. Two H200s have now also been
lost overnight before running a single test, so GPU time is the scarcest
thing here and it should go on runs, not on plumbing.

So this drives the REAL loop -- `migrate_codebase`, unwrapped, the same
function the pod runs -- with three things swapped for local equivalents:

    the model    a scripted OpenAI-compatible server (tests/fake_model_server)
    the host     bash instead of ssh, a temp dir instead of /home/agent-*
    the grader   scripted pytest output instead of a Daytona sandbox

Everything else is the shipped code: real Vibe, real skill install, real
`/skill-name` loading, real stream parsing, real ingestion, real
distillation with its real validator, real metrics. If this passes, what
remains to be discovered on the pod is the model's behaviour -- which is
the only thing a pod is actually needed for.

THE GRAPH IS ALWAYS REAL. There is no stub and no fallback: if Aura is
not reachable the rehearsal FAILS. "Graph links were verified" means
nothing if the graph was a dictionary, and the previous version of this
file was worse than that -- its docstring claimed a conditional fallback
while the code used the recording stub unconditionally, so every graph
assertion here had been passing against an in-memory dict.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv

load_dotenv()

from orchestrator import distill as distill_mod
from orchestrator import metrics as metrics_mod
from orchestrator import series
from orchestrator import skills
from orchestrator import writers
from orchestrator.events import EventBus
from orchestrator.sync import AttemptSync
from orchestrator.vibe_agent import AttemptBudget, migrate_codebase
from swarm.agent_workspace import (AgentWorkspace, SwarmHost,
                                   inline_references)
from tests.fake_model_server import FakeModelServer, Turn


# --------------------------------------------------------------------------
# The three swaps
# --------------------------------------------------------------------------

class LocalHost(SwarmHost):
    """`SwarmHost` over bash, with /home/<user> mapped into a temp dir.

    Subclassed rather than reimplemented so that everything above it --
    install_skill's read-back, the fingerprint, the distillation
    environment -- is the code that runs on the pod, not a parallel copy.
    """

    def __init__(self, root: Path, vibe: Path, venv: Path,
                 model_url: str) -> None:
        super().__init__(host="local", port=0, identity=Path("/dev/null"))
        self.root, self.vibe, self.venv_path = root, vibe, venv
        # Passed explicitly, never taken from agent_workspace.MODEL_BASE_URL:
        # that is a DATACLASS DEFAULT, bound when the class was defined, so
        # patching the module attribute afterwards changes nothing and every
        # agent quietly dials 127.0.0.1:30000 instead. Cost the first
        # rehearsal run a 10-minute hang with four wedged Vibe processes.
        self.model_url = model_url

    def _map(self, command: str) -> str:
        """Rewrite pod paths into this tree. MUST BE IDEMPOTENT.

        Not all pod-shaped paths arrive pod-shaped. `MSF_RELAY_PATH` and
        `MSF_HOOK_PATH` are set to files ALREADY under this root, because
        Vibe executes those itself and never passes through here -- so
        `{root}/opt/swarm/reasoning_relay.py` reaches this method with the
        prefix on it. A blind `str.replace` added a second one.
        `/opt/swarm/` occurs in the relay's own argv, so the effect was:
        the relay failed to start, its end of `vibe | relay` closed, and
        VIBE DIED OF A BROKEN PIPE on its first tool call -- every attempt,
        warm only, silently. The graph stayed empty, no `post_tool` hook
        ever fired, and the visible symptom was "Vibe does not run hooks in
        this environment", which is a statement about Vibe and was false.
        Guarding the substitution is the whole fix.
        """
        root = re.escape(str(self.root))
        for pod in ("/home/", "/opt/swarm/"):
            # Anything already inside the root is left alone.
            command = re.sub(f"(?<!{root}){re.escape(pod)}",
                             f"{self.root}{pod}", command)
        # GNU coreutils flags the pod has and BSD/macOS does not. Shim-only
        # substitutions: the pod keeps the real command.
        return command.replace("base64 -w0", "base64")

    def run(self, command: str, *, timeout: float = 600.0, check: bool = True,
            **kw) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", "-lc", self._map(command)],
                              capture_output=True, text=True, timeout=timeout)

    def _as(self, agent_user: str, command: str) -> str:
        """Run as the agent would see it, with HOME pointed at its own tree.

        On the pod this is `su - <agent>`, so `~` is the agent's home and
        the transcript dump (`~/.vibe/logs/session/*`) resolves correctly.
        Locally there is no su, and without this `~` expands to the
        OPERATOR's home: the dump then reads my own Vibe sessions, finds no
        assistant turn for the attempt, and every attempt aborts. Nine
        attempts ran and none completed before this was set.
        """
        # UNMAPPED on purpose: `_map` rewrites every "/home/" once, so
        # building the real path here would prefix the root twice and every
        # `cd` would fail into a directory that does not exist.
        home = f"/home/{agent_user}"
        return f"export HOME={home}; cd {home}; " + command

    def run_as(self, agent_user: str, command: str, **kw):
        return self.run(self._as(agent_user, command), **kw)

    def argv(self, command: str) -> list[str]:
        return ["bash", "-lc", self._map(command)]

    def argv_as(self, agent_user: str, command: str) -> list[str]:
        return self.argv(self._as(agent_user, command))

    def put(self, data: bytes, dst: str, *, mode: str = "600",
            owner: str | None = None) -> None:
        path = Path(self._map(dst))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(int(mode, 8))

    def gpu_description(self) -> str:
        return "none (local rehearsal)"


class LocalWorkspace(AgentWorkspace):
    """AgentWorkspace pointed at a local tree and a local Vibe."""

    def _vibe_command(self, prompt: str, *, resume: bool,
                      vibe_home: str | None = None,
                      cwd: str | None = None) -> str:
        home = vibe_home or f"{self.home}/.vibe"
        workdir = cwd or self.repo_path
        vibe = (f"{self.host.vibe} --prompt {shlex.quote(prompt)} "
                f"--auto-approve --trust --output streaming < /dev/null")
        # THE REASONING RELAY, exactly as production splices it. Omitting
        # it here is why `thought` came back holding serialised tool input:
        # with no relay the hook has no reasoning to attach and falls back
        # to the tool's arguments, which is the precise bug the relay was
        # written to fix -- and this override was quietly not testing it.
        if self.relay_port is not None and cwd is None:
            from swarm.agent_workspace import HOOK_PYTHON, RELAY_PATH
            # `pipefail` so the pipeline reports VIBE's exit code, not the
            # relay's -- `_ended_cleanly` keys on it.
            return (f"cd {workdir} && set -o pipefail && "
                    f"VIBE_HOME={home} {vibe} "
                    f"| {HOOK_PYTHON} -u {RELAY_PATH} {self.relay_port} "
                    f"{self.label}")
        return f"cd {workdir} && VIBE_HOME={home} {vibe}"

    def install_dependencies(self, install_command: str, **kw):
        return subprocess.CompletedProcess([], 0, "", "")

    @property
    def venv(self) -> str:
        return str(self.host.venv_path)


@dataclass
class ScriptedResult:
    """Mirrors orchestrator.sandbox.SandboxResult field for field.

    A shim that is missing a field fails at the first `emit` that reads it,
    ~200 lines into the attempt loop, which is a slow way to learn that the
    grader's contract has three members and not two.
    """
    exit_code: int
    output: str
    create_ms: float = 0.0


class ScriptedPool:
    """The grader, scripted. One verdict per call, last one repeats."""

    def __init__(self, verdicts: list[tuple[int, str]]) -> None:
        self.verdicts = verdicts
        self.calls = 0

    async def run_pytest(self, *, file_contents, test_command, cwd="/repo"):
        code, output = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return ScriptedResult(code, output)


class _SidecarClient:
    """What the attempt loop talks to, mirroring RemoteTraceBridge.

    Production reaches the sidecar over SSH; here it is a loopback socket
    to a separate process. Same control protocol either way, so the
    rehearsal exercises the real message shapes rather than method calls
    on an object that happens to be in scope.
    """

    def __init__(self, port: int) -> None:
        self._port = port

    def _ask(self, payload: dict) -> dict:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", self._port), 10) as s:
                s.sendall((json.dumps(payload) + "\n").encode())
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
            return json.loads(buf.decode() or "{}")
        except Exception:
            return {}

    def set_trace(self, agent: str, trace_id) -> None:
        self._ask({"control": "set_trace", "agent": agent,
                   "trace_id": str(trace_id)})

    def clear_trace(self, agent: str) -> None:
        self._ask({"control": "clear_trace", "agent": agent})

    def set_pending_reasoning(self, agent, text, turn_id=None) -> None:
        return None

    def note_turn(self, agent, turn_id) -> None:
        return None

    def flush(self) -> bool:
        return True

    @property
    def steps_written(self) -> int:
        try:
            return int(self._ask({"control": "summary"}).get("steps_written") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def errors(self) -> int:
        return self.counter("errors")

    def counter(self, field: str) -> int:
        """Any of the sidecar's tallies, over the same control channel.

        `thoughts_from_reasoning` / `thought_fallbacks` in particular: on
        the live-hook path they are the ONLY record of whether the relay
        delivered, and asking the service object for them is not available
        here -- it is in another process, exactly as on the pod.
        """
        try:
            return int(self._ask({"control": "summary"}).get(field) or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def thoughts_from_reasoning(self) -> int:
        return self.counter("thoughts_from_reasoning")

    @property
    def thoughts_from_tool_input(self) -> int:
        return self.counter("thought_fallbacks")

    @property
    def reasoning_pushes(self) -> int:
        return self.counter("reasoning_pushes")


# RecordingMemory DELETED. It was a graph in a dictionary, used
# unconditionally while the docstring claimed it was a fallback,
# so every graph assertion in this file passed without Aura ever
# being contacted. The rehearsal now aborts instead.
# --------------------------------------------------------------------------
# The script the fake model follows
# --------------------------------------------------------------------------

def attempt_turns(*, edit: bool, finish_text: str) -> list[Turn]:
    """One attempt's worth of model behaviour.

    TWO SHAPES, because the production model does not use the one this
    file used to script. Measured directly against Mistral-Small-4-119B on
    SGLang 0.5.14: `reasoning_content` comes back **None** and the model's
    reasoning arrives as ordinary assistant `content` --

        "The user is experiencing a PydanticUserError related to const..."

    -- alongside the tool call it justifies. Every turn here used to carry
    `reasoning=`, so the rehearsal exercised only the hybrid channel, the
    relay's `type == "reasoning"` filter passed 56/56 locally, and on the
    pod it forwarded nothing: 27 of 27 steps stored serialised tool input.
    A fixture I wrote, validating my implementation against my own
    assumption rather than against the model.

    So: turn 1 is CONTENT-ONLY (the production shape), and the rest keep a
    separate reasoning channel (the hybrid shape). Both must reach the
    graph as a thought.
    """
    turns = [
        # Content-only. No `reasoning=` on purpose -- this is Mistral-Small-4.
        Turn(text="The repo fails to import. I should see what is in it "
                  "before changing anything.",
             tools=[("bash", {"command": "ls -la"})]),
    ]
    if edit:
        turns.append(Turn(
            reasoning="config.py imports BaseSettings from pydantic. That "
                      "moved. I will change the import.",
            text="Editing config.py.",
            tools=[("write_file", {"file_path": "config.py",
                                   "content": "VALUE = 2\n"})]))
    turns.append(Turn(reasoning="I have made the change I intended.",
                      text=finish_text))
    return turns


VALID_SKILL = """---
name: pydantic-v2-migration
description: A procedure distilled from my own graded attempts at migrating a codebase to Pydantic v2.
metadata:
  aip:
    spec: "{spec}"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: {version}
    derived_from_traces: []
---

```yaml
purpose: >
  Migrate a codebase to Pydantic v2 so its own suite passes.
trigger_when:
  - Asked to migrate a codebase to Pydantic v2
steps:
  - name: read-the-first-error
    description: Run the suite and work the first failure, not the last.
  - name: change-one-thing
    description: Make one change, then re-run, so a regression is attributable.
```
"""

INVALID_SKILL = "Here is my improved skill!\n\nIt has no frontmatter at all.\n"


def external_distill_turns(*, first: str, then: str | None = None) -> list[Turn]:
    """Distillation as the EXTERNAL writer sees it.

    `ExternalWriter` has no tools and no filesystem: it reads
    `choices[0].message.content` and that string IS the proposed
    SKILL.md. The agent-writer script below drives `write_file` tool
    calls instead, which this writer ignores entirely -- so scripting
    only that one made every distillation return an empty proposal and
    the rehearsal reported "the distiller wrote nothing".
    """
    turns = [Turn(text=first)]
    if then is not None:
        turns.append(Turn(text=then))
    return turns


def distill_turns(out_path: str, *, first: str,
                  then: str | None = None) -> list[Turn]:
    """A distillation turn writes a file; a repair turn writes another.

    `out_path` must be ABSOLUTE: Vibe's WriteFileArgs.file_path is
    documented "must be absolute, not relative", and a relative one fails
    validation silently -- the tool errors, the file keeps its old
    contents, and the next thing anyone sees is the distiller rejected for
    proposing version 0 again. The real prompt hands the model an absolute
    path already; this makes the rehearsal match it.
    """
    turns = [Turn(reasoning="What did I try before, and what failed?",
                  text="Checking my past attempts.",
                  tools=[("neo4j-agent-memory_search_steps",
                          {"query": "pydantic migration failure"})]),
             Turn(reasoning="Now I will write the improved procedure.",
                  text="Writing the skill.",
                  tools=[("write_file", {"file_path": out_path,
                                         "content": first})]),
             # A turn with no tools ENDS the invocation. The repair loop is
             # a second invocation, not two turns of one -- so the script
             # has to stop here or both writes land in the same turn and
             # the second fails against the file the first just created.
             Turn(text="Written.")]
    if then is not None:
        turns += [
            Turn(reasoning="It was rejected. The validator says what is wrong.",
                 text="Fixing the format.",
                 tools=[("write_file", {"file_path": out_path,
                                        "content": then})]),
            Turn(text="Fixed."),
        ]
    return turns


# --------------------------------------------------------------------------

# The whole rehearsal is scripted, so anything slow is a bug in it.
REHEARSAL_DEADLINE_S = 300.0

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}"
          + (f"  -- {detail}" if detail and not ok else ""))


def _tamper_is_caught(aw, host, relay: Path) -> bool:
    """Require the installer to refuse when the write does not land.

    NOT a staleness test, and it matters to be precise about which
    property is being bought. The installer OVERWRITES from the repo on
    every run, so a stale file is impossible by construction; what the
    sha256 read-back catches is the write silently not arriving -- a
    refused path, a truncated transfer, a `put` that reported success and
    did nothing. That failure is invisible otherwise: the relay keeps
    running whatever was there before.

    Simulated by neutering `put`, because there is no way to make a real
    transfer half-fail on demand. Restored afterwards, whatever happens.
    """
    original = relay.read_bytes()
    real_put = host.put
    try:
        host.put = lambda *a, **kw: None          # the write goes nowhere
        relay.write_bytes(b"# not the relay\n")   # what was there before
        try:
            aw.install_host_scripts(host)
        except RuntimeError:
            return True
        return False
    finally:
        host.put = real_put
        relay.write_bytes(original)


async def rehearse(vibe: Path, root: Path, model_url: str,
                   server: FakeModelServer, mem) -> int:
    host = LocalHost(root, vibe, vibe.parent, model_url)
    host.server = server
    bus = EventBus(f"rehearsal-{int(time.time())}")

    spaces = {}
    for label in ("warm-0", "cold-0"):
        ws = LocalWorkspace(host=host, label=label, model="fake-model",
                            model_base_url=model_url)
        (root / f"home/agent-{label}").mkdir(parents=True, exist_ok=True)
        repo = root / f"home/agent-{label}/repo"
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "config.py").write_text("VALUE = 1\n")
        ws.write_config(web_url=None)
        spaces[label] = ws

    # ---- 0a. THE LIVE WRITE PATH: Vibe -> post_tool hook -> sidecar -> Aura
    #
    # This is the one thing the rehearsal never covered, and it is the
    # thing that matters: the graph is supposed to be written BY VIBE while
    # the agent works, not reconstructed from a transcript afterwards.
    # Every check in this file passed for weeks while that path was
    # disconnected.
    print("... starting the step-memory sidecar", flush=True)
    (root / "opt" / "swarm").mkdir(parents=True, exist_ok=True)
    # THE PRODUCTION INSTALLER, not a shutil.copy standing in for it.
    #
    # This block used to copy the two files itself. That is precisely the
    # bug it was meant to be testing: nothing in the repo put hook.py or
    # reasoning_relay.py on a pod, they were hand-scp'd, and the rehearsal
    # hand-copying them too meant the gap was invisible from both ends.
    # `install_host_scripts` is now what the pod uses AND what runs here,
    # digest check included.
    local_hook = root / "opt" / "swarm" / "hook.py"
    local_relay = root / "opt" / "swarm" / "reasoning_relay.py"
    # Vibe runs these two commands itself, so LocalHost's path mapping
    # cannot reach them -- they must be absolute in this tree before the
    # installer reads where to put them.
    os.environ["MSF_HOOK_PATH"] = str(local_hook)
    os.environ["MSF_RELAY_PATH"] = str(local_relay)
    import swarm.agent_workspace as _aw
    _aw.HOOK_PATH = str(local_hook)
    _aw.RELAY_PATH = str(local_relay)
    installed = _aw.install_host_scripts(host)
    # BOTH halves, counted separately. `host_scripts` is what Vibe and the
    # provisioners execute; `host_modules` is the sidecar and the
    # orchestrator modules it imports. The sidecar was the half that was
    # still hand-copied after the 2026-09-19 installer fix, and it stayed
    # invisible because this check only ever counted `host_scripts`.
    expected = len(_aw.host_scripts()) + len(_aw.host_modules())
    check("the harness installs its own scripts and verifies the digests",
          local_hook.is_file() and local_relay.is_file()
          and len(installed) == expected,
          f"{len(installed)}/{expected} file(s): "
          + ", ".join(f"{Path(p).name} {d[:8]}" for p, d in installed.items()))
    check("the sidecar and the modules it imports are installed by code",
          all(any(Path(p).name == Path(remote).name for p in installed)
              for remote, _ in _aw.host_modules().values()),
          "provision_memory.sh runs /opt/swarm/swarm/sidecar_main.py and "
          "imports orchestrator.step_memory from PYTHONPATH=/opt/swarm; "
          "nothing put either there, so every pod that worked had been "
          "hand-copied and no version of the sidecar could be established")
    check("a script that did not land is caught, not assumed",
          _tamper_is_caught(_aw, host, local_relay),
          "the sha256 is read back OFF THE HOST; a relay whose upload "
          "silently failed keeps running whatever was there before, and "
          "forwards nothing while every counter looks healthy")

    # A SEPARATE PROCESS, as on the pod. Run in-process, the sidecar shares
    # this event loop with the rehearsal, so Vibe's hook competes with
    # whatever the loop is doing and its 8s timeout fires at random -- the
    # live-write check went 3 steps, then 1, then 0 across identical runs.
    # That flakiness is the harness's, not the system's, and it would have
    # been reported as "the hook is unreliable".
    import socket as _socket
    with _socket.socket() as _s:
        _s.bind(("127.0.0.1", 0))
        sidecar_port = _s.getsockname()[1]
    sidecar_proc = await asyncio.create_subprocess_exec(
        sys.executable, str(REPO / "swarm" / "sidecar_main.py"),
        "--port", str(sidecar_port), "--agents", "warm-0",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": str(REPO)})
    for _ in range(60):
        await asyncio.sleep(0.5)
        with contextlib.suppress(OSError):
            with _socket.create_connection(("127.0.0.1", sidecar_port), 1):
                break
    if sidecar_proc.returncode is not None:
        died = (await sidecar_proc.stdout.read()).decode(errors="replace")
        died = "\n".join(died.splitlines()[-6:])
        print(f"      sidecar died:\n{died}")
    check("the sidecar is listening", sidecar_proc.returncode is None,
          f"port {sidecar_port}, pid {sidecar_proc.pid}, "
          f"rc={sidecar_proc.returncode}")

    service = _SidecarClient(sidecar_port)

    # DIRECTLY invoke the hook the way Vibe does, before any agent runs.
    # The hook fails open on everything -- a refused connection prints {}
    # and exits 0 -- so "the hook ran" and "the hook reached the sidecar"
    # are different facts and only the second one matters.
    probe_trace = await mem.start_trace(f"{bus.run_id}:warm-0", "probe")
    service.set_trace("warm-0", getattr(probe_trace, "id", probe_trace))
    before = service.steps_written
    probe_in = json.dumps({
        "hook_event_name": "post_tool", "tool_name": "bash",
        "tool_input": {"command": "echo hi"}, "tool_output_text": "hi",
        "tool_status": "success",
    })
    # ASYNC subprocess: a blocking one would freeze this loop, and with an
    # in-process sidecar that froze the very server the hook was dialling.
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/python3", str(local_hook), str(sidecar_port), "warm-0",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(
        proc.communicate(probe_in.encode()), timeout=30)
    await asyncio.sleep(2.0)
    check("the hook can reach the sidecar and write a step",
          proc.returncode == 0 and service.steps_written > before,
          f"rc={proc.returncode} stdout={out[:60]!r} stderr={err[:120]!r} "
          f"steps {before}->{service.steps_written} errors={service.errors}")

    # ---- 0. there is NO rollback, and no way back to one ------------------
    #
    # This used to assert that the best-tree rollback worked. It did work,
    # and that was the problem: keyed on `tests_passed`, it fired twice in
    # the 2026-09-18/19 series and both times discarded warm's most complete
    # migration for a barely-migrated tree that happened to import. The
    # operator never asked for it. The check is now the other way round.
    print("... checking that attempts continue rather than reset", flush=True)
    probe = spaces["warm-0"]
    check("the workspace offers no checkpoint or rollback",
          not any(hasattr(probe, name) for name in
                  ("checkpoint", "restore_best", "init_history")),
          "a Workspace with these grows a rollback again the moment "
          "something calls hasattr() on it -- which is how the last one "
          "was wired in")
    # The tree an attempt leaves behind is the tree the next one starts
    # from, mistakes included. Proven rather than asserted: write a file,
    # and require nothing in the harness to take it away.
    scratch = f"{probe.repo_path}/continuity_probe.py"
    probe.host.run_as(probe.user, f"echo 'x = 1' > {scratch}", check=False)
    check("an attempt's edits survive in the checkout",
          probe.host.run_as(probe.user, f"cat {scratch}",
                            check=False).stdout.strip() == "x = 1")
    probe.host.run_as(probe.user, f"rm -f {scratch}", check=False)

    # ---- 1. install the whole skill package, verified as the agent -------
    print("... installing the skill package", flush=True)
    live = skills.current()
    installed = spaces["warm-0"].install_skill(live.files,
                                               name=skills.SKILL_NAME,
                                               version=live.version)
    check("skill package installs and reads back",
          installed["dir"] == live.dir_sha and installed["body"] == live.body_sha,
          f"{installed} vs dir={live.dir_sha} body={live.body_sha}")
    # AIP'S SECOND TIER, on the pod. The relocation pass produces packages
    # with a `references/` subdirectory, and nothing had ever installed
    # one -- every skill v0..v45 was SKILL.md plus source/. If the
    # read-back verification does not recurse, the FIRST distillation of
    # the real run raises "the skill on the pod is not the skill that was
    # sent" and warm loses its procedure mid-run.
    with_refs = dict(live.files)
    with_refs["references/probe-detail.md"] = b"# detail\nRead when X.\n"
    tiered = spaces["warm-0"].install_skill(
        with_refs, name=skills.SKILL_NAME, version=live.version)
    ref_body = spaces["warm-0"].host.run_as(
        spaces["warm-0"].user,
        f"cat {spaces['warm-0'].home}/.vibe/skills/{skills.SKILL_NAME}"
        f"/references/probe-detail.md", check=False).stdout
    check("a package with a references/ tier installs and verifies",
          "Read when X." in ref_body and tiered["dir"] != live.dir_sha,
          f"the agent reads {len(ref_body)} byte(s) back from references/")
    # Put the real package back: everything downstream compares against it.
    spaces["warm-0"].install_skill(live.files, name=skills.SKILL_NAME,
                                   version=live.version)
    check("warm has a skills directory", spaces["warm-0"].has_skills_dir())

    # hooks.toml + the MCP registration, exactly as run.py does it. The MCP
    # url is deliberately unreachable here: this check is about the WRITE
    # path, and an unreachable MCP server must not stop the hook firing.
    spaces["warm-0"].enable_memory(mcp_url="http://127.0.0.1:1/mcp",
                                   sidecar_port=sidecar_port)
    hooks_present = spaces["warm-0"].host.run_as(
        spaces["warm-0"].user,
        f"test -f {spaces['warm-0'].home}/.vibe/hooks.toml && echo yes || echo no",
        check=False).stdout.strip()
    check("warm got a hooks.toml", hooks_present.endswith("yes"))
    # DOES VIBE FIRE post_tool AT ALL HERE? A canary hook that only
    # touches a file, so "the memory hook is broken" and "Vibe never ran
    # any hook" stop being the same observation.
    canary = root / "canary.txt"
    ws0 = spaces["warm-0"]
    canary_toml = (
        "[[hooks]]\n"
        'name = "canary"\n'
        'type = "post_tool"\n'
        f'command = "/bin/sh -c \'echo fired >> {canary}\'"\n'
        'match = "*"\n'
        "timeout = 10.0\n\n"
    )
    for target in (f"{ws0.home}/.vibe/hooks.toml",
                   f"{ws0.repo_path}/.vibe/hooks.toml"):
        ws0.host.run_as(ws0.user, f"cat >> {target} <<'EOF'\n{canary_toml}EOF",
                        check=False)
    # What Vibe will actually try to execute, and whether it exists here.
    ws0 = spaces["warm-0"]
    toml_txt = ws0.host.run_as(
        ws0.user, f"cat {ws0.home}/.vibe/hooks.toml", check=False).stdout
    cmdline = next((l.split("=", 1)[1].strip().strip('"')
                    for l in toml_txt.splitlines()
                    if l.startswith("command")), "")
    print(f"      hook command: {cmdline}")
    interp, script = (cmdline.split() + ["", ""])[:2]
    for what, path in (("interpreter", interp), ("hook script", script)):
        # Already absolute-and-local once MSF_HOOK_PATH is set; only map
        # the pod-shaped path.
        mapped = (path if Path(path).exists()
                  else path.replace("/opt/swarm/", f"{root}/opt/swarm/"))
        ok = Path(mapped).exists()
        check(f"the hook's {what} exists where Vibe will look", ok,
              f"{mapped}")
    check("cold got NO hooks.toml",
          spaces["cold-0"].host.run_as(
              spaces["cold-0"].user,
              f"test -f {spaces['cold-0'].home}/.vibe/hooks.toml "
              f"&& echo yes || echo no",
              check=False).stdout.strip().endswith("no"))
    check("cold has NO skills directory",
          not spaces["cold-0"].has_skills_dir())

    # ---- 2. arm parity ----------------------------------------------------
    print("... building the distillation environment", flush=True)
    spaces["warm-0"].enable_distillation(
        mcp_url="http://127.0.0.1:1/mcp", model_base_url=host.model_url)
    for ws in spaces.values():
        probe = ws.invoke_vibe("Reply with the single word: ready", timeout=120.0)
        if not ws.loaded_tools():
            # Say why, immediately. "0 tools" with no explanation is the
            # exact shape of run 9, which took a day to diagnose.
            print(f"    {ws.label} probe rc={probe.returncode}")
            print(f"    stdout: {(probe.stdout or '')[:300]}")
            print(f"    stderr: {(probe.stderr or '')[-600:]}")
    print("... fingerprinting both arms", flush=True)
    warm_fp = spaces["warm-0"].setup_fingerprint()
    cold_fp = spaces["cold-0"].setup_fingerprint()
    differences = {k: (warm_fp[k], cold_fp[k]) for k in warm_fp
                   if warm_fp[k] != cold_fp[k]}
    # Warm writes the graph natively, so it HAS extra config and hooks.
    # Those are declared in run.py's KNOWN_ARM_DIFFERENCES and printed on
    # every run. Anything outside that set is a confound nobody chose.
    from swarm.run import KNOWN_ARM_DIFFERENCES
    undeclared = set(differences) - set(KNOWN_ARM_DIFFERENCES)
    check("arms differ ONLY in the declared ways", not undeclared,
          f"undeclared: {sorted(undeclared)} "
          f"(declared: {sorted(KNOWN_ARM_DIFFERENCES)})")
    check("both arms loaded the same tools",
          warm_fp["tools"] == cold_fp["tools"] and bool(warm_fp["tools"]),
          f"warm={len(warm_fp['tools'])} cold={len(cold_fp['tools'])}")
    check("only WARM has a post_tool hook",
          bool(warm_fp["hook_files"]) and not cold_fp["hook_files"],
          f"warm={warm_fp['hook_files']} cold={cold_fp['hook_files']}")

    # ---- 3. the real attempt loop ----------------------------------------
    # Ordered log of what each arm was doing when, so the rehearsal can
    # assert that no distillation overlapped the other arm's attempt.
    timeline: list[tuple[str, str, float]] = []

    def mark(what: str, who: str) -> None:
        timeline.append((what, who, time.monotonic()))

    # prov_fixture TOO, exactly as swarm/run.py stamps it. Without it the
    # rehearsal's traces carry no fixture, `distill()` filters eligible
    # traces on `fixture=FIXTURE_DIR.name`, and the writer is handed an
    # empty corpus -- "(none yet -- this is the first attempt on this
    # harness)" -- on every distillation. That was true for every
    # rehearsal ever run and invisible, because the only check on the
    # evidence path asserted the AGENT writer's tool calls, which the
    # scripted model always made.
    from orchestrator.manifest import FIXTURE_DIR
    mem.set_provenance(prov_model="fake-model", prov_gpu="none",
                       prov_commit="local", prov_writable=True,
                       prov_fixture=FIXTURE_DIR.name)

    # Which TRACES this rehearsal created. Not sessions: every trace in
    # this database shares the session id "warm-0", so a session filter
    # selects all 98 runs of history and the assertions fail on the Qwen
    # era rather than on anything here.
    rehearsal_traces: set[str] = set()
    _real_start_trace = mem.start_trace

    async def _tracking_start_trace(session_id, task):
        trace = await _real_start_trace(session_id, task)
        if trace is not None:
            rehearsal_traces.add(str(getattr(trace, "id", trace)))
        return trace

    mem.start_trace = _tracking_start_trace
    distilled: list[distill_mod.DistillResult] = []

    # THE REAL ExternalWriter, against the fake OpenAI-compatible server.
    #
    # This is the production default now (`--distill-writer` ->
    # OPENAI_AUTHOR), and until this line the rehearsal only ever
    # exercised AgentWriter -- so the default path had no pre-pod
    # coverage at all. Both bugs that cost pod runs on 2026-09-18 were in
    # code the rehearsal could not reach, and shipping an untestable
    # default is that mistake with a different name.
    #
    # `base_url` points THIS writer at the scripted server -- a parameter,
    # not an env var: the OpenAI SDK's own `OPENAI_BASE_URL` would also
    # redirect neo4j-agent-memory's extractor and embedder, which it did,
    # and the run died in add_message. The key is a placeholder the fake
    # server ignores. Everything else -- the
    # prompt, the AIP procedure it carries, `strip_fence`, the usage
    # counters, the repair loop -- is the shipped code.
    external = writers.ExternalWriter(
        model="fake-model", api_key="rehearsal",
        base_url=model_url.rstrip("/") + "/v1")

    async def distiller(*, attempt, tests_passed, suite_passed, error):
        mark("distil-start", "warm-0")
        result = await distill_mod.distill(
            workspace=spaces["warm-0"], mem=mem, model="fake-model",
            attempt=attempt, tests_passed=tests_passed,
            suite_passed=suite_passed, error=error, writer=external)
        distilled.append(result)
        # The same install-after-accept that run.py does, and for the same
        # reason: `propose` moves the live pointer on this machine, the
        # agent reads its own $VIBE_HOME. Rehearsing the loop without this
        # rehearses a loop that cannot close.
        if result.accepted is not None:
            spaces["warm-0"].install_skill(result.accepted.files,
                                           name=skills.SKILL_NAME,
                                           version=result.accepted.version)
        mark("distil-end", "warm-0")
        return result

    def emit_for(arm: str, label: str):
        async def emit(event_type, **kw):
            if event_type in ("ATTEMPT_START", "ATTEMPT_DONE"):
                mark(event_type.lower().replace("_", "-"), label)
            return await bus.emit(event_type, swarm=arm, agent=label, **kw)
        return emit

    # Attempt 1 fails, attempt 2 passes. The first distillation writes an
    # invalid skill then repairs it; the second writes a valid one.
    pool = ScriptedPool([
        (1, "E   ImportError: cannot import name 'BaseSettings'\n"
            "=== 8 passed, 25 failed in 1.2s ==="),
        (0, "=== 33 passed in 1.4s ==="),
    ])
    # The absolute path the distiller is told to write, as the agent's own
    # shell sees it.
    out_path = str(root) + spaces["warm-0"].distill_skill_path()
    # RELATIVE to whatever the copied package starts at. The rehearsal runs
    # against a copy of the REAL skill, which advances with every run, so
    # hard-coded version numbers rot the moment the agent distils.
    v0 = skills.current().version
    # ONE ATTEMPT SCRIPT PER ARM, not one shared between them.
    #
    # A script repeats its final turn once exhausted (FakeModelServer's own
    # documented behaviour), and the two arms run CONCURRENTLY against the
    # same server. With a single "attempt" script they drained one index
    # together: cold reached it first and consumed the turns that make tool
    # calls, and warm was served the terminal turn on both its attempts.
    # Warm therefore made ZERO tool calls, so no `post_tool` event existed,
    # so its hook never fired and nothing was written to the graph live --
    # which read as "Vibe does not fire hooks in this environment" and cost
    # a session chasing Vibe. The arms must not share a queue for the same
    # reason they must not share anything else.
    #
    # Routed on the agent's own directory, which Vibe puts in the system
    # prompt ("absolute path: /home/agent-<label>/repo"), so the route is
    # read off what the agent actually is rather than off turn order.
    host.server.scripts = {
        "attempt-warm-0": (
            attempt_turns(edit=True, finish_text="I changed the import.")
            + attempt_turns(edit=True,
                            finish_text="The migration is complete.")),
        "attempt-cold-0": (
            attempt_turns(edit=True, finish_text="I changed the import.")
            + attempt_turns(edit=True,
                            finish_text="The migration is complete.")),
        # The external writer is the production default, so the scripts
        # are written for it: one turn, the body as the reply.
        "distil-1": external_distill_turns(
            first=INVALID_SKILL,
            then=VALID_SKILL.format(spec=skills.aip_spec_url(), version=v0 + 1)),
        "distil-2": external_distill_turns(
            first=VALID_SKILL.format(spec=skills.aip_spec_url(), version=v0 + 2)),
        # `loaded_tools()` makes a real Vibe call per arm before the clock
        # so the two tool lists can be compared. It runs in the agent's own
        # home, so it looks exactly like that arm's attempt unless it is
        # routed out -- and it would eat the first turn of the script.
        "probe": [Turn(text="ready")],
    }
    host.server._indices = {k: 0 for k in host.server.scripts}

    distil_calls = {"n": 0}

    last_distil = {"key": "distil-1"}

    def route(body: dict) -> str:
        text = json.dumps(body.get("messages") or [])
        # Match on a marker BOTH the first distillation prompt and its
        # repair prompts carry. It used to be the output path, which only
        # works for the agent writer -- `ExternalWriter.out_path()` is the
        # prose "the improved SKILL.md", not a filesystem path, so every
        # distillation call routed to an attempt queue instead.
        # `<aip_skill>` is in the build prompt and `metadata.aip.version`
        # in the repair prompt; neither appears in an attempt.
        if "Reply with the single word: ready" in text:
            return "probe"
        is_distil = ("<aip_skill>" in text
                     or "The procedure you wrote was rejected" in text)
        if not is_distil:
            # Whose attempt is this? The agent's checkout is named in the
            # system prompt. Unroutable would silently fall back to one
            # arm's queue, which is the bug this replaced, so it raises.
            for label in ("warm-0", "cold-0"):
                if f"agent-{label}" in text:
                    return f"attempt-{label}"
            raise RuntimeError(
                "a model call could not be attributed to an arm: no "
                "agent-<label> path in the prompt. Serving it from either "
                "arm's queue would drain the other's.")
        if "attempt 2" in text:
            last_distil["key"] = "distil-2"
        elif "attempt 1" in text:
            last_distil["key"] = "distil-1"
        # A repair prompt names neither attempt: it continues whichever
        # distillation is in progress.
        return last_distil["key"]

    host.server.router = route

    print("... running the real attempt loop", flush=True)
    # BASELINE THE SIDECAR'S COUNTERS. They are cumulative and outlive a
    # single run -- the same odometer trap NOTES-hard-won.md records
    # against the proxies -- and the probes above deliberately wrote steps
    # with no Vibe in the picture, so those legitimately fell back. Only
    # the delta across the attempts says whether the relay delivered.
    thoughts_before = service.thoughts_from_reasoning
    fallbacks_before = service.thoughts_from_tool_input
    # BOTH arms, through the real loop, sharing one barrier -- the
    # arrangement the pod runs, and the only way to test the ordering.
    sync = AttemptSync(["warm-0", "cold-0"])
    cold_pool = ScriptedPool([
        (1, "E   ImportError: cannot import name 'BaseSettings'\n"
            "=== 5 passed, 28 failed in 1.1s ==="),
        (1, "=== 9 passed, 24 failed in 1.2s ==="),
        (1, "=== 11 passed, 22 failed in 1.2s ==="),
    ])

    # THE EXPERIMENT: a fixed number of attempts on one checkout, per agent.
    #
    # DELIBERATELY UNEQUAL. The arms get their own budgets in production
    # (one AttemptBudget per agent), and giving cold one more here is what
    # keeps "cold kept working after warm left" testable. That check used
    # to rely on the clock: warm pays ~3.3s per tool call for the hook, so
    # cold simply fitted more attempts into the same deadline. Now that
    # attempts are counted rather than timed, both arms would do exactly N
    # and the check would pass for no reason -- it would stop guarding the
    # barrier and start restating the budget.
    ATTEMPTS = {"warm-0": 2, "cold-0": 3}
    budgets = {label: AttemptBudget(n) for label, n in ATTEMPTS.items()}
    trees: dict[str, list[int]] = {"warm-0": [], "cold-0": []}

    def tree_sink(label: str):
        # Records that a tree was offered per attempt, without writing
        # 640 KB per attempt into a temp dir the rehearsal then deletes.
        def sink(attempt: int, file_contents: dict) -> None:
            assert file_contents, "an attempt handed the archive an empty tree"
            trees[label].append(attempt)
        return sink

    async def run_arm(label: str, warm: bool):
        try:
            return await migrate_codebase(
                pool=(pool if warm else cold_pool),
                workspace=spaces[label], test_command="pytest -q",
                # Short: a rehearsal that can spin for half an hour is a
                # rehearsal nobody runs. Scripted attempts need seconds.
                deadline=time.monotonic() + REHEARSAL_DEADLINE_S,
                emit=emit_for("warm" if warm else "cold", label),
                mem=mem if warm else None,
                session_id=f"{bus.run_id}:{label}" if warm else None,
                baseline_signature="ImportError: BaseSettings",
                baseline_passed=0, agent_label=label,
                # The LIVE write path. With this set, the loop points the
                # sidecar at the current trace and skips transcript
                # back-fill, so anything in the graph afterwards was put
                # there by Vibe's own hook while the agent worked.
                step_memory=service if warm else None,
                skill_name=skills.SKILL_NAME if warm else None,
                distiller=distiller if warm else None,
                sync=sync,
                # THE EXPERIMENT'S SHAPE, exercised rather than assumed.
                # An experiment is N attempts on one checkout; before this
                # the only bound was the clock, so the rehearsal could not
                # tell 3 attempts from however many fitted in the deadline.
                budget=budgets[label],
                on_attempt_tree=tree_sink(label),
            )
        finally:
            sync.leave(label)

    result, cold_result = await asyncio.gather(
        run_arm("warm-0", True), run_arm("cold-0", False))

    check("the loop converged on the scripted pass", result.success,
          f"success={result.success} attempts={result.attempts}")
    check("two attempts ran", result.attempts == 2, f"{result.attempts}")

    # ---- 3b. distillation must not overlap the other arm's attempt ------
    #
    # Warm and cold share one SGLang server; per-stream throughput roughly
    # halves under contention. A distillation running during cold's
    # attempt would slow cold down, and that slowdown would appear in the
    # wall-clock comparison as though memory caused it.
    overlaps = []
    for what, who, when in timeline:
        if what != "distil-start":
            continue
        end = next((t for w, _, t in timeline if w == "distil-end" and t > when),
                   when)
        overlaps += [(when, t2, end) for w2, who2, t2 in timeline
                     if who2 == "cold-0" and w2 == "attempt-start"
                     and when < t2 < end]
    check("no distillation overlapped cold's attempt", not overlaps,
          f"{len(overlaps)} overlap(s)")

    seq = [(w, o) for w, o, _ in timeline
           if w in ("attempt-start", "attempt-done")]
    warm_n = sum(1 for w, o in seq if w == "attempt-start" and o == "warm-0")
    cold_n = sum(1 for w, o in seq if w == "attempt-start" and o == "cold-0")

    # Only WHILE BOTH ARMS ARE RUNNING. Warm converges on attempt 2 and
    # leaves the barrier; cold then keeps going alone until the deadline,
    # which is correct -- the arms are independent and stopping cold early
    # would censor its distribution. So the ordering property is asserted
    # over the prefix up to warm's last attempt, not over the whole run.
    # Whole rounds only. Warm's last attempt-done can land just before
    # cold's, so cutting at warm's final event leaves a half round -- that
    # is the two arms finishing within milliseconds of each other, not a
    # barrier failure.
    last_warm = max((i for i, (w, o) in enumerate(seq)
                     if o == "warm-0" and w == "attempt-done"), default=-1)
    prefix = seq[:((last_warm + 1) // 4) * 4]
    rounds_ok = bool(prefix) and all(
        sorted(w for w, _ in prefix[i:i + 2]) == ["attempt-start", "attempt-start"]
        and sorted(w for w, _ in prefix[i + 2:i + 4]) == ["attempt-done", "attempt-done"]
        and {o for _, o in prefix[i:i + 4]} == {"warm-0", "cold-0"}
        for i in range(0, len(prefix), 4))
    check("attempts are synchronised in rounds while both arms run",
          rounds_ok, f"{prefix}")
    check("the arms stayed in step while both were running",
          len(prefix) // 4 >= warm_n - 1 and warm_n > 0,
          f"warm ran {warm_n}, {len(prefix) // 4} whole synchronised round(s)")
    # Cold's budget is one larger than warm's, so this is still a real
    # question: does cold run its remaining attempt once warm has left the
    # barrier, or does warm leaving strand it?
    check("cold kept working after warm left", cold_n > warm_n,
          f"warm={warm_n} cold={cold_n} (budgets "
          f"{ATTEMPTS['warm-0']}/{ATTEMPTS['cold-0']}) -- cold should not "
          f"stop when warm does")

    # ---- 4. fresh sessions ------------------------------------------------
    resumed = [e for e in bus.events if e["type"] == "ATTEMPT_DONE"
               and e.get("resumed")]
    check("no attempt resumed a session", not resumed,
          f"{len(resumed)} resumed")

    # ---- 5. the skill reached the model, every attempt --------------------
    loaded = spaces["warm-0"].loaded_skill_text(skills.SKILL_NAME)
    check("the skill reached the model", loaded is not None)
    starts = [e for e in bus.events
              if e["type"] == "ATTEMPT_START" and e.get("agent") == "warm-0"]
    check("attempt 1 used the starting version and attempt 2 the distilled one",
          [e.get("skill_version") for e in starts] == [v0, v0 + 1],
          f"{[e.get('skill_version') for e in starts]}")
    # AND the file on the pod is the one that version names. The check above
    # passed for two runs while the loop was open: it read
    # skills.current(), so it confirmed the ORCHESTRATOR's pointer had
    # advanced and said nothing about what the agent could read. The bytes
    # in the agent's own skills directory are the only version that acts on
    # the model.
    on_pod = spaces["warm-0"]._skill_files_on_pod(
        f"{spaces['warm-0'].home}/.vibe/skills/{skills.SKILL_NAME}")
    final = skills.current()
    # Hashed against the RENDERED package, because that is what install_skill
    # writes: `references/` is appended to the body, since the model never
    # follows the relative pointers AIP's disclosure pass leaves (measured
    # across all six attempts of swarm-1789903474). Still byte-exact -- the
    # question is whether the agent can read THIS version, and the rendering
    # is a deterministic function of it. See agent_workspace.inline_references.
    want = hashlib.sha256(
        inline_references(final.files)["SKILL.md"]).hexdigest()
    check("the improved skill reached the agent's own skills directory",
          on_pod.get("SKILL.md") == want
          and spaces["warm-0"].installed_skill_version == final.version,
          f"pod has {str(on_pod.get('SKILL.md'))[:12]}, live v{final.version} "
          f"renders to {want[:12]}, "
          f"workspace says v{spaces['warm-0'].installed_skill_version}")
    cold_starts = [e for e in bus.events
                   if e["type"] == "ATTEMPT_START" and e.get("agent") == "cold-0"]
    check("cold never had a skill version",
          all(e.get("skill_version") is None for e in cold_starts),
          f"{ {e.get('skill_version') for e in cold_starts} }")

    # ---- 6. ingestion -----------------------------------------------------
    ingested = [e for e in bus.events if e["type"] == "INGESTED"]
    check("every attempt was ingested", len(ingested) == 2, f"{len(ingested)}")
    # THE POINT OF ALL THIS: did Vibe's own hook write, while the agent
    # worked, or did the transcript back-fill quietly cover for a dead
    # hook? `source` says which.
    for e in ingested:
        print(f"      attempt {e.get('attempt')}: source="
              f"{e.get('source') or 'back-fill'} steps={e.get('steps')}")
    live = [e for e in ingested if e.get("source") == "live_hook"]
    check("the graph was written LIVE by Vibe's hook, not back-filled",
          len(live) == len(ingested) and service.steps_written > 0,
          f"{len(live)}/{len(ingested)} attempts written live; "
          f"sidecar counted {service.steps_written} step(s), "
          f"{service.errors} error(s)")
    # READ BACK OUT OF AURA. These used to read the stub's own python
    # attributes (`mem.steps`), so they asserted that a dictionary the
    # rehearsal had just filled in contained what the rehearsal had just
    # put there. Now they are Cypher against the database the run wrote
    # to, which is the only version of this check worth having.
    # SCOPED TO THIS REHEARSAL'S OWN TRACES. Aura holds 98 traces and
    # 4,700+ steps from months of runs, including the Qwen era when
    # `thought` was serialised tool input, so an unscoped query fails on
    # history rather than on anything this run did.
    check("the rehearsal created traces to check against",
          len(rehearsal_traces) > 0, f"{len(rehearsal_traces)}")
    rows = await mem._client.query.cypher(
        "MATCH (t:ReasoningTrace)-[:HAS_STEP]->(s:ReasoningStep) "
        "WHERE toString(t.id) IN $traces "
        "RETURN t.id AS trace, s.step_number AS n, "
        "       s.thought AS thought, s.action AS action "
        "ORDER BY trace, n",
        {"traces": sorted(rehearsal_traces)})
    check("steps were written to the graph", len(rows) > 0,
          f"{len(rows)} steps read back from Aura")
    with_reasoning = [r for r in rows if (r.get("thought") or "").strip()]
    check("every step carries the model's own reasoning",
          len(with_reasoning) == len(rows),
          f"{len(with_reasoning)}/{len(rows)}")
    check("no step stored tool-argument JSON as its thought",
          not any((r.get("thought") or "").lstrip().startswith("{")
                  for r in rows),
          "thought holding serialised tool input is the bug the reasoning "
          "relay existed to fix")
    # NOT CUMULATIVE. Both checks above passed for the whole 2026-09-20
    # series while every step's thought was the concatenation of all
    # reasoning so far: they ask "is this reasoning?", and it was. Measured
    # on Aura, thought lengths ran 267 -> 1537 and never reset, so
    # `render_steps`' 300-character truncation showed the skill author one
    # identical sentence per step. The cause was Vibe emitting ONE turnId
    # for a whole attempt (scripts/probe_turn_ids.py), which no sidecar unit
    # test could see because they all pass turn ids in by hand.
    #
    # WITHIN ONE TRACE, and STRICT containment. Both qualifiers are load
    # bearing. The fake model replays the same script every attempt, so
    # attempt 2's first thought is EQUAL to attempt 1's -- which is
    # repetition, not accumulation, and flagging it made this check fail on
    # a correct relay the first time it ran.
    by_trace: dict[str, list[str]] = {}
    for r in rows:
        by_trace.setdefault(str(r.get("trace")), []).append(r.get("thought") or "")
    grew = [(trace, i, j)
            for trace, thoughts in by_trace.items()
            for i, later in enumerate(thoughts)
            for j, earlier in enumerate(thoughts[:i])
            if earlier and earlier != later and earlier in later]
    # THE EXPERIMENT'S SHAPE. Attempts used to be bounded by the clock, so
    # "3 attempts" was not expressible and runs came out 2-4 depending on
    # how slow the model felt. These assert the loop the operator actually
    # described: N attempts on one checkout, one skill per attempt, every
    # tree kept.
    for label, budget in sorted(budgets.items()):
        check(f"{label} took exactly the attempts its budget allowed",
              budget.remaining == 0,
              f"{ATTEMPTS[label] - budget.remaining}/{ATTEMPTS[label]} "
              f"claimed; the deadline, not the budget, is bounding the loop"
              if budget.remaining else
              f"{ATTEMPTS[label]} attempt(s), budget exhausted")
    check("every attempt's tree was offered to the archive, not just the last",
          all(trees[label] == list(range(1, n + 1))
              for label, n in ATTEMPTS.items()),
          f"{ {k: v for k, v in sorted(trees.items())} } -- per-attempt "
          f"trees are what make closeness recomputable after the fact")
    check("a step's thought does not grow to contain an earlier one's",
          not grew,
          ("reasoning is accumulating across model turns rather than being "
           "replaced: "
           + ", ".join(f"{t[:8]} step {i} contains step {j}"
                       for t, i, j in grew[:3]))
          if grew else
          f"{len(rows)} step(s) across {len(by_trace)} trace(s), "
          f"each with its own reasoning")
    # THE SIDECAR'S OWN TALLY, which is the only one that exists on the
    # live-hook path. The Cypher above proves the graph is right HERE; this
    # proves the counter that reports it on the pod is wired to the same
    # fact. Without it, six runs wrote 988 tool-JSON thoughts out of 993 and
    # every number the operator could see looked healthy.
    thoughts = service.thoughts_from_reasoning - thoughts_before
    fallbacks = service.thoughts_from_tool_input - fallbacks_before
    check("the sidecar counted the relay's reasoning, not fall-backs",
          thoughts > 0 and fallbacks == 0,
          f"across the attempts: {thoughts} from reasoning, {fallbacks} "
          f"fell back to tool input; {service.reasoning_pushes} push(es) "
          f"received from the relay in total")
    # NOTHING ROLLS BACK. The loop just ran for real; if a checkpoint/
    # restore ever returns, this is where it shows up.
    check("no attempt was rolled back",
          not [e for e in bus.events if e["type"] == "RESTORED"],
          "attempts continue from where the last one left the tree")
    # USES_TOOL, confirmed against the live schema -- not a guessed name.
    calls = await mem._client.query.cypher(
        "MATCH (t:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)"
        "-[:USES_TOOL]->(c:ToolCall) "
        "WHERE toString(t.id) IN $traces "
        "RETURN count(c) AS n",
        {"traces": sorted(rehearsal_traces)})
    n_calls = (calls[0]["n"] if calls else 0)
    check("tool calls were recorded", n_calls > 0, f"{n_calls} in Aura")

    check("Vibe fires post_tool hooks in this environment",
          (root / "canary.txt").exists(),
          "no canary file -- Vibe ran no post_tool hook at all, so the "
          "memory hook never had a chance")

    # ---- 6b. the session must not be the whole project --------------------
    #
    # Every trace ever written shared the session id "warm-0", so that one
    # session holds 3,105 messages from 98 runs. `extract_entities_from_
    # session` walks the whole session, so each run re-extracted the entire
    # history, got slower every time, and crossed the 240s bound on
    # 2026-09-17. The entity layer has been empty since. Nothing asserted
    # session size, so nothing noticed.
    sizes = await mem._client.query.cypher(
        "MATCH (m:Message) WHERE m.session_id = $sid RETURN count(m) AS n",
        {"sid": f"{bus.run_id}:warm-0"})
    this_run_msgs = sizes[0]["n"] if sizes else 0
    allmsg = await mem._client.query.cypher(
        "MATCH (m:Message) RETURN count(m) AS n", {})
    total_msgs = allmsg[0]["n"] if allmsg else 0
    check("this run's session holds only this run's messages",
          this_run_msgs < max(50, total_msgs // 4),
          f"{this_run_msgs} in this session vs {total_msgs} in the database "
          f"-- a session that grows without bound is what killed entity "
          f"extraction")

    started_x = time.monotonic()
    try:
        ents = await asyncio.wait_for(
            mem.extract_entities_from_session(f"{bus.run_id}:warm-0"),
            timeout=120.0)
        took = time.monotonic() - started_x
        check("entity extraction completes on a per-run session",
              True, f"{took:.1f}s, {ents}")
        print(f"      extraction: {took:.1f}s on {this_run_msgs} message(s) "
              f"-> {ents}")
    except asyncio.TimeoutError:
        check("entity extraction completes on a per-run session", False,
              "timed out at 120s on a SINGLE run's session -- the bound is "
              "not the problem, the session is")
    except Exception as exc:
        check("entity extraction completes on a per-run session", False,
              f"{exc!r}")

    # ---- 7. distillation: rejection, repair, versioning -------------------
    check("distillation ran after each attempt", len(distilled) == 2,
          f"{len(distilled)}")
    for i, d in enumerate(distilled):
        if d.rejection is not None:
            print(f"    distillation {i}: {d.rejection.reason}")
            print(f"      detail: {d.rejection.detail[:400]}")
            print(f"      proposal head: {d.rejection.proposal[:160]!r}")
    check("an invalid skill was rejected and repaired",
          distilled and distilled[0].repairs == 1,
          f"repairs={distilled[0].repairs if distilled else 'n/a'} "
          f"{getattr(distilled[0].rejection, 'reason', '') if distilled else ''}")
    check("the repaired skill became the next version",
          distilled and distilled[0].version == v0 + 1,
          f"{distilled[0].version if distilled else None}")
    check("the second distillation advanced again",
          len(distilled) > 1 and distilled[1].version == v0 + 2,
          f"{distilled[1].version if len(distilled) > 1 else None}")
    check("the live skill advanced twice", skills.current().version == v0 + 2,
          f"v{skills.current().version}")
    # THE EVIDENCE REACHED THE WRITER -- which is a different assertion
    # depending on who writes.
    #
    # This used to require `memory_tool_calls > 0`, correct only for the
    # AGENT writer, which holds memory tools and chooses what to look at.
    # The default is now a frontier model over the API: it has no tools,
    # so zero is the honest number, and the orchestrator queries the
    # graph on its behalf and puts the result in the prompt. Asserting
    # tool calls against that writer would fail a healthy run; asserting
    # nothing would let an empty prompt through. So: assert the
    # *evidence*, by the route this writer actually uses.
    used_tools = any(d.memory_tool_calls > 0 for d in distilled)
    saw_traces = all(d.eligible_traces > 0 for d in distilled)
    check("the distiller was given the graph's evidence",
          used_tools or saw_traces,
          f"memory_tool_calls={[d.memory_tool_calls for d in distilled]} "
          f"eligible_traces={[d.eligible_traces for d in distilled]} -- "
          f"the writer neither queried the graph nor was handed traces")
    check("the distiller never edited the repo",
          (root / "home/agent-warm-0/repo/config.py").read_text() != VALID_SKILL,
          "the distillation turn wrote into the agent's checkout")

    # ---- 8. metrics -------------------------------------------------------
    print("... collecting metrics", flush=True)
    run_metrics = metrics_mod.collect(
        bus.events, run_id=bus.run_id, gpu="none", model="fake-model",
        commit="local", skill_version=skills.current().version,
        skill_approx_tokens=skills.current().approx_tokens,
        skill_dir_sha=skills.current().dir_sha,
        arms_identical=not differences, known_differences=sorted(differences),
        distil_usage={"warm": {"prompt_tokens": 1, "completion_tokens": 1}},
        gpu_usd_per_hour=3.59)
    check("the run counts as evidence, not as debugging",
          run_metrics.counts_toward_clearly_working,
          f"differences {sorted(differences)} -- warm having memory is the "
          f"TREATMENT; anything else is a confound and disqualifies the run")
    check("GPU spend is computed from the run's own length",
          run_metrics.gpu_usd is not None and run_metrics.run_seconds > 0,
          f"{run_metrics.gpu_usd} over {run_metrics.run_seconds}s")
    warm = run_metrics.arms.get("warm")
    check("metrics recorded both attempts",
          warm is not None and warm.attempts == 2)
    check("attempt and distillation time are separate",
          warm is not None and warm.attempt_seconds > 0
          and warm.distil_seconds > 0,
          f"attempt={getattr(warm, 'attempt_seconds', 0):.1f}s "
          f"distil={getattr(warm, 'distil_seconds', 0):.1f}s")
    check("the per-attempt table records the skill version used",
          warm is not None
          and [a["skill_version"] for a in warm.per_attempt] == [v0, v0 + 1],
          f"{[a['skill_version'] for a in warm.per_attempt] if warm else None} "
          f"expected {[v0, v0 + 1]}")
    # THE CHARTS, from this run's own events. The demonstration is built
    # off this document, so "the run produced plottable data" is a
    # pre-pod gate like everything else here -- finding out afterwards
    # that a panel is empty means the run has to be paid for again.
    doc = series.within_run(bus.events, run_id=bus.run_id, fixture="rehearsal")
    populated = [p["id"] for p in doc["panels"]
                 if any(s["points"] for s in p["series"])]
    check("every chart panel has data in it",
          len(populated) == len(doc["panels"]),
          f"empty: {sorted({p['id'] for p in doc['panels']} - set(populated))}")
    check("both arms appear in the chart data",
          set(doc["arms"]) == {"warm", "cold"}, str(doc["arms"]))
    check("the series document is JSON-serialisable",
          bool(json.dumps(doc)))
    table = metrics_mod.append_to_table(run_metrics,
                                        path=root / "cross-run.md")
    check("the cross-run table was written", table.exists())

    bus.close()
    return 0 if all(ok for _, ok, _ in CHECKS) else 1


async def _with_graph(vibe: Path, root: Path, server: FakeModelServer) -> int:
    """Open the REAL graph, or stop.

    No stub and no fallback. A rehearsal that silently swaps a dictionary
    in for Aura reports "steps were written to the graph" either way, and
    that assertion is the whole reason this script is trusted before a pod
    is rented.
    """
    from neo4j_agent_memory import MemoryClient

    from orchestrator.memory import ScopedMemory, build_settings

    async with MemoryClient(build_settings()) as client:
        mem = ScopedMemory(client, user_identifier="warm-0")
        # ONLY the probe is allowed to be blamed on the graph. Wrapping the
        # whole rehearsal in this handler reported a NameError in my own
        # check code as "the graph is not reachable", which is a lie the
        # operator would have had to debug from scratch.
        try:
            probe = await client.query.cypher("RETURN 1 AS ok", {})
            if not probe:
                raise RuntimeError("Aura answered nothing to RETURN 1")
        except Exception as exc:
            print(f"\nABORT: the graph is not reachable -- {exc!r}")
            print("The rehearsal asserts that steps reach the graph. With "
                  "no graph there is nothing to assert against, and a stub "
                  "would make those checks pass while proving nothing.")
            return 2
        print("graph: REAL (Aura), reachable")
        return await rehearse(vibe, root, server.base_url, server, mem)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vibe", default=os.environ.get("REHEARSE_VIBE", ""),
                    help="path to a vibe binary (python 3.12+ venv)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the temp tree for inspection")
    args = ap.parse_args()

    vibe = Path(args.vibe) if args.vibe else None
    if not vibe or not vibe.exists():
        print("ERROR: --vibe must point at a vibe binary. Vibe needs python "
              "3.12+, which this project's venv is not, so the rehearsal "
              "uses a separate one:\n"
              "  uv venv --python 3.13 /tmp/vibetest\n"
              "  VIRTUAL_ENV=/tmp/vibetest uv pip install mistral-vibe==2.25.4\n"
              "  scripts/rehearse_loop.py --vibe /tmp/vibetest/bin/vibe")
        return 2

    root = Path(tempfile.mkdtemp(prefix="rehearse-"))
    # The live skill is mutated by distillation, so the rehearsal works on
    # a COPY of the package. Running it must never advance the real skill.
    sandbox_skills = root / "skills"
    shutil.copytree(skills.SKILLS_DIR, sandbox_skills)
    skills.SKILLS_DIR = sandbox_skills
    skills.VALIDATOR = sandbox_skills / "_aip" / "scripts" / "validate.py"

    print(f"rehearsal root: {root}")
    print(f"vibe: {vibe}")
    script: list[Turn] = [Turn(text="ready")]
    with FakeModelServer(script) as server:
        code = asyncio.run(_with_graph(vibe, root, server))

    print()
    failed = [(n, d) for n, ok, d in CHECKS if not ok]
    print(f"{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    for name, detail in failed:
        print(f"  FAILED: {name}  {detail}")
    if args.keep:
        print(f"tree kept at {root}")
    else:
        shutil.rmtree(root, ignore_errors=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
