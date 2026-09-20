"""Warm's treatment is a MIX, and this pins both halves of it.

The first pass of the Cognee migration shipped one half: the MCP server.
Everything in the harness was green -- the server answered, the tools
registered, the procedure was in the graph -- and the model was handed a
prompt byte-identical to cold's. Warm was cold with a longer tool list,
and nothing said so.

So the properties here are about WHAT REACHES THE MODEL and WHAT REACHES
THE GRAPH, not about whether a call was made:

  * cold's prompt is unchanged, byte for byte;
  * warm's carries the procedure Cognee holds and what Cognee retrieved;
  * the attempt runs inside `cognee.agent_memory`, which is what writes
    the session trace;
  * the trace is bridged into the graph with `improve`, without which it
    is visible to its own session and to nothing else;
  * every attempt reports how many characters of memory it was handed,
    because that is the one asymmetry between the arms that costs tokens.

Everything is driven with a fake `cognee` module: these have to run with
no Aura, no OpenAI key and no GPU, which is the difference between a
property that is checked on every commit and one that is checked when
someone remembers to rent a pod.
"""
from __future__ import annotations

import asyncio
import sys
import types
from collections import Counter
from dataclasses import dataclass, field

import pytest

from orchestrator import cognee_layer as C
from orchestrator import vibe_agent
from orchestrator.vibe_agent import attempt_prompt, migrate_codebase


# --- 1. the modes ---------------------------------------------------------


@pytest.mark.parametrize(
    "mode, mcp, injection",
    [("hybrid", True, True), ("mcp", True, False),
     ("deterministic", False, True), ("off", False, False)],
)
def test_each_mode_selects_the_halves_it_names(mode, mcp, injection) -> None:
    assert C.uses_mcp(mode) is mcp
    assert C.uses_injection(mode) is injection


def test_an_unknown_mode_is_refused_at_construction() -> None:
    """Not at the first attempt, on a pod, an hour in."""
    with pytest.raises(ValueError):
        C.CogneeMemory(mode="warm")


# --- 2. rendering what recall returned ------------------------------------


def test_render_recall_reads_the_text_off_each_entry_shape() -> None:
    """`recall` returns a union of eight response models discriminated on
    `source`, and which ones come back depends on what has been distilled.
    Reading one attribute would silently drop the others."""
    class Entry:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    block = C.render_recall([
        Entry(text="pydantic_settings holds BaseSettings now"),
        {"content": "regex= became pattern="},
        Entry(answer="validators take mode="),
    ])
    assert "pydantic_settings holds BaseSettings now" in block
    assert "regex= became pattern=" in block
    assert "validators take mode=" in block


def test_render_recall_skips_entries_with_nothing_readable() -> None:
    """A pydantic repr in the prompt is noise the model pays for and
    cannot use."""
    class Opaque:
        pass

    assert C.render_recall([Opaque(), {"score": 0.4}]) == ""


def test_render_recall_is_capped_and_keeps_the_best_matches() -> None:
    """Recall returns its best match first, so the cut is at the tail.

    The last retrieved-memory block this harness put in a prompt reached
    15,170 characters and warm spent three attempts reporting on it
    instead of migrating anything."""
    entries = [{"text": f"lesson {i}: " + "x" * 200} for i in range(50)]
    block = C.render_recall(entries, limit=500)
    assert len(block) <= 520          # the cap, plus the "[...]" marker
    assert "lesson 0" in block
    assert "lesson 49" not in block


# --- 3. the decorator is Cognee's, with the arguments the docs give -------


class _FakeCognee(types.ModuleType):
    """Just enough of `cognee` to see what the layer asks it for."""

    def __init__(self) -> None:
        super().__init__("cognee")
        self.agent_memory_calls: list[dict] = []
        self.improve_calls: list[tuple] = []

    def agent_memory(self, **kwargs):
        self.agent_memory_calls.append(kwargs)

        def decorate(fn):
            async def wrapper(*a, **kw):
                wrapper.ran = True
                return await fn(*a, **kw)
            wrapper.ran = False
            wrapper.__wrapped__ = fn
            return wrapper
        return decorate

    async def improve(self, dataset, **kwargs):
        self.improve_calls.append((dataset, kwargs))
        stage = types.SimpleNamespace(
            stage="persist_agent_traces", status="completed", reason=None,
            counts={"steps": 3})
        return types.SimpleNamespace(status="completed", stages=[stage])


