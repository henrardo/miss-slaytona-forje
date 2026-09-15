# neo4j-agent-memory — architectural reference

Written 2026-09-13 after getting this wrong twice. Everything below is verified
against one of three authoritative sources, cited inline:

- **PKG** — the installed package, `.venv/lib/python3.11/site-packages/neo4j_agent_memory/`, version **0.5.0** (matches the current PyPI release, 0.5.0, released 2026-05-30).
- **WS** — the GraphAcademy workshop code at `/Users/t6w652j6ft/Documents/GitHub/workshop-agent-memory-scripts/`, in particular `memory_agent_mvp.py` and `solutions/4_reasoning/agent.py`.
- **GH** — <https://github.com/neo4j-labs/agent-memory> README.

Nothing here is inferred. If a thing is not in one of those three, it does not
exist and must not be written.

---

## 0. The two mistakes to never repeat

**Mistake 1 — inventing functions.** This repo once shipped
`harness/memory_mcp_server.py` exposing `record_pattern`, `known_patterns`, and
`recall_similar_migrations`. **None of those are neo4j-agent-memory functions.**
They were invented. The real surface is section 3 below; it is complete, and
every capability the demo needs is already in it.

**Mistake 2 — confusing NAMS with the library.** They are different products.

| | this project uses | this project does **not** use |
|---|---|---|
| Name | `neo4j-agent-memory`, the Python library | NAMS — Neo4j Agent Memory Service |
| Where | `pip install neo4j-agent-memory`, in-process | hosted at `https://memory.neo4jlabs.com` |
| Storage | Neo4j over Bolt — here, the Docker container `miss-slaytona-forje-neo4j` (neo4j:5.26-community) on `bolt://localhost:7688` | per-workspace Neo4j Aura, provisioned by the service |
| Auth | Neo4j username/password | a `nams_…` bearer API key |
| Config | `MemorySettings(backend="bolt", neo4j=Neo4jConfig(...))` | `MemorySettings(backend="nams", nams=NamsConfig(api_key=...))` |

> **The trap, and it is a real one.** `MemorySettings.backend` defaults to
> `None`, and the `_resolve_backend` validator (PKG `config/settings.py:742-779`)
> then does:
>
> ```python
> env_api_key = os.environ.get("MEMORY_API_KEY")
> if env_api_key and self.nams.api_key is None:
>     self.nams.api_key = SecretStr(env_api_key)
> ...
> if self.backend is None:
>     self.backend = "nams" if self.nams.api_key is not None else "bolt"
> ```
>
> A bare `MEMORY_API_KEY` anywhere in the environment silently reroutes every
> memory call away from the local Docker Neo4j and into the hosted service.
> **Always pass `backend="bolt"` explicitly.** It costs one keyword argument
> and removes the failure mode entirely.
>
> (Checked 2026-09-13: `MEMORY_API_KEY` is not currently set in this repo's
> `.env` or shell, so no run to date actually hit NAMS — but nothing was
> stopping it.)

---

## 1. The shape of the integration

There is exactly one demonstrated integration shape, and it is **in-process
library calls from the host application**, not an MCP server.

WS `memory_agent_mvp.py` — the finished reference agent — never registers an MCP
server. It opens a client and calls it:

```python
async with MemoryClient(memory_settings) as memory:
    ...
```

The host owns the client. The agent framework (pydantic-ai there, Mistral Vibe
here) knows nothing about memory. Memory attaches at four points in the turn
loop:

| # | When | Call | WS reference |
|---|---|---|---|
| 1 | before the turn | `short_term.add_message(session, "user", text, user_identifier=…)` | `memory_agent_mvp.py` main loop |
| 2 | before the turn | `reasoning.start_trace(session_id=…, task=…, user_identifier=…)` | same |
| 3 | during the turn | `get_context(query, session_id=…)` spliced into the prompt; each tool call reported via `reasoning.add_step` + `reasoning.record_tool_call` | `what_you_remember`, `report_step` |
| 4 | after the turn | `short_term.add_message(session, "assistant", answer)` and `reasoning.complete_trace(trace_id, outcome=…, success=…)` | main loop, both branches of the try/except |

Point 3 is the one worth internalising. `what_you_remember` is a **dynamic
system prompt** — the framework calls it on *every* turn, unconditionally. The
model does not decide to consult memory. Retrieval is the host's job; the model
only ever sees text.

