"""Two agents must actually run at the same time.

They did not, for thirteen runs. `AgentWorkspace.run_vibe` was an `async def`
whose body was a blocking `subprocess.run` over SSH, so the event loop was
pinned for the whole Vibe invocation -- minutes -- and the other agent's
coroutine could not advance. Measured on the live endpoint during run 12:

    #running-req   0 or 1, across all 1,032 scheduler samples, never 2
    #queue-req     0, throughout
    token usage    0.02-0.06

...while the same endpoint served 4 concurrent requests at 543 tok/s the
moment anything asked it to. Warm and cold alternated instead of running
together, which invalidates every wall-clock and attempt-count comparison in
those runs, and silently: a blocked loop is indistinguishable from a slow
model.

These tests use a fake ssh argv (`sleep`) so nothing here needs a pod, a
model, or a network. What they pin is the shape: if the async path is
reintroduced as a blocking call, the elapsed time goes from ~max(durations)
to ~sum(durations) and `test_two_invocations_overlap` fails.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from swarm import agent_workspace
from swarm.agent_workspace import AgentWorkspace, SwarmHost


class FakeHost(SwarmHost):
    """A host whose "ssh" is `sleep`, so concurrency is the only variable."""

    def __init__(self, seconds: float) -> None:
        super().__init__(host="fake", port=22, identity=Path("/dev/null"))
        self.seconds = seconds

    def argv(self, command: str) -> list[str]:
        return ["sleep", str(self.seconds)]

    def argv_as(self, agent_user: str, command: str) -> list[str]:
        return self.argv(command)


def _workspace(seconds: float, label: str) -> AgentWorkspace:
    ws = AgentWorkspace(host=FakeHost(seconds), label=label, model="m",
                        model_base_url="http://127.0.0.1:1")
    # refresh() would try to reach the host; the cache is not what is under
    # test here. Populating it also proves the accessors stop making calls.
    ws._cache = {"tree": {}, "sessions": []}

    async def _noop() -> None:
        return None

    ws.refresh = _noop  # type: ignore[method-assign]
    return ws


SLEEP = 1.0


@pytest.mark.asyncio
async def test_two_invocations_overlap() -> None:
    """The load-bearing one. Sequential execution takes ~2x SLEEP."""
    a, b = _workspace(SLEEP, "warm-0"), _workspace(SLEEP, "cold-0")
    start = time.monotonic()
    await asyncio.gather(
        a.run_vibe("task", timeout_s=30, resume=False, on_entry=None),
        b.run_vibe("task", timeout_s=30, resume=False, on_entry=None),
    )
    elapsed = time.monotonic() - start
    assert elapsed < SLEEP * 1.6, (
        f"two agents took {elapsed:.2f}s for {SLEEP}s of work each -- they ran "
        f"one after the other, not together. Something on the run_vibe path is "
        f"blocking the event loop again (a subprocess.run, a requests call, a "
        f"synchronous ssh)."
    )


@pytest.mark.asyncio
async def test_the_loop_is_free_while_vibe_runs() -> None:
    """A blocked loop starves everything, not just the other agent -- the
    event bus, the deadline checks and the sidecar calls all live there."""
    ws = _workspace(SLEEP, "warm-0")
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    t = asyncio.ensure_future(ticker())
    await ws.run_vibe("task", timeout_s=30, resume=False, on_entry=None)
    t.cancel()
    assert ticks > 5, (
        f"the loop ticked {ticks} times during a {SLEEP}s invocation -- it was "
        f"blocked, so nothing else could make progress"
    )


@pytest.mark.asyncio
async def test_timeout_returns_rather_than_raises() -> None:
    """A clock-cut attempt is still graded, so the timeout path must return a
    CompletedProcess. Raising here unwound agent_worker and produced a run
    that reported '0/0 converged, 0 attempts' while 33 steps had been written.
    """
    ws = _workspace(10.0, "warm-0")
    ws._kill_remote_vibe = lambda: None  # type: ignore[method-assign]
    proc = await ws.invoke_vibe_async("task", timeout=0.3)
    assert proc.returncode == 1
    assert "timed out" in proc.stderr


@pytest.mark.asyncio
async def test_cache_is_dropped_before_the_attempt() -> None:
    """Never answer a post-attempt question with pre-attempt data.

    `collect_file_contents` feeds the Daytona grader. Serving the previous
    attempt's tree would grade the wrong code and attribute the verdict to
    this attempt."""
    ws = _workspace(0.05, "warm-0")
    ws._cache = {"tree": {"stale.py": b"old"}, "sessions": []}
    seen = {}

    async def _capture() -> None:
        seen["cache_after_vibe"] = ws._cache

    ws.refresh = _capture  # type: ignore[method-assign]
    await ws.run_vibe("task", timeout_s=30, resume=False, on_entry=None)
    assert seen["cache_after_vibe"] is None, (
        "run_vibe left the previous attempt's tree in the cache while Vibe ran"
    )


class StreamingThenHangingHost(SwarmHost):
    """Emits a few stream lines, then hangs past the timeout.

    This is what a real attempt looks like when the clock cuts it: Vibe has
    already streamed N complete turns and is mid-way through the next one
    when it is killed.
    """

    def __init__(self, lines: list[str], hang: float) -> None:
        super().__init__(host="fake", port=22, identity=Path("/dev/null"))
        self.lines, self.hang = lines, hang

    def argv(self, command: str) -> list[str]:
        script = "".join(f"printf '%s\\n' {line!r}; " for line in self.lines)
        return ["sh", "-c", f"{script} sleep {self.hang}"]

    def argv_as(self, agent_user: str, command: str) -> list[str]:
        return self.argv(command)


@pytest.mark.asyncio
async def test_a_timeout_keeps_the_stream_that_already_arrived() -> None:
    """Run 10 attempt 3, in miniature.

    That attempt worked for 59 turns, took the suite to 33/33 -- the only
    passing attempt in the run -- hit its timeout, and ingested ZERO steps,
    because `proc.communicate()` buffered the stream inside a coroutine
    that was then cancelled. The agent's whole record of how it succeeded
    went out with it.

    Under a task that cannot be one-shotted this is the common case:
    attempts that run out of clock are exactly the ones carrying the
    failure information the distiller needs.
    """
    entries = [
        '{"type":"reasoning","turnId":"t1","text":"Read the models first."}',
        '{"type":"message","turnId":"t1","role":"assistant","content":[]}',
    ]
    ws = AgentWorkspace(host=StreamingThenHangingHost(entries, hang=30.0),
                        label="warm-0", model="m",
                        model_base_url="http://127.0.0.1:1")
    ws._cache = {"tree": {}, "sessions": []}
    ws._kill_remote_vibe = lambda: None  # type: ignore[method-assign]

    proc = await ws.invoke_vibe_async("task", timeout=1.0)

    assert proc.returncode == 1
    assert "timed out" in proc.stderr
    parsed = ws.stream_entries(proc.stdout)
    assert len(parsed) == 2, (
        f"the timeout threw away the stream: got {parsed}")
    assert parsed[0]["text"] == "Read the models first."


# ---- progressive disclosure: the model does not follow pointers ----------


def _pkg() -> dict[str, bytes]:
    """A relocated AIP package, in the shape v1 actually took."""
    return {
        "SKILL.md": (b"---\nname: s\n---\n\n```yaml\nsteps:\n"
                     b"  - name: migrate-field-validators\n"
                     b"    description: >\n"
                     b"      Before changing field validators, read the "
                     b"matching step in references/validator-migration.md "
                     b"and follow it.\n```\n"),
        "references/validator-migration.md":
            b"# Validators\nRemove allow_reuse. pre=True becomes "
            b'mode="before".\n',
        "references/anti-patterns.md":
            b"# Anti-patterns\nNever import pydantic.v1.\n",
        "source/procedure.schema.json": b"{}",
    }


def test_references_are_inlined_into_the_body() -> None:
    """Measured: zero reference reads across all six attempts of
    swarm-1789903474, despite Vibe handing the agent the absolute base
    directory and the file list. The content has to come to the model."""
    out = agent_workspace.inline_references(_pkg())
    body = out["SKILL.md"].decode()
    assert "Remove allow_reuse" in body
    assert "Never import pydantic.v1" in body
    assert 'mode="before"' in body


def test_the_authored_body_survives_inlining() -> None:
    """Appended, never replaced -- the author's procedure is the skill."""
    out = agent_workspace.inline_references(_pkg())
    body = out["SKILL.md"].decode()
    assert "migrate-field-validators" in body
    assert body.index("migrate-field-validators") < body.index("Remove allow_reuse")


