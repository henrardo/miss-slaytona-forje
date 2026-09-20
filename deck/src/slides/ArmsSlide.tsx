/**
 * Warm against cold, straight off `runs/<id>-metrics.json`.
 *
 * `steps_with_reasoning: null` renders as "—", never as 0. In the harness null
 * means UNCOUNTED and zero means counted-and-empty; six pod runs were read the
 * wrong way round because a metric collapsed the two. The deck will not repeat
 * that.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ARM_COLOR } from '@/lib/brand'
import type { ArmMetrics } from '@/lib/types'
import type { SlideProps } from './types'

const num = (v: number) => v.toLocaleString('en-GB')
/** null is UNCOUNTED, and that is not zero. */
const maybe = (v: number | null) => (v == null ? '—' : num(v))

interface Row {
  label: string
  of: (a: ArmMetrics) => string
}

const ROWS: Row[] = [
  { label: 'tests passed', of: (a) => num(a.tests_passed) },
  { label: 'attempts', of: (a) => num(a.attempts) },
  { label: 'converged', of: (a) => (a.converged ? 'YES' : 'no') },
  { label: 'turns', of: (a) => num(a.turns) },
  { label: 'attempt seconds', of: (a) => a.attempt_seconds.toFixed(1) },
  { label: 'prompt tokens', of: (a) => num(a.attempt_prompt_tokens) },
  { label: 'completion tokens', of: (a) => num(a.attempt_completion_tokens) },
  { label: 'steps ingested', of: (a) => num(a.steps_ingested) },
  { label: 'w/ reasoning', of: (a) => maybe(a.steps_with_reasoning) },
  { label: 'thought fallbacks', of: (a) => maybe(a.thought_fallbacks) },
  { label: 'memory tool calls', of: (a) => num(a.memory_tool_calls) },
  {
    label: 'distillations',
    of: (a) => `${num(a.distillations_accepted)} / ${num(a.distillations)}`,
  },
]

export function ArmsSlide({ onStage }: SlideProps) {
  const { metrics } = useRunFeed()
  const warm = metrics?.arms.warm
  const cold = metrics?.arms.cold

  return (
    <SlideChrome
      title="Warm vs cold"
      accent={ARM_COLOR.warm}
      badge={metrics ? `skill v${metrics.skill_version}` : 'no metrics'}
      focused={onStage}
      footer={
        <span>
          runs/&lt;id&gt;-metrics.json · “—” means UNCOUNTED, which is not zero
        </span>
      }
    >
      {!warm || !cold ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          metrics are written when the run ends
        </div>
      ) : (
        <table className="font-pixel h-full w-full" style={{ fontSize: 40 }}>
          <thead>
            <tr style={{ color: 'hsl(var(--muted-fg))' }}>
              <th className="text-left font-normal" />
              <th
                className="heading-solid text-right"
                style={{ fontSize: 52, color: ARM_COLOR.warm, width: '26%' }}
              >
                warm
              </th>
              <th
                className="heading-solid text-right"
                style={{ fontSize: 52, color: ARM_COLOR.cold, width: '26%' }}
              >
                cold
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr
                key={row.label}
                style={{ borderTop: '1px solid hsl(var(--border))' }}
              >
                <td style={{ color: 'hsl(var(--muted-fg))' }}>{row.label}</td>
                <td
                  className="text-right tabular-nums"
                  style={{ color: ARM_COLOR.warm }}
                >
                  {row.of(warm)}
                </td>
                <td
                  className="text-right tabular-nums"
                  style={{ color: ARM_COLOR.cold }}
                >
                  {row.of(cold)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SlideChrome>
  )
}
