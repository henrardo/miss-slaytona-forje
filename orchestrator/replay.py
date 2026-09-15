"""Replay a recorded run's event stream over a WebSocket.

    python -m orchestrator.replay runs/<run_id>.jsonl [--speed 2.0]

Events are re-emitted at their original wall-clock pacing (scaled by
--speed), over the same WebSocket contract a live run uses. The UI cannot
tell replay from live -- no code path, here or in the UI, may branch on it.
This is the stage-insurance fallback: if a live run fails, switch to
`runs/golden.jsonl` and narrate.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Iterable

from orchestrator.events import EventBroadcaster


def load_events(path: Path) -> list[dict]:
    events = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


async def replay(events: Iterable[dict], broadcaster: EventBroadcaster, speed: float = 1.0) -> None:
    """Re-broadcast events, sleeping between them by the delta of their `t`
    fields (divided by `speed` -- higher speed plays back faster)."""
    previous_t = None
    for event in events:
        t = event.get("t", 0.0)
        if previous_t is not None:
            delay = max(0.0, (t - previous_t) / speed)
            if delay:
                await asyncio.sleep(delay)
        previous_t = t
        await broadcaster.broadcast(event)


async def serve_replay(
    path: Path,
    host: str,
    port: int,
    speed: float,
    connect_timeout: float | None = 10.0,
) -> None:
    events = load_events(path)
    broadcaster = EventBroadcaster()
    server = await broadcaster.serve(host, port)
    print(f"replay: serving {len(events)} events from {path} on ws://{host}:{port} (speed={speed}x)")
    try:
        connected = await broadcaster.wait_for_clients(min_clients=1, timeout=connect_timeout)
        if not connected:
            print("replay: no client connected within timeout, playing anyway")
        await replay(events, broadcaster, speed=speed)
        print("replay: done")
    finally:
        server.close()
        await server.wait_closed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="path to a runs/<run_id>.jsonl file")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--speed", type=float, default=1.0, help="pacing multiplier; higher = faster")
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=10.0,
        help="seconds to wait for a UI client before playing anyway (0 = don't wait)",
    )
    args = parser.parse_args(argv)

    timeout = args.connect_timeout if args.connect_timeout > 0 else None
    asyncio.run(serve_replay(args.path, args.host, args.port, args.speed, connect_timeout=timeout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
