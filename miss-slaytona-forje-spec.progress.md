# Miss Slaytona Forje — build spec

> **THIS IS A WORKING COPY, NOT THE SOURCE OF TRUTH.** The original is
> `miss-slaytona-forje-spec.md` in this same directory — never edit that one.
> This copy exists so a fresh-context session can see, at a glance, what's
> been built, what deviated from the plan below and why, and what's next.
> Progress notes are blockquoted and timestamped like this one; everything
> else is the original spec text, unchanged.
>
> **Read this first, top to bottom, before touching code.** The full detail
> behind every note here also lives in the persistent memory system
> (project-type memories for this repo) — check there too if something below
> needs more context than fits in a callout.

> ## PROGRESS SUMMARY (as of 2026-09-08)
>
> - **M1 — done, verified.** `fixture/` (12 modules + 12 test modules),
>   `fixture/manifest.yaml`, `scripts/validate_fixture.py` (5/5 assertions
>   green), `orchestrator/events.py`, `orchestrator/replay.py`. Replay
>   stub-consumer test passes (`tests/test_replay.py`).
> - **M2 — done, verified live against a real Daytona account.**
>   `orchestrator/sandbox.py` (`SandboxPool`), `orchestrator/snapshot.py`,
>   `scripts/build_snapshot.py`, `scripts/verify_m2_sandboxes.py`,
>   `fixture/reference_v2/` (hand-written, verified-correct pydantic v2
>   migration of all 12 files — the M2 "known-correct" answer key). Last
>   live run: 12/12 files pass in real sandboxes, `sandboxes_live` returns
>   to 0, independently confirmed via a full-account `client.list()`.
> - **M3 — not started.** Blocked on a real GPU host running real SGLang.
>   A local Apple-Silicon SGLang build was tried and abandoned as the
>   forward path — see the §10 note below. Decision: rent a real CUDA GPU
>   and run SGLang normally rather than keep fighting the brand-new local
>   MLX backend. Next concrete step: get GPU host access (rent one — see
>   §9.3/§17 "GPU host booked" item, never done), install plain SGLang there
>   (`pip install sglang`, no from-source MLX dance needed on CUDA), launch
>   with a real Mistral/Devstral model, then build `orchestrator/agent.py` +
>   `orchestrator/llm.py` per §6/§14.
> - **M4, M5, M6 — not started.** Neo4j / `neo4j-agent-memory` has not been
>   touched at all yet (no local Docker instance stood up, no §7 isolation
>   test written). UI (`ui/`) doesn't exist yet. `queries/closing.cypher`
>   doesn't exist yet.
> - **Two deviations from this spec's assumptions, found empirically, both
>   important if you're debugging anything nearby:**
>   1. §4.2's "Fails at" column is wrong for the pydantic version actually
>      installed (2.13.x) — see the note under §4.2 below. Fixed via
>      `fixture/pytest.ini`, not by changing the patterns.
>   2. §9's Daytona API assumptions needed real correction (method
>      locations, the account-permission wrinkle) — see notes under §9
>      below.
> - A refactor/audit pass was done after M2 (user-requested): duplicated
>   constants/logic across `scripts/*.py` were centralized into
>   `orchestrator/manifest.py` and `orchestrator/snapshot.py`. Full
>   regression re-confirmed green after.
> - `.env` (gitignored) holds `DAYTONA_API_KEY`. Two local venvs exist for
>   the fixture itself (`.venvs/v1`, `.venvs/v2`, python3.11 — system python
>   is 3.14, too new for pydantic v1) plus `.venv` (python3.11) for
>   orchestrator/dev tooling. None of this is committed to git yet — ask
>   before committing, per this session's working style.

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

