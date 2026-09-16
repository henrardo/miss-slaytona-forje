"""The attempt loop has to produce a graded attempt. Nothing else it does
matters if it doesn't.

Across the 40 runs in runs/accumulation.csv it never did: 19 of the last 20
run logs record `ATTEMPT_DONE: 0`, `SANDBOX_CREATED: 0`, `MEMORY_WRITE: 0`.
Daytona -- the only success oracle -- was never invoked after the baseline,
every trace closed as "ran out of time mid-attempt", warm retrieval was empty
by construction, and token_ratio was noise around 1.0.

Three separate faults had to line up, and each is pinned by a test here:

1. `_run_vibe` was handed the whole remaining deadline. Vibe's loop only stops
   on a text-only assistant turn and the model never emitted one, so one
   invocation ate the run and `pool.run_pytest` was called with 0.0s left.
2. `--max-turns` is CUMULATIVE over a `--continue`d session, so a flat
   per-attempt allowance gives attempt 2 onward zero turns.
3. Vibe blocks on `sys.stdin.read()` for any stdin that is not a TTY, so every
   agent hung before its first LLM call under nohup/CI/redirect.

All three are silent. Each produces a run that completes, prints a plausible
summary, and measures nothing.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest

from orchestrator import vibe_agent
from orchestrator.vibe_agent import (
    VERDICT_RESERVE_S,
    _ended_cleanly,
    _steps_used,
)


# --- 1. an attempt must leave room for its own verdict ---------------------


def test_verdict_reserve_is_smaller_than_a_sane_deadline() -> None:
    """Sanity: the reserve has to fit inside a run, or no attempt ever starts."""
    assert 0 < VERDICT_RESERVE_S < 300


def test_attempt_is_not_started_without_room_to_grade_it() -> None:
    """migrate_codebase must break, not start an attempt it cannot grade.

    The loop guard is `if remaining <= VERDICT_RESERVE_S: break`. Reading it
    out of the source is unlovely, but the alternative is standing up Daytona
    and a model to assert one comparison, and this is the line whose absence
    cost 19 runs."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "remaining <= VERDICT_RESERVE_S" in src, (
        "the deadline guard no longer reserves time for the Daytona verdict; "
        "an attempt started with less than that left will call run_pytest with "
        "~0s and raise TimeoutError instead of grading anything"
    )


def test_verdict_timeout_is_the_reserve_not_the_remaining_deadline() -> None:
    """`timeout=deadline - now` is the specific expression that broke this."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "timeout=VERDICT_RESERVE_S" in src
    assert "timeout=max(0.0, deadline - time.monotonic())" not in src


# --- 2. --max-turns is cumulative across --continue ------------------------


def _write_session(tmp_path: Path, roles: list[str]) -> Path:
    """A minimal VIBE_HOME containing one session transcript."""
    d = tmp_path / "logs" / "session" / "session_20260915_120000_abcd1234"
    d.mkdir(parents=True)
    (d / "messages.jsonl").write_text(
        "\n".join(json.dumps({"role": r, "content": "x"}) for r in roles) + "\n"
    )
    return tmp_path


def test_steps_used_counts_users_and_assistants_only(tmp_path: Path) -> None:
    """Vibe increments stats.steps per user message and per completed
    assistant turn (core/agent_loop/_loop.py:2022, :2106). Tool results do
    not count, and counting them would inflate the allowance."""
    home = _write_session(
        tmp_path, ["user", "assistant", "tool", "assistant", "tool", "user"]
    )
    assert _steps_used(home) == 4


def test_steps_used_is_zero_for_a_fresh_home(tmp_path: Path) -> None:
    assert _steps_used(tmp_path) == 0


def test_steps_used_ignores_unparseable_lines(tmp_path: Path) -> None:
    d = tmp_path / "logs" / "session" / "session_20260915_120000_a"
    d.mkdir(parents=True)
    (d / "messages.jsonl").write_text(
        json.dumps({"role": "user"}) + "\n{ not json\n\n"
        + json.dumps({"role": "assistant"}) + "\n"
    )
    assert _steps_used(tmp_path) == 2


def test_steps_used_reads_the_newest_session(tmp_path: Path) -> None:
    """`--continue` resumes the most recent session, so that is the only one
    whose step count matters. Summing all of them would over-grant turns by
    the size of the agent's whole history."""
    root = tmp_path / "logs" / "session"
    for name, roles in (
        ("session_20260915_100000_old", ["user"] * 9),
        ("session_20260915_110000_new", ["user", "assistant"]),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "messages.jsonl").write_text(
            "\n".join(json.dumps({"role": r}) for r in roles) + "\n"
        )
    assert _steps_used(tmp_path) == 2


