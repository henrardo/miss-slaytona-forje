"""Cognee as the memory layer, as shipped.

Every function here is a thin, named passthrough to a documented Cognee
call. If something in this file starts reshaping Cognee's output to fit
this harness, that is the bug -- it happened once already and is worth
recording:

    a first version of this module wrapped Cognee's `procedure` in YAML
    frontmatter, gave it a version counter, and reconciled two different
    hashes of it, so that a SKILL.md could be installed on the pod the
    way the AIP layer used to. All of that was scaffolding for a delivery
    mechanism Cognee does not use. Cognee keeps skills IN THE GRAPH and
    agents reach them through its MCP server.

WARM'S TREATMENT HAS TWO HALVES, and the second one was missing.

  VOLUNTARY -- the cognee MCP server. `cognee_recall`, `cognee_remember`,
  `cognee_search` are in warm's tool list and whether it calls them is
  the agent's decision, which is one of the things this experiment
  measures.

  DETERMINISTIC -- what the harness does with Cognee's own surfaces, on
  every attempt, whether the model asks or not:

      cognee.agent_memory(...)   wraps the attempt. Cognee retrieves
                                 before the call and persists a session
                                 trace (params, status, return, error)
                                 after it. Its `/guides/agent-session-
                                 traces` mechanism, not ours.
      recall(only_context=True)  the retrieved text, rendered into the
                                 attempt prompt.
      remember(SkillRunEntry)    the graded attempt, carrying OUR score.
      improve_skill(apply=True)  the rewritten procedure.
      cognee.improve(sessions)   bridges the session traces into the
                                 permanent graph so the NEXT attempt's
                                 recall can see them.

The first version of this migration shipped the voluntary half alone. On
a 119B model that is a bet that the model will choose to call a tool it
was never told it needs -- and the bet this project has already lost 40
runs in a row on. A deterministic integration does not depend on the
model's choice, which is what makes it usable by a small model; the MCP
tools stay because "did it go and read for itself" is a different and
also interesting question.

The cost of the deterministic half is a real arm difference and is
declared as one: it is prompt tokens warm reads and cold does not, it is
reported per attempt (ATTEMPT_DONE.memory_chars) and it can be switched
off with `--memory-mode mcp` to measure the voluntary half alone.

What this harness still owns, and must: THE SCORE. It comes from a real
test suite in a Daytona sandbox no agent has touched, and it is the only
reason any of this is measurement rather than self-report.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

# The dataset every skill, run and proposal for one fixture lives in.
# Cognee scopes by dataset, so this is also the isolation boundary between
# fixtures -- the job the `prov_fixture` trace property used to do, but
# structural rather than a stamp that can be forgotten on a write.
DEFAULT_DATASET = "msf"

SKILL_NAME = "pydantic-v2-migration"

# Where the starting procedure is read from, once, to seed Cognee. A file
# because it is the EXPERIMENT'S CONTROL: a scaffold stating the shape of
# the job and containing no migration knowledge, reviewed by a human.
# Seeding from anything else -- a previous run, another fixture -- is the
# contamination the whole design exists to rule out.
SEED_SKILL_PATH = (Path(__file__).resolve().parent.parent
                   / "skills" / SKILL_NAME / "SKILL.md")

# WHICH HALVES OF THE TREATMENT ARE LIVE. A flag rather than a constant
# because the two halves answer different questions and a run has to be
# able to ask one of them at a time.
#
#   hybrid         both. The default, and what a small model needs.
#   mcp            the tools only. Nothing is retrieved on the agent's
#                  behalf, so a retrieval in the transcript is the
#                  model's own -- this is the arm that measures whether
#                  it will go and look.
#   deterministic  the injected context and the traces only, no MCP
#                  server. Isolates the value of the memory from the
#                  agent's willingness to use a tool.
#   off            warm == cold. For proving the harness, not a result.
MEMORY_MODES = ("hybrid", "mcp", "deterministic", "off")


def uses_mcp(mode: str) -> bool:
    return mode in ("hybrid", "mcp")


def uses_injection(mode: str) -> bool:
    return mode in ("hybrid", "deterministic")


# What warm is told it has. Cognee's MCP server returns
# `instructions=None` -- measured -- so unlike the old layer there is
# nothing to relay and the tool descriptions are all the model gets.
#
# The tools are NAMED, because Vibe publishes an MCP tool as
# f"{server_alias}_{tool}" and a model told to "use your memory tools"
# has to guess at `cognee_recall`. Naming them is not coaching; it is the
# same fact the tool list already carries, stated where the model reads
# instructions. Deliberately no advice on WHEN to call them: a prompt
# that tells the agent how to use memory measures the prompt.
MEMORY_TOOLS_GUIDE = """\
A memory server is available to you as MCP tools: `cognee_recall` to
search what you or a previous attempt stored, `cognee_remember` to store
something, `cognee_search` to query the knowledge graph. Whether to use
them, and when, is your decision."""

# How much retrieved memory may be put in front of the model. A cap, not
# a target: warm's prompt already differs from cold's and every character
# here is a character of that difference, charged to warm's context
# window. 2,000 is ~500 tokens, which is small beside a 5-6k prompt and
# large enough for the three or four lessons a recall actually returns.
MAX_CONTEXT_CHARS = 2000


def configure(*, dataset: str = DEFAULT_DATASET) -> str:
    """Map this repo's env vars onto Cognee's, per the Graph Stores doc.

    Must run before the first `import cognee`: cognee reads its config
    from the environment at import time and runs relational migrations
    on first import.

    THE DEFAULTS THAT BITE, all found by running it:

      * `authentication=required, multi_tenant=enabled` out of the box.
        This is a single-operator harness; the permission system is not
        what is being measured.
      * vector and relational stores default to LOCAL LanceDB + SQLite.
        Only the GRAPH is remote, so "the memory is in Aura" is false.
      * session caching is on by default, and it must STAY on: the
        deterministic half reads session memory back before the graph
        has been distilled.
      * APOC must exist on the instance or every node lands as a generic
        `__Node__`. `assert_ready` checks rather than trusting it.
    """
    os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
    os.environ["GRAPH_DATABASE_URL"] = _require("NEO4J_URI")
    os.environ["GRAPH_DATABASE_NAME"] = os.environ.get("NEO4J_DATABASE", "neo4j")
    os.environ["GRAPH_DATABASE_USERNAME"] = os.environ.get("NEO4J_USERNAME", "neo4j")
    os.environ["GRAPH_DATABASE_PASSWORD"] = _require("NEO4J_PASSWORD")
    os.environ["LLM_API_KEY"] = _require("OPENAI_API_KEY")
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    return dataset


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Cognee needs it to reach the graph, and it "
            f"has no default on purpose: without it cognee falls back to its "
            f"embedded Kuzu store, the run's graph goes somewhere nobody is "
            f"looking, and every log line still says ok.")
    return value


async def assert_ready() -> dict[str, Any]:
    """Prove the graph is reachable AND typed before a run starts.

    The APOC check is the load-bearing one: without APOC cognee still
    writes -- it does not error -- so the failure mode is a run that
    looks fine and produces a graph with one label in it.
    """
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    rows = await engine.query(
        "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc.' "
        "RETURN count(*) AS n", {})
    apoc = rows[0]["n"] if rows else 0
    if not apoc:
        raise RuntimeError(
            "No APOC on this Neo4j instance. Cognee will still write, but "
            "every node lands as __Node__ and the typed model is lost.")
    counts = await engine.query("MATCH (n) RETURN count(n) AS n", {})
    return {"apoc_procedures": apoc, "nodes": counts[0]["n"] if counts else 0}


# ---- skills: docs.cognee.ai/examples/self-improving-skills -------------


async def seed_skill(text: str, *, name: str = SKILL_NAME,
                     dataset: str = DEFAULT_DATASET) -> None:
    """Put the starting procedure into Cognee."""
    import cognee

    # `self_improvement=False`: the harness owns the bridge, through
    # `improve_from_sessions`, at a point in the loop it controls. Left at
    # its default (True) every write also fires a background improve,
    # which races the explicit one and makes "what is in the graph when
    # the next attempt reads" a question about timing.
    await cognee.remember(text, dataset_name=dataset, content_type="skills",
                          skill_name=name, skills_text=text,
                          self_improvement=False)


async def dataset_id(name: str) -> str | None:
    """The UUID for a dataset name.

    `get_skill` takes a UUID and silently returns None for a name, so
    resolving this first is the difference between reading a procedure
    and concluding the skill does not exist.
    """
    import cognee

    for row in await cognee.datasets.list_datasets():
        got = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
        if got == name:
            rid = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
            return str(rid) if rid else None
    return None


async def find_skill(name: str = SKILL_NAME, *,
                     dataset: str = DEFAULT_DATASET) -> dict | None:
    """The skill row for `name` IN THIS DATASET.

    ALWAYS RESOLVE THE UUID FIRST. `list_skills(dataset="some-name")`
    does NOT scope to that dataset: measured, it returned two skills of
    the same name belonging to two different datasets. Taking the first
    row gives a foreign skill id, and `get_skill(foreign_id, this)`
    correctly answers None -- which reads as "the skill did not land".
    """
    from cognee.api.v1.skills.list_skills import list_skills

    did = await dataset_id(dataset)
    for skill in await list_skills(dataset=did or dataset):
        if skill.get("name") != name:
            continue
        if did and did not in (skill.get("dataset_scope") or [did]):
            continue
        return skill
    return None


async def current_procedure(name: str = SKILL_NAME, *,
                            dataset: str = DEFAULT_DATASET) -> str | None:
    """The procedure as Cognee currently holds it."""
    from cognee.api.v1.skills.list_skills import get_skill

    skill = await find_skill(name, dataset=dataset)
    did = await dataset_id(dataset)
    if skill is None or did is None:
        return None
    return (await get_skill(skill["id"], did) or {}).get("procedure")


async def ensure_seeded(*, dataset: str = DEFAULT_DATASET) -> str:
    """Seed from the scaffold if this dataset has no skill yet.

    Idempotent: an existing skill is returned as Cognee holds it,
    improvements and all. A second run against the same dataset must
    continue from the skill Cognee has rather than overwrite it with the
    scaffold -- that reset-every-run mistake threw away a night's work
    once already.
    """
    text = await current_procedure(dataset=dataset)
    if text:
        return text
    await seed_skill(SEED_SKILL_PATH.read_text(), dataset=dataset)
    return await current_procedure(dataset=dataset) or ""


def score_from_verdict(*, tests_passed: int, tests_total: int,
                       closeness: float | None = None) -> float:
    """Our grader's verdict, in the range Cognee requires.

    THE FUZZY MEASURE IS THE SCORE. `closeness` is 0.0 for an untouched
    checkout and 1.0 for the human's merged PR, normalised per file
    against the baseline and compared after `ast.unparse` so layout is
    not mistaken for divergence. It moves when an attempt migrates 12 of
    40 sites, which is what the skill needs to be taught by.

    WHY NOT `tests_passed`, which this used to be. On these fixtures it
    is a step function: the package either imports or it does not, so one
    correct edit takes it from 0 to hundreds while the migration itself
    is barely begun. Measured on x12sdk, 2026-09-21: warm's attempt 3
    scored 60 of 261 tests with a closeness of 0.0161 -- its LEAST
    reference-like tree of three -- while cold, at 0 tests, was at
    0.0495. Scoring on the suite taught the skill that the import fix was
    the win. The operator's words, twice: *"an agent with shit code but a
    good import goes from 0-300+. This is not a test."*

    THE NORMALISATION, stated because the previous version of this
    docstring used its absence as the reason not to do this:

      * closeness is SIGNED. An attempt that damages the tree scores
        below zero -- -1.9748 was recorded on this run when cold left a
        syntax error. Clamped to 0.0, which is the honest reading: worse
        than not trying, and there is nothing below "no credit".
      * a GREEN SUITE IS 1.0 regardless. The suite is a bad gradient and
        a perfect terminator: `tests_passed == tests_total` means solved,
        however unlike the reference the solution looks. Closeness itself
        cannot express this -- two arms that both passed all 445 tests on
        oapi scored 0.86 and 0.91, because it ranks resemblance to one
        implementation, never correctness.
      * NO ANSWER KEY, no closeness (`None`). Then the suite ratio is all
        there is, and it is used with the step-function caveat above --
        a fixture without a reference cannot be scored well.
    """
    if tests_total > 0 and tests_passed >= tests_total:
        return 1.0
    if closeness is None:
        if tests_total <= 0:
            return 0.0
        return max(0.0, min(1.0, tests_passed / tests_total))
    return max(0.0, min(1.0, float(closeness)))


async def record_run(*, score: float, task: str, summary: str,
                     skill: str = SKILL_NAME, error_message: str = "",
                     latency_ms: int = 0, propose: bool = True,
                     score_threshold: float = 0.5, max_runs: int = 5,
                     dataset: str = DEFAULT_DATASET,
                     session_id: str | None = None) -> tuple[Any, str | None]:
    """One graded attempt, as a SkillRun, plus a proposal if it was poor.

    `skill` IS THE SKILL'S NAME, NOT ITS ID, despite landing in a field
    called `selected_skill_id`: `resolve_skills` sends any `str` to
    `find_skill_by_name`, so passing the UUID `list_skills` just gave you
    raises "Skill '<uuid>' was not found or is not visible".

    `skill_improvement` has to RIDE ON this call -- a bare
    `remember("", skill_improvement=...)` is rejected outright.
    Recording the run and drafting the proposal are one operation by
    design, which is reasonable: the proposal is drawn from the runs.
    """
    import cognee
    from cognee.memory.entries import SkillRunEntry

    entry = SkillRunEntry(
        selected_skill_id=skill, task_text=task, result_summary=summary,
        success_score=score, error_message=error_message,
        latency_ms=latency_ms)
    improvement = ({"skill_name": skill, "score_threshold": score_threshold,
                    "max_runs": max_runs} if propose else None)
    result = await cognee.remember(entry, dataset_name=dataset,
                                   session_id=session_id,
                                   skill_improvement=improvement,
                                   # See seed_skill: the bridge is ours to
                                   # time, not a background task's.
                                   self_improvement=False)
    return result, proposal_id_of(result)


def proposal_id_of(result: Any) -> str | None:
    """The proposal id out of a remember() result, or None when no run
    scored below the threshold -- Cognee's way of saying there is
    nothing to learn from yet."""
    for item in (getattr(result, "items", None) or []):
        if isinstance(item, dict) and item.get("kind") == "skill_improvement_proposal":
            pid = item.get("proposal_id")
            return str(pid) if pid else None
    return None


async def apply_improvement(proposal_id: str, *, skill: str = SKILL_NAME,
                            dataset: str = DEFAULT_DATASET) -> Any:
    """Accept a drafted procedure. Rewrites it in the graph, in place.

    Calls `improve_skill` directly, as the docs' own example does. The
    remember() route cannot express apply on its own: `skill_improvement`
    must ride on a SkillRunEntry or a `content_type="skills"` ingest, and
    both would mean inventing a spurious run or re-ingesting the skill
    we are about to rewrite.
    """
    from cognee.modules.memify.skill_improvement import improve_skill

    return await improve_skill(skill, dataset=await _dataset_object(dataset),
                               proposal_id=proposal_id, apply=True)


async def _dataset_object(name: str):
    """The Dataset row. `improve_skill` needs `.id` and `.owner_id`."""
    from cognee.modules.pipelines.layers.resolve_authorized_user_datasets import (
        resolve_authorized_user_datasets)
    from cognee.modules.users.methods import get_default_user

    _, datasets = await resolve_authorized_user_datasets(
        name, await get_default_user())
    if not datasets:
        raise RuntimeError(f"no dataset {name!r}")
    return datasets[0]


async def distil_after_attempt(*, tests_passed: int, tests_total: int,
                               attempt: int, suite_passed: bool,
                               error: str | None,
                               closeness: float | None = None,
                               dataset: str = DEFAULT_DATASET,
                               session_id: str | None = None) -> dict:
    """Record the graded attempt; let Cognee rewrite the procedure.

    This is the whole of what `distill.py` did, and it is short because
    the prompting, the validation, the repair loop and the disclosure
    pass are Cognee's now. Nothing is written to disk: the procedure
    Cognee rewrote is the procedure the next attempt is handed and the
    procedure `recall` returns.
    """
    import time

    started = time.monotonic()
    score = score_from_verdict(tests_passed=tests_passed,
                               tests_total=tests_total,
                               closeness=closeness)
    # WHAT THE SKILL IS TOLD IT ACHIEVED. Closeness first, because that is
    # what the score is; the suite second, with its denominator, because
    # `tests_passed` alone is a step function and a proposal written
    # against "56/261 passing" learns to chase the import.
    summary = (f"closeness {closeness:.4f} to the reference migration"
               if closeness is not None else "closeness not measurable")
    summary += f"; {tests_passed}/{tests_total} tests passing"
    if suite_passed:
        summary += "; SUITE GREEN"
    _run, proposal_id = await record_run(
        score=score,
        task=f"attempt {attempt}: migrate the repository to Pydantic v2",
        summary=summary,
        error_message=(error or "")[:2000],
        dataset=dataset, session_id=session_id)

    if proposal_id:
        await apply_improvement(proposal_id, dataset=dataset)
    text = await current_procedure(dataset=dataset) or ""
    return {"score": score, "closeness": closeness, "proposal_id": proposal_id,
            "applied": bool(proposal_id), "procedure_chars": len(text),
            "seconds": time.monotonic() - started}


# ---- the deterministic half -------------------------------------------
#
# docs.cognee.ai/guides/agent-session-traces (the decorator) and
# /examples/agent-trace-lessons (improve's distillation stages).


def with_agent_memory(fn: Callable[..., Awaitable[Any]], *,
                      dataset: str = DEFAULT_DATASET,
                      session_id: str,
                      agent_session_name: str,
                      top_k: int = 5) -> Callable[..., Awaitable[Any]]:
    """Wrap one attempt in Cognee's own agent-memory decorator.

    THE CANONICAL INTEGRATION, and the reason there is no hand-rolled
    trace writing in this file any more. On each call Cognee:

      * retrieves memory for the query named by `query_param` (this
        attempt's previous error -- the thing that differs between
        attempts, and therefore the thing worth embedding), and leaves
        it on a contextvar the wrapped function reads with
        `memory_context()`;
      * persists a session trace afterwards carrying the function's
        parameters, its status, its return value and any error.

    `memory_only_context=True`: the retrieval must not spend an LLM call
    synthesising an answer. The attempt prompt wants the evidence, and a
    synthesised paragraph is a second model's opinion inserted into a
    measurement of the first.

    `save_session_traces=True` writes into SESSION memory, which is NOT
    graph-queryable until something distils it -- see
    `improve_from_sessions`, which is the other half of this and has to
    run or the traces are written and never read.

    APPLIED PER ATTEMPT, not at import: dataset and session are per run,
    and the decorator's config is fixed at decoration time.
    """
    import cognee

    return cognee.agent_memory(
        agent_session_name=agent_session_name,
        dataset_name=dataset,
        session_id=session_id,
        # WRITES, NOT READS. `with_memory=True` made the decorator retrieve
        # with `GRAPH_SUMMARY_COMPLETION`, which re-summarises the projected
        # subgraph with an LLM on every call. Measured 2026-09-21, three
        # calls against one unchanged graph:
        #
        #   291 / 329 / 239 characters, three different hashes, and the
        #   content was graph TOPOLOGY -- "The `None` node has three
        #   duplicate skill relationships to pydantic-v2-migration" --
        #   not a lesson.
        #
        # So warm's "memory" was a stochastic description of the graph's
        # shape, injected fresh each attempt. The distilled lessons that
        # `improve()` had correctly written were sitting unread. Reads are
        # now `lessons()`, which is stored text and byte-identical across
        # calls.
        with_memory=False,
        with_session_memory=True,
        save_session_traces=True,
        memory_top_k=top_k,
    )(fn)


def memory_context() -> str:
    """What the decorator retrieved for the call we are inside.

    Empty string when there is no decorator on the stack (every cold
    attempt) or when Cognee found nothing (every attempt 1). Both are
    normal and neither is an error.
    """
    try:
        from cognee.modules.agent_memory import get_current_agent_memory_context
    except Exception:
        return ""
    context = get_current_agent_memory_context()
    return getattr(context, "memory_context", "") or "" if context else ""


async def recall_context(query: str, *, dataset: str = DEFAULT_DATASET,
                         session_id: str | None = None,
                         scope: str | list[str] = "session_first",
                         top_k: int = 5,
                         limit: int = MAX_CONTEXT_CHARS) -> str:
    """Cognee's own retrieval, rendered as a block for the prompt.

    `only_context=True` reads without spending a completion, and
    `context_profile="agent"` is the profile Cognee's own trace-lesson
    example uses for exactly this: what an agent should know before it
    starts.

    `scope="session_first"` because of a measured Cognee behaviour worth
    stating plainly: a `remember(..., session_id=...)` lands in SESSION
    memory and is not graph-queryable until `improve` distils it, so a
    graph-only read straight after a write answers
    `status='memory_warming_up'` -- which reads as a lost write and is
    not one.
    """
    import cognee

    entries = await cognee.recall(
        query, datasets=[dataset], session_id=session_id, scope=scope,
        context_profile="agent", top_k=top_k, only_context=True)
    return render_recall(entries, limit=limit)


def render_recall(entries: Any, *, limit: int = MAX_CONTEXT_CHARS) -> str:
    """Recall's typed entries as plain text, truncated to `limit`.

    Defensive about shape on purpose: `recall` returns a union of eight
    response models discriminated on `source`, and which ones come back
    depends on what has been distilled. Anything without text we can
    read is skipped rather than str()'d -- a pydantic repr in the
    prompt is noise the model has to pay for and cannot use.
    """
    lines: list[str] = []
    for entry in (entries or []):
        text = ""
        for attribute in ("text", "content", "answer", "memory_context",
                          "method_return_value", "session_feedback"):
            value = (entry.get(attribute) if isinstance(entry, dict)
                     else getattr(entry, attribute, None))
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        if not text:
            continue
        if text not in lines:
            lines.append(text)
    block = "\n\n".join(lines).strip()
    if len(block) > limit:
        # Head, not tail: recall returns its best match first.
        block = block[:limit].rsplit("\n", 1)[0] + "\n[...]"
    return block


# The marker `distill_sessions` writes at the head of every lesson it
# produces. Matched on rather than guessed: read off a real lesson in
# Aura after the 2026-09-21 pod run.
LESSON_PREFIX = "# Session learning"


async def lessons(*, dataset: str = DEFAULT_DATASET,
                  limit: int = MAX_CONTEXT_CHARS) -> str:
    """The distilled session learnings for this fixture, as stored text.

    THE DETERMINISTIC READ, and the reason it is a Cypher query rather
    than a `search()`: every search path in Cognee that returns prose
    puts a model in the way. `GRAPH_SUMMARY_COMPLETION` re-summarises the
    subgraph per call (measured: three different answers to three
    identical calls), `RAG_COMPLETION` and the graph completions answer a
    question, and even `only_context=True` returns the framing rather
    than the text. What `improve()`'s `distill_sessions` stage writes is
    a DOCUMENT, and reading the document back is both exact and
    repeatable -- 697 characters, same sha256, three calls running.

    SCOPED BY THE SESSION ID, which carries the dataset name (see
    CogneeMemory.session_id). Cognee's graph search ignores the dataset
    it is given -- see the note above `forget_everything` -- so a filter
    on the lesson's own session marker is the only thing that actually
    keeps one fixture's lessons out of another's prompt.

    Ordered by session then text so the block is stable: an unordered
    read would reshuffle the prompt between attempts and make warm's
    context differ for no reason anyone could see.
    """
    from cognee.infrastructure.databases.graph import get_graph_engine

    # NEVER FATAL. This is read from inside the attempt body, which is not
    # wrapped in the loop's own guard -- so an unreachable graph, or a
    # store whose nodes have no `text` property, would cost the agent its
    # attempt rather than its memory. Loud, because warm running without
    # its lessons looks exactly like warm running with useless ones.
    try:
        engine = await get_graph_engine()
        rows = await engine.query(
            "MATCH (n) WHERE n.text STARTS WITH $prefix AND n.text CONTAINS $scope "
            "RETURN n.text AS text ORDER BY n.text",
            {"prefix": LESSON_PREFIX, "scope": f"(session {dataset}:"})
    except Exception as exc:
        print(f"  lessons() could not read the graph ({exc!r}); this "
              f"attempt runs without its distilled lessons")
        return ""
    seen: list[str] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if text and text not in seen:
            seen.append(text)
    block = "\n\n".join(seen)
    if len(block) > limit:
        block = block[:limit].rsplit("\n", 1)[0] + "\n[...]"
    return block


async def improve_from_sessions(session_ids: list[str], *,
                                dataset: str = DEFAULT_DATASET) -> dict:
    """Bridge this run's session traces into the permanent graph.

    Cognee's `improve` runs nine stages in a fixed order; the three that
    matter here need `session_ids` and are why this call exists at all:
    `persist_agent_traces` (the decorator's traces become graph nodes),
    `extract_agent_context` and `distill_sessions` (the trace-lesson
    distillation this project used to hand-write in `distill.py`).

    WITHOUT THIS, THE TRACES ARE WRITE-ONLY. The decorator stores them in
    session memory; `recall(scope="session_first")` finds them for the
    same session, and nothing else ever does. A second run, a second
    agent, or a graph query sees nothing.

    Returns a per-stage summary rather than the ImproveResult object, so
    the caller can print what ran without importing cognee's types. A
    stage that declines work reports `skipped` with a reason -- that is
    normal (several stages are opt-in) and is not a failure.
    """
    import cognee

    result = await cognee.improve(dataset, session_ids=session_ids)
    # DRAIN BEFORE ANYONE READS. `remember` defaults to
    # `self_improvement=True` and launches improvement in the background
    # -- cognee's own docstring for this function says so: "a background
    # remember that fires an improve". Without the wait, the next
    # attempt's read races writes from the last one, and which lessons
    # exist depends on timing. Bounded, and never fatal: a drain that
    # times out costs freshness, not the run.
    try:
        await cognee.wait_for_background_tasks(timeout=120.0)
    except Exception:
        pass
    stages = {}
    for stage in (getattr(result, "stages", None) or []):
        name = getattr(stage, "stage", None) or "?"
        stages[name] = {"status": getattr(stage, "status", None),
                        "reason": getattr(stage, "reason", None),
                        "counts": getattr(stage, "counts", None)}
    return {"status": getattr(result, "status", None)
                      or getattr(result, "finished", None),
            "stages": stages}


# ---- the repo under migration: docs.cognee.ai/guides/code-graph --------


async def add_code_graph(repo: Path, *,
                         dataset: str = "code_graph") -> Any:
    """Ingest a repo as a code graph, per `guides/code-graph`.

    A CUSTOM PIPELINE, not `remember`. The first version of this called
    `remember(str(repo), content_type="code")`, which is plausible and
    wrong -- written from the docs index's one-line description of a
    page I had not opened. The shipped path is
    `run_custom_pipeline(get_code_graph_tasks(...))`.

    Two properties of it worth knowing before using it here:

      * it needs the `enola` binary, which auto-installs to
        `~/.cognee/bin` on first run (`ENOLA_AUTO_INSTALL=false` to
        disable, `ENOLA_PATH` to point at your own);
      * it is ENTIRELY DETERMINISTIC and needs no API key. That makes it
        a different kind of thing from the rest of this module -- no
        model reads the repo, so nothing about the fixture leaks into an
        LLM, and a code graph costs nothing to rebuild.

    Its own dataset by default: the code graph is a map of the codebase,
    not a memory of attempts at it, and mixing them makes "what does
    warm know" unanswerable.
    """
    import cognee
    from cognee.tasks.code_graph import get_code_graph_tasks

    return await cognee.run_custom_pipeline(
        tasks=get_code_graph_tasks(str(repo)), data=str(repo),
        dataset=dataset, pipeline_name="code_graph_pipeline",
        skip_connection_test=True)


async def query_code_graph(operation: str = "query_facts", *,
                           dataset: str = "code_graph", **params) -> Any:
    """Ask the code graph a structured question.

    `SearchType.CODE` takes a `code_query` dict rather than a text
    query, and the operations are deterministic graph traversals, not
    similarity ranking: `query_facts`, `architecture`, `insights`,
    `explore`, `traverse`, `find_path`, `impact_analysis`.

    `impact_analysis` is the one to reach for on a migration -- "what
    breaks if this model changes" is the question the agent keeps
    getting wrong.
    """
    import cognee
    from cognee import SearchType

    return await cognee.search(
        query_type=SearchType.CODE, query_text="", datasets=[dataset],
        code_query={"operation": operation, **params})


# THE DATASET IS NOT AN ISOLATION BOUNDARY FOR GRAPH SEARCH. MEASURED.
#
# The rest of this module scopes everything by dataset, and the previous
# design note said that made fixture isolation structural -- the job
# `prov_fixture` used to do with a stamp on every trace, done instead by
# a name that cannot be forgotten on a write.
#
# It is not true of `SearchType.GRAPH_SUMMARY_COMPLETION`, which is the
# retrieval `cognee.agent_memory` performs. Reproduced on 2026-09-20,
# cognee 1.6.0 against Aura:
#
#     add("Zorblatt Quixnar <stamp> is the secret migration rule.") -> A
#     add("Unrelated filler text.")                                 -> B
#     cognify A; cognify B
#     search(..., datasets=[B], query="What is Zorblatt Quixnar?")
#       -> "Zorblatt Quixnar <stamp> contains the secret migration rule"
#
# Dataset B never saw the marker and returned it. Writes ARE scoped;
# graph reads are not, because every dataset lives in one Neo4j database
# and the traversal does not filter on the dataset the caller named.
#
# WHAT IT MEANS FOR A RUN. Warm on one fixture can retrieve a lesson
# distilled on another, which is exactly the contamination this project
# added `prov_fixture` to stop after a distiller learned from 25 traces
# belonging to a different codebase. It also means `--reset-memory`,
# which forgets one dataset, does not give a clean graph on an instance
# that has ever held another.
#
# WHAT TO DO ABOUT IT, in order of how much it actually buys:
#
#   * one Neo4j instance (or database) per fixture -- the only complete
#     answer, and not available on an Aura tier that gives one database;
#   * `forget_everything(everything=True)` before a series, which is what
#     `--reset-memory-everything` is for: a genuinely empty graph, at the
#     cost of every earlier experiment's memory;
#   * state it in the run's output and read every cross-fixture result
#     with it in mind. That is the minimum, and it is not optional.
#
# Not papered over here: a filter this module applied on the way out
# would look like isolation while the retrieval it wraps stayed unscoped.


async def forget_everything(*, dataset: str = DEFAULT_DATASET,
                            everything: bool = False) -> int:
    """Cognee's own `forget`, for `--reset-memory`.

    Scoped to the dataset by default. The old `reset_graph()` was
    `MATCH (n) DETACH DELETE n` -- every node for every fixture -- which
    is wider than the flag ever meant.

    `everything=True` is that wider thing, back, deliberately: graph
    search is not dataset-scoped (see above), so forgetting one dataset
    leaves a run able to retrieve another fixture's lessons. When a
    series needs a genuinely empty graph, this is the only way to get
    one on a single instance.
    """
    import cognee

    if everything:
        await cognee.forget(everything=True)
    else:
        await cognee.forget(dataset=dataset)
    return 0


async def datasets_in_graph() -> list[str]:
    """Every dataset name the graph holds, for the isolation warning.

    A run on a shared instance should say what else is in there, because
    graph retrieval can reach all of it -- see the note above.
    """
    import cognee

    names = []
    for row in await cognee.datasets.list_datasets():
        name = (row.get("name") if isinstance(row, dict)
                else getattr(row, "name", None))
        if name:
            names.append(str(name))
    return sorted(names)


@dataclass
class CogneeMemory:
    """One warm agent's handle on Cognee. Warm gets one; cold gets None.

    The attempt loop still branches on `mem is not None` to tell the
    arms apart, and this is what warm is handed.

    ITS METHODS ARE THE DETERMINISTIC HALF, and each one is a single
    documented Cognee call. Its predecessor under this name, `WarmMemory`,
    had none at all, on the argument that anything the harness writes on
    the agent's behalf is the harness measuring itself. That argument is
    right about WRITING THE AGENT'S MEMORY FOR IT -- the harness does not
    decide what the agent chose to remember, and `remember` stays the
    agent's own tool -- and wrong about the rest: retrieving before an
    attempt and recording a graded outcome are the integration Cognee
    ships, they do not depend on the model's choice, and without them
    warm is cold plus a tool list.

    Its predecessor before THAT, `ScopedMemory`, had thirteen methods and
    a hand-rolled trace model. The test is not "how many methods" but
    "is there a Cognee call underneath each one": if a method here ever
    starts reshaping, versioning or hashing what Cognee returned, that is
    the thing to stop.
    """

    dataset: str = DEFAULT_DATASET
    label: str = "warm-0"
    # PER RUN, PER AGENT, AND CARRYING THE DATASET. Once the constant
    # "warm-0", so 98 runs wrote into one session and anything that walked
    # it got slower every time until it stopped finishing at all.
    #
    # The dataset prefix is load-bearing for reads: Cognee's graph search
    # ignores the dataset it is given, so the session id embedded in each
    # distilled lesson is the only thing that keeps one fixture's lessons
    # out of another fixture's prompt. `lessons()` filters on it.
    session_id: str = "warm-0"
    mode: str = "hybrid"
    # Counted, printed, and carried into the event log: how much
    # retrieved text warm was handed and how often. "Warm read nothing"
    # and "warm read and it was empty" are different findings.
    reads: int = field(default=0, init=False)
    chars: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.mode not in MEMORY_MODES:
            raise ValueError(f"memory mode {self.mode!r} is not one of "
                             f"{MEMORY_MODES}")

    async def procedure(self) -> str:
        """The skill, as Cognee currently holds it, when the mode injects it.

        EMPTY UNDER `mcp`, and that is the whole point of that mode: the
        procedure is in the graph, the agent has `cognee_recall`, and
        whether it arrives in the prompt is then the model's decision
        rather than the harness's. Handing it over anyway would make
        `mcp` and `hybrid` the same experiment with different labels.

        Cognee keeps no lineage -- it rewrites `procedure` in place -- so
        this is read once per attempt. Reading it after the attempt would
        attribute the result to whatever distillation wrote next.
        """
        if not uses_injection(self.mode):
            return ""
        return await current_procedure(dataset=self.dataset) or ""

    def wrap_attempt(self, fn: Callable[..., Awaitable[Any]],
                     **kwargs) -> Callable[..., Awaitable[Any]]:
        """Cognee's decorator around one attempt.

        STILL WRAPPED UNDER `mcp`, deliberately. The retrieval it does is
        not injected in that mode, but the TRACE it writes is what fills
        the graph -- and an agent given `cognee_recall` over an empty
        graph is being measured on its willingness to read nothing.
        `off` is the only mode that skips it, because `off` means warm ==
        cold.
        """
        if self.mode == "off":
            return fn
        return with_agent_memory(
            fn, dataset=self.dataset, session_id=self.session_id,
            agent_session_name=f"msf:{self.label}", **kwargs)

    async def retrieved(self) -> str:
        """What this attempt is handed as memory: the distilled lessons.

        ASYNC AND DETERMINISTIC, and both are deliberate. It used to read
        the decorator's contextvar, which held an LLM re-summary of the
        graph produced fresh on every call -- so warm's treatment varied
        between two attempts with an identical graph, and the experiment
        could not attribute a difference to memory rather than to the
        summariser. `lessons()` returns stored text.
        """
        if not uses_injection(self.mode):
            return ""
        block = await lessons(dataset=self.dataset)
        if block:
            self.reads += 1
            self.chars += len(block)
        return block

    async def context(self, query: str) -> str:
        """An explicit recall, for when there is no decorator context.

        The decorator covers the attempt; this covers everything else --
        a preflight warm-up, a distillation turn, an operator asking the
        graph what it holds.
        """
        if not uses_injection(self.mode):
            return ""
        block = await recall_context(query, dataset=self.dataset,
                                     session_id=self.session_id)
        if block:
            self.reads += 1
            self.chars += len(block)
        return block

    async def improve(self) -> dict:
        """Distil this agent's session traces into the graph.

        Nothing to bridge under `off`: no decorator ran, so the session
        holds no traces and calling `improve` would spend round trips to
        be told so.
        """
        if self.mode == "off":
            return {"status": "skipped", "stages": {}}
        return await improve_from_sessions([self.session_id],
                                           dataset=self.dataset)


# The name the first pass of the Cognee migration used. Kept so a call
# site that has not been visited yet still constructs something that
# works, rather than failing at the one point in a pod run where the
# error costs the most.
WarmMemory = CogneeMemory
