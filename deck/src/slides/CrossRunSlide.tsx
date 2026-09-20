/**
 * `runs/cross-run.md` — the actual deliverable.
 *
 * Append-only, one row per arm per run, written by the harness at the end of
 * every run. This card renders the file rather than recomputing the table:
 * `orchestrator/metrics.py` is the only thing allowed to produce these numbers,
 * and a second implementation in TypeScript would be a second answer.
 *
 * The rightmost column is `counts`. A run counts toward "clearly working" only
 * when the arms differed by the treatment alone; anything else is debugging
 * material and is dimmed here rather than quietly averaged in.
 *
 * ── The file has two schemas under one header ────────────────────────────
 *
 * Measured, not assumed: 63 rows carry 15 columns and 71 carry 18, under a
 * single 15-column header. The harness gained three columns partway through
 * the project and never rewrote the header line. Rendered naively, the wider
 * rows shift left and the GPU price appears under "skill v" — which is how
 * this was found.
 *
 * So a row is only shown when its width matches the header. The others are
 * COUNTED and reported rather than silently dropped: "132 rows" with half of
 * them invisible would be its own lie. The fix belongs in metrics.py, not here.
 */
import { useEffect, useMemo, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, ARM_COLOR, NEO4J } from '@/lib/brand'
import type { SlideProps } from './types'

/** Columns worth the width on a projector. The file has fifteen. */
const KEEP = [
  'run',
  'skill v',
  'arm',
  'passed',
  'attempts',
  'converged',
  'turns',
  'counts',
]

interface Table {
  head: string[]
  rows: string[][]
  /** Rows whose column count did not match the header. See the note above. */
  skipped: number
}

function parse(md: string): Table | null {
  const lines = md.split('\n').filter((l) => l.trim().startsWith('|'))
  if (lines.length < 3) return null
  const cells = (l: string) =>
    l
      .split('|')
      .slice(1, -1)
      .map((c) => c.trim())
  const head = cells(lines[0])
  const want = KEEP.map((k) => head.indexOf(k)).filter((i) => i >= 0)
  // lines[1] is the markdown separator row.
  const body = lines.slice(2).map(cells)
  const usable = body.filter((c) => c.length === head.length)
  return {
    head: want.map((i) => head[i]),
    rows: usable.map((c) => want.map((i) => c[i] ?? '')),
    skipped: body.length - usable.length,
  }
}

export function CrossRunSlide({ onStage }: SlideProps) {
  const { runId } = useRunFeed()
  const [md, setMd] = useState<string | null>(null)

  useEffect(() => {
    void fetch('/api/doc/cross-run')
      .then((r) => r.json())
      .then((j: { text?: string }) => setMd(j.text ?? null))
      .catch(() => setMd(null))
    // Re-read when the followed run changes; the harness appends at run end.
  }, [runId])

  const table = useMemo(() => (md ? parse(md) : null), [md])
  const rows = useMemo(() => table?.rows.slice(-16).reverse() ?? [], [table])

  return (
    <SlideChrome
      title="Cross-run summary"
      accent={NEO4J.lightPeriwinkle}
      badge={
        table ? (
          <span style={{ color: table.skipped ? ALARM : undefined }}>
            {table.rows.length} rows
            {table.skipped ? ` · ${table.skipped} unreadable` : ''}
          </span>
        ) : (
          'no table'
        )
      }
      focused={onStage}
      footer={
        <span>
          {table?.skipped
            ? `${table.skipped} row(s) have more columns than the header — not shown`
            : 'runs/cross-run.md, verbatim · a row counts only when the arms differed by the treatment'}
        </span>
      }
    >
      {!table ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          cross-run.md is written when a run ends
        </div>
      ) : (
        <table className="font-pixel w-full" style={{ fontSize: 27 }}>
          <thead>
            <tr style={{ color: 'hsl(var(--muted-fg))' }}>
              {table.head.map((h) => (
                <th
                  key={h}
                  className={h === 'run' ? 'text-left' : 'text-right'}
                  style={{ fontWeight: 400 }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const arm = r[table.head.indexOf('arm')]
              const counts = r[table.head.indexOf('counts')] === 'yes'
              const here = r[0] === runId
              return (
                <tr
                  key={i}
                  style={{
                    borderTop: '1px solid hsl(var(--border))',
                    opacity: counts ? 1 : 0.42,
                  }}
                >
                  {r.map((c, j) => (
                    <td
                      key={j}
                      className={j === 0 ? 'text-left' : 'text-right tabular-nums'}
                      style={{
                        color:
                          j === 0 && here
                            ? NEO4J.cream
                            : table.head[j] === 'arm' || j === 0
                              ? (ARM_COLOR[arm as 'warm' | 'cold'] ??
                                'hsl(var(--muted-fg))')
                              : table.head[j] === 'counts' && !counts
                                ? ALARM
                                : 'hsl(var(--muted-fg))',
                        fontWeight: here ? 700 : 400,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {c}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </SlideChrome>
  )
}
