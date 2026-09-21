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
import atexit
import contextlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv

load_dotenv()

from orchestrator import cognee_layer as C
from orchestrator import metrics as metrics_mod
from orchestrator import series
from orchestrator.events import EventBus
from orchestrator.sync import AttemptSync
from orchestrator.vibe_agent import AttemptBudget, migrate_codebase
from swarm.agent_workspace import AgentWorkspace, SwarmHost
from swarm.run import assert_hook_can_read
from tests.fake_model_server import FakeModelServer, Turn

# Set per run in main(); every Cognee call in this file is scoped to it.
DATASET = "msf-rehearsal"
# The node-set prefix warm's documents are written under and read back from.
# Per rehearsal, like the dataset: node sets are the read-scoping boundary, so
# sharing one with a real experiment would put rehearsal fictions in a real
# agent's prompt.
FIXTURE = "rehearsal"


async def _cypher(query: str, params: dict | None = None):
    """Read the graph directly, as the old ScopedMemory client did.

    The checks below assert against what is IN Aura rather than against
    anything the harness reports, and that is the point: they used to
    read the stub's own python attributes, so they asserted that a
    dictionary the rehearsal had just filled in contained what the
    rehearsal had just put in it.
    """
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    return await engine.query(query, params or {})


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

        Guarded, and it must stay guarded even though the case that
        earned it is gone. `MSF_RELAY_PATH`/`MSF_HOOK_PATH` pointed at
        files ALREADY under this root, because Vibe executed those
        commands itself and they never passed through here -- so
        `{root}/opt/swarm/reasoning_relay.py` arrived with the prefix on
        it and a blind `str.replace` added a second one. The relay then
        failed to start, its end of `vibe | relay` closed, and VIBE DIED
        OF A BROKEN PIPE on its first tool call, every attempt, warm
        only, silently. Anything under the root is left alone.
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

    def agent_path(self, path: str) -> str:
        """Vibe runs the hook itself, so the hook command and the journal
        path never pass through `host.run`'s pod-path rewrite. Without this
        the hook was installed and verified, Vibe could not start it, and the
        rehearsal reported a working hook."""
        return self.host._map(path)

    def _vibe_command(self, prompt: str, *, resume: bool,
                      vibe_home: str | None = None,
                      cwd: str | None = None) -> str:
        home = vibe_home or f"{self.home}/.vibe"
        workdir = cwd or self.repo_path
        vibe = (f"{self.host.vibe} --prompt {shlex.quote(prompt)} "
                f"--auto-approve --trust --output streaming < /dev/null")
        # THE HOOK'S ENVIRONMENT, exactly as production passes it. Left out
        # of this override once and the hook ran with no COGNEE_API, so it
        # exited 0 with no output and the rehearsal reported a working hook.
        hook_env = " ".join(f"{k}={shlex.quote(v)}"
                            for k, v in sorted(self._hook_env.items()))
        # NOTHING IS PIPED, exactly as production no longer splices it.
        # This used to tee Vibe's stream through the reasoning relay,
        # because with no relay the post_tool hook had no reasoning to
        # attach and fell back to the tool's arguments -- 988 of 993 steps
        # in one series. Hook and relay are both retired; the stream is
        # read in-process.
        return f"cd {workdir} && env VIBE_HOME={home} {hook_env} {vibe}"

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


# _SidecarClient DELETED. It spoke the sidecar's control protocol over a
# loopback socket so the rehearsal exercised the real message shapes
# rather than method calls on an in-scope object. There is no sidecar,
# no hook and no relay: the agent writes through its MCP server and the
# harness writes from its own process, so the equivalent question is
# whether `cognee.agent_memory` retrieved and persisted -- asserted
# directly, further down, against Aura.
# RecordingMemory DELETED. It was a graph in a dictionary, used
# unconditionally while the docstring claimed it was a fallback,
# so every graph assertion in this file passed without Aura ever
# being contacted. The rehearsal now aborts instead.
# --------------------------------------------------------------------------
# The script the fake model follows
# --------------------------------------------------------------------------

def attempt_turns(*, edit: bool, finish_text: str,
                  recall: bool = False) -> list[Turn]:
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
        # A COMMAND THAT FAILS, so the `post_tool` hook's failure branch
        # actually runs. Without one the hook is installed, registered,
        # verified and never invoked -- which is indistinguishable, in
        # every number the rehearsal reports, from a hook that works.
        Turn(text="Let me run the suite and see the error.",
             tools=[("bash", {"command": "python -m pytest -q; exit 1"})]),
    ]
    if recall:
        # THE VOLUNTARY HALF, exercised. Warm has the cognee MCP server and
        # may call it; nothing in the harness makes it, and a scripted model
        # is the only way to find out whether a call that IS made is counted
        # -- separately from the context the harness injects, which is the
        # distinction the whole warm/cold reading turns on.
        #
        # `cognee_recall`, not `recall`: Vibe publishes an MCP tool as
        # f"{server-name}_{raw-tool-name}" (core/skills/builtins/vibe.py).
        # Getting that wrong is not cosmetic -- the model calls a tool that
        # does not exist and Vibe answers with an error the agent then has
        # to recover from.
        turns.insert(0, Turn(
            text="Before I change anything, what did previous attempts hit?",
            tools=[("cognee_recall", {"query": "pydantic v2 migration "
                                               "failures on this repo",
                                      "top_k": 3})]))
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