```python
@agent.system_prompt
async def what_you_remember(ctx: RunContext[AgentDeps]) -> str:
    if ctx.deps.current_query is None:
        return ""
    context = await ctx.deps.memory_client.get_context(
        ctx.deps.current_query, session_id=ctx.deps.session_id,
    )
    return f"What you remember:\n{context}"
```

The agent-callable tools in WS (`search_messages`, `how_did_i_handle`,
`save_fact`, …) are a *supplement* to that, for a frontier model (the MVP runs
`gpt-5.2`) that can be trusted to reach for them. They are not the mechanism.

### The MCP server exists, but it is a different consumption model

`neo4j-agent-memory mcp serve` (PKG `mcp/server.py`, `[mcp]` extra) is real and
correct — it is how you give **Claude Desktop / Claude Code / Cursor** memory.
Its tools, verified in PKG `mcp/_tools.py`:

- `--profile core` (6): `memory_search`, `memory_get_context`, `memory_store_message`, `memory_add_entity`, `memory_add_preference`, `memory_add_fact`
- `--profile extended` (default): the above plus `memory_get_conversation`, `memory_list_sessions`, `memory_get_entity`, `memory_export_graph`, `memory_create_relationship`, `memory_start_trace`, `memory_record_step`, `memory_complete_trace`, `memory_get_observations`, `memory_set_entity_feedback`, `memory_get_entity_history`, `memory_get_entity_provenance`, `memory_get_reflections`

That server is for *an assistant you are chatting with*. It is the wrong tool
for a harness you control the loop of — see `AGENT-MEMORY-SPEC.md` §2 for why it
was removed from this project specifically.

---

## 2. Configuration

Canonical shape, GH README:

```python
settings = MemorySettings(
    neo4j={"uri": "bolt://localhost:7687", "password": "your-password"},
    llm="anthropic/claude-3-5-sonnet-latest",
    embedding="openai/text-embedding-3-small",
)
```

`embedding` and `llm` accept three shapes (PKG `config/settings.py:601-616`):

1. **provider string** — `"openai/text-embedding-3-small"`. Canonical since 0.3.0. Use this.
2. a constructed `EmbeddingProvider` / `LLMProvider` instance.
3. legacy `EmbeddingConfig(api_key=…)` / `LLMConfig(...)` — **emits a `DeprecationWarning`**, documented for removal in 0.5.0 (the installed version). WS still uses this shape; the workshop predates the string form. Don't copy it.

Other config objects worth knowing (all exported from `neo4j_agent_memory.config`):

- `Neo4jConfig(uri=, username=, password=SecretStr(...))`
- `ExtractionConfig(extractor_type=ExtractorType.LLM, entity_types=[...])` — controls the entity-extraction pipeline that runs on stored messages. spaCy → GLiNER → LLM, cheapest to most accurate.
- `MemoryConfig` — `multi_tenant` (forces `user_identifier=` on every call that accepts it), `write_mode="sync"|"buffered"`, `message_embedding_enabled`, `trace_embedding_enabled`.
- `SearchConfig`, `ResolutionConfig`, `EnrichmentConfig`, `GeocodingConfig`.

### Embedding dimensions are bound to the vector indexes

The vector indexes are created at the embedder's dimension on first connect
(PKG `__init__.py`, `_connect_bolt` → `SchemaManager(vector_dimensions=…)` →
`validate_vector_index_dimensions`). Change embedder, and every client — the
library *and* `mcp serve` — refuses to start:

```
EmbeddingDimensionMismatchError: Index 'entity_embedding_idx': expected 1536, found 384
```

Indexes must be dropped and recreated (`scripts/reset_memory_indexes.py` in this
repo). sentence-transformers/all-MiniLM-L6-v2 = 384; OpenAI
text-embedding-3-small = 1536. **Pick one and never change it mid-project.**

---

## 3. The API surface — complete, as of 0.5.0

Everything reachable from `MemoryClient`. Signatures taken from PKG; the
"✔ WS" column marks what the workshop demonstrates.

### `MemoryClient` (PKG `__init__.py:341`)

