# miss-slaytona-forje

Does an agent with memory beat the same agent without it?

One prompt — *"migrate this codebase from Pydantic v1 to Pydantic v2"* — goes
to two swarms at once. The **warm** swarm has a Cognee memory of the codebase
and of every attempt any warm agent has made on it. The **cold** swarm has
nothing. Both get the same clock, the same model, the same checkout and the
same grader.

## What warm has that cold does not

Five things, all of them Cognee's own surfaces. `orchestrator/cognee_layer.py`
is one function per call and nothing else.

| | What it is | Cognee call |
|---|---|---|
| the code graph | the fixture's modules, classes per file, and enola's structural findings | `run_custom_pipeline(get_code_graph_tasks(...))`, read with `SearchType.CODE` |
| the outcome memory | one document per graded attempt, in the `<fixture>-worked` or `<fixture>-failed` node set, carrying the grader's verdict and the diff | `remember(doc, node_set=[...])`, read with `recall(CHUNKS, only_context=True, node_name=[...])` |
| the procedure | a skill Cognee rewrites in place from the grader's score after every attempt | `remember(SkillRunEntry, skill_improvement=...)` + `improve_skill(apply=True)` |
| the session trace | what the attempt did, bridged into the graph and distilled into `session_learnings` | `agent_memory(save_session_traces=True)` + `improve(session_ids=[...])` |
| the deterministic read | a Vibe `post_tool` hook on `bash`: when the agent's own command fails, what earlier graded attempts did about that failure is appended to the tool result | `POST /api/v1/recall` |

The **MCP server** (`cognee_recall` / `_remember` / `_search`) is registered
for warm as well, and whether the model uses it is a measurement rather than a
mechanism: over the last forty runs the agents made 4,767 `bash` calls and 9
`cognee_recall` calls. That is why the reads above do not depend on the model
choosing to make them.

`--memory-mode` selects which halves are live (`hybrid`, `mcp`,
`deterministic`, `off`). `off` makes warm identical to cold, for proving the
harness.

### Why the reads are shaped the way they are

Each of these was measured against cognee 1.6.0 and each one cost a run:

- **`recall` ignores the dataset it is given.** A marker written only to
  dataset A came back from a recall told to read only dataset B. **Node sets
  do** scope, so the node set carries the fixture name and is the isolation
  boundary. `SearchType.CODE` is not dataset-scoped either; its facts carry
  `repo`, which is the filter there.
- **`agent_memory(with_memory=True)` is hardwired to
  `GRAPH_SUMMARY_COMPLETION`**, which re-summarises the subgraph with an LLM
  per call: three calls over one unchanged graph returned 291/329/239
  characters, all describing graph *topology*. So the decorator writes and does
  not read; reads are `CHUNKS` + `only_context=True`, which returns the stored
  bytes and is identical across repeat calls.
- **`remember` defaults to `self_improvement=True`**, which fires a background
  improve that races the explicit one. Off at every call site.
- **A cold node set answers `recall` with a `source="system"` warming-up
  marker, not an empty list.** Rendered, that reads to the model as a memory
  saying "memory is still warming up".
- **enola writes its snapshot to `<repo>/.enola/` by default.** One ingest put
  2.3 MB of `facts.jsonl` inside the tree the grader scores.

## The stack