# distill_turns DELETED. It scripted the two turns a distillation used to
# take -- write SKILL.md, then repair it after the AIP validator rejected
# it -- and both belong to a loop Cognee owns now: it calls its own
# authoring model directly, so no request reaches this file's fake server
# and there is nothing to script or route.


# --------------------------------------------------------------------------

# The whole rehearsal is scripted, so anything slow is a bug in it.
REHEARSAL_DEADLINE_S = 300.0

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}"
          + (f"  -- {detail}" if detail and not ok else ""))


def _tamper_is_caught(aw, host, script: Path) -> bool:
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
    original = script.read_bytes()
    real_put = host.put
    try:
        host.put = lambda *a, **kw: None          # the write goes nowhere
        script.write_bytes(b"# not the script\n")  # what was there before
        try:
            aw.install_host_scripts(host)
        except RuntimeError:
            return True
        return False
    finally:
        host.put = real_put
        script.write_bytes(original)


def _kill_quietly(proc) -> None:
    with contextlib.suppress(Exception):
        proc.kill()


async def rehearse(vibe: Path, root: Path, model_url: str,
                   server: FakeModelServer) -> int:
    host = LocalHost(root, vibe, vibe.parent, model_url)
    host.server = server
    bus = EventBus(f"rehearsal-{int(time.time())}")
    # BUILT HERE, not passed in, because its session id has to be the one
    # the attempt loop uses -- `{run_id}:{label}`, per run and per agent.
    # A memory whose session does not match the loop's retrieves from one
    # place and writes to another, and every check still passes.
    mem = C.CogneeMemory(dataset=DATASET, fixture=FIXTURE, label="warm-0",
                         session_id=f"{DATASET}:{bus.run_id}:warm-0",
                         mode="hybrid")

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

    # ---- 0a. WHAT THE HARNESS PUTS ON THE POD, AND ITS DIGESTS ---------
    print("... installing the harness's own scripts", flush=True)
    (root / "opt" / "swarm").mkdir(parents=True, exist_ok=True)
    # THE PRODUCTION INSTALLER, not a shutil.copy standing in for it.
    #
    # This block used to copy the two files itself. That is precisely the
    # bug it was meant to be testing: nothing in the repo put hook.py or
    # reasoning_relay.py on a pod, they were hand-scp'd, and the rehearsal
    # hand-copying them too meant the gap was invisible from both ends.
    # `install_host_scripts` is now what the pod uses AND what runs here,
    # digest check included.
    import swarm.agent_workspace as _aw
    local_proxy = root / "opt" / "swarm" / "id_fix_proxy.py"
    installed = _aw.install_host_scripts(host)
    # The hook and the relay used to be checked here by name, and they
    # were the reason this check exists: until 2026-09-19 nothing in the
    # repo put either on a pod, they were hand-scp'd, and the rehearsal
    # hand-copying them too made the gap invisible from both ends. Both
    # are retired with the old memory layer, and `host_modules()` is now
    # empty -- Cognee's MCP server is installed from PyPI by
    # provision_cognee.sh, so NO harness module runs on the pod at all.
    #
    # The check survives them because the property is not about those
    # files: what remains must still come from the repo and still be
    # verified on arrival.
    expected = len(_aw.host_scripts()) + len(_aw.host_modules())
    check("the harness installs its own scripts and verifies the digests",
          local_proxy.is_file() and len(installed) == expected,
          f"{len(installed)}/{expected} file(s): "
          + ", ".join(f"{Path(p).name} {d[:8]}" for p, d in installed.items()))
    check("no harness module is shipped to the pod any more",
          _aw.host_modules() == {},
          f"host_modules() still ships {list(_aw.host_modules())}")
    check("a script that did not land is caught, not assumed",
          _tamper_is_caught(_aw, host, local_proxy),
          "the sha256 is read back OFF THE HOST; a file whose upload "
          "silently failed leaves whatever was there before in place "
          "while every counter looks healthy")

    # ---- warm's memory actually writes and reads back ------------------
    #
    # WHAT THIS REPLACES. A sidecar process, a `post_tool` hook invoked
    # the way Vibe invokes it, and a reasoning relay -- roughly sixty
    # lines of setup here -- all of which existed so that a tool call
    # became a ReasoningStep in the old layer. Cognee's agents call
    # `remember` on its MCP server themselves, so there is no second
    # writer, no hook to fail open, and no relay whose collapse turned
    # 988 of 993 thoughts into serialised tool JSON.
    #
    # The property worth keeping is the one those checks were really
    # buying: a write that LOOKS fine and lands nowhere. "The hook ran"
    # and "the hook reached the sidecar" were different facts and only
    # the second mattered; the same is true of remember/recall.
    print("... checking warm's memory writes land", flush=True)
    import cognee
    probe_session = f"{DATASET}:{bus.run_id}:warm-0"
    marker = f"rehearsal marker {bus.run_id}"
    await cognee.remember(marker, dataset_name=DATASET,
                          session_id=probe_session)
    # READ BACK THROUGH THE SESSION, not the graph.
    #
    # MEASURED, and it is the thing to know about Cognee's model: a
    # `remember(..., session_id=...)` goes into SESSION memory and is not
    # graph-queryable until something distils it. A plain
    # `recall(datasets=[...])` right after a write returns
    # `status='memory_warming_up'` -- "no knowledge graph data exists yet
    # for the requested dataset" -- which reads as a lost write and is
    # not one. The session-scoped read is the one that answers "did this
    # land".
    read_back = ""
    try:
        import cognee
        got = await cognee.recall("what rehearsal marker was stored?",
                                  datasets=[DATASET], session_id=probe_session,
                                  only_context=True)
        read_back = str(got)
    except Exception as exc:
        read_back = f"recall raised {exc!r}"
    check("a warm memory write lands and reads back from its session",
          bus.run_id in read_back,
          f"session recall returned {read_back[:200]!r}")

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

    # ---- 1. the skill is in Cognee, not on the pod ---------------------
    #
    # WHAT THIS REPLACES. Four checks installed an AIP package into the
    # agent's own $VIBE_HOME, verified its two hashes as the agent user,
    # proved a `references/` tier installed recursively, and confirmed
    # cold had no skills directory at all. Every one of them was about a
    # FILE delivery mechanism, and it was earned -- a package whose
    # read-back did not recurse would have made the first distillation
    # of a real run fail with "the skill on the pod is not the skill
    # that was sent".
    #
    # Cognee keeps the procedure in the graph. Nothing is installed, so
    # the question is simply whether the procedure is there to be
    # recalled.
    procedure = await C.ensure_skill(dataset=DATASET)
    check("the starting procedure is in Cognee", len(procedure) > 0,
          f"{len(procedure):,} chars")
    check("cold has NO skills directory",
          not spaces["cold-0"].has_skills_dir())

    # A REAL COGNEE MCP SERVER, the same one provision_cognee.sh starts.
    #
    # This url used to point at 127.0.0.1:1 -- deliberately unreachable,
    # because the check here was about the hook WRITE path and a dead
    # server must not stop a hook firing. There is no hook now, and the
    # question is whether warm's memory tools REGISTER, which an
    # unreachable server can never answer.
    #
    # Worth the ~30s it costs to boot: the failure it can catch is
    # Vibe's `http` transport selecting its legacy SSE client, which a
    # streamable-HTTP server answers with 406 -- the agent then registers
    # ZERO memory tools while the config, the server and every log line
    # look healthy. That cost a whole pod run once, and no amount of
    # config inspection finds it.
    print("... starting a real cognee MCP server", flush=True)
    import socket as _socket
    with _socket.socket() as _s:
        _s.bind(("127.0.0.1", 0))
        mcp_port = _s.getsockname()[1]
    mcp_proc = await asyncio.create_subprocess_exec(
        str(Path(sys.executable).parent / "cognee-mcp"),
        "--transport", "http", "--host", "127.0.0.1", "--port", str(mcp_port),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ})
    # KILLED ON EXIT. Without this every rehearsal left a cognee-mcp behind:
    # eighteen of them had accumulated, each holding an Aura session and a
    # handle on the same local SQLite, and the nineteenth run blocked on a
    # write for as long as it was left alone.
    atexit.register(_kill_quietly, mcp_proc)
    for _ in range(90):
        await asyncio.sleep(1.0)
        with contextlib.suppress(OSError):
            with _socket.create_connection(("127.0.0.1", mcp_port), 1):
                break
    check("the cognee MCP server is listening",
          mcp_proc.returncode is None, f"port {mcp_port}")
    spaces["warm-0"].enable_memory(mcp_url=f"http://127.0.0.1:{mcp_port}/mcp")

    # THE DETERMINISTIC READ, installed for warm exactly as the pod
    # installs it: a `post_tool` hook on `bash` that recalls what earlier
    # graded attempts did about a failure, through Cognee's REST API.
    #
    # THREE SILENT FAILURES LIVE HERE, each of which produced a clean run
    # with an empty prompt block: a hooks.toml Vibe does not read, an
    # interpreter that does not exist in the hook command, and a hook
    # script that is not where the command says. All three are checked
    # below rather than assumed.
    print("... starting cognee's REST API for the hook", flush=True)
    with _socket.socket() as _s:
        _s.bind(("127.0.0.1", 0))
        api_port = _s.getsockname()[1]
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "cognee.api.client:app",
         "--host", "127.0.0.1", "--port", str(api_port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ})
    atexit.register(api_proc.terminate)
    api_url = f"http://127.0.0.1:{api_port}"
    for _ in range(120):
        await asyncio.sleep(1.0)
        with contextlib.suppress(Exception):
            with urllib.request.urlopen(f"{api_url}/health", timeout=2) as r:
                if r.status == 200:
                    break
    check("cognee's REST API answers the hook's endpoint",
          not assert_hook_can_read(api_url, dataset=DATASET,
                                   node_set=C.node_set(FIXTURE)),
          api_url)
    spaces["warm-0"].enable_hook(api_url=api_url, dataset=DATASET,
                                 node_set=C.node_set(FIXTURE))
    warm_home = spaces["warm-0"].home
    check("warm got a hooks.toml where Vibe looks for it",
          spaces["warm-0"].host.run_as(
              spaces["warm-0"].user,
              f"test -f {warm_home}/.vibe/hooks.toml && echo yes || echo no",
              check=False).stdout.strip().endswith("yes"))
    check("the hook script is where the hook command names it",
          spaces["warm-0"].host.run_as(
              spaces["warm-0"].user,
              f"test -r {warm_home}/.vibe/cognee_on_failure.py "
              f"&& echo yes || echo no",
              check=False).stdout.strip().endswith("yes"))
    # AND THE COMMAND IS RUNNABLE, as written, by the user that will run it.
    # `command` in hooks.toml is executed by VIBE, so it never passes through
    # the rehearsal's pod-path rewrite -- the first version named an unmapped
    # path, Vibe could not start it, and every other check still passed.
    hook_cmd = re.search(
        r'command = "([^"]+)"',
        (Path(spaces["warm-0"].host._map(f"{warm_home}/.vibe/hooks.toml"))
         ).read_text()).group(1)
    check("the hook command in hooks.toml actually runs",
          subprocess.run(shlex.split(hook_cmd), input="{}", text=True,
                         capture_output=True, timeout=60).returncode == 0,
          hook_cmd)
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
    # THE ARMS DIFFER BY THE MEMORY TOOLS, AND BY NOTHING ELSE.
    #
    # This used to assert the two tool lists were IDENTICAL, and it
    # passed for the wrong reason: the rehearsal pointed warm at an
    # unreachable MCP server, so warm registered no memory tools and the
    # lists matched trivially. With a real server warm has 11 more, and
    # that difference IS the treatment -- what must not happen is warm
    # quietly gaining anything else.
    extra = set(warm_fp["tools"]) - set(cold_fp["tools"])
    missing = set(cold_fp["tools"]) - set(warm_fp["tools"])
    non_memory = {t for t in extra
                  if "cognee" not in t and t not in
                  ("remember", "recall", "forget", "cognify_file")}
    check("warm's only extra tools are memory tools",
          bool(extra) and not non_memory and not missing,
          f"extra={sorted(extra)} unexpected={sorted(non_memory)} "
          f"missing_from_warm={sorted(missing)}")
    # THE HOOK IS WARM'S SECOND DIFFERENCE FROM COLD, and it is declared
    # rather than hidden: it is latency warm pays and cold does not, on
    # every failed command, out of a shared deadline. It fires only on a
    # FAILURE and has an 8s ceiling for that reason, and ATTEMPT_DONE
    # carries the count either way.
    check("warm has the post_tool hook and cold has none",
          warm_fp["hook_files"] == ["hooks.toml"] and not cold_fp["hook_files"],
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
    # NO PROVENANCE STAMP. `prov_model`, `prov_gpu`, `prov_writable`,
    # `prov_fixture` and `prov_experiment` were properties written onto
    # every trace so distillation could filter out runs it must not learn
    # from -- a weaker model, a read-only checkout, another codebase,
    # last night's experiment. Each was added after distillation learned
    # from the wrong runs. Cognee scopes by DATASET, and this rehearsal
    # has its own, so the same isolation is structural and cannot be
    # forgotten on a write.

    # NO TRACES TO TRACK. This wrapped `mem.start_trace` to collect the
    # ids this rehearsal created, because every trace in the database
    # shared the session id "warm-0" and an unscoped query would have
    # asserted against 98 runs of history -- including the Qwen era.
    # The harness opens no traces now; the dataset is the scope.


    # THE REAL COGNEE DISTILLATION, against the real graph.
    #
    # Not the fake model server: Cognee calls its own authoring model
    # directly, so there is no request for the scripted server to
    # intercept and nothing about the distillation is simulated here.
    # That is the point -- the two bugs that cost pod runs on 2026-09-18
    # were both in code the rehearsal could not reach, and a stubbed
    # distiller would recreate exactly that blind spot.
    #
    # It costs an OpenAI call and some Aura writes per rehearsal. Both
    # are cheap and neither is the spend that matters; the GPU is.

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
    # RELATIVE to whatever the copied package starts at. The rehearsal runs
    # against a copy of the REAL skill, which advances with every run, so
    # hard-coded version numbers rot the moment the agent distils.
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
            attempt_turns(edit=True, recall=True,
                          finish_text="I changed the import.")
            + attempt_turns(edit=True, recall=True,
                            finish_text="The migration is complete.")),
        "attempt-cold-0": (
            attempt_turns(edit=True, finish_text="I changed the import.")
            + attempt_turns(edit=True,
                            finish_text="The migration is complete.")),
        # NO distil queues. Cognee's authoring model is called directly
        # and never reaches this server, so there is nothing to script --
        # and nothing to route, which is why the marker-matching below
        # only has to tell the two arms apart now.
        # `loaded_tools()` makes a real Vibe call per arm before the clock
        # so the two tool lists can be compared. It runs in the agent's own
        # home, so it looks exactly like that arm's attempt unless it is
        # routed out -- and it would eat the first turn of the script.
        "probe": [Turn(text="ready")],
    }
    host.server._indices = {k: 0 for k in host.server.scripts}

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
    # Cognee stamps `created_at` in unix MILLISECONDS (DataPoint), so the
    # scope below is "since this run began" rather than a trace id list.
    started_ms = int(time.time() * 1000)
    # BASELINE THE SIDECAR'S COUNTERS. They are cumulative and outlive a
    # single run -- the same odometer trap NOTES-hard-won.md records
    # against the proxies -- and the probes above deliberately wrote steps
    # with no Vibe in the picture, so those legitimately fell back. Only
    # the delta across the attempts says whether the relay delivered.
    # No sidecar counters any more: Cognee does not expose a per-write
    # tally, and where a thought came from is not a question anything can
    # answer now that there is no per-step write.
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
                session_id=f"{DATASET}:{bus.run_id}:{label}" if warm else None,
                baseline_signature="ImportError: BaseSettings",
                baseline_passed=0, agent_label=label,
                skill_name=C.SKILL_NAME if warm else None,
                tests_total=33,
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

    # ---- 5. warm could reach its memory, every attempt -------------------
    #
    # THIS USED TO BE "the skill reached the model", read off the
    # transcript for a `<skill_content>` block. Vibe injected one when a
    # prompt began `/<name>`, and its absence was the difference between
    # "the agent ignored its procedure" and "the procedure never reached
    # it" -- opposite fixes, which is why the check existed.
    #
    # There is no skill file and no prefix now. The procedure is in
    # Cognee and warm gets there with `recall`, so the equivalent fact
    # is whether warm had the tools at all. Whether it USED them is
    # counted below and deliberately not asserted: "warm chose not to
    # recall" is the result, and the old layer produced exactly that for
    # 40 consecutive runs while every check here was green.
    warm_tools = spaces["warm-0"].loaded_tools()
    check("warm had memory tools available to it",
          any("cognee" in t or t in ("remember", "recall")
              for t in warm_tools),
          f"{sorted(warm_tools)}")
    warm_calls = spaces["warm-0"].memory_tool_calls()
    print(f"      warm made {warm_calls} memory tool call(s) across its "
          f"attempts")
    # THE TWO HALVES MUST BE COUNTABLE APART. Warm's script calls
    # `cognee_recall` itself, and the harness separately injects what
    # `cognee.agent_memory` retrieved. Summing them answers "did warm have
    # memory" and destroys the answer to "did warm go and get it" -- and
    # the second question is the one this project spent 40 runs failing to
    # ask cleanly.
    check("the agent's own memory calls are counted", warm_calls > 0,
          f"{warm_calls} -- the scripted model calls cognee_recall on every "
          f"attempt, so zero means the counter does not recognise the tool "
          f"name Vibe publishes (f'{{server}}_{{tool}}')")
    by_agent = [e for e in bus.events if e["type"] == "MEMORY_READ"
                and "cognee.agent_memory" not in (e.get("sources") or [])]
    check("the agent's reads and the harness's are separate events",
          bool(by_agent) and all("cognee_recall" in (e.get("sources") or [])
                                 for e in by_agent),
          f"{[e.get('sources') for e in by_agent]}")
    starts = [e for e in bus.events
              if e["type"] == "ATTEMPT_START" and e.get("agent") == "warm-0"]
    # NO VERSION PER ATTEMPT. Cognee rewrites the procedure in place,
    # so ATTEMPT_START carries None and there is no v5..v6 to assert.
    # What replaces it is the content check below: the procedure Cognee
    # holds after distillation is not the one it held before.
    check("no attempt claims a skill version that cannot exist",
          all(e.get("skill_version") is None for e in starts),
          f"{[e.get('skill_version') for e in starts]}")
    # AND the file on the pod is the one that version names. The check above
    # passed for two runs while the loop was open: it read
    # the local registry, so it confirmed the ORCHESTRATOR's pointer had
    # advanced and said nothing about what the agent could read. The bytes
    # in the agent's own skills directory are the only version that acts on
    # the model.
    # DID THE PROCEDURE ACTUALLY CHANGE? The old check hashed the bytes
    # in the agent's own skills directory against the rendered package,
    # because installed / hashed / prefixed were three things that could
    # each succeed while the agent ran with no procedure. Nothing is
    # installed now, so the honest question is whether Cognee's own copy
    # moved -- and, separately, whether warm ever went and read it.
    final = await C.current_procedure(dataset=DATASET) or ""
    check("the procedure in Cognee changed after distillation",
          final.strip() != procedure.strip(),
          f"{len(final):,} chars now vs {len(procedure):,} at the start")
    check("warm could reach its memory tools",
          spaces["warm-0"].memory_tool_calls() >= 0,
          "counted, not required: whether warm consults memory is the "
          "thing being measured, not a precondition")

    # ---- 5b. THE DETERMINISTIC HALF, asserted off the wire -------------
    #
    # THE CHECK THIS FILE WAS MISSING, and the reason the first Cognee
    # migration shipped a warm arm that was cold in everything but its
    # tool list: the treatment is only real if it reaches the MODEL. Not
    # "the procedure is in Cognee" (checked above, and true while the
    # agent never sees it), not "the server is up" (checked above, and
    # true while Vibe registers zero tools) -- what the model was
    # actually sent.
    #
    # Read off the fake model server's recorded request bodies, which are
    # the bytes that crossed the wire. Everything else is a claim about
    # this harness.
    def _prompts_for(label: str) -> list[str]:
        out = []
        for body in server.requests:
            text = json.dumps(body.get("messages") or [])
            if f"agent-{label}" in text:
                out.append(text)
        return out

    warm_prompts = _prompts_for("warm-0")
    cold_prompts = _prompts_for("cold-0")
    # A distinctive slice of the procedure, so the check cannot pass on a
    # coincidence. json.dumps escapes newlines, so match on a line.
    needle = next((line.strip() for line in procedure.splitlines()
                   if len(line.strip()) > 25), procedure[:40])
    check("the procedure reached the warm model",
          any(needle in p for p in warm_prompts),
          f"{len(warm_prompts)} warm request(s), none carrying "
          f"{needle[:50]!r} -- warm ran as a cold agent with extra tools")
    check("the procedure never reached the cold model",
          not any(needle in p for p in cold_prompts),
          f"{len(cold_prompts)} cold request(s); one carries the procedure, "
          f"so the arms differ by nothing and the run measures nothing")
    check("cold was never told about memory tools",
          not any("cognee_recall" in p for p in cold_prompts))
    # RETRIEVAL IS COUNTED, NOT REQUIRED. Attempt 1 has no previous error,
    # so Cognee derives no query and skips retrieval -- correctly. Whether
    # attempt 2 gets anything back depends on what improve() bridged, which
    # is a property of the graph rather than of this harness, so an empty
    # retrieval is reported rather than failed.
    injected = [e for e in bus.events if e["type"] == "MEMORY_READ"
                and "cognee.agent_memory" in (e.get("sources") or [])]
    print(f"      cognee retrieved for warm on {len(injected)} attempt(s), "
          f"{sum(e.get('chars', 0) for e in injected)} chars")
    done = [e for e in bus.events if e["type"] == "ATTEMPT_DONE"]
    check("every attempt reports what the harness put in its prompt",
          all("memory_chars" in e for e in done),
          "ATTEMPT_DONE must carry memory_chars for both arms -- an "
          "unmeasured asymmetry in the prompt has invalidated a series "
          "before")
    check("cold's prompt carried no injected memory at all",
          all((e.get("memory_chars") or 0) == 0 for e in done
              if e.get("swarm") == "cold"),
          f"{[e.get('memory_chars') for e in done if e.get('swarm') == 'cold']}")

    cold_starts = [e for e in bus.events
                   if e["type"] == "ATTEMPT_START" and e.get("agent") == "cold-0"]
    check("cold never had a skill version",
          all(e.get("skill_version") is None for e in cold_starts),
          f"{ {e.get('skill_version') for e in cold_starts} }")

    # ---- 6. ingestion -----------------------------------------------------
    ingested = [e for e in bus.events if e["type"] == "INGESTED"]
    check("every attempt was ingested", len(ingested) == 2, f"{len(ingested)}")
    # WHAT `improve` DID WITH EACH ATTEMPT'S SESSION TRACE. `stages`
    # carries each stage's status, so a stage that declined -- and why --
    # is in the event log rather than only in stdout that dies with the
    # run.
    for e in ingested:
        print(f"      attempt {e.get('attempt')}: source={e.get('source')} "
              f"steps={e.get('steps')} stages={e.get('stages')}")
    check("every attempt ran cognee.improve() over its own session",
          all(e.get("source") == "cognee.improve" for e in ingested),
          f"{[e.get('source') for e in ingested]}")
    # THE BRIDGE IS THE WHOLE DETERMINISTIC HALF. A session trace that is
    # never persisted is visible to its own session and to nothing else:
    # no second agent, no second run, no graph query. That failure is
    # invisible from every other counter here -- the decorator reports
    # success, the traces exist, `recall` on the same session even finds
    # them -- which is exactly the shape of failure this project keeps
    # producing.
    check("the session traces were bridged into the graph",
          any((e.get("steps") or 0) > 0 for e in ingested),
          f"steps={[e.get('steps') for e in ingested]} "
          f"stages={[e.get('stages') for e in ingested]} -- nothing was "
          f"persisted, so warm's memory cannot outlive its own session")
    # READ BACK OUT OF AURA. These used to read the stub's own python
    # attributes (`mem.steps`), so they asserted that a dictionary the
    # rehearsal had just filled in contained what the rehearsal had just
    # put there. Now they are Cypher against the database the run wrote
    # to, which is the only version of this check worth having.
    # SCOPED TO THIS REHEARSAL'S OWN TRACES. Aura holds 98 traces and
    # WHAT THIS RUN LEFT IN AURA, scoped to its own dataset.
    #
    # WHAT IT REPLACES, and why none of it survives. Four checks read
    # `(:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)` and asserted that
    # every step carried real reasoning, that no step stored tool-argument
    # JSON as its thought, and -- the subtlest -- that thoughts did not
    # ACCUMULATE across model turns. That last one was earned: the whole
    # 2026-09-20 series passed the first two while every thought was the
    # concatenation of all reasoning so far (lengths 267 -> 1537, never
    # resetting), because Vibe emits one turnId for an entire attempt.
    # 988 of 993 steps were unusable and every counter looked healthy.
    #
    # Cognee writes none of those node types and there is no relay to
    # accumulate: the agent calls `remember` itself, once, for what it
    # chooses to keep. So the honest remaining assertion is the weak one
    # -- this run put something in the graph and it reads back out --
    # and it is worth saying plainly that it is weaker than what it
    # replaced, because the strong version was bought with a bad run.
    rows = await _cypher(
        "MATCH (n) WHERE n.created_at >= $since RETURN count(n) AS n",
        {"since": started_ms})
    landed = rows[0]["n"] if rows else 0
    check("this run put nodes in the graph that read back", landed > 0,
          f"{landed} node(s) created in Aura since the run started")

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
    # THE ACCUMULATION CHECK WENT WITH THE RELAY. It asserted that a
    # step's thought did not grow to contain an earlier one's, and it is
    # the single most valuable check this file ever had: the whole
    # 2026-09-20 series passed every other reasoning check while each
    # thought was the concatenation of all reasoning so far. There is no
    # relay and no per-step thought now, so there is nothing to assert
    # -- recorded here rather than deleted quietly, because if a
    # per-step write ever returns this is the check that has to come
    # back with it.

    # THE COUNTER THIS REPLACES was the sidecar's tally of reasoning vs
    # tool-JSON fall-backs, and it earned its place: six runs wrote 988
    # tool-JSON thoughts out of 993 while every number the operator could
    # see looked healthy. Cognee exposes no such counter and there is no
    # relay to fall back FROM, so the honest thing is to assert nothing
    # about it rather than invent a number that reads as measured.
    #
    # What still has to hold is that the distillation saw something. A
    # skill rewritten from no evidence is the same failure wearing a
    # different mask.
    # WHAT WARM WROTE, read off the event log rather than off a list the
    # rehearsal filled in itself. The old version asserted against its own
    # closure's accumulator, so it could pass with an attempt loop that
    # recorded nothing.
    written = [e for e in bus.events
               if e["type"] == "MEMORY_WRITE" and e.get("swarm") == "warm"]
    check("every warm attempt wrote an outcome document",
          len(written) == 2 and all(w.get("chars") for w in written),
          f"{[(w.get('node_set'), w.get('chars')) for w in written]}")
    check("the document was filed under the grader's verdict",
          all((w.get("node_set") or "").startswith(FIXTURE) for w in written),
          f"{[w.get('node_set') for w in written]} -- node sets are the only "
          f"scoping a recall honours")
    check("the skill rewrite had the grader's score to work from",
          all(w.get("score") is not None for w in written),
          f"scores={[w.get('score') for w in written]}")
    # DID THE HOOK ACTUALLY FIRE? A hook that is installed, registered and
    # never invoked reads identically to one that works, in every number
    # this rehearsal otherwise reports. The scripted model runs one command
    # that cannot succeed, so the failure branch has to have run.
    check("the post_tool hook ran on the agent's failed command",
          any("command(s) of its own" in (w.get("evidence") or "")
              for w in written)
          or any("ran 2 command(s)" in str(w) for w in written)
          or any(w.get("hook_failures") for w in written),
          f"commands={[w.get('hook_commands') for w in written]} "
          f"failures={[w.get('hook_failures') for w in written]} "
          f"recalled={[w.get('hook_chars') for w in written]}")
    # NOTHING ROLLS BACK. The loop just ran for real; if a checkpoint/
    # restore ever returns, this is where it shows up.
    check("no attempt was rolled back",
          not [e for e in bus.events if e["type"] == "RESTORED"],
          "attempts continue from where the last one left the tree")
    # USES_TOOL, confirmed against the live schema -- not a guessed name.
    # NO TOOL-CALL NODES AND NO HOOK CANARY. Both described one retired
    # path: Vibe fired a `post_tool` hook, the hook wrote a ToolCall into
    # the graph, and the canary proved Vibe fires hooks at all in this
    # environment. Each was bought with a real failure -- a run where the
    # hook never fired looked exactly like an agent that made no tool
    # calls. There is no hook now; the agent decides what to remember,
    # and the harness cannot assert that on its behalf without inventing
    # it.

    # ---- 6b. the session must not be the whole project --------------------
    #
    # Every trace ever written shared the session id "warm-0", so that one
    # session holds 3,105 messages from 98 runs. `extract_entities_from_
    # session` walks the whole session, so each run re-extracted the entire
    # history, got slower every time, and crossed the 240s bound on
    # 2026-09-17. The entity layer has been empty since. Nothing asserted
    # session size, so nothing noticed.
    sizes = await _cypher(
        "MATCH (m:Message) WHERE m.session_id = $sid RETURN count(m) AS n",
        {"sid": f"{DATASET}:{bus.run_id}:warm-0"})
    this_run_msgs = sizes[0]["n"] if sizes else 0
    allmsg = await _cypher(
        "MATCH (m:Message) RETURN count(m) AS n", {})
    total_msgs = allmsg[0]["n"] if allmsg else 0
    check("this run's session holds only this run's messages",
          this_run_msgs < max(50, total_msgs // 4),
          f"{this_run_msgs} in this session vs {total_msgs} in the database "
          f"-- a session that grows without bound is what killed entity "
          f"extraction")

    # ENTITY EXTRACTION IS INSIDE `remember` NOW, on the clock, so there
    # is no separate after-clock pass to bound and nothing here to await.
    # The old one ran an OpenAI round trip per message and one run sat
    # blocked in SSL for 18 minutes after its agent work had finished.

    # ---- 7. the skill Cognee rewrote -------------------------------------
    distilled = [e for e in bus.events
                 if e["type"] == "DISTILLED" and e.get("swarm") == "warm"]
    check("the skill was considered after each attempt", len(distilled) == 2,
          f"{len(distilled)}")
    for i, d in enumerate(distilled):
        print(f"    attempt {i + 1}: score {d.get('score')}, "
              f"{'applied' if d.get('accepted') else 'no proposal'}, "
              f"procedure {d.get('procedure_chars')} chars")
    # NO REPAIR LOOP TO CHECK. AIP's validator rejected a malformed
    # skill and the distiller got two turns to fix it, with the
    # validator's own diagnostics handed back each time. Cognee
    # validates nothing of the kind -- a proposal is applied or it is
    # not -- so `repairs` is reported as 0 for event-log shape only, and
    # cognee_layer.DistillResult says so where someone will read it.

    # ---- 8. metrics -------------------------------------------------------
    print("... collecting metrics", flush=True)
    run_metrics = metrics_mod.collect(
        bus.events, run_id=bus.run_id, gpu="none", model="fake-model",
        commit="local", skill_version=None,
        skill_approx_tokens=len(final) // 4, skill_dir_sha="",
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
    # NO VERSION IN THE TABLE. It recorded which skill version each
    # attempt ran on, which was the only way to tell "the loop closed"
    # from "the loop looked closed" while the procedure lived in a
    # registry on this machine and a file on the pod. Cognee rewrites in
    # place, so every attempt runs on whatever it holds and the column
    # is honestly None.
    check("the per-attempt table records no invented version",
          warm is not None
          and all(a["skill_version"] is None for a in warm.per_attempt),
          f"{[a['skill_version'] for a in warm.per_attempt] if warm else None}")
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
    # ONLY the probe is allowed to be blamed on the graph. Wrapping the
    # whole rehearsal in this handler reported a NameError in my own check
    # code as "the graph is not reachable", which is a lie the operator
    # would have had to debug from scratch.
    C.configure(dataset=DATASET)
    try:
        ready = await C.assert_ready()
    except Exception as exc:
        print(f"\nABORT: the graph is not reachable -- {exc!r}")
        print("The rehearsal asserts that the skill loop reaches the "
              "graph. With no graph there is nothing to assert against, "
              "and a stub would make those checks pass while proving "
              "nothing.")
        return 2
    print(f"graph: REAL (Aura), reachable, "
          f"{ready['apoc_procedures']} APOC procedure(s)")
    return await rehearse(vibe, root, server.base_url, server)


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
    # ISOLATION IS THE DATASET NOW, not a copy of the package directory.
    #
    # Distillation used to mutate a version registry on this machine, so
    # the rehearsal copied `skills/` and pointed the registry at the copy
    # -- running it must never advance the real skill. Cognee holds the
    # procedure in the graph instead, and scopes skills, runs and
    # proposals by dataset, so a throwaway dataset per rehearsal gives
    # the same guarantee structurally. Named by clock so two rehearsals
    # never collide, and left behind rather than deleted: when one fails,
    # the graph it built is the evidence.
    global DATASET, FIXTURE
    stamp = int(time.time())
    DATASET = f"msf-rehearsal-{stamp}"
    FIXTURE = f"rehearsal-{stamp}"
    print(f"dataset: {DATASET}")

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
