import { useState } from 'react'
import { RunFeedProvider, type Source } from '@/data/RunFeed'
import { GraphFeedProvider } from '@/data/GraphFeed'
import { Hud } from '@/hud/Hud'

/**
 * Live or rehearsal.
 *
 * Two views, identical cards. LIVE follows the newest `swarm-*` run — the pod.
 * REHEARSAL follows the newest `rehearsal-*` — `scripts/rehearse_loop.py`
 * driving the same loop locally against a scripted model, which is the pass
 * being coded during the talk. The switch lives in the bottom rail and changes
 * exactly one thing: which file the collector tails.
 */
export default function App() {
  // `?run=<id>` pins a specific run and overrides the switch — for rehearsing
  // against a finished one. Without it the deck follows whatever is newest of
  // the chosen kind and re-latches when a fresh run starts, so it can be on
  // the projector before launch.
  const params = new URLSearchParams(window.location.search)
  const pinned = params.get('run')
  const [source, setSource] = useState<Source>(
    params.get('source') === 'rehearsal' ? 'rehearsal' : 'swarm',
  )

  return (
    <RunFeedProvider run={pinned ?? undefined} source={source}>
      {/* Inside RunFeed: the graph is scoped to whichever run is followed. */}
      <GraphFeedProvider>
        <Hud onSource={setSource} sourceLocked={!!pinned} />
      </GraphFeedProvider>
    </RunFeedProvider>
  )
}
