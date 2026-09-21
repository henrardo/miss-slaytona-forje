/**
 * The slide holder.
 *
 * Every card is mounted exactly once, for the life of the session, in one
 * absolutely-positioned layer. Joining the board, leaving it, and re-packing
 * change nothing but a card's transform target — it is never unmounted,
 * re-parented or re-created, so a card that has been collecting for twenty
 * minutes arrives on the board with twenty minutes of state intact. That is
 * the whole reason for this shape, and it is what made the move from swapping
 * to joining a change of rect assignment rather than a rewrite.
 *
 * JOIN, not swap. Clicking a card at home sends it to the board, where the
 * packer re-arranges everything already there around it. Clicking a card on
 * the board sends it home. Homes are PERMANENT — card i always owns ring slot
 * i — and a card away from home leaves a ghost in its slot, so the ring still
 * reads as complete and nothing drifts.
 *
 * COMPOSITING — read before touching the style object below.
 *
 * Each wrapper is a canonical-width box shrunk by a transform. A promoted
 * layer is rasterised at its UNSCALED size, because the compositor applies the
 * scale after raster: a tile 578px wide on screen still costs a 1920x1080
 * backing store, and 4x that on a Retina panel. Twenty of those is roughly
 * 660 MB, far past Chrome's tile budget, and what the budget does when it runs
 * out is evict — which paints as rectangular fragments of stale tile.
 *
 * So: nothing here promotes a layer except the cards actually moving, and only
 * while they move. A join moves at most MAX_ON_STAGE + 1 of them, which is the
 * other reason that cap exists. Specifically —
 *   - `translate`, never `translate3d`. The 3D variant forces promotion on its
 *     own, independently of will-change.
 *   - `will-change: transform` is applied transiently, to the movers only.
 *   - transitions are suppressed for one frame across a viewport change, so
 *     entering fullscreen re-lays-out instantly instead of animating every
 *     card at once.
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  canvasFor,
  computeHudLayout,
  gridRect,
  MAX_TILES,
  scaleFor,
  type Rect,
} from '@/lib/layout'
import { MAX_ON_STAGE, packStage, type Slot } from '@/lib/stage'
import { CARD_SLOTS, HOME_SLOT, SLIDES } from '@/slides/registry'
import type { Source } from '@/data/RunFeed'
import { useViewport } from './useViewport'
import { StatusRail } from './StatusRail'
import { StageContainer, STAGE_RADIUS } from './StageContainer'
import { Racetrack } from './Racetrack'
import { RaceProvider } from './RaceMode'
import { Ghost } from './Ghost'
import { MIN_TYPE_PX } from '@/lib/type'

const MORPH_MS = 760
const MORPH = `${MORPH_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`

/**
 * The board opens holding the home card.
 *
 * Not slot 0 any more: slot 0 is a corner of the frame and holds a block of
 * colour, so the home card is the first slot that holds a CARD. Everything
 * here indexes SLIDES, which includes the corners, and every traversal goes
 * through CARD_SLOTS so the corners are never landed on.
 */
const OPENING: number[] = [HOME_SLOT]

/**
 * How much of the stage the race takes, as a fraction of its shorter side.
 *
 * This is the whole of "the middle card shrinks a little": the ring does not
 * move, the stage gives up a band on all four sides, and the racers lap it.
 *
 * 8%, not 7%. Two Ms have to fit ACROSS the band on its vertical stretches,
 * and the M is 1.4 as wide as it is tall — at 7% with the old token size the
 * pair spanned 1.12 of the band, so they could not both fit and warm sat on
 * top of cold every time they were level. See TOKEN and LANES in Racetrack.
 */
const RACE_BAND = 0.08

export interface HudProps {
  onSource: (s: Source) => void
  sourceLocked: boolean
}

