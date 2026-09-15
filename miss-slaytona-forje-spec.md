# Miss Slaytona Forje — build spec

A live conference demo for a 15-minute talk on the agentic stack and multi-agent applications.

**Stack:** **Mi**stral · **S**GLang · Dayton**a** · Neo**4j** (`neo4j-agent-memory`)

---

## 0. What this is, in one paragraph

Two identical swarms of coding agents race to perform the same real migration on the same codebase, side by side on one screen. Every variable is held constant — same model, same prompts, same sandboxes, same task — except one: the right-hand swarm shares a memory graph and the left-hand swarm does not. The audience watches the right side stop repeating itself. The talk closes with a Cypher query against the resulting graph that no log file could answer.

**The single success criterion:** the warm swarm completes the migration using materially fewer tokens than the cold swarm, live, in under four minutes, without operator intervention.

Every decision in this document is subordinate to that sentence. If a feature does not serve it, it is out of scope.

---

## 1. Demo narrative

This section is the contract. Everything downstream justifies itself against it.

| Time | On screen | Presenter |
|---|---|---|
| 0:00 | Title slide | Framing: parallel agents are not a multi-agent system. Most "swarms" are N agents re-deriving the same thing N times. |
| 2:00 | Architecture slide | The four components, 60 seconds. |
| 3:00 | Demo UI, idle. Two empty columns, empty graph pane. | "Same model, same sandboxes, same task. One difference." Press start. |
| 3:15 | Both columns light up. File cards move from queued → running → passed. Token counters climb. | Narrate the first minute. Both sides look identical and that is the point. |
| ~4:30 | Right column starts landing files on first attempt. Graph pane has nodes. First **memory hit flash**. | "That agent just used something another agent learned ninety seconds ago." |
| ~6:30 | Right column finishes. Left column still working. Token gap is large and obvious. | Let it sit. Do not talk over the gap. |
| 7:30 | Scoreboard final state. | The number. |
| 8:00 | Cypher pane | Run the closing query live. Which patterns were learned, by whom, and how many re-derivations the graph prevented. |
| 11:00 | Close + Q&A | |

**The wow moment is the flash, not the numbers.** Budget engineering effort accordingly.

### Anticipated objection, to be pre-empted at 3:00

Someone will think "there is a codemod for that." The presenter says up front: this is not a claim that LLMs are the best tool for this migration. The task was chosen *because* the correct answers are already known — that is what makes it a clean measuring stick. The variable under test is memory, not the model.

---

## 2. Non-goals

Do not build these. They were considered and cut.

- **No Skills / distillation.** The `neo4j-agent-memory` Skills API is Preview, REST/MCP-only, and NAMS-only. Out of scope entirely.
- **No critic or planner agent.** One agent role.
- **No model routing.** One model, one endpoint.
- **No lineage / DERIVED_FROM tree.** Agents do not fork each other's attempts.
- **No auth, no user accounts, no multi-tenancy beyond the one scoping flag in §7.**
- **No persistence beyond the run.** The database is wiped between runs.
- **No sophisticated retry strategy.** Fixed attempt cap, error appended to prompt, that is all.
- **No test-suite discovery, no repo crawling.** The file list is a static manifest.
- **No streaming token display.** Counters update on completion.
- **No mobile layout, no responsive design.** It renders on one projector at one resolution.

---

## 3. Architecture

Four processes, one machine (except the GPU, which may be remote).

```
orchestrator.py  ── HTTP ──►  SGLang server (Devstral Small)     [GPU host]
      │                             /v1/chat/completions
      │                             /metrics
      ├─ AsyncDaytona  ──────►  12 ephemeral sandboxes           [Daytona cloud]
      ├─ MemoryClient  ──────►  Neo4j 5.x                        [local Docker]
      └─ WebSocket     ──────►  ui/index.html (d3)               [browser, fullscreen]
```

**Responsibilities:**

