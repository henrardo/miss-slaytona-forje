/**
 * The home card.
 *
 * No header bar: the wordmark IS the title, and a second copy of the name in
 * VT323 above it only competed with it. `SlideChrome` still gets the title —
 * the registry and the ghost sockets use it — but nothing draws it, and the
 * card is named to a screen reader by the wordmark's own `role="img"`.
 *
 * Two thirds wordmark, one third follow line. A proportion, not a pixel value,
 * so it holds whether the card is the whole stage, a quarter of it, or a tile.
 *
 * ── When the card goes portrait, the lettering leaves ────────────────────
 *
 * The lockup is lettering beside a character, and that only works while the
 * card is wider than it is tall. Her sprite is 34x48 — aspect 0.708 — so in the
 * 46% column she fills the card's height only while `W/H >= 1.54`; narrower
 * than that she simply gets smaller (see `object-fit` in Slaytona.tsx, which is
 * what stopped her being squashed), and by the time the card stops being
 * landscape at all there is no honest way to set three lines of display type
 * beside her. So at `W/H < 1` the lettering slides out to the left and she
 * takes the whole card. She is the one that stays: the wordmark is legible in
 * the ring tile and on the board, whereas a 4-square-wide sliver of "Slaytona"
 * is not, and she is the thing the card is for.
 *
 * The lettering is translated out, not unmounted — the wordmark's `role="img"`
 * is this headerless card's accessible name, and opacity-0 content is still in
 * the a11y tree. Slay moves rather than leaves, for the same reason: the card
 * can be on stage in a tall slot mid-talk, and the one control on it must not
 * become unreachable because of how the packer arranged the board.
 */
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { Wordmark } from '@/wordmark/Wordmark'
import { Slaytona } from '@/character/Slaytona'
import { useRace } from '@/hud/RaceMode'
import { FLOWER_PINK, NEON_PINK, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

/** The wordmark's own face, so the lockup reads as one piece of lettering. */
const FAB = "'Shrikhand', system-ui, sans-serif"
/** Largest the follow line may be set, in canonical units. */
const FOLLOW_MAX = 64
/** The split: lettering left, her right, while there is room for both. */
const LETTERING = '54%'
const HERS = '46%'
/** Below this width-over-height the lettering goes. See the note above. */
const SPLIT_AT = 1
/** Everything that moves when it does, so the pieces travel together. */
const GLIDE = '460ms cubic-bezier(0.4, 0, 0.2, 1)'

/**
 * Is this card's body taller than it is wide?
 *
 * Measured, not inferred from `footprint`: the card is also rendered at home in
 * the ring and inside a transition between slots, and the only thing that is
 * true in all three is the box it currently occupies. Layout px here are
 * canonical units — the Hud's scale is uniform, so it cancels in the ratio.
 */
function usePortrait(ref: RefObject<HTMLElement>): boolean {
  const [portrait, setPortrait] = useState(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const read = () => {
      const { clientWidth: w, clientHeight: h } = el
      if (w > 0 && h > 0) setPortrait(w / h < SPLIT_AT)
    }
    read()
    // Fires all through a re-pack; React drops the identical states, so the
    // flip happens once, as the box crosses square.
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return portrait
}

/**
 * One line of type, scaled to the width it is given and never wrapped.
 *
 * Same trick the wordmark uses, and for the same reason: measure the LAYOUT
 * width (`offsetWidth`, immune to the transform about to be applied), scale,
 * then size the wrapper to the scaled ink so the box matches what is drawn — a
 * transform changes what is painted, not the space it occupies.
 *
 * Fitting rather than picking a font size is what keeps the follow line on one
 * line. Set at a fixed size it wrapped to two, which put "Stacks" on its own
 * line directly under the wordmark and read as a fourth title line.
 */
function FitLine({
  max,
  children,
  style,
}: {
  max: number
  children: ReactNode
  style?: React.CSSProperties
}) {
  const host = useRef<HTMLDivElement>(null)
  const ink = useRef<HTMLSpanElement>(null)
  const [fit, setFit] = useState(0)
  const [nat, setNat] = useState({ w: 0, h: 0 })

  const measure = useCallback(() => {
    const h = host.current
    const i = ink.current
    if (!h || !i) return
    const natural = i.offsetWidth
    const avail = h.clientWidth
    if (natural <= 0 || avail <= 0) return
    setNat({ w: natural, h: i.offsetHeight })
    setFit(Math.min(1, avail / natural))
  }, [])

  useLayoutEffect(() => {
    measure()
    void document.fonts?.ready.then(measure)
    const ro = new ResizeObserver(measure)
    if (host.current) ro.observe(host.current)
    return () => ro.disconnect()
  }, [measure, children])

  return (
    <div ref={host} style={{ width: '100%', minWidth: 0 }}>
      <div
        style={{
          position: 'relative',
          width: nat.w ? nat.w * fit : undefined,
          height: nat.h ? nat.h * fit : undefined,
        }}
      >
        <span
          ref={ink}
          style={{
            ...style,
            position: 'absolute',
            left: 0,
            top: 0,
            display: 'block',
            fontSize: max,
            lineHeight: 1,
            whiteSpace: 'nowrap',
            transform: `scale(${fit})`,
            transformOrigin: 'left top',
            // Hidden until measured: the unscaled line is wider than the card
            // and would flash across it on the first frame.
            visibility: fit ? 'visible' : 'hidden',
          }}
        >
          {children}
        </span>
      </div>
    </div>
  )
}

/**
 * Arms the race. Part of the card, not the chrome.
 *
 * Two things it has to get right, both about living inside a card:
 *
 * 1. `stopPropagation`. The whole card is a click target — clicking it sends it
 *    to the board or home again. Without this, arming the race would also
 *    bounce the card, which is not what pressing Slay means.
 *
 * 2. It is INERT off-stage. The card is mounted at all times, including as a
 *    ~10px tile in the ring, and a tile's job is to answer a click by joining
 *    the board. So the button only takes clicks when the card is on stage;
 *    everywhere else it is drawn but transparent to the pointer.
 *
 * Sized in canonical units like everything else on a card, so it scales with
 * whatever box the card is given rather than being pinned to screen pixels.
 */
function SlayButton({ live }: { live: boolean }) {
  const { racing, slay } = useRace()
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        slay()
      }}
      aria-pressed={racing}
      title="Race the two arms around the board. Display only — it does not start a run."
      style={{
        alignSelf: 'flex-start',
        fontFamily: FAB,
        fontSize: 58,
        lineHeight: 1,
        padding: '18px 44px 24px',
        letterSpacing: '0.03em',
        borderRadius: 12,
        border: `2px solid ${racing ? alpha(NEON_PINK, 0.45) : NEON_PINK}`,
        // Dimmed while it is running: the call to action has been answered, so
        // it stops asking. Lit and filled when there is still a button to press.
        color: racing ? alpha(FLOWER_PINK.light, 0.55) : '#1a1730',
        background: racing ? 'transparent' : FLOWER_PINK.light,
        boxShadow: racing ? 'none' : `0 0 40px ${alpha(NEON_PINK, 0.45)}`,
        opacity: racing ? 0.55 : 1,
        cursor: 'pointer',
        pointerEvents: live ? 'auto' : 'none',
        transition:
          'background 220ms, color 220ms, opacity 220ms, box-shadow 220ms',
      }}
    >
      {racing ? 'Slaying...' : 'Slay'}
    </button>
  )
}

