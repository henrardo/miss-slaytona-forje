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
Full account: [NOTES-hard-won.md](NOTES-hard-won.md).

Same rule applies to the wire: `id_fix_proxy` rewrites tool-call IDs and
nothing else. `PROXY_MAX_TOKENS` defaults to 0 — it used to inject
`max_tokens: 2048` into every request Vibe sent.

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
outside this repo (`/tmp/msf-agents/{swarm}-{i}`, override with
`M4_AGENT_ROOT`) so `fixture/`, the answer key in
`fixture/reference_v2/`, and sibling agents are not reachable. They used to
live under `harness/`, and agents did reach all three — warm agents edited
the pristine fixture *and* wrote into a cold agent's codebase.
`check_containment()` runs after every run and prints a **CONTAINMENT
VIOLATION** block if any agent wrote outside its own tree or the fixture
changed. If you see that block, throw the run away.

## Running it

```bash
# 1. Point at the pod. RunPod exposes each HTTP port directly, so no SSH
#    tunnel is needed (and the ssh.runpod.io proxy does NOT support -L anyway):
UP=https://<pod-id>-30000.proxy.runpod.net
curl -s $UP/v1/models                   # must answer, and the `id` it
                                        # returns is what --model must be

# 2. One usage-tracking proxy per swarm. Both forward to the same upstream;
#    two instances is how per-swarm token usage is measured at all.
python3 harness/id_fix_proxy.py 8899 $UP &
python3 harness/id_fix_proxy.py 8900 $UP &

# 3. Build the Daytona image/snapshot (only after fixture/ changes)
python3 scripts/build_snapshot.py

# 4. Run. preflight() checks the proxies, the model match and snapshot
#    freshness before spending any GPU time.
python3 orchestrator/run.py --deadline-s 600 --model <model-id>
```

`--deadline-s` is the **agents'** budget. Setup (config rendering, MCP
smoke-tests, memory warmup, the baseline pytest) runs before the clock starts
and is reported separately as `setup_s`; it used to be deducted silently, which
is why every 600s run reported a 540s wall-clock.

Run it from a terminal or with `< /dev/null`. Vibe reads stdin unconditionally
when stdin is not a TTY, and the orchestrator hands its children `DEVNULL` for
exactly that reason — but the orchestrator itself will happily inherit a pipe.

One attempt is bounded in **turns**, not seconds, by Vibe's own `--max-turns`
(`M4_TURNS_PER_ATTEMPT`, default 8). How many attempts that buys depends on the
card: measured on an A40 with Qwen3-14B and 8 concurrent agents, a turn is ~36s,
so an 8-turn attempt plus its Daytona verdict is ~350s — 2–3 attempts in 900s.
Lower it when the card is saturated. **The binding constraint is tokens/sec,
not the turn budget**; no setting here makes a saturated GPU converge.

`runs/golden.jsonl` is the recorded fallback (`python3 -m orchestrator.replay
runs/golden.jsonl`). It is currently a **placeholder**: the most legible run so
far, not a good one — it shows cross-agent retrieval, a rejected shim attempt
and two memory writes, but neither arm converged. Replace it once a run does.

`--reset-memory` wipes the graph first. Use it to measure *"what four warm
agents do for each other inside one run"*; omit it to measure a graph that
has accumulated across runs. Both are honest demos of different claims — the
run summary always prints the starting graph contents so which one you ran
is never ambiguous.

## Reading the result

The run prints its own gate last, and **exits non-zero if it fails**:

```
GATE ok: 9 attempt(s) graded by 9 real Daytona run(s).
     warm memory: 4 read(s), 3 hit(s), from ['warm-0', 'warm-1']
```

A zero there means throw the run away. 40 consecutive runs reported plausible
token ratios and 4 attempts a side while the oracle **never ran once** — one
Vibe invocation ate the whole deadline, `run_pytest` got 0.0s and raised, and
every trace closed without a verdict. Nothing in the summary said so.

For any run, live or past:

```bash
python3 scripts/inspect_run.py [runs/m4-<id>.jsonl]   # newest by default
```

Three counts matter more than the summary:

- `ATTEMPT_DONE` — attempts that reached a verdict.
- `SANDBOX_CREATED` — times Daytona, the only success oracle, actually ran.
- `MEMORY_READ` — warm retrievals, with `hits` and `sources`. `hits: 0` all
  run means warm == cold, so any `token_ratio` is a null result, not a
  finding.

Then:

- `runs/m4-<id>.jsonl` — every event; `ATTEMPT_DONE.exit_code` is the real
  pytest result. `ATTEMPT_REJECTED` means the suite went green (or improved)
  but the tree shimmed `pydantic.v1` or deleted behaviour instead of porting
  it — see `v1_shim_files` / `gutted_files`.
- `/tmp/msf-agents/{swarm}-{i}.vibe/logs/session/session_*/messages.jsonl` —
  the actual per-attempt tool-call transcript. Tool errors should be ~0, and
  `tool_choice_relaxed` on `/usage` must be 0. Attempts normally end on
  `<vibe_stop_event>Turn limit of N reached</vibe_stop_event>`, not on a
  text-only turn — that is `--max-turns` doing its job, and it exits 1.
- `/tmp/msf-agents/{swarm}-{i}/` is a real git repo — `git diff HEAD~1` shows
  exactly what that agent changed.

## Gotchas that have each cost a full run

- **The endpoint stops answering.** Every agent then retries `Server
  disconnected` with backoff for the whole run and the token counts come out
  looking plausible. `preflight()` checks the proxies and the model name now.
- **A run that grades nothing looks exactly like one that works.** This cost
  40 runs. The `GATE` line and `scripts/inspect_run.py` exist for it.
- **A stale Daytona snapshot** means the oracle is not the suite in
  `fixture/`. Rebuild after any fixture change.
- **`MISTRAL_API_KEY` is rate-limited to zero**, so Vibe's native
  `web_search` 429s on every call. It is disabled via `disabled_tools` in
  the rendered `config.toml` — **not** the `--disabled-tools` flag, which
  leaves the tool in the `tools` array sent to the model.
- **`daytona` org limit is ~10 vCPU**, hence `SWARM_SIZE = 4` (8 agents).

## Documents

- **[NOTES-hard-won.md](NOTES-hard-won.md)** — the things that cost a run to
  learn, each with the measurement. Code comments point here by heading
  instead of carrying the story. Read this before "simplifying" any guard.
- **[AUDIT-2026-09-15-fix-spec.md](AUDIT-2026-09-15-fix-spec.md)** and
  **[FIXES-2026-09-15.md](FIXES-2026-09-15.md)** — the audit that found the
  40 null runs, and what was done about it, including what is still open.
- `miss-slaytona-forje-spec.md` is **historical**. It describes a twelve-module
  synthetic CFP fixture with `P1…P6` pattern tags that was replaced by
  `fastapi-mail`. This README is the accurate document.
