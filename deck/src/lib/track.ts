/**
 * A closed lap around a rounded rectangle, parametrised 0..1.
 *
 * The racers ride this. Nothing else in the deck needs it, but it is here
 * rather than inside the component because it is pure geometry and it is the
 * part that has to be RIGHT: a token that drifts off the corner arcs looks
 * broken in a way no amount of styling hides.
 *
 * The lap starts at the BOTTOM CENTRE and runs rightwards along the bottom
 * edge, up the right side, leftwards across the top, down the left, back to the
 * start. Progress therefore begins as left-to-right motion, which is the one
 * direction an audience already reads as "further along".
 */

export interface Oval {
  x: number
  y: number
  w: number
  h: number
  /** Corner radius. Clamped to half the shorter side. */
  r: number
}

export interface Point {
  x: number
  y: number
}

type Segment = { len: number; at: (u: number) => Point }

const TAU = Math.PI * 2

/** Quarter arc, centre `c`, from angle `a0` to `a0 + sweep` (radians). */
function arc(c: Point, r: number, a0: number, sweep: number): Segment {
  return {
    len: Math.abs(sweep) * r,
    at: (u) => ({
      x: c.x + r * Math.cos(a0 + sweep * u),
      y: c.y + r * Math.sin(a0 + sweep * u),
    }),
  }
}

function line(a: Point, b: Point): Segment {
  return {
    len: Math.hypot(b.x - a.x, b.y - a.y),
    at: (u) => ({ x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u }),
  }
}

/**
 * The lap as an ordered list of segments, plus its total length.
 *
 * Angles are in SCREEN space, where y grows downward — so 0 is east, +90° is
 * south. Each corner sweeps a quarter turn anticlockwise on screen (negative
 * sweep) because the lap runs bottom -> right -> top -> left.
 */
export function lap(o: Oval): { segments: Segment[]; length: number } {
  const r = Math.max(0, Math.min(o.r, Math.min(o.w, o.h) / 2))
  const l = o.x
  const t = o.y
  const rt = o.x + o.w
  const b = o.y + o.h
  const cx = o.x + o.w / 2
  const q = TAU / 4

  const segments: Segment[] = [
    // bottom edge, start point to the bottom-right corner
    line({ x: cx, y: b }, { x: rt - r, y: b }),
    arc({ x: rt - r, y: b - r }, r, q, -q), // bottom-right
    line({ x: rt, y: b - r }, { x: rt, y: t + r }), // right edge, upward
    arc({ x: rt - r, y: t + r }, r, 0, -q), // top-right
    line({ x: rt - r, y: t }, { x: l + r, y: t }), // top edge, leftward
    arc({ x: l + r, y: t + r }, r, -q, -q), // top-left
    line({ x: l, y: t + r }, { x: l, y: b - r }), // left edge, downward
    arc({ x: l + r, y: b - r }, r, Math.PI, -q), // bottom-left
    // bottom edge again, corner back to the start point
    line({ x: l + r, y: b }, { x: cx, y: b }),
  ]
  return { segments, length: segments.reduce((n, s) => n + s.len, 0) }
}

/** The point at `t` (0..1, wrapped) around the lap. */
export function lapPoint(o: Oval, t: number): Point {
  const { segments, length } = lap(o)
  let d = (((t % 1) + 1) % 1) * length
  for (const s of segments) {
    if (d <= s.len || s === segments[segments.length - 1]) {
      return s.at(s.len > 0 ? Math.min(1, d / s.len) : 0)
    }
    d -= s.len
  }
  return { x: o.x, y: o.y }
}

/** `d` attribute for the same lap, for drawing the lane guide. */
export function lapPath(o: Oval): string {
  const r = Math.max(0, Math.min(o.r, Math.min(o.w, o.h) / 2))
  const { x, y, w, h } = o
  return [
    `M ${x + r} ${y}`,
    `H ${x + w - r}`,
    `A ${r} ${r} 0 0 1 ${x + w} ${y + r}`,
    `V ${y + h - r}`,
    `A ${r} ${r} 0 0 1 ${x + w - r} ${y + h}`,
    `H ${x + r}`,
    `A ${r} ${r} 0 0 1 ${x} ${y + h - r}`,
    `V ${y + r}`,
    `A ${r} ${r} 0 0 1 ${x + r} ${y}`,
    'Z',
  ].join(' ')
}

/** Grow (or shrink, with a negative value) an oval about its centre. */
export function expand(o: Oval, by: number): Oval {
  return {
    x: o.x - by,
    y: o.y - by,
    w: o.w + by * 2,
    h: o.h + by * 2,
    r: Math.max(0, o.r + by),
  }
}

if (import.meta.env.DEV) {
  // The lap must close, and the start point must be the bottom centre. Both
  // have been wrong in hand-rolled versions of this and neither is obvious
  // from looking at a moving token.
  const o: Oval = { x: 0, y: 0, w: 400, h: 200, r: 40 }
  const a = lapPoint(o, 0)
  const z = lapPoint(o, 1)
  const expected = 2 * (400 - 80) + 2 * (200 - 80) + TAU * 40
  const err = Math.abs(lap(o).length - expected)
  if (
    err > 0.001 ||
    Math.hypot(a.x - 200, a.y - 200) > 0.001 ||
    Math.hypot(a.x - z.x, a.y - z.y) > 0.001
  ) {
    console.error('[track] lap is wrong', { a, z, length: lap(o).length, expected })
  }
}
