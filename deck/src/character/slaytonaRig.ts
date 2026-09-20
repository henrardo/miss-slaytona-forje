/**
 * Miss Slaytona — the 8-bit character, vendored from the rig in
 * `miss-slaytona-sprite.html` / `slaytona.js`.
 *
 * No assets and no build step: the artwork is arrays of strings, one character
 * per pixel, through `PAL`. Poses are pure translations of three layers — body,
 * wand, and the graph she summons — so animating her costs three `blit`s.
 *
 * ── What changed on the way in, and why ──────────────────────────────────
 *
 * 1. The four Neo4j hexes are the REAL ones now. The rig shipped them marked
 *    `APPROXIMATE. Replace with the real hexes from Needle`, so this is the
 *    author's own instruction carried out: values come from `lib/brand.ts`,
 *    which is Neo4j's shipping product palette.
 *
 * 2. The rig's `createSlaytona()` owned a `requestAnimationFrame` loop and
 *    resized its own canvas. Both are React's job here, so what survives is
 *    the data and `drawFrame` — the exact same drawing, one frame at a time.
 *    Two lifecycles fighting over one canvas is the sort of thing that works
 *    until the card is re-laid out mid-talk.
 *
 * 3. `drawFrame` paints at ONE canvas pixel per sprite pixel. The rig scaled
 *    by reallocating a big canvas; here the backing store stays 34x48 and CSS
 *    does the magnifying under `image-rendering: pixelated`. See Slaytona.tsx —
 *    the card is already inside a CSS transform, so a canvas sized in canonical
 *    units would be rasterised at the wrong scale anyway.
 *
 * Costume, never decal — the author's note, worth keeping: the wig is connected
 * nodes with edges between them, the gown steps through warm bands from bodice
 * to hem, the wand is the router, and the platform heels are the sandbox she
 * executes from. The graph materialises on her FAR side, away from the wand:
 * a reveal she is presenting, not a beam she is firing.
 */
import { NEO4J } from '@/lib/brand'

export const PAL: Record<string, string | null> = {
  '.': null,
  K: '#14142B',
  B: '#4C8EDA',
  b: '#2F5B8F',
  C: '#8FE3F0',
  S: '#F5C9A6',
  s: '#D9A47F',
  L: '#FF5C8A',
  Y: '#FFD21E',
  A: '#FF9F1C',
  O: '#FF6B35',
  R: '#E63946',
  G: '#38D39F',
  g: '#1F9E75',
  D: '#3A4150',
  d: '#98A7BA',
  '*': '#F7C948',
  /* Neo4j brand. Real values, from lib/brand.ts — see the note at the top. */
  '1': NEO4J.midBaltic,
  '2': NEO4J.periwinkle,
  '3': NEO4J.marigold,
  H: NEO4J.yellowHl,
}

export const NAMES: Record<string, string> = {
  K: 'outline',
  B: 'wig',
  b: 'wig shade',
  C: 'node',
  S: 'skin',
  s: 'skin shade',
  L: 'lip',
  Y: 'bodice',
  A: 'waist',
  O: 'skirt',
  R: 'hem / sole',
  G: 'wand',
  g: 'wand shade',
  D: 'platform',
  d: 'platform edge',
  '*': 'star / sparkle',
  '1': 'Mid Baltic',
  '2': 'Periwinkle',
  '3': 'Marigold',
  H: 'Highlighter',
}

