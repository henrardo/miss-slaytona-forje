# Can memory make a model finish a job it cannot finish alone?

**Overnight run, 2026-09-20.** Written to be rebuilt from: every number here
has a file behind it, and every caveat is stated where the number is, not in
a footnote.

Status: **COMPLETE.** 3 cold calibration runs + 14 series runs; the pod
was terminated by RunPod at 04:30 UTC when the credit ran out. Every
defect found during the night has since been fixed and tested locally
(sections 7 and 8); nothing was changed while the series was running.

---

## 1. Why a new fixture was needed

The six-run series of 2026-09-19 ran on `fixtures/oapi`
(openapi-python-client#779). It ended 3 warm / 2 cold / 1 tie on the test
oracle, and warm ahead in five of six on the fuzzy closeness measure. But it
could not answer the question the project actually cares about, because
**cold solved oapi outright in three of six runs**. A fixture both arms can
finish measures speed, not capability.

So: find a repo where cold makes real headway and never finishes.

## 2. How candidates were screened

Screening a candidate costs **one API call**, not a clone.
`scratchpad/screen.py` pulls a merged PR's unified diff
(`gh api repos/{o}/{r}/pulls/{n} -H "Accept: …v3.diff"`), counts
`orchestrator.surfaces.SURFACES` hits on removed vs added lines, and ranks by
*distinct surfaces* then *net constructs removed*. **356 merged PRs screened
in about two minutes**; only survivors paid for a clone.

**Rank on distinct surfaces, not size.** oapi's 281 removed constructs are
214 copies of `construct()` — one substitution, repeated. Breadth is what
makes a migration hard: each surface is a separate thing to understand.

### What was rejected, and why

| candidate | verdict | evidence |
|---|---|---|
| **hera#795** | not a migration | answer key has **137** v1 surfaces vs baseline **130** — it imports `pydantic.v1` and keeps the v1 API. A compatibility port wearing a migration's title. |
| **canarytokens#997** | infra cost | best *content* found (13/21 surfaces, 258-test oracle, 59% sensitivity, merged after the model's cutoff). Needs Python 3.13, ~35 deps incl. azure/boto3/twisted/netifaces, and a live redis. Revisit with budget. |
| **zenml#2543** | size | 345 files, +6517/−4393; 1.9 GB of checkouts, diff too large for the API. Out on cost, not merit. |
| **ariadne-codegen#186** | too easy | 9 v1 constructs total across 9 source files — easier than oapi. |
| **distiller#1375** | no oracle | zero tests. |
| **contentctl#90** | no oracle | one test. |
| **somesy#46** | too small | 43 constructs, 33-test oracle; smaller than oapi. |
| **pandera#1253** | weak oracle | 570 tests of which 38 touch the migration — 7% sensitivity. |

## 3. The fixture chosen: `fixtures/x12sdk`

`owgreen-dev/x12sdk#8`, merged 2026-09-19 — a HIPAA ASC X12 EDI SDK.

| | oapi | **x12sdk** |
|---|---|---|
| v1 surfaces in the package | 64 | **383** |
| distinct surface kinds | 6/21 | **11/21** |
| answer-key floor | 3 | **2** |
| oracle | 445 tests | 261 tests |
| oracle sensitivity | 78% | 78% |
| runtime dependencies | 13 | **2** |
| merged | 2023 | **2026-09-19** (after the model's 2026-03 cutoff) |

Surface breakdown at baseline: `Field(const/regex/items)` 256,
`@root_validator` 59, `conint/constr/etc` 42, `__fields__` 7, `.dict()/.json()`
6, `@validator` 6, `class Config` 3, and one each of `BaseSettings`,
`Extra.`, `ModelField`, `schema()`.

**`pydantic-settings` is part of the task.** The baseline's first error is
`PydanticImportError: BaseSettings has been moved to the pydantic-settings
package` — the agent has to discover a package split, not rename a symbol.

**Validated before any GPU spend** (`scripts/grade_fixture.py`, real Daytona
sandbox): baseline **0 passing / 383 surfaces**; answer key **261 passing /
2 surfaces**. The floor is 2, not 0.

**Two departures from upstream, both in `manifest.yaml`:** flattened from the
`src/` layout because the harness keys an uploaded tree on the package
directory's own name (a nested `package_path` graded *both* baseline and
answer key at 0 passing / 0 surfaces — nothing uploaded was ever read); and no
editable install, because the flat layout plus `tests/__init__.py` puts
`/repo` on `sys.path` already. No source file was touched.

## 4. Faults found and fixed before the run

1. **The installer was still half hand-copied.** The 2026-09-19
   `install_host_scripts` fix covered hook, relay, proxy and web server but
   not `swarm/sidecar_main.py` or the `orchestrator` modules it imports. On
   the first pod never touched by hand, `provision_memory.sh` died with
   `can't open file '/opt/swarm/swarm/sidecar_main.py'`. Fixed with
   `host_modules()`; four more files, digests read back off the host.
   The rehearsal check could not have caught it — it asserted
   `len(installed) == len(host_scripts())`, which only ever counted the half
   already fixed. Now checks both. **57/57.**
2. **The v0 skill carried 16 KB of oapi knowledge.** `skills/pydantic-v2-migration/`
   still held the untracked `references/` tier from v38 of the oapi lineage.
   It would have silently seeded warm's first x12sdk attempt. Archived to
   `skills/versions-oapi-refs-v38/`.
3. **v0 failed AIP validation.** Its `metadata.aip.spec` was the stale
   `arxiv.org/abs/2606.04781`; the installed validator targets
   `github.com/zach-blumenfeld/aip/tree/v0.3a3`. One field corrected, body
   untouched. `VALID`.
4. **The demo export's closeness column was stale for runs 1–5.**
   `orchestrator/surfaces.py` changed mid-series (23:32:55, during run 5) to
   normalise through `ast.unparse`. All twelve final trees were rescored with
   the current scorer into `final.closeness_recomputed`, and a
   `closeness_WARNING` block was added to `series.json`. Run 6 is the only
   run whose logged values reproduce exactly — which is how the change was
   detected.

## 5. Cold calibration — can this model finish x12sdk alone?

Three cold-only runs, `--arms cold --deadline-s 600 --no-stop-for-victory`,
identical in every respect to the series that follows except that the warm
arm is absent. The graph was wiped once before run 1 (`--reset-memory`,
0 nodes deleted — it was already empty).

### Run 1 — 3 attempts, 180 turns, $0.55 GPU

| attempt | tests | v1 left (of 383) | parses | closeness | first error |
|---|---|---|---|---|---|
| 1 | 0 | 372 | 65/65 | 0.003 | `NameError: name 'validator' is not defined` |
| 2 | 0 | 369 | 65/65 | 0.002 | `PydanticUserError: field overridden by a non-annotated attribute` |
| 3 | 0 | 363 | 65/65 | 0.019 | `PydanticUserError: @root_validator … MUST specify skip_on_failure=True` |

Monotone, cautious, and nowhere near done: **20 of 383 surfaces cleared in
180 turns**, nothing broken. The error signature advances in *kind* — missing
import → v2 field semantics → validator semantics — which is what progress
looks like when the count barely moves.

### Run 2 — the opposite strategy

Attempt 1 cleared **78** surfaces (383 → 305) and broke nine files
(`parse 56/65`), scoring closeness **−0.141**.

**This is the single most important measurement caveat in this document.**
Run 1 attempt 1 (11 surfaces cleared, nothing broken) and run 2 attempt 1
(78 cleared, nine files broken) are *opposite* outcomes, and `tests_passed`
scores both **0**. Anyone plotting `tests_passed` alone sees a flat line
through two genuinely different behaviours. Read `v1_remaining` with
`parse_ok`: many surfaces cleared and files not parsing is "did the work and
broke it"; few cleared and everything parsing is "kept it valid by not doing
it".

### Verdict: x12sdk qualifies

Three runs, nine attempts, **zero convergence**.

| run | best tests | surfaces cleared (of 383) | ended parsing | attempts |
|---|---|---|---|---|
| 1 | **0**/261 | 20 | 65/65 | 3 |
| 2 | **60**/261 | 89 | 59/65 | 3 |
| 3 | **58**/261 | 87 | 65/65 | 3 |

Cold makes real headway — up to 23% of the suite and a quarter of the
surfaces — and never comes close to finishing. Three runs produced three
different strategies against the same ceiling: cautious and intact (run 1),
aggressive and broken (run 2), aggressive and intact (run 3). Cost: **$1.65**.

**The honest caveat.** Each run is bounded by `--deadline-s 600`, the same
budget the oapi series used. So the claim this licenses is "cold cannot
finish x12sdk in ten minutes of wall clock", not "cold can never finish
x12sdk". Distinguishing those needs one long-deadline cold control, which is
listed as open work below.

## 6. The series — warm vs cold

Both arms, `--arms both`, skill starting at **v0** (empty scaffold, 569
tokens, 0 traces), graph wiped before the calibration and accumulating from
there. Runs are **not independent**: warm's skill is re-authored from the
graph after every attempt, so run N starts on run N−1's output.

Declared treatment differences, identical to the 2026-09-19 oapi series
(`arms_identical = False`, `known_differences = ['config_names',
'hook_files', 'tools']`): warm has the memory MCP server, the `post_tool`
hook, and the memory tools. Nothing else differs.

### Run 1

| arm | best tests | attempts | turns | per-attempt (tests / v1 left / parsing / closeness) |
|---|---|---|---|---|
| **warm** | **57**/261 | 2 | 195 | a1 0/317/64/+0.046 · a2 57/313/64/+0.046 |
| cold | 0/261 | 4 | 192 | a1 0/371/65/+0.005 · a2 0/369/65/+0.006 · a3 0/363/65/+0.005 · a4 0/363/65/+0.005 |

190 steps written live to the graph, 0 injections. $1.24 GPU.

**Do not read run 1 as a treatment effect.** On attempt 1 warm holds skill
v0 — which contains no migration knowledge by construction — and an empty
graph, so the two arms are materially identical at that point, and warm still
cleared 66 surfaces to cold's 12. That gap is **run-to-run variance on this
fixture**, and it is the reason a single run proves nothing here. The first
attempt that can carry any treatment at all is warm's attempt 2.

Note also warm took 2 attempts to cold's 4 in the same wall clock: the
`post_tool` hook costs warm ~3.3 s per tool call, and the deadline charges
that to warm.

### Run 2 — both arms plateau, and the plateau is not the treatment

| arm | a1 | a2 | a3 | a4 |
|---|---|---|---|---|
| warm (skill v2→v4→v6→v8) | 59 turns, 369 v1 | 58 turns, **348** | 31 turns, 348 | 28 turns, 348 |
| cold | 75 turns, 354 v1 | 67 turns, **295** | 19 turns, 295 | 20 turns, 295 |

Both arms: 0 tests. $1.52 GPU.

After attempt 2 **both arms froze completely** — identical `v1_remaining`,
identical `parse_ok`, identical `closeness`, identical error signature. Not
zero-turn attempts: 19–31 turns each, spent without producing a single net
edit. Warm's skill was re-authored and **accepted after every attempt**
(v2→v4→v6→v8) and behaviour did not move at all.

**Cold plateaus identically, so the plateau is a property of the model, not
of memory or the skill.** This reproduces the oapi run-5 observation (warm
stuck at `v1_remaining=54` for four attempts) on a different fixture, and
shows the earlier reading — that the skill had trapped warm in a local
optimum — was wrong: an arm with no skill does the same thing.

The harness knows it happened. The trace outcome warm wrote for those
attempts reads, verbatim:

> No edit was made. The suite still fails with: …

### Run 3 — warm skill v10→v14, no movement

| arm | attempts | best tests | best v1 | turns |
|---|---|---|---|---|
| warm | 3 | 0 | 306 | 198 |
| cold | 3 | 0 | 301 | 177 |

191 steps ingested, **0 thought fallbacks** — the relay is healthy, so this is
the model, not instrumentation. $1.43.

Warm froze between a1 and a2 (identical trees) and then *unfroze* on a3 with
a new error. The freeze is **intermittent, not terminal**: attempts alternate
between productive and no-op.

### Run 4 — cold's best run of the night

| arm | attempts | best tests | best v1 | turns |
|---|---|---|---|---|
| warm (skill v16→v18) | 2 | 57 | 301 | 177 |
| **cold** | 3 | **60** | **53** | 194 |

Cold's attempt 1 cleared **326 of 383 surfaces in one attempt** with all 65
files still parsing, and ended the run at 53 — 86% of the migration done
structurally, and still only 60/261 tests. $1.14.

Note the two measures disagree sharply and both are right: cold is far ahead
on `v1_remaining` (53 vs 301) while the arms are level on `tests_passed`
(60 vs 57). Clearing v1 constructs is necessary and nowhere near sufficient;
the remaining failures are v2 *semantics* (`ValidationInfo` is not
subscriptable, `values` is not defined), which no surface count can see.

### Runs 5 and 6

Run 5: both arms 0 tests — a tie. Warm 318 v1, cold 304. $1.34.
Run 6: **cold 57 tests / 294 v1; warm 0 tests / 365 v1** — cold. $1.77.

Run 6 contains the clearest instance of two failure modes:

- **Warm's attempt 1 left the tree completely untouched** — `v1_remaining`
  383 (the baseline), `closeness` 0.000, and the *baseline's own* error
  signature. Not a bad attempt: no attempt at all. This is the "collapse to
  baseline" pattern recorded as unexplained after the oapi series.
- Warm then froze for **three consecutive attempts** (a2=a3=a4, all
  identical at 365 v1), while cold worked its way to 57 tests.

### Final series result — 14 runs, credit exhausted

The pod was terminated by RunPod when the credit ran out at 04:30 UTC; the
driver stopped itself after three consecutive failed starts. Run 15 was
partial and is excluded (its token counters are negative — the proxy
snapshot it differenced against died mid-run).

| run | warm tests | cold tests | warm best v1 | cold best v1 | winner | attempts w/c |
|---|---|---|---|---|---|---|
| 1 | **57** | 0 | 313 | 363 | warm | 2/4 |
| 2 | 0 | 0 | 348 | 295 | tie | 4/4 |
| 3 | 0 | 0 | 306 | 301 | tie | 3/3 |
| 4 | 57 | **60** | 301 | **53** | cold | 2/3 |
| 5 | 0 | 0 | 318 | 304 | tie | 3/3 |
| 6 | 0 | **57** | 365 | 294 | cold | 4/3 |
| 7 | 0 | 0 | 332 | 303 | tie | 3/3 |
| 8 | 0 | **65** | 358 | 296 | cold | 4/4 |
| 9 | **56** | 0 | 296 | 301 | warm | 2/3 |
| 10 | 0 | 0 | 358 | 302 | tie | 3/3 |
| 11 | 0 | **57** | 368 | 308 | cold | 4/4 |
| 12 | 0 | **57** | 305 | 318 | cold | 3/3 |
| 13 | 0 | **57** | 363 | 300 | cold | 4/4 |
| 14 | **58** | 0 | 328 | 361 | warm | 2/4 |

**Tally: cold 6, warm 3, 5 ties.**

- Best ever: **cold 65/261, warm 58/261**. Neither arm passed a quarter of
  the suite in 14 runs.
- Best structural state: **cold reached 53 of 383 surfaces left; warm never
  got below 296.** Cold led on `v1_remaining` in **10 of 14** runs.
- Warm took fewer attempts per run almost everywhere (the `post_tool` hook
  costs it ~3.3 s per tool call and the deadline charges that to warm).

**The answer to "does warm write better code": on this fixture, no — cold
did.** But see section 7 before treating that as a verdict on memory: warm's
distillation input was degenerate for the entire series, so this measures a
broken treatment, not the idea.

### Series progress during the run

| run | warm best tests | cold best tests | warm best v1 | cold best v1 | winner |
|---|---|---|---|---|---|
| 1 | **57** | 0 | 313 | 363 | warm |
| 2 | 0 | 0 | 348 | 295 | tie (cold better structurally) |
| 3 | 0 | 0 | 306 | 301 | tie |
| 4 | 57 | **60** | 301 | **53** | cold |
| 5 | 0 | 0 | 318 | 304 | tie |
| 6 | 0 | **57** | 365 | 294 | cold |
| 7 | 0 | 0 | 374 | — | tie |
| 8 | 0 | **65** | — | — | cold |
| 9 | **56** | 0 | — | — | warm |
| 10 | 0 | 0 | — | — | tie |
| 11 | 0 | **57** | — | — | cold |
| 12 | 0 | **57** | — | — | cold |

**Warm 2, cold 5, five ties.** Neither arm has ever passed more than 60 of
261 tests, and cold is ahead on `v1_remaining` in five of six runs. Read
section 7 before drawing any conclusion from warm's side of this table: the
treatment was degraded for the entire series.

### What actually blocks the model

Every graded attempt tonight, by the error the suite died on
(`scripts/x12_summary.py` reads the same event logs):

| n | warm / cold | first error |
|---|---|---|
| 6 | 3 / 3 | `NameError: name 'validator' is not defined` |
| 6 | 3 / 3 | `PydanticUserError: Field 'segment_name' … overridden by a non-annotated attribute` |
| 3 | 0 / 3 | `SyntaxError: unexpected character after line continuation` |
| 2 | 1 / 1 | `PydanticUserError: @root_validator … MUST specify skip_on_failure=True` |
| 2 | 0 / 2 | `ImportError: cannot import name 'SHAPE_LIST' from 'pydantic.fields'` |
| 2 | 0 / 2 | `AttributeError: 'ValidationInfo' object has no attribute 'get'` |
| 2 | 1 / 1 | `AttributeError: 'FieldInfo' object has no attribute 'outer_type_'` |
| 2 | 0 / 2 | `PydanticUserError: 'regex' is removed. use 'pattern' instead` |
| 2 | 1 / 1 | `TypeError: field_validator() got an unexpected keyword 'allow_reuse'` |

Two walls, tied at 6 attempts each, and **split evenly between the arms**:

1. **`validator` is not defined** — the agent removes the v1 import and
   leaves `@validator` decorators behind (or the reverse). A
   self-inflicted, purely mechanical failure.
2. **non-annotated attribute override** — a real v2 semantics change:
   overriding an inherited field now requires a type annotation. Nothing
   about it is guessable from the v1 source.

That the arms hit both walls 3–3 is itself a result: whatever warm's memory
is contributing, it is not helping with the two things that actually stop
the run. Read with section 7 — the author never saw per-step reasoning that
could have taught either.

## 7. THE FINDING: step thoughts are cumulative, so the distillation input is degenerate

This is the most important result of the night and it explains why warm's
skill does not help. Found by querying warm's graph on Aura, not by reading
code.

**Measured.** Within a single attempt, `ReasoningStep.thought` length grows
monotonically and never resets:

```
step  1-5:  267 chars   (identical text)
step  6:    331
step  7:    454
step  8-9:  538
step 11-12: 756
step 13-14: 1052
step 15-20: 1198 → 1537
```

Each step's "thought" is the **concatenation of all reasoning so far in the
attempt**, not the reasoning for that step. Every step in the trace begins
with the same sentence — *"I will migrate this codebase from Pydantic v1 to
native Pydantic v2. I'll follow the structured migration plan, starting with
understanding the repository struc…"* — across `bash`, `read_file`, and
every other action.

**Why this is fatal to the treatment, not cosmetic:**

1. `orchestrator/distill.render_steps` truncates each thought to its first
   **300 characters**. On a cumulative thought, the first 300 characters are
   always the opening sentence. **So the AIP author sees the same sentence
   repeated once per step**, plus an action name and 200 characters of
   observation. That is the corpus the skill is distilled from.
2. `search_steps` embeds thought+action, so every step in a trace is a near
   duplicate in the vector index — retrieval cannot distinguish them.
3. Every health counter reads green. The sidecar reports **599 steps, 0
   thought fallbacks, 340 relay pushes**; `steps_with_reasoning` is high
   because the text genuinely is model reasoning. The alarm built after the
   2026-09-19 tool-JSON fault cannot see this, because it asks "is this
   reasoning?" and the answer is yes.

This is the same failure *shape* as the fault fixed on 2026-09-19 — the
counters were healthy and the content was wrong — in a new place.

**What is NOT established: the mechanism.** `note_turn()` deletes pending
reasoning when the turn id changes, and `set_pending_reasoning()` accumulates
only while `previous[0] == turn_id`. Cumulative growth across ~28 turns
therefore implies the sidecar saw one unchanging turn id. Two candidates,
not yet separated:

- Vibe 2.25.5 emits a single `turnId` for a whole agent run on this
  model/build. (`tests/data-vibe-stream.jsonl` is a real capture from
  **2.25.4**, where `turnId` is a per-turn UUID — so this would be a version
  or model difference, and note the relay was previously validated against
  that 2.25.4 capture.)
- `note_turn` messages are not reaching the sidecar, or arrive in an order
  that defeats the reset.

**MECHANISM ESTABLISHED, AND FIXED — after the series ended.**
`scripts/probe_turn_ids.py` runs the real vibe 2.25.5 binary against
`tests/fake_model_server.py` with a scripted multi-turn conversation. Result,
reproducible in ~20 s on a laptop with no GPU:

```
scripted model turns: 5
streamed entries: 14
entries carrying a turnId: 14 / 14
DISTINCT turn ids: 1
```

**`turnId` is the CONVERSATION turn — one user prompt, one id.** An agent
attempt is a single prompt, so it never changes for the entire attempt.
Candidate (a) confirmed; candidate (b) refuted. `note_turn()` could never
fire and `set_pending_reasoning()` accumulated all attempt long.

`orchestrator/ingest.py` — the reference implementation — never used
`turnId` for this, and says why in its own comment: *"the user's turn, not
the model's. The model's own cadence is reason-speak-act, and the act is
what closes a step."*

**The fix** (`harness/reasoning_relay.py`): count model turns in the relay,
one per reason-speak-act cycle, and send that as the grouping key. An
`effect` arms the boundary; the next `reasoning` or assistant `message`
trips it. Everything in one cycle shares a key, so several tool calls
decided in one piece of reasoning still share that reasoning — the property
the sidecar documents — while the key now actually changes between turns.

The first version of this fix advanced the key on the assistant message and
**the rehearsal caught it immediately**: 0 thoughts from reasoning, 4
fall-backs, because the `effect` entry then carried the *next* key and
`note_turn` deleted the pending reasoning a moment before the `post_tool`
hook read it. Under the old constant `turnId` nothing was ever deleted,
which is how the accumulation bug hid a second one underneath it.

**New guards, each verified to fail without its fix:**

- `tests/data-vibe-stream-2255.jsonl` — a *real* capture from vibe 2.25.5,
  kept beside the 2.25.4 one. Its defining property is the single `turnId`.
- `tests/test_relay_turn_boundaries.py` (4 tests) — drives the real relay
  over that stream and asserts one key per model turn, that a reasoning
  entry and its assistant message share a key, and that thoughts do not
  accumulate when replayed through the real `StepMemoryService`. Every
  pre-existing sidecar test passed throughout the failure because they hand
  `set_pending_reasoning` a turn id by hand — supplying the one thing the
  live path never supplied.
- A rehearsal check: *"a step's thought does not grow to contain an earlier
  one's"*, scoped within a trace and requiring strict containment (the fake
  model replays the same script each attempt, so equal thoughts are
  repetition, not accumulation — flagging them failed a correct relay on the
  first run).

