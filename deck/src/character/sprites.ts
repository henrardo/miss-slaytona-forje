/**
 * Sprite artwork for slot placeholders.
 *
 * Miss Slaytona herself is NOT here. She arrived as an animated three-layer
 * rig rather than a single still, so she lives in `slaytonaRig.ts` (grids,
 * palette, poses) and `Slaytona.tsx` (canvas + the run feed). This file and
 * `Sprite.tsx` remain for static, one-layer artwork — currently just the
 * reserved-slot noise below.
 */
import type { SpriteData } from './Sprite'

/**
 * Placeholder for an empty slot. Deliberately abstract noise rather than a
 * character — it marks a slot as reserved without pre-empting what goes in it.
 * Deterministic so it does not flicker when the ring re-lays out.
 */
export function noiseSprite(seed: number, colour: string): SpriteData {
  const rows: string[] = []
  for (let y = 0; y < 8; y++) {
    let row = ''
    for (let x = 0; x < 8; x++) {
      const v = Math.sin(seed * 12.9898 + (y * 8 + x) * 78.233) * 43758.5453
      const f = v - Math.floor(v)
      row += f > 0.78 ? 'a' : f > 0.62 ? 'b' : '.'
    }
    rows.push(row)
  }
  return { rows, palette: { a: colour, b: `${colour}66` } }
}
