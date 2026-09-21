/**
 * The collector.
 *
 * Serves `runs/` — the orchestrator's own output directory — over HTTP, and
 * tails it. Nothing here parses semantics; it moves bytes the harness already
 * wrote. The rule from the harness applies to the deck too: read what was
 * actually emitted, never recompute it from something else.
 *
 * Wire:
 *   GET /api/runs                    -> index of every run found on disk
 *   GET /api/runs/:id                -> { events, metrics } for one run, whole
 *   GET /api/stream[?run=][&kind=]   -> SSE. Snapshot, then deltas as lines land.
 *   GET /api/log[?file=]             -> the orchestrator's own stdout, whole
 *   GET /api/series/:id              -> the harness's chart document for a run
 *   GET /api/series-across[?file=]   -> a cross-run chart document
 *   GET /api/skills                  -> every distilled skill version, sized
 *   GET /api/skills/:v               -> one version's full text
 *   GET /api/tokens                  -> every run's token spend, oldest first
 *   GET /api/reasoning[?cap=]        -> the newest packaged agent's transcripts
 *   GET /api/attempts?run=           -> every graded attempt of one run
 *   GET /api/verification            -> graded attempts + the code each submitted
 *   GET /api/doc/cross-run           -> runs/cross-run.md
 *   GET /api/source?file=            -> a whitelisted repo source file
 *
 * `.jsonl` grows line by line while a run is in flight, so the stream keeps a
 * byte offset per file and emits only what is new. Without `?run`, it follows
 * whichever run is newest and re-latches when a fresher one appears — so the
 * deck can be open on stage before the run is launched.
 *
 * `?kind=` narrows "newest" to one writer prefix. That is the whole of the
 * live/rehearsal switch: a pod run writes `swarm-*.jsonl`, a local rehearsal
 * writes `rehearsal-*.jsonl`, and the deck follows the newest of whichever it
 * is asked for. Same cards, same wire, different source.
 *
 * ── The series document is COMPUTED BY THE HARNESS, not by this file ──────
 *
 * `orchestrator/series.py` turns an event log into a self-describing chart
 * document — axes, reference lines, whether y may start at zero, and a caveat
 * per panel saying what would make it misleading. Its own docstring says it
 * exists so that "the figures are going to be rebuilt as React components" and
 * the domain knowledge survives the port.
 *
 * So the deck does not re-derive any of that in TypeScript. It shells out to
 * the repo's venv and asks the real module, which also means a run that never
 * wrote a `-series.json` still charts — rehearsals write none. Results are
 * cached on (size, mtime), so a live run pays for it once per append.
 */
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

export interface RunsDataOptions {
  /** Absolute path to the harness `runs/` directory. */
  runsDir: string
  /** Repo root — for the venv python and `orchestrator.series`. */
  repoRoot: string
  /** Debounce on filesystem events, ms. */
  debounceMs?: number
}

/**
 * How often `runs/` is re-read while a client is listening.
 *
 * One second: fast enough that an attempt landing looks immediate, slow enough
 * that a full stat of the directory is free. See `startWatching` for why this
 * exists at all rather than relying on the watcher.
 */
const POLL_MS = 1000

interface RunIndexEntry {
  id: string
  /** `swarm`, `rehearsal`, `m4`, `m3`, … — the writer's own prefix. */
  kind: string
  mtimeMs: number
  bytes: number
  hasMetrics: boolean
}

interface Client {
  res: ServerResponse
  /** Pinned run id, or null to follow the newest. */
  pinned: string | null
  /** Writer prefix to narrow "newest" to, or null for any. */
  kind: string | null
  /** Run id this client is currently receiving. */
  following: string | null
  /** Log file this client is currently tailing, and how far. */
  logFile: string | null
  logAt: number
}

const isJsonl = (f: string) => f.endsWith('.jsonl')
const metricsNameFor = (id: string) => `${id}-metrics.json`

function runKind(id: string): string {
  const m = /^([a-z0-9]+?)-/i.exec(id)
  return m ? m[1] : id
}

/**
 * The orchestrator's stdout.
 *
 * Not paired with a run id, deliberately. A driver script names its own log
 * (`x12-series-4.log`, `run30.log`) and only reveals which event log it wrote
 * on its LAST line — `event log: runs/<id>.jsonl` — which is no use while the
 * run is still going. So the terminal follows the newest `.log` by mtime and
 * reports the run id if and when the log names one.
 */
const isLog = (f: string) => f.endsWith('.log')

/**
 * Repo files the deck may read, by exact path. A WHITELIST, not a sandbox
 * check: this endpoint exists so two cards can show their own integration
 * source, and "any file under the repo root" would also mean `.env`.
 */
const SOURCE_WHITELIST = new Set([
  'scripts/launch_sglang.sh',
  'harness/vibe-config.template.toml',
  'orchestrator/vibe_agent.py',
  'orchestrator/ingest.py',
  'orchestrator/sandbox.py',
  'orchestrator/distill.py',
  'orchestrator/skills.py',
  'orchestrator/sync.py',
  'harness/memory_step_hook.py',
  'harness/reasoning_relay.py',
  // The fixture report: the Daytona card reads the baseline-vs-answer-key
  // pair out of it rather than restating the numbers in the component.
  'runs/x12sdk-report.md',
])
const EVENT_LOG_LINE = /^event log:\s*runs\/([\w.-]+)\.jsonl/m

/**
 * One arm's spend, and one run's pair of them. See `/api/tokens`.
 *
 * PER ARM, not summed. There are two agents in every run — warm-0 and
 * cold-0 — and the whole comparison is between them, so an endpoint that
 * added them together would destroy the only thing the card is for.
 */
interface ArmTokens {
  in: number
  out: number
  distilIn: number
  distilOut: number
  attempts: number
  turns: number
  seconds: number
  passed: number
}

interface RunTokens {
  id: string
  warm: ArmTokens
  cold: ArmTokens
  /** Wall clock, first event to last. What the GPU is billed for. */
  runSeconds: number
  /**
   * Wall seconds in which SOME agent was generating, which is the only
   * honest denominator for a tokens-per-second figure that aggregates both
   * arms. See `activeSeconds()`.
   */
  activeSeconds: number
  counts: boolean
}

const NO_ARM: ArmTokens = {
  in: 0,
  out: 0,
  distilIn: 0,
  distilOut: 0,
  attempts: 0,
  turns: 0,
  seconds: 0,
  passed: 0,
}

