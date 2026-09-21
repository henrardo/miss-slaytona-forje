/**
 * Two agents. One run. Two token counts, head to head.
 *
 * Every run puts one warm agent and one cold agent on the same GPU, on the
 * same checkout, against the same suite. The only difference between them is
 * memory. So this card is two numbers and the bars that compare them.
 *
 * ── Which run, and why it is not all of them ─────────────────────────────
 *
 * ONE RUN. Summing the archive was the first version of this card and it
 * hid the result: 76 runs of warm against cold average out to a 7% gap,
 * because a run where warm spent a third of cold cancels one where it spent
 * half again as much. A single run is a real comparison; the mean of
 * seventy-six is mostly an artefact of how many attempts each arm happened
 * to get.
 *
 * `pick()` takes the NEWEST run where both arms ran and ran the SAME NUMBER
 * OF ATTEMPTS. Equal attempts is what makes the two totals comparable at
 * all — an arm that took five attempts to another's three has spent more
 * for reasons that have nothing to do with memory. The run is named in the
 * badge, so what is on screen is always checkable against the file.
 *
 * If no run has matched attempts, it falls back to the newest run where both
 * arms spent anything and the badge says `attempts differ` — the card
 * degrades into a weaker claim rather than into a wrong one.
 *
 * ── Where the numbers come from ──────────────────────────────────────────
 *
 * `/api/tokens`, which indexes every `runs/*-metrics.json` and keeps the
 * arms apart: `attempt_prompt_tokens` and `attempt_completion_tokens` per
 * arm, exactly as `orchestrator/metrics.py` wrote them. Nothing here is
 * recomputed and nothing is summed across the two arms.
 *
 * DISTILLATION IS NOT IN THE COMPARISON. Cold has no skill to write, so its
 * distil columns are structurally zero, and folding warm's authoring cost in
 * would score warm for having a treatment at all. Splitting attempt from
 * distillation is `What it cost`'s whole subject; this card is the agents'
 * own spend, and the footer says which fields that is.
 */
