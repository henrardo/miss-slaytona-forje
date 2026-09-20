# Hard-won notes

Things that cost a run (or twelve) to learn. Code comments point here by
heading instead of carrying the whole story, so the source stays readable and
these stay findable.

Rule for adding to this file: a note earns its place if it records a
**measurement** or a **reproduction**, not a worry. If the failure mode it
describes can no longer happen, delete the note and the guard together.

---

## The loop must produce a graded attempt

**Symptom.** 40 consecutive runs (`runs/accumulation.csv`, runs 63–102):
0 agents converged, `warm_best = cold_best = 0`, exactly 4 attempts a side,
`token_ratio` 0.79–1.26 with no trend, `mem_calls = 0`. 19 of the last 20 run
logs: `ATTEMPT_DONE: 0`, `SANDBOX_CREATED: 0`, `MEMORY_WRITE: 0`.

**Cause.** `_run_vibe` was handed the whole remaining deadline. Vibe's agent
loop exits only on a text-only assistant message, and the model never emitted
one — measured on a real transcript, `cold-0` made 22 tool-calling turns and
`warm-0` 19, with **zero** text-only turns. So one invocation consumed the run,
and `pool.run_pytest` was then called with `timeout=max(0.0, deadline - now)`
= `0.0` and raised `TimeoutError` every time. Daytona — the only success
oracle — never ran after the baseline. Every trace closed as
`"ran out of time mid-attempt"`, which `_reasoning_context` correctly filters
out, so warm retrieval was empty **by construction** and warm ≡ cold.

**Fix.** Bound an attempt in turns with Vibe's own `--max-turns`, and reserve
`VERDICT_RESERVE_S` for the Daytona check. Don't start an attempt that cannot
afford its own verdict.

**Do not** "fix" this by giving Vibe a wall-clock kill. A wall-clock kill lands
mid-turn and leaves a dangling tool call in the transcript; `--max-turns` lands
on a turn boundary and the session stays resumable.

## Prompt block order is A, B, C — and it is not cosmetic

Sec. 6.1: Block A (the instruction, byte-identical for every agent for the
whole run) → Block B (retrieved memory, warm only) → Block C (this attempt's
error).

`_task_prompt` used to PREPEND the memory block, making the order B, A, C.
Besides destroying the shared RadixAttention prefix for exactly the arm whose
token count is the headline number, it changed what the model did: an agent
handed a page of "### Similar Past Tasks" before being told what to do reports
on it rather than acting.

Measured on one 4-a-side run, same model, same everything else:

| | attempts | assistant turns | tool calls | text-only turns |
|---|---|---|---|---|
| warm-1 | 3 | 6 | 4 | **2** |
| warm-2 | 3 | 5 | 3 | **2** |
| cold-2 | 1 | 8 | **8** | **0** |
| cold-3 | 1 | 8 | **8** | **0** |

Warm got ~2 productive turns per attempt against cold's 8, and warm attempts
finished in 65–142s against cold's 347–360s — so warm accumulated *more graded
attempts* while doing a quarter of the work in each. Any comparison drawn from
that run favours warm for the wrong reason.

Cold's whole prompt (no memory, no error) must be a strict prefix of warm's.
If it isn't, the arms differ in something other than memory.

## `pgrep -f "orchestrator/run.py"` matches your own waiter

Not a project bug, but it cost an hour: a shell loop like

```bash
until ! pgrep -f "orchestrator/run.py"; do sleep 10; done
```

never exits, because the wrapper shell's own command line contains that string,
so `pgrep -f` matches it. The loop spins forever and whatever you queued behind
it never starts — while the proxies still show a rising request count from the
*previous* run, which makes it look like work is happening.

Match on the interpreter instead (`pgrep -f "[p]ython.*orchestrator/run"`), or
just use the launcher's own job control.

## `--max-turns` is cumulative across `--continue`

`TurnLimitMiddleware` tests `context.stats.steps - 1 >= max_turns` against the
**whole session's** step count, and `--continue` restores that count with the
history.

Measured against the proxy's request counter: a session with 3 users and 3
assistants, resumed with `--max-turns 2` → "Turn limit of 2 reached", **0**
completion requests. Same session with `--max-turns 5` → **0** requests. With
`--max-turns 8` → exactly **2** requests.

