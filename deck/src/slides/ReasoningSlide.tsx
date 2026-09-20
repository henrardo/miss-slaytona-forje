/**
 * What the agent was actually thinking.
 *
 * Thought, tool call, arguments, observation and any entities — one display, in
 * order, as each step lands in the graph. This is the card the event log cannot
 * produce: `STEP_WRITES` carries counts, not text.
 *
 * ── Ageing, and why it matters here specifically ─────────────────────────
 *
 * Same rule as the graph card: nothing is removed, it recedes. Steps are
 * grouped by attempt, the newest group is at full strength, and each older
 * group dims by a fixed factor — so the eye lands on what is happening now
 * without the history disappearing and making the run look shorter than it was.
 *
 * ── The one thing to be careful about ────────────────────────────────────
 *
 * `thought` has not always contained thinking. On the live-hook path the field
 * held serialised TOOL INPUT — 988 of 993 steps in one six-run series — which
 * makes a card like this look rich while showing nothing but JSON the agent
 * typed. `orchestrator/ingest.py` exists because of it. So a step whose thought
 * is really tool arguments is FLAGGED rather than rendered as reasoning: if the
 * stream fills with those again, this card is where it shows.
 */
import { useMemo } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useGraphFeed, type GraphStep } from '@/data/GraphFeed'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

/** Groups older than this many steps back are dimmed by DIM per step. */
const DIM = 0.42
const KEEP_GROUPS = 6

/**
 * Tool input masquerading as reasoning. The live hook wrote `{"file_path": ...`
 * into `thought`; real reasoning is prose.
 */
function looksLikeToolInput(thought: string | null): boolean {
  if (!thought) return false
  const t = thought.trim()
  return (
    (t.startsWith('{') && t.endsWith('}') && t.includes('":')) ||
    /^(command|file_path|pattern|content)\s*[:=]/.test(t)
  )
}

interface Group {
  key: string
  session: string
  task: string | null
  steps: GraphStep[]
}

function group(steps: GraphStep[]): Group[] {
  const out: Group[] = []
  for (const s of steps) {
    const last = out[out.length - 1]
    if (last && last.key === s.traceId) last.steps.push(s)
    else
      out.push({
        key: s.traceId,
        session: s.sessionId,
        task: s.task,
        steps: [s],
      })
  }
  return out
}

const clip = (s: string | null, n: number) =>
  !s ? '' : s.length > n ? `${s.slice(0, n)}…` : s

export function ReasoningSlide({ onStage }: SlideProps) {
  const { steps, live, staleAgeMs, scope } = useGraphFeed()
  const groups = useMemo(() => group(steps).slice(-KEEP_GROUPS), [steps])
  const fallbacks = useMemo(
    () => steps.filter((s) => looksLikeToolInput(s.thought)).length,
    [steps],
  )

  return (
    <SlideChrome
      title="Reasoning stream"
      accent={NEO4J.lightBaltic}
      badge={
        fallbacks > 0 ? (
          <span style={{ color: ALARM, fontWeight: 700 }}>
            {fallbacks} tool-input thoughts
          </span>
        ) : (
          `${steps.length} steps · ${scope === 'run' ? 'this run' : 'whole graph'}`
        )
      }
      focused={onStage}
      footer={
        <span>
          ReasoningStep.thought / action / observation, from the graph
          {live ? '' : ` · cached ${Math.round((staleAgeMs ?? 0) / 1000)}s ago`}
        </span>
      }
    >
      {groups.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          nothing written yet — only the warm arm writes reasoning
        </div>
      ) : (
        <div
          className="flex h-full flex-col-reverse overflow-hidden"
          style={{ gap: 18 }}
        >
          {/* Reversed: newest group at the top of the reading order, and the
              flex reversal means the bottom of the list is what gets clipped. */}
          {groups.map((g, gi) => {
            const back = groups.length - 1 - gi
            const strength = DIM ** back
            return (
              <section
                key={`${g.key}-${gi}`}
                style={{
                  opacity: Math.max(0.16, strength),
                  borderLeft: `4px solid ${alpha(NEO4J.lightPeriwinkle, 0.5)}`,
                  paddingLeft: 20,
                }}
              >
                <header
                  className="font-pixel"
                  style={{ fontSize: 26, color: NEO4J.lightPeriwinkle }}
                >
                  {g.session} · {clip(g.task, 90)}
                </header>
                {g.steps.slice(-8).map((s) => {
                  const sus = looksLikeToolInput(s.thought)
                  return (
                    <div key={s.id} style={{ marginTop: 10 }}>
                      <div
                        className="font-pixel"
                        style={{
                          fontSize: 30,
                          lineHeight: 1.35,
                          color: sus ? ALARM : NEO4J.cream,
                        }}
                      >
                        <span style={{ color: 'hsl(var(--muted))' }}>
                          {s.stepNumber ?? '·'}{' '}
                        </span>
                        {sus ? '[tool input, not reasoning] ' : ''}
                        {clip(s.thought, 260) || '(no thought recorded)'}
                      </div>
                      {s.toolName ? (
                        <div
                          className="font-pixel"
                          style={{
                            fontSize: 26,
                            color:
                              s.toolStatus === 'success' ? NEO4J.marigold : ALARM,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          → {s.toolName}({clip(s.toolArgs, 120)})
                        </div>
                      ) : null}
                      {s.entities.length ? (
                        <div
                          className="font-pixel"
                          style={{ fontSize: 24, color: NEO4J.lightForest }}
                        >
                          entities: {s.entities.join(', ')}
                        </div>
                      ) : null}
                    </div>
                  )
                })}
              </section>
            )
          })}
        </div>
      )}
    </SlideChrome>
  )
}
