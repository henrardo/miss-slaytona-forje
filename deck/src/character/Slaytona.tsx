/**
 * Miss Slaytona, animated, reacting to the live run.
 *
 * ── The canvas is 34x48 and stays 34x48 ──────────────────────────────────
 *
 * The backing store is exactly one pixel per sprite pixel; CSS magnifies it
 * under `image-rendering: pixelated`. That is not a shortcut, it is the only
 * sizing that survives this HUD: a card is authored at canonical units and then
 * CSS-scaled by the Hud, so a canvas allocated to its canonical size would be
 * rasterised at the wrong scale anyway — and at stage size it would be a
 * ~700x1000 backing store repainting every 340ms, next to twenty other scaled
 * subtrees. See the layer-budget note in hud/Hud.tsx. This way a repaint is
 * 1632 pixels and the compositor does the magnifying for free.
 *
 * ── She reacts to the feed ───────────────────────────────────────────────
 *
 * The rig's author specified the mapping, and the harness emits exactly these:
 *
 *   MEMORY_READ with hits > 0   summon   the graph materialises on her far side
 *   MEMORY_WRITE                wink     something went into the graph
 *   FILE_DONE, warm, success    dip      the warm arm converged
 *
 * Only genuinely NEW events count. The feed opens with a snapshot of the whole
 * run so far, which for a finished run is thousands of events — replaying that
 * as choreography would have her convulsing on load. The cursor is planted at
 * the end of whatever arrives first, per run id.
 */
import { useEffect, useRef } from 'react'
import { useRunFeed } from '@/data/RunFeed'
import type { RunEvent } from '@/lib/types'
import { FRAME_MS, H, IDLE, POSES, W, drawFrame, type Frame } from './slaytonaRig'

/** Highest priority wins when a batch of events arrives together. */
const TRIGGERS: { pose: keyof typeof POSES; when: (e: RunEvent) => boolean }[] = [
  {
    pose: 'dip',
    when: (e) => e.type === 'FILE_DONE' && e.swarm === 'warm' && !!e.success,
  },
  {
    pose: 'summon',
    when: (e) => e.type === 'MEMORY_READ' && (e.hits ?? 0) > 0,
  },
  { pose: 'wink', when: (e) => e.type === 'MEMORY_WRITE' },
]

export interface SlaytonaProps {
  className?: string
  /** Where she sits in her box when it is a different shape to her. */
  align?: 'center' | 'right'
}

export function Slaytona({ className, align = 'center' }: SlaytonaProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  /** The running animation, mutated in place so the rAF loop never restarts. */
  const rig = useRef({ seq: IDLE as Frame[], i: 0, last: 0, until: 0 })

  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return

    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      // One still frame. She is a character, not a load-bearing animation.
      drawFrame(ctx, IDLE[0])
      return
    }

    let raf = 0
    const loop = (t: number) => {
      const r = rig.current
      if (t - r.last > FRAME_MS) {
        r.last = t
        if (r.until && t > r.until) {
          r.until = 0
          r.seq = IDLE
          r.i = 0
        }
        drawFrame(ctx, r.seq[r.i % r.seq.length])
        r.i++
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  usePoseOnEvents(rig)

  return (
    <canvas
      ref={canvas}
      width={W}
      height={H}
      aria-hidden
      className={className}
      style={{
        // `object-fit`, not `width: auto`. A replaced element sized
        // `height: 100%; width: auto; max-width: 100%` does NOT keep its
        // aspect when the max-width bites: the width is clamped and the
        // height, being explicit, is left alone — so she squashed sideways
        // in any box narrower than 0.71 of its own height. Contain scales
        // her down instead, which is the behaviour the old code was reaching
        // for. Bottom-anchored so she stands on the floor of her box at
        // whatever size it allows.
        width: '100%',
        height: '100%',
        display: 'block',
        objectFit: 'contain',
        objectPosition: align === 'right' ? 'right bottom' : 'center bottom',
        // Animatable, and the one thing that moves when the title card drops
        // its lettering: she glides to the middle rather than jumping.
        transition: 'object-position 460ms cubic-bezier(0.4, 0, 0.2, 1)',
        imageRendering: 'pixelated',
      }}
    />
  )
}

/** Watch the feed and hand the rig a pose when something worth marking lands. */
function usePoseOnEvents(
  rig: React.MutableRefObject<{
    seq: Frame[]
    i: number
    last: number
    until: number
  }>,
) {
  const { events, runId } = useRunFeed()
  /** How far into THIS run's events we have already looked. */
  const seen = useRef<{ runId: string | null; n: number }>({
    runId: null,
    n: 0,
  })

  useEffect(() => {
    const cursor = seen.current
    if (cursor.runId !== runId) {
      // New run (or the first snapshot): adopt its history without performing
      // it. Also covers the feed re-latching onto a fresher run mid-talk.
      cursor.runId = runId
      cursor.n = events.length
      return
    }
    if (events.length <= cursor.n) return
    const fresh = events.slice(cursor.n)
    cursor.n = events.length

    const hit = TRIGGERS.find((t) => fresh.some(t.when))
    if (!hit) return
    const pose = POSES[hit.pose]
    const r = rig.current
    r.seq = pose.frames
    r.i = 0
    r.until = performance.now() + pose.frames.length * FRAME_MS + 120
  }, [events, runId, rig])
}
