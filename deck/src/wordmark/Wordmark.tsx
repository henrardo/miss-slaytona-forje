/**
 * "Miss Slaytona Fourje" — a portmanteau wordmark built out of the four
 * brands it names, set as three stacked, left-aligned lines.
 *
 *   Mi ss      M = Mistral's pixel icon, i = the Mistral Small pixel flower
 *   Sl aytona  S and the swashed L from the SGLang logo, o = Daytona's glyph
 *   Fourj e    e = Neo4j's graph mark, reversed
 *
 * ── Logos are artwork; everything else is type ───────────────────────────
 *
 * Six pieces are BRAND MARKS and keep their own colour and drawing: M, the
 * flower, S, L, the Daytona glyph, the graph mark. Every remaining character
 * is set in ONE face — Shrikhand — in the flower's own pink, with a neon
 * outline of the same hue.
 *
 * An earlier version cut the letters out of each brand's logotype too, so
 * "ss" was Mistral's 's' and "aytona" was Daytona's letters. Four type designs
 * in one word is a ransom note however carefully it is aligned, and it left the
 * lettering unable to carry a colour of its own. Those glyphs are still in
 * ./glyphs and scripts/extract-wordmark.mjs still produces them, so the
 * decision is reversible; they are simply not imported any more.
 *
 * ── It is set like a font, not assembled like a collage ──────────────────
 *
 * ONE tracking value, applied as flex `gap`, between every pair on every
 * line — a mark standing in for a letter is spaced exactly as a letter is.
 * There are no per-pair nudges; if a join looks wrong the fix is the mark's
 * crop or its size, never a one-off margin.
 *
 * Vertical placement is likewise computed. The row is a fixed cap-height box
 * with `align-items: flex-end`, and every piece has had its bottom margin edge
 * put ON the baseline — artwork by the `drop` it was measured with, text by
 * BASELINE_FROM_BOTTOM. So aligning bottom edges IS baseline alignment, and it
 * is one rule for all of them.
 *
 * ── Two things that bit, both now structural ─────────────────────────────
 *
 * 1. Marks are imported, NOT served from `public/`. Vite content-hashes them,
 *    so re-running the extractor can never leave a browser showing yesterday's
 *    artwork. It did exactly that once: the letters had been recoloured to
 *    cream on disk and still rendered black. Imports are explicit rather than
 *    an `import.meta.glob`, so the retired letter glyphs sitting in the same
 *    folder are not silently bundled.
 *
 * 2. Colour is BAKED INTO each SVG. An `<img>`-loaded SVG is an isolated
 *    document, so `currentColor` resolves against its own root and comes out
 *    black, silently. The extractor writes an explicit fill.
 */
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { alpha, FLOWER_PINK, NEON_PINK } from '@/lib/brand'
import mistralM from './glyphs/mistral-M.svg?url'
import mistralFlower from './glyphs/mistral-flower.svg?url'
import sglangS from './glyphs/sglang-S.svg?url'
import sglangL from './glyphs/sglang-L.svg?url'
import daytonaGlyph from './glyphs/daytona-glyph.svg?url'
import neo4jMark from './glyphs/neo4j-mark.svg?url'

/**
 * Shrikhand, measured in the browser from `TextMetrics`, not assumed:
 *   cap / em = 0.666   x / em = 0.529   ascent / em = 1.026   descent / em = 0.432
 */
const FAB = "'Shrikhand', system-ui, sans-serif"
const FAB_CAP = 0.666
const FAB_X = 0.529
const FAB_ASCENT = 1.026
const FAB_DESCENT = 0.432

/**
 * Where a span's baseline sits above its own bottom edge, as a fraction of
 * font-size, with `line-height: 1`.
 *
 * Half-leading is `(1 - (ascent + descent)) / 2` — negative here, because the
 * face's ascent and descent sum to 1.458em. That makes the distance from the
 * bottom of the line box up to the baseline `(1 - ascent + descent) / 2`.
 * Pulling the span down by exactly this puts its bottom margin edge ON the
 * baseline, which is what every extracted mark already does.
 */
const BASELINE_FROM_BOTTOM = (1 - FAB_ASCENT + FAB_DESCENT) / 2

/**
 * x-height in cap units — 0.794. The two marks that stand in for lowercase
 * letters (Daytona's 'o', the graph mark as 'e') are sized to this, so they
 * track the lettering instead of a number typed in by hand. Shrikhand has a
 * tall x-height, which is part of why it sits well with the pictograms.
 */
const X = FAB_X / FAB_CAP

