/**
 * The flow-chart engine both arm cards are drawn with.
 *
 * Cold and warm are the same stack with a memory layer bolted onto one of
 * them, and the cards must LOOK like that — same box size, same lattice, same
 * connector weight, same badges. Two hand-maintained copies would not stay
 * that way for a week, so the geometry, the elbow router, the glyphs and the
 * prompt document live here and each card supplies only its own nodes, edges
 * and prompt.
 *
 * ── The rules the diagrams follow ───────────────────────────────────────
 *
 * ONE GRID. Every node is the same box on a three-column lattice. Uniform
 * boxes on a lattice is most of what makes a diagram read as a diagram rather
 * than as a pile of labels.
 *
 * ORTHOGONAL CONNECTORS. Every arrow runs horizontally or vertically, with a
 * rounded elbow where it turns, and meets a box edge at a right angle. The
 * first version of the cold card drew straight lines between box CENTRES,
 * which produced long diagonals, arrows out of the middle of boxes, and
 * labels on top of other labels.
 *
 * ONE VISUAL WEIGHT. Every box has the same fill and the same border; the
 * only colour is the node's own name. Seven differently-coloured boxes is a
 * vendor wall, and a vendor wall is what these cards are not.
 *
 * THE STRUCTURE IS PERIWINKLE ON BOTH CARDS. Boxes, connectors and badges do
 * not take the card's accent. The accent says which ARM you are looking at —
 * blue for cold, gold for warm — and if the wiring took it too, the two cards
 * would look like two different systems instead of one system twice. It also
 * keeps the lit state legible: marigold means "this just happened" deck-wide,
 * and it can only mean that if the unlit stroke is never gold.
 */
import type { ReactNode } from 'react'
import { NEO4J, alpha } from '@/lib/brand'
import { isLit, type Activity, type Trigger } from './SourceSparkle'
import { pt } from '@/lib/type'
import { FitText } from '@/hud/FitText'

/**
 * One box, and the rows it sits on. Taller than a label needs, to carry a
 * mark above the name: mark-on-the-left leaves a 240-unit text column, and at
 * the 12pt floor "Mistral Small 4" alone is 280 units wide.
 */
export const BOX = { w: 344, h: 170 }
export const ROW = [60, 370, 680] // top edges
/** The mark's box, centred at the top of a node. */
export const MARK = 48

/** Opaque, and a shade off the card so the boxes sit ON it. */
export const FILL = '#221f3e'
export const EDGE = alpha(NEO4J.periwinkle, 0.45)
export const LINE = alpha(NEO4J.periwinkle, 0.6)

/** What a card hands its nodes so their sub-lines can read the live run. */
export interface Live {
  gpu: string | null
  model: string | null
  fixture: string | null
  attempts: number
  passed: number | null
}

export interface FlowNode {
  id: string
  col: number
  row: number
  title: string
  /** One line under the title. A function so it can read the live run. */
  sub: (m: Live) => string
  /** The name's colour. The box itself is the same as every other box. */
  ink: string
  /**
   * The vendor's own mark, from `public/brand` (provenance in SOURCES.md) or
   * from the wordmark's extracted glyphs. Omitted where there IS no asset:
   * neither RunPod nor Cognee ships one here, and the three parts that are
   * not products — the checkout, its output, the suite — are not anyone's
   * brand. Those get `glyph` instead.
   */
  logo?: string
  glyph?: GlyphKind
  trigger?: Trigger
}

export interface FlowEdge {
  /** The badge text. Short: it sits in a 19-unit disc. */
  n: string
  /** Every turn is a right angle; two points is a straight run. */
  points: [number, number][]
  /** Where the number badge sits on the path. */
  badge: [number, number]
  /** Arrowheads at both ends — for a link that is genuinely two-way. */
  both?: boolean
  /** Dashed, for a part of the stack only one arm has. */
  dashed?: boolean
}

export interface Geom {
  /** viewBox width and height. */
  W: number
  H: number
  /** Column left edges. */
  COL: number[]
}

