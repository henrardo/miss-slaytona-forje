/**
 * WARM, end to end — the cold card plus the layer that is the whole point.
 *
 * Same engine, same lattice, same box size as ColdStackSlide, deliberately:
 * the two cards are the same stack, and the difference between them should be
 * a thing you can SEE rather than a thing you have to diff. Cold's middle row
 * is empty; warm's holds Cognee and the graph it writes into.
 *
 * ── What the memory layer actually is ───────────────────────────────────
 *
 * `cognee[neo4j]==1.6.0`, provisioned onto the pod by swarm/provision_cognee.sh
 * and configured in orchestrator/cognee_layer.py, which sets
 * `GRAPH_DATABASE_PROVIDER=neo4j` and points it at Aura. So **Cognee → Neo4j**
 * is not an association, it is where Cognee puts the graph; without those
 * variables it falls back to an embedded Kuzu store and nothing reaches Aura.
 *
 * The link between Vibe and Cognee is drawn BOTH WAYS on purpose, and that is
 * the measured shape of warm's treatment: the agent may call the MCP tools
 * itself, and the harness also writes each step and injects the retrieved
 * procedure and memory into the next prompt. The MCP half alone made warm
 * byte-identical to cold — agents made zero memory-tool calls across fifteen
 * sessions while being told to use them — which is why the deterministic half
 * exists at all.
 *
 * ── The prompt is the real prompt ───────────────────────────────────────
 *
 * The WARM branch of `_task_prompt` in orchestrator/vibe_agent.py: the same
 * eleven steps in the same order plus three memory steps (4, 5 and 11, marked
 * gold) and a closing note. That asymmetry is deliberate and it is a real
 * confound — warm's list is longer, so warm reads more tokens before it
 * starts and has more steps to work through. The prompt also carries the
 * tools guide and the two blocks the harness injects; those are named in the
 * footer rather than rendered, because they are as long as the card.
 */
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J } from '@/lib/brand'
import { useActivity } from './SourceSparkle'
import type { SlideProps } from './types'
import type { RunEvent } from '@/lib/types'
import {
  BOX,
  FlowChart,
  PromptAside,
  ROW,
  cx,
  cy,
  type FlowEdge,
  type FlowNode,
  type Geom,
  type Live,
} from './StackFlow'
import { PROMPT_HEAD, WARM_CLOSING, WARM_ONLY, WARM_STEPS } from './prompts'
import daytonaGlyph from '@/wordmark/glyphs/daytona-glyph.svg?url'
import mistralM from '@/wordmark/glyphs/mistral-M.svg?url'
import neo4jMark from '@/wordmark/glyphs/neo4j-mark.svg?url'

/**
 * Gold, where cold is blue. The frame is the only thing that carries the arm
 * — the diagram inside stays periwinkle on both cards, so they read as one
 * system twice rather than two systems (see StackFlow's header).
 */
const ACCENT = NEO4J.marigold

/**
 * Cold's lattice, shifted right to open a 40-unit channel down the left edge.
 *
 * Cold runs its checkout edge (1b) straight down INSIDE the left column,
 * because cold's middle row is empty. Warm's is not — Neo4j sits there — so
 * that line would pass through a box, which is the single thing this diagram
 * must not do. The channel is the fix; boxes are otherwise identical, and at
 * 4.5% wider the two cards are indistinguishable side by side.
 */
const GEOM: Geom = { W: 1296, H: 940, COL: [80, 480, 880] }
const C = GEOM.COL
/** The left-hand channel, and the one below the middle row. */
const LEFT = 40
const UNDER = 610

const NODES: FlowNode[] = [
  {
    id: 'runpod',
    col: 0,
    row: 0,
    title: 'RunPod',
    sub: (m) => m.gpu?.split(',')[0] ?? 'one GPU pod per run',
    ink: NEO4J.cream,
    glyph: 'chip',
  },
  {
    id: 'sglang',
    col: 1,
    row: 0,
    title: 'SGLang',
    sub: () => 'OpenAI-compatible server',
    ink: BRANDS.sglang.accent,
    logo: '/brand/sglang-logo-square.svg',
    trigger: 'model_call',
  },
  {
    id: 'model',
    col: 2,
    row: 0,
    title: 'Mistral Small 4',
    sub: (m) => m.model?.split('/').pop() ?? 'served by SGLang',
    ink: BRANDS.mistral.accent,
    logo: '/brand/mistral-model-small.svg',
    trigger: 'model_call',
  },
  {
    id: 'neo4j',
    col: 0,
    row: 1,
    title: 'Neo4j Aura',
    sub: () => 'where the graph lives',
    ink: BRANDS.neo4j.accent,
    logo: neo4jMark,
    trigger: 'step_write',
  },
  {
    id: 'cognee',
    col: 1,
    row: 1,
    title: 'Cognee',
    // Both halves, because either one alone is not the treatment.
    sub: () => 'v1.6.0 · MCP + injected',
    ink: NEO4J.midBaltic,
    glyph: 'graph',
    trigger: 'step_write',
  },
  {
    id: 'vibe',
    col: 2,
    row: 1,
    title: 'Mistral Vibe',
    sub: () => 'hooks.toml · memory tools',
    ink: BRANDS.mistral.accent,
    logo: mistralM,
    trigger: 'tool_call',
  },
  {
    id: 'repo',
    col: 0,
    row: 2,
    title: 'the cloned repo',
    sub: (m) => `${m.fixture ?? 'the fixture'} · Pydantic v1`,
    ink: NEO4J.lightPeriwinkle,
    glyph: 'folder',
    trigger: 'sandbox',
  },
  {
    id: 'output',
    col: 1,
    row: 2,
    title: 'output migration',
    sub: (m) =>
      m.passed == null ? 'the edited tree' : `${m.passed} test(s) passing`,
    ink: NEO4J.lightForest,
    glyph: 'diff',
    trigger: 'sandbox',
  },
  {
    id: 'suite',
    col: 2,
    row: 2,
    title: 'the test suite',
    sub: (m) => `pytest · ${m.attempts} graded`,
    ink: BRANDS.daytona.accent,
    logo: daytonaGlyph,
    trigger: 'sandbox',
  },
]

