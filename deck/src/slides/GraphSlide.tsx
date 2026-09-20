/**
 * The memory graph, filling up.
 *
 * Every reasoning step the warm swarm writes lands here within a second or two
 * of being written. Nodes arrive, unfold, and are pushed back by the ones that
 * come after them.
 *
 * ── Borrowed from guitar-to-graph, with the reason it works ──────────────
 *
 * That project's force view is the best thing on this machine for watching a
 * graph grow, and its central idea is not the physics, it is the DEPTH MODEL:
 *
 *   "Depth carries AGE — what was just played is nearest and sharpest, and
 *    everything recedes behind it as the music moves on. Nothing is ever
 *    removed; it only gets further away."
 *
 * That is exactly right for a run: the newest reasoning is the thing being
 * talked about, the graph from twenty minutes ago is context, and deleting it
 * would be a lie about what the agent has. So age maps to a perspective
 * divide — not a linear ramp, because linear gives too little separation at
 * the near end, where all the interesting nodes are.
 *
 * Also taken: ticking the simulation inside the rAF loop rather than letting
 * d3 own a timer, unfolding a node over its first moments instead of popping
 * it in, and drawing each edge toward its target rather than snapping it.
 *
 * ── Two things this file does differently ────────────────────────────────
 *
 * 1. IT ONLY ANIMATES ON STAGE. Every card is mounted always — that is how
 *    tiles keep collecting — but a force simulation running in a 10px tile is
 *    pure heat. Off stage the canvas is idle; arriving on stage it settles the
 *    layout in one go (260 ticks, off-screen) so it opens composed rather
 *    than exploding outward in front of an audience.
 *
 * 2. THE BACKING STORE IS CAPPED. The card is inside a CSS transform, so a
 *    canvas sized in canonical units rasterises at the wrong scale; it is
 *    sized in real device pixels instead (`scale` x dpr), capped, because a
 *    3600px-wide buffer repainting at 60fps is the layer budget all over
 *    again. See the note in hud/Hud.tsx.
 */
import { useEffect, useMemo, useRef } from 'react'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { SlideChrome } from '@/hud/SlideChrome'
import { useGraphFeed, type GraphNode } from '@/data/GraphFeed'
import { ALARM, NEO4J } from '@/lib/brand'
import type { SlideProps } from './types'

/** Device pixels. Past this the extra sharpness is not worth the raster. */
const MAX_BACKING = 2400
/** A node easing open. */
const UNFOLD_MS = 900
/** An edge drawing itself toward its target. */
const LINK_MS = 520
/** Lens distance in depth units — a real divide, not a linear ramp. */
const CAMERA = 1.45
/** How much of the depth falloff lands at the near end. <1 favours recent. */
const DEPTH_CURVE = 0.55

/**
 * Node size, as a fraction of the SMALLER canvas side — not of the layout fit.
 *
 * Scaling by the fit was wrong in the obvious direction: a sparse graph gets a
 * large fit, so the eighteen nodes of a short rehearsal rendered as specks,
 * exactly when there was most room for them. Size belongs to the canvas.
 */
const RADIUS: Record<string, number> = {
  ReasoningTrace: 0.026,
  ReasoningStep: 0.012,
  ToolCall: 0.0085,
}

/**
 * How many of the newest nodes get a halo — a COUNT, not a depth threshold.
 *
 * Depth is a fraction of the run's time span, and a short rehearsal has three
 * distinct timestamps, so `depth < 0.06` matched nearly everything and the
 * card bloomed into white blobs. "The most recent few" is what was meant, and
 * it is what survives both an 18-node rehearsal and a 2,500-node series.
 */
const HALO_NEWEST = 5

/**
 * Three labels, three roles — so hue is free to mean something. Trace is the
 * anchor, step is the thinking, call is the doing. A failed call is the only
 * thing that goes red, because red means failure everywhere else in the deck.
 */
const COLOUR: Record<string, string> = {
  ReasoningTrace: NEO4J.lightPeriwinkle,
  ReasoningStep: NEO4J.lightBaltic,
  ToolCall: NEO4J.marigold,
}

interface Sim extends SimulationNodeDatum {
  id: string
  label: string
  at: number
  caption: string
  ok?: boolean | null
  /** When this node arrived on screen, for the unfold. */
  born: number
}
type Edge = SimulationLinkDatum<Sim> & { born: number }

