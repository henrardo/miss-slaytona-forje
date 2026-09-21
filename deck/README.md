# deck

The talk HUD. A live data collector for `runs/`, presented as a slide holder.

```bash
cd deck
npm install
npm run dev          # http://127.0.0.1:5273
```

Open it before launching a run. It follows whichever run in `runs/` is newest
and re-latches when a fresher one appears, so it can be on the projector while
the pod is still warming up.

The rail switches between two views of the same cards. **REPLAY** is the
default: the newest `rehearsal-*`, written by `scripts/rehearse_loop.py`
driving the same loop locally. **LIVE** is the newest `swarm-*`, the pod.
Replay is the default because it is the view that always has something in it —
a replay is on disk before the talk starts, whereas LIVE is empty until a pod
run exists. `?source=live` opens on LIVE instead.

`rehearsal` remains the key in the code and the prefix on disk, because that is
what the writer emits; `REPLAY` is the label on the glass.

`?run=<id>` pins one run instead, and locks the switch. **This is mandatory for
a demo**, not cosmetic: without it the deck follows the newest `swarm-*.jsonl`
and re-latches when a fresher run starts, which would swap the run out
mid-presentation.

```
http://127.0.0.1:5273/?run=swarm-1789998106&source=swarm
```

Cards that follow the pinned run read `useRunFeed()`. Two read the run's
package as well — `runs/packages/<id>/` — for records the event log does not
pre-join: `attempts.json` (one row per graded attempt) and `MANIFEST.json`'s
`windows`, which is how Daytona verification knows that attempts 1–9 are the
equal-attempt comparison and 10–11 are warm continuing alone.

## The shape

**One flat list. No nesting, no groups.** A tile *is* a slide: the same
component, authored once at 1920×1080, CSS-scaled to fit its slot. Not a
thumbnail, not a summary view — the same component.

Every slide is mounted once for the life of the session in a single
absolutely-positioned layer. Staging one changes nothing but its transform
target; it is never unmounted or re-parented. A tile that has been collecting
for twenty minutes arrives on stage with twenty minutes of state intact.

**Sixteen cards, twenty slots, one board.** Clicking a card at home sends it
to the board in the middle, where everything already there re-packs around it.
Clicking a card on the board sends it home. Up to four share the board.

**The four corners are not cards.** The ring is the perimeter of a 6×6 grid,
so it seats twenty or it stops being a rectangle; the deck has sixteen things
worth saying. The corners hold blocks of colour — see *The corners* below.

**Homes are permanent** — a card owns its ring slot for the whole talk. A card
away from home leaves a **ghost** in its slot: a dashed socket with its name
on it, itself clickable to recall the card. So the ring still reads as
complete and nothing drifts.

A digit key addresses the *n*th **card** in talk order, skipping the corners,
so `1` is always the home card. It no longer doubles as a ring position: the
ring now has slots that are not cards, and a digit that landed on one would
put an empty rectangle on the board.

`DECK_SIZE` in `lib/layout.ts` is the authority for the ring; the registry
warns in dev if a card ends up with no slot.

## The board

The board is a **14 × 8 grid of squares** (`STAGE_COLS`, rows derived so cells
stay square). A card joining it occupies a whole number of squares.

### Bias

Every card ranks the three shape classes it could be handed, most wanted
first — `BIAS_WIDE`, `BIAS_TALL`, `BIAS_SQUARE` in `lib/stage.ts`. A
terminal-ish card whose rows must not wrap ranks `hor` first and gets a wide
slot whenever one is going.

This is why arrangements come in *alternatives* rather than one preset per
count: for two cards there is a side-by-side (two squarish halves) **and** a
stacked (two wide bands), and which is right depends entirely on what those two
cards want to be. Bias is the input that decides.

Packing is exhaustive and deterministic — at most 4 cards, so at most 24
assignments per arrangement across a handful of arrangements. No heuristics:
the same cards always produce the same board. Ties break toward the first-listed
arrangement and join order, so the designed default wins when bias is
indifferent.

Scoring is **convex — 6 / 2 / 1, not 3 / 2 / 1**. Linear scoring makes two
second-choices (4) beat one first-choice (3), so the packer spreads mild
disappointment evenly and nothing ever gets what it asked for. That was
measured, not theorised: a four-card board tied at 10 between "give the square
card its square" and "give everyone their second choice", and the tie-break
handed out seconds.

### Caps and rules

- **Four cards maximum.** Legibility (14 × 8 would *fit* nine; nobody at the
  back reads nine) and compositing (re-packing N cards is N simultaneous
  transform transitions — see below).
- **A fifth evicts the oldest, FIFO** — first in is sent home automatically.
  Refusing a click in front of an audience looks like a broken deck.
- Every arrangement must tile 14 × 8 exactly. A dev assertion in `stage.ts`
  checks coverage and overlap, because a gap reads as a rendering bug at the
  worst possible moment.
- **From three cards up, every arrangement mixes at least two shape classes.**
  A board of three or four identical shapes reads as a spreadsheet rather than
  a composition, *and* it makes bias meaningless — if every slot is the same
  class there is nothing for a preference to win. The same assertion enforces
  it, so an all-wide or all-tall arrangement cannot creep back in. Two cards
  are exempt: a matched pair is a comparison, which is exactly what warm
  against cold wants.

### Motion

