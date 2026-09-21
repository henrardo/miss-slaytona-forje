"""Cognee as the memory layer. One Cognee call per function, no shadow store.

What a warm agent gets and a cold agent does not:

    the code graph      the fixture ingested by `get_code_graph_tasks`, read
                        back with SearchType.CODE. Deterministic, keyless.
    the outcome memory  one document per graded attempt, written into the
                        `<fixture>-worked` or `<fixture>-failed` node set and
                        read back with recall(CHUNKS, only_context=True).
    the procedure        a Cognee skill that `improve_skill` rewrites from the
                        grader's score after every attempt.
    the session trace    `agent_memory(save_session_traces=True)` writes it,
                        `improve(session_ids=...)` bridges and distils it.
    the MCP server       `cognee_recall` / `_remember` / `_search`, which the
                        agent may call or not. That choice is a measurement.

Measured against cognee 1.6.0, and the reason the reads are shaped this way:

  * recall IGNORES the dataset for reads -- a marker written to dataset A came
    back from a recall told to read only dataset B. NODE SETS do scope, so the
    node set carries the fixture name and is the isolation boundary.
  * SearchType.CHUNKS with only_context=True returns the stored text, byte
    identical across repeat calls. GRAPH_SUMMARY_COMPLETION (what the decorator
    uses when with_memory=True) re-summarises the subgraph per call: three
    calls over one unchanged graph gave 291/329/239 characters describing graph
    topology rather than a lesson. So the decorator writes and does not read.
  * `remember` defaults to self_improvement=True, which fires a background
    improve that races the explicit one. Off everywhere here.
  * a cold dataset answers recall with a `source="system"` warming-up marker,
    not an empty list. Markers are dropped, not rendered.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

DEFAULT_DATASET = "msf"
SKILL_NAME = "pydantic-v2-migration"
SEED_SKILL_PATH = (Path(__file__).resolve().parent.parent
                   / "skills" / SKILL_NAME / "SKILL.md")

# hybrid = both halves; mcp = the agent's own tools only; deterministic =
# injection only; off = warm == cold, for proving the harness.
MEMORY_MODES = ("hybrid", "mcp", "deterministic", "off")

# Cap per block. The last uncapped retrieved-memory block this harness put in a
# prompt reached 15,170 characters and warm spent three attempts reporting on it
# instead of migrating anything.
MAX_BLOCK_CHARS = 2500

MEMORY_TOOLS_GUIDE = """\
A memory server is available to you as MCP tools: `cognee_recall` to
search what you or a previous attempt stored, `cognee_remember` to store
something, `cognee_search` to query the knowledge graph. Whether to use
them, and when, is your decision."""


def uses_mcp(mode: str) -> bool:
    return mode in ("hybrid", "mcp")


def uses_injection(mode: str) -> bool:
    return mode in ("hybrid", "deterministic")


def configure(*, dataset: str = DEFAULT_DATASET) -> str:
    """Map this repo's env onto Cognee's. MUST run before `import cognee`.

    Without GRAPH_DATABASE_*, cognee falls back to its embedded Kuzu store and
    the run's graph goes somewhere nobody is looking while every log says ok.
    Vector and relational stay local (LanceDB + SQLite); only the graph is
    remote, which is why every cognee process that has to see these writes --
    the MCP server, the REST API the hooks call -- runs on this machine.
    """
    os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
    os.environ["GRAPH_DATABASE_URL"] = _require("NEO4J_URI")
    os.environ["GRAPH_DATABASE_NAME"] = os.environ.get("NEO4J_DATABASE", "neo4j")
    os.environ["GRAPH_DATABASE_USERNAME"] = os.environ.get("NEO4J_USERNAME", "neo4j")
    os.environ["GRAPH_DATABASE_PASSWORD"] = _require("NEO4J_PASSWORD")
    os.environ["LLM_API_KEY"] = _require("OPENAI_API_KEY")
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    # Skills ingestion writes skill nodes without logging a graph build, so
    # recall's warm-up guard reads the dataset as empty and answers with a
    # marker instead of the content (docs: Recall warm-up).
    os.environ.setdefault("RECALL_WARMUP_SHORTCIRCUIT", "false")
    return dataset


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set; cognee would silently use Kuzu")
    return value


async def assert_ready() -> dict[str, Any]:
    """Reachable AND typed. Without APOC cognee still writes -- it does not
    error -- and every node lands as `__Node__`."""
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    rows = await engine.query(
        "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc.' "
        "RETURN count(*) AS n", {})
    apoc = rows[0]["n"] if rows else 0
    if not apoc:
        raise RuntimeError("no APOC on this instance; every node would be __Node__")
    counts = await engine.query("MATCH (n) RETURN count(n) AS n", {})
    return {"apoc_procedures": apoc, "nodes": counts[0]["n"] if counts else 0}


def node_sets(fixture: str) -> tuple[str, str]:
    """The two node sets one fixture's attempts write into. Node sets are the
    read-scoping boundary, so the fixture name has to be in them."""
    return f"{fixture}-worked", f"{fixture}-failed"


# ---- the code graph --------------------------------------------------


async def ingest_code_graph(repo: Path, *, dataset: str,
                            scratch: Path | None = None) -> dict[str, Any]:
    """The fixture as a code graph (guides/code-graph).

    A custom pipeline, not `remember(content_type="code")`: deterministic, no
    LLM or embedding call, and it needs the `enola` binary, which auto-installs
    to ~/.cognee/bin on first run. Measured 1.6s on a three-file tree and 15s
    on x12sdk.

    INGESTED FROM A COPY, and that is not tidiness. enola writes its snapshot
    to `<repo>/.enola/`, full stop: `snapshot_dir` on `get_code_graph_tasks`
    is an INPUT -- pass it and enola is not run at all, the task just parses
    what is already there. Pointing it at an empty scratch directory fails
    with `No facts.jsonl found`. So the only way to keep the snapshot out of
    the tree is to ingest a different tree.

    Left in place, one ingest put 2.3 MB of `facts.jsonl`, `insights.json`
    and an extractor cache INSIDE the package the grader scores and the agents
    edit -- counted by `surfaces`, diffed by `closeness`, tarred to the pod
    and uploaded to Daytona on every attempt.

    The copy keeps the package's own directory name, because that name is
    what enola stamps on every fact as `repo` and what scopes the read.

    Returns the per-kind fact counts for the repo just ingested, so "the
    pipeline said completed and the graph holds nothing" is visible at the
    call site rather than two attempts later as an empty prompt block.
    """
    import shutil

    import cognee
    from cognee.tasks.code_graph import get_code_graph_tasks

    repo = Path(repo)
    root = Path(scratch or default_scratch(dataset))
    copy = root / repo.name
    if copy.exists():
        shutil.rmtree(copy)
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo, copy,
                    ignore=shutil.ignore_patterns("__pycache__", ".*"))
    await cognee.run_custom_pipeline(
        tasks=get_code_graph_tasks(str(copy)), data=str(copy),
        dataset=dataset, pipeline_name="code_graph_pipeline",
        skip_connection_test=True)
    return await code_graph_size(dataset=dataset, repo=copy.name)


def default_scratch(dataset: str) -> Path:
    """Where the copy enola indexes lives: never inside the repository."""
    import tempfile

    return Path(tempfile.gettempdir()) / "msf-code-graph" / dataset


async def code_graph_size(*, dataset: str, repo: str) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    for fact in await _code_query(dataset, {"operation": "query_facts",
                                            "limit": 20000}, repo=repo):
        kind = fact.get("kind", "?")
        kinds[kind] = kinds.get(kind, 0) + 1
    return kinds


async def _code_query(dataset: str, code_query: dict, *,
                      repo: str | None = None) -> list[dict]:
    """One SearchType.CODE operation, unwrapped and scoped to one repository.

    MEASURED 2026-09-21, and both halves cost a run's worth of empty prompt
    block:

      * the result is the operation payload itself -- `{"operation": ...,
        "facts": [...]}` -- not the `{dataset_id, dataset_name,
        search_result}` envelope the search docs describe. Reading
        `search_result` returned None for every entry and the code brief came
        back empty while the pipeline reported completed.
      * the operation is NOT dataset-scoped: `query_facts` over a fresh
        dataset returned five facts belonging to a repository ingested into a
        different one an hour earlier. Facts carry `repo`, so that is the
        filter -- same lesson as node sets on the document side.
    """
    import cognee
    from cognee import SearchType

    results = await cognee.search(
        query_type=SearchType.CODE, query_text="", datasets=[dataset],
        code_query=code_query)
    return _scoped_to_repo(results, "facts", repo)


def _scoped_to_repo(results: Any, key: str, repo: str | None) -> list[dict]:
    """The items under `key` in a SearchType.CODE payload, for one repo only.

    The payload arrives either bare or inside a `search_result` envelope
    depending on the operation; reading only one of the two shapes is how the
    code brief came back empty while the pipeline reported completed.
    """
    out: list[dict] = []
    for entry in results or []:
        payload = entry
        if isinstance(entry, dict) and "search_result" in entry:
            payload = entry["search_result"]
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        if not isinstance(payload, dict):
            continue
        for item in (payload.get(key) or []):
            if repo is None or item.get("repo") == repo:
                out.append(item)
    return out


async def code_brief(*, dataset: str, repo: str, package: str | None = None,
                     limit: int = MAX_BLOCK_CHARS) -> str:
    """What the code graph knows about this codebase, as text for a prompt.

    Modules by how much depends on them, and the classes that carry the
    migration. Deterministic: SearchType.CODE reads graph indexes only, with
    no LLM and no embedding call.
    """
    facts = await _code_query(dataset, {"operation": "query_facts",
                                        "limit": 20000}, repo=repo)
    if not facts:
        return ""
    lines = []
    if package:
        lines.append(f"Package under migration: {package}")

    # WHERE THE CLASSES ARE, not a list of them. Listing 40 classes spent the
    # whole block on one file: x12sdk declares 238 classes and 200 of them are
    # nested enums inside v4010/segments.py. Per-file counts fit, and they are
    # what says which files carry the migration.
    classes = [f for f in facts
               if (f.get("properties") or {}).get("symbol_kind") == "class"]
    if classes:
        per_file: dict[str, int] = {}
        data_per_file: dict[str, int] = {}
        for s in classes:
            name = str(s.get("file") or "?")
            per_file[name] = per_file.get(name, 0) + 1
            if (s.get("properties") or {}).get("data_class"):
                data_per_file[name] = data_per_file.get(name, 0) + 1
        ranked = sorted(per_file, key=lambda f: (-data_per_file.get(f, 0),
                                                 -per_file[f], f))
        lines.append(f"{len(classes)} class(es) across {len(per_file)} "
                     f"file(s); most model-bearing first:")
        for name in ranked[:25]:
            lines.append(f"  {name}: {per_file[name]} class(es)"
                         + (f", {data_per_file[name]} of them data classes"
                            if data_per_file.get(name) else ""))

    mods = [f for f in facts if f.get("kind") == "module"]
    if mods:
        def depended_on(f):
            return int((f.get("properties") or {}).get("afferent") or 0)

        ranked = sorted(mods, key=lambda f: (-depended_on(f), str(f.get("name"))))
        if any(depended_on(f) for f in ranked):
            lines.append(f"{len(mods)} module(s), most depended-on first:")
            lines += [f"  {f.get('name')} (imported by {depended_on(f)})"
                      for f in ranked[:20]]
        else:
            # Every count is zero: enola resolved no cross-module imports
            # here, so printing "(imported by 0)" forty times is noise.
            lines.append(f"{len(mods)} module(s): "
                         + ", ".join(str(f.get("name")) for f in ranked[:20]))
    return _cap("\n".join(lines), limit)


async def code_insights(*, dataset: str, repo: str, limit: int = 8) -> str:
    """enola's own architectural findings over the same graph.

    Structural ones (cycles, declared-layer violations) score 1.0; heuristic
    ones (hotspots, god-class, complexity outliers) below. Nothing here is
    about Pydantic -- it is what the codebase is like, which is the half warm
    cannot learn from its own attempts.
    """
    try:
        import cognee
        from cognee import SearchType

        results = await cognee.search(
            query_type=SearchType.CODE, query_text="", datasets=[dataset],
            code_query={"operation": "insights", "min_confidence": 0.6,
                        "limit": 200})
    except Exception as exc:
        print(f"  code_insights failed ({exc!r}); continuing without them")
        return ""
    ranked = sorted(
        _scoped_to_repo(results, "insights", repo),
        key=lambda i: -float((i.get("properties") or {}).get("confidence") or 0))
    lines: list[str] = []
    for item in ranked:
        name = str(item.get("name") or "").strip()
        if name and name not in lines:
            lines.append(name)
        if len(lines) >= limit:
            break
    return "\n".join(f"  {line}" for line in lines)


# ---- the skill -------------------------------------------------------


async def dataset_id(name: str) -> str | None:
    import cognee

    for row in await cognee.datasets.list_datasets():
        got = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
        if got == name:
            rid = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
            return str(rid) if rid else None
    return None


async def find_skill(name: str = SKILL_NAME, *,
                     dataset: str = DEFAULT_DATASET) -> dict | None:
    """`list_skills(dataset="a-name")` does not scope by name -- resolve the
    UUID first, or a foreign skill id comes back and its None reads as "the
    skill never landed"."""
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
    from cognee.api.v1.skills.list_skills import get_skill

    skill = await find_skill(name, dataset=dataset)
    did = await dataset_id(dataset)
    if skill is None or did is None:
        return None
    procedure = (await get_skill(skill["id"], did) or {}).get("procedure")
    # `clean`, because this text was written by a model into a graph and is
    # about to become a process argument. One rewrite carried a NUL.
    return clean(procedure) if procedure else procedure


