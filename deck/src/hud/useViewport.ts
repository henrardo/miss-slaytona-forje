import { useEffect, useState } from 'react'

export interface Viewport {
  w: number
  h: number
}

/** Viewport size, tracked through resize and fullscreen transitions. */
export function useViewport(): Viewport {
  const [size, setSize] = useState<Viewport>(() => ({
    w: typeof window === 'undefined' ? 3840 : window.innerWidth,
    h: typeof window === 'undefined' ? 2160 : window.innerHeight,
  }))

  useEffect(() => {
    let frame = 0
    const measure = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() =>
        setSize({ w: window.innerWidth, h: window.innerHeight }),
      )
    }
    window.addEventListener('resize', measure)
    // Entering fullscreen on a 4K projector does not always fire `resize`
    // before the paint, so listen for the transition itself too.
    document.addEventListener('fullscreenchange', measure)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', measure)
      document.removeEventListener('fullscreenchange', measure)
    }
  }, [])

  return size
}
