/**
 * Renders one panel of the harness's chart document. Obeys it; decides nothing.
 *
 * Read `orchestrator/series.py` before touching this. That module emits a
 * self-describing document precisely so the chart decisions do not get retyped
 * here, and it names the failure it is guarding against:
 *
 *   "If that lives in matplotlib calls it gets retyped by hand into
 *    TypeScript, and the retyping is where 'the floor is 3, not 0' quietly
 *    becomes a y-axis starting at zero."
 *
 * So the three rules of this file:
 *
 *   1. `y_starts_at_zero` is the document's call, never this renderer's.
 *   2. Every `annotation` is drawn. A reference line that says "answer key =
 *      261" or "floor = 2 (a COMPLETED migration)" is the difference between a
 *      rising line and a rising line that never got there.
 *   3. The `caveat` is rendered with the panel, not hidden behind anything.
 *
 * Arm colour comes from the series' own `arm` field where the document supplies
 * one, so warm and cold are the same two colours here as everywhere else.
 */
import { useMemo } from 'react'
import { ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { PanelSeries, SeriesPanel } from '@/lib/types'
import { pt } from '@/lib/type'

/** Plot box inset, in canonical units. Room for tick labels and the axis. */
const PAD = { left: 130, right: 40, top: 20, bottom: 78 }

function colourOf(s: PanelSeries, i: number): string {
  const arm = (s.arm ?? '').toLowerCase()
  if (arm === 'warm' || /warm/.test(s.label)) return ARM_COLOR.warm
  if (arm === 'cold' || /cold/.test(s.label)) return ARM_COLOR.cold
  return [NEO4J.lightPeriwinkle, NEO4J.lightForest, NEO4J.marigold][i % 3]
}

/** Rounded "nice" upper bound, so the top gridline is a number worth reading. */
function niceCeil(v: number): number {
  if (v <= 0) return 1
  const mag = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / mag) * mag
}

export interface PanelChartProps {
  panel: SeriesPanel
  /** Canonical units. The card decides how much room the chart gets. */
  width: number
  height: number
}

