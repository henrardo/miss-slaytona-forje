/**
 * What the agent was actually thinking. The real transcript, playing.
 *
 * Thought, tool call, arguments and observation — one display, in order, the
 * way the agent produced them.
 *
 * ── Where this reads from, and why it changed ────────────────────────────
 *
 * `/api/reasoning`, which is the agent's OWN Vibe session out of the
 * packaged run artifacts: `messages.jsonl` under
 * `runs/exp<n>-artifacts/home/agent-<arm>-0/.vibe/logs/session/`. Twelve of
 * them on disk; the endpoint takes the newest agent and its last four
 * attempts.
 *
 * It used to read the live graph through `GraphFeed`, and that is why it
 * spent the talk showing "nothing written yet": the graph holds what Cognee
 * distilled, on its own schedule, for the warm arm only, and it is empty
 * whenever nothing has been bridged. The transcript is the primary record
 * and it is already on disk — so the card no longer depends on a write
 * having landed somewhere else first.
 *
 * THE THOUGHT IS THE ASSISTANT'S `content`. Measured against
 * Mistral-Small-4 on SGLang, `reasoning_content` comes back None and the
 * reasoning arrives as ordinary assistant content beside the tool call it
 * justifies. There is no separate channel to read.
 *
 * ── It plays, and only the live part plays ───────────────────────────────
 *
 * Earlier attempts are drawn immediately, dimmed: they have already
 * happened, and a card that spends four minutes redrawing history is a card
 * nobody watches. The NEWEST attempt advances a step at a time, loops, and
 * is what the eye lands on. So the card is full the moment it is staged and
 * still visibly moving.
 *
 * ── The one thing to be careful about ────────────────────────────────────
 *
 * `thought` has not always contained thinking. On the retired live-hook path
 * the field held serialised TOOL INPUT — 988 of 993 steps in one six-run
 * series — which makes a card like this look rich while showing nothing but
 * JSON the agent typed. So a thought that is really tool arguments is
 * FLAGGED rather than rendered as reasoning: if it ever comes back, this
 * card is where it shows.
 */