async def ensure_skill(*, dataset: str = DEFAULT_DATASET) -> str:
    """Idempotent. A second run continues from the skill Cognee holds rather
    than overwriting it with the scaffold."""
    import cognee

    text = await current_procedure(dataset=dataset)
    if text:
        return text
    seed = SEED_SKILL_PATH.read_text()
    await cognee.remember(seed, dataset_name=dataset, content_type="skills",
                          skill_name=SKILL_NAME, skills_text=seed,
                          self_improvement=False)
    return await current_procedure(dataset=dataset) or ""


# ---- the graded attempt ----------------------------------------------


def score_from_verdict(*, tests_passed: int, tests_total: int,
                       closeness: float | None = None) -> float:
    """THE FUZZY MEASURE IS THE SCORE.

    `tests_passed` is a step function on these fixtures -- the package imports
    or it does not -- so one correct edit moves it by hundreds while the
    migration is barely begun. Measured on x12sdk: warm's best test score (60
    of 261) came from its LEAST reference-like tree (closeness 0.0161), while
    cold at 0 tests was at 0.0495.

    closeness is signed: -1.9748 was recorded when cold left a syntax error.
    Clamped to 0. A green suite is 1.0 regardless, because closeness ranks
    resemblance to one implementation, never correctness.
    """
    if tests_total > 0 and tests_passed >= tests_total:
        return 1.0
    if closeness is None:
        return max(0.0, min(1.0, tests_passed / tests_total)) if tests_total > 0 else 0.0
    return max(0.0, min(1.0, float(closeness)))