const EDGES: FlowEdge[] = [
  // The spine keeps cold's numbering, so the two cards can be read against
  // each other. The memory layer is M1 and M2 rather than 8 and 9: it does
  // not happen after step 7, it happens all the way through.
  {
    n: '1a',
    points: [
      [C[0] + BOX.w, cy(0)],
      [C[1] - 8, cy(0)],
    ],
    badge: [C[0] + BOX.w + 38, cy(0)],
  },
  {
    n: '2',
    points: [
      [C[1] + BOX.w, cy(0)],
      [C[2] - 8, cy(0)],
    ],
    badge: [C[1] + BOX.w + 38, cy(0)],
  },
  {
    n: '3',
    points: [
      [cx(GEOM, 2), ROW[0] + BOX.h],
      [cx(GEOM, 2), ROW[1] - 8],
    ],
    badge: [cx(GEOM, 2), ROW[0] + BOX.h + 62],
  },
  {
    n: '4',
    points: [
      [GEOM.W, cy(1)],
      [C[2] + BOX.w + 8, cy(1)],
    ],
    badge: [GEOM.W - 38, cy(1)],
  },
  // The checkout, out of the pod's left edge and down the channel.
  {
    n: '1b',
    points: [
      [C[0], cy(0)],
      [LEFT, cy(0)],
      [LEFT, cy(2)],
      [C[0] - 8, cy(2)],
    ],
    badge: [LEFT, cy(1)],
  },
  // The agent edits the checkout. Cold routes this along the middle row;
  // warm's middle row is full, so it drops below it first.
  {
    n: '5',
    points: [
      [cx(GEOM, 2), ROW[1] + BOX.h],
      [cx(GEOM, 2), UNDER],
      [C[0] + 230, UNDER],
      [C[0] + 230, ROW[2] - 8],
    ],
    badge: [C[0] + 600, UNDER],
  },
  {
    n: '6',
    points: [
      [C[0] + BOX.w, cy(2)],
      [C[1] - 8, cy(2)],
    ],
    badge: [C[0] + BOX.w + 38, cy(2)],
  },
  {
    n: '7',
    points: [
      [C[2], cy(2)],
      [C[1] + BOX.w + 8, cy(2)],
    ],
    badge: [C[2] - 38, cy(2)],
  },
  // THE TREATMENT. Two-way: warm's agent calls the tools, and the harness
  // writes steps and injects what it retrieves back into the next prompt.
  {
    n: 'M1',
    points: [
      [C[2], cy(1)],
      [C[1] + BOX.w + 8, cy(1)],
    ],
    badge: [(C[2] + C[1] + BOX.w) / 2, cy(1)],
    both: true,
    dashed: true,
  },
  {
    n: 'M2',
    points: [
      [C[1], cy(1)],
      [C[0] + BOX.w + 8, cy(1)],
    ],
    badge: [(C[1] + C[0] + BOX.w) / 2, cy(1)],
    dashed: true,
  },
]

export function WarmStackSlide({ onStage }: SlideProps) {
  const { metrics, events, series } = useRunFeed()
  const activity = useActivity()

  const warm = (events as RunEvent[]).filter(
    (e) => e.swarm === 'warm' && e.type === 'ATTEMPT_DONE',
  )
  const live: Live = {
    gpu: metrics?.gpu ?? null,
    model: metrics?.model ?? null,
    fixture: series?.fixture ?? null,
    attempts: warm.length,
    passed: warm.length
      ? Math.max(...warm.map((e) => (e.tests_passed as number) ?? 0))
      : null,
  }

  return (
    <SlideChrome
      title="Warm"
      accent={ACCENT}
      badge="the whole stack"
      focused={onStage}
      footer={
        <span>
          `_task_prompt(memory_enabled=True)` in orchestrator/vibe_agent.py — three
          memory steps, a closing note, the tools guide, and the procedure and
          memory blocks the harness injects
        </span>
      }
    >
      <div className="flex h-full" style={{ gap: 28 }}>
        <FlowChart
          id="warm"
          geom={GEOM}
          nodes={NODES}
          edges={EDGES}
          live={live}
          activity={activity}
          label="Warm, end to end"
        />
        <PromptAside
          arm="warm"
          head={PROMPT_HEAD}
          steps={WARM_STEPS}
          only={WARM_ONLY}
        >
          <p style={{ color: 'hsl(var(--muted))', marginTop: 10 }}>
            {WARM_CLOSING}
          </p>
        </PromptAside>
      </div>
    </SlideChrome>
  )
}
