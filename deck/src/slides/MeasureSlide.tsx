/**
 * One measure, warm against cold, for the whole run — drawn in one go.
 *
 * Three cards share this component, one per measure:
 *
 *   work_remaining   Pydantic v1 surfaces left in the package
 *   files_parsing    Files in the package that still compile
 *   closeness        Distance travelled from v1 to the merged PR
 *
 * They were one card with three small charts, which put three y-axes, three
 * caveats and six lines into a third of a card each. Separated, each measure
 * gets the whole board: two lines big enough to read from the back, the two
 * end values side by side as the head-to-head, and the reference lines the
 * harness supplied.
 *
 * ── The animation runs the whole run at once ─────────────────────────────
 *
 * ONE SWEEP, BOTH ARMS TOGETHER, 1.4 seconds. Not attempt-by-attempt on a
 * timer: the point of these cards is the SHAPE of the two paths against each
 * other, and a card that reveals a point every second makes the audience wait
 * eight seconds to see it. `stroke-dasharray` + `stroke-dashoffset` draws
 * each path from its own length, so both lines grow from attempt 1 to the end
 * in step and land together.
 *
 * ── The figures are the document's, not this card's ──────────────────────
 *
 * Points, axis labels, reference lines and the caveat all come from the panel
 * `orchestrator/series.py` emitted for the run. This card scales and draws;
 * it decides nothing. `y_starts_at_zero` is obeyed, every annotation is
 * drawn, and the caveat is rendered — the three rules in charts/Panel.tsx.
 */
import { useEffect, useMemo, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { SeriesPanel } from '@/lib/types'
import type { SlideProps } from './types'
import { pt } from '@/lib/type'

const W = 1500
const H = 620
const PAD = { l: 150, r: 220, t: 34, b: 86 }

/** One sweep for the whole run. */
const SWEEP_MS = 1400

interface Arm {
  arm: 'warm' | 'cold'
  label: string
  points: { x: number; y: number }[]
}

function armsOf(panel: SeriesPanel): Arm[] {
  return panel.series
    .map((s) => {
      const arm =
        (s.arm ?? '').toLowerCase() === 'warm' || /warm/.test(s.label)
          ? 'warm'
          : 'cold'
      return {
        arm: arm as 'warm' | 'cold',
        label: s.label,
        points: s.points
          .filter((p) => p.y != null && Number.isFinite(p.x))
          .map((p) => ({ x: p.x, y: p.y as number })),
      }
    })
    .filter((a) => a.points.length > 0)
}

/** Rounded upper bound, so the top gridline is a number worth reading. */
function niceCeil(v: number): number {
  if (v <= 0) return 1
  const mag = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / mag) * mag
}

const fmt = (v: number, decimals = 2) =>
  Math.abs(v) >= 100 || Number.isInteger(v)
    ? Math.round(v).toLocaleString('en-GB')
    : v.toFixed(decimals)

/**
 * WHICH POINT IS THE HEADLINE.
 *
 * `last` for work_remaining and files_parsing: both are states of the tree
 * the agent left behind, so where it ended up IS the result.
 *
 * `best` for closeness, and only for closeness, because there the last point
 * is an artefact. Closeness 0 means "identical to the untouched checkout", so
 * the scale is not monotone in effort: an arm can walk back toward 0 by
 * UNDOING its migration. Cold did exactly that — it sat near -1.5 for eight
 * attempts and reached -0.001 on attempt 9 by reverting, which as a last
 * point reads as cold finishing closer to the answer than warm. It is the
 * starting line, not progress. Warm was higher on all eight contested
 * attempts, and its best (+0.055, attempt 3) is the only figure that says so.
 *
 * The LINE is unchanged either way: cold's flat -1.5 and its late jump are
 * the shape that explains the number, and removing it would hide the thing
 * being warned about.
 */
type Pick = 'last' | 'best'

