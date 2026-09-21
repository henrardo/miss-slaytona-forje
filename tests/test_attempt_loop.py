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


def test_verdict_timeout_is_the_reserve_as_a_floor_not_a_ceiling() -> None:
    """The reserve is a floor. Both ways of getting that wrong cost a run.

    `timeout=deadline - now` was the original bug: Vibe eats the clock, the
    expression evaluates to ~0.0, and the one call that decides success never
    runs. That is the negative assertion below, and it still holds.

    `timeout=VERDICT_RESERVE_S` on its own is the opposite bug, and it cost
    run 7's entire warm arm. It caps grading at 120s however much clock is
    left; the handler underneath reads the resulting TimeoutError as "the
    shared clock expired" and breaks out of the attempt loop permanently.
    warm-0 lost a cold-pool sandbox race at t=46, blew the cap, and finished
    with 1 attempt and 1,060s unused while cold-0 ran 9.

    max() satisfies both: grading can use whatever clock is left, and still
    gets its full reserve when there is none -- so the wait can only expire at
    or after the deadline, which is what the handler claims to detect."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    # `deadline + off_clock` since ingestion moved off the agent's clock:
    # time the harness spends writing the graph after an attempt is added
    # back, so grading still gets whatever ATTEMPT clock is left. The
    # property under test is unchanged -- the reserve is the floor, the
    # remaining clock is the ceiling -- so the string is updated and both
    # negative assertions below stay exactly as they were.
    timeout_expr = ("timeout=max(VERDICT_RESERVE_S,\n"
                    "                            (deadline + off_clock) "
                    "- time.monotonic()),")
    assert timeout_expr in src, (
        "the verdict timeout is no longer max(reserve, remaining); a bare "
        "reserve caps grading and ends the agent's run, a bare remaining "
        "leaves it no time to grade at all"
    )
    assert "timeout=max(0.0, deadline - time.monotonic())" not in src
    # The two original bugs, in whichever form the clock now takes.
    for clock in ("deadline", "(deadline + off_clock)"):
        assert f"timeout={clock} - time.monotonic()" not in src
    assert "timeout=VERDICT_RESERVE_S," not in src


@pytest.mark.parametrize(
    "remaining, expected",
    [(600.0, 600.0), (VERDICT_RESERVE_S + 1, VERDICT_RESERVE_S + 1),
     (10.0, VERDICT_RESERVE_S), (0.0, VERDICT_RESERVE_S),
     (-5.0, VERDICT_RESERVE_S)],
)
def test_the_floor_arithmetic(remaining: float, expected: float) -> None:
    """What max(reserve, remaining) actually yields, including past the
    deadline -- a verdict a few seconds late is worth having."""
    assert max(VERDICT_RESERVE_S, remaining) == expected
    assert max(VERDICT_RESERVE_S, remaining) >= VERDICT_RESERVE_S


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
    """Warm = the same task, the operator's longer list, and a statement
    of what memory tools exist.

    HISTORY WORTH KEEPING. This used to assert that neo4j-agent-memory's
    own 1,935-character MCP instructions were relayed VERBATIM, because
    Vibe drops the `instructions` field from MCP initialize and relaying
    it was the only way the agent learned what its memory tools were for
    -- 40 consecutive runs had ended with zero agent-initiated memory
    calls before that was found. Cognee sends no instructions at all, so
    there is nothing to relay; the assertion below guards the replacement
    against drifting from description into coaching.

    NOTE what is no longer true: cold's prompt used to be a byte-exact PREFIX
    of warm's, so SGLang's RadixAttention could share the whole task text
    across arms. Warm now has three extra numbered steps interleaved into the
    list, so the shared prefix ends at the first sentence. That is a real cost
    of per-arm instructions and it is the operator's call, not a regression to
    fix here."""
    from orchestrator.cognee_layer import MEMORY_TOOLS_GUIDE
    from orchestrator.vibe_agent import _task_prompt

    warm = _task_prompt(None, memory_enabled=True)
    cold = _task_prompt(None, memory_enabled=False)
    assert warm.endswith(MEMORY_TOOLS_GUIDE)
    # Cognee's server ships NO instructions -- `initialize()` returns
    # `instructions=None` -- so there is nothing to relay and this text is
    # ours. It therefore has to be held to the standard the relayed
    # payload got for free: state what exists, do not coach. If a future
    # edit starts telling the agent WHEN to call memory, the experiment
    # is measuring the prompt.
    for coaching in ("ALWAYS", "You should", "Make sure to", "first call"):
        assert coaching not in MEMORY_TOOLS_GUIDE, (
            f"{coaching!r} is instruction, not description")
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
    # Spelled through the workspace since the loop became runnable against a
    # remote host as well as a local checkout. Same guard, same place, same
    # `continue` before the oracle -- only where the transcript is read from
    # moved behind a method.
    assert "workspace.assistant_turns_total() <= turns_before" in src
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


def test_the_attempt_budget_hands_out_exactly_n() -> None:
    from orchestrator.vibe_agent import AttemptBudget

    budget = AttemptBudget(3)
    assert [budget.take() for _ in range(5)] == [True, True, True, False, False]
    assert budget.remaining == 0


def test_the_budget_is_claimed_before_the_attempt_counter() -> None:
    """Claimed on START, so a crash loop spends the budget instead of
    spinning inside it. If it were decremented after a completed attempt, an
    agent that died mid-attempt every time would never exhaust it."""
    import inspect

    src = inspect.getsource(vibe_agent.migrate_codebase)
    take = src.index("budget.take()")
    bump = src.index("attempt += 1")
    assert take < bump, (
        "the budget must be claimed before the attempt counter advances")


def test_a_retry_cannot_hand_the_agent_a_fresh_allowance() -> None:
    """The reason the budget is a shared mutable object and not an int.

    `_attempt_until_done` re-enters `migrate_codebase` after any non-harness
    exception, and `attempt` restarts at 0 in there -- the reset that made
    2026-09-19 run 6 report one attempt where three had run. So the budget
    has to be created ONCE, outside the retry, and forwarded into every
    re-entry.
    """
    import inspect

    from swarm import run as swarm_run

    worker = inspect.getsource(swarm_run.agent_worker)
    assert "AttemptBudget(" not in worker, (
        "agent_worker must RECEIVE a budget, not build one -- it is the "
        "function the retry loop lives in")
    assert "budget=budget" in worker, "the budget must reach _attempt_until_done"

    until_done = inspect.getsource(swarm_run._attempt_until_done)
    assert "AttemptBudget(" not in until_done, (
        "the retry loop must not mint a new budget per re-entry")
    assert "budget=budget" in until_done, (
        "the same budget object must be forwarded into every migrate_codebase "
        "call, or a retry starts the experiment over")

    # And the object really is shared: two "re-entries" draw from one pool.
    budget = vibe_agent.AttemptBudget(3)
    first_entry = [budget.take(), budget.take()]     # two attempts, then a crash
    second_entry = [budget.take(), budget.take()]    # the retry
    assert first_entry == [True, True]
    assert second_entry == [True, False], (
        "the retry got more than the experiment's remaining attempts")


def test_neo4j_settings_have_no_silent_default() -> None:
    """A default URI sent the orchestrator to a local Neo4j while the agents'
    MCP server used the hosted one, so the two halves of a run read different
    graphs -- and the local one still held a trace containing a complete,
    correct migration at 33/33. Which database a measurement runs against must
    not be decided by an unset variable.

    Carried across to Cognee unchanged in spirit: `cognee_layer.configure`
    raises on a missing NEO4J_URI rather than letting cognee fall back to
    its default embedded Kuzu store, which would put the graph somewhere
    nobody is looking while every log line still said "ok".
    """
    import subprocess
    import sys

    from orchestrator.manifest import REPO_ROOT

    # A fresh interpreter with the vars removed: import must fail loudly.
    result = subprocess.run(
        [sys.executable, "-c", "import orchestrator.cognee_layer as c; c.configure()"],
        cwd=REPO_ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert result.returncode != 0, "cognee_layer.configure() ran with no NEO4J_URI set"
    assert "NEO4J_URI is not set" in result.stderr, result.stderr[-500:]


def test_both_arms_are_barrier_parties() -> None:
    """Cold must arrive at the barrier under its own name.

    `agent_label` was passed as `ws.label if warm else None`, so cold
    arrived as "anonymous" -- not a party -- and `arrive()` returned 0.0
    every time. Cold never synchronised; warm waited at barrier 1 for an
    arm that never came and was released only when cold LEFT. On the first
    pod run warm idled from t=195 to t=776 and took 2 attempts to cold's
    4, which is exactly the GPU-contention confound the barrier exists to
    remove.
    """
    import re
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "swarm" / "run.py"
    text = src.read_text()
    assigns = re.findall(r"agent_label\s*=\s*([^,\n]+)", text)
    assert assigns, "agent_label is no longer passed from swarm/run.py"
    for value in assigns:
        assert "if warm" not in value, (
            f"agent_label={value.strip()} makes cold a non-party at the "
            f"attempt barrier, so the arms do not synchronise")


def test_a_stranger_at_the_barrier_is_reported() -> None:
    """Passing through unrecognised must never be silent again."""
    import asyncio

    from orchestrator.sync import AttemptSync

    async def scenario() -> AttemptSync:
        sync = AttemptSync(["warm-0", "cold-0"], timeout=1.0)
        assert await sync.arrive("anonymous") == 0.0
        # An arm that has genuinely left passes through too, but that is
        # expected and must NOT be counted as a stranger.
        sync.leave("cold-0")
        await sync.arrive("cold-0")
        return sync

    sync = asyncio.run(scenario())
    assert sync.strangers == 1, "an unknown arrival was not counted"


# ---- truncated turns: a tool call that never parsed ----------------------
#
# Experiment swarm-1789903474 lost three of its six attempts to this, and it
# read as "the agent plateaued". It had not; it had been cut off.


def _stream(*entries: dict) -> str:
    return "\n".join(json.dumps(e) for e in entries)


def _assistant(text: str, tool_calls: list | None = None) -> dict:
    e = {"type": "message", "role": "assistant",
         "content": [{"type": "text", "text": text}]}
    if tool_calls:
        e["tool_calls"] = tool_calls
    return e


def test_a_leaked_tool_call_is_a_truncated_turn() -> None:
    """warm attempt 3 and cold attempt 3, verbatim in shape.

    The model emitted `[TOOL_CALLS]edit_file[ARGS]{...}` as message TEXT.
    Vibe saw no tool call and ended the attempt at 14 and 20 turns.
    """
    out = _stream(_assistant(
        "I can see the issues now. Let me start by updating the dependency "
        'metadata:[TOOL_CALLS]edit_file[ARGS]{"file_path": "pyproject.toml"}'))
    why = vibe_agent.truncated_turn(out)
    assert why is not None
    assert "leaked" in why and "edit_file" in why


def test_stopping_mid_task_without_a_tool_call_is_a_truncated_turn() -> None:
    """warm attempt 2: no leak, no tool call, sentence ends on a colon."""
    out = _stream(_assistant(
        "Good! The v5010 segments already have the correct annotations. Now "
        "let me update the todo and move to the next task - fixing the "
        "deprecated Field usage:"))
    assert vibe_agent.truncated_turn(out) is not None


@pytest.mark.parametrize("text", [
    "Task completed.",
    "Done.",                       # the rehearsal's fake model
    "The migration is finished and the suite passes.",
    "I could not resolve the remaining failures.",
])
def test_a_finished_agent_is_not_resumed(text: str) -> None:
    """Attempt 1 of both arms ended this way and must be left alone.

    A false positive is expensive, not free: an unnecessary resume replays
    work and doubles the step count. "Done." is here because the first
    version of this detector keyed on a list of completion PHRASES and so
    judged every one of the fake model's turns truncated -- 61/61 became
    59/61 and attempt 1's live steps went 3 -> 6.
    """
    assert vibe_agent.truncated_turn(_stream(_assistant(text))) is None


def test_a_turn_that_made_a_tool_call_is_not_truncated() -> None:
    """The turn ended for some other reason; resuming would be wrong."""
    out = _stream(_assistant("Let me read the file.", tool_calls=[
        {"function": {"name": "read_file", "arguments": "{}"}}]))
    assert vibe_agent.truncated_turn(out) is None


def test_only_the_last_assistant_turn_decides() -> None:
    """A leak mid-session that the model then recovered from is not a
    truncation -- otherwise every long attempt would resume forever."""
    out = _stream(
        _assistant("oops [TOOL_CALLS]edit_file[ARGS]{}"),
        _assistant("Recovered.", tool_calls=[
            {"function": {"name": "bash", "arguments": "{}"}}]),
        _assistant("Task completed."),
    )
    assert vibe_agent.truncated_turn(out) is None


def test_no_output_is_not_treated_as_a_truncated_turn() -> None:
    """That case is ATTEMPT_ABORTED already and has its own handling."""
    assert vibe_agent.truncated_turn("") is None
    assert vibe_agent.truncated_turn("not json at all") is None


def test_continuations_are_bounded_and_emitted() -> None:
    """A serving layer emitting nothing parseable must fail the attempt
    rather than spin on it, and every continuation has to be countable."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "MAX_CONTINUATIONS" in src
    assert "ATTEMPT_CONTINUED" in src
    assert vibe_agent.MAX_CONTINUATIONS >= 1
    assert vibe_agent.MAX_CONTINUATIONS <= 5, (
        "an unbounded retry on a broken endpoint eats the run's clock")