> **PROGRESS (2026-09-08):** built exactly as specified, plus one extra
> directory not in this tree: `fixture/reference_v2/` — a full pydantic v2
> mirror of `cfp/` (the "known-correct" migration), used by M2's sandbox
> verification and not shown to any agent. Also added: `fixture/conftest.py`
> (sys.path shim so `cfp` is importable from `tests/`) and `fixture/pytest.ini`
> (see the §4.2 note below for why it's load-bearing, not incidental).

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

> **PROGRESS (2026-09-08) — important correction to this table:** verified
> empirically against pydantic 2.13.5 (the version that actually installs
> for `>=2.6` today) that this "Fails at" column is only accurate for two
> of the six patterns as literally described. `@root_validator` (bare, no
> `skip_on_failure=True`) and implicit-`Optional`-no-default both hard-fail
> exactly as described, independent of any config. But `@validator`,
> `.dict()/.json()`, `class Config`, and `.parse_obj()/.parse_raw()` all
> **still work** on pydantic 2.13 — they only emit a `PydanticDeprecatedSince20`
> warning and otherwise behave identically. Left alone, the fixture would
> NOT fail its test suite on v2 as this spec's manifest assertions require.
>
> Fix: `fixture/pytest.ini` sets `filterwarnings = error::DeprecationWarning`.
> This promotes every deprecation warning to a hard error, so all six
> patterns now genuinely break the v2 run — at collection time for
> `class Config`/`@validator` (they fire at class-body execution), at
> runtime for `.dict()/.json()/.parse_obj()/.parse_raw()` (only warn when
> called). A fully-migrated v2 file emits zero deprecation warnings, so this
> filter has zero effect post-migration — confirmed via `fixture/reference_v2/`
> passing cleanly under `.venvs/v2` with no warnings at all. Used the
> builtin `DeprecationWarning` class specifically (not
> `pydantic.warnings.PydanticDeprecatedSince20`) because pytest's
> `filterwarnings` eagerly imports the named class at collection time, and
> `pydantic.warnings` doesn't exist in pydantic v1 — referencing it directly
> would break the v1 collection too (verified: raises `UsageError`).
> `DeprecationWarning` is a Python builtin importable in both environments.
>
> Practical implication: don't add exception-type-specific tests (e.g.
> `pytest.raises(TypeError)` for frozen-model mutation) to the fixture —
> the exact exception type pydantic raises for the same conceptual error
> differs between v1 and correctly-migrated v2 code, which would make a
> test fail post-migration for the wrong reason.

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

> **PROGRESS (2026-09-08):** `fixture/manifest.yaml` is built exactly to
> this shape, all 12 entries, pattern counts matching the table above
> exactly (P1×8, P2×7, P3×6, P4×4, P5×3, P6×5, 33 total). `scripts/validate_fixture.py`
> implements all 5 assertions via AST/regex pattern checks, and by default
> shells out to `.venvs/v1/bin/python` / `.venvs/v2/bin/python` (overridable
> via `FIXTURE_V1_PYTHON`/`FIXTURE_V2_PYTHON` env vars). Last run: all 5
> green, full suite (72 tests) runs in ~0.3–0.5s under v1, well under the
> 25s cap.

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

> **PROGRESS (2026-09-08):** not started. No Neo4j instance stood up yet,
> `neo4j-agent-memory` not installed/inspected yet. This is M4 territory.
> §16's open questions about this package's actual API shape (`add_entity`
> return type, `search_traces` tuple shape, whether `record_tool_call` needs
> a step object) are all still open — verify them empirically when this
> milestone starts, same "check the installed package, don't guess" approach
> used for the `daytona` package in M2 (see notes under §9).

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

> **PROGRESS (2026-09-08):** not started — this is `orchestrator/agent.py`,
> M3 work. `orchestrator/sandbox.py`'s `SandboxPool.run_pytest()` already
> implements the create→upload→exec→delete inner portion of this loop
> (verified live in M2), so M3 mainly needs the memory calls (once M4/Neo4j
> exists — M3 itself runs with no memory per its own done-when) and the
> SGLang chat call wired around it.

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