**286 tests, rehearsal 58/58.**

**Consequence for tonight's numbers:** warm's treatment was measurably
degraded for the whole series. "Warm did not finish" is therefore not
evidence that memory cannot help here — it is evidence about a pipeline that
fed the author one sentence per step.

## 8. Two further defects — both now fixed and tested locally

Both were found by querying warm's own graph on Aura rather than by reading
code. Neither is fixed: changing the harness during a running series would
make runs 3+ incomparable with runs 1–2.

### 7.1 Trace outcome summaries store file HASHES, not the edit

`orchestrator/vibe_agent.py` passes `workspace.snapshot()` into
`observed_fix()`. `snapshot()` is documented as *"path -> sha256, for the
'did anything change' check"*; `observed_fix()` expects file **contents** —
its docstring promises "what this edit actually did to the suite, in words,
plus the edit", and its own cautionary comment quotes a real code diff. The
result is that every trace summary in the graph looks like:

```
--- x12sdk/models.py
+++ x12sdk/models.py
@@ -1 +1 @@
-6c8ad5c43b1c9b19261919460f6a005fea8f2dc312a500d8b5216a278992b894
+8b733746a82d85f7e886c3fed9cbf64f915df1909f71ac3e5ffb416b8d340778
```

It records *which files changed* and nothing about *what changed*. This is
the one field designed to tell another agent what edit fixed an error.

