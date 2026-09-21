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
import os
import re
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any

from daytona import AsyncDaytona
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.events import EventBus
from orchestrator import cognee_layer as C
from orchestrator.sandbox import SandboxPool, install_cleanup_handlers
from orchestrator.run import (MAX_CONSECUTIVE_AGENT_FAILURES, _smoke_test_tool,
                              run_swarm)
from orchestrator import metrics as metrics_mod
from orchestrator import surfaces
from orchestrator import series
from orchestrator.sync import AttemptSync, NullSync
from orchestrator.snapshot import load_state, pool_kwargs_from_state
from orchestrator.vibe_agent import (AttemptBudget, MigrationResult,
                                     _collect_file_contents,
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


# THE SIDECAR IS GONE, and with it the bridge that talked to it.
#
# `RemoteTraceBridge` told a sidecar process on the pod which trace the
# current attempt belonged to, so that Vibe's `post_tool` hook could
# attach the steps it wrote to the right one. The hook, the sidecar, the
# reasoning relay and the trace model they served are all retired with
# neo4j-agent-memory (archive/neo4j-agent-memory-2026-09-20/).
#
# Under Cognee there is no harness code on the pod at all: the MCP server
# is installed from PyPI by provision_cognee.sh and runs as root, the
# agent calls `remember` on it if it chooses to, and the deterministic
# writes happen HERE, in this process, through `cognee.agent_memory`.
# The `step_memory` seam migrate_codebase used to expose went with it:
# there is no second writer to tell which trace an attempt belongs to.


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


@contextlib.contextmanager
def reverse_tunnel(host: SwarmHost, remote_port: int, local_port: int):
    """Expose a HARNESS-side port on the pod's loopback, for a block.

    THE OPPOSITE DIRECTION FROM `tunnels`, and the reason it exists is a
    measured fault, not a preference.

    A cognee process keeps its users, datasets and vector index in LOCAL
    SQLite and LanceDB; only the GRAPH is remote. So a cognee-mcp running
    on the pod is not a window onto the harness's memory -- it is a
    SECOND, EMPTY memory that happens to write into the same Neo4j
    database. Measured 2026-09-21 with a fresh store against the same
    Aura:

        default user id: ca938241-...        (a new one, not the harness's)
        datasets visible: ['podprobe']       (its own; the harness's 31 are not)
        recall(datasets=["msf-..."]) -> DatasetNotFoundError:
            "Dataset names resolve only among the datasets you own"

    A warm agent on that server calls `cognee_recall` and gets nothing,
    forever, while the config, the server and every log line look healthy
    -- which reads as "the model chose not to use memory" and is the exact
    failure this project has already spent 40 runs on.

    So the server runs HERE, beside the orchestrator, sharing its stores,
    and the pod reaches it through `ssh -R`. The agent's URL does not
    change: it still dials 127.0.0.1:8811 on its own loopback. Two things
    come free -- the Neo4j password never reaches the pod at all, and the
    topology is now the one the rehearsal proves, since there the MCP
    server and the harness are on one machine by construction.

    The cost is a dependency the old arrangement did not have: if this
    tunnel dies, warm's tools die with it. That is why the preflight calls
    a tool through it rather than checking the socket.
    """
    proc = subprocess.Popen(
        ["ssh", "-i", str(host.identity), "-p", str(host.port),
         "-o", "StrictHostKeyChecking=no", "-o", "ExitOnForwardFailure=yes",
         "-o", "ServerAliveInterval=15",
         "-N", "-R", f"127.0.0.1:{remote_port}:127.0.0.1:{local_port}",
         f"{host.user}@{host.host}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        # The forward is remote, so there is nothing local to poll. Ask the
        # POD whether the port answers -- which is the only end that
        # matters, and the one an agent will use.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"ssh -R died: {(proc.stderr.read() or b'').decode()[:300]}")
            probe = host.run(
                f"python3 -c \"import socket,sys;"
                f"s=socket.socket();s.settimeout(2);"
                f"sys.exit(s.connect_ex(('127.0.0.1',{remote_port})))\"",
                check=False, timeout=60)
            if probe.returncode == 0:
                break
            time.sleep(1.0)
        else:
            raise RuntimeError(
                f"the pod cannot reach 127.0.0.1:{remote_port} after 30s; "
                f"agents would have a memory server that is not there")
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@contextlib.contextmanager
def local_cognee_mcp(port: int):
    """`cognee-mcp` on this machine, sharing the orchestrator's stores.

    Same venv, so same SQLite, same LanceDB, same Aura, same default user
    -- which is what makes the agent's `cognee_recall` and the harness's
    deterministic writes ONE memory rather than two (see reverse_tunnel).

    Streamable-HTTP on loopback, exactly as cognee's own docs run it and
    exactly as the rehearsal starts it.
    """
    binary = Path(sys.executable).parent / "cognee-mcp"
    if not binary.exists():
        raise RuntimeError(
            f"{binary} not found. `pip install cognee-mcp` into the "
            f"orchestrator's venv -- it must be THIS venv, because the "
            f"point is that the server shares this process's stores.")
    proc = subprocess.Popen(
        [str(binary), "--transport", "http", "--host", "127.0.0.1",
         "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ},
    )
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("cognee-mcp exited during startup")
            with socket.socket() as s:
                s.settimeout(1.0)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(1.0)
        else:
            raise RuntimeError(f"cognee-mcp did not listen on {port} in 120s")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


@contextlib.contextmanager
def local_cognee_api(port: int):
    """Cognee's REST API on this machine, sharing the orchestrator's stores.

    What the Vibe `post_tool` hook talks to. Same reason the MCP server runs
    here rather than on the pod: a cognee process keeps its users, datasets
    and vector index in LOCAL SQLite and LanceDB, so a second cognee over
    there would be a second, empty memory writing into the same Neo4j.

    Cognee's own documented deployment -- `uvicorn cognee.api.client:app` --
    and unauthenticated on loopback only, which is what
    `ENABLE_BACKEND_ACCESS_CONTROL=false` (set by `C.configure`) permits. The
    Neo4j credential stays in this process's environment and never reaches
    the pod: the hook is handed a URL, a dataset name and two node-set names.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "cognee.api.client:app",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ},
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("cognee's REST API exited during startup")
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=3) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(2.0)
        else:
            raise RuntimeError(f"cognee's REST API was not ready on {port} "
                               f"in 180s")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def assert_hook_can_read(api_url: str, *, dataset: str,
                         node_set: str) -> list[str]:
    """Call the hook's own endpoint, with the hook's own payload.

    Not "the API answers /health". The failure this catches is the one every
    cheaper check passes: the server is up, the route exists, and the recall
    returns a warming-up marker or someone else's dataset -- so the hook
    silently appends nothing for the whole run and the log stays green.
    """
    body = json.dumps({"query": "pydantic v1 to v2 migration",
                       "datasets": [dataset], "nodeName": [node_set],
                       "searchType": "CHUNKS", "onlyContext": True,
                       "topK": 3}).encode()
    request = urllib.request.Request(
        f"{api_url}/api/v1/recall", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        return [f"the hook's recall endpoint is unusable: {exc!r}"]
    if not isinstance(payload, list):
        return [f"POST /api/v1/recall answered {type(payload).__name__}, "
                f"not a list; the hook parses a list"]
    return []


async def assert_one_memory(url: str, *, dataset: str) -> list[str]:
    """Write through the harness, read through the AGENT'S server.

    THE CHECK THAT WOULD HAVE CAUGHT THE SPLIT. Every cheaper check --
    the server answers, the tools register, the graph has nodes -- passes
    on two separate memories sharing one Neo4j database. Only a write on
    one side and a read on the other can tell them apart.

    Returns problems; empty means the agent's tools see what the harness
    remembers.
    """
    import cognee
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    marker = f"cross-visibility probe {int(time.time())}"
    session = f"probe-{int(time.time())}"
    await cognee.remember(marker, dataset_name=dataset, session_id=session)
    try:
        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as client:
                await asyncio.wait_for(client.initialize(), timeout=60)
                result = await asyncio.wait_for(client.call_tool(
                    "recall", {"query": marker, "session_id": session,
                               "datasets": dataset, "top_k": 3}), timeout=120)
    except Exception as exc:
        return [f"the memory server could not be asked whether it shares the "
                f"harness's memory ({exc!r})"]
    text = " ".join(getattr(b, "text", "") or ""
                    for b in (result.content or []))
    if marker.split()[-1] not in text:
        return [
            "THE AGENT'S MEMORY IS NOT THE HARNESS'S. A marker written here "
            "did not come back through the MCP server the agents use. A "
            "cognee process keeps its users, datasets and vector index in "
            "LOCAL SQLite/LanceDB -- only the graph is remote -- so a server "
            "running anywhere else is a second, empty memory writing into the "
            "same Neo4j. Warm would call `cognee_recall` and get nothing, all "
            "run, while every other check stays green. Drop --cognee-on-pod "
            f"to run the server here and reverse-tunnel it. Got: {text[:200]!r}"
        ]
    print("  cognee: the agent's server returns what the harness remembers "
          "-- one memory, not two")
    return []


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
                       mem: Any | None,
                       baseline_signature: str | None, baseline_passed: int,
                       baseline_v1: int | None = None,
                       results: list, skill_name: str | None = None,
                       package_path: str | None = None,
                       run_id: str | None = None,
                       tests_total: int = 0,
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
            deadline=deadline, emit=emit, mem=mem,
            baseline_signature=baseline_signature,
            baseline_passed=baseline_passed, baseline_v1=baseline_v1,
            results=results,
            skill_name=skill_name, package_path=package_path,
            run_id=run_id, tests_total=tests_total,
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
                              mem, baseline_signature, baseline_passed,
                              baseline_v1,
                              results, skill_name, tests_total, usage_probe,
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
                baseline_v1=baseline_v1,
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
                # Safe for cold because every memory-side use of this
                # label is additionally gated on `mem is not None`, and
                # cold has no mem, no MCP server and no graph.
                agent_label=ws.label,
                skill_name=skill_name,
                package_path=package_path,
                tests_total=tests_total,
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
    # Cognee scopes skills, runs and proposals by DATASET, so the fixture
    # name is what keeps two codebases' skills apart -- the job the
    # `prov_fixture` property did, but structural rather than a stamp
    # that can be forgotten on a write.
    dataset = C.configure(dataset=f"msf-{FIXTURE_DIR.name}")
    bus = EventBus(run_id)
    repo = Path(args.repo).resolve()

    if args.reset_memory or args.reset_memory_everything:
        # Same flag, same function as the local run: measure what the warm
        # agents build for each other WITHIN one run, rather than a graph that
        # has accumulated across runs. Both are real; they are different claims.
        await C.forget_everything(dataset=dataset,
                                  everything=args.reset_memory_everything)
        print("--reset-memory: forgot "
              + ("EVERY dataset in the graph"
                 if args.reset_memory_everything else f"dataset {dataset}"))

    # THE HARNESS'S OWN SCRIPTS, FROM THE REPO, BEFORE ANYTHING ELSE.
    # Uploaded and hash-checked rather than assumed present: until
    # 2026-09-19 nothing put `hook.py` or `reasoning_relay.py` on the pod
    # at all, and the version running during the 2026-09-18/19 series can
    # no longer be established. See install_host_scripts.
    for remote, digest in install_host_scripts(host).items():
        print(f"host script: {remote} sha256 {digest[:12]}")

    usage_before = {"warm": proxy_usage(host, args.warm_proxy),
                    "cold": proxy_usage(host, args.cold_proxy)}

    # Preflight, before the clock: a dead memory server is indistinguishable
    # at run time from "the model chose not to use memory", which is the
    # failure this project has already had 40 times.
    problems = []
    # THE GRAPH THIS PROCESS WRITES TO, not just the one the pod's MCP
    # server writes to. They are the same Aura instance and they are
    # reached by two different routes, and the deterministic half of the
    # treatment travels by this one: `cognee.agent_memory` runs HERE. A
    # run whose pod server is healthy and whose local client cannot reach
    # Aura would retrieve nothing, inject nothing, and report a clean
    # warm arm that was cold all along.
    try:
        ready = await C.assert_ready()
        print(f"cognee: graph reachable from the harness, "
              f"{ready['apoc_procedures']} APOC procedure(s), "
              f"{ready['nodes']:,} node(s)")
    except Exception as exc:
        problems.append(f"the harness cannot reach the Cognee graph ({exc!r}); "
                        f"warm's deterministic memory would be silently empty")
    # WHAT ELSE IS IN THIS GRAPH. Not a problem, a disclosure: graph
    # retrieval is NOT scoped to the dataset it is given -- measured, see
    # cognee_layer -- so anything listed here is reachable by warm's
    # recall no matter which fixture this run is about. On a shared
    # instance that is a confound in any cross-fixture reading, and the
    # only clean answers are a separate instance or
    # `--reset-memory-everything`.
    try:
        others = [d for d in await C.datasets_in_graph() if d != dataset]
        if others:
            print(f"  NOTE: {len(others)} other dataset(s) in this graph "
                  f"({', '.join(others[:6])}{'...' if len(others) > 6 else ''}). "
                  f"Cognee's graph search is not dataset-scoped, so warm can "
                  f"retrieve from them.")
    except Exception as exc:
        print(f"  could not list the graph's datasets ({exc!r})")
    # A urlopen() GET used to stand in for this. It passed while the memory
    # server answered Vibe's handshake with 406 and the model was handed zero
    # memory tools -- the run then reported 22 steps written and 0 retrievals,
    # which reads as a model that chose not to retrieve. Call the tools.
    def _local(url: str, port: int) -> str:
        return re.sub(r"//127\.0\.0\.1:\d+", f"//127.0.0.1:{port}", url)

    # WHERE THE AGENTS' MEMORY SERVER ACTUALLY IS. By default: here,
    # beside the orchestrator, reverse-tunnelled onto the pod's loopback
    # (see reverse_tunnel for the measurement that forced it). The agent's
    # URL is the same either way -- 127.0.0.1:8811 on its own machine --
    # so this only changes which end of the tunnel answers.
    cognee_url = (_local(args.mcp_url, 18811) if args.cognee_on_pod
                  else f"http://127.0.0.1:{args.cognee_local_port}/mcp")
    forwards = {18813: _port_of(args.web_url)}
    if args.cognee_on_pod:
        forwards[18811] = _port_of(args.mcp_url)
    try:
        with tunnels(host, forwards):
            servers = {"web": _local(args.web_url, 18813)}
            # Only when an agent will actually be given it. Under
            # `--memory-mode deterministic` no agent gets the server, so
            # failing the run on it would refuse to start over a
            # capability nothing uses.
            if C.uses_mcp(args.memory_mode):
                servers["cognee"] = cognee_url
            problems += await smoke_test_mcp(servers)
    except Exception as exc:
        problems.append(f"could not reach the MCP servers to test them: {exc!r}")
    # AND THE ONE CHECK NOTHING CHEAPER CAN MAKE: is the memory the agents
    # can reach the SAME memory the harness writes? Two cognee processes
    # sharing one Neo4j are two memories, and every other check here
    # passes on that arrangement.
    if C.uses_mcp(args.memory_mode) and not problems:
        problems += await assert_one_memory(cognee_url, dataset=dataset)
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
    # SEEDED ONCE INTO COGNEE, and left there. No version, no pinning,
    # no hash: Cognee rewrites `procedure` in place and keeps no
    # lineage, and warm is handed whatever it holds at the start of each
    # attempt.
    procedure = await C.ensure_skill(dataset=dataset)
    print(f"skill: {len(procedure):,} chars in Cognee, dataset {dataset}")
    print(f"memory mode: {args.memory_mode}  "
          f"(mcp tools: {C.uses_mcp(args.memory_mode)}, "
          f"injected context: {C.uses_injection(args.memory_mode)})")
    # THE CODEBASE AS A GRAPH. Deterministic (no LLM, no key), off the
    # clock, and re-ingested every run: `get_code_graph_tasks` is
    # incremental, and the fixture's tree is whatever the last experiment
    # left it as. Warm reads it back through `code_brief`; cold never sees
    # it. `--no-code-graph` turns it off for the runs that isolate the
    # outcome memory from it.
    code_dataset: str | None = None
    code_root = repo / (load_manifest().get("package_path") or ".")
    if args.code_graph:
        graph_started = time.monotonic()
        try:
            kinds = await C.ingest_code_graph(code_root,
                                              dataset=f"{dataset}-code")
            code_dataset = f"{dataset}-code"
            print(f"code graph: {repo.name} ingested in "
                  f"{time.monotonic() - graph_started:.1f}s "
                  f"(dataset {code_dataset}, {kinds})")
            if not kinds:
                print("  WARNING: the code graph holds no modules or "
                      "symbols; warm's code block will be empty")
        except Exception as exc:
            # Never fatal: it is one of warm's three blocks, not the whole
            # treatment.
            print(f"code graph: ingestion failed ({exc!r}); the run "
                  f"continues without it")
    else:
        print("code graph: off (--no-code-graph)")
    if args.no_distill:
        print("skill rewrite: disabled  (outcome memory still recorded)")
    else:
        print("skill rewrite: cognee improve_skill, from the grader's score")

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
            # HALF OF WARM'S TREATMENT IS THIS SERVER, and the agent
            # decides whether to use it. No skill package is installed:
            # the procedure lives in Cognee. Cold never gets the block.
            #
            # The OTHER half -- the procedure and the retrieved context in
            # the prompt, and the session trace written after -- is the
            # CogneeMemory built below and runs in this process, not on
            # the pod. Under `--memory-mode deterministic` that half runs
            # alone and no server is registered at all, which is why this
            # is conditional rather than "warm gets memory".
            if C.uses_mcp(args.memory_mode):
                ws.enable_memory(mcp_url=args.mcp_url)
                loaded = ws.assert_memory_tools_loaded()
                print(f"  {label} memory tools: {len(loaded)} loaded")
                ws.clear_session_logs()   # drop the probe, not the run's

            # THE DETERMINISTIC READ INSIDE THE ATTEMPT. Warm only; cold's
            # config registers no hook and its environment carries no
            # COGNEE_* variable, so it has no path to the graph from a tool
            # call either.
            hook_api = getattr(args, "hook_api_url", "")
            if args.hook and hook_api:
                ws.enable_hook(api_url=hook_api, dataset=dataset,
                               node_set=C.node_set(FIXTURE_DIR.name))
                problems = assert_hook_can_read(
                    f"http://127.0.0.1:{args.cognee_api_local_port}",
                    dataset=dataset,
                    node_set=C.node_set(FIXTURE_DIR.name))
                if problems:
                    raise RuntimeError("; ".join(problems))
                print(f"  {label} post_tool hook: registered on `bash`, "
                      f"reading {dataset} through {hook_api}")

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
    # The denominator for the skill's success score. Cognee wants a
    # proportion in [0.0, 1.0] and `tests_passed` is a count -- 56 means
    # nothing on its own. Measured by running the answer key and recorded
    # in the manifest, because the suite parametrises heavily and the
    # static count is less than half the collected total.
    baseline_total = int(load_manifest().get("test_total") or 0)
    if not baseline_total:
        raise RuntimeError(
            f"{FIXTURE_DIR.name}/manifest.yaml has no `test_total`. Without "
            f"it every skill run scores against an invented denominator.")
    # WHAT THE UNTOUCHED TREE COUNTS, off the source. `advanced` keys on
    # this falling, so attempt 1 needs the floor; without it the first
    # attempt of every run falls back to a measure that has twice been
    # wrong.
    baseline_v1 = surfaces.count(
        _collect_file_contents(repo / (load_manifest().get("package_path")
                                       or ".")),
        within=load_manifest().get("package_path"))
    print(f"baseline: {baseline_passed} passing of {baseline_total} | "
          f"{baseline_v1} v1 surface(s) | {baseline_signature or '(none)'}")

    state = load_state()
    async with AsyncDaytona() as client:
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

        def _scoped(label):
            # Cognee scopes by DATASET, not by a provenance stamp on every
            # trace. `prov_fixture`/`prov_experiment` -- both added after
            # distillation learned from the wrong runs -- are now the
            # dataset name, which cannot be forgotten on a write.
            #
            # The SESSION is per run AND per agent. It was the bare label
            # once, so 98 runs of traces shared one session called
            # "warm-0" and everything that walked it got slower until it
            # stopped finishing inside its timeout at all.
            return C.CogneeMemory(
                dataset=dataset,
                # The node sets warm reads and writes are named after the
                # fixture, and node sets -- unlike datasets -- really do
                # scope a recall.
                fixture=FIXTURE_DIR.name,
                label=label,
                session_id=f"{dataset}:{run_id}:{label}",
                mode=args.memory_mode,
                code_dataset=code_dataset,
                code_repo=code_root.name,
                package=load_manifest().get("package_path"),
                distil=not args.no_distill)

        scopes = {label: _scoped(label) for label, w in labels if w}

        # One barrier across BOTH arms. With a single arm there is nothing
        # to synchronise and NullSync keeps the call sites uniform.
        running = [label for label, _ in labels]
        arms_present = {w for _, w in labels}
        sync = (AttemptSync(running) if len(arms_present) > 1 else NullSync())

        def tasks_for(warm: bool) -> list:
            return [asyncio.ensure_future(agent_worker(
                ws=spaces[label], warm=warm, pool=pool, test_command=args.test,
                deadline=deadline, bus=bus,
                mem=scopes.get(label) if warm else None,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed, results=results,
                # Warm only, and it is the ONLY thing warm's prompt carries
                # that cold's does not. Cold has no skills directory, so the
                # prefix would be a stray token rather than a load.
                package_path=load_manifest().get("package_path"),
                run_id=run_id,
                skill_name=C.SKILL_NAME if warm else None,
                # The denominator for the grader's score. Measured by
                # running the answer key and recorded in the manifest.
                tests_total=baseline_total,
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

        # ONE LAST BRIDGE FROM SESSION MEMORY TO THE GRAPH, after the
        # clock. `migrate_codebase` calls `improve` after every attempt,
        # so in a healthy run these report "no new session entries" and
        # cost a round trip each. They run anyway because the per-attempt
        # call sits inside the loop's never-fatal guard, and an agent
        # cancelled between its last verdict and its last bridge would
        # otherwise leave its most informative trace where only its own
        # session can see it.
        #
        # BOUNDED, for the reason the entity pass it replaces was bounded:
        # this is off the measured window, so a slow or rate-limited key
        # cannot change a result, but it CAN hold a finished run open --
        # one did, for 18 minutes, blocked in SSL while an A/B sweep
        # waited behind it.
        entities_extracted = 0
        for label, warm in labels:
            if not warm or label not in scopes:
                continue
            try:
                bridged = await asyncio.wait_for(scopes[label].improve(),
                                                 timeout=ENTITY_TIMEOUT_S)
            except Exception as exc:
                print(f"  {label}: final improve() failed ({exc!r}); its last "
                      f"trace stays in session memory only")
                continue
            for name, stage in (bridged.get("stages") or {}).items():
                counts = (stage or {}).get("counts") or {}
                entities_extracted += sum(v for v in counts.values()
                                          if isinstance(v, int))
                if (stage or {}).get("status") == "completed" and counts:
                    print(f"  {label}: improve/{name} {counts}")

    # DID WARM ACTUALLY USE MEMORY? The old question was whether a skill
    # FILE had reached the model -- installed, hashed and prefixed were
    # three things that could each succeed while the agent ran with no
    # procedure at all. There is no file now, so the equivalent question
    # is whether the agent called its memory tools, and only the agent
    # can answer it: the procedure is reachable, and using it is its
    # decision.
    #
    # Counted, not asserted, because "warm chose not to recall" is a
    # RESULT rather than a failure -- and it is the result the old layer
    # produced for 40 consecutive runs while every check here was green.
    skill_loaded: dict[str, bool] = {}
    for label, warm in labels:
        if not warm:
            continue
        calls = spaces[label].memory_tool_calls()
        skill_loaded[label] = calls > 0
        print(f"  {label}: {calls} memory tool call(s) during its attempts"
              + ("" if calls else "  -- warm never consulted its memory, "
                                  "which is a finding, not an error"))

    # THE TWO HALVES OF THE TREATMENT, READ OFF THE EVENT LOG AND KEPT
    # APART. `cognee.agent_memory` is the harness retrieving; every other
    # source is a tool the agent chose to call. Summing them answers "did
    # warm have memory" and destroys the answer to "did warm go and get
    # it" -- and the second question is the one 40 runs of this project
    # turned on.
    #
    # This replaces the sidecar's counters, which no longer exist: there
    # is no hook, no relay and no second writer, so there is nothing to
    # ask a pod process about. `from_reasoning`/`thought_fallbacks` are
    # reported as 0 because they are UNMEASURABLE now rather than
    # measured-as-zero, and STEP_WRITES below says so.
    reads = [e for e in bus.events if e["type"] == "MEMORY_READ"]
    injected = [e for e in reads
                if "cognee.agent_memory" in (e.get("sources") or [])]
    chosen = [e for e in reads if e not in injected]
    from_reasoning = from_tool_input = reasoning_pushes = 0
    if injected:
        print(f"  cognee retrieved for warm on {len(injected)} attempt(s), "
              f"{sum(e.get('chars', 0) for e in injected):,} chars injected "
              f"into the prompt. This is warm's deterministic treatment: it "
              f"costs prompt tokens, and cold pays none of them.")
    elif C.uses_injection(args.memory_mode) and any(w for _, w in labels):
        print("  WARNING: cognee retrieved NOTHING on any attempt. Either "
              "the graph is empty (attempt 1 of a fresh dataset is "
              "expected) or improve() is not bridging the traces -- check "
              "the INGESTED lines below before reading anything into the "
              "warm/cold comparison.")

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
    print(f"     graph writes: {_total('steps')} trace step(s) bridged from "
          f"session memory into the graph by cognee.improve(), over "
          f"{len(ingested)} attempt(s)")
    if skill_loaded:
        final = await C.current_procedure(dataset=dataset) or ""
        # Start..end by SIZE, not by version: Cognee rewrites the
        # procedure in place and keeps no lineage, so there is no v5..v7
        # to report and inventing one would read as more than we know.
        print(f"     skill: {len(procedure):,} chars at the start, "
              f"{len(final):,} at the end; "
              f"{sum(skill_loaded.values())}/{len(skill_loaded)} warm "
              f"agent(s) also called memory of their own accord")
    print(f"     improve() stage counts after the clock stopped: "
          f"{entities_extracted}")
    # THE ALARM THAT MATTERS, and the one shape of failure this project
    # keeps producing: every check green, every counter plausible, and an
    # empty graph. If nothing was bridged then `recall` has nothing to
    # return on the next attempt or the next run, and warm is cold plus
    # the latency of asking.
    if any(w for _, w in labels) and _total("steps") == 0:
        print("     NOTHING REACHED THE GRAPH -- improve() bridged no trace "
              "steps, so the next attempt's recall has nothing to find and "
              "warm == cold. Check the per-attempt improve() lines above "
              "for the stage that declined and why.")
    for label, warm in labels:
        if warm:
            # Into the event log, so the judgement is re-derivable from the
            # record rather than only visible in stdout that dies with the
            # pod.
            #
            # THE THREE COUNTERS ARE NOW STRUCTURALLY ZERO, and that is a
            # different fact from "measured zero". They counted where each
            # ReasoningStep's `thought` came from -- the model's own
            # reasoning, or a fall-back to serialised tool input -- and
            # they earned their place: six runs wrote 993 steps of which
            # 988 held tool JSON while every visible number looked
            # healthy. There is no per-step write and no relay under
            # Cognee, so nothing can answer the question. Emitted anyway
            # so the event log keeps one shape across the migration; read
            # `memory_reads` instead.
            await bus.emit("STEP_WRITES", swarm="warm", agent=label,
                           thoughts_from_reasoning=from_reasoning,
                           thought_fallbacks=from_tool_input,
                           reasoning_pushes=reasoning_pushes,
                           memory_reads_injected=len(injected),
                           memory_reads_by_agent=len(chosen))
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
        # Cognee's authoring model is called from HERE, not through the
        # pod's counting proxy, and cognee exposes no usage counter -- so
        # unlike the old ExternalWriter there is nothing to read. Reported
        # as the proxy's view, which for this path is zero, rather than
        # invented: a distillation cost that reads 0 is a cost that was
        # never measured, and that distinction has been lost once before.
        distil_usage["warm"] = proxy_usage(host, args.distill_proxy)
        break
    run_metrics = metrics_mod.collect(
        bus.events, run_id=run_id, gpu=gpu, model=args.model, commit=commit,
        skill_version=None,
        skill_approx_tokens=len(procedure) // 4,
        skill_dir_sha="",
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
    p.add_argument("--mcp-url", default="http://127.0.0.1:8811/mcp",
                   help="where the AGENT dials its memory server, on its own "
                        "loopback. The harness reverse-tunnels this port to "
                        "its own cognee-mcp unless --cognee-on-pod.")
    # WHICH END RUNS COGNEE. Default: here. A cognee process keeps its
    # users, datasets and vector index in local SQLite/LanceDB and only
    # the graph is remote, so a server on the pod is a second, EMPTY
    # memory writing into the same Neo4j -- measured, see reverse_tunnel.
    # The flag keeps the old topology reachable for comparison, and the
    # preflight will tell you plainly what it costs.
    p.add_argument("--cognee-on-pod", action="store_true",
                   help="use a cognee-mcp running ON THE POD instead of "
                        "reverse-tunnelling the harness's own. Its memory is "
                        "NOT the harness's; the preflight says so.")
    p.add_argument("--cognee-local-port", type=int, default=8814,
                   help="port for the harness-side cognee-mcp (tunnelled to "
                        "the pod as --mcp-url's port).")
    p.add_argument("--web-url", default="http://127.0.0.1:8813/mcp",
                   help="web_lookup MCP server; registered for BOTH arms.")
    # WHICH HALVES OF WARM'S TREATMENT ARE LIVE.
    #
    # `hybrid` is both, and is what a 119B model needs: the cognee MCP
    # server it may call, AND the procedure plus retrieved context the
    # harness puts in its prompt. `mcp` is the voluntary half alone --
    # the arm that answers "will the model go and look", which this
    # project has already answered `no` for 40 consecutive runs under a
    # different server. `deterministic` is the other half alone, which
    # measures the memory without the model's willingness to use a tool.
    # `off` makes warm == cold and exists to prove the harness.
    p.add_argument("--memory-mode", choices=C.MEMORY_MODES, default="hybrid",
                   help="which halves of warm's memory treatment are live: "
                        "hybrid (both), mcp (tools only), deterministic "
                        "(injected context and traces only), off.")
    # THE CODEBASE AS A GRAPH. Deterministic, no LLM, no API key -- but
    # minutes of wall-clock on a large fixture, so it is opt-in rather
    # than always-on. Lands in its own dataset: a map of the code is not
    # a memory of attempts at it, and mixing them makes "what does warm
    # know" unanswerable.
    p.add_argument("--reset-memory", action="store_true",
                   help="Forget THIS fixture's dataset before starting.")
    # THE ONLY COMPLETE RESET AVAILABLE ON ONE INSTANCE. Graph search is
    # not dataset-scoped (measured -- see cognee_layer), so forgetting one
    # dataset still leaves warm able to retrieve another fixture's
    # lessons. Separate flag rather than a wider default: it destroys
    # every earlier experiment's memory, which is not something to do by
    # accident.
    p.add_argument("--reset-memory-everything", action="store_true",
                   help="Forget EVERY dataset in the graph. The only way to "
                        "start a series from a genuinely empty graph, "
                        "because graph retrieval ignores dataset scope.")
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
                   help="leave the procedure alone. The outcome documents "
                        "are still written and read; only Cognee's skill "
                        "rewrite is skipped, so the skill under test cannot "
                        "change underneath the run.")
    # ON BY DEFAULT. A code graph of the repository under migration is
    # plain Cognee, deterministic and keyless, and it is the one thing warm
    # can know about the codebase that is not derived from its own past
    # attempts. Off is the control.
    #
    # THERE WAS A SECOND FLAG FOR THIS, `--code-graph` (store_true, default
    # False), left over from when it was opt-in. argparse fills the
    # namespace in the order actions were added and does not overwrite a
    # dest already set, so the FIRST action for a dest wins the default --
    # this one was dead and every run silently had no code graph. Caught on
    # the pod, 3 minutes into a $4.59/hr run, by the setup line printing
    # "code graph: off" with nothing on the command line asking for that.
    p.add_argument("--no-code-graph", dest="code_graph", action="store_false",
                   default=True,
                   help="do not ingest the fixture as a code graph, so "
                        "warm's memory is only its own graded attempts.")
    # THE DETERMINISTIC READ INSIDE AN ATTEMPT, on by default.
    #
    # Warm's other two reads happen at the attempt boundary: the procedure
    # and the brief go into the prompt. This one fires when the agent's own
    # command fails, which is where the "do not repeat this" half is worth
    # most -- and it is the only read that does not depend on the model
    # choosing to call a tool. Over the last forty runs the agents made
    # 4,767 `bash` calls and 9 `cognee_recall` calls.
    p.add_argument("--no-hook", dest="hook", action="store_false", default=True,
                   help="do not register the post_tool hook, so warm's only "
                        "reads are the ones in its prompt.")
    p.add_argument("--cognee-api-local-port", type=int, default=8815,
                   help="port for the harness-side cognee REST API the hook "
                        "reads through.")
    p.add_argument("--cognee-api-pod-port", type=int, default=8815,
                   help="port the pod dials for that API, reverse-tunnelled.")
    # WHO AUTHORS THE SKILL IS NO LONGER OURS TO CHOOSE.
    #
    # This used to select between the agent's own model and an external
    # OpenAI one, because AIP's guidance is explicit -- "Use the largest
    # frontier model available when using the AIP skill... smaller models
    # struggle" -- and the flag defaulted to "agent" for three runs on
    # 2026-09-18, during which Mistral-Small-4 authored its own procedure
    # and collapsed it from 24 steps to 11.
    #
    # Cognee's `improve_skill` uses Cognee's own model and prompt. The
    # flag is kept so the event log and metrics keep their shape, but it
    # names what actually did the work rather than choosing it. Reopening
    # this is one of the things to revisit once there is a result to
    # compare against.
    p.add_argument("--distill-writer", default="cognee",
                   help="informational: who authored the skill. Cognee owns "
                        "the improvement pass now, so this is recorded "
                        "rather than selected.")
    args = p.parse_args()
    watch = BlockingCallWatch()
    if not args.no_loop_debug:
        # asyncio's debug mode is what surfaces a blocked loop at all. 0.1s is
        # far below anything legitimate here -- every real wait in this
        # harness is awaited, so a callback holding the loop for a tenth of a
        # second is a bug, not load.
        logging.getLogger("asyncio").addHandler(watch)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    # BEFORE asyncio.run, and outside it, because both are plain
    # subprocesses that have to outlive every attempt: the agents' memory
    # server is this machine's, and it reaches them through `ssh -R`.
    #
    # `C.configure` first: cognee reads its configuration from the
    # environment at import time, and the server we are about to launch
    # inherits this process's environment. Launched without it, the
    # server would fall back to cognee's embedded Kuzu store and the
    # agents' memory would be a different graph from the harness's --
    # while every log line still said ok.
    with contextlib.ExitStack() as stack:
        pod = SwarmHost(host=args.ssh_host, port=args.ssh_port,
                        identity=Path(args.ssh_key))
        warm_memory = args.memory_mode != "off"
        if warm_memory and not args.cognee_on_pod:
            C.configure(dataset=f"msf-{FIXTURE_DIR.name}")
        if C.uses_mcp(args.memory_mode) and not args.cognee_on_pod:
            url = stack.enter_context(local_cognee_mcp(args.cognee_local_port))
            print(f"cognee-mcp: {url} (this machine, sharing the "
                  f"orchestrator's stores)")
            stack.enter_context(reverse_tunnel(
                pod, _port_of(args.mcp_url), args.cognee_local_port))
            print(f"reverse tunnel: pod 127.0.0.1:{_port_of(args.mcp_url)} "
                  f"-> harness 127.0.0.1:{args.cognee_local_port}")
        # THE DETERMINISTIC READ'S TRANSPORT. Cognee's own REST API, here,
        # reached from the pod through a second reverse tunnel -- so the
        # `post_tool` hook and the harness read one memory, not two.
        if args.hook and warm_memory and not args.cognee_on_pod:
            api = stack.enter_context(local_cognee_api(args.cognee_api_local_port))
            print(f"cognee REST API: {api} (this machine, for the post_tool "
                  f"hook)")
            stack.enter_context(reverse_tunnel(
                pod, args.cognee_api_pod_port, args.cognee_api_local_port))
            args.hook_api_url = f"http://127.0.0.1:{args.cognee_api_pod_port}"
            print(f"reverse tunnel: pod {args.hook_api_url} -> harness "
                  f"127.0.0.1:{args.cognee_api_local_port}")
        rc = asyncio.run(main_async(args, watch), debug=not args.no_loop_debug)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