> **PROGRESS (2026-09-08) — real finding, read before building `orchestrator/llm.py`:**
> tried exactly this (constrained decoding via `response_format: json_schema`)
> against a real Mistral model served locally through SGLang's brand-new
> (2026) Apple Silicon MLX backend. It's broken: every single
> grammar-constrained token gets rejected ("Tokens not accepted"),
> `finish_reason: "abort"`, degenerate/empty output — reproduced with two
> different grammar backends (`xgrammar` and `llguidance`) and two different
> models (a Mistral-tekken-tokenizer model and a standard-tokenizer model),
> so it's not schema- or tokenizer-specific. Root cause looks like the MLX
> backend samples a token unconstrained and checks the grammar after,
> instead of masking invalid tokens before sampling (the correct approach,
> and how xgrammar has worked on CUDA for ~1.5+ years). SGLang's own e2e
> test suite for this backend doesn't cover grammar-constrained decoding at
> all yet — it's that new.
>
> Plain (non-structured) generation on that same local MLX setup works
> fine, with correct token usage accounting.
>
> **Decision made:** don't fight this locally. Rent a real CUDA GPU for M3
> onward and run standard SGLang there (`pip install sglang`, no from-source
> MLX build, no MLX-specific flags) — mature xgrammar support on CUDA means
> this almost certainly isn't an issue there. This section's structured-output
> requirement should be buildable as literally specified once M3 has a real
> GPU. The local MLX experiment (`vendor/sglang`, a from-source build) was
> deleted after this finding — it served its diagnostic purpose and isn't
> the forward path. Full findings, including the exact build recipe if
> local iteration is ever wanted again, are in memory (not repeated here).

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

> **PROGRESS (2026-09-08):** not started. This is the M3 mandatory
> verification step — not yet run, since Neo4j/`neo4j-agent-memory` hasn't
> been touched at all. Do this early in M3, per the spec's own instruction,
> since it gates whether `memory_isolation` is `user_identifier` or
> `read_gate`.

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

> **PROGRESS (2026-09-08):** `orchestrator/events.py` implements the event
> schema (`EVENT_TYPES` frozenset matching this table exactly), a
> `JsonlWriter`, an `EventBroadcaster` (WebSocket fan-out, drops disconnected
> clients silently, has a `wait_for_clients()` used by replay), and an
> `EventBus` combining both behind one `emit()` call. No `config.yaml` or
> `orchestrator/run.py` yet (M4 territory) — config values like `swarm_size`/
> `max_attempts` above aren't wired to anything real yet.

---

## 9. Sandbox lifecycle

```python
from daytona import AsyncDaytona, DaytonaConfig, CreateSandboxFromSnapshotParams
```

> **PROGRESS (2026-09-08) — real API corrections, verified against the
> actually-installed `daytona` package (not guessed from docs):**
> - Package name is `daytona` (also published as `daytona_sdk`, same
>   versions) — the import above is correct as written.
> - `AsyncDaytona()` with no config reads `DAYTONA_API_KEY` from the
>   environment automatically — confirmed via source, no need to construct
>   `DaytonaConfig` explicitly for the common case.
> - Snapshot creation is **not** a method on `AsyncDaytona` directly. It's
>   `client.snapshot.create(CreateSnapshotParams(name=..., image=..., resources=...))`
>   — a sub-service (`AsyncSnapshotService`), not shown in this spec's import
>   line.
> - Sandbox teardown is `delete` (both `client.delete(sandbox)` and
>   `sandbox.delete()` exist) — never `remove`. §16's open question below is
>   answered.
> - `ExecuteResponse` (the `sandbox.process.exec(...)` return value) has
>   `.exit_code` and `.result` exactly as this spec's agent-loop pseudocode
>   in §6 assumes.
> - **Account-specific wrinkle, may or may not apply to whatever Daytona
>   account ends up used for the real talk:** this session's Daytona account
>   returns `403 Forbidden` specifically on `client.snapshot.create(...)` —
>   plain sandbox create/delete works fine, and listing snapshots/sandboxes
>   works fine. This strongly suggests an account-verification/plan gate on
>   persisted snapshots specifically (matching this spec's own §9.3/§17 note
>   that Daytona account verification has an external waiting period).
>   Workaround built and verified live: `CreateSandboxFromImageParams`
>   (build a custom image directly per-sandbox, no persisted `Snapshot`
>   resource) also works on this account, and Daytona caches the built
>   image server-side by content hash — a second sandbox created from the
>   identical `Image` spec was just as fast as the first (~1-2s), so it
>   satisfies this section's actual goal ("nothing touches the network
>   mid-demo, sandbox creation stays fast") just as well as a real snapshot
>   would. `orchestrator/snapshot.py`'s `register_or_warm()` tries the
>   proper snapshot path first and falls back to warming the image cache on
>   `DaytonaForbiddenError`, recording which mode was used in
>   `.snapshot_state.json` (gitignored) so downstream code picks the right
>   path automatically. **If the real talk's Daytona account is different
>   from this session's and turns out to support persisted snapshots
>   cleanly, this fallback simply never triggers — no code changes needed
>   either way.**

