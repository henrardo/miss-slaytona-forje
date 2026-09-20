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
])
const EVENT_LOG_LINE = /^event log:\s*runs\/([\w.-]+)\.jsonl/m

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
    return (req: IncomingMessage, res: ServerResponse, next: () => void) => {
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
