/**
 * The single source of run data for every slide.
 *
 * Slides hold no data state of their own. They are pure views over this feed,
 * which is what makes "tiles keep collecting while off-stage" true by
 * construction rather than by keeping twenty components alive correctly: a
 * tile and the stage render the same component against the same feed, so
 * neither can fall behind the other.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from 'react'
import type {
  RunEvent,
  RunIndexEntry,
  RunLog,
  RunMetrics,
  SeriesDoc,
} from '@/lib/types'

export type Connection = 'connecting' | 'live' | 'down'

/**
 * Which writer the deck is following.
 *
 * `swarm` is a pod run, `rehearsal` is `scripts/rehearse_loop.py` driving the
 * same loop locally against a scripted model. The cards do not know the
 * difference and must not: this narrows which file the collector tails, and
 * nothing else.
 *
 * The rail labels `rehearsal` REPLAY, and it is the default view. The key
 * keeps its name because it is the filename prefix the writer emits.
 */
export type Source = 'swarm' | 'rehearsal'

export interface RunFeed {
  connection: Connection
  /** Every run on disk, newest first. */
  runs: RunIndexEntry[]
  /** The run currently being followed, or null if `runs/` is empty. */
  runId: string | null
  events: RunEvent[]
  metrics: RunMetrics | null
  /** The harness's own chart document. See SeriesDoc. */
  series: SeriesDoc | null
  /** The orchestrator's stdout, accumulated. Not paired with `runId`. */
  log: RunLog | null
  /** Wall-clock of the last byte received, for the liveness pip. */
  lastUpdate: number | null
  /** Which writer is being followed. */
  source: Source
}

type Action =
  | { kind: 'connection'; value: Connection }
  | { kind: 'runs'; runs: RunIndexEntry[] }
  | { kind: 'active'; runId: string }
  | {
      kind: 'snapshot'
      runId: string
      events: RunEvent[]
      metrics: RunMetrics | null
      series: SeriesDoc | null
    }
  | { kind: 'events'; runId: string; events: RunEvent[] }
  | { kind: 'metrics'; runId: string; metrics: RunMetrics }
  | { kind: 'series'; runId: string; series: SeriesDoc }
  | { kind: 'log'; log: RunLog; reset: boolean }

const EMPTY: RunFeed = {
  connection: 'connecting',
  runs: [],
  runId: null,
  events: [],
  metrics: null,
  series: null,
  log: null,
  lastUpdate: null,
  source: 'swarm',
}

function reduce(state: RunFeed, action: Action): RunFeed {
  switch (action.kind) {
    case 'connection':
      return { ...state, connection: action.value }
    case 'runs':
      return { ...state, runs: action.runs }
    case 'active':
      // Re-latched onto a different run: drop the old one entirely rather
      // than interleaving two runs' events on one timeline.
      // The log is NOT cleared here: it is not keyed on the run id and has
      // its own reset signal.
      return action.runId === state.runId
        ? state
        : {
            ...state,
            runId: action.runId,
            events: [],
            metrics: null,
            series: null,
          }
    case 'snapshot':
      return {
        ...state,
        runId: action.runId,
        events: action.events,
        metrics: action.metrics,
        series: action.series,
        lastUpdate: Date.now(),
      }
    case 'events':
      if (action.runId !== state.runId) return state
      return {
        ...state,
        events: state.events.concat(action.events),
        lastUpdate: Date.now(),
      }
    case 'metrics':
      if (action.runId !== state.runId) return state
      return { ...state, metrics: action.metrics, lastUpdate: Date.now() }
    case 'series':
      if (action.runId !== state.runId) return state
      return { ...state, series: action.series, lastUpdate: Date.now() }
    case 'log':
      // `reset` means the collector moved to a different .log — a series
      // driver starts one per run, and appending the next run's first line to
      // the previous transcript would be a lie about what happened.
      return {
        ...state,
        log:
          action.reset || !state.log
            ? action.log
            : { ...action.log, text: state.log.text + action.log.text },
        lastUpdate: Date.now(),
      }
  }
}

const FeedContext = createContext<RunFeed>(EMPTY)

export function RunFeedProvider({
  children,
  run,
  source: writer = 'swarm',
}: {
  children: ReactNode
  /** Pin a run id, or leave undefined to follow whichever is newest. */
  run?: string
  /** Which writer to follow. Changing it reopens the stream from scratch. */
  source?: Source
}) {
  const [state, dispatch] = useReducer(reduce, EMPTY)

  useEffect(() => {
    const qs = new URLSearchParams()
    if (run) qs.set('run', run)
    else qs.set('kind', writer)
    const url = `/api/stream?${qs}`
    const source = new EventSource(url)

    const on = <T,>(name: string, fn: (payload: T) => void) =>
      source.addEventListener(name, (e) => {
        try {
          fn(JSON.parse((e as MessageEvent).data) as T)
        } catch {
          /* a malformed frame must not take the deck down mid-talk */
        }
      })

    source.onopen = () => dispatch({ kind: 'connection', value: 'live' })
    // EventSource reconnects on its own; surface the gap, do not tear down.
    source.onerror = () => dispatch({ kind: 'connection', value: 'down' })

    on<{ runs: RunIndexEntry[] }>('runs', (p) =>
      dispatch({ kind: 'runs', runs: p.runs }),
    )
    on<{ runId: string }>('active', (p) =>
      dispatch({ kind: 'active', runId: p.runId }),
    )
    on<{
      runId: string
      events: RunEvent[]
      metrics: RunMetrics | null
      series: SeriesDoc | null
    }>('snapshot', (p) =>
      dispatch({
        kind: 'snapshot',
        runId: p.runId,
        events: p.events,
        metrics: p.metrics,
        series: p.series,
      }),
    )
    on<{ runId: string; events: RunEvent[] }>('events', (p) =>
      dispatch({ kind: 'events', runId: p.runId, events: p.events }),
    )
    on<{ runId: string; metrics: RunMetrics }>('metrics', (p) =>
      dispatch({ kind: 'metrics', runId: p.runId, metrics: p.metrics }),
    )
    on<{ runId: string; series: SeriesDoc }>('series', (p) =>
      dispatch({ kind: 'series', runId: p.runId, series: p.series }),
    )
    on<RunLog & { reset: boolean }>('log', ({ reset, ...log }) =>
      dispatch({ kind: 'log', log, reset }),
    )

    return () => source.close()
  }, [run, writer])

  return (
    <FeedContext.Provider value={{ ...state, source: writer }}>
      {children}
    </FeedContext.Provider>
  )
}

export function useRunFeed(): RunFeed {
  return useContext(FeedContext)
}

/** Events for one arm, in order. */
export function useArmEvents(arm: 'warm' | 'cold'): RunEvent[] {
  const { events } = useRunFeed()
  return useMemo(() => events.filter((e) => e.swarm === arm), [events, arm])
}

/** Count of a given event type, optionally scoped to one arm. */
export function useEventCount(type: string, arm?: 'warm' | 'cold'): number {
  const { events } = useRunFeed()
  return useMemo(
    () => events.filter((e) => e.type === type && (!arm || e.swarm === arm)).length,
    [events, type, arm],
  )
}