### 9.1 Snapshot, built once, ahead of time

`scripts/build_snapshot.py` produces a named snapshot containing:

- Python 3.12
- pydantic v2 and pytest pre-installed
- The fixture repo pre-copied to `/repo` in its **unmigrated v1 state**

Nothing is cloned, downloaded or pip-installed at runtime. The conference network must never be on the critical path. Rebuild the snapshot whenever the fixture changes; `validate_fixture.py` should refuse to run if the snapshot hash is stale.

> **PROGRESS (2026-09-08):** built as `orchestrator/snapshot.py` (logic:
> `fixture_hash()`, `build_image()`, `register_or_warm()`, `load_state()`/
> `save_state()`, `is_stale()`) plus a thin CLI at `scripts/build_snapshot.py`
> (`--check` flag to test staleness without a Daytona client — the
> "`validate_fixture.py` should refuse to run if stale" requirement is
> implemented as this separate `--check` mode rather than folded into
> `validate_fixture.py` itself, since staleness-checking needs Daytona
> account state that fixture validation otherwise doesn't). Image built via
> `Image.debian_slim("3.12").pip_install_from_requirements(...)` +
> `add_local_dir`/`add_local_file` for `cfp/`, `tests/`, `conftest.py`,
> `pytest.ini` — deliberately excludes `fixture/reference_v2/` (never baked
> into the snapshot/image, only uploaded per-verification-run) and
> `requirements-v1.txt` (irrelevant inside a v2-only sandbox).

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

> **PROGRESS (2026-09-08):** `orchestrator/sandbox.py`'s `SandboxPool`
> implements exactly this — `sandbox()` is an async context manager that
> creates (from either a snapshot or an ad-hoc image, see §9 note above),
> yields `(sandbox, create_ms)`, and deletes unconditionally in `finally`.
> `run_pytest()` wraps that with file upload + `pytest -x -q` exec, matching
> this spec's agent-loop pseudocode in §6. `sweep()` (list-by-run_id-label,
> delete each) and `install_cleanup_handlers()` (atexit/SIGINT/SIGTERM ->
> `sweep()`) are both built; `install_cleanup_handlers` has no call sites
> yet since there's no long-running orchestrator process yet (M4) — it's
> ready for that, not dead code. Verified live: one real bug found and
> fixed — calling a final safety-net `sweep()` right after every sandbox
> already deleted itself via its own `finally` raced Daytona's own in-flight
> teardown and threw a 409 `DaytonaConflictError`; now treated as "already
> going away," not a leak.

### 9.3 Resource budget — read this before writing any code

Daytona org limits **start at roughly 10 vCPU / 20 GiB RAM / 30 GiB storage** and step up with account verification and prepaid balance. Twelve concurrent sandboxes at 2 vCPU each is 24 vCPU and **will not fit the starting cap**.

Actions, in this order:
1. Sign up today. $200 free compute is included, no card required — it should cover the whole build and the talk.
2. Verify the account and request a limit increase immediately. This has an external waiting period and is the only item in this project that cannot be compressed by working harder.
3. Design for the default 1 vCPU / 1 GiB sandbox. The fixture's test constraints in §4.1 exist to make this viable. Only raise `Resources(cpu=..., memory=...)` if rehearsal proves it necessary.
4. Keep `swarm_size` a config value. If the increase does not land, demo at four a side. The argument is identical.

Instrument `sandboxes_live` and put it on screen. It is a good number for the Daytona speaker and it is your early warning for a leak.

> **PROGRESS (2026-09-08):** account signed up and in use on free credits
> (per user: "if it requires payment later, we can go for it" — not yet
> needed). Account verification for persisted snapshots specifically has
> **not** been done (see the 403 finding under §9 above) — the image-mode
> fallback sidesteps this for now rather than blocking on it. `Resources(cpu=1, memory=1)`
> is the default used throughout M2 (`scripts/build_snapshot.py --cpu 1 --memory 1`),
> matching this section's guidance, never needed to raise it.
> `sandboxes_live` is tracked on `SandboxPool` (local bookkeeping) with
> `sweep()` as the independent source of truth against the real API — not
> yet "put on screen" since there's no UI yet (M5).

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

