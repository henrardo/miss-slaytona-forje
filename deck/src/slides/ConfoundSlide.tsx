/**
 * Is this run allowed to be a result?
 *
 * The comparison only means anything if the two arms differed by the TREATMENT
 * and nothing else. `orchestrator/metrics.py` records every difference it can
 * see and names the three that are the treatment; anything else makes the run
 * debugging material.
 *
 *   hook_files     warm has hooks.toml, cold has none — that IS the treatment
 *   config_names   warm's Vibe config lists the memory MCP server
 *   tools          warm's tool list therefore includes the memory tools
 *
 * Any fourth entry is a confound, and this card says so in hibiscus rather than
 * leaving it to a footnote. The rail carries the same verdict on every slide
 * because "which run is this, and does it count?" is the question that has cost
 * this project the most: a run that graded nothing looks exactly like one that
 * worked.
 *
 * Provenance below it, straight off the run: model, GPU, harness commit, skill
 * version and the hash of the skill directory that was actually installed.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import { TREATMENT_DIFFERENCES, runCounts } from '@/lib/types'
import type { SlideProps } from './types'

export function ConfoundSlide({ onStage }: SlideProps) {
  const { metrics, runId, events } = useRunFeed()
  const counts = runCounts(metrics)
  const diffs = metrics?.known_differences ?? []
  const start = events.find((e) => e.type === 'RUN_START')

  const rows: [string, string][] = [
    ['run', runId ?? '—'],
    ['model', metrics?.model ?? (start?.model as string) ?? '—'],
    ['gpu', metrics?.gpu ?? '—'],
    ['harness commit', metrics?.commit ?? '—'],
    [
      'skill',
      metrics
        ? `v${metrics.skill_version} · ~${metrics.skill_approx_tokens} tok · ${metrics.skill_dir_sha?.slice(0, 12) ?? '—'}`
        : '—',
    ],
    ['fixture', (start?.package as string) ?? '—'],
    ['test command', (start?.test_command as string) ?? '—'],
  ]

  return (
    <SlideChrome
      title="Does this run count?"
      accent={counts ? NEO4J.lightForest : ALARM}
      badge={
        metrics ? (
          <span
            style={{
              color: counts ? NEO4J.lightForest : ALARM,
              fontWeight: 700,
            }}
          >
            {counts ? 'ARMS OK' : 'CONFOUNDED'}
          </span>
        ) : (
          'awaiting metrics'
        )
      }
      focused={onStage}
      footer={
        <span>
          arms_identical + known_differences, from metrics.py · a confounded run is
          debugging material, never a result
        </span>
      }
    >
      <div className="flex h-full flex-col" style={{ gap: 18 }}>
        <div>
          <div
            className="font-pixel"
            style={{ fontSize: 28, color: 'hsl(var(--muted-fg))' }}
          >
            differences between the arms
          </div>
          {!metrics ? (
            <div
              className="font-pixel"
              style={{ fontSize: 34, color: 'hsl(var(--muted))', marginTop: 8 }}
            >
              written when the run ends
            </div>
          ) : diffs.length === 0 ? (
            <div
              className="font-pixel"
              style={{ fontSize: 34, color: NEO4J.marigold, marginTop: 8 }}
            >
              none recorded — which for these two arms would itself be odd
            </div>
          ) : (
            <div className="flex flex-wrap" style={{ gap: 12, marginTop: 10 }}>
              {diffs.map((d) => {
                const ok = TREATMENT_DIFFERENCES.has(d)
                return (
                  <span
                    key={d}
                    className="font-pixel"
                    style={{
                      fontSize: 32,
                      padding: '8px 18px',
                      borderRadius: 8,
                      color: ok ? NEO4J.lightForest : ALARM,
                      border: `2px solid ${ok ? NEO4J.lightForest : ALARM}`,
                      background: alpha(ok ? '#b6d4ae' : ALARM, 0.12),
                      fontWeight: ok ? 400 : 700,
                    }}
                  >
                    {d}
                    {ok ? ' · the treatment' : ' · CONFOUND'}
                  </span>
                )
              })}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1">
          <div
            className="font-pixel"
            style={{ fontSize: 28, color: 'hsl(var(--muted-fg))' }}
          >
            provenance
          </div>
          <table className="font-pixel w-full" style={{ fontSize: 30 }}>
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k} style={{ borderTop: '1px solid hsl(var(--border))' }}>
                  <td
                    style={{
                      color: 'hsl(var(--muted-fg))',
                      width: '30%',
                      paddingTop: 6,
                      paddingBottom: 6,
                    }}
                  >
                    {k}
                  </td>
                  <td
                    style={{
                      color: NEO4J.cream,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: 0,
                    }}
                  >
                    {v}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </SlideChrome>
  )
}