def test_vibe_is_never_given_a_turn_limit() -> None:
    """No leash. `--max-turns` must not be passed, and `_run_vibe` must not
    even take the parameter.

    This replaces a test that pinned the cumulative-`--max-turns` arithmetic.
    That arithmetic was correct and the bug it guarded was real, but the whole
    mechanism is gone: capping an attempt at 8 turns meant the agent never
    decided it was finished -- `stop='Turn limit of 8 reached'` on essentially
    every attempt -- and an attempt that loses turns to failed edits (9 of 13
    tool calls, once) had no allowance left to recover. The only bound now is
    the run's own clock minus the verdict reserve.

    Asserted against the source because the flag is passed positionally to
    create_subprocess_exec: there is no object to introspect, and mocking the
    subprocess would test the mock. The docstring is stripped first -- it
    names the flag in order to say it is gone, and matching prose would fail
    on its own explanation."""
    assert "max_turns" not in inspect.signature(vibe_agent._run_vibe).parameters
    src = inspect.getsource(vibe_agent._run_vibe)
    body = src.replace(vibe_agent._run_vibe.__doc__ or "", "")
    assert '"--max-turns"' not in body, "the turn leash is back"


# --- 3. the turn limit is a CLEAN stop, so the session may be resumed ------


def test_turn_limit_counts_as_a_clean_end() -> None:
    """Vibe exits 1 when --max-turns fires, so an exit-code check refuses to
    resume on every attempt and throws away the agent's context each time."""
    out = "<vibe_stop_event>Turn limit of 8 reached</vibe_stop_event>\n"
    assert _ended_cleanly(1, out) is True


def test_natural_stop_counts_as_a_clean_end() -> None:
    assert _ended_cleanly(0, "done") is True


def test_a_real_crash_is_not_a_clean_end() -> None:
    """A session that died of context overflow must NOT be resumed: resuming
    replays the same oversized history into the same 400, and compaction
    cannot run on a history already too large to send."""
    assert _ended_cleanly(1, "The input (35516 tokens) is longer than ...") is False
    assert _ended_cleanly(None, "") is False


# --- 4. vibe must never inherit the orchestrator's stdin -------------------


def test_run_vibe_closes_the_childs_stdin() -> None:
    """Vibe calls get_prompt_from_stdin() unconditionally and blocks in
    sys.stdin.read() for any non-TTY stdin. Inheriting the parent's stdin
    therefore hangs every agent forever under nohup, CI, or a redirect --
    before its first LLM call, with a proxy request count of 0, which is
    indistinguishable from a dead endpoint."""
    src = inspect.getsource(vibe_agent._run_vibe)
    assert "stdin=asyncio.subprocess.DEVNULL" in src


@pytest.mark.asyncio
async def test_vibe_would_hang_on_an_open_stdin_pipe() -> None:
    """Demonstrates the failure mode itself against a stand-in that does what
    Vibe does, so the test does not depend on a GPU or the real binary."""
    code = "import sys; sys.stdin.read(); print('never')"

    async def run(stdin):
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return proc

    # An open pipe that never closes: the child blocks.
    proc = await run(asyncio.subprocess.PIPE)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(proc.communicate(), timeout=1.0)
    proc.kill()
    await proc.wait()

    # DEVNULL: immediate EOF, the child proceeds.
    proc = await run(asyncio.subprocess.DEVNULL)
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
    assert b"never" in stdout


