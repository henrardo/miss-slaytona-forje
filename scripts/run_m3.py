#!/usr/bin/env python3
"""Milestone 3: one agent, real coding-agent harness (Mistral Vibe), full
loop, sequential over the fixture.

For each manifest file: Vibe (programmatic mode, reasoning via our SGLang
endpoint) reads, edits and tests the file itself through Daytona's own MCP
tools, against one sandbox this script creates from the v1 snapshot. This
script then makes its own independent pytest check in that same sandbox --
that, not Vibe's self-report, decides success. Retries on failure, continuing
from the file's current state in the sandbox rather than resetting, until a
single run-level deadline (--deadline-s, default 300s, Sec. 8's
HARD_DEADLINE_S) is reached -- not a fixed attempt count. That deadline is
shared across every file in this sequential loop, same as the live demo's own
stopping rule: the run ends on TIME, not on a file exhausting some small
number of tries. No memory -- that's M4.

Requires DAYTONA_API_KEY and SGLANG_BASE_URL in the environment, a snapshot
already built via scripts/build_snapshot.py, `harness/.venv` pip-installed
with mistral-vibe, and `daytona login` already run locally (see
orchestrator/vibe_agent.py).

Done when: at least 8/12 files migrate unaided (spec Sec. 15, M3).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from daytona import AsyncDaytona

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.vibe_agent import VIBE_BIN, FileResult, migrate_file, render_config
from orchestrator.events import EventBus
from orchestrator.manifest import load_manifest
from orchestrator.sandbox import SandboxPool
from orchestrator.snapshot import load_state, pool_kwargs_from_state

# Sec. 8's HARD_DEADLINE_S -- the run stops on TIME, not on any file
# exhausting a fixed attempt count. Shared across every file in this
# sequential loop: earlier files leave less budget for later ones, same as
# the live demo's single run-level clock. Override with --deadline-s or
# M3_HARD_DEADLINE_S for ad hoc/exploratory runs.
DEFAULT_HARD_DEADLINE_S = 300.0


async def main_async(hard_deadline_s: float) -> int:
    manifest = load_manifest()
    state = load_state()
    pool_kwargs = pool_kwargs_from_state(state)

    base_url = os.environ["SGLANG_BASE_URL"]
    model = os.environ.get("SGLANG_MODEL", "mistralai/Devstral-Small-2-24B-Instruct-2512")
    render_config(base_url, model)

    run_id = f"m3-{int(time.time())}"
    bus = EventBus(run_id)
    deadline = time.monotonic() + hard_deadline_s

    results = []
    async with AsyncDaytona() as client:
        pool = SandboxPool(client, run_id=run_id, **pool_kwargs)
        await pool.sweep()

        await bus.emit(
            "RUN_START",
            run_id=run_id,
            files=[e["path"] for e in manifest["files"]],
            model=model,
        )

        for entry in manifest["files"]:
            path, test_target = entry["path"], entry["tests"]
            remaining = deadline - time.monotonic()
            if remaining < 1:
                print(f"[{path}] SKIPPED -- run deadline already reached")
                results.append(FileResult(path, False, 0))
                continue
            await bus.emit("FILE_CLAIMED", swarm="single", agent=0, file=path)
            print(f"[{path}] migrating... ({remaining:.0f}s left in the run)")
            result = await migrate_file(
                pool=pool, path=path, test_target=test_target, deadline=deadline, emit=bus.emit
            )
            results.append(result)
            outcome = "PASS" if result.success else "OUT OF TIME"
            print(f"  {outcome} after {result.attempts} attempt(s)")

        leaked = await pool.sweep()
        if leaked:
            print(f"  WARNING: swept {leaked} sandbox(es) not accounted for locally")

        await bus.emit("RUN_END", passed=sum(r.success for r in results), total=len(results))

    bus.close()

    print()
    print("=" * 60)
    for r in results:
        outcome = "PASS" if r.success else "OUT OF TIME"
        print(f"  {outcome:11} {r.path} ({r.attempts} attempt(s))")
    passed = sum(r.success for r in results)
    print(f"\n{passed}/{len(results)} files migrated unaided (event log: runs/{run_id}.jsonl)")
    return 0 if passed >= 8 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--deadline-s",
        type=float,
        default=float(os.environ.get("M3_HARD_DEADLINE_S", DEFAULT_HARD_DEADLINE_S)),
        help=(
            "Run-level wall-clock budget in seconds, shared across every file "
            "(Sec. 8's HARD_DEADLINE_S). The run stops on time, not on any file "
            "exhausting a fixed attempt count. Default: 300s, or $M3_HARD_DEADLINE_S."
        ),
    )
    args = parser.parse_args()

    if not os.environ.get("DAYTONA_API_KEY"):
        print("DAYTONA_API_KEY is not set.")
        return 1
    if not os.environ.get("SGLANG_BASE_URL"):
        print("SGLANG_BASE_URL is not set (the RunPod SGLang proxy URL).")
        return 1
    if not VIBE_BIN.exists():
        print(f"{VIBE_BIN} not found -- run `cd harness && uv venv .venv && uv pip install mistral-vibe` first.")
        return 1

    return asyncio.run(main_async(args.deadline_s))


if __name__ == "__main__":
    raise SystemExit(main())