`stats.steps` increments per user message (`_loop.py:2022`), per completed
assistant turn (`:2106`), and per compaction (`:1780`). Tool results do not
count. So the allowance for N further turns is `users + assistants + N`, which
is what `_steps_used()` reconstructs from the transcript.

A flat per-attempt allowance gives attempt 2 onward **zero** turns: the agent
appears to run, produces no tokens, changes nothing, and is still graded.

## Under load, Vibe exits without completing a turn

The completions fail, Vibe retries with backoff, and it exits non-zero having
written the session's user message and **no assistant message at all**. The
attempt looks normal from outside: ~135s elapsed, a session directory on disk,
a Daytona verdict.

Observed in a 2-a-side run: 3 of `warm-1`'s 4 attempts and 2 of `cold-0`'s.
The same configuration at `--swarm-size 1` was clean —
`turns=9 stop='Turn limit of 8 reached'` on every attempt — so the loop is
right and the endpoint was the problem. This is the README's "Server
disconnected" gotcha one level down, where nothing could see it.

Grading such an attempt is actively harmful: the tree is byte-identical to the
previous attempt, so it spends a sandbox to re-derive a verdict already held,
and writes a "no edit was made" trace that retrieval later surfaces as
knowledge. `migrate_codebase()` now compares `_steps_used()` before and after
and emits `ATTEMPT_ABORTED` instead.

**Diagnostic:** `turns_used <= 1` on a graded `ATTEMPT_DONE` means the agent did
nothing; `scripts/inspect_run.py` flags it.

## `--max-turns` exits 1

So `resume = last_exit == 0` refuses to resume on every attempt and throws away
everything the agent learned. Key on Vibe's own stop event instead:
`<vibe_stop_event>Turn limit of N reached</vibe_stop_event>`. See
`_ended_cleanly()`.

Still do **not** resume a session that died some other way — usually context
overflow, and resuming replays the same oversized history into the same 400.
Compaction cannot run on a history already too large to send. Measured:
`cold-3` spent 58 attempts at ~5s each in that loop, every call rejected with
"The input (35516 tokens) is longer than the model's context length (32768
tokens)".

## Vibe blocks on inherited stdin

`cli/cli.py:463` calls `get_prompt_from_stdin()` unconditionally before
dispatching, and it does a blocking `sys.stdin.read()` for **any** stdin that
is not a TTY. It exists so `echo "do this" | vibe -p` works.

Run the orchestrator from a terminal and stdin is a TTY, `isatty()`
short-circuits, nothing happens. Run it under `nohup`, `&`, a redirect, CI, or
any supervising harness, and stdin is a pipe that never reaches EOF — so
**every agent blocks inside that read forever, before its first LLM call.**

Confirmed by stack-sampling a hung agent: main thread in
`_io_FileIO_readall_impl → read()`, and the proxy's `/usage` showing 0
requests. The symptom is a run that burns its whole deadline with zero tokens,
which is indistinguishable from a dead endpoint.

`_run_vibe` passes `stdin=asyncio.subprocess.DEVNULL`.

## The model must tool-call under plain `tool_choice: "auto"`

The one hard constraint on model choice. Vanilla Vibe sends `"auto"`, and the
loop can only end a turn on a text-only assistant message.

A previous session hand-edited the installed package —
`APIToolFormatHandler.get_tool_choice()` (`core/llm/format.py:62`) — from
`"auto"` to `"required"`, to work around a model that would not spontaneously
emit tool calls. SGLang enforces `"required"` with constrained decoding,
confirmed directly against the pod:

```
tool_choice=None       -> finish=stop       tool_calls=[]      content='Hello! ...'
tool_choice='auto'     -> finish=stop       tool_calls=[]      content='Hello! ...'
tool_choice='required' -> finish=tool_calls tool_calls=['bash'] content=''
```

…for the prompt "Say hello. Do not use any tools." So the model was
grammar-constrained into a tool call on every turn and **the agent could never
stop**. `run-warm-0`'s session: 576 assistant messages, 576 tool results, not
one text-only turn, 524 of them `read_file`. That is the whole of the "agents
get nothing done" symptom across twelve runs, and every downstream oddity
(600+ `skill` calls, 90M-token runs) is a consequence.

