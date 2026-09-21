/**
 * The deck. One flat list — there is no nesting and no grouping.
 *
 * ── Sixteen cards in a frame that seats twenty ───────────────────────────
 *
 * The ring is the perimeter of a 6x6 grid, so it holds exactly twenty tiles
 * or it stops being a rectangle. The deck has sixteen things worth saying.
 * The four spare slots are the CORNERS, and they are held open by blocks of
 * colour rather than by cards nobody would ever stage — see CornerBlock.tsx
 * for why a corner is the right slot to give up.
 *
 * `CORNER_SLOTS` is derived from the ring's own fill order, not typed out:
 * `computeHudLayout` lays the tiles top row, bottom row, right column, left
 * column, so on a 6-wide ring the corners are 0 and 5 (top) and 6 and 11
 * (bottom). Change the ring shape and the corners move with it.
 *
 * ── Order ────────────────────────────────────────────────────────────────
 *
 * `CARDS` is in TALK order, and the cards are seated into the non-corner
 * slots in that order, so `ArrowRight` walks the deck as it is meant to be
 * told: the setup, the result, how an attempt is graded, what the memory
 * layer produced, then the machinery and the caveats.
 *
 * Homes are permanent: a card owns its ring slot for the whole talk. The
 * digit keys address the Nth CARD, skipping the corners, so `1` is always
 * the home card however the frame is filled.
 *
 * ── Bias ─────────────────────────────────────────────────────────────────
 *
 * Each card ranks the shape classes it wants to be handed, most wanted first.
 * The packer picks between arrangements to satisfy as much of that as it can,
 * so a card that ranks `hor` first gets a wide slot whenever one is going. Set
 * it from what the card's CONTENT needs, not from what looks nice empty:
 *
 *   BIAS_WIDE   long lines that must not wrap — logs, tails, timelines
 *   BIAS_TALL   lists and tables that want rows more than columns
 *   BIAS_SQUARE grids, logo blocks, big single figures
 */
import { BRANDS, NEO4J } from '@/lib/brand'
import { DECK_SIZE, ringShape } from '@/lib/layout'
import { BIAS_SQUARE, BIAS_TALL, BIAS_WIDE } from '@/lib/stage'
import { TitleSlide } from './TitleSlide'
import {
  ClosenessSlide,
  FilesParsingSlide,
  WorkRemainingSlide,
} from './MeasureSlide'
import { WarmStackSlide } from './WarmStackSlide'
import { RadixSlide } from './RadixSlide'
import { DaytonaSlide } from './DaytonaSlide'
import { TokenCostSlide } from './TokenCostSlide'
import { CodeGraphSlide } from './CodeGraphSlide'
import { ReasoningSlide } from './ReasoningSlide'
import { ModelSlide } from './ModelSlide'
import { VibeSlide } from './VibeSlide'
import { ColdStackSlide } from './ColdStackSlide'
import { TokensSlide } from './TokensSlide'
import { DaytonaStackSlide } from './DaytonaStackSlide'
import { RepoSlide } from './RepoSlide'
import { makeCornerBlock } from './CornerBlock'
import type { SlideDef } from './types'

/**
 * The cards, in talk order.
 *
 * Four were removed rather than reseated, because the deck was long and each
 * of them was already said somewhere better: **Event tail** (the raw JSONL —
 * Attempt anatomy is the same events, read), **Cross-run summary** (a table
 * of past runs, when the talk is about the run happening now), **The stack**
 * (superseded outright by Cold and Warm, which draw the same wiring with the
 * arms' asymmetry visible) and **Does this run count?** (the confound audit,
 * which belongs in the notes, not on a wall). They are in git.
 */
