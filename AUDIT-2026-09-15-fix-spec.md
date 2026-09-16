# Audit + fix spec — 2026-09-15

> **STATUS: implemented.** This document is kept as the diagnosis. What was
> done about it, what it changed, and what is still open is in
> [FIXES-2026-09-15.md](FIXES-2026-09-15.md). Hard-won operational knowledge
> extracted from the code comments now lives in
> [NOTES-hard-won.md](NOTES-hard-won.md).

Read-only audit. No code was changed. Every claim below was checked by running
something, not by reading a comment.

**What I ran:** `pytest tests` (52 pass); the three `scripts/*.py` entry points; the
fixture suite under both the pristine-v1 and the `reference_v2` trees using the real
agent venv; the last 20 `runs/*.jsonl` event logs; `runs/accumulation.csv` (runs
63–102); the live Vibe transcripts in `/tmp/msf-agents/*.vibe/`; a rendered
`config.toml`; and read-only Cypher against the configured Neo4j.

---

## 0. The verdict in one paragraph

The harness runs. It does not measure anything. In **19 of the last 20 runs, zero
attempts were graded**: `SANDBOX_CREATED = 0`, `ATTEMPT_DONE = 0`, `MEMORY_WRITE = 0`.
Daytona — documented as "the **only** success oracle" — is never invoked after the
baseline. Every agent spends its entire wall-clock budget inside **one** Vibe
invocation, never gets a verdict, and its trace is closed as
`"ran out of time mid-attempt"`. Those traces are then filtered out of retrieval by
design, so warm retrieves nothing, warm ≡ cold, and `token_ratio` is noise around 1.0
(0.79–1.26 across 40 consecutive runs, `warm_best = cold_best = 0` in all 40,
`mem_calls = 0` in all 40).

Everything downstream of the verdict — the shim check, the gutted-code check,
`errors_cleared`, `observed_fix`, `_trim_error_for_prompt`, `_localize_sandbox_paths`,
the retry prompt, `MEMORY_WRITE` — is **dead code at runtime**. That is roughly 600 of
the 617 executable lines in `orchestrator/vibe_agent.py`. The file is 1,703 lines, 54%
of it prose about failures that no longer reproduce because the code paths they describe
no longer execute.

The fix is not more machinery. Three changes (§1.1–§1.3) restore the loop. Then
delete.

---

## 1. Blockers — the run measures nothing without these

### 1.1 One Vibe invocation consumes the whole run budget

`vibe_agent.py:1484` passes `timeout_s=remaining` — the *entire* remaining run
deadline — to `_run_vibe`. Vibe's own agent loop then runs until it decides to stop.
It never does: measured on the last run, `cold-0` made 22 assistant turns and
`warm-0` 19, **zero text-only assistant turns in either** (the loop's only exit
condition), at ~25 s/turn over ~540 s.

So: one attempt per agent, ever. `ATTEMPT_START = 8` and `FILE_DONE = 8` with
`SWARM_SIZE = 4` means exactly 1 attempt × 8 agents.

Then `pool.run_pytest` is called with
`timeout=max(0.0, deadline - time.monotonic())` → **0.0** → instant `TimeoutError` →
`break`. No Daytona run, no verdict, no memory write.

The module comment at `vibe_agent.py:116-133` removed the per-invocation cap on the
grounds that "every result observed under that cap was an artifact of the cap." That
was true of a 180 s cap. Removing it entirely replaced the artifact with a harness
that cannot iterate at all.

**Fix.** Give one Vibe turn a bounded slice of the budget:

```python
ATTEMPT_BUDGET_S = 150.0          # ~6 turns at the measured 25s/turn
VERDICT_RESERVE_S = 90.0          # upload + sandbox create + pytest

slice_s = min(ATTEMPT_BUDGET_S, max(0.0, remaining - VERDICT_RESERVE_S))
if slice_s < 20:                  # not enough left to be worth starting
    break
vibe_exit_code, vibe_output = await _run_vibe(task, timeout_s=slice_s, ...)
```

and give the Daytona check its own reserve rather than `deadline - now`:

