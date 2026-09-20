# Brand asset provenance

Every file here, where it came from, and whether it was modified. Third-party
marks remain the property of their owners; they are used to identify the
components of the stack this deck describes.

| file | source | modified |
|---|---|---|
| `neo4j-logo-cream.svg` | `neo4j-graphacademy/monorepo` → `apps/web/public/brand/logos/neo4j-logo-cream.svg`. **This is the one the deck uses** — the official reversed logo for dark surfaces, single fill `#FCF9F6`. | no |
| `neo4j-logo-color.svg` | same directory, `neo4jLogoColor.svg` | no |
| `neo4j-letter.svg` | same directory, `neo4jLetter.svg` — the mark alone | no |
| `neo4j-logo.svg` | `https://dist.neo4j.com/wp-content/uploads/20230926084108/Logo_FullColor_RGB_TransBG.svg` — kept for the light-background case | no |
| `mistral-icon.svg` | `https://mistral.ai/cms-media/api/media/file/2a1ffaf3-f171-460b-be1b-fc734aa776aa.svg`, linked from mistral.ai/brand | no |
| `mistral-model-small.svg` | `https://mistral.ai/cms-media/api/media/file/Icon-Model-Small.svg` | no |
| `mistral-model-codestral.svg` | `.../Icon-Model-Codestral.svg` | no |
| `mistral-model-magistral.svg` | `.../Icon-Model-Magistral.svg` | no |
| `mistral-model-large.svg` | `.../Icon-Model-Large 3.svg` | no |
| `sglang-logo.svg` | `https://raw.githubusercontent.com/sgl-project/sglang/main/assets/logo.svg` | no |
| `sglang-logo-square.svg` | `.../assets/logo_square.svg` | no |
| `daytona-logotype-white.png` | `https://raw.githubusercontent.com/daytonaio/daytona/main/assets/images/Daytona-logotype-white.png` | no |
| `daytona-logotype-black.png` | `.../Daytona-logotype-black.png` | no |

## Colour values

In `src/lib/brand.ts`, each with its source on the line. Summary:

- **Neo4j** — from `neo4j-graphacademy/monorepo` →
  `packages/ui/src/styles.css`, the palette their shipping product renders.
  Named brand colours (`--n4j-baltic #014063`, `--n4j-light-baltic #8fe3e8`,
  `--n4j-cream #fcf9f6`, `--n4j-periwinkle #6a82ff`, `--n4j-hibiscus #f96746`,
  `--n4j-marigold #f5b642`, `--n4j-forest #145439`) with their own comments and
  measured contrast ratios. Cross-checks against `@neo4j-ndl/base@4.21.1`
  (Needle): `baltic-20`/`baltic-60` agree exactly.
- **Mistral** — extracted from the official pixel icon SVGs above. The flame
  ramp `#fec63a → #ffaf00 → #ff8205 → #fa500f → #e92700` recurs across the set.
- **SGLang** — extracted from `assets/logo.svg`: `#a5300f` dominant, `#d55816`
  mid, `#faddcd` pale.
- **Daytona** — read from daytona.io's live stylesheet: `#00bbff`, `#0099ff`,
  with `#ff3366` as the site's warm accent. Daytona publish logotypes but no
  hex list, so **this one is a site scrape, not a brand-book value.**

## Not obtained

**Mistral's M lockup/icon as a file.** mistral.ai/brand links these from
`cms.globalaegis.net`, which this environment's network policy blocks:

```
https://cms.globalaegis.net/api/documents/file/Mistral_Brandkit_2026.zip
https://cms.globalaegis.net/api/documents/file/Mistral_Logos_2026.zip
https://cms.globalaegis.net/api/documents/file/Mistral-Lockup-Gradient-RGB.png
https://cms.globalaegis.net/api/documents/file/Mistral-Icon-Gradient-RGB.png
```

Download any of those by hand into this directory and point `BRANDS.mistral.logo`
at it. The colour values do not depend on it — they came from the SVGs
mistral.ai serves directly.

## Fonts

Self-hosted on purpose: a CDN font that fails to load on conference wifi takes
the whole visual identity with it.

| file | source | licence |
|---|---|---|
| `fonts/syne-neo/SyneNeo-{Medium,SemiBold,Bold}.woff2` | `neo4j-graphacademy/monorepo` → `apps/web/public/fonts/syne-neo/` | **Neo4j proprietary** |
| `fonts/vt323-*.woff2` | Google Fonts | SIL Open Font License |
| `fonts/shrikhand-latin{,-ext}.woff2` | Google Fonts v17 (Jonny Pinhorn) | SIL Open Font License 1.1 |

**Shrikhand** is the wordmark face, and it was chosen by test rather than by
taste: the actual wordmark — brand marks and all — was rendered in twelve
candidates at matched cap height on the deck's own ground, and compared.
Shrikhand, Abril Fatface, Rozha One, Lobster Two, Righteous, Bungee, Monoton,
Yeseva One, Pacifico, Bowlby One SC, Rampart One, Bodoni Moda. It won on three
things that are checkable rather than felt:

- **It has real lowercase.** Bungee, Monoton and Bowlby One SC are caps-only
  faces, and "MISS SLAYTONA FOURJE" loses the ascender/x-height rhythm the
  three-line stack is built on.
- **It is fat enough to hold an outline.** The neon stroke is 2.4% of cap; on
  Bodoni Moda and Yeseva One that is wider than the hairlines, so the outline
  swallows the letter instead of edging it.
- **It has enough swagger to sit beside SGLang's swashed L** without reading
  as a caption. Righteous and Abril Fatface are the sober ones; the wordmark is
  a drag name.

Its x-height is unusually tall (0.794 of cap), which is also why the two
pictograms standing in for lowercase letters — Daytona's glyph as the 'o', the
graph mark as the 'e' — sit comfortably against it.

**Syne Neo is Neo4j's own display cut, not Google's Syne** — the two are
different faces and the Google one is not a substitute. Weights are declared
exactly as Neo4j declare them (`apps/cup/app/globals.css`). Headings use 600
rather than 700 on their own guidance: *"Syne semi-bold — bold reads too
heavy/stretched at display sizes"* (`packages/ui/src/styles.css`).

Because Syne Neo is proprietary rather than OFL, it is fine bundled in an
internal talk deck but must not be redistributed if this repo is ever made
public. Cinzel (OFL) was the previous display face and would be the drop-in
if that ever matters.