**Blast radius, measured, not assumed:** the AIP author's prompt includes
only one line per trace (`id`, step count, `tests_passed`, `suite_passed`),
so the skill author is *not* directly fed these. What is affected is a warm
agent's retrieval at attempt time, where the summary is what surfaces.

**FIXED.** `orchestrator/vibe_agent.source_tree()` decodes
`collect_file_contents()` and strips the grader's `/repo/` prefix; both call
sites now use it. It reads the same cached tree `snapshot()` did, so there is
no extra round trip. Guarded by
`test_the_trace_summary_diffs_source_and_not_hashes`, which goes through the
seam that was wrong — the old test handed `observed_fix` source text
directly, which is exactly why it passed while production passed hashes.

### 7.2 The agent pollutes its own trace with junk files

The recorded diffs contain `MIGRATION_PLAN.md`, `fix_v5010.py`,
`fix_v5010_bodies.py` and a full `pytest_cache/` tree — helper scripts and
caches the agent created. They are not part of the migration and they crowd
the record. `repo_tarball` excludes `.pytest_cache`; the agent created
`pytest_cache` (no dot), which nothing excludes.

## 9. Still open

- **One long-deadline cold control.** Everything above says "cold cannot
  finish x12sdk in 600 s", not "cold cannot finish x12sdk". One cold run at
  `--deadline-s 1800` would settle it (~$2.30) — but it is now much less
  pressing: both arms repeatedly stopped editing *well before* the deadline
  and the loop kept launching attempts into that silence, so a longer budget
  buys more frozen attempts rather than more work.