export function GraphSlide({ onStage }: SlideProps) {
  const { nodes, live, staleAgeMs, scope, labels, error } = useGraphFeed()
  const canvas = useRef<HTMLCanvasElement>(null)
  const host = useRef<HTMLDivElement>(null)

  /** The simulation and its data, kept across renders and mutated in place. */
  const rig = useRef<{
    sim: Simulation<Sim, Edge> | null
    nodes: Sim[]
    edges: Edge[]
    byId: Map<string, Sim>
  }>({ sim: null, nodes: [], edges: [], byId: new Map() })

  const total = useMemo(
    () => labels.find((l) => l.label === 'ReasoningStep')?.n ?? 0,
    [labels],
  )

  /** Fold new rows into the simulation without restarting it. */
  useEffect(() => {
    const r = rig.current
    let added = 0
    for (const n of nodes as GraphNode[]) {
      if (r.byId.has(n.id)) continue
      const node: Sim = {
        id: n.id,
        label: n.label,
        at: n.at ?? Date.now(),
        caption: n.caption ?? '',
        ok: n.ok,
        born: performance.now(),
        // Enter from the rim so it visibly arrives rather than appearing in
        // the middle of everything already settled.
        x: (Math.cos(added * 2.4) * 240) | 0,
        y: (Math.sin(added * 2.4) * 240) | 0,
      }
      r.nodes.push(node)
      r.byId.set(n.id, node)
      added++
      const parent = n.parent ? r.byId.get(n.parent) : undefined
      if (parent) r.edges.push({ source: parent, target: node, born: node.born })
    }
    if (!added || !r.sim) return
    r.sim.nodes(r.nodes)
    ;(r.sim.force('link') as ReturnType<typeof forceLink<Sim, Edge>>)?.links(
      r.edges,
    )
    r.sim.alpha(0.6).restart()
  }, [nodes])

  useEffect(() => {
    if (!onStage) return
    const cv = canvas.current
    const box = host.current
    const ctx = cv?.getContext('2d')
    if (!cv || !box || !ctx) return

    let W = 0
    let H = 0
    let dpr = 1
    const resize = () => {
      const rect = box.getBoundingClientRect()
      // Real on-screen size: the card is inside a transform, so the element's
      // own bounding rect is already in device-independent screen pixels.
      const want = Math.min(MAX_BACKING, Math.round(rect.width * devicePixelRatio))
      dpr = rect.width > 0 ? want / rect.width : 1
      W = Math.max(1, Math.round(rect.width))
      H = Math.max(1, Math.round(rect.height))
      cv.width = Math.max(1, Math.round(W * dpr))
      cv.height = Math.max(1, Math.round(H * dpr))
      cv.style.width = '100%'
      cv.style.height = '100%'
      rig.current.sim?.force('centre', forceCenter(0, 0))
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(box)

    const r = rig.current
    if (!r.sim) {
      r.sim = forceSimulation<Sim, Edge>(r.nodes)
        .force(
          'link',
          forceLink<Sim, Edge>(r.edges)
            .id((n) => n.id)
            // A trace holds its steps close; the chain stays readable.
            .distance((l) =>
              (l.source as Sim).label === 'ReasoningTrace' ? 52 : 26,
            )
            .strength(0.5),
        )
        .force(
          'charge',
          forceManyBody<Sim>().strength((n) =>
            n.label === 'ReasoningTrace' ? -420 : -60,
          ),
        )
        .force('centre', forceCenter(0, 0))
        .force(
          'collide',
          // In layout units, which are not canvas units — a constant here is
          // the right thing: it keeps the cloud from self-overlapping whatever
          // size it is eventually drawn at.
          forceCollide<Sim>().radius((n) =>
            n.label === 'ReasoningTrace' ? 26 : 11,
          ),
        )
        .stop() // ticked inside the rAF loop below, never by d3's own timer
      // Settle off-screen so the card opens composed. guitar-to-graph's trick.
      for (let i = 0; i < 260; i++) r.sim.tick()
    }

    let raf = 0
    const frame = (t: number) => {
      const sim = rig.current.sim
      if (sim && sim.alpha() > sim.alphaMin()) sim.tick()
      draw(t)
      raf = requestAnimationFrame(frame)
    }

    function draw(t: number) {
      const r = rig.current
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx!.clearRect(0, 0, W, H)
      if (!r.nodes.length) return

      // Age -> depth. Newest is 0 (nearest), oldest is 1 (furthest).
      let minAt = Infinity
      let maxAt = -Infinity
      for (const n of r.nodes) {
        if (n.at < minAt) minAt = n.at
        if (n.at > maxAt) maxAt = n.at
      }
      const span = Math.max(1, maxAt - minAt)
      // Rank, not fraction. See HALO_NEWEST.
      const newest = new Set(
        [...r.nodes]
          .sort((a, b) => b.at - a.at)
          .slice(0, HALO_NEWEST)
          .map((n) => n.id),
      )
      const depthOf = (n: Sim) => ((maxAt - n.at) / span) ** DEPTH_CURVE
      // A perspective divide, not a linear ramp: most of the falloff belongs
      // at the near end, which is where the new nodes are.
      const zoomOf = (d: number) => CAMERA / (CAMERA + d)

      // Fit the settled layout to the box, once per frame — the cloud grows.
      let rx = 1
      let ry = 1
      for (const n of r.nodes) {
        rx = Math.max(rx, Math.abs(n.x ?? 0))
        ry = Math.max(ry, Math.abs(n.y ?? 0))
      }
      const fit = Math.min((W / 2 - 40) / rx, (H / 2 - 40) / ry, 2.2)
      // The size datum. Node radii are fractions of this, never of `fit`.
      const base = Math.min(W, H)
      const px = (n: Sim) => W / 2 + (n.x ?? 0) * fit * zoomOf(depthOf(n))
      const py = (n: Sim) => H / 2 + (n.y ?? 0) * fit * zoomOf(depthOf(n))

      ctx!.globalCompositeOperation = 'lighter'

      for (const e of r.edges) {
        const a = e.source as Sim
        const b = e.target as Sim
        const grow = Math.min(1, (t - e.born) / LINK_MS)
        if (grow <= 0) continue
        const d = depthOf(b)
        const ax = px(a)
        const ay = py(a)
        ctx!.beginPath()
        ctx!.moveTo(ax, ay)
        ctx!.lineTo(ax + (px(b) - ax) * grow, ay + (py(b) - ay) * grow)
        ctx!.strokeStyle = NEO4J.periwinkle
        ctx!.globalAlpha = 0.3 * (1 - d) + 0.12
        ctx!.lineWidth = Math.max(1, base * 0.0028 * zoomOf(d))
        ctx!.stroke()
      }

      for (const n of r.nodes) {
        const d = depthOf(n)
        const z = zoomOf(d)
        const unfold = Math.min(1, (t - n.born) / UNFOLD_MS)
        // ease-out-back, so a node arrives with a little overshoot
        const e = 1 + 2.2 * (unfold - 1) ** 3 + 1.2 * (unfold - 1) ** 2
        const rad = base * (RADIUS[n.label] ?? 0.014) * z * Math.max(0.05, e)
        const colour = n.ok === false ? ALARM : (COLOUR[n.label] ?? NEO4J.cream)
        // The floor matters. At 0.07 a 129-step run rendered as six bright
        // points and a lot of nothing: the older nodes were technically drawn.
        // Receding is the effect wanted, vanishing is not — the whole claim of
        // this card is that the graph ACCUMULATES.
        ctx!.globalAlpha = (0.72 * (1 - d) + 0.28) * Math.min(1, unfold * 1.6)
        ctx!.beginPath()
        ctx!.arc(px(n), py(n), Math.max(0.6, rad), 0, Math.PI * 2)
        ctx!.fillStyle = colour
        ctx!.fill()
        // The newest few get a halo. It is what makes "this is happening now"
        // legible from the back of a room.
        if (newest.has(n.id)) {
          ctx!.globalAlpha = 0.2
          ctx!.beginPath()
          ctx!.arc(px(n), py(n), Math.max(1, rad * 2.1), 0, Math.PI * 2)
          ctx!.fillStyle = colour
          ctx!.fill()
        }
      }
      ctx!.globalAlpha = 1
      ctx!.globalCompositeOperation = 'source-over'
    }

    raf = requestAnimationFrame(frame)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [onStage])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const n of nodes) c[n.label] = (c[n.label] ?? 0) + 1
    return c
  }, [nodes])

  return (
    <SlideChrome
      title="The memory graph"
      accent={NEO4J.lightPeriwinkle}
      badge={
        !live ? (
          <span style={{ color: ALARM }}>
            CACHED{staleAgeMs ? ` ${Math.round(staleAgeMs / 1000)}s` : ''}
          </span>
        ) : (
          // Which graph this is. Never let an accumulated graph read as
          // "this run".
          <span
            style={{ color: scope === 'run' ? NEO4J.lightForest : NEO4J.marigold }}
          >
            {scope === 'run' ? 'this run' : 'whole graph'}
          </span>
        )
      }
      focused={onStage}
      footer={
        <span>
          {Object.entries(counts)
            .map(([k, v]) => `${v} ${k}`)
            .join(' · ') || 'nothing written yet'}
          {total ? ` · ${total.toLocaleString('en-GB')} steps on Aura` : ''}
          {error ? ` · ${error}` : ''}
        </span>
      }
    >
      <div ref={host} className="relative h-full w-full">
        <canvas ref={canvas} aria-hidden style={{ display: 'block' }} />
        {nodes.length === 0 ? (
          <div
            className="font-pixel absolute inset-0 flex items-center justify-center"
            style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
          >
            {live
              ? 'no reasoning written yet — cold writes nothing here'
              : 'graph unreachable; showing the last good read'}
          </div>
        ) : null}
      </div>
    </SlideChrome>
  )
}
