import type { ComponentType } from 'react'
import type { Bias, Slot } from '@/lib/stage'

export interface SlideProps {
  /** True when this card is on the board rather than at its home in the ring. */
  onStage: boolean
  /**
   * Current render scale (1 = canonical). A card may use it to drop detail
   * that would be illegible at home — but it must not stop *collecting*,
   * because a card that pauses is a card that lies when it reaches the board.
   */
  scale: number
  /**
   * The footprint it was given, in squares, when on the board. Undefined at
   * home. A card that wants to be genuinely denser at 7x4 than at 14x8 keys
   * off this — scaling alone is not the same as showing less.
   */
  footprint?: Slot
}

export interface SlideDef {
  id: string
  title: string
  accent: string
  /**
   * Ranked preference over shape classes, most wanted first. The packer
   * chooses between arrangements to satisfy as much of this as it can, so a
   * terminal-ish card ranking `hor` first will be handed a wide slot whenever
   * one is going. See lib/stage.ts.
   */
  bias: Bias
  Component: ComponentType<SlideProps>
  /**
   * A block of colour holding a ring slot open. Not a card: it cannot be
   * staged, it is skipped by the walk and the digit keys, it leaves no ghost
   * and it is hidden from assistive tech.
   *
   * The ring is the perimeter of a 6x6 grid, so it seats twenty or it is not
   * a rectangle. When the deck has fewer than twenty things worth saying, the
   * choice is a ragged frame, filler cards nobody will look at, or this.
   * Corners are the right slots to give up: they are the two tiles furthest
   * from the eye's path along any edge, and the only ones that belong to two
   * edges at once.
   */
  decorative?: boolean
}