const CARDS: SlideDef[] = [
  {
    id: 'title',
    title: 'Miss Slaytona Fourje',
    accent: NEO4J.periwinkle,
    // A title wants width for the display type.
    bias: BIAS_WIDE,
    Component: TitleSlide,
  },
  {
    // The card that says what the whole talk is running on. Everything after
    // it assumes the reader has seen it.
    id: 'cold-stack',
    title: 'Cold',
    // Periwinkle, not the cold arm's marigold: this card is the stack, not
    // the series. See the note in ColdStackSlide.
    accent: NEO4J.periwinkle,
    // A left-to-right flow with a long return edge: it wants width.
    bias: BIAS_WIDE,
    Component: ColdStackSlide,
  },
  {
    // Warm immediately after cold, drawn by the same engine: the only honest
    // way to show a treatment is to show the control beside it.
    id: 'warm-stack',
    title: 'Warm',
    // Gold to cold's blue. The frame carries the arm; the diagram inside
    // both cards stays periwinkle.
    accent: NEO4J.marigold,
    bias: BIAS_WIDE,
    Component: WarmStackSlide,
  },
  {
    // Replaced the improvement curve, which was a chart nobody could read at
    // a glance. This one animates its argument instead of plotting it.
    id: 'radix',
    title: 'RadixAttention',
    accent: BRANDS.sglang.accent,
    // Twelve stacked request bars folding into a tree: it wants width, and
    // the bars must not be squeezed into a column.
    bias: BIAS_WIDE,
    Component: RadixSlide,
  },
  {
    id: 'reasoning',
    title: 'Reasoning stream',
    accent: NEO4J.lightBaltic,
    // Stacked groups of prose. Rows over columns, every time.
    bias: BIAS_TALL,
    Component: ReasoningSlide,
  },
  {
    // Replaced "Attempt anatomy", a live list of RESTORED / REJECTED /
    // ABORTED events — which is the event log read aloud, and the three
    // cards after it already carry what those events mean. This says what
    // an hour of H200 buys instead, which nothing in the deck said.
    id: 'token-cost',
    title: 'Token cost',
    accent: NEO4J.lightForest,
    // One division, set large. Width: the denominator is a nine-digit
    // number and must not wrap under its own rule.
    bias: BIAS_WIDE,
    Component: TokenCostSlide,
  },
  {
    // Replaced "The distilled skill", which showed the procedure Cognee
    // holds verbatim. The skill's content is shown on Warm and argued on
    // Daytona; what nothing in the deck did was put the two agents' token
    // counts side by side, which is the comparison the project exists to
    // make. Read off every runs/*-metrics.json, arms kept apart.
    id: 'tokens',
    title: 'Tokens, head to head',
    accent: NEO4J.marigold,
    // Two figures facing each other over four paired bars: it wants width
    // far more than height, or the bars lose the precision they exist for.
    bias: BIAS_WIDE,
    Component: TokensSlide,
  },
  {
    // Replaced "What is in the way", a list of error signatures grouped by
    // frequency — which said what the agents were tripping over without
    // ever saying what they were working ON. Three questions, three
    // panels: what the package is, what it does, and why it cannot ship
    // until it is migrated.
    id: 'repo',
    title: 'The repo under test',
    accent: NEO4J.hibiscus,
    // Three panels, one of which is a wire-format string that must not
    // wrap. Width, and plenty of it.
    bias: BIAS_WIDE,
    Component: RepoSlide,
  },
  {
    // Replaced the ontology-of-memory card. One point — the exact model in
    // this talk is one anyone can pull and run — made in three panels.
    id: 'model',
    title: 'Mistral Small 4',
    accent: BRANDS.mistral.accent,
    // Three panels side by side. It wants width, and squeezing them into a
    // column would stack three headings above three fragments.
    bias: BIAS_WIDE,
    Component: ModelSlide,
  },
  {
    id: 'vibe',
    title: 'Mistral Vibe',
    accent: NEO4J.periwinkle,
    bias: BIAS_WIDE,
    Component: VibeSlide,
  },
  {
    // Replaced Skill growth. The companion to "Daytona verification": that
    // card shows every grading live and states no limits, so this one
    // carries the architecture and the numbers, and neither repeats the
    // other. Placed after Vibe — the harness, then the thing that judges it.
    id: 'daytona-stack',
    title: 'Daytona',
    accent: BRANDS.daytona.accent,
    // A boundary diagram: two territories side by side. It needs width.
    bias: BIAS_WIDE,
    Component: DaytonaStackSlide,
  },
  {
    // Replaced "The memory graph", a force layout of whatever Aura held.
    // This is the sharper claim from the same graph: the codebase is nodes
    // and edges, so querying it is a read rather than a summary.
    id: 'code-graph',
    title: 'The code graph',
    accent: BRANDS.neo4j.accent,
    // One wire across the card, and the route it does not take beneath it.
    bias: BIAS_WIDE,
    Component: CodeGraphSlide,
  },
  {
    // One of three measure cards. They replaced "The result" (all three
    // measures crammed into one card, three y-axes and six lines in a third
    // of a card each), "What warm was given" and "SGLang". Each now gets the
    // whole board: two lines, the head-to-head end values, and the harness's
    // own reference lines. See MeasureSlide.tsx.
    id: 'work-remaining',
    title: 'Surfaces left',
    accent: NEO4J.lightPeriwinkle,
    // A line chart across the run. Width.
    bias: BIAS_WIDE,
    Component: WorkRemainingSlide,
  },
  {
    id: 'files-parsing',
    title: 'Still compiles',
    accent: NEO4J.lightForest,
    bias: BIAS_WIDE,
    Component: FilesParsingSlide,
  },
  {
    id: 'closeness',
    title: 'Distance to the answer',
    accent: NEO4J.lightBaltic,
    bias: BIAS_WIDE,
    Component: ClosenessSlide,
  },
  {
    id: 'daytona',
    title: 'Daytona verification',
    accent: BRANDS.daytona.accent,
    // Seven columns, one of them a long error signature.
    bias: BIAS_WIDE,
    Component: DaytonaSlide,
  },
]