export function PanelChart({ panel, width, height }: PanelChartProps) {
  const geom = useMemo(() => {
    const pts = panel.series.flatMap((s) =>
      s.points.filter((p) => p.y != null && Number.isFinite(p.x)),
    )
    const ann = panel.annotations ?? []

    // Reference lines are part of the DATA range, not decoration. A floor at 2
    // drawn outside the axis would be worse than not drawing it.
    const ys = [
      ...pts.map((p) => p.y as number),
      ...ann.filter((a) => a.y != null).map((a) => a.y as number),
    ]
    const xs = pts.map((p) => p.x)

    const yMaxRaw = ys.length ? Math.max(...ys) : 1
    const yMinRaw = ys.length ? Math.min(...ys) : 0
    // The document's call, not ours.
    const yMin = panel.y_starts_at_zero ? Math.min(0, yMinRaw) : yMinRaw
    const yMax = niceCeil(yMaxRaw === yMin ? yMin + 1 : yMaxRaw)

    const xMin = xs.length ? Math.min(...xs) : 0
    const xMax = xs.length ? Math.max(...xs) : 1
    const xSpan = xMax === xMin ? 1 : xMax - xMin

    const w = Math.max(1, width - PAD.left - PAD.right)
    const h = Math.max(1, height - PAD.top - PAD.bottom)
    const X = (x: number) => PAD.left + ((x - xMin) / xSpan) * w
    const Y = (y: number) => PAD.top + h - ((y - yMin) / (yMax - yMin || 1)) * h
    return { X, Y, yMin, yMax, xMin, xMax, w, h, empty: pts.length === 0 }
  }, [panel, width, height])

  const { X, Y, yMin, yMax, xMin, xMax, empty } = geom

  const path = (s: PanelSeries, stepped: boolean): string => {
    const p = s.points.filter((q) => q.y != null)
    if (!p.length) return ''
    let d = `M ${X(p[0].x)} ${Y(p[0].y as number)}`
    for (let i = 1; i < p.length; i++) {
      if (stepped) d += ` H ${X(p[i].x)}`
      d += ` ${stepped ? 'V' : 'L'} ${stepped ? Y(p[i].y as number) : `${X(p[i].x)} ${Y(p[i].y as number)}`}`
    }
    return d
  }

  const ticksY = [yMin, yMin + (yMax - yMin) / 2, yMax]
  /**
   * Enough decimals to tell the three ticks apart.
   *
   * `Math.round` printed a 0..1 axis as 0, 1, 1 — two identical labels at
   * different heights, which reads as a broken chart rather than as a
   * rounding choice. Only visible once the type was legible.
   */
  const dpY = Math.max(
    0,
    Math.min(3, Math.ceil(-Math.log10(Math.max(1e-9, (yMax - yMin) / 2))) + 1),
  )
  const labelY = (t: number) =>
    t.toLocaleString('en-GB', {
      minimumFractionDigits: dpY,
      maximumFractionDigits: dpY,
    })
  const ticksX =
    xMax - xMin <= 8
      ? Array.from({ length: Math.round(xMax - xMin) + 1 }, (_, i) => xMin + i)
      : [xMin, Math.round((xMin + xMax) / 2), xMax]

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={panel.title}
      style={{ display: 'block' }}
    >
      {/* grid + y ticks */}
      {ticksY.map((t) => (
        <g key={`y${t}`}>
          <line
            x1={PAD.left}
            x2={width - PAD.right}
            y1={Y(t)}
            y2={Y(t)}
            stroke={alpha(NEO4J.periwinkle, 0.16)}
            strokeWidth={2}
          />
          <text
            x={PAD.left - 16}
            y={Y(t) + 12}
            textAnchor="end"
            style={{ fontSize: pt(30) }}
            fill="hsl(var(--muted-fg))"
            fontFamily="'VT323', monospace"
          >
            {labelY(t)}
          </text>
        </g>
      ))}
      {ticksX.map((t) => (
        <text
          key={`x${t}`}
          x={X(t)}
          y={height - PAD.bottom + 40}
          textAnchor="middle"
          style={{ fontSize: pt(30) }}
          fill="hsl(var(--muted-fg))"
          fontFamily="'VT323', monospace"
        >
          {Math.round(t)}
        </text>
      ))}

      {/* Reference lines. Rule 2: all of them, labelled. */}
      {(panel.annotations ?? [])
        .filter((a) => a.y != null)
        .map((a, i) => (
          <g key={`ann${i}`}>
            <line
              x1={PAD.left}
              x2={width - PAD.right}
              y1={Y(a.y as number)}
              y2={Y(a.y as number)}
              stroke={alpha(NEO4J.marigold, 0.65)}
              strokeWidth={3}
              strokeDasharray="14 10"
            />
            {a.label ? (
              <text
                x={width - PAD.right}
                y={Y(a.y as number) - 12}
                textAnchor="end"
                style={{ fontSize: pt(28) }}
                fill={NEO4J.marigold}
                fontFamily="'VT323', monospace"
              >
                {a.label}
              </text>
            ) : null}
          </g>
        ))}

      {/* axes */}
      <line
        x1={PAD.left}
        x2={PAD.left}
        y1={PAD.top}
        y2={height - PAD.bottom}
        stroke={alpha(NEO4J.periwinkle, 0.5)}
        strokeWidth={2}
      />
      <line
        x1={PAD.left}
        x2={width - PAD.right}
        y1={height - PAD.bottom}
        y2={height - PAD.bottom}
        stroke={alpha(NEO4J.periwinkle, 0.5)}
        strokeWidth={2}
      />

      {panel.series.map((s, i) => {
        const c = colourOf(s, i)
        const pts = s.points.filter((p) => p.y != null)
        if (!pts.length) return null
        return (
          <g key={s.label}>
            {panel.kind !== 'scatter' ? (
              <path
                d={path(s, panel.kind === 'step')}
                fill="none"
                stroke={c}
                strokeWidth={5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : null}
            {pts.map((p, j) => (
              <circle
                key={j}
                cx={X(p.x)}
                cy={Y(p.y as number)}
                r={panel.kind === 'scatter' ? 9 : 7}
                fill={c}
              />
            ))}
          </g>
        )
      })}

      {empty ? (
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          style={{ fontSize: pt(40) }}
          fill="hsl(var(--muted-fg))"
          fontFamily="'VT323', monospace"
        >
          no graded attempts yet
        </text>
      ) : null}

      {/* axis labels */}
      <text
        x={PAD.left + (width - PAD.left - PAD.right) / 2}
        y={height - 10}
        textAnchor="middle"
        style={{ fontSize: pt(30) }}
        fill="hsl(var(--muted-fg))"
        fontFamily="'VT323', monospace"
      >
        {panel.x_label}
      </text>
      <text
        x={-(PAD.top + (height - PAD.top - PAD.bottom) / 2)}
        y={34}
        transform="rotate(-90)"
        textAnchor="middle"
        style={{ fontSize: pt(30) }}
        fill="hsl(var(--muted-fg))"
        fontFamily="'VT323', monospace"
      >
        {panel.y_label}
      </text>
    </svg>
  )
}

/** The legend, and the caveat. Rule 3: the caveat ships with the panel. */
export function PanelLegend({ panel }: { panel: SeriesPanel }) {
  return (
    <div
      className="font-pixel flex items-center gap-8"
      style={{ fontSize: pt(30) }}
    >
      {panel.series
        .filter((s) => s.points.some((p) => p.y != null))
        .map((s, i) => (
          <span key={s.label} className="flex items-center gap-3">
            <span
              style={{
                width: 26,
                height: 8,
                background: colourOf(s, i),
                display: 'inline-block',
              }}
            />
            <span style={{ color: colourOf(s, i) }}>{s.label}</span>
          </span>
        ))}
    </div>
  )
}