**The box is final before the move starts.** Width and height are set
instantly; only the transform is transitioned.

They used to transition too, and that was a visible glitch: a card joining the
board swung from 1.78 to 0.50 aspect across 45 frames, reflowing its whole
subtree on every one. Traced by sampling geometry through a join — the *motion*
was perfectly smooth, the *content* was not. The cost of the fix is a
single-frame reshape at the origin, where the card is at its smallest.

### Scale is normalised by area, not width

`unitFor()` uses `sqrt(area / canonical area)`. Width-normalisation is fine
while every box is 16:9 and wrong the moment they are not: a 5×8 slot is 426px
wide and 848 tall, and normalising by width gave it a 1920×3819 canvas with
52-unit type rendering at 11px — unreadable, in a slot with plenty of room. By
area the same slot gets 1021×2031 and ~22px type. Tiles and the full board are
unchanged to within a pixel; this only rescues the shapes that were broken.

### The container

`StageContainer` sits in the hole in the ring, behind everything, and never
moves. It is not a card: no registry entry, cannot be staged or sent home,
holds no run data. It draws the square lattice so the grid is visible rather
than notional, and keeps one gutter of padding so cards sit *inside* it.

## Geometry

The ring is the **perimeter of a 6×6 grid** — which seats exactly 20 tiles
(`2·6 + 2·6 − 4`). One uniform gutter everywhere, tiles on the edge cells, the
stage filling the hole. Rows and columns therefore align at the corners by
construction, and all four stage-to-band distances are equal by construction
rather than by tuning.

Measured from the live DOM at 3840×2160, 2560×1440, 1920×1200 and 3440×1440
(ultrawide): four gaps equal to within 0.2px, corners aligned, at every size
and after a swap.

**The stage is deliberately not 16:9.** Cells are 16:9, but the hole is
`(4·tw + 3g) × (4·th + 3g)` — the gutters add equally in both axes while the
cells add in 16:9 proportion, so the hole comes out ~1.73. Solving
`stage.w == A · stage.h` across every ring shape that seats 20 tiles gives a
negative tile size in each case, and demands `g == 0` at cols == rows. *Stage
exactly 16:9*, *one uniform gutter*, and *aligned grid* are not simultaneously
satisfiable — pick two.

Letterboxing a 16:9 slide inside the hole would cost `1.5g(1 − 1/A)` of slack
top and bottom: vertical gaps 1.66× the horizontal ones, a ratio independent of
`g`, so a tighter gutter does not dilute it.

So the slide canvas is **fixed in width, adaptive in height**. Every slide is
authored 1920 wide and fills whatever box it is handed; `SlideChrome` is
flexbox, so header and footer stay put and the body absorbs the difference —
under 3% between tile and stage. Type is in canonical width units, so a heading
is the same size on every slide.

| key | |
|---|---|
| click a card at home | send it to the board |
| click a card on the board | send it home |
| click a ghost | recall that card |
| `←` `→` `space` | linear walk through the cards, in talk order — the board becomes exactly that one card |
| `1`–`9`, `0` | toggle the *n*th card on/off the board. `1` is the home card |
| `Home` / `Esc` | board becomes the home card alone |
| `F` | fullscreen |
| **Reset** (bottom rail) | send everything home |

Arrows are the linear motion for talking through the deck; clicks and digits
are for the interactive moments where two or three cards want to be side by
side.

**Reset touches the cards and nothing else** — the feed, the followed run and
the connection are untouched, because a presenter reaching for it has lost
track of the deck, not of the run. It is disabled while the cards are already
where they started, so it never reads as a live control when it would do
nothing.

It snaps rather than animates, deliberately: a reset can move every card at
once, and sixteen simultaneous transform transitions is the same
layer storm described under Compositing below.

## The collector

`plugins/runsData.ts` is a Vite plugin serving the harness's real `runs/`
directory in place. It never copies or caches it.

```
GET /api/runs             index of every run on disk
GET /api/runs/:id         { events, metrics } for one run
GET /api/stream[?run=id]  SSE — snapshot, then deltas as lines land
```

A `.jsonl` grows line by line while a run is in flight, so the stream keeps a
byte offset per file and emits only what is new, holding back a torn final
line until it completes. Verified end to end: a client connected against an
empty directory receives `RUN_START`, `ATTEMPT_START`, `ATTEMPT_DONE` in
order, no duplicates, no drops, for a run created after it connected.

**It polls, once a second, and the watcher is only the fast path.** `fs.watch`
on a directory is FSEvents here, and appending to a file already in that
directory did not wake it: measured against a writer appending every four
seconds, the deck sat on *1 event* for 24 seconds and then received all six at
once when the writer closed the file — which on stage is indistinguishable from
a run that has stalled. A full pass stats every file in `runs/` (648 of them,
2.4ms), so a poll costs nothing; it runs only while a client is connected, and
the run index is re-sent only when it actually changes.

**Empty runs are skipped when picking "newest".** A run that dies before its
first event leaves a zero-byte `.jsonl`, and two of those sat at the top of
`runs/` for six hours — so the deck followed one, reported `0 events`, and
showed an empty board while a perfectly good run of the same kind sat one row
down. This is also why the racers did not move on LIVE.

Override the directory with `MSF_RUNS_DIR`.

