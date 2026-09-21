"""What reaches the model, and what reaches the graph.

The first pass of the Cognee migration shipped a memory layer that was fully
wired and carried nothing. Everything was green -- the MCP server answered,
the tools registered, the procedure was in the graph, `improve` ran every
attempt -- and the only thing the graph learned per attempt was

    "attempt 3: vibe exited 0 after 12 assistant turn(s)"

because `observed_fix`, the function that says what the edit did and whether
it helped, had become dead code. Distillation had nothing about Pydantic to
distil, so it distilled process advice, and warm was cold with a longer
prompt.

So the properties here are about CONTENT:

  * one outcome document per graded attempt, carrying the grader's verdict
    and the diff, written into the WORKED or the FAILED node set;
  * node sets carry the fixture name, because a Cognee recall ignores the
    dataset it is given and node sets are the only scoping that holds;
  * the next attempt's prompt gets both halves back, LABELLED, so the model
    is told which paragraph to repeat and which to avoid;
  * the code graph comes from `get_code_graph_tasks`, not from anything this
    harness parsed itself;
  * cold's prompt is unchanged, byte for byte.

Driven with a fake `cognee`: these run with no Aura, no OpenAI key and no
GPU, which is the difference between a property checked on every commit and
one checked when someone remembers to rent a pod.
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


def test_every_injected_block_is_capped() -> None:
    """The last uncapped retrieved-memory block this harness injected reached
    15,170 characters and warm spent three attempts reporting on it."""
    assert C.MAX_BLOCK_CHARS <= 4000
    assert C._cap("a" * 9000, 100).endswith("[...]")
    assert len(C._cap("a" * 9000, 100)) <= 110


# --- 2. the fake ----------------------------------------------------------


class _FakeCognee(types.ModuleType):
    """Just enough of `cognee` to see what the layer asks it for, plus a
    node-set-keyed store so a recall can return what a remember wrote."""

    def __init__(self) -> None:
        super().__init__("cognee")
        self.agent_memory_calls: list[dict] = []
        self.improve_calls: list[tuple] = []
        self.remembered: list[tuple[Any, dict]] = []
        self.pipelines: list[dict] = []
        self.recalls: list[dict] = []
        # What `improve`/`distill_sessions` left in the graph for a later
        # recall to find. Set by a test; the harness no longer writes here.
        self.graph: list[str] = []

    def agent_memory(self, **kwargs):
        self.agent_memory_calls.append(kwargs)

        def decorate(fn):
            async def wrapper(*a, **kw):
                return await fn(*a, **kw)
            return wrapper
        return decorate

    async def remember(self, data, dataset_name=None, **kwargs):
        self.remembered.append((data, dict(kwargs, dataset_name=dataset_name)))
        return types.SimpleNamespace(items=[], items_processed=1)

    async def recall(self, query, *, datasets=None, query_type=None,
                     only_context=False, top_k=15, **kw):
        self.recalls.append(dict(query=query, datasets=datasets,
                                 query_type=query_type,
                                 only_context=only_context, top_k=top_k,
                                 **kw))
        out = [types.SimpleNamespace(source="graph", text=t)
               for t in self.graph]
        # A cold dataset answers with a warming-up marker, not [].
        return out or [types.SimpleNamespace(
            source="system", status="memory_warming_up",
            text="Memory is still warming up.")]

    async def improve(self, dataset, **kwargs):
        self.improve_calls.append((dataset, kwargs))
        stage = types.SimpleNamespace(
            stage="persist_agent_traces", status="completed", reason=None,
            counts={"steps": 3})
        return types.SimpleNamespace(status="completed", stages=[stage])

    async def run_custom_pipeline(self, **kwargs):
        self.pipelines.append(kwargs)
        return types.SimpleNamespace(status="completed")

    async def search(self, **kwargs):
        return []

    async def wait_for_background_tasks(self, timeout=None):
        return True


from typing import Any  # noqa: E402  (used by _FakeCognee's annotations)


@pytest.fixture
def fake_cognee(monkeypatch):
    fake = _FakeCognee()
    monkeypatch.setitem(sys.modules, "cognee", fake)
    search_type = types.ModuleType("cognee")
    monkeypatch.setattr(fake, "SearchType",
                        types.SimpleNamespace(CHUNKS="CHUNKS", CODE="CODE"),
                        raising=False)
    del search_type
    return fake


# --- 3. the decorator writes, and does not read ---------------------------


def test_the_wrapper_is_cognees_own_decorator_configured_per_attempt(
        fake_cognee) -> None:
    async def body(last_error=None):
        return 0

    C.with_agent_memory(body, dataset="ds", session_id="ds:run:warm-0",
                        agent_session_name="msf:warm-0",
                        node_set_name="msf-x12sdk")
    kwargs = fake_cognee.agent_memory_calls[-1]
    assert kwargs["dataset_name"] == "ds"
    assert kwargs["session_id"] == "ds:run:warm-0"
    assert kwargs["save_session_traces"] is True
    # The bridged traces must land where the scoped read looks. Left at the
    # default node set the write is unscoped and the read finds nothing.
    assert kwargs["persist_session_trace_node_set_name"] == "msf-x12sdk"


def test_the_decorator_does_not_retrieve(fake_cognee) -> None:
    """MEASURED 2026-09-21: with `with_memory=True` the decorator reads via
    `GRAPH_SUMMARY_COMPLETION` -- hardwired, see
    cognee.modules.agent_memory.runtime -- which re-summarises the subgraph
    with an LLM per call. Three calls against one unchanged graph returned
    291, 329 and 239 characters, three different texts, describing graph
    TOPOLOGY. Reading stored documents back with CHUNKS returned the same
    bytes three times running.

    A treatment that varies between two attempts with an identical graph
    cannot be attributed to memory rather than to the summariser."""
    async def body(last_error=None):
        return 0

    C.with_agent_memory(body, dataset="ds", session_id="s",
                        agent_session_name="msf:warm-0",
                        node_set_name="msf-x12sdk")
    kwargs = fake_cognee.agent_memory_calls[-1]
    assert kwargs["with_memory"] is False
    assert kwargs["save_session_traces"] is True


def test_bridge_reports_each_stage_rather_than_a_bare_ok(fake_cognee) -> None:
    """A stage that declines says why, and "nothing was bridged" has to be
    readable off the result -- it is the difference between a memory that
    outlives its session and one that does not."""
    out = asyncio.run(C.bridge(["run:warm-0"], dataset="ds"))
    assert fake_cognee.improve_calls == [("ds", {"session_ids": ["run:warm-0"]})]
    assert out["stages"]["persist_agent_traces"]["counts"] == {"steps": 3}


def test_our_writes_do_not_fire_background_improves(fake_cognee) -> None:
    """`remember` defaults to `self_improvement=True`, which launches an
    improve in the background -- cognee's own `wait_for_background_tasks`
    docstring says so. Left on, it races the explicit bridge and what is in
    the graph when the next attempt reads becomes a question about timing."""
    import inspect

    src = inspect.getsource(C)
    assert src.count("self_improvement=False") >= 2, (
        "every remember() call site must opt out; the harness owns the "
        "bridge, at a point in the loop it controls")
    assert "wait_for_background_tasks" in src


# --- 4. the one write -------------------------------------------------


def test_the_only_write_is_the_graded_run(fake_cognee, monkeypatch) -> None:
    """`success_score` and `feedback` ARE the information.

    The harness used to write a prose document per attempt as well -- its own
    verdict, metrics and diff, filed into WORKED and DID-NOT-WORK node sets
    it invented. Over five pod attempts that became three near-identical
    "DID NOT WORK, same gutted file" documents saturating a 2,500-character
    block, one of them 1,139 characters of nothing because the attempt made
    no edits. It told warm louder and louder that it had failed and never
    what to do.

    Cognee's own loop is the channel: a SkillRunEntry with a low score
    drafts a skill-improvement proposal, `improve_skill` applies it, and the
    rewritten procedure is what a later attempt reads. `skill_improvement`
    must ride ON the entry -- sent alone it is rejected -- and
    `selected_skill_id` wants the skill's NAME, not its id.
    """
    entries = types.ModuleType("cognee.memory.entries")

    class SkillRunEntry:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    entries.SkillRunEntry = SkillRunEntry
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)
    monkeypatch.setattr(C, "current_procedure", _async_value("1. do it"))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))

    asyncio.run(C.record_attempt(
        attempt=1, fixture="x12sdk", tests_passed=0, tests_total=261,
        closeness=0.02, helped=False, summary="the suite is no better",
        error_signature="E   boom", dataset="ds", session_id="s"))

    assert len(fake_cognee.remembered) == 1, (
        "one write, not two: no document of ours goes in beside it")
    entry, kwargs = fake_cognee.remembered[0]
    assert isinstance(entry, SkillRunEntry)
    assert entry.selected_skill_id == C.SKILL_NAME
    assert entry.success_score == pytest.approx(0.02)
    assert entry.feedback == -1.0
    assert kwargs["skill_improvement"]["skill_name"] == C.SKILL_NAME
    assert kwargs["session_id"] == "s"
    assert kwargs["self_improvement"] is False
    assert not kwargs.get("node_set"), "no node sets of ours"


def test_feedback_keys_on_closeness_not_the_test_count(fake_cognee,
                                                       monkeypatch) -> None:
    """MEASURED ON THE POD, 2026-09-21, and it cost a round of a $4.59/hr run.

    Warm's first attempt went 0 -> 0 tests while taking closeness from the
    untouched checkout's 0.0 to +0.0092 -- its best result, and better than
    cold's -0.049. `feedback` went in as -1.0, so `improve_skill` was taught
    that warm's best work was its worst. `tests_passed` has two effective
    values on these fixtures; the score already knew that and the sign did
    not."""
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)
    monkeypatch.setattr(C, "current_procedure", _async_value("1. do it"))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))

    async def go(helped):
        return await C.record_attempt(
            attempt=1, fixture="x12sdk", tests_passed=0, tests_total=261,
            closeness=0.0092, helped=helped, summary="s", dataset="ds")

    asyncio.run(go(True))
    assert fake_cognee.remembered[-1][0].feedback == 1.0
    asyncio.run(go(False))
    assert fake_cognee.remembered[-1][0].feedback == -1.0


def test_no_distill_writes_nothing_at_all(fake_cognee, monkeypatch) -> None:
    """`--no-distill` freezes the procedure. With the document layer gone
    there is nothing else to write, so it is a true off switch."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. do it"))
    out = asyncio.run(C.record_attempt(
        attempt=1, fixture="x12sdk", tests_passed=1, tests_total=2,
        closeness=0.1, helped=True, summary="s", dataset="ds",
        improve_skill=False))
    assert out["applied"] is False
    assert fake_cognee.remembered == []


