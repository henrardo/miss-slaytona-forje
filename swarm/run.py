#!/usr/bin/env python3
"""Run a swarm against a repo, with the agents on a remote host.

    swarm/run.py --repo ./fixture --install "pip install -r requirements-v2.txt" \
                 --test "python -m pytest tests -q" --deadline-s 900 \
                 --ssh-host H --ssh-port P --ssh-key K

This file is deliberately thin. The attempt loop, the grading, the trace
keying, `observed_fix`, the shim and gutted-validator gates and every emitted
event are `orchestrator.vibe_agent.migrate_codebase`, unchanged and unwrapped
-- the same function, producing the same graph, in the same way. The only
difference from a local run is the Workspace it is handed: an AgentWorkspace
that runs Vibe over SSH on the swarm host instead of a LocalWorkspace running
it here.

An earlier version of this file had its own attempt loop, its own cruder
`tests_passed` and `error_signature`, and its own outcome strings. It produced
a different graph and would have drifted further with every fix applied to one
copy and not the other.

Where things run, and why:

  agents      the swarm host, one unix user each, home 0700, containing only
              the repo they were given. The harness is not on that machine.
  the model   the same host, at localhost:30000.
  the grader  a fresh Daytona sandbox, driven from HERE -- the one environment
              no agent has touched, which is what makes its verdict ground
              truth, and it keeps DAYTONA_API_KEY off the swarm host.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import re
import socket
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

from daytona import AsyncDaytona
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j_agent_memory import MemoryClient

from orchestrator.events import EventBus
from orchestrator.memory import ScopedMemory, build_settings, reset_graph
from orchestrator.sandbox import SandboxPool, install_cleanup_handlers
from orchestrator.run import (MAX_CONSECUTIVE_AGENT_FAILURES, _smoke_test_tool,
                              run_swarm)
from orchestrator import skills
from orchestrator.distill import distill
from orchestrator import metrics as metrics_mod
from orchestrator import series
from orchestrator.sync import AttemptSync, NullSync
from orchestrator import writers
from orchestrator.writers import AgentWriter, ExternalWriter
from orchestrator.snapshot import load_state, pool_kwargs_from_state
from orchestrator.vibe_agent import (AttemptBudget, MigrationResult,
                                     error_signature, migrate_codebase,
                                     tests_passed)
from orchestrator.manifest import FIXTURE_DIR, load_manifest
from swarm.agent_workspace import (AgentWorkspace, SwarmHost,
                                   install_host_scripts, repo_tarball,
                                   tree_tarball)


def _port_of(url: str) -> int:
    """The port an MCP url points at, for the local forward to mirror."""
    m = re.search(r":(\d+)", url.split("//", 1)[-1])
    if not m:
        raise ValueError(f"no port in {url!r}")
    return int(m.group(1))


class BlockingCallWatch(logging.Handler):
    """Counts asyncio's own "callback took too long" warnings.

    Run 12's whole concurrency failure was one `subprocess.run` inside an
    `async def`: `#running-req` never exceeded 1 across 1,032 scheduler
    samples while the endpoint happily served 4 concurrent requests at 543
    tok/s. Nothing in the harness noticed, because a blocked event loop looks
    exactly like a slow model.

    asyncio already detects this in debug mode -- it logs a WARNING whenever a
    callback exceeds `loop.slow_callback_duration`. It is off by default and
    goes to a logger nobody configured, so this attaches to it, keeps the
    worst offenders and makes the run say so at the end.
    """

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.hits: list[tuple[float, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "took" not in msg or "seconds" not in msg:
            return
        try:
            secs = float(msg.rsplit("took", 1)[1].split("seconds")[0].strip())
        except (IndexError, ValueError):
            secs = 0.0
        self.hits.append((secs, msg))

    def report(self) -> str:
        if not self.hits:
            return "event loop: no blocking callbacks over the threshold"
        worst = sorted(self.hits, reverse=True)[:3]
        lines = [f"BLOCKING EVENT LOOP: {len(self.hits)} callback(s) over the "
                 f"threshold -- agents cannot run concurrently while this happens"]
        lines += [f"     {s:.1f}s  {m[:150]}" for s, m in worst]
        return "\n".join(lines)

# After-the-clock graph enrichment. Generous, because it is real work on a
# long session, but finite: it must never be able to hold a run open.
ENTITY_TIMEOUT_S = 240.0

_HARNESS_BUGS = (TypeError, AttributeError, NameError, ImportError, AssertionError)


def control(host: SwarmHost, port: int, payload: dict) -> dict:
    """One request on the sidecar's control channel, over SSH.

    The sidecar holds the warm agents' ScopedMemory and the Neo4j credentials,
    and it lives on the swarm host beside the agents so the hook still reaches
    it over loopback. `set_trace` is how it learns which trace the current
    attempt belongs to -- in the local design that was an in-process call.
    """
    body = json.dumps(json.dumps(payload))
    out = host.run(
        f"printf %s {body} | python3 -c \"import socket,sys;"
        f"d=sys.stdin.read();s=socket.create_connection(('127.0.0.1',{port}),timeout=60);"
        f"s.sendall((d+chr(10)).encode());print(s.makefile().readline().strip())\"",
        check=False, timeout=120,
    ).stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def proxy_usage(host: SwarmHost, base_url: str) -> dict:
    """Cumulative token counters from a counting proxy on the swarm host.

    Two of them, one per arm, because Vibe never surfaces per-call usage
    outside its own process -- the same reason the local design ran two."""
    out = host.run(
        f"python3 -c \"import urllib.request;"
        f"print(urllib.request.urlopen('{base_url}/usage', timeout=20).read().decode())\"",
        check=False, timeout=60).stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


class RemoteTraceBridge:
    """Tells the remote sidecar which trace an attempt belongs to.

    Locally, `step_memory.set_trace(agent, trace_id)` is a dict assignment.
    The sidecar is now on the swarm host, so the same call goes over SSH. The
    method names match `StepMemoryService` exactly, because migrate_codebase
    calls them without knowing which it has.
    """

    def __init__(self, host: SwarmHost, port: int) -> None:
        self._host, self._port = host, port

    def set_trace(self, agent: str, trace_id) -> None:
        control(self._host, self._port,
                {"control": "set_trace", "agent": agent, "trace_id": str(trace_id)})

    def clear_trace(self, agent: str) -> None:
        control(self._host, self._port, {"control": "clear_trace", "agent": agent})

    def set_pending_reasoning(self, agent: str, text: str, turn_id=None) -> None:
        # The remote sidecar receives reasoning through the hook's own
        # transcript reads; the streamed-entry path is local-only.
        return None

    def note_turn(self, agent: str, turn_id) -> None:
        return None

    @property
    def steps_written(self) -> int:
        """How many steps the hook has written, asked of the sidecar.

        The attempt loop uses this to decide whether transcript back-fill
        is needed. Without it the loop would see 0 on this proxy object,
        replay every attempt on top of the hook's own writes, and double
        every step in the graph.

        0 on any error, which is the safe direction: a back-fill on top of
        nothing is correct, and the run says the hook wrote nothing.
        """
        reply = control(self._host, self._port, {"control": "summary"})
        try:
            return int(reply.get("steps_written") or 0)
        except (TypeError, ValueError):
            return 0

    def flush(self, timeout: float = 120.0) -> bool:
        """Block until the sidecar's write queue is empty.

        Called before anything reads the graph expecting this run's steps to
        be in it -- entity extraction and the summary both do."""
        r = control(self._host, self._port,
                    {"control": "flush", "timeout": timeout})
        return bool(r.get("ok", False))

    def summary(self) -> str:
        return control(self._host, self._port, {"control": "summary"}).get("summary", "")


@contextlib.contextmanager
def tunnels(host: SwarmHost, ports: dict[int, int]):
    """Local port forwards to the pod's loopback, for the duration of a block.

    The MCP servers bind 127.0.0.1 on the pod deliberately -- that is what
    keeps them off the network and their credentials out of reach. Forwarding
    is how the operator-side smoke test reaches them without loosening that,
    and it lets the real `_smoke_test_tool` run against them unchanged rather
    than a second copy of it living on the pod.
    """
    fwd: list[str] = []
    for local, remote in ports.items():
        fwd += ["-L", f"127.0.0.1:{local}:127.0.0.1:{remote}"]
    proc = subprocess.Popen(
        ["ssh", "-i", str(host.identity), "-p", str(host.port),
         "-o", "StrictHostKeyChecking=no", "-o", "ExitOnForwardFailure=yes",
         "-N", *fwd, f"{host.user}@{host.host}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        # ssh -N prints nothing on success, so there is no banner to wait for.
        # Poll the forwarded port instead of sleeping a guessed interval.
        deadline = time.monotonic() + 20
        for local in ports:
            while time.monotonic() < deadline:
                with socket.socket() as s:
                    s.settimeout(1.0)
                    if s.connect_ex(("127.0.0.1", local)) == 0:
                        break
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"ssh forward died: {(proc.stderr.read() or b'').decode()[:200]}")
                time.sleep(0.25)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


async def smoke_test_mcp(urls: dict[str, str]) -> list[str]:
    """Call one real tool on each MCP server and read the answer.

    `_smoke_test_tool` and `_SMOKE_TESTS` are imported, not reimplemented --
    the specs are the ones already chosen for these two servers, and the
    error-string checks are the ones written against the two live failures
    they were found by. Only the transport differs: the pod serves both over
    loopback streamable-HTTP, and `check_mcp_servers` skips those by design
    ("http/sse transports aren't started by us"), so it cannot cover them.

    This is the check that was missing when the memory server published its
    tools to nobody: the process was up and answering, the config listed it,
    and the model was handed no memory tools at all. A run with 22 steps
    written and 0 retrievals looks exactly like a model that chose not to
    read.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    problems: list[str] = []
    for name, url in urls.items():
        try:
            async with streamablehttp_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=60)
                    tools = (await session.list_tools()).tools
                    if not tools:
                        problems.append(f"MCP {name!r} started but published no tools.")
                        continue
                    print(f"  MCP {name}: {len(tools)} tool(s)")
                    problems.extend(await _smoke_test_tool(session, name, tools))
        except Exception as exc:
            problems.append(
                f"MCP server {name!r} at {url} did not answer ({exc!r}). Its "
                f"tools will be silently absent from every agent's tool list."
            )
    return problems