@pytest.fixture
def fake_cognee(monkeypatch):
    fake = _FakeCognee()
    monkeypatch.setitem(sys.modules, "cognee", fake)
    return fake


def test_the_wrapper_is_cogntes_own_decorator_configured_per_attempt(
        fake_cognee) -> None:
    """It is there to WRITE the trace, scoped to this run's session."""
    async def body(last_error=None):
        return 0

    C.with_agent_memory(body, dataset="ds", session_id="ds:run:warm-0",
                        agent_session_name="msf:warm-0")
    kwargs = fake_cognee.agent_memory_calls[-1]
    assert kwargs["dataset_name"] == "ds"
    assert kwargs["session_id"] == "ds:run:warm-0"
    assert kwargs["save_session_traces"] is True


def test_improve_reports_each_stage_rather_than_a_bare_ok(fake_cognee) -> None:
    """A stage that declines says why, and "nothing was bridged" has to be
    readable off the result -- it is the difference between a memory that
    outlives its session and one that does not."""
    out = asyncio.run(C.improve_from_sessions(["run:warm-0"], dataset="ds"))
    assert fake_cognee.improve_calls == [("ds", {"session_ids": ["run:warm-0"]})]
    assert out["stages"]["persist_agent_traces"]["counts"] == {"steps": 3}


# --- 4. what CogneeMemory hands the loop ----------------------------------


def test_retrieved_is_empty_unless_the_mode_injects(monkeypatch) -> None:
    monkeypatch.setattr(C, "lessons", _async_value("a distilled lesson"))
    assert asyncio.run(C.CogneeMemory(mode="mcp").retrieved()) == ""
    assert asyncio.run(C.CogneeMemory(mode="off").retrieved()) == ""
    assert asyncio.run(C.CogneeMemory(mode="hybrid").retrieved()) == "a distilled lesson"


def test_retrieved_counts_what_it_handed_over(monkeypatch) -> None:
    """Counted here so the run can report warm's injected context without
    the attempt loop keeping a second tally that can disagree."""
    monkeypatch.setattr(C, "lessons", _async_value("x" * 40))
    mem = C.CogneeMemory(mode="hybrid")
    asyncio.run(mem.retrieved())
    asyncio.run(mem.retrieved())
    assert (mem.reads, mem.chars) == (2, 80)


def test_the_decorator_no_longer_retrieves(fake_cognee) -> None:
    """MEASURED 2026-09-21: with `with_memory=True` the decorator read via
    `GRAPH_SUMMARY_COMPLETION`, which re-summarises the subgraph with an
    LLM per call. Three calls against one unchanged graph returned 291,
    329 and 239 characters -- three different texts -- and the content was
    graph topology, not a lesson. Reading the stored `session_learnings`
    documents instead returned 697 characters with the same sha256 three
    times running.

    A treatment that varies between two attempts with an identical graph
    cannot be attributed to memory rather than to the summariser."""
    async def body(last_error=None):
        return 0

    C.with_agent_memory(body, dataset="ds", session_id="ds:run:warm-0",
                        agent_session_name="msf:warm-0")
    kwargs = fake_cognee.agent_memory_calls[-1]
    assert kwargs["with_memory"] is False, (
        "the decorator must not retrieve: its retrieval is an LLM summary")
    # ...but it must still WRITE the trace, which is why it is there.
    assert kwargs["save_session_traces"] is True


def test_our_writes_do_not_fire_background_improves(fake_cognee) -> None:
    """`remember` defaults to `self_improvement=True`, which launches an
    improve in the background -- cognee's own `wait_for_background_tasks`
    docstring says so. Left on, the bridge races the explicit one and what
    is in the graph when the next attempt reads becomes a question about
    timing."""
    import inspect

    src = inspect.getsource(C)
    assert src.count("self_improvement=False") >= 2, (
        "both remember() call sites must opt out; the harness owns the "
        "bridge, at a point in the loop it controls")
    assert "wait_for_background_tasks" in src


