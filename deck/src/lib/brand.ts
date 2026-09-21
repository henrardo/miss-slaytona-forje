/**
 * Brand constants, each traced to where it was actually read from.
 *
 * Nothing here is recalled from memory. Every hex was extracted from an
 * official asset, an official design-token package, or Neo4j's own product
 * monorepo, and the source is named on the line. If a value needs changing,
 * re-derive it from the source rather than eyedropping a screenshot.
 */

export type BrandKey = 'neo4j' | 'mistral' | 'sglang' | 'daytona'

export interface Brand {
  key: BrandKey
  name: string
  /** What this component does in the stack. One line, for tile chrome. */
  role: string
  /** Accent for rails, labels and tile edge on dark ground. */
  accent: string
  /** Deeper companion, for fills behind the accent. */
  deep: string
  /** Logo served from public/brand. */
  logo: string
  source: string
}

/**
 * Neo4j's brand palette, lifted verbatim from
 * `neo4j-graphacademy/monorepo` → `packages/ui/src/styles.css`, which is the
 * palette their shipping product actually renders. Comments are theirs,
 * including the measured contrast ratios.
 */
export const NEO4J = {
  baltic: '#014063', // primary brand blue
  darkBaltic: '#012437', // deepest trusted color; dark-mode page base
  midBaltic: '#4c99a4', // transitional teal
  lightBaltic: '#8fe3e8', // airy digital accent; dark-mode primary
  cream: '#fcf9f6', // default page background / reversed logo fill
  darkCream: '#f2ead4',
  black: '#181414', // warm near-black
  forest: '#145439', // brand green
  midForest: '#4a8e57',
  lightForest: '#b6d4ae',
  hibiscus: '#f96746', // warm accent
  marigold: '#f5b642', // golden accent
  periwinkle: '#6a82ff', // electric violet-blue — 3.2:1 on cream, never body text
  deepPeriwinkle: '#4353c4',
  lightPeriwinkle: '#9aa9ff', // periwinkle for text on dark — 6.2:1 on card
  yellowHl: '#ffeb6a',
  /** Dark-mode surfaces, from the same file's `.dark` block. */
  surfaceDark: '#01304d',
  surfaceElevated: '#013a5a',
} as const

/**
 * Mistral's flame, in order, extracted from the official pixel model icons
 * served at mistral.ai/cms-media. Their brand system renders models as pixel
 * characters "designed to shine at small scale" — which is the tile problem
 * exactly, so the deck borrows the principle rather than the art.
 */
export const MISTRAL_FLAME = [
  '#fec63a',
  '#ffaf00',
  '#ff8205',
  '#fa500f',
  '#e92700',
] as const

/**
 * The pinks in Mistral Small's pixel flower, read straight out of the icon's
 * own `fill` attributes (src/wordmark/glyphs/mistral-flower.svg). The flower
 * stands in for the 'i' in the wordmark, so the lettering around it borrows its
 * colour rather than inventing one.
 */
export const FLOWER_PINK = {
  light: '#ff92dc', // the petal highlight — the wordmark's fill
  magenta: '#ce1493', // the petal body
  deep: '#83075c', // the shadowed petals
} as const

/**
 * Neon pink, derived rather than picked: `FLOWER_PINK.magenta` is hsl(319, 82%,
 * 44%), and this is that SAME hue at full saturation and neon lightness —
 * hsl(319, 100%, 53%). It reads as the lit version of a colour already in the
 * artwork, which is what makes an outline around `FLOWER_PINK.light` look like
 * a tube rather than a border.
 */
export const NEON_PINK = '#ff0fb3'

export const BRANDS: Record<BrandKey, Brand> = {
  neo4j: {
    key: 'neo4j',
    name: 'Neo4j',
    role: 'shared memory graph — warm arm only',
    accent: NEO4J.lightBaltic,
    deep: NEO4J.baltic,
    logo: '/brand/neo4j-logo-cream.svg',
    source: 'neo4j-graphacademy/monorepo packages/ui/src/styles.css',
  },
  mistral: {
    key: 'mistral',
    name: 'Mistral',
    role: 'Mistral Small 4 — the model under test',
    accent: '#ff8205',
    deep: '#e92700',
    logo: '/brand/mistral-icon.svg',
    source: 'mistral.ai/brand official icon SVGs (flame ramp)',
  },
  sglang: {
    key: 'sglang',
    name: 'SGLang',
    role: 'serving the model on a RunPod H200',
    accent: '#d55816',
    deep: '#a5300f',
    logo: '/brand/sglang-logo.svg',
    source: 'sgl-project/sglang assets/logo.svg',
  },
  daytona: {
    key: 'daytona',
    name: 'Daytona',
    role: 'the only success oracle — pytest in a clean sandbox',
    accent: '#00bbff',
    deep: '#0099ff',
    logo: '/brand/daytona-logotype-white.png',
    source: 'daytona.io stylesheet (site scrape — not a published brand book)',
  },
}

export const BRAND_ORDER: BrandKey[] = ['neo4j', 'mistral', 'sglang', 'daytona']

