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
from orchestrator.snapshot import load_state, pool_kwargs_from_state
from orchestrator.vibe_agent import MigrationResult, error_signature, migrate_codebase, tests_passed
from swarm.agent_workspace import AgentWorkspace, SwarmHost, repo_tarball


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


async def agent_worker(*, ws: AgentWorkspace, warm: bool, pool: SandboxPool,
                       test_command: str, deadline: float, bus: EventBus,
                       bridge: RemoteTraceBridge, mem: ScopedMemory | None,
                       baseline_signature: str | None, baseline_passed: int,
                       results: list) -> MigrationResult:
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
                session_id=ws.label if warm else None,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed,
                step_memory=bridge if warm else None,
                agent_label=ws.label if warm else None,
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
    print(f"gpu: {gpu}")
    print(f"repo: {repo}")
    tar = repo_tarball(repo, exclude=(".git", "__pycache__", ".venv",
                                      ".pytest_cache", "reference_v2"))
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
            ws.enable_memory(mcp_url=args.mcp_url, sidecar_port=args.sidecar_port)
            # Before the clock, because a warm agent with no memory tools is
            # not a warm agent and the run measures nothing. Run 9 passed
            # every other check -- GATE ok, 0 errors, 22 steps written -- and
            # still could not retrieve, because Vibe loaded no tools at all.
            loaded = ws.assert_memory_tools_loaded()
            print(f"  {label} memory tools: {len(loaded)} loaded")
            ws.clear_session_logs()  # drop the probe session, not the run's
        # Fill the tree/transcript cache before the clock. Without this the
        # first attempt pays ~14s of blocking ssh inside the event loop --
        # see AgentWorkspace.refresh().
        ws.prime()
        spaces[label] = ws
        print(f"  {label} seeded{' (memory)' if warm else ''}")

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

        def tasks_for(warm: bool) -> list:
            return [asyncio.ensure_future(agent_worker(
                ws=spaces[label], warm=warm, pool=pool, test_command=args.test,
                deadline=deadline, bus=bus, bridge=bridge,
                mem=ScopedMemory(mem_client, user_identifier=label) if warm else None,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed, results=results,
            )) for label, w in labels if w is warm]

        # `run_swarm` unchanged from the local orchestrator: the moment one
        # agent in a swarm converges, the rest of THAT swarm is cancelled
        # rather than left grinding out the deadline. The arms stay
        # independent, so warm stopping early does not touch cold.
        await asyncio.gather(run_swarm("warm", tasks_for(True)),
                             run_swarm("cold", tasks_for(False)))
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
        entities_extracted, steps_linked = 0, 0
        for label, warm in labels:
            if not warm:
                continue
            scoped = ScopedMemory(mem_client, user_identifier=label)
            try:
                stats = await scoped.extract_entities_from_session(label)
                entities_extracted += sum(v for v in stats.values() if isinstance(v, int))
            except Exception as exc:
                print(f"  entity extraction failed for {label}: {exc!r}")
            try:
                steps_linked += await scoped.link_step_entities(label)
            except Exception as exc:
                print(f"  step entity linking failed for {label}: {exc!r}")

    summary = control(host, args.sidecar_port, {"control": "summary"})
    # The injection log, written beside the event log. Run 13 made 44
    # injections and recorded nothing about them, so their provenance had to
    # be reconstructed afterwards from tool histograms and graph timestamps.
    inj = control(host, args.sidecar_port, {"control": "injections"}).get("injections") or []
    if inj:
        path = Path("runs") / f"{run_id}-injections.json"
        path.write_text(json.dumps(inj, indent=2))
        srcs = Counter(r["source_trace"] for i in inj for r in i["returned"])
        print(f"  injection log: {len(inj)} injection(s), "
              f"{sum(i['approx_tokens'] for i in inj):,} approx tokens, "
              f"{len(srcs)} distinct source trace(s) -> {path}")
    bus.close()

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
    d = {k: summary.get(k, 0) - baseline_summary.get(k, 0)
         for k in ("steps_written", "text_turns_written", "context_returned", "errors")}
    print(f"     step hook (this run): {d['steps_written']} step(s) written by the "
          f"agents ({d['text_turns_written']} of them turns that called no tool), "
          f"{d['context_returned']} injection(s), {d['errors']} error(s)")
    print(f"     entities extracted after the clock stopped: {entities_extracted} "
          f"from messages, {steps_linked} TOUCHED edge(s) from reasoning steps")
    if d["steps_written"] == 0:
        print("     the step hook wrote nothing -- warm's graph is empty, so "
              "warm == cold and any token comparison above is a null result.")
    print(f"event log: runs/{run_id}.jsonl")
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
    p.add_argument("--deadline-s", type=float, default=900.0)
    p.add_argument("--swarm-size", type=int, default=1,
                   help="agents PER ARM; --swarm-size 1 --arms both is 2 agents.")
    p.add_argument("--no-loop-debug", action="store_true",
                   help="disable asyncio debug mode and the blocking-call guard.")
    p.add_argument("--arms", choices=("both", "warm", "cold"), default="both",
                   help="which arm(s) to run. One arm per run avoids two "
                        "agents contending for a single endpoint.")
    p.add_argument("--model", default="Qwen/Qwen3-14B")
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