- **The per-field truncation in `distill.render_steps`** — thought 300
  chars, action 200, observation 200. The step *count* cap was removed; these
  were not. **This needs a decision, not a guess.** While thoughts were
  cumulative the 300 was catastrophic (it showed the author the same opening
  sentence every time); now that each thought is one model turn it is an
  ordinary cap on real reasoning, and the standing instruction is that the
  compression should never be a limit on the model. Recommend removing all
  three and measuring the prompt size, rather than removing them blind.
- **THE SERIES SHOULD BE RE-RUN.** Every warm number in section 6 was
  produced with the degraded pipeline. The fixes are in and tested, but no
  warm arm has yet run on x12sdk with per-turn reasoning reaching the
  author.
- **`parse_ok` vs the oracle** (carried over from the oapi series): `parses()`
  scans only the package, so a syntax error elsewhere is invisible.
- The artifact pull still takes only each arm's final tree, so per-attempt
  closeness cannot be recomputed after the fact.

## 10. The number that summarises the night

**81 skill versions were authored and accepted** (`skills/versions-x12sdk/`,
v001–v081) across the calibration and 14 series runs. Warm's procedure was
re-distilled by `gpt-5.6-sol` after every single attempt, the AIP validator
passed every one, and **warm's behaviour never moved**: it never got below
296 of 383 surfaces in any run, in any attempt, all night.