/**
 * The four corner slots, derived from the ring's fill order in
 * `computeHudLayout`: top row left to right, then the bottom row, then the
 * columns. So the corners are the ends of those first two runs.
 */
const { cols } = ringShape(DECK_SIZE)
export const CORNER_SLOTS = [0, cols - 1, cols, cols * 2 - 1]

/**
 * Twenty slots: cards in talk order, corners held open by colour.
 *
 * This is why the title now sits in slot 1 rather than slot 0 — slot 0 is the
 * top-left corner, and the frame's corners are no longer cards. Everything
 * that followed her moved along with her.
 */
export const SLIDES: SlideDef[] = (() => {
  const out: SlideDef[] = []
  const queue = [...CARDS]
  for (let slot = 0; slot < DECK_SIZE; slot++) {
    if (CORNER_SLOTS.includes(slot)) {
      out.push({
        id: `corner-${slot}`,
        title: '',
        accent: NEO4J.periwinkle,
        bias: BIAS_SQUARE,
        Component: makeCornerBlock(CORNER_SLOTS.indexOf(slot)),
        decorative: true,
      })
      continue
    }
    const card = queue.shift()
    if (card) out.push(card)
  }
  if (import.meta.env.DEV && queue.length) {
    console.warn(
      `[registry] ${queue.length} card(s) have no slot: ${queue
        .map((c) => c.id)
        .join(', ')}. The ring seats ${DECK_SIZE} and ` +
        `${CORNER_SLOTS.length} of those are corners.`,
    )
  }
  return out
})()

/** Every index that is a real card, in talk order. The walk and the digits. */
export const CARD_SLOTS = SLIDES.map((s, i) => (s.decorative ? -1 : i)).filter(
  (i) => i >= 0,
)

/** What the board holds on load, and what Home / Esc / Reset return to. */
export const HOME_SLOT = CARD_SLOTS[0]

if (import.meta.env.DEV && SLIDES.length !== DECK_SIZE) {
  console.warn(
    `[registry] ${SLIDES.length} tiles but the ring seats ${DECK_SIZE}. ` +
      `${SLIDES.length > DECK_SIZE ? 'The surplus has no home and will never render.' : 'A ring slot will be empty.'}`,
  )
}