export const cx = (g: Geom, c: number) => g.COL[c] + BOX.w / 2
export const cy = (r: number) => ROW[r] + BOX.h / 2

/**
 * An orthogonal path with rounded corners.
 *
 * Each interior point is cut back by `r` along both of its segments and
 * replaced with a quadratic through the corner — which is what every diagram
 * tool draws and what a straight-line polyline conspicuously does not.
 */
export function elbow(points: [number, number][], r = 16): string {
  if (points.length < 2) return ''
  const [start] = points
  let d = `M ${start[0]} ${start[1]}`
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1]
    const [x, y] = points[i]
    const [nx, ny] = points[i + 1]
    const inLen = Math.hypot(x - px, y - py)
    const outLen = Math.hypot(nx - x, ny - y)
    const ri = Math.min(r, inLen / 2, outLen / 2)
    const a: [number, number] = [
      x - ((x - px) / (inLen || 1)) * ri,
      y - ((y - py) / (inLen || 1)) * ri,
    ]
    const b: [number, number] = [
      x + ((nx - x) / (outLen || 1)) * ri,
      y + ((ny - y) / (outLen || 1)) * ri,
    ]
    d += ` L ${a[0]} ${a[1]} Q ${x} ${y} ${b[0]} ${b[1]}`
  }
  const end = points[points.length - 1]
  return `${d} L ${end[0]} ${end[1]}`
}

export type GlyphKind = 'chip' | 'folder' | 'diff' | 'graph'

/**
 * Marks for the nodes that have no vendor asset.
 *
 * Drawn rather than sourced, deliberately: a checkout, an edited tree and a
 * test suite are not anyone's brand, and reaching for a lookalike logo would
 * be the one thing a stack diagram must not do. RunPod and Cognee ship no
 * asset in this repo, so they get a drawn mark too rather than a stand-in.
 * Each is a 48-unit square, stroked in the node's own ink.
 */