# Differences between the arms that are KNOWN and tolerated. EMPTY, and it
# must stay empty for a run to count toward "clearly working".
#
# It briefly held three entries -- hook_files, config_names, tools -- all
# caused by warm writing to the graph during its attempts through a
# post_tool hook and the reasoning relay. Post-attempt ingestion removed
# the need for any of it (orchestrator/ingest.py), so warm's machine is now
# cold's machine plus a skill.
#
# Anything added back here is a confound in every warm-vs-cold number from
# that run, so a run with a non-empty list is a debugging run and is
# labelled as one in the output.
# DECLARED, not engineered away.
#
# Warm writes the graph natively during an attempt: the memory MCP server
# (~16 tools), a post_tool hook and the reasoning relay. Those are real
# differences between the arms and they are named here so every run
# prints them.
#
# They were once emptied by deleting the mechanism itself, which removed
# the variable under test -- warm's only remaining advantage was a text
# prefix, which is a skill, not memory. An honest confound beats a clean
# comparison of the wrong thing.
#
# What the differences cost, measured: ~1.30-1.49s of hook latency per
# tool call. NOT tokens -- a write puts nothing in the context. The token
# gap was injection, which stays off.
#
# Defined in orchestrator.metrics so the harness's "permitted" and the
# table's "counts" cannot drift apart.
KNOWN_ARM_DIFFERENCES: frozenset[str] = metrics_mod.TREATMENT_DIFFERENCES


def assert_arms_match(spaces: dict[str, AgentWorkspace],
                      labels: list[tuple[str, bool]]) -> list[str]:
    """Refuse to start unless warm and cold differ ONLY in the skill.

    The experiment's entire claim is a one-variable difference, and it has
    silently been a two-variable difference twice: the `web` MCP server was
    registered for warm only, and warm's task prompt carried three extra
    numbered steps. Both were found by reading code afterwards, and every
    token comparison from the runs in between was worthless.

    So it is asserted from the machine's own state, before the clock,
    rather than from a reading of this file. Hooks are included because the
    post_tool hook cost warm ~3.3s per tool call, which is wall-clock the
    deadline charges to warm alone; tool lists are included because a
    missing tool is a missing capability, not a missing memory.

    Skipped when only one arm is running -- there is nothing to compare.
    """
    warm_labels = [l for l, w in labels if w]
    cold_labels = [l for l, w in labels if not w]
    if not warm_labels or not cold_labels:
        return []
    warm_fp = spaces[warm_labels[0]].setup_fingerprint()
    cold_fp = spaces[cold_labels[0]].setup_fingerprint()
    differences = {k: (warm_fp[k], cold_fp[k]) for k in warm_fp
                   if warm_fp[k] != cold_fp[k]}
    unexpected = {k: v for k, v in differences.items()
                  if k not in KNOWN_ARM_DIFFERENCES}
    if unexpected:
        detail = "\n".join(f"    {k}: warm={w!r} cold={c!r}"
                           for k, (w, c) in sorted(unexpected.items()))
        raise RuntimeError(
            "warm and cold are not set up identically. The skill is the only "
            "permitted difference; these are not it:\n" + detail
        )
    if differences:
        print(f"  arms differ in {sorted(differences)} -- KNOWN, and a "
              f"confound in any warm-vs-cold number from this run. See "
              f"KNOWN_ARM_DIFFERENCES.")
        for k in sorted(differences):
            w, c = differences[k]
            print(f"      {k}: warm={_short(w)} cold={_short(c)}")
    else:
        print(f"  arms match exactly: {len(warm_fp['tools'])} tool(s) each, "
              f"hooks {warm_fp['hook_files'] or 'none'}, "
              f"mcp {warm_fp['config_names']}")
    return sorted(differences)


def _short(value, limit: int = 90) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...]"


def experiment_dir(run_id: str) -> Path:
    """Where this experiment's own artifacts go. One directory per run id."""
    return Path(__file__).resolve().parent.parent / "runs" / "experiments" / run_id


