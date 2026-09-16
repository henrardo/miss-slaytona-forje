"""AsyncDaytona wrapper: sandbox lifecycle, cleanup sweep, resource budget.

One ephemeral sandbox per file-attempt (Sec. 9.2). Every sandbox this module
creates is tagged with a run_id label so a crash mid-run can still be swept
clean afterwards -- the standard way to overspend on Daytona is a loop that
forgets to close them.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from daytona import (
    AsyncDaytona,
    AsyncSandbox,
    CreateSandboxFromImageParams,
    CreateSandboxFromSnapshotParams,
    DaytonaConflictError,
    DaytonaNotFoundError,
    Image,
    ListSandboxesQuery,
    Resources,
)

RUN_ID_LABEL = "miss-slaytona-forje-run-id"


@dataclass
class SandboxResult:
    exit_code: int
    output: str
    create_ms: float


class SandboxPool:
    """Owns every sandbox created for one run_id and guarantees cleanup.

    Sandboxes are created either from a persisted, named Snapshot
    (`snapshot_name`) or from an ad-hoc `Image` definition (`image`) --
    exactly one of the two must be given. The ad-hoc path exists because
    persisted-snapshot registration (`client.snapshot.create`) can be gated
    behind account verification/plan on some Daytona accounts (a 403 there,
    while sandbox create/delete itself works fine, means this); Daytona
    caches ad-hoc image builds server-side by content hash, so repeated
    `image=` creates are just as fast after the first one. Once the account
    is verified for snapshot creation, switch back by passing
    `snapshot_name` instead -- no other code changes needed.

    `sandboxes_live` reflects local bookkeeping only (create succeeded,
    delete hasn't happened yet) -- it's the number to put on screen. `sweep`
    goes to the Daytona API directly and is the source of truth for "did
    anything leak," independent of whether this process is still alive.
    """

    def __init__(
        self,
        client: AsyncDaytona,
        run_id: str,
        snapshot_name: str | None = None,
        image: Image | None = None,
        resources: Resources | None = None,
    ) -> None:
        if (snapshot_name is None) == (image is None):
            raise ValueError("pass exactly one of snapshot_name or image")
        self.client = client
        self.run_id = run_id
        self.snapshot_name = snapshot_name
        self.image = image
        self.resources = resources
        self._live: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def sandboxes_live(self) -> int:
        return len(self._live)

    @asynccontextmanager
    async def sandbox(self) -> AsyncIterator[tuple[AsyncSandbox, float]]:
        """Create one ephemeral sandbox, yield (sandbox, create_ms), delete
        it unconditionally in `finally` -- even if the caller raises.

        No timeout or auto_stop_interval override here: an earlier revision
        passed timeout=60.0 (redundantly restating the SDK's own default of
        60 as if we'd chosen it) and auto_stop_interval=5 (where the SDK's
        own default is None -- an invented number with no basis, layered on
        top of a sandbox that's already explicitly deleted in `finally`
        regardless). Removed; `client.create()` and the params objects now
        get whatever Daytona's own authors decided, undecorated."""
        start = time.monotonic()
        if self.snapshot_name is not None:
            params = CreateSandboxFromSnapshotParams(
                snapshot=self.snapshot_name,
                language="python",
                ephemeral=True,
                labels={RUN_ID_LABEL: self.run_id},
            )
        else:
            params = CreateSandboxFromImageParams(
                image=self.image,
                language="python",
                ephemeral=True,
                labels={RUN_ID_LABEL: self.run_id},
                resources=self.resources,
            )
        box = await self.client.create(params)
        create_ms = (time.monotonic() - start) * 1000
        async with self._lock:
            self._live.add(box.id)
        try:
            yield box, create_ms
        finally:
            async with self._lock:
                self._live.discard(box.id)
            await self.client.delete(box)

    async def run_pytest(
        self, *, file_contents: dict[str, bytes], test_command: str, cwd: str = "/repo",
    ) -> SandboxResult:
        """Upload file_contents (dst path -> bytes) into a fresh sandbox and
        run test_command. One sandbox per call, always deleted.

        This is the whole of Daytona's role in M4 (Sec. 6, corrected
        2026-09-13): running and validating, nothing else. Editing happens
        locally, with Vibe's own unrestricted native tools -- Vibe never
        talks to Daytona at all. Each call here uploads whatever the local
        working tree currently looks like (post-edit) into a fresh,
        disposable sandbox and runs the real test suite against it; no
        sandbox persists across attempts, since there's no in-sandbox state
        to preserve anymore."""
        async with self.sandbox() as (box, create_ms):
            for dst_path, content in file_contents.items():
                await box.fs.upload_file(content, dst_path)
            result = await box.process.exec(test_command, cwd=cwd)
            return SandboxResult(exit_code=result.exit_code, output=result.result, create_ms=create_ms)

    async def sweep(self) -> int:
        """Delete every sandbox tagged with this run_id, regardless of local
        bookkeeping. Call this at startup (to clean up a crashed prior run
        with the same run_id) and from an atexit/signal handler on this one.

        A sandbox this same pool already deleted moments ago (via the
        `sandbox()` finally block) can still show up in `list()` briefly
        before Daytona finishes tearing it down server-side; deleting it
        again then races the in-flight teardown and returns 409 (mid-
        teardown) or 404 (already gone by the time this call lands) --
        both observed in practice under real concurrent load (12 agents
        racing their own sandbox cleanup against this same sweep). Neither
        is a leak -- it's already going away -- so both are counted as
        swept, not raised."""
        deleted = 0
        async for box in self.client.list(ListSandboxesQuery(labels={RUN_ID_LABEL: self.run_id})):
            try:
                await self.client.delete(box)
            except (DaytonaConflictError, DaytonaNotFoundError):
                pass  # already gone or mid-teardown from a delete we issued moments ago
            deleted += 1
        async with self._lock:
            self._live.clear()
        return deleted


def install_cleanup_handlers(pool: SandboxPool) -> None:
    """Best-effort sweep on SIGINT/SIGTERM and, only if needed, at exit.

    This is for the paths that do NOT unwind: a Ctrl-C or a SIGTERM leaves
    every live sandbox running and billable, and the `finally` in `sandbox()`
    cannot help because the interpreter is going away rather than unwinding.

    The atexit hook checks `sandboxes_live` first. A normal run ends with its
    own final `pool.sweep()`, so by the time atexit fires there is nothing to
    do -- and doing it anyway raises: Daytona's SDK uses a thread pool, so a
    sweep issued during interpreter shutdown dies with "cannot schedule new
    futures after interpreter shutdown". That surfaced as a traceback printed
    *after* a clean run's summary, which reads as a failed run and is worse
    than the leak it was guarding against.

    Everything here swallows exceptions on purpose. A best-effort cleanup that
    can fail loudly on the way out is not best-effort."""
    import atexit
    import signal

    def _sweep_sync() -> None:
        if pool.sandboxes_live == 0:
            return
        try:
            asyncio.run(pool.sweep())
        except Exception as exc:  # noqa: BLE001 -- best effort, never raise on the way out
            print(f"  cleanup: could not sweep {pool.sandboxes_live} sandbox(es): {exc!r}")
            print(f"  check app.daytona.io for label {RUN_ID_LABEL}={pool.run_id}")

    atexit.register(_sweep_sync)

    def _handle_signal(signum, frame) -> None:  # noqa: ANN001 -- signal handler signature
        _sweep_sync()
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)