def test_the_continuation_resumes_rather_than_restarting() -> None:
    """`--continue` inside ONE attempt. Restarting would throw away the
    work the truncated turn had already done, which is the whole point."""
    src = inspect.getsource(vibe_agent.migrate_codebase)
    head, _, tail = src.partition("ATTEMPT_CONTINUED")
    assert "resume=True" in tail.split("last_ended_cleanly")[0], (
        "the continuation must resume this attempt's own session")


# --- 7. the grader's numbers, and the agent's own notes -------------------


def test_the_verdict_states_the_graders_numbers_and_adds_nothing() -> None:
    """Warm read past the tally and believed its own summary instead.

    On run 5 attempt 3 warm wrote itself a MIGRATION_SUMMARY.md opening
    "Successfully migrated the x12sdk codebase from Pydantic v1 to
    Pydantic v2", with ticks, while 47 v1 surfaces remained and 202 of 261
    tests failed. Attempts 4 and 5 read it back and ended "Task
    completed." without an edit. The counts were already in the prompt --
    in the tail of 8,000 characters of trimmed tracebacks.

    So they go at the head of the failure block, and they stay bare: no
    instruction rides along, because steering is what this prompt was
    stripped of.
    """
    from orchestrator.vibe_agent import _task_prompt

    verdict = ("- 59 of 261 tests passing\n"
               "- 47 Pydantic v1 surfaces remaining in x12sdk\n"
               "- 65 of 65 source files parse")
    plain = _task_prompt("SomeError: boom", memory_enabled=False)
    with_verdict = _task_prompt("SomeError: boom", memory_enabled=False,
                                verdict=verdict)
    assert with_verdict != plain
    assert verdict in with_verdict
    # Ahead of the output it was measured from, so it cannot be buried.
    assert with_verdict.index(verdict) < with_verdict.index("SomeError: boom")
    # And nothing of ours travels with it.
    assert with_verdict == plain.replace(
        "\n\nThe test suite still fails:",
        f"\n\nThe independent grader measured your last attempt:\n{verdict}"
        "\n\nThe test suite still fails:")


