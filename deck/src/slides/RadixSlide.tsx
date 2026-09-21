/**
 * RadixAttention, shown rather than described — and shown the right thing.
 *
 * This replaced the improvement curve, which was a chart nobody could read
 * at a glance.
 *
 * ── The claim this card USED to make, and why it was wrong ──────────────
 *
 * The first version said "twelve agents on one GPU". This project does not
 * run twelve agents. `--swarm-size` defaults to 1 and counts agents PER ARM,
 * so `--arms both` is TWO — `warm-0` and `cold-0` — which is what every run
 * in `runs/` contains. swarm/run.py argues against going wider, not for it:
 * two agents on one pod already contend, and `--arms warm` / `--arms cold`
 * exists so they can be run one at a time. The "twelve" came from a comment
 * in that same file about *run 12*, which is a run number in an anecdote
 * about two agents colliding.
 *
 * ── What prefix caching is actually doing here ──────────────────────────
 *
 * The swarm is tiny. The RE-READING is enormous: an agent's turn N+1 sends
 * turn N's whole conversation back plus one more tool result, so a 64-turn
 * attempt submits its prompt sixty-four times over. Measured on the run in
 * flight — 2 agents, 20 attempts, 1,290 turns — that is 49.5 M prompt tokens
 * against 164 K generated, a ratio of about 302 to 1, and the last six runs
 * all land between 286 and 356. Prefix caching is what stops a GPU
 * prefilling fifty million tokens to produce a hundred and sixty thousand.
 *
 * So the picture is a STAIRCASE, not a stack of identical siblings: each
 * turn's prompt is the previous turn's prompt plus a tip. Unfolded, the lit
 * area is a triangle — everything, every turn. Folded, only the tips stay
 * lit. That is a radix tree seen side-on, and it is what the machine is
 * really doing.
 *
 * ── Every number is live ────────────────────────────────────────────────
 *
 * `attempt_prompt_tokens` and `attempt_completion_tokens` are on every
 * ATTEMPT_DONE event. They come from a counting proxy per arm on the pod
 * (`proxy_usage`, swarm/run.py), which sums the `usage` block of every chat
 * completion; the harness samples it at attempt boundaries and charges the
 * probe to off-clock time so it cannot contaminate the arms' timing. The
 * GPU line is the run's own `metrics.gpu`, with the last full run's card as
 * a fallback — there is no RUN_START event, so a live run has no GPU to name
 * until it ends.
 *
 * Nothing here is stamped, and no counterfactual is computed. "What a server
 * without prefix caching would prefill" needs no arithmetic — every
 * submitted token is a prefilled token by definition — so the card says
 * SUBMITTED and RECOMPUTED and leaves it there.
 */
import { useEffect, useState } from 'react'
import type { ReactElement } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import { FitText } from '@/hud/FitText'
import type { SlideProps } from './types'
import type { RunEvent } from '@/lib/types'
import { SHARED_PREFIX, SHARED_STEPS } from './prompts'

const ACCENT = BRANDS.sglang.accent

/** The last full run's card, for when this run does not name one. */
const FALLBACK_GPU = 'NVIDIA H200'

/**
 * The device out of a `gpu` field, or the fallback.
 *
 * `metrics.gpu` is not always a device: a run that could not read the pod
 * writes the literal string `(not recorded)`, and `?? FALLBACK` does not
 * catch that — the field is present, it just does not say anything. This
 * card printed "one SGLang server on one (not recorded)" until it did.
 */
const gpuName = (raw: string | null | undefined): string => {
  const head = (raw ?? '')
    .split(',')[0]
    .replace(/^\dx\s*/, '')
    .trim()
  return /^[A-Za-z]/.test(head) ? head : FALLBACK_GPU
}

/* ── The staircase ────────────────────────────────────────────────────── */

const W = 1120
const H = 700
/** Turns drawn. A sample: the real count per attempt is in the dozens. */
const TURNS = 14
const BAR = 26
const PITCH = 38
const TOP = 58