Both `npm run dev` and `npm run preview` mount it. Preview too, deliberately —
finding out on stage that the built bundle serves a deck with no data is not a
discovery worth having.

## The sixteen cards

`CARDS` in `slides/registry.tsx` is in **talk order**, and the cards are
seated into the non-corner slots in that order — so `ArrowRight` walks the
deck as it is meant to be told, and slot number and talk position are the
same thing for every card. Each one names the file it reads, and none of them
recomputes a number the harness already produced.

| slot | # | card | source |
|---|---|---|---|
| 0 | — | *corner* | a block of colour |
| 1 | 1 | Miss Slaytona Fourje | the wordmark, the sprite, Slay |
| 2 | 2 | Cold | the whole stack as a flow chart, with the real prompt |
| 3 | 3 | Warm | the same stack with the memory layer, and warm's prompt |
| 4 | 4 | RadixAttention | `attempt_prompt_tokens` vs `attempt_completion_tokens`, live |
| 5 | — | *corner* | a block of colour |
| 6 | — | *corner* | a block of colour |
| 7 | 5 | Reasoning stream | the agent's own `messages.jsonl`, out of the packaged artifacts, playing |
| 8 | 6 | Token cost | $4.69/hour ÷ both agents' tokens per second |
| 9 | 7 | Tokens, head to head | one run's `-metrics.json`, the two arms kept apart |
| 10 | 8 | The repo under test | its own demo file, its own model class, its own README |
| 11 | — | *corner* | a block of colour |
| 12 | 9 | Mistral Small 4 | the launch script's absences · `tools` counters, live |
| 13 | 10 | Mistral Vibe | the provider block, and the one line that moves |
| 14 | 11 | Daytona | the boundary · oracle pair read from `runs/x12sdk-report.md` |
| 15 | 12 | The code graph | a live Aura query, d3-force on canvas |
| 16 | 13 | Surfaces left | `work_remaining`, warm against cold, swept in one go |
| 17 | 14 | Still compiles | `files_parsing`, warm against cold |
| 18 | 15 | Distance to the answer | `closeness`, warm against cold |
| 19 | 16 | Daytona verification | every graded attempt of the followed run, tick or cross |

Slot 0 is a corner, which is why **Miss Slaytona sits in slot 1** rather than
at the top-left of the ring, and why everything that follows her moved one
place along.

### What was removed, and why

The deck was too long. Seven cards went, each because it was already said
somewhere better, or not clearly enough to be worth a slot:

| card | why |
|---|---|
| **Event tail** | the raw JSONL. Attempt anatomy is the same events, read. |
| **Cross-run summary** | a table of past runs, in a talk about the run happening now. |
| **The stack** | superseded outright by Cold and Warm, which draw the same wiring *with the arms' asymmetry visible*. |
| **Does this run count?** | the confound audit. It belongs in the notes, not on a wall — the status rail still says `CONFOUNDED` when it matters. |
| **Improvement curve** | a chart nobody could read at a glance. Its slot went to RadixAttention, which animates its argument instead of plotting it. `charts/Panel.tsx` is now unused; it is the only chart primitive, so it stays. |
| **The ontology of memory** | the graph's own schema, which is a picture of the tooling rather than of the result. Its slot went to Mistral Small 4. |
| **Skill growth** | a sawtooth of byte counts. Its slot went to the Daytona boundary card. |
| **Warm vs cold** | a 12-row table off `-metrics.json`; on swarm-1789998106 seven of its rows are 0, — or null. Its slot went to The result, which makes the same comparison with the three panels the harness computes for it. |
| **The result** | all three measures on one card: three y-axes, three caveats and six lines in a third of a card each, and nothing readable from the back. Split into Surfaces left, Still compiles and Distance to the answer. |
| **What warm was given** | the three memory channels per attempt. Its slot went to Still compiles. |
| **SGLang** | source excerpts and a sparkle. Its slot went to Distance to the answer; RadixAttention still carries the SGLang argument. |
| **What it cost** | attempt vs distillation spend plus a GPU bill. On a run stopped before `RUN_END` the distillation columns are 0 (uncounted, not zero), `gpu_usd_per_hour` is 0.0 and `gpu_usd` is null — it would have drawn $0.00. Spend is on Token cost and Tokens head to head. Its slot went to What warm was given. |
| **What is in the way** | error signatures grouped by frequency. It said what the agents were tripping over and never what they were working *on* — an audience three cards in still did not know what the codebase was. Its slot went to The repo under test. |
| **Attempt anatomy** | a live list of `RESTORED` / `REJECTED` / `ABORTED`, which is the event log read aloud; the three cards after it already carry what those events mean. Its slot went to Token cost. |
| **The distilled skill** | the procedure Cognee holds, verbatim. What it contains is shown on Warm and argued on Daytona; what nothing in the deck did was put the two agents' token counts side by side. Its slot went to Tokens, head to head. |

**RunPod terminal** also lost its slot, to Warm, so the treatment sits beside
its control. `slides/TerminalSlide.tsx` is still in the tree and still works;
it just has no registry entry. The seven above are deleted, and in git.

### RadixAttention animates its argument

