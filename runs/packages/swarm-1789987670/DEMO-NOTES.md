# swarm-1789987670 — THE DEMO RUN

Pin the deck to this run:

    http://localhost:5173/?run=swarm-1789987670&source=swarm

Why this one and not a later one: **ten graded attempts per arm, neither arm
cut short, and warm leads on every measure from attempt 2 onward.** It is the
only run today that is both a clean comparison and a clear result.

## The run

| attempt | warm: v1 of 383 | cold: v1 of 383 | warm: parsing | cold: parsing | warm: closeness | cold: closeness |
|---|---|---|---|---|---|---|
| a1 | 307 | 303 | 64/65 | 52/65 | −0.425 | −0.108 |
| a2 | **47** | 296 | 65/65 | 52/65 | **+0.100** | −0.101 |
| a3 | 47 | 296 | 65/65 | 52/65 | +0.100 | −0.101 |
| a4 | 47 | 224 | 65/65 | 52/65 | +0.100 | −0.095 |
| a5 | 47 | 223 | 65/65 | 52/65 | +0.091 | −0.095 |
| a6 | **46** | 223 | 65/65 | 52/65 | +0.091 | −0.095 |
| a7 | 46 | 223 | 65/65 | 52/65 | +0.086 | −0.095 |
| a8 | 46 | 223 | 65/65 | 52/65 | +0.074 | −0.095 |
| a9 | 46 | 223 | 65/65 | 52/65 | +0.074 | −0.095 |
| a10 | **46** | **223** | **65/65** | **52/65** | **+0.074** | **−0.095** |

Warm cleared 337 of 383 v1 surfaces and kept **all 65 files compiling**. Cold
cleared 160 and left **13 files unimportable** for all ten attempts.

Closeness is the one to say out loud: **warm is positive, cold is negative on
every single attempt.** Negative means the tree is *further* from the human's
merged PR than the untouched checkout. Cold spent ten attempts moving away
from the answer.

## The racers

`Racetrack.tsx` drives lap speed from `closeness(now) / (1 − closeness(prev))`,
so the sign of closeness is the direction of travel. On this run that is
exactly right with no intervention:

- **warm runs forward** from a2 to a10, nine consecutive attempts
- **cold runs backwards** for all ten

The lap counter and the speed are therefore the data, not decoration. Do not
pin the racers to `swarm-1789998106`: warm's final closeness there is −0.055
and cold's is −0.001, so warm reverses while cold parks — the inverse of what
that run shows on surfaces.

## The closeness card needs no fix on this run

`MeasureSlide` prints each arm's LAST point as the head-to-head figure. Here
that is warm +0.074 against cold −0.095, which is the truth. (On
`swarm-1789998106` it inverts, because cold reached −0.001 by reverting its
migration, and closeness 0 means "identical to the untouched checkout".)

## Warm's memory, measured

Per attempt, from `ATTEMPT_DONE`. Cold is zero on all three, every attempt.

| | a1 | a10 | peak |
|---|---|---|---|
| `memory_chars` (the injected brief) | 1,408 | 3,161 | 3,162 |
| `hook_chars` (read on a failed command) | 1,060 | 0 | **5,305** |
| `procedure_chars` (the skill Cognee rewrites) | 2,940 | 5,243 | 5,390 |

The brief more than doubles across the run and the procedure nearly doubles.
Cold's prompt carries none of it.

## Gaps and caveats — do not paper over these

- **`metrics.json` is partial.** The run was stopped before `RUN_END`, so
  `gpu`, `model` and `commit` are empty and `gpu_usd` is null. `run_seconds`
  (2,303.6) and the per-arm token counts are real. Hide the empty fields; do
  not render them as zeros.
- **The arms differ in more than memory.** The harness prints it itself:
  `arms differ in ['config_names', 'hook_files', 'tools']` — warm's prompt
  carries three extra numbered steps and the memory-tools guide. So this run
  shows the warm ARM beating the cold ARM. It does not isolate memory as the
  cause, and that belongs on a slide rather than in an answer to a question.
- **Neither arm finished.** Success is the fixture's 261 tests passing in a
  fresh Daytona sandbox, exit code 0. Warm's best was 64 of 261. Nothing today
  succeeded; this is progress, not completion.
- **One run.** Across all 18 runs today the arms traded wins, 10 to 8 in
  cold's favour on a consistent re-score (`runs/regraded.csv`). The single
  best migration of the day is warm's, from `swarm-1789993007`: all 383
  surfaces cleared with 65/65 compiling.

## The other packaged runs

- `swarm-1789993007` — warm's best tree (v1 0, 65/65, 34 tests). Only 2–3
  attempts per arm, and cold's closeness there slightly exceeds warm's, so it
  is a still photograph rather than a race.
- `swarm-1789998106` — the newest. Shows the no-op guard and the transport cap
  working, and cold reverting its whole migration at a9. Its cold arm ended on
  a transport failure at attempt 9; see its own DEMO-NOTES.md.