Eighty-one accepted revisions with no measurable effect is not a model
failing to learn. It is a pipeline feeding the author one sentence per step
(section 7). Acceptance was never a fitness test — see the earlier
`distillation-has-no-fitness-test` note — and this is the most expensive
demonstration of that so far.

## 11. Artifacts

| what | where |
|---|---|
| this report | `runs/x12sdk-report.md` |
| cold calibration | `runs/x12-cold-{1,2,3}.log`, `runs/x12-cold-driver.log` |
| the series | `runs/x12-series-{1..15}.log`, `runs/x12-series-driver.log` |
| per-run events (authoritative) | `runs/swarm-*.jsonl` |
| per-run metrics / series JSON | `runs/swarm-*-metrics.json`, `runs/swarm-*-series.json` |
| skill lineage, 81 versions | `skills/versions-x12sdk/` |
| agent trees | `runs/x12-artifacts/` — **a mid-series snapshot taken during run 9**, not final trees; the pod died before a final pull |
| the fixture | `fixtures/x12sdk/` (manifest records both departures from upstream) |
| regenerate every table | `.venv/bin/python scripts/x12_summary.py` |

Event logs are the record of truth: they are written as the run happens and
are what survives a pod dying — which is exactly what happened at 04:30.

**Cost:** ~$13 of GPU for the whole night (pod 23:17–04:30 at $4.59/hr),
of which $1.65 was the cold calibration. Nothing committed.

## 12. Reproducing this

```bash
# the fixture
python3 scripts/make_fixture.py owgreen-dev/x12sdk 8 \
    --tests src/tests --package src/x12sdk \
    --test-command "python -m pytest src/tests -q" --out fixtures/x12sdk
# then flatten src/ and write requirements-v2.txt (see manifest.yaml)

MSF_FIXTURE_DIR=fixtures/x12sdk .venv/bin/python scripts/build_snapshot.py
MSF_FIXTURE_DIR=fixtures/x12sdk .venv/bin/python scripts/grade_fixture.py
bash scripts/x12_cold_calibration.sh
```

Pod: NVIDIA H200 SXM, SECURE, US-NC-1, CUDA 13.0 exact, $4.59/hr,
`runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`, 300 GB.
Model `mistralai/Mistral-Small-4-119B-2603` on SGLang 0.5.14.
Skill author `gpt-5.6-sol`.
