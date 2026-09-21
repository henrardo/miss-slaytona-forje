/**
 * A corner of the frame, with nothing in it.
 *
 * The ring is the perimeter of a 6x6 grid — it seats twenty tiles or it stops
 * being a rectangle. Sixteen cards is the right number of things to say, so
 * four slots have to be held open by something, and the honest something is a
 * block of colour rather than a card nobody will ever put on the board.
 *
 * It takes the CORNERS because a corner is the weakest slot in the ring: it
 * is the furthest tile from the eye's path along either edge it belongs to,
 * and it is the only slot that has to read in two directions at once. If a
 * slot has to hold nothing, it should be one of those.
 *
 * ── What it is, exactly ─────────────────────────────────────────────────
 *
 * OPAQUE, because the vignette and the page grid show through anything that
 * is not, and a translucent corner reads as a card that failed to load rather
 * than as a deliberate blank.
 *
 * PERIWINKLE, and not marigold or light baltic. Those two mean the cold arm
 * and the warm arm everywhere a number is drawn (see lib/brand.ts), and four
 * large gold blocks in the frame would be the deck's loudest use of a colour
 * that is supposed to mean one thing. Periwinkle is the chrome accent — it
 * already means "this is the holder, not the content".
 *
 * NOT A BUTTON. No click target, no ghost, no keyboard stop, `aria-hidden`.
 * A decorative tile that can be staged is just a card with no content, which
 * is the thing this exists to avoid.
 */
import { NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

/** Matches SlideChrome's, so the corners sit in the same family as the cards. */
const RADIUS = 14

/**
 * The four corners, in ring-slot order: top-left, top-right, bottom-left,
 * bottom-right. The ramp runs deep at the top of the frame to light at the
 * bottom, so the ring reads as lit from below like the cards' own halos do,
 * and each block's gradient points AWAY from the hole — diagonally outward —
 * so the four of them frame the stage instead of pointing at each other.
 */
const CORNERS = [
  { from: NEO4J.deepPeriwinkle, to: NEO4J.periwinkle, angle: 135 },
  { from: NEO4J.deepPeriwinkle, to: NEO4J.periwinkle, angle: 225 },
  { from: NEO4J.periwinkle, to: NEO4J.deepPeriwinkle, angle: 135 },
  { from: NEO4J.periwinkle, to: NEO4J.deepPeriwinkle, angle: 225 },
] as const

/**
 * A scrim over the ramp, and the reason for it: at full strength the four
 * blocks were the brightest things on the screen. A corner is the weakest
 * slot in the ring — it cannot be the loudest thing in it, or the frame
 * out-shouts the deck. This sits the blocks below the cards in luminance
 * while keeping them unmistakably periwinkle.
 *
 * Layered rather than eyedropped, so both stops stay traceable to the
 * palette instead of becoming two more hexes nobody can source.
 */
const SCRIM = 0.42

export function makeCornerBlock(n: number) {
  const c = CORNERS[n % CORNERS.length]
  return function CornerBlock(_: SlideProps) {
    return (
      <div
        aria-hidden
        className="pixel-grid h-full w-full"
        style={{
          borderRadius: RADIUS,
          // Two stops of one hue: a flat fill at this size reads as a missing
          // asset, and anything more than two reads as a chart. The scrim is
          // a second, flat layer on top — still opaque overall.
          background: [
            `linear-gradient(rgba(1, 4, 20, ${SCRIM}), rgba(1, 4, 20, ${SCRIM}))`,
            `linear-gradient(${c.angle}deg, ${c.from}, ${c.to})`,
          ].join(', '),
          // The same inset rim the cards wear at tile scale, so the corner is
          // part of the frame rather than a hole punched in it.
          boxShadow: `inset 0 0 0 4px ${alpha(NEO4J.lightPeriwinkle, 0.35)}`,
        }}
      />
    )
  }
}
