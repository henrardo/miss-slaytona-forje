"""The arms must not overlap one arm's off-clock work with the other's attempt.

Warm and cold share one SGLang server, and per-stream throughput on this
hardware roughly halves under contention (182.6 tok/s single vs 320.1
across four concurrent). A distillation turn running while cold is still
working makes cold slower, and that slowdown would land in the wall-clock
comparison as though it were an effect of memory.

The other half is that nobody deadlocks. Agents leave at different times --
one converges, one runs out of clock, one hits its failure limit -- and a
fixed-party barrier strands the survivors the moment the first one stops.
"""
from __future__ import annotations

import asyncio

import pytest

from orchestrator.sync import AttemptSync, NullSync


@pytest.mark.asyncio
async def test_neither_arm_proceeds_until_both_arrive() -> None:
    sync = AttemptSync(["warm-0", "cold-0"])
    order: list[str] = []

    async def agent(name: str, work: float) -> None:
        await asyncio.sleep(work)
        order.append(f"{name}-arrived")
        await sync.arrive(name)
        order.append(f"{name}-released")

    await asyncio.gather(agent("warm-0", 0.01), agent("cold-0", 0.10))
    # Both arrivals must precede either release: that is the barrier.
    assert order.index("warm-0-released") > order.index("cold-0-arrived")


@pytest.mark.asyncio
async def test_the_waiting_arm_is_paid_for_waiting() -> None:
    """Cold is not working during warm's distillation, so it is not
    charged for it -- the wait is returned for the caller to add to its
    own off_clock, which is what keeps ATTEMPT time equal."""
    sync = AttemptSync(["warm-0", "cold-0"])
    waited: dict[str, float] = {}

    async def fast() -> None:
        waited["cold"] = await sync.arrive("cold-0")

    async def slow() -> None:
        await asyncio.sleep(0.25)
        waited["warm"] = await sync.arrive("warm-0")

    await asyncio.gather(fast(), slow())
    assert waited["cold"] >= 0.2, f"cold waited {waited['cold']:.2f}s, unpaid"
    assert waited["warm"] < 0.1


@pytest.mark.asyncio
async def test_an_agent_that_leaves_does_not_strand_the_other() -> None:
    """The deadlock this exists to avoid: one arm converges and stops
    while the other is still looping."""
    sync = AttemptSync(["warm-0", "cold-0"])

    async def leaver() -> None:
        await asyncio.sleep(0.05)
        sync.leave("warm-0")

    async def survivor() -> None:
        await sync.arrive("cold-0")

    await asyncio.wait_for(asyncio.gather(leaver(), survivor()), timeout=5)


@pytest.mark.asyncio
async def test_leaving_while_the_other_already_waits_releases_it() -> None:
    sync = AttemptSync(["warm-0", "cold-0"])
    released = asyncio.Event()

    async def survivor() -> None:
        await sync.arrive("cold-0")
        released.set()

    task = asyncio.ensure_future(survivor())
    await asyncio.sleep(0.05)
    assert not released.is_set(), "released before the other arm left"
    sync.leave("warm-0")
    await asyncio.wait_for(released.wait(), timeout=5)
    await task


@pytest.mark.asyncio
async def test_the_barrier_is_reusable_across_attempts() -> None:
    """One barrier, many attempts. A single-shot barrier would let the
    arms drift apart from attempt 2 onwards."""
    sync = AttemptSync(["warm-0", "cold-0"])
    rounds: list[int] = []

    async def agent(name: str) -> None:
        for i in range(3):
            await sync.arrive(name)
            rounds.append(i)

    await asyncio.wait_for(
        asyncio.gather(agent("warm-0"), agent("cold-0")), timeout=5)
    assert rounds == [0, 0, 1, 1, 2, 2]


@pytest.mark.asyncio
async def test_a_dead_arm_times_out_rather_than_hanging_the_run() -> None:
    """Proceeding unsynchronised contaminates a comparison; hanging loses
    the run. The timeout is the backstop, and it is counted."""
    sync = AttemptSync(["warm-0", "cold-0"], timeout=0.2)
    waited = await asyncio.wait_for(sync.arrive("cold-0"), timeout=5)
    assert waited >= 0.2
    assert sync.timeouts == 1


@pytest.mark.asyncio
async def test_a_single_arm_run_never_waits() -> None:
    sync = NullSync()
    assert await sync.arrive("warm-0") == 0.0
    sync.leave("warm-0")


@pytest.mark.asyncio
async def test_an_unknown_agent_does_not_block_the_barrier() -> None:
    """An agent that already left must not be able to re-enter and hold
    the remaining arm."""
    sync = AttemptSync(["warm-0"])
    assert await asyncio.wait_for(sync.arrive("cold-0"), timeout=5) == 0.0