**The first version of this card was wrong, and the correction is the
interesting part.** It said "twelve agents on one GPU". This project does not
run twelve agents: `--swarm-size` defaults to 1 and counts agents *per arm*,
so `--arms both` is **two** — `warm-0` and `cold-0` — which is what every run
in `runs/` contains. `swarm/run.py` argues against going wider, not for it:
two agents on one pod already contend, and `--arms warm` / `--arms cold`
exists so they can be run one at a time. The "twelve" came from a comment in
that same file about *run 12*, a run number in an anecdote about two agents
colliding.

**What prefix caching is actually doing here is better.** The swarm is tiny;
the re-reading is enormous. An agent's turn N+1 sends turn N's whole
conversation back plus one more tool result, so a 64-turn attempt submits its
prompt sixty-four times over. Measured on the run in flight — 2 agents, 20
attempts, 1,290 turns:

| | |
|---|---|
| prompt tokens submitted | **49.5 M** |
| tokens generated | **164 K** |
| ratio | **302 : 1** |
| per turn | ~38,000 prompt tokens |

The last six runs land between 286:1 and 356:1. Prefix caching is what stops
a GPU prefilling fifty million tokens to produce a hundred and sixty
thousand.

**So the picture is a staircase**, not a stack of identical siblings: each
turn's prompt is the previous turn's plus a tip. Unfolded, every row is lit
and the lit area is a triangle — everything, every turn. Folded, only the
tips stay lit and the rest is ringed as *already in the cache*. That is a
radix tree seen side-on, and it is what the machine is really doing. Beside
it, two bars to one scale: submitted against generated, the second a sliver.
Two numbers side by side read as two numbers; that reads as the
disproportion it is.

**Every figure is live.** `attempt_prompt_tokens` and
`attempt_completion_tokens` are on every `ATTEMPT_DONE`, from a counting
proxy per arm on the pod (`proxy_usage` in `swarm/run.py`) that sums the
`usage` block of every chat completion. The harness samples it at attempt
boundaries and charges the probe to off-clock time, so measuring cannot
contaminate the arms' timing. Nothing on the card is stamped.

Two things it deliberately does not do. It draws **no counterfactual** —
"what a server without prefix caching would prefill" needs no arithmetic,
because every submitted token is a prefilled token by definition, so the
card says *submitted* and *recomputed* and stops there. And the bar lengths
are labelled **not to scale**: the only ratios claimed are the ones written
in words.

The fold runs **only on the board** — at home a tile is a texture, and twenty
animating at once is the layer storm the Hud exists to avoid. Reduced motion
gets the folded state as a still frame, which is the more legible of the two
anyway.

One trap worth keeping: `metrics.gpu` is not always a device. A run that
could not read the pod writes the literal string `(not recorded)`, and `??`
does not catch that — the field is present, it just says nothing. The card
printed "one SGLang server on one (not recorded)" until `gpuName()` started
checking that the value begins with a letter.

### Mistral Small 4 argues by absence

One point, made in three panels: **the exact model in this talk is one anyone
can pull and run.** Not a hosted endpoint, not a preview, not a partner
build — the string in our launch line is the string you would type.

The middle panel carries it, and everything in it is a thing that *isn't*
there in `scripts/launch_sglang.sh`:

| | |
|---|---|
| **no token** | no `HF_TOKEN`, no login, no credential anywhere in the launch path. The script names the model and runs. |
| **no `--quantization`** | the checkpoint arrives FP8 and is served FP8. No calibration pass, no conversion step. |
| **`--tp 1`** | one GPU. The script's own note: "one H200/B200 holds the FP8 weights at ~113 GB". |

Showing how little there is beats asserting that it is easy. The three reveal
one at a time and then hold with all three lit — on the board only, like
every other animation here.

Two claims are deliberately *not* drawn as evidence. That this checkpoint
replaced three — Codestral for code, Magistral for reasoning, a Small/Large
for instruction — is Mistral's product history and not a fact in this repo,
so it is a dim caption under the hero rather than a diagram. And "open
weights" is stated without naming a licence: the repo proves you can pull the
weights with no credential, it does not say what the licence permits.

The third panel is live — tool calls, distinct tools, files written, turns and
graded attempts, all counted off `ATTEMPT_DONE`. A run writes none of those
for its first few minutes, and five noughts in a row is not a measurement, so
before the first graded attempt the panel says so in words instead.

One more trap of the same family as the GPU one: **`metrics.model` is not
always a model.** A run that could not read it back writes the *empty string*,
which `??` does not catch either, and the identifier rendered as a blank box
until `modelPath()` started requiring an org/name pair.

### Two Daytona cards, and they do not overlap

**Daytona verification** shows every grading as it happens — a row per
attempt with the sandbox's create time, the count, and pytest's own error
tail. It states no limits, no sizing and no architecture, on purpose.

**Daytona** (card 11) carries exactly those. It is a boundary diagram,
because the argument is a topology: the agents live on the pod with SSH,
SGLang and Aura; `DAYTONA_API_KEY` is not there at all, since grading is
driven from the orchestrator's own process; and the sandbox has no route to
the served model or the graph. Two things cross the wall — **a file tree
goes in, a number comes back** — so "an agent cannot touch its own grade" is
a property of the shape rather than of careful bookkeeping, and "no state
crosses between the arms" holds because every grading call gets a brand-new
sandbox deleted in a `finally`.

The wall is also *why Daytona is the grader*: its egress is SNI-filtered and
the allow-list cannot be overridden per sandbox, which disqualified it as an
agent runtime. Being unable to reach the model is the property you want in
something that judges.

