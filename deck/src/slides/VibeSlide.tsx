/**
 * Vibe: the agent loop, and the two places this project extends it.
 *
 * Both extension points are Vibe's OWN surfaces, not patches. That distinction
 * is the hard-won one here: an earlier version of this project monkey-patched
 * the installed package in site-packages and produced an agent loop that could
 * not terminate. Vibe stays vanilla; `hooks.toml` and the stream it emits are
 * documented extension points, and everything below uses only those.
 *
 * `hooks.toml` is written for WARM ONLY. Cold gets no hook file at all — no
 * hook process, no latency, no writes — which is one of the three known arm
 * differences the confound card names.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, NEO4J } from '@/lib/brand'
import {
  RegionView,
  isLit,
  useActivity,
  useSources,
  type Region,
} from './SourceSparkle'
import type { SlideProps } from './types'

const REGIONS: Region[] = [
  {
    file: 'orchestrator/vibe_agent.py',
    from: 436,
    to: 444,
    label: "hooks.toml — Vibe's own post_tool hook",
    note: 'warm only; cold gets no hook file, so no hook process and no writes',
    trigger: 'step_write',
  },
  {
    file: 'orchestrator/ingest.py',
    from: 134,
    to: 141,
    label: 'parsing the stream into steps',
    note: 'grouped by the tool call they precede — Vibe reuses one turnId per exchange',
    trigger: 'ingest',
  },
  {
    file: 'harness/vibe-config.template.toml',
    from: 12,
    to: 15,
    label: 'the model Vibe is given',
    note: 'a self-hosted provider, declared the way Mistral document it',
    trigger: 'tool_call',
  },
]

export function VibeSlide({ onStage }: SlideProps) {
  const activity = useActivity()
  const texts = useSources(REGIONS)
  const { events, metrics } = useRunFeed()

  const ingested = events.filter((e) => e.type === 'INGESTED')
  const steps = ingested.reduce((n, e) => n + (e.steps ?? 0), 0)
  const failedTools = ingested.reduce(
    (n, e) => n + ((e.failed_tool_calls as number) ?? 0),
    0,
  )
  // null is UNCOUNTED, and that is not zero — the rule from metrics.py.
  const withReasoning = metrics?.arms?.warm?.steps_with_reasoning
  const fallbacks = metrics?.arms?.warm?.thought_fallbacks

  return (
    <SlideChrome
      title="Vibe"
      accent={NEO4J.periwinkle}
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
        <span>
          {steps} step(s) ingested · reasoning on{' '}
          {withReasoning == null ? '—' : withReasoning} ·{' '}
          <span style={{ color: fallbacks ? ALARM : undefined }}>
            {fallbacks == null ? '—' : fallbacks} thought fallback(s)
          </span>
          {failedTools ? ` · ${failedTools} failed tool call(s)` : ''}
        </span>
      }
    >
      <div className="flex h-full flex-col" style={{ gap: 12 }}>
        {REGIONS.map((r) => (
          <RegionView
            key={`${r.file}:${r.from}`}
            region={r}
            text={texts[r.file]}
            lit={isLit(activity, r.trigger)}
          />
        ))}
      </div>
    </SlideChrome>
  )
}