def outcome_document(*, fixture: str, attempt: int, agent: str,
                     helped: bool, headline: str, evidence: str,
                     tests_passed: int, tests_total: int,
                     closeness: float | None, v1_remaining: int,
                     error_signature: str | None, rejected_because: str = "",
                     max_chars: int = 3000) -> str:
    """The one document per attempt that carries what the agent actually did.

    Everything here is the GRADER's, not the model's: an independent pytest run
    in a fresh sandbox, and a diff of the tree the harness took itself. Written
    as prose with the diff inline, because that is what a later attempt reads
    back and what `distill_sessions` draws its lesson from. Before this existed
    the graph held `"attempt 3: vibe exited 0 after 12 assistant turn(s)"` and
    distillation had nothing about Pydantic to distil.
    """
    verdict = "WORKED" if helped else "DID NOT WORK"
    head = [
        f"{verdict} -- {fixture} attempt {attempt} by {agent}.",
        headline.strip(),
        (f"Graded independently: {tests_passed}/{tests_total} tests passing, "
         f"{v1_remaining} pydantic v1 surfaces left in the package"
         + (f", closeness to the reference migration {closeness:.4f}"
            if closeness is not None else "") + "."),
    ]
    if error_signature:
        head.append(f"First failure after this attempt: {error_signature}")
    if rejected_because:
        head.append(rejected_because.strip())
    body = "\n".join(h for h in head if h)
    room = max_chars - len(body) - 2
    if evidence.strip() and room > 200:
        body += "\n\n" + _cap(evidence.strip(), room)
    return body