# --- 5. the read ----------------------------------------------------------


def test_the_brief_is_the_code_graph_and_one_recall(
        fake_cognee, monkeypatch) -> None:
    """Two blocks, neither of them this harness's opinion: the code graph as
    SearchType.CODE reports it, and ONE recall against the failure this
    attempt is working on. No WORKED/DID-NOT-WORK split and no documents of
    ours -- what comes back is whatever `improve`'s `distill_sessions` stage
    and the bridged traces put in the graph."""
    fake_cognee.graph = ["Replace the removed regex field constraint with "
                         "the supported pattern constraint."]
    monkeypatch.setattr(C, "code_brief", _async_value("13 module(s): v4010"))
    monkeypatch.setattr(C, "code_insights", _async_value(""))

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="hybrid",
                         code_dataset="ds-code", code_repo="x12sdk")
    brief = asyncio.run(mem.brief("E   PydanticUserError: regex is removed"))

    assert C.BRIEF_CODE in brief and C.BRIEF_MEMORY in brief
    assert "13 module(s): v4010" in brief
    assert "pattern constraint" in brief
    # Ranked against the failure, read as stored, deterministically.
    call = fake_cognee.recalls[-1]
    assert call["query"] == "E   PydanticUserError: regex is removed"
    assert call["datasets"] == ["ds"]
    assert call["only_context"] is True
    # SCOPED BY NODE SET, because `datasets` does not scope a recall.
    # MEASURED on a live pod run with no filter: warm was handed
    # `regex -> pattern`, where `BaseSettings` moved to and
    # `allow_mutation -> frozen` out of two scratch datasets from local
    # testing, and cleared 67 v1 surfaces on its first attempt because it
    # had been given the answer.
    assert call["node_name"] == [C.node_set("x12sdk")]