def _tree_writer(run_id: str, label: str):
    """Save every attempt's tree, not just the last one.

    The grader is handed the tree anyway, so this costs no round trip --
    see `on_attempt_tree` in migrate_codebase. Kept per attempt because
    attempts now accumulate on one checkout, so the sequence of trees is
    the experiment's record of progress, and because per-attempt
    `closeness` could not be recomputed after either previous series.
    """
    def write(attempt: int, file_contents: dict[str, bytes]) -> None:
        out = experiment_dir(run_id) / "trees"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{label}-a{attempt:02d}.tgz").write_bytes(
            tree_tarball(file_contents))
    return write


async def agent_worker(*, ws: AgentWorkspace, warm: bool, pool: SandboxPool,
                       test_command: str, deadline: float, bus: EventBus,
                       bridge: RemoteTraceBridge, mem: ScopedMemory | None,
                       baseline_signature: str | None, baseline_passed: int,
                       results: list, skill_name: str | None = None,
                       package_path: str | None = None,
                       run_id: str | None = None,
                       distiller: Any | None = None,
                       usage_probe: Any | None = None,
                       sync: Any | None = None,
                       budget: AttemptBudget | None = None,
                       on_attempt_tree: Any | None = None) -> MigrationResult:
    """Retries transient infrastructure failures; reports harness bugs loudly.

    Same split as the local orchestrator's agent_worker, and for the same
    measured reason: one Daytona "Failed to remove sandbox" ended warm-0's
    entire run while cold completed 8 attempts, and the summary read "WARM 0/0
    converged" as though memory had made the agent do nothing.
    """
    arm = "warm" if warm else "cold"

    async def emit(event_type: str, **kw):
        return await bus.emit(event_type, swarm=arm, agent=ws.label, **kw)

    best = MigrationResult(False, 0)
    consecutive_failures = 0

    try:
        return await _attempt_until_done(
            ws=ws, warm=warm, pool=pool, test_command=test_command,
            deadline=deadline, emit=emit, mem=mem, bridge=bridge,
            baseline_signature=baseline_signature,
            baseline_passed=baseline_passed, results=results,
            skill_name=skill_name, package_path=package_path,
            run_id=run_id, distiller=distiller,
            usage_probe=usage_probe, sync=sync, best=best,
            consecutive_failures=consecutive_failures, budget=budget,
            on_attempt_tree=on_attempt_tree)
    finally:
        # ALWAYS, on every exit: converged, clock expired, harness bug,
        # cancelled by run_swarm. An agent that stops without leaving the
        # barrier strands the other arm waiting for an attempt that will
        # never come.
        if sync is not None:
            sync.leave(ws.label)


async def _attempt_until_done(*, ws, warm, pool, test_command, deadline, emit,
                              package_path=None, run_id=None,
                              # EXPLICIT, not a closure over main_async's
                              # local. It was read as a free variable here
                              # and raised NameError on the first real
                              # attempt of the first pod run -- after
                              # provisioning, the model download and the
                              # control test had all been paid for. The
                              # rehearsal cannot catch it: it drives
                              # migrate_codebase directly and never enters
                              # this wrapper. See test_swarm_signatures.
                              bridge,
                              mem, baseline_signature, baseline_passed,
                              results, skill_name, distiller, usage_probe,
                              sync, best, consecutive_failures, budget=None,
                              on_attempt_tree=None):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append((ws.label, warm, best))
            return best
        try:
            result = await migrate_codebase(
                pool=pool,
                workspace=ws,
                test_command=test_command,
                deadline=deadline,
                emit=emit,
                mem=mem,
                # PER RUN, not per agent. This was `ws.label` -- the
                # constant string "warm-0" -- so every trace ever written
                # landed in ONE session: 98 runs, 3,105 messages, one
                # session id. `extract_entities_from_session` walks the
                # whole session, so each run re-extracted the entire
                # history of the project and got slower every time. It
                # crossed the 240s bound on 2026-09-17 and the entity
                # layer has been empty since. The bound exposed this; it
                # did not cause it.
                session_id=f"{run_id}:{ws.label}" if warm else None,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed,
                # The bridge is back: it tells the sidecar which trace the
                # current attempt belongs to, so the post_tool hook's writes
                # land on the right trace. Warm only -- cold has no sidecar,
                # no hook and no graph.
                step_memory=bridge if warm else None,
                # BOTH ARMS, always. This was `ws.label if warm else None`,
                # and the only thing that reads it unconditionally is the
                # attempt barrier -- so cold arrived as "anonymous", which
                # is not one of the barrier's parties, so `arrive()`
                # returned 0.0 immediately and cold never synchronised at
                # all. Warm then waited at barrier 1 for an arm that never
                # came, and was released only when cold LEFT on converging.
                # Measured on the first pod run: warm sat idle from t=195
                # to t=776 and got 2 attempts while cold got 4, which is
                # precisely the contention confound orchestrator/sync.py
                # exists to remove.
                #
                # Safe for cold because every memory-side use of this label
                # is additionally gated on `step_memory is not None`, and
                # cold has no step_memory, no sidecar and no hook.
                agent_label=ws.label,
                skill_name=skill_name,
                package_path=package_path,
                distiller=distiller,
                usage_probe=usage_probe,
                sync=sync,
                budget=budget,
                on_attempt_tree=on_attempt_tree,
            )
            results.append((ws.label, warm, result))
            return result
        except _HARNESS_BUGS as exc:
            print(f"  [{ws.label}] HARNESS BUG, not retrying: {exc!r}")
            traceback.print_exc()
            result = MigrationResult(False, 0)
            results.append((ws.label, warm, result))
            return result
        except Exception as exc:
            # DO NOT emit() from this handler. An earlier version of this
            # clause called emit("ATTEMPT_FAILED", ...), which orchestrator.
            # events.EVENT_TYPES does not declare, so make_event raised
            # ValueError from inside the handler for a Daytona 404 -- run 8's
            # entire cold arm died there, 0 attempts, while warm ran the full
            # clock. The local agent_worker prints and backs off and emits
            # nothing; this is that code, not a variation on it.
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_AGENT_FAILURES:
                print(
                    f"  [{ws.label}] {exc!r} -- "
                    f"{consecutive_failures} consecutive failures, giving up on this agent"
                )
                traceback.print_exc()
                result = MigrationResult(False, best.attempts)
                results.append((ws.label, warm, result))
                return result
            print(
                f"  [{ws.label}] {exc!r} -- retrying "
                f"({consecutive_failures}/{MAX_CONSECUTIVE_AGENT_FAILURES})"
            )
            await asyncio.sleep(min(30.0, 2.0 ** consecutive_failures))