/* 24 wide x 44 tall. Head centred, body and hip carried left. */
export const BODY = [
  '.......KKKKKKKK.........',
  '.....KKBBBBBBBBKK.......',
  '....KBBBBBBBBBBBBK......',
  '...KBBCCBBBBBBCCBBK.....',
  '...KBBCCBBBBBBCCBBBK....',
  '..KBBBCBBBBBCBBBBBBK....',
  '..KBBBBCBBBCBBBBBBBBK...',
  '..KBBBBBCCBBBBBBBBBBK...',
  '..KBBBBBCCBBBBBBBBBBK...',
  '..KBBBBBBBBBBBBBBBBBK...',
  '...KBBBBBBBBBBBBBBBK....',
  '...KBBBKSSSSSSSSKBBBK...',
  '...KBBBKSKKSSKKSKBBBK...',
  '...KBBBKSSSSSSSSKBBBK...',
  '...KBBBKSKKSSKKSKBBBK...',
  '...KBBBKSSKSSKSSKBBBK...',
  '...KBBBKSSSSSSSSKBBBK...',
  '....KBBKSSSLLSSSKBBK....',
  '.....KKKsSSSSSSsKKK.....',
  '..........KSSK..........',
  '.....KYYYYYYYYYYK...KSSK',
  '.KSSKKYYYYYYYYYYKSSSSSSK',
  '.KSSK.KYYYYYYYYK........',
  '.KSSK..KYYYYYYK.........',
  '..KSSK..KAAAAK..........',
  '...KSSK.KAAAAK..........',
  '....KSSKAAAAAAK.........',
  '......KAAAAAAAAK........',
  '.....KOOOOOOOOOOK.......',
  '....KOOOOOOOOOOOOK......',
  '...KOOOOOOOOOOOOOOK.....',
  '..KOOOOOOOOOOOOOOOOK....',
  '..KOOOOOOOOOOOOOOOOK....',
  '.KRRRRRRRRRRRRRRRRRRK...',
  '.KRRRRRRRRRRRRRRRRRRK...',
  'KRRRRRRRRRRRRRRRRRRRRK..',
  'KRRRRRRRRRRRRRRRRRRRRK..',
  'KRRRRRRRRRRRRRRRRRRRRRK.',
  'KRRRRRRRRRRRRRRRRRRRRRK.',
  '.KKKKKKKKKKKKKKKKKKKKK..',
  '.......KDDKKDDK.........',
  '......KDDDKDDDK.........',
  '......KRRRKRRRK.........',
  '.......KRK.KRK..........',
]

export const WAND = [
  '.*...',
  '*C*..',
  '.*...',
  '.G...',
  '.G...',
  '.G...',
  '.G...',
  '.G...',
  '.G...',
  '.G...',
  '.g...',
  '.g...',
]

export const GRAPH = [
  '........',
  '.11...22',
  '.11HHH22',
  '..H...H.',
  '...H.H..',
  '...HH...',
  '...33...',
  '...33...',
]

/* Canvas is 34 x 48 so the summoned graph has clear space on her far side. */
export const W = 34
export const H = 48
const BASE = 1
const BODY_X = 8
const WAND_X = 29
const WAND_Y = 9
const GRAPH_X = 0
const GRAPH_Y = 22

/** Where the sparkles land when a frame sets `flash`. */
const FLASH_AT: [number, number][] = [
  [32, 8],
  [31, 13],
  [2, 12],
  [5, 7],
  [33, 19],
  [1, 17],
]

export interface Frame {
  bodyDX?: number
  bodyDY?: number
  wandDX?: number
  wandDY?: number
  graphDY?: number
  graph?: boolean
  wink?: boolean
  flash?: boolean
}

/* Default: still, smouldering, weight settled. One pixel of breath. */
export const IDLE: Frame[] = [
  { bodyDY: 0, wandDY: 0 },
  { bodyDY: 0, wandDY: 0 },
  { bodyDY: 1, wandDY: -1 },
  { bodyDY: 0, wandDY: 0 },
]

export interface Pose {
  label: string
  frames: Frame[]
}

