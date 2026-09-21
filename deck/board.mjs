import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } })
await p.goto('http://127.0.0.1:5273/', { waitUntil: 'networkidle' })
await p.evaluate(() => document.fonts.ready)
await p.waitForTimeout(1500)
await p.keyboard.press('8')
await p.waitForTimeout(1400)
await p.screenshot({ path: 'board-8.png' })
console.log('staged:', await p.evaluate(() =>
  [...document.querySelectorAll('[aria-pressed="true"]')].map((e) =>
    (e.getAttribute('aria-label') ?? '').replace(/ \(on the board\)$/, ''))))
await b.close()