/**
 * The deck's own accent rotation, for slides that are not about a vendor.
 *
 * Every value is from Neo4j's palette, so nothing here fights the brand — but
 * the ordering leads with periwinkle and treats marigold and hibiscus as
 * punctuation. It replaced a rotation through Mistral's flame ramp, which had
 * the side effect of tinting two thirds of the HUD rust and made the whole
 * thing read as a terminal.
 *
 * Periwinkle appears first and third so it stays dominant around the ring.
 */
export const WHIMSY = [
  NEO4J.periwinkle,
  NEO4J.lightPeriwinkle,
  NEO4J.lightForest,
  NEO4J.periwinkle,
  NEO4J.yellowHl,
  NEO4J.lightPeriwinkle,
] as const

export const whimsyAt = (i: number) => WHIMSY[i % WHIMSY.length]

/**
 * SGLang's rust and Mistral's flame are genuinely adjacent hues — a fact about
 * the two brands, not a palette bug. They are separated by lightness (#d55816
 * vs #ff8205) and never placed adjacent without their logo present.
 */
export const ADJACENT_HUE_PAIRS: [BrandKey, BrandKey][] = [['sglang', 'mistral']]

/**
 * Arm identity. The entire talk turns on telling these two apart at a glance,
 * so they are separated by HUE, not lightness — a badly calibrated projector
 * flattens lightness long before it flattens hue.
 *
 * Cyan (183°) against gold (41°) is ~140° apart and near-complementary.
 *
 * WARM IS GOLD. It used to be cyan — "because it is the arm with the Neo4j
 * graph" — and that reasoning is about the implementation, not about what the
 * audience has been taught. By the time any chart appears they have seen the
 * Warm card in a marigold frame, the Cold card in blue, and both counts on
 * Tokens head to head in those two colours. A chart that then drew warm in
 * cyan and cold in gold inverted the only colour key in the talk, on the one
 * card where the lines cross: cold's surface count dives to 0 and rebounds to
 * 365, and in gold that read as warm collapsing.
 *
 * The hue argument is untouched — still cyan against gold, still ~140° apart,
 * still separated by hue rather than lightness because a badly calibrated
 * projector flattens lightness first. Only the mapping moved.
 *
 * Deliberately NOT periwinkle for cold: periwinkle is the deck's chrome accent
 * and is all over the HUD, so an arm wearing it would read as "the default"
 * rather than as one side of a comparison. For the same reason marigold and
 * light baltic stay out of WHIMSY — in a data context those two colours mean
 * one thing each, and nothing else may borrow them.
 */
export const ARM_COLOR = {
  warm: NEO4J.marigold,
  cold: NEO4J.lightBaltic,
} as const

/** Reserved for failure and confound warnings. Never decorative. */
export const ALARM = NEO4J.hibiscus

/**
 * `#rrggbb` + 0..1 alpha -> `#rrggbbaa`.
 *
 * Exists because the obvious shorthand is a trap. Accents are interpolated
 * into box-shadows and gradients, and `${accent}44` only works when `accent`
 * is a six-digit hex literal. Hand it `var(--periwinkle)` or `hsl(var(--x))`
 * and you get `var(--periwinkle)44`, which is not a colour — so the browser
 * discards the WHOLE declaration and the border, gradient or glow silently
 * vanishes. That shipped for two passes: the title, feed and stack slides had
 * no border and no glow, and nothing anywhere said so.
 *
 * Accents are therefore hex literals, and this is the only way to fade one.
 */
/**
 * Rewrite a colour's HUE, keeping its saturation and lightness exactly.
 *
 * Exists so the cold racer can be "the Mistral M, in blue" rather than a
 * second drawing: the flame ramp's five stops keep their own value structure —
 * which is what makes the M read as shaded pixel art rather than a flat
 * silhouette — and only the hue moves. Rotating by a fixed amount instead
 * would not do: the flame spans amber to dark red, and a constant rotation
 * lands the dark end in green.
 */
export function withHue(hex: string, hue: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const r = (n >> 16) / 255
  const g = ((n >> 8) & 255) / 255
  const b = (n & 255) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  const d = max - min
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1))

  const h = (((hue % 360) + 360) % 360) / 60
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h % 2) - 1))
  const lo = l - c / 2
  const [rr, gg, bb] =
    h < 1
      ? [c, x, 0]
      : h < 2
        ? [x, c, 0]
        : h < 3
          ? [0, c, x]
          : h < 4
            ? [0, x, c]
            : h < 5
              ? [x, 0, c]
              : [c, 0, x]
  const byte = (v: number) =>
    Math.round(Math.max(0, Math.min(1, v + lo)) * 255)
      .toString(16)
      .padStart(2, '0')
  return `#${byte(rr)}${byte(gg)}${byte(bb)}`
}

export function alpha(hex: string, a: number): string {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) {
    if (import.meta.env.DEV) {
      console.warn(
        `[brand] alpha() needs a #rrggbb literal, got "${hex}". ` +
          `Accents must not be CSS variables — see the note on alpha().`,
      )
    }
    return hex
  }
  const byte = Math.round(Math.max(0, Math.min(1, a)) * 255)
  return hex + byte.toString(16).padStart(2, '0')
}
