/**
 * Mirrors of what the harness writes. Derived from the writers themselves —
 * `orchestrator/events.py` (EVENT_TYPES) and `orchestrator/metrics.py`
 * (ArmMetrics, RunMetrics) — not from a sample file, so a field that is
 * usually absent is still typed.
 */

/** Exactly the set declared in orchestrator/events.py. */
export const EVENT_TYPES = [
  'RUN_START',
  'MEMORY_READ',
  'ATTEMPT_START',
  'SANDBOX_CREATED',
  'ATTEMPT_DONE',
  'ATTEMPT_REJECTED',
  'ATTEMPT_ABORTED',
  'INGESTED',
  'DISTILLED',
  'STEP_WRITES',
  'RESTORED',
  'FILE_DONE',
  'MEMORY_WRITE',
  'RUN_END',
] as const

export type EventType = (typeof EVENT_TYPES)[number]

export type Arm = 'warm' | 'cold'

/**
 * Every event is flat: `{t, type, ...payload}`. Unknown types are kept rather
 * than dropped — the harness has retired and added types mid-project, and a
 * deck that silently discards an event it does not recognise would show a
 * quieter run than actually happened.
 */
export interface RunEvent {
  t: number
  type: EventType | string
  swarm?: Arm
  agent?: string
  attempt?: number
  skill_version?: number | null
  tests_passed?: number | null
  exit_code?: number | null
  turns_used?: number | null
  attempt_seconds?: number | null
  attempt_prompt_tokens?: number | null
  attempt_completion_tokens?: number | null
  ended_cleanly?: boolean | null
  parse_ok?: number | null
  parse_total?: number | null
  v1_remaining?: number | null
  create_ms?: number | null
  steps?: number | null
  hits?: number | null
  sources?: string[]
  error_kind?: string
  success?: boolean
  attempts?: number
  [key: string]: unknown
}

export interface PerAttempt {
  attempt: number | null
  skill_version: number | null
  tests_passed: number | null
  v1_remaining?: number | null
  parse_ok: number | null
  parse_total: number | null
  turns: number | null
  seconds: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  ended_cleanly: boolean | null
}

export interface ArmMetrics {
  arm: string
  tests_passed: number
  attempts: number
  converged: boolean
  turns: number
  attempt_seconds: number
  attempt_prompt_tokens: number
  attempt_completion_tokens: number
  distil_seconds: number
  distil_prompt_tokens: number
  distil_completion_tokens: number
  steps_ingested: number
  /**
   * `null` means UNCOUNTED, which is not zero. The live-hook path never
   * back-fills this. Render it as "—", never as 0 — six pod runs were
   * misread exactly that way.
   */
  steps_with_reasoning: number | null
  thought_fallbacks: number | null
  skill_versions: number[]
  distillations: number
  distillations_accepted: number
  memory_tool_calls: number
  per_attempt: PerAttempt[]
}

export interface RunMetrics {
  run_id: string
  gpu: string
  model: string
  commit: string
  skill_version: number
  skill_approx_tokens: number
  skill_dir_sha: string
  /** False means the run is debugging material, not a result. */
  arms_identical: boolean
  known_differences: string[]
  arms: Record<string, ArmMetrics>
  run_seconds: number
  gpu_usd_per_hour: number
}

/**
 * The chart document, mirrored from `orchestrator/series.py`.
 *
 * Read that module's docstring before changing anything here. The document is
 * SELF-DESCRIBING on purpose: it carries its own axes, reference lines, whether
 * y may start at zero, and — the part that matters — a `caveat` per panel
 * saying what would make it misleading. The renderer's job is to obey it, not
 * to make chart decisions of its own.
 *
 *   "If that lives in matplotlib calls it gets retyped by hand into
 *    TypeScript, and the retyping is where 'the floor is 3, not 0' quietly
 *    becomes a y-axis starting at zero."
 *
 * So: no y-axis logic that ignores `y_starts_at_zero`, and no panel rendered
 * without its caveat within reach.
 */
export type PanelKind = 'line' | 'step' | 'scatter' | 'bar' | 'timeline'

export interface SeriesPoint {
  x: number
  y: number | null
  /** Free-form per-point payload; panels use different keys. */
  [key: string]: unknown
}

export interface PanelSeries {
  label: string
  arm?: string
  points: SeriesPoint[]
  [key: string]: unknown
}

export interface PanelAnnotation {
  kind: string
  y?: number
  x?: number
  label?: string
  note?: string
}

export interface SeriesPanel {
  id: string
  title: string
  kind: PanelKind | string
  x_label: string
  y_label: string
  series: PanelSeries[]
  annotations?: PanelAnnotation[]
  y_starts_at_zero?: boolean
  /** What would make this panel misleading. Always render it. */
  caveat?: string
}

export interface SeriesDoc {
  schema_version: number
  scope: 'within_run' | 'across_runs' | string
  run_id?: string
  fixture?: string
  n_runs?: number
  oracle?: Record<string, unknown>
  panels: SeriesPanel[]
  [key: string]: unknown
}

/** One tail of the orchestrator's stdout. */
export interface RunLog {
  file: string
  text: string
  bytes: number
  mtimeMs: number
  /** The event log this transcript named, once it names one. */
  runId?: string | null
}

export interface RunIndexEntry {
  id: string
  kind: string
  mtimeMs: number
  bytes: number
  hasMetrics: boolean
}

/**
 * The treatment, copied from metrics.py TREATMENT_DIFFERENCES. A run whose
 * `known_differences` fall inside this set counts; anything else is a
 * confound.
 */
export const TREATMENT_DIFFERENCES = new Set([
  'hook_files',
  'config_names',
  'tools',
])

export function runCounts(metrics: RunMetrics | null): boolean {
  if (!metrics) return false
  return metrics.known_differences.every((d) => TREATMENT_DIFFERENCES.has(d))
}