def test_the_procedure_is_injected_only_when_the_mode_injects(monkeypatch) -> None:
    """`mcp` mode leaves the procedure in the graph and gives the agent
    `cognee_recall`. Injecting it anyway would make `mcp` and `hybrid` the
    same experiment under two names."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Do the thing."))
    assert asyncio.run(C.CogneeMemory(mode="hybrid").procedure()) == "1. Do the thing."
    assert asyncio.run(C.CogneeMemory(mode="deterministic").procedure()) == "1. Do the thing."
    assert asyncio.run(C.CogneeMemory(mode="mcp").procedure()) == ""
    assert asyncio.run(C.CogneeMemory(mode="off").procedure()) == ""


def test_memory_context_is_empty_outside_a_decorated_call() -> None:
    """Every cold attempt, and every attempt before Cognee retrieves
    anything. Normal, and not an error."""
    assert C.memory_context() == ""


# --- 5. the prompt --------------------------------------------------------


def test_colds_prompt_is_unchanged_by_any_of_this() -> None:
    """The arms have to differ in the treatment and nothing else. Cold's
    prompt is the task, the operator's numbered list, and the previous
    verdict -- as it has always been."""
    cold = attempt_prompt("E   ImportError: BaseSettings", None)
    assert "Your procedure" not in cold
    assert "What you and other agents learned" not in cold
    assert "cognee" not in cold.lower()
    assert cold.endswith("The test suite still fails:\n```\n"
                         "E   ImportError: BaseSettings\n```")


def test_warms_prompt_carries_the_procedure_and_the_recalled_memory() -> None:
    warm = attempt_prompt(
        "E   ImportError: BaseSettings", "pydantic-v2-migration",
        procedure="1. Move BaseSettings to pydantic_settings.",
        memory="A previous attempt shimmed pydantic.v1 and was rejected.",
        mcp_tools=True)
    assert "1. Move BaseSettings to pydantic_settings." in warm
    assert "A previous attempt shimmed pydantic.v1 and was rejected." in warm
    assert "cognee_recall" in warm
    # THE TASK COMES FIRST. It once came after a retrieved-memory block,
    # and warm-1 spent three attempts reporting on the memory instead of
    # migrating anything -- which is a reasonable thing to do when you are
    # handed a page of prose before you are told what the job is.
    assert warm.startswith("Please migrate this codebase")
    # ...and the verdict comes last, where the agent reads it.
    assert warm.rstrip().endswith("```")
    assert warm.index("Your procedure") < warm.index("The test suite still fails")


def test_the_memory_block_says_the_agent_need_not_follow_it() -> None:
    """It is evidence, not instruction. An attempt that treats a previous
    agent's wrong turn as a spec is worse than one with no memory."""
    warm = attempt_prompt(None, None, memory="something a previous agent did")
    assert "You do not have to follow any of it." in warm


# --- 6. the loop, end to end, with everything faked -----------------------


@dataclass
class _FakeWorkspace:
    """A Workspace that records the prompts it was given."""

    prompts: list[str] = field(default_factory=list)
    turns: int = 0
    installed_skill_version: int | None = None

    async def run_vibe(self, task, *, timeout_s, resume, on_entry):
        self.prompts.append(task)
        self.turns += 1
        return 0, '{"type": "message", "role": "assistant", "text": "done"}'

    def snapshot(self):
        return {"pkg/config.py": "sha"}

    def collect_file_contents(self):
        return {"/repo/pkg/config.py": b"from pydantic import BaseModel\n"}

    def assistant_turns_total(self):
        return self.turns

    def tool_calls_total(self):
        return Counter({"edit": 1})

    def steps_used(self):
        return 2

    def stream_entries(self, stdout):
        return []