import { useEffect, useMemo, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'
import { pt } from '@/lib/type'

/** Older attempts are dimmed by this much per attempt back. */
const DIM = 0.42
const KEEP_GROUPS = 4
/** Steps shown per attempt. The newest gets more room than the history. */
const STEPS_LIVE = 7
const STEPS_PAST = 2

/** One step forward, and the pause before the stream loops. */
const PACE = 1100
const LOOP_PAUSE = 5000

interface Step {
  n: number
  thought: string
  toolName: string | null
  toolArgs: string | null
  ok: boolean | null
  observation: string | null
}

interface Session {
  id: string
  agent: string
  startedAt: string
  task: string | null
  total: number
  steps: Step[]
}

/**
 * Tool input masquerading as reasoning. The live hook wrote `{"file_path": …`
 * into `thought`; real reasoning is prose.
 */
function looksLikeToolInput(thought: string): boolean {
  const t = thought.trim()
  return (
    (t.startsWith('{') && t.endsWith('}') && t.includes('":')) ||
    /^(command|file_path|pattern|content)\s*[:=]/.test(t)
  )
}

const clip = (s: string | null, n: number) =>
  !s ? '' : s.length > n ? `${s.slice(0, n)}…` : s

/** `session_20260920_161552_fbd5cf5e` → `16:15:52`. */
const clock = (iso: string) => (iso.length >= 19 ? iso.slice(11, 19) : iso)

export function ReasoningSlide({ onStage }: SlideProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [agent, setAgent] = useState<string | null>(null)
  /** How many steps of the NEWEST attempt have played. */
  const [cursor, setCursor] = useState(0)

  useEffect(() => {
    void fetch('/api/reasoning?cap=60')
      .then((r) => r.json())
      .then((d) => {
        setSessions((d?.sessions as Session[]) ?? [])
        setAgent(d?.agent ?? null)
      })
      .catch(() => undefined)
  }, [])

  const live = sessions[sessions.length - 1]
  const past = sessions.slice(-KEEP_GROUPS, -1)
  const liveCount = live?.steps.length ?? 0

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still || liveCount === 0) {
      setCursor(liveCount)
      return
    }
    setCursor(1)
    let at = 1
    let timer: number
    const tick = () => {
      at = at >= liveCount ? 1 : at + 1
      setCursor(at)
      timer = window.setTimeout(tick, at >= liveCount ? LOOP_PAUSE : PACE)
    }
    timer = window.setTimeout(tick, PACE)
    return () => window.clearTimeout(timer)
  }, [onStage, liveCount])

  const flagged = useMemo(
    () =>
      sessions.reduce(
        (n, s) => n + s.steps.filter((x) => looksLikeToolInput(x.thought)).length,
        0,
      ),
    [sessions],
  )

  /**
   * NEWEST FIRST, and the container is a plain column.
   *
   * It was oldest-first inside a `flex-col-reverse`, which does put the
   * newest group at the top — and then clips it, because a reversed column
   * overflows at the top edge. The playing attempt was the one cut off: its
   * header gone and one line of it left. Newest first in a normal column
   * clips the OLDEST instead, which is the history and is meant to trail
   * off.
   */
  const groups: { session: Session; steps: Step[]; back: number }[] = [
    ...(live
      ? [
          {
            session: live,
            steps: live.steps.slice(0, cursor).slice(-STEPS_LIVE),
            back: 0,
          },
        ]
      : []),
    ...past
      .map((s, i) => ({
        session: s,
        steps: s.steps.slice(-STEPS_PAST),
        back: past.length - i,
      }))
      .reverse(),
  ]

  return (
    <SlideChrome
      title="Reasoning stream"
      accent={NEO4J.lightBaltic}
      badge={
        flagged > 0 ? (
          <span style={{ color: ALARM, fontWeight: 700 }}>
            {flagged} tool-input thoughts
          </span>
        ) : live ? (
          // The STEP'S OWN NUMBER, not the cursor. The endpoint returns the
          // last `cap` steps of a longer attempt, so a cursor of 4 was
          // sitting under a step labelled 48 and the badge disagreed with
          // the body of the card.
          `${agent ?? 'agent'} · step ${live.steps[cursor - 1]?.n ?? cursor} of ${live.total}`
        ) : (
          'reading the artifacts'
        )
      }
      focused={onStage}
      footer={
        <span>
          the agent's own Vibe transcript, messages.jsonl, out of the packaged run
          artifacts · assistant content is where this model puts its reasoning ·
          earlier attempts are dimmed, the newest one is playing
        </span>
      }
    >
      {groups.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: pt(48), color: 'hsl(var(--muted-fg))' }}
        >
          no packaged transcript on disk
        </div>
      ) : (
        <div className="flex h-full flex-col overflow-hidden" style={{ gap: 18 }}>
          {/* Newest first. See `groups`: this order is what keeps the playing
              attempt off the clipped edge. */}
          {groups.map((g) => (
            <section
              key={g.session.id}
              style={{
                // 0.78, not 0.16: the ramp is de-emphasis, and text faded
                // below 3:1 is not de-emphasised — it is unreadable while
                // still taking up the room. At 0.16 the oldest group
                // measured 1.08:1, and 0.55 was still only 2.06.
                opacity: Math.max(0.78, DIM ** g.back),
                borderLeft: `4px solid ${alpha(
                  g.back === 0 ? NEO4J.lightBaltic : NEO4J.lightPeriwinkle,
                  g.back === 0 ? 0.9 : 0.45,
                )}`,
                paddingLeft: 20,
              }}
            >
              <header
                className="font-pixel"
                style={{ fontSize: pt(26), color: NEO4J.lightPeriwinkle }}
              >
                {clock(g.session.startedAt)} · {g.session.total} steps
                {g.back === 0 ? '' : ' · earlier attempt'}
              </header>
              {g.steps.map((s) => {
                const sus = looksLikeToolInput(s.thought)
                return (
                  <div key={s.n} style={{ marginTop: 10 }}>
                    {s.thought ? (
                      <div
                        className="font-pixel"
                        style={{
                          fontSize: pt(30),
                          lineHeight: 1.35,
                          color: sus ? ALARM : NEO4J.cream,
                        }}
                      >
                        <span style={{ color: 'hsl(var(--muted))' }}>{s.n} </span>
                        {sus ? '[tool input, not reasoning] ' : ''}
                        {clip(s.thought, 260)}
                      </div>
                    ) : null}
                    {s.toolName ? (
                      <div
                        className="font-pixel"
                        style={{
                          fontSize: pt(26),
                          color: s.ok === false ? ALARM : NEO4J.marigold,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {s.thought ? '' : `${s.n} `}→ {s.toolName}(
                        {clip(s.toolArgs, 110)})
                      </div>
                    ) : null}
                    {s.observation ? (
                      <div
                        className="font-pixel"
                        style={{
                          fontSize: pt(24),
                          color: NEO4J.lightForest,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        ← {clip(s.observation, 150)}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </section>
          ))}
        </div>
      )}
    </SlideChrome>
  )
}