def test_the_brief_drops_the_warming_up_marker(fake_cognee) -> None:
    """A cold dataset answers recall with a `source="system"` marker, not an
    empty list. Rendered, it reads to the model as a memory that says
    "Memory is still warming up" -- which is worse than no block."""
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="hybrid")
    assert asyncio.run(mem.brief("anything")) == ""


def test_a_graph_that_cannot_be_read_costs_the_memory_not_the_attempt(
        fake_cognee, monkeypatch) -> None:
    """This read happens inside the attempt body."""
    async def boom(*a, **kw):
        raise RuntimeError("no route to Aura")

    monkeypatch.setattr(fake_cognee, "recall", boom)
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="hybrid")
    assert asyncio.run(mem.brief("anything")) == ""


def test_the_brief_is_empty_unless_the_mode_injects(fake_cognee) -> None:
    fake_cognee.graph = ["a distilled lesson"]
    for mode in ("mcp", "off"):
        mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode=mode)
        assert asyncio.run(mem.brief("q")) == ""
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="deterministic")
    assert "a distilled lesson" in asyncio.run(mem.brief("q"))


def test_the_brief_counts_what_it_handed_over(fake_cognee) -> None:
    """Counted here so the run can report warm's injected context without the
    attempt loop keeping a second tally that can disagree."""
    fake_cognee.graph = ["x" * 40]
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="hybrid")
    asyncio.run(mem.brief("q"))
    asyncio.run(mem.brief("q"))
    assert mem.reads == 2 and mem.chars > 80