- **Orchestrator** — owns the file queue, spawns 2N agent coroutines, aggregates metrics, emits the event stream. Single process, pure `asyncio`. Both the memory SDK and the Daytona SDK are async-native, so there is no thread pool anywhere in this system.
- **SGLang** — serves one Mistral model on an OpenAI-compatible endpoint to all agents. Its RadixAttention prefix cache is what makes 12 concurrent agents affordable on one GPU.
- **Daytona** — one ephemeral sandbox per file attempt. Runs the test suite. Nothing model-generated ever executes on the presenter's machine.
- **Neo4j + `neo4j-agent-memory`** — reasoning traces and pattern entities. Shared by the warm swarm, isolated for the cold swarm.
- **UI** — static HTML + vanilla JS + d3. No build step. Consumes the event stream live or from a recorded file.

---

## 4. The fixture and the task

### 4.1 The fixture

An authored Python service, checked into this repo at `fixture/`. **Do not use a third-party repo.** Authoring it gives exact control over file count, pattern distribution and test runtime, and removes all licensing questions.

**`fixture/` — a conference CFP (call for papers) service.** Twelve modules, roughly 150–300 lines each, written properly against **pydantic v1**. Real models, real validation logic, real business rules. It must read as a codebase someone actually wrote, not as a pattern-injection exercise.

```
fixture/
  cfp/
    __init__.py
    models/
      speaker.py          # Speaker, SpeakerProfile
      talk.py             # Talk, TalkFormat, Duration
      submission.py       # Submission, SubmissionState
      review.py           # Review, ReviewScore
      schedule.py         # ScheduleSlot, Track
      venue.py            # Venue, Room, Capacity
    services/
      scoring.py          # aggregate review scores
      matching.py         # match talks to slots
      notification.py     # build acceptance/rejection payloads
      export.py           # serialise schedule to JSON
      validation.py       # cross-model business rules
      importer.py         # parse external CFP submissions
  tests/
    test_speaker.py
    test_talk.py
    ... one test module per source module
  requirements-v1.txt     # pydantic>=1.10,<2
  requirements-v2.txt     # pydantic>=2.6
```

**Hard constraints on the fixture:**

- Every test module must run in **under 2 seconds** on 1 vCPU.
- No network, no database, no filesystem beyond `tmp_path`, no sleeps, no randomness without a fixed seed.
- The full suite passes on pydantic v1 and fails on pydantic v2 before migration.
- Each source module's tests can be run independently: `pytest tests/test_speaker.py`.

### 4.2 The task

Migrate the fixture from pydantic v1 to pydantic v2. Six recurring breakage patterns:

| ID | Pattern | Fix | Files | Fails at |
|---|---|---|---|---|
| `P1_VALIDATOR` | `@validator` | `@field_validator` + `@classmethod` | 8 | import |
| `P2_DICT_JSON` | `.dict()`, `.json()` | `.model_dump()`, `.model_dump_json()` | 7 | runtime |
| `P3_CONFIG_CLASS` | `class Config:` | `model_config = ConfigDict(...)` | 6 | import/runtime |
| `P4_PARSE_OBJ` | `.parse_obj()`, `.parse_raw()` | `.model_validate()`, `.model_validate_json()` | 4 | runtime |
| `P5_ROOT_VALIDATOR` | `@root_validator` | `@model_validator(mode="before"\|"after")` | 3 | import |
| `P6_IMPLICIT_OPTIONAL` | `x: Optional[str]` with no default | `x: Optional[str] = None` | 5 | **runtime, only on some paths** |

`P6` is the star. In v1 an `Optional` field was implicitly optional; in v2 it is required unless a default is given. It does not fail at import, and it does not fail on every code path — only where a model is constructed without that field. It is the pattern an agent has to genuinely *discover* from a test failure, and therefore the one whose sharing is most visible. Distribute it across files whose tests exercise it in non-obvious ways.

Roughly 33 pattern occurrences across 12 files. That distribution is deliberate: enough repetition that memory compounds, few enough distinct patterns that the compounding completes within the run.

### 4.3 The manifest

`fixture/manifest.yaml` — the ground truth, checked in, validated before every run.

```yaml
target_version: "pydantic>=2.6"
files:
  - path: cfp/models/speaker.py
    tests: tests/test_speaker.py
    patterns: [P1_VALIDATOR, P2_DICT_JSON, P6_IMPLICIT_OPTIONAL]
    expected_attempts_cold: 3      # rehearsal-measured, informational only
  - path: cfp/models/talk.py
    tests: tests/test_talk.py
    patterns: [P1_VALIDATOR, P3_CONFIG_CLASS]
  # ... 12 entries
patterns:
  P1_VALIDATOR:
    label: "@validator → @field_validator"
    occurrences: 8
  # ... 6 entries
```