def test_the_reference_files_are_still_written() -> None:
    """The package stays AIP-shaped. This changes the RENDERING handed to
    one model, not the artifact that gets validated and archived."""
    out = agent_workspace.inline_references(_pkg())
    assert out["references/validator-migration.md"] == \
        _pkg()["references/validator-migration.md"]
    assert set(out) == set(_pkg())


def test_inlining_is_idempotent() -> None:
    """install_skill runs every attempt; twice must not double the tail."""
    once = agent_workspace.inline_references(_pkg())
    twice = agent_workspace.inline_references(once)
    assert once["SKILL.md"] == twice["SKILL.md"]


def test_a_package_with_no_references_is_untouched() -> None:
    """v2 and v3 kept their content inline. Nothing to do, and no marker
    appended to a body that does not need one."""
    pkg = {"SKILL.md": b"---\nname: s\n---\nbody\n"}
    assert agent_workspace.inline_references(pkg) == pkg


def test_the_version_hash_stays_the_authored_one() -> None:
    """Otherwise every install reports a version mismatch against what
    `propose` accepted, on every attempt, forever."""
    import inspect
    src = inspect.getsource(agent_workspace.AgentWorkspace.install_skill)
    assert "canonical_body" in src
    assert '"body": _body_sha(canonical_body)' in src
    # and what the model really read is still reported, from the read-back
    assert "body_rendered" in src
