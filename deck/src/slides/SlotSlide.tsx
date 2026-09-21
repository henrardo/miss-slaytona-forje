/**
 * An empty slot.
 *
 * These exist so the ring is laid out at full capacity from day one — the
 * geometry is much harder to fix once sixteen real slides are fighting over
 * it. Replace one by swapping its entry in `registry.tsx`; nothing else in the
 * HUD needs to know.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { Sprite } from '@/character/Sprite'
import { noiseSprite } from '@/character/sprites'
import { whimsyAt } from '@/lib/brand'
import type { SlideProps } from './types'
import { pt } from '@/lib/type'

export function makeSlotSlide(index: number) {
  const accent = whimsyAt(index)
  const sprite = noiseSprite(index + 1, accent)

  return function SlotSlide({ onStage }: SlideProps) {
    return (
      <SlideChrome
        title={`Slot ${String(index).padStart(2, '0')}`}
        accent={accent}
        badge="EMPTY"
        focused={onStage}
        footer={<span>add a slide in src/slides/registry.tsx</span>}
      >
        <div className="flex h-full items-center justify-center gap-16">
          <Sprite sprite={sprite} pixel={30} />
          <div
            className="font-pixel"
            style={{
              fontSize: pt(54),
              color: 'hsl(var(--muted-fg))',
              maxWidth: 820,
            }}
          >
            Reserved. The ring is laid out at full capacity so the geometry is
            settled before the content arrives.
          </div>
        </div>
      </SlideChrome>
    )
  }
}