export function Hud({ onSource, sourceLocked }: HudProps) {
  const { w, h } = useViewport()
  const slides = SLIDES
  const tileCount = Math.min(slides.length, MAX_TILES)

  /**
   * Race mode: the stage gives up a band and the two arms lap it. Armed from
   * the Slay button on the home card, so it travels by context — see RaceMode.
   */
  const [racing, setRacing] = useState(false)
  const race = useMemo(
    () => ({ racing, slay: () => setRacing((r) => !r) }),
    [racing],
  )

  const railH = Math.round(h * 0.03)
  const layout = useMemo(() => {
    // Measure the band against the UN-inset hole, or arming the race would
    // shrink the stage, which would shrink the band, which would... .
    const hole = computeHudLayout(w, h - railH, tileCount)
    if (!racing) return hole
    const band = Math.round(Math.min(hole.stage.w, hole.stage.h) * RACE_BAND)
    return computeHudLayout(w, h - railH, tileCount, band)
  }, [w, h, railH, tileCount, racing])

  /** Card indices on the board, in join order. Everything else is home. */
  const [staged, setStaged] = useState<number[]>(OPENING)
  /** Cards that moved on the last change, so only they get promoted. */
  const movers = useRef<Set<number>>(new Set())

  const [morphing, setMorphing] = useState(false)
  const morphTimer = useRef<number | undefined>(undefined)
  const [resettling, setResettling] = useState(false)

  const stagedSet = useMemo(() => new Set(staged), [staged])

  /** Where each staged card sits, in squares. Pure function of `staged`. */
  const placements = useMemo(() => {
    const packed = packStage(
      staged.map((i) => ({ id: slides[i].id, bias: slides[i].bias })),
    )
    const byId = new Map(packed.map((p) => [p.id, p.slot]))
    const bySlide = new Map<number, Slot>()
    for (const i of staged) {
      const slot = byId.get(slides[i].id)
      if (slot) bySlide.set(i, slot)
    }
    return bySlide
  }, [staged, slides])

  const beginMorph = useCallback((moved: Set<number>) => {
    movers.current = moved
    setMorphing(true)
    window.clearTimeout(morphTimer.current)
    morphTimer.current = window.setTimeout(() => setMorphing(false), MORPH_MS + 80)
  }, [])

  /** Send a card to the board, or home again if it is already there. */
  const toggle = useCallback(
    (i: number) => {
      // Belt and braces: the corner blocks have no click target and the walk
      // skips them, but nothing else should be able to stage one either.
      if (slides[i]?.decorative) return
      const prev = staged
      let next = prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]
      // A fifth card evicts the oldest rather than being refused. Refusing a
      // click in front of an audience looks like a broken deck.
      if (next.length > MAX_ON_STAGE) next = next.slice(next.length - MAX_ON_STAGE)
      beginMorph(new Set([...prev, ...next]))
      setStaged(next)
    },
    [staged, slides, beginMorph],
  )

  /** Replace the board with exactly one card — the linear-talk motion. */
  const only = useCallback(
    (i: number) => {
      if (staged.length === 1 && staged[0] === i) return
      beginMorph(new Set([...staged, i]))
      setStaged([i])
    },
    [staged, beginMorph],
  )

  const dirty = staged.length !== 1 || staged[0] !== OPENING[0]

  /**
   * Put the cards back. Cards ONLY — the feed, the followed run and the
   * connection are untouched.
   *
   * Snaps rather than animates: a reset can move every card at once, which is
   * the layer storm described above.
   */
  const reset = useCallback(() => {
    setResettling(true)
    setStaged(OPENING)
    movers.current = new Set()
    setMorphing(false)
    window.clearTimeout(morphTimer.current)
    requestAnimationFrame(() => requestAnimationFrame(() => setResettling(false)))
  }, [])

  useEffect(() => () => window.clearTimeout(morphTimer.current), [])

  // Arming the race re-lays-out every card at once, exactly as a viewport
  // change does, so it is taken in ONE frame with transitions suppressed
  // rather than animated. Twenty cards mid-transition is the layer storm.
  useLayoutEffect(() => {
    setResettling(true)
    const frame = requestAnimationFrame(() =>
      requestAnimationFrame(() => setResettling(false)),
    )
    return () => cancelAnimationFrame(frame)
  }, [w, h, racing])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // The walk steps through CARDS, not through slots: four of the twenty
      // slots are corner blocks, and a walk that stopped on one would put an
      // empty rectangle on the board in front of an audience.
      const n = CARD_SLOTS.length
      const current = staged[staged.length - 1] ?? HOME_SLOT
      const here = CARD_SLOTS.indexOf(current)
      const step = (d: number) => CARD_SLOTS[((here < 0 ? 0 : here) + d + n) % n]
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        e.preventDefault()
        only(step(1))
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault()
        only(step(-1))
      } else if (e.key === 'Home' || e.key === 'Escape') {
        only(HOME_SLOT)
      } else if (e.key === 'f') {
        if (document.fullscreenElement) void document.exitFullscreen()
        else void document.documentElement.requestFullscreen()
      } else if (/^[0-9]$/.test(e.key)) {
        // A digit addresses the Nth CARD in talk order — `1` is always the
        // home card. It no longer doubles as a ring position, because the
        // ring now has slots that are not cards. It toggles rather than
        // replaces.
        const nth = e.key === '0' ? 9 : Number(e.key) - 1
        if (nth < n) toggle(CARD_SLOTS[nth])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [staged, only, toggle])

  return (
    <RaceProvider value={race}>
      <div className="vignette relative h-full w-full overflow-hidden bg-bg">
        <div className="pixel-grid pointer-events-none absolute inset-0 opacity-40" />

        {/* The container. Behind everything on the board. */}
        <StageContainer layout={layout} />

        {/* The race, in the band the stage gave up. Mounted always so it has
          something to fade from; it is a 1px band at opacity 0 when idle. */}
        <Racetrack
          outer={layout.stageOuter}
          inner={layout.stage}
          radius={STAGE_RADIUS}
          visible={racing}
        />

        {/* A ghost marks the home of every card currently on the board. */}
        {staged.map((i) =>
          layout.tiles[i] ? (
            <Ghost
              key={`ghost-${slides[i].id}`}
              rect={layout.tiles[i]}
              title={slides[i].title}
              accent={slides[i].accent}
              onClick={() => toggle(i)}
            />
          ) : null,
        )}

        {slides.map((slide, i) => {
          const onStage = stagedSet.has(i)
          const footprint = placements.get(i)
          const rect: Rect | null = onStage
            ? footprint
              ? gridRect(
                  layout,
                  footprint.col,
                  footprint.row,
                  footprint.w,
                  footprint.h,
                )
              : null
            : (layout.tiles[i] ?? null)
          if (!rect) return null

          const scale = scaleFor(rect)
          const canvas = canvasFor(rect)
          const { Component } = slide
          const moving = morphing && movers.current.has(i)
          // A corner block is scenery: no click target, no keyboard stop, no
          // accessible name. It is a rectangle of colour holding the frame
          // square, and offering to stage it would be offering nothing.
          const solid = slide.decorative === true
          const press = solid ? undefined : () => toggle(i)

          return (
            <div
              key={slide.id}
              role={solid ? 'presentation' : 'button'}
              aria-hidden={solid || undefined}
              tabIndex={solid ? -1 : 0}
              aria-label={
                solid
                  ? undefined
                  : `${slide.title}${onStage ? ' (on the board)' : ''}`
              }
              aria-pressed={solid ? undefined : onStage}
              onClick={press}
              onKeyDown={(e) => {
                if (!solid && e.key === 'Enter') toggle(i)
              }}
              className="absolute left-0 top-0 origin-top-left outline-none"
              style={{
                ['--slide-scale' as string]: String(scale),
                // The canonical size that lands at 12pt once this card's
                // transform is applied. Cards floor every font size against
                // it — see lib/type.ts. Zero at home: a 276x155 tile holds
                // about seven words at 12pt, so tiles stay textures.
                ['--type-floor' as string]: onStage
                  ? `${MIN_TYPE_PX / scale}px`
                  : '0px',
                width: canvas.w,
                height: canvas.h,
                transform: `translate(${rect.x}px, ${rect.y}px) scale(${scale})`,
                transition: resettling ? 'none' : `transform ${MORPH}`,
                zIndex: onStage ? 40 : 10,
                cursor: solid ? 'default' : 'pointer',
                willChange: moving ? 'transform' : undefined,
                contain: 'layout',
              }}
            >
              <Component onStage={onStage} scale={scale} footprint={footprint} />
            </div>
          )
        })}

        <StatusRail
          onReset={reset}
          resetEnabled={dirty}
          onSource={onSource}
          sourceLocked={sourceLocked}
        />
      </div>
    </RaceProvider>
  )
}
