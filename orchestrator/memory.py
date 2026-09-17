"""MemoryClient wrapper -- the warm swarm's only entry point into Neo4j.

The cold swarm has zero contact with this module or with Neo4j: no reads, no
writes, no traces, no messages. That is decided once, in run.py's main_async,
by passing `mem=None` down a cold agent's entire call chain -- not by gating
reads. An earlier `read_gate` revision still had cold agents writing
ReasoningTrace nodes to the shared graph, which is not an isolated baseline.

What lives here is the deterministic half of the memory loop, modelled on
workshop-agent-memory-scripts/memory_agent_mvp.py: get_context() read fresh
before every attempt, one trace per attempt, every Vibe tool call replayed as
a reasoning step, the trace closed on an independent pytest verdict. None of
it depends on the model choosing to call anything. The agent-callable half is
separate -- warm agents also get neo4j-agent-memory's own MCP server
registered into Vibe (see render_config) -- and the two are complementary.

Thin by design. Everything here is either a pass-through to the package or one
of three things the package genuinely cannot do for us: drop verdict-less
traces, break the similarity tie that ties every trace at 0.9996 on an
identical codebase, and report which agent a retrieved trace came from.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from neo4j_agent_memory import MemoryClient, MemorySettings
from neo4j_agent_memory.config import ExtractionConfig
from neo4j_agent_memory.config.settings import ExtractorType, Neo4jConfig
from neo4j_agent_memory.memory.reasoning import ToolCallStatus

# One definition, used by build_settings() below AND by the neo4j-agent-memory
# MCP server registration in vibe_agent.render_config(). They must agree: the
# MCP server builds its own client, and a mismatch means it opens the six
# vector indexes at the wrong dimension and refuses to start.
EMBEDDING_MODEL = "openai/text-embedding-3-small"

import json
import logging
import os

# Keep the embedding stack off the network. A synchronous network call inside
# this orchestrator's asyncio loop does not slow one agent down, it stalls
# every coroutine on the loop -- confirmed live: four warm agents hit a hanging
# HF Hub request and the whole run froze, including all four COLD agents, which
# never even spawned their Vibe subprocess. Warm's memory latency landing on
# cold's wall-clock is the cross-arm contamination this experiment cannot have.
#
# Harmless now that embeddings go to OpenAI, but kept because anything that
# re-introduces a local embedder inherits the trap.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# NO DEFAULTS. Both must be in the environment (.env, loaded by run.py before
# this module is imported) or importing this module fails.
#
# They used to default to `bolt://localhost:7688` /
# "miss-slaytona-forje-dev" -- a local Docker Neo4j -- while the deployed
# configuration is an Aura instance. A default is the wrong shape for this
# value, for two reasons that both bit:
#
# * SILENT DIVERGENCE. Any entry point that does not `load_dotenv()` before
#   importing this module resolves to the local instance instead, while the
#   agents' MCP server is given the Aura URI explicitly by render_config().
#   Orchestrator and agents then read and write DIFFERENT DATABASES, and
#   nothing says so: `--reset-memory` reports "deleted 148 node(s)" and
#   "graph at start: (empty)" about a server the agents never touch. Caught
#   by inspecting a graph that turned out to hold a four-agent run from the
#   previous day when the run being inspected had one agent.
#
# * CONTAMINATION. That local instance still held a trace whose summary read
#   "This change made the full test suite pass", with a complete and correct
#   migration diff, at tests_passed 33/33. A warm agent pointed at it would
#   retrieve the finished answer. Not the answer key -- an earlier agent's own
#   work, which is the intended cross-run mechanism -- but selected by an
#   unset environment variable rather than by anyone's decision.
#
# A measurement tool must not be able to guess which database it is measuring.
def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. It has no default on purpose: a default sent "
            f"the orchestrator to a local Neo4j while the agents' MCP server "
            f"used the hosted one, so the two halves of a run read different "
            f"graphs and the run log described the wrong server. Put it in "
            f".env (run.py calls load_dotenv() before importing this module)."
        )
    return value


NEO4J_URI = _require("NEO4J_URI")
NEO4J_PASSWORD = _require("NEO4J_PASSWORD")

# EMBEDDING_MODEL is baked into six vector indexes at creation time, so
# changing it means dropping and recreating all six
# (scripts/reset_memory_indexes.py), and it must stay in step with the
# `--embedding` flag handed to the MCP server in vibe_agent.render_config(),
# which builds its own client and refuses to start on a mismatch.


def build_settings() -> MemorySettings:
    """The canonical shape from the package README: a Neo4j connection and a
    provider string for the embedder.

    `backend="bolt"` is pinned deliberately. Left unset, MemorySettings
    resolves the backend at construction time (config/settings.py,
    `_resolve_backend`) and switches to the hosted NAMS service the moment a
    `MEMORY_API_KEY` appears anywhere in the environment. NAMS is a separate
    product with separate auth; this project talks to Neo4j over Bolt and must
    never silently become anything else.

    `embedding` uses the provider-string form rather than EmbeddingConfig:
    that legacy shape emits a DeprecationWarning and the package's own source
    marks it for removal in v0.5.0, which is the version installed here. It is
    stated rather than inherited because the dimension is baked into six vector
    indexes, and changing it silently is what causes
    EmbeddingDimensionMismatchError across all of them (see
    scripts/reset_memory_indexes.py).

    The embedder is a network call to OpenAI and the client is async, so it
    does not block the shared asyncio loop. That property is load-bearing: a
    blocking embedder would put warm's memory latency on cold's wall-clock and
    invalidate the comparison, which is what the HF_HUB_OFFLINE note above
    records happening with a local one."""
    return MemorySettings(
        backend="bolt",
        neo4j=Neo4jConfig(uri=NEO4J_URI, password=SecretStr(NEO4J_PASSWORD)),
        # A standing project decision, not a tuning knob -- it has been
        # changed away and reverted more than once. The argument for a local
        # embedder is real but loses: this costs warm a measured ~300ms per
        # stored message that cold does not pay, and what it buys is a
        # dimension and provider the whole stack agrees on by default,
        # including the MCP server's own client.
        #
        # `generate_embedding` stays ON wherever it appears: turning it off
        # silently disables entity extraction too (verified -- embed ON gives
        # entities, embed OFF gives []), which would gut the POLE+O graph this
        # demo exists to show.
        embedding=EMBEDDING_MODEL,
        # LLM extraction, which `ExtractorType` lists as one of five
        # first-class extractors ('llm', 'gliner', 'spacy', 'pipeline',
        # 'none') -- not a fallback stage.
        #
        # This was `ExtractionConfig(enable_llm_fallback=False)`, i.e. the
        # spaCy -> GLiNER pipeline, on a cost measurement: 2071 ms/message
        # with the LLM stage against 289 ms without, and run 30 completing 1
        # warm attempt to cold's 17. That measurement was of extraction
        # running INLINE on every message as the agents worked. It no longer
        # does: messages are stored with extract_entities=False and
        # extract_entities_from_session() runs once after the clock stops, so
        # the cost is outside the measured window and the constraint that
        # forced local-only extraction is gone.
        #
        # What local extraction cost instead was precision, and on this corpus
        # that is severe. spaCy's en_core_web_sm is general-English NER; the
        # entities that matter here are code symbols -- `BaseSettings`,
        # `model_validator`, `pydantic_settings`, `email_validator`. It maps
        # them onto PERSON/LOCATION/ORGANIZATION because those are the labels
        # it has. Visible in the graph from a PYDANTIC MIGRATION: Person 32,
        # Location 12, City 1, Facility 1, Company 1. Earlier measured worse
        # -- 78 of 229 entities were strings like '100->' and '0.17s'.
        #
        # entity_types is narrowed to OBJECT, and this is the difference
        # between a useful entity layer and an empty one. Measured on one
        # paragraph of real agent reasoning, all three run against the same
        # text in the same minute:
        #
        #   LLM, default POLE+O ..................... 0 entities
        #   LLM, entity_types=["OBJECT"] ............ 9 entities
        #   spaCy + GLiNER (the previous setting) ... 3 entities
        #
        # The LLM with the full POLE+O list returns NOTHING, and it is right
        # to: `BaseSettings` is not a person, place, organisation or event, so
        # a careful extractor declines rather than guessing. Local NER has no
        # such scruple, which is where Person 32 / Location 12 / City 1 /
        # Facility 1 came from in a pydantic migration.
        #
        # Told to look for objects, the LLM returns exactly the right nine:
        # Pydantic v1, Pydantic v2, BaseSettings, pydantic_settings,
        # config.py, root_validator, model_validator, EmailStr,
        # email_validator.
        #
        # This is not narrowing POLE+O -- OBJECT *is* the O, and a codebase
        # contains no people or cities. It is declining to invent the other
        # four. Leave confidence_threshold alone: 0.0 empties the result
        # (measured), so it is not a "keep everything" dial.
        extraction=ExtractionConfig(
            extractor_type=ExtractorType.LLM, entity_types=["OBJECT"]
        ),
    )


async def graph_counts() -> dict[str, int]:
    """Node counts by primary label, for the run summary. What is already in
    the graph when a run starts is part of the result and should never be
    invisible: a warm swarm reading a graph that still holds twelve previous
    runs of this same task is a different experiment from one starting
    clean, and the printed summary looks identical either way."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
    try:
        records, _, _ = await driver.execute_query(
            "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC"
        )
        return {r["l"]: r["c"] for r in records}
    finally:
        await driver.close()