`scripts/validate_fixture.py` must assert, before any run:
1. Every file in the manifest exists.
2. Every declared pattern is actually present in that file (regex or AST check).
3. The suite passes under pydantic v1.
4. The suite fails under pydantic v2.
5. Full suite runtime is under 25 seconds sequentially.

The `patterns` field is **never** shown to an agent. It exists for validation and for the closing Cypher query only.

---

## 5. Data model

`neo4j-agent-memory` creates most of this. Do not hand-roll it.

**Created by the package:**

- `(:Message)` — short-term memory. Used lightly here.
- `(:Entity)` with type labels `:Person` `:Organization` `:Location` `:Event` `:Object` and optional subtype labels. POLE+O model.
- `(:ReasoningTrace {id, session_id, task, outcome, success, started_at})`
- `(:ReasoningTrace)-[:INITIATED_BY]->(:Message)`
- `(:Message)-[:MENTIONS]->(:Entity)`
- `(:Entity)-[:SAME_AS]->(:Entity)` from the dedup pass
- `TOUCHED` edges for reasoning audit
- Vector indexes for semantic search (requires Neo4j 5.11+; use 5.20+)

**Added by this project:** exactly one thing.

Breakage patterns are stored as long-term entities:

```python
await client.long_term.add_entity(
    name="P6_IMPLICIT_OPTIONAL",
    entity_type="OBJECT",
    subtype="BREAKAGE_PATTERN",
    description="<agent's own description of the failure and fix>",
)
```

They land as `:Entity:Object:BreakagePattern`. Entity resolution and dedup are what make this work: when three warm agents independently hit the same pattern, the resolver merges them into one node rather than three. Leave `DeduplicationConfig` at defaults initially (auto-merge above ~0.92, `SAME_AS` flag between ~0.85 and 0.92) and tune only if rehearsal shows near-duplicates surviving.

**Do not** invent a custom graph schema for attempts, files or agents. Reasoning traces already carry that. If the UI needs per-file state, it comes from the event stream, not from Neo4j.

---

## 6. The agent loop

One coroutine per agent. Agents pull from a shared `asyncio.Queue` of file tasks.

```
for each file claimed from the queue:

  trace = await memory.reasoning.start_trace(
      session_id = agent.session_id,
      task = f"Migrate {file.path} from pydantic v1 to v2",
      metadata = {"swarm": agent.swarm, "agent_id": agent.id, "file": file.path},
  )

  prior = await memory.reasoning.search_traces(
      query = f"Migrate {file.path} from pydantic v1 to v2",
      limit = 3,
      min_score = MIN_TRACE_SCORE,
  )
  known = await memory.long_term.search_entities("pydantic v2 migration breakage pattern")
  emit(MEMORY_READ, hits=len(prior) + len(known), pattern_names=[...])

  for attempt in 1..MAX_ATTEMPTS:

      prompt   = assemble(prior, known, file, last_error)
      response = await sglang.chat(prompt, response_format=PATCH_SCHEMA)
      patch    = response.patched_file
      claimed  = response.patterns_found     # agent's own labels, free text

      sandbox = await daytona.create(...)
      try:
          await sandbox.fs.upload_file(patch.encode(), f"/repo/{file.path}")
          result = await sandbox.process.exec(
              f"python -m pytest {file.tests} -x -q", cwd="/repo", timeout=TEST_TIMEOUT
          )
      finally:
          await daytona.delete(sandbox)          # ALWAYS. See §9.

      await memory.reasoning.record_tool_call(...)   # see §16 note
      emit(ATTEMPT_DONE, exit_code=result.exit_code, tokens=response.usage)

      if result.exit_code == 0:
          break
      last_error = tail(result.result, MAX_ERROR_CHARS)

  await memory.reasoning.complete_trace(
      trace.id,
      outcome = summary,
      success = (result.exit_code == 0),
  )

  if success:
      for p in claimed:
          await memory.long_term.add_entity(p, "OBJECT", subtype="BREAKAGE_PATTERN", ...)
      emit(MEMORY_WRITE, patterns=claimed)
```

