/**
 * The container.
 *
 * Sits in the hole in the ring, behind everything on stage, and never moves.
 * It is not a slide: it has no entry in the registry, it cannot be swapped or
 * sent home, and it holds no run data. Its whole job is to be the surface
 * cards are placed onto, and to make the square grid they are placed against
 * visible rather than notional.
 *
 * Cards on stage are laid out inside `stageInner` — one gutter in from this
 * frame — so the container reads as a frame rather than being covered by the
 * first card that lands on it.
 */
import type { HudLayout } from '@/lib/layout'
import { NEO4J, alpha } from '@/lib/brand'

/** Exported so the racetrack's lanes can follow the same corners. */
export const STAGE_RADIUS = 18
const RADIUS = STAGE_RADIUS

export function StageContainer({ layout }: { layout: HudLayout }) {
  const { stage, stageInner, grid } = layout
  const accent = NEO4J.periwinkle

  return (
    <div
      className="pointer-events-none absolute"
      style={{
        left: stage.x,
        top: stage.y,
        width: stage.w,
        height: stage.h,
        zIndex: 5,
        borderRadius: RADIUS,
        background: 'hsl(var(--bg) / 0.55)',
        boxShadow: [
          `inset 0 0 0 2px ${alpha(accent, 0.22)}`,
          `0 0 26px ${alpha(accent, 0.12)}`,
        ].join(', '),
      }}
    >
      {/* The square lattice. Faint — it is a substrate, not a chart. */}
      <div
        className="absolute"
        style={{
          left: stageInner.x - stage.x,
          top: stageInner.y - stage.y,
          width: stageInner.w,
          height: stageInner.h,
          backgroundImage: [
            `linear-gradient(${alpha(accent, 0.1)} 1px, transparent 1px)`,
            `linear-gradient(90deg, ${alpha(accent, 0.1)} 1px, transparent 1px)`,
          ].join(', '),
          backgroundSize: `${grid.cell.w}px ${grid.cell.h}px`,
        }}
      />
    </div>
  )
}