async def record_attempt(*, fixture: str, attempt: int, agent: str,
                         helped: bool, headline: str, evidence: str,
                         tests_passed: int, tests_total: int,
                         closeness: float | None, v1_remaining: int,
                         error_signature: str | None,
                         rejected_because: str = "",
                         latency_ms: int = 0,
                         dataset: str = DEFAULT_DATASET,
                         session_id: str | None = None,
                         improve_skill: bool = True,
                         score_threshold: float = 0.9,
                         max_runs: int = 5) -> dict[str, Any]:
    """Two writes, both Cognee's own: the outcome document into the worked or
    failed node set, and the graded run as a SkillRunEntry that drafts -- and
    then applies -- a rewrite of the procedure."""
    import cognee

    worked_set, failed_set = node_sets(fixture)
    document = outcome_document(
        fixture=fixture, attempt=attempt, agent=agent, helped=helped,
        headline=headline, evidence=evidence, tests_passed=tests_passed,
        tests_total=tests_total, closeness=closeness,
        v1_remaining=v1_remaining, error_signature=error_signature,
        rejected_because=rejected_because)
    await cognee.remember(document, dataset_name=dataset,
                          node_set=[worked_set if helped else failed_set],
                          self_improvement=False)

    score = score_from_verdict(tests_passed=tests_passed,
                               tests_total=tests_total, closeness=closeness)
    if not improve_skill:
        return {"score": score, "document_chars": len(document),
                "node_set": worked_set if helped else failed_set,
                "proposal_id": None, "applied": False,
                "procedure_chars": len(await current_procedure(
                    dataset=dataset) or "")}

    from cognee.memory.entries import SkillRunEntry

    entry = SkillRunEntry(
        # Wants the skill's NAME, not its id.
        selected_skill_id=SKILL_NAME,
        task_text=f"attempt {attempt}: migrate {fixture} to Pydantic v2",
        result_summary=document[:2000],
        success_score=score,
        feedback=1.0 if helped else -1.0,
        error_message=(error_signature or "")[:500],
        latency_ms=latency_ms)
    # `skill_improvement` must ride on a SkillRunEntry; sent alone it is
    # rejected.
    result = await cognee.remember(
        entry, dataset_name=dataset, session_id=session_id,
        skill_improvement={"skill_name": SKILL_NAME,
                           "score_threshold": score_threshold,
                           "max_runs": max_runs},
        self_improvement=False)
    proposal_id = _proposal_id_of(result)
    if proposal_id:
        await _apply_improvement(proposal_id, dataset=dataset)
    procedure = await current_procedure(dataset=dataset) or ""
    return {"score": score, "document_chars": len(document),
            "node_set": worked_set if helped else failed_set,
            "proposal_id": proposal_id, "applied": bool(proposal_id),
            "procedure_chars": len(procedure)}


