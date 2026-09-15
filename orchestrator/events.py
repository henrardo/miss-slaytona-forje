"""Event schema, WebSocket broadcast, and JSONL persistence for a run.

Every event is a flat dict: {"t": <seconds since run start>, "type": <EVENT
TYPE>, ...payload}. This module owns creating, stamping, persisting and
broadcasting those dicts; it does not know anything about agents, sandboxes
or memory. See queries/../README or the build spec (Sec. 8.1) for the full
event-type/payload table.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import websockets
from websockets.asyncio.server import Server, ServerConnection

EVENT_TYPES = frozenset(
    {
        "RUN_START",
        "FILE_CLAIMED",
        "MEMORY_READ",
        "ATTEMPT_START",
        "SANDBOX_CREATED",
        "ATTEMPT_DONE",
        "FILE_DONE",
        "MEMORY_WRITE",
        "METRICS",
        "RUN_END",
    }
)


def make_event(event_type: str, t: float, **payload: Any) -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type!r}")
    return {"t": round(t, 3), "type": event_type, **payload}


class RunClock:
    """Elapsed seconds since the clock was created; stamps every event."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self._start


class JsonlWriter:
    """Appends every event to a run's .jsonl file as it is emitted."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")

    def write(self, event: dict) -> None:
        self._fh.write(json.dumps(event) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()


class EventBroadcaster:
    """Fans out events to every connected WebSocket client.

    Clients are read-only consumers (the UI); nothing they send upstream is
    interpreted. A client that disconnects mid-broadcast is dropped silently
    -- the run must never stall because a browser tab closed.
    """

    def __init__(self) -> None:
        self._clients: set[ServerConnection] = set()

    async def register(self, ws: ServerConnection) -> None:
        self._clients.add(ws)

    async def unregister(self, ws: ServerConnection) -> None:
        self._clients.discard(ws)

    async def broadcast(self, event: dict) -> None:
        if not self._clients:
            return
        message = json.dumps(event)
        stale: set[ServerConnection] = set()
        for ws in list(self._clients):
            try:
                await ws.send(message)
            except websockets.ConnectionClosed:
                stale.add(ws)
        self._clients -= stale

    async def wait_for_clients(self, min_clients: int = 1, timeout: float | None = None) -> bool:
        """Block until at least `min_clients` are connected, or `timeout` elapses.

        Returns True if the threshold was reached, False on timeout. Used so
        a replay (or a live run) doesn't broadcast its opening events into
        the void before the UI has connected.
        """
        loop = asyncio.get_event_loop()
        deadline = None if timeout is None else loop.time() + timeout
        while len(self._clients) < min_clients:
            if deadline is not None and loop.time() >= deadline:
                return False
            await asyncio.sleep(0.05)
        return True

    async def serve(self, host: str, port: int) -> Server:
        async def handler(ws: ServerConnection) -> None:
            await self.register(ws)
            try:
                async for _ in ws:
                    pass
            finally:
                await self.unregister(ws)

        return await websockets.serve(handler, host, port)


class EventBus:
    """The single entry point agents/orchestrator code emits events through.

    Combines timestamping, jsonl persistence and WebSocket broadcast behind
    one `emit()` call, so no caller has to know both sinks exist.
    """

    def __init__(self, run_id: str, runs_dir: Path = Path("runs")) -> None:
        self.run_id = run_id
        self.clock = RunClock()
        self.writer = JsonlWriter(runs_dir / f"{run_id}.jsonl")
        self.broadcaster = EventBroadcaster()

    async def emit(self, event_type: str, **payload: Any) -> dict:
        event = make_event(event_type, self.clock.elapsed(), **payload)
        self.writer.write(event)
        await self.broadcaster.broadcast(event)
        return event

    def close(self) -> None:
        self.writer.close()