/** The task prompt, at the head of every turn's prompt. */
const HEAD = 96
/** What one turn adds: a tool result and an assistant message. */
const STEP = 50

const rowY = (i: number) => TOP + i * PITCH
/** Turn i's whole prompt: the task, then everything said since. */
const total = (i: number) => HEAD + STEP * (i + 1)
/** Where the part that is new this turn begins — the only part not cached. */
const tipX = (i: number) => total(i) - STEP

const CACHED = NEO4J.lightPeriwinkle
const SHARED_INK = NEO4J.cream
const HOT = ACCENT

const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
const MORPH = 1100
/** Long enough on each state to land mid-talk on either one. */
const DWELL = { open: 2800, folded: 6800 }

function Staircase({ folded }: { folded: boolean }) {
  const fade = (on: boolean) => ({
    opacity: on ? 1 : 0,
    transition: `opacity ${MORPH}ms ${EASE}`,
  })
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-full w-full"
      role="img"
      aria-label={
        folded
          ? 'Only each turn’s new tokens are recomputed'
          : 'Every turn re-sends the whole conversation'
      }
    >
      {/* The conversation so far, on every row. Always drawn, always dim: it
          is always SUBMITTED. Whether it is also RECOMPUTED is the question
          the fold answers. */}
      {Array.from({ length: TURNS }, (_, i) => (
        <g key={`base${i}`}>
          <rect
            x={0}
            y={rowY(i)}
            width={HEAD}
            height={BAR}
            rx={4}
            fill={alpha(SHARED_INK, 0.22)}
          />
          <rect
            x={HEAD + 2}
            y={rowY(i)}
            width={total(i) - HEAD - 2}
            height={BAR}
            rx={4}
            fill={alpha(CACHED, 0.18)}
          />
        </g>
      ))}

      {/* UNFOLDED: the whole of every prompt is hot. The lit area is a
          triangle, and the triangle is the point. */}
      <g style={fade(!folded)}>
        {Array.from({ length: TURNS }, (_, i) => (
          <rect
            key={`hot${i}`}
            x={0}
            y={rowY(i)}
            width={total(i)}
            height={BAR}
            rx={4}
            fill={alpha(HOT, 0.85)}
          />
        ))}
      </g>
      {/* The state captions live OUTSIDE the bar groups. Inside, anything
          measuring a group's text against that group's own rects reads them
          as escaping a bar — they are not part of the bars, they are labels
          for which state the picture is in. */}
      <text
        x={12}
        y={rowY(0) - 16}
        style={{ fontSize: pt(24), ...fade(!folded) }}
        fill={alpha(HOT, 0.95)}
        fontFamily="'VT323', monospace"
      >
        every turn re-sends the whole conversation
      </text>

      {/* FOLDED: only each row's tip is hot — what that turn added. */}
      <g style={fade(folded)}>
        {Array.from({ length: TURNS }, (_, i) => (
          <rect
            key={`tip${i}`}
            x={tipX(i)}
            y={rowY(i)}
            width={STEP}
            height={BAR}
            rx={4}
            fill={alpha(HOT, 0.95)}
          />
        ))}
        <rect
          x={-6}
          y={rowY(0) - 6}
          width={tipX(TURNS - 1) + 6}
          height={rowY(TURNS - 1) - rowY(0) + BAR + 12}
          rx={7}
          fill="none"
          stroke={alpha(CACHED, 0.5)}
          strokeWidth={2}
          strokeDasharray="10 7"
        />
      </g>
      <text
        x={12}
        y={rowY(0) - 16}
        style={{ fontSize: pt(24), ...fade(folded) }}
        fill={alpha(CACHED, 0.95)}
        fontFamily="'VT323', monospace"
      >
        already in the cache · not recomputed
      </text>

      {/* The axes, in words: turns run down, the prompt grows right. */}
      <text
        x={12}
        y={H - 96}
        style={{ fontSize: pt(22) }}
        fill="hsl(var(--muted))"
        fontFamily="'VT323', monospace"
      >
        ↓ one attempt, turn by turn
      </text>
      <FitText
        maxWidth={430}
        x={0}
        y={H - 56}
        style={{ fontSize: pt(22) }}
        fill={alpha(SHARED_INK, 0.85)}
        fontFamily="'VT323', monospace"
      >
        {`the task prompt · ${SHARED_PREFIX.length} chars`}
      </FitText>
      <FitText
        maxWidth={430}
        x={0}
        y={H - 26}
        style={{ fontSize: pt(22) }}
        fill="hsl(var(--muted))"
        fontFamily="'VT323', monospace"
      >
        {`both arms share it to step ${SHARED_STEPS}, then fork`}
      </FitText>
      <FitText
        maxWidth={500}
        x={W - 8}
        y={H - 56}
        textAnchor="end"
        style={{ fontSize: pt(22) }}
        fill={alpha(HOT, 0.9)}
        fontFamily="'VT323', monospace"
      >
        new this turn →
      </FitText>
      <FitText
        maxWidth={500}
        x={W - 8}
        y={H - 26}
        textAnchor="end"
        style={{ fontSize: pt(22) }}
        fill="hsl(var(--muted))"
        fontFamily="'VT323', monospace"
      >
        a tool result and a reply · not to scale
      </FitText>
    </svg>
  )
}

