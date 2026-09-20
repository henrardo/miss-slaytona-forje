"""The relay must give the sidecar a key that CHANGES between model turns.

`tests/data-vibe-stream-2255.jsonl` is a REAL capture from mistral-vibe
2.25.5, produced by `scripts/probe_turn_ids.py` driving the real binary
against `tests/fake_model_server.py`. Its defining property, and the reason
it exists next to the 2.25.4 capture: **every entry carries the same
`turnId`**. `turnId` is the CONVERSATION turn -- one user prompt -- and an
agent attempt is one prompt, so it never changes for a whole attempt.

That is what broke the 2026-09-20 series. `note_turn()` clears pending
reasoning only when the key changes, so it never fired; `set_pending_
reasoning()` accumulates while the key is equal, so it accumulated across
the entire attempt. Measured on Aura: step thoughts grew 267 -> 1537 chars
and never reset, every step opening with the same sentence, and because
`render_steps` truncates to 300 chars the skill author saw ONE IDENTICAL
SENTENCE PER STEP.

Every existing sidecar test passed throughout, because they hand
`set_pending_reasoning` a turn_id of "t1" then "t2" -- supplying by hand the
one thing the live path never supplied. So these tests drive the REAL relay
over the REAL stream instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

STREAM = Path(__file__).parent / "data-vibe-stream-2255.jsonl"
RELAY = REPO / "harness" / "reasoning_relay.py"


def _relay_messages(stream_text: str) -> list[dict]:
    """Run the real relay over `stream_text`, collecting what it sends.

    The relay talks to the sidecar over a TCP socket, so a stub listener
    stands in for it -- the relay itself is unmodified and is the file the
    installer ships to the pod.
    """
    import socketserver
    import threading

    received: list[dict] = []

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            data = b""
            while not data.endswith(b"\n"):
                chunk = self.request.recv(65536)
                if not chunk:
                    break
                data += chunk
            for line in data.decode().splitlines():
                if line.strip():
                    received.append(json.loads(line))
            self.request.sendall(b"{}\n")

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        proc = subprocess.run(
            [sys.executable, str(RELAY), str(port), "warm-0"],
            input=stream_text, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr[-400:]
    finally:
        server.shutdown()
        server.server_close()
    return received


def test_the_real_2255_stream_carries_exactly_one_turn_id() -> None:
    """Guards the premise. If a future Vibe emits per-turn ids this fails,
    and the relay's counter should then be revisited rather than left to
    double-count."""
    entries = [json.loads(l) for l in STREAM.read_text().splitlines() if l.strip()]
    ids = {e.get("turnId") for e in entries if e.get("turnId")}
    assert len(entries) >= 8, "fixture too small to show turn structure"
    assert len(ids) == 1, f"expected one conversation turn id, got {ids}"


def test_the_relay_gives_each_model_turn_its_own_key() -> None:
    """One key per assistant message, which is one model turn."""
    text = STREAM.read_text()
    entries = [json.loads(l) for l in text.splitlines() if l.strip()]
    assistant_messages = sum(
        1 for e in entries
        if e.get("type") == "message" and e.get("role") == "assistant")

    keys = [m["turn_id"] for m in _relay_messages(text)
            if m.get("control") == "note_turn"]
    assert keys, "the relay sent no note_turn at all"
    # One key per assistant message. The counter advances AFTER the message
    # is forwarded, so the last turn's key is the highest one emitted and
    # there is no extra key past it.
    assert len(set(keys)) == assistant_messages, (
        f"{len(set(keys))} distinct keys for {assistant_messages} assistant "
        f"message(s); the key must change exactly once per model turn")
    # Monotonic and contiguous -- a key that went backwards would make
    # note_turn drop a turn's reasoning onto the wrong step.
    suffixes = [int(k.rsplit("#", 1)[1]) for k in keys]
    assert suffixes == sorted(suffixes), f"keys not monotonic: {suffixes}"
    assert set(suffixes) == set(range(assistant_messages)), suffixes


def test_reasoning_and_its_assistant_message_share_one_key() -> None:
    """`ingest.py` joins the reasoning entry and the assistant message into
    one thought before it flushes. The relay must not split that pair across
    two keys, or the message's text would land on the NEXT step."""
    sends = [m for m in _relay_messages(STREAM.read_text())
             if m.get("control") == "reasoning"]
    assert sends, "the relay forwarded no reasoning"
    by_key: dict[str, int] = {}
    for m in sends:
        by_key[m["turn_id"]] = by_key.get(m["turn_id"], 0) + 1
    assert max(by_key.values()) >= 2, (
        "no key carries both a reasoning entry and its assistant message; "
        f"got {by_key}")


def test_thoughts_do_not_accumulate_across_model_turns() -> None:
    """The regression itself, end to end through the real StepMemoryService.

    Replays the relay's own messages into the sidecar and fires a tool call
    per model turn, then asserts no step's thought contains an earlier
    turn's text. Before the fix every thought was the concatenation of all
    reasoning so far.
    """
    import asyncio

    from orchestrator.step_memory import StepMemoryService
    from tests.test_step_memory import _FakeMem  # the suite's own stub

    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    messages = _relay_messages(STREAM.read_text())

    async def replay() -> None:
        # ONE event loop for the whole replay: StepMemoryService owns an
        # asyncio.Queue and a drain task, and a fresh asyncio.run() per call
        # binds that queue to a loop that is then closed under it.
        seen: list[str] = []
        for msg in messages:
            key = msg.get("turn_id")
            if msg.get("control") == "note_turn":
                svc.note_turn("warm-0", key)
            elif msg.get("control") == "reasoning":
                svc.set_pending_reasoning("warm-0", msg["text"], turn_id=key)
                # One tool call per model turn, fired once its reasoning has
                # arrived -- the shape the post_tool hook produces.
                if key not in seen:
                    seen.append(key)
                    await svc.handle({
                        "agent": "warm-0", "tool_name": "bash",
                        "tool_input": {"command": f"echo {len(seen)}"},
                        "tool_output_text": "ok", "tool_error": None,
                    })

    asyncio.run(replay())

    thoughts = [s["thought"] for s in mem.steps]
    assert len(thoughts) >= 3, f"expected several steps, got {len(thoughts)}"
    lengths = [len(t) for t in thoughts]
    assert lengths != sorted(lengths) or len(set(lengths)) == 1, (
        f"thought lengths are monotonically growing -- still accumulating: "
        f"{lengths}")
    for i, later in enumerate(thoughts[1:], start=1):
        for earlier in thoughts[:i]:
            assert earlier not in later, (
                f"step {i}'s thought still contains step {thoughts.index(earlier)}'s "
                f"text -- reasoning is accumulating across model turns")
