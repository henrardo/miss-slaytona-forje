/**
 * The stage model: what happens when cards join the board.
 *
 * The board is a grid of squares (14 x 8 — see STAGE_COLS). A card joining it
 * occupies some whole number of squares. Cards already there re-pack.
 *
 * ── Bias ─────────────────────────────────────────────────────────────────
 *
 * Every card ranks the three shape classes it could be handed. A terminal-ish
 * card wants to be WIDE, so it ranks `hor` first; a tall list ranks `vert`
 * first; a logo block ranks `sqr` first. The packer then picks, among the
 * arrangements that fit N cards, the one that satisfies the most bias.
 *
 * This is why arrangements come in alternatives rather than one preset per
 * count: for two cards there is a side-by-side (two squarish halves) AND a
 * stacked (two wide bands), and which is right depends entirely on what the
 * two cards want to be. Bias is the input that decides.
 *
 * Packing is exhaustive and deterministic — at most 4 cards, so at most 24
 * assignments per arrangement and a handful of arrangements. No heuristics, no
 * surprises in front of an audience: the same cards always produce the same
 * board.
 */
// Both come from layout.ts. They used to be two numbers — 14 imported, 8
// hard-coded here to "mirror" a derived value over there — and they disagreed
// the first time the stage changed shape. One source now; see STAGE_ROWS.
import { STAGE_COLS, STAGE_ROWS } from './layout'

export { STAGE_ROWS }

/**
 * How many cards may share the board.
 *
 * Four, for two independent reasons. Legibility: 14 x 8 with a ~4x3 minimum
 * would fit nine, but nobody at the back of a room reads nine cards at once.
 * Compositing: re-packing N cards is N simultaneous transform transitions,
 * and that is the layer storm documented in hud/Hud.tsx. Four is comfortable;
 * nine is not.
 *
 * A fifth card does not get refused — the oldest is evicted, FIFO. Refusing a
 * click on stage looks like a broken deck.
 */
export const MAX_ON_STAGE = 4

export type ShapeClass = 'hor' | 'vert' | 'sqr'

/** A card's ranked preference. Most wanted first. Must list all three. */
export type Bias = readonly [ShapeClass, ShapeClass, ShapeClass]

export const BIAS_WIDE: Bias = ['hor', 'sqr', 'vert']
export const BIAS_TALL: Bias = ['vert', 'sqr', 'hor']
export const BIAS_SQUARE: Bias = ['sqr', 'hor', 'vert']

export interface Slot {
  col: number
  row: number
  w: number
  h: number
}

/**
 * Cells are square, so a footprint's aspect in squares IS its visual aspect.
 * The dead band is deliberately wide: 10x8 (1.25) should read as "wide" and
 * 7x8 (0.875) as "square-ish", because that is how they look on a projector.
 */
const HOR_AT = 1.2
const VERT_AT = 1 / HOR_AT

export function classify({ w, h }: { w: number; h: number }): ShapeClass {
  const ratio = w / h
  if (ratio >= HOR_AT) return 'hor'
  if (ratio <= VERT_AT) return 'vert'
  return 'sqr'
}

/**
 * Convex on purpose: 6 / 2 / 1, not 3 / 2 / 1.
 *
 * A linear scale makes two second-choices (4) beat one first-choice (3), so
 * the packer spreads mild disappointment evenly and nothing ever gets what it
 * asked for. Measured, not theorised: with 3/2/1 a four-card board tied at 10
 * between "give the square card its square" and "give everyone their second
 * choice", and the tie-break handed out seconds.
 *
 * With 6/2/1 a single first choice (6) outranks two seconds (4), so a card
 * that really wants to be wide gets to be wide. Two first choices still beat
 * one, which is the behaviour you want when cards genuinely compete.
 */
const RANK_SCORE = [6, 2, 1]

function biasScore(bias: Bias, shape: ShapeClass): number {
  const rank = bias.indexOf(shape)
  return rank < 0 ? 0 : RANK_SCORE[rank]
}

/**
 * Candidate arrangements by card count. The FIRST entry for each count is the
 * default — it wins ties, so it is what you get when bias has no opinion.
 *
 * Every arrangement tiles 14 x 8 exactly, with no gaps and no overlaps; the
 * dev assertion at the bottom of this file enforces that, because an
 * arrangement that silently leaves a hole looks like a layout bug at the worst
 * possible moment.
 */