> **PROGRESS (2026-09-08) — decision point, read this before starting M3:**
> attempted the "build against something small and cheap" path locally
> first, for free, via SGLang's brand-new (2026) Apple Silicon MLX backend
> (built from source; see §6.2 note above for the structured-output finding
> that ended this path). Confirmed working: plain chat completion, real
> token usage accounting, on a real small Mistral model
> (`Ministral-8B-Instruct-2410`, 4-bit, via `mlx-community`) served through
> SGLang's actual OpenAI-compatible endpoint. Confirmed broken: structured
> output / constrained decoding, which §6.2 requires. Also found along the
> way: the newest "Ministral-3" model family (`model_type: "mistral3"`)
> crashes this backend outright (attention-wrapper argument-count mismatch)
> — stick to classic `model_type: "mistral"` checkpoints (which `mlx_lm`
> remaps to its long-established `llama.py` implementation) if this local
> path is ever revisited.
>
> **Given the choice between continuing to fight a brand-new experimental
> backend for a demo, versus renting a real CUDA GPU where SGLang's
> xgrammar support is mature (~1.5+ years), the user chose the real GPU
> rig.** So: M3 onward should target a rented CUDA GPU with plain
> `pip install sglang` (no from-source build, no MLX flags, no `srt_mps`
> extra) and this section's launch command works as literally written.
> GPU host booking (§17 "weeks ahead" checklist) has not happened yet — this
> is the concrete next external dependency, same shape as the Daytona
> account was for M2 (something only the user can provision).
>
> The exact metric-prefix question (`sglang:` vs `sglang_`) hasn't been
> checked yet — do that once a real server is up, same "probe both, don't
> guess" approach used for the pydantic-version and Daytona-API questions
> above.

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

> **PROGRESS (2026-09-08):** not started (M5). No `ui/` directory exists
> yet.

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

> **PROGRESS (2026-09-08):** `orchestrator/replay.py` built in M1 exactly
> as this section demands — `python -m orchestrator.replay runs/<id>.jsonl [--speed]`,
> paces re-broadcast by the delta of each event's `t` field, waits for a
> UI client to connect (`--connect-timeout`, default 10s) before playing so
> opening events aren't broadcast into the void. Verified via
> `tests/test_replay.py`: a real WebSocket stub-consumer receives
> `runs/sample.jsonl` (hand-written) in order, byte-identical to the source,
> with no replay-only marker fields — confirming the "UI cannot tell the
> difference" requirement structurally, not just by assertion. `--stub-model`
> and `fixture/stubs/` do not exist yet (M3/M4 territory — no agent loop
> exists yet to stub). `runs/golden.jsonl` does not exist yet (M6).

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