`harness/.venv` is verified byte-identical to the published wheel.
`id_fix_proxy`'s `tool_choice_relaxed` counter is a tripwire: vanilla Vibe
never sends `required`, so anything but 0 means the package has been patched
again. `preflight()` trips on it.

Qwen2.5-Coder-7B does **not** satisfy the constraint (it writes tool calls as
markdown prose). Qwen3-8B and Qwen3-14B do. Check any candidate before
committing a run to it.

## Don't inject max_tokens into every request

`PROXY_MAX_TOKENS` defaulted to 2048, so every completion in every run carried
a ceiling the harness never asked for. The justification was Qwen3's reasoning
mode — the cheap stand-in, not the demo's model. On Mistral Small 4 a 2,048
ceiling truncates a turn mid-tool-call and yields malformed JSON, which is
indistinguishable from "this model emits unreliable tool calls" — the exact
symptom that led to the `get_tool_choice` patch above.

It now defaults off. The runaway-generation failure it was added for (one turn
decoding for minutes, all eight agents still inside their first response at the
deadline) is handled by bounding the attempt in turns instead.

## Mistral tool-call ids must match `^[a-zA-Z0-9]{9}$`

Vibe generates OpenAI-style ids (`call_` + 24 hex). `mistral_common`'s strict
request validator (`protocol/instruct/validator.py`) rejects them, so a Vibe
conversation that echoes its own prior `tool_call.id` back as a tool-result
message's `tool_call_id` gets rejected by SGLang on the very next turn.

Root-caused by bisection replay of captured request bodies down to a minimal
curl case. There is no Vibe-side config for the id format, so
`id_fix_proxy.py` rewrites them response-side; Vibe then stores and echoes the
compliant id itself, so no request-side fix is needed.

## The oracle has two holes the test suite cannot see

`tests/` comes from the real merge commit and never calls a v2-only API, so:

- **v1 shim.** Rewriting every `from pydantic import ...` to
  `from pydantic.v1 import ...` and changing nothing else gives **32 of 33
  passing**. The oracle is 97% gameable.
- **Deleted behaviour.** Run 54's `warm-2` scored 32/33 — the best result the
  harness ever recorded, and reported at the time as a verified success — by
  replacing a `@root_validator` body with `return values` and leaving the
  original body unreachable below it. The function still imports, still has the
  right name, still carries a v2 decorator.

The asymmetry is what makes this load-bearing: gutting the file scores 32,
migrating it wrongly-but-honestly scores 3 (run 56, same file, same decorator).
Shared memory propagates whichever scored higher, so the hole **actively trains
the warm swarm to delete code**.

**How dominant the shim strategy is, measured once the loop could actually
grade attempts (2026-09-15):** in one 2-a-side run, **all nine** graded
attempts were rejected as shims -- every agent in both arms, independently,
and repeatedly after being told:

```
warm-1 attempt 1: pytest_passed=32  shimmed=[config.py, fastmail.py, schemas.py]
warm-1 attempt 2: pytest_passed=32  shimmed=[config.py, fastmail.py, schemas.py]
cold-1 attempt 1: pytest_passed=31  shimmed=[config.py, fastmail.py, schemas.py]
cold-1 attempt 2: pytest_passed=31  shimmed=[config.py, fastmail.py, schemas.py]
cold-1 attempt 3: pytest_passed=31  shimmed=[config.py, fastmail.py, schemas.py]
cold-0 attempt 2: pytest_passed=27  shimmed=[schemas.py]
```

Without these two checks that run reports **32 of 33** for warm-1 and reads as
near-total success. This is not a rare edge case to guard against; it is what
the model does first, and keeps doing.

The whole run therefore scored `errors_cleared 0` and `best_passed 0` for both
arms -- which is the correct answer, and only possible because the gates stop
rewriting `passed`/`signature` (see above). A harness without them reports this
same run as a near-win.

The rejection notice is now placed at the TOP of the fed-back error rather than
appended after the pytest output. Appending buried it ~85% into a
5,655-character prompt; verified present and still ignored. Whether the top
placement helps was untested at the time of writing -- check before trusting
it.

