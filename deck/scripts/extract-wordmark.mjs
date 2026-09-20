import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const OUT = '/Users/t6w652j6ft/Documents/GitHub/miss-slaytona-forje/deck/src/wordmark/glyphs'
const HOME = process.env.HOME
const MB = `${HOME}/Downloads/Mistral_Brandkit_2026`
const DL = `${HOME}/Downloads/Daytona_Logo/Daytona - Brand svg`
const MR = `${HOME}/Documents/GitHub/monorepo/apps/web/public/brand`
const DECK = '/Users/t6w652j6ft/Documents/GitHub/miss-slaytona-forje/deck/public/brand'

// Per-source type metrics, measured from the wordmarks themselves (cap top and
// baseline of a known capital), so every extracted glyph can be placed on a
// shared baseline instead of nudged by eye.
const SOURCES = {
  mistral: { file: `${MB}/Mistral_Logos_2026/Lockup/Monochrome/RGB/SVG/Mistral-Lockup-White-RGB.svg`,
             capTop: 26, baseline: 156 },
  daytona: { file: `${DL}/Daytona Full Logo White.svg`, capTop: 15.5, baseline: 72.6 },
  sglang:  { file: `${DECK}/sglang-logo.svg`, capTop: 36.5, baseline: 694.5 },
  neo4j:   { file: `${MR}/logos/neo4jLogoColor.svg`, capTop: 8, baseline: 31 },
}

// NOTE: the four LETTER cuts below — mistral-s, daytona-a/y/t/n — are no
// longer used by the wordmark. It now sets every non-logo character in one
// face (Shrikhand); four type designs in one word read as a ransom note, and
// borrowed letterforms cannot take a colour of their own. They stay here, and
// on disk, because that decision is worth being able to reverse in one step.
// Wordmark.tsx imports its marks explicitly rather than globbing the folder,
// so nothing unused is bundled.
const JOBS = [
  { name: 'mistral-s',    src: 'mistral', leaves: [13], fill: '#FCF9F6' },
  { name: 'sglang-S',     src: 'sglang',  leaves: [10] },
  { name: 'sglang-L',     src: 'sglang',  leaves: [23, 24, 25, 26] },
  { name: 'daytona-a',    src: 'daytona', leaves: [9],  fill: '#FCF9F6' },
  { name: 'daytona-y',    src: 'daytona', leaves: [13], fill: '#FCF9F6' },
  { name: 'daytona-t',    src: 'daytona', leaves: [14], fill: '#FCF9F6' },
  { name: 'daytona-n',    src: 'daytona', leaves: [11], fill: '#FCF9F6' },
  { name: 'neo4j-mark',   src: 'neo4j',   leaves: [6] },
  // Neo4j's actual logotype 'e' — kept as a drop-in should the graph
  // mark prove too abstract to read as a letter.
  { name: 'neo4j-e',      src: 'neo4j',   leaves: [1], fill: '#FCF9F6' },
]

const browser = await chromium.launch()
const page = await browser.newPage()
const metrics = {}

