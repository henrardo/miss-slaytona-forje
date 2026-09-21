/**
 * What a token costs here. One division, set large.
 *
 *     $0.0013 per second  ÷  30,829 tokens per second  =  $0.04 per million
 *
 * That is the card. The rig is rented by the hour and the tokens are free
 * once it is running, so the price of a token is not a price list — it is
 * the rate divided by how fast the thing goes. Showing the division rather
 * than its answer is the difference between an audience believing the
 * number and being able to check it.
 *
 * ── The denominator is the whole argument ────────────────────────────────
 *
 * TOKENS PER SECOND, AGGREGATED OVER BOTH SWARMS, over the seconds in which
 * some agent was generating. Every other candidate is wrong in a way that
 * is invisible on a slide:
 *
 *   Wall clock (`run_seconds`) includes a THIRD of the run spent idle —
 *   grading in Daytona, distillation, sandbox creation, both arms waiting
 *   on the barrier. On swarm-1789987670 that is 2,304 s against 1,611 s of
 *   generating, and dividing by it reports 21,563 tok/s instead of 30,829:
 *   idle time charged as though it were work.
 *
 *   Summing the two arms' `attempt_seconds` is worse. They run
 *   CONCURRENTLY, so adding their clocks counts the same wall second twice
 *   — 2,746 s, longer than the run itself — and concurrency, the entire
 *   reason for one server and two agents, shows up as a slowdown.
 *
 * The denominator `activeSeconds()` builds is per ROUND: `AttemptSync`
 * holds the arms in step at one attempt each, so a round costs the LONGER
 * of the two attempts, and both arms' tokens were produced inside it. Sum
 * the rounds. Both arms' spend over one shared clock, which is what the
 * hardware actually did.
 *
 * ── The rate ─────────────────────────────────────────────────────────────
 *
 * `$4.69/hour`, the operator's, converted to a per-second price so the
 * division's units are honest. Where a metrics file records a rate at all
 * it says `4.59` (41 of 76 runs; the other 35 record 0.0), so the constant
 * and the files disagree by ten cents. The operator's figure wins because
 * it is the one on the invoice, and the footer names both.
 *
 * ── One run, the same one the head-to-head card shows ────────────────────
 *
 * Newest run with both arms, matched attempts, and a clock. Named in the
 * badge. Averaging the archive would blend a 36,000 tok/s run with a 28,097
 * one and land on a number that describes neither.
 */
