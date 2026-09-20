/**
 * The orchestrator's own stdout, as it is written.
 *
 * Not a re-render of the event log — the actual transcript the harness prints
 * while it runs: MCP tool counts, the baseline score, GPU and skill provenance,
 * the arm-difference warning, per-attempt lines, and the final summary. The
 * driver redirects it into `runs/<name>.log` on THIS machine, line by line, so
 * it tails exactly like the event log does.
 *
 * ── LIVE vs REPLAY, and why the badge is loud ────────────────────────────
 *
 * A terminal that is not moving is a dead screen on stage, so when nothing has
 * been appended for a while this card replays the most recent transcript from
 * the top at a readable rate. That is a presentation device and it is the one
 * thing on this card that is not literally happening, so it says REPLAY in
 * hibiscus with the file name next to it, and it stops the moment a real line
 * lands — a growing log always wins.
 *
 * Nothing is ever invented: replay types out bytes that are on disk, in order.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

/** Quiet for this long and the card starts replaying instead. */
const IDLE_MS = 20_000
/** Replay speed. Fast enough to feel like a machine, slow enough to read. */
const REPLAY_LINES_PER_S = 14
/** How much scrollback to keep. A long series log is tens of thousands. */
const MAX_LINES = 400

/**
 * Lines the eye should catch. Everything else is the same muted green, because
 * a terminal where nine colours compete is just noise at the back of a room.
 */
const RULES: { test: RegExp; colour: string; bold?: boolean }[] = [
  { test: /^(WARM|COLD)\b/, colour: NEO4J.lightBaltic, bold: true },
  { test: /\bGPU:|\$\d/, colour: NEO4J.marigold },
  { test: /arms differ|CONFOUND|Traceback|Error|FAILED|failed/, colour: ALARM },
  { test: /^GATE ok|converged|counts toward/, colour: NEO4J.lightForest },
  {
    test: /^===|^ *skill:|^ *distiller:|^metrics:|^event log:/,
    colour: NEO4J.lightPeriwinkle,
  },
  { test: /^ *baseline:|^ *graph at start|^ *MCP /, colour: NEO4J.cream },
]

function colourFor(line: string): { colour: string; bold: boolean } {
  for (const r of RULES) {
    if (r.test.test(line)) return { colour: r.colour, bold: !!r.bold }
  }
  return { colour: '#8fb69a', bold: false }
}

export function TerminalSlide({ onStage }: SlideProps) {
  const { log } = useRunFeed()
  const lines = useMemo(
    () => (log?.text ?? '').split('\n').filter((l) => l.length > 0),
    [log?.text],
  )

  /**
   * Whether the file is actually growing. Driven by byte count rather than by
   * mtime: a log can be touched without being appended to, and "it changed"
   * is not the claim this badge makes.
   */
  const [growing, setGrowing] = useState(false)
  const lastBytes = useRef<number | null>(null)
  const lastGrowth = useRef(0)

  useEffect(() => {
    const bytes = log?.bytes ?? null
    if (bytes !== null && lastBytes.current !== null && bytes > lastBytes.current) {
      lastGrowth.current = performance.now()
      setGrowing(true)
    }
    lastBytes.current = bytes
  }, [log?.bytes])

  useEffect(() => {
    const t = setInterval(() => {
      if (growing && performance.now() - lastGrowth.current > IDLE_MS) {
        setGrowing(false)
      }
    }, 1000)
    return () => clearInterval(t)
  }, [growing])

  /** How many lines of a replay have been typed. Ignored while live. */
  const [typed, setTyped] = useState(0)
  useEffect(() => {
    if (growing || lines.length === 0) return
    setTyped(0)
    const step = 1000 / REPLAY_LINES_PER_S
    const t = setInterval(() => {
      setTyped((n) => (n >= lines.length ? 0 : n + 1))
    }, step)
    return () => clearInterval(t)
  }, [growing, lines.length])

  const shown = growing ? lines : lines.slice(0, typed)
  const tail = shown.slice(-MAX_LINES)

  // Stick to the bottom. `scrollTop = scrollHeight` rather than scrollIntoView
  // so it cannot scroll an ancestor — this card is inside a transformed layer.
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (el) el.scrollTop = el.scrollHeight
  }, [tail.length])

  return (
    <SlideChrome
      title="RunPod terminal"
      accent={NEO4J.lightForest}
      badge={
        growing ? (
          <span style={{ color: NEO4J.lightForest }}>● LIVE</span>
        ) : (
          <span style={{ color: ALARM, fontWeight: 700 }}>REPLAY</span>
        )
      }
      focused={onStage}
      footer={
        <span>
          runs/{log?.file ?? '—'}
          {log?.runId ? ` · ${log.runId}` : ''}
          {growing ? '' : ' · replaying a finished transcript, not live'}
        </span>
      }
    >
      {lines.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          no .log in runs/ yet
        </div>
      ) : (
        <div
          ref={box}
          className="font-pixel h-full overflow-hidden"
          style={{ fontSize: 30, lineHeight: 1.32 }}
        >
          {tail.map((line, i) => {
            const { colour, bold } = colourFor(line)
            return (
              <div
                key={`${tail.length}-${i}`}
                style={{
                  color: colour,
                  fontWeight: bold ? 700 : 400,
                  whiteSpace: 'pre',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {line}
              </div>
            )
          })}
          {/* The cursor only blinks on a live tail. A blinking cursor under a
              replay would be the one detail that sells it as live. */}
          {growing ? (
            <span
              style={{
                display: 'inline-block',
                width: '0.6em',
                height: '1em',
                background: alpha(NEO4J.lightForest, 0.9),
              }}
            />
          ) : null}
        </div>
      )}
    </SlideChrome>
  )
}