def _proposal_id_of(result: Any) -> str | None:
    for item in (getattr(result, "items", None) or []):
        if isinstance(item, dict) and item.get("kind") == "skill_improvement_proposal":
            pid = item.get("proposal_id")
            return str(pid) if pid else None
    return None


async def _apply_improvement(proposal_id: str, *,
                             dataset: str = DEFAULT_DATASET) -> Any:
    """apply needs `improve_skill` directly, with a Dataset OBJECT."""
    from cognee.modules.memify.skill_improvement import improve_skill
    from cognee.modules.pipelines.layers.resolve_authorized_user_datasets import (
        resolve_authorized_user_datasets)
    from cognee.modules.users.methods import get_default_user

    _, datasets = await resolve_authorized_user_datasets(
        dataset, await get_default_user())
    if not datasets:
        raise RuntimeError(f"no dataset {dataset!r}")
    return await improve_skill(SKILL_NAME, dataset=datasets[0],
                               proposal_id=proposal_id, apply=True)


# ---- reads -----------------------------------------------------------


async def recall_node_set(*, dataset: str, node_set: str, query: str,
                          top_k: int = 8,
                          limit: int = MAX_BLOCK_CHARS) -> str:
    """The stored documents in one node set, ranked against `query`.

    CHUNKS + only_context returns the text as stored, with no model in the way
    and no reshuffling between attempts. Never fatal: this runs inside the
    attempt body, so an unreachable graph must cost the memory and not the
    attempt.
    """
    try:
        import cognee
        from cognee import SearchType

        entries = await cognee.recall(
            query or "pydantic v1 to v2 migration", datasets=[dataset],
            node_name=[node_set], query_type=SearchType.CHUNKS,
            only_context=True, top_k=top_k)
    except Exception as exc:
        print(f"  recall({node_set}) could not read the graph ({exc!r}); "
              f"this attempt runs without that block")
        return ""
    seen: list[str] = []
    for entry in entries or []:
        # A cold dataset answers with a warming-up marker, not an empty list.
        if getattr(entry, "source", None) == "system":
            continue
        text = (getattr(entry, "text", None) or "").strip()
        for para in text.split("\n\n"):
            para = para.strip()
            if para and para not in seen:
                seen.append(para)
    return _cap("\n\n".join(seen), limit)