/** Reference cap everything is laid out at before being fitted. */
const CAP = 200
/** The single tracking value. Every gap on every line. */
const TRACK = 0.055 * CAP
/**
 * Leading between the three lines; baseline to baseline is CAP + this.
 *
 * MIN is the set-tight default. Under `distribute` the leading opens up until
 * the block fills the height it has been given, which is a different thing from
 * scaling the type: the cap stays where it was put and the lines simply breathe.
 *
 * MAX is the reason `distribute` centres rather than fills. Solving for the
 * height exactly put 1.29 cap between the lines, and at that setting the three
 * lines stopped reading as one phrase — they read as three. 0.7 cap is the
 * widest that still holds together, so past that the block takes the height it
 * wants and sits in the middle of what it was given.
 */
const LEAD_MIN = 0.26 * CAP
const LEAD_MAX = 0.7 * CAP

/**
 * How far Shrikhand's deepest descender ('j', 0.19em) falls below the baseline,
 * in cap units. The rows are fixed cap-height boxes, so a descender paints
 * outside its row — this is the allowance that keeps it inside the block's own
 * layout box instead of hanging into whatever sits below the wordmark.
 */
const DESCENDER = 0.19 / FAB_CAP

/** Block height for a given leading. Analytic, because the rows are fixed. */
const blockHeight = (lead: number) => 3 * CAP + 2 * lead + DESCENDER * CAP

/**
 * The neon treatment, in cap units so it scales with the type — an outline is
 * part of a letterform, unlike the card glow in SlideChrome, which is pinned to
 * screen pixels because it is part of the frame.
 *
 * `paint-order: stroke fill` matters: without it the stroke is centred on the
 * outline and eats half the counter, which at 2.4% visibly fattens Shrikhand's
 * thin strokes. With it the stroke goes down first and the fill covers its
 * inner half, so the whole width reads outside the letter and stays "slight".
 */
const STROKE = 0.024 * CAP
const GLOW = 0.18 * CAP

type Piece =
  | {
      kind: 'mark'
      src: string
      alt: string
      /** Height as a fraction of cap. */
      h: number
      /** Intrinsic width / height of the artwork. */
      aspect: number
      /** How far it hangs below the baseline, as a fraction of cap. */
      drop?: number
      flip?: boolean
    }
  | { kind: 'text'; text: string }

const LINES: Piece[][] = [
  [
    { kind: 'mark', src: mistralM, alt: 'M', h: 1.0, aspect: 1.4 },
    { kind: 'mark', src: mistralFlower, alt: 'i', h: 1.0, aspect: 1 },
    { kind: 'text', text: 'ss' },
  ],
  [
    { kind: 'mark', src: sglangS, alt: 'S', h: 1, aspect: 0.798 },
    { kind: 'mark', src: sglangL, alt: 'l', h: 1.006, aspect: 0.78, drop: 0.003 },
    { kind: 'text', text: 'ayt' },
    // Their glyph as the 'o', at the x-height of the letters around it.
    { kind: 'mark', src: daytonaGlyph, alt: 'o', h: X, aspect: 0.9596 },
    { kind: 'text', text: 'na' },
  ],
  [
    { kind: 'text', text: 'Fourj' },
    // The graph mark standing in for the 'e', reversed. It is a substitution,
    // not a letterform. `./glyphs/neo4j-e.svg` is their actual logotype 'e' if
    // this reads as too abstract — swap the import, h: 1, aspect: 1.0435.
    { kind: 'mark', src: neo4jMark, alt: 'e', h: X, aspect: 0.8, flip: true },
  ],
]

function renderPiece(p: Piece, i: number) {
  if (p.kind === 'text') {
    const size = CAP / FAB_CAP
    return (
      <span
        key={i}
        style={{
          fontFamily: FAB,
          fontWeight: 400,
          fontSize: size,
          lineHeight: 1,
          // The same single tracking value as between the marks, so the
          // typeset runs are spaced identically to the assembled ones. The
          // negative right margin removes the trailing one letter-spacing
          // adds after the final character.
          letterSpacing: `${TRACK}px`,
          marginRight: -TRACK,
          // Put the span's bottom margin edge on the baseline, so it obeys
          // the same flex-end rule as the artwork. See the constant.
          marginBottom: -BASELINE_FROM_BOTTOM * size,
          color: FLOWER_PINK.light,
          WebkitTextStroke: `${STROKE}px ${NEON_PINK}`,
          paintOrder: 'stroke fill',
          // text-shadow, not a filter on the container: the halo belongs to
          // the lettering, and a container filter would put a pink bloom
          // around the brand marks as well.
          textShadow: `0 0 ${GLOW}px ${alpha(NEON_PINK, 0.35)}`,
          whiteSpace: 'nowrap',
        }}
      >
        {p.text}
      </span>
    )
  }
  const w = p.h * CAP * p.aspect
  const h = p.h * CAP
  return (
    <img
      key={i}
      src={p.src}
      alt=""
      aria-hidden
      width={w}
      height={h}
      style={{
        width: w,
        height: h,
        marginBottom: -(p.drop ?? 0) * CAP,
        display: 'block',
        transform: p.flip ? 'scaleX(-1)' : undefined,
      }}
    />
  )
}