```python
result = await asyncio.wait_for(
    pool.run_pytest(...),
    timeout=max(30.0, min(VERDICT_RESERVE_S, deadline - time.monotonic() + 30.0)),
)
```

Tune `ATTEMPT_BUDGET_S` from the measured turn rate, and say so in one line. This is
the single highest-value change in the document: it is what turns 1 ungraded attempt
into 3–4 graded ones.

### 1.2 ~60 s of every run budget is spent before the agents start

`run.py:532` sets `deadline = time.monotonic() + hard_deadline_s` at the *top* of
`main_async`, then does the seeding, `render_config` × 8, `check_mcp_servers`
(two configs, four MCP servers, with 120 s smoke-test calls against OpenAI and Aura),
the graph counts, `pool.sweep()`, the two memory warmups, and the baseline Daytona
pytest — **all inside the deadline**.

Evidence: `RUN_START` is stamped at `t = 68.9 s` in the last run; the reported
`wall-clock` is 533–546 s for every `--deadline-s 600` run in `accumulation.csv`,
because `wall_start` is taken *after* setup while `deadline` was taken before it.

**Fix.** Move the `deadline` computation to immediately before `wall_start`, and
report both numbers (`setup_s`, `agent_s`) in the summary.

### 1.3 The oracle never runs, so memory has nothing true to store

Consequence of 1.1 and 1.2, but it needs stating separately because it is what makes
the graph useless:

```
ReasoningTrace              172
  outcome "ran out of time mid-attempt"   168   (98%)
  outcome with real content                 4
  success = true                            0
ReasoningStep                89      (~0.5 steps per trace)
```

`ScopedMemory._reasoning_context` drops every `_NO_VERDICT` trace — correctly — so
**warm retrieval returns the empty string on essentially every call**. That is the
whole explanation for `token_ratio ≈ 1.000` and for the flat accumulation series;
it is not a model-size finding and not a memory finding.

Once 1.1/1.2 land, re-measure before changing anything else in §2.

---

## 2. The memory layer is wired to the wrong thing

### 2.1 The agent-callable half is never used

`mem_calls = 0` in **all 40** recorded runs, despite `_MEMORY_TOOLS_GUIDE`
(`vibe_agent.py:477`) and 20 published `memory_*` tools. In the last run `warm-0`
called `graphrag_neo4j_vector` once and `memory_*` zero times in 19 turns.

So warm's *only* live memory channel is the deterministic `get_context()` splice —
which per 1.3 returns nothing. The warm arm has, empirically, no memory.

**Fix.** Do not add more prompt. Pick one channel and make it work:

- Keep the deterministic splice (`get_context` before each attempt). It is the
  `memory_agent_mvp.py` pattern and it does not depend on the model's choice.
- Drop `_MEMORY_TOOLS_GUIDE` and the 20-tool MCP registration for now. 20 tool
  schemas on every warm request is a per-call prompt-token tax on the arm whose
  token count is the headline metric, in exchange for zero measured calls. Re-add
  later with `--profile core` if you want the agent-callable story on stage.

### 2.2 Entity extraction is mining Vibe's line-number gutter

Read-only query against the live graph:

```
Entity total                                229
  names matching ^[0-9]+→$                   78   (34%)
```

Sample entity names: `'100→'`, `'171→'`, `'0.17s'`, `"'1"`, `'+ args)\\n\\n**V1'`.

Cause: `_replay_session_messages` stores every `role: "tool"` result as a `:Message`,
and `read_file` results are rendered by Vibe with a `123→` line gutter. The extraction
pipeline then names each gutter token as an `:Entity:Object`. A third of the long-term
graph is line numbers, and `MemoryClient.get_context(include_long_term=True)` is what
serves it back to warm agents.

**Fix.** Stop storing tool results as messages. The tool result is *already* stored,
capped, as the owning `ReasoningStep.observation` — the code's own `_cap` docstring
says so. Store only `role == "assistant"` content/reasoning as `:Message`. One
condition, ~60 lines of `_tool_results`/`_cap` machinery deleted, and the entity graph
stops being junk.