async def bridge(session_ids: list[str], *,
                 dataset: str = DEFAULT_DATASET) -> dict:
    """Session traces into the permanent graph, and lessons out of them.

    Without this the traces are write-only: `recall` on the same session finds
    them and nothing else ever does. The stages that matter are
    persist_agent_traces, extract_agent_context and distill_sessions. Drains
    cognee's background work afterwards so the next read cannot race it.
    """
    import cognee

    result = await cognee.improve(dataset, session_ids=session_ids)
    try:
        await cognee.wait_for_background_tasks(timeout=120.0)
    except Exception:
        pass
    stages = {}
    for stage in (getattr(result, "stages", None) or []):
        stages[getattr(stage, "stage", None) or "?"] = {
            "status": getattr(stage, "status", None),
            "reason": getattr(stage, "reason", None),
            "counts": getattr(stage, "counts", None),
        }
    return {"status": getattr(result, "status", None), "stages": stages}


def with_agent_memory(fn: Callable[..., Awaitable[Any]], *,
                      dataset: str, session_id: str,
                      agent_session_name: str) -> Callable[..., Awaitable[Any]]:
    """Cognee's decorator around one attempt: it WRITES the trace.

    `with_memory=False` because the decorator's retrieval is hardwired to
    GRAPH_SUMMARY_COMPLETION, which describes graph topology rather than a
    lesson and is different on every call. Reads are `recall_node_set`.
    """
    import cognee

    return cognee.agent_memory(
        agent_session_name=agent_session_name,
        dataset_name=dataset,
        session_id=session_id,
        with_memory=False,
        with_session_memory=True,
        save_session_traces=True,
    )(fn)