async def reset_graph() -> int:
    """Delete every node and relationship. For a clean warm-vs-cold
    comparison within a single run -- i.e. "did these four warm agents help
    each other over ten minutes", not "does a graph built over a dozen
    earlier runs help". Opt-in via run.py's --reset-memory; both are
    legitimate demos, but they are different claims and the difference has
    to be chosen rather than inherited."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
    try:
        records, _, _ = await driver.execute_query(
            "MATCH (n) DETACH DELETE n RETURN count(n) AS deleted"
        )
        return records[0]["deleted"] if records else 0
    finally:
        await driver.close()


logger = logging.getLogger(__name__)


class ScopedMemory:
    """The warm swarm's -- and only the warm swarm's -- view of memory.
    Never constructed for a cold agent; orchestrator/run.py passes mem=None
    down a cold agent's entire call chain instead."""

    def __init__(self, client: MemoryClient, *, user_identifier: str):
        self._client = client
        self.user_identifier = user_identifier

    async def start_trace(self, session_id: str, task: str):
        return await self._client.reasoning.start_trace(
            session_id=session_id, task=task, user_identifier=self.user_identifier,
        )

    def set_provenance(self, **props: Any) -> None:
        """What produced the traces this scope writes.

        `TraceOutcome.metrics` is typed `dict[str, float]`, so the model
        name, GPU and harness commit cannot live there. They are stamped
        onto the trace node directly instead, by complete_trace below.

        This exists because the graph already contains traces from two
        models on three GPUs, written under two different definitions of
        `success`, some by agents whose checkout was read-only and who
        therefore could not edit anything. Mixing those into distillation
        would teach the distiller from runs that measured the harness rather
        than the agent. Eligibility is decided on these properties -- see
        eligible_traces().
        """
        self._provenance = dict(props)

    async def complete_trace(
        self,
        trace_id: UUID,
        *,
        outcome: Any,
        success: bool | None = None,
        generate_step_embeddings: bool = False,
    ):
        """`outcome` takes either a plain string (the legacy shape) or a
        TraceOutcome, which additionally persists `error_kind` as a top-level
        indexed property and `metrics` on the node. A TraceOutcome overrides
        `success`."""
        result = await self._client.reasoning.complete_trace(
            trace_id, outcome=outcome, success=success,
            generate_step_embeddings=generate_step_embeddings,
        )
        # Stamped here rather than at the call site, so every trace this
        # scope completes carries provenance without migrate_codebase --
        # the shared, tested path -- needing to know about it.
        prov = getattr(self, "_provenance", None)
        if prov:
            try:
                await self._client.graph.execute_write(
                    "MATCH (t:ReasoningTrace) WHERE toString(t.id) = $id SET t += $p",
                    {"id": str(trace_id), "p": prov},
                )
            except Exception as exc:
                logger.error("provenance stamp failed for trace %s: %r",
                             trace_id, exc)
        return result

    async def eligible_traces(self, *, model: str, schema: float = 2.0) -> list[dict]:
        """Traces a distiller may learn from.

        Three filters, each for a failure already in the graph:
          * `prov_model` -- 109 of 187 steps were written by Qwen3-14B, a
            weaker model on different hardware;
          * `prov_writable` -- seven early runs handed agents a chmod a-w
            checkout and recorded 13 graded attempts with zero edits;
          * `outcome_schema >= 2` -- before that, `success` meant "passed OR
            advanced", so two traces claim success at tests_passed<33.
        """
        rows = await self._client.query.cypher(
            "MATCH (t:ReasoningTrace) WHERE t.user_identifier = $who "
            "AND t.prov_model = $model AND t.prov_writable = true "
            "OPTIONAL MATCH (t)-[:HAS_STEP]->(s:ReasoningStep) "
            "WITH t, count(s) AS steps, "
            "  sum(CASE WHEN s.thought IS NOT NULL AND NOT s.thought STARTS WITH '{' "
            "      THEN 1 ELSE 0 END) AS real_thoughts "
            "RETURN toString(t.id) AS id, t.success AS suite_passed, "
            "  t.metrics_json AS metrics, steps, real_thoughts, "
            "  t.outcome AS outcome, t.task AS task "
            "ORDER BY t.started_at",
            {"who": self.user_identifier, "model": model},
        )
        out = []
        for r in rows:
            try:
                m = json.loads(r["metrics"]) if r["metrics"] else {}
            except (json.JSONDecodeError, TypeError):
                m = {}
            if m.get("outcome_schema", 0.0) < schema:
                continue
            out.append({**dict(r), "metrics": m})
        return out

    async def add_step(
        self,
        trace_id: UUID,
        *,
        thought: str | None,
        action: str | None,
        observation: str | None = None,
        generate_embedding: bool = True,
    ):
        """thought / action / observation are ReasoningMemory.add_step's own
        parameters, forwarded unchanged.

        `observation` was missing from this wrapper while the caller had
        already started passing it, which is not a cosmetic mismatch: every
        warm agent in run 27 raised `TypeError: ScopedMemory.add_step() got an
        unexpected keyword argument 'observation'` after finishing its Vibe
        turn, so all 18 attempts were discarded and retried, 140 LLM calls
        produced 0 completed attempts, and the run reported a token ratio of
        0.634 that measured nothing but this bug. This class is a thin
        pass-through; when the package gains a parameter the caller wants, it
        belongs here too."""
        return await self._client.reasoning.add_step(
            trace_id, thought=thought, action=action, observation=observation,
            generate_embedding=generate_embedding,
        )

    async def record_tool_call(
        self,
        step_id: UUID,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any | None = None,
        status: ToolCallStatus = ToolCallStatus.SUCCESS,
    ):
        return await self._client.reasoning.record_tool_call(
            step_id, tool_name=tool_name, arguments=arguments, result=result, status=status,
        )

    async def search_steps(
        self,
        query: str,
        *,
        limit: int = 10,
        success_only: bool = True,
        threshold: float = 0.7,
    ):
        """Step-level retrieval, for the per-step hook (step_memory.py).

        The package's own docstring calls this granularity "the right cut for
        case-based imitation prompting", and it returns
        ReasoningStepWithContext -- so `parent_success` ("did this work")
        comes from the package rather than from any inference of ours.

        NOT scoped by user_identifier or session, by the package's design:
        get_similar_traces/search_steps are pure vector searches over the
        whole graph. That is what makes one agent able to see another's work,
        and it is the property the whole warm arm rests on.

        This wrapper existed nowhere for one run. The hook called
        `mem.search_steps(...)`, ScopedMemory did not have it, and every
        single call raised AttributeError inside the fail-open branch -- so
        the run reported 24 steps written and 24 errors, 0 retrievals, and
        looked exactly like a graph with nothing in it."""
        return await self._client.reasoning.search_steps(
            query, limit=limit, success_only=success_only, threshold=threshold,
        )

    async def extract_entities_from_session(self, session_id: str) -> dict:
        """Entity + relation extraction over a whole session, after the fact.

        The package's own answer to extraction cost, named in its docstring for
        messages "loaded without extraction". `add_message` defaults to
        `extract_entities=True`, and that default is what made memory writes
        expensive: 0.50s per message, 45.5s per attempt, paid by warm only --
        most of why cold completed 21-28 attempts per run while warm managed
        8-10.

        So messages are stored with extraction OFF during the run, and this is
        called once at the end, outside the measured window. Same entities,
        same POLE+O typing, off the agents' clock."""
        return await self._client.short_term.extract_entities_from_session(session_id)

    async def link_step_entities(self, session_id: str) -> int:
        """Extract entities from this session's REASONING STEPS and link them.

        `extract_entities_from_session` covers messages only -- verified:
        add_step has no extraction path at all. But the reasoning is where the
        substance is on this task, and most of it never becomes a message: a
        turn that is pure reasoning plus a tool call has no text content, so
        its thinking lives in ReasoningStep.thought and nowhere else.

        The package models the link itself, as
        `(:ReasoningStep)-[:TOUCHED]->(:Entity)`, and its Cypher MERGEs the
        entity -- so this creates and links in one step, with resolution
        against whatever is already there.

        `_record_touched_edge` is the one PRIVATE call in this file. The public
        route is `record_tool_call(touched_entities=[...])`, which happens at
        record time, inside the agent's tool-call path -- and extraction is an
        LLM round-trip. Putting it there is the exact mistake that made warm
        complete 8-10 attempts per run against cold's 21-28. So this runs once
        after the clock stops, and accepts a private call to stay off the
        agents' budget. If the package grows a public post-hoc equivalent,
        this should move to it.
        """
        from neo4j_agent_memory.extraction.factory import create_extractor
        from neo4j_agent_memory.schema.models import EntityRef

        # `client.query.cypher`, not `client.graph.execute_read`: the latter is
        # a _DeprecatedGraphProxy that emits a DeprecationWarning pointing here
        # and is "scheduled for removal in v0.6.0".
        rows = await self._client.query.cypher(
            """
            MATCH (t:ReasoningTrace {session_id: $sid})-[:HAS_STEP]->(s:ReasoningStep)
            WHERE s.thought IS NOT NULL AND size(s.thought) > 40
            RETURN s.id AS id, s.thought AS thought
            """,
            {"sid": session_id},
        )
        extractor = create_extractor(build_settings().extraction)
        linked = 0
        for row in rows:
            try:
                result = await extractor.extract(row["thought"])
            except Exception:
                continue
            for entity in (result.entities or [])[:12]:
                name = getattr(entity, "name", None)
                if not name:
                    continue
                etype = getattr(entity, "type", None)
                await self._client.reasoning._record_touched_edge(
                    UUID(row["id"]) if not isinstance(row["id"], UUID) else row["id"],
                    EntityRef(name=str(name), type=getattr(etype, "value", etype)),
                )
                linked += 1
        return linked

    async def trace_metrics(self, trace_ids: list[str]) -> dict[str, dict]:
        """metrics_json for these traces, parsed, keyed by trace id.

        `search_steps` returns parent_task/parent_outcome/parent_success but
        not metrics, and `tests_passed` is what makes a retrieved step
        interpretable. One query for the whole hit set."""
        rows = await self._client.query.cypher(
            "MATCH (t:ReasoningTrace) WHERE toString(t.id) IN $ids "
            "RETURN toString(t.id) AS id, t.metrics_json AS m",
            {"ids": list(trace_ids)},
        )
        out: dict[str, dict] = {}
        for row in rows:
            try:
                out[row["id"]] = json.loads(row["m"]) if row["m"] else {}
            except (json.JSONDecodeError, TypeError):
                out[row["id"]] = {}
        return out

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        extract_entities: bool = True,
    ):
        """`extract_entities` is the package's own parameter and the ONLY
        default overridden here, by the caller, for a measured reason: it
        defaults to True, and extraction is 0.50s of spaCy + GLiNER + OpenAI
        per message. Messages streamed live during a run pass False and
        extract_entities_from_session() runs once at the end instead.

        Nothing else is overridden. An earlier revision also passed
        extraction_mode='skip' and generate_embedding=False, both untested
        guesses about the pipeline; without them this matches
        memory_agent_mvp.py's own add_message call."""
        return await self._client.short_term.add_message(
            session_id, role, content,
            extract_entities=extract_entities,
            user_identifier=self.user_identifier,
        )
