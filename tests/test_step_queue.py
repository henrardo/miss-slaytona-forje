"""The hook's writes are queued; they must still land on the right trace.

Writing to Aura inside the hook cost warm 3.3s per tool call (run 13: 5.16
s/tool-call against cold's 1.78, ~200s of a 310s attempt). Cold pays none of
it and the deadline is wall-clock, so it biased every comparison. The writes
are now queued and drained behind the agent.

The hazard that introduces is misfiling. `set_trace` moves an agent to the
next attempt's trace, and a queued step that resolved its trace at FLUSH time
would be filed under whichever attempt happened to be current when the drain
caught up. The notes already record that class of corruption -- steps from one
run attached to a trace keyed on another run's error. So the trace id is bound
into the queue item at enqueue, and that is what these tests pin.
"""
from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio

from orchestrator.step_memory import StepMemoryService


class RecordingMemory:
    """A ScopedMemory stand-in that records what it was asked to write."""

    def __init__(self) -> None:
        self.steps: list[tuple] = []
        self.fail_next = False
        self.delay = 0.0

    async def add_step(self, trace_id, *, thought, action, observation,
                       generate_embedding=False):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("aura is down")
        self.steps.append((str(trace_id), action, thought))

        class _Step:
            id = f"step-{len(self.steps)}"
        return _Step()

    async def record_tool_call(self, step_id, *, tool_name, arguments):
        return None


@pytest_asyncio.fixture
async def service():
    """Yields (service, memory) and awaits the drain task's cancellation, so
    a leaked task cannot outlive the test's event loop."""
    svc = StepMemoryService()
    mem = RecordingMemory()
    svc.register("warm-0", mem)
    yield svc, mem
    if svc._drain is not None:
        svc._drain.cancel()
        try:
            await svc._drain
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_queued_write_keeps_the_trace_it_was_enqueued_with(service) -> None:
    """THE one that matters. Enqueue against trace A, switch to B, then flush.

    If the item resolved its trace at flush time it would land on B, and the
    graph would say the agent did something during an attempt in which it did
    not."""
    svc, mem = service
    svc.set_trace("warm-0", "trace-A")
    svc._enqueue_write("warm-0", "trace-A", "why", "edit", "ok", {})
    svc.set_trace("warm-0", "trace-B")          # next attempt begins
    svc._enqueue_write("warm-0", "trace-B", "why2", "bash", "ok", {})
    assert await svc.flush(timeout=5)
    assert [(t, a) for t, a, _ in mem.steps] == [("trace-A", "edit"),
                                                 ("trace-B", "bash")]


@pytest.mark.asyncio
async def test_set_trace_flushed_drains_before_moving_on(service) -> None:
    """The previous attempt must be complete in the graph before the next one
    starts retrieving against it."""
    svc, mem = service
    svc.set_trace("warm-0", "trace-A")
    for i in range(5):
        svc._enqueue_write("warm-0", "trace-A", f"t{i}", "edit", "ok", {})
    await svc.set_trace_flushed("warm-0", "trace-B")
    assert len(mem.steps) == 5
    assert {t for t, _, _ in mem.steps} == {"trace-A"}
    assert svc._trace["warm-0"] == "trace-B"


@pytest.mark.asyncio
async def test_the_hook_returns_without_waiting_for_the_write(service) -> None:
    """The whole point: the agent must not pay for the round trip."""
    svc, mem = service
    mem.delay = 0.4
    svc.set_trace("warm-0", "trace-A")
    start = asyncio.get_running_loop().time()
    for _ in range(5):
        svc._enqueue_write("warm-0", "trace-A", "t", "edit", "ok", {})
    enqueue_time = asyncio.get_running_loop().time() - start
    assert enqueue_time < 0.05, (
        f"enqueueing 5 writes took {enqueue_time:.2f}s -- the hook is still "
        f"waiting on the write path"
    )
    assert await svc.flush(timeout=10)
    assert len(mem.steps) == 5


