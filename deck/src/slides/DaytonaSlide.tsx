/**
 * Daytona: the only success oracle. Every graded attempt, and its verdict.
 *
 * ── Why this was blank, and what changed ─────────────────────────────────
 *
 * The previous version keyed on packaged Vibe TRANSCRIPTS, so it could show
 * the agent's own diff beside the verdict. swarm-1789998106's package has no
 * transcripts — it ships `attempts.json`, `trees/` and DEMO-NOTES.md — so the
 * card picked a different run, or rendered its empty state, on the very run
 * the deck is pinned to. A graded attempt must never be invisible.
 *
 * So it now follows the run the DECK is following (`useRunFeed().runId`,
 * which `?run=` pins) and reads `/api/attempts`, which prefers the run's own
 * `packages/<id>/attempts.json` — one row per ATTEMPT_DONE, "derived from the
 * jsonl; nothing new" — and falls back to the event log for a run with no
 * package. The footer says which source answered.
 *
 * ── The two windows are not one chart ────────────────────────────────────
 *
 * DEMO-NOTES.md is explicit: attempts 1-9 are the equal-attempt comparison
 * and 10-11 are warm continuing alone, "uncontested, and not evidence about
 * cold". The split comes from the package's own MANIFEST rather than a
 * constant here, and the strip draws a rule at it — so nobody reads warm's
 * two extra attempts as two more wins.
 *
 * ── The tick is the exit code ────────────────────────────────────────────
 *
 * `tests_passed` is 0 both when nothing has been migrated and when the agent
 * broke the package so the suite cannot import — 70% of 77 graded attempts
 * scored exactly 0. The suite either passed or it did not; that is the oracle
 * and it is one bit. Surfaces left and files parsing sit beside it as the
 * gradient one bit cannot carry.
 *
 * On this run every verdict is a cross: cold's best was 59 tests with 18
 * files unimportable, warm's 59 with 63 of 65 parsing. Nine attempts each and
 * nothing standing — which is the point of the card, not a failure of it.
 */
import { useEffect, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, BRANDS, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'
import daytonaGlyph from '@/wordmark/glyphs/daytona-glyph.svg?url'
import { pt } from '@/lib/type'

const ACCENT = BRANDS.daytona.accent
const PASS = NEO4J.lightForest
const FAIL = ALARM

interface Attempt {
  agent: string
  arm: string
  attempt: number
  passed: number | null
  exitCode: number | null
  signature: string | null
  brokeSyntax: boolean
  v1Left: number | null
  parseOk: number | null
  parseTotal: number | null
  seconds: number | null
  turns: number | null
  stop: string | null
  createMs: number | null
  tools: Record<string, number>
  edits: number
}

interface Windows {
  comparison?: { attempts: [number, number]; note?: string }
  continuation?: { attempts: [number, number]; arms?: string[]; note?: string }
}

/** Featured attempt. Long enough to read the signature. */
const STEP_MS = 5200

const num = (n: number | null) => (n == null ? '—' : n.toLocaleString('en-GB'))

const oneLine = (s: string | null, n = 120) => {
  if (!s) return null
  const first = s.split('\n')[0].trim()
  return first.length > n ? `${first.slice(0, n)}…` : first
}

const armOf = (arm: string) => ARM_COLOR[arm === 'warm' ? 'warm' : 'cold']

/** The oracle's one bit, drawn rather than typed. */
function Mark({ ok, size }: { ok: boolean; size: number }) {
  const c = ok ? PASS : FAIL
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      role="img"
      aria-label={ok ? 'suite passed' : 'suite failed'}
      style={{ flexShrink: 0 }}
    >
      <circle
        cx="24"
        cy="24"
        r="21"
        fill={alpha(c, 0.14)}
        stroke={c}
        strokeWidth="3"
      />
      {ok ? (
        <path
          d="M 14 25 L 21 32 L 34 16"
          fill="none"
          stroke={c}
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <path
          d="M 16 16 L 32 32 M 32 16 L 16 32"
          fill="none"
          stroke={c}
          strokeWidth="5"
          strokeLinecap="round"
        />
      )}
    </svg>
  )
}