def test_the_procedure_is_injected_only_when_the_mode_injects(
        monkeypatch) -> None:
    """`mcp` mode leaves the procedure in the graph and gives the agent
    `cognee_recall`. Injecting it anyway would make `mcp` and `hybrid` the
    same experiment under two names."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Do the thing."))
    assert asyncio.run(C.CogneeMemory(mode="hybrid").procedure()) == "1. Do the thing."
    assert asyncio.run(C.CogneeMemory(mode="deterministic").procedure()) == "1. Do the thing."
    assert asyncio.run(C.CogneeMemory(mode="mcp").procedure()) == ""
    assert asyncio.run(C.CogneeMemory(mode="off").procedure()) == ""


# --- 6. the code graph is Cognee's, not ours ------------------------------


def test_the_code_graph_comes_from_cognees_own_pipeline(
        fake_cognee, monkeypatch, tmp_path) -> None:
    """`get_code_graph_tasks` + `run_custom_pipeline`, per the code-graph
    guide: deterministic, no LLM, no embedding, no key. Anything this harness
    parsed out of the tree itself would be a second, worse code graph."""
    seen: dict = {}
    tasks = types.ModuleType("cognee.tasks.code_graph")

    def get_code_graph_tasks(path, **kw):
        seen.update(path=path)
        return [f"tasks-for:{path}"]

    tasks.get_code_graph_tasks = get_code_graph_tasks
    monkeypatch.setitem(sys.modules, "cognee.tasks.code_graph", tasks)
    monkeypatch.setattr(C, "code_graph_size", _async_value({"module": 7}))

    from pathlib import Path

    package = Path(tmp_path) / "fixture" / "x12sdk"
    (package / "sub").mkdir(parents=True)
    (package / "sub" / "models.py").write_text("x = 1\n")
    scratch = Path(tmp_path) / "scratch"

    out = asyncio.run(C.ingest_code_graph(package, dataset="ds-code",
                                          scratch=scratch))
    # ENOLA INDEXES A COPY. `snapshot_dir` on get_code_graph_tasks is an
    # INPUT -- pass it and enola never runs -- so the only way to keep
    # `<repo>/.enola/` out of the package the grader scores and the agents
    # edit is to index a different tree. One ingest in place put 2.3 MB of
    # facts.jsonl inside it, counted by `surfaces` and diffed by `closeness`.
    indexed = Path(seen["path"])
    assert indexed != package
    assert not str(indexed).startswith(str(package))
    # ...under the package's OWN name, because that is what enola stamps on
    # every fact as `repo`, and `repo` is what scopes the read.
    assert indexed.name == package.name
    assert (indexed / "sub" / "models.py").read_text() == "x = 1\n"
    call = fake_cognee.pipelines[-1]
    assert call["tasks"] == [f"tasks-for:{seen['path']}"]
    assert call["pipeline_name"] == "code_graph_pipeline"
    assert call["dataset"] == "ds-code"
    assert call["skip_connection_test"] is True, (
        "the pipeline is keyless; a connection test would demand an LLM key")
    assert out == {"module": 7}


def test_the_code_brief_is_reported_empty_rather_than_faked(
        fake_cognee, monkeypatch) -> None:
    monkeypatch.setattr(C, "_code_query", _async_value([]))
    assert asyncio.run(C.code_brief(dataset="ds-code", repo="x12sdk")) == ""


def test_the_code_brief_counts_classes_per_file_rather_than_listing_them(
        fake_cognee, monkeypatch) -> None:
    """MEASURED: x12sdk declares 238 classes and 200 of them are nested enums
    inside one file, so a list of 40 spent the whole block on `segments.py`.
    Per-file counts fit, and they are what says which files carry the work."""
    facts = [{"kind": "module", "name": "v5010",
              "properties": {"afferent": 9, "efferent": 2}}]
    facts += [{"kind": "symbol", "name": f"segments.Enum{i}",
               "file": "v4010/segments.py", "line": i,
               "properties": {"symbol_kind": "class"}} for i in range(200)]
    facts += [{"kind": "symbol", "name": "models.X12Segment",
               "file": "models.py", "line": 123,
               "properties": {"symbol_kind": "class", "data_class": True}}]

    async def code_query(dataset, query, *, repo=None):
        return facts

    monkeypatch.setattr(C, "_code_query", code_query)
    brief = asyncio.run(C.code_brief(dataset="ds-code", repo="x12sdk",
                                     package="x12sdk"))
    assert "Package under migration: x12sdk" in brief
    assert "201 class(es) across 2 file(s)" in brief
    # The file with a data class ranks above the file with 200 enums.
    assert brief.index("models.py:") < brief.index("v4010/segments.py:")
    assert "models.py: 1 class(es), 1 of them data classes" in brief
    assert "v5010 (imported by 9)" in brief
    assert len(brief) <= C.MAX_BLOCK_CHARS


def test_the_code_graph_is_scoped_to_one_repository(fake_cognee,
                                                    monkeypatch) -> None:
    """MEASURED 2026-09-21: `query_facts` over a fresh dataset returned five
    facts belonging to a repository ingested into a DIFFERENT dataset an hour
    earlier. SearchType.CODE is not dataset-scoped; facts carry `repo`, so
    that is the filter."""
    results = [{"operation": "query_facts", "facts": [
        {"kind": "module", "name": "mine", "repo": "x12sdk",
         "properties": {}},
        {"kind": "module", "name": "someone-elses", "repo": "oapi",
         "properties": {}},
    ]}]
    assert [f["name"] for f in C._scoped_to_repo(results, "facts", "x12sdk")] \
        == ["mine"]
    # Both shapes: the payload arrives bare or inside a `search_result`
    # envelope depending on the operation, and reading only one of the two is
    # how the brief came back empty while the pipeline reported completed.
    enveloped = [{"search_result": results[0]}]
    assert [f["name"] for f in C._scoped_to_repo(enveloped, "facts", "x12sdk")] \
        == ["mine"]


def test_code_insights_are_ranked_by_confidence(fake_cognee,
                                                monkeypatch) -> None:
    """enola's explainers: structural findings score 1.0, heuristics below."""
    async def search(**kwargs):
        return [{"operation": "insights", "insights": [
            {"name": "a heuristic", "repo": "x12sdk",
             "properties": {"confidence": 0.7}},
            {"name": "a cycle", "repo": "x12sdk",
             "properties": {"confidence": 1.0}},
            {"name": "another repo's", "repo": "oapi",
             "properties": {"confidence": 1.0}},
        ]}]

    monkeypatch.setattr(fake_cognee, "search", search)
    out = asyncio.run(C.code_insights(dataset="ds-code", repo="x12sdk"))
    assert out.splitlines() == ["  a cycle", "  a heuristic"]


# --- 7. the prompt --------------------------------------------------------


def test_colds_prompt_is_unchanged_by_any_of_this() -> None:
    """The arms have to differ in the treatment and nothing else."""
    cold = attempt_prompt("E   ImportError: BaseSettings", None)
    assert "Your procedure" not in cold
    assert "Your memory of this codebase" not in cold
    assert "cognee" not in cold.lower()
    assert cold.endswith("The test suite still fails:\n```\n"
                         "E   ImportError: BaseSettings\n```")


def test_warms_prompt_carries_the_procedure_and_the_brief() -> None:
    warm = attempt_prompt(
        "E   ImportError: BaseSettings", "pydantic-v2-migration",
        procedure="1. Move BaseSettings to pydantic_settings.",
        memory=f"### {C.BRIEF_MEMORY}\nReplace regex with pattern.",
        mcp_tools=True)
    assert "1. Move BaseSettings to pydantic_settings." in warm
    assert "Replace regex with pattern." in warm
    assert "cognee_recall" in warm
    # THE TASK COMES FIRST. It once came after a retrieved-memory block, and
    # warm-1 spent three attempts reporting on the memory instead of
    # migrating anything.
    assert warm.startswith("Please migrate this codebase")
    assert warm.rstrip().endswith("```")
    assert warm.index("Your procedure") < warm.index("The test suite still fails")


def test_the_prompt_says_where_the_two_halves_came_from() -> None:
    """A model handed two paragraphs with no provenance has to guess which
    to trust -- and the header must not promise content that is absent.

    It used to say "the WORKED section is verified progress; repeat it.
    The DID NOT WORK section is verified waste; do something else". Those
    were two node sets the harness wrote documents into, and they were
    removed when `success_score` and `feedback` became the signal. The
    sentence stayed. For four attempts of run 7 warm was told to find two
    sections that did not exist, above three lines of harness telemetry.

    The grader's own numbers do reach the prompt -- as the verdict block,
    which `test_the_verdict_states_the_graders_numbers_and_adds_nothing`
    pins. This block is the code graph and the attempt accounts, so this
    is what it may claim to be.
    """
    warm = attempt_prompt(None, None, memory="something a previous agent did")
    assert "what earlier attempts on this same checkout did to it" in warm
    assert "measured rather than claimed" in warm
    for absent in ("WORKED section", "DID NOT WORK section"):
        assert absent not in warm, (
            f"the header promises a {absent!r} that no longer exists")