# --- 5. prompt block order is A, B, C -------------------------------------


def test_the_prompt_is_the_users_request_and_not_our_coaching() -> None:
    """The prompt is the task plus the OPERATOR's ordering of the work, and
    still none of the harness's old coaching.

    The one-sentence ceiling this test used to enforce is gone by instruction:
    the numbered procedure is the operator's own, given verbatim. What the
    ceiling was actually protecting against is unchanged and still asserted --
    the ~2,500 tokens of harness-authored technique that used to live here
    (how to invoke pytest, that `edit` matches byte-for-byte including
    indentation, not to resend a failed edit, which errors warrant a lookup).
    That was the harness doing a coding agent's job for it inside an
    experiment about whether the agent can do that job, and anything the model
    needs to know about `edit` belongs in `edit`'s tool description upstream.

    So: procedure yes, technique no."""
    from orchestrator.vibe_agent import _task_prompt

    cold = _task_prompt(None, memory_enabled=False)
    assert cold.startswith(
        "Please migrate this codebase from Pydantic v1 to Pydantic v2.\n\n1. "
    )
    # The operator's list, minus the three steps that name tools cold has not
    # got. Numbering is contiguous, so cold is never told to skip a step.
    assert "\n11. Continue iteratively until the migration is complete." in cold
    assert "12." not in cold
    assert "memory" not in cold.lower(), "cold has no memory tools to be told about"
    # "keep going until" came off this list on 2026-09-16 and went back on
    # when the instruction that needed it was reverted: it bought 1 pytest run
    # across 4 agents and no change in score, against a run where warm-0 made
    # 7 of 7 file operations outside its own checkout.
    for technique in (
        "byte-for-byte", "pytest -q", "stderr", "resend", "relative path",
        "keep going until",
    ):
        assert technique not in cold, f"harness technique is back: {technique!r}"


def test_warm_gets_the_memory_steps_and_the_packages_own_instructions() -> None:
    """Warm = the same task, the operator's longer list, and
    neo4j-agent-memory's own MCP server instructions, verbatim.

    The verbatim property is the load-bearing one. Vibe drops the
    `instructions` field from MCP initialize, so relaying it is the only way
    the agent ever learns what its own memory tools are for; the moment it gets
    paraphrased or trimmed we are writing the guidance ourselves again.

    NOTE what is no longer true: cold's prompt used to be a byte-exact PREFIX
    of warm's, so SGLang's RadixAttention could share the whole task text
    across arms. Warm now has three extra numbered steps interleaved into the
    list, so the shared prefix ends at the first sentence. That is a real cost
    of per-arm instructions and it is the operator's call, not a regression to
    fix here."""
    from neo4j_agent_memory.mcp._instructions import get_instructions
    from orchestrator.vibe_agent import _task_prompt

    warm = _task_prompt(None, memory_enabled=True)
    cold = _task_prompt(None, memory_enabled=False)
    assert warm.endswith(get_instructions("extended"))
    assert "\n14. Continue iteratively until the migration is complete." in warm
    assert "15." not in warm
    # The three memory steps, and the closing note that they are optional.
    assert warm.count("memory tools") == 2
    assert "You do not have to follow them." in warm
    # Same task sentence, same wording of every step they share.
    first = "Please migrate this codebase from Pydantic v1 to Pydantic v2."
    assert warm.startswith(first) and cold.startswith(first)
    for shared in (
        "Review the entire codebase, so you understand how everything is connected.",
        "Use web_lookup to review the Pydantic docs, specifically those about "
        "migration.",
        "Continue iteratively until the migration is complete.",
    ):
        assert shared in warm and shared in cold


def test_the_retry_prompt_only_states_the_failure() -> None:
    """The one thing the agent cannot see: a verdict from a suite that ran in
    Daytona after its turn ended. Stated, not editorialised -- the advice that
    used to follow it was the harness steering, and an agent can read a
    traceback."""
    from orchestrator.vibe_agent import _task_prompt

    p = _task_prompt("SomeError: boom", memory_enabled=False)
    assert p == (
        _task_prompt(None, memory_enabled=False)
        + "\n\nThe test suite still fails:\n```\nSomeError: boom\n```"
    )