`v1_shim_files()` and `gutted_files()` gate `success`. They deliberately do
**not** rewrite `passed` or `signature` any more: forcing `passed = 0` and
substituting a synthetic signature fed that signature into `seen_signatures`,
so gaming the oracle *inflated* `errors_cleared` — the metric used to compare
the arms when neither converges.

## A changed error signature is not progress

Run 21: an agent replaced `from pydantic import BaseSettings as Settings` with
`from pydantic_settings import BaseSettings, SettingsConfigDict`, clearing
`PydanticImportError` and introducing `NameError: name 'Settings' is not
defined` — it dropped the alias every later line in `config.py` depends on.

The signature changed, so the attempt scored as a success, the diff was written
to shared memory as a verified fix, and warm agents then retrieved it — at
similarity 0.72, with the broken diff quoted verbatim — and reproduced the
mistake. Four traces hit that `NameError` and none cleared it.

Memory that propagates a wrong fix is worse than no memory, and the fault was
in the success criterion. Progress is now `tests_passed` strictly increasing.

## Similarity cannot rank traces on an identical codebase

A trace's embedding is built from its `task`, and `task` is the pytest error
signature — so every agent that hit the same error has a byte-identical task
string. Measured on the run 53–56 graph: 16 of 37 traces share one task string,
and a query for it returns all 15 fetched rows at similarity **0.9996**, tied
to four decimal places. The vector index returns them in storage order and
`[:5]` takes whichever came back first.

That is the whole of the run 54 "result": its `warm-2` drew the one informative
trace out of six candidates and jumped to 32/33 on attempt 1. Runs 55 and 56
asked the identical question of a larger graph, drew differently, got 3. It was
a coin toss, and it gets worse as the graph grows.

The tie is now broken on outcome (`tests_passed` from `metrics_json`), then
recency.

## Don't store tool results as messages

Every stored message goes through entity extraction, and Vibe renders
`read_file` results with a line-number gutter (`  12→from pydantic import ...`).
The extractor mined each gutter token as a named entity: **78 of 229 `:Entity`
nodes** were names like `'100→'`, `'171→'`, `'0.17s'`, `"'1"`. Those are what
`get_context(include_long_term=True)` served back to warm agents as "what you
remember".

Nothing is lost by dropping them — the tool's output is already stored, capped,
as the owning `ReasoningStep.observation`, which is the field the reasoning
layer embeds.

Related, and still true: do **not** store the entire Vibe stdout as one
message, and do **not** store the orchestrator's own constructed prompt.
The prompt contains the "What you remember" block, so storing it makes memory
retrieve its own previous output — attempt N's prompt embedding attempt N−1's
memory block, which embeds N−2's. Caught live at 15,170 chars and growing.

## Entity resolution is not merging

Observed on the live graph: three `pydantic` nodes with contradictory type
labels (`Organization/Company` twice, `Object/Document/Device` once),
`root_validator` as both an `Object` and a `Person`, `pydantic-settings` ×3.

The build spec asserts the resolver merges these. It does not, currently.
Unresolved — check whether `ExtractionConfig(enable_llm_fallback=False)`
suppresses the resolution pass before blaming `DeduplicationConfig`.

## The warmup must not mention the task

The pre-run memory warmup (there to pay the spaCy/GLiNER/embedder load cost
outside the measured window) used to store: *"migrating fastapi_mail config.py
from pydantic BaseSettings to pydantic_settings for Pydantic v2."*

That is the correct fix for the first file in the failure chain, written into
the **warm arm's** memory scope, on every run, and nowhere in cold's. Confirmed
in the graph: `Conversation {session_id:'warmup', user_identifier:'warm'}` with
`pydantic_settings`, `pydantic-settings` and `pydantic BaseSettings` all
present as warm-scope entities.

Any string of similar length loads the same models.

## Extraction cost, measured

```
spacy + gliner + llm (default)   2071 ms/message
enable_llm_fallback=False         289 ms/message
```

An attempt stores tens of messages, so that is ~103s of memory writes per
attempt against ~14s. Run 30: warm completed 1 attempt while cold completed 17.
Retrieval was never the expensive half.