### 6.1 Prompt assembly — cache-critical, do not reorder

```
BLOCK A   system prompt + migration rules + output JSON schema
          IDENTICAL for all 12 agents, byte for byte, for the entire run
BLOCK B   retrieved traces + known patterns    (empty string for cold agents)
BLOCK C   file path, file content, and on retry the previous error
```

Block A must never vary — not by agent id, not by swarm, not by whitespace. It is the shared prefix that RadixAttention caches across all 12 agents. Block B is placed immediately before Block C because Block C invalidates the cache from that point anyway, so memory costs nothing extra.

Block A must **not** name the six patterns. It states the goal ("migrate this file to pydantic v2 so its tests pass"), the output contract, and nothing more. If Block A contains the answers, memory has nothing to teach and the demo is a lie.

### 6.2 Structured output

Enforce with SGLang's constrained decoding (xgrammar). Nothing should ever fail to parse on stage.

```json
{
  "patched_file": "<complete file contents>",
  "patterns_found": ["short label", "..."],
  "reasoning": "<two sentences max>"
}
```

Whole-file replacement, not diffs. Diffs fail to apply; whole files always apply. The fixture's file sizes were chosen to make this affordable.

---

## 7. The cold/warm differential

**This is the heart of the demo and it must be honest.** Both swarms run the identical code path with the identical prompt template. The only difference is the scope of memory they can see.

**Primary mechanism:**

- Warm agents: `user_identifier="warm"` — shared. Six agents, one knowledge scope.
- Cold agents: `user_identifier=f"cold-{agent_id}"` — six isolated scopes.

Cold agents still write traces and entities. They simply cannot see each other's. This means both swarms are fully queryable afterwards, which the closing Cypher query depends on.

**Verification step, milestone 3, mandatory:** confirm that `user_identifier` scoping actually isolates `reasoning.search_traces` results and not only long-term entities. Write a test: two clients with different identifiers, one writes a trace, the other searches for it and must get zero hits.

**If that test fails**, fall back to gating the read:

```python
prior = await memory.reasoning.search_traces(...) if agent.reads_memory else []
known = await memory.long_term.search_entities(...) if agent.reads_memory else []
```

Less elegant, equally valid, bulletproof. Writes stay on for both swarms either way. Record which mechanism is in use in the run config, because the presenter will be asked.

**Fairness requirements** — violating any of these makes the demo dishonest:

- Same model, same temperature, same seed policy, same `max_tokens`.
- Same file queue, same order, same attempt cap.
- Same sandbox resources and same test command.
- Both swarms start within 500ms of each other.
- The cold swarm must not be starved of SGLang throughput. Both swarms submit to the same endpoint with no priority.

---

## 8. Orchestrator

Single process, `asyncio.gather` over `2 × SWARM_SIZE` agent coroutines plus a metrics poller plus a WebSocket server.

**Run config** (`config.yaml`, overridable by env):

```yaml
swarm_size: 6                 # per side; drop to 4 if Daytona limits bite (§9)
max_attempts: 3
test_timeout_s: 60
sandbox_create_timeout_s: 60
max_error_chars: 2000
min_trace_score: 0.55
model: "<devstral-small-tag>"
temperature: 0.1
max_tokens: 8000
memory_isolation: "user_identifier"   # or "read_gate"
```

**Queue:** a single `asyncio.Queue` per swarm, both seeded with the same 12 files in the same order. Agents claim, complete, and claim again until empty.

**Failure policy:** an agent that exhausts `max_attempts` on a file marks it failed and moves on. A crashed agent coroutine is logged and does not take down the run — `asyncio.gather(..., return_exceptions=True)` with per-agent supervision. **The run must always reach a terminal state within `HARD_DEADLINE_S` (default 300).** On deadline, cancel outstanding work, close all sandboxes, emit `RUN_END`, and let the UI display final state. A demo that hangs is worse than a demo that stops.

### 8.1 Event stream

Newline-delimited JSON, broadcast over WebSocket and simultaneously appended to `runs/<run_id>.jsonl`.