/**
 * How long this run was actually generating, in wall seconds.
 *
 * NEITHER OF THE TWO EASY NUMBERS IS RIGHT.
 *
 *   `run_seconds` is wall clock, and a third of it is idle: grading in
 *   Daytona, distillation, sandbox creation, and both arms waiting on the
 *   `AttemptSync` barrier. Dividing both arms' tokens by it understates
 *   throughput — measured on swarm-1789987670, 2,304 s against 1,611 s of
 *   generating.
 *
 *   The two arms' `attempt_seconds` SUMMED is worse, because the arms run
 *   CONCURRENTLY. Adding their clocks together counts the same wall second
 *   twice and makes concurrency look like a slowdown: 2,746 s, i.e. longer
 *   than the run.
 *
 * So: per ROUND — `AttemptSync` holds the arms in step, one attempt each —
 * take the longer of the two attempts, because that is how much wall time
 * that round consumed while at least one agent was generating. Sum the
 * rounds. An unpaired attempt (one arm outlived the other's budget) ran
 * alone and contributes its own seconds.
 *
 * Reads `per_attempt[].seconds`, which `orchestrator/vibe_agent.py` already
 * reports with the harness's own bookkeeping subtracted — so the idle this
 * is trying to exclude is excluded at source, not estimated here.
 */
function activeSeconds(
  warm: Record<string, number>[] | undefined,
  cold: Record<string, number>[] | undefined,
): number {
  const w = (warm ?? []).map((p) => Number(p?.seconds) || 0)
  const c = (cold ?? []).map((p) => Number(p?.seconds) || 0)
  let total = 0
  for (let i = 0; i < Math.max(w.length, c.length); i++) {
    total += Math.max(w[i] ?? 0, c[i] ?? 0)
  }
  return total
}

/**
 * The agents' own transcripts, out of the packaged run artifacts.
 *
 * `scripts/package_run.py` brings each agent's `$VIBE_HOME` home off the pod,
 * so `runs/exp<n>-artifacts/home/agent-<arm>-0/.vibe/logs/session/session_<id>`
 * holds the REAL session: `messages.jsonl`, one JSON object per message, and
 * `meta.json` with the session's clock and which agent it was. (Written with
 * no glob in it on purpose: a `*` followed by a slash ends this comment.)
 *
 * THE THOUGHT IS THE ASSISTANT'S `content`. Measured against
 * Mistral-Small-4-119B on SGLang: `reasoning_content` comes back None and
 * the model's reasoning arrives as ordinary assistant content beside the
 * tool call it justifies — `scripts/rehearse_loop.py` has the same note. So
 * there is no separate reasoning channel to read here, and a card that
 * looked for one would find every step blank.
 *
 * A STEP is an assistant message plus the tool results that answered it.
 * Vibe writes them as separate lines, so they are paired back up here
 * rather than in the component.
 */
const SESSION_SKIP = new Set(['__pycache__', 'node_modules', '.git', 'plots'])

/** Every `messages.jsonl` under `runs/`, depth-capped. */
function findSessions(root: string, depth = 0): string[] {
  if (depth > 9) return []
  let entries: fs.Dirent[]
  try {
    entries = fs.readdirSync(root, { withFileTypes: true })
  } catch {
    return []
  }
  const out: string[] = []
  for (const e of entries) {
    if (e.isDirectory()) {
      if (SESSION_SKIP.has(e.name)) continue
      out.push(...findSessions(path.join(root, e.name), depth + 1))
    } else if (e.name === 'messages.jsonl') {
      out.push(path.join(root, e.name))
    }
  }
  return out
}

interface ReasoningStep {
  n: number
  thought: string
  toolName: string | null
  toolArgs: string | null
  /** null when the tool reports no exit code — not every tool has one. */
  ok: boolean | null
  observation: string | null
}

const clipTo = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s)

/** One session, paired into steps. */
function readSession(file: string, cap: number) {
  let meta: Record<string, unknown> = {}
  try {
    meta = JSON.parse(
      fs.readFileSync(path.join(path.dirname(file), 'meta.json'), 'utf8'),
    )
  } catch {
    /* a session with no meta still has its messages */
  }
  const rows: Record<string, unknown>[] = []
  try {
    for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
      if (!line.trim()) continue
      try {
        rows.push(JSON.parse(line))
      } catch {
        /* a half-written last line: the run was packaged mid-flight */
      }
    }
  } catch {
    return null
  }
  if (!rows.length) return null

  const task = rows.find((r) => r.role === 'user')?.content
  const steps: ReasoningStep[] = []
  let n = 0
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i]
    if (r.role !== 'assistant') continue
    const thought = String(r.content ?? '').trim()
    const call = (r.tool_calls as Record<string, any>[] | undefined)?.[0]
    // A turn with neither thought nor tool call is Vibe's own bookkeeping.
    if (!thought && !call) continue
    // The answer to this call, if the next line is one.
    const answer = rows[i + 1]?.role === 'tool' ? rows[i + 1] : null
    const output = (answer?.tool_result as Record<string, any> | null)?.output
    const code = output?.exit_code ?? output?.returncode
    steps.push({
      n: ++n,
      thought: clipTo(thought, 420),
      toolName: call?.function?.name ?? null,
      toolArgs: call?.function?.arguments
        ? clipTo(String(call.function.arguments), 180)
        : null,
      ok: typeof code === 'number' ? code === 0 : null,
      observation: answer?.content
        ? clipTo(String(answer.content).replace(/\s+/g, ' ').trim(), 200)
        : null,
    })
  }
  if (!steps.length) return null
  return {
    id: path.basename(path.dirname(file)),
    agent: String(meta.username ?? ''),
    startedAt: String(meta.start_time ?? ''),
    endedAt: String(meta.end_time ?? ''),
    task: task ? clipTo(String(task).replace(/\s+/g, ' ').trim(), 160) : null,
    total: steps.length,
    // Oldest steps first; the tail is what a card has room for.
    steps: steps.slice(-cap),
  }
}

/**
 * THE CODE AN ATTEMPT ACTUALLY CHANGED, as lines removed and added.
 *
 * Vibe's `edit` tool records `old_string` and `new_string`, and both carry
 * enough unchanged context around the change to be unambiguous in the file —
 * which means rendering them raw shows mostly identical text twice. So the
 * common leading and trailing LINES are stripped and what is left is the
 * change itself.
 *
 * `write_file` has no `old_string`: nothing was removed, so it is all
 * additions.
 */