/* ── Read against written ─────────────────────────────────────────────── */

const compact = (n: number): string =>
  n >= 1e6
    ? `${(n / 1e6).toFixed(1)} M`
    : n >= 1e3
      ? `${(n / 1e3).toFixed(0)} K`
      : String(n)

interface Totals {
  agents: number
  attempts: number
  turns: number
  prompt: number
  completion: number
}

/**
 * Two bars to one scale: submitted, and generated.
 *
 * The second is a sliver, and is supposed to be. Nothing else on the card
 * makes 302:1 feel like 302:1 — two numbers side by side read as two
 * numbers, and this reads as the disproportion it is.
 */
function ReadVsWritten({ t }: { t: Totals }) {
  const w = (n: number) => `${Math.max(0.4, (n / Math.max(t.prompt, 1)) * 100)}%`
  const row = (
    label: string,
    n: number,
    ink: string,
    note: string,
  ): ReactElement => (
    <div style={{ marginBottom: 14 }}>
      <div
        className="font-pixel flex items-baseline justify-between"
        style={{ fontSize: pt(23), color: alpha(NEO4J.cream, 0.85) }}
      >
        <span>{label}</span>
        <span style={{ color: ink }}>{compact(n)}</span>
      </div>
      <div
        style={{
          height: pt(26),
          marginTop: 6,
          borderRadius: 5,
          background: alpha(NEO4J.periwinkle, 0.12),
        }}
      >
        <div
          style={{
            width: w(n),
            height: '100%',
            borderRadius: 5,
            background: alpha(ink, 0.85),
            transition: `width ${MORPH}ms ${EASE}`,
          }}
        />
      </div>
      <div
        className="font-pixel"
        style={{ fontSize: pt(21), color: 'hsl(var(--muted))', marginTop: 4 }}
      >
        {note}
      </div>
    </div>
  )
  return (
    <div>
      {row(
        'prompt tokens submitted',
        t.prompt,
        ACCENT,
        `${compact(Math.round(t.prompt / Math.max(t.turns, 1)))} per turn, on average`,
      )}
      {row(
        'tokens generated',
        t.completion,
        NEO4J.lightForest,
        'the only part that was never going to be cached',
      )}
    </div>
  )
}

/* ── The card ─────────────────────────────────────────────────────────── */