> **PROGRESS (2026-09-08) — actual current repo layout vs. this plan:**
>
> ```
> miss-slaytona-forje/
>   .env                          # gitignored; DAYTONA_API_KEY
>   .gitignore
>   .snapshot_state.json          # gitignored; records snapshot/image mode + fixture hash
>   .venv/  .venvs/v1/  .venvs/v2/  # gitignored; see PROGRESS SUMMARY at top
>   miss-slaytona-forje-spec.md            # original, untouched
>   miss-slaytona-forje-spec.progress.md   # this file
>   requirements-dev.txt          # pyyaml, websockets, pytest, daytona
>   orchestrator/
>     __init__.py
>     events.py                   # BUILT — matches spec exactly (M1)
>     replay.py                   # BUILT — matches spec exactly (M1)
>     sandbox.py                  # BUILT — SandboxPool (M2)
>     manifest.py                 # BUILT, not in original spec — load_manifest() etc.,
>                                  #   extracted during a post-M2 tightening pass to
>                                  #   deduplicate constants that scripts/*.py had each
>                                  #   redefined
>     snapshot.py                 # BUILT, not in original spec — build_image()/
>                                  #   register_or_warm()/state load-save, extracted
>                                  #   from build_snapshot.py in the same tightening pass
>     run.py                      # NOT BUILT (M4)
>     agent.py                    # NOT BUILT (M3)
>     memory.py                   # NOT BUILT (M4)
>     llm.py                      # NOT BUILT (M3)
>     metrics.py                  # NOT BUILT (M4)
>   fixture/
>     cfp/ ...                    # BUILT (M1) — 12 modules per spec
>     reference_v2/cfp/ ...       # BUILT, not in original spec — hand-written pydantic v2
>                                  #   answer key, used only by M2's sandbox verification,
>                                  #   never uploaded into the real agent-facing snapshot
>     tests/ ...                  # BUILT (M1) — 12 test modules, 72 tests total
>     manifest.yaml                # BUILT (M1)
>     conftest.py                  # BUILT, not in original spec — sys.path shim
>     pytest.ini                    # BUILT, not in original spec — see §4.2 note
>     requirements-v1.txt / -v2.txt # BUILT (M1)
>     stubs/                       # created empty in M1, still empty — no --stub-model yet
>   scripts/
>     build_snapshot.py            # BUILT (M2) — now a thin CLI over orchestrator/snapshot.py
>     validate_fixture.py          # BUILT (M1)
>     verify_m2_sandboxes.py       # BUILT, not in original spec — the M2 done-when
>                                  #   verification script (12-file live sandbox check)
>     wipe_graph.py                # NOT BUILT (M4, needs Neo4j to exist first)
>     preflight.py                 # NOT BUILT (M6)
>   ui/                            # NOT BUILT (M5) — directory doesn't exist yet
>   queries/                       # NOT BUILT (M6) — directory doesn't exist yet
>   runs/
>     sample.jsonl                 # BUILT, not in original spec — hand-written, used by
>                                  #   tests/test_replay.py
>     golden.jsonl                 # NOT BUILT (M6)
>   tests/
>     test_replay.py               # BUILT (M1) — the stub-consumer test, lives at repo
>                                  #   root rather than inside orchestrator/, since it
>                                  #   exercises the WebSocket contract end-to-end rather
>                                  #   than unit-testing one module
> ```

---

## 15. Build order

Six milestones. Each has a runnable "done when". Do not proceed until the current one passes.

**M1 — Fixture and harness. No LLM, no memory, no Daytona.**
Write the 12 modules, the tests, the manifest. Write `validate_fixture.py`. Write the event schema and the replay player.
*Done when:* `validate_fixture.py` passes all five assertions, and `replay.py` can play a hand-written sample jsonl to a stub consumer.

> **PROGRESS (2026-09-08): DONE.** Both done-when conditions verified green
> — see §4.3 and §13 notes above.

**M2 — Sandbox harness. Still no LLM.**
Build the snapshot. Run the *known-correct* migrated version of each file through a real Daytona sandbox and confirm the tests pass. This proves the whole execution path with zero model risk.
*Done when:* all 12 files pass in real sandboxes, every sandbox is confirmed deleted, and `sandboxes_live` returns to zero.

> **PROGRESS (2026-09-08): DONE, verified live against a real Daytona
> account** (not a mock/dry-run). `scripts/verify_m2_sandboxes.py` — one
> real sandbox per file, `fixture/reference_v2/` uploaded, that file's own
> test module run, sandbox deleted. Last run: 12/12 PASS,
> `sandboxes_live` final = 0, independently re-confirmed via a full-account
> `client.list()` showing zero sandboxes anywhere (not just zero for this
> run_id). Design note: uploads the *entire* `reference_v2/cfp` tree per
> sandbox, not just the one target file, so files with cross-module imports
> (`scoring.py` → `models/review.py`, etc.) don't spuriously fail because
> some unrelated file is still in its v1 form — this script validates the
> sandbox *pipeline*, not agent migration ordering.

**M3 — Single agent, no memory.**
One agent, real SGLang (or `--stub-model`), full loop, sequential over 12 files. Also: run the §7 isolation verification test.
*Done when:* one agent migrates at least 8/12 files unaided, and the isolation mechanism is chosen and recorded.

