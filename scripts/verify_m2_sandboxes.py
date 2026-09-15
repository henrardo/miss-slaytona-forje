#!/usr/bin/env python3
"""Milestone 2: prove the sandbox execution path with zero model risk.

For each of the 12 manifest files, spin up one real Daytona sandbox, upload
the KNOWN-CORRECT pydantic v2 migration (fixture/reference_v2/), run that
file's own test module, and confirm it passes. This exercises exactly the
create -> upload -> exec -> delete lifecycle the real agent loop will use
(spec Sec. 6, Sec. 9.2), with no LLM involved.

Uploads the full reference_v2/cfp tree (not just the one target file) so
that files with cross-module imports (scoring.py -> models/review.py, etc.)
don't spuriously fail due to an unrelated file still being in its v1 form --
this script is validating the sandbox pipeline, not agent ordering.

Requires:
  - DAYTONA_API_KEY in the environment (or a DaytonaConfig equivalent)
  - A snapshot already built via scripts/build_snapshot.py

Done when: all 12 files pass, every sandbox is confirmed deleted, and
sandboxes_live returns to zero (spec Sec. 15, M2).
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

from orchestrator.manifest import FIXTURE_DIR, load_manifest
from orchestrator.sandbox import SandboxPool
from orchestrator.snapshot import load_state, pool_kwargs_from_state

REFERENCE_V2_DIR = FIXTURE_DIR / "reference_v2"


def reference_file_contents() -> dict[str, bytes]:
    """Every migrated cfp/*.py file, keyed by its destination path in the
    sandbox. Uploaded in full for every check (see module docstring)."""
    contents: dict[str, bytes] = {}
    cfp_dir = REFERENCE_V2_DIR / "cfp"
    for path in sorted(cfp_dir.rglob("*.py")):
        rel = path.relative_to(REFERENCE_V2_DIR)
        contents[f"/repo/{rel.as_posix()}"] = path.read_bytes()
    return contents


async def main_async() -> int:
    manifest = load_manifest()
    file_contents = reference_file_contents()
    if not file_contents:
        print(f"FAIL: no reference files found under {REFERENCE_V2_DIR}")
        return 1

    state = load_state()
    if state.get("mode") == "image":
        print("using ad-hoc image mode (persisted snapshot registration was forbidden on this account)")
    else:
        print(f"using persisted snapshot {state.get('snapshot_name')!r}")
    pool_kwargs = pool_kwargs_from_state(state)

    run_id = f"m2-verify-{int(time.time())}"
    results: list[tuple[str, bool, float, str]] = []

    async with AsyncDaytona() as client:
        pool = SandboxPool(client, run_id=run_id, **pool_kwargs)

        print(f"sweeping any stale sandboxes tagged run_id={run_id} ...")
        await pool.sweep()

        for entry in manifest["files"]:
            test_target = entry["tests"]
            print(f"[{test_target}] creating sandbox, uploading migrated tree, running pytest...")
            try:
                result = await pool.run_pytest(
                    file_contents=file_contents, test_target=test_target
                )
                passed = result.exit_code == 0
                results.append((entry["path"], passed, result.create_ms, result.output))
                status = "PASS" if passed else "FAIL"
                print(f"  {status} (sandbox create: {result.create_ms:.0f}ms, sandboxes_live={pool.sandboxes_live})")
                if not passed:
                    print(result.output)
            except Exception as e:  # noqa: BLE001 -- report and keep going, don't leak sandboxes on one bad file
                results.append((entry["path"], False, 0.0, str(e)))
                print(f"  ERROR: {e}")

        print("final sweep to confirm zero sandboxes remain for this run...")
        leaked = await pool.sweep()
        if leaked:
            print(f"  WARNING: swept {leaked} sandbox(es) that local bookkeeping thought were already deleted")

    print()
    print("=" * 60)
    failed = [path for path, passed, _, _ in results if not passed]
    for path, passed, create_ms, _ in results:
        print(f"  {'PASS' if passed else 'FAIL':4} {path} ({create_ms:.0f}ms)")
    print(f"sandboxes_live (final): {pool.sandboxes_live}")

    if failed:
        print(f"\nFAILED: {len(failed)}/12 file(s) did not pass in sandbox: {failed}")
        return 1
    if pool.sandboxes_live != 0:
        print(f"\nFAILED: sandboxes_live did not return to zero ({pool.sandboxes_live})")
        return 1
    print(f"\nPASSED: all {len(results)} files passed in real sandboxes, sandboxes_live=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()

    if not os.environ.get("DAYTONA_API_KEY") and not os.environ.get("DAYTONA_JWT_TOKEN"):
        print(
            "DAYTONA_API_KEY (or DAYTONA_JWT_TOKEN) is not set.\n"
            "Sign up at https://app.daytona.io, create an API key, then:\n"
            "  export DAYTONA_API_KEY=...\n"
            "before re-running this script."
        )
        return 1

    try:
        return asyncio.run(main_async())
    except FileNotFoundError as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
