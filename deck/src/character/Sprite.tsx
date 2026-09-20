/**
 * 8-bit sprite renderer.
 *
 * A sprite is a list of equal-length strings, one character per pixel, plus a
 * palette mapping character -> colour. `.` is always transparent. This is the
 * standard way pixel art is authored by hand, and it means the artwork is a
 * diffable text file rather than a binary someone has to open an editor for.
 *
 * Rendered as one absolutely-positioned box-shadow chain on a single element:
 * a 32x32 sprite is 1024 pixels, and 1024 DOM nodes inside a tile that is
 * already one of twenty scaled 1920x1080 subtrees is exactly the kind of thing
 * that put the compositor over budget in the first place. One node, one paint.
 */
import { useMemo } from 'react'

export interface SpriteData {
  /** One string per row, all the same length. `.` = transparent. */
  rows: string[]
  /** Character -> CSS colour. Characters absent from the map are skipped. */
  palette: Record<string, string>
}

export interface SpriteProps {
  sprite: SpriteData
  /** Size of one sprite pixel, in canonical slide units. */
  pixel?: number
  className?: string
  style?: React.CSSProperties
}

/** Width/height of a sprite in pixels, and a check that it is rectangular. */
export function spriteSize(sprite: SpriteData): { w: number; h: number } {
  const h = sprite.rows.length
  const w = h ? sprite.rows[0].length : 0
  if (import.meta.env.DEV) {
    const ragged = sprite.rows.findIndex((r) => r.length !== w)
    if (ragged >= 0) {
      // Loud in dev, silent in the talk. A ragged sprite renders skewed and
      // the cause is invisible if you only see the result.
      console.warn(
        `[Sprite] row ${ragged} is ${sprite.rows[ragged].length} wide, expected ${w}`,
      )
    }
  }
  return { w, h }
}

export function Sprite({ sprite, pixel = 8, className, style }: SpriteProps) {
  const { w, h } = spriteSize(sprite)

  const shadow = useMemo(() => {
    const parts: string[] = []
    sprite.rows.forEach((row, y) => {
      for (let x = 0; x < row.length; x++) {
        const colour = sprite.palette[row[x]]
        if (!colour) continue
        parts.push(`${x * pixel}px ${y * pixel}px 0 0 ${colour}`)
      }
    })
    return parts.join(', ')
  }, [sprite, pixel])

  return (
    <div
      className={className}
      style={{
        width: w * pixel,
        height: h * pixel,
        position: 'relative',
        ...style,
      }}
      aria-hidden
    >
      {/* The single painted pixel; every other pixel is one of its shadows. */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: pixel,
          height: pixel,
          boxShadow: shadow,
        }}
      />
    </div>
  )
}
