/**
 * The raw event tail. The least interpreted view there is: what the harness
 * wrote, in order, arm-coloured. Everything else in the deck is derived from
 * this, so it stays here as the thing to fall back to when a derived number
 * looks wrong.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ARM_COLOR, NEO4J } from '@/lib/brand'
import type { RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

/** Events that say something happened, versus bookkeeping. */
const LOUD = new Set([
  'ATTEMPT_DONE',
  'ATTEMPT_REJECTED',
  'ATTEMPT_ABORTED',
  'MEMORY_WRITE',
  'MEMORY_READ',
  'DISTILLED',
  'FILE_DONE',
  'RUN_END',
])

function summarise(e: RunEvent): string {
  switch (e.type) {
    case 'ATTEMPT_START':
      return `attempt ${e.attempt}${e.skill_version != null ? ` · skill v${e.skill_version}` : ''}`
    case 'ATTEMPT_DONE':
      return `attempt ${e.attempt} → ${e.tests_passed ?? '?'} passed · ${e.turns_used ?? '?'} turns`
    case 'SANDBOX_CREATED':
      return `oracle up in ${e.create_ms ?? '?'}ms`
    case 'MEMORY_READ':
      return `read · ${e.hits ?? 0} hit(s)${e.sources?.length ? ` from ${e.sources.join(', ')}` : ''}`
    case 'MEMORY_WRITE':
      return `wrote · ${e.error_kind ?? ''}`
    case 'INGESTED':
      return `ingested ${e.steps ?? 0} step(s)`
    case 'DISTILLED':
      return `distilled → skill v${e.skill_version ?? '?'}`
    case 'FILE_DONE':
      return e.success ? `converged after ${e.attempts} attempt(s)` : 'gave up'
    default:
      return ''
  }
}

export function FeedSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  // Newest at the top: on stage the eye should not have to hunt for the
  // bottom of a list that is still growing.
  const tail = events.slice(-22).reverse()

  return (
    <SlideChrome
      title="Event tail"
      accent={NEO4J.lightPeriwinkle}
      badge={`${events.length} total`}
      focused={onStage}
      footer={<span>runs/&lt;id&gt;.jsonl, verbatim · newest first</span>}
    >
      {tail.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          waiting for the first event…
        </div>
      ) : (
        <ul
          className="font-pixel flex h-full flex-col gap-1"
          style={{ fontSize: 36 }}
        >
          {tail.map((e, i) => {
            const color = e.swarm ? ARM_COLOR[e.swarm] : 'hsl(var(--muted-fg))'
            return (
              <li
                key={`${e.t}-${e.type}-${i}`}
                className="flex shrink-0 items-baseline gap-6 truncate"
                style={{ opacity: LOUD.has(e.type) ? 1 : 0.55 }}
              >
                <span
                  style={{ color: 'hsl(var(--muted-fg))', width: 130 }}
                  className="shrink-0 text-right tabular-nums"
                >
                  {e.t.toFixed(1)}s
                </span>
                <span style={{ color, width: 220 }} className="shrink-0">
                  {e.agent ?? e.swarm ?? '—'}
                </span>
                <span
                  style={{ color: 'hsl(var(--fg))', width: 420 }}
                  className="shrink-0"
                >
                  {e.type}
                </span>
                <span
                  className="truncate"
                  style={{ color: 'hsl(var(--muted-fg))' }}
                >
                  {summarise(e)}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </SlideChrome>
  )
}
