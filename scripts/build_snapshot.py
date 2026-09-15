#!/usr/bin/env python3
"""CLI: build (or check the staleness of) the Daytona snapshot demo sandboxes
run from. Logic lives in orchestrator/snapshot.py; this just wires up argparse
and the Daytona client.

Requires DAYTONA_API_KEY (see https://app.daytona.io) in the environment.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daytona import AsyncDaytona

from orchestrator.snapshot import SNAPSHOT_NAME_DEFAULT, STATE_PATH, is_stale, register_or_warm, save_state


async def build(name: str, cpu: int, memory: int) -> None:
    async with AsyncDaytona() as client:
        state = await register_or_warm(client, name, cpu, memory)
    save_state(state)
    print(f"recorded state at {STATE_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default=SNAPSHOT_NAME_DEFAULT, help="snapshot name to create/update")
    parser.add_argument("--cpu", type=int, default=1, help="vCPUs baked into the snapshot (default: 1, see spec Sec. 9.3)")
    parser.add_argument("--memory", type=int, default=1, help="GiB RAM baked into the snapshot (default: 1)")
    parser.add_argument("--check", action="store_true", help="only check staleness, don't build; exits 1 if stale")
    args = parser.parse_args()

    if args.check:
        stale, message = is_stale()
        print(message)
        return 1 if stale else 0

    asyncio.run(build(args.name, args.cpu, args.memory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