import { useEffect, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'

const ACCENT = NEO4J.lightForest

/**
 * The operator's hourly price for the pod. See the header on why this is a
 * constant here and not read from `gpu_usd_per_hour`.
 */
const USD_PER_HOUR = 4.69
/** What the metrics files say, where they say anything. Footer only. */
const RECORDED_RATE = 4.59

interface Arm {
  in: number
  out: number
  attempts: number
  seconds: number
}

interface Run {
  id: string
  warm: Arm
  cold: Arm
  runSeconds: number
  activeSeconds: number
}

const spend = (a: Arm) => a.in + a.out

/** Newest run with both arms, matched attempts, and a clock to divide by. */
function pick(runs: Run[]): Run | null {
  const ran = runs.filter(
    (r) => spend(r.warm) > 0 && spend(r.cold) > 0 && r.activeSeconds > 0,
  )
  for (let i = ran.length - 1; i >= 0; i--) {
    if (ran[i].warm.attempts === ran[i].cold.attempts) return ran[i]
  }
  return ran[ran.length - 1] ?? null
}

const group = (n: number) => Math.round(n).toLocaleString('en-GB')

const mins = (s: number) => `${Math.round(s / 60)} min`

const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
/** Numerator, denominator, answer. */
const BEAT = 900
const HOLD = 6000

/** One term of the fraction: a figure over its unit. */
function Term({ value, unit }: { value: string; unit: string }) {
  return (
    <>
      <div
        className="heading-solid"
        style={{
          fontSize: pt(88),
          color: alpha(NEO4J.cream, 0.95),
          textAlign: 'center',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </div>
      <div
        className="font-pixel"
        style={{
          fontSize: pt(30),
          color: 'hsl(var(--muted-fg))',
          textAlign: 'center',
        }}
      >
        {unit}
      </div>
    </>
  )
}

export function TokenCostSlide({ onStage }: SlideProps) {
  const [runs, setRuns] = useState<Run[]>([])
  /** 1 rate, 2 rate over throughput, 3 the answer too. */
  const [beat, setBeat] = useState(3)

  useEffect(() => {
    void fetch('/api/tokens')
      .then((r) => r.json())
      .then((d) => setRuns((d?.perRun as Run[]) ?? []))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setBeat(3)
      return
    }
    let timer: number
    const step = (n: number) => {
      setBeat(n)
      timer = window.setTimeout(
        () => step(n >= 3 ? 1 : n + 1),
        n >= 3 ? HOLD : BEAT,
      )
    }
    step(1)
    return () => window.clearTimeout(timer)
  }, [onStage])

  const run = pick(runs)
  const tokens = run ? spend(run.warm) + spend(run.cold) : 0
  // BOTH SWARMS OVER ONE SHARED CLOCK. See the header, and `activeSeconds()`
  // in plugins/runsData.ts for why this is not the wall clock and not the
  // sum of the two arms' own clocks.
  const perSecond = run && run.activeSeconds > 0 ? tokens / run.activeSeconds : 0
  const usdPerSecond = USD_PER_HOUR / 3600
  const perMillion = perSecond > 0 ? (usdPerSecond / perSecond) * 1e6 : 0
  const idle = run ? Math.max(0, run.runSeconds - run.activeSeconds) : 0

  const show = (at: number) => ({
    opacity: beat >= at ? 1 : 0,
    transition: `opacity ${EASE} 450ms`,
  })

  return (
    <SlideChrome
      title="Token cost"
      accent={ACCENT}
      badge={run ? run.id : 'reading the archive'}
      focused={onStage}
      footer={
        <span>
          ${USD_PER_HOUR.toFixed(2)}/hour is the pod's price, per second · tokens
          and per-attempt seconds are that run's own metrics file · the clock is the
          seconds an agent was generating, both swarms over one shared clock · a
          metrics file that records a rate says ${RECORDED_RATE.toFixed(2)}
        </span>
      }
    >
      {!run || perSecond <= 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: pt(44), color: 'hsl(var(--muted-fg))' }}
        >
          no priced run on disk
        </div>
      ) : (
        <div className="flex h-full flex-col justify-between">
          {/* THE DIVISION. Numerator over a rule over denominator, then the
              answer, at the size of the claim. */}
          <div
            className="flex min-h-0 flex-1 items-center justify-center"
            style={{ gap: 56 }}
          >
            <div className="flex shrink-0 flex-col" style={{ gap: 10 }}>
              <div style={show(1)}>
                <Term
                  value={`$${usdPerSecond.toFixed(4)}`}
                  unit={`per second · $${USD_PER_HOUR.toFixed(2)} an hour`}
                />
              </div>
              <div
                style={{
                  height: 6,
                  background: alpha(ACCENT, 0.85),
                  borderRadius: 2,
                  ...show(2),
                }}
              />
              <div style={show(2)}>
                <Term
                  value={group(perSecond)}
                  unit="tokens per second · both agents"
                />
              </div>
            </div>

            <div
              className="heading-solid shrink-0"
              style={{
                fontSize: pt(76),
                color: 'hsl(var(--muted-fg))',
                ...show(3),
              }}
            >
              =
            </div>

            <div className="shrink-0" style={show(3)}>
              <div
                className="heading-solid"
                style={{
                  fontSize: pt(180),
                  lineHeight: 0.92,
                  color: ACCENT,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                ${perMillion.toFixed(2)}
              </div>
              <div
                className="font-pixel"
                style={{ fontSize: pt(38), color: alpha(NEO4J.cream, 0.95) }}
              >
                per million tokens
              </div>
            </div>
          </div>

          {/* What that run was, and what was taken out of the clock. */}
          <div
            className="flex shrink-0 items-baseline"
            style={{ gap: 44, flexWrap: 'wrap' }}
          >
            {(
              [
                [group(tokens), 'tokens'],
                [mins(run.activeSeconds), 'generating'],
                [mins(idle), 'idle, not counted'],
                [
                  group(run.warm.attempts + run.cold.attempts),
                  'graded attempts, two agents',
                ],
              ] as [string, string][]
            ).map(([n, of]) => (
              <div key={of} className="flex items-baseline" style={{ gap: 10 }}>
                <span
                  className="heading-solid"
                  style={{ fontSize: pt(40), color: alpha(NEO4J.cream, 0.95) }}
                >
                  {n}
                </span>
                <span
                  className="font-pixel"
                  style={{ fontSize: pt(26), color: 'hsl(var(--muted-fg))' }}
                >
                  {of}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SlideChrome>
  )
}
