import { useState } from 'react'
import { RunFeedProvider, type Source } from '@/data/RunFeed'
import { GraphFeedProvider } from '@/data/GraphFeed'
import { Hud } from '@/hud/Hud'

/**
 * THE DEMO RUN IS WHAT THE DECK OPENS ON. Nothing else is safe.
 *
 * Every card that reads per-attempt data — the three measures, Daytona
 * verification, Tokens head to head — needs a run that actually migrated
 * something. A bare URL used to follow the newest `rehearsal-*`, and a
 * rehearsal is `scripts/rehearse_loop.py` driving the loop against a SCRIPTED
 * model: it writes `VALUE = 2` into one file, so its v1-surface count is 0 on
 * every attempt and its chart document has no closeness panel at all. The
 * cards were correct and the run was a plumbing test, which on a projector is
 * indistinguishable from a broken deck. It read as "nothing" twice.
 *
 * So the pin has a default. `?run=` still overrides it — that is the same
 * mechanism, with a value — and `?run=newest` opts back into following
 * whichever run is freshest, which is what you want while a pod run is in
 * flight and being watched.
 */
const DEFAULT_RUN = 'swarm-1789998106'

/** `?run=newest` (or `latest`) follows the newest run of the chosen kind. */
const FOLLOW_NEWEST = new Set(['newest', 'latest', 'live'])

export default function App() {
  const params = new URLSearchParams(window.location.search)
  const asked = params.get('run')
  const pinned =
    asked && FOLLOW_NEWEST.has(asked.toLowerCase()) ? null : (asked ?? DEFAULT_RUN)

  // The switch only decides which kind "newest" means, so it matters only
  // when nothing is pinned. `?source=live` / `swarm` picks the pod's runs,
  // anything else leaves it on replay.
  const source = params.get('source')
  const [kind, setKind] = useState<Source>(
    source === 'swarm' || source === 'live' ? 'swarm' : 'rehearsal',
  )

  return (
    <RunFeedProvider run={pinned ?? undefined} source={kind}>
      {/* Inside RunFeed: the graph is scoped to whichever run is followed. */}
      <GraphFeedProvider>
        <Hud onSource={setKind} sourceLocked={!!pinned} />
      </GraphFeedProvider>
    </RunFeedProvider>
  )
}