export interface WordmarkProps {
  /** Largest cap height to use, in canonical units. */
  maxCap?: number
  /**
   * Open the leading until the three lines fill the host's height. Off by
   * default: a wordmark in a box of unknown height should set itself tight.
   */
  distribute?: boolean
  className?: string
}

export function Wordmark({
  maxCap = 120,
  distribute = false,
  className,
}: WordmarkProps) {
  const host = useRef<HTMLDivElement>(null)
  const ink = useRef<HTMLDivElement>(null)
  const [fit, setFit] = useState(1)
  const [lead, setLead] = useState(LEAD_MIN)
  /** Unscaled ink size, so the layout box can be made to match the drawn one. */
  const [nat, setNat] = useState({ w: 0, h: 0 })

  /**
   * `offsetWidth`, not `getBoundingClientRect()`. Layout width is wanted, and
   * it is immune to the transform about to be applied — so this measures once
   * and stays stable rather than chasing its own tail. The bounding rect is
   * wrong twice over: post-transform, and as a flex child it reports the width
   * the row was squeezed to rather than its content width.
   *
   * Only the WIDTH is measured. Leading is a column gap, so it cannot change
   * the block's width — which is what makes `distribute` safe: the fit is
   * settled from width first, then the leading is solved for the leftover
   * height. Measuring the height instead would be a feedback loop, since the
   * leading it produced would change the height it was read from.
   */
  const measure = useCallback(() => {
    const h = host.current
    const i = ink.current
    if (!h || !i) return
    const natural = i.offsetWidth
    const availW = h.clientWidth
    const availH = h.clientHeight
    if (natural <= 0 || availW <= 0) return
    const f = Math.min(maxCap / CAP, availW / natural)
    const l =
      distribute && availH > 0
        ? Math.min(LEAD_MAX, Math.max(LEAD_MIN, (availH / f - blockHeight(0)) / 2))
        : LEAD_MIN
    setFit(f)
    setLead(l)
    setNat({ w: natural, h: blockHeight(l) })
  }, [maxCap, distribute])

  useLayoutEffect(() => {
    measure()
    void document.fonts?.ready.then(measure)
    const ro = new ResizeObserver(measure)
    if (host.current) ro.observe(host.current)
    return () => ro.disconnect()
  }, [measure])

  return (
    <div
      ref={host}
      className={className}
      // minWidth:0 or a flex item refuses to go below its content size, and
      // clientWidth would report the wordmark rather than the room it has.
      //
      // Centred, not top-aligned: once the leading hits LEAD_MAX the block is
      // shorter than its box, and the leftover has to go somewhere. Splitting
      // it moves the first and last lines toward the middle one, which is what
      // makes the three read as a single phrase.
      style={{
        width: '100%',
        height: '100%',
        minWidth: 0,
        display: 'flex',
        alignItems: 'center',
      }}
    >
      {/* A transform scales what is painted but not the space it occupies, so
          the unscaled box would leave a block of dead air below the wordmark
          and defeat any attempt to centre it. This wrapper is sized to the
          SCALED ink, and the ink is taken out of flow inside it. */}
      <div
        style={{
          position: 'relative',
          width: nat.w ? nat.w * fit : undefined,
          height: nat.h ? nat.h * fit : undefined,
        }}
      >
        <div
          ref={ink}
          role="img"
          aria-label="Miss Slaytona Fourje"
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            width: 'max-content',
            flexShrink: 0,
            gap: lead,
            transform: `scale(${fit})`,
            transformOrigin: 'left top',
          }}
        >
          {LINES.map((line, n) => (
            <div
              key={n}
              style={{
                display: 'flex',
                // flex-end, not baseline: every piece here — artwork and text
                // alike — has had its bottom margin edge put ON the baseline,
                // so aligning bottom edges IS baseline alignment, and it is the
                // same rule for all of them.
                alignItems: 'flex-end',
                flexWrap: 'nowrap',
                gap: TRACK,
                // A FIXED baseline grid. Let the rows size to their content and
                // a descender on one line pushes every line below it down: the
                // three measured 147 / 158 / 222 tall, with leading of 185 then
                // 196. Pinning the height puts the baseline at the row's bottom
                // on every line, so baseline-to-baseline is exactly CAP + lead.
                height: CAP,
              }}
            >
              {line.map(renderPiece)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