@pytest.mark.asyncio
async def test_a_failed_write_is_counted_and_logged_not_swallowed(service) -> None:
    svc, mem = service
    svc.set_trace("warm-0", "trace-A")
    mem.fail_next = True
    svc._enqueue_write("warm-0", "trace-A", "t", "edit", "ok", {})
    svc._enqueue_write("warm-0", "trace-A", "t2", "bash", "ok", {})
    assert await svc.flush(timeout=5)
    assert svc.errors == 1, "a failed write must be counted"
    assert len(mem.steps) == 1, "the queue must keep going after one failure"


@pytest.mark.asyncio
async def test_overflow_is_reported_rather_than_silent(service) -> None:
    """A dropped step is a hole in the graph. It must be countable."""
    svc, mem = service
    svc.QUEUE_MAX = 3
    svc.set_trace("warm-0", "trace-A")
    mem.delay = 0.2          # keep the drain busy so the queue actually fills
    for _ in range(12):
        svc._enqueue_write("warm-0", "trace-A", "t", "edit", "ok", {})
    assert svc.writes_dropped > 0
    assert "dropped" in svc.queue_report()
    await svc.flush(timeout=10)


@pytest.mark.asyncio
async def test_flush_reports_failure_rather_than_lying(service) -> None:
    """A flush that times out must return False, so the caller can say the
    graph is incomplete instead of reporting counts as if it were whole."""
    svc, mem = service
    mem.delay = 5.0
    svc.set_trace("warm-0", "trace-A")
    svc._enqueue_write("warm-0", "trace-A", "t", "edit", "ok", {})
    assert await svc.flush(timeout=0.3) is False


@pytest.mark.asyncio
async def test_thought_is_never_the_serialised_tool_input(service) -> None:
    """A step whose `thought` is its own arguments is not retrievable by why.

    `search_steps` embeds thought+action. On the remote path every step
    stored `{"pattern": "pydantic", "path": "/home/agent-warm-0/repo", ...}`
    as its thought, because `RemoteTraceBridge.set_pending_reasoning` was a
    no-op AND the entry stream was consumed only after Vibe exited -- so the
    reasoning could not arrive before post_tool fired by any route through
    the operator. harness/reasoning_relay.py now forwards it on the pod, over
    loopback, while the agent is still running.

    This fails if the fallback ever becomes the norm again."""
    svc, mem = service
    svc.set_trace("warm-0", "trace-A")
    tool_input = {"pattern": "pydantic", "path": "/repo", "max_matches": 50}
    svc.set_pending_reasoning("warm-0", "I need to find every v1 import "
                                        "before touching anything.", "turn-1")
    pending = svc._pending_reasoning["warm-0"]
    thought = pending[1]
    svc._enqueue_write("warm-0", "trace-A", thought, "grep", "3 matches", tool_input)
    assert await svc.flush(timeout=5)

    stored = mem.steps[0][2]
    assert stored != json.dumps(tool_input), (
        "thought is the serialised tool input -- the reasoning relay is not "
        "reaching the sidecar, so the graph is searchable by what was typed "
        "and not by why"
    )
    assert not stored.strip().startswith("{"), (
        f"thought looks like a serialised payload, not reasoning: {stored[:120]!r}"
    )
    assert "every v1 import" in stored


@pytest.mark.asyncio
async def test_note_turn_expires_reasoning_so_it_cannot_bleed(service) -> None:
    """Reasoning belongs to one turn. Without expiry, a later turn that
    emitted none silently inherited it -- measured at 20 consecutive steps
    sharing one thought, which made them near-duplicates in the index."""
    svc, _ = service
    svc.set_pending_reasoning("warm-0", "turn one thinking", "turn-1")
    svc.note_turn("warm-0", "turn-2")
    assert "warm-0" not in svc._pending_reasoning