export function Glyph({
  kind,
  x,
  y,
  ink,
}: {
  kind: GlyphKind
  x: number
  y: number
  ink: string
}) {
  const s = MARK
  const stroke = alpha(ink, 0.85)
  const common = {
    fill: 'none',
    stroke,
    strokeWidth: 2.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
  if (kind === 'chip') {
    // A package with pins: the machine the rest of this runs on.
    return (
      <g transform={`translate(${x} ${y})`}>
        <rect
          x={s * 0.2}
          y={s * 0.2}
          width={s * 0.6}
          height={s * 0.6}
          rx={4}
          {...common}
        />
        <rect
          x={s * 0.36}
          y={s * 0.36}
          width={s * 0.28}
          height={s * 0.28}
          rx={2}
          {...common}
        />
        {[0.34, 0.5, 0.66].map((f) => (
          <g key={f}>
            <line x1={s * f} y1={s * 0.06} x2={s * f} y2={s * 0.2} {...common} />
            <line x1={s * f} y1={s * 0.8} x2={s * f} y2={s * 0.94} {...common} />
            <line x1={s * 0.06} y1={s * f} x2={s * 0.2} y2={s * f} {...common} />
            <line x1={s * 0.8} y1={s * f} x2={s * 0.94} y2={s * f} {...common} />
          </g>
        ))}
      </g>
    )
  }
  if (kind === 'folder') {
    return (
      <g transform={`translate(${x} ${y})`}>
        <path
          d={`M ${s * 0.1} ${s * 0.78} V ${s * 0.26} H ${s * 0.42} L ${s * 0.52} ${s * 0.38} H ${s * 0.9} V ${s * 0.78} Z`}
          {...common}
        />
        <line x1={s * 0.1} y1={s * 0.5} x2={s * 0.9} y2={s * 0.5} {...common} />
      </g>
    )
  }
  if (kind === 'graph') {
    // Four nodes and the edges between them: what Cognee builds out of the
    // traces. Not Neo4j's mark — Cognee writes INTO that, and the node next
    // to this one wears the real one.
    const n: [number, number][] = [
      [s * 0.22, s * 0.26],
      [s * 0.78, s * 0.2],
      [s * 0.5, s * 0.54],
      [s * 0.3, s * 0.82],
      [s * 0.8, s * 0.74],
    ]
    const link: [number, number][] = [
      [0, 2],
      [1, 2],
      [2, 3],
      [2, 4],
    ]
    return (
      <g transform={`translate(${x} ${y})`}>
        {link.map(([a, b], i) => (
          <line
            key={i}
            x1={n[a][0]}
            y1={n[a][1]}
            x2={n[b][0]}
            y2={n[b][1]}
            {...common}
            strokeWidth={2}
          />
        ))}
        {n.map(([px, py], i) => (
          <circle
            key={i}
            cx={px}
            cy={py}
            r={i === 2 ? s * 0.11 : s * 0.08}
            {...common}
            fill={FILL}
          />
        ))}
      </g>
    )
  }
  // A page with a diff down it: what the agent hands back.
  return (
    <g transform={`translate(${x} ${y})`}>
      <path
        d={`M ${s * 0.18} ${s * 0.86} V ${s * 0.14} H ${s * 0.62} L ${s * 0.82} ${s * 0.34} V ${s * 0.86} Z`}
        {...common}
      />
      <path
        d={`M ${s * 0.62} ${s * 0.14} V ${s * 0.34} H ${s * 0.82}`}
        {...common}
      />
      <line x1={s * 0.3} y1={s * 0.52} x2={s * 0.58} y2={s * 0.52} {...common} />
      <line x1={s * 0.44} y1={s * 0.38} x2={s * 0.44} y2={s * 0.66} {...common} />
      <line x1={s * 0.3} y1={s * 0.72} x2={s * 0.7} y2={s * 0.72} {...common} />
    </g>
  )
}

export interface FlowChartProps {
  /** Unique per card: SVG marker ids are document-global. */
  id: string
  geom: Geom
  nodes: FlowNode[]
  edges: FlowEdge[]
  live: Live
  activity: Activity
  /** For the accessible name — "Cold, end to end". */
  label: string
}

export function FlowChart({
  id,
  geom,
  nodes,
  edges,
  live,
  activity,
  label,
}: FlowChartProps) {
  const head = `${id}-head`
  const tail = `${id}-tail`
  return (
    <svg
      viewBox={`0 0 ${geom.W} ${geom.H}`}
      className="h-full"
      style={{ flex: '1 1 0', minWidth: 0 }}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={label}
    >
      <defs>
        <marker
          id={head}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={LINE} />
        </marker>
        {/* A second marker for the tail of a two-way link. `auto-start-reverse`
            turns it round, so the geometry is the same. */}
        <marker
          id={tail}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={LINE} />
        </marker>
      </defs>

      {edges.map((e) => (
        <path
          key={e.n}
          d={elbow(e.points)}
          fill="none"
          stroke={LINE}
          strokeWidth={2.5}
          strokeDasharray={e.dashed ? '12 8' : undefined}
          markerEnd={`url(#${head})`}
          markerStart={e.both ? `url(#${tail})` : undefined}
        />
      ))}

      {nodes.map((n) => {
        const lit = n.trigger ? isLit(activity, n.trigger) : false
        const x = geom.COL[n.col]
        const y = ROW[n.row]
        return (
          <g key={n.id}>
            <rect
              x={x}
              y={y}
              width={BOX.w}
              height={BOX.h}
              rx={10}
              fill={FILL}
              stroke={lit ? NEO4J.marigold : EDGE}
              strokeWidth={lit ? 3.5 : 2}
              style={{ transition: 'stroke 300ms, stroke-width 300ms' }}
            />
            {n.logo ? (
              <image
                href={n.logo}
                x={x + BOX.w / 2 - MARK / 2}
                y={y + 18}
                width={MARK}
                height={MARK}
                preserveAspectRatio="xMidYMid meet"
              />
            ) : n.glyph ? (
              <Glyph
                kind={n.glyph}
                x={x + BOX.w / 2 - MARK / 2}
                y={y + 18}
                ink={n.ink}
              />
            ) : null}
            <FitText
              maxWidth={BOX.w - 32}
              x={x + BOX.w / 2}
              y={y + 108}
              textAnchor="middle"
              style={{ fontSize: pt(34) }}
              fill={n.ink}
              fontFamily="'Syne Neo', system-ui, sans-serif"
              fontWeight={600}
            >
              {n.title}
            </FitText>
            <FitText
              maxWidth={BOX.w - 32}
              x={x + BOX.w / 2}
              y={y + 144}
              textAnchor="middle"
              style={{ fontSize: pt(22) }}
              fill="hsl(var(--muted-fg))"
              fontFamily="'VT323', monospace"
            >
              {n.sub(live)}
            </FitText>
          </g>
        )
      })}

      {/* The step numbers, on the line: the path runs behind an opaque disc,
          which is how a connector label reads as belonging to its arrow. */}
      {edges.map((e) => (
        <g key={`b${e.n}`}>
          <circle
            cx={e.badge[0]}
            cy={e.badge[1]}
            r={19}
            fill={FILL}
            stroke={EDGE}
            strokeWidth={1.5}
          />
          <text
            x={e.badge[0]}
            y={e.badge[1] + 8}
            textAnchor="middle"
            style={{ fontSize: pt(22) }}
            fill={alpha(NEO4J.cream, 0.7)}
            fontFamily="'VT323', monospace"
          >
            {e.n}
          </text>
        </g>
      ))}
    </svg>
  )
}

export interface PromptAsideProps {
  /** Which arm's prompt this is — the label in the document's header. */
  arm: string
  head: string
  steps: string[]
  /** Which step numbers only this arm gets, highlighted in the list. */
  only?: number[]
  /** Anything after the numbered list — warm's closing note. */
  children?: ReactNode
}

/**
 * The prompt, as a document beside the flow.
 *
 * HTML, not SVG text: SVG has no line breaking, so the hand-wrapped version
 * overflowed its box the moment the 12pt floor made the type bigger than the
 * widths it had been wrapped for. This wraps itself, and what does not fit is
 * clipped — the trade this deck makes everywhere else.
 */
export function PromptAside({
  arm,
  head,
  steps,
  only = [],
  children,
}: PromptAsideProps) {
  return (
    <aside
      className="flex flex-col"
      style={{
        width: '31%',
        flexShrink: 0,
        background: FILL,
        border: `2px solid ${EDGE}`,
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      <div
        className="font-pixel flex items-baseline justify-between"
        style={{
          padding: '14px 26px',
          borderBottom: `2px solid ${EDGE}`,
          fontSize: pt(26),
          color: alpha(NEO4J.cream, 0.75),
        }}
      >
        <span>the prompt</span>
        <span style={{ fontSize: pt(22), color: 'hsl(var(--muted))' }}>{arm}</span>
      </div>
      <div
        className="font-pixel min-h-0 flex-1"
        style={{ padding: '14px 24px', fontSize: pt(22), lineHeight: 1.28 }}
      >
        <p style={{ color: NEO4J.cream, marginBottom: 10 }}>{head}</p>
        <ol style={{ color: 'hsl(var(--muted-fg))' }}>
          {steps.map((line, i) => {
            // The steps one arm has and the other does not are the treatment,
            // so they are marked rather than left to be spotted by diffing
            // two cards from the back of a room.
            const extra = only.includes(i + 1)
            return (
              <li key={i} style={{ display: 'flex', gap: 10, marginBottom: 2 }}>
                <span
                  style={{ color: extra ? NEO4J.marigold : 'hsl(var(--muted))' }}
                >
                  {i + 1}.
                </span>
                <span style={extra ? { color: NEO4J.marigold } : undefined}>
                  {line}
                </span>
              </li>
            )
          })}
        </ol>
        {children}
      </div>
    </aside>
  )
}