| Piece | What it does |
|---|---|
| **SGLang on a RunPod GPU pod** | serves the model (Mistral Small 4 119B) |
| **Mistral Vibe** | the agent, vanilla and unmodified, one process per agent, editing a real checkout with its own tools |
| **Daytona** | runs the real test suite in a disposable sandbox. The **only** success oracle |
| **Cognee 1.6.0 + Neo4j Aura** | warm's memory. Every cognee process runs on the harness; the pod reaches them through `ssh -R` |
| **`fixtures/x12sdk`** | [`owgreen-dev/x12sdk` PR #8](https://github.com/owgreen-dev/x12sdk/pull/8), a real merged v1→v2 migration: 383 v1 surfaces, a 261-test oracle, and an answer key that never reaches the pod |
| **`harness/id_fix_proxy.py`** | one per swarm — measures per-swarm token usage, fixes Mistral-incompatible tool-call IDs |

## Non-negotiables

**Vibe must stay vanilla.** `harness/.venv` holds the published
`mistral-vibe` wheel and nothing else. A previous session hand-edited
`get_tool_choice()` from `"auto"` to `"required"`, which made the agent loop
unable to terminate and produced twelve consecutive 0/4 runs. `hooks.toml`,
`config.toml` and `--output streaming` are Vibe's own documented surfaces and
are not patches.

**The model must call tools under plain `tool_choice: "auto"`** and must be
able to end a turn with a text-only message. That is the one hard constraint
on model choice.

**Every cognee process runs on the harness.** A cognee process keeps its
users, datasets and vector index in local SQLite and LanceDB; only the graph
is remote. A cognee on the pod is therefore a second, *empty* memory writing
into the same Neo4j — measured: it saw its own one dataset and none of the
harness's 31, and warm's `cognee_recall` returned nothing all run while every
log line looked healthy. The MCP server and the REST API both run here and are
reverse-tunnelled, so the Neo4j credential never reaches the pod.

**Warm and cold differ only in the declared ways.** Cold is constructed with
`mem=None`, gets no MCP block, no hook and no `COGNEE_*` in its environment —
zero contact with the graph, not gated reads. Warm's two extra costs are
declared and measured: the prompt blocks (`ATTEMPT_DONE.memory_chars`,
`procedure_chars`) and the hook (`hook_commands`, `hook_failures`,
`hook_chars`). `assert_arms_match` fingerprints both arms every run.

**Agents stay in their own checkout**, outside this repo, with a contained
`HOME` — `skill` once pulled the operator's installed skills into context and
issued six `edit` calls against them.

**The verdict is never the model's.** An independent pytest run in a fresh
Daytona sandbox decides, and that is what reaches Cognee as the skill run's
score. The score is `closeness` to the reference migration, not
`tests_passed`: the suite is a step function on these fixtures — the package
imports or it does not — so one correct edit moves it by hundreds while the
migration is barely begun.

## Proving it without a GPU

Three layers, cheapest first. Run all three before renting a pod.

```bash
# 1. the properties, against a fake cognee: no Aura, no key, no GPU
.venv/bin/python -m pytest tests/ -q

# 2. the memory loop, against the REAL graph: three scripted attempts,
#    then read back what attempt 4 would be handed
MSF_FIXTURE_DIR=fixtures/x12sdk .venv/bin/python scripts/prove_memory.py

# 3. the whole loop, against real Vibe and real Cognee, with a scripted
#    model server standing in for SGLang
.venv/bin/python scripts/rehearse_loop.py --vibe "$PWD/harness/.venv/bin/vibe"
```

`prove_memory.py` is the one that answers the question this project exists to
ask. It asserts that a later attempt is handed the WORKED half and the FAILED
half, that the verified fix is in there as a diff, that the brief grows, that
two identical reads over one unchanged graph are byte-identical, that a
sibling fixture's node set does not leak in, and that Cognee rewrote the
procedure.

`rehearse_loop.py` runs the real attempt loop against real Vibe: it installs
the hook where Vibe reads it, makes the scripted model run a command that
cannot succeed, and checks the hook fired.

## Running it

A pod needs an H200-class card (the FP8 weights are ~113 GB, and
`--load-format mistral` fetches a second consolidated copy, so allow 300 GB
of disk) and `gpu.allowedCudaVersions: ["13.0"]` — an exact set, not a floor.
A `minCudaVersion: "12.8"` floor got a 12.8 host, and `torch.cuda` then
reported no accelerator while `nvidia-smi` looked healthy.

**First, once per clone: build your own Daytona snapshot.** The grader runs
the suite in a disposable sandbox, and the sandbox comes from a snapshot in
*your* Daytona account. `.snapshot_state-<fixture>.json` records which one,
and it is deliberately not in this repository — a snapshot id from someone
else's account fails confusingly, where an absent file fails clearly.

```bash
.venv/bin/python scripts/build_snapshot.py     # writes .snapshot_state-<fixture>.json
```

Optionally `scripts/grade_fixture.py` too: it runs the fixture's answer key
and writes `.oracle-<fixture>.json`, which is where the charts get their
reference lines. Both fixtures ship with theirs already measured, so this is
only needed for a fixture you add yourself.

```bash
# On the pod, in this order. The model download is the long pole (40-60 min),
# so start it first and provision underneath it.
scp harness/web-tools/{server.py,requirements.txt} root@POD:/root/harness/web-tools/
ssh root@POD 'nohup setsid bash launch_sglang.sh > /root/sglang.log 2>&1 &'
ssh root@POD 'bash provision.sh 2'
ssh root@POD 'OPENAI_API_KEY=sk-... bash provision_web.sh'

# Wait for the model, then one experiment: N attempts on one checkout,
# then archive, then stop.
curl -s http://POD:30000/v1/models          # must answer first
scripts/run_experiment.sh <ssh-host> <ssh-port> 5 both
```

`provision_web.sh` writes `/opt/swarm/env` from its own environment and
copies the web server out of `/root/harness/web-tools` if bring-up has not
already placed them. Both were assumed by an earlier step that does not
exist: `SwarmHost.write_env_file` is called by nothing, and `host_scripts()`
installs the server only once a run starts, which is after this script.

One experiment is N attempts on **one** checkout. There is no outer loop:
every invocation re-seeds the agents' trees, so calling it repeatedly throws
away the work the last call did. On 2026-09-20 a `while` loop around it ran 14
times and discarded cold's best state of the night.

`--deadline-s` is the **agents'** budget. Everything the harness does per
attempt — the brief, the outcome document, the bridge, the skill rewrite — is
charged to `off_clock` and added back, so both arms get the same amount of
attempt time even though warm does more bookkeeping.

## Reading the result

```bash
.venv/bin/python scripts/inspect_run.py     # newest run by default
```

The counts that matter more than the summary:

- `SANDBOX_CREATED` — times the only success oracle actually ran. Zero means
  throw the run away: 40 consecutive runs reported plausible token ratios
  while the oracle never ran once.
- `MEMORY_WRITE` — one per warm attempt, with the `node_set` it was filed
  under and the document's size. None means warm is cold with extra latency.
- `MEMORY_READ` — `sources: ["cognee.agent_memory"]` is the harness's
  injection; a tool name is the agent's own call. Counting them together
  destroys the answer to "did warm go and get it", which is the question forty
  runs of this project turned on.
- `ATTEMPT_DONE.closeness` — the measure that tracks the migration.
  `tests_passed` beside it is the step function.
- `ATTEMPT_REJECTED` — the suite improved but the tree shimmed `pydantic.v1`
  or stubbed a validator out. Both score 32 of 33 on the old fixture and
  neither is a migration.

## Where the reasoning lives

This README is the only document here, and it is the accurate one. The lab
notebook, the dated audits and an obsolete spec are not in this repository:
they are the record of experiments already run, and what you need is what
runs one.

The reasoning that matters is **in the code, at the line it applies to**.
Nearly every guard in `orchestrator/` and `swarm/` carries the measurement
that put it there — which run, what it cost, and what breaks if it is
removed. `_trim_error_for_prompt` names the 43,054-character prompt;
`argv(multiplex=False)` names the three runs an arm died on;
`score_from_verdict` quotes the six consecutive attempts that scored 0.0.
Read the comment before simplifying the guard.

A few comments cite `NOTES-hard-won.md`. That file is the author's own and
is not published; the comment beside the code says enough to act on.
