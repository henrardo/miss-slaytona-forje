/**
 * The memory graph, polled.
 *
 * Separate from `RunFeed` because it is a different source with different
 * failure modes: `runs/` is a local file that cannot be unreachable, Aura is a
 * paused instance on conference wifi. A card that reads both should be able to
 * show one while the other is down, and say which.
 *
 * Polling rather than streaming: there is no change feed here, and "rows newer
 * than this cursor" is bounded, restartable and trivially correct. The cursor
 * is the largest `timestamp.epochMillis` seen.
 *
 * ── Scope, and why it can change under you ───────────────────────────────
 *
 * Traces are keyed `<run_id>:<agent>`, so the graph can be narrowed to the run
 * the deck is following — which is what you want on stage, since the database
 * also holds a hundred earlier traces. But a cold-only run writes nothing, and
 * an older run's nodes may predate the current schema. So: ask run-scoped
 * first, and if that comes back empty, widen to the whole graph and set
 * `scope: 'all'`. Consumers must show which one they are looking at. An
 * accumulated graph presented as "this run" would be the single most
 * misleading thing this deck could do.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useRunFeed } from './RunFeed'

export interface GraphStep {
  id: string
  stepNumber: number | null
  thought: string | null
  action: string | null
  observation: string | null
  at: number
  traceId: string
  sessionId: string
  task: string | null
  outcome: string | null
  success: boolean | string | null
  toolName: string | null
  toolArgs: string | null
  toolStatus: string | null
  entities: string[]
}

export interface GraphNode {
  id: string
  label: 'ReasoningTrace' | 'ReasoningStep' | 'ToolCall' | string
  at: number
  caption: string
  detail: string
  parent?: string | null
  ok?: boolean | null
}

export interface SchemaNode {
  id: string
  label: string
  indexes: string[]
  constraints: number
}
export interface SchemaRel {
  id: string
  type: string
  from: string
  to: string
}

export interface GraphFeed {
  /** Whether the last read came from Aura rather than the disk cache. */
  live: boolean
  /** How old the cached answer is, when serving one. */
  staleAgeMs: number | null
  error: string | null
  /** 'run' = only the followed run's traces; 'all' = the whole graph. */
  scope: 'run' | 'all'
  steps: GraphStep[]
  nodes: GraphNode[]
  labels: { label: string; n: number }[]
  schema: { nodes: SchemaNode[]; rels: SchemaRel[] } | null
}

const EMPTY: GraphFeed = {
  live: false,
  staleAgeMs: null,
  error: null,
  scope: 'run',
  steps: [],
  nodes: [],
  labels: [],
  schema: null,
}

/** Keep the stream bounded. Older ones have already receded out of view. */
const MAX_STEPS = 400
const MAX_NODES = 900
const POLL_MS = 1500
const HEALTH_MS = 20_000

const GraphContext = createContext<GraphFeed>(EMPTY)

interface Envelope<T> {
  ok: boolean
  stale: boolean
  staleAgeMs: number | null
  error?: string
  value: T | null
}

export function GraphFeedProvider({ children }: { children: ReactNode }) {
  const { runId } = useRunFeed()
  const [feed, setFeed] = useState<GraphFeed>(EMPTY)

  /** Cursor and scope live in refs: the poll must not restart when they move. */
  const cursor = useRef(0)
  const scope = useRef<'run' | 'all'>('run')
  const widened = useRef(false)
  /**
   * Which question the in-flight requests were asked under.
   *
   * A poll started before a run change lands after it, and without this its
   * rows were merged into the new run's set — so the card showed 259
   * whole-graph nodes under a badge reading "this run". That is the single
   * most misleading thing this deck could do, so the answer to a question
   * nobody is asking any more is dropped rather than merged.
   */
  const generation = useRef(0)

  // A new run means a new question. Reset rather than interleaving two runs'
  // reasoning on one timeline — the same rule RunFeed follows on re-latch.
  useEffect(() => {
    generation.current += 1
    cursor.current = 0
    scope.current = 'run'
    widened.current = false
    setFeed((f) => ({ ...f, steps: [], nodes: [], scope: 'run' }))
  }, [runId])

  const poll = useCallback(async () => {
    const mine = generation.current
    const run = scope.current === 'run' && runId ? runId : 'all'
    const qs = `since=${cursor.current}&run=${encodeURIComponent(run)}&limit=120`
    try {
      const [sRes, dRes] = await Promise.all([
        fetch(`/api/graph/steps?${qs}`),
        fetch(`/api/graph/delta?${qs}`),
      ])
      const s = (await sRes.json()) as Envelope<GraphStep[]>
      const d = (await dRes.json()) as Envelope<{ nodes: GraphNode[] }>
      // Asked under a question that is no longer being asked. Drop it whole.
      if (mine !== generation.current) return
      const fresh = s.value ?? []
      const nodes = d.value?.nodes ?? []

      // Nothing for this run, ever? Then it is not a run with a graph. Widen
      // once, and record that we did so the badge can say `all`.
      if (
        !widened.current &&
        scope.current === 'run' &&
        cursor.current === 0 &&
        fresh.length === 0 &&
        s.ok
      ) {
        widened.current = true
        scope.current = 'all'
      }

      if (fresh.length) {
        cursor.current = Math.max(cursor.current, ...fresh.map((x) => x.at))
      }

      setFeed((f) => {
        const seen = new Set(f.steps.map((x) => x.id))
        const steps = [...f.steps, ...fresh.filter((x) => !seen.has(x.id))]
        const nodeSeen = new Set(f.nodes.map((x) => x.id))
        const merged = [...f.nodes, ...nodes.filter((x) => !nodeSeen.has(x.id))]
        return {
          ...f,
          live: s.ok,
          staleAgeMs: s.staleAgeMs ?? null,
          error: s.ok ? null : (s.error ?? 'graph unreachable'),
          scope: scope.current,
          steps: steps.slice(-MAX_STEPS),
          nodes: merged.slice(-MAX_NODES),
        }
      })
    } catch (err) {
      if (mine !== generation.current) return
      setFeed((f) => ({ ...f, live: false, error: String(err) }))
    }
  }, [runId])

  useEffect(() => {
    void poll()
    const t = setInterval(() => void poll(), POLL_MS)
    return () => clearInterval(t)
  }, [poll])

  useEffect(() => {
    const load = async () => {
      try {
        const r = (await (await fetch('/api/graph/health')).json()) as Envelope<{
          labels: { label: string; n: number }[]
        }>
        setFeed((f) => ({ ...f, labels: r.value?.labels ?? f.labels }))
      } catch {
        /* the badge simply keeps its last count */
      }
    }
    void load()
    const t = setInterval(() => void load(), HEALTH_MS)
    return () => clearInterval(t)
  }, [])

  // The ontology does not change during a talk. Once.
  useEffect(() => {
    void (async () => {
      try {
        const r = (await (await fetch('/api/graph/schema')).json()) as Envelope<{
          nodes: SchemaNode[]
          rels: SchemaRel[]
        }>
        if (r.value) setFeed((f) => ({ ...f, schema: r.value }))
      } catch {
        /* the ontology card says so itself */
      }
    })()
  }, [])

  return <GraphContext.Provider value={feed}>{children}</GraphContext.Provider>
}

export function useGraphFeed(): GraphFeed {
  return useContext(GraphContext)
}
