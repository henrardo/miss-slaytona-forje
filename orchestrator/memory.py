"""MemoryClient wrapper (Sec. 5) -- the warm swarm's only entry point into
Neo4j. The cold swarm has zero contact with this module or with Neo4j at
all: no reads, no writes, no traces, no messages. That is the actual
"isolated" baseline arm the comparison needs (see orchestrator/run.py --
cold agents are built with mem=None throughout, not with reads disabled).

An earlier revision (`read_gate`) still let cold agents write reasoning
traces to the shared graph, tagged with their own user_identifier --
start_trace/complete_trace were called unconditionally for every agent, warm
and cold alike, and only the *read* tools were gated per-agent. Confirmed
live: cold-0..cold-3 each had 3 ReasoningTrace nodes in Neo4j after a run.
That's not an isolated baseline, it's a baseline that still writes to the
shared graph. Fixed by moving every memory call -- not just reads -- behind
`mem is not None`, decided once in orchestrator/run.py's main_async().

This module is the orchestrator's own client. The warm agents separately get
neo4j-agent-memory's MCP server registered into Vibe (see render_config), so
they can call memory themselves; the two are complementary. What lives here
is the deterministic loop from
workshop-agent-memory-scripts/memory_agent_mvp.py -- get_context() read fresh
before every attempt, one trace per attempt, every Vibe tool call replayed as
a reasoning step, the trace closed on an independent pytest verdict. None of
it depends on the model choosing to call anything.

An earlier revision of this file also carried commit_pattern()/
known_patterns(), which wrote "migration patterns" as OBJECT entities with a
BREAKAGE_PATTERN subtype and read them back with search_entities. Both are
gone. They existed because the traces retrieved nothing useful -- and they
retrieved nothing useful because they were keyed on the task description,
which is identical for every attempt. Keying them on the error signature
instead (see migrate_codebase) makes the reasoning layer do the job it
already had, and the parallel entity store has no reason to exist.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import SecretStr

from neo4j_agent_memory import MemoryClient, MemorySettings
from neo4j_agent_memory.config import ExtractionConfig
from neo4j_agent_memory.config.settings import Neo4jConfig
from neo4j_agent_memory.memory.reasoning import ToolCallStatus

# One definition, used by build_settings() below AND by the neo4j-agent-memory
# MCP server registration in vibe_agent.render_config(). They must agree: the
# MCP server builds its own client, and a mismatch means it opens the six
# vector indexes at the wrong dimension and refuses to start.
EMBEDDING_MODEL = "openai/text-embedding-3-small"

import json
import os

# Keep the embedding stack off the network. sentence-transformers/
# huggingface_hub phone home to check for model revisions on load and on
# first use, and those calls are synchronous. Inside this orchestrator's
# asyncio loop a synchronous network call doesn't just slow one agent down,
# it stalls every coroutine on the loop -- confirmed live: four warm agents
# hit a hanging HF Hub request (four ESTABLISHED sockets to a Cloudflare
# endpoint, 0% CPU) and the whole run froze, including all four *cold*
# agents, which never even spawned their Vibe subprocess. That is worse than
# a hang: warm's memory latency landing on cold's wall-clock is exactly the
# cross-arm contamination this experiment cannot have. Harmless now that
# embeddings are a network call to OpenAI rather than a local model, but
# kept because anything that re-introduces a local embedder inherits the
# same trap.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "miss-slaytona-forje-dev")

# Embeddings are local again (BAAI/bge-small-en-v1.5, 384 dimensions) -- see
# EMBEDDING_MODEL above and build_settings() below for the measurement.
#
# The history matters, because this moved twice. It was originally
# sentence-transformers/all-MiniLM-L6-v2 at 384; that was blamed for making
# the package's own MCP server unusable ("expected 1536, found 384") and a
# bespoke MCP server was written around it. The real fix was to pass the
# server the same `--embedding` the client uses -- a documented flag -- not to
# change embedder. It is now passed explicitly in vibe_agent.render_config(),
# so client and server agree by construction.
#
# Whenever this value changes, the six vector indexes must be dropped and
# recreated at the new dimension: scripts/reset_memory_indexes.py.


def build_settings() -> MemorySettings:
    """The canonical shape from the package README: a Neo4j connection and a
    provider string for the embedder. No API key needed -- the embedder is
    local (see EMBEDDING_MODEL).

    `backend="bolt"` is pinned deliberately. Left unset, MemorySettings
    resolves the backend at construction time (config/settings.py,
    `_resolve_backend`) and switches to the hosted NAMS service the moment a
    `MEMORY_API_KEY` appears anywhere in the environment. NAMS is a separate
    product with separate auth; this project's memory is the local Docker
    Neo4j and must never silently become anything else.

    `embedding` uses the provider-string form rather than EmbeddingConfig:
    that legacy shape emits a DeprecationWarning and the package's own source
    marks it for removal in v0.5.0, which is the version installed here. It is
    stated rather than inherited because the dimension is baked into six vector
    indexes, and changing it silently is what causes
    EmbeddingDimensionMismatchError across all of them (see
    scripts/reset_memory_indexes.py).

    The sentence-transformers adapter runs `model.encode` via
    `loop.run_in_executor`, so a local embedder does not block the shared
    asyncio loop -- checked in the package source, because a local embedder
    that blocked would put warm's memory latency on cold's wall-clock and
    invalidate the comparison. The freeze this module's HF_HUB_OFFLINE note
    describes was a hanging Hub *network* request at model load, not encode,
    and those env vars plus a pre-cached model prevent it."""
    return MemorySettings(
        backend="bolt",
        neo4j=Neo4jConfig(uri=NEO4J_URI, password=SecretStr(NEO4J_PASSWORD)),
        # openai/text-embedding-3-small, 1536 dimensions. This is a standing
        # project decision, not a tuning knob -- do not swap it for a local
        # model. It has been changed away and reverted more than once.
        #
        # The argument for going local is real but loses: the embedder runs
        # once per stored message, ~90 messages per attempt, at a measured
        # 303-336 ms round-trip each, so warm pays ~45s of memory work per
        # attempt that cold does not. That cost is accepted. What it buys is a
        # dimension and a provider that the rest of the stack -- the MCP
        # server's own client, and anything else pointed at this graph --
        # agrees on by default.
        #
        # Whatever else changes here, `generate_embedding` stays on:
        # turning it off silently disables entity extraction too (verified --
        # embed ON gives entities ['conference','Tuesday','Berlin'], embed OFF
        # gives []), which would gut the POLE+O graph this demo exists to show.
        #
        # Changing this value means recreating all six vector indexes at the
        # new dimension: scripts/reset_memory_indexes.py exists for that. It
        # must also stay in step with the `--embedding` flag passed to the MCP
        # server in vibe_agent.render_config(), which builds its own client.
        embedding=EMBEDDING_MODEL,
        # The extraction pipeline runs spaCy -> GLiNER -> LLM, all three, and
        # merges. The LLM stage is the package's own named *fallback* for when
        # the local extractors come up short; with `neo4j-agent-memory[gliner]`
        # installed they do not, and it becomes a billed OpenAI round-trip on
        # every stored message -- two, in fact, since the first returns 400 and
        # is retried.
        #
        # Measured, not assumed, on this workload:
        #
        #   spacy + gliner + llm (default)  2071 ms/message
        #   enable_llm_fallback=False        289 ms/message
        #
        # An agent attempt stores ~50 messages, so that is ~103s of memory
        # writes per attempt against ~14s. Run 30 is what it costs: warm
        # completed 1 attempt while cold completed 17, and the graph had grown
        # to 833 messages. Retrieval was never the expensive half.
        #
        # POLE+O typing survives -- checked directly, not inferred: spaCy and
        # GLiNER still produce ['Entity','Person'] / ['Entity','Location',
        # 'City'] / ['Entity','Object','Device'] with `type` set to PERSON /
        # LOCATION / OBJECT. Precision drops a little (GLiNER called "Neo4j" a
        # PERSON where the LLM would not), which is a fair trade for 7x the
        # attempts. Turn it back on by dropping this argument.
        #
        # This is the package's documented configuration surface, not a
        # workaround. Note the prior revision of this file disabled extraction
        # outright via extraction_mode='skip' as an untested guess and was
        # rightly reverted; the difference here is the measurement above.
        extraction=ExtractionConfig(enable_llm_fallback=False),
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


class ScopedMemory:
    """The warm swarm's -- and only the warm swarm's -- view of memory.
    Never constructed for a cold agent; orchestrator/run.py passes mem=None
    down a cold agent's entire call chain instead."""

    def __init__(self, client: MemoryClient, *, user_identifier: str):
        self._client = client
        self.user_identifier = user_identifier

    async def get_context(
        self,
        query: str,
        *,
        session_id: str | None = None,
        include_short_term: bool = True,
    ) -> str:
        """Called before every attempt regardless of whether the model calls a
        memory tool -- memory_agent_mvp.py's `what_you_remember`, whose
        framework runs it on every turn. The agent also has the
        neo4j-agent-memory MCP tools; this is the floor under that, not a
        replacement for it.

        `include_short_term` is the package's own get_context parameter. See
        migrate_codebase() for why this loop passes False.

        The reasoning layer is called separately, and deliberately.
        MemoryClient.get_context() hardcodes its reasoning call to
        success_only=True and does not forward a kwarg for it, so on this
        task it can only ever return "". Nothing here has ever completed with
        success=True: the fixture's tests/conftest.py imports fastapi_mail,
        and a conftest that fails to import aborts pytest before collection
        (--continue-on-collection-errors does not apply to conftest), so
        pytest emits no tally at all until the whole package imports cleanly.
        `tests_passed` is therefore structurally pinned at 0 and the strict
        criterion can never fire. Run 25: 13 traces, every one success=False,
        every warm retrieval empty, warm and cold indistinguishable at a
        token ratio of 0.962.

        Failed traces are the knowledge worth having here. Three agents
        independently rediscovered the same config.py BaseSettings fix in one
        run; one of them separately burned five attempts learning that
        `pydantic.model_validators` does not exist. ReasoningMemory.get_context
        takes `include_successful_only` as a documented parameter and already
        labels what it returns "- Success: No", so the failure stays marked as
        a failure all the way into the prompt. The trace-level success
        criterion is left strict -- retrieval no longer depends on it."""
        parts: list[str] = []
        base = await self._client.get_context(
            query,
            session_id=session_id,
            include_short_term=include_short_term,
            include_reasoning=False,
        )
        if base:
            parts.append(base)
        reasoning = await self._reasoning_context(query, max_traces=5)
        if reasoning:
            parts.append(reasoning)
        return "\n\n".join(parts)

    # Verdict-less outcomes. A trace closed on the deadline records that it was
    # interrupted, which is true and worth storing, but it is not knowledge.
    _NO_VERDICT = "ran out of time mid-attempt"

    async def _reasoning_context(self, query: str, *, max_traces: int) -> str:
        """HAND-ROLLED STANDIN for ReasoningMemory.get_context().

        Same output shape -- Task / Similarity / Outcome / Success -- built
        from the package's own get_similar_traces(). It exists only to drop
        traces that have nothing to say, which the package's formatter cannot
        do because it has no reason to expect them:

        * traces still OPEN. Agents run concurrently against one graph, so a
          sibling mid-attempt has a trace with a task and an embedding but no
          outcome yet. Observed in run 51: the two highest-similarity results
          (0.86, 0.85) rendered as a bare error name and a similarity score,
          nothing else, taking two of five slots at the top of the prompt.
        * traces closed with _NO_VERDICT, which say only that the clock ran
          out.

        Both are retrieved at high similarity precisely because they are keyed
        on the error the asking agent is looking at right now. Fetching extra
        and trimming keeps five *useful* traces rather than five rows.

        SIMILARITY CANNOT RANK THESE. A trace's embedding is built from its
        `task`, and `task` is the pytest error signature the attempt started
        from -- so every agent that hit the same error has a byte-identical
        task string. Measured on the run 53-56 graph: 16 of 37 traces share one
        task string, and a query for it returns all 15 fetched rows at
        similarity 0.9996, tied to four decimal places. The vector index then
        returns them in storage order and `[:max_traces]` takes whichever five
        happen to come back first. Quality never entered the ordering.

        That is the whole of the run 54 "result". Its warm-2 agent drew the one
        genuinely informative trace out of six candidates and jumped to 32 of
        33 on attempt 1. Runs 55 and 56 asked the identical question of a
        larger graph, drew differently, and got 3. I read that as "not
        reproducible" and reported a model-size conclusion; it was a coin
        toss I had built myself, and it gets worse as the graph grows, because
        every run adds more traces tied at the same score.

        So the tie is broken on the outcome instead: how many tests the attempt
        actually got passing, then recency. `tests_passed` lives in
        `metrics_json`, which complete_trace() writes from TraceOutcome.metrics
        but get_similar_traces() does not carry onto the model (it populates
        metadata with `similarity` alone), hence the second read."""
        traces = await self._client.reasoning.get_similar_traces(
            query, limit=max_traces * 3, success_only=False,
        )
        useful = [
            t for t in traces
            if t.outcome and not str(t.outcome).startswith(self._NO_VERDICT)
        ]
        if not useful:
            return ""
        scores = await self._trace_scores([t.id for t in useful])
        useful.sort(
            key=lambda t: (
                scores.get(t.id, 0.0),
                t.started_at.timestamp() if t.started_at else 0.0,
            ),
            reverse=True,
        )
        useful = useful[:max_traces]
        parts = ["### Similar Past Tasks"]
        for t in useful:
            parts.append(f"\n**Task**: {t.task}")
            parts.append(f"- Similarity: {t.metadata.get('similarity', 0):.2f}")
            # Ordered best-first on this, so say what it is. Similarity above is
            # ~1.00 for every row (see the docstring) and carries no ranking
            # information; without this the list looks arbitrary, because
            # until now it was.
            parts.append(f"- Tests passing after this attempt: {scores.get(t.id, 0):.0f}")
            parts.append(f"- Outcome: {t.outcome}")
            if t.success is not None:
                parts.append(f"- Success: {'Yes' if t.success else 'No'}")
        return "\n".join(parts)

    async def _trace_scores(self, trace_ids: list) -> dict:
        """HAND-ROLLED STANDIN -- tests_passed per trace, for ranking only.

        Reads `metrics_json`, which the package's own complete_trace() writes
        from TraceOutcome.metrics. get_similar_traces() does not carry it onto
        ReasoningTrace, so there is no package call that returns it alongside
        the traces being ranked.

        Goes through client.query.cypher(), the package's supported read-only
        Cypher surface and the one behind its `graph_query` MCP tool -- not
        client.graph.execute_read(), which is a _DeprecatedGraphProxy."""
        if not trace_ids:
            return {}
        records = await self._client.query.cypher(
            "MATCH (rt:ReasoningTrace) WHERE rt.id IN $ids "
            "RETURN rt.id AS id, rt.metrics_json AS m",
            {"ids": [str(i) for i in trace_ids]},
        )
        out: dict[UUID, float] = {}
        for r in records:
            try:
                out[UUID(r["id"])] = float(json.loads(r["m"] or "{}").get("tests_passed", 0))
            except (ValueError, TypeError, json.JSONDecodeError):
                out[UUID(r["id"])] = 0.0
        return out

    async def start_trace(self, session_id: str, task: str):
        return await self._client.reasoning.start_trace(
            session_id=session_id, task=task, user_identifier=self.user_identifier,
        )

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
        return await self._client.reasoning.complete_trace(
            trace_id, outcome=outcome, success=success,
            generate_step_embeddings=generate_step_embeddings,
        )

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

    async def add_message(self, session_id: str, role: str, content: str):
        """No extraction_mode/generate_embedding override -- an earlier
        revision passed extraction_mode='skip' and generate_embedding=False
        here, both untested guesses about what the extractor pipeline or
        embedding cost would do. Removed; this now matches
        memory_agent_mvp.py's own add_message call exactly and just takes
        whatever neo4j-agent-memory's own defaults are."""
        return await self._client.short_term.add_message(
            session_id, role, content, user_identifier=self.user_identifier,
        )

    async def prior_traces(self, task: str, limit: int = 3) -> list:
        """No success_only/threshold override -- an earlier revision passed
        success_only=False and a custom threshold, second-guessing both the
        library's own default (success_only=True) and
        memory_agent_mvp.py's own `how_did_i_handle`, which passes neither.
        Reverted to match."""
        return await self._client.reasoning.get_similar_traces(task, limit=limit)