async def forget_everything(*, dataset: str = DEFAULT_DATASET,
                            everything: bool = False) -> None:
    """`everything=True` is the only clean reset available on one instance,
    because recall is not dataset-scoped."""
    import cognee

    if everything:
        await cognee.forget(everything=True)
    else:
        await cognee.forget(dataset=dataset)


async def datasets_in_graph() -> list[str]:
    import cognee

    names = []
    for row in await cognee.datasets.list_datasets():
        name = (row.get("name") if isinstance(row, dict)
                else getattr(row, "name", None))
        if name:
            names.append(str(name))
    return sorted(names)


# Control characters that cannot survive the trip to the model: the prompt is
# passed to Vibe as a process argument, and `subprocess` rejects a NUL in argv
# outright. Tab, newline and carriage return are kept.
_CONTROL = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}
_CONTROL[0x7F] = None


def clean(text: str) -> str:
    """Strip what cannot be passed to a process argument.

    MEASURED 2026-09-21: a procedure Cognee had rewritten came back with an
    embedded NUL, and the attempt died in `subprocess.Popen` with
    `ValueError: embedded null byte` -- inside the decorator, so it read as
    "cognee could not open this attempt's memory" and the attempt ran with no
    memory at all. Everything this module hands the prompt goes through here,
    because all of it is text some model wrote into a graph.
    """
    return (text or "").translate(_CONTROL)


async def _bounded(coro, seconds: float, what: str, default):
    """Await `coro` with a deadline, or return `default` loudly.

    Cognee has no deadline of its own on the provider calls under `improve`
    and `improve_skill`, and neither did this harness: a rehearsal sat for two
    hours in one SSL read with the event loop otherwise idle, mid-attempt,
    after the GPU had been paid for. Nothing distinguished it from work.
    """
    import asyncio

    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        print(f"  MEMORY TIMED OUT after {seconds:.0f}s in {what}; "
              f"continuing without it")
        return default


def _cap(text: str, limit: int) -> str:
    """Never longer than `limit`, marker included. Prefers a line boundary,
    but not at the cost of most of the text."""
    text = clean(text)
    if len(text) <= limit:
        return text
    marker = "\n[...]"
    head = text[:max(0, limit - len(marker))]
    cut = head.rfind("\n")
    if cut > len(head) * 0.8:
        head = head[:cut]
    return head + marker


# ---- one warm agent's handle -----------------------------------------


# EVERY MEMORY CALL IS BOUNDED, and none of these is a guess at a normal
# duration -- they are the point past which a hung provider is costing the run
# rather than doing work.
#
# MEASURED 2026-09-21: a rehearsal sat for two hours in one `_ssl_SSLSocket_
# read` with the event loop otherwise idle. Neither Cognee nor the harness had
# a deadline anywhere on the path, so a provider that accepts a connection and
# never answers stops the experiment dead -- silently, mid-attempt, after the
# GPU has been paid for.
READ_TIMEOUT_S = 120.0          # inside the attempt; costs the agent's clock
WRITE_TIMEOUT_S = 420.0         # off the clock, but bounded all the same
BRIEF_WORKED = "What WORKED on earlier attempts at this codebase"
BRIEF_FAILED = "What DID NOT WORK on earlier attempts at this codebase"
BRIEF_CODE = "This codebase, from its code graph"


