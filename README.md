# miss-slaytona-forje

Neo4j agent memory and a racy stack.

A conference demo. One prompt — *"migrate this codebase from Pydantic v1 to
Pydantic v2"* — goes to two 4-agent swarms at once. One swarm shares a Neo4j
memory graph (**warm**); the other has no memory at all (**cold**). Both get
ten minutes. At the end you compare convergence, token spend and cost.

## The stack

| Piece | What it does |
|---|---|
| **SGLang on a RunPod GPU pod** | serves the model (target: Mistral Small 4; a cheap stand-in during development) |
| **`harness/id_fix_proxy.py`** | one per swarm — measures per-swarm token usage, fixes Mistral-incompatible tool-call IDs |
| **Mistral Vibe** | the agent harness. Vanilla, unmodified, one subprocess per agent, editing a real local checkout |
| **Daytona** | runs the real test suite in a disposable sandbox. The **only** success oracle |
| **Neo4j + `neo4j-agent-memory`** | shared memory — warm swarm only |
| **`fixture/`** | [`sabuhish/fastapi-mail` PR #195](https://github.com/sabuhish/fastapi-mail/pull/195), a real merged v1→v2 migration |

Each component is plain and isolated. Vibe never talks to Daytona or Neo4j;
the orchestrator calls those itself, between Vibe turns.

## Non-negotiables

**Vibe must stay vanilla.** `harness/.venv` is verified byte-identical to the
published `mistral-vibe` wheel. A previous session hand-edited
`get_tool_choice()` from `"auto"` to `"required"`; because Vibe can only end
a turn on a text-only assistant message, and SGLang constrain-decodes
`required`, that made the agent loop *unable to terminate* and produced
twelve consecutive 0/4 runs. `preflight()` now trips if it ever comes back.
Full account: [FINDINGS-2026-09-13-refactor.md](FINDINGS-2026-09-13-refactor.md).

**The model must call tools under plain `tool_choice: "auto"`.** This is the
one hard constraint on model choice. Qwen2.5-Coder-7B does not (it writes
tool calls as markdown prose) and cannot be used. Check any candidate before
committing a run to it.

**Warm and cold must differ in exactly one thing.** Cold agents are built
with `mem=None` and never get a `memory` MCP block — zero Neo4j contact, not
gated reads. Anything else that touches one arm and not the other is a bug,
including latency: blocking calls on the shared event loop leak warm's
memory cost into cold's wall-clock.

**Agents must stay in their own checkout.** `AGENT_ROOT` puts each agent
outside this repo (`$TMPDIR/miss-slaytona-forje-agents/{swarm}-{i}`,
override with `M4_AGENT_ROOT`) so `fixture/`, the answer key in
`fixture/reference_v2/`, and sibling agents are not reachable. They used to
live under `harness/`, and agents did reach all three — warm agents edited
the pristine fixture *and* wrote into a cold agent's codebase.
`check_containment()` runs after every run and prints a **CONTAINMENT
VIOLATION** block if any agent wrote outside its own tree or the fixture
changed. If you see that block, throw the run away.

## Running it

```bash
# 1. Tunnel to the pod (the ssh.runpod.io proxy does NOT support -L)
ssh -N -L 30000:localhost:30000 root@<pod-ip> -p <port> \
    -i .ssh_runpod/miss_slaytona_forje_pod_key &
curl localhost:30000/v1/models          # must answer

# 2. One usage-tracking proxy per swarm
python3 harness/id_fix_proxy.py 8899 http://localhost:30000 &
python3 harness/id_fix_proxy.py 8900 http://localhost:30000 &

# 3. Build the Daytona image/snapshot (only after fixture/ changes)
python3 scripts/build_snapshot.py

# 4. Run. preflight() checks tunnel, proxies, model match and snapshot
#    freshness before spending any GPU time.
python3 orchestrator/run.py --deadline-s 600 --model <model-id>
```

`--reset-memory` wipes the graph first. Use it to measure *"what four warm
agents do for each other inside one run"*; omit it to measure a graph that
has accumulated across runs. Both are honest demos of different claims — the
run summary always prints the starting graph contents so which one you ran
is never ambiguous.

## Reading the result

Don't trust the printed summary alone.

- `runs/m4-<id>.jsonl` — every event; `ATTEMPT_DONE.exit_code` is the real
  pytest result.
- `harness/run-{swarm}-{i}/.vibe/logs/session/session_*/messages.jsonl` — the
  actual per-attempt tool-call transcript. **Three numbers tell you whether
  the harness is healthy**: tool errors should be ~0, there should be at
  least one text-only assistant turn (the agent chose to stop), and
  `tool_choice_relaxed` on `/usage` must be 0.
- `harness/run-{swarm}-{i}/` is a real git repo — `git diff HEAD~1` shows
  exactly what that agent changed.

## Gotchas that have each cost a full run

- **The SSH tunnel dies silently.** Port 30000 stops answering, every agent
  retries `Server disconnected` with backoff for the whole run, and the token
  counts come out looking plausible. `preflight()` checks this now.
- **A stale Daytona snapshot** means the oracle is not the suite in
  `fixture/`. Rebuild after any fixture change.
- **`MISTRAL_API_KEY` is rate-limited to zero**, so Vibe's native
  `web_search` 429s on every call. It stays disabled via `--disabled-tools`.
- **`daytona` org limit is ~10 vCPU**, hence `SWARM_SIZE = 4` (8 agents).
