/**
 * The memory graph, read-only, server-side.
 *
 * Three things the deck needs that `runs/` cannot answer. The event log carries
 * COUNTS of what was written to the graph — `STEP_WRITES` is
 * `{thoughts_from_reasoning, thought_fallbacks, reasoning_pushes}` and nothing
 * more — so the model's actual reasoning, the tool calls and the ontology exist
 * only in Aura.
 *
 *   GET /api/graph/health              reachable? counts by label
 *   GET /api/graph/delta?since=&run=   nodes and edges newer than a cursor
 *   GET /api/graph/steps?since=&run=   reasoning steps with their text
 *   GET /api/graph/schema              CALL db.schema.visualization()
 *
 * ── Credentials stay here ────────────────────────────────────────────────
 *
 * `.env` is read in the Node process and never leaves it. The browser gets
 * rows, never a connection. This plugin runs in dev AND preview for the same
 * reason the collector does: discovering on stage that the built bundle has no
 * graph is not a discovery worth having.
 *
 * ── It has to survive Aura being asleep ──────────────────────────────────
 *
 * A free Aura instance pauses, and conference wifi is conference wifi. Every
 * successful read is written to a small on-disk cache; when the driver fails,
 * the cache is served with `stale: true` and the age of it, so the card can say
 * so rather than showing an empty canvas that looks like "nothing happened".
 *
 * ── The cursor ───────────────────────────────────────────────────────────
 *
 * `timestamp` is a Neo4j DateTime, so the wire uses `.epochMillis` and the
 * client sends back the largest one it has seen. Polling, not streaming: the
 * driver has no change feed here, and a 1s poll of "newer than X" is both
 * simpler and bounded.
 */
import fs from 'node:fs'
import path from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import neo4j, { type Driver } from 'neo4j-driver'

export interface GraphDataOptions {
  /** Repo root — `.env` lives there. */
  repoRoot: string
  /** Where to keep the last-good responses. */
  cacheDir?: string
}

/** Minimal .env reader. No dependency, no interpolation, no surprises. */
function readEnv(file: string): Record<string, string> {
  const out: Record<string, string> = {}
  let raw: string
  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return out
  }
  for (const line of raw.split('\n')) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/i.exec(line)
    if (!m) continue
    let v = m[2].trim()
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1)
    }
    out[m[1]] = v
  }
  return out
}

/**
 * Steps, their tool call, and the trace they belong to.
 *
 * `HAS_STEP` comes from the trace, `USES_TOOL` goes to the call. `embedding`
 * and `task_embedding` are excluded by naming the fields rather than returning
 * the node — a step embedding is 1,536 floats and there are thousands of them.
 */
const STEPS_CYPHER = `
MATCH (t:ReasoningTrace)-[:HAS_STEP]->(s:ReasoningStep)
WHERE s.timestamp IS NOT NULL
  AND s.timestamp.epochMillis > $since
  AND ($run IS NULL OR t.session_id STARTS WITH $run)
OPTIONAL MATCH (s)-[:USES_TOOL]->(c:ToolCall)
OPTIONAL MATCH (s)-[:MENTIONS]->(e:Entity)
RETURN s.id            AS id,
       s.step_number   AS stepNumber,
       s.thought       AS thought,
       s.action        AS action,
       s.observation   AS observation,
       s.timestamp.epochMillis AS at,
       t.id            AS traceId,
       t.session_id    AS sessionId,
       t.task          AS task,
       t.outcome       AS outcome,
       t.success       AS success,
       c.tool_name     AS toolName,
       c.arguments     AS toolArgs,
       c.status        AS toolStatus,
       collect(DISTINCT e.name) AS entities
ORDER BY at ASC
LIMIT $limit
`

/**
 * Nodes and edges for the viewer.
 *
 * Deliberately the same four labels the harness writes, not `MATCH (n)` — this
 * database also holds a workshop's worth of unrelated Message/Conversation
 * nodes, and a viewer that pulled those in would be showing something the talk
 * is not about.
 */