export const POSES: Record<string, Pose> = {
  summon: {
    // the memory-hit pose
    label: 'Summon graph',
    frames: [
      { bodyDY: 0, wandDY: -1 },
      { bodyDY: -1, wandDY: -3, wandDX: 1, flash: true },
      { bodyDY: 0, wandDY: -1, graph: true, graphDY: 1, flash: true },
      { bodyDY: 0, wandDY: 0, graph: true },
      { bodyDY: 1, wandDY: 0, graph: true },
      { bodyDY: 0, wandDY: 0, graph: true },
    ],
  },
  wink: {
    label: 'Wink',
    frames: [
      { bodyDY: 0, wandDY: 0, wink: true },
      { bodyDY: 0, bodyDX: 1, wandDY: -1, wink: true },
      { bodyDY: 1, wandDY: 0 },
    ],
  },
  sashay: {
    label: 'Sashay',
    frames: [
      { bodyDX: -1, bodyDY: 0, wandDX: 1, wandDY: 0 },
      { bodyDX: 0, bodyDY: 1, wandDX: 0, wandDY: -1 },
      { bodyDX: 1, bodyDY: 0, wandDX: -1, wandDY: 0 },
      { bodyDX: 0, bodyDY: 1, wandDX: 0, wandDY: -1 },
    ],
  },
  point: {
    // wand snaps down and levels off
    label: 'Point',
    frames: [
      { bodyDY: 0, wandDY: -2 },
      { bodyDY: 0, wandDY: 3, wandDX: 1, flash: true },
      { bodyDY: 1, wandDY: 3, wandDX: 1 },
      { bodyDY: 0, wandDY: 1 },
    ],
  },
  dip: {
    label: 'Dip',
    frames: [
      { bodyDY: 1, wandDY: -3, wandDX: -1 },
      { bodyDY: 3, wandDY: 2, wandDX: -2, flash: true },
      { bodyDY: 3, wandDY: 3, wandDX: -2, flash: true },
      { bodyDY: 1, wandDY: -1, wandDX: -1 },
    ],
  },
  flip: {
    label: 'Hair flip',
    frames: [
      { bodyDX: 0, bodyDY: 0, wandDY: -2 },
      { bodyDX: -2, bodyDY: -1, wandDY: -4, flash: true },
      { bodyDX: 1, bodyDY: 0, wandDY: -2 },
      { bodyDX: 0, bodyDY: 1, wandDY: 0 },
    ],
  },
}

export type PoseName = keyof typeof POSES

/** How long one frame is held. The rig's value; her timing is her character. */
export const FRAME_MS = 340

function blit(
  ctx: CanvasRenderingContext2D,
  grid: string[],
  ox: number,
  oy: number,
) {
  for (let y = 0; y < grid.length; y++) {
    const row = grid[y]
    for (let x = 0; x < row.length; x++) {
      const col = PAL[row[x]]
      if (!col) continue
      ctx.fillStyle = col
      ctx.fillRect(ox + x, oy + y, 1, 1)
    }
  }
}

/** One frame, at one canvas pixel per sprite pixel. */
export function drawFrame(ctx: CanvasRenderingContext2D, f: Frame) {
  ctx.clearRect(0, 0, W, H)
  const bx = BODY_X + (f.bodyDX ?? 0)
  const by = BASE + (f.bodyDY ?? 0)
  blit(
    ctx,
    WAND,
    WAND_X + (f.bodyDX ?? 0) + (f.wandDX ?? 0),
    by + WAND_Y - BASE + (f.wandDY ?? 0),
  )
  blit(ctx, BODY, bx, by)
  if (f.wink) {
    // close the left eye into a lash line
    ctx.fillStyle = PAL.K as string
    ctx.fillRect(bx + 9, by + 15, 3, 1)
  }
  if (f.graph) blit(ctx, GRAPH, GRAPH_X, GRAPH_Y + (f.graphDY ?? 0))
  if (f.flash) {
    ctx.fillStyle = PAL['*'] as string
    for (const [x, y] of FLASH_AT) ctx.fillRect(x, y, 1, 1)
  }
}

if (import.meta.env.DEV) {
  // Ragged rows blit skewed and the cause is invisible in the result.
  for (const [name, grid] of Object.entries({ BODY, WAND, GRAPH })) {
    const w = grid[0]?.length ?? 0
    const bad = grid.findIndex((r) => r.length !== w)
    if (bad >= 0) {
      console.error(
        `[slaytona] ${name} row ${bad} is ${grid[bad].length} wide, expected ${w}`,
      )
    }
  }
}