for (const job of JOBS) {
  const src = SOURCES[job.src]
  await page.goto('file://' + encodeURI(src.file))
  const res = await page.evaluate(({ keep, fill }) => {
    const root = document.querySelector('svg')
    const leaves = [...root.querySelectorAll('path,rect,circle,polygon,ellipse')]
    const rootInv = root.getScreenCTM().inverse()
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
    leaves.forEach((el, i) => {
      if (!keep.includes(i)) { el.remove(); return }
      if (fill) el.setAttribute('fill', fill)
      const bb = el.getBBox()
      const m = rootInv.multiply(el.getScreenCTM())
      for (const [px, py] of [[bb.x,bb.y],[bb.x+bb.width,bb.y],[bb.x,bb.y+bb.height],[bb.x+bb.width,bb.y+bb.height]]) {
        const p = root.createSVGPoint(); p.x = px; p.y = py
        const q = p.matrixTransform(m)
        x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y)
        x1 = Math.max(x1, q.x); y1 = Math.max(y1, q.y)
      }
    })
    // Strip anything left that is now empty chrome.
    root.setAttribute('viewBox', `${x0} ${y0} ${x1 - x0} ${y1 - y0}`)
    root.setAttribute('width', (x1 - x0).toFixed(3))
    root.setAttribute('height', (y1 - y0).toFixed(3))
    root.removeAttribute('style')
    return { svg: root.outerHTML, x0, y0, x1, y1 }
  }, { keep: job.leaves, fill: job.fill })

  const cap = src.baseline - src.capTop
  metrics[job.name] = {
    w: +(res.x1 - res.x0).toFixed(3),
    h: +(res.y1 - res.y0).toFixed(3),
    // In cap-height units, relative to the baseline. Positive = above it.
    above: +((src.baseline - res.y0) / cap).toFixed(4),
    below: +((res.y1 - src.baseline) / cap).toFixed(4),
    widthInCaps: +((res.x1 - res.x0) / cap).toFixed(4),
  }
  fs.writeFileSync(path.join(OUT, `${job.name}.svg`), res.svg)
  const m = metrics[job.name]
  console.log(`${job.name.padEnd(14)} ${String(m.w).padStart(9)} x ${String(m.h).padStart(8)}   above=${String(m.above).padStart(7)} below=${String(m.below).padStart(7)} widthCaps=${m.widthInCaps}`)
}

// Pictograms: no baseline of their own, but they MUST be cropped to their ink
// like the letters are. Copied verbatim, their viewBox padding became silent
// sidebearings — the flower shoved 'ss' a whole stem away from 'Mi', and the
// Daytona glyph collided with the 't' beside it.
for (const [name, file] of [
  ['mistral-M', `${MB}/Mistral_Logos_2026/Icon/Gradient/RGB/SVG/Mistral-Icon-Gradient-RGB.svg`],
  ['mistral-flower', `${MB}/Mistral_Models_2026/SVG/Icon-Model-Small.svg`],
  ['daytona-glyph', `${DL}/Daytona Glyph Logo White.svg`],
]) {
  await page.goto('file://' + encodeURI(file))
  const res = await page.evaluate(() => {
    const root = document.querySelector('svg')
    const leaves = [...root.querySelectorAll('path,rect,circle,polygon,ellipse')]
    const rootInv = root.getScreenCTM().inverse()
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
    for (const el of leaves) {
      const bb = el.getBBox()
      if (!bb.width || !bb.height) continue
      const m = rootInv.multiply(el.getScreenCTM())
      for (const [px, py] of [[bb.x,bb.y],[bb.x+bb.width,bb.y],[bb.x,bb.y+bb.height],[bb.x+bb.width,bb.y+bb.height]]) {
        const p = root.createSVGPoint(); p.x = px; p.y = py
        const q = p.matrixTransform(m)
        x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y)
        x1 = Math.max(x1, q.x); y1 = Math.max(y1, q.y)
      }
    }
    root.setAttribute('viewBox', `${x0} ${y0} ${x1 - x0} ${y1 - y0}`)
    root.setAttribute('width', (x1 - x0).toFixed(3))
    root.setAttribute('height', (y1 - y0).toFixed(3))
    return { svg: root.outerHTML, w: x1 - x0, h: y1 - y0 }
  })
  fs.writeFileSync(path.join(OUT, `${name}.svg`), res.svg)
  metrics[name] = { w: +res.w.toFixed(3), h: +res.h.toFixed(3), aspect: +(res.w / res.h).toFixed(4) }
  console.log(`${name.padEnd(14)} ${res.w.toFixed(1).padStart(9)} x ${res.h.toFixed(1).padStart(8)}   aspect=${(res.w/res.h).toFixed(4)}`)
}

fs.writeFileSync(path.join(OUT, 'metrics.json'), JSON.stringify(metrics, null, 2))
console.log('\nwrote', Object.keys(metrics).length + 3, 'assets to public/wordmark')
await browser.close()