function lineDiff(
  oldText: string,
  newText: string,
): { removed: string[]; added: string[] } {
  const o = oldText.split('\n')
  const n = newText.split('\n')
  let head = 0
  while (head < o.length && head < n.length && o[head] === n[head]) head++
  let tail = 0
  while (
    tail < o.length - head &&
    tail < n.length - head &&
    o[o.length - 1 - tail] === n[n.length - 1 - tail]
  ) {
    tail++
  }
  const cut = (xs: string[]) =>
    xs
      .slice(head, xs.length - tail)
      .filter((l) => l.trim().length > 0)
      .slice(0, 5)
      .map((l) => clipTo(l.replace(/\t/g, '  '), 110))
  return { removed: cut(o), added: cut(n) }
}

interface CodeEdit {
  step: number
  file: string
  tool: string
  removed: string[]
  added: string[]
}

/** One graded attempt and the code it submitted. See `/api/verification`. */
interface GradedAttempt {
  agent: string
  arm: string
  attempt: number
  passed: number | null
  exitCode: number | null
  signature: string | null
  brokeSyntax: boolean
  v1Left: number | null
  parseOk: number | null
  parseTotal: number | null
  seconds: number | null
  createMs: number | null
  turns: number | null
  edits: CodeEdit[]
}

/** Every edit an agent made in one session, in order. */
function readEdits(file: string, cap: number): CodeEdit[] {
  let rows: Record<string, any>[] = []
  try {
    rows = fs
      .readFileSync(file, 'utf8')
      .split('\n')
      .filter((l) => l.trim())
      .map((l) => {
        try {
          return JSON.parse(l)
        } catch {
          return null
        }
      })
      .filter((r): r is Record<string, any> => r !== null)
  } catch {
    return []
  }
  const out: CodeEdit[] = []
  let step = 0
  for (const r of rows) {
    if (r.role !== 'assistant') continue
    step++
    for (const call of (r.tool_calls ?? []) as Record<string, any>[]) {
      const tool = call?.function?.name
      if (tool !== 'edit' && tool !== 'write_file') continue
      let args: Record<string, any> = {}
      try {
        args = JSON.parse(call.function.arguments || '{}')
      } catch {
        continue
      }
      const target = String(args.file_path ?? args.file ?? '')
      const diff = lineDiff(
        String(args.old_string ?? ''),
        String(args.new_string ?? args.content ?? ''),
      )
      if (!diff.removed.length && !diff.added.length) continue
      out.push({
        step,
        // The pod path is nine-tenths boilerplate: keep it from `repo/`.
        file: target.replace(/^.*?\/repo\//, ''),
        tool,
        ...diff,
      })
    }
  }
  return out.slice(0, cap)
}

/**
 * Which run a packaged session belongs to.
 *
 * BY WALL CLOCK, because nothing in either record names the other: the
 * session's `meta.json` carries an absolute `start_time`, and a run id IS
 * its start in unix seconds, so a session belongs to the run whose window
 * contains it. Checked against all twelve sessions on disk — each falls
 * inside exactly one run, three per agent per run, matching that run's
 * three graded attempts per arm.
 *
 * The slack absorbs the gap between the orchestrator starting and the first
 * session opening, and between the last session closing and the final event.
 */
const JOIN_SLACK_BEFORE = 180
const JOIN_SLACK_AFTER = 300

/**
 * The code graph, read live out of Aura.
 *
 * This is the graph Cognee built during the run — `CodeSymbol` nodes with
 * the relationships it extracted between them (`implements`, `calls`,
 * `has_method`, `instantiates`), scoped by the `repo` property. An earlier
 * version walked the fixture on disk and re-derived an import graph, which
 * was a picture of the same codebase but not of the thing being claimed.
 *
 * Over the HTTP Query API rather than bolt, so the deck needs no driver:
 * Aura serves `/db/<db>/query/v2` with basic auth. Credentials come out of
 * the repo's own .env and never leave this process — the response carries
 * nodes and edges and nothing else.
 *
 * BOUNDED IN JS, NOT IN CYPHER. The graph holds ~1,800 symbols and 685
 * edges for x12sdk; 1,800 nodes is a grey cloud on a slide. So the read is
 * whole and the cut is explicit: rank by degree, keep the top N, keep the
 * edges between the survivors, and report both numbers so the card can say
 * what it is showing out of what exists.
 */
function neo4jEnv(repoRoot: string) {
  const out: Record<string, string> = {}
  try {
    for (const line of fs
      .readFileSync(path.join(repoRoot, '.env'), 'utf8')
      .split('\n')) {
      const m = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim())
      if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, '')
    }
  } catch {
    /* no .env: the endpoint answers 503 and the card says so */
  }
  return out
}

async function cypher(
  repoRoot: string,
  statement: string,
  parameters: Record<string, unknown> = {},
): Promise<{ fields: string[]; values: unknown[][] }> {
  const env = neo4jEnv(repoRoot)
  const uri = env.NEO4J_URI ?? ''
  // `[a-z+]` does not match the 4 in `neo4j+s`, so the scheme survived
  // and DNS was asked to resolve a host called `neo4j+s`.
  const host = uri.replace(/^[a-z0-9+.-]+:\/\//i, '').replace(/:\d+$/, '')
  const db = env.NEO4J_DATABASE || 'neo4j'
  if (!host || !env.NEO4J_PASSWORD) throw new Error('no Neo4j credentials')
  const auth = Buffer.from(
    `${env.NEO4J_USERNAME || 'neo4j'}:${env.NEO4J_PASSWORD}`,
  ).toString('base64')
  const r = await fetch(`https://${host}/db/${db}/query/v2`, {
    method: 'POST',
    headers: {
      authorization: `Basic ${auth}`,
      'content-type': 'application/json',
      accept: 'application/json',
    },
    body: JSON.stringify({ statement, parameters }),
  })
  const j = (await r.json()) as {
    data?: { fields: string[]; values: unknown[][] }
    errors?: { message: string }[]
  }
  if (!r.ok || !j.data)
    throw new Error(j.errors?.[0]?.message ?? `HTTP ${r.status}`)
  return j.data
}

/** `v4010/x12_837.../loops.Loop2420G` -> `loops.Loop2420G`. */
const shortName = (n: string) => n.split('/').pop() || n

async function liveCodeGraph(repoRoot: string, repo: string, keep: number) {
  const data = await cypher(
    repoRoot,
    `MATCH (a:CodeSymbol)-[r]->(b:CodeSymbol)
     WHERE a.repo = $repo AND b.repo = $repo AND a.name <> b.name
     RETURN a.name AS a, type(r) AS t, b.name AS b`,
    { repo },
  )
  const edges = data.values.map((v) => ({
    source: String(v[0]),
    type: String(v[1]),
    target: String(v[2]),
  }))

  const deg = new Map<string, number>()
  const inDeg = new Map<string, number>()
  for (const e of edges) {
    deg.set(e.source, (deg.get(e.source) ?? 0) + 1)
    deg.set(e.target, (deg.get(e.target) ?? 0) + 1)
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1)
  }
  const ranked = [...deg.entries()].sort((x, y) => y[1] - x[1])
  const kept = new Set(ranked.slice(0, keep).map(([id]) => id))
  return {
    source: 'neo4j',
    repo,
    totalNodes: deg.size,
    totalEdges: edges.length,
    nodes: [...kept].map((id) => ({
      id,
      label: shortName(id),
      inDegree: inDeg.get(id) ?? 0,
      degree: deg.get(id) ?? 0,
    })),
    edges: edges.filter((e) => kept.has(e.source) && kept.has(e.target)),
  }
}

