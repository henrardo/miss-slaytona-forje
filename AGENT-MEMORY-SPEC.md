# Spec: where agent memory goes in miss-slaytona-forje, and how

Companion to `AGENT-MEMORY-ARCHITECTURE.md`, which is the verified API
reference. This file says where in *this* codebase memory attaches, and why
each placement is the one the package and the workshop actually demonstrate.

Nothing in this spec calls a function that isn't in the architecture doc's §3.

---

## 1. What the demo is measuring

Two 4-agent swarms get the identical prompt — "migrate this codebase from
Pydantic v1 to Pydantic v2" — and 10 minutes. The **warm** swarm shares a
neo4j-agent-memory graph; the **cold** swarm has no contact with Neo4j at all.
Afterwards we compare tokens and completion.

For that comparison to mean anything, exactly one thing has to be true: **a warm
agent must be able to start from what another warm agent already established.**
Everything below serves that sentence.

The unit of shareable knowledge on this task is:

> *"The suite was failing with error **E**. This edit **D** made **E** stop happening."*

That is the thing to store, the thing to retrieve, and the thing the current
implementation stores in the wrong place.

---

## 2. ~~The MCP server comes out~~ — WITHDRAWN, NOT IMPLEMENTED

**This section was wrong. The MCP server stays, and is registered.**

The argument below rested on "agents called a memory tool once in 253 calls, so
small models will not use them". That measurement was never validated. At least
one MCP server in this project was dead on import for an entire run series with
nothing in the output to say so, and I never confirmed the memory server was
alive when I took that number. It is not evidence about the model.

What is implemented instead — both halves, as the workshop does:

* The server, exactly as its README says to register it:
  `uvx "neo4j-agent-memory[mcp,openai]" mcp serve --uri … --password …`.
  The `openai` extra is **required**: `[mcp]` alone leaves the server without an
  embedder and every retrieval tool answers *"OpenAI package not installed"*
  while still appearing healthy and publishing all 16 tools.
* The orchestrator-side deterministic loop of §4–§6, running alongside it as a
  floor under whatever the model chooses to do.

`orchestrator/run.py`'s `preflight()` now starts every registered server and
**calls a real tool**, failing the run before the clock starts if the answer is
an error. Listing a tool never proved the tool worked.

The original reasoning is kept below for the record only. Do not act on it.

Four reasons, in order of weight:

1. **It is not the demonstrated shape.** The workshop's finished agent
   (`memory_agent_mvp.py`) never registers an MCP server. The host process opens
   a `MemoryClient` and calls it directly. The MCP server is the *other*
   consumption model — the one for an assistant you are chatting with, where no
   one owns the loop. Here the orchestrator owns the loop completely.

2. **The model never calls the tools.** Measured on this fixture: across a
   45-minute run the four warm agents made **253 tool calls, of which 1 was a
   memory tool**. `record_pattern` was called **0 times** in every run ever
   measured. Qwen3-8B under `tool_choice: "auto"` does not reach for an optional
   tool, and the target model (Mistral Small 4) is not going to be dramatically
   different in kind. A retrieval path that fires once per 253 opportunities is
   not a retrieval path.

3. **It creates a second writer.** The MCP server builds its *own* `MemoryClient`
   with its own `--session-strategy persistent --user-id warm`, while
   `orchestrator/run.py` holds another one writing under `session_id="warm-0"`.
   Two clients, two identity schemes, one graph, no coordination.

4. **It is where the invented functions came from.** The bespoke
   `harness/memory_mcp_server.py` (`record_pattern`, `known_patterns`,
   `recall_similar_migrations` — none of them real) existed only because an
   embedding-dimension mismatch stopped the package's own server from starting.
   Removing the server removes the pressure to invent a surface for it.

What replaces it: nothing agent-facing. **The agent's only memory interface is
prose in its prompt.** Retrieval is the orchestrator's job, performed
unconditionally before every attempt — exactly what `what_you_remember` does in
the workshop.

> `web_lookup` (`harness/web_search_mcp_server.py`) stays, registered
> identically for both swarms. It is a task capability, not a memory
> capability, and it is outside this spec.

---

## 3. The one place the client is constructed

**[`orchestrator/memory.py`](orchestrator/memory.py) `build_settings()`** — the
only place `MemorySettings` is built, and the only module that imports
`neo4j_agent_memory`.