const DELTA_CYPHER = `
MATCH (t:ReasoningTrace)-[:HAS_STEP]->(s:ReasoningStep)
WHERE s.timestamp IS NOT NULL
  AND s.timestamp.epochMillis > $since
  AND ($run IS NULL OR t.session_id STARTS WITH $run)
OPTIONAL MATCH (s)-[:USES_TOOL]->(c:ToolCall)
WITH t, s, c ORDER BY s.timestamp.epochMillis ASC LIMIT $limit
RETURN collect(DISTINCT {
         id: t.id, label: 'ReasoningTrace', at: t.started_at.epochMillis,
         caption: coalesce(t.user_identifier, 'trace'),
         detail: coalesce(t.outcome, ''), ok: t.success
       }) AS traces,
       collect(DISTINCT {
         id: s.id, label: 'ReasoningStep', at: s.timestamp.epochMillis,
         caption: toString(coalesce(s.step_number, '')),
         detail: left(coalesce(s.thought, ''), 160), parent: t.id
       }) AS steps,
       collect(DISTINCT CASE WHEN c IS NULL THEN NULL ELSE {
         id: c.id, label: 'ToolCall', at: c.timestamp.epochMillis,
         caption: c.tool_name, detail: left(coalesce(c.arguments, ''), 120),
         parent: s.id, ok: c.status = 'success'
       } END) AS calls
`

const HEALTH_CYPHER = `
MATCH (n) UNWIND labels(n) AS l
RETURN l AS label, count(*) AS n ORDER BY n DESC LIMIT 20
`