class _FakePool:
    """The grader, scripted. One failing attempt, then a pass."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)

    async def run_pytest(self, *, file_contents, test_command):
        from orchestrator.sandbox import SandboxResult

        code, output = self.verdicts.pop(0) if self.verdicts else (0, "1 passed")
        return SandboxResult(exit_code=code, output=output, create_ms=1.0)


def _run_loop(mem, *, attempts=2, monkeypatch=None):
    """Drive the real attempt loop twice and return (events, workspace)."""
    import time as _time

    ws = _FakeWorkspace()
    pool = _FakePool([
        (1, "E   ImportError: cannot import name 'BaseSettings'\n"
            "=== 2 passed, 8 failed in 1.0s ==="),
        (0, "=== 10 passed in 1.0s ==="),
    ])
    events: list[tuple[str, dict]] = []

    async def emit(event_type, **kw):
        events.append((event_type, kw))

    result = asyncio.run(migrate_codebase(
        pool=pool, workspace=ws, test_command="pytest -q",
        deadline=_time.monotonic() + 600, emit=emit, mem=mem,
        session_id="run:warm-0" if mem is not None else None,
        agent_label="warm-0" if mem is not None else "cold-0",
        budget=vibe_agent.AttemptBudget(attempts),
    ))
    return result, events, ws


def test_the_warm_loop_runs_inside_cognees_decorator_and_bridges_after(
        fake_cognee, monkeypatch) -> None:
    """The whole deterministic half, asserted where it is observable.

    Each property here has a failure mode that every other check in this
    harness reports as healthy: an attempt that never entered the
    decorator writes no trace; a prompt without the procedure is a cold
    attempt wearing warm's label; an improve() that never runs leaves the
    trace where only its own session can see it.
    """
    mem = C.CogneeMemory(dataset="ds", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    monkeypatch.setattr(C, "current_procedure",
                        _async_value("1. Move BaseSettings."))
    monkeypatch.setattr(C, "lessons",
                        _async_value("attempt 1 shimmed pydantic.v1"))

    result, events, ws = _run_loop(mem)

    assert result.attempts == 2
    # The decorator wrapped the attempt body -- `cognee.agent_memory` was
    # asked for once per attempt, because its config is per run and fixed
    # at decoration time.
    assert len(fake_cognee.agent_memory_calls) == 2
    # Both halves reached the model.
    assert all("1. Move BaseSettings." in p for p in ws.prompts)
    assert any("attempt 1 shimmed pydantic.v1" in p for p in ws.prompts)
    # The session traces were bridged, once per attempt.
    ingested = [kw for name, kw in events if name == "INGESTED"]
    assert [kw["source"] for kw in ingested] == ["cognee.improve"] * 2
    assert all(kw["steps"] == 3 for kw in ingested)
    # And the cost of the injection is on the record.
    done = [kw for name, kw in events if name == "ATTEMPT_DONE"]
    assert all(kw["memory_chars"] > 0 for kw in done)
    assert all(kw["procedure_chars"] > 0 for kw in done)
    reads = [kw for name, kw in events if name == "MEMORY_READ"]
    assert all(r["sources"] == ["cognee.agent_memory"] for r in reads)


def test_the_cold_loop_touches_cognee_not_at_all(fake_cognee) -> None:
    """`mem=None` is not a gate, it is an absence: no decorator, no
    retrieval, no trace, no improve, nothing in the prompt."""
    result, events, ws = _run_loop(None)

    assert result.attempts == 2
    assert fake_cognee.agent_memory_calls == []
    assert fake_cognee.improve_calls == []
    assert not [name for name, _ in events if name in ("INGESTED", "MEMORY_READ")]
    assert all("Your procedure" not in p for p in ws.prompts)
    done = [kw for name, kw in events if name == "ATTEMPT_DONE"]
    assert all(kw["memory_chars"] == 0 for kw in done)


def test_a_memory_failure_before_the_attempt_does_not_cost_the_attempt(
        fake_cognee, monkeypatch) -> None:
    """Cognee resolves the agent user, the dataset scope and a connection
    BEFORE the wrapped body runs, and outside its own error handling. A
    graph that is unreachable at that moment must cost retrieval and a
    trace -- not the agent's work."""
    mem = C.CogneeMemory(dataset="ds", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))

    def exploding_decorator(**kwargs):
        def decorate(fn):
            async def wrapper(*a, **kw):
                raise RuntimeError("no route to Aura")
            return wrapper
        return decorate

    monkeypatch.setattr(fake_cognee, "agent_memory", exploding_decorator)
    result, events, ws = _run_loop(mem)

    assert result.attempts == 2
    assert len(ws.prompts) == 2, "the attempts ran without their memory"
    # The procedure still reached the model: it is read separately, not
    # through the decorator.
    assert all("1. Move it." in p for p in ws.prompts)


