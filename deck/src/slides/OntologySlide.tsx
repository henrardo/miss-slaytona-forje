/**
 * The shape of memory: `CALL db.schema.visualization()`, rendered.
 *
 * Neo4j's own answer to "what is in here", not a diagram anybody drew. Labels
 * with their indexes and constraints, and the relationship types between them.
 * If the harness changes what it writes, this card changes with it — which is
 * the point of asking the database rather than maintaining a picture.
 *
 * Laid out radially rather than force-directed: an ontology has a dozen nodes
 * and does not move, so a deterministic ring is steadier to look at and never
 * settles differently between rehearsal and stage. The hub — whichever label
 * has the most relationships — goes in the middle.
 */
import { useMemo } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useGraphFeed } from '@/data/GraphFeed'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

const W = 1700
const H = 900

/** Labels the harness itself writes. Everything else is the workshop's. */
const OURS = new Set([
  'ReasoningTrace',
  'ReasoningStep',
  'ToolCall',
  'Tool',
  'Entity',
])

export function OntologySlide({ onStage }: SlideProps) {
  const { schema, labels, live, staleAgeMs } = useGraphFeed()

  const laid = useMemo(() => {
    if (!schema) return null
    const degree = new Map<string, number>()
    for (const r of schema.rels) {
      degree.set(r.from, (degree.get(r.from) ?? 0) + 1)
      degree.set(r.to, (degree.get(r.to) ?? 0) + 1)
    }
    const sorted = [...schema.nodes].sort(
      (a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0),
    )
    // The hub is the busiest label THE HARNESS WRITES, not the busiest label
    // outright — this database also holds a workshop's Message/Conversation
    // graph, and centring that would put the talk's subject on the rim.
    const hub = sorted.find((n) => OURS.has(n.label)) ?? sorted[0]
    const ring = sorted.filter((n) => n.id !== hub?.id)
    const pos = new Map<string, { x: number; y: number }>()
    if (hub) pos.set(hub.id, { x: W / 2, y: H / 2 })
    const rx = W * 0.4
    const ry = H * 0.38
    ring.forEach((n, i) => {
      const a = (i / Math.max(1, ring.length)) * Math.PI * 2 - Math.PI / 2
      pos.set(n.id, { x: W / 2 + Math.cos(a) * rx, y: H / 2 + Math.sin(a) * ry })
    })
    const count = new Map(labels.map((l) => [l.label, l.n]))
    return { pos, hub, nodes: schema.nodes, rels: schema.rels, count }
  }, [schema, labels])

  return (
    <SlideChrome
      title="The ontology of memory"
      accent={NEO4J.lightForest}
      badge={
        schema ? (
          `${schema.nodes.length} labels · ${schema.rels.length} types`
        ) : (
          <span style={{ color: ALARM }}>no schema</span>
        )
      }
      focused={onStage}
      footer={
        <span>
          CALL db.schema.visualization() · solid = written by this harness
          {live ? '' : ` · cached ${Math.round((staleAgeMs ?? 0) / 1000)}s ago`}
        </span>
      }
    >
      {!laid ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          asking the database for its own shape…
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-full w-full"
          role="img"
          aria-label="Graph schema"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={alpha(NEO4J.periwinkle, 0.7)} />
            </marker>
          </defs>

          {laid.rels.map((r) => {
            const a = laid.pos.get(r.from)
            const b = laid.pos.get(r.to)
            if (!a || !b) return null
            const mx = (a.x + b.x) / 2
            const my = (a.y + b.y) / 2
            return (
              <g key={r.id}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={alpha(NEO4J.periwinkle, 0.45)}
                  strokeWidth={3}
                  markerEnd="url(#arrow)"
                />
                <text
                  x={mx}
                  y={my - 8}
                  textAnchor="middle"
                  fontSize={24}
                  fill={alpha(NEO4J.cream, 0.7)}
                  fontFamily="'VT323', monospace"
                >
                  {r.type}
                </text>
              </g>
            )
          })}

          {laid.nodes.map((n) => {
            const p = laid.pos.get(n.id)
            if (!p) return null
            const ours = OURS.has(n.label)
            const n_ = laid.count.get(n.label) ?? 0
            // Size by population, floored so an empty label is still legible.
            const rad = 34 + Math.min(46, Math.sqrt(n_) * 1.6)
            return (
              <g key={n.id}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={rad}
                  fill={
                    ours
                      ? alpha(NEO4J.lightForest, 0.22)
                      : alpha(NEO4J.periwinkle, 0.08)
                  }
                  stroke={ours ? NEO4J.lightForest : alpha(NEO4J.periwinkle, 0.45)}
                  strokeWidth={ours ? 4 : 2}
                  strokeDasharray={ours ? undefined : '10 8'}
                />
                <text
                  x={p.x}
                  y={p.y + 6}
                  textAnchor="middle"
                  fontSize={30}
                  fill={ours ? NEO4J.cream : 'hsl(var(--muted-fg))'}
                  fontFamily="'Syne Neo', system-ui, sans-serif"
                  fontWeight={600}
                >
                  {n.label}
                </text>
                <text
                  x={p.x}
                  y={p.y + rad + 30}
                  textAnchor="middle"
                  fontSize={26}
                  fill="hsl(var(--muted-fg))"
                  fontFamily="'VT323', monospace"
                >
                  {n_ ? n_.toLocaleString('en-GB') : '—'}
                  {n.indexes.length ? ` · ${n.indexes.length} idx` : ''}
                </text>
              </g>
            )
          })}
        </svg>
      )}
    </SlideChrome>
  )
}
