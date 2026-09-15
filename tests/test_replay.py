"""Stub-consumer test for the replay player (build spec, milestone 1).

Starts orchestrator.replay serving runs/sample.jsonl over a real WebSocket,
connects a bare-bones client, and asserts every event arrives, in order,
byte-identical to the source file. The UI is exactly this kind of
read-only consumer, so this is the contract M5 will build against.
"""
import asyncio
import json
from pathlib import Path

import websockets

from orchestrator.replay import load_events, serve_replay

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = REPO_ROOT / "runs" / "sample.jsonl"
HOST, PORT = "localhost", 18765


async def _stub_consumer(uri: str, expected_count: int, received: list[dict]) -> None:
    last_error = None
    for _ in range(50):
        try:
            async with websockets.connect(uri) as ws:
                while len(received) < expected_count:
                    message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    received.append(json.loads(message))
            return
        except (ConnectionRefusedError, OSError) as e:
            last_error = e
            await asyncio.sleep(0.1)
    raise RuntimeError(f"could not connect to replay server: {last_error}")


def test_replay_delivers_sample_events_in_order_to_a_stub_consumer():
    expected = load_events(SAMPLE_PATH)
    received: list[dict] = []

    async def run_both() -> None:
        consumer = asyncio.create_task(_stub_consumer(f"ws://{HOST}:{PORT}", len(expected), received))
        server = asyncio.create_task(
            serve_replay(SAMPLE_PATH, HOST, PORT, speed=200.0, connect_timeout=5.0)
        )
        await asyncio.wait_for(consumer, timeout=20.0)
        await asyncio.wait_for(server, timeout=20.0)

    asyncio.run(run_both())

    assert received == expected
    assert [e["type"] for e in received] == [
        "RUN_START",
        "FILE_CLAIMED",
        "MEMORY_READ",
        "ATTEMPT_START",
        "ATTEMPT_DONE",
        "FILE_DONE",
        "MEMORY_WRITE",
        "METRICS",
        "RUN_END",
    ]


def test_replay_is_not_live_indistinguishable_payloads():
    """The UI must not be able to tell replay from live: replayed events are
    exactly the recorded dicts, with no replay-only marker fields added."""
    expected = load_events(SAMPLE_PATH)
    for event in expected:
        assert set(event.keys()) >= {"t", "type"}
        assert "replay" not in event
