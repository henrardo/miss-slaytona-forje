/**
 * Real source, with the parts currently in use lit up.
 *
 * Shared by the SGLang and Vibe cards. Both show excerpts of files that are
 * actually in this repo — fetched from the collector's whitelist, never pasted
 * — and light a region when the thing it does happens.
 *
 * ── The resolution problem, stated on the card ───────────────────────────
 *
 * There are two sources of "this just happened" and they are not equivalent:
 *
 *   GRAPH   every ToolCall and ReasoningStep carries a timestamp, so regions
 *           light per call, seconds apart. Warm ONLY — cold writes nothing to
 *           the graph, so a cold-only stretch would look idle when it is not.
 *   EVENTS  ATTEMPT_START/DONE, SANDBOX_CREATED, DISTILLED, INGESTED. True for
 *           both arms and available with Aura down, but attempt-granular: a
 *           pulse a minute rather than a pulse a second.
 *
 * So both, with the finer one preferred while it is producing — and the card
 * SAYS which resolution it is showing. A sparkle implying per-call activity
 * when the truth is one pulse per attempt would be decoration pretending to be
 * instrumentation.
 */
import { useEffect, useMemo, useState } from 'react'
import { useRunFeed } from '@/data/RunFeed'
import { useGraphFeed } from '@/data/GraphFeed'
import { NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'

/** What a region can be wired to. */
export type Trigger =
  'model_call' | 'tool_call' | 'step_write' | 'sandbox' | 'distil' | 'ingest'

export interface Region {
  /** Whitelisted repo path — see SOURCE_WHITELIST in plugins/runsData.ts. */
  file: string
  /** 1-indexed, inclusive. */
  from: number
  to: number
  label: string
  /** What this region does, in one line. */
  note: string
  trigger: Trigger
}

/** A region stays lit this long after its trigger. */
const LIT_MS = 2600
/** Beyond this the graph is not keeping up and events take over. */
const GRAPH_FRESH_MS = 20_000

export interface Activity {
  /** Trigger -> epoch ms it last fired. */
  at: Partial<Record<Trigger, number>>
  resolution: 'per call (graph)' | 'per attempt (events)' | 'idle'
}

/**
 * When each trigger last fired, from whichever source is actually producing.
 *
 * Event `t` is seconds since the run started, not wall clock, so events are
 * stamped with the arrival time of the feed update rather than with `t`. That
 * is honest about what is being measured: "the deck learned of this just now".
 */
export function useActivity(): Activity {
  const { events, lastUpdate } = useRunFeed()
  const { steps } = useGraphFeed()
  const [now, setNow] = useState(() => Date.now())

  // The lit state decays, so this has to re-render without new data.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 400)
    return () => clearInterval(t)
  }, [])

  return useMemo(() => {
    const at: Partial<Record<Trigger, number>> = {}

    // Fine: the graph timestamps every call and every step.
    let newestGraph = 0
    for (const s of steps) {
      if (s.at > newestGraph) newestGraph = s.at
      if (s.toolName) at.tool_call = Math.max(at.tool_call ?? 0, s.at)
      at.step_write = Math.max(at.step_write ?? 0, s.at)
      at.model_call = Math.max(at.model_call ?? 0, s.at)
    }
    const graphFresh = newestGraph > 0 && now - newestGraph < GRAPH_FRESH_MS

    // Coarse: true for both arms, and available with Aura down.
    const stamp = lastUpdate ?? 0
    const recent = events.slice(-12)
    for (const e of recent) {
      if (e.type === 'SANDBOX_CREATED') at.sandbox = stamp
      if (e.type === 'DISTILLED') at.distil = stamp
      if (e.type === 'INGESTED') at.ingest = stamp
      if (e.type === 'ATTEMPT_START' || e.type === 'ATTEMPT_DONE') {
        if (!graphFresh) {
          at.model_call = Math.max(at.model_call ?? 0, stamp)
          at.tool_call = Math.max(at.tool_call ?? 0, stamp)
        }
      }
      if (e.type === 'STEP_WRITES' && !graphFresh) at.step_write = stamp
    }

    const anyRecent = Object.values(at).some((v) => v && now - v < LIT_MS)
    return {
      at,
      resolution: !anyRecent
        ? 'idle'
        : graphFresh
          ? 'per call (graph)'
          : 'per attempt (events)',
    }
  }, [events, steps, lastUpdate, now])
}

