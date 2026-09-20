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
}