export function RadixSlide({ onStage }: SlideProps) {
  const { metrics, events } = useRunFeed()
  const [folded, setFolded] = useState(true)

  const done = (events as RunEvent[]).filter((e) => e.type === 'ATTEMPT_DONE')
  const sum = (f: (e: RunEvent) => number) => done.reduce((n, e) => n + f(e), 0)
  const t: Totals = {
    agents: new Set(done.map((e) => e.agent).filter(Boolean)).size,
    attempts: done.length,
    turns: sum((e) => e.turns_used ?? 0),
    prompt: sum((e) => e.attempt_prompt_tokens ?? 0),
    completion: sum((e) => e.attempt_completion_tokens ?? 0),
  }
  const ratio = t.completion ? Math.round(t.prompt / t.completion) : null

  /**
   * The fold runs only on the board.
   *
   * At home a tile is a texture, twenty of them animating at once is the
   * layer storm the Hud exists to avoid, and the folded state is the more
   * legible still frame anyway. Reduced motion gets the same still frame.
   */
  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setFolded(true)
      return
    }
    let timer: number
    const open = () => {
      setFolded(false)
      timer = window.setTimeout(shut, DWELL.open)
    }
    const shut = () => {
      setFolded(true)
      timer = window.setTimeout(open, DWELL.folded)
    }
    open()
    return () => window.clearTimeout(timer)
  }, [onStage])

  const gpu = gpuName(metrics?.gpu)

  return (
    <SlideChrome
      title="RadixAttention"
      accent={ACCENT}
      mark="/brand/sglang-logo-square.svg"
      badge={ratio ? `${ratio} : 1` : `one ${gpu}`}
      focused={onStage}
      footer={
        <span>
          every figure is this run's own: `attempt_prompt_tokens` and
          `attempt_completion_tokens` on each ATTEMPT_DONE, from a counting proxy
          per arm on the pod (`proxy_usage`, swarm/run.py) that sums the usage block
          of every chat completion
        </span>
      }
    >
      <div className="flex h-full flex-col" style={{ gap: 14 }}>
        <h3
          className="heading-solid shrink-0"
          style={{ fontSize: pt(40), color: alpha(NEO4J.cream, 0.95) }}
        >
          {ratio
            ? `${ratio} tokens read for every token written — prefix caching is what makes that affordable`
            : 'Prefix caching: the swarm is small, the re-reading is enormous'}
        </h3>

        <div className="flex min-h-0 flex-1" style={{ gap: 28 }}>
          <div className="min-w-0 flex-1">
            <Staircase folded={folded} />
          </div>

          <div
            className="flex shrink-0 flex-col justify-between"
            style={{ width: '32%' }}
          >
            <ReadVsWritten t={t} />

            {ratio ? (
              <div>
                <div
                  className="heading-solid"
                  style={{ fontSize: pt(96), color: ACCENT, lineHeight: 1 }}
                >
                  {ratio} : 1
                </div>
                <div
                  className="font-pixel"
                  style={{ fontSize: pt(23), color: 'hsl(var(--muted-fg))' }}
                >
                  read : written, this run
                </div>
              </div>
            ) : null}

            <div>
              <p
                className="font-pixel"
                style={{ fontSize: pt(23), color: alpha(NEO4J.cream, 0.82) }}
              >
                {t.attempts
                  ? `${t.agents} agents · ${t.attempts} attempts · ${t.turns.toLocaleString()} turns so far, through one SGLang server on one ${gpu}.`
                  : `Waiting for the first graded attempt. One SGLang server on one ${gpu}, shared by both arms.`}
              </p>
              <p
                className="font-pixel"
                style={{
                  fontSize: pt(22),
                  color: 'hsl(var(--muted))',
                  marginTop: 12,
                }}
              >
                Two agents, not a crowd: swarm/run.py defaults to one per arm and
                says why — two on one pod already contend. The saving is not in how
                many agents there are. It is in how much of each turn the server has
                already seen.
              </p>
            </div>
          </div>
        </div>
      </div>
    </SlideChrome>
  )
}
