# Handoff: M4 agent swarm is not converging

## What this is for

Twelve consecutive full runs this session, across several corrected
architectures, have produced **zero successful migrations** — 0/4 warm, 0/4
cold, every time. Each run surfaced one new mechanical cause, was fixed, and
the *next* run surfaced a different one. This document is a complete,
evidence-backed account of everything found so a fresh pass (not more
back-and-forth) can look at the whole picture at once instead of one
symptom at a time.

Nothing below is speculation dressed up as fact. Every claim has a file,
line, or exact log line next to it. Where something is a hypothesis rather
than confirmed, it's labeled as one.

## The goal

A conference demo: a user types one prompt ("migrate this codebase from
Pydantic v1 to Pydantic v2"), it's sent concurrently to two 4-agent swarms —
one with shared Neo4j memory ("warm"), one without ("cold") — and the demo
shows the warm swarm converging faster/cheaper because agents share learned
patterns. Stack: RunPod GPU pod running SGLang (serving
`Qwen/Qwen2.5-Coder-7B-Instruct`) → Mistral Vibe CLI (the agent harness) →
Daytona (sandboxed test execution) → Neo4j (`neo4j-agent-memory`, warm only).

**Hard constraint from the user, stated repeatedly and emphatically this
session: "vanilla."** Do not add timeouts, retry caps, tool restrictions, or
prompt-engineering "safety" beyond what the stated architecture structurally
requires. Every one of those, when added unilaterally in earlier sessions,
turned out to be actively hiding the real signal (see "Resolved issues"
below). Any fix proposed for the open issues at the bottom of this doc
should be judged against this bar: is this a structural/mechanical fix, or
is it a guessed precaution? Only the former is welcome without asking first.

**Second constraint: the warm/cold comparison must stay uncontaminated.**
Anything that isn't Neo4j memory access must be identical between the two
swarms, or the comparison is meaningless.

## Current architecture (as of this doc)

- **`orchestrator/run.py`** — entrypoint. `main_async()` seeds each of the 8
  agents (4 warm + 4 cold) with its own local directory
  (`harness/run-{swarm}-{i}/`, via `seed_repo()`, a fresh `shutil.copytree`
  from `fixture/fastapi_mail/` — the real pydantic-v1 source), renders each
  agent's own Vibe config, and runs both swarms concurrently via
  `asyncio.gather(run_swarm("warm", ...), run_swarm("cold", ...))`.
  `run_swarm()` implements "stop for victory": the instant one agent in a
  swarm converges, the rest of that swarm's tasks are cancelled.
- **`orchestrator/vibe_agent.py`** — the actual per-agent loop.
  `migrate_codebase()` (line 377) retries until the shared run deadline:
  each attempt calls `_run_vibe()` (spawns the real `vibe --prompt ...`
  subprocess, unrestricted, against the agent's local directory), then
  calls `pool.run_pytest()` (Daytona) to independently verify, and feeds the
  real failure text back as `last_error` in the next attempt's prompt if it
  didn't pass.
  - `render_config()` (line 80) writes each agent's `.vibe/config.toml`:
    the SGLang route, plus MCP blocks for `memory` (warm only) and `web`
    (both swarms — see below).
  - `_run_vibe()` (line 218): no `--enabled-tools` filter (all of Vibe's
    native tools — edit/write_file/read_file/bash/grep/task/skill/etc. —
    are available, unfiltered), **except** `--disabled-tools web_search`
    (Vibe's own built-in tool, disabled for cause — see Resolved Issue #4).
  - `_collect_file_contents()` (line 361): walks the agent's local
    `fastapi_mail/` dir and returns `{f"/repo/fastapi_mail/...": bytes}` —
    what gets uploaded to Daytona each attempt.
- **`orchestrator/sandbox.py`** — `SandboxPool.run_pytest()`: uploads
  `file_contents` into a fresh, disposable Daytona sandbox (created from a
  pre-built snapshot/image, `workdir("/repo")`) and runs `test_command`
  (`python -m pytest tests -q`) with `cwd="/repo"`.
- **`orchestrator/snapshot.py`** — `INCLUDED_RELATIVE_PATHS =
  ["fastapi_mail", "tests", "requirements-v2.txt"]`: the Daytona
  snapshot/image is pre-baked with `tests/` (the real, post-migration test
  suite) and a v1 copy of `fastapi_mail/` at `/repo/tests` and
  `/repo/fastapi_mail` respectively; only `fastapi_mail/` gets overwritten
  per-attempt by `_collect_file_contents`'s upload.
- **`harness/memory_mcp_server.py`** — agent-callable memory (warm only):
  `recall_similar_migrations`, `recall_known_patterns`, `record_pattern`
  (staged, only committed to Neo4j after an independent pytest pass).
- **`harness/web_search_mcp_server.py`** — **new this session**. Wraps
  OpenAI's Responses API (`client.responses.create(tools=[{"type":
  "web_search"}])`) as an MCP tool, published to Vibe as `web_search`
  (server alias `web` + tool name `search`; Vibe publishes MCP tools as
  `f"{alias}_{tool_name}"`, confirmed in
  `vibe/core/tools/mcp/tools.py:217`). Registered unconditionally for every
  agent in `render_config()` (not gated on memory) so it isn't a confound.
  Needs `OPENAI_API_KEY` passed explicitly via `--env` (MCP stdio servers
  only inherit a curated minimal env — `HOME`/`PATH`/etc, confirmed in
  `mcp.client.stdio.get_default_environment` — not the parent's full env).
- **`fixture/`** — real fixture, not synthetic: `sabuhish/fastapi-mail`
  PR #195, a real merged pydantic v1→v2 migration. `fastapi_mail/` = pre-
  migration commit (v1 source, what agents edit); `tests/` = post-migration
  commit's test suite (the real success oracle);
  `reference_v2/fastapi_mail/` = the actual answer key (never baked into
  the sandbox).

## Infra / environment

- RunPod pod `9xpixu394yeniu` ("qwen7b-sglang-parallel-demo"), A40 GPU,
  `$0.49/hr`, region `EU-SE-1`. SGLang serves `Qwen/Qwen2.5-Coder-7B-
  Instruct` on the pod's port 30000.
- **Local port 30000 must be tunneled to the pod** for anything to work at
  all: `ssh -N -L 30000:localhost:30000 root@194.68.245.67 -p 22170 -i
  .ssh_runpod/miss_slaytona_forje_pod_key` (the direct SSH route — the
  `ssh.runpod.io` proxy relay does *not* support `-L` port forwarding,
  confirmed: it returns `channel 2: open failed: unknown channel type:
  unsupported channel type` for every forwarded connection). **This tunnel
  is not persistent** — it's a plain background `ssh` process with no
  supervisor; if the shell/session that started it dies, port 30000 goes
  dead silently (this happened mid-session and caused an entire wasted run
  — see Resolved Issue #5). Anyone picking this up should check
  `curl localhost:30000/health` returns `200` before trusting any run.
- Two `harness/id_fix_proxy.py` instances (ports 8899 warm, 8900 cold),
  both forwarding to `localhost:30000` — this is how per-swarm token usage
  is measured (`/usage` endpoint), since Vibe itself doesn't expose
  per-call usage.
- `.env` at repo root: `DAYTONA_API_KEY`, `MISTRAL_API_KEY` (added this
  session), `OPENAI_API_KEY` (added this session), `SGLANG_BASE_URL`,
  `SGLANG_MODEL`. `harness/run-*/` (per-agent `.vibe` dirs, which now
  contain a plaintext `OPENAI_API_KEY` in `config.toml`) is gitignored —
  confirm this is still true (`.gitignore` was patched this session to add
  `harness/run-*/`) before ever running `git add -A` in this repo.
- Neo4j: whatever `NEO4J_URI`/`NEO4J_PASSWORD` resolve to in
  `orchestrator/memory.py:build_settings()`.

## Resolved issues (this session, chronological — context, not action items)

1. **Hidden 180s per-invocation timeout.** An earlier revision wrapped
   every `vibe` subprocess call in a hardcoded 180s cap "for safety."
   Confirmed firing on 100% of attempts — every observed result was an
   artifact of the cap, not the model. Removed; the only time limit now is
   the run's own shared deadline.
2. **Full "vanilla" audit.** User: "assume anywhere you have put your
   little anxious extras is inappropriate... remove EVERYTHING you've added
   out of anxiety." Removed: `id_fix_proxy`'s embedded per-request
   timeouts, memory.py's `extraction_mode="skip"`/hardcoded score
   thresholds, `_task_prompt`'s editorializing ("do not start over from
   scratch"), error-text truncation, `SandboxPool`'s redundant/invented
   `timeout`/`auto_stop_interval` defaults, guessed sandbox-requeue retry
   caps.
3. **Wrong task shape.** Original design gave each agent one claimed file
   out of 12 (a queue). User's actual demo mechanic: one prompt, one whole
   codebase, N agents each independently given the identical task. Rebuilt
   `migrate_codebase()`/`run.py` around that; sourced a real, appropriately
   licensed, human-authored migration (`sabuhish/fastapi-mail`) to replace
   a synthetic fixture.
4. **The big one: editing was routed entirely through Daytona.** Inherited
   from an earlier M3 design: `--enabled-tools daytona_* --enabled-tools
   memory_*` disabled every one of Vibe's own native tools (edit/
   write_file/read_file/bash), forcing all "editing" through Daytona's raw
   remote-shell MCP tool — and inadvertently exposed
   `daytona_computer_use_*` (GUI automation), which 3 of 4 cold agents got
   stuck looping in for nearly an hour. Root-caused via direct session-
   transcript inspection: literally zero tool calls, across all 8 agents,
   ever referenced a `fastapi_mail/*.py` path. Fixed per explicit user
   correction, in three escalating rounds, to the current architecture:
   edits are local (Vibe's own unrestricted native tools, on a real local
   checkout), Daytona is the orchestrator's own tool, called directly,
   never exposed to Vibe, used only to run/validate between attempts.
5. **`web_search` 429 on every call.** Vibe's *native* `web_search` tool
   (`vibe/core/tools/builtins/web_search.py`) calls Mistral's own hosted
   `mistral-vibe-cli-with-tools` model via the beta Conversations API —
   hardcoded, unrelated to the SGLang backend. Every single call, across
   two full runs (with a real `MISTRAL_API_KEY` in place, confirmed
   correctly wired), returned `429: web_search rate limit reached` — and
   the user's own Mistral dashboard showed zero corresponding searches
   (this is a separate, bundled-feature quota, not the account's normal
   API usage — confirmed by reading the tool's source: it targets a
   special CLI-bundled model/endpoint, not the generic Chat Completions
   API). One agent gave up on the actual task and tried to write a
   markdown file admitting it was rate-limited. **Fix:** disabled Vibe's
   native `web_search` per-invocation (`--disabled-tools web_search`);
   replaced it with a working equivalent via a new MCP server
   (`harness/web_search_mcp_server.py`, OpenAI Responses API), registered
   for both swarms equally.
6. **SSH tunnel silently died mid-session, one full run wasted.** A run
   (`full_run9`) produced identical token-usage numbers to the previous run
   — turned out every single agent made *zero* real LLM calls; Vibe's own
   log showed `RemoteProtocolError('Server disconnected without sending a
   response')`, retried with exponential backoff (capped 60s) for the
   entire attempt. Root cause: the local SSH tunnel to the pod's port 30000
   had died (not the pod — confirmed healthy and running via the RunPod
   API). Re-established via the direct SSH route (see Infra section).

## Current state: still 0/4, 0/4, and the failure mode keeps moving

Latest run (`full_run12.log`, event log `runs/m4-1789317019.jsonl`), with
the tunnel confirmed healthy and the new `web_search` MCP tool wired in for
both swarms: **0/4 warm, 0/4 cold converged**, 1730.8s wall-clock (deadline
was 1200s — see Open Issue #3 on why it overran), 89.9M warm / 102.1M cold
combined tokens.

Notably: **`web_search` was not called by a single one of the 8 agents this
run.** The fix removed that specific failure mode cleanly, but didn't get
anyone closer to a real edit, because two *different* things dominated
instead (Open Issues #1 and #2 below). Across every run this session, **no
agent, in either swarm, has ever successfully landed a real edit to
`fastapi_mail/*.py`** that passed the independent pytest check. The handful
of `edit` tool calls actually observed (3-4 total, across ~90 attempts) were
either hallucinated paths (a `main.py` that doesn't exist) or off-task (a
`migration-guide.md` explaining the model couldn't search the web).

## Open issue #1: local/sandbox path mismatch

`read_file` failed **100% of the time** in the latest run — 524, 190, and
92 calls respectively across three warm agents (`run-warm-0/1/2`'s latest
sessions), every single one erroring:

```
<tool_error>read_file failed: File not found at: /repo/tests/conftest.py</tool_error>
```

**Mechanism, confirmed by reading the actual fed-back error text:** the
pytest traceback returned by `SandboxPool.run_pytest()` (run with
`cwd="/repo"` inside Daytona) uses Daytona's own absolute paths —
`/repo/tests/conftest.py`, `/repo/fastapi_mail/config.py` — because that's
where the sandbox actually put things. This traceback is fed back verbatim
as `last_error` in the next attempt's prompt (`_task_prompt`,
`vibe_agent.py:193`). The model reads the real error and reasonably tries
to open the exact path it names — but the *local* directory Vibe is
actually running in (e.g. `harness/run-warm-0/`) has no `/repo` prefix at
all, and `tests/` was never copied there in the first place (only
`fastapi_mail/` is seeded locally via `seed_repo()`; `tests/` only exists
baked into the Daytona snapshot). So the model burns the bulk of an attempt
hammering a file path that cannot exist on the machine it's actually
running on.

This is a straightforward path-space bug, not a model failure or something
needing a policy decision. Two ways to close it (not prescribing — flagging
both as real options for whoever picks this up):
- Make the local checkout mirror the real repo layout completely (copy
  `tests/` locally too, read-only, so paths the model reasons about
  actually resolve), or
- Rewrite `/repo/...` back to local paths in `last_error` before it goes
  into the prompt.

## Open issue #2: `skill` tool exploration loop / token blowup

Cold agents called Vibe's *native* `skill` tool 600+ times each this run
(`run-cold-0`: 602 calls/86 errors, `run-cold-1`: 656/89, `run-cold-2`:
654/329), the overwhelming majority repeating the exact same call —
`{"name": "find-skills"}` — over and over, each time reloading a large
skill-content blob back into context. This is very likely the main driver
of token counts climbing run over run (35M → 60M → 90M cumulative combined
tokens across the session) — not the task getting harder, but the same
content being re-injected repeatedly. Not yet root-caused *why* the model
keeps re-selecting this; see the tool_choice fact below, which may be
directly relevant.

**One fact discovered while investigating this that changes the picture:**
Vibe's tool-choice is **not** "auto" as an earlier planning document in
this repo assumed. `APIToolFormatHandler.get_tool_choice()`
(`vibe/core/llm/format.py:60-61`) unconditionally returns the literal
string `"required"`, confirmed live in an actual request payload sent to
SGLang (`"tool_choice":"required"` in the 400-error body from a context-
overflow this session). **This means the model can never end a turn with
plain text/reasoning alone — it is forced to call some tool on every single
turn**, for the entire session, until the run deadline or a context/token
limit cuts it off. This is very plausibly connected to both this issue and
to the general pattern (across every run this session) of agents grasping
at whatever tool is available — `skill`, `web_fetch` with a hallucinated
URL, `read_file` on a nonexistent path — rather than ever just finishing.
Worth investigating directly rather than assumed; flagging as a fact, not a
diagnosis.

## Open issue #3 (minor): run overshoots its deadline

`full_run12` ran 1730.8s against a requested 1200s deadline. Mechanism (not
yet a problem, just noted): `deadline` in `migrate_codebase()` only bounds
the `_run_vibe()` subprocess wait (`asyncio.wait_for(..., timeout=
remaining)`); the subsequent `pool.run_pytest()` call (upload + sandbox
create + real pytest run) has no timeout of its own and isn't bounded by
the shared deadline at all. Under real load (8 agents, several near the
boundary simultaneously) this can add several minutes past the nominal
deadline. Whether this needs bounding is a judgment call for whoever picks
this up, not a diagnosed bug.

## How to reproduce

```
# 1. Confirm the tunnel is up (see Infra section for the ssh command if not):
curl localhost:30000/health   # expect 200
curl localhost:8899/v1/models  # expect 200
curl localhost:8900/v1/models  # expect 200

# 2. Sweep any leaked sandboxes from a prior run:
source .venv/bin/activate
python3 -c "
import asyncio
from daytona import AsyncDaytona, ListSandboxesQuery
from orchestrator.sandbox import RUN_ID_LABEL
async def main():
    async with AsyncDaytona() as client:
        async for box in client.list(ListSandboxesQuery(labels={})):
            if RUN_ID_LABEL in (getattr(box, 'labels', {}) or {}):
                await client.delete(box)
asyncio.run(main())
"

# 3. Run (20 min; add --deadline-s to change):
python3 orchestrator/run.py --deadline-s 1200 2>&1 | tee run.log

# 4. Inspect what actually happened (don't trust the printed summary alone):
#    - runs/m4-<id>.jsonl -- ATTEMPT_DONE exit_code/vibe_exit_code per attempt
#    - harness/run-{swarm}-{i}/.vibe/logs/session/session_*/messages.jsonl
#      -- the real per-attempt tool-call transcript, most recent dir per agent
```

## File map

| File | Role |
|---|---|
| `orchestrator/run.py` | entrypoint, swarm orchestration, seeding |
| `orchestrator/vibe_agent.py` | per-agent retry loop, Vibe subprocess, config rendering |
| `orchestrator/sandbox.py` | Daytona sandbox lifecycle, `run_pytest` |
| `orchestrator/snapshot.py` | what's baked into the Daytona snapshot |
| `orchestrator/memory.py` | `ScopedMemory` wrapper over `neo4j_agent_memory` |
| `orchestrator/manifest.py` | loads `fixture/manifest.yaml` |
| `harness/memory_mcp_server.py` | agent-callable memory tools (warm only) |
| `harness/web_search_mcp_server.py` | agent-callable web search (both swarms, new this session) |
| `harness/vibe-config.template.toml` | SGLang provider/model declaration |
| `harness/id_fix_proxy.py` | per-swarm usage-tracking proxy in front of SGLang |
| `fixture/` | the real fastapi-mail v1 source, v2 tests, manifest |
| `.ssh_runpod/miss_slaytona_forje_pod_key` | private key for the RunPod tunnel |
