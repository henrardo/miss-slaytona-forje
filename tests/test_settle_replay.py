"""`_settle_replay` must let the memory writes finish, not cancel them.

It used to cancel. The replay is the only thing that writes reasoning steps
and messages, so cancelling it left a :ReasoningTrace with a task, an
embedding and nothing inside. Over 41 runs on 2026-09-15 that produced 168
traces holding 13 steps between them, and the entire accumulated-memory series
came out flat because the graph never accumulated anything to retrieve.
"""
from __future__ import annotations

import asyncio

import pytest

from orchestrator.vibe_agent import _settle_replay


@pytest.mark.asyncio
async def test_replay_is_allowed_to_finish() -> None:
    """The regression that mattered: work in flight must still land."""
    written: list[str] = []

    async def replay() -> None:
        await asyncio.sleep(0.05)
        written.append("step")

    task = asyncio.ensure_future(replay())
    await _settle_replay(task)
    assert written == ["step"], "settle cancelled the write instead of joining it"
    assert task.done()


@pytest.mark.asyncio
async def test_none_is_a_noop() -> None:
    await _settle_replay(None)


@pytest.mark.asyncio
async def test_exception_in_replay_is_swallowed() -> None:
    """A failed replay must not take the attempt down with it -- the attempt's
    own verdict still has to be recorded."""
    async def boom() -> None:
        raise RuntimeError("neo4j went away")

    await _settle_replay(asyncio.ensure_future(boom()))


@pytest.mark.asyncio
async def test_stuck_replay_is_cancelled_after_grace() -> None:
    """Bounded, so a hung write cannot hold the whole run open."""
    started = asyncio.Event()

    async def hang() -> None:
        started.set()
        await asyncio.sleep(3600)

    task = asyncio.ensure_future(hang())
    await started.wait()
    await _settle_replay(task, grace_s=0.05)
    assert task.cancelled() or task.done()