import { useEffect, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'

/**
 * Gold is warm, blue is cold — the frames of the Warm and Cold cards, which
 * is where an audience learnt which is which. Deliberately NOT `ARM_COLOR`,
 * whose warm/cold are the other way round; every chart in the deck uses it
 * and flipping it is its own change, not this card's.
 */
const WARM = NEO4J.marigold
const COLD = NEO4J.periwinkle
const ACCENT = WARM

interface Arm {
  in: number
  out: number
  attempts: number
  turns: number
  seconds: number
}

interface Run {
  id: string
  warm: Arm
  cold: Arm
}

/** What the agent itself read and wrote. Distillation is not in here. */
const spend = (a: Arm) => a.in + a.out

/**
 * The run this card shows. See the header: equal attempts first, because
 * that is what makes two token totals comparable.
 */
function pick(runs: Run[]): { run: Run | null; matched: boolean } {
  const ran = runs.filter((r) => spend(r.warm) > 0 && spend(r.cold) > 0)
  for (let i = ran.length - 1; i >= 0; i--) {
    if (ran[i].warm.attempts === ran[i].cold.attempts) {
      return { run: ran[i], matched: true }
    }
  }
  return { run: ran[ran.length - 1] ?? null, matched: false }
}

const group = (n: number) => Math.round(n).toLocaleString('en-GB')

const short = (n: number): string =>
  n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : `${Math.round(n / 1e3)} K`

/** The bars grow once, on arrival. */
const GROW = 1600
const TICK = 40
const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'

function Side({
  label,
  sub,
  value,
  colour,
  right,
}: {
  label: string
  sub: string
  value: number
  colour: string
  right?: boolean
}) {
  return (
    <div
      className="flex min-w-0 flex-1 flex-col"
      style={{ alignItems: right ? 'flex-end' : 'flex-start' }}
    >
      <div
        className="font-pixel"
        style={{ fontSize: pt(34), color: colour, letterSpacing: '0.16em' }}
      >
        {label}
      </div>
      <div
        className="heading-solid"
        style={{
          fontSize: pt(104),
          lineHeight: 0.94,
          color: colour,
          // Or every digit change reflows the number while the bars grow.
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {group(value)}
      </div>
      <div
        className="font-pixel"
        style={{ fontSize: pt(26), color: 'hsl(var(--muted-fg))' }}
      >
        {sub}
      </div>
    </div>
  )
}

/** One measure, warm against cold, as two halves of a single scale. */
function Row({
  label,
  warm,
  cold,
  format,
  grown,
}: {
  label: string
  warm: number
  cold: number
  format: (n: number) => string
  grown: number
}) {
  const of = Math.max(warm, cold, 1)
  const bar = (value: number, colour: string, alignRight: boolean) => (
    <div
      className="flex flex-1"
      style={{ justifyContent: alignRight ? 'flex-end' : 'flex-start' }}
    >
      <div
        style={{
          // ONE SCALE FOR THE PAIR. Scaling each side to itself would draw
          // every row as a dead heat whatever the numbers beside it say.
          width: `${(value / of) * 100 * grown}%`,
          height: pt(58),
          background: colour,
          borderRadius: 4,
          transition: `width ${EASE} 120ms`,
        }}
      />
    </div>
  )
  return (
    <div className="flex items-center" style={{ gap: 16 }}>
      <span
        className="font-pixel shrink-0"
        style={{
          fontSize: pt(30),
          color: WARM,
          width: pt(150),
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {format(warm)}
      </span>
      {bar(warm, WARM, true)}
      <span
        className="font-pixel shrink-0"
        style={{
          fontSize: pt(28),
          color: 'hsl(var(--muted-fg))',
          width: pt(250),
          textAlign: 'center',
        }}
      >
        {label}
      </span>
      {bar(cold, COLD, false)}
      <span
        className="font-pixel shrink-0"
        style={{
          fontSize: pt(30),
          color: COLD,
          width: pt(150),
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {format(cold)}
      </span>
    </div>
  )
}

export function TokensSlide({ onStage }: SlideProps) {
  const [runs, setRuns] = useState<Run[]>([])
  /** 0..1, how far the bars have grown. */
  const [grown, setGrown] = useState(1)

  useEffect(() => {
    void fetch('/api/tokens')
      .then((r) => r.json())
      .then((d) => setRuns((d?.perRun as Run[]) ?? []))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setGrown(1)
      return
    }
    setGrown(0)
    let t = 0
    const id = window.setInterval(() => {
      t += TICK
      setGrown(Math.min(1, t / GROW))
      if (t >= GROW) window.clearInterval(id)
    }, TICK)
    return () => window.clearInterval(id)
  }, [onStage])

  const { run, matched } = pick(runs)
  const warm = run?.warm
  const cold = run?.cold
  const wt = warm ? spend(warm) : 0
  const ct = cold ? spend(cold) : 0
  // Which way round, and by how much. Stated, because the bars are not
  // readable to two decimal places and should not pretend to be.
  const lead = wt && ct ? Math.max(wt, ct) / Math.min(wt, ct) : 1
  const leader = ct > wt ? 'cold' : 'warm'

  return (
    <SlideChrome
      title="Tokens, head to head"
      accent={ACCENT}
      badge={
        run
          ? `${run.id}${matched ? '' : ' · attempts differ'}`
          : 'reading the archive'
      }
      focused={onStage}
      footer={
        <span>
          runs/{run?.id ?? '<id>'}-metrics.json · attempt_prompt_tokens +
          attempt_completion_tokens, per arm · the newest run in which both agents
          took the same number of attempts
        </span>
      }
    >
      {!run || !warm || !cold ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: pt(44), color: 'hsl(var(--muted-fg))' }}
        >
          no metrics on disk
        </div>
      ) : (
        <div className="flex h-full flex-col justify-between">
          {/* The two counts. Nothing between them but the word. */}
          <div className="flex shrink-0 items-start" style={{ gap: 24 }}>
            <Side
              label="WARM"
              sub={`${group(warm.attempts)} attempts · with memory`}
              value={wt}
              colour={WARM}
            />
            <div
              className="font-pixel shrink-0"
              style={{
                fontSize: pt(34),
                color: 'hsl(var(--muted-fg))',
                paddingTop: pt(46),
              }}
            >
              vs
            </div>
            <Side
              label="COLD"
              sub={`${group(cold.attempts)} attempts · no memory`}
              value={ct}
              colour={COLD}
              right
            />
          </div>

          {/* The same pair, per measure, each row to its own shared scale. */}
          <div
            className="flex min-h-0 flex-1 flex-col justify-center"
            style={{ gap: pt(34) }}
          >
            <Row
              label="tokens read"
              warm={warm.in}
              cold={cold.in}
              format={short}
              grown={grown}
            />
            <Row
              label="tokens written"
              warm={warm.out}
              cold={cold.out}
              format={short}
              grown={grown}
            />
            <Row
              label="per attempt"
              warm={wt / Math.max(warm.attempts, 1)}
              cold={ct / Math.max(cold.attempts, 1)}
              format={short}
              grown={grown}
            />
            <Row
              label="agent turns"
              warm={warm.turns}
              cold={cold.turns}
              format={group}
              grown={grown}
            />
          </div>

          <div
            className="font-pixel shrink-0"
            style={{ fontSize: pt(30), color: alpha(NEO4J.cream, 0.92) }}
          >
            {leader} spent {lead.toFixed(2)}× the{' '}
            {leader === 'cold' ? 'warm' : 'cold'} agent
          </div>
        </div>
      )}
    </SlideChrome>
  )
}