```python
def build_settings() -> MemorySettings:
    return MemorySettings(
        backend="bolt",
        neo4j=Neo4jConfig(uri=NEO4J_URI, password=SecretStr(NEO4J_PASSWORD)),
        embedding="openai/text-embedding-3-small",
    )
```

Three changes from what's there now, each load-bearing:

- **`backend="bolt"` — add it.** Unpinned, `MemorySettings._resolve_backend()`
  switches to the hosted NAMS service the moment a `MEMORY_API_KEY` appears in
  the environment. NAMS is a different product with a different auth model and
  is not what this demo uses; the memory lives in the Docker container
  `miss-slaytona-forje-neo4j` on `bolt://localhost:7688`. One keyword removes
  the failure mode permanently.
- **`embedding="openai/text-embedding-3-small"` — say it out loud.** Currently
  the field is omitted and the package default is relied on. The default happens
  to be right, but the 1536-dimension choice is bound into six vector indexes
  and was the direct cause of the `EmbeddingDimensionMismatchError` that spawned
  the bespoke MCP server. Something that consequential is stated, not inherited.
  The provider-string form is canonical (GH README); `EmbeddingConfig` is the
  deprecated legacy shape and must not come back.
- **No `ExtractionConfig`.** The default extractor stays. The entity-extraction
  pipeline looks for POLE+O entities — people, orgs, places — and a pytest
  traceback contains none. Turning on `ExtractorType.LLM` (as the workshop does,
  for a corpus of human introductions) would spend an LLM call per stored
  message inside the measured 10-minute window to extract nothing. The long-term
  layer is not where this task's knowledge lives; §5 explains where it does.

`ScopedMemory` stays as the warm-only wrapper. Cold agents keep `mem=None`
threaded through the entire call chain — no reads, no writes, no trace nodes.
That part of the current design is correct and should not be touched.

---

## 4. Where memory attaches in the loop

The workshop's four attachment points map onto
[`orchestrator/vibe_agent.py`](orchestrator/vibe_agent.py) `migrate_codebase()`
with one substitution: **a "turn" is one attempt of the `while True` loop**
(`vibe_agent.py:622`).

| WS | here | call site |
|---|---|---|
| user turn | the task prompt for this attempt | top of the attempt |
| `start_trace` | one trace per attempt | top of the attempt |
| `what_you_remember` | `memory_context` spliced into `_task_prompt()` | top of the attempt |
| `report_step` | `_replay_session_messages()` over Vibe's `messages.jsonl` | after the Vibe subprocess exits |
| assistant turn | the attempt's outcome | after the Daytona check |
| `complete_trace` | the Daytona pytest verdict | after the Daytona check |

One substitution is a genuine **improvement** over the workshop and should be
stated as such: the workshop closes its trace with `success=True` unless the
agent raised — the agent's own say-so. Here, `complete_trace` is driven by an
**independent pytest run in a fresh Daytona sandbox**. The trace's success flag
is ground truth. That is the strongest version of reasoning memory this demo can
have, and it is worth saying on stage.

The post-hoc replay of `messages.jsonl` is also correct and stays. We don't own
Vibe's inner loop the way the workshop owns pydantic-ai's, but Vibe's own
session transcript carries every message and every tool call, so nothing is
lost — it just lands after the attempt rather than during it.

---

## 5. The core change: the trace is keyed on the error, not the task

This is the substantive fix, and everything else is housekeeping.

### What's wrong now