POLE+O typing survives with the fallback off — checked directly, spaCy and
GLiNER still produce `['Entity','Person']` / `['Entity','Location','City']` /
`['Entity','Object','Device']`. Precision drops a little.

This requires the `[gliner]` and `[spacy]` extras. Without them the local
stages are skipped and the long-term graph degrades silently.

## Agents must stay in their own checkout

`AGENT_ROOT` puts each agent outside this repo so `fixture/`, the answer key in
`fixture/reference_v2/`, and sibling agents are not reachable. They used to
live under `harness/`, and the 2026-09-13 run did all three of:

- four warm agents edited `fixture/fastapi_mail/config.py` itself, corrupting
  the pristine source every later run seeds from;
- `warm-0`, `warm-1` and `warm-3` each wrote into `harness/run-cold-1/` — a
  warm agent editing a cold agent's codebase, which by itself invalidates the
  comparison;
- one agent ran grep against `fixture/reference_v2/`, the answer key.

The agents were not being adversarial. They were handed absolute paths in the
fed-back pytest output, walked up from them, and found a tree full of
pydantic-v1 code that looked like more of their own task.

`fixture/` is also `chmod a-w` on disk, because directory placement is not
containment when the agent has bash and `--trust`.

`check_containment()` is a tripwire on `edit`/`write_file` only. Vibe also
ships `bash`, `git_bash` and `experimental_bash`; an agent writing with
`sed -i` is invisible to it.

## Keep the paths the model must retype short

`AGENT_ROOT` was `tempfile.gettempdir()/...`, which on macOS expands to
`/var/folders/r9/py7xygs97mdfz1lxk_gyfmlw0000gp/T/...` — a 20-character random
blob the agent has to reproduce exactly, by hand, because Vibe's `read_file`
description says "use absolute paths".

Run 13's transcripts contain 9 absolute paths and 0 relative ones. Two of the 9
(22%) were typos — `gyfmlw00000gp` for `gyfmlw0000gp`, one zero too many — both
`edit` calls, both silently written to a directory that does not exist. The
agent believed it had made the edit; the orchestrator uploaded the unedited
file; the suite failed on a change already "made".

118 characters down to 47 fixed it. Same reason `_localize_sandbox_paths`
strips `/repo/` rather than swapping in the local root: 11 of run 38's 66
failed edits were "File does not exist", including `fastapi-mail/config.py` for
`fastapi_mail/` — a hyphen for an underscore, 40 characters in.

`.resolve()` is load-bearing too: on macOS `/tmp` symlinks to `/private/tmp`,
and Vibe records a session against its *resolved* cwd, so launching with the
unresolved spelling made `--continue` die with "No previous sessions found" —
`warm-0` once burned 27 consecutive 8-second attempts that way, which also
faked a 2.05x token ratio.

## VIBE_HOME must be a sibling of the checkout, not a child

`messages.jsonl` is one JSON object per line, with lines up to 210,108
characters. With the home inside the directory the agent was told to search:

```
agent edits config.py, writes about BaseSettings
  -> its transcript now contains "BaseSettings"
  -> agent greps "BaseSettings" to find what else to migrate
  -> grep matches its own transcript, returns a 64,000-char line
  -> the 32,768-token context window is gone in one tool result
```

Run 11: seven greps returned ~64k chars each, `max_matches: 10` made no
difference because a single *match* is a 210k line, 827,189 characters of tool
results across 75 results. Eight agents managed 15 attempts in 411 seconds.

Session logs go to `$VIBE_HOME/logs/session`, so the home can be anywhere.

## Clear session logs between runs

`VIBE_HOME` persisted across runs, so transcripts accumulated — 14 to 17
session directories per agent by run 34. `_replay_session_messages` globs
*every* transcript under the home and the line-offset dict starts empty each
run, so on attempt 1 each warm agent replayed every message it had ever
produced into the current run's trace: 476 messages over 16 transcripts, 118.6s
of memory work on `warm-1` alone against a 600s budget. Cold pays none of it.

It also corrupted the data: tool calls from a run days earlier were attached as
`ReasoningStep`s to a trace keyed on today's error.