export interface MeasureSlideProps extends SlideProps {
  /** Panel id in the harness's chart document. */
  panelId: string
  title: string
  accent: string
  /** What the two end values mean, under the head-to-head figures. */
  endLabel: string
  /** True when a LOWER number is the better one. Drives nothing but a word. */
  lowerIsBetter?: boolean
  /** Which point becomes the head-to-head figure. See `Pick`. */
  pick?: Pick
  /** Decimals on the head-to-head figure. -0.001 must not print as -0.00. */
  decimals?: number
  /** Optional line under the figures, for a summary the last point hides. */
  note?: string
  /**
   * A word on one arm's LAST point, when that point needs explaining.
   *
   * Closeness needs it: cold's line rises to meet warm's on its final
   * attempt, and without a word there the chart says "cold caught up" while
   * the figures above say warm was closer. It did not catch up — it reverted.
   */
  lastNote?: Partial<Record<'warm' | 'cold', string>>
}

export function MeasureSlide({
  onStage,
  panelId,
  title,
  accent,
  endLabel,
  lowerIsBetter,
  pick = 'last',
  decimals = 2,
  note,
  lastNote,
}: MeasureSlideProps) {
  const { series, runId } = useRunFeed()
  const panel = (series?.panels ?? []).find((p) => p.id === panelId)
  const arms = useMemo(() => (panel ? armsOf(panel) : []), [panel])

  /** 0..1 of the sweep. One go, both arms. */
  const [grown, setGrown] = useState(1)
  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still || !arms.length) {
      setGrown(1)
      return
    }
    setGrown(0)
    // Two frames, not a timer per point: the transition does the work.
    const id = window.requestAnimationFrame(() =>
      window.requestAnimationFrame(() => setGrown(1)),
    )
    return () => window.cancelAnimationFrame(id)
  }, [onStage, arms.length, panelId])

  const geom = useMemo(() => {
    const ys = arms.flatMap((a) => a.points.map((p) => p.y))
    const anns = (panel?.annotations ?? []).filter((a) => a.y != null)
    // Reference lines are part of the DATA range, not decoration.
    const all = [...ys, ...anns.map((a) => a.y as number)]
    const xs = arms.flatMap((a) => a.points.map((p) => p.x))
    const zero = panel?.y_starts_at_zero === true
    const lo = Math.min(...all, zero ? 0 : Math.min(...all))
    const hi = Math.max(...all, 0)
    const top = hi > 0 ? niceCeil(hi) : 1
    const bottom = lo < 0 ? -niceCeil(-lo) : zero ? 0 : lo
    const xMin = Math.min(...xs, 1)
    const xMax = Math.max(...xs, xMin + 1)
    const px = (x: number) =>
      PAD.l + ((x - xMin) / (xMax - xMin)) * (W - PAD.l - PAD.r)
    const py = (y: number) =>
      PAD.t + (1 - (y - bottom) / (top - bottom || 1)) * (H - PAD.t - PAD.b)
    return { top, bottom, xMin, xMax, px, py, anns }
  }, [arms, panel])

  const warm = arms.find((a) => a.arm === 'warm')
  const cold = arms.find((a) => a.arm === 'cold')

  /** The headline point for an arm: its last, or its best. See `Pick`. */
  const figureOf = (a: Arm | undefined): { y: number; x: number } | null => {
    if (!a || !a.points.length) return null
    if (pick === 'best') {
      return a.points.reduce((b, p) => (p.y > b.y ? p : b), a.points[0])
    }
    return a.points[a.points.length - 1]
  }

  return (
    <SlideChrome
      title={title}
      accent={accent}
      badge={
        panel
          ? `${runId ?? 'this run'} · ${arms.reduce((n, a) => n + a.points.length, 0)} graded attempts`
          : 'awaiting the chart document'
      }
      focused={onStage}
      footer={
        <span>
          {panel?.caveat ??
            'from the chart document orchestrator/series.py wrote for this run'}
        </span>
      }
    >
      {!panel || !arms.length ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: pt(44), color: 'hsl(var(--muted-fg))' }}
        >
          this run's chart document has no {panelId} panel
        </div>
      ) : (
        <div className="flex h-full flex-col">
          {/* THE HEAD-TO-HEAD, where the two paths end up. */}
          <div className="flex shrink-0 items-end" style={{ gap: 40 }}>
            {(
              [
                ['WARM', figureOf(warm), ARM_COLOR.warm],
                ['COLD', figureOf(cold), ARM_COLOR.cold],
              ] as [string, { y: number; x: number } | null, string][]
            ).map(([label, at, c]) => (
              <div key={label} className="flex items-baseline" style={{ gap: 12 }}>
                <span
                  className="font-pixel"
                  style={{ fontSize: pt(28), color: c, letterSpacing: '0.14em' }}
                >
                  {label}
                </span>
                <span
                  className="heading-solid"
                  style={{
                    fontSize: pt(76),
                    color: c,
                    lineHeight: 1,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {at == null ? '—' : fmt(at.y, decimals)}
                </span>
                {/* WHICH attempt it was. On a best-of card the answer is the
                    point: warm's was attempt 3, cold's was its last. */}
                {at != null && pick === 'best' ? (
                  <span
                    className="font-pixel"
                    style={{ fontSize: pt(26), color: alpha(c, 0.8) }}
                  >
                    a{at.x}
                  </span>
                ) : null}
              </div>
            ))}
            <div className="min-w-0">
              <div
                className="font-pixel"
                style={{ fontSize: pt(25), color: 'hsl(var(--muted-fg))' }}
              >
                {endLabel}
                {lowerIsBetter ? ' · lower is better' : ''}
              </div>
              {note ? (
                <div
                  className="font-pixel"
                  style={{ fontSize: pt(24), color: alpha(NEO4J.cream, 0.85) }}
                >
                  {note}
                </div>
              ) : null}
            </div>
          </div>

          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="min-h-0 w-full flex-1"
            role="img"
            aria-label={`${panel.title}: warm against cold, per attempt`}
          >
            {/* Axes. */}
            <line
              x1={PAD.l}
              y1={geom.py(geom.bottom)}
              x2={W - PAD.r}
              y2={geom.py(geom.bottom)}
              stroke={alpha(NEO4J.lightPeriwinkle, 0.4)}
              strokeWidth={2}
            />
            {[geom.top, geom.bottom].map((v) => (
              <text
                key={v}
                x={PAD.l - 16}
                y={geom.py(v) + 10}
                textAnchor="end"
                style={{ fontSize: pt(26) }}
                fill="hsl(var(--muted-fg))"
                fontFamily="'VT323', monospace"
              >
                {fmt(v)}
              </text>
            ))}
            <text
              x={PAD.l}
              y={H - 28}
              style={{ fontSize: pt(26) }}
              fill="hsl(var(--muted-fg))"
              fontFamily="'VT323', monospace"
            >
              attempt {geom.xMin}
            </text>
            <text
              x={W - PAD.r}
              y={H - 28}
              textAnchor="end"
              style={{ fontSize: pt(26) }}
              fill="hsl(var(--muted-fg))"
              fontFamily="'VT323', monospace"
            >
              attempt {geom.xMax}
            </text>

            {/* RULE 2: every annotation is drawn. */}
            {geom.anns.map((a, i) => (
              <g key={`${a.label}-${i}`}>
                <line
                  x1={PAD.l}
                  y1={geom.py(a.y as number)}
                  x2={W - PAD.r}
                  y2={geom.py(a.y as number)}
                  stroke={alpha(NEO4J.marigold, 0.5)}
                  strokeWidth={2}
                  strokeDasharray="12 10"
                />
                <text
                  x={W - PAD.r - 8}
                  y={geom.py(a.y as number) - 12}
                  textAnchor="end"
                  style={{ fontSize: pt(24) }}
                  fill={alpha(NEO4J.marigold, 0.95)}
                  fontFamily="'VT323', monospace"
                >
                  {a.label}
                </text>
              </g>
            ))}

            {/* The two paths, swept together in one go. */}
            {arms.map((a) => {
              const last = a.points[a.points.length - 1]
              const best = a.points.reduce(
                (b, p) => (p.y > b.y ? p : b),
                a.points[0],
              )
              const d = a.points
                .map(
                  (p, i) =>
                    `${i === 0 ? 'M' : 'L'} ${geom.px(p.x)} ${geom.py(p.y)}`,
                )
                .join(' ')
              // Generous over-estimate of the path length: dasharray only
              // has to exceed it for the reveal to be complete.
              const len = (W + H) * a.points.length
              return (
                <g key={a.label}>
                  <path
                    d={d}
                    fill="none"
                    stroke={ARM_COLOR[a.arm]}
                    strokeWidth={6}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    style={{
                      strokeDasharray: len,
                      strokeDashoffset: grown ? 0 : len,
                      transition: `stroke-dashoffset ${SWEEP_MS}ms linear`,
                    }}
                  />
                  {a.points.map((p, i) => (
                    <circle
                      key={i}
                      cx={geom.px(p.x)}
                      cy={geom.py(p.y)}
                      r={8}
                      fill={ARM_COLOR[a.arm]}
                      style={{
                        opacity: grown,
                        transition: `opacity ${SWEEP_MS}ms linear ${(i / Math.max(a.points.length - 1, 1)) * SWEEP_MS * 0.5}ms`,
                      }}
                    />
                  ))}
                  {/* THE POINT THE HEADLINE CAME FROM, ringed on the line.
                      Without this the chart and the figures above it were
                      describing different things: the numbers said warm's
                      best beat cold's, and the lines ended level. */}
                  {pick === 'best' && best
                    ? (() => {
                        const bx = geom.px(best.x)
                        const by = geom.py(best.y)
                        return (
                          <g style={{ opacity: grown }}>
                            <circle
                              cx={bx}
                              cy={by}
                              r={20}
                              fill="none"
                              stroke={ARM_COLOR[a.arm]}
                              strokeWidth={4}
                            />
                            {best !== last ? (
                              <text
                                x={bx}
                                y={by - 32}
                                textAnchor="middle"
                                style={{ fontSize: pt(28) }}
                                fill={ARM_COLOR[a.arm]}
                                fontFamily="'VT323', monospace"
                              >
                                best {fmt(best.y, decimals)}
                              </text>
                            ) : null}
                          </g>
                        )
                      })()
                    : null}

                  {/* Why this arm's line ends where it does. */}
                  {lastNote?.[a.arm] && a.points.length > 1
                    ? (() => {
                        const prev = a.points[a.points.length - 2]
                        return (
                          <text
                            x={(geom.px(prev.x) + geom.px(last.x)) / 2 - 24}
                            y={(geom.py(prev.y) + geom.py(last.y)) / 2}
                            textAnchor="end"
                            style={{ fontSize: pt(26), opacity: grown }}
                            fill={ARM_COLOR[a.arm]}
                            fontFamily="'VT323', monospace"
                          >
                            ↑ {lastNote[a.arm]}
                          </text>
                        )
                      })()
                    : null}

                  {/* The arm's name at the end of its own line. */}
                  <text
                    x={geom.px(a.points[a.points.length - 1].x) + 16}
                    y={geom.py(a.points[a.points.length - 1].y) + 10}
                    style={{ fontSize: pt(28), opacity: grown }}
                    fill={ARM_COLOR[a.arm]}
                    fontFamily="'VT323', monospace"
                  >
                    {a.arm}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
      )}
    </SlideChrome>
  )
}

/** The three measures, as three cards. */
export const WorkRemainingSlide = (p: SlideProps) => (
  <MeasureSlide
    {...p}
    panelId="work_remaining"
    title="Surfaces left"
    accent={NEO4J.lightPeriwinkle}
    endLabel="v1 constructs still in the package, of 383"
    lowerIsBetter
  />
)

export const FilesParsingSlide = (p: SlideProps) => (
  <MeasureSlide
    {...p}
    panelId="files_parsing"
    title="Still compiles"
    accent={NEO4J.lightForest}
    endLabel="source files that still import, of 65"
  />
)

export const ClosenessSlide = (p: SlideProps) => (
  <MeasureSlide
    {...p}
    panelId="closeness"
    title="Distance to the answer"
    accent={NEO4J.lightBaltic}
    // BEST, not last — see `Pick`. Cold's last point is its revert.
    pick="best"
    decimals={3}
    endLabel="best distance travelled · 0 = untouched checkout, 1 = the merged PR"
    note="warm was higher on all eight contested attempts · mean across the run: warm −0.058, cold −1.322"
    // The two words that stop the lines contradicting the figures.
    lastNote={{ cold: 'reverted its migration — back to the start line' }}
  />
)
