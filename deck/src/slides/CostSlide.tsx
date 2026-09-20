/**
 * What this cost, split the way the claim requires.
 *
 * ATTEMPT cost and DISTILLATION cost are two different claims — "the skill made
 * the agent cheaper" and "the skill was cheap to produce" — and one token total
 * answers neither. `orchestrator/metrics.py` keeps them apart, and so does this
 * card. The distiller even has its own counting proxy, because Vibe surfaces no
 * per-call usage and a separate endpoint is the only place the split exists.
 *
 * The GPU figure is the harness's own: `gpu_usd_per_hour x run_seconds`,
 * measured from the first event to the last. Provisioning and the model
 * download happen before the first event and are NOT in it — the run log says
 * so in the same words, and so does the footer here.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { ArmMetrics, RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

const num = (v: number) => Math.round(v).toLocaleString('en-GB')

/** Live totals from the log, so the card is not blank until the run ends. */
function live(events: RunEvent[], arm: 'warm' | 'cold') {
  const mine = events.filter((e) => e.swarm === arm && e.type === 'ATTEMPT_DONE')
  return {
    in: mine.reduce((n, e) => n + (e.attempt_prompt_tokens ?? 0), 0),
    out: mine.reduce((n, e) => n + (e.attempt_completion_tokens ?? 0), 0),
    seconds: mine.reduce((n, e) => n + (e.attempt_seconds ?? 0), 0),
    turns: mine.reduce((n, e) => n + (e.turns_used ?? 0), 0),
  }
}

function Bar({
  label,
  value,
  of,
  colour,
}: {
  label: string
  value: number
  of: number
  colour: string
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div
        className="font-pixel flex justify-between"
        style={{ fontSize: 28, color: 'hsl(var(--muted-fg))' }}
      >
        <span>{label}</span>
        <span className="tabular-nums" style={{ color: colour }}>
          {num(value)}
        </span>
      </div>
      <div style={{ height: 16, background: alpha(colour, 0.14) }}>
        <div
          style={{
            width: `${of > 0 ? Math.min(100, (value / of) * 100) : 0}%`,
            height: '100%',
            background: colour,
            transition: 'width 600ms ease-out',
          }}
        />
      </div>
    </div>
  )
}

export function CostSlide({ onStage }: SlideProps) {
  const { events, metrics } = useRunFeed()
  const end = events.find((e) => e.type === 'RUN_END')

  const arms: Record<'warm' | 'cold', ArmMetrics | undefined> = {
    warm: metrics?.arms?.warm,
    cold: metrics?.arms?.cold,
  }
  const lw = live(events, 'warm')
  const lc = live(events, 'cold')

  const attemptOut = {
    warm: arms.warm?.attempt_completion_tokens ?? lw.out,
    cold: arms.cold?.attempt_completion_tokens ?? lc.out,
  }
  const attemptIn = {
    warm: arms.warm?.attempt_prompt_tokens ?? lw.in,
    cold: arms.cold?.attempt_prompt_tokens ?? lc.in,
  }
  const distilOut = {
    warm: arms.warm?.distil_completion_tokens ?? 0,
    cold: arms.cold?.distil_completion_tokens ?? 0,
  }
  const maxIn = Math.max(attemptIn.warm, attemptIn.cold, 1)
  const maxOut = Math.max(attemptOut.warm, attemptOut.cold, 1)
  const maxDistil = Math.max(distilOut.warm, distilOut.cold, 1)

  const usd = (end?.gpu_usd as number | undefined) ?? null
  const secs = (end?.run_seconds as number | undefined) ?? null

  return (
    <SlideChrome
      title="What it cost"
      accent={NEO4J.marigold}
      badge={
        usd != null ? (
          `$${usd.toFixed(2)}`
        ) : (
          <span style={{ color: 'hsl(var(--muted))' }}>run in flight</span>
        )
      }
      focused={onStage}
      footer={
        <span>
          attempt and distillation kept apart — they are two different claims ·
          provisioning and the model download are before the first event and are not
          counted
        </span>
      }
    >
      <div className="flex h-full flex-col" style={{ gap: 10 }}>
        <div
          className="grid flex-1"
          style={{ gridTemplateColumns: '1fr 1fr', gap: 40 }}
        >
          {(['warm', 'cold'] as const).map((arm) => (
            <div key={arm}>
              <div
                className="heading-solid"
                style={{ fontSize: 46, color: ARM_COLOR[arm], marginBottom: 14 }}
              >
                {arm}
              </div>
              <Bar
                label="attempt tokens in"
                value={attemptIn[arm]}
                of={maxIn}
                colour={ARM_COLOR[arm]}
              />
              <Bar
                label="attempt tokens out"
                value={attemptOut[arm]}
                of={maxOut}
                colour={ARM_COLOR[arm]}
              />
              <Bar
                label="distillation tokens out"
                value={distilOut[arm]}
                of={maxDistil}
                colour={NEO4J.marigold}
              />
              <div
                className="font-pixel"
                style={{ fontSize: 28, color: 'hsl(var(--muted-fg))' }}
              >
                {num(arms[arm]?.turns ?? (arm === 'warm' ? lw.turns : lc.turns))}{' '}
                turns ·{' '}
                {num(
                  arms[arm]?.attempt_seconds ??
                    (arm === 'warm' ? lw.seconds : lc.seconds),
                )}
                s on the clock
                {arms[arm] ? ` · ${num(arms[arm]!.distil_seconds)}s off it` : ''}
              </div>
            </div>
          ))}
        </div>

        <div
          className="font-pixel shrink-0"
          style={{
            fontSize: 30,
            color: NEO4J.cream,
            borderTop: `1px solid ${alpha(NEO4J.marigold, 0.4)}`,
            paddingTop: 10,
          }}
        >
          {usd != null && secs != null ? (
            <>
              {end?.gpu as string} at $
              {(end?.gpu_usd_per_hour as number)?.toFixed(2)}/hr × {num(secs)}s ={' '}
              <span style={{ color: NEO4J.marigold, fontWeight: 700 }}>
                ${usd.toFixed(2)}
              </span>{' '}
              for this run
            </>
          ) : (
            'the GPU figure is written at RUN_END'
          )}
        </div>
      </div>
    </SlideChrome>
  )
}
