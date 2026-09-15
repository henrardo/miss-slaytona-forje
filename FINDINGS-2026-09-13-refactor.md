# Why the swarm got nothing done, and what changed

Supersedes `HANDOFF-M4-agent-swarm.md`. That document's evidence was sound;
its conclusions were looking at symptoms one layer above the cause.

## The root cause: Vibe had been hand-patched, and the patch made the agent
## loop unable to terminate

The installed `mistral-vibe` package in `harness/.venv` was **not the
published release**. Verified against the wheel's own SHA-256 manifest
(`mistral_vibe-2.25.3.dist-info/RECORD`): two files differed.

1. **`vibe/core/llm/format.py`** — `APIToolFormatHandler.get_tool_choice()`
   had been edited from `return "auto"` to `return "required"`.
2. **`vibe/core/llm/backend/generic.py`** — a hand-added
   `_generate_mistral_compatible_id()` plus two call sites rewriting
   tool-call IDs on the request, duplicating what `harness/id_fix_proxy.py`
   already does on the response.

Both edits are documented in `notes/sglang-mistral-small-4-postmortem.md`
("Fixed (for Devstral) with a one-line patch to the installed package,
`"auto"` → `"required"`"). Neither was visible from the repo — they lived in
a gitignored `site-packages`, so every later session inherited them as if
they were Vibe's real behaviour, including the handoff doc, which reports
`tool_choice: "required"` as a fact about Vibe.

### Why that one line was fatal

Vibe's agent loop ends a turn in exactly one way — the model returns an
assistant message carrying **no tool calls**:

```
vibe/core/agent_loop/_loop.py:2483
    if not resolved.tool_calls and not resolved.failed_calls:
        return
```

SGLang enforces `tool_choice: "required"` with constrained decoding.
Confirmed directly against the pod, same model, same endpoint, for the
prompt *"Say hello. Do not use any tools."*:

| `tool_choice` | finish_reason | tool_calls | content |
|---|---|---|---|
| omitted | `stop` | `[]` | `Hello! How can I assist you today?` |
| `"auto"` | `stop` | `[]` | `Hello! How can I assist you today?` |
| `"required"` | `tool_calls` | `['bash']` | *(empty)* |

So under the patch the model was grammar-forced to call a tool on **every
single turn**, and the loop's only exit condition became unreachable. The
agent could not stop. Ever.

This is visible in the last run's own transcript
(`harness/run-warm-0/.vibe/logs/session/session_20260913_163108_8cca7422/`):
**576 assistant messages, 576 tool results, zero text-only turns.** 524 of
them `read_file`. It ran until the deadline killed it.

Every open issue in the handoff is downstream of this:

- *"`skill` tool exploration loop, 600+ identical calls"* — forced to emit a
  tool call with nothing useful left to do, the model reached for whatever
  was in the list. Reproduced directly: with the full 9-tool set under
  `required` it calls `skill{"name": "pydantic-migration"}` (a skill that
  doesn't exist); with a 5-tool set it calls `read_file` correctly.
- *"token counts climbing run over run, 35M → 60M → 90M"* — not the task
  getting harder; sessions that can never end, re-injecting context until
  the clock stops them.
- *"0/4, 0/4, twelve runs running"* — an agent that cannot finish a turn
  never hands control back for the test suite to run.

The handoff flagged the `tool_choice` fact and said it was "worth
investigating directly rather than assumed." It was the whole thing.

## The second cause: the model couldn't drive vanilla Vibe either

Reverting the patch is necessary but not sufficient. The patch existed
because `tool_choice: "auto"` genuinely didn't work — just not for the
reason assumed.

Qwen2.5-Coder-7B-Instruct, under plain `auto`, **will not call tools**. Not
a prompt problem: tested with the full 13,357-char Vibe system prompt, with
a short one, and with **no system prompt at all**; with 9 tools and with 5;
at temperature 0.2 and 0.7; on the migration task and on an unambiguous
"Read the file `fastapi_mail/config.py`". In every case it emitted the tool
call as *markdown text*:

```
```json
{ "name": "read_file", "arguments": { "file_path": "/repo/fastapi_mail/config.py" } }
```
```

The serving layer is fine — tools reach the prompt (30 → 1334 prompt tokens
when 5 tools are attached), and the model's chat template renders the
`<tool_call>` protocol correctly (verified by rendering it on the pod). The
model simply doesn't use it unless forced.

So the earlier session patched the harness to compensate for a model
limitation, and traded *"the model never starts"* for *"the model can never
stop"* — a strictly worse failure, because the first is visible and the
second looks like the agent is busy working.

**The fix is at the model layer, not the harness layer.** Any model used
here must emit tool calls under plain `auto`. Qwen3-8B does, and drove a
complete, clean session (below). Mistral Small 4 is the eventual target.

## Everything else that was fixed

**Local checkout was a fragment, not a repo.** Agents were seeded with only
`fastapi_mail/`. The pytest tracebacks fed back to them name
`/repo/tests/conftest.py` — a path that existed only inside Daytona. Hence
524 consecutive failed `read_file` calls on a file that could not exist.
Now `seed_repo()` lays down `fastapi_mail/` + `tests/` +
`requirements-v2.txt` + a `.gitignore`, and runs `git init` + one commit.
The git part is load-bearing: Vibe's entire project context is the absolute
path plus `git status`, so in a bare directory the model was told nothing
about what it was looking at. Additionally `_localize_sandbox_paths()`
rewrites `/repo/...` to the agent's own path before the error text goes into
the next prompt. Edits to `tests/` are never uploaded, so the oracle still
runs the pristine suite and can't be gamed.

**The OpenAI web-search MCP server is gone.** It was added on the theory
that the task wasn't solvable without live migration docs. It was never
called once by any of the 8 agents in the run it was added for; it pulled a
second vendor and a plaintext `OPENAI_API_KEY` into every agent's
`config.toml`; and giving both arms an external oracle for pydantic
v1→v2 patterns dilutes the one thing this demo measures. Vibe's own
`web_search` stays disabled — re-confirmed today that this repo's
`MISTRAL_API_KEY` returns `429 Rate limit exceeded` on a bare
`mistral-small-latest` chat completion, so the whole key is exhausted. It is
not, as previously recorded, a separate quota on the bundled feature.

**`run_pytest` now respects the shared deadline.** It was the one step
outside the budget, which is why a run asked for 1200s took 1730.8s.

**`__pycache__`/`*.pyc` no longer shipped to Daytona.** Stale bytecode
compiled against pre-migration source, uploaded on every attempt.

**Summary denominator.** "Stop for victory" cancels the rest of a swarm on
first success, and cancelled agents never append a result — so the summary
printed `1/1` where it meant `1 of 4`. Now uses `SWARM_SIZE`.

**`preflight()` added to `run.py`.** Checks, before spending the GPU
budget, the things that have each silently consumed a whole run: proxies
answering, proxy model matching `--model`, the snapshot not stale, and
`tool_choice_relaxed == 0` — a live tripwire that fires if Vibe is ever
re-patched.

**Blocking HF Hub calls were stalling the whole event loop — and
contaminating the comparison.** Found by running the rebuilt orchestrator:
all 8 agents emitted `ATTEMPT_START` and then nothing happened for minutes,
0% CPU, no Vibe subprocess ever spawned. `lsof` on the orchestrator showed
four hanging HTTPS connections to a Cloudflare endpoint — sentence-
transformers/`huggingface_hub` doing synchronous model-revision checks. A
synchronous network call inside an asyncio loop doesn't stall one coroutine,
it stalls all of them, so **four warm agents' memory setup froze all four
cold agents**, which never even started. That is worse than a hang: warm's
memory latency landing on cold's wall-clock is precisely the cross-arm
contamination this experiment cannot tolerate. Fixed by pinning the
embedding stack offline (`HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE`, in both
`orchestrator/memory.py` and `harness/memory_mcp_server.py` — the model is a
local, already-cached MiniLM), and by warming the embedder once in
`main_async()` before `RUN_START` so the 4.2s lazy load is paid outside the
measured window. Verified after: first load 4.2s, then four concurrent
`get_context()` calls in 0.1s.

**`fixture_hash()` was hashing `__pycache__`, so the snapshot reported
itself STALE at random.** `preflight()` caught this on its first real
outing. Any local import or pytest run rewrote a `.pyc` under `fixture/` and
invalidated the hash with nothing about the fixture actually changed — and
those same stale `.pyc` files, compiled against *pre*-migration source, were
being baked into the Daytona image. Junk is now excluded from both the hash
and the upload, `fixture/` has been cleaned, and the snapshot rebuilt.

**`spacy` + `en_core_web_sm` installed.** `neo4j-agent-memory`'s extraction
pipeline was logging `Stage 'SpacyEntityExtractor' failed` and skipping,
silently degrading the long-term half of the warm swarm's memory — the exact
capability being demonstrated. Now in `requirements-dev.txt`.

## Verified working

- **Oracle discriminates.** v1 source → exit 4 (`PydanticImportError:
  BaseSettings has been moved`). `fixture/reference_v2` → exit 0, **33
  passed**.
- **Memory round-trips.** Traces, confirmed patterns, and `get_context()`
  all read back from Neo4j.
- **A full Vibe session runs correctly.** Qwen3-8B, vanilla Vibe, real
  checkout: main session 12 messages with **1 text-only turn** (it
  terminated on its own), explore subagent 72 messages, **0 tool errors
  across both**, and a real, correct edit committed:

  ```diff
  -    class Config:
  -        arbitrary_types_allowed = True
  +    model_config = ConfigDict(
  +        arbitrary_types_allowed=True
  +    )
  ```

  which is exactly what `reference_v2` does. Compare to the previous state:
  576 forced turns, 524 failed reads, zero edits.

## First full run on the rebuilt pipeline

`runs/m4-1789322806.jsonl`, Qwen3-8B, 600s deadline, 4 warm + 4 cold.

```
WARM (shared memory):  0/4 agents converged |  75 LLM calls | 1,167,633 tokens
COLD (no memory):      0/4 agents converged | 115 LLM calls | 1,379,190 tokens
token_ratio (cold/warm): 1.181
wall-clock: 610.4s   GPU cost: $0.0831
```

**Nobody converged.** That is the honest headline. What changed is
everything underneath it:

| | before | after |
|---|---|---|
| attempts that completed | 0, ever | 9 across 8 agents |
| agents that landed an edit | 0 | **8 of 8** |
| tool error rate | 100% `read_file` | 29.5% overall |
| turns the agent chose to end | 0 | 12 |
| deadline overrun | +530s | +10s |

All 8 agents made the same correct first change —
`from pydantic import BaseSettings` → `from pydantic_settings import
BaseSettings` — and `config.py`'s only remaining difference from the answer
key is *import ordering*, i.e. it is functionally migrated. They then
iterated on the genuine next failure
(`@root_validator ... MUST specify skip_on_failure=True`). One of three
files, in ten minutes, on an 8B stand-in. The pipeline is no longer the
limiting factor; the model is.

The warm/cold token gap (1.18×) is **not** a result to quote. Neither arm
finished, the graph was not reset so warm was reading a dozen earlier runs,
and n=1.

### Two more bugs this run exposed

**`--disabled-tools web_search` silently does nothing.** 24 `web_search`
calls got through, all from the main session, every one returning
`429 web_search rate limit reached` — 32% of every tool error in the run.
Confirmed by capturing the real request body both ways: with the CLI flag
the tool is still in the `tools` array sent to the model; with
`disabled_tools` in `config.toml` it is gone. Moved to the config in
`render_config()` and verified end-to-end through the real code path.

**Memory context nested into itself.** `_replay_session_messages()` was
registering the constructed user prompt back into memory, so `get_context()`
retrieved its own previous output and attempt N's prompt embedded attempt
N-1's memory block, which embedded N-2's. The second attempt's prompt
already carried "What you remember" twice at 15,170 chars, on a 32k model.
User-role messages are now skipped in replay; the orchestrator separately
registers the canonical one-line task description, which is what belongs
there.

### The serious one: agents were not contained

This invalidates the run above, and is worth stating plainly.

Agent checkouts lived at `harness/run-{swarm}-{i}/` — inside the same tree
as `fixture/` (the pristine v1 source), `fixture/reference_v2/` (**the answer
key**) and all seven sibling agents, with Vibe running
`--trust --auto-approve` over it. The 2026-09-13 run did all three of the
things that layout permits:

- **Four warm agents edited `fixture/fastapi_mail/config.py`** — the source
  every future run seeds from. They edited it *wrongly*, writing
  `from pydantic_settings import BaseSettings` and dropping the
  `as Settings` alias that `class ConnectionConfig(Settings)` depends on, so
  the fixture was left in a state that would `NameError` on import.
- **warm-0, warm-1 and warm-3 each wrote into `harness/run-cold-1/`** — warm
  agents editing a *cold* agent's codebase. On its own that voids the
  warm/cold comparison for that run.
- **One agent ran `grep` against `fixture/reference_v2/`**, the answer key.
  (Only a grep, and no tool call ever opened the file — but the layout made
  it reachable, which is the point.)

None of this was adversarial. Agents were handed absolute paths in the
fed-back pytest output, walked up from them, and found a tree full of
pydantic-v1 code that looked like more of their own task.

**Fixed two ways.** `AGENT_ROOT` now places each checkout outside this
repository (`$TMPDIR/miss-slaytona-forje-agents/{swarm}-{i}`, overridable via
`M4_AGENT_ROOT`), so the fixture, the answer key and this project's source
are not reachable at all — verified: the agent's tree holds only its own
checkout, and `reference_v2` has zero copies under the agent root. Siblings
still share a parent, so this is containment by construction rather than a
sandbox; `check_containment()` is the backstop, scanning every agent's own
transcript after the run for `edit`/`write_file` outside its own tree and
re-checking the fixture hash. Replayed against the bad run it correctly
reports all 11 violations. A run that crosses arms now says so loudly
instead of printing a clean-looking summary.

The fixture has been restored and verified byte-identical to a pristine v1
seed commit, and the snapshot rebuilt.

### Remaining error budget (74 of 251 tool calls)

After the `web_search` fix removes 24, the rest are model behaviour, not
harness faults: `grep` passing a comma-joined list as one path (22), `edit`
failing "string not found" because the file was already migrated on a prior
attempt (18), `read_file` dropping the `fastapi_mail/` prefix (7).

## Validation run: isolation confirmed

`runs/m4-1789323969.jsonl`, Qwen3-8B, 300s, `--reset-memory`, agents in
isolated roots. 16,109 nodes deleted, graph empty at start.

```
WARM (shared memory):  0/4 converged | 73 LLM calls | 516,917 tokens
COLD (no memory):      0/4 converged | 61 LLM calls | 468,554 tokens
token_ratio (cold/warm): 0.906      wall-clock: 307.9s (300s budget)
```

Containment, checked four independent ways:

- `check_containment()` → **0 real findings**. Two were the model mistyping
  its own path (`gyfmlw00000gp`, five zeros, vs the real four); that root
  does not exist, so those writes failed and did nothing.
- fixture hash → unchanged.
- transcripts mentioning `fixture/` or `reference_v2/` → **0**.
- cross-agent tool calls → **NONE**.

`web_search` calls: **0** (was 24). Retry prompts contain "What you
remember" exactly once at ~7.8k chars (was twice at 15.2k and doubling).
Attempt turnaround is much faster — warm-2 completed four attempts in 224s,
where the previous run's *first* attempts took 280s+.

Two caveats on the check itself, both fixed after this run: it compared only
the `resolve()`d path (so on macOS, where `$TMPDIR` is `/var/...` symlinked
to `/private/var/...`, an agent writing to its own checkout via the other
spelling was falsely flagged), and it counted writes to Vibe's own
per-session scratchpad, which the system prompt explicitly tells agents to
use. Both now handled; the numbers above are from the corrected check.

### The memory arm cannot win a run nobody finishes

`token_ratio` came out at **0.906 — warm used *more* than cold.** With the
graph reset, that is the expected and honest result, and it points at a real
design issue for the demo:

`record_pattern` is gated on ground truth — a proposed pattern only becomes a
shared `Entity` after the orchestrator's own pytest check passes for that
exact attempt. Nothing passed, so nothing was ever shared. Warm therefore
paid the cost of carrying a memory block in every prompt and received
nothing back. **In a time-boxed run where no agent converges, the warm swarm
can only look worse.**

That gate is correct — it exists because agents previously recorded
"patterns" from attempts that went on to fail. But it means the demo needs
either a model that actually converges inside the budget, or a run that
starts from an already-populated graph (`--reset-memory` omitted), which is
a different and equally honest claim. The flag exists so that choice is made
deliberately; the summary always prints the starting graph contents.

## Does waiting longer produce convergence? No.

Tested directly: `runs/m4-1789324602.jsonl`, 45 minutes (2700s), Qwen3-8B.
**0/4 warm, 0/4 cold.** 8.8M tokens, $0.37. Progress trace sampled every two
minutes is in `runs/convergence-trace-m4-1789324602.txt`:

```
t=  42s   warm-2:1, everyone else 0
t= 403s   most agents at 1-2 of 3 files
t= 763s   six of eight at 2 files      <-- plateau
t=1124s   unchanged
t=1485s   unchanged
t=1845s   unchanged
t=2206s   unchanged
t=2567s   cold-3 reaches 3, warm-0 reaches 1
```

Agents reach 2 of 3 files in about 13 minutes and then stop. The extra half
hour bought one additional file being touched. **The 10-minute demo budget is
not the binding constraint** — they plateau at roughly that point regardless.

### Why they plateau

`cold-3` was the only agent to edit `email_check.py`, and it wrote:

```diff
-        EmailStr.validate(email)
+        return EmailStr(email).validate()
```

The answer key requires a *different package*:

```python
from email_validator import EmailNotValidError, validate_email
emailinfo = validate_email(email, check_deliverability=False)
email = emailinfo.normalized
```

The model invented a plausible-looking pydantic-v2 API rather than knowing
`email_validator` exists. Retrying cannot fix this: the traceback says
`EmailStr has no attribute validate`, which does not tell you to reach for a
different library. `schemas.py` also drifts rather than converges — warm-2
finished *further* from the answer key (23 differing lines) than the
unmigrated fixture (17).

### Consequences for the demo design

Two structural problems, independent of model choice:

1. **This fixture contains a step shared memory cannot bootstrap.**
   `record_pattern` promotes a pattern only after a full green suite, and the
   suite cannot go green until the `email_validator` substitution is made.
   So the one piece of knowledge memory would be most valuable for is the
   one piece it can never acquire. Circular.
2. **Warm structurally loses any run nobody finishes**, because it carries a
   memory block in every prompt and gets nothing back.

Options, none of which were applied here because they change what the demo
*claims* and that is the owner's call: test Mistral Small 4 before assuming
the fixture is at fault; trim the fixture to the two files that are pure
v1→v2 renames (`config.py`, `schemas.py`), which memory can genuinely
propagate; or loosen the promotion gate to reward an attempt whose traceback
advanced rather than only a fully green suite.

Containment held on this run: the two flagged paths
(`/Users/.../Projects/fastapi-mail`, `gyfmlw00000gp`) do not exist — the
model hallucinated them. Fixture intact, no cross-agent writes.

## The task, for scale

The whole migration is **36 changed lines across 3 files** — `config.py`
(4), `schemas.py` (17), `email_utils/email_check.py` (21). `BaseSettings`
moves to `pydantic-settings`; `@validator`/`@root_validator` become
`@field_validator`/`@model_validator(mode="after")` with attribute access
instead of dict access; `class Config` becomes `model_config =
ConfigDict(...)`; `EmailStr.validate()` is replaced by `email_validator`.
Well within a 10-minute budget for a capable model.