> **PROGRESS (2026-09-08): NOT STARTED.** Blocked on GPU host access — see
> §10 note above for the full local-MLX-backend investigation and why the
> decision was made to rent a real CUDA GPU instead of continuing that
> path. Next concrete action: book/rent a GPU host (§17 checklist item,
> untouched so far), install plain SGLang there, then build
> `orchestrator/agent.py` + `orchestrator/llm.py`.

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

> **PROGRESS (2026-09-08):** M4/M5/M6 not started — no notes beyond what's
> in the PROGRESS SUMMARY at the top of this file.

---

## 16. Things to verify, not assume

The following were read from documentation and may differ in the installed version. **Check the actual signatures in the installed package before building on them.** Do not guess.

- `reasoning.record_tool_call(...)` — the documented example passes a step id as its first argument (`record_tool_call(step.id, "tool", params, results)`), which implies a step object obtained from somewhere not shown. Inspect the `ReasoningMemory` source. If steps are awkward, `record_tool_call` is optional for this demo — `start_trace` and `complete_trace` carry the load.

  > **PROGRESS (2026-09-08):** not yet checked — no Neo4j/`neo4j-agent-memory` work done yet (M4).

- `long_term.add_entity(...)` returns a tuple in at least one documented example (`entity, _ = await ...`). Confirm the shape.

  > **PROGRESS (2026-09-08):** not yet checked (M4).

- `reasoning.search_traces(...)` returns `(ReasoningTrace, score)` tuples. Confirm `min_score` semantics and the embedding model in use.

  > **PROGRESS (2026-09-08):** not yet checked (M4).

- Whether `user_identifier` scopes reasoning traces or only long-term entities. **This is the §7 verification test and it gates the design.**

  > **PROGRESS (2026-09-08):** not yet checked — this is the M3 mandatory
  > verification step, not yet run.

- `AsyncDaytona` sandbox teardown is variously `delete` and `remove` in the docs. Use whichever exists; wrap in `finally` either way.

  > **PROGRESS (2026-09-08): CHECKED.** It's `delete` — both
  > `client.delete(sandbox)` and `sandbox.delete()` exist; `orchestrator/sandbox.py`
  > uses `client.delete(box)`, wrapped in `finally` as directed.

- Exact current Devstral Small model tag on Hugging Face, and whether an FP8/AWQ build is available for your card.

  > **PROGRESS (2026-09-08):** not yet checked against a real CUDA card
  > (M3, once a GPU host exists). The local MLX detour used
  > `Ministral-8B-Instruct-2410` (a genuinely small Mistral model, not
  > Devstral) purely to test the SGLang integration path itself — the real
  > M3+ build should use whatever Devstral Small tag/quantization this note
  > was asking about, checked against the actual rented card.

- SGLang metric prefix (`sglang:` vs `sglang_`). Probe both at startup.

  > **PROGRESS (2026-09-08):** not yet checked against a real server (M3).

The package is **async-only** — every memory operation is a coroutine. There is no sync fallback.

---

## 17. Pre-flight checklist

`scripts/preflight.py` runs everything mechanical. The rest is human.

**Weeks ahead:**
- [ ] Daytona account created, verified, limit increase requested — **do this first, it has a waiting period**
- [ ] GPU host booked for rehearsal and talk day
- [ ] Neo4j 5.20+ running, `neo4j-agent-memory` installed against it

> **PROGRESS (2026-09-08):** Daytona account created and in active use
> (free credits) — ✅ created, ❌ NOT verified for persisted snapshots (see
> §9 note; image-mode fallback in use instead), limit increase not
> requested (not yet needed at `swarm_size` this small / M2's single-sandbox-
> at-a-time verification pattern). GPU host: ❌ not booked — this is the
> live blocker for M3. Neo4j: ❌ not started at all.

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

> **PROGRESS (2026-09-08):** not started (M6, needs M4's graph to exist
> first).

---

## 19. Definition of done

The build is finished when a cold laptop, following `preflight.py` and nothing else, can run the demo end to end in under four minutes, with the flash firing at least three times, `token_ratio` above 2, and a one-keystroke fallback to a recorded run that is visually indistinguishable from live.

> **PROGRESS (2026-09-08):** far from done — M1/M2 of 6. See PROGRESS
> SUMMARY at the top of this file for the punch list into M3.
