/**
 * The code graph, as a graph.
 *
 * ONE POINT: the codebase IS nodes and edges, so "which modules does
 * everything depend on" is a read. Nothing is generated, so nothing drifts
 * — `code_brief` in orchestrator/cognee_layer.py says it in its own
 * docstring: "SearchType.CODE reads graph indexes only, with no LLM and no
 * embedding call."
 *
 * ── It is the live graph ───────────────────────────────────────────────
 *
 * Every node and edge comes out of Aura, over the HTTP Query API: the
 * `CodeSymbol` nodes Cognee extracted and the relationships it found
 * between them — `implements`, `calls`, `has_method`, `instantiates`.
 *
 * An earlier version walked the fixture on disk and re-derived an import
 * graph. It looked the same and it was the wrong thing: a picture of the
 * codebase rather than of the graph the claim is about.
 *
 * THE CUT IS EXPLICIT. x12sdk's symbol graph is 674 nodes and 680 edges,
 * and 674 nodes is a grey cloud at slide size. The read is whole; the
 * endpoint ranks by degree, keeps the top N and keeps the edges between
 * the survivors, and the badge says how many of how many are on screen.
 * Silently drawing a subset would be the one thing a card about
 * determinism must not do.
 *
 * ── The render ─────────────────────────────────────────────────────────
 *
 * d3-force onto a canvas, after the pattern in the senegraph repo's
 * GraphModal: link + charge + centre + collide, radial-gradient node
 * bodies, labels on the nodes that earn one. Canvas rather than SVG
 * because a hundred nodes re-rendered through React every tick is the
 * layer storm the Hud exists to avoid — and the simulation only runs on
 * the board.
 *
 * DRAG AND CLICK. A pointer-down inside a node's radius pins it to the
 * cursor (`fx`/`fy`) and re-heats the simulation, so pulling one symbol
 * out shows what is attached to it; releasing unpins. A press that does
 * not move selects instead: the node, its label and its edges light, and
 * everything else dims, which is the only way to read a single symbol's
 * neighbourhood out of a hairball. Clicking the background clears it.
 *
 * Hit-testing happens in GRAPH coordinates, not screen ones: the canvas
 * carries the fit-to-box transform AND the card's own CSS scale, so the
 * pointer position has to come back through both or the hit lands
 * somewhere else entirely. The transform is kept in a ref by the draw
 * loop, which is the only thing that knows it.
 */
