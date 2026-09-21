/**
 * The frame every slide wears.
 *
 * Authored once at canonical WIDTH (1920) — a tile is this same markup under a
 * CSS scale, so the header that is legible on stage becomes a coloured sliver
 * in the ring, which is the intended read. Nothing here branches on `focused`
 * except detail that would be illegible at tile scale anyway.
 *
 * Height is whatever the Hud gives it. Header and footer are fixed; the body
 * flexes. That is what lets the stage fill a box that is not 16:9 without
 * letterboxing or distorting — see lib/layout.ts.
 */
import type { ReactNode } from 'react'
import { alpha } from '@/lib/brand'
import { pt, ptBox } from '@/lib/type'

/**
 * Corner radius, in canonical units — so it scales with everything else. At
 * 4K that is ~17px on the stage and ~4px on a tile: present, not decorative.
 * A radius fixed in screen pixels would look heavy-handed on a tile and
 * invisible on the stage, which is the usual way this goes wrong.
 */
const RADIUS = 14

/**
 * Edge treatment: a hard inset rim, then two outer halos — a tight one that
 * reads as the edge catching light, and a wide faint one that lifts the card
 * off the ground.
 *
 * THE HALOS ARE IN SCREEN PIXELS, not canonical units. Everything else here
 * scales with the card, which is right for anything that behaves like
 * content. A halo does not: it is a lighting effect, and light does not get
 * smaller because the thing it falls on is further away. Authored in canonical
 * units, a 44px halo landed as 13px on a tile and 115px on the stage — which
 * is exactly why the tiles looked bare and the stage looked faint.
 *
 * `--slide-scale` is set by the Hud on each wrapper; dividing by it cancels
 * the transform, so a value here is what you actually get on the glass.
 *
 * The rim stays in canonical units deliberately — it is a border, it belongs
 * to the card, and it should thin out as the card shrinks.
 *
 * Requires the Hud wrapper to use `contain: layout`, NOT `layout paint` —
 * paint containment clips a child's outer shadow to the border box and none
 * of this would be seen.
 */
const onGlass = (px: number) => `calc(${px}px / var(--slide-scale, 1))`

const GLOW_TILE = (a: string) =>
  [
    `inset 0 0 0 4px ${alpha(a, 0.63)}`,
    `0 0 ${onGlass(11)} ${alpha(a, 0.27)}`,
    `0 0 ${onGlass(34)} ${alpha(a, 0.18)}`,
  ].join(', ')

const GLOW_STAGE = (a: string) =>
  [
    `inset 0 0 0 6px ${a}`,
    `0 0 ${onGlass(26)} ${alpha(a, 0.35)}`,
    `0 0 ${onGlass(105)} ${alpha(a, 0.24)}`,
  ].join(', ')

export interface SlideChromeProps {
  title: string
  accent: string
  /** Short right-aligned label: brand, arm, or source. */
  badge?: ReactNode
  /**
   * The vendor's own mark, left of the title, for a card that IS a component
   * of the stack. A URL into `public/brand` or an imported glyph — provenance
   * for every asset is in `public/brand/SOURCES.md`. Sized off the type floor
   * so it keeps step with the heading at any card size.
   */
  mark?: string
  /** Status line along the bottom edge. */
  footer?: ReactNode
  focused: boolean
  /**
   * Drop the header bar. For a card whose content already IS its title — the
   * home card sets the name as artwork, and a second copy of it in VT323 above
   * only competed with it.
   *
   * A headerless card must then name ITSELF; `title` is still required because
   * the registry and the ghost sockets use it, but nothing here draws it. The
   * home card is named by the wordmark's own `role="img" aria-label`. Putting a
   * label on this element too would announce the name twice.
   */
  header?: boolean
  /** Optional: a card may legitimately be an empty shell while being built. */
  children?: ReactNode
}

export function SlideChrome({
  title,
  accent,
  badge,
  mark,
  footer,
  focused,
  header = true,
  children,
}: SlideChromeProps) {
  return (
    <div
      className="pixel-grid relative flex h-full w-full flex-col overflow-hidden"
      style={{
        background: 'hsl(var(--surface))',
        borderRadius: RADIUS,
        boxShadow: focused ? GLOW_STAGE(accent) : GLOW_TILE(accent),
      }}
    >
      {header ? (
        <header
          className="flex shrink-0 items-center justify-between px-10"
          style={{
            height: ptBox(96, 2.4),
            background: `linear-gradient(90deg, ${alpha(accent, 0.13)}, transparent 65%)`,
            borderBottom: `4px solid ${alpha(accent, 0.4)}`,
          }}
        >
          <div className="flex min-w-0 items-center" style={{ gap: 18 }}>
            {mark ? (
              <img
                src={mark}
                alt=""
                aria-hidden
                style={{ height: pt(52), width: 'auto', flexShrink: 0 }}
              />
            ) : null}
            <h2
              className="heading-solid truncate"
              style={{ fontSize: pt(52), letterSpacing: '0.04em', color: accent }}
            >
              {title}
            </h2>
          </div>
          {badge ? (
            <div
              className="font-pixel shrink-0 pl-8"
              style={{ fontSize: pt(40), color: 'hsl(var(--muted-fg))' }}
            >
              {badge}
            </div>
          ) : null}
        </header>
      ) : null}

      <div className="relative min-h-0 flex-1 overflow-hidden px-10 py-8">
        {children}
      </div>

      {footer ? (
        <footer
          className="font-pixel flex shrink-0 items-center gap-8 px-10 py-2"
          style={{
            // minHeight, not height. At 12pt a long footer wraps to two lines,
            // and a fixed box clipped the second one — "…are not counted" cut
            // in half along the bottom edge of the card. The body flexes, so
            // the footer taking a second line costs content, not legibility.
            minHeight: ptBox(72, 2.0),
            fontSize: pt(34),
            color: 'hsl(var(--muted-fg))',
            borderTop: `2px solid ${alpha(accent, 0.27)}`,
          }}
        >
          {footer}
        </footer>
      ) : null}
    </div>
  )
}

/* A `SlideCanvas` helper lived here, pinning slides to a fixed 1920x1080 box.
   It is gone: the Hud now sizes each wrapper to fill its rect exactly, and the
   stage's box is deliberately not 16:9 (see lib/layout.ts). A helper that
   re-imposed a fixed height would have silently reintroduced the letterbox the
   grid exists to remove. It was unused, which is the only reason this is a
   comment and not a migration. */
