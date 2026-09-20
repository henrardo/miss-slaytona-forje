import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { runsData } from './plugins/runsData'
import { graphData } from './plugins/graphData'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '..')

export default defineConfig({
  plugins: [
    react(),
    // The deck reads the harness's real output directory in place. It never
    // copies or caches it: one source of truth, same as the harness rule.
    runsData({
      runsDir: process.env.MSF_RUNS_DIR ?? path.join(repoRoot, 'runs'),
      // For `.venv/bin/python -m orchestrator.series` — the deck renders the
      // harness's own chart document rather than re-deriving one.
      repoRoot,
    }),
    // The memory graph. Credentials are read from the repo's .env in this
    // Node process and never reach the browser — see plugins/graphData.ts.
    graphData({ repoRoot }),
  ],
  resolve: { alias: { '@': path.join(here, 'src') } },
  server: { host: '127.0.0.1', port: 5273, strictPort: true },
})