```json
{"t": 12.481, "type": "ATTEMPT_START", "swarm": "warm", "agent": 3, "file": "cfp/models/talk.py", "attempt": 2}
```

Event types:

| Type | Payload |
|---|---|
| `RUN_START` | config snapshot, file list, run_id |
| `FILE_CLAIMED` | swarm, agent, file |
| `MEMORY_READ` | swarm, agent, file, hit_count, pattern_names, source_agents |
| `ATTEMPT_START` | swarm, agent, file, attempt |
| `SANDBOX_CREATED` | swarm, agent, sandbox_id, create_ms |
| `ATTEMPT_DONE` | swarm, agent, file, attempt, exit_code, prompt_tokens, completion_tokens |
| `FILE_DONE` | swarm, agent, file, success, attempts, total_tokens |
| `MEMORY_WRITE` | swarm, agent, patterns, entity_ids, merged (bool) |
| `METRICS` | cache_hit_rate, sandboxes_live, tokens_by_swarm |
| `RUN_END` | totals, per-swarm summary |

`MEMORY_READ` with `hit_count > 0` and non-empty `source_agents` is what triggers the flash. Populating `source_agents` correctly is a first-class requirement, not a nicety — it is the payload of the demo's best moment.

---

## 9. Sandbox lifecycle

```python
from daytona import AsyncDaytona, DaytonaConfig, CreateSandboxFromSnapshotParams
```

### 9.1 Snapshot, built once, ahead of time

`scripts/build_snapshot.py` produces a named snapshot containing:

- Python 3.12
- pydantic v2 and pytest pre-installed
- The fixture repo pre-copied to `/repo` in its **unmigrated v1 state**

Nothing is cloned, downloaded or pip-installed at runtime. The conference network must never be on the critical path. Rebuild the snapshot whenever the fixture changes; `validate_fixture.py` should refuse to run if the snapshot hash is stale.

### 9.2 Per-attempt

```python
sandbox = await daytona.create(
    CreateSandboxFromSnapshotParams(
        snapshot=SNAPSHOT_NAME,
        language="python",
        ephemeral=True,
        auto_stop_interval=5,
    ),
    timeout=SANDBOX_CREATE_TIMEOUT_S,
)
```

Then `await sandbox.fs.upload_file(...)`, `await sandbox.process.exec(...)`, and **delete in a `finally` block, unconditionally**. Also register an atexit / signal handler that sweeps any sandbox created by this run_id. The standard way to overspend on Daytona is a loop that forgets to close them.

### 9.3 Resource budget — read this before writing any code

Daytona org limits **start at roughly 10 vCPU / 20 GiB RAM / 30 GiB storage** and step up with account verification and prepaid balance. Twelve concurrent sandboxes at 2 vCPU each is 24 vCPU and **will not fit the starting cap**.

Actions, in this order:
1. Sign up today. $200 free compute is included, no card required — it should cover the whole build and the talk.
2. Verify the account and request a limit increase immediately. This has an external waiting period and is the only item in this project that cannot be compressed by working harder.
3. Design for the default 1 vCPU / 1 GiB sandbox. The fixture's test constraints in §4.1 exist to make this viable. Only raise `Resources(cpu=..., memory=...)` if rehearsal proves it necessary.
4. Keep `swarm_size` a config value. If the increase does not land, demo at four a side. The argument is identical.

Instrument `sandboxes_live` and put it on screen. It is a good number for the Daytona speaker and it is your early warning for a leak.

---

## 10. SGLang

```bash
python3 -m sglang.launch_server \
  --model-path <devstral-small-tag> \
  --host 0.0.0.0 --port 30000 \
  --enable-metrics \
  --chunked-prefill-size 4096
```

- OpenAI-compatible: `POST /v1/chat/completions`. Use the `openai` client pointed at `http://<host>:30000/v1`.
- Token accounting comes from the `usage` object on each response, tagged by swarm. **Do not** derive per-swarm tokens from `/metrics` — those counters are global across both swarms.
- `/metrics` is Prometheus format. Scrape `cache_hit_rate` for the on-screen gauge. **The metric prefix changed from `sglang:` to `sglang_` in v0.5.4+ — probe both and use whichever is present.** Same for `prompt_tokens_total` and `generation_tokens_total`.
- Send a warmup request at startup so the first real agent call is not paying for lazy init.