export const isLit = (a: Activity, t: Trigger) => {
  const when = a.at[t]
  return !!when && Date.now() - when < LIT_MS
}

/** Fetch a whitelisted source file once, and cache it for the session. */
const cache = new Map<string, Promise<string>>()
function source(file: string): Promise<string> {
  let hit = cache.get(file)
  if (!hit) {
    hit = fetch(`/api/source?file=${encodeURIComponent(file)}`)
      .then((r) => r.json())
      .then((j: { text?: string; error?: string }) => j.text ?? `// ${j.error}`)
      .catch((e) => `// ${e}`)
    cache.set(file, hit)
  }
  return hit
}

export function useSources(regions: Region[]): Record<string, string> {
  const [texts, setTexts] = useState<Record<string, string>>({})
  const files = useMemo(
    () => [...new Set(regions.map((r) => r.file))].join('|'),
    [regions],
  )
  useEffect(() => {
    let alive = true
    void Promise.all(
      files.split('|').map((f) => source(f).then((t) => [f, t] as const)),
    ).then((pairs) => {
      if (alive) setTexts(Object.fromEntries(pairs))
    })
    return () => {
      alive = false
    }
  }, [files])
  return texts
}

/** The excerpt itself: real lines, real numbers, lit or not. */
export function RegionView({
  region,
  text,
  lit,
}: {
  region: Region
  text: string | undefined
  lit: boolean
}) {
  const lines = useMemo(() => {
    if (!text) return []
    const all = text.split('\n')
    return all
      .slice(region.from - 1, region.to)
      .map((l, i) => ({ n: region.from + i, l }))
  }, [text, region.from, region.to])

  return (
    <div
      style={{
        border: `2px solid ${lit ? NEO4J.marigold : alpha(NEO4J.periwinkle, 0.3)}`,
        borderRadius: 8,
        background: lit ? alpha(NEO4J.marigold, 0.09) : 'transparent',
        boxShadow: lit ? `0 0 34px ${alpha(NEO4J.marigold, 0.3)}` : 'none',
        // Colour and glow only. Nothing here moves: this card sits next to a
        // force simulation and a canvas sprite, and a third animation would be
        // the layer budget again.
        transition: 'border-color 260ms, background 260ms, box-shadow 260ms',
        padding: '10px 14px',
        overflow: 'hidden',
      }}
    >
      <div className="flex items-baseline justify-between" style={{ gap: 16 }}>
        <span
          className="font-pixel"
          style={{
            fontSize: pt(26),
            color: lit ? NEO4J.marigold : NEO4J.lightPeriwinkle,
            fontWeight: lit ? 700 : 400,
          }}
        >
          {region.label}
        </span>
        <span
          className="font-pixel"
          style={{ fontSize: pt(22), color: 'hsl(var(--muted))' }}
        >
          {region.file}:{region.from}
        </span>
      </div>
      <div
        className="font-pixel"
        style={{ fontSize: pt(23), lineHeight: 1.3, marginTop: 4 }}
      >
        {lines.map(({ n, l }) => (
          <div key={n} style={{ whiteSpace: 'pre', overflow: 'hidden' }}>
            <span style={{ color: 'hsl(var(--muted))' }}>
              {String(n).padStart(4, ' ')}{' '}
            </span>
            <span style={{ color: lit ? NEO4J.cream : 'hsl(var(--muted-fg))' }}>
              {l}
            </span>
          </div>
        ))}
        {!lines.length ? (
          <span style={{ color: 'hsl(var(--muted))' }}>loading source…</span>
        ) : null}
      </div>
      <div
        className="font-pixel"
        style={{ fontSize: pt(22), color: 'hsl(var(--muted))', marginTop: 4 }}
      >
        {region.note}
      </div>
    </div>
  )
}