| Member | Notes | ✔ WS |
|---|---|---|
| `async with MemoryClient(settings) as memory:` | canonical; `connect()`/`close()` also public | ✔ |
| `await memory.get_context(query, *, session_id=None, include_short_term=True, include_long_term=True, include_reasoning=True, max_items=10) -> str` | concatenates all three layers into one prompt block | ✔ |
| `await memory.get_stats() -> dict` | counts per memory type | |
| `memory.short_term` / `.long_term` / `.reasoning` | the three layers | ✔ |
| `memory.query` | `await memory.query.cypher(q, params)` — read-only, validated | ✔ |
| `memory.users`, `memory.buffered`, `memory.consolidation`, `memory.eval` | bolt-only accessors | |
| `memory.ontology` | NAMS-only; a `_NamsUnsupported` sentinel on bolt | |

### Short-term — conversation (PKG `memory/short_term.py`)

| Method | ✔ WS |
|---|---|
| `add_message(session_id, role, content, *, user_identifier=None, ...) -> Message` | ✔ |
| `add_messages_batch(...)` | ✔ |
| `search_messages(query, *, session_id=None, limit=10, threshold=0.7) -> list[Message]` | ✔ |
| `get_conversation(session_id, limit=…) -> Conversation` | ✔ |
| `get_conversation_summary(...)` — LLM-backed | ✔ |
| `get_context(query, *, session_id=None, max_messages=10) -> str` | ✔ |
| `list_sessions(...)`, `clear_session(session_id)`, `delete_message(...)` | ✔ |
| `extract_entities_from_session(...)`, `generate_embeddings_batch(...)` | ✔ |

> `short_term.get_context(session_id=X)` returns **the last `max_messages`
> messages of session X verbatim**, plus a semantic search over messages that is
> *not* session-scoped (PKG `short_term.py:860-894`). Whatever you put in with
> `add_message` comes back out in full. Store answers, never transcripts.

### Long-term — knowledge graph, POLE+O (PKG `memory/long_term.py`)

Entity types: `PERSON`, `ORGANIZATION`, `LOCATION`, `EVENT`, `OBJECT` (+`subtype` for finer classification).

| Method | ✔ WS |
|---|---|
| `add_entity(name, entity_type, *, subtype=, description=, aliases=, attributes=, metadata=, ...) -> tuple[Entity, DeduplicationResult]` — **returns a tuple, not an Entity** | ✔ |
| `add_fact(subject, predicate, obj, *, confidence=1.0, valid_from=, valid_until=, metadata=) -> Fact` | ✔ |
| `add_preference(category=, preference=, user_identifier=, ...) -> Preference` | ✔ |
| `add_relationship(entity_a, entity_b, rel_type) -> Relationship` | ✔ |
| `search_entities(query, *, entity_types=None, limit=10, threshold=0.7) -> list[Entity]` | ✔ |
| `search_facts(query, ...)`, `search_preferences(query, *, category=, limit=10, threshold=0.7)` | ✔ |
| `get_entity_by_name(name) -> Entity \| None` | ✔ |
| `get_related_entities(...)`, `get_entity_relationships(...)`, `get_facts_about(...)`, `get_preferences_for(...)` | ✔ |
| `supersede_preference(...)` | ✔ |
| `find_potential_duplicates(...)`, `review_duplicate(...)`, `merge_duplicate_entities(...)`, `get_deduplication_stats()` | ✔ |
| `get_entity_provenance(...)`, `link_entity_to_message(...)`, `get_extraction_stats()` | |
| `geocode_locations(...)`, `search_locations_near(...)`, `search_locations_in_bounding_box(...)` | |
| `get_context(query, *, include_entities=True, include_preferences=True, max_items=…) -> str` | |

### Reasoning — traces, steps, tool calls (PKG `memory/reasoning.py`)

**The differentiating layer.** Most memory systems have the first two.