**Model:** Devstral Small is the right capability. At ~24B it wants roughly 48 GB at bf16, so a single 48 GB card (L40S, A6000) with an FP8/AWQ build holds 12 concurrent agents plus KV cache comfortably; an 80 GB H100 runs it unquantized with no thought required.

**Cost strategy:** milestones 1 and 2 need no GPU at all. Milestones 3 and 4 only need *a* model — build against something small and cheap, or the stub in §13. Rent the real card only for milestone 6 rehearsals and the talk itself. The demo runs for four minutes; your entire GPU bill is rehearsal time.

---

## 11. UI

Static `ui/index.html`, vanilla JS, d3 from CDN, no build step. Designed for one projector at 1920×1080, dark background.

```
┌──────────────────────────┬──────────────────────────┐
│  COLD SWARM              │  WARM SWARM              │
│  no shared memory        │  shared memory           │
│                          │                          │
│  [file cards ×12]        │  [file cards ×12]        │
│                          │                          │
│  tokens   1,284,000      │  tokens     412,000      │
│  passed        7/12      │  passed       12/12      │
│  attempts        31      │  attempts         14     │
├──────────────────────────┴──────────────────────────┤
│  SHARED MEMORY GRAPH                                │
│  [d3 force layout — pattern & trace nodes]          │
├─────────────────────────────────────────────────────┤
│  sandboxes live: 9    ·    prefix cache hit: 0.87   │
└─────────────────────────────────────────────────────┘
```

**File cards:** twelve per column, fixed grid, fixed position. States: `queued` (dim) → `running` (outlined, attempt number shown) → `passed` (filled) / `failed` (struck). No animation on state change beyond a 150ms fade. The columns must be visually calm so the graph pane owns all motion.

**Graph pane:** only the warm swarm's graph is drawn — the cold graph is six disconnected stars and adds nothing. Pattern entities are large nodes; reasoning traces are small nodes attached to them.

**The flash — spec this precisely, it is the demo:**

On `MEMORY_READ` with `hit_count > 0`, for each hit: draw a pulse travelling along the edge from the pattern node to the reading agent's node, and briefly ring the pattern node. Roughly 800ms, ease-out, then fully settled. Alongside it, one line of text in a fixed slot below the graph:

> `agent 5 → P6_IMPLICIT_OPTIONAL, learned by agent 2 · 94s ago`

That sentence, appearing at the moment the pulse fires, is the single most valuable pixel in the talk. It converts an abstraction into an event.

**d3 layout warning:** default `forceSimulation` charge settings drift and jiggle indefinitely, which reads as noise on a projector. Use a low `alphaDecay`, let it settle, and freeze it. New nodes join with a brief local re-heat only — never re-heat the whole simulation. **The flash must be the only motion on screen.**

**Scoreboard is tokens, not wall-clock.** At this scale the cold swarm may well finish *faster* in wall-clock terms — memory reads add latency and brute force parallelises fine. Time is not on screen anywhere. Tokens, attempts and pass count are monotonic and cannot embarrass the presenter.

---

## 12. Metrics

Exact definitions. No ambiguity permitted.

| Metric | Definition | Source |
|---|---|---|
| `tokens[swarm]` | Σ (`usage.prompt_tokens` + `usage.completion_tokens`) over every completion by agents in that swarm | SGLang response `usage` |
| `attempts[swarm]` | count of `ATTEMPT_DONE` events | orchestrator |
| `passed[swarm]` | count of `FILE_DONE` with `success=true` | orchestrator |
| `token_ratio` | `tokens[cold] / tokens[warm]` — **the headline number** | derived |
| `cache_hit_rate` | latest gauge value, whole server, both swarms | SGLang `/metrics` |
| `sandboxes_live` | created minus deleted, current | orchestrator |
| `tool_stats` | per-tool call/success/failure counts | `reasoning.get_tool_stats(session_id=...)` |

`get_tool_stats` is a free aggregation from the memory package — use it rather than writing your own counters where it fits.