# --- 6. an attempt that did no work must not be graded --------------------


def test_assistant_turns_total_is_monotonic_across_sessions(tmp_path: Path) -> None:
    """The abort check compares this before and after the Vibe call, so it has
    to be a TOTAL, not a per-session count.

    `_steps_used` reads only the newest session -- correct for `--max-turns`,
    since that is what `--continue` resumes. But an attempt that starts a
    FRESH session legitimately has a lower newest-session count than the
    previous attempt did, so comparing newest-before against newest-after
    would mark most productive attempts as having done nothing."""
    from orchestrator.vibe_agent import _assistant_turns_total

    root = tmp_path / "logs" / "session"
    for name, roles in (
        ("session_20260915_100000_a", ["user", "assistant", "tool", "assistant"]),
        ("session_20260915_110000_b", ["user", "assistant"]),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "messages.jsonl").write_text(
            "\n".join(json.dumps({"role": r}) for r in roles) + "\n"
        )

    # 2 in the old session + 1 in the new one. _steps_used sees only the new.
    assert _assistant_turns_total(tmp_path) == 3
    assert _steps_used(tmp_path) == 2


def test_assistant_turns_total_is_zero_for_a_fresh_home(tmp_path: Path) -> None:
    from orchestrator.vibe_agent import _assistant_turns_total

    assert _assistant_turns_total(tmp_path) == 0


