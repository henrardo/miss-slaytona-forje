/**
 * Daytona: the only success oracle.
 *
 * One ephemeral sandbox per file-attempt (orchestrator/sandbox.py), pytest run
 * inside it, and the count that comes back is the only evidence anybody in the
 * room should accept. This card shows each verification as it happens: sandbox
 * up (with how long that took), then the verdict.
 *
 * ── Why the score column is not the headline ─────────────────────────────
 *
 * `tests_passed` is 0 for two opposite states — the migration has not started,
 * and the agent broke the package so the suite cannot import. Measured over 77
 * graded attempts, 70% scored exactly 0 (orchestrator/surfaces.py). So each row
 * carries the error signature that produced the score, and a run of identical
 * signatures down the column is the tell that nothing is moving. The score
 * alone would look like steady failure either way.
 *
 * `exit_code` is pytest's, verbatim. `create_ms` is the sandbox's own.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, BRANDS, NEO4J, alpha } from '@/lib/brand'
import type { Arm, RunEvent } from '@/lib/types'
import type { SlideProps } from './types'

interface Verification {
  key: string
  arm: Arm
  agent: string
  attempt: number | null
  createMs: number | null
  passed: number | null
  v1Left: number | null
  exitCode: number | null
  signature: string | null
  seconds: number | null
}

/** Pair each SANDBOX_CREATED with the ATTEMPT_DONE it graded. */
function verifications(events: RunEvent[]): Verification[] {
  const pending = new Map<string, RunEvent>()
  const out: Verification[] = []
  for (const e of events) {
    const agent = String(e.agent ?? e.swarm ?? '?')
    if (e.type === 'SANDBOX_CREATED') {
      pending.set(agent, e)
    } else if (e.type === 'ATTEMPT_DONE') {
      const sb = pending.get(agent)
      pending.delete(agent)
      out.push({
        key: `${agent}-${e.attempt}-${e.t}`,
        arm: (e.swarm as Arm) ?? 'cold',
        agent,
        attempt: e.attempt ?? null,
        createMs: (sb?.create_ms as number | undefined) ?? null,
        passed: e.tests_passed ?? null,
        v1Left: e.v1_remaining ?? null,
        exitCode: e.exit_code ?? null,
        signature: (e.error_signature as string | undefined) ?? null,
        seconds: e.attempt_seconds ?? null,
      })
    }
  }
  return out
}

const short = (sig: string | null) => (sig ? sig.split('\n')[0].slice(0, 96) : '—')

export function DaytonaSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const all = verifications(events)
  const rows = all.slice(-14).reverse()
  const swept = all.length
  const created = all.filter((v) => v.createMs != null).length

  return (
    <SlideChrome
      title="Daytona verification"
      accent={BRANDS.daytona.accent}
      badge={`${swept} graded · ${created} sandboxes`}
      focused={onStage}
      footer={
        <span>
          one ephemeral sandbox per attempt · exit code and count are pytest's,
          verbatim
        </span>
      }
    >
      {rows.length === 0 ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 56, color: 'hsl(var(--muted-fg))' }}
        >
          no attempt has been graded yet
        </div>
      ) : (
        <table className="font-pixel w-full" style={{ fontSize: 30 }}>
          <thead>
            <tr style={{ color: 'hsl(var(--muted-fg))' }}>
              <th className="text-left font-normal">agent</th>
              <th className="text-right font-normal">att</th>
              <th className="text-right font-normal">sandbox</th>
              <th className="text-right font-normal">passed</th>
              <th className="text-right font-normal">v1 left</th>
              <th className="text-right font-normal">exit</th>
              <th className="text-left font-normal" style={{ paddingLeft: 24 }}>
                what pytest said
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((v) => {
              const c = ARM_COLOR[v.arm] ?? NEO4J.cream
              const green = v.exitCode === 0
              return (
                <tr
                  key={v.key}
                  style={{ borderTop: '1px solid hsl(var(--border))' }}
                >
                  <td style={{ color: c }}>{v.agent}</td>
                  <td className="text-right tabular-nums">{v.attempt ?? '—'}</td>
                  <td
                    className="text-right tabular-nums"
                    style={{ color: 'hsl(var(--muted-fg))' }}
                  >
                    {v.createMs != null ? `${v.createMs}ms` : '—'}
                  </td>
                  <td
                    className="text-right tabular-nums"
                    style={{ color: green ? NEO4J.lightForest : c }}
                  >
                    {v.passed ?? '—'}
                  </td>
                  <td className="text-right tabular-nums">{v.v1Left ?? '—'}</td>
                  <td
                    className="text-right tabular-nums"
                    style={{ color: green ? NEO4J.lightForest : ALARM }}
                  >
                    {v.exitCode ?? '—'}
                  </td>
                  <td
                    style={{
                      paddingLeft: 24,
                      color: green ? NEO4J.lightForest : alpha(NEO4J.cream, 0.75),
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: 0,
                    }}
                  >
                    {green ? 'suite passed' : short(v.signature)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </SlideChrome>
  )
}