@dataclass
class CogneeMemory:
    """Warm gets one; cold gets None. Every method is one Cognee call."""

    dataset: str = DEFAULT_DATASET
    fixture: str = "fixture"
    label: str = "warm-0"
    # Per run, per agent. Once the constant "warm-0", so 98 runs wrote into one
    # session -- and `forget` does not prune the session cache, so a REUSED id
    # distils nothing ever again (measured: 0 documents on three attempts, 1
    # per attempt the moment the id changed).
    session_id: str = "warm-0"
    mode: str = "hybrid"
    code_dataset: str | None = None
    # The directory name enola stamped on every fact. SearchType.CODE is not
    # dataset-scoped, so without it one fixture's code graph reaches another's
    # prompt -- measured.
    code_repo: str | None = None
    package: str | None = None
    # `--no-distill`: still record the outcome document (that is the memory
    # under test), but leave the procedure alone so the skill cannot change
    # mid-run. Without the split, turning the skill off turned the memory off.
    distil: bool = True
    reads: int = field(default=0, init=False)
    chars: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.mode not in MEMORY_MODES:
            raise ValueError(f"memory mode {self.mode!r} is not one of {MEMORY_MODES}")

    async def procedure(self) -> str:
        if not uses_injection(self.mode):
            return ""
        return await _bounded(current_procedure(dataset=self.dataset),
                              READ_TIMEOUT_S, "procedure()", "") or ""

    async def brief(self, query: str) -> str:
        """What this attempt is handed as memory, with the two halves labelled.

        The labels are the point. `distill_sessions` writes lessons and
        `recall` ranks documents, but neither says which of two retrieved
        paragraphs is the one to copy and which is the one to avoid. The node
        set does, because the grader decided it.
        """
        if not uses_injection(self.mode):
            return ""
        worked_set, failed_set = node_sets(self.fixture)
        worked = await _bounded(
            recall_node_set(dataset=self.dataset, node_set=worked_set,
                            query=query), READ_TIMEOUT_S, "brief/worked", "")
        failed = await _bounded(
            recall_node_set(dataset=self.dataset, node_set=failed_set,
                            query=query), READ_TIMEOUT_S, "brief/failed", "")
        code = ""
        if self.code_dataset and self.code_repo:
            try:
                code = await _bounded(
                    code_brief(dataset=self.code_dataset, repo=self.code_repo,
                               package=self.package),
                    READ_TIMEOUT_S, "code_brief", "")
                insights = await _bounded(
                    code_insights(dataset=self.code_dataset,
                                  repo=self.code_repo),
                    READ_TIMEOUT_S, "code_insights", "")
                if insights:
                    code += f"\nWhat its structure looks like:\n{insights}"
            except Exception as exc:
                print(f"  code_brief failed ({exc!r}); continuing without it")
        blocks = []
        if code:
            blocks.append(f"### {BRIEF_CODE}\n{code}")
        if worked:
            blocks.append(f"### {BRIEF_WORKED}\n{worked}")
        if failed:
            blocks.append(f"### {BRIEF_FAILED}\nDo not repeat these.\n{failed}")
        block = "\n\n".join(blocks)
        if block:
            self.reads += 1
            self.chars += len(block)
        return block

    def wrap_attempt(self, fn: Callable[..., Awaitable[Any]],
                     **kwargs) -> Callable[..., Awaitable[Any]]:
        if self.mode == "off":
            return fn
        return with_agent_memory(
            fn, dataset=self.dataset, session_id=self.session_id,
            agent_session_name=f"msf:{self.label}", **kwargs)

    async def record(self, **kwargs) -> dict[str, Any]:
        if self.mode == "off":
            return {}
        return await _bounded(
            record_attempt(fixture=self.fixture, agent=self.label,
                           dataset=self.dataset, session_id=self.session_id,
                           improve_skill=self.distil, **kwargs),
            WRITE_TIMEOUT_S, "record()", {})

    async def improve(self) -> dict:
        if self.mode == "off":
            return {"status": "skipped", "stages": {}}
        return await _bounded(bridge([self.session_id], dataset=self.dataset),
                              WRITE_TIMEOUT_S, "improve()",
                              {"status": "timed_out", "stages": {}})


WarmMemory = CogneeMemory
