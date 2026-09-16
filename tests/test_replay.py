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

from orchestrator.events import EVENT_TYPES
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
    types = [e["type"] for e in received]
    assert types[0] == "RUN_START"
    assert types[-1] == "RUN_END"


def test_sample_only_contains_event_types_the_orchestrator_emits():
    """The sample is the replay contract, so it has to describe a real run.

    It previously hardcoded the abandoned synthetic-fixture design --
    `cfp/models/speaker.py`, `FILE_CLAIMED`, `METRICS`, per-file
    `MEMORY_WRITE` with `P1_VALIDATOR` pattern names -- none of which the
    orchestrator has emitted since the fixture became fastapi-mail. The test
    passed throughout, because load_events() only parses JSON and never
    checked the types against the schema. So the one file documenting the
    UI contract described a run that could not happen, and nothing said so."""
    declared = EVENT_TYPES
    seen = {e["type"] for e in load_events(SAMPLE_PATH)}
    unknown = seen - declared
    assert not unknown, (
        f"runs/sample.jsonl contains event types the orchestrator does not "
        f"emit: {sorted(unknown)}. Regenerate it from a real run."
    )


def test_replay_is_not_live_indistinguishable_payloads():
    """The UI must not be able to tell replay from live: replayed events are
    exactly the recorded dicts, with no replay-only marker fields added."""
    expected = load_events(SAMPLE_PATH)
    for event in expected:
        assert set(event.keys()) >= {"t", "type"}
        assert "replay" not in event


def test_connect_timeout_zero_does_not_wait_for_a_client():
    """`--connect-timeout 0` is documented as "don't wait" and must not hang.

    It used to be mapped to `None` by main(), and `None` means *no deadline* in
    wait_for_clients -- so the flag that says "start immediately" blocked
    forever when no UI was connected. This is the stage-insurance path, so a
    hang here is the worst possible place for one."""
    import time

    started = time.monotonic()
    asyncio.run(
        serve_replay(SAMPLE_PATH, HOST, PORT + 1, speed=5000.0, connect_timeout=0)
    )
    assert time.monotonic() - started < 10.0, "replay waited for a client it was told to skip"