## Disabled tools and skills, and why

Applied identically to both swarms, so none of it can skew warm against cold.

- **`web_search`** — routes through Mistral's hosted API; this repo's
  `MISTRAL_API_KEY` 429s on every call (re-confirmed against a bare
  `mistral-small-latest` completion, so the key is exhausted outright). 24
  calls in one run, all failing, 32% of every tool error. Must be disabled in
  `config.toml`, **not** via `--disabled-tools`: with the flag alone the tool
  is still in the `tools` array sent to the model. Confirmed by capturing the
  request body both ways. `harness/web-tools/server.py` publishes `web_lookup`
  as the working replacement.
- **`disabled_skills = ["*"]`** — all four builtins document *how to use Vibe*.
  Run 12: the agents' opening move was "I should check if there are any
  existing skills", and the `vibe` skill returned 54,708 characters (~13,700
  tokens, 42% of a 32k window) five separate times. Skills were 284,428 of the
  run's 314,652 characters of tool results — 90% — while the actual work
  (edit/grep/read_file) came to under 11,000.
- **`skill`** — with every skill disabled it can only answer "Available
  skills: none". Run 15's agents called it 8 times, each inventing a skill they
  hoped existed ("pydantic_v2_migration", "pydantic_v2_migrator", …).
- **`task`** — run 14: five `task` calls spawned `explore` subagents that
  between them accounted for 527 of the run's 673 messages (78% of the token
  budget). The largest made 47 `read_file` calls and ~100 turns before
  returning, as its finished answer, `from pydantic.main import BaseModel`,
  which is wrong. `explore` subagents are read-only, so none of it could become
  an edit even if it had been right, and the parent blocks while they run — 17
  attempts started, 9 finished. **Revisit on the target model**: this one is a
  judgement about an 8B, not a fact about Vibe.

## MCP servers need their own venvs, and must be smoke-tested

`mistral-vibe` pins `mcp==1.28.1`; `fastmcp` requires `mcp>=2`. Installing
fastmcp beside Vibe silently upgrades `mcp` and Vibe's MCP subsystem stops
importing (`ImportError: cannot import name 'RequestContext'`), which removes
**every** MCP server from the model's tool list. An MCP stdio server shares
nothing with its client but the protocol, so it gets its own venv.

`list_tools` succeeding proves only that the server started and can describe
itself. It proved exactly that, twice, while the tool underneath was dead:

- `harness/web-tools/server.py` raised `ModuleNotFoundError` on import for an
  entire run series. Vibe reports that only as "MCP stdio discovery failed:
  Connection closed" and the tool silently vanishes.
- `uvx "neo4j-agent-memory[mcp]"` (without the `openai` extra) started
  cleanly, published all its tools, and answered every embedding-backed call
  with `"Error getting context: OpenAI package not installed"`.

Both are indistinguishable from a model that chose not to call the tool. That
one cost five runs and two confident wrong conclusions: that this codebase had
a step no agent could bootstrap, and that small models don't use memory tools.
Both were a dead server. `_smoke_test_tool` now calls one tool per server and
reads the answer.

`--with httpx` works around a packaging bug in the published package (seen on
0.6.0): `_connect_bolt()` imports `neo4j_agent_memory.nams._unsupported`, which
pulls `nams/transport` → `import httpx`, but httpx is declared only by the
`nams` extra, and `[openai]` brings openai 3.x which depends on httpx2.

## /usage counters are cumulative

`id_fix_proxy`'s counters never reset — they count everything since the proxy
process started. Reading them once at the end and reporting the result as "this
run used N tokens" is reading an odometer and calling it a speed.

It corrupted the whole run 12–17 series: reported LLM calls rose
45 → 104 → 321 → 526 → 601 → 648 → 665 and were presented as a 13x throughput
improvement, when the real per-run figures were 104, 217, 205, 75, 47, 18 —
throughput *falling*. Snapshot before, snapshot after, subtract.

## The suite runs in ~70s locally on macOS, for a silly reason

