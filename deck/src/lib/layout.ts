/**
 * HUD geometry.
 *
 * The ring is the PERIMETER OF A GRID. `cols x rows` cells, one uniform gutter
 * `g` everywhere, tiles on the edge cells and the stage filling the hole. That
 * is what makes the four distances the eye actually checks — top row's lower
 * edge, bottom row's upper edge, right column's left edge, left column's right
 * edge — all exactly `g` from the stage, and it makes the rows and columns
 * align at the corners by construction rather than by tuning.
 *
 * Twenty tiles is exactly a 6x6 perimeter: 2*6 + 2*6 - 4 = 20.
 *
 * ── Why the canvas is not a fixed 16:9 ───────────────────────────────────
 *
 * A cell is 16:9, so the hole is (4*tw + 3g) x (4*th + 3g), and that is NOT
 * 16:9 — the gutters add equally in both axes while the cells add in 16:9
 * proportion. Solving `stage.w == A * stage.h` over every ring shape that
 * seats 20 tiles yields a negative tile size in every case; at cols == rows it
 * demands g == 0. The three properties "stage exactly 16:9", "one uniform
 * gutter" and "aligned grid" are not simultaneously satisfiable.
 *
 * Letterboxing a 16:9 slide inside the hole costs `1.5g(1 - 1/A)` of slack top
 * and bottom, i.e. vertical gaps 1.66x the horizontal ones — and that ratio is
 * independent of g, so a smaller gutter does not dilute it.
 *
 * So the slide canvas is fixed in WIDTH and adapts in height: every slide is
 * authored 1920 wide and fills whatever box it is given. Type stays in
 * canonical width units, so a heading is the same size on every slide; only
 * the body's breathing room changes, by under 3% between tile and stage. The
 * chrome is flexbox and absorbs it without being asked.
 */

/** Authoring width. Height adapts to the box — see the note above. */
export const CANONICAL = { w: 1920, h: 1080 } as const
export const ASPECT = CANONICAL.w / CANONICAL.h

export const MAX_TILES = 20

/**
 * One card per ring slot, and every card keeps that slot for the whole talk.
 *
 * This used to be MAX_TILES + 1, because swapping needed a spare body to fill
 * the hole the stage occupant left. Joining does not: a card on the board
 * leaves a GHOST at its own home, so the ring still looks complete and homes
 * never drift. The drift that swapping forced — "the tokens tile moves around
 * as you navigate" — is simply gone, and the number keys now address a card
 * as well as a position, because those are the same thing again.
 */
export const DECK_SIZE = MAX_TILES

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

/**
 * The stage's own square grid, in columns. Cards joining the stage are sized
 * in these squares — the square is the atom the whole stage model is built on.
 *
 * Fourteen, measured rather than picked. Rows are DERIVED (below) so the cells
 * stay square whatever the hole's proportions turn out to be, and across
 * 3840x2160, 2560x1440, 1920x1200 and 3440x1440 the error from true square is:
 *
 *   10 cols -> 5.4%    12 -> 2.7%    14 -> 0.7%    16 -> 1.0%    18 -> 2.3%
 *
 * 14 x 8 also divides cleanly for the arrangements that actually get used:
 * halves are 7x8, quadrants 7x4, a big-plus-two is 7x8 and two 7x4. 16x9 is
 * nearly as square but quarters to 8x4.5, which is not a thing.
 */
export const STAGE_COLS = 14

/**
 * And fourteen columns means EIGHT rows. Not derived — fixed.
 *
 * This used to be computed as `round(stageInner.h / cellW)`, to keep the cells
 * square whatever the hole's proportions turned out to be, with `stage.ts`
 * separately hard-coding 8 to match. Two sources for one number, agreeing by
 * luck: every arrangement in `ARRANGEMENTS` tiles 14x8 exactly, so the moment
 * the derivation rounds to 7 or 9 the packer is laying out against a grid that
 * does not exist. Arming the race made it round to 7, and cards rendered 618px
 * tall inside a 571px container — overflowing it and painting over the
 * racetrack, because cards sit above the track.
 *
 * The arrangements cannot bend, so squareness does. `assertSquarish` below
 * says so out loud when the cells drift.
 */
export const STAGE_ROWS = 8

export interface SquareGrid {
  cols: number
  rows: number
  cell: { w: number; h: number }
}

export interface HudLayout {
  /** The container: the whole hole in the ring, minus `stageInset`. */
  stage: Rect
  /**
   * The hole itself, before `stageInset`. Equal to `stage` unless the race is
   * on, in which case the difference IS the racetrack's band.
   */
  stageOuter: Rect
  /** Inside the container's own padding — where cards actually get placed. */
  stageInner: Rect
  /** The square lattice cards are sized and packed against. */
  grid: SquareGrid
  tiles: Rect[]
  /** The uniform gutter. Every stage-to-band distance equals this. */
  gutter: number
  cols: number
  rows: number
}

/**
 * The ring shape that seats `n` tiles on a grid perimeter.
 *
 * Cells are 16:9, so the hole comes closest to 16:9 when cols == rows: a
 * 7x5 ring, for instance, leaves a hole five cells wide and three tall, which
 * is nearly 3:1 and useless for a slide.
 */
export function ringShape(n: number): { cols: number; rows: number } {
  const half = Math.round(n / 2) + 2 // cols + rows
  const rows = Math.max(3, Math.round(half / 2))
  const cols = Math.max(3, half - rows)
  return { cols, rows }
}