def test_both_arms_get_the_verdict_in_the_same_place() -> None:
    """It is the grader's own count, so it cannot be a warm-only block.
    An unmeasured asymmetry in this prompt has invalidated a series
    before."""
    from orchestrator.vibe_agent import attempt_prompt

    verdict = "- 1 of 2 tests passing"
    warm = attempt_prompt("E: x", "skill", procedure="P", memory="M",
                          verdict=verdict, mcp_tools=True)
    cold = attempt_prompt("E: x", None, verdict=verdict)
    assert verdict in warm and verdict in cold
    assert cold.endswith(warm[warm.index(verdict):])


def test_stray_home_files_go_and_the_checkout_stays(tmp_path: Path) -> None:
    """Runs the real shell, because the risk is in the shell.

    The checkout persisting across attempts IS the experiment, so a clear
    that reached it would delete the work under test. Vibe's own state and
    the agent's venv have to survive too, or the next attempt has no
    agent to run.
    """
    import subprocess

    from swarm.agent_workspace import AgentWorkspace, SwarmHost

    home = tmp_path / "agent-warm-0"
    for name in (".vibe/logs", "venv/bin", "repo/x12sdk", "distill"):
        (home / name).mkdir(parents=True)
    (home / ".bashrc").write_text("export X=1\n")
    (home / "repo" / "x12sdk" / "models.py").write_text("class M: pass\n")
    (home / ".vibe" / "logs" / "session.jsonl").write_text("{}\n")
    (home / "MIGRATION_SUMMARY.md").write_text("Successfully migrated!\n")
    (home / "test_migration.py").write_text("assert True\n")
    (home / "notes.txt").write_text("scratch\n")

    class LocalHost(SwarmHost):
        def run_as(self, agent_user, command, **kw):
            return subprocess.run(["bash", "-c", command], check=False,
                                  capture_output=True, text=True)

    class Local(AgentWorkspace):
        @property
        def home(self) -> str:
            return str(home)

    ws = Local(host=LocalHost(host="fake", port=22, identity=Path("/dev/null")),
               label="warm-0", model="m", model_base_url="http://127.0.0.1:1",
               repo_name="repo")
    removed = ws.clear_stray_home_files()

    assert sorted(removed) == ["MIGRATION_SUMMARY.md", "notes.txt",
                               "test_migration.py"]
    assert (home / "repo" / "x12sdk" / "models.py").read_text() == \
        "class M: pass\n"
    for kept in (".bashrc", ".vibe/logs/session.jsonl", "venv/bin", "distill"):
        assert (home / kept).exists(), kept
    assert not (home / "MIGRATION_SUMMARY.md").exists()
    # Idempotent: a home with nothing stray in it reports nothing removed.
    assert ws.clear_stray_home_files() == []