def test_attempt_with_no_completed_turn_is_aborted_not_graded() -> None:
    """Under load Vibe exits having written the prompt and no assistant
    message. Grading that spends a Daytona sandbox to re-derive a verdict on a
    byte-identical tree and writes a "no edit was made" trace that retrieval
    later surfaces as knowledge."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "_assistant_turns_total(vibe_home) <= turns_before" in src
    assert "ATTEMPT_ABORTED" in src
    # and it must not fall through to the oracle
    abort = src[src.index("<= turns_before"):]
    assert abort.index("continue") < abort.index("pool.run_pytest"), (
        "an aborted attempt must `continue` before reaching the Daytona check"
    )


# --- 5. memory tools arrive ALIASED, and the counter must see them ---------


def test_memory_tools_are_detected_through_vibes_server_alias() -> None:
    """Vibe publishes an MCP tool as f"{server_alias}_{tool}", so the name in
    the transcript is `neo4j-agent-memory_memory_get_context`, not
    `memory_get_context`.

    The detector originally tested `startswith("memory")`. The first time an
    agent ever called memory for itself -- warm-0, attempt 1, immediately after
    the package's own server instructions started reaching the model -- that
    test failed on a name beginning "neo4j-", so `memory_calls` read 0 and
    MEMORY_READ never fired. The single event whose job is to report
    agent-initiated retrieval was silent on the only occasion it was true.

    The aliased string below is copied verbatim out of that run's
    ATTEMPT_DONE payload."""
    from orchestrator.vibe_agent import _is_memory_read, _is_memory_tool

    observed = "neo4j-agent-memory_memory_get_context"
    assert _is_memory_read(observed)
    assert _is_memory_tool(observed)

    # Bare names too -- a differently-aliased server, or a direct call.
    assert _is_memory_read("memory_search")
    assert _is_memory_tool("memory_start_trace")
    # Writes are memory calls but not reads.
    assert not _is_memory_read("neo4j-agent-memory_memory_record_step")
    assert _is_memory_tool("neo4j-agent-memory_memory_record_step")
    # Cypher against the same graph counts as using memory.
    assert _is_memory_read("neo4j-agent-memory_graph_query")
    # ...and Vibe's own tools do not.
    for native in ("edit", "read_file", "bash", "grep", "write_file", "web_lookup"):
        assert not _is_memory_read(native), native
        assert not _is_memory_tool(native), native


# --- 6. everything enabled, but not the operator's home -------------------


def test_agents_get_a_private_home_not_the_operators() -> None:
    """`skill` is enabled, so Vibe's global skills directory must not be the
    real one.

    Vibe resolves it as `Path.home() / ".agents" / "skills"`
    (core/paths/_agents_home.py). With `skill` enabled and HOME inherited,
    warm-0 pulled the operator's installed `find-skills` skill into context as
    an ordinary project file, issued six `edit` calls against
    ~/.agents/skills/find-skills/SKILL.md -- all six missed on `old_string`,
    which is the only reason that file survived -- and at transcript line 52
    tried to write the pydantic `validate_alternative_body` fix into it.

    The answer is containment, not switching `skill` back off: HOME belongs to
    the run, so `user_skills_dirs` finds nothing and the operator's files are
    unreachable, while every tool stays enabled."""
    from orchestrator.vibe_agent import (
        AGENT_HOMES,
        _SHARED_CACHE_ENV,
        agent_home_for,
        _run_vibe,
    )

    home = agent_home_for(Path("/tmp/msf-agents/warm-0.vibe"))
    assert home.is_dir()
    assert str(home).startswith(str(AGENT_HOMES))
    assert home != Path.home()
    # The absence of .agents/ is the mechanism -- user_skills_dirs returns []
    # for a directory that does not exist.
    assert not (home / ".agents").exists(), (
        "an agent's HOME must not contain .agents/, or Vibe will offer it "
        "global skills again"
    )

    # Each agent gets its own, so one cannot reach a sibling's.
    other = agent_home_for(Path("/tmp/msf-agents/cold-0.vibe"))
    assert other != home

    # HOME is actually applied to the child process.
    src = inspect.getsource(_run_vibe)
    assert 'env["HOME"] = str(agent_home_for(vibe_home))' in src

    # ...and the caches stay shared, or uvx re-downloads the memory MCP server
    # on every agent start instead of using the existing cache.
    assert "UV_CACHE_DIR" in _SHARED_CACHE_ENV
    assert Path(_SHARED_CACHE_ENV["UV_CACHE_DIR"]).name == "uv"


# --- 7. a trace's summary must not contradict its own success flag --------


def test_summary_and_success_flag_agree_when_more_tests_pass() -> None:
    """`resolved = success or advanced`, and `advanced` keys on the
    tests-passed delta. So a summary that keys only on the error signature can
    disagree with the flag stored beside it.

    It did. In the graph: attempt 7 stored with success=True under a summary
    reading "This change did NOT help. The suite still fails with the same
    error" -- while tests_passed had gone 2 -> 3. Retrieval ranks on the flag;
    a reader reads the text. The two disagreeing is worse than either being
    wrong on its own."""
    from orchestrator.vibe_agent import observed_fix

    before = {"a.py": "x = 1\n"}
    after = {"a.py": "x = 2\n"}

    helped = observed_fix(
        before, after,
        prior_error="AttributeError: boom",
        next_error="AttributeError: boom",
        suite_passed=False,
        tests_delta=1,
    )
    assert helped is not None
    assert "did NOT help" not in helped
    assert "1 more test(s) pass" in helped

    stuck = observed_fix(
        before, after,
        prior_error="AttributeError: boom",
        next_error="AttributeError: boom",
        suite_passed=False,
        tests_delta=0,
    )
    assert stuck is not None
    assert "did NOT help" in stuck
    assert "no additional tests pass" in stuck


def test_neo4j_settings_have_no_silent_default() -> None:
    """A default URI sent the orchestrator to a local Neo4j while the agents'
    MCP server used the hosted one, so the two halves of a run read different
    graphs -- and the local one still held a trace containing a complete,
    correct migration at 33/33. Which database a measurement runs against must
    not be decided by an unset variable."""
    import subprocess
    import sys

    from orchestrator.manifest import REPO_ROOT

    # A fresh interpreter with the vars removed: import must fail loudly.
    result = subprocess.run(
        [sys.executable, "-c", "import orchestrator.memory"],
        cwd=REPO_ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert result.returncode != 0, "orchestrator.memory imported with no NEO4J_URI set"
    assert "NEO4J_URI is not set" in result.stderr, result.stderr[-500:]
