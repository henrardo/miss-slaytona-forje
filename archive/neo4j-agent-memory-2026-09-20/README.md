# neo4j-agent-memory layer, archived 2026-09-20

The memory layer as it stood at the end of experiment `swarm-1789919913`
(warm 56 tests / cold 0). Retired in favour of Cognee. Nothing here is
committed anywhere else, so this directory is the only copy.

## What is here

| file | what it did |
|---|---|
| `orchestrator/memory.py` | `ScopedMemory` (13 methods), `build_settings`, `graph_counts`, `reset_graph` |
| `orchestrator/step_memory.py` | the pod-side sidecar: `StepMemoryService`, live per-tool-call step writes |
| `orchestrator/ingest.py` | post-attempt stream ingestion |
| `swarm/sidecar_main.py` | sidecar entrypoint, run as root on the pod |
| `swarm/provision_memory.sh` | the loopback-HTTP MCP server on :8811, credentials in a root-only file |
| `harness/memory_step_hook.py` | Vibe `post_tool` hook client (stdlib only, no secrets) |
| `scripts/` | `eligible_traces`, `mark_legacy_traces`, `reset_memory_indexes` |
| `tests/` | `test_step_memory`, `test_ingest`, `test_scoped_memory_signatures` |
| `requirements-pin.txt` | the pinned extras line -- the extras were load-bearing |

## Why it was retired

Henry, 2026-09-20: *"I've come to the conclusion that neo4j-agent-memory...
doesn't work. At least not here, on this specific project."*

Supporting evidence from this repo's own runs, for whoever reads this next:

- Across every run, the distiller made **0 memory tool calls**, and with
  `--swarm-size 1` there were no peer agents, so warm's treatment reduced
  to the distilled SKILL alone. The graph was written but barely read.
- `search_steps` retrieval never demonstrably changed an attempt.
- The one unambiguous win of the whole project (warm 56 tests, cold 0 in
  `swarm-1789919913`) is attributable to the skill, not to memory --
  see the memory note `warm-passed-56-tests`.

That is a verdict on this layer IN THIS HARNESS, not on the library.

## What replaces it

Cognee (https://github.com/topoteretes/cognee, https://docs.cognee.ai).
Neo4j Aura stays -- Cognee supports it as a first-class graph backend via
`GRAPH_DATABASE_PROVIDER="neo4j"`.
