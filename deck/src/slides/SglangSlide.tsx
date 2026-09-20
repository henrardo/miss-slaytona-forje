/**
 * SGLang: where the model actually comes from.
 *
 * Three real places this repo touches SGLang — the launch line on the pod, the
 * provider block that points Vibe at it, and the substitution that fills that
 * block in. Each lights when the thing it does happens.
 *
 * The launch line is worth showing for its own sake: `sglang==0.5.14` is
 * pinned, `--load-format mistral` is required for this checkpoint, and both
 * facts were found by bisecting the PyPI release history rather than by
 * reading a doc. The comments in the file say so; they are shown verbatim.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J } from '@/lib/brand'
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
    file: 'scripts/launch_sglang.sh',
    from: 89,
    to: 96,
    label: 'the server',
    note: 'every token in this talk comes through this process',
    trigger: 'model_call',
  },
  {
    file: 'harness/vibe-config.template.toml',
    from: 6,
    to: 15,
    label: 'pointing Vibe at it',
    note: 'api_style=openai + backend=generic targets any OpenAI-compatible endpoint',
    trigger: 'model_call',
  },
  {
    file: 'orchestrator/vibe_agent.py',
    from: 549,
    to: 553,
    label: 'the substitution',
    note: 'the base URL is injected per agent, so both arms share one server',
    trigger: 'tool_call',
  },
]

export function SglangSlide({ onStage }: SlideProps) {
  const activity = useActivity()
  const texts = useSources(REGIONS)
  const { events, metrics } = useRunFeed()

  const turns = events
    .filter((e) => e.type === 'ATTEMPT_DONE')
    .reduce((n, e) => n + (e.turns_used ?? 0), 0)
  const out = events
    .filter((e) => e.type === 'ATTEMPT_DONE')
    .reduce((n, e) => n + (e.attempt_completion_tokens ?? 0), 0)

  return (
    <SlideChrome
      title="SGLang"
      accent={BRANDS.sglang.accent}
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
          {metrics?.model ?? 'mistralai/Mistral-Small-4-119B-2603'} ·{' '}
          {turns.toLocaleString('en-GB')} turns · {out.toLocaleString('en-GB')}{' '}
          completion tokens
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