### 2.3 Deduplication is not merging

```
pydantic                       ['Entity','Organization','Company']
pydantic                       ['Entity','Organization','Company']
pydantic                       ['Entity','Object','Document','Device']
pydantic-settings              x3
root_validator                 ['Entity','Object']  and  ['Entity','Person']
basesettings-has-moved-...     x3
```

The build spec §5 asserts "when three warm agents independently hit the same pattern,
the resolver merges them into one node rather than three." It is not happening. Same
name, three nodes, contradictory type labels.

**Fix.** Check whether `ExtractionConfig(enable_llm_fallback=False)`
(`memory.py:171`) also suppresses the resolution pass, and whether
`DeduplicationConfig` is being constructed at all. This is a `MemorySettings`
question, not a code question — measure it with a two-message script before touching
anything.

### 2.4 The warmup message leaks the answer into warm's scope

`run.py:600-604` writes, on every run, under `user_identifier="warm"`:

> "Warmup message: migrating fastapi_mail config.py from pydantic BaseSettings to
> pydantic_settings for Pydantic v2."

Confirmed in the graph: `Conversation {session_id: 'warmup', user_identifier: 'warm'}`,
and `pydantic_settings` / `pydantic-settings` / `pydantic BaseSettings` all present as
warm-scope entities. That sentence is the correct fix for the first file in the failure
chain, placed in the warm arm's memory and nowhere in cold's.

**Fix.** Warm up with a string that has nothing to do with the task. Anything with the
same length will load the same models.

### 2.5 `mcp-neo4j-vector-graphrag` is a third product duplicating a package method

`GRAPHRAG_RETRIEVAL_QUERY` (`vibe_agent.py:101`) walks
`(:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)` and formats thought/action/
observation. `neo4j_agent_memory.memory.reasoning` already ships:

- `search_steps(query, limit, success_only, threshold)` → `ReasoningStepWithContext`
- `get_trace_with_steps(trace_id)`
- `get_context(query, max_traces=…, include_successful_only=…)` — which is a
  line-for-line match for `_reasoning_context`'s output shape, verified in the
  installed source

Cost of the duplicate: a separate `uv` project, a separate lockfile, hand-written
Cypher, `INDEX_NAME`/`EMBEDDING_MODEL` that must be kept in step with two other
places — and `harness/neo4j-mcp-experiments/` is **untracked in git**. A fresh clone
registers a `graphrag` server whose command does not exist, `check_mcp_servers`
returns a problem, and `main_async` returns 1. **The warm arm cannot start from a
clean checkout.**

**Fix.** Delete the `graphrag` registration and `GRAPHRAG_RETRIEVAL_QUERY`. If
step-level retrieval is wanted, call `reasoning.search_steps()` from
`ScopedMemory`.

### 2.6 `_reasoning_context` should be four lines

`ReasoningMemory.get_context(query, max_traces=5, include_successful_only=False)`
produces the identical `Task / Similarity / Outcome / Success` block. The
hand-rolled version exists for two legitimate reasons (drop open + no-verdict traces;
break the similarity tie on `tests_passed`) and one that evaporates once §1.1 lands
(everything is a no-verdict trace).

**Fix.** Keep the tie-break — the 0.9996-tie finding is real and correct. Build it
on top of `get_similar_traces` + `_trace_scores` and drop the re-implemented
formatter, reusing the package's. ~40 lines out.

---

## 3. Wrappers inserting themselves into the shipped stack

### 3.1 `PROXY_MAX_TOKENS=2048` is injected into every request, by default

`id_fix_proxy.py:131` — `MAX_TOKENS = int(os.environ.get("PROXY_MAX_TOKENS", "2048"))`,
applied to every request that does not already carry `max_tokens`, which is every
request Vibe sends.

The README's first non-negotiable is "Vibe must stay vanilla." This is a wire-level
mutation of every completion, and the justification in the docstring is entirely about
Qwen3's reasoning mode — the cheap stand-in. On Mistral Small 4 a 2,048-token ceiling
will truncate a turn mid-tool-call and produce malformed JSON, which is exactly the
"agents produce unreliable tool calls" symptom this project already spent twelve runs
chasing.