# --- 8. the loop, end to end ----------------------------------------------


@dataclass
class _FakeWorkspace:
    """A Workspace that records the prompts it was given and edits one file
    per attempt, so `observed_fix` has a real diff to describe."""

    prompts: list[str] = field(default_factory=list)
    turns: int = 0
    edits: int = 0
    installed_skill_version: int | None = None

    async def run_vibe(self, task, *, timeout_s, resume, on_entry):
        self.prompts.append(task)
        self.turns += 1
        self.edits += 1
        return 0, '{"type": "message", "role": "assistant", "text": "done"}'

    def _source(self) -> str:
        if self.edits == 0:
            return "from pydantic import BaseModel, validator\n"
        return (f"from pydantic import BaseModel, field_validator\n"
                f"# attempt {self.edits}\n")

    def snapshot(self):
        return {"pkg/config.py": str(self.edits)}

    def collect_file_contents(self):
        return {"/repo/pkg/config.py": self._source().encode()}

    def assistant_turns_total(self):
        return self.turns

    def tool_calls_total(self):
        return Counter({"edit": 1})

    def steps_used(self):
        return 2

    def stream_entries(self, stdout):
        return []


class _FakePool:
    """The grader, scripted."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)

    async def run_pytest(self, *, file_contents, test_command):
        from orchestrator.sandbox import SandboxResult

        code, output = self.verdicts.pop(0) if self.verdicts else (0, "1 passed")
        return SandboxResult(exit_code=code, output=output, create_ms=1.0)


def _run_loop(mem, *, attempts=2, verdicts=None, baseline_v1=None):
    import time as _time

    ws = _FakeWorkspace()
    pool = _FakePool(verdicts or [
        (1, "E   ImportError: cannot import name 'BaseSettings'\n"
            "=== 2 passed, 8 failed in 1.0s ==="),
        (1, "E   PydanticUserError: `regex` is removed\n"
            "=== 6 passed, 4 failed in 1.0s ==="),
    ])
    events: list[tuple[str, dict]] = []

    async def emit(event_type, **kw):
        events.append((event_type, kw))

    result = asyncio.run(migrate_codebase(
        pool=pool, workspace=ws, test_command="pytest -q",
        deadline=_time.monotonic() + 600, emit=emit, mem=mem,
        session_id="run:warm-0" if mem is not None else None,
        agent_label="warm-0" if mem is not None else "cold-0",
        tests_total=10, baseline_v1=baseline_v1,
        budget=vibe_agent.AttemptBudget(attempts),
    ))
    return result, events, ws


def test_the_loop_reports_the_signal_it_sent(fake_cognee,
                                            monkeypatch) -> None:
    """One MEMORY_WRITE per attempt, carrying the score Cognee was given and
    whether it applied a rewrite. That event is the only place a run records
    what warm's memory was told, and a run where it is absent is warm running
    as cold with extra latency."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)
    fake_cognee.graph = ["a distilled lesson about field_validator"]

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    result, events, ws = _run_loop(mem)

    assert result.attempts == 2
    written = [kw for name, kw in events if name == "MEMORY_WRITE"]
    assert len(written) == 2
    assert all(w.get("score") is not None for w in written)
    # Attempt 2 was handed what the graph holds, under Cognee's own heading.
    assert C.BRIEF_MEMORY in ws.prompts[1]
    assert "a distilled lesson about field_validator" in ws.prompts[1]


def test_progress_is_judged_on_v1_surfaces_cleared(
        fake_cognee, monkeypatch) -> None:
    """MEASURED ON THE POD, 2026-09-21, and it cost a round of a $4.59/hr run.

    Warm's first attempt went 0 -> 0 tests while taking closeness from the
    untouched checkout's 0.0 to +0.0092 and leaving all 65 files parsing --
    its best result, and better than cold's -0.049. It was recorded as a
    failure, so `improve_skill` was taught that warm's best work was its
    worst. The score already keyed on closeness; the SIGN still keyed on
    `tests_passed`, which has two effective values on these fixtures."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)
    # 0 -> 0 tests, closeness FALLING, and one v1 surface cleared. All
    # three happened together on the pod: warm rewrote `class Config:
    # allow_mutation = False` as `model_config = ConfigDict(frozen=True,)`
    # -- correct -- and closeness fell because the right answer with
    # different whitespace is further from the reference text.
    monkeypatch.setattr(vibe_agent, "_closeness",
                        lambda contents, package: 0.0146)
    monkeypatch.setattr(vibe_agent.surfaces, "count",
                        lambda contents, within=None: 305)

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    _, events, _ = _run_loop(mem, attempts=1, baseline_v1=309, verdicts=[
        (1, "E   TypeError: field_validator() got an unexpected keyword "
            "argument 'allow_reuse'\n=== 261 failed in 1.0s ==="),
    ])
    written = [kw for name, kw in events if name == "MEMORY_WRITE"]
    assert written and written[0]["on"] == "progress", (
        "an attempt that cleared a v1 surface is verified progress, "
        "whatever the step function or the text similarity says")
    assert fake_cognee.remembered[-1][0].feedback == 1.0


def test_damage_is_recorded_as_damage_even_though_it_edited(
        fake_cognee, monkeypatch) -> None:
    """The other side of the same switch: cold's first pod attempt left a
    SyntaxError and scored -0.049. Below the untouched checkout is not
    progress."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)
    monkeypatch.setattr(vibe_agent, "_closeness",
                        lambda contents, package: -0.049)
    # Not one v1 surface cleared, and the tree no longer parses.
    monkeypatch.setattr(vibe_agent.surfaces, "count",
                        lambda contents, within=None: 383)

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    _, events, _ = _run_loop(mem, attempts=1, baseline_v1=383, verdicts=[
        (1, "E   SyntaxError: invalid syntax\n=== 261 failed in 1.0s ==="),
    ])
    written = [kw for name, kw in events if name == "MEMORY_WRITE"]
    assert written and written[0]["on"] == "no-progress"
    assert fake_cognee.remembered[-1][0].feedback == -1.0