async def main_async(args, watch=None) -> int:
    if not args.no_loop_debug:
        asyncio.get_running_loop().slow_callback_duration = 0.1
    host = SwarmHost(host=args.ssh_host, port=args.ssh_port,
                     identity=Path(args.ssh_key))
    run_id = f"swarm-{int(time.time())}"
    bus = EventBus(run_id)
    bridge = RemoteTraceBridge(host, args.sidecar_port)
    repo = Path(args.repo).resolve()

    if args.reset_memory:
        # Same flag, same function as the local run: measure what the warm
        # agents build for each other WITHIN one run, rather than a graph that
        # has accumulated across runs. Both are real; they are different claims.
        deleted = await reset_graph()
        print(f"--reset-memory: deleted {deleted} node(s) from the shared graph")

    # THE HARNESS'S OWN SCRIPTS, FROM THE REPO, BEFORE ANYTHING ELSE.
    # Uploaded and hash-checked rather than assumed present: until
    # 2026-09-19 nothing put `hook.py` or `reasoning_relay.py` on the pod
    # at all, and the version running during the 2026-09-18/19 series can
    # no longer be established. See install_host_scripts.
    for remote, digest in install_host_scripts(host).items():
        print(f"host script: {remote} sha256 {digest[:12]}")

    baseline_summary = control(host, args.sidecar_port, {"control": "summary"})
    usage_before = {"warm": proxy_usage(host, args.warm_proxy),
                    "cold": proxy_usage(host, args.cold_proxy)}

    # Preflight, before the clock: a dead memory server or sidecar is
    # indistinguishable at run time from "the model chose not to use memory",
    # which is the failure this project has already had 40 times.
    problems = []
    if not control(host, args.sidecar_port, {"control": "summary"}):
        problems.append(f"step-memory sidecar not answering on :{args.sidecar_port}")
    # A urlopen() GET used to stand in for this. It passed while the memory
    # server answered Vibe's handshake with 406 and the model was handed zero
    # memory tools -- the run then reported 22 steps written and 0 retrievals,
    # which reads as a model that chose not to retrieve. Call the tools.
    def _local(url: str, port: int) -> str:
        return re.sub(r"//127\.0\.0\.1:\d+", f"//127.0.0.1:{port}", url)

    try:
        with tunnels(host, {18811: _port_of(args.mcp_url),
                            18813: _port_of(args.web_url)}):
            problems += await smoke_test_mcp({
                "neo4j-agent-memory": _local(args.mcp_url, 18811),
                "web": _local(args.web_url, 18813),
            })
    except Exception as exc:
        problems.append(f"could not reach the pod's MCP servers to test them: {exc!r}")
    for name, url in (("warm", args.warm_proxy), ("cold", args.cold_proxy)):
        if not proxy_usage(host, url):
            problems.append(f"{name} counting proxy not answering at {url}")
    for problem in problems:
        print(f"PREFLIGHT: {problem}")
    if problems:
        return 1

    gpu = host.gpu_description()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    print(f"gpu: {gpu} | harness: {commit}")
    print(f"repo: {repo}")
    tar = repo_tarball(repo, exclude=(".git", "__pycache__", ".venv",
                                      ".pytest_cache", "pytest_cache",
                                      "reference_v2"))
    print(f"tarball: {len(tar):,} bytes")

    # `--swarm-size N` is N agents PER ARM, so the smallest both-arms run is
    # already 2 agents sharing one endpoint. On a single pod that is enough to
    # make them contend: run 12 saw warm-0 abort with "vibe completed no
    # assistant turn" while cold-0 was mid-attempt, which is the documented
    # under-load failure. `--arms warm` / `--arms cold` runs one arm at a
    # time so the comparison is between two clean runs instead of two agents
    # timesharing a GPU.
    want = {"both": (True, False), "warm": (True,), "cold": (False,)}[args.arms]
    labels = [(f"warm-{i}", True) for i in range(args.swarm_size) if True in want] + \
             [(f"cold-{i}", False) for i in range(args.swarm_size) if False in want]
    # The skill the warm arm starts this run on. Read once: every warm agent
    # must begin from the same version, or "which skill produced this result"
    # has as many answers as there are agents.
    live_skill = (skills.archived(args.skill_version)
                  if args.skill_version is not None else skills.current())
    if args.skill_version is not None:
        print(f"skill PINNED to v{args.skill_version}"
              + ("" if args.no_distill else
                 "  WARNING: distillation is on, so this version will be "
                 "superseded mid-run and the comparison is not controlled"))
    if args.no_distill:
        print("distiller: disabled  (the skill cannot change during this run)")
    elif args.distill_writer == "agent":
        print("distiller: the agent's own model  (self-improvement)")
    else:
        print(f"distiller: {args.distill_writer}  (EXTERNAL model: this run "
              f"does not measure self-improvement)")
    print(f"skill: v{live_skill.version} | dir {live_skill.dir_sha} | "
          f"body {live_skill.body_sha} | {len(live_skill.files)} file(s) | "
          f"{live_skill.approx_tokens} approx tokens | "
          f"derived from {len(live_skill.derived_from)} trace(s)")
    skill_shas: dict[str, str] = {}

    spaces: dict[str, AgentWorkspace] = {}
    for label, warm in labels:
        ws = AgentWorkspace(host=host, label=label, model=args.model,
                            model_base_url=args.warm_proxy if warm else args.cold_proxy,
                            auto_compact_threshold=args.auto_compact)
        ws.seed(tar)
        ws.clear_session_logs()
        ws.write_config(web_url=args.web_url)
        r = ws.install_dependencies(args.install)
        if r.returncode != 0:
            print(f"  {label}: install FAILED: {(r.stderr or '')[-200:]}")
        if warm:
            # The skill, before anything else warm gets. Installed into this
            # agent's own VIBE_HOME, so cold has no skills directory at all
            # rather than a disabled one -- the same shape as its missing
            # memory server, and it is re-verified on every run.
            installed = ws.install_skill(live_skill.files,
                                         name=skills.SKILL_NAME,
                                         version=live_skill.version)
            if (installed["dir"] != live_skill.dir_sha
                    or installed["body"] != live_skill.body_sha):
                raise RuntimeError(
                    f"{label}: the installed skill hashes "
                    f"{installed} but the live skill is dir="
                    f"{live_skill.dir_sha} body={live_skill.body_sha}. The "
                    f"agent would run against a different procedure than the "
                    f"one this run records."
                )
            skill_shas[label] = installed["body"]
            # NATIVE GRAPH WRITES, back where they belong.
            #
            # These were removed on a token argument that did not apply to
            # them. Measured: warm's extra ~20,814 tokens/turn were
            # INJECTION (12,236, 59%) plus the agent's own memory-MCP tool
            # RESULTS. Both are reads. A write sends data out and puts
            # nothing in the context -- its cost is latency (1.30-1.49s per
            # tool call), not tokens. Removing the writes bought nothing on
            # the metric and cost the live graph.
            #
            # Injection stays OFF. That is the part that was expensive.
            ws.enable_memory(mcp_url=args.mcp_url,
                             sidecar_port=args.sidecar_port)
            loaded = ws.assert_memory_tools_loaded()
            print(f"  {label} memory tools: {len(loaded)} loaded")
            ws.clear_session_logs()   # drop the probe session, not the run's

            # The distiller's own environment: separate VIBE_HOME (so the
            # memory MCP server exists nowhere near an attempt), separate
            # working directory (so it cannot edit the checkout between
            # attempts) and separate endpoint (so its tokens are counted
            # apart).
            ws.enable_distillation(mcp_url=args.mcp_url,
                                   model_base_url=args.distill_proxy)
            ws.invoke_vibe("Reply with the single word: ready", timeout=300.0)
        else:
            # Verified every run, not assumed. "Cold never sees a skill" is a
            # claim about this machine, and the cheap way to be wrong about it
            # is to change where skills are installed and leave the old path
            # behind on a reused pod.
            if ws.has_skills_dir():
                raise RuntimeError(
                    f"{label} is a COLD agent and has a skills directory. "
                    f"Cold must have no skill and no graph; this run would "
                    f"compare warm against a cold arm that also had one."
                )
            # Both arms probe, so `loaded_tools` has a meta.json to read
            # and the tool lists can actually be compared. Without it the
            # comparison silently passes on two empty lists -- which is how
            # warm-only `web` survived two runs.
            ws.invoke_vibe("Reply with the single word: ready", timeout=300.0)
        # Fill the tree/transcript cache before the clock. Without this the
        # first attempt pays ~14s of blocking ssh inside the event loop --
        # see AgentWorkspace.refresh().
        ws.prime()
        spaces[label] = ws
        print(f"  {label} seeded{' (memory)' if warm else ''}")

    arm_differences = assert_arms_match(spaces, labels)
    # AFTER the fingerprint, which reads the probe session's meta.json for
    # the tool list. Dropping the probe first would leave nothing to read.
    for ws in spaces.values():
        ws.clear_session_logs()

    # The starting state, so attempt 1's trace is keyed on the error the suite
    # actually begins with rather than on the task description -- the same
    # reason the local run.py computes a baseline.
    probe = spaces[labels[0][0]]
    base = await pool_baseline(probe, args.test, args.install)
    baseline_signature, baseline_passed = base
    print(f"baseline: {baseline_passed} passing | {baseline_signature or '(none)'}")

    state = load_state()
    async with AsyncDaytona() as client, MemoryClient(build_settings()) as mem_client:
        pool = SandboxPool(client, run_id=run_id, **pool_kwargs_from_state(state))
        install_cleanup_handlers(pool)
        deadline = time.monotonic() + args.deadline_s
        results: list = []

        # Stamped onto every trace this run writes. See
        # ScopedMemory.set_provenance for why it cannot live in `metrics`.
        provenance = {
            "prov_model": args.model,
            "prov_gpu": gpu,
            "prov_commit": commit,
            "prov_writable": all(ws.checkout_is_writable()
                                 for ws in spaces.values()),
            # WHICH codebase. Without it a distiller on a new fixture
            # learns from the old fixture's traces -- measured: 25 of them
            # on the very first distillation, before the new fixture had
            # written any.
            "prov_fixture": FIXTURE_DIR.name,
            # WHICH EXPERIMENT. `prov_fixture` stops a distiller learning
            # from a different codebase; it does NOT stop it learning from
            # every earlier run on the SAME codebase. On 2026-09-20 warm's
            # attempt 1 wrote 103 steps and the distiller was handed 2,574
            # -- the other 2,471 came from the previous night's 14 runs --
            # which rendered to 11,818,940 characters and drew a hard 400
            # (the author's ceiling is 10,485,760 characters per message).
            # An experiment is N attempts on one checkout, so eligibility
            # is scoped to the experiment that wrote the trace.
            "prov_experiment": run_id,
        }
        print(f"provenance: {provenance}")
        if not provenance["prov_writable"]:
            print("  WARNING: at least one checkout is READ-ONLY -- agents "
                  "cannot edit source; this run is not a fair test")

        def _scoped(client, label, prov):
            m = ScopedMemory(client, user_identifier=label)
            m.set_provenance(**prov)
            return m

        def distiller_for(label: str, scoped: ScopedMemory):
            """One distillation turn for this agent, bound to its own
            workspace and memory scope.

            A closure rather than arguments threaded through
            migrate_codebase: the attempt loop should know that something
            happens after an attempt, not how a skill is written.
            """
            writer = writers_by_label[label]

            async def run(*, attempt: int, tests_passed: int,
                          suite_passed: bool, error: str | None):
                # No seeding. `distill` calls `clear_distilled` before every
                # turn, because Vibe's write_file refuses to overwrite an
                # existing file -- seeding the output path is precisely what
                # made every distillation fail in the first rehearsal.
                outcome = await distill(
                    workspace=spaces[label], mem=scoped, model=args.model,
                    writer=writer,
                    attempt=attempt, tests_passed=tests_passed,
                    suite_passed=suite_passed, error=error,
                    experiment=run_id,
                )
                # AND PUT IT ON THE POD. Without this the loop was open:
                # `propose` writes the accepted version to the
                # orchestrator's disk and moves the live pointer, but the
                # agent reads $VIBE_HOME/skills, which was last written at
                # run setup. So attempt N+1 re-read the SAME procedure while
                # the event log said it was on the new one -- the skill could
                # never improve within a run, which is exactly what the
                # can't-one-shot-it task is meant to measure.
                if outcome.accepted is not None:
                    ws = spaces[label]
                    got = ws.install_skill(outcome.accepted.files,
                                           name=skills.SKILL_NAME,
                                           version=outcome.accepted.version)
                    if got["body"] != outcome.accepted.body_sha:
                        # Do not fail the run: the attempt loop continues on
                        # whatever install_skill last verified, and a loud
                        # line beats a silent version mismatch.
                        print(f"  {label}: distilled v"
                              f"{outcome.accepted.version} did not install "
                              f"cleanly ({got} vs body="
                              f"{outcome.accepted.body_sha}); the next "
                              f"attempt runs on v"
                              f"{ws.installed_skill_version}")
                return outcome
            return run

        scopes = {label: _scoped(mem_client, label, provenance)
                  for label, w in labels if w}
        # Built here, not inside the closure, so the run can read the
        # external writer's own token counters afterwards. An OpenAI call
        # does not pass through the counting proxy, so without this the
        # distillation cost of an external writer reports as ZERO -- which
        # reads as a distiller that was free rather than one that was
        # never measured.
        writers_by_label = {
            label: (AgentWriter(spaces[label])
                    if args.distill_writer == "agent"
                    else ExternalWriter(args.distill_writer))
            for label, w in labels if w
        }

        # One barrier across BOTH arms. With a single arm there is nothing
        # to synchronise and NullSync keeps the call sites uniform.
        running = [label for label, _ in labels]
        arms_present = {w for _, w in labels}
        sync = (AttemptSync(running) if len(arms_present) > 1 else NullSync())

        def tasks_for(warm: bool) -> list:
            return [asyncio.ensure_future(agent_worker(
                ws=spaces[label], warm=warm, pool=pool, test_command=args.test,
                deadline=deadline, bus=bus, bridge=bridge,
                mem=scopes.get(label) if warm else None,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed, results=results,
                # Warm only, and it is the ONLY thing warm's prompt carries
                # that cold's does not. Cold has no skills directory, so the
                # prefix would be a stray token rather than a load.
                package_path=load_manifest().get("package_path"),
                run_id=run_id,
                skill_name=skills.SKILL_NAME if warm else None,
                # Cold never distils: it has no skill to improve and no
                # graph to read. Verified every run by assert_arms_match.
                distiller=(None if args.no_distill else
                           (distiller_for(label, scopes[label]) if warm else None)),
                # Sampled at each attempt boundary, and charged to
                # off_clock -- the harness measuring, not the agent working.
                usage_probe=(lambda url=(args.warm_proxy if warm
                                         else args.cold_proxy):
                             proxy_usage(host, url)),
                sync=sync,
                # ONE BUDGET PER AGENT, constructed here so warm and cold
                # each get their own N attempts. Sharing one object between
                # the arms would let whichever arm ran faster eat the
                # other's allowance.
                budget=(AttemptBudget(args.attempts) if args.attempts > 0
                        else None),
                on_attempt_tree=_tree_writer(run_id, label),
            )) for label, w in labels if w is warm]

        # `run_swarm` unchanged from the local orchestrator: the moment one
        # agent in a swarm converges, the rest of THAT swarm is cancelled
        # rather than left grinding out the deadline. The arms stay
        # independent, so warm stopping early does not touch cold.
        stop = not args.no_stop_for_victory
        await asyncio.gather(
            run_swarm("warm", tasks_for(True), stop_on_success=stop),
            run_swarm("cold", tasks_for(False), stop_on_success=stop))
        swept = await pool.sweep()

        # Entities, once, AFTER the agents' clock has stopped and while the
        # client is still open -- the same two calls, in the same order, as
        # the local run. Messages are stored during the run with
        # extract_entities=False because extraction is an LLM round-trip and
        # inline it cost warm 45s per attempt; and nothing in the package
        # reads ReasoningStep.thought, which is where the substance is on a
        # coding task, so link_step_entities covers that gap.
        # The hook queues its writes (see StepMemoryService._queue), so drain
        # them before anything reads the graph. link_step_entities walks
        # ReasoningStep.thought; a step still sitting in the queue is a step
        # it cannot link, and the run would under-report without saying so.
        if not bridge.flush():
            print("  WARNING: the step-memory write queue did not drain -- "
                  "entity extraction and the counts below are incomplete")
        # BOUNDED. Both of these are OpenAI round trips -- one per message
        # for extraction -- and they run AFTER the measured window, so a
        # slow or rate-limited key cannot change a result but can stall the
        # run indefinitely. One did: the event log showed FILE_DONE at
        # t=214 and the process was still inside this block 18 minutes
        # later, blocked in SSL, holding up an A/B sweep.
        #
        # Nothing in the distillation loop reads these -- the distiller uses
        # search_steps and trace_steps -- so a timeout costs entity edges
        # and is recorded as such.
        entities_extracted, steps_linked = 0, 0
        for label, warm in labels:
            if not warm:
                continue
            scoped = ScopedMemory(mem_client, user_identifier=label)
            try:
                stats = await asyncio.wait_for(
                    scoped.extract_entities_from_session(label),
                    timeout=ENTITY_TIMEOUT_S)
                entities_extracted += sum(v for v in stats.values() if isinstance(v, int))
            except asyncio.TimeoutError:
                print(f"  entity extraction for {label} exceeded "
                      f"{ENTITY_TIMEOUT_S:.0f}s and was abandoned -- the "
                      f"run's own numbers are unaffected, the graph has "
                      f"fewer entity edges")
            except Exception as exc:
                print(f"  entity extraction failed for {label}: {exc!r}")
            try:
                steps_linked += await asyncio.wait_for(
                    scoped.link_step_entities(label),
                    timeout=ENTITY_TIMEOUT_S)
            except asyncio.TimeoutError:
                print(f"  step entity linking for {label} exceeded "
                      f"{ENTITY_TIMEOUT_S:.0f}s and was abandoned")
            except Exception as exc:
                print(f"  step entity linking failed for {label}: {exc!r}")

    # Did the skill actually reach the model? Installed, hashed and prefixed
    # are three separate things that can each succeed while the agent runs
    # with no procedure at all -- the same silent shape as run 9's memory
    # server, which was configured, up, answering, and handed the model zero
    # tools. Read off the agent's own transcript, after the clock.
    # Checked against the version THAT ATTEMPT started on, which is not the
    # version the run started on. Once distillation worked, the two
    # diverged by design: run 10 began on v5 and its three attempts loaded
    # v5, v6 and v7. Comparing against `live_skill` reported "skill v5
    # reached 0/1 warm agent(s)" -- a false negative, and the exact reading
    # this check exists to rule out.
    skill_loaded: dict[str, bool] = {}
    last_version = {                         # label -> version of its last attempt
        e["agent"]: e.get("skill_version")
        for e in bus.events if e["type"] == "ATTEMPT_START"
    }
    for label, warm in labels:
        if not warm:
            continue
        loaded = spaces[label].loaded_skill_text(skills.SKILL_NAME)
        served = skills.identify(loaded) if loaded else None
        want = last_version.get(label)
        skill_loaded[label] = served is not None and served == want
        if loaded is None:
            print(f"  {label}: SKILL NEVER LOADED -- no skill tool result in "
                  f"the transcript. Vibe did not treat the prompt as an "
                  f"invocation; the agent worked with no procedure.")
        elif served is None:
            print(f"  {label}: skill loaded but its text matches NO archived "
                  f"version -- Vibe served something that is not a version "
                  f"this run wrote, so what the agent read is unknown.")
        elif served != want:
            print(f"  {label}: last attempt started on v{want} but the "
                  f"transcript served v{served} -- the install after "
                  f"distillation did not reach the agent before it ran.")
        else:
            print(f"  {label}: skill v{served} reached the model on its last "
                  f"attempt (this run ran v"
                  f"{live_skill.version}..v{served})")

    summary = control(host, args.sidecar_port, {"control": "summary"})
    # THE SIDECAR AND THE HOOK MUST BE SILENT NOW. Nothing writes to the
    # graph during an attempt any more, so a non-zero count here means a
    # hooks.toml survived on a reused pod and warm is paying per-tool-call
    # latency cold does not -- exactly the confound this removed.
    live_hook_writes = summary.get("steps_written", 0) - baseline_summary.get("steps_written", 0)
    live_injections = summary.get("context_returned", 0) - baseline_summary.get("context_returned", 0)
    # Where this run's thoughts came from. Deltas for the same reason the
    # two above are deltas -- the sidecar outlives a single run on a reused
    # pod, and reading its cumulative totals as this run's is the odometer
    # mistake NOTES-hard-won.md records against the proxies.
    def _delta(field: str) -> int:
        return (summary.get(field) or 0) - (baseline_summary.get(field) or 0)
    from_reasoning = _delta("thoughts_from_reasoning")
    from_tool_input = _delta("thought_fallbacks")
    reasoning_pushes = _delta("reasoning_pushes")
    # THE HOOK FIRING IS THE TREATMENT. This used to print "the step hook
    # is still live ... this run cannot be compared" whenever the counter
    # moved -- written when a redesign had moved memory off the attempt
    # path, and left behind when memory moved back. It therefore fired on
    # every healthy run and declared it uncomparable, which is false and
    # contradicts `counts_toward_clearly_working`. The alarm is the other
    # way round: warm writing NOTHING means warm is cold with extra
    # latency.
    if live_hook_writes or live_injections:
        print(f"  live graph writes during the attempts: {live_hook_writes} "
              f"step(s), {live_injections} injection(s) of prior agents' "
              f"steps. This is warm's treatment, and it costs latency, not "
              f"tokens.")
    elif any(w for _, w in labels):
        print("  WARNING: the step hook wrote NOTHING during any attempt. "
              "Warm carried the hook's latency and got no graph for it, so "
              "the next distillation has nothing new to read.")

    print("\n" + "=" * 60)
    print(f"hardware: {gpu} | model: {args.model}")
    for arm_warm in (True, False):
        rows = [r for r in results if r[1] is arm_warm]
        key = "warm" if arm_warm else "cold"
        after = proxy_usage(host, args.warm_proxy if arm_warm else args.cold_proxy)
        d_in = after.get("prompt_tokens", 0) - usage_before[key].get("prompt_tokens", 0)
        d_out = after.get("completion_tokens", 0) - usage_before[key].get("completion_tokens", 0)
        name = "WARM (shared memory)" if arm_warm else "COLD (no memory)  "
        print(f"{name}: {sum(1 for r in rows if r[2].success)}/{args.swarm_size} converged"
              f" | {sum(r[2].attempts for r in rows)} attempts"
              f" | errors cleared {max((r[2].errors_cleared for r in rows), default=0)}"
              f" | best tests passing {max((r[2].best_passed for r in rows), default=0)}"
              f" | in {d_in:,} / out {d_out:,}")

    graded = sum(1 for e in bus.events if e["type"] == "ATTEMPT_DONE")
    oracle = sum(1 for e in bus.events if e["type"] == "SANDBOX_CREATED")
    if watch is not None:
        print(f"     {watch.report()}")
    print(f"\nGATE {'ok' if graded and oracle else 'FAILED'}: {graded} attempt(s) "
          f"graded by {oracle} real Daytona run(s); {swept} sandbox(es) swept")
    # What ingestion wrote, off the clock, from each attempt's own stream.
    # This replaces the step-hook counters: the hook is gone, and reporting
    # its always-zero numbers would read as "warm's graph is empty".
    # `or 0`, not a default. On the LIVE-HOOK path these fields are None --
    # deliberately, because the hook wrote the steps and back-fill never
    # ran, so "how many carry reasoning" is UNCOUNTED, which is a different
    # fact from zero. `sum(e.get(k, 0) ...)` reads the key, gets None, and
    # dies with `int + NoneType` -- which is exactly what happened at the
    # end of the first pod run, AFTER both arms had converged and the
    # summary had printed, taking the metrics file, the cross-run row and
    # the series document with it. All three were recoverable from the
    # event log, which is the only reason that was survivable.
    ingested = [e for e in bus.events if e["type"] == "INGESTED"]
    def _total(field: str) -> int:
        return sum(e.get(field) or 0 for e in ingested)
    live = [e for e in ingested if e.get("with_reasoning") is None]
    reasoning = (f"{_total('with_reasoning')} with the model's own reasoning"
                 if not live else
                 f"reasoning counted on {len(ingested) - len(live)} of "
                 f"{len(ingested)} attempt(s) -- the rest were written live "
                 f"by the hook and not re-counted")
    print(f"     graph writes: {_total('steps')} step(s) from "
          f"{len(ingested)} attempt(s), {reasoning}, "
          f"{_total('failed_tool_calls')} failed tool call(s) recorded")
    if skill_loaded:
        final = skills.current()
        # Started..ended, because a run with distillation on does not have
        # "the" version -- naming only the starting one made a working loop
        # look like a broken one.
        print(f"     skill started v{live_skill.version} "
              f"({live_skill.approx_tokens} approx tokens), ended v"
              f"{final.version} ({final.approx_tokens}); the version each "
              f"agent started its last attempt on reached "
              f"{sum(skill_loaded.values())}/{len(skill_loaded)} warm agent(s)")
    print(f"     entities extracted after the clock stopped: {entities_extracted} "
          f"from messages, {steps_linked} TOUCHED edge(s) from reasoning steps")
    # The alarm is on TOTAL graph writes -- live-hook plus back-fill --
    # because either route leaving the graph empty has the same
    # consequence: the next distillation has nothing to learn from and
    # warm is cold with extra latency.
    total_steps = _total("steps") + live_hook_writes
    if any(w for _, w in labels) and total_steps == 0:
        print("     NOTHING REACHED THE GRAPH -- neither the post_tool hook "
              "nor back-fill wrote a step, so the next distillation has "
              "nothing to learn from and warm == cold.")
    else:
        # WHERE THE THOUGHTS CAME FROM -- on BOTH paths.
        #
        # The previous version of this alarm was `elif _total("steps") and
        # _total("with_reasoning") == 0 and not live`. Every attempt of the
        # 2026-09-18/19 series was live, so `not live` was False and the
        # alarm was unreachable on the only path production uses. The graph
        # took 993 steps of which 988 held serialised tool input and this
        # line said nothing, six runs running.
        #
        # The live path's count comes from the sidecar, which is the only
        # thing that sees it; the back-fill path's from the INGESTED events.
        back_filled = _total("with_reasoning") if not live else 0
        thoughts = from_reasoning + back_filled
        fell_back = from_tool_input
        if thoughts or fell_back:
            print(f"     thoughts: {thoughts} carry the model's own "
                  f"reasoning, {fell_back} fell back to serialised tool "
                  f"input ({reasoning_pushes} reasoning push(es) received "
                  f"from the relay)")
        alarm = metrics_mod.reasoning_verdict(thoughts, fell_back,
                                              reasoning_pushes)
        if alarm:
            print(f"     {alarm}")
    for label, warm in labels:
        if warm:
            # Into the event log, so the judgement is re-derivable from the
            # record rather than only visible in stdout that dies with the pod.
            await bus.emit("STEP_WRITES", swarm="warm", agent=label,
                           thoughts_from_reasoning=from_reasoning,
                           thought_fallbacks=from_tool_input,
                           reasoning_pushes=reasoning_pushes)
            break
    # Metrics last, derived from the event log rather than from anything
    # accumulated along the way -- rerunnable against runs/<id>.jsonl, so a
    # bug here cannot corrupt the record it describes.
    # Where the distillation tokens come from depends on WHO wrote the
    # skill: the agent's turns go through the pod's counting proxy, an
    # external model's do not and are counted by the writer itself.
    distil_usage = {}
    for label, warm in labels:
        if not warm:
            continue
        writer = writers_by_label.get(label)
        own = getattr(writer, "usage", None)
        distil_usage["warm"] = (dict(own) if own is not None
                                else proxy_usage(host, args.distill_proxy))
        break
    run_metrics = metrics_mod.collect(
        bus.events, run_id=run_id, gpu=gpu, model=args.model, commit=commit,
        skill_version=live_skill.version,
        skill_approx_tokens=live_skill.approx_tokens,
        skill_dir_sha=live_skill.dir_sha,
        arms_identical=not arm_differences,
        known_differences=list(arm_differences),
        distil_usage=distil_usage,
        gpu_usd_per_hour=args.gpu_usd_per_hour,
    )
    metrics_path = metrics_mod.write(run_metrics)
    table_path = metrics_mod.append_to_table(run_metrics)
    print(metrics_mod.summarise(run_metrics))

    # RUN_END, so the event log is self-contained. It was declared in
    # EVENT_TYPES and never emitted, which left the log with no terminal
    # marker at all -- a run killed by a dying pod and a run that finished
    # look the same from the file, and two H200s have already died mid-run.
    # It carries the hardware and the rate because a chart drawn months
    # later should not have to find the run's console output to learn what
    # it cost.
    await bus.emit(
        "RUN_END", gpu=gpu, model=args.model, fixture=FIXTURE_DIR.name,
        gpu_usd_per_hour=args.gpu_usd_per_hour,
        gpu_usd=run_metrics.gpu_usd, run_seconds=run_metrics.run_seconds,
        counts_toward_clearly_working=run_metrics.counts_toward_clearly_working,
    )

    # The chart-ready document, written without being asked. A plotting
    # step that has to be remembered is a plotting step that gets skipped
    # on the run that mattered; this is pure and derived from the events,
    # so it cannot affect the record it describes. Wrapped because a
    # charting bug must never be able to fail a finished run.
    series_path = metrics_path.parent / f"{run_id}-series.json"
    try:
        series_path.write_text(json.dumps(
            series.within_run(bus.events, run_id=run_id,
                              fixture=FIXTURE_DIR.name), indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001 -- never fail a graded run
        print(f"  series document not written: {exc!r} (the event log and "
              f"metrics are unaffected; rerun scripts/plot_series.py)")
        series_path = None

    # LAST. `bus.close()` used to run ~100 lines earlier, before the
    # summary, so the RUN_END added later emitted into a closed file and
    # the run died with "I/O operation on closed file" -- after both arms
    # had finished and everything had been printed. The log must stay open
    # until nothing else will be written to it.
    bus.close()

    print(f"event log: runs/{run_id}.jsonl | metrics: {metrics_path} | "
          f"table: {table_path}"
          + (f" | series: {series_path}" if series_path else ""))
    return 0 if (graded and oracle) else 1


async def pool_baseline(ws: AgentWorkspace, test_command: str,
                        install_command: str) -> tuple[str | None, int]:
    """The pristine suite's own verdict, from the agent's own environment."""
    out = ws.host.run_as(
        ws.user, f"cd {ws.repo_path} && {ws.venv}/bin/{test_command} 2>&1 | tail -40",
        check=False, timeout=900).stdout
    return error_signature(out), tests_passed(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", required=True)
    p.add_argument("--install", required=True, help="the repo's own dependency install command")
    p.add_argument("--test", required=True, help="the repo's own test command")
    # A SAFETY NET, not the bound. `--attempts` decides how long an
    # experiment runs; this only stops a wedged agent from running forever.
    # It used to be the only bound, which is why runs came out anywhere
    # between 2 and 4 attempts depending on how slow the model felt.
    p.add_argument("--deadline-s", type=float, default=7200.0)
    p.add_argument("--attempts", type=int, default=3,
                   help="attempts per agent in this experiment: attempt, "
                        "distil a skill, continue from where the agent left "
                        "off, distil again, stop. 0 means unbounded (the old "
                        "clock-bounded behaviour).")
    p.add_argument("--swarm-size", type=int, default=1,
                   help="agents PER ARM; --swarm-size 1 --arms both is 2 agents.")
    p.add_argument("--no-stop-for-victory", action="store_true",
                   help="let both arms run the full deadline even after one "
                        "converges. Required for measurement runs: stopping "
                        "early censors the winner's distribution and leaves "
                        "the other agents' undefined.")
    p.add_argument("--no-loop-debug", action="store_true",
                   help="disable asyncio debug mode and the blocking-call guard.")
    p.add_argument("--arms", choices=("both", "warm", "cold"), default="both",
                   help="which arm(s) to run. One arm per run avoids two "
                        "agents contending for a single endpoint.")
    p.add_argument("--model", default="Qwen/Qwen3-14B")
    # The pod's all-in hourly rate, from RunPod. No default: a wrong number
    # here is worse than none, and 0.0 reports as "unknown", never as free.
    # What it buys is the only honest answer to "what did this experiment
    # cost" -- two H200s have already been lost mid-run, and neither loss
    # is visible anywhere in the record.
    p.add_argument("--gpu-usd-per-hour", type=float, default=0.0,
                   help="pod's all-in $/hr; omitted means spend is reported "
                        "as unknown rather than as zero")
    # Vibe's own default (200,000) assumes a large-context model and never
    # fires before a 32k model's own limit does; 24000 is the Qwen3-14B
    # figure. It has to track the served model's context window, so it is a
    # flag rather than a constant -- Mistral Small 4 reports 128,000.
    p.add_argument("--auto-compact", type=int, default=24000,
                   help="Vibe auto_compact_threshold; size to the model's context.")
    p.add_argument("--ssh-host", required=True)
    p.add_argument("--ssh-port", type=int, required=True)
    p.add_argument("--ssh-key", required=True)
    p.add_argument("--mcp-url", default="http://127.0.0.1:8811/mcp")
    p.add_argument("--web-url", default="http://127.0.0.1:8813/mcp",
                   help="web_lookup MCP server; registered for BOTH arms.")
    p.add_argument("--sidecar-port", type=int, default=8812)
    p.add_argument("--reset-memory", action="store_true",
                   help="Wipe the Neo4j graph before starting.")
    p.add_argument("--warm-proxy", default="http://127.0.0.1:8821")
    p.add_argument("--cold-proxy", default="http://127.0.0.1:8822")
    # A THIRD counting proxy, for the distillation turn alone. Vibe never
    # surfaces per-call usage, so a separate endpoint is the only place
    # "what did the skill cost to produce" can be read apart from "what
    # did the attempt cost".
    p.add_argument("--distill-proxy", default="http://127.0.0.1:8823")
    # WHO WRITES THE SKILL. "agent" is the mission's claim -- the warm
    # agent improves its own procedure on the served model. Naming an
    # external model instead changes the result from "the agent improved
    # itself" to "a stronger model distilled a procedure from its
    # traces", which is a different claim and must be reported as one.
    # The writer is stamped into every run's metrics for that reason.
    # HOLD THE SKILL CONSTANT. Pins warm to an archived version instead of
    # whatever is live, so a run measures one skill rather than a moving
    # one. Pair with --no-distill or the pinned version is superseded by
    # the first acceptance and the run stops being a controlled one.
    p.add_argument("--skill-version", type=int, default=None,
                   help="install this archived skill version instead of the "
                        "live one (skills/versions/vNNN-*.md).")
    p.add_argument("--no-distill", action="store_true",
                   help="skip the distillation turn. Required when pinning "
                        "a version, so the skill under test cannot change "
                        "underneath the run.")
    # A FRONTIER MODEL BY DEFAULT, because AIP says so: "Use the largest
    # frontier model available when using the AIP skill. The work is
    # cognitively intense and underrepresented in current training data --
    # smaller models struggle. For consuming the resulting skill, the
    # opposite holds." Authoring and consumption are different jobs and
    # this experiment only needs the SMALL model for the second.
    #
    # This defaulted to "agent" and all three runs of 2026-09-18 took the
    # default, so Mistral-Small-4 authored its own procedure and collapsed
    # it from 24 steps to 11. The capability was built and simply not
    # switched on.
    p.add_argument("--distill-writer", default=writers.author_model(),
                   help=f"an OpenAI model id (default: OPENAI_AUTHOR, "
                        f"currently {writers.author_model()}) or 'agent' "
                        "to make the warm model "
                        "write its own skill through Vibe and its memory "
                        "tools -- self-improvement, which AIP's own "
                        "guidance advises against for authoring.")
    args = p.parse_args()
    watch = BlockingCallWatch()
    if not args.no_loop_debug:
        # asyncio's debug mode is what surfaces a blocked loop at all. 0.1s is
        # far below anything legitimate here -- every real wait in this
        # harness is awaited, so a callback holding the loop for a tenth of a
        # second is a bug, not load.
        logging.getLogger("asyncio").addHandler(watch)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    rc = asyncio.run(main_async(args, watch), debug=not args.no_loop_debug)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
