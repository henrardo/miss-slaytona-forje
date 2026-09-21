/**
 * COLD, end to end — a flow chart, drawn the way flow charts are drawn.
 *
 * This replaced the AIP distillation card, which described a mechanism this
 * project no longer has.
 *
 * The lattice, the elbow router, the glyphs and the prompt document are in
 * StackFlow.tsx, shared with the warm card. This file is the cold arm's own
 * nodes, edges and prompt, and nothing else — the two cards must stay
 * comparable at a glance, which two hand-maintained copies would not.
 *
 * THE ROWS ARE THE STORY, top to bottom: the machine that serves the model,
 * the agent that uses it, the work it does. Each arrow carries its step
 * number in a badge ON the line, so the order is readable without a legend.
 *
 * ── The prompt is the real prompt ───────────────────────────────────────
 *
 * Assembled by `_task_prompt` in orchestrator/vibe_agent.py; what is rendered
 * is the COLD branch — the same eleven steps in the same order, without the
 * three memory steps and the closing note that only warm gets. That asymmetry
 * is deliberate in the harness (warm reads more before it starts) and it is
 * why this card can only honestly be labelled for one arm.
 *
 * Live where there is anything live: GPU and model come off the run's metrics,
 * the fixture off the chart document, and a box lights when cold does the
 * thing it names.
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
import { COLD_STEPS, PROMPT_HEAD } from './prompts'
import daytonaGlyph from '@/wordmark/glyphs/daytona-glyph.svg?url'
import mistralM from '@/wordmark/glyphs/mistral-M.svg?url'

/**
 * Periwinkle, the deck's own blue — not ARM_COLOR.cold's marigold. This card
 * is the STACK, not the series: nothing on it is plotted, and the boxes,
 * connectors and badges are periwinkle, so a gold rim and header would read
 * as a second, contradicting colour system. Marigold still means "the cold
 * arm" wherever a number is drawn.
 */
const ACCENT = NEO4J.periwinkle

/** Three columns, three rows. Cold's middle row is empty by design. */
const GEOM: Geom = { W: 1240, H: 940, COL: [24, 424, 824] }

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
    id: 'vibe',
    col: 2,
    row: 1,
    title: 'Mistral Vibe',
    sub: () => 'no hooks · no memory',
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

const C = GEOM.COL

const EDGES: FlowEdge[] = [
  // Along the top row: the pod brings up the server, the server serves the model.
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
  // Down the right-hand column: the model into the agent loop.
  {
    n: '3',
    points: [
      [cx(GEOM, 2), ROW[0] + BOX.h],
      [cx(GEOM, 2), ROW[1] - 8],
    ],
    badge: [cx(GEOM, 2), ROW[0] + BOX.h + 62],
  },
  // The prompt, in from the right.
  {
    n: '4',
    points: [
      [GEOM.W, cy(1)],
      [C[2] + BOX.w + 8, cy(1)],
    ],
    badge: [GEOM.W - 38, cy(1)],
  },
  // The pod also lays down the checkout, straight down the left column.
  {
    n: '1b',
    points: [
      [C[0] + 70, ROW[0] + BOX.h],
      [C[0] + 70, ROW[2] - 8],
    ],
    badge: [C[0] + 70, (ROW[0] + BOX.h + ROW[2]) / 2],
  },
  // The agent edits that checkout: out of its left edge, along the middle
  // channel, and down into the top of the repo. The one long path on the
  // card, and the reason the middle row is otherwise empty.
  {
    n: '5',
    points: [
      [C[2], cy(1)],
      [C[0] + 230, cy(1)],
      [C[0] + 230, ROW[2] - 8],
    ],
    badge: [C[0] + 560, cy(1)],
  },
  // Along the bottom row: the edited tree, and the suite that judges it.
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
]

export function ColdStackSlide({ onStage }: SlideProps) {
  const { metrics, events, series } = useRunFeed()
  const activity = useActivity()

  const cold = (events as RunEvent[]).filter(
    (e) => e.swarm === 'cold' && e.type === 'ATTEMPT_DONE',
  )
  const live: Live = {
    gpu: metrics?.gpu ?? null,
    model: metrics?.model ?? null,
    // The fixture is named by the chart document, not by the metrics file.
    fixture: series?.fixture ?? null,
    attempts: cold.length,
    passed: cold.length
      ? Math.max(...cold.map((e) => (e.tests_passed as number) ?? 0))
      : null,
  }

  return (
    <SlideChrome
      title="Cold"
      accent={ACCENT}
      badge="the whole stack"
      focused={onStage}
      footer={
        <span>
          the prompt is `_task_prompt(memory_enabled=False)` in
          orchestrator/vibe_agent.py — warm gets three more steps and a closing note
        </span>
      }
    >
      <div className="flex h-full" style={{ gap: 28 }}>
        <FlowChart
          id="cold"
          geom={GEOM}
          nodes={NODES}
          edges={EDGES}
          live={live}
          activity={activity}
          label="Cold, end to end"
        />
        <PromptAside arm="cold" head={PROMPT_HEAD} steps={COLD_STEPS} />
      </div>
    </SlideChrome>
  )
}