export function computeHudLayout(
  viewportW: number,
  viewportH: number,
  n: number,
  /**
   * Pull the stage in from the hole on all four sides, leaving a band around
   * it. The ring does not move — the stage gives the space up, the tiles do
   * not — so the four equidistance properties above still hold, measured to
   * the hole rather than to the stage. Used by the racetrack.
   */
  stageInset = 0,
): HudLayout {
  const pad = Math.round(viewportH * 0.018)
  const gutter = Math.max(8, Math.round(viewportH * 0.014))

  const innerX = pad
  const innerY = pad
  const innerW = Math.max(1, viewportW - pad * 2)
  const innerH = Math.max(1, viewportH - pad * 2)

  const { cols, rows } = ringShape(Math.max(8, Math.min(n, MAX_TILES)))

  // One tile size, from whichever axis binds. Mixed tile sizes read as a bug.
  const tileH = Math.max(
    24,
    Math.floor(
      Math.min(
        (innerW - (cols - 1) * gutter) / (cols * ASPECT),
        (innerH - (rows - 1) * gutter) / rows,
      ),
    ),
  )
  const tileW = Math.round(tileH * ASPECT)

  const outerW = cols * tileW + (cols - 1) * gutter
  const outerH = rows * tileH + (rows - 1) * gutter
  // The ring keeps its proportions and centres; the slack goes outside it.
  const originX = Math.round(innerX + (innerW - outerW) / 2)
  const originY = Math.round(innerY + (innerH - outerH) / 2)

  const cell = (c: number, r: number): Rect => ({
    x: originX + c * (tileW + gutter),
    y: originY + r * (tileH + gutter),
    w: tileW,
    h: tileH,
  })

  // Fill order: top row left to right, then bottom row, then the right column
  // top to bottom, then the left column. Corner cells belong to the rows.
  const tiles: Rect[] = []
  for (let c = 0; c < cols; c++) tiles.push(cell(c, 0))
  for (let c = 0; c < cols; c++) tiles.push(cell(c, rows - 1))
  for (let r = 1; r < rows - 1; r++) tiles.push(cell(cols - 1, r))
  for (let r = 1; r < rows - 1; r++) tiles.push(cell(0, r))

  // The hole: every cell not on the perimeter, plus the gutters between them.
  const stageOuter: Rect = {
    x: cell(1, 1).x,
    y: cell(1, 1).y,
    w: (cols - 2) * tileW + (cols - 3) * gutter,
    h: (rows - 2) * tileH + (rows - 3) * gutter,
  }

  // Never let the band eat more than a third of the hole, whatever it is told.
  const inset = Math.max(
    0,
    Math.min(stageInset, Math.min(stageOuter.w, stageOuter.h) / 3),
  )
  const stage: Rect = {
    x: stageOuter.x + inset,
    y: stageOuter.y + inset,
    w: Math.max(1, stageOuter.w - inset * 2),
    h: Math.max(1, stageOuter.h - inset * 2),
  }

  // The container keeps one gutter of padding, so its frame reads as a frame
  // and cards on stage sit inside it rather than covering it.
  const stageInner: Rect = {
    x: stage.x + gutter,
    y: stage.y + gutter,
    w: Math.max(1, stage.w - gutter * 2),
    h: Math.max(1, stage.h - gutter * 2),
  }

  // 14 x 8, always. See STAGE_ROWS for why this is not derived.
  const grid: SquareGrid = {
    cols: STAGE_COLS,
    rows: STAGE_ROWS,
    cell: {
      w: stageInner.w / STAGE_COLS,
      h: stageInner.h / STAGE_ROWS,
    },
  }
  if (import.meta.env.DEV) {
    const off = Math.abs(grid.cell.w / grid.cell.h - 1)
    if (off > 0.15) {
      console.warn(
        `[layout] stage cells are ${(off * 100).toFixed(0)}% off square ` +
          `(${grid.cell.w.toFixed(1)} x ${grid.cell.h.toFixed(1)}). The grid is ` +
          `fixed at ${STAGE_COLS}x${STAGE_ROWS} because the arrangements are; ` +
          `if this is large, the ring shape or the race band wants adjusting.`,
      )
    }
  }

  return { stage, stageOuter, stageInner, grid, tiles, gutter, cols, rows }
}

/** The rect covering a footprint of squares at a grid position. */
export function gridRect(
  layout: HudLayout,
  col: number,
  row: number,
  w: number,
  h: number,
): Rect {
  const { stageInner, grid } = layout
  return {
    x: stageInner.x + col * grid.cell.w,
    y: stageInner.y + row * grid.cell.h,
    w: w * grid.cell.w,
    h: h * grid.cell.h,
  }
}

/**
 * The scale a card renders at: normalised by AREA, not by width.
 *
 * Width-normalisation (`rect.w / CANONICAL.w`) is fine while every box is
 * 16:9, and wrong the moment they are not. A 5x8 slot on the board is 426px
 * wide and 848 tall; normalised by width it got a 1920x3819 canvas and set
 * 52-unit type at 11px on screen — unreadable, in a slot with plenty of room.
 *
 * Area-normalisation keeps type size tied to how much room the card actually
 * has. The same slot now renders that type at ~22px. Tiles and the full board
 * are unchanged to within a pixel, because they are already 16:9-ish — this
 * only rescues the shapes that were broken.
 */
export function unitFor(rect: Rect): number {
  const u = Math.sqrt((rect.w * rect.h) / (CANONICAL.w * CANONICAL.h))
  return u > 0 ? u : 1
}

/** The canvas a card is laid out on so that, scaled by `unitFor`, it fills `rect`. */
export function canvasFor(rect: Rect): { w: number; h: number } {
  const u = unitFor(rect)
  return {
    w: Math.max(1, Math.round(rect.w / u)),
    h: Math.max(1, Math.round(rect.h / u)),
  }
}

export const scaleFor = unitFor
