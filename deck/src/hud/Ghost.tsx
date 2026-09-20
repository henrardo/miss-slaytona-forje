/**
 * The mark a card leaves at home while it is on the board.
 *
 * Joining would otherwise punch a hole in the ring, which is the one thing the
 * ring geometry was built to avoid. A ghost keeps the frame reading as
 * complete, says plainly where the card went, and is itself the recall
 * control — clicking it sends the card home, same as clicking the card.
 *
 * Deliberately not a shrunken copy of the card: a faint duplicate of live
 * content in two places at once is the kind of thing an audience reads as a
 * bug. It is an empty socket with a name on it.
 */
import { alpha } from '@/lib/brand'
import type { Rect } from '@/lib/layout'

export function Ghost({
  rect,
  title,
  accent,
  onClick,
}: {
  rect: Rect
  title: string
  accent: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${title} — on the board, click to send home`}
      className="absolute cursor-pointer outline-none"
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
        zIndex: 8,
        borderRadius: Math.round(rect.w * 0.008),
        background: alpha(accent, 0.04),
        border: `1px dashed ${alpha(accent, 0.38)}`,
      }}
    >
      <span
        className="font-pixel block truncate px-[0.6em]"
        style={{
          fontSize: Math.max(9, Math.round(rect.h * 0.11)),
          color: alpha(accent, 0.75),
          letterSpacing: '0.06em',
        }}
      >
        {title}
      </span>
      <span
        className="font-pixel block px-[0.8em] pt-[0.3em]"
        style={{
          fontSize: Math.max(8, Math.round(rect.h * 0.075)),
          color: 'hsl(var(--muted-fg) / 0.7)',
        }}
      >
        on the board
      </span>
    </button>
  )
}
