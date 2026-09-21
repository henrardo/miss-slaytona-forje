/**
 * SVG text that stays inside its box.
 *
 * HTML text has three ways to cope with a box too small for it — wrap,
 * ellipsis, scroll — and SVG `<text>` has none. It draws at the length it
 * draws at and hangs out of whatever it was meant to be inside, which is
 * exactly what "pytest · in Daytona · 2 graded" did to its node.
 *
 * SHORTEN, DO NOT SHRINK. The obvious fix is to scale the type down until it
 * fits, and that is not available here: 12pt is the floor (see lib/type.ts),
 * and a card that meets the floor by making one label 9px has not met it. So
 * this measures with `getComputedTextLength` and drops characters — binary
 * search, one ellipsis — until the ink fits `maxWidth`. A label that cannot
 * fit says less; it never says it smaller.
 *
 * Measuring happens in a layout effect and again after `document.fonts.ready`,
 * because the first measurement of a webfont-bound string is taken against the
 * fallback face and is wrong by whatever those two faces differ by.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties, SVGProps } from 'react'

export interface FitTextProps extends Omit<SVGProps<SVGTextElement>, 'children'> {
  /** The widest the ink may be, in the same units as the SVG's viewBox. */
  maxWidth: number
  children: string
  style?: CSSProperties
}

export function FitText({ maxWidth, children, ...rest }: FitTextProps) {
  const ref = useRef<SVGTextElement>(null)
  const [shown, setShown] = useState(children)

  const fit = () => {
    const el = ref.current
    if (!el || maxWidth <= 0) return
    // Measure the full string first: the common case is that it fits, and
    // the DOM write is skipped entirely.
    el.textContent = children
    if (el.getComputedTextLength() <= maxWidth) {
      setShown(children)
      return
    }
    let lo = 0
    let hi = children.length
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2)
      el.textContent = `${children.slice(0, mid).trimEnd()}…`
      if (el.getComputedTextLength() <= maxWidth) lo = mid
      else hi = mid - 1
    }
    setShown(`${children.slice(0, lo).trimEnd()}…`)
  }

  useLayoutEffect(fit)
  useEffect(() => {
    let alive = true
    void document.fonts?.ready.then(() => {
      if (alive) fit()
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [children, maxWidth])

  return (
    <text ref={ref} {...rest}>
      {shown}
    </text>
  )
}