**Fix.** Default `PROXY_MAX_TOKENS=0`. Keep the knob, opt in for Qwen experiments
only. The id rewrite and the usage tally are the proxy's legitimate jobs; those stay.

### 3.2 The two AST oracle patches can veto a green suite

`v1_shim_files` and `gutted_files` both force `success = False` **and** `passed = 0`
on a suite that pytest reported green. The reasoning is sound (both holes are real and
documented), but:

- `gutted_files` is a heuristic over *the whole uploaded package*, including files the
  agent never touched. A legitimate pass-through validator anywhere in the tree pins
  the run at 0 forever.
- Forcing `passed = 0` and overwriting `signature` with a synthetic string
  (`"pydantic.v1 compatibility shim still imported by: …"`) feeds that synthetic
  string into `seen_signatures`, so **gaming the oracle inflates `errors_cleared`** —
  the metric used to compare warm against cold when neither converges.

**Fix.**
- Keep both as gates on `success`. They are correct and cheap.
- Stop overwriting `passed` and `signature`. Report `shimmed` / `gutted` as their own
  fields on `MigrationResult` and their own event payload, and exclude synthetic
  signatures from `seen_signatures`.
- Longer term the honest fix is the oracle, not the patch: the suite is the merge
  commit's and genuinely cannot see either hole.

### 3.3 The containment check is blind to three of Vibe's five write primitives