export function TitleSlide({ onStage }: SlideProps) {
  const body = useRef<HTMLDivElement>(null)
  const portrait = usePortrait(body)

  return (
    <SlideChrome
      title="Miss Slaytona Fourje"
      accent={NEO4J.periwinkle}
      focused={onStage}
      header={false}
      footer={<span>Mistral · SGLang · Daytona · Neo4j</span>}
    >
      <div ref={body} className="relative h-full w-full">
        {/* Lettering left. 54% was chosen to leave her room, and still does —
            while the card is landscape. Off the left edge when it is not; the
            card clips, so it leaves rather than piles up in the corner. */}
        <div
          className="absolute inset-y-0 left-0 flex flex-col"
          style={{
            width: LETTERING,
            transform: portrait ? 'translateX(-108%)' : 'translateX(0)',
            opacity: portrait ? 0 : 1,
            pointerEvents: portrait ? 'none' : undefined,
            transition: `transform ${GLIDE}, opacity 300ms`,
          }}
        >
          <div style={{ flex: '2 1 0', minHeight: 0 }}>
            <Wordmark maxCap={108} distribute />
          </div>
          {/* Name, then tagline, then the one thing to press. */}
          <div
            className="flex flex-col justify-center"
            style={{ flex: '1 1 0', gap: 40 }}
          >
            <FitLine
              max={FOLLOW_MAX}
              style={{
                fontFamily: FAB,
                letterSpacing: '0.02em',
                color: NEO4J.cream,
                // A whisper of the wordmark's neon, no outline. The follow line
                // answers the name; it does not compete with it.
                textShadow: `0 0 26px ${alpha(FLOWER_PINK.light, 0.3)}`,
              }}
            >
              ... and Her Racy AI Stacks
            </FitLine>
            {portrait ? null : <SlayButton live={onStage} />}
          </div>
        </div>

        {/* Her. Beside the lettering at full card height, the whole card when
            the lettering has gone. Right-aligned in the split rather than
            centred because the graph she summons materialises on her LEFT —
            it opens toward the wordmark instead of off the edge of the card. */}
        <div
          className="absolute inset-y-0 right-0"
          style={{
            width: portrait ? '100%' : HERS,
            paddingLeft: portrait ? 0 : 24,
            transition: `width ${GLIDE}, padding-left ${GLIDE}`,
          }}
        >
          <Slaytona align={portrait ? 'center' : 'right'} />
        </div>

        {/* Slay, rehomed rather than lost. Above her, but she is transparent
            canvas out to her silhouette, so it reads as sitting on the floor
            beside her. */}
        {portrait ? (
          <div className="absolute bottom-0 left-0 z-10">
            <SlayButton live={onStage} />
          </div>
        ) : null}
      </div>
    </SlideChrome>
  )
}
