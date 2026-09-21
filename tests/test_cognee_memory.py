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


def test_node_sets_carry_the_fixture_name() -> None:
    """MEASURED 2026-09-21: a recall told to read only `msf-probe` returned a
    sentinel written only to `msf-probe-other`. Datasets scope writes, not
    reads; NODE SETS scope reads. So the fixture name has to be in the node
    set or one codebase's lessons reach another's prompt."""
    worked, failed = C.node_sets("x12sdk")
    assert worked == "x12sdk-worked" and failed == "x12sdk-failed"
    assert C.node_sets("oapi") != C.node_sets("x12sdk")


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
        self.store: dict[str, list[str]] = {}

    def agent_memory(self, **kwargs):
        self.agent_memory_calls.append(kwargs)

        def decorate(fn):
            async def wrapper(*a, **kw):
                return await fn(*a, **kw)
            return wrapper
        return decorate

    async def remember(self, data, dataset_name=None, **kwargs):
        self.remembered.append((data, dict(kwargs, dataset_name=dataset_name)))
        for name in (kwargs.get("node_set") or []):
            self.store.setdefault(name, []).append(str(data))
        return types.SimpleNamespace(items=[], items_processed=1)

    async def recall(self, query, *, datasets=None, node_name=None,
                     query_type=None, only_context=False, top_k=15, **kw):
        out = []
        for name in (node_name or []):
            for text in self.store.get(name, []):
                out.append(types.SimpleNamespace(source="graph", text=text))
        # A cold node set answers with a warming-up marker, not [].
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
                        agent_session_name="msf:warm-0")
    kwargs = fake_cognee.agent_memory_calls[-1]
    assert kwargs["dataset_name"] == "ds"
    assert kwargs["session_id"] == "ds:run:warm-0"
    assert kwargs["save_session_traces"] is True


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
                        agent_session_name="msf:warm-0")
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
    assert src.count("self_improvement=False") >= 3, (
        "every remember() call site must opt out; the harness owns the "
        "bridge, at a point in the loop it controls")
    assert "wait_for_background_tasks" in src


# --- 4. the outcome document ----------------------------------------------


def test_the_outcome_document_carries_the_verdict_and_the_diff() -> None:
    """The one write that makes the next attempt better than a cold one.

    Before this existed the graph held "attempt 3: vibe exited 0 after 12
    assistant turn(s)" and nothing else about the attempt, so nothing
    downstream -- distillation, recall, the skill rewrite -- had anything
    about Pydantic to work from."""
    doc = C.outcome_document(
        fixture="x12sdk", attempt=2, agent="warm-0", helped=True,
        headline="More of the suite passes than before this attempt.",
        evidence="--- a/x12sdk/models.py\n+++ b/x12sdk/models.py\n"
                 "-    @validator('npi')\n+    @field_validator('npi')",
        tests_passed=60, tests_total=261, closeness=0.0401, v1_remaining=295,
        error_signature="E   PydanticUserError: `regex` is removed")
    assert doc.startswith("WORKED")
    assert "x12sdk attempt 2 by warm-0" in doc
    assert "60/261 tests passing" in doc
    assert "295 pydantic v1 surfaces left" in doc
    assert "closeness to the reference migration 0.0401" in doc
    assert "E   PydanticUserError: `regex` is removed" in doc
    assert "+    @field_validator('npi')" in doc, "the diff IS the content"


def test_a_failed_attempt_says_so_in_its_first_line() -> None:
    """The first line is what ranks in retrieval and what a reader skims."""
    doc = C.outcome_document(
        fixture="x12sdk", attempt=3, agent="warm-0", helped=False,
        headline="The suite is no better than before this attempt.",
        evidence="-import pydantic\n+import pydantic.v1 as pydantic",
        tests_passed=0, tests_total=261, closeness=-1.97, v1_remaining=300,
        error_signature="E   IndentationError",
        rejected_because="MIGRATION NOT COMPLETE: pydantic.v1 shim")
    assert doc.startswith("DID NOT WORK")
    assert "MIGRATION NOT COMPLETE" in doc


def test_the_document_is_bounded() -> None:
    """A 3,000-line diff in the graph is a chunk boundary problem, not a
    lesson."""
    doc = C.outcome_document(
        fixture="x12sdk", attempt=1, agent="warm-0", helped=True,
        headline="h", evidence="x" * 100_000, tests_passed=1, tests_total=2,
        closeness=0.5, v1_remaining=1, error_signature=None, max_chars=3000)
    assert len(doc) <= 3000