`check_containment` inspects `edit` and `write_file` tool calls. Vibe also ships
`bash`, `git_bash` and `experimental_bash`, all enabled, under `--trust
--auto-approve`, with sibling agent checkouts one `..` away in `/tmp/msf-agents/`.
An agent that writes with `sed -i` or `cat >` escapes the check entirely — and the
transcripts show agents using `bash` constantly (7 of `cold-0`'s 22 calls).

**Fix.** Either add a `bash`-command scan for paths outside `own_dir`, or stop
claiming the check is a backstop. Given the two-hour budget: downgrade the claim in
the README to "covers `edit`/`write_file` only" and move on.

### 3.4 `_STRIPPED_ENV` is cosmetic — the secrets are in a sibling file

`vibe_agent.py:632` strips `OPENAI_API_KEY` and `NEO4J_PASSWORD` from the agent's
environment. `render_config` then writes both, in plaintext, into
`/tmp/msf-agents/{swarm}-{i}.vibe/config.toml` — a **sibling of the agent's cwd**,
readable with one `cat`, by every agent including cold's.

So the "cold agents have zero path to Neo4j — not gated, none" claim holds only
because no cold agent has happened to read a file 40 characters away.

**Fix.** Two hours is not enough to sandbox this properly. Minimum honest change:
put the vibe homes somewhere that is not a sibling of the checkout (e.g.
`$XDG_STATE_HOME/msf/{swarm}-{i}`), and soften the claim in `memory.py`'s module
docstring to what is actually true.

**Also: rotate the OpenAI key and the Aura password.** Both are in plaintext in
`/tmp`, and both appeared in this audit's terminal output.

---

## 4. Dead and broken code

| Item | Status | Evidence |
|---|---|---|
| `scripts/run_m3.py` | **broken** | `ImportError: cannot import name 'FileResult'` — `migrate_file`/`FileResult` were removed from `vibe_agent.py` |
| `scripts/validate_fixture.py` | **broken** | `KeyError: 'files'` — targets the abandoned synthetic CFP fixture and its `P1…P6` manifest |
| `scripts/verify_m2_sandboxes.py` | **broken** | `manifest["files"]` + `pool.run_pytest(test_target=…)`; the parameter is `test_command`. Also the only entry point that never calls `load_dotenv()` |
| `install_cleanup_handlers` | **never called** | 0 references. Ctrl-C mid-run leaks paid Daytona sandboxes |
| `ScopedMemory.prior_traces` | **never called** | 0 references |
| `MEMORY_READ`, `FILE_CLAIMED`, `METRICS` | **never emitted** | declared in `EVENT_TYPES`, absent from every `emit` call site in `run.py`/`vibe_agent.py` |
| `EventBus.broadcaster.serve()` | **never called in a live run** | only `replay.py` serves. No UI can connect to a live run |
| `ui/`, `queries/` | **empty directories** | the "flash" and the closing Cypher — the spec's two named wow moments — do not exist |
| `runs/golden.jsonl` | **missing** | the documented stage fallback |
| `orchestrator/replay.py` + 2 test files | **working, for a UI that does not exist** | |
| `AGENT_ROOT` | **defined twice** | `run.py:200` and `vibe_agent.py:66`, same default, same env var |
| `check_containment` | **wrong annotation** | declared `-> list[str]`, returns a 2-tuple |
| `run.py:1057-1059` | **indentation bug** | `return 1` is inside the `for problem in problems` loop, so only the first preflight problem is ever printed |
| `agent_worker` bare retry | **unbounded tight loop** | `except Exception: print(...)` with no sleep and no cap. `FileNotFoundError` (missing `vibe` binary) is not in `_HARNESS_BUGS`, so a missing binary spins and prints until the deadline |

---

## 5. Environment and reproducibility

- **`requirements-dev.txt` cannot reproduce the working environment.** It pins bare
  `neo4j-agent-memory`. The configured embedder is `openai/text-embedding-3-small`,
  which needs the `[openai]` extra; the installed venv also has `gliner 0.2.29`
  (the `[gliner]`/`[extraction]` extra), which is what makes
  `enable_llm_fallback=False` viable. Neither is declared. A fresh install gives a
  non-working orchestrator.
  → `neo4j-agent-memory[openai,gliner,spacy]`.
- **`.venvs/v1` and `.venvs/v2` are near-empty** (10 and 14 packages, no `fakeredis`).
  `validate_fixture.py` steps 3–5 cannot pass even after the `KeyError` is fixed.
- **`harness/neo4j-mcp-experiments/` is untracked** — see §2.5. Blocks warm on a clean
  clone.
- **Neo4j is Aura, not local Docker.** `.env` points at
  `neo4j+s://…databases.neo4j.io`. Every comment in `memory.py` describes "the local
  Docker Neo4j", and `--reset-memory` / `scripts/reset_memory_indexes.py` will
  `DETACH DELETE` and drop indexes on the hosted instance. Also: every stored message
  is now a round-trip to OpenAI *and* a round-trip to Aura, paid only by warm.
- **`memory.py`'s comments contradict its code.** `build_settings`'s docstring says
  "No API key needed -- the embedder is local (see EMBEDDING_MODEL)"; the module-level
  block at line 76 says "Embeddings are local again (BAAI/bge-small-en-v1.5, 384
  dimensions)". `EMBEDDING_MODEL = "openai/text-embedding-3-small"` (1536). Three
  statements, one file, mutually exclusive.

---

## 6. Fixture / oracle facts worth knowing

- **Ground truth passes: 33/33.** Verified against `fixture/reference_v2` + the real
  `tests/` in the agent venv.
- **Ground truth takes 70.5 s on this machine**, not the spec's mandated <25 s. Cause
  found: `email.utils.make_msgid()` → `socket.getfqdn()` → 5.01 s reverse-DNS timeout,
  × 14 tests. Measured directly (`getfqdn 5.011s`).
  - This is almost certainly a macOS/local-DNS artifact and probably does not
    reproduce in a Linux container — **verify it in Daytona before assuming**.
  - It matters regardless: the task prompt tells agents to run the suite locally
    "after every change". Right now they never get past the collection error so it
    costs nothing. The moment an agent fixes the imports, its self-check jumps from
    ~1 s to ~70 s on the demo laptop, and at 25 s/turn that eats attempts.
- **`_collect_file_contents` uploads only `<package_path>`.** A new file the agent
  creates outside `fastapi_mail/` (a compat shim, a helper module) passes locally and
  is silently absent in the sandbox. Known-limitation comment covers deletion, not
  creation.