def test_the_warm_loop_bridges_its_session_every_attempt(
        fake_cognee, monkeypatch) -> None:
    """Cognee's decorator writes the trace into SESSION memory, which is not
    graph-queryable. `improve` is the documented bridge; without it the
    traces are write-only and nothing but their own session ever sees them."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    _, events, _ = _run_loop(mem)

    assert len(fake_cognee.agent_memory_calls) == 2
    ingested = [kw for name, kw in events if name == "INGESTED"]
    assert [kw["source"] for kw in ingested] == ["cognee.improve"] * 2
    assert all(kw["steps"] == 3 for kw in ingested)
    done = [kw for name, kw in events if name == "ATTEMPT_DONE"]
    assert all(kw["procedure_chars"] > 0 for kw in done)


def test_the_cold_loop_touches_cognee_not_at_all(fake_cognee) -> None:
    """`mem=None` is not a gate, it is an absence: no decorator, no read, no
    trace, no document, no improve, nothing in the prompt."""
    result, events, ws = _run_loop(None)

    assert result.attempts == 2
    assert fake_cognee.agent_memory_calls == []
    assert fake_cognee.improve_calls == []
    assert fake_cognee.remembered == []
    assert not [name for name, _ in events
                if name in ("INGESTED", "MEMORY_READ", "MEMORY_WRITE")]
    assert all("Your procedure" not in p for p in ws.prompts)
    done = [kw for name, kw in events if name == "ATTEMPT_DONE"]
    assert all(kw["memory_chars"] == 0 for kw in done)


def test_a_memory_failure_before_the_attempt_does_not_cost_the_attempt(
        fake_cognee, monkeypatch) -> None:
    """Cognee resolves the agent user, the dataset scope and a connection
    BEFORE the wrapped body runs, and outside its own error handling. A graph
    unreachable at that moment must cost retrieval and a trace -- not the
    agent's work."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))

    def exploding_decorator(**kwargs):
        def decorate(fn):
            async def wrapper(*a, **kw):
                raise RuntimeError("no route to Aura")
            return wrapper
        return decorate

    monkeypatch.setattr(fake_cognee, "agent_memory", exploding_decorator)
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    result, events, ws = _run_loop(mem)

    assert result.attempts == 2
    assert len(ws.prompts) == 2, "the attempts ran without their memory"
    assert all("1. Move it." in p for p in ws.prompts)