import { useEffect, useRef, useState } from 'react'
import {
  forceCenter,
  forceCollide,
  forceX,
  forceY,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'
import neo4jMark from '@/wordmark/glyphs/neo4j-mark.svg?url'

const ACCENT = BRANDS.neo4j.accent

interface ApiNode {
  id: string
  label: string
  inDegree: number
  degree: number
}
interface ApiGraph {
  /** The repo actually read, which may not be the one asked for. */
  repo: string
  totalNodes: number
  totalEdges: number
  nodes: ApiNode[]
  edges: { source: string; target: string; type: string }[]
}

interface SimNode extends ApiNode, SimulationNodeDatum {
  x?: number
  y?: number
  r: number
}

/** d3 rewrites `source`/`target` from id to node object on the first tick. */
interface SimLink extends SimulationLinkDatum<SimNode> {
  source: string | SimNode
  target: string | SimNode
}

/** Radius from degree: the size of a node IS how connected it is. */
const radius = (degree: number) => 6 + Math.sqrt(degree) * 3.6

/** A symbol earns a label when enough touches it to be worth reading. */
const LABEL_AT = 8

function useCodeGraph(repo: string | null): ApiGraph | null {
  const [g, setG] = useState<ApiGraph | null>(null)
  useEffect(() => {
    if (!repo) return
    let alive = true
    void fetch(`/api/code-graph?repo=${encodeURIComponent(repo)}`)
      .then((r) => r.json())
      .then((j: ApiGraph & { error?: string }) => {
        if (alive && !j.error) setG(j)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [repo])
  return g
}

function Graph({
  graph,
  running,
  scale,
}: {
  graph: ApiGraph
  running: boolean
  /** The card's own transform scale, so the backing store is crisp on stage. */
  scale: number
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const frame = useRef<number>(0)
  const sim = useRef<Simulation<SimNode, undefined> | null>(null)
  /** The draw loop's current fit-to-box transform, for hit-testing. */
  const view = useRef({ zoom: 1, cx: 0, cy: 0, w: 0, h: 0, dpr: 1 })
  const nodesRef = useRef<SimNode[]>([])
  const dragging = useRef<SimNode | null>(null)
  const moved = useRef(false)
  const [picked, setPicked] = useState<string | null>(null)
  const pickedRef = useRef<string | null>(null)
  pickedRef.current = picked

  useEffect(() => {
    const el = canvas.current
    const box = wrap.current
    if (!el || !box) return

    // No x/y: d3 seeds its own spiral. See the note on SimNode.
    const nodes: SimNode[] = graph.nodes.map((n) => ({
      ...n,
      r: radius(n.degree),
    }))
    const byId = new Map(nodes.map((n) => [n.id, n]))
    const links: SimLink[] = graph.edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ source: e.source, target: e.target }))

    const s = forceSimulation(nodes)
      .force(
        'link',
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(70)
          .strength(0.35),
      )
      // `distanceMax` and the x/y forces are both about the same thing: a
      // fifth of these modules import nothing and are imported by nothing,
      // so the link force never pulls them back. Unbounded charge threw
      // them to the edges and the fit-to-box then squeezed the connected
      // core into a knot in the middle.
      .force(
        'charge',
        forceManyBody<SimNode>()
          .strength((d) => -d.r * 9)
          .distanceMax(340),
      )
      .force('center', forceCenter(0, 0).strength(0.08))
      .force('x', forceX(0).strength(0.06))
      .force('y', forceY(0).strength(0.09))
      .force('collide', forceCollide<SimNode>((d) => d.r + 6).iterations(1))
      .alphaDecay(0.025)
      .velocityDecay(0.4)
    sim.current = s
    nodesRef.current = nodes
    if (!running) {
      // Settle without painting every frame: at home the card is a texture.
      s.tick(220)
      s.stop()
    }

    const draw = () => {
      const ctx = el.getContext('2d')
      if (!ctx) return
      const dpr = (window.devicePixelRatio || 1) * scale
      const w = Math.max(1, Math.round(box.clientWidth * dpr))
      const h = Math.max(1, Math.round(box.clientHeight * dpr))
      if (el.width !== w || el.height !== h) {
        el.width = w
        el.height = h
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, w, h)

      // Fit the settled cloud to the box, so the graph never drifts off.
      let minX = Infinity
      let maxX = -Infinity
      let minY = Infinity
      let maxY = -Infinity
      for (const n of nodes) {
        minX = Math.min(minX, (n.x ?? 0) - n.r)
        maxX = Math.max(maxX, (n.x ?? 0) + n.r)
        minY = Math.min(minY, (n.y ?? 0) - n.r)
        maxY = Math.max(maxY, (n.y ?? 0) + n.r)
      }
      const pad = 46 * dpr
      const zoom = Math.min(
        (w - pad * 2) / Math.max(1, maxX - minX),
        (h - pad * 2) / Math.max(1, maxY - minY),
      )
      const cx = (minX + maxX) / 2
      const cy = (minY + maxY) / 2
      view.current = { zoom, cx, cy, w, h, dpr }
      ctx.translate(w / 2, h / 2)
      ctx.scale(zoom, zoom)
      ctx.translate(-cx, -cy)

      const sel = pickedRef.current
      const near = new Set<string>()
      if (sel) {
        near.add(sel)
        for (const l of links) {
          const a = (l.source as SimNode).id
          const b = (l.target as SimNode).id
          if (a === sel) near.add(b)
          if (b === sel) near.add(a)
        }
      }

      ctx.lineWidth = 1.1 / zoom
      for (const lit of [false, true]) {
        ctx.strokeStyle = lit
          ? alpha(ACCENT, 0.85)
          : alpha(NEO4J.periwinkle, sel ? 0.1 : 0.3)
        ctx.lineWidth = (lit ? 2 : 1.1) / zoom
        ctx.beginPath()
        for (const l of links) {
          const a = l.source as SimNode
          const b = l.target as SimNode
          const on = !!sel && (a.id === sel || b.id === sel)
          if (on !== lit) continue
          ctx.moveTo(a.x ?? 0, a.y ?? 0)
          ctx.lineTo(b.x ?? 0, b.y ?? 0)
        }
        ctx.stroke()
      }

      for (const n of nodes) {
        const nx = n.x ?? 0
        const ny = n.y ?? 0
        ctx.globalAlpha = !sel || near.has(n.id) ? 1 : 0.3
        const g = ctx.createRadialGradient(
          nx - n.r * 0.35,
          ny - n.r * 0.4,
          n.r * 0.05,
          nx,
          ny,
          n.r,
        )
        // The more depends on it, the hotter it reads.
        const hot = Math.min(1, n.degree / 20)
        g.addColorStop(0, hot > 0.4 ? ACCENT : NEO4J.lightPeriwinkle)
        g.addColorStop(1, hot > 0.4 ? NEO4J.midBaltic : NEO4J.deepPeriwinkle)
        ctx.beginPath()
        ctx.arc(nx, ny, n.r, 0, Math.PI * 2)
        ctx.fillStyle = g
        ctx.fill()
        ctx.lineWidth = (n.id === sel ? 3 : 1.4) / zoom
        ctx.strokeStyle = n.id === sel ? NEO4J.cream : alpha(NEO4J.cream, 0.35)
        ctx.stroke()
        ctx.globalAlpha = 1
      }

      for (const n of nodes) {
        // A selected node always gets its name, however small it is.
        if (n.degree < LABEL_AT && n.id !== sel) continue
        if (sel && !near.has(n.id)) continue
        const fs = Math.max(12, 15 / zoom) * dpr
        ctx.font = `${fs}px 'VT323', monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const nx = n.x ?? 0
        const y = (n.y ?? 0) + n.r + fs * 0.9
        const wTxt = ctx.measureText(n.label).width
        ctx.fillStyle = alpha('#1b1830', 0.8)
        ctx.fillRect(
          nx - wTxt / 2 - 3 / zoom,
          y - fs * 0.6,
          wTxt + 6 / zoom,
          fs * 1.2,
        )
        ctx.fillStyle = NEO4J.cream
        ctx.fillText(n.label, nx, y)
      }

      if (running) frame.current = requestAnimationFrame(draw)
    }

    draw()
    return () => {
      cancelAnimationFrame(frame.current)
      s.stop()
    }
  }, [graph, running, scale])

  /** Screen pointer -> graph coordinates, back through both transforms. */
  const toGraph = (e: React.PointerEvent) => {
    const box = wrap.current
    const v = view.current
    if (!box || !v.zoom) return null
    const r = box.getBoundingClientRect()
    // The rect is post-CSS-scale, so normalise through it rather than
    // assuming canvas pixels and screen pixels are the same thing.
    const px = ((e.clientX - r.left) / r.width) * v.w
    const py = ((e.clientY - r.top) / r.height) * v.h
    return {
      x: (px - v.w / 2) / v.zoom + v.cx,
      y: (py - v.h / 2) / v.zoom + v.cy,
    }
  }

  const hit = (e: React.PointerEvent) => {
    const g = toGraph(e)
    if (!g) return null
    let best: SimNode | null = null
    let bestD = Infinity
    for (const n of nodesRef.current) {
      const dx = (n.x ?? 0) - g.x
      const dy = (n.y ?? 0) - g.y
      const d = Math.hypot(dx, dy)
      if (d <= n.r + 4 && d < bestD) {
        best = n
        bestD = d
      }
    }
    return best
  }

  const onDown = (e: React.PointerEvent) => {
    e.stopPropagation()
    const n = hit(e)
    moved.current = false
    if (!n) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragging.current = n
    n.fx = n.x
    n.fy = n.y
    // Re-heat, or a settled simulation will not follow the node.
    sim.current?.alphaTarget(0.25).restart()
  }

  const onMove = (e: React.PointerEvent) => {
    e.stopPropagation()
    const n = dragging.current
    if (!n) return
    const g = toGraph(e)
    if (!g) return
    moved.current = true
    n.fx = g.x
    n.fy = g.y
  }

  const onUp = (e: React.PointerEvent) => {
    e.stopPropagation()
    const n = dragging.current
    if (n) {
      n.fx = null
      n.fy = null
      dragging.current = null
      sim.current?.alphaTarget(0)
    }
    // A press that did not move is a click: select, or clear.
    if (!moved.current) {
      const h = hit(e)
      setPicked((cur) => (h && h.id !== cur ? h.id : null))
    }
  }

  return (
    <div ref={wrap} className="relative h-full w-full">
      <canvas
        ref={canvas}
        className="block h-full w-full"
        style={{
          // Inert at home: a tile is a texture, and a canvas that ate the
          // click would be a card that cannot be put on the board.
          pointerEvents: running ? 'auto' : 'none',
          cursor: 'grab',
          touchAction: 'none',
        }}
        onPointerDown={running ? onDown : undefined}
        onPointerMove={running ? onMove : undefined}
        onPointerUp={running ? onUp : undefined}
        onPointerCancel={running ? onUp : undefined}
        onClick={(e) => e.stopPropagation()}
      />
      {/* The click target is the canvas, so the card must not also treat a
          press on it as "send me home". */}
      <span className="sr-only">{picked ?? ''}</span>
    </div>
  )
}

export function CodeGraphSlide({ onStage, scale }: SlideProps) {
  const { series } = useRunFeed()
  const graph = useCodeGraph(series?.fixture ?? 'x12sdk')

  const top = graph ? [...graph.nodes].sort((a, b) => b.degree - a.degree)[0] : null

  return (
    <SlideChrome
      title="The code graph"
      accent={ACCENT}
      mark={neo4jMark}
      badge={
        graph
          ? `${graph.repo} · ${graph.nodes.length} of ${graph.totalNodes} symbols`
          : 'a read, not a summary'
      }
      focused={onStage}
      footer={
        <span>
          live from Aura over the Query API: the CodeSymbol nodes Cognee extracted
          and the edges it found between them
          {graph
            ? ` · the ${graph.totalNodes}-node graph, cut to its ${graph.nodes.length} most connected`
            : ''}
        </span>
      }
    >
      <div className="flex h-full flex-col">
        <h3
          className="heading-solid shrink-0"
          style={{ fontSize: pt(44), color: alpha(NEO4J.cream, 0.95) }}
        >
          {top
            ? `Ask what the codebase leans on and it is a read: ${top.label}, touched by ${top.degree}`
            : 'Ask it twice, get the same answer — nothing is generated'}
        </h3>
        <div className="min-h-0 flex-1">
          {graph ? (
            <Graph graph={graph} running={onStage} scale={scale} />
          ) : (
            <p
              className="font-pixel"
              style={{ fontSize: pt(26), color: 'hsl(var(--muted))' }}
            >
              reading the code graph from Aura…
            </p>
          )}
        </div>
      </div>
    </SlideChrome>
  )
}
