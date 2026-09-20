/**
 * How the stack is actually wired — and which part is moving right now.
 *
 * Not a vendor logo wall. Every box is a process or a service that exists, the
 * arrows are the real dependencies between them, and a box lights when the
 * harness emits the event that means it just did something.
 *
 * Two things the diagram is careful about, because they are the two things a
 * logo wall gets wrong:
 *
 *   THE ARMS ARE NOT SYMMETRIC. Warm and cold share one SGLang server and one
 *   Daytona account; only warm reaches Neo4j, only warm runs a hook, only warm
 *   distils. Drawing four vendors in a row implies all four serve both arms.
 *
 *   THE ORCHESTRATOR IS LOCAL. It runs on the laptop and reaches the pod over
 *   ssh. That is why `runs/*.log` is tailable at all, and it is the reason the
 *   deck can be live without anything being deployed.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, BRANDS, NEO4J, alpha } from '@/lib/brand'
import { isLit, useActivity, type Trigger } from './SourceSparkle'
import type { SlideProps } from './types'

const W = 1780
const H = 900

interface Box {
  id: string
  x: number
  y: number
  w: number
  h: number
  title: string
  sub: string
  colour: string
  trigger?: Trigger
  /** Warm-only parts are drawn in the warm colour and labelled. */
  warmOnly?: boolean
}

const BOXES: Box[] = [
  {
    id: 'orch',
    x: 40,
    y: 360,
    w: 300,
    h: 170,
    title: 'orchestrator',
    sub: 'this laptop · run.py',
    colour: NEO4J.cream,
  },
  {
    id: 'warm',
    x: 430,
    y: 150,
    w: 300,
    h: 150,
    title: 'warm swarm',
    sub: 'Vibe + hooks.toml',
    colour: ARM_COLOR.warm,
    trigger: 'tool_call',
    warmOnly: true,
  },
  {
    id: 'cold',
    x: 430,
    y: 600,
    w: 300,
    h: 150,
    title: 'cold swarm',
    sub: 'Vibe, no hooks',
    colour: ARM_COLOR.cold,
    trigger: 'model_call',
  },
  {
    id: 'sglang',
    x: 830,
    y: 375,
    w: 320,
    h: 150,
    title: 'SGLang',
    sub: 'RunPod H200 · one server, both arms',
    colour: BRANDS.sglang.accent,
    trigger: 'model_call',
  },
  {
    id: 'daytona',
    x: 1260,
    y: 600,
    w: 300,
    h: 150,
    title: 'Daytona',
    sub: 'one sandbox per attempt',
    colour: BRANDS.daytona.accent,
    trigger: 'sandbox',
  },
  {
    id: 'neo4j',
    x: 1260,
    y: 150,
    w: 300,
    h: 150,
    title: 'Neo4j Aura',
    sub: 'reasoning graph',
    colour: BRANDS.neo4j.accent,
    trigger: 'step_write',
    warmOnly: true,
  },
  {
    id: 'skill',
    x: 830,
    y: 90,
    w: 300,
    h: 120,
    title: 'AIP skill',
    sub: 'distilled from the graph',
    colour: NEO4J.marigold,
    trigger: 'distil',
    warmOnly: true,
  },
]

interface Arrow {
  from: string
  to: string
  label: string
  warmOnly?: boolean
}

const ARROWS: Arrow[] = [
  { from: 'orch', to: 'warm', label: 'ssh' },
  { from: 'orch', to: 'cold', label: 'ssh' },
  { from: 'warm', to: 'sglang', label: 'chat/completions' },
  { from: 'cold', to: 'sglang', label: 'chat/completions' },
  { from: 'warm', to: 'neo4j', label: 'steps', warmOnly: true },
  { from: 'neo4j', to: 'skill', label: 'distil', warmOnly: true },
  { from: 'skill', to: 'warm', label: 'loaded next attempt', warmOnly: true },
  { from: 'orch', to: 'daytona', label: 'grade' },
]

const centre = (b: Box) => ({ x: b.x + b.w / 2, y: b.y + b.h / 2 })

export function StackSlide({ onStage }: SlideProps) {
  const activity = useActivity()
  const { metrics } = useRunFeed()
  const byId = Object.fromEntries(BOXES.map((b) => [b.id, b]))

  return (
    <SlideChrome
      title="The stack"
      accent={BRANDS.daytona.accent}
      badge={
        <span
          style={{
            color:
              activity.resolution === 'idle' ? 'hsl(var(--muted))' : NEO4J.marigold,
          }}
        >
          {activity.resolution}
        </span>
      }
      focused={onStage}
      footer={
        // Short: this card takes narrow slots and the rail is one line.
        <span>
          dashed = warm only · one SGLang server, both arms
          {metrics?.gpu ? ` · ${metrics.gpu}` : ''}
        </span>
      }
    >
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-full w-full"
        role="img"
        aria-label="Stack"
      >
        {ARROWS.map((a, i) => {
          const s = centre(byId[a.from])
          const e = centre(byId[a.to])
          const lit =
            byId[a.to].trigger && isLit(activity, byId[a.to].trigger as Trigger)
          return (
            <g key={i}>
              <line
                x1={s.x}
                y1={s.y}
                x2={e.x}
                y2={e.y}
                stroke={lit ? NEO4J.marigold : alpha(NEO4J.periwinkle, 0.35)}
                strokeWidth={lit ? 5 : 3}
                strokeDasharray={a.warmOnly ? '14 10' : undefined}
                style={{ transition: 'stroke 300ms, stroke-width 300ms' }}
              />
              <text
                x={(s.x + e.x) / 2}
                y={(s.y + e.y) / 2 - 10}
                textAnchor="middle"
                fontSize={24}
                fill={alpha(NEO4J.cream, 0.62)}
                fontFamily="'VT323', monospace"
              >
                {a.label}
              </text>
            </g>
          )
        })}

        {BOXES.map((b) => {
          const lit = b.trigger ? isLit(activity, b.trigger) : false
          return (
            <g key={b.id}>
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={14}
                fill={alpha(b.colour, lit ? 0.22 : 0.08)}
                stroke={lit ? NEO4J.marigold : b.colour}
                strokeWidth={lit ? 5 : 3}
                strokeDasharray={b.warmOnly ? '16 10' : undefined}
                style={{ transition: 'fill 300ms, stroke 300ms' }}
              />
              <text
                x={b.x + b.w / 2}
                y={b.y + b.h / 2 - 6}
                textAnchor="middle"
                fontSize={38}
                fill={b.colour}
                fontFamily="'Syne Neo', system-ui, sans-serif"
                fontWeight={600}
              >
                {b.title}
              </text>
              <text
                x={b.x + b.w / 2}
                y={b.y + b.h / 2 + 34}
                textAnchor="middle"
                fontSize={24}
                fill="hsl(var(--muted-fg))"
                fontFamily="'VT323', monospace"
              >
                {b.sub}
              </text>
            </g>
          )
        })}

        {/* The one asymmetry worth stating on the face of the diagram. */}
        <text
          x={W - 20}
          y={H - 14}
          textAnchor="end"
          fontSize={24}
          fill={alpha(ALARM, 0.8)}
          fontFamily="'VT323', monospace"
        >
          cold reaches neither Neo4j nor the skill — that IS the treatment
        </text>
      </svg>
    </SlideChrome>
  )
}
