/**
 * The improvement curve: the harness's own chart document, rendered.
 *
 * Nothing here computes a series. `orchestrator/series.py` produces the panels
 * — axes, reference lines, whether y may start at zero, and a caveat per panel
 * — and the collector serves them, deriving them from the event log for runs
 * that never wrote a `-series.json` (every rehearsal). See charts/Panel.tsx.
 *
 * The default panel is `convergence`, and its own caveat is the reason this
 * card exists in the shape it does: *"Monotone by construction — the harness
 * restores the best tree after a regression. A flat line means no attempt beat
 * the first, not that nothing happened."* A rising line here is not obviously
 * good news, and the card says so on its face rather than in the notes.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { PanelChart, PanelLegend } from '@/charts/Panel'
import { useRunFeed } from '@/data/RunFeed'
import { NEO4J, alpha } from '@/lib/brand'
import type { SeriesPanel } from '@/lib/types'
import type { SlideProps } from './types'

/** Preference order. The first one present is shown. */
const PREFERRED = ['convergence', 'work_remaining', 'attempt_score']

export function CurveSlide({ onStage }: SlideProps) {
  const { series } = useRunFeed()
  const panels = series?.panels ?? []
  const [chosen, setChosen] = useState<string | null>(null)

  const panel = useMemo(() => {
    if (!panels.length) return null
    if (chosen) return panels.find((p) => p.id === chosen) ?? panels[0]
    for (const id of PREFERRED) {
      const p = panels.find((q) => q.id === id)
      if (p) return p
    }
    return panels[0]
  }, [panels, chosen])

  return (
    <SlideChrome
      title={panel?.title ?? 'Improvement curve'}
      accent={NEO4J.lightBaltic}
      badge={series ? `${panels.length} panels` : 'no series'}
      focused={onStage}
      footer={
        <span>
          orchestrator/series.py · {series?.scope ?? '—'}
          {series?.fixture ? ` · ${series.fixture}` : ''}
        </span>
      }
    >
      {!panel ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          the chart document arrives with the first graded attempt
        </div>
      ) : (
        <div className="flex h-full flex-col" style={{ gap: 14 }}>
          <div className="flex items-start justify-between" style={{ gap: 24 }}>
            <PanelLegend panel={panel} />
            {/* Panel picker. Small: the default is the right one for the talk,
                and this is for answering a question from the floor. */}
            <div className="flex flex-wrap justify-end gap-2">
              {panels.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setChosen(p.id)
                  }}
                  className="font-pixel px-3"
                  style={{
                    fontSize: 24,
                    lineHeight: 1.6,
                    color: p.id === panel.id ? '#12102a' : 'hsl(var(--muted-fg))',
                    background:
                      p.id === panel.id
                        ? NEO4J.lightPeriwinkle
                        : alpha(NEO4J.periwinkle, 0.12),
                    border: `1px solid ${alpha(NEO4J.periwinkle, 0.4)}`,
                    borderRadius: 6,
                    cursor: 'pointer',
                    pointerEvents: onStage ? 'auto' : 'none',
                  }}
                >
                  {p.id}
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <FillChart panel={panel} />
          </div>

          {/* Rule 3 from charts/Panel.tsx: the caveat ships with the panel. */}
          {panel.caveat ? (
            <div
              className="font-pixel shrink-0"
              style={{
                fontSize: 28,
                lineHeight: 1.35,
                color: NEO4J.marigold,
                borderTop: `1px solid ${alpha(NEO4J.marigold, 0.35)}`,
                paddingTop: 10,
              }}
            >
              {panel.caveat}
            </div>
          ) : null}
        </div>
      )}
    </SlideChrome>
  )
}

/**
 * The chart is authored in canonical units, so it needs its box in those same
 * units — `clientWidth` is pre-transform, which is exactly what is wanted. A
 * ResizeObserver rather than a measuring ref: the card is re-laid-out whenever
 * it joins or leaves the board, and a ref callback only fires on mount.
 */
function FillChart({ panel }: { panel: SeriesPanel }) {
  const host = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState({ w: 0, h: 0 })

  useLayoutEffect(() => {
    const el = host.current
    if (!el) return
    const measure = () => {
      const w = el.clientWidth
      const h = el.clientHeight
      setBox((b) => (b.w === w && b.h === h ? b : { w, h }))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <div ref={host} className="h-full w-full">
      {box.w > 0 && box.h > 0 ? (
        <PanelChart panel={panel} width={box.w} height={box.h} />
      ) : null}
    </div>
  )
}