def _async_value(value):
    async def f(*a, **kw):
        return value
    return f


def test_off_is_a_real_off_switch(fake_cognee) -> None:
    """`off` makes warm == cold: no decorator, no trace, no bridge.

    It exists to prove the harness -- a run where the arms differ in
    nothing should produce two arms that behave the same, and if it does
    not, the difference being measured elsewhere is not the treatment."""
    mem = C.CogneeMemory(mode="off", session_id="run:warm-0")

    async def body(last_error=None):
        return "ran"

    assert mem.wrap_attempt(body) is body
    assert asyncio.run(mem.improve())["stages"] == {}
    assert fake_cognee.agent_memory_calls == []
    assert fake_cognee.improve_calls == []


# --- 7. what the dataset does and does not isolate ------------------------


def test_forget_can_be_told_to_forget_everything(fake_cognee) -> None:
    """MEASURED, 2026-09-20: a dataset-scoped Cognee graph search returns
    other datasets' content. A marker added only to dataset A came back
    from a search told to read only dataset B.

    Writes are scoped; graph reads are not, because every dataset lives
    in one Neo4j database. So `--reset-memory` on one dataset does not
    give a clean graph, and the only complete reset available on a single
    instance is this one -- which is why it has its own flag rather than
    being a wider default."""
    calls = []

    async def forget(**kw):
        calls.append(kw)
        return {}

    fake_cognee.forget = forget
    asyncio.run(C.forget_everything(dataset="msf-x12sdk"))
    asyncio.run(C.forget_everything(dataset="msf-x12sdk", everything=True))
    assert calls == [{"dataset": "msf-x12sdk"}, {"everything": True}]


# --- 8. the skill is scored on the fuzzy measure, not the step function ---


def test_the_score_is_closeness_not_the_test_count() -> None:
    """THE MEASURE THAT MATTERS, and the one this was scored on before.

    `tests_passed` is a step function on these fixtures: the package
    either imports or it does not. Measured on x12sdk 2026-09-21, warm
    attempt 3 scored 60 of 261 tests at closeness 0.0161 -- its LEAST
    reference-like tree -- while cold at 0 tests was at 0.0495. Scoring
    the skill on the suite taught it that the import fix was the win."""
    # The suite is a step function; the score must not follow it.
    assert C.score_from_verdict(tests_passed=60, tests_total=261,
                                closeness=0.0161) == pytest.approx(0.0161)
    assert C.score_from_verdict(tests_passed=0, tests_total=261,
                                closeness=0.0495) == pytest.approx(0.0495)
    # ...so the attempt with FEWER tests passing can score higher, which
    # is the whole point.
    assert (C.score_from_verdict(tests_passed=0, tests_total=261, closeness=0.0495)
            > C.score_from_verdict(tests_passed=60, tests_total=261, closeness=0.0161))


def test_damage_scores_zero_not_negative() -> None:
    """closeness is SIGNED: -1.9748 was recorded when cold left a syntax
    error. Cognee requires [0,1], and "worse than not trying" has no
    reading below "no credit"."""
    assert C.score_from_verdict(tests_passed=0, tests_total=261,
                                closeness=-1.9748) == 0.0


def test_a_green_suite_is_a_one_however_it_got_there() -> None:
    """The suite is a bad gradient and a perfect terminator. Closeness
    cannot express "solved": two arms that both passed all 445 tests on
    oapi scored 0.86 and 0.91, because it ranks resemblance to one
    implementation, never correctness."""
    assert C.score_from_verdict(tests_passed=261, tests_total=261,
                                closeness=0.86) == 1.0


def test_without_an_answer_key_it_falls_back_and_says_so() -> None:
    """A fixture with no reference cannot be scored well; the fallback is
    the suite ratio, with the step-function caveat documented at the
    function."""
    assert C.score_from_verdict(tests_passed=130, tests_total=260,
                                closeness=None) == pytest.approx(0.5)
    assert "step function" in C.score_from_verdict.__doc__