---

## 13. Replay mode

**Build this in milestone 1, not at the end.** It is what makes every subsequent milestone testable without a GPU or a Daytona balance, and it is the stage insurance.

- Every run writes `runs/<run_id>.jsonl`.
- `python -m orchestrator.replay runs/<id>.jsonl` re-emits that stream over the same WebSocket at original wall-clock pacing, with `--speed` to scale.
- The UI cannot tell the difference. No code path in the UI may branch on live-vs-replay.
- A `--stub-model` flag on the orchestrator returns canned patches from `fixture/stubs/` instead of calling SGLang, so the full pipeline including Daytona can be exercised with no GPU.

**Rehearsal protocol:** keep the best recorded run as `runs/golden.jsonl`. If the live run fails on stage, the presenter switches to replay and narrates. The audience will not know.

---

## 14. Repo layout

```
miss-slaytona-forje/
  README.md
  config.yaml
  orchestrator/
    __init__.py
    run.py              # entry point
    agent.py            # the loop in §6
    memory.py           # MemoryClient wrapper, scoping, retrieval
    sandbox.py          # AsyncDaytona wrapper, lifecycle, cleanup sweep
    llm.py              # SGLang client, structured output, usage accounting
    events.py           # event schema, WebSocket broadcast, jsonl writer
    metrics.py          # /metrics scraper, aggregation
    replay.py
  fixture/
    cfp/ ...            # the pydantic v1 service
    tests/ ...
    manifest.yaml
    stubs/              # canned patches for --stub-model
  scripts/
    build_snapshot.py
    validate_fixture.py
    wipe_graph.py
    preflight.py        # runs the §17 checklist
  ui/
    index.html
    app.js
    graph.js
    style.css
  queries/
    closing.cypher
  runs/
    golden.jsonl
```

---

## 15. Build order

Six milestones. Each has a runnable "done when". Do not proceed until the current one passes.

**M1 — Fixture and harness. No LLM, no memory, no Daytona.**
Write the 12 modules, the tests, the manifest. Write `validate_fixture.py`. Write the event schema and the replay player.
*Done when:* `validate_fixture.py` passes all five assertions, and `replay.py` can play a hand-written sample jsonl to a stub consumer.

**M2 — Sandbox harness. Still no LLM.**
Build the snapshot. Run the *known-correct* migrated version of each file through a real Daytona sandbox and confirm the tests pass. This proves the whole execution path with zero model risk.
*Done when:* all 12 files pass in real sandboxes, every sandbox is confirmed deleted, and `sandboxes_live` returns to zero.

**M3 — Single agent, no memory.**
One agent, real SGLang (or `--stub-model`), full loop, sequential over 12 files. Also: run the §7 isolation verification test.
*Done when:* one agent migrates at least 8/12 files unaided, and the isolation mechanism is chosen and recorded.

**M4 — Memory on, both swarms.**
Full orchestrator, 2×N agents, both scopes. No UI — console output only.
*Done when:* `token_ratio > 1.5` reproducibly over three consecutive runs.

**M5 — UI.**
Panes, cards, scoreboard, graph, the flash.
*Done when:* a golden replay renders end to end and the flash fires correctly with accurate `source_agents` attribution.

**M6 — Rehearsal and hardening.**
Fifty runs. Tune `min_trace_score`, `max_attempts`, and the Block A wording until the run completes inside four minutes with `token_ratio` reliably above 2. Record the golden run. Write `preflight.py`.
*Done when:* ten consecutive clean runs, and a deliberately killed SGLang mid-run still produces a graceful `RUN_END`.

M1 and M2 need no GPU. M3 and M4 need only a cheap one.

---

## 16. Things to verify, not assume

The following were read from documentation and may differ in the installed version. **Check the actual signatures in the installed package before building on them.** Do not guess.

