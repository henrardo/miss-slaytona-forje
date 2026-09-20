/**
 * What is actually blocking each arm, attempt after attempt.
 *
 * The error signature pytest produced, grouped, with how many attempts hit it
 * and whether anyone has ever cleared it. This is the card that shows a stuck
 * agent as stuck: the score column says 0 either way, but eight attempts
 * against the identical signature is a different fact from eight attempts
 * against eight signatures.
 *
 * ── Why "errors cleared" is not on this card ─────────────────────────────
 *
 * Because it is not progress. Run 21 replaced a `BaseSettings` import with one
 * that cleared `PydanticImportError` and introduced `NameError` — signature
 * changed, attempt scored as a success, the diff was written to shared memory
 * as a verified fix, and warm agents then RETRIEVED it and reproduced the
 * mistake. `tests_passed` is the only measure this project trusts, so a
 * signature row shows the best score anyone reached while it was in the way,
 * and never claims that a changed signature was an improvement.
 */
import { useMemo } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, NEO4J, alpha } from '@/lib/brand'
import type { Arm, RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

interface Sig {
  sig: string
  hits: number
  arms: Set<Arm>
  best: number
  lastAt: number
  cleared: boolean
}

function signatures(events: RunEvent[]): Sig[] {
  const by = new Map<string, Sig>()
  for (const e of events) {
    if (e.type !== 'ATTEMPT_DONE') continue
    const raw = (e.error_signature as string | null) ?? null
    const sig = raw
      ? raw.split('\n')[0]
      : e.exit_code === 0
        ? '(suite passed)'
        : '(no signature)'
    const hit = by.get(sig) ?? {
      sig,
      hits: 0,
      arms: new Set<Arm>(),
      best: 0,
      lastAt: 0,
      cleared: false,
    }
    hit.hits++
    if (e.swarm === 'warm' || e.swarm === 'cold') hit.arms.add(e.swarm)
    hit.best = Math.max(hit.best, e.tests_passed ?? 0)
    hit.lastAt = Math.max(hit.lastAt, e.t)
    if (e.exit_code === 0) hit.cleared = true
    by.set(sig, hit)
  }
  return [...by.values()].sort((a, b) => b.hits - a.hits)
}

export function ErrorsSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const sigs = useMemo(() => signatures(events), [events])
  const graded = events.filter((e) => e.type === 'ATTEMPT_DONE').length
  const worst = sigs[0]

  return (
    <SlideChrome
      title="What is in the way"
      accent={ALARM}
      badge={
        sigs.length
          ? `${sigs.length} distinct · ${graded} graded`
          : 'nothing graded yet'
      }
      focused={onStage}
      footer={
        <span>
          error_signature from pytest · a changed signature is NOT progress — only
          tests passing is
        </span>
      }
    >
      {!sigs.length ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          waiting for the first graded attempt
        </div>
      ) : (
        <div className="font-pixel" style={{ fontSize: 28, lineHeight: 1.4 }}>
          {sigs.slice(0, 12).map((s) => {
            const share = worst ? s.hits / worst.hits : 0
            return (
              <div
                key={s.sig}
                style={{
                  borderTop: '1px solid hsl(var(--border))',
                  paddingTop: 7,
                  paddingBottom: 7,
                }}
              >
                <div className="flex items-baseline gap-5">
                  <span
                    className="shrink-0 tabular-nums"
                    style={{
                      width: 90,
                      color: s.cleared ? NEO4J.lightForest : ALARM,
                      fontWeight: 700,
                    }}
                  >
                    {s.hits}×
                  </span>
                  <span className="shrink-0" style={{ width: 150 }}>
                    {[...s.arms].map((a) => (
                      <span key={a} style={{ color: ARM_COLOR[a], marginRight: 8 }}>
                        {a}
                      </span>
                    ))}
                  </span>
                  <span
                    className="shrink-0 tabular-nums"
                    style={{ width: 200, color: 'hsl(var(--muted-fg))' }}
                  >
                    best {s.best}
                  </span>
                  <span
                    style={{
                      color: s.cleared ? NEO4J.lightForest : NEO4J.cream,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {s.sig}
                  </span>
                </div>
                {/* How much of the run this one error accounts for. */}
                <div
                  style={{
                    height: 6,
                    marginTop: 3,
                    width: `${Math.max(2, share * 100)}%`,
                    background: s.cleared
                      ? alpha(NEO4J.lightForest, 0.6)
                      : alpha(ALARM, 0.6),
                  }}
                />
              </div>
            )
          })}
        </div>
      )}
    </SlideChrome>
  )
}
