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

`?run=<id>` pins one run instead — use that to rehearse against a finished one:

```
http://127.0.0.1:5273/?run=swarm-1789812476
```

## The shape

**One flat list. No nesting, no groups.** A tile *is* a slide: the same
component, authored once at 1920×1080, CSS-scaled to fit its slot. Not a
thumbnail, not a summary view — the same component.

Every slide is mounted once for the life of the session in a single
absolutely-positioned layer. Staging one changes nothing but its transform
target; it is never unmounted or re-parented. A tile that has been collecting
for twenty minutes arrives on stage with twenty minutes of state intact.

**Twenty cards, twenty homes, one board.** Clicking a card at home sends it to
the board in the middle, where everything already there re-packs around it.
Clicking a card on the board sends it home. Up to four share the board.

**Homes are permanent** — card *i* always owns ring slot *i*, for the whole
talk. A card away from home leaves a **ghost** in its slot: a dashed socket
with its name on it, itself clickable to recall the card. So the ring still
reads as complete, nothing drifts, and a digit key addresses a card and a ring
position at once because those are now the same thing.

`DECK_SIZE` in `lib/layout.ts` is the authority; the registry warns in dev if
the card count drifts from it.

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
| `←` `→` `space` | linear walk — the board becomes exactly that one card |
| `1`–`9`, `0` | toggle that card on/off the board |
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

It snaps rather than animates, deliberately: a reset can move all twenty-one
slides at once, and twenty-one simultaneous transform transitions is the same
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

## The twenty cards

Every slot is a real card; there are no placeholders left. Each one names the
file it reads, and none of them recomputes a number the harness already
produced.

| # | card | source |
|---|---|---|
| 0 | Miss Slaytona Fourje | the wordmark, the sprite, Slay |
| 1 | RunPod terminal | `runs/*.log`, tailed — live or REPLAY |
| 2 | Improvement curve | `orchestrator/series.py`'s chart document |
| 3 | Daytona verification | `SANDBOX_CREATED` + `ATTEMPT_DONE` |
| 4 | Attempt anatomy | `RESTORED` / `REJECTED` / `ABORTED`, interleaved |
| 5 | The memory graph | Neo4j delta poll, canvas force layout |
| 6 | Reasoning stream | `ReasoningStep.thought` / tool calls / entities |
| 7 | The ontology of memory | `CALL db.schema.visualization()` |
| 8 | The stack | hand-drawn, event-lit |
| 9 | Event tail | `runs/<id>.jsonl`, verbatim |
| 10 | Warm vs cold | `runs/<id>-metrics.json` |
| 11 | SGLang | real source + hybrid sparkle |
| 12 | Vibe | real source + hybrid sparkle |
| 13 | AIP distillation | `DISTILLED`, with rejection reasons |
| 14 | The distilled skill | `skills/versions*/vNNN.md` |
| 15 | Skill growth | every version, by bytes |
| 16 | Cross-run summary | `runs/cross-run.md` |
| 17 | What it cost | attempt vs distillation, kept apart |
| 18 | What is in the way | `error_signature`, grouped |
| 19 | Does this run count? | `known_differences` + provenance |

### The sparkle is two resolutions, and says which

Cards 8, 11 and 12 light a region when the thing it does happens. There are two
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
the GPU price appears under "skill v", which is how it was found. Card 16 shows
only rows whose width matches the header and reports the rest as unreadable —
the fix belongs in `metrics.py`, not in the deck.

**The skill sawtooths.** The procedure is rewritten from scratch each time, so
it routinely halves and regrows; marking every drop put forty overlapping
labels on card 15. The three deepest are labelled and the count is in the
footer.

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

**The racers run, and progress is SPEED.** Position-as-progress was the first
model and it does not survive the data: five graded attempts across a 15-second
rehearsal is five small hops and then stillness, and on x12sdk, where the suite
never moves, it was two Ms sitting on the start line for a whole talk. A
racetrack whose racers do not go round is a diagram.

So both arms lap the board continuously while the run is going, and the one
making more of the measure laps faster. The gap, and the **lap counts on the
track**, are the race; an arm that converges stops at the line. A stalled arm
still circles slowly, which is true — it is still burning GPU on attempts that
are not landing. Lap times run from 26s to 9s.

Speed is driven by each arm's progress **relative to the leader's**, not by its
absolute share. On the run above, warm cleared 60 of 364 surfaces and cold 8:
as absolute shares those are lap times of 23.2s and 25.6s, a difference nobody
in a room can see, for a run where one arm did seven times the work. Against
the leader they become 9s and 23.8s. The caption prints the raw counts — `warm
60 · cold 8 of 364 seen` — so the pace never has to be taken on trust.

The motion is integrated per frame and written straight to the two elements'
transforms. **None of it goes through React**: sixty state updates a second
would re-render the track, both lane paths and the caption sixty times a
second, next to a force simulation, a canvas sprite and twenty live cards. The
only state is the lap count, which changes once a lap.

**Which number the measure is** is decided from the fixture's own data:

| the measure | when | denominator |
|---|---|---|
| share of best `tests_passed` | the suite moves — oapi goes 5 → 9 → 33 | lowest to best reported in the run |
| `v1_remaining` surfaces cleared | the fixture reports surfaces — x12sdk | the most anyone was still carrying |

`tests_passed` is the measure this project trusts, and on x12sdk it does not
move: the harness's own note records **70% of 77 graded attempts scoring exactly
0**, because 0 means both "has not migrated it yet" and "broke the package". A
race run on that number is two Ms crawling in step for a whole talk. Surfaces
are counted off the source and are defined even when the tree does not parse.

The surfaces denominator is labelled `of 364 seen`, never `of 383`: the
untouched count is never emitted, because the first graded attempt has already
edited the tree. On that measure an arm can lead *because* it broke the
package, so a racer whose latest attempt does not fully parse is **haloed in
the alarm colour** and the caption says `cold 64/65 files parse`.

**Only `FILE_DONE` with `success` puts a racer on the line** and stops it,
because converging is the oracle's call and nothing else.

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

Racers leave from just *after* the start line and finish just *before* it. On a
closed lap t=0 and t=1 are the same point, so without that a racer who converged
would park exactly where one who had not started sits.

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