export function runsData(options: RunsDataOptions): Plugin {
  const { runsDir, repoRoot, debounceMs = 120 } = options
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python')

  /** Byte offset already streamed, per jsonl absolute path. */
  const offsets = new Map<string, number>()
  const clients = new Set<Client>()
  let watcher: fs.FSWatcher | null = null
  let timer: NodeJS.Timeout | null = null
  let poll: NodeJS.Timeout | null = null
  /** Last index sent, so an unchanged one is not re-sent every poll. */
  let indexStamp = ''

  function listRuns(): RunIndexEntry[] {
    let names: string[]
    try {
      names = fs.readdirSync(runsDir)
    } catch {
      return []
    }
    const metricsPresent = new Set(names.filter((n) => n.endsWith('-metrics.json')))
    const out: RunIndexEntry[] = []
    for (const name of names) {
      if (!isJsonl(name)) continue
      const id = name.slice(0, -'.jsonl'.length)
      let st: fs.Stats
      try {
        st = fs.statSync(path.join(runsDir, name))
      } catch {
        continue
      }
      if (!st.isFile()) continue
      out.push({
        id,
        kind: runKind(id),
        mtimeMs: st.mtimeMs,
        bytes: st.size,
        hasMetrics: metricsPresent.has(metricsNameFor(id)),
      })
    }
    out.sort((a, b) => b.mtimeMs - a.mtimeMs)
    return out
  }

  /**
   * Newest run, optionally narrowed to one writer prefix.
   *
   * EMPTY FILES ARE SKIPPED. A run that dies before its first event still
   * leaves a zero-byte `.jsonl` behind, and two of those sat at the top of
   * `runs/` for six hours — so the deck followed them, reported "0 events",
   * and every card sat empty while a perfectly good run of the same kind was
   * one row down. A file with no bytes cannot be the run anyone means.
   *
   * This does not delay latching onto a real new run by anything that matters:
   * the orchestrator writes its first event within a second or two of creating
   * the file, and the collector re-picks on every poll.
   */
  function newestRunId(kind: string | null): string | null {
    const runs = listRuns()
    const of = (r: RunIndexEntry) => !kind || r.kind === kind
    const pick = runs.find((r) => of(r) && r.bytes > 0) ?? runs.find(of)
    return pick ? pick.id : null
  }

  /** Newest `.log` by mtime, with its size and whether it named a run. */
  function newestLog(): { file: string; mtimeMs: number; bytes: number } | null {
    let names: string[]
    try {
      names = fs.readdirSync(runsDir)
    } catch {
      return null
    }
    let best: { file: string; mtimeMs: number; bytes: number } | null = null
    for (const name of names) {
      if (!isLog(name)) continue
      try {
        const st = fs.statSync(path.join(runsDir, name))
        if (!st.isFile()) continue
        if (!best || st.mtimeMs > best.mtimeMs) {
          best = { file: name, mtimeMs: st.mtimeMs, bytes: st.size }
        }
      } catch {
        /* vanished between readdir and stat */
      }
    }
    return best
  }

  function readLog(file: string): {
    file: string
    text: string
    bytes: number
    mtimeMs: number
    runId: string | null
  } | null {
    const abs = path.join(runsDir, file)
    try {
      const st = fs.statSync(abs)
      const text = fs.readFileSync(abs, 'utf8')
      const m = EVENT_LOG_LINE.exec(text)
      return {
        file,
        text,
        bytes: st.size,
        mtimeMs: st.mtimeMs,
        runId: m ? m[1] : null,
      }
    } catch {
      return null
    }
  }

  /**
   * The harness's own chart document for a run.
   *
   * Prefers `runs/<id>-series.json` when the run wrote one, and otherwise asks
   * `orchestrator.series` to derive it from the event log — which is the only
   * way rehearsals chart at all, since `rehearse_loop.py` builds the document
   * in memory and never writes it.
   *
   * Cached on the event log's (size, mtime): a live run recomputes once per
   * append, not once per request, and a finished run computes once ever.
   */
  const seriesCache = new Map<string, { key: string; doc: unknown }>()

  function readSeries(id: string): unknown | null {
    const jsonl = path.join(runsDir, `${id}.jsonl`)
    let key: string
    try {
      const st = fs.statSync(jsonl)
      key = `${st.size}:${st.mtimeMs}`
    } catch {
      return null
    }
    const hit = seriesCache.get(id)
    if (hit && hit.key === key) return hit.doc

    const onDisk = path.join(runsDir, `${id}-series.json`)
    let doc: unknown | null = null
    try {
      doc = JSON.parse(fs.readFileSync(onDisk, 'utf8'))
    } catch {
      doc = deriveSeries(id, jsonl)
    }
    if (doc) seriesCache.set(id, { key, doc })
    return doc
  }

  function deriveSeries(id: string, jsonl: string): unknown | null {
    if (!fs.existsSync(venvPython)) return null
    const script = [
      'import json,sys',
      'sys.path.insert(0, sys.argv[1])',
      'from orchestrator import series',
      'ev=[json.loads(l) for l in open(sys.argv[3]) if l.strip()]',
      'json.dump(series.within_run(ev, run_id=sys.argv[2], fixture="rehearsal"), sys.stdout)',
    ].join('\n')
    try {
      const out = execFileSync(venvPython, ['-c', script, repoRoot, id, jsonl], {
        encoding: 'utf8',
        timeout: 20000,
        maxBuffer: 32 * 1024 * 1024,
      })
      return JSON.parse(out)
    } catch (err) {
      // Loud once, not per request: a missing venv or a series.py that moved
      // should be visible while building, not a silently empty chart on stage.
      console.warn(`[runs-data] could not derive series for ${id}:`, err)
      return null
    }
  }

  /** Parse whole-file events. Tolerates a torn final line on a live file. */
  function readEvents(id: string): unknown[] {
    const file = path.join(runsDir, `${id}.jsonl`)
    let raw: string
    try {
      raw = fs.readFileSync(file, 'utf8')
    } catch {
      return []
    }
    offsets.set(file, Buffer.byteLength(raw, 'utf8'))
    return parseLines(raw).events
  }

  function readMetrics(id: string): unknown | null {
    const file = path.join(runsDir, metricsNameFor(id))
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'))
    } catch {
      return null
    }
  }

  /**
   * Split a chunk into events, returning any trailing partial line so the
   * next read can complete it. A run being appended to mid-write will
   * otherwise drop or corrupt one event per poll.
   */
  function parseLines(chunk: string): { events: unknown[]; rest: string } {
    const events: unknown[] = []
    const lines = chunk.split('\n')
    const rest = lines.pop() ?? ''
    for (const line of lines) {
      const s = line.trim()
      if (!s) continue
      try {
        events.push(JSON.parse(s))
      } catch {
        /* a line still being written; it arrives complete on the next tick */
      }
    }
    return { events, rest }
  }

  /** Read only what was appended since the last call. */
  function readDelta(id: string): unknown[] {
    const file = path.join(runsDir, `${id}.jsonl`)
    let st: fs.Stats
    try {
      st = fs.statSync(file)
    } catch {
      return []
    }
    const from = offsets.get(file) ?? 0
    if (st.size <= from) {
      // Truncated or rewritten — start over rather than serve garbage.
      if (st.size < from) offsets.set(file, 0)
      return []
    }
    const fd = fs.openSync(file, 'r')
    try {
      const len = st.size - from
      const buf = Buffer.alloc(len)
      fs.readSync(fd, buf, 0, len, from)
      const { events, rest } = parseLines(buf.toString('utf8'))
      offsets.set(file, st.size - Buffer.byteLength(rest, 'utf8'))
      return events
    } finally {
      fs.closeSync(fd)
    }
  }

  function send(client: Client, type: string, payload: unknown) {
    try {
      client.res.write(`event: ${type}\ndata: ${JSON.stringify(payload)}\n\n`)
    } catch {
      clients.delete(client)
    }
  }

  function sendSnapshot(client: Client, runId: string) {
    client.following = runId
    send(client, 'snapshot', {
      runId,
      events: readEvents(runId),
      metrics: readMetrics(runId),
      series: readSeries(runId),
    })
  }

  /**
   * Bring one client's terminal up to date.
   *
   * Tails by byte offset like the event log, and re-sends the whole file when
   * the newest log CHANGES — a series driver starts a new log per run, and
   * appending run 5's first line to run 4's transcript would be a lie.
   */
  function pumpLog(client: Client) {
    const newest = newestLog()
    if (!newest) return
    if (client.logFile !== newest.file) {
      const whole = readLog(newest.file)
      if (!whole) return
      client.logFile = newest.file
      client.logAt = whole.bytes
      send(client, 'log', { ...whole, reset: true })
      return
    }
    if (newest.bytes <= client.logAt) {
      if (newest.bytes < client.logAt) client.logAt = 0
      return
    }
    const abs = path.join(runsDir, newest.file)
    let fd: number
    try {
      fd = fs.openSync(abs, 'r')
    } catch {
      return
    }
    try {
      const len = newest.bytes - client.logAt
      const buf = Buffer.alloc(len)
      fs.readSync(fd, buf, 0, len, client.logAt)
      client.logAt = newest.bytes
      send(client, 'log', {
        file: newest.file,
        text: buf.toString('utf8'),
        bytes: newest.bytes,
        mtimeMs: newest.mtimeMs,
        reset: false,
      })
    } finally {
      fs.closeSync(fd)
    }
  }

  function onChange() {
    const runs = listRuns()
    for (const client of clients) {
      const target = client.pinned ?? newestRunId(client.kind)
      pumpLog(client)
      if (!target) continue
      if (client.following !== target) {
        // A fresher run appeared (or the first one did). Re-latch.
        send(client, 'active', { runId: target })
        sendSnapshot(client, target)
        continue
      }
      const delta = readDelta(target)
      if (delta.length) {
        send(client, 'events', { runId: target, events: delta })
        // The chart document is a pure function of the log, so it only needs
        // resending when the log actually grew.
        const series = readSeries(target)
        if (series) send(client, 'series', { runId: target, series })
      }
      const metrics = readMetrics(target)
      if (metrics) send(client, 'metrics', { runId: target, metrics })
    }
    // The index is ~650 rows and changes rarely; at one poll a second, sending
    // it unconditionally would be most of the bytes on this stream.
    const stamp = runs.map((r) => `${r.id}:${r.mtimeMs}:${r.bytes}`).join(',')
    if (stamp !== indexStamp) {
      indexStamp = stamp
      for (const client of clients) send(client, 'runs', { runs })
    }
  }

  /**
   * Watch AND poll.
   *
   * The watcher alone does not see a live run. `fs.watch` on a directory is
   * FSEvents here, and appending to a file already in that directory did not
   * wake it: measured against a writer appending every 4s, the deck sat on
   * "1 event" for 24 seconds and then received all six at once when the writer
   * closed the file. A talk cannot be driven by that — and worse, it looks
   * exactly like a run that is not producing.
   *
   * So a plain poll is the primary mechanism and the watcher is the fast path
   * that makes it feel instant. A full pass stats every file in `runs/` — 648
   * of them, measured at 2.4ms — so once a second is nothing, and the poll only
   * runs while something is actually listening.
   */
  function startWatching() {
    if (!poll) poll = setInterval(onChange, POLL_MS)
    if (watcher) return
    try {
      watcher = fs.watch(runsDir, { persistent: false }, () => {
        if (timer) clearTimeout(timer)
        timer = setTimeout(onChange, debounceMs)
      })
    } catch (err) {
      console.warn(`[runs-data] cannot watch ${runsDir}:`, err)
    }
  }

  /** Nothing listening: stop polling. The watcher is cheap and stays. */
  function stopIfIdle() {
    if (clients.size === 0 && poll) {
      clearInterval(poll)
      poll = null
    }
  }

  /**
   * Distilled skill versions.
   *
   * Several `skills/versions*` directories exist — one per fixture, plus some
   * quarantined ones (`-contaminated`, `-prerestore`). The live one is simply
   * the most recently written; picking by name would need a fixture lookup the
   * deck has no business doing, and would go stale the next time one is added.
   */
  function skillsDir(): string | null {
    const root = path.join(repoRoot, 'skills')
    try {
      const dirs = fs
        .readdirSync(root)
        .filter((d) => d.startsWith('versions'))
        .map((d) => ({ d, m: fs.statSync(path.join(root, d)).mtimeMs }))
        .sort((a, b) => b.m - a.m)
      return dirs.length ? path.join(root, dirs[0].d) : null
    } catch {
      return null
    }
  }

  function listSkills() {
    const dir = skillsDir()
    if (!dir) return { dir: null, versions: [] }
    try {
      const versions = fs
        .readdirSync(dir)
        .filter((f) => /^v\d+-.*\.md$/.test(f))
        .map((f) => {
          const st = fs.statSync(path.join(dir, f))
          return {
            file: f,
            version: Number(/^v(\d+)/.exec(f)?.[1] ?? 0),
            bytes: st.size,
            mtimeMs: st.mtimeMs,
          }
        })
        .sort((a, b) => a.version - b.version)
      return { dir: path.relative(repoRoot, dir), versions }
    } catch {
      return { dir: null, versions: [] }
    }
  }

  function json(res: ServerResponse, body: unknown, status = 200) {
    const payload = JSON.stringify(body)
    res.writeHead(status, {
      'content-type': 'application/json',
      'cache-control': 'no-store',
    })
    res.end(payload)
  }

  function middleware() {
    if (!fs.existsSync(runsDir)) {
      console.warn(`[runs-data] runs dir not found: ${runsDir}`)
    } else {
      console.log(`[runs-data] serving ${runsDir}`)
    }
    // Async: the code-graph route awaits a Cypher read over HTTPS.
    return async (req: IncomingMessage, res: ServerResponse, next: () => void) => {
      const url = new URL(req.url ?? '/', 'http://localhost')
      const p = url.pathname

      if (p === '/api/runs') return json(res, { runs: listRuns() })

      if (p === '/api/stream') {
        res.writeHead(200, {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache, no-transform',
          connection: 'keep-alive',
          // Vite sits behind no proxy in dev, but this is free insurance.
          'x-accel-buffering': 'no',
        })
        res.write('retry: 2000\n\n')
        const pinned = url.searchParams.get('run')
        const kind = url.searchParams.get('kind')
        const client: Client = {
          res,
          pinned,
          kind,
          following: null,
          logFile: null,
          logAt: 0,
        }
        clients.add(client)
        startWatching()

        send(client, 'runs', { runs: listRuns() })
        const target = pinned ?? newestRunId(kind)
        if (target) {
          send(client, 'active', { runId: target })
          sendSnapshot(client, target)
        }
        pumpLog(client)

        // Comment frames keep the connection warm through idle stretches
        // between attempts, which can run minutes on a saturated card.
        const ping = setInterval(() => {
          try {
            res.write(': ping\n\n')
          } catch {
            clearInterval(ping)
          }
        }, 15000)
        req.on('close', () => {
          clearInterval(ping)
          clients.delete(client)
          stopIfIdle()
        })
        return
      }

      const one = /^\/api\/runs\/([^/]+)$/.exec(p)
      if (one) {
        const id = decodeURIComponent(one[1])
        if (!/^[\w.-]+$/.test(id)) return json(res, { error: 'bad id' }, 400)
        return json(res, {
          runId: id,
          events: readEvents(id),
          metrics: readMetrics(id),
          series: readSeries(id),
        })
      }

      if (p === '/api/log') {
        const asked = url.searchParams.get('file')
        // A filename, never a path: `?file=../../.env` is the obvious attack
        // on an endpoint that reads a file the caller names.
        if (asked && !/^[\w.-]+\.log$/.test(asked)) {
          return json(res, { error: 'bad file' }, 400)
        }
        const file = asked ?? newestLog()?.file
        if (!file) return json(res, { error: 'no log on disk' }, 404)
        const log = readLog(file)
        return log ? json(res, log) : json(res, { error: 'unreadable' }, 404)
      }

      const series = /^\/api\/series\/([^/]+)$/.exec(p)
      if (series) {
        const id = decodeURIComponent(series[1])
        if (!/^[\w.-]+$/.test(id)) return json(res, { error: 'bad id' }, 400)
        const doc = readSeries(id)
        return doc ? json(res, doc) : json(res, { error: 'no series' }, 404)
      }

      if (p === '/api/skills') return json(res, listSkills())

      const skill = /^\/api\/skills\/(\d+)$/.exec(p)
      if (skill) {
        const want = Number(skill[1])
        const { dir, versions } = listSkills()
        const hit = versions.find((v) => v.version === want)
        if (!dir || !hit) return json(res, { error: 'no such version' }, 404)
        try {
          const text = fs.readFileSync(path.join(repoRoot, dir, hit.file), 'utf8')
          return json(res, { ...hit, dir, text })
        } catch {
          return json(res, { error: 'unreadable' }, 404)
        }
      }

      if (p === '/api/tokens') {
        // WARM AGAINST COLD, per run, oldest first. Read straight off the
        // `*-metrics.json` the harness already wrote — one file per run,
        // one `ArmMetrics` per arm — so this endpoint only indexes. The
        // arms are kept apart all the way to the card.
        //
        // NOT cross-run.md, which carries the same figures in a table. That
        // file is append-only and has GAINED COLUMNS over the project's
        // life: early rows put `arm` at index 4, later ones at index 7, so
        // one parser reads 81 of its 142 rows as malformed. The JSON is
        // keyed, and cannot drift that way.
        //
        // A run id is `<kind>-<unix seconds>`, so the numeric suffix is the
        // chronological order. mtime would be wrong: a metrics file is
        // rewritten when a run is re-graded.
        const stamp = (id: string) => Number(/-(\d+)$/.exec(id)?.[1] ?? 0)
        let files: string[] = []
        try {
          files = fs.readdirSync(runsDir).filter((n) => n.endsWith('-metrics.json'))
        } catch {
          return json(res, { runs: [], warm: null, cold: null }, 404)
        }
        const arm = (raw: Record<string, number> | undefined): ArmTokens =>
          !raw
            ? { ...NO_ARM }
            : {
                in: Number(raw.attempt_prompt_tokens) || 0,
                out: Number(raw.attempt_completion_tokens) || 0,
                // Kept apart from the attempt figures, because they answer
                // different questions — see the header of CostSlide.tsx.
                distilIn: Number(raw.distil_prompt_tokens) || 0,
                distilOut: Number(raw.distil_completion_tokens) || 0,
                attempts: Number(raw.attempts) || 0,
                turns: Number(raw.turns) || 0,
                seconds: Number(raw.attempt_seconds) || 0,
                passed: Number(raw.tests_passed) || 0,
              }
        const runs: RunTokens[] = []
        for (const name of files.sort(
          (a, b) =>
            stamp(a.replace(/-metrics\.json$/, '')) -
            stamp(b.replace(/-metrics\.json$/, '')),
        )) {
          let doc: Record<string, unknown>
          try {
            doc = JSON.parse(fs.readFileSync(path.join(runsDir, name), 'utf8'))
          } catch {
            continue
          }
          const arms = (doc.arms ?? {}) as Record<string, Record<string, number>>
          runs.push({
            id: String(doc.run_id ?? name.replace(/-metrics\.json$/, '')),
            warm: arm(arms.warm),
            cold: arm(arms.cold),
            runSeconds: Number(doc.run_seconds) || 0,
            activeSeconds: activeSeconds(
              arms.warm?.per_attempt as unknown as Record<string, number>[],
              arms.cold?.per_attempt as unknown as Record<string, number>[],
            ),
            counts: doc.counts_toward_clearly_working !== false,
          })
        }
        const totalFor = (side: 'warm' | 'cold'): ArmTokens => {
          const out = { ...NO_ARM }
          for (const r of runs) {
            for (const k of Object.keys(out) as (keyof ArmTokens)[]) {
              out[k] += r[side][k]
            }
          }
          return out
        }
        return json(res, {
          runs: runs.length,
          perRun: runs,
          warm: totalFor('warm'),
          cold: totalFor('cold'),
        })
      }

      if (p === '/api/reasoning') {
        // THE NEWEST PACKAGED AGENT, and all of its attempts in order.
        //
        // One agent, not both: warm's and cold's sessions interleaved read
        // as one confused agent changing its mind about whether it has a
        // skill. The arm is named on the card.
        const cap = Math.min(
          200,
          Math.max(10, Number(url.searchParams.get('cap') ?? 60)),
        )
        const found = findSessions(runsDir)
          .map((f) => readSession(f, cap))
          .filter((s): s is NonNullable<typeof s> => s !== null)
          .sort((a, b) => a.startedAt.localeCompare(b.startedAt))
        if (!found.length) {
          return json(res, { agent: null, sessions: [] }, 404)
        }
        const newest = found[found.length - 1]
        const mine = found.filter((s) => s.agent === newest.agent)
        return json(res, {
          agent: newest.agent,
          // Up to four attempts: the card's ageing ramp keeps six groups and
          // four is what fits on the glass at a readable size.
          sessions: mine.slice(-4),
          available: found.length,
        })
      }

      if (p === '/api/attempts') {
        // EVERY GRADED ATTEMPT OF ONE RUN, from the run's own package.
        //
        // `runs/packages/<id>/attempts.json` is one row per ATTEMPT_DONE with
        // the memory write, the rewrite, any rejection and the ingest folded
        // in — its MANIFEST says "derived from the jsonl; nothing new". So it
        // is the same record, pre-joined, and it exists for a finished run
        // whether or not anyone packaged the agents' transcripts.
        //
        // THAT DISTINCTION IS WHY THIS ENDPOINT EXISTS. `/api/verification`
        // keys on packaged Vibe sessions, and swarm-1789998106's package has
        // none — so the graded-attempts card rendered its empty state on the
        // one run the deck is pinned to. This falls back to the event log, so
        // a graded attempt is never invisible.
        const id = (url.searchParams.get('run') ?? '').replace(/[^\w.-]/g, '')
        if (!id) return json(res, { error: 'no run' }, 400)
        const pkg = path.join(runsDir, 'packages', id)

        let attempts: Record<string, unknown>[] = []
        let source = 'event log'
        try {
          const raw = JSON.parse(
            fs.readFileSync(path.join(pkg, 'attempts.json'), 'utf8'),
          )
          if (Array.isArray(raw) && raw.length) {
            attempts = raw
            source = 'packages/attempts.json'
          }
        } catch {
          /* no package for this run: derive below */
        }
        if (!attempts.length) {
          attempts = (readEvents(id) as Record<string, unknown>[]).filter(
            (e) => e.type === 'ATTEMPT_DONE',
          )
        }

        // Sandbox creation is on SANDBOX_CREATED, not on the attempt row.
        const created = new Map<string, number[]>()
        for (const e of readEvents(id) as Record<string, any>[]) {
          if (e.type !== 'SANDBOX_CREATED') continue
          const who = String(e.agent ?? e.swarm ?? '?')
          created.set(who, [...(created.get(who) ?? []), Number(e.create_ms) || 0])
        }

        // The two windows, from the package's MANIFEST where it states them:
        // attempts 1-9 are the equal-attempt comparison, 10-11 are warm
        // alone. DEMO-NOTES.md is explicit that they must not be charted as
        // one, so the split travels with the data rather than living in a
        // constant in a component.
        let windows: unknown = null
        try {
          windows =
            JSON.parse(fs.readFileSync(path.join(pkg, 'MANIFEST.json'), 'utf8'))
              .windows ?? null
        } catch {
          /* no manifest: the card shows one window */
        }

        const seen = new Map<string, number>()
        const rows = attempts.map((a) => {
          const agent = String(a.agent ?? a.swarm ?? '?')
          const nth = seen.get(agent) ?? 0
          seen.set(agent, nth + 1)
          const tools = (a.tools ?? {}) as Record<string, number>
          return {
            agent,
            arm: String(a.swarm ?? ''),
            attempt: Number(a.attempt) || nth + 1,
            t: Number(a.t) || 0,
            passed: a.tests_passed ?? null,
            exitCode: a.exit_code ?? null,
            signature: (a.error_signature as string | null) ?? null,
            brokeSyntax: a.broke_syntax === true,
            v1Left: a.v1_remaining ?? null,
            parseOk: a.parse_ok ?? null,
            parseTotal: a.parse_total ?? null,
            seconds: a.attempt_seconds ?? null,
            turns: a.turns_used ?? null,
            stop: (a.vibe_stop as string | null) ?? null,
            createMs: created.get(agent)?.[nth] ?? null,
            tools,
            edits: (tools.edit ?? 0) + (tools.write_file ?? 0),
            memoryChars: Number(a.memory_chars) || 0,
            hookChars: Number(a.hook_chars) || 0,
            procedureChars: Number(a.procedure_chars) || 0,
          }
        })
        return json(res, { runId: id, source, windows, attempts: rows })
      }

      if (p === '/api/verification') {
        // ONE RUN, ITS GRADED ATTEMPTS, AND THE CODE EACH ONE SUBMITTED.
        //
        // The verdicts come from the run's own event log — `exit_code` and
        // `tests_passed` are pytest's, `create_ms` is the sandbox's. The
        // code comes from the agent's packaged Vibe session for the same
        // attempt. Two records, joined on wall clock; see JOIN_SLACK_BEFORE.
        //
        // The run is the NEWEST one that has packaged transcripts at all,
        // because a verdict with no code beside it is the card this
        // replaced.
        const sessions = findSessions(runsDir)
          .map((f) => {
            let meta: Record<string, any> = {}
            try {
              meta = JSON.parse(
                fs.readFileSync(path.join(path.dirname(f), 'meta.json'), 'utf8'),
              )
            } catch {
              return null
            }
            const started = Date.parse(String(meta.start_time ?? ''))
            if (!Number.isFinite(started)) return null
            return { file: f, agent: String(meta.username ?? ''), started }
          })
          .filter((s): s is NonNullable<typeof s> => s !== null)
          .sort((a, b) => a.started - b.started)

        // Runs, newest first, so the first one with sessions wins.
        const ids = listRuns()
          .filter((r) => r.hasMetrics)
          .map((r) => r.id)
        let chosen: { id: string; mine: typeof sessions } | null = null
        for (const id of ids) {
          const start = Number(/-(\d+)$/.exec(id)?.[1] ?? 0) * 1000
          if (!start) continue
          const metrics = readMetrics(id) as Record<string, any> | null
          const span = (Number(metrics?.run_seconds) || 0) * 1000
          const mine = sessions.filter(
            (s) =>
              s.started >= start - JOIN_SLACK_BEFORE * 1000 &&
              s.started <= start + span + JOIN_SLACK_AFTER * 1000,
          )
          if (mine.length) {
            chosen = { id, mine }
            break
          }
        }
        if (!chosen) return json(res, { runId: null, attempts: [] }, 404)

        // The k-th session an agent opened is its k-th attempt: the loop
        // starts a fresh session per attempt and never resumes one (that is
        // asserted in the harness, and `resumed` is false on every event).
        const byAgent = new Map<string, string[]>()
        for (const s of chosen.mine) {
          const list = byAgent.get(s.agent) ?? []
          list.push(s.file)
          byAgent.set(s.agent, list)
        }

        const events = readEvents(chosen.id) as Record<string, any>[]
        const sandbox = new Map<string, number[]>()
        // Annotated, because `nth` counts what is already in this array and
        // an inferred type would be defined in terms of itself (TS7022).
        const attempts: GradedAttempt[] = []
        for (const e of events) {
          const agent = String(e.agent ?? e.swarm ?? '?')
          if (e.type === 'SANDBOX_CREATED') {
            const list = sandbox.get(agent) ?? []
            list.push(Number(e.create_ms) || 0)
            sandbox.set(agent, list)
            continue
          }
          if (e.type !== 'ATTEMPT_DONE') continue
          const nth = attempts.filter((a) => a.agent === agent).length
          const file = byAgent.get(`agent-${agent}`)?.[nth]
          attempts.push({
            agent,
            arm: String(e.swarm ?? ''),
            attempt: Number(e.attempt) || nth + 1,
            passed: e.tests_passed ?? null,
            exitCode: e.exit_code ?? null,
            signature: (e.error_signature as string | null) ?? null,
            brokeSyntax: e.broke_syntax === true,
            v1Left: e.v1_remaining ?? null,
            parseOk: e.parse_ok ?? null,
            parseTotal: e.parse_total ?? null,
            seconds: e.attempt_seconds ?? null,
            createMs: sandbox.get(agent)?.[nth] ?? null,
            turns: e.turns_used ?? null,
            edits: file ? readEdits(file, 24) : [],
          })
        }
        return json(res, {
          runId: chosen.id,
          attempts,
          sessions: chosen.mine.length,
        })
      }

      if (p === '/api/doc/cross-run') {
        try {
          return json(res, {
            text: fs.readFileSync(path.join(runsDir, 'cross-run.md'), 'utf8'),
          })
        } catch {
          return json(res, { error: 'no cross-run.md' }, 404)
        }
      }

      if (p === '/api/source') {
        const want = url.searchParams.get('file') ?? ''
        // Exact membership. See SOURCE_WHITELIST.
        if (!SOURCE_WHITELIST.has(want)) {
          return json(res, { error: 'not whitelisted' }, 403)
        }
        try {
          return json(res, {
            file: want,
            text: fs.readFileSync(path.join(repoRoot, want), 'utf8'),
          })
        } catch {
          return json(res, { error: 'unreadable' }, 404)
        }
      }

      if (p === '/api/series-across') {
        // Written by scripts/plot_series.py into runs/plots/. Same document
        // shape as a within-run series, scope `across_runs`.
        const asked = url.searchParams.get('file') ?? 'aip-series.json'
        if (!/^[\w.-]+\.json$/.test(asked)) {
          return json(res, { error: 'bad file' }, 400)
        }
        try {
          const raw = fs.readFileSync(path.join(runsDir, 'plots', asked), 'utf8')
          return json(res, JSON.parse(raw))
        } catch {
          return json(res, { error: 'no such series' }, 404)
        }
      }

      if (p === '/api/code-graph') {
        // `repo` is the fixture's own name, which is what Cognee stamps on
        // every code node. A run's `series.fixture` can read `rehearsal` on
        // the live path, which is not a repo in the graph, so an unknown
        // name falls back to the repo that has the most nodes and the reply
        // says which one it used.
        const asked = (url.searchParams.get('repo') ?? '').replace(/[^\w.-]/g, '')
        const keep = Math.min(
          260,
          Math.max(20, Number(url.searchParams.get('keep') ?? 110)),
        )
        try {
          let repo = asked
          const repos = await cypher(
            repoRoot,
            `MATCH (s:CodeSymbol) WHERE s.repo IS NOT NULL
             RETURN s.repo AS repo, count(*) AS n ORDER BY n DESC`,
          )
          const names = repos.values.map((v) => String(v[0]))
          if (!names.includes(repo)) repo = names[0] ?? ''
          if (!repo) return json(res, { error: 'no code graph in the graph' }, 404)
          return json(res, {
            asked,
            ...(await liveCodeGraph(repoRoot, repo, keep)),
          })
        } catch (e) {
          return json(res, { error: String((e as Error).message) }, 503)
        }
      }

      next()
    }
  }

  return {
    name: 'msf:runs-data',
    // Both servers, deliberately. `npm run dev` is the normal path, but a
    // preview of the built bundle must collect too — discovering on stage
    // that `dist` serves a deck with no data is not a discovery worth having.
    configureServer(server) {
      server.middlewares.use(middleware())
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware())
    },
    closeBundle() {
      watcher?.close()
      watcher = null
    },
  }
}