export function DaytonaSlide({ onStage }: SlideProps) {
  const { runId } = useRunFeed()
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [windows, setWindows] = useState<Windows | null>(null)
  const [source, setSource] = useState('')
  const [at, setAt] = useState(0)

  // KEYED ON THE RUN THE DECK IS FOLLOWING, so `?run=` reaches this card too.
  useEffect(() => {
    if (!runId) return
    setAt(0)
    void fetch(`/api/attempts?run=${encodeURIComponent(runId)}`)
      .then((r) => r.json())
      .then((d) => {
        setAttempts((d?.attempts as Attempt[]) ?? [])
        setWindows((d?.windows as Windows) ?? null)
        setSource(String(d?.source ?? ''))
      })
      .catch(() => undefined)
  }, [runId])

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still || attempts.length === 0) return
    const id = window.setInterval(
      () => setAt((i) => (i + 1) % attempts.length),
      STEP_MS,
    )
    return () => window.clearInterval(id)
  }, [onStage, attempts.length])

  const cur = attempts[at]
  const ok = cur?.exitCode === 0
  const passes = attempts.filter((a) => a.exitCode === 0).length
  const cut = windows?.comparison?.attempts?.[1] ?? null

  /** What the attempt actually ran, biggest first. */
  const used = cur
    ? Object.entries(cur.tools)
        .filter(([, n]) => n > 0)
        .sort((a, b) => b[1] - a[1])
    : []
  const busiest = used.length ? used[0][1] : 1

  return (
    <SlideChrome
      title="Daytona verification"
      mark={daytonaGlyph}
      accent={ACCENT}
      badge={
        attempts.length
          ? `${attempts.length} graded · ${passes} passed the suite`
          : runId
            ? 'no graded attempt yet'
            : 'no run'
      }
      focused={onStage}
      footer={
        <span>
          {runId ?? '<run>'} · {source || 'reading'} · one ephemeral sandbox per
          attempt, pytest inside it · exit code and count are pytest's, verbatim ·
          orchestrator/sandbox.py
        </span>
      }
    >
      {!cur ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: pt(44), color: 'hsl(var(--muted-fg))' }}
        >
          {runId ? 'nothing graded yet in this run' : 'no run on disk'}
        </div>
      ) : (
        <div className="flex h-full flex-col" style={{ gap: 14 }}>
          {/* THE PIPELINE. What happens to an attempt, left to right. */}
          <div
            className="font-pixel flex shrink-0 items-center"
            style={{ fontSize: pt(26), gap: 12, color: 'hsl(var(--muted-fg))' }}
          >
            <span style={{ color: armOf(cur.arm) }}>
              {cur.agent} · attempt {cur.attempt}
            </span>
            <span>→</span>
            <span>its whole tree</span>
            <span>→</span>
            <span style={{ color: ACCENT }}>
              fresh sandbox
              {cur.createMs != null ? ` · ${Math.round(cur.createMs)} ms` : ''}
            </span>
            <span>→</span>
            <span style={{ color: ACCENT }}>pytest</span>
            <span>→</span>
            <span style={{ color: ok ? PASS : FAIL }}>
              exit {num(cur.exitCode)}
            </span>
            <span>→</span>
            <span>sandbox deleted</span>
          </div>

          <div className="flex min-h-0 flex-1" style={{ gap: 20 }}>
            {/* WHAT THE AGENT DID to earn that verdict. Tool counts are the
                honest answer when the transcript was not packaged: this run
                ships attempts.json and trees/, not sessions. */}
            <div
              className="flex min-w-0 flex-col"
              style={{
                flex: '52 1 0',
                background: '#221f3e',
                border: `2px solid ${alpha(ACCENT, 0.4)}`,
                borderRadius: 10,
                padding: '14px 18px',
                overflow: 'hidden',
              }}
            >
              <div
                className="font-pixel shrink-0"
                style={{ fontSize: pt(25), color: 'hsl(var(--muted))' }}
              >
                what it ran · {num(cur.turns)} turns ·{' '}
                {cur.seconds != null ? `${Math.round(cur.seconds)}s` : '—'}
              </div>
              <div
                className="flex min-h-0 flex-1 flex-col justify-center"
                style={{ gap: 7, marginTop: 8 }}
              >
                {used.map(([tool, n]) => (
                  <div key={tool} className="flex items-center" style={{ gap: 12 }}>
                    <span
                      className="font-pixel tabular-nums shrink-0"
                      style={{
                        fontSize: pt(27),
                        color: alpha(NEO4J.cream, 0.95),
                        width: pt(70),
                        textAlign: 'right',
                      }}
                    >
                      {n}
                    </span>
                    <span
                      style={{
                        height: pt(18),
                        width: `${(n / busiest) * 52}%`,
                        // The edit calls are the ones that changed the tree;
                        // everything else is the agent looking around.
                        background:
                          tool === 'edit' || tool === 'write_file'
                            ? ACCENT
                            : alpha(NEO4J.lightPeriwinkle, 0.7),
                        borderRadius: 3,
                        flexShrink: 0,
                      }}
                    />
                    <span
                      className="font-pixel"
                      style={{
                        fontSize: pt(25),
                        color: 'hsl(var(--muted-fg))',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {tool}
                    </span>
                  </div>
                ))}
              </div>
              <div
                className="font-pixel shrink-0"
                style={{
                  fontSize: pt(23),
                  color: alpha(NEO4J.cream, 0.8),
                  marginTop: 8,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {cur.edits} edit{cur.edits === 1 ? '' : 's'} to the package ·{' '}
                {oneLine(cur.stop, 64) ?? 'no stop reason recorded'}
              </div>
            </div>

            {/* THE VERDICT. One bit, then the gradient it cannot see. */}
            <div
              className="flex flex-col justify-between"
              style={{ flex: '48 1 0', gap: 12 }}
            >
              <div className="flex items-center" style={{ gap: 18 }}>
                <Mark ok={ok} size={88} />
                <div className="min-w-0">
                  <div
                    className="heading-solid"
                    style={{ fontSize: pt(52), color: ok ? PASS : FAIL }}
                  >
                    {ok ? 'suite passed' : 'suite failed'}
                  </div>
                  <div
                    className="font-pixel"
                    style={{ fontSize: pt(26), color: 'hsl(var(--muted-fg))' }}
                  >
                    {num(cur.passed)} tests passed
                  </div>
                </div>
              </div>

              <div
                className="font-pixel"
                style={{
                  fontSize: pt(25),
                  lineHeight: 1.35,
                  color: ok ? PASS : alpha(NEO4J.cream, 0.92),
                  background: alpha(ok ? PASS : FAIL, 0.1),
                  border: `2px solid ${alpha(ok ? PASS : FAIL, 0.45)}`,
                  borderRadius: 8,
                  padding: '10px 14px',
                  overflowWrap: 'anywhere',
                }}
              >
                {ok
                  ? 'exit 0 — the only thing that counts as success'
                  : (oneLine(cur.signature) ?? 'no signature recorded')}
                {cur.brokeSyntax ? (
                  <div style={{ color: FAIL, marginTop: 6 }}>
                    the edit broke the syntax — self-inflicted
                  </div>
                ) : null}
              </div>

              <div className="flex" style={{ gap: 26 }}>
                {(
                  [
                    [num(cur.v1Left), 'v1 surfaces left'],
                    [
                      cur.parseTotal
                        ? `${num(cur.parseOk)}/${num(cur.parseTotal)}`
                        : '—',
                      'files still parsing',
                    ],
                  ] as [string, string][]
                ).map(([n, of]) => (
                  <div key={of}>
                    <div
                      className="heading-solid"
                      style={{
                        fontSize: pt(38),
                        color: alpha(NEO4J.cream, 0.95),
                      }}
                    >
                      {n}
                    </div>
                    <div
                      className="font-pixel"
                      style={{ fontSize: pt(24), color: 'hsl(var(--muted-fg))' }}
                    >
                      {of}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* EVERY GRADED ATTEMPT — ONE ROW PER ARM, aligned by attempt.
              Twenty chips in a single row overflowed the card and cut the
              last three off, which also hid the window rule. Two rows fit,
              and they say more: warm's row runs two chips past cold's, so
              the continuation is visible as a shape rather than asserted in
              a caption. */}
          <div className="flex shrink-0 flex-col" style={{ gap: 6 }}>
            {(['warm', 'cold'] as const).map((arm) => {
              const mine = attempts.filter((a) =>
                arm === 'warm' ? a.arm === 'warm' : a.arm !== 'warm',
              )
              return (
                <div key={arm} className="flex items-center" style={{ gap: 6 }}>
                  <span
                    className="font-pixel shrink-0"
                    style={{
                      fontSize: pt(23),
                      color: armOf(arm),
                      width: pt(80),
                    }}
                  >
                    {arm}
                  </span>
                  {mine.map((a) => {
                    const good = a.exitCode === 0
                    const past = cut != null && a.attempt > cut
                    const featured = attempts[at] === a
                    return (
                      <div
                        key={a.attempt}
                        className="flex min-w-0 flex-1 items-center"
                        style={{
                          gap: 7,
                          padding: '6px 8px',
                          borderRadius: 7,
                          background: alpha(
                            good ? PASS : FAIL,
                            featured ? 0.16 : 0.06,
                          ),
                          border: `2px solid ${alpha(good ? PASS : FAIL, featured ? 0.9 : 0.22)}`,
                          // The continuation is drawn as itself: dashed and
                          // dimmed, because it is warm unopposed.
                          borderStyle: past ? 'dashed' : 'solid',
                          opacity: past ? 0.7 : 1,
                        }}
                      >
                        <Mark ok={good} size={24} />
                        <span
                          className="font-pixel"
                          style={{
                            fontSize: pt(22),
                            color: 'hsl(var(--muted-fg))',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          #{a.attempt} · {num(a.passed)}
                        </span>
                      </div>
                    )
                  })}
                  {/* Cold's row is shorter by exactly the continuation. */}
                  {arm === 'cold' && cut != null
                    ? Array.from({
                        length: Math.max(
                          0,
                          attempts.filter((a) => a.arm === 'warm').length -
                            mine.length,
                        ),
                      }).map((_, i) => (
                        <div
                          key={`gap-${i}`}
                          className="font-pixel flex min-w-0 flex-1 items-center justify-center"
                          style={{
                            fontSize: pt(20),
                            color: 'hsl(var(--muted))',
                            border: `2px dashed ${alpha(NEO4J.lightPeriwinkle, 0.3)}`,
                            borderRadius: 7,
                            padding: '6px 4px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                          }}
                        >
                          {i === 0 ? 'arm ended' : ''}
                        </div>
                      ))
                    : null}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </SlideChrome>
  )
}