def test_record_attempt_files_it_under_the_verdict_the_grader_gave(
        fake_cognee, monkeypatch) -> None:
    """`helped` decides the node set, and the node set is what lets the next
    prompt say "repeat this" over one block and "do not" over the other."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. do it"))

    async def go(helped):
        return await C.record_attempt(
            fixture="x12sdk", attempt=1, agent="warm-0", helped=helped,
            headline="h", evidence="d", tests_passed=1, tests_total=2,
            closeness=0.1, v1_remaining=3, error_signature="E   boom",
            dataset="ds", session_id="s", improve_skill=False)

    out = asyncio.run(go(True))
    assert out["node_set"] == "x12sdk-worked"
    out = asyncio.run(go(False))
    assert out["node_set"] == "x12sdk-failed"
    assert set(fake_cognee.store) == {"x12sdk-worked", "x12sdk-failed"}
    assert all(kw["dataset_name"] == "ds"
               for _, kw in fake_cognee.remembered)


def test_the_graded_run_also_goes_in_as_a_skill_run(fake_cognee,
                                                    monkeypatch) -> None:
    """Cognee's own self-improving-skill loop: a SkillRunEntry with a low
    score drafts a proposal, and applying it rewrites the procedure in
    place. `skill_improvement` must ride ON the entry -- sent alone it is
    rejected -- and `selected_skill_id` wants the skill's NAME, not its id.
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
        fixture="x12sdk", attempt=1, agent="warm-0", helped=False,
        headline="h", evidence="d", tests_passed=0, tests_total=261,
        closeness=0.02, v1_remaining=300, error_signature="E   boom",
        dataset="ds", session_id="s"))

    entry, kwargs = fake_cognee.remembered[-1]
    assert isinstance(entry, SkillRunEntry)
    assert entry.selected_skill_id == C.SKILL_NAME
    assert entry.success_score == pytest.approx(0.02)
    assert entry.feedback == -1.0, "a failed attempt is negative feedback"
    assert kwargs["skill_improvement"]["skill_name"] == C.SKILL_NAME
    assert kwargs["session_id"] == "s"
    # The outcome document itself is the result summary, so the proposal is
    # drafted against what actually happened rather than against a count.
    assert "DID NOT WORK" in entry.result_summary


def test_no_distill_keeps_the_outcome_memory(fake_cognee, monkeypatch) -> None:
    """`--no-distill` freezes the PROCEDURE. It used to freeze the memory
    too, which made "hold the skill constant" and "turn memory off" the same
    flag."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. do it"))
    out = asyncio.run(C.record_attempt(
        fixture="x12sdk", attempt=1, agent="warm-0", helped=True,
        headline="h", evidence="d", tests_passed=1, tests_total=2,
        closeness=0.1, v1_remaining=3, error_signature=None,
        dataset="ds", improve_skill=False))
    assert out["applied"] is False
    assert fake_cognee.store["x12sdk-worked"], "the document was still written"
    assert not any(kw.get("skill_improvement")
                   for _, kw in fake_cognee.remembered)


# --- 5. the read ----------------------------------------------------------


def test_the_brief_labels_the_two_halves_and_scopes_each_to_its_node_set(
        fake_cognee) -> None:
    """The labels are the treatment. `distill_sessions` writes lessons and
    `recall` ranks documents, but neither tells a model which of two
    retrieved paragraphs is the one to copy and which is the one to avoid.
    The node set does, because the grader decided it."""
    fake_cognee.store["x12sdk-worked"] = ["WORKED: field_validator landed."]
    fake_cognee.store["x12sdk-failed"] = ["DID NOT WORK: the v1 shim."]
    fake_cognee.store["oapi-worked"] = ["WORKED: a DIFFERENT codebase."]

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="hybrid")
    brief = asyncio.run(mem.brief("E   PydanticUserError"))

    assert C.BRIEF_WORKED in brief and C.BRIEF_FAILED in brief
    assert "field_validator landed" in brief
    assert "the v1 shim" in brief
    assert "Do not repeat these." in brief
    assert brief.index(C.BRIEF_WORKED) < brief.index(C.BRIEF_FAILED)
    assert "a DIFFERENT codebase" not in brief, (
        "another fixture's node set must not reach this prompt")


def test_the_brief_drops_the_warming_up_marker(fake_cognee) -> None:
    """A cold node set answers recall with a `source="system"` marker, not an
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
    fake_cognee.store["x12sdk-worked"] = ["WORKED: something."]
    for mode in ("mcp", "off"):
        mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode=mode)
        assert asyncio.run(mem.brief("q")) == ""
    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", mode="deterministic")
    assert "WORKED: something." in asyncio.run(mem.brief("q"))


