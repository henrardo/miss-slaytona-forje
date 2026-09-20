#!/usr/bin/env python
"""Grade a fixture's OWN two known trees on the real Daytona oracle.

WHY THIS EXISTS. Every run measures the distance between the agent's tree
and green. That number is worthless unless green is reachable, and the only
way to know is to put the human's own merged migration through the same
grader the agent is judged by. On the small fixture that check was never
made, and when it finally was, the answer key scored 29/33 -- the harness
had made four tests unpassable and every run had been measuring the
distance to an unreachable state.

So this asks a fixture three questions before a GPU is ever rented:

    baseline    does the PRE-migration tree fail the way we think it does,
                and what is the error signature the agents will start from?
    answer key  does `reference_v2/` -- the real merged PR -- score green?
    floor       how many v1 surfaces does a COMPLETED migration still
                count? (Not zero. See orchestrator/surfaces.py.)

Nothing here is a parallel implementation: it uploads through
`SandboxPool.run_pytest`, collects through `vibe_agent._collect_file_contents`
and reads the verdict through `vibe_agent.tests_passed` /
`error_signature`, so a change to how a run is graded changes this too.

    MSF_FIXTURE_DIR=fixtures/oapi scripts/grade_fixture.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daytona import AsyncDaytona
from dotenv import load_dotenv

# BEFORE the orchestrator imports, not inside main(). `orchestrator.memory`
# reads NEO4J_URI at module scope and raises if it is unset -- deliberately,
# because a default once pointed the orchestrator at a different graph from
# the agents'. swarm/run.py does the same thing for the same reason.
load_dotenv()

from orchestrator import series as S  # noqa: E402
from orchestrator import surfaces  # noqa: E402
from orchestrator.manifest import FIXTURE_DIR, load_manifest  # noqa: E402
from orchestrator.sandbox import (SandboxPool,  # noqa: E402
                                  install_cleanup_handlers)
from orchestrator.snapshot import (is_stale, load_state,  # noqa: E402
                                   pool_kwargs_from_state)
from orchestrator.vibe_agent import (_collect_file_contents,  # noqa: E402
                                     error_signature, tests_passed)

# Read by orchestrator/series.py to draw a chart's reference lines. One per
# fixture, at the repo root beside `.snapshot_state-<fixture>.json`, which
# is the other per-fixture thing a run depends on. `series.oracle_for()`
# looks exactly here; the two must not drift.
ORACLE_PATH = S.REPO_ROOT / f".oracle-{FIXTURE_DIR.name}.json"


def _tree(package: str, source: Path) -> dict[str, bytes]:
    """`file_contents` for a checkout whose package is `source`.

    Copied into a temp dir named after the package first, because
    `_collect_file_contents` keys on the directory's own name and
    `reference_v2/<package>` must arrive as `/repo/<package>`, not as
    `/repo/reference_v2/<package>`.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / package
        shutil.copytree(source, dst)
        return _collect_file_contents(dst)


async def grade(pool: SandboxPool, name: str, contents: dict[str, bytes],
                test_command: str, package: str) -> dict:
    started = time.monotonic()
    result = await pool.run_pytest(file_contents=contents,
                                   test_command=test_command)
    passed = tests_passed(result.output)
    return {
        "tree": name,
        "exit_code": result.exit_code,
        "tests_passed": passed,
        "signature": error_signature(result.output) or "-",
        "v1_surfaces": surfaces.count(contents, within=package),
        "seconds": round(time.monotonic() - started, 1),
        "create_ms": round(result.create_ms),
        "tail": result.output.strip().splitlines()[-1:] or [""],
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", default=f"grade-{int(time.time())}")
    args = ap.parse_args()

    manifest = load_manifest()
    package = manifest["package_path"]
    test_command = manifest["test_command"]
    reference = FIXTURE_DIR / "reference_v2" / package
    if not reference.is_dir():
        print(f"ERROR: no answer key at {reference}")
        return 2
    stale, why = is_stale()
    print(f"fixture: {FIXTURE_DIR.name}   package: {package}")
    print(f"snapshot: {why}")
    if stale:
        print("Refusing to grade against a stale snapshot: the sandbox "
              "would hold a different tree from the one being measured.")
        return 2

    trees = {
        "baseline (pre-migration)": _tree(package, FIXTURE_DIR / package),
        "answer key (reference_v2)": _tree(package, reference),
    }

    async with AsyncDaytona() as client:
        pool = SandboxPool(client, run_id=args.run_id,
                           **pool_kwargs_from_state(load_state()))
        install_cleanup_handlers(pool)
        try:
            rows = [await grade(pool, name, contents, test_command, package)
                    for name, contents in trees.items()]
        finally:
            leaked = await pool.sweep()
            print(f"swept {leaked} sandbox(es)")

    print()
    print(f"{'tree':28s} {'exit':>4s} {'passed':>7s} {'v1':>4s} {'s':>5s}  signature")
    for r in rows:
        print(f"{r['tree']:28s} {r['exit_code']:4d} {r['tests_passed']:7d} "
              f"{r['v1_surfaces']:4d} {r['seconds']:5.1f}  {r['signature'][:52]}")
    for r in rows:
        print(f"  {r['tree']}: {r['tail'][0][:110]}")

    base, key = rows
    ok = True
    # The answer key is the ONLY hard assertion. A baseline that already
    # passes would mean there is nothing to migrate, so that is checked
    # too -- but a baseline failing in an unexpected WAY is information,
    # not an error.
    if key["exit_code"] != 0:
        print("\nFAIL: the answer key does not pass the grader. Every run "
              "on this fixture would measure the distance to an unreachable "
              "state. Fix the fixture or the seeding, not the agents.")
        ok = False
    if base["exit_code"] == 0:
        print("\nFAIL: the pre-migration tree already passes. There is "
              "nothing for an agent to do and no signal to measure.")
        ok = False
    if ok:
        print(f"\nOK: {base['tests_passed']} -> {key['tests_passed']} tests, "
              f"{base['v1_surfaces']} -> {key['v1_surfaces']} v1 surfaces. "
              f"The floor is {key['v1_surfaces']}, NOT zero -- report it "
              f"beside any progress number from this fixture.")
        # Persisted so every later chart draws its reference lines from a
        # MEASUREMENT of this fixture rather than from a number somebody
        # typed into a plot script. The floor being 3 and not 0 is exactly
        # the kind of fact that gets lost between here and a slide.
        ORACLE_PATH.write_text(json.dumps({
            "fixture": FIXTURE_DIR.name,
            "package": package,
            "graded_at": int(time.time()),
            "baseline_passed": base["tests_passed"],
            "baseline_v1_surfaces": base["v1_surfaces"],
            "baseline_signature": base["signature"],
            "answer_key_passed": key["tests_passed"],
            "answer_key_v1_surfaces": key["v1_surfaces"],
        }, indent=2) + "\n")
        print(f"oracle reference written to {ORACLE_PATH.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