`email.utils.make_msgid()` → `socket.getfqdn()` → 5.01s reverse-DNS timeout,
× 14 tests. Measured directly (`getfqdn 5.011s`). Almost certainly local-DNS
only, and probably not reproducible in a Linux container — **verify in Daytona
before assuming.**

It matters because the task prompt tells agents to run the suite after every
change. While the imports are broken it costs nothing (collection dies early).
The moment an agent fixes the imports, its self-check jumps from ~1s to ~70s.

## Ground truth

`fixture/reference_v2` + the real `tests/` passes **33/33** in the agent venv.
If `gutted_files()` or `v1_shim_files()` ever flags `reference_v2`, the check is
wrong, not the ground truth.

Pristine v1 under pydantic v2 dies at collection with
`PydanticImportError: BaseSettings has been moved` and passes **0** tests — a
conftest that fails to import aborts pytest before collection, so there is no
tally at all until the whole package imports cleanly. `tests_passed` is
therefore pinned at 0 until that first fix lands.

## SGLang version pins

`sglang==0.5.14` for `mistralai/Mistral-Small-4-119B-2603`. Every later release
through at least 0.5.19 is broken in one of two independent ways, both found by
bisecting the PyPI release history between 0.5.10 and 0.5.19:

1. `tool_choice="auto"` silently returns empty output (no tool_calls, no
   content, 1 completion token) on 0.5.15, 0.5.15.post1 and 0.5.16 — 4/4
   reproducible on each, immediately upstream of 0.5.14 which gets it right
   4/4. Vibe hardcodes `"auto"`, so this is fatal for the whole harness.
2. From 0.5.17 the server segfaults deterministically during decode-phase CUDA
   graph capture (full faulthandler traceback: inside the MLA "absorb"
   attention path's batched FP8 matmul) on every configuration tried — both GPU
   families (H100 sm90, B200 sm100), tp=1 and tp=2, every `--fp8-gemm-backend`,
   with and without `--disable-custom-all-reduce`, with and without EAGLE, at
   every CUDA-graph batch size from 8 to 256. Confirmed in 0.5.17, 0.5.18 and
   0.5.19 directly. A control test (Qwen2.5-7B, identical install, hardware and
   tp) came up clean, ruling out environment.

The A40 has no FP8. Don't bump the pin without re-running the bisection.

**THE HOST NEEDS CUDA 13.0.** `sglang[all]==0.5.14` pins
`torch==2.11.0+cu130` and `flashinfer_python[cu13]`, so a host whose driver
reports CUDA 12.8 installs cleanly and then dies at startup with

    RuntimeError: No accelerator (CUDA, XPU, HPU, NPU, MUSA, MPS) or
    platform plugin is available.

`torch.cuda.is_available()` is False while `nvidia-smi` looks perfectly
healthy, which reads as a broken install rather than a host mismatch. The
working B200 pod logged `torch 2.11.0+cu130 cuda 13.0 available True cap
(10, 0)`; a 12.8 host logs the same torch with `available False`.

When creating the pod, pass **`gpu.allowedCudaVersions: ["13.0"]`**, not
`minCudaVersion: "12.8"` -- the latter is a floor and the scheduler will
happily hand back a 12.8 host. H200 hosts exist at 12.8, 12.9 and 13.0
(`get-gpu-type "NVIDIA H200" include=AVAILABILITY product=POD`). Cost of
learning this the second way: one pod, ~$0.40 and 20 minutes.

Also: RunPod's ubuntu 24.04 images are PEP 668 "externally managed", so
system-wide `pip install` fails outright. Install into a venv -- the
working pod used `/root/sglang-venv`.

## Daytona

Org limits start at roughly 10 vCPU. 12 concurrent sandboxes at 1 vCPU hit a
hard `"Total CPU limit exceeded. Maximum allowed: 10"` 400, losing work items
outright. Hence `SWARM_SIZE = 4` (8 agents), with real margin rather than
sitting exactly on the cap.

A sandbox this pool already deleted can still appear in `list()` briefly;
deleting it again races the teardown and returns 409 or 404. Neither is a leak.

Persisted snapshot registration (`client.snapshot.create`) can be 403'd on
unverified accounts while sandbox create/delete works fine — hence the ad-hoc
`image=` fallback, which Daytona caches server-side by content hash.
