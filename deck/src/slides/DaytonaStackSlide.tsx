/**
 * Daytona: one point.
 *
 * THE GRADE RUNS IN A BOX THE AGENT CANNOT REACH.
 *
 * That is the whole card. The first version said it with four panels, a
 * stamped fact list and an oracle readout, which is word soup in boxes and
 * not a picture — a reader could not tell what was being claimed.
 *
 * So: two shapes and a wall. The agent's code crosses right, a number comes
 * back left, nothing else crosses. The box is built and destroyed on a loop,
 * because a fresh one per attempt is the same point seen over time, and
 * motion says it without a sentence.
 *
 * The text budget is one headline and two arrow labels. Everything else
 * that used to be here — the vCPU cap, the sizing, the free credit, the
 * egress rationale, the oracle pair — belongs in the talk track or on the
 * Daytona verification card, which already shows every grading live.
 */
import { useEffect, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'
import type { RunEvent } from '@/lib/types'
import daytonaGlyph from '@/wordmark/glyphs/daytona-glyph.svg?url'
import mistralM from '@/wordmark/glyphs/mistral-M.svg?url'

const ACCENT = BRANDS.daytona.accent

const W = 1500
const H = 620
/** The wall, dead centre. */
const WALL = W / 2
const MID = 300

const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
/** built · graded · gone · empty. */
const BEAT = 1500

export function DaytonaStackSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const [beat, setBeat] = useState(1)

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setBeat(1)
      return
    }
    const id = window.setInterval(() => setBeat((b) => (b + 1) % 4), BEAT)
    return () => window.clearInterval(id)
  }, [onStage])

  const ev = events as RunEvent[]
  const graded = ev.filter((e) => e.type === 'ATTEMPT_DONE').length
  const boxes = ev.filter(
    (e) => e.type === 'SANDBOX_CREATED' && e.create_ms != null,
  ).length

  const there = beat !== 3
  const gone = beat === 2
  const fade = (on: boolean) => ({
    opacity: on ? 1 : 0,
    transition: `opacity ${EASE} 450ms`,
  })

  return (
    <SlideChrome
      title="Daytona"
      accent={ACCENT}
      mark={daytonaGlyph}
      badge={graded ? `${graded} graded · ${boxes} sandboxes` : 'the grader'}
      focused={onStage}
      footer={
        <span>
          one ephemeral sandbox per attempt, deleted in a finally ·
          orchestrator/sandbox.py
        </span>
      }
    >
      <div className="flex h-full flex-col">
        <h3
          className="heading-solid shrink-0"
          style={{ fontSize: pt(46), color: alpha(NEO4J.cream, 0.95) }}
        >
          The grade runs in a box the agent cannot reach
        </h3>

        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="min-h-0 w-full flex-1"
          role="img"
          aria-label="The agent's code crosses into a sealed sandbox; only a number comes back"
        >
          {/* The wall. */}
          <line
            x1={WALL}
            y1={20}
            x2={WALL}
            y2={H - 20}
            stroke={alpha(ACCENT, 0.85)}
            strokeWidth={5}
            strokeDasharray="16 12"
          />

          {/* The agent. */}
          <image href={mistralM} x={130} y={MID - 150} width={120} height={120} />
          <text
            x={190}
            y={MID + 10}
            textAnchor="middle"
            style={{ fontSize: pt(40) }}
            fill={alpha(NEO4J.cream, 0.95)}
            fontFamily="'Syne Neo', system-ui, sans-serif"
            fontWeight={600}
          >
            the agent
          </text>

          {/* The box. Built, graded, struck through, gone, built again. */}
          <g style={fade(there)}>
            <rect
              x={WALL + 210}
              y={MID - 160}
              width={360}
              height={260}
              rx={14}
              fill={alpha(ACCENT, 0.12)}
              stroke={alpha(ACCENT, 0.9)}
              strokeWidth={4}
              strokeDasharray={gone ? '14 10' : undefined}
            />
            <image
              href={daytonaGlyph}
              x={WALL + 350}
              y={MID - 130}
              width={80}
              height={80}
            />
            <text
              x={WALL + 390}
              y={MID - 10}
              textAnchor="middle"
              style={{ fontSize: pt(40) }}
              fill={alpha(NEO4J.cream, 0.95)}
              fontFamily="'Syne Neo', system-ui, sans-serif"
              fontWeight={600}
              textDecoration={gone ? 'line-through' : undefined}
            >
              a new sandbox
            </text>
            <text
              x={WALL + 390}
              y={MID + 55}
              textAnchor="middle"
              style={{ fontSize: pt(30) }}
              fill={ACCENT}
              fontFamily="'VT323', monospace"
            >
              pytest
            </text>
          </g>

          {/* In: the code. Out: the number. Nothing else. */}
          <defs>
            <marker
              id="dt-head"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={alpha(NEO4J.cream, 0.9)} />
            </marker>
            <marker
              id="dt-back"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={ACCENT} />
            </marker>
          </defs>

          <line
            x1={300}
            y1={MID - 60}
            x2={WALL + 195}
            y2={MID - 60}
            stroke={alpha(NEO4J.cream, 0.9)}
            strokeWidth={4}
            markerEnd="url(#dt-head)"
          />
          <text
            x={(300 + WALL + 195) / 2}
            y={MID - 80}
            textAnchor="middle"
            style={{ fontSize: pt(34) }}
            fill={alpha(NEO4J.cream, 0.9)}
            fontFamily="'VT323', monospace"
          >
            its code
          </text>

          <line
            x1={WALL + 195}
            y1={MID + 60}
            x2={300}
            y2={MID + 60}
            stroke={ACCENT}
            strokeWidth={4}
            markerEnd="url(#dt-back)"
          />
          <text
            x={(300 + WALL + 195) / 2}
            y={MID + 105}
            textAnchor="middle"
            style={{ fontSize: pt(34) }}
            fill={ACCENT}
            fontFamily="'VT323', monospace"
          >
            a number
          </text>
        </svg>
      </div>
    </SlideChrome>
  )
}