The animation is the disposability — a box appears, is graded, is struck
through and gone, and the next attempt gets a new one.

The oracle pair is **read live** out of `runs/x12sdk-report.md` through the
same `/api/source` endpoint the source-excerpt cards use, so `0 → 261` and
`383 → 2` are facts about the grading rather than constants in a component.
(The report had to be added to `SOURCE_WHITELIST` in `plugins/runsData.ts`;
that list is exact membership, and anything not on it 403s.) The org cap,
the sizing and the free credit are stamped, and the footer says which is
which.

### The corners

Four blocks of periwinkle, in `slides/CornerBlock.tsx`. Not cards: no click
target, no ghost, no keyboard stop, `aria-hidden`, and `toggle()` refuses
them even if something calls it. A decorative tile that can be staged is a
card with no content, which is the thing they exist to avoid.

Corners, and not some other four slots, because a corner is the weakest slot
in the ring: the furthest tile from the eye's path along either edge it
belongs to, and the only slot that has to read in two directions at once. If
a slot must hold nothing, it should be one of those.

They are **periwinkle and not marigold or light baltic** — those two mean the
cold arm and the warm arm wherever a number is drawn, and four large gold
blocks would be the deck's loudest use of a colour that is supposed to mean
one thing. They are also deliberately *under* the cards in luminance: at full
strength they were the brightest thing on the screen, which is the frame
out-shouting the deck. The ramp is two palette stops with a flat scrim over
it, layered rather than eyedropped so both stops stay traceable.

`CORNER_SLOTS` is derived from the ring's own fill order, not typed out —
change the ring shape and the corners move with it.

### Cold and Warm are one drawing

Cold and warm are the same stack with a memory layer bolted onto one of them,
so they are drawn by one engine — `slides/StackFlow.tsx` holds the lattice,
the orthogonal elbow router, the drawn glyphs and the prompt document, and
each card supplies only its own nodes, edges and prompt. Two hand-maintained
copies would not stay comparable for a week, and comparability is the entire
point of showing them next to each other.

What differs, and all of it is real:

- **Warm's middle row is full.** Cognee sits between the agent loop and Neo4j
  Aura. `cognee[neo4j]==1.6.0`, configured in `orchestrator/cognee_layer.py`
  with `GRAPH_DATABASE_PROVIDER=neo4j` — so *Cognee → Neo4j* is where the
  graph physically goes, not an association. Without those variables Cognee
  falls back to an embedded Kuzu store and nothing reaches Aura.
- **The Vibe ↔ Cognee link is two-way**, because warm's treatment is two
  halves: the agent may call the MCP tools itself, *and* the harness writes
  each step and injects the retrieved procedure and memory into the next
  prompt. The voluntary half alone made warm byte-identical to cold.
- **The memory edges are lettered M1/M2, not numbered 8 and 9.** They do not
  happen after step 7; they happen throughout. The numbered spine is
  identical on both cards so the eye can compare it.
- **Warm's prompt is three steps longer** and the extra steps are marked gold
  in the document. That is a confound, not a detail: warm reads more tokens
  before it starts and has more steps to work through.
- **Warm's lattice is shifted 56 units right**, to open a channel for the
  checkout edge that cold runs straight down its empty middle row. A
  connector through a box is the one thing these diagrams must not do.

The frame is the only thing that carries the arm — blue for cold, gold for
warm. The wiring stays periwinkle on both, so they read as one system twice
rather than two systems, and so the lit state (marigold, deck-wide) is never
confusable with an unlit stroke.

### The sparkle is two resolutions, and says which

**Cold**, **Warm** and **SGLang** light a region when the thing it
names happens. (The stack card did too, and is gone.) There are two
sources and they are not equivalent: the GRAPH timestamps every tool call, so
regions light seconds apart — but warm only, because cold writes nothing. EVENTS
are true for both arms and survive Aura being down, but are attempt-granular.
The finer one is preferred while it is producing, and the badge reads
`per call (graph)` / `per attempt (events)` / `idle`. A sparkle implying
per-call activity when the truth is one pulse per attempt would be decoration
pretending to be instrumentation.

### Two things the data turned out to be

**`runs/cross-run.md` has two schemas under one header.** 63 rows carry 15
columns and 71 carry 18; the harness gained three columns partway through and
never rewrote the header line. Rendered naively the wider rows shift left and
the GPU price appears under "skill v", which is how it was found. The card
that showed it is gone, but the defect is not: the fix belongs in
`metrics.py`, and anything that reads that file has to handle both widths.

**The skill sawtooths.** The procedure is rewritten from scratch each time, so
it routinely halves and regrows; marking every drop put forty overlapping
labels on Skill growth. The three deepest are labelled and the count is in
the footer.

## Adding a slide

Slides are pure views over `useRunFeed()`. They hold no data state of their
own, which is what makes "tiles keep collecting off-stage" true by
construction rather than by keeping twenty components alive correctly.

Replace a `makeSlotSlide(n)` entry in `src/slides/registry.tsx` with a real
component. Nothing else needs to change. Wrap it in `<SlideChrome>` so it
carries the same frame, and lay it out against 1920×1080 — the scale is
applied for you.

`SlideProps` carries `focused` and `scale`. Use `scale` to drop detail that
would be illegible at tile size if you need to; do not use it to stop
collecting, because a tile that pauses is a tile that lies when it reaches the
stage.