export function graphData(options: GraphDataOptions): Plugin {
  const { repoRoot } = options
  const cacheDir = options.cacheDir ?? path.join(repoRoot, 'deck', '.graph-cache')
  const env = readEnv(path.join(repoRoot, '.env'))
  const uri = env.NEO4J_URI
  const user = env.NEO4J_USERNAME ?? 'neo4j'
  const password = env.NEO4J_PASSWORD
  const database = env.NEO4J_DATABASE || 'neo4j'

  let driver: Driver | null = null
  function getDriver(): Driver | null {
    if (!uri || !password) return null
    if (!driver) {
      driver = neo4j.driver(uri, neo4j.auth.basic(user, password), {
        // The deck must never hang on stage waiting for a paused instance.
        connectionAcquisitionTimeout: 8000,
        maxConnectionPoolSize: 4,
      })
    }
    return driver
  }

  function cacheFile(key: string) {
    return path.join(cacheDir, `${key}.json`)
  }

  function putCache(key: string, value: unknown) {
    try {
      fs.mkdirSync(cacheDir, { recursive: true })
      fs.writeFileSync(
        cacheFile(key),
        JSON.stringify({ at: Date.now(), value }),
        'utf8',
      )
    } catch {
      /* a cache that cannot be written is not worth failing a request over */
    }
  }

  function getCache(key: string): { at: number; value: unknown } | null {
    try {
      return JSON.parse(fs.readFileSync(cacheFile(key), 'utf8'))
    } catch {
      return null
    }
  }

  /** Neo4j Integers arrive as {low, high}; nothing downstream wants that. */
  function plain(v: unknown): unknown {
    if (neo4j.isInt(v)) return (v as { toNumber(): number }).toNumber()
    if (Array.isArray(v)) return v.map(plain)
    if (v && typeof v === 'object') {
      const o: Record<string, unknown> = {}
      for (const [k, x] of Object.entries(v as Record<string, unknown>)) {
        o[k] = plain(x)
      }
      return o
    }
    return v
  }

  async function query(
    cypher: string,
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>[]> {
    const d = getDriver()
    if (!d) throw new Error('no NEO4J_URI/NEO4J_PASSWORD in .env')
    const session = d.session({ database, defaultAccessMode: neo4j.session.READ })
    try {
      const res = await session.run(cypher, params)
      return res.records.map((r) => plain(r.toObject()) as Record<string, unknown>)
    } finally {
      await session.close()
    }
  }

  function json(res: ServerResponse, body: unknown, status = 200) {
    res.writeHead(status, {
      'content-type': 'application/json',
      'cache-control': 'no-store',
    })
    res.end(JSON.stringify(body))
  }

  /**
   * Answer from Aura, cache the answer, and fall back to the cache when the
   * driver fails — always saying which of the two it was.
   */
  async function served(
    res: ServerResponse,
    key: string,
    run: () => Promise<unknown>,
  ) {
    try {
      const value = await run()
      putCache(key, value)
      return json(res, { ok: true, stale: false, value })
    } catch (err) {
      const hit = getCache(key)
      return json(res, {
        ok: false,
        stale: true,
        staleAgeMs: hit ? Date.now() - hit.at : null,
        error: String((err as Error)?.message ?? err),
        value: hit?.value ?? null,
      })
    }
  }

  function middleware() {
    if (!uri || !password) {
      console.warn('[graph-data] no NEO4J_URI / NEO4J_PASSWORD in .env')
    } else {
      console.log(`[graph-data] ${uri} (${database})`)
    }
    return (req: IncomingMessage, res: ServerResponse, next: () => void) => {
      const url = new URL(req.url ?? '/', 'http://localhost')
      const p = url.pathname
      if (!p.startsWith('/api/graph/')) return next()

      const since = Number(url.searchParams.get('since') ?? 0) || 0
      const runParam = url.searchParams.get('run')
      // The graph keys traces as `<run_id>:<agent>`, so a run id is a prefix.
      const run = runParam && runParam !== 'all' ? runParam : null
      const limit = neo4j.int(
        Math.min(500, Number(url.searchParams.get('limit') ?? 120) || 120),
      )

      if (p === '/api/graph/health') {
        void served(res, 'health', async () => {
          const rows = await query(HEALTH_CYPHER, {})
          return { uri, database, labels: rows }
        })
        return
      }

      if (p === '/api/graph/schema') {
        void served(res, 'schema', async () => {
          const rows = await query('CALL db.schema.visualization()', {})
          const row = rows[0] as
            { nodes?: unknown[]; relationships?: unknown[] } | undefined
          // The procedure returns real Node/Relationship objects; reduce them
          // to what a renderer needs rather than shipping driver internals.
          const nodes = (row?.nodes ?? []).map((n) => {
            const node = n as {
              elementId: string
              labels: string[]
              properties: Record<string, unknown>
            }
            return {
              id: node.elementId,
              label: node.labels?.[0] ?? '?',
              indexes: (node.properties?.indexes as string[]) ?? [],
              constraints: (node.properties?.constraints as string[])?.length ?? 0,
            }
          })
          const rels = (row?.relationships ?? []).map((r) => {
            const rel = r as {
              elementId: string
              type: string
              startNodeElementId: string
              endNodeElementId: string
            }
            return {
              id: rel.elementId,
              type: rel.type,
              from: rel.startNodeElementId,
              to: rel.endNodeElementId,
            }
          })
          return { nodes, rels }
        })
        return
      }

      if (p === '/api/graph/steps') {
        void served(res, 'steps', () => query(STEPS_CYPHER, { since, run, limit }))
        return
      }

      if (p === '/api/graph/delta') {
        void served(res, 'delta', async () => {
          const rows = await query(DELTA_CYPHER, { since, run, limit })
          const row = (rows[0] ?? {}) as Record<string, unknown[]>
          const nodes = [
            ...((row.traces ?? []) as unknown[]),
            ...((row.steps ?? []) as unknown[]),
            ...((row.calls ?? []) as unknown[]),
          ].filter(Boolean)
          return { nodes }
        })
        return
      }

      return next()
    }
  }

  return {
    name: 'msf:graph-data',
    configureServer(server) {
      server.middlewares.use(middleware())
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware())
    },
    async closeBundle() {
      await driver?.close()
      driver = null
    },
  }
}