`migrate_codebase()` opens the trace with
`task=f"Migrate this codebase from pydantic v1 to v2 (attempt {attempt})"`
([`vibe_agent.py:670`](orchestrator/vibe_agent.py#L670)). That string is what
gets embedded, and it is therefore what `get_similar_traces()` matches against.
Every trace in the graph has effectively the same task, so trace similarity
carries no information — it retrieves a random successful attempt, or with
`success_only=True` and a suite that never goes green, nothing at all.

Having found that the traces were useless, the code worked around it by
inventing a parallel store: `commit_pattern()` writes the fix as
`add_entity(name, "OBJECT", subtype="BREAKAGE_PATTERN", description=<diff>)`
([`memory.py:201-209`](orchestrator/memory.py#L201-L209)) and `known_patterns()`
reads it back with `search_entities()`. Both are real API calls, but they are
the wrong layer: `OBJECT/BREAKAGE_PATTERN` is not a POLE+O entity, and
reasoning memory — the package's own differentiating feature, the layer this
demo exists to show off — sits unused beside it holding the same information in
a shape nobody queries.

### What it becomes

**Key the trace on the failure the attempt is actually working against.**

```python
# attempt 1 has no prior failure; from attempt 2 on, `last_signature` is
# error_signature() over the previous attempt's real pytest output.
trace_task = last_signature or "pydantic v1 to v2 migration: initial state"
trace = await mem.start_trace(session_id, task=trace_task)
```

`error_signature()` ([`vibe_agent.py:493`](orchestrator/vibe_agent.py#L493))
already produces exactly the right string — the first `E  SomeError: message`
line with paths, addresses and numbers stripped. It stays as-is.

**Close the trace with a `TraceOutcome`, not a bare string.**

```python
resolved = advanced or success   # this attempt cleared the error it was given
await mem.complete_trace(
    trace_id,
    outcome=TraceOutcome(
        success=resolved,
        summary=observed_fix_summary or ("suite passed" if success else "no change"),
        error_kind=trace_task,
        metrics={"attempt": float(attempt)},
    ),
    generate_step_embeddings=True,
)
```

`success` on the trace now means **"this attempt resolved the error it was
handed"**, not "the whole migration finished". That single redefinition is what
makes `get_similar_traces(..., success_only=True)` — the library default, and
what the workshop passes — start returning useful rows. The old definition made
the default filter reject everything, which is why the code was reaching for
overrides and a parallel entity store.

Suite-level completion is not lost: it is `MigrationResult.success`, reported by
`run.py`'s summary. Those are two different questions and they get two different
records.

`advanced` ([`vibe_agent.py:740`](orchestrator/vibe_agent.py#L740)) is already
the right predicate — the orchestrator's own independent test run moved onto a
*different* failure, so the previous one is demonstrably gone. It keeps its
existing meaning.

`observed_fix()` ([`vibe_agent.py:525`](orchestrator/vibe_agent.py#L525)) keeps
its diffing logic but stops returning a `(name, description)` pair for
`add_entity`. It returns the unified diff, which becomes `TraceOutcome.summary`.

**Retrieve by the error the agent is facing right now.**

```python
async def prior_fixes(self, error_signature: str, limit: int = 3) -> list:
    exact = await self._client.query.cypher(
        """
        MATCH (rt:ReasoningTrace)
        WHERE rt.error_kind = $sig AND rt.success = true
        RETURN rt.task AS task, rt.outcome AS outcome
        ORDER BY rt.completed_at DESC LIMIT $limit
        """,
        {"sig": error_signature, "limit": limit},
    )
    if exact:
        return exact
    return await self._client.reasoning.get_similar_traces(error_signature, limit=limit)
```

Exact match first because agents on an identical fixture hit *byte-identical*
error signatures — a vector search is the wrong instrument for a string two
agents both have verbatim. `complete_trace` writes `error_kind` as a top-level,
index-friendly property for precisely this. `get_similar_traces` is the fallback
for a failure that is merely *similar* to one already solved, which is the more
impressive half of the demo and the half that actually needs embeddings.

`query.cypher` is the package's own read-only-validated Cypher accessor and is
used this way in `memory_agent_mvp.py` (`find_similar_attendees`). Not a raw
driver call, not a bypass.

**Delete** `ScopedMemory.commit_pattern`, `ScopedMemory.known_patterns`,
`_read_pending_patterns()`, `pending_patterns_file_for()`, and every
`pending_patterns_file` parameter threaded through `run.py` and `vibe_agent.py`.
That whole apparatus existed to serve a tool the model never called.

---

## 6. What goes into short-term memory

Currently `migrate_codebase()` calls
`mem.add_message(session_id, "assistant", vibe_output)`
([`vibe_agent.py:697`](orchestrator/vibe_agent.py#L697)) — `vibe_output` is the
subprocess's entire stdout+stderr. And `_replay_session_messages()` adds every
assistant message from the transcript on top of that.

`short_term.get_context(session_id=X)` returns the last 10 messages of session X
**verbatim**. So the transcript goes in and comes straight back out into the next
attempt's prompt, on a model with a 32,768-token window. This is the mechanism
behind the context-overflow 400s that cost cold-3 fifty-eight attempts, and it
is why `_replay_session_messages` needed a special case to skip user-role
messages to stop the memory block nesting inside itself.

**Store the outcome, not the transcript.** The workshop stores
`str(result.output)` — one answer, not a log.

```python
await mem.add_message(session_id, "user", trace_task)
...
await mem.add_message(
    session_id, "assistant",
    f"attempt {attempt}: {'suite passed' if success else signature or 'no change'}",
)
```

And **turn short-term off in the prompt splice**:

```python
dynamic_context = await mem.get_context(
    trace_task, session_id=session_id, include_short_term=False,
)
```

`include_short_term` is a real `get_context` parameter. An agent re-reading its
own previous prompts is pure token cost — it is the *other* agents' reasoning
traces that carry information, and those come through the reasoning section,
which is not session-scoped. Short-term stays populated (it is the record of
what happened, and `search_messages` can still reach it), it just stops being
echoed back into every prompt.

The user-role skip in `_replay_session_messages`
([`vibe_agent.py:428`](orchestrator/vibe_agent.py#L428)) can then be dropped —
it was compensating for this.

---

## 7. Cost: stop paying an embedding per tool call

`_replay_session_messages()` calls `add_step()` once per Vibe tool call, each
with `generate_embedding=True` (the default) — one OpenAI round-trip per step,
on the shared asyncio event loop. A run with 576 tool calls means 576 blocking
network calls in the warm arm, and because both swarms share one event loop,
**warm's memory latency lands on cold's wall clock**. That contaminates the exact
comparison this demo exists to make.

The package ships the fix and names it in the docstring:

```python
step = await mem.add_step(trace_id, thought=..., action=..., generate_embedding=False)
...
await mem.complete_trace(trace_id, outcome=..., generate_step_embeddings=True)
```

Steps are written immediately with no embedding; `complete_trace` batches them
once at the end. `ScopedMemory.add_step` gains a `generate_embedding` passthrough
and `complete_trace` gains `generate_step_embeddings`.

Trace-task and message embeddings stay synchronous — there is one of each per
attempt, not one per tool call.

---

## 8. Identity

| | value | why |
|---|---|---|
| `session_id` | `f"{swarm}-{agent_id}"`, e.g. `warm-2` | one conversation per agent; short-term is per-agent by construction |
| `user_identifier` | `"warm"`, shared by all four | `start_trace(user_identifier=…)` hangs every trace off one `(:User {identifier:"warm"})`; that shared node **is** the swarm |

Unchanged from the current implementation, which got this right. Stated here
because it is the whole warm premise and must not drift: short-term is private,
long-term and reasoning are shared, and sharing happens because traces are not
session-filtered — `get_similar_traces` and the `error_kind` lookup both search
the graph, not the session.

`multi_tenant` stays `False` (the default). Turning it on would force
`user_identifier=` on every accepting call and buy nothing in a two-tenant demo.

---

## 9. What changes, by file

| File | Change |
|---|---|
| `orchestrator/memory.py` | `build_settings()`: add `backend="bolt"`, `embedding="openai/text-embedding-3-small"`. `ScopedMemory`: delete `commit_pattern`, `known_patterns`; rename `prior_traces` → `prior_fixes` with the exact-then-vector lookup of §5; add `TraceOutcome` support to `complete_trace`; add `generate_embedding` / `generate_step_embeddings` passthroughs; add `include_short_term` passthrough on `get_context`. |
| `orchestrator/vibe_agent.py` | `render_config()`: delete the MCP block (L178-237) and its two parameters. `migrate_codebase()`: trace task = error signature (§5); `TraceOutcome` on completion; `prior_fixes` retrieval; short outcome messages (§6); `generate_embedding=False` on replayed steps (§7); delete `_read_pending_patterns` and the pending-patterns plumbing. `observed_fix()` returns a diff string, not a `(name, description)` pair. `_replay_session_messages()`: drop the user-role skip. |
| `orchestrator/run.py` | Delete `MEMORY_TOOL_HINT` and the `tool_hint` argument — there are no memory tools to hint at. Delete `pending_patterns_file_for()` and its call sites. Drop `memory_user_identifier` / `memory_pending_patterns_file` from the warm `render_config()` call. Add `pending_patterns.jsonl` removal from `seed_repo`'s `.gitignore`. |
| `harness/memory_mcp_server.py` | Already deleted. Stays deleted. |
| `scripts/reset_memory_indexes.py` | Unchanged — still the correct tool if the embedder ever changes. |

---

## 10. How this gets verified before it is called done

In order. No step is skipped and no result is reported from inference.

1. **Unit, no GPU.** Open a `MemoryClient` against the Docker Neo4j; write a trace with `task=<a real error signature>`, `TraceOutcome(success=True, error_kind=<same>, summary=<a diff>)`; then read it back through both `prior_fixes` paths. Assert the exact-match arm returns it and the vector arm returns it for a *paraphrased* signature.
2. **Two agents, no swarm.** One warm agent, 120 s, `--reset-memory`. Assert in Neo4j: `ReasoningTrace` nodes whose `task` is an error signature (not the generic sentence), non-null `error_kind` on the resolved ones, `ReasoningStep` children with embeddings, and `(:User {identifier:"warm"})-[:HAS_TRACE]->` on all of them.
3. **Prompt inspection.** Capture the literal prompt string of a second attempt. Assert it contains a retrieved prior fix, contains no nested "What you remember" block, and is under a stated token bound.
4. **Cold isolation.** After any run: zero nodes in Neo4j carry `user_identifier = "cold"`, and zero `Conversation` nodes have a `cold-*` session id.
5. **Full warm-vs-cold, 600 s.** Only after 1-4 pass. Report the token ratio *with* the completion counts and the containment check, and report it as one run, not as a result.

**Nothing is called working until step 5 has run end to end and the numbers have
been read.** No exceptions — the last three runs each produced a token ratio
that turned out to be an artifact of a bug rather than a memory effect.

---

# 11. Findings after implementation (runs 25-33, 2026-09-14)

Everything above was written before the loop ran end to end. This section is
what the runs actually showed, and it changed several conclusions.

## 11.1 The oracle was weaker than the task

Two independent holes, both found by testing the fixture directly rather than
reasoning about it.

**A pure `pydantic.v1` shim scores 32 of 33.** Rewriting every
`from pydantic import ...` to `from pydantic.v1 import ...` -- which migrates
nothing -- passes all but `test_default_checker`. The tests came from the
post-migration commit but never call a v2-only API, so they cannot see the
difference. Any result quoted at "32/33" is therefore indistinguishable from a
shim, including the "best ever" result this project cited for several days.
Closed by `v1_shim_files()` in orchestrator/vibe_agent.py, which overrides a
green suite, forces `passed` to 0 so a shimmed attempt can never reach shared
memory, and tells the agent in the fed-back pytest output. Verified against a
shimmed tree (flags all four files), the pristine fixture (clean) and
`fixture/reference_v2/` (clean).

**`@validator` and `class Config` can be left in v1 form and the suite still
passes 33/33.** The designed mitigation was `fixture/pytest.ini` with
`filterwarnings = error::DeprecationWarning`. That file no longer exists and
**must not be restored**: under pydantic 2.13.5 it makes `reference_v2` itself
fail at collection, because 2.12 deprecated `@model_validator(mode="after")`
on a classmethod. The fixture is a genuine three-file migration gated on the
changes that hard-fail -- `BaseSettings`, bare `@root_validator`,
`EmailStr.validate()` -- and is not exhaustive beyond that. Known and accepted.

## 11.2 Retrieval was never the expensive half

Warm agents were completing a fraction of cold's attempts, and the cause was
the write path. `short_term.add_message()` runs spaCy -> GLiNER -> LLM and
merges; `neo4j-agent-memory[gliner]` was not installed, so every stored message
fell through to the LLM stage -- two OpenAI round-trips, since the first
returns 400 and is retried.

| configuration                   | per message |
|---------------------------------|-------------|
| defaults (spacy + gliner + llm) | 2071 ms     |
| `enable_llm_fallback=False`     |  289 ms     |

At ~50 messages per attempt: ~103s against ~14s. Run 30 cost warm 1 completed
attempt against cold's 17. After installing gliner and setting
`ExtractionConfig(enable_llm_fallback=False)` in `build_settings()`, warm ran
8 attempts and became the cheaper arm per attempt. POLE+O typing survives --
check with `labels(e)`, not `labels(e)[0]`, which is always `Entity`.

## 11.3 The agent could not check its own work

Every iteration cost a full Vibe turn plus a Daytona round-trip, so an agent
spent an entire attempt to learn one error, against a chain five fixes long.
Agents now get `AGENT_VENV` -- built from the fixture's own
`requirements-v2.txt` -- and are told to run

    python -m pytest tests -q -x --tb=short 2>&1 | tail -30

The `2>&1 | tail` is load-bearing twice over: pytest writes collection errors
to stderr, and Vibe wraps any non-zero exit as `<tool_error>`, so the bare
command gave agents an empty result and a Pluggy warning instead of the real
failure. Grading is unchanged -- Daytona alone decides success.

This is what produced the first genuine `success=True` trace in the series:
run 32's warm-2 reached **31 of 33 passing on attempt 1**, with the shim check
active.

## 11.4 Isolation was nominal

Agents inherited `env = dict(os.environ)`: `DAYTONA_API_KEY`,
`OPENAI_API_KEY`, `MISTRAL_API_KEY`, and a `VIRTUAL_ENV` pointing at the
orchestrator's venv with `neo4j`, `daytona` and `neo4j_agent_memory` all
importable. "Cold has zero Neo4j contact" held only because no cold agent
tried. Now stripped in `_run_vibe` (not in `render_config`, which legitimately
needs `OPENAI_API_KEY` for `vibe mcp add --env`), and verified.

## 11.5 What the numbers can and cannot support

Variance across runs currently exceeds the warm/cold difference: warm reached
31 tests passing in run 32 and 0 in run 33 on identical configuration. **No
single run separates the arms**, and `token_ratio` on its own is misleading --
run 28's 1.543 read as a 35% saving for warm while warm had made 71 LLM calls
to cold's 132. The summary now also prints `errors cleared`, `best tests
passing`, attempts, and tokens per attempt, and a series of runs is the unit of
measurement rather than any one run.

---

# 12. The warm arm's overhead, traced to the end (runs 44-52)

§11.5 said variance exceeded the warm/cold difference. That stopped being true
once the harness stabilised: across runs 44-47 cold completed 21-28 attempts
per run and warm 8-10, every run, same direction. That is a real effect and
this section is what it turned out to be. Four separate causes, each found by
measuring rather than reasoning, and each one wrong about the next.

## 12.1 It was not the embedder

`add_message` runs the extraction pipeline, so the obvious suspect was the
OpenAI embedding round-trip. Switching to a local embedder
(`BAAI/bge-small-en-v1.5`) cut `add_message` from 336 ms to 142 ms -- and made
the full replay *worse*, 500 -> 591 ms per message. The isolated benchmark did
not reflect reality.

Two things nearly went wrong here and are worth keeping:

* `generate_embedding=False` looks like the obvious fix and silently disables
  **entity extraction** as well. Verified: embed on gives entities
  `['conference','Tuesday','Berlin']`, embed off gives `[]`. It would have
  emptied the POLE+O graph while the timing improved.
* This module's own `HF_HUB_OFFLINE` note records a local embedder once
  hanging on a Hub request and freezing an entire run, cold agents included.
  Re-enabling one is safe only because the model is pre-cached and because the
  package runs `model.encode` through `loop.run_in_executor` -- checked in its
  source, since a blocking embedder would put warm's latency on cold's
  wall-clock and invalidate the comparison.

The local embedder was kept anyway: no outbound call per stored message is the
right default for a conference demo. It was simply not the fix.

## 12.2 It was message size

Profiling the three replay operations gave `add_message` 142 ms, `add_step`
5 ms, `record_tool_call` 6 ms -- which cannot produce 591 ms. Extraction cost
scales with text length (140 ms at 100 chars, 381 ms at 2,000, 644 ms at
8,000), and one warm attempt stored 45 messages totalling **492,928
characters**, with `role: "tool"` results reaching 21,410 each. Those were
already stored a second time, capped, as the owning step's `observation`.

Capping stored message content took the replay from 68.6s to 20.2s (591 ->
174 ms/message) with the graph shape unchanged. This is the same defect
`_replay_session_messages`'s docstring already records -- an earlier revision
stored the whole Vibe stdout as one message; splitting per message fixed the
blob but never bounded the pieces.

## 12.3 It was not the replay either

Overlapping the replay with the Daytona check, the local embedder and the
content cap together took memory work from ~68s to ~20s per attempt -- and
warm's attempt count did not move: 8, 9, 8, 8 across runs 44/48/49/50.

The per-attempt arithmetic found the real constraint:

    warm  33 LLM calls/attempt | 12,838 prompt tokens per call
    cold  21 LLM calls/attempt | 11,336 prompt tokens per call
    AUTO_COMPACT_THRESHOLD = 12000

Warm sat just above the compaction threshold and cold just below it, so warm
compacted on 18.1% of its messages against cold's 10.6%. The retrieved-memory
block is what pushes it over -- warm was paying a compaction tax for carrying
the thing being measured. The threshold's own justification (room for a long
tool result) predated `_trim_error_for_prompt`, which bounds the fed-back
pytest output at 6,000 characters where it used to arrive at 43,000. Raised to
18,000; run 51 took warm 8 -> 10 attempts and cold 17 -> 27.

## 12.4 Retrieval was returning empty rows

Run 51's prompts showed the two highest-similarity traces (0.86, 0.85)
rendering as a bare error name and a similarity score and nothing else.

Agents run concurrently against one graph, so a sibling mid-attempt has a
trace with a task and an embedding but no outcome yet -- and it ranks at the
top precisely because it is keyed on the error the asking agent is looking at
right now. Traces closed with "ran out of time mid-attempt" are the same kind
of nothing. `ScopedMemory._reasoning_context` now reproduces the package
formatter's output and drops both (labelled as a standin; the package's
formatter cannot filter what it has no reason to expect).

## 12.5 What is still true

Warm still completes fewer attempts than cold and reaches less far. After all
of the above, warm takes ~27 LLM calls per attempt against cold's ~10 --
carrying the memory block makes each attempt longer in agent turns, not just
in memory work, and on this model that has not converted into progress. That
is the honest state of the comparison, and it is a finding about a 8B model
with a 32k window, not a proven property of graph memory.

## 12.6 CORRECTION: `errors_cleared` is biased, and the arms are tied

§12.5 said warm "reaches less far". That reading came from `errors_cleared`,
and it is wrong.

Run 52, warm vs cold, whole run:

    tool calls      203  vs  232
    assistant turns 208  vs  255
    attempts          9  vs   26
    turns per attempt 23  vs   10

The two swarms do nearly the same amount of work. What differs is attempt
*length*: a Vibe turn ends when the model emits a text-only message, and cold
stops sooner, so cold cycles through the Daytona check far more often.

`errors_cleared` counts distinct pytest error signatures seen across attempts,
so an agent making 26 short attempts encounters more signatures than one
making 9 long attempts even when both finish in the same state. The metric
rewards frequent verification, not progress. It was added in §11.5 to be more
honest than `token_ratio` and carries its own bias.

On `best_tests_passing`, which is not bias-prone, the arms are tied:

    run 48  warm 3  cold 3
    run 50  warm 2  cold 2
    run 51  warm 3  cold 3
    run 52  warm 3  cold 3

**The honest statement: warm and cold reach the same result, warm with
slightly fewer LLM calls and fewer, longer attempts.** Shared memory is
currently neutral on this task at this model size -- not harmful, as the
attempt counts alone suggested, and not yet demonstrated to help.

Any future metric added here should be checked for the same failure: does it
measure the outcome, or does it measure how often the agent happened to stop?

---

# 13. Two defects behind the "model-bound" conclusion

§11 and §12 ended by attributing the remaining gap to model size. That
conclusion was reached with two architecture defects still open, both of which
had to be ruled out first and neither of which had been looked at. This section
is the correction.

## 13.1 The best result ever recorded was the agent deleting code

Run 54's warm-2 scored **32 of 33 on attempt 1** and was reported as verified,
shim-free progress. It was neither. The agent hit a `@root_validator` it could
not port and stubbed it:

```diff
-    @root_validator
-    def validate_alternative_body(cls, values):
+    @model_validator(mode='after')
+    def validate_alternative_body(self, values):
+        return values
         """            <- original docstring and body now unreachable
```

`return values` fires immediately. The function still imports, keeps its name,
and carries a v2 decorator, so 32 tests pass. The 33rd is the only test that
exercises what the validator was *for* (`assert 'alternative' is None`), which
is why the failure read as an ordinary behavioural remainder rather than the
symptom of a deleted body. Ground truth (`reference_v2/fastapi_mail/schemas.py`
lines 96-101) keeps the logic.

`v1_shim_files()` did not fire, correctly -- this is a second, independent
hole. The error was treating "the shim check passed" as "the result is
genuine".

**The scoring was inverted.** Gutting that file scores 32. Migrating it
wrongly-but-honestly scores 3 -- run 56's warm-2, same file, same decorator,
no stub, writing `@model_validator(mode='after')` with a v1 `(cls, values)`
signature that crashes loudly. The oracle paid roughly 10x more for destroying
the code than for attempting it, and shared memory propagates whatever scored
highest. The hole did not merely mis-score one attempt; it trained the warm
swarm toward the stub.

Closed by `gutted_files()` (`orchestrator/vibe_agent.py`), an `ast` check for
two structural signatures, neither needing the v1 original for comparison:

* statements unreachable after a `return`/`raise`/`continue`/`break` in the
  same statement list -- the exact residue of stubbing over a body;
* a validator whose body is a bare `return <name>`, `pass`, or `...`.

It overrides a green suite the same way the shim check does, forcing `passed`
to 0 so the diff can never be written to shared memory as progress, and tells
the agent plainly through the same channel as any other failure. Verified
clean on `reference_v2` and on the pristine v1 fixture; `tests/
test_gutted_detection.py`.

## 13.2 Retrieval was a coin toss, and it degrades as the graph grows

A trace embeds its `task`, and `task` is the pytest error signature the attempt
started from. Keying on the error rather than the task description was itself a
fix (§12.4) -- but the error signature is shared too. Every agent that hits the
same error writes a byte-identical `task`.

Measured on the run 53-56 graph: **16 of 37 traces share one task string**, and
a query for it returns all 15 fetched rows at similarity **0.9996, tied to four
decimal places**. The vector index returns them in storage order and
`[:max_traces]` took whichever five arrived first. Quality never entered the
ordering.

That is the whole of the run 54 result. Its warm-2 drew the one informative
trace out of six candidates; runs 55 and 56 asked the identical question of a
larger graph, drew differently, and got 3. That was read as "not reproducible"
and used to support a model-size conclusion. It was a coin toss built into the
harness, and it gets *worse* with accumulation, since every run adds more
traces tied at the same score -- the precise opposite of what the demo claims.

Fixed in `ScopedMemory._reasoning_context()`: break the tie on `tests_passed`,
then recency, and render the tally in the prompt, because the similarity line
is a constant ~1.00 and carries no ranking information. `tests_passed` lives in
`metrics_json`, which `complete_trace()` writes from `TraceOutcome.metrics` but
`get_similar_traces()` does not carry onto the model, so it needs a second read
through `client.query.cypher()` -- the package's supported read-only Cypher
surface, the one behind its shipped `graph_query` MCP tool, and not
`client.graph.execute_read()`, which is a `_DeprecatedGraphProxy`.

## 13.3 The two fixes are only correct together

Ranking on `tests_passed` while 13.1 was open would have made the system
strictly worse: the stub diff goes from *occasionally* retrieved to *first,
every time*. Confirmed live after the ranking fix -- against the old graph the
gutted trace ranked #1 at 32. That graph was discarded rather than rescored.

## 13.4 What this does to the earlier conclusions

* Run 54's 32/33 is withdrawn. The best genuine result remains run 32's 31/33.
* "Warm and cold are tied on `best_tests_passing`" (§12.6) stands, but it was
  measured through a retrieval path that was selecting arbitrarily, so it is a
  measurement of a broken warm arm, not of shared memory.
* The model-bound finding (§11.5) is unchanged as far as it goes -- edit
  failure 43% -> 14% and tool errors 22% -> 6% from 8B to 14B are real and
  independently measured. What is withdrawn is the claim that it is the
  *remaining* constraint. It was the largest measured one while two unmeasured
  ones were open.