def test_a_write_failure_after_the_verdict_keeps_the_attempt(
        fake_cognee, monkeypatch) -> None:
    """The attempt is graded and the tree is on disk. Losing the record of it
    must not lose the work -- but it must be loud, because a deterministic
    half that writes nothing leaves warm == cold with extra latency while
    every number in the summary looks healthy."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))

    async def boom(*a, **kw):
        raise RuntimeError("Aura went away")

    monkeypatch.setattr(C, "record_attempt", boom)
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    result, events, _ = _run_loop(mem)

    assert result.attempts == 2
    assert [kw["on"] for kw in
            (kw for name, kw in events if name == "MEMORY_WRITE")] == \
        ["failed", "failed"]


def test_off_is_a_real_off_switch(fake_cognee) -> None:
    """`off` makes warm == cold: no decorator, no trace, no bridge, no
    document. It exists to prove the harness."""
    mem = C.CogneeMemory(mode="off", session_id="run:warm-0")

    async def body(last_error=None):
        return "ran"

    assert mem.wrap_attempt(body) is body
    assert asyncio.run(mem.improve())["stages"] == {}
    assert asyncio.run(mem.record(attempt=1, helped=True, headline="h",
                                  evidence="d", tests_passed=1, tests_total=2,
                                  closeness=0.1, v1_remaining=0,
                                  error_signature=None)) == {}
    assert fake_cognee.agent_memory_calls == []
    assert fake_cognee.improve_calls == []
    assert fake_cognee.remembered == []


# --- 9. what the dataset does and does not isolate ------------------------


def test_forget_can_be_told_to_forget_everything(fake_cognee) -> None:
    """MEASURED 2026-09-21: a dataset-scoped Cognee recall returns other
    datasets' content. A marker added only to dataset A came back from a
    recall told to read only dataset B.

    Writes are scoped; reads are not, because every dataset lives in one
    Neo4j database. So `--reset-memory` on one dataset does not give a clean
    graph, and the only complete reset available on a single instance is this
    one -- which is why it has its own flag rather than being a default."""
    calls = []

    async def forget(**kw):
        calls.append(kw)
        return {}

    fake_cognee.forget = forget
    asyncio.run(C.forget_everything(dataset="msf-x12sdk"))
    asyncio.run(C.forget_everything(dataset="msf-x12sdk", everything=True))
    assert calls == [{"dataset": "msf-x12sdk"}, {"everything": True}]


def test_the_warmup_guard_is_turned_off(monkeypatch) -> None:
    """Skills ingestion writes skill nodes without logging a graph build, so
    recall's warm-up guard reads the dataset as empty and answers with a
    marker instead of the content (docs: Recall warm-up)."""
    import os

    for key in ("NEO4J_URI", "NEO4J_PASSWORD", "OPENAI_API_KEY"):
        monkeypatch.setenv(key, "x")
    monkeypatch.delenv("RECALL_WARMUP_SHORTCIRCUIT", raising=False)
    C.configure(dataset="ds")
    assert os.environ["RECALL_WARMUP_SHORTCIRCUIT"] == "false"


# --- 10. the skill is scored on the fuzzy measure, not the step function --


def test_the_score_is_closeness_not_the_test_count() -> None:
    """`tests_passed` is a step function on these fixtures: the package
    either imports or it does not. Measured on x12sdk 2026-09-21, warm
    attempt 3 scored 60 of 261 tests at closeness 0.0161 -- its LEAST
    reference-like tree -- while cold at 0 tests was at 0.0495. Scoring the
    skill on the suite taught it that the import fix was the win."""
    assert C.score_from_verdict(tests_passed=60, tests_total=261,
                                closeness=0.0161) == pytest.approx(0.0161)
    assert C.score_from_verdict(tests_passed=0, tests_total=261,
                                closeness=0.0495) == pytest.approx(0.0495)
    assert (C.score_from_verdict(tests_passed=0, tests_total=261, closeness=0.0495)
            > C.score_from_verdict(tests_passed=60, tests_total=261, closeness=0.0161))


def test_damage_scores_zero_not_negative() -> None:
    """closeness is SIGNED: -1.9748 was recorded when cold left a syntax
    error. Cognee requires [0,1], and "worse than not trying" has no reading
    below "no credit"."""
    assert C.score_from_verdict(tests_passed=0, tests_total=261,
                                closeness=-1.9748) == 0.0


def test_a_green_suite_is_a_one_however_it_got_there() -> None:
    """The suite is a bad gradient and a perfect terminator. Closeness cannot
    express "solved": two arms that both passed all 445 tests on oapi scored
    0.86 and 0.91, because it ranks resemblance to one implementation."""
    assert C.score_from_verdict(tests_passed=261, tests_total=261,
                                closeness=0.86) == 1.0


def test_without_an_answer_key_it_falls_back_and_says_so() -> None:
    assert C.score_from_verdict(tests_passed=130, tests_total=260,
                                closeness=None) == pytest.approx(0.5)
    assert "step function" in C.score_from_verdict.__doc__


def _async_value(value):
    async def f(*a, **kw):
        return value
    return f


# --- 9. the code read is paged ---------------------------------------------


def test_the_code_read_follows_every_page(monkeypatch) -> None:
    """`limit` is clamped to 500 SERVER-SIDE, without an error.

    code_retriever `_query_facts` ends
    `_bounded_int(self.config.get("limit"), field="limit", default=100,
    maximum=500)`, so a request for 20,000 returns one page of 500 and a
    `has_more: true` nobody read. Measured 2026-09-21: Aura held 2,247
    nodes for x12sdk -- the ingest had dropped nothing -- and one call
    returned exactly 500, of which 482 were x12sdk's and 18 belonged to
    two stale probe repos. The code brief was built from 9 of 54 files,
    and `v5010/segments.py`, holding 18 of the 42 v1 surfaces warm could
    not find in run 5, was not among them.
    """
    import asyncio
    import types

    from orchestrator import cognee_layer as C

    # A mixed graph, as the live one was: foreign-repo facts sit INSIDE the
    # page, not appended to it -- 500 returned, 482 of them x12sdk's.
    total = 1150
    facts = [{"kind": "symbol", "name": f"s{i}",
              "repo": "probe" if i % 100 == 7 else "x12sdk"}
             for i in range(total)]
    mine = [f for f in facts if f["repo"] == "x12sdk"]
    calls = []

    class Paged:
        SearchType = types.SimpleNamespace(CODE="CODE")

        async def search(self, **kwargs):
            q = kwargs["code_query"]
            offset = int(q.get("offset") or 0)
            # THE CLAMP, reproduced. Asking for more than 500 gets 500.
            limit = min(int(q.get("limit") or 100), 500)
            calls.append((offset, limit))
            page = facts[offset:offset + limit]
            return [{"operation": "query_facts", "facts": page,
                     "total": total, "offset": offset, "limit": limit,
                     "has_more": offset + len(page) < total}]

    monkeypatch.setitem(sys.modules, "cognee", Paged())
    got = asyncio.run(C._code_query("ds", {"operation": "query_facts"},
                                    repo="x12sdk"))

    assert len(got) == len(mine), f"one page only: {len(got)} of {len(mine)}"
    assert [f["name"] for f in got] == [f["name"] for f in mine]
    assert not any(f["repo"] != "x12sdk" for f in got)
    # Three pages, each asking for the server's own maximum, offsets
    # advancing by the page the server actually returned.
    assert calls == [(0, 500), (500, 500), (1000, 500)], calls


def test_a_code_read_with_a_limit_stops_at_it(monkeypatch) -> None:
    """`limit` still means what it says to a caller that passes one --
    `code_insights` wants the top few, not the whole graph."""
    import asyncio
    import types

    from orchestrator import cognee_layer as C

    facts = [{"kind": "symbol", "name": f"s{i}", "repo": "r"}
             for i in range(1200)]

    class Paged:
        SearchType = types.SimpleNamespace(CODE="CODE")

        async def search(self, **kwargs):
            q = kwargs["code_query"]
            offset = int(q.get("offset") or 0)
            page = facts[offset:offset + 500]
            return [{"facts": page, "total": len(facts), "offset": offset,
                     "has_more": offset + len(page) < len(facts)}]

    monkeypatch.setitem(sys.modules, "cognee", Paged())
    got = asyncio.run(C._code_query("ds", {"operation": "query_facts",
                                           "limit": 600}, repo="r"))
    assert len(got) == 600


# --- 10. what the trace actually stores -----------------------------------


def test_the_trace_carries_the_migration_not_the_exit_code() -> None:
    """The return value of the decorated body IS warm's memory.

    `agent_memory` stores it as the trace's `method_return_value`,
    `persist_session_trace_after=1` bridges that trace into the fixture's
    node set, and the node set is the only thing `recall` can read.

    It used to be `f"attempt {n}: vibe exited {code} after {turns}
    assistant turn(s)"`. Run 7 measured what that does: warm's fourth
    attempt was handed three lines reading "migrate_codebase.<locals>.
    _attempt_turn succeeded. Output: attempt 2: vibe exited 0 after 131
    assistant turn(s)" as its memory of the migration, with "succeeded"
    on three attempts that had all failed. Warm went 323 -> 259 -> 259 ->
    303 v1 surfaces; cold, with no memory, went 383 -> 48 -> 1.
    """
    from orchestrator.vibe_agent import _attempt_account

    before = {
        "x12sdk/v4010/segments.py": b"a: condecimal(gt=0)\nb: conint(ge=1)\n",
        "x12sdk/models.py": b"from pydantic.fields import ModelField\n",
        "x12sdk/parsing.py": b"x = m.schema()\n",
    }
    after = {
        # Converted, in the answer key's own form.
        "x12sdk/v4010/segments.py":
            b"a: Annotated[Decimal, Field(gt=0)]\nb: Annotated[int, Field(ge=1)]\n",
        # Untouched.
        "x12sdk/models.py": b"from pydantic.fields import ModelField\n",
        # Broken while being edited.
        "x12sdk/parsing.py": b"x = m.model_json_schema(\n",
    }
    account = _attempt_account(
        attempt=3, package_path="x12sdk", tree=after, prev_tree=before,
        prev_v1=4, prev_parse_ok=3,
        started_from="NameError: name 'conint' is not defined")

    # The failure it started from, so the entry is retrievable against a
    # later attempt hitting the same thing.
    assert "NameError: name 'conint' is not defined" in account
    # What changed, measured off the trees rather than reported by the
    # model. models.py was not touched, so it must not be listed as
    # changed -- though it does appear below as where a surface remains.
    changed = next(line for line in account.splitlines()
                   if line.startswith("Changed "))
    assert "x12sdk/v4010/segments.py" in changed and "parsing.py" in changed
    assert "models.py" not in changed, "unchanged file reported as work"
    # How the surfaces moved, in both directions.
    # 4 -> 2: the untouched models.py line matches both `pydantic.fields`
    # and `ModelField`, so it counts twice. The account reports the
    # measure as it is defined, not a tidier number.
    assert "v1 surfaces 4 -> 2." in account
    assert "Cleared: 2 x conint/constr/etc" in account
    assert "1 x schema()/schema_json()" in account
    # What is left, named.
    assert "Still left: 2 x pydantic.fields/ModelField" in account
    # And that the package is broken, which is the fact that decides what
    # the next attempt must do first.
    assert "2 of 3 source files parse (was 3) -- the package cannot be " \
           "imported." in account
    # None of the old telemetry.
    for telemetry in ("vibe exited", "assistant turn", "Task completed"):
        assert telemetry not in account, telemetry
    assert len(account) <= 950, len(account)


def test_the_account_reports_surfaces_it_put_back() -> None:
    """An attempt that undoes an earlier one is the failure mode warm hit
    on run 7 attempt 4, going 259 -> 303. Silence about that reads as no
    change."""
    from orchestrator.vibe_agent import _attempt_account

    before = {"x12sdk/a.py": b"x: Annotated[int, Field(ge=1)]\n"}
    after = {"x12sdk/a.py": b"x: conint(ge=1)\ny: conint(ge=2)\n"}
    account = _attempt_account(
        attempt=4, package_path="x12sdk", tree=after, prev_tree=before,
        prev_v1=0, prev_parse_ok=1, started_from=None)
    assert "REINTRODUCED: 2 x conint/constr/etc" in account
    assert "v1 surfaces 0 -> 2." in account


def test_the_first_attempt_reports_state_without_a_comparison() -> None:
    """Attempt 1 has no predecessor. It must still say where the tree is."""
    from orchestrator.vibe_agent import _attempt_account

    account = _attempt_account(
        attempt=1, package_path="x12sdk",
        tree={"x12sdk/a.py": b"@validator\ndef f(): pass\n"},
        prev_tree=None, prev_v1=None, prev_parse_ok=None, started_from=None)
    assert "v1 surfaces remaining: 1." in account
    # No comparison of any kind: no before-and-after arrow in the body, no
    # claim about what changed. (The title says "v1 -> v2", which is the
    # task, not a measurement.)
    assert "surfaces 1 ->" not in account
    assert "Cleared" not in account and "Changed" not in account


def test_attempt_one_claims_nothing_was_reintroduced() -> None:
    """`prev_v1` is seeded from the pristine tree; `prev_tree` is not.

    Comparing against an empty breakdown made every surface present on
    attempt 1 read as newly added. Run 8's warm was told "REINTRODUCED:
    253 x Field(const/regex/items), 42 x conint/constr/etc" about
    surfaces it had never touched -- a false statement in the one place
    the experiment claims is measured rather than claimed.
    """
    from orchestrator.vibe_agent import _attempt_account

    account = _attempt_account(
        attempt=1, package_path="x12sdk",
        tree={"x12sdk/a.py": b"x: conint(ge=1)\n@validator\n"},
        prev_tree=None, prev_v1=383, prev_parse_ok=None, started_from=None)
    assert "REINTRODUCED" not in account
    assert "Cleared" not in account
    assert "v1 surfaces remaining: 2." in account