def test_the_brief_counts_what_it_handed_over(fake_cognee) -> None:
    """Counted here so the run can report warm's injected context without the
    attempt loop keeping a second tally that can disagree."""
    fake_cognee.store["x12sdk-worked"] = ["x" * 40]
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
        memory=f"### {C.BRIEF_WORKED}\nWORKED: field_validator landed.\n\n"
               f"### {C.BRIEF_FAILED}\nDID NOT WORK: the v1 shim.",
        mcp_tools=True)
    assert "1. Move BaseSettings to pydantic_settings." in warm
    assert "WORKED: field_validator landed." in warm
    assert "DID NOT WORK: the v1 shim." in warm
    assert "cognee_recall" in warm
    # THE TASK COMES FIRST. It once came after a retrieved-memory block, and
    # warm-1 spent three attempts reporting on the memory instead of
    # migrating anything.
    assert warm.startswith("Please migrate this codebase")
    assert warm.rstrip().endswith("```")
    assert warm.index("Your procedure") < warm.index("The test suite still fails")


def test_the_prompt_says_where_the_two_halves_came_from() -> None:
    """A model handed two contradictory paragraphs with no provenance has to
    guess which to trust. The grader ran the real suite; say so."""
    warm = attempt_prompt(None, None, memory="something a previous agent did")
    assert "independent grader" in warm
    assert "WORKED section is verified progress" in warm
    assert "DID NOT WORK section is verified waste" in warm


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


def _run_loop(mem, *, attempts=2, verdicts=None):
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
        tests_total=10,
        budget=vibe_agent.AttemptBudget(attempts),
    ))
    return result, events, ws


def test_attempt_two_reads_back_what_attempt_one_wrote(
        fake_cognee, monkeypatch) -> None:
    """THE PROPERTY THE WHOLE PROJECT TURNS ON, at harness level: whatever
    the grader concluded about attempt 1 is in attempt 2's prompt, under the
    heading that says whether to repeat it.

    Not a claim about the model. A claim that the loop closes -- which it did
    not, for the whole first pass of the Cognee migration."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    result, events, ws = _run_loop(mem)

    assert result.attempts == 2
    # Attempt 1 knew nothing; attempt 2 was handed attempt 1's verdict.
    assert "Your memory of this codebase" not in ws.prompts[0]
    assert "Your memory of this codebase" in ws.prompts[1]
    # Attempt 1 moved the suite 2 -> 6 passing, so the grader filed it under
    # WORKED, and attempt 2's prompt says to repeat it.
    written = [kw for name, kw in events if name == "MEMORY_WRITE"]
    assert [w["node_set"] for w in written[:1]] == ["x12sdk-worked"]
    assert C.BRIEF_WORKED in ws.prompts[1]
    # ...and what it repeats is the diff the harness took itself.
    assert "field_validator" in ws.prompts[1]
    # The error the suite reached is in there too, which is what the recall
    # was ranked against.
    assert "PydanticUserError" in ws.prompts[1] or "ImportError" in ws.prompts[1]


def test_a_regression_is_filed_under_failed(fake_cognee, monkeypatch) -> None:
    """An attempt that leaves the suite no better is verified waste, and the
    next attempt is told not to repeat it. This is the half that cannot come
    from the agent: it requires two independent test runs."""
    monkeypatch.setattr(C, "current_procedure", _async_value("1. Move it."))
    monkeypatch.setattr(C, "_apply_improvement", _async_value(None))
    entries = types.ModuleType("cognee.memory.entries")
    entries.SkillRunEntry = lambda **kw: types.SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules, "cognee.memory.entries", entries)

    mem = C.CogneeMemory(dataset="ds", fixture="x12sdk", label="warm-0",
                         session_id="run:warm-0", mode="hybrid")
    # No test ever passes, and the first failure never changes: the tree
    # moved and the suite did not.
    _, events, ws = _run_loop(mem, verdicts=[
        (1, "E   ImportError: BaseSettings\n=== 10 failed in 1.0s ==="),
        (1, "E   ImportError: BaseSettings\n=== 10 failed in 1.0s ==="),
    ])
    written = [kw for name, kw in events if name == "MEMORY_WRITE"]
    assert written and written[0]["node_set"] == "x12sdk-failed"
    assert C.BRIEF_FAILED in ws.prompts[1]
    assert "Do not repeat these." in ws.prompts[1]


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
    assert done[-1]["memory_chars"] > 0


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