## Reading the numbers honestly

Two rules carried over from the harness, both of which have cost real runs:

- **`null` is UNCOUNTED, and that is not zero.** `steps_with_reasoning` and
  `thought_fallbacks` render as `—` when null. Six pod runs were misread
  because a metric collapsed the two.
- **A confounded run is not a result.** The status rail shows `ARMS OK` only
  when `known_differences` fall inside `TREATMENT_DIFFERENCES`; otherwise it
  says `CONFOUNDED` and names them, in hibiscus, loudly.

## Look

The *structure* comes from Stranger Graphs — near-black ground, one saturated
accent, neon-outlined display type, glow — but rotated off blue-grey onto
violet so it reads whimsical rather than terminal. Ground is Neo4j's own
`--tint-lavender-deep #1a1730`; the primary accent is **periwinkle `#6a82ff`**;
greys are warm and violet-leaning, because neutral grey is what made the first
pass look like a hacker in a hoodie. Display face is **Syne Neo**, Neo4j's own
cut (not Google's Syne); VT323 for everything else.

The wordmark is its own thing: **Shrikhand**, in the pink of Mistral Small's
pixel flower (`#ff92dc`) with a neon outline in the same hue at full saturation
(`#ff0fb3`). Six pieces of it are brand marks rather than letters and keep their
own colour — see `src/wordmark/Wordmark.tsx` and the font note in
`public/brand/SOURCES.md`.

Three colours mean exactly one thing each and nothing may borrow them:

| colour | meaning |
|---|---|
| light baltic `#8fe3e8` | the **warm** arm — it has the graph |
| marigold `#f5b642` | the **cold** arm |
| hibiscus `#f96746` | failure, or a confounded run |

Warm and cold are separated by ~140° of **hue**, not lightness — a badly
calibrated projector flattens lightness long before it flattens hue. Cold is
deliberately not periwinkle: periwinkle is all over the chrome, so an arm
wearing it would read as "the default" rather than as one side of a
comparison.

**A card named "Cold" is not the cold arm.** The Cold card is the stack
diagram; nothing on it is plotted, and its frame is periwinkle like the
connectors it contains. Marigold means the cold *series*, and only where a
number is drawn. The reverse mistake is the one to watch for: if a chart ever
takes periwinkle for a data colour, the rule above is broken and the two arms
stop being one hue apart.

Everything decorative rotates through `WHIMSY` in `src/lib/brand.ts`, which is
periwinkle-led and drawn entirely from Neo4j's palette.

Cards carry an inset rim plus two outer halos — a tight one that reads as the
edge catching light, a wide faint one that lifts the card off the ground.

**The halos are authored in screen pixels, not canonical units.** Everything
else scales with the card, which is right for anything content-like. A halo is
not content — it is a lighting effect, and light does not get smaller because
the thing it falls on is further away. In canonical units a 44px halo landed as
13px on a tile and 115px on the stage, which is why the tiles looked bare. The
Hud sets `--slide-scale` on each wrapper and `onGlass()` in `SlideChrome`
divides by it, cancelling the transform. The rim stays in canonical units
deliberately: it is a border, it belongs to the card, and it should thin out as
the card shrinks.

Needs `contain: layout` on the Hud wrapper, **not** `layout paint`: paint
containment clips a child's outer shadow to the border box and the glow
disappears entirely.

### Accents must be hex literals

`alpha()` in `src/lib/brand.ts` is the only way to fade an accent, and accents
are `#rrggbb` strings rather than CSS variables. The shorthand it replaces —
`` `${accent}44` `` — silently produces `var(--periwinkle)44`, which is not a
colour, so the browser discards the **entire** declaration. That shipped for
two passes: the title, feed and stack slides had no border and no glow at all,
and nothing said so. `alpha()` warns in dev if handed anything but a hex
literal.

## Compositing

Read the header comment in `src/hud/Hud.tsx` before touching the transform on a
slide wrapper. Short version: a promoted layer rasterises at its **unscaled**
size, so a 578px-wide tile still costs a 1920×1080 backing store — ×4 on a
Retina panel. Promoting all twenty cost roughly 660 MB, blew Chrome's tile
budget, and painted as rectangular fragments of stale tile across the HUD.

So `translate` not `translate3d`, `will-change` only on the two slides actually
moving and only while they move, `contain: layout paint` on every wrapper, and
transitions suppressed for one frame across a viewport change so entering
fullscreen re-lays-out instantly instead of animating twenty tiles at once.

Verified at 3840×2160 / dSF 2: 0 elements carry `will-change` at rest, 2
mid-morph, 0 after — through 14 rapid clicks and two viewport changes.

The ring invariant is verified the same way: 21 slides at 21 distinct
positions, exactly 1 stage-sized and 20 tile-sized, held across ten clicks, a
keyboard walk and a viewport change.

## The race

**Slay**, on the home card under the follow line, arms race mode; pressed, it
dims and reads *Slaying…*. The ring does not move; the **stage gives up a band**
on all four sides (`RACE_BAND`, 7% of its shorter side) and two Mistral Ms lap
it — warm in Mistral's own flame, cold in the same artwork at a cold hue. It is
display only: the deck reads `runs/`, it does not drive the GPU, and the button
says so on hover.

Being a control *inside a card* costs two things. It `stopPropagation`s, or
arming the race would also bounce the card off the board; and it is
`pointer-events: none` when the card is off-stage, because a tile's job is to
answer a click by joining the board, not to arm a race at 10px wide. Race state
reaches it through `hud/RaceMode` context rather than `SlideProps` — twenty
cards should not carry two fields about a racetrack.

The cold M is **not a second asset**. `mistral-M.svg` is imported as source and
every fill is re-hued, keeping each stop's saturation and lightness, so the M
stays shaded pixel art and re-running the extractor updates both racers at once.
A constant hue *rotation* would not do — the flame spans amber to dark red, and
rotating the dark end lands it in green.

**The racers run, and both the lap and the speed come from `closeness`.**
That is the harness's own measure of how far along the v1 → v2 path a tree is:
`0.0` is the untouched checkout, `1.0` is the human's merged PR, and *negative*
means the attempt moved away from the answer. It is what the harness itself now
judges progress on — `moved = closeness > prior` in `vibe_agent.py`, where
`prior` is the previous attempt's closeness.

| | from | meaning |
|---|---|---|
| **track length** | `1 − closeness(previous attempt)` | the journey still to run from where that arm last stood |
| **speed** | `closeness(latest attempt)`, in closeness-units per second | how close it has got |

```
laps/second = closeness_now / (1 − closeness_prev)
```

There is no display constant in that: one closeness-unit is one second. On the
run going while this was written, warm scored `+0.054` against a lap of `0.942`
— 17s a lap — and cold `+0.084` against `0.925`, 11s a lap. Verified against a
hand-computed case: `c=+0.050` after `0.100` gives exactly the 18s/lap the
track printed.

**Negative closeness runs backwards**, because that is what it means. An
attempt that scored `−0.4267` did not fail to progress; it took the tree
further from the answer than the untouched checkout, and a racer that reverses
says that better than any caption. Lap counts go negative with it, and the
track prints `net −2`.

Two clamps, both stated on the track: a lap is never shorter than 6s (a
near-finished arm would blur) nor longer than 45s (at `closeness 0.001` a lap
would take twenty minutes, which on stage is indistinguishable from the racer
being broken — the fault this whole thing exists to fix). The raw closeness is
printed either way, so a crawl is never mistaken for progress.

**A fixture with no answer key reports no closeness at all** — `_closeness`
returns `None`, and the harness's own chart document omits the panel rather
than drawing zeroes. oapi, which the rehearsal loop runs, is one of those. On
those runs the race falls back to tests passing (or v1 surfaces, if the fixture
counts them) paced against the leader, and the track says
`no closeness on this fixture` in those words.

The motion is integrated per frame and written straight to the two elements'
transforms. **None of it goes through React** — and nothing else may write
those transforms. The element's JSX set one too, at the position each arm's
progress earned it, and the two writers fought: every re-render (the replay
clock ticks 4×/s, a live run's index lands 1×/s) snapped both tokens back to a
fixed anchor and the frame loop crawled away again. On screen that is two Ms
twitching near two points, with apparent speed decided by whose anchor was
further round. The only React state is the lap count, which changes once a lap.

**Live, or a replay.** A run still being written is tracked as it lands, and
the racers' speeds change as attempts are graded. A *finished* run arrives as
one snapshot, so arming it replays it on the clock from each event's own `t`,
stretched or compressed into 40–60s, with the rate on the track: `replay ×19`,
`replay ×0.4`. **A replay loops** rather than parking — a race that stops after
a minute leaves two Ms standing for the rest of the talk — and the loop counter
is on the track, so lap 12 is never mistaken for a twelve-lap run. Which of the
two it is gets latched when Slay is pressed, so a live run that finishes
mid-talk keeps being tracked rather than rewinding itself under the audience.

A run counts as finished on `RUN_END`, on `FILE_DONE` for *both* arms (the
rehearsal loop writes no `RUN_END`), or after six minutes of silence. Six, not
twenty-five seconds: measured on a live x12sdk run, the log went quiet for 3½
minutes between two graded attempts, and at 25s the deck called it finished and
replayed a race that was still being run.

**Only `FILE_DONE` with `success` stops a racer**, on the line, because
converging is the oracle's call and nothing else. A finisher parks at
`FINISH_T`, just *before* the line, so it cannot be confused with a racer that
never started — on a closed lap `t=0` and `t=1` are the same point. A *running*
racer uses the whole lap, `0..1`: confining it to `START_T..FINISH_T` left a 3%
gap it hopped across once a lap, measured at ~104px.

Under `prefers-reduced-motion` nobody laps: each racer holds the position its
progress earns it, which still says who is ahead.

Arming the race re-lays-out every card at once, so it is taken in **one frame**
with transitions suppressed, exactly as a viewport change is — twenty cards
mid-transition is the layer storm. Only the track's opacity animates.

> **Colour conflict, flagged not fixed.** The racers are orange = warm, blue =
> cold. The rest of the deck uses `ARM_COLOR` — light baltic (cyan) = warm,
> marigold (gold) = cold — and the table above says nothing may borrow those.
> Two colour languages for the same two arms is worse than either; the racers'
> mapping is the intuitive one, so flipping `ARM_COLOR` to match is probably the
> right resolution. Not done unasked, because it repaints slides already signed
> off.

## Brand marks

Where a node or a card IS a component of the stack, it carries that vendor's
own mark: SGLang's square logo, Mistral's model-small icon on the model and
the flame M on the agent loop, Daytona's glyph, Neo4j's. `SlideChrome` takes a
`mark` prop (left of the title, sized off the type floor); the two diagrams
place marks inside their boxes.

Two rules. **Nothing gets a mark it does not own** — a checkout, an edited tree
and a test suite are not anyone's brand, so those are drawn glyphs, and RunPod,
which ships no asset here, gets a generic chip rather than a lookalike.
**Provenance for every file is in [`public/brand/SOURCES.md`](public/brand/SOURCES.md)**,
including what is missing and how to drop it in.

## Type: 12pt floor

Cards are authored in canonical units and CSS-scaled, so a size in the source
is not a size on the glass — 26 units is 16px on a full board, 8px in a quarter
slot, 3.7px on a ring tile. Measured across the twenty cards on stage, body
text was rendering between **8px and 15px**. Not small: unreadable.

Every font size now goes through `pt(units)` from `lib/type.ts`, which compiles
to `max(Npx, var(--type-floor))`. The Hud sets `--type-floor` on each *staged*
card to `16px / scale` — the canonical size that lands at exactly 12pt after
the transform. A card renders at its designed proportions while there is room
and stops shrinking at 12pt; what gives instead is **content**, clipped, which
is the trade this deck already makes everywhere else. Verified: all twenty
cards report a 16px minimum on the board.

**Tiles are exempt, and that is physics.** The floor is `0px` at home. A ring
tile is 276×155px on a 1920 screen and holds about seven words at 12pt —
enforcing it there would replace twenty miniature cards with twenty fragments
of a sentence. A tile is a texture that says "something is happening over
here"; the board is where reading happens.

Three things only became visible once the type was legible, and are fixed:
the stack diagram's arrow labels all piled up at their line midpoints (they now
sit at staggered positions along each line); a 0..1 chart axis printed its
three ticks as `0, 1, 1` (decimals now scale to the axis range); and a long
footer wrapped to a second line inside a fixed-height box and got cut in half
(the footer is `min-height` now).

## The character

Miss Slaytona stands on the right of the home card. She is a three-layer 8-bit
rig — body, wand, and the graph she summons — authored as arrays of strings, one
character per pixel, in `src/character/slaytonaRig.ts`. No assets, no build step.
Costume, never decal: the wig is connected nodes with edges between them, the
gown steps warm bands from bodice to hem, the wand is the router, and the
platform heels are the sandbox she executes from.

**Her canvas is 34×48 and stays 34×48.** The backing store is one pixel per
sprite pixel and CSS magnifies it under `image-rendering: pixelated`. That is
forced by the HUD, not a shortcut: a card is authored in canonical units and
then CSS-scaled, so a canvas sized in canonical units would be rasterised at the
wrong scale *and* would be a ~700×1000 buffer repainting every 340ms next to
twenty other scaled subtrees. A repaint is 1632 pixels; the compositor does the
magnifying.

**She reacts to the feed**, per the rig author's mapping, against event types
the harness actually emits:

| event | pose |
|---|---|
| `MEMORY_READ` with `hits > 0` | **summon** — the graph materialises on her far side |
| `MEMORY_WRITE` | **wink** |
| `FILE_DONE`, warm, `success` | **dip** |

Only *new* events count. The feed opens with a snapshot of the whole run, and
replaying thousands of historical events as choreography would have her
convulsing on load — so the cursor is planted at the end of whatever arrives
first, per run id.

**When the card goes portrait, the lettering leaves and she stays.** The lockup
is lettering beside a character, which only works while the card is wider than it
is tall; the packer can hand the home card a 7×8 or a 4×8 slot. Below `W/H = 1`
the lettering slides out to the left and she takes the whole card. She is the one
that stays — the wordmark is legible in the ring tile and on the board, a
four-square-wide sliver of "Slaytona" is not, and she is what the card is for.
The lettering is translated out rather than unmounted, because the wordmark's
`role="img"` is this headerless card's accessible name; **Slay** is rehomed to the
bottom-left rather than lost, so the one control on the card cannot be taken away
by how the board happened to pack.

This also fixed a real squash. She was sized `height: 100%; width: auto;
max-width: 100%`, and a replaced element clamped by `max-width` with an explicit
height does **not** keep its aspect — the width shrinks and the height does not.
Any box narrower than 0.71 of its own height squashed her sideways. `object-fit:
contain` with `object-position: … bottom` scales her down instead and stands her
on the floor, which is what the old declaration was reaching for.

Four hexes in her palette (Mid Baltic, Periwinkle, Marigold, Highlighter) shipped
in the rig marked `APPROXIMATE — replace with the real hexes from Needle`; they
now come from `lib/brand.ts`. Everything else is the author's.

`src/character/Sprite.tsx` and `sprites.ts` are the separate, static one-layer
path — a text matrix rendered as a single `box-shadow` chain, one DOM node, not
one per pixel. Only the reserved-slot noise uses it now.

Fonts are self-hosted in `public/fonts`. Brand assets and every colour value
are traced to source in [`public/brand/SOURCES.md`](public/brand/SOURCES.md) —
including the one asset that could not be fetched here and how to drop it in.