export const ARRANGEMENTS: Record<number, Slot[][]> = {
  1: [[{ col: 0, row: 0, w: 14, h: 8 }]],

  2: [
    // two squarish halves
    [
      { col: 0, row: 0, w: 7, h: 8 },
      { col: 7, row: 0, w: 7, h: 8 },
    ],
    // two wide bands — what two terminal-ish cards want
    [
      { col: 0, row: 0, w: 14, h: 4 },
      { col: 0, row: 4, w: 14, h: 4 },
    ],
    // a tall sidebar and a wide main
    [
      { col: 0, row: 0, w: 4, h: 8 },
      { col: 4, row: 0, w: 10, h: 8 },
    ],
  ],

  // From three cards up, every arrangement MIXES shape classes. A board of
  // three or four identical shapes reads as a spreadsheet, not a composition,
  // and it also makes bias meaningless: if every slot is the same class there
  // is nothing for a card's preference to win. The dev assertion below
  // enforces it, so an all-hor or all-vert arrangement cannot creep back in.
  3: [
    // squarish anchor, two wide
    [
      { col: 0, row: 0, w: 7, h: 8 },
      { col: 7, row: 0, w: 7, h: 4 },
      { col: 7, row: 4, w: 7, h: 4 },
    ],
    // tall sidebar, two wide
    [
      { col: 0, row: 0, w: 4, h: 8 },
      { col: 4, row: 0, w: 10, h: 4 },
      { col: 4, row: 4, w: 10, h: 4 },
    ],
    // broad squarish anchor, two narrow wides
    [
      { col: 0, row: 0, w: 9, h: 8 },
      { col: 9, row: 0, w: 5, h: 4 },
      { col: 9, row: 4, w: 5, h: 4 },
    ],
    // tall sidebar, one broad wide over one very wide
    [
      { col: 0, row: 0, w: 5, h: 8 },
      { col: 5, row: 0, w: 9, h: 5 },
      { col: 5, row: 5, w: 9, h: 3 },
    ],
  ],

  4: [
    // anchor, wide, and two small — all three classes present
    [
      { col: 0, row: 0, w: 7, h: 8 },
      { col: 7, row: 0, w: 7, h: 4 },
      { col: 7, row: 4, w: 3, h: 4 },
      { col: 10, row: 4, w: 4, h: 4 },
    ],
    // tall sidebar, one broad wide, two halves
    [
      { col: 0, row: 0, w: 4, h: 8 },
      { col: 4, row: 0, w: 10, h: 4 },
      { col: 4, row: 4, w: 5, h: 4 },
      { col: 9, row: 4, w: 5, h: 4 },
    ],
    // squarish anchor and three stacked wides
    [
      { col: 0, row: 0, w: 7, h: 8 },
      { col: 7, row: 0, w: 7, h: 3 },
      { col: 7, row: 3, w: 7, h: 3 },
      { col: 7, row: 6, w: 7, h: 2 },
    ],
    // tall sidebar, wide, square, wide — all three classes again
    [
      { col: 0, row: 0, w: 5, h: 8 },
      { col: 5, row: 0, w: 9, h: 4 },
      { col: 5, row: 4, w: 4, h: 4 },
      { col: 9, row: 4, w: 5, h: 4 },
    ],
  ],
}

/** How many distinct shape classes an arrangement offers. */
export const shapeSpread = (slots: Slot[]) => new Set(slots.map(classify)).size

export interface StageCard {
  id: string
  bias: Bias
}

export interface Placement {
  id: string
  slot: Slot
}

function* permutations<T>(xs: T[]): Generator<T[]> {
  if (xs.length <= 1) {
    yield xs
    return
  }
  for (let i = 0; i < xs.length; i++) {
    const rest = [...xs.slice(0, i), ...xs.slice(i + 1)]
    for (const p of permutations(rest)) yield [xs[i], ...p]
  }
}

/** Reading order: top to bottom, then left to right. */
const readingOrder = (slots: Slot[]) =>
  [...slots].sort((a, b) => a.row - b.row || a.col - b.col)

/**
 * Choose an arrangement and assign cards to it.
 *
 * Cards arrive in join order. Ties are broken toward the earlier arrangement
 * and the earlier permutation, which means: the default arrangement wins when
 * bias is indifferent, and cards land in join order reading top-left to
 * bottom-right. Deterministic in, deterministic out.
 */
export function packStage(cards: StageCard[]): Placement[] {
  const n = Math.min(cards.length, MAX_ON_STAGE)
  if (n === 0) return []
  const options = ARRANGEMENTS[n]
  if (!options) return []

  let best: Placement[] | null = null
  let bestScore = -Infinity

  for (const arrangement of options) {
    const slots = readingOrder(arrangement)
    for (const order of permutations(cards.slice(0, n))) {
      let score = 0
      for (let i = 0; i < n; i++) {
        score += biasScore(order[i].bias, classify(slots[i]))
      }
      // Strictly greater: first-found wins ties, so the default arrangement
      // and join order are the fallback.
      if (score > bestScore) {
        bestScore = score
        best = order.map((card, i) => ({ id: card.id, slot: slots[i] }))
      }
    }
  }
  return best ?? []
}

if (import.meta.env.DEV) {
  // Every arrangement must tile the board exactly. A hole or an overlap reads
  // as a rendering bug on stage and is impossible to diagnose live.
  for (const [count, options] of Object.entries(ARRANGEMENTS)) {
    options.forEach((slots, i) => {
      const covered = new Set<string>()
      let overlap = false
      for (const s of slots) {
        for (let c = s.col; c < s.col + s.w; c++) {
          for (let r = s.row; r < s.row + s.h; r++) {
            const key = `${c},${r}`
            if (covered.has(key)) overlap = true
            covered.add(key)
          }
        }
      }
      const expected = STAGE_COLS * STAGE_ROWS
      if (overlap || covered.size !== expected) {
        console.error(
          `[stage] arrangement ${count}/${i} covers ${covered.size} of ${expected} squares` +
            `${overlap ? ' and overlaps itself' : ''}`,
        )
      }
      // Three or more identical shapes is a spreadsheet, not a composition —
      // and it leaves bias with nothing to choose between.
      if (Number(count) >= 3 && shapeSpread(slots) < 2) {
        console.error(
          `[stage] arrangement ${count}/${i} is all ${classify(slots[0])} — ` +
            `arrangements for 3+ cards must mix at least two shape classes`,
        )
      }
    })
  }
}
