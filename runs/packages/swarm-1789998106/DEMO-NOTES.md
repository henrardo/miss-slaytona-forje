# swarm-1789998106 — what this run shows, and what it does not

The x12sdk Pydantic v1→v2 experiment. One checkout per arm, both arms on the
same model, the same clock and the same grader. 20 graded attempts: **cold 9,
warm 11.**

Read it as **two windows**. They answer different questions and must not be
charted as one.

---

## Window 1 — the comparison: attempts 1–9

Both arms had equal attempts here. Every head-to-head claim comes from this
window and nothing else.

| attempt | warm: v1 left of 383 | cold: v1 left of 383 | warm: parsing | cold: parsing | warm: closeness | cold: closeness |
|---|---|---|---|---|---|---|
| a1 | 309 | 300 | 60/65 | 43/65 | −0.018 | −1.571 |
| a2 | 305 | 177 | 63/65 | 45/65 | +0.046 | −1.485 |
| a3 | 297 | 265 | 63/65 | 45/65 | +0.055 | −1.508 |
| a4 | 282 | 0 | 63/65 | 47/65 | +0.053 | −1.475 |
| a5 | 341 | 0 | 63/65 | 47/65 | +0.006 | −1.454 |
| a6 | 320 | 0 | 62/65 | 47/65 | −0.488 | −1.461 |
| a7 | 295 | 41 | 63/65 | 47/65 | −0.061 | −1.470 |
| a8 | 255 | 16 | 63/65 | 47/65 | −0.061 | −1.471 |
| a9 | **255** | **365** | 63/65 | 65/65 | −0.056 | −0.001 |

Three facts decide the window:

1. **Cold's zero-surface trees were never migrations.** At a4–a6 it reported 0
   of 383 v1 surfaces with **18 files that could not be imported**. Cleared
   spellings, unusable package.
2. **Forced to compile, cold gave the migration back.** At a9 it reached 65/65
   parsing by reverting to **365 of 383** — eighteen surfaces from the
   untouched checkout. Nine attempts, nothing standing.
3. **Cold's closeness sat near −1.5 for eight consecutive attempts**, meaning
   every cold tree was *further* from the human's merged PR than the
   pre-migration source. Warm's was positive for four of its first five.

## Window 2 — the continuation: attempts 10–11 (warm only)

Cold's arm ended at a9. Anything after that is **uncontested** and is not
evidence about cold.

| attempt | warm: v1 left | tests | parsing | closeness | procedure |
|---|---|---|---|---|---|
| a9 | 255 | 59 | 63/65 | −0.0556 | 5,349 chars |
| a10 | 254 | 59 | 63/65 | −0.0551 | 5,600 chars |
| a11 | **253** | 59 | 63/65 | −0.0546 | **6,162 chars** |

What it demonstrates on its own terms: **warm kept improving under its own
memory, unprompted by any competitor** — surfaces down on every attempt, the
tree never regressing below 63/65, and the procedure Cognee maintains still
growing (4,934 → 6,162 chars across the run).

---

## Why cold's arm ended, and why it is fair

`FILE_DONE cold success=False attempts=9`, reason
`20 consecutive aborts; vibe never started`.

Cold's Vibe process could not start: exit code 255 in ~3 seconds, **zero
assistant turns**, `mux_client_request_session: send fds failed` — the ssh
transport between the harness and the pod failing to open a session. No prompt
was sent, no token was generated, no model call was made. This is the harness
failing, not the agent.

It is a fair stop for four reasons, all in the event log:

- **Equal shots.** Cold ended with 9 graded attempts against warm's 9 at that
  moment. The comparison window is attempt-for-attempt equal.
- **Not arm-specific.** Warm took the same transport abort at t=3182, in the
  middle of cold's run of them. Warm recovered, cold did not — luck, not
  treatment.
- **The harness tried to heal it and recorded the failure.** At 5 consecutive
  aborts it recycled the ssh control master; that did not help, which is also
  logged. At 20 it stopped rather than spin. Earlier runs today spun 126 times
  on this fault and the log read like a cold agent that would not work.
- **Auditable.** The reason string is in the jsonl, not in anyone's notes.

## Caveat that belongs on a slide

The arms differ in more than memory, and the harness says so itself:
`arms differ in ['config_names', 'hook_files', 'tools']`. Warm's prompt carries
three extra numbered steps and the memory-tools guide. So this run shows the
**warm arm** outperforming the **cold arm**; it does not isolate memory as the
cause. Across all 18 runs today the arms traded wins, 10 to 8 in cold's favour
— while the single best migration of the day is warm's, from a different run
(`swarm-1789993007`): 383 v1 surfaces cleared with all 65 files compiling.

## Warm's memory, measured

Per attempt, from `ATTEMPT_DONE`. Cold is 0 on all three, every attempt.

| | first attempt | last attempt | peak |
|---|---|---|---|
| `memory_chars` (prompt block) | 2,302 | 4,829 | 4,829 |
| `hook_chars` (deterministic read on a failed command) | 0 | 3,600 | **19,200** |
| `procedure_chars` (the skill Cognee rewrites) | 4,934 | 6,162 | 6,162 |

An example of what warm actually read back, from the graph:

```
Attempt 1 on the x12sdk Pydantic v1 -> v2 migration.
Started from: PydanticImportError: BaseSettings has been moved to pydantic-settings
v1 surfaces 383 -> 296.
Still left: 253 x Field(const/regex/items) -- v4010/.../loops.py (50),
            v5010/.../loops.py (45), and 15 more file(s);
            42 x conint/constr/etc -- v4010/segments.py (24), v5010/segments.py (18)
65 of 65 source files parse.
```

Every line of that is measured off the tree by the grader, not reported by the
agent.
