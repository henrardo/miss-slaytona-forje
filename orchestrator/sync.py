"""Keep the two arms in step at attempt boundaries.

WHY. Warm and cold share ONE SGLang server. If warm's distillation turn
runs while cold is still working, cold's attempt is served by a busy GPU
and takes longer -- so the measured difference between the arms would
include "how much load the other arm happened to be under", which is not
the variable under test. Measured on this hardware: single-stream 182.6
tok/s against 320.1 tok/s across four concurrent requests, i.e. per-stream
throughput roughly halves under contention.

So attempts are synchronised: both arms finish attempt N, everything
off-clock happens while nothing else is running, then both start N+1.

Cold waits through warm's distillation and is paid for it -- the wait is
added to cold's `off_clock`, exactly as the distillation is added to
warm's, so both arms still get the same amount of ATTEMPT time out of a
shared wall-clock deadline. Cold's clock is paused for work it is not
doing.

NOT asyncio.Barrier, which has fixed parties and no way to leave. Agents
drop out at different times -- one converges, one exhausts the clock, one
hits its consecutive-failure limit -- and a fixed-party barrier deadlocks
the survivors the moment the first one finishes. Every waiter here is
released when a party leaves, and there is a timeout as a backstop: a run
that hangs at a barrier has lost more than a confound is worth.
"""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# A barrier wait should last as long as the other arm's remaining attempt.
# This is the backstop for an arm that died without leaving: proceeding
# unsynchronised is a confound, hanging is a lost run.
DEFAULT_TIMEOUT_S = 1800.0


class AttemptSync:
    """A reusable, leavable barrier over the agents still running."""

    def __init__(self, parties: set[str] | list[str], *,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self._parties = set(parties)
        self._timeout = timeout
        self._waiting: set[str] = set()
        self._event = asyncio.Event()
        self._generation = 0
        self.timeouts = 0
        # Arms that have legitimately left, so their later pass-throughs
        # are expected rather than reported as strangers.
        self._left: set[str] = set()
        # Arrivals from a name that is not a party and never was. Non-zero
        # means an arm silently skipped every barrier.
        self.strangers = 0

    @property
    def parties(self) -> set[str]:
        return set(self._parties)

    def leave(self, agent: str) -> None:
        """This agent will not reach any further barrier.

        Called from a `finally`, so an agent that raised does not strand
        the other arm at a barrier it will never reach.
        """
        self._parties.discard(agent)
        self._waiting.discard(agent)
        self._left.add(agent)
        self._release_if_ready()

    def _release_if_ready(self) -> None:
        if self._parties and self._waiting >= self._parties:
            self._generation += 1
            self._waiting.clear()
            self._event.set()
            self._event = asyncio.Event()
        elif not self._parties:
            self._event.set()

    async def arrive(self, agent: str) -> float:
        """Wait until every remaining agent has arrived. Returns seconds
        waited, for the caller to add to its own off_clock."""
        if agent not in self._parties:
            # A non-party passes straight through, which is correct for an
            # arm that has already left -- and was catastrophic when it
            # happened by accident. Cold arrived as "anonymous" (a caller
            # passed `agent_label=... if warm else None`), sailed through
            # every barrier, and left warm waiting 580s for an arm that
            # never arrived. Silence is what made that survive a whole pod
            # run, so an unrecognised name is now counted and logged: it is
            # either a left arm, or a bug that has just voided the
            # wall-clock comparison.
            if agent not in self._left:
                self.strangers += 1
                logger.warning(
                    "%r arrived at the attempt barrier but is not one of its "
                    "parties %s and never left it -- it will not synchronise "
                    "with anything, and this run's wall-clock comparison is "
                    "contaminated", agent, sorted(self._parties))
            return 0.0
        started = time.monotonic()
        self._waiting.add(agent)
        generation = self._generation
        event = self._event
        self._release_if_ready()
        if self._generation != generation:
            # This arrival completed the barrier; nothing to wait for.
            return time.monotonic() - started
        try:
            await asyncio.wait_for(event.wait(), timeout=self._timeout)
        except asyncio.TimeoutError:
            self.timeouts += 1
            self._waiting.discard(agent)
            logger.warning(
                "attempt barrier timed out after %.0fs waiting for %s; "
                "proceeding unsynchronised, so this run's wall-clock "
                "comparison is contaminated",
                self._timeout, sorted(self._parties - {agent}))
        return time.monotonic() - started


class NullSync:
    """No synchronisation: a single-arm run has nothing to wait for."""

    def leave(self, agent: str) -> None:
        return None

    async def arrive(self, agent: str) -> float:
        return 0.0