| Method | ✔ WS |
|---|---|
| `start_trace(session_id, task, *, generate_embedding=True, metadata=None, triggered_by_message_id=None, user_identifier=None) -> ReasoningTrace` | ✔ |
| `add_step(trace_id, *, thought=None, action=None, observation=None, generate_embedding=True, metadata=None) -> ReasoningStep` | ✔ |
| `record_tool_call(step_id, tool_name, arguments, *, result=None, status=ToolCallStatus.SUCCESS, duration_ms=None, error=None, auto_observation=False, message_id=None, touched_entities=None) -> ToolCall` | ✔ |
| `complete_trace(trace_id, *, outcome=None, success=None, generate_step_embeddings=False) -> ReasoningTrace` | ✔ |
| `get_similar_traces(task, *, limit=5, success_only=True, threshold=0.7) -> list[ReasoningTrace]` | ✔ |
| `search_steps(query, *, limit=10, success_only=True, threshold=0.7) -> list[ReasoningStepWithContext]` | |
| `get_context(query, *, max_traces=3, include_successful_only=True) -> str` | |
| `get_trace_with_steps(trace_id)`, `get_trace(id)`, `get_session_traces(...)`, `list_traces(...)` | ✔ |
| `get_tool_stats(tool_name=None) -> list[ToolStats]` — pre-aggregated, use this | |
| `get_tool_usage_stats(...)` — **deprecated**, use `get_tool_stats` | |
| `link_trace_to_message(...)`, `on_tool_call_recorded(hook)` | |
| `StreamingTraceRecorder` — async CM for long loops: `start_step`, `record_tool_call`, `add_observation`, `set_outcome` | |
| `ProceduralMemory` | back-compat alias for `ReasoningMemory` | |

Three structured types that exist and should be used instead of hand-rolled
equivalents (PKG `schema/models.py:117,157`):

```python
TraceOutcome(
    success: bool,
    summary: str,                       # human-readable
    error_kind: str | None = None,      # INDEXED category, for fast filtering
    related_entities: list[EntityRef] = [],
    metrics: dict[str, float] = {},     # e.g. {"attempt": 3, "tokens": 41022}
)
```
Passing a `TraceOutcome` to `complete_trace(outcome=…)` **overrides** any
`success=` argument.

```python
EntityRef(name=..., type=..., id=..., label=...)   # needs name or id
```

`ToolCallStatus` — enum, `SUCCESS` etc., from `neo4j_agent_memory.memory.reasoning`.

### Cost controls that are already in the API

Do not invent throttling. These exist:

- `add_step(..., generate_embedding=False)` + `complete_trace(..., generate_step_embeddings=True)` — batch the embedding calls at the end instead of one network round-trip per step. The docstring names this exact pattern ("useful when steps were recorded with `generate_embedding=False` during streaming").
- `MemoryConfig(write_mode="buffered", max_pending=200)` + `client.buffered.submit(...)` + `client.flush()` — fire-and-forget writes drained by a background task.
- `MemoryConfig(message_embedding_enabled=False)`, `trace_embedding_enabled=False`.

### `MemoryIntegration` (PKG `integration.py`)

A higher-level facade over `MemoryClient` that owns session-id resolution
(`SessionStrategy`: persistent / per_day / …), auto preference detection, and an
observer hook. `mcp serve --session-strategy` is built on it. Use it when you
*don't* want to manage session ids; skip it when you do.

---

## 4. Graph shape (for writing Cypher against it)

Confirmed from the queries the package itself runs:

```
(:User {identifier})-[:HAS_TRACE]->(:ReasoningTrace)
(:User)-[:HAS_CONVERSATION]->(:Conversation {session_id})-[:HAS_MESSAGE]->(:Message {role, content})
(:ReasoningTrace {session_id, task, outcome, success, started_at, completed_at, user_identifier})
    -[:HAS_STEP]->(:ReasoningStep {step_number, thought, action, observation})
        -[:HAS_TOOL_CALL]->(:ToolCall {tool_name, arguments, result, status, duration_ms, error})
(:ReasoningStep)-[:TOUCHED]->(:Entity)          # from record_tool_call(touched_entities=…)
(:ReasoningTrace)-[:INITIATED_BY]->(:Message)   # from start_trace(triggered_by_message_id=…)
(:Entity {name, type, subtype, description})
(:Fact {subject, predicate, object}), (:Preference {category, preference})
```

Vector indexes exist on entity / message / trace / step / fact / preference
embeddings — six of them, all at the same dimension.

---

## 5. Checklist before touching memory code in any project

- [ ] `backend="bolt"` passed explicitly — no accidental NAMS.
- [ ] `embedding="openai/text-embedding-3-small"` (string form), not `EmbeddingConfig`.
- [ ] Embedding dimension matches the existing vector indexes, or they get dropped first.
- [ ] Every function called appears in §3 above. No exceptions, ever.
- [ ] `add_entity`'s tuple return is unpacked or deliberately discarded.
- [ ] Retrieval is host-driven (a `get_context`-style splice), not dependent on the model choosing a tool.
- [ ] `user_identifier=` passed wherever the API accepts it, if identity matters.
- [ ] Nothing large goes into `add_message` — it comes straight back out via `get_context`.
