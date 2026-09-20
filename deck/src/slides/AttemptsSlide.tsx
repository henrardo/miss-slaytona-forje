/**
 * Attempt anatomy: what each attempt actually cost, and what it did to the tree.
 *
 * The three rows that matter and are easy to miss:
 *
 *   RESTORED          the harness put the best tree back after a regression.
 *                     Convergence is monotone BECAUSE of this, which is why a
 *                     rising curve is not by itself evidence of learning.
 *   ATTEMPT_REJECTED  the attempt was graded and thrown out: `gutted` means
 *                     validators were emptied, `shimmed` means imports were
 *                     redirected at `pydantic.v1`. A 32/33 that got there by
 *                     gutting is the single worst result this project has had,
 *                     because it looks exactly like success.
 *   ATTEMPT_ABORTED   the agent loop stopped without producing a gradeable
 *                     tree — usually a Vibe stop event, which is named.
 *
 * So the card is the timeline of attempts with those three interleaved, not a
 * table of scores. A score column on its own has already misled this project.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { Arm, RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

interface Row {
  key: string
  t: number
  arm: Arm
  agent: string
  kind: 'done' | 'rejected' | 'aborted' | 'restored'
  attempt: number | null
  headline: string
  detail: string
  alarm: boolean
}

const num = (v: number | null | undefined) =>
  v == null ? '—' : v.toLocaleString('en-GB')

function rows(events: RunEvent[]): Row[] {
  const out: Row[] = []
  for (const e of events) {
    const arm = (e.swarm as Arm) ?? 'cold'
    const agent = String(e.agent ?? e.swarm ?? '?')
    const base = {
      key: `${e.type}-${agent}-${e.attempt}-${e.t}`,
      t: e.t,
      arm,
      agent,
      attempt: e.attempt ?? null,
    }
    if (e.type === 'ATTEMPT_DONE') {
      out.push({
        ...base,
        kind: 'done',
        headline: `${num(e.tests_passed)} passed`,
        detail: [
          `${num(e.turns_used)} turns`,
          `${e.attempt_seconds?.toFixed(0) ?? '—'}s`,
          `${num(e.attempt_completion_tokens)} out`,
          e.v1_remaining != null ? `${num(e.v1_remaining)} v1 left` : null,
          e.ended_cleanly === false ? 'did not end cleanly' : null,
        ]
          .filter(Boolean)
          .join(' · '),
        alarm: e.ended_cleanly === false,
      })
    } else if (e.type === 'ATTEMPT_REJECTED') {
      const how = [e.gutted ? 'gutted' : null, e.shimmed ? 'shimmed' : null]
        .filter(Boolean)
        .join(' + ')
      out.push({
        ...base,
        kind: 'rejected',
        headline: 'REJECTED',
        detail: `${how || 'failed the integrity check'} — scored ${num(
          e.pytest_passed as number,
        )} and thrown out`,
        alarm: true,
      })
    } else if (e.type === 'ATTEMPT_ABORTED') {
      out.push({
        ...base,
        kind: 'aborted',
        headline: 'ABORTED',
        detail: String(e.reason ?? e.vibe_stop ?? 'no reason given'),
        alarm: true,
      })
    } else if (e.type === 'RESTORED') {
      out.push({
        ...base,
        kind: 'restored',
        headline: 'RESTORED',
        detail: `best tree put back: ${num(e.from_passed as number)} → ${num(
          e.to_passed as number,
        )}${e.reason ? ` (${e.reason})` : ''}`,
        alarm: false,
      })
    }
  }
  return out
}

const TINT: Record<Row['kind'], string> = {
  done: NEO4J.cream,
  rejected: ALARM,
  aborted: ALARM,
  restored: NEO4J.marigold,
}

export function AttemptsSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const all = rows(events)
  const tail = all.slice(-16).reverse()
  const rejected = all.filter((r) => r.kind === 'rejected').length
  const restored = all.filter((r) => r.kind === 'restored').length

  return (
    <SlideChrome
      title="Attempt anatomy"
      accent={NEO4J.marigold}
      badge={
        rejected || restored ? (
          <span style={{ color: rejected ? ALARM : NEO4J.marigold }}>
            {rejected} rejected · {restored} restored
          </span>
        ) : (
          `${all.length} attempts`
        )
      }
      focused={onStage}
      footer={
        // Short enough not to wrap in the narrowest slot this card takes.
        <span>
          REJECTED = scored, then thrown out · RESTORED = regression undone
        </span>
      }
    >
      {tail.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          waiting for the first attempt
        </div>
      ) : (
        <div className="font-pixel" style={{ fontSize: 30, lineHeight: 1.5 }}>
          {tail.map((r) => (
            <div
              key={r.key}
              className="flex items-baseline gap-6"
              style={{
                borderTop: '1px solid hsl(var(--border))',
                paddingTop: 6,
                paddingBottom: 6,
                background: r.alarm ? alpha(ALARM, 0.08) : undefined,
              }}
            >
              <span
                className="tabular-nums shrink-0"
                style={{ color: 'hsl(var(--muted))', width: 110 }}
              >
                {r.t.toFixed(0)}s
              </span>
              <span
                className="shrink-0"
                style={{ color: ARM_COLOR[r.arm], width: 160 }}
              >
                {r.agent}
              </span>
              <span
                className="shrink-0 tabular-nums"
                style={{ color: 'hsl(var(--muted-fg))', width: 90 }}
              >
                {r.attempt != null ? `#${r.attempt}` : ''}
              </span>
              <span
                className="shrink-0"
                style={{
                  color: TINT[r.kind],
                  fontWeight: r.kind === 'done' ? 400 : 700,
                  width: 260,
                }}
              >
                {r.headline}
              </span>
              <span
                style={{
                  color: 'hsl(var(--muted-fg))',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {r.detail}
              </span>
            </div>
          ))}
        </div>
      )}
    </SlideChrome>
  )
}
