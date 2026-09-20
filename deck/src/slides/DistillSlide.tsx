/**
 * The distillation turn: did the agent manage to rewrite its own procedure?
 *
 * Once per attempt, off the clock, the warm model is handed its current skill
 * and asked for a better one. `orchestrator/skills.py` then decides whether to
 * take it — and the interesting number on this card is the REJECTIONS, with
 * their reasons, because a rejected proposal means the previous version stays
 * live and the arm did not improve this round.
 *
 * ── Accepted is not the same as improved ─────────────────────────────────
 *
 * The validator checks that a proposal is a valid AIP procedure and within the
 * size cap. It cannot check that the procedure is better, and there is no
 * fitness test in this loop. One accepted version collapsed the skill from
 * 3,439 words to 686 and the warm arm stopped editing files altogether — a
 * clean "accepted: true" the whole way. So this card shows acceptance and
 * SIZE together, and says what acceptance does not mean.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

interface Row {
  key: string
  t: number
  attempt: number | null
  version: number | null
  accepted: boolean
  reason: string | null
  detail: string | null
  repairs: number
  seconds: number | null
  traces: number | null
  memCalls: number | null
}

function rows(events: RunEvent[]): Row[] {
  return events
    .filter((e) => e.type === 'DISTILLED')
    .map((e) => ({
      key: `${e.t}-${e.attempt}`,
      t: e.t,
      attempt: e.attempt ?? null,
      version: (e.version as number | undefined) ?? null,
      accepted: !!e.accepted,
      reason: (e.reason as string | null) ?? null,
      detail: (e.reason_detail as string | null) ?? null,
      repairs: (e.repairs as number | undefined) ?? 0,
      seconds: (e.seconds as number | undefined) ?? null,
      traces: (e.eligible_traces as number | undefined) ?? null,
      memCalls: (e.memory_tool_calls as number | undefined) ?? null,
    }))
}

export function DistillSlide({ onStage }: SlideProps) {
  const { events, metrics } = useRunFeed()
  const all = rows(events)
  const tail = all.slice(-12).reverse()
  const accepted = all.filter((r) => r.accepted).length
  const warm = metrics?.arms?.warm

  return (
    <SlideChrome
      title="AIP distillation"
      accent={NEO4J.marigold}
      badge={
        all.length ? (
          <span
            style={{ color: accepted < all.length ? ALARM : NEO4J.lightForest }}
          >
            {accepted} / {all.length} accepted
          </span>
        ) : (
          'no distillation yet'
        )
      }
      focused={onStage}
      footer={
        <span>
          accepted means VALID and within the size cap — there is no fitness test,
          so it does not mean better
          {warm ? ` · ${warm.distil_seconds.toFixed(0)}s off the clock` : ''}
        </span>
      }
    >
      {tail.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          the warm arm distils after each attempt
        </div>
      ) : (
        <div className="font-pixel" style={{ fontSize: 30, lineHeight: 1.45 }}>
          {tail.map((r) => (
            <div
              key={r.key}
              className="flex items-baseline gap-6"
              style={{
                borderTop: '1px solid hsl(var(--border))',
                paddingTop: 8,
                paddingBottom: 8,
                background: r.accepted ? undefined : alpha(ALARM, 0.08),
              }}
            >
              <span
                className="shrink-0 tabular-nums"
                style={{ color: 'hsl(var(--muted))', width: 110 }}
              >
                {r.t.toFixed(0)}s
              </span>
              <span
                className="shrink-0 tabular-nums"
                style={{ color: ARM_COLOR.warm, width: 130 }}
              >
                att #{r.attempt ?? '—'}
              </span>
              <span
                className="shrink-0"
                style={{
                  width: 210,
                  fontWeight: 700,
                  color: r.accepted ? NEO4J.lightForest : ALARM,
                }}
              >
                {r.accepted ? `→ v${r.version}` : 'REJECTED'}
              </span>
              <span
                className="shrink-0 tabular-nums"
                style={{ color: 'hsl(var(--muted-fg))', width: 360 }}
              >
                {r.seconds != null ? `${r.seconds.toFixed(0)}s` : '—'}
                {r.traces != null ? ` · ${r.traces} eligible trace(s)` : ''}
                {r.repairs ? ` · ${r.repairs} repair(s)` : ''}
              </span>
              <span
                style={{
                  color: r.accepted ? 'hsl(var(--muted))' : ALARM,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {r.reason ?? r.detail ?? ''}
                {r.memCalls === 0 && r.accepted
                  ? 'wrote it without querying the graph'
                  : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </SlideChrome>
  )
}
