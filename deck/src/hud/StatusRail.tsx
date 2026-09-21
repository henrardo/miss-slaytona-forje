/**
 * The strip along the bottom edge: what the deck is connected to, and what it
 * is showing. Present on every slide because "which run is this?" is the
 * question that has cost this project the most — a run that graded nothing
 * looks exactly like one that worked.
 */
import { useRunFeed, type Source } from '@/data/RunFeed'
import { runCounts } from '@/lib/types'
import { ALARM, BRANDS, BRAND_ORDER, NEO4J, alpha } from '@/lib/brand'

const DOT: Record<string, string> = {
  live: '#b6d4ae', // light forest — legible on the violet ground
  connecting: '#9aa9ff',
  down: ALARM,
}

/**
 * Live / Replay, as a two-state segmented control.
 *
 * Deliberately shows BOTH labels with one lit rather than one label that
 * toggles: on a projector, a button reading "LIVE" is ambiguous about whether
 * that is the current state or the thing it will do. The lit one is the state.
 *
 * REPLAY is the label; `rehearsal` is still the key, because the key IS the
 * filename prefix `scripts/rehearse_loop.py` writes. Renaming it here would
 * mean renaming the writer's output, so the rename stops at the glass.
 */
function SourceSwitch({
  source,
  onSource,
  locked,
}: {
  source: Source
  onSource: (s: Source) => void
  locked: boolean
}) {
  const OPTIONS: { key: Source; label: string; hint: string }[] = [
    { key: 'swarm', label: 'LIVE', hint: 'follow the newest pod run (swarm-*)' },
    {
      key: 'rehearsal',
      label: 'REPLAY',
      hint: 'follow the newest local replay (rehearsal-*)',
    },
  ]
  return (
    <span
      className="flex shrink-0 items-center"
      style={{
        border: `1px solid ${alpha(NEO4J.periwinkle, 0.5)}`,
        borderRadius: '0.4vh',
        overflow: 'hidden',
        opacity: locked ? 0.65 : 1,
      }}
      title={
        locked
          ? 'A run is pinned with ?run= — the switch does not apply.'
          : undefined
      }
    >
      {OPTIONS.map((o) => {
        const on = source === o.key
        return (
          <button
            key={o.key}
            type="button"
            disabled={locked}
            onClick={() => onSource(o.key)}
            aria-pressed={on}
            title={o.hint}
            className="font-pixel px-[1vh]"
            style={{
              fontSize: '1.7vh',
              lineHeight: 1,
              height: '2.2vh',
              border: 'none',
              color: on ? '#12102a' : 'hsl(var(--muted-fg))',
              background: on ? NEO4J.lightPeriwinkle : 'transparent',
              cursor: locked ? 'default' : 'pointer',
            }}
          >
            {o.label}
          </button>
        )
      })}
    </span>
  )
}

export interface StatusRailProps {
  /** Restore the starting card arrangement. Cards only. */
  onReset: () => void
  /** False when the cards are already where they started. */
  resetEnabled: boolean
  onSource: (s: Source) => void
  /** True when `?run=` pins a run, which overrides the switch. */
  sourceLocked: boolean
}

export function StatusRail({
  onReset,
  resetEnabled,
  onSource,
  sourceLocked,
}: StatusRailProps) {
  const { connection, runId, events, metrics, runs, source } = useRunFeed()
  const counts = runCounts(metrics)
  /**
   * The arms are declared different, but the record does not say how.
   *
   * `package_run.py` rebuilding a summary from the event log cannot recover
   * `known_differences`, so the field comes back empty on a run that was
   * stopped before `RUN_END`. The harness itself printed the answer at
   * launch — on swarm-1789998106, `['config_names', 'hook_files', 'tools']`.
   */
  const unrecorded =
    !!metrics &&
    metrics.arms_identical === false &&
    !metrics.known_differences.length

  return (
    <div
      className="font-pixel absolute inset-x-0 bottom-0 z-[60] flex items-center gap-[2vh] px-[1.2vh]"
      style={{
        height: '3vh',
        fontSize: '1.7vh',
        background: 'hsl(var(--bg) / 0.92)',
        borderTop: '1px solid hsl(var(--border))',
        color: 'hsl(var(--muted-fg))',
      }}
    >
      <span className="flex items-center gap-[0.6vh]">
        <span
          style={{
            width: '1vh',
            height: '1vh',
            background: DOT[connection],
            boxShadow: `0 0 1.2vh ${DOT[connection]}`,
          }}
        />
        {connection === 'live' ? 'COLLECTING' : connection.toUpperCase()}
      </span>

      <span style={{ color: 'hsl(var(--fg))' }}>{runId ?? 'no run on disk'}</span>

      <span>{events.length} events</span>

      {metrics ? (
        <>
          {/* OMITTED WHEN BLANK, not rendered as an empty span. A summary
              rebuilt from the event log after a run was stopped carries
              `model: ""` and `commit: ""` — which drew a stray "@" on the
              rail with nothing after it, and an invisible gap where the
              model should be. An absent field says "not recorded" or says
              nothing; it never mimics a value. */}
          {metrics.model ? <span>{metrics.model}</span> : null}
          {metrics.gpu ? <span>{metrics.gpu}</span> : null}
          {metrics.commit ? <span>@{metrics.commit}</span> : null}
          {/* Loud on purpose. A run whose arms differed outside the treatment
              is debugging material, and must never be presented as a result.
              THREE STATES, NOT TWO: `known_differences: []` on a run that
              also says `arms_identical: false` is not a clean comparison, it
              is a record that does not say what differed — and `[].every()`
              is vacuously true, so it was being reported as ARMS OK. */}
          <span
            style={{
              color: unrecorded ? NEO4J.marigold : counts ? '#b6d4ae' : ALARM,
              fontWeight: counts && !unrecorded ? 400 : 700,
            }}
          >
            {unrecorded
              ? 'ARM DIFFERENCES NOT RECORDED'
              : counts
                ? 'ARMS OK'
                : `CONFOUNDED: ${metrics.known_differences.join(', ')}`}
          </span>
        </>
      ) : (
        <span>awaiting metrics</span>
      )}

      <span className="ml-auto flex shrink-0 items-center gap-[1.2vh]">
        <SourceSwitch source={source} onSource={onSource} locked={sourceLocked} />
      </span>

      {/* Cards only. Deliberately says so, so nobody on stage has to wonder
          whether pressing it drops the run. */}
      <button
        type="button"
        onClick={onReset}
        disabled={!resetEnabled}
        title="Put the cards back in their starting positions. Does not affect the run."
        className="font-pixel shrink-0 px-[1.2vh] transition-opacity"
        style={{
          fontSize: '1.7vh',
          lineHeight: 1,
          height: '2.2vh',
          color: resetEnabled
            ? 'var(--neo4j-periwinkle-light)'
            : 'hsl(var(--muted))',
          border: `1px solid ${resetEnabled ? 'var(--neo4j-periwinkle)' : 'hsl(var(--border))'}`,
          borderRadius: '0.4vh',
          background: resetEnabled ? 'hsl(232 100% 71% / 0.12)' : 'transparent',
          cursor: resetEnabled ? 'pointer' : 'default',
          opacity: resetEnabled ? 1 : 0.8,
        }}
      >
        Reset
      </button>

      <span className="flex items-center gap-[1.4vh] opacity-70">
        {runs.length} runs on disk
        {BRAND_ORDER.map((key) => (
          <img
            key={key}
            src={BRANDS[key].logo}
            alt={BRANDS[key].name}
            style={{ height: '1.6vh', width: 'auto' }}
          />
        ))}
      </span>
    </div>
  )
}
