/**
 * The deck. One flat list — there is no nesting and no grouping.
 *
 * Index 0 is the home card: it is what the board holds on load, and what
 * `Home` / `Esc` / Reset return to. Every card owns the ring slot of the same
 * index, permanently — homes do not drift, so a digit key addresses a card and
 * a ring position at once.
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
 *
 * To add content: replace a `makeSlotSlide(n)` entry with a real component and
 * give it an honest bias. Nothing else changes.
 */
import { ALARM, ARM_COLOR, BRANDS, NEO4J, whimsyAt } from '@/lib/brand'
import { DECK_SIZE } from '@/lib/layout'
import { BIAS_SQUARE, BIAS_TALL, BIAS_WIDE } from '@/lib/stage'
import { TitleSlide } from './TitleSlide'
import { StackSlide } from './StackSlide'
import { FeedSlide } from './FeedSlide'
import { ArmsSlide } from './ArmsSlide'
import { TerminalSlide } from './TerminalSlide'
import { CurveSlide } from './CurveSlide'
import { DaytonaSlide } from './DaytonaSlide'
import { AttemptsSlide } from './AttemptsSlide'
import { GraphSlide } from './GraphSlide'
import { ReasoningSlide } from './ReasoningSlide'
import { OntologySlide } from './OntologySlide'
import { SglangSlide } from './SglangSlide'
import { VibeSlide } from './VibeSlide'
import { DistillSlide } from './DistillSlide'
import { SkillSlide } from './SkillSlide'
import { SkillGrowthSlide } from './SkillGrowthSlide'
import { CrossRunSlide } from './CrossRunSlide'
import { CostSlide } from './CostSlide'
import { ErrorsSlide } from './ErrorsSlide'
import { ConfoundSlide } from './ConfoundSlide'
import { makeSlotSlide } from './SlotSlide'
import type { SlideDef } from './types'

const REAL: SlideDef[] = [
  {
    id: 'title',
    title: 'Miss Slaytona Fourje',
    accent: NEO4J.periwinkle,
    // A title wants width for the display type.
    bias: BIAS_WIDE,
    Component: TitleSlide,
  },
  {
    id: 'terminal',
    title: 'RunPod terminal',
    accent: NEO4J.lightForest,
    // Fixed-width transcript lines that must not wrap. The widest thing here.
    bias: BIAS_WIDE,
    Component: TerminalSlide,
  },
  {
    id: 'curve',
    title: 'Improvement curve',
    accent: NEO4J.lightBaltic,
    // A chart with axis labels and a caveat strip. Wants area, not a strip.
    bias: BIAS_SQUARE,
    Component: CurveSlide,
  },
  {
    id: 'daytona',
    title: 'Daytona verification',
    accent: BRANDS.daytona.accent,
    // Seven columns, one of them a long error signature.
    bias: BIAS_WIDE,
    Component: DaytonaSlide,
  },
  {
    id: 'attempts',
    title: 'Attempt anatomy',
    accent: NEO4J.marigold,
    // A growing list of events. Rows over columns.
    bias: BIAS_TALL,
    Component: AttemptsSlide,
  },
  {
    id: 'graph',
    title: 'The memory graph',
    accent: NEO4J.lightPeriwinkle,
    // A force layout wants area in both axes, not a strip.
    bias: BIAS_SQUARE,
    Component: GraphSlide,
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
    id: 'ontology',
    title: 'The ontology of memory',
    accent: NEO4J.lightForest,
    // A radial diagram. Square or nothing.
    bias: BIAS_SQUARE,
    Component: OntologySlide,
  },
  {
    id: 'stack',
    title: 'The stack',
    accent: BRANDS.daytona.accent,
    // Four logo panels in a 2x2 — squarest slot available, please.
    bias: BIAS_SQUARE,
    Component: StackSlide,
  },
  {
    id: 'feed',
    title: 'Event tail',
    accent: NEO4J.lightPeriwinkle,
    // The terminal case: fixed-width rows that must not wrap. Give it width
    // over height every time.
    bias: BIAS_WIDE,
    Component: FeedSlide,
  },
  {
    id: 'arms',
    title: 'Warm vs cold',
    accent: ARM_COLOR.warm,
    // Twelve rows, three columns. It wants rows far more than columns.
    bias: BIAS_TALL,
    Component: ArmsSlide,
  },
  {
    id: 'sglang',
    title: 'SGLang',
    accent: BRANDS.sglang.accent,
    // Three source excerpts stacked. Wants height, and lines must not wrap.
    bias: BIAS_WIDE,
    Component: SglangSlide,
  },
  {
    id: 'vibe',
    title: 'Vibe',
    accent: NEO4J.periwinkle,
    bias: BIAS_WIDE,
    Component: VibeSlide,
  },
  {
    id: 'distill',
    title: 'AIP distillation',
    accent: NEO4J.marigold,
    // One row per distillation, growing.
    bias: BIAS_TALL,
    Component: DistillSlide,
  },
  {
    id: 'skill',
    title: 'The distilled skill',
    accent: NEO4J.marigold,
    // A page of YAML. It wants as much area as it can get.
    bias: BIAS_SQUARE,
    Component: SkillSlide,
  },
  {
    id: 'skill-growth',
    title: 'Skill growth',
    accent: NEO4J.marigold,
    bias: BIAS_SQUARE,
    Component: SkillGrowthSlide,
  },
  {
    id: 'cross-run',
    title: 'Cross-run summary',
    accent: NEO4J.lightPeriwinkle,
    // Eight columns of fixed-width numbers. Width over height.
    bias: BIAS_WIDE,
    Component: CrossRunSlide,
  },
  {
    id: 'cost',
    title: 'What it cost',
    accent: NEO4J.marigold,
    // Two columns of bars, side by side.
    bias: BIAS_SQUARE,
    Component: CostSlide,
  },
  {
    id: 'errors',
    title: 'What is in the way',
    accent: ALARM,
    // Long error signatures that must not wrap.
    bias: BIAS_WIDE,
    Component: ErrorsSlide,
  },
  {
    id: 'confound',
    title: 'Does this run count?',
    accent: NEO4J.lightForest,
    bias: BIAS_TALL,
    Component: ConfoundSlide,
  },
]

const ROTATION = [BIAS_WIDE, BIAS_SQUARE, BIAS_TALL]

const SLOTS: SlideDef[] = Array.from(
  { length: DECK_SIZE - REAL.length },
  (_, i) => {
    const n = i + REAL.length
    return {
      id: `slot-${n}`,
      title: `Slot ${String(n).padStart(2, '0')}`,
      accent: whimsyAt(n),
      // Placeholders rotate so the packer has something to chew on before the
      // real cards exist. Replace with an honest bias when the card is built.
      bias: ROTATION[n % ROTATION.length],
      Component: makeSlotSlide(n),
    }
  },
)

export const SLIDES: SlideDef[] = [...REAL, ...SLOTS]

if (import.meta.env.DEV && SLIDES.length !== DECK_SIZE) {
  console.warn(
    `[registry] ${SLIDES.length} cards but the ring seats ${DECK_SIZE}. ` +
      `${SLIDES.length > DECK_SIZE ? 'The surplus has no home and will never render.' : 'A ring slot will be empty.'}`,
  )
}