- **The local pytest command always exits 0.** `… 2>&1 | tail -30` makes the exit
  status `tail`'s. Confirmed in the transcripts: `exit_code: 0` on a collection
  error. Intentional per the prompt's note, but the agent can only judge by reading
  stdout — worth stating in the prompt rather than leaving it to be inferred.

---

## 7. Verbosity — measured

Tokenised comment/docstring line counts across the orchestrator and proxy:

| file | lines | comment | docstring | ~code | prose |
|---|---|---|---|---|---|
| `orchestrator/vibe_agent.py` | 1703 | 468 | 459 | ~617 | **54%** |
| `orchestrator/run.py` | 1065 | 256 | 244 | ~446 | **47%** |
| `orchestrator/memory.py` | 454 | 85 | 181 | ~141 | **59%** |
| `harness/id_fix_proxy.py` | 315 | 15 | 129 | ~120 | 46% |
| **total** | | **840** | **1132** | **~1660** | **54%** |

Plus 5,714 lines of `*.progress*.md` / `FINDINGS` / `HANDOFF` / `AGENT-MEMORY-*.md`,
and a 673-line build spec describing a twelve-module CFP fixture with `P1…P6` pattern
tags that was replaced by `fastapi-mail` and now only exists in three broken scripts.

The commentary is not decoration — most individual notes are true and were
expensive to learn. The problem is that they are attached to code paths that no longer
run, so the file reads as a defended design when it is a graveyard. Two rules going
forward:

1. **A run-number anecdote belongs in a findings log, not above a `def`.** Keep a
   one-line *why* at the code; put the measurement in the log and cite it.
2. **If a guard's failure mode no longer reproduces, delete the guard and the note.**
   `README.md` is the one document in the repo that describes reality; make it the
   only narrative one.

---

## 8. Ordered work list for a two-hour session

**Hour 1 — make the loop measure something.**

1. §1.1 Time-box one Vibe invocation; reserve budget for the Daytona verdict.
2. §1.2 Start `deadline` at `wall_start`; report `setup_s` and `agent_s` separately.
3. §3.1 Default `PROXY_MAX_TOKENS=0`.
4. §2.4 Neutral warmup string.
5. Run once at `--deadline-s 900 --swarm-size 2`. **Gate: `ATTEMPT_DONE > 0` and
   `SANDBOX_CREATED > 0`.** Nothing below matters until that gate passes.

**Hour 2 — clean the memory path, then delete.**

6. §2.2 Store only assistant messages; drop `_tool_results`.
7. §2.5 Delete the `graphrag` registration + `GRAPHRAG_RETRIEVAL_QUERY`.
8. §2.1 Delete `_MEMORY_TOOLS_GUIDE` and the 20-tool MCP block (re-add later,
   deliberately, with a profile).
9. §4 Delete `run_m3.py`, `verify_m2_sandboxes.py`, `validate_fixture.py`,
   `prior_traces`, `install_cleanup_handlers` (or wire it — pick one),
   `ui/`, `queries/`. Fix the `run.py:1057` indentation.
10. §3.2 Stop overwriting `passed`/`signature` in the shim and gutted branches.
11. §5 Fix `requirements-dev.txt` extras; commit or vendor whatever `graphrag`
    needed (if you keep it); reconcile `memory.py`'s comments with its code.
12. Rotate the OpenAI key and the Aura password.

**Explicitly not in scope for two hours**, and worth saying out loud: the UI, the
flash, the closing Cypher, `golden.jsonl`, and `token_ratio > 2`. Those are M5/M6 and
they are downstream of a loop that grades attempts. There is no point tuning
`min_trace_score` against a graph of 168 no-verdict traces.

**One thing to decide before the talk, not during it.** At 25 s per turn with 8
agents on one A40, an agent gets ~20 turns per 600 s no matter what memory does. The
binding constraint on this demo is currently throughput, not knowledge. Either raise
throughput (fewer agents per card, a second card, or a smaller/faster model) or lower
the bar (a shorter failure chain than `fastapi-mail`'s five-fix import cascade).
Memory cannot show a 2× token gap inside 20 turns if a single dead end costs 6 of
them.