- `reasoning.record_tool_call(...)` — the documented example passes a step id as its first argument (`record_tool_call(step.id, "tool", params, results)`), which implies a step object obtained from somewhere not shown. Inspect the `ReasoningMemory` source. If steps are awkward, `record_tool_call` is optional for this demo — `start_trace` and `complete_trace` carry the load.
- `long_term.add_entity(...)` returns a tuple in at least one documented example (`entity, _ = await ...`). Confirm the shape.
- `reasoning.search_traces(...)` returns `(ReasoningTrace, score)` tuples. Confirm `min_score` semantics and the embedding model in use.
- Whether `user_identifier` scopes reasoning traces or only long-term entities. **This is the §7 verification test and it gates the design.**
- `AsyncDaytona` sandbox teardown is variously `delete` and `remove` in the docs. Use whichever exists; wrap in `finally` either way.
- Exact current Devstral Small model tag on Hugging Face, and whether an FP8/AWQ build is available for your card.
- SGLang metric prefix (`sglang:` vs `sglang_`). Probe both at startup.

The package is **async-only** — every memory operation is a coroutine. There is no sync fallback.

---

## 17. Pre-flight checklist

`scripts/preflight.py` runs everything mechanical. The rest is human.

**Weeks ahead:**
- [ ] Daytona account created, verified, limit increase requested — **do this first, it has a waiting period**
- [ ] GPU host booked for rehearsal and talk day
- [ ] Neo4j 5.20+ running, `neo4j-agent-memory` installed against it

**Day before:**
- [ ] `validate_fixture.py` green
- [ ] Snapshot rebuilt and hash current
- [ ] Ten clean rehearsal runs
- [ ] `golden.jsonl` recorded and replay verified on the actual presentation laptop
- [ ] Graph wiped
- [ ] Daytona balance sufficient; no orphaned sandboxes

**On the day:**
- [ ] SGLang up, warmed, `/metrics` responding, correct prefix detected
- [ ] Neo4j up and empty
- [ ] Browser fullscreen at projector resolution, UI connected
- [ ] Replay tab open on `golden.jsonl`, one keystroke away
- [ ] Laptop display sleep and notifications disabled

### Known failure modes

| Failure | Mitigation |
|---|---|
| Conference wifi dies | Everything but Daytona and the GPU is local. If those are unreachable, replay. |
| Daytona limit hit mid-run | `swarm_size` config; rehearse at 4 a side too |
| Sandbox leak | `finally` teardown + run-scoped sweep + `sandboxes_live` on screen |
| Cold swarm finishes first | Wall-clock is not displayed anywhere |
| Warm swarm learns too fast, gap looks trivial | Tune `min_trace_score` upward; more files, not more patterns |
| Warm swarm learns too slowly | Lower `min_trace_score`; verify retrieval is actually returning hits before blaming the model |
| Model emits unparseable output | Constrained decoding; plus a parse-failure path that counts as a failed attempt rather than crashing |
| Run hangs | `HARD_DEADLINE_S` cancels and terminates cleanly |

---

## 18. The closing query

`queries/closing.cypher`. Run live on stage. It must return in under a second and fit on one screen.

The point being made: this answers a question a log file cannot. Not "what happened" but "what was learned, by whom, from whom, and what did it save."

```cypher
// Patterns learned by the warm swarm, and how many agents reused each
MATCH (p:Entity:Object)
WHERE p.subtype = 'BREAKAGE_PATTERN'
OPTIONAL MATCH (t:ReasoningTrace)-[:TOUCHED]->(p)
WHERE t.success = true
RETURN p.name              AS pattern,
       count(DISTINCT t)   AS traces_using_it,
       min(t.started_at)   AS first_learned
ORDER BY traces_using_it DESC
```

Tune the exact traversal against the real graph once M4 is green — the relationship between traces and pattern entities depends on how the package wires `TOUCHED` and `MENTIONS` in this version. The *shape* of the answer is fixed: pattern, reuse count, who got there first.

A second query worth having ready for Q&A, comparing both swarms:

```cypher
MATCH (t:ReasoningTrace)
RETURN t.metadata.swarm      AS swarm,
       count(*)              AS traces,
       sum(CASE WHEN t.success THEN 1 ELSE 0 END) AS succeeded
ORDER BY swarm
```

---

## 19. Definition of done

The build is finished when a cold laptop, following `preflight.py` and nothing else, can run the demo end to end in under four minutes, with the flash firing at least three times, `token_ratio` above 2, and a one-keystroke fallback to a recorded run that is visually indistinguishable from live.
