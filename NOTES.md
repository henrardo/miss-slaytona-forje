# Mission log — warm-arm AIP skill distillation

Running log for the distillation-loop mission. Updated after every change and
every run. Newest section last.

---

## 2026-09-17 — session start, state of the world

### Budget

| | |
|---|---|
| RunPod **balance** | **NOT READABLE.** The API exposes billing history, not balance, and no balance tool exists in the available surface. |
| spend 14 Sept | $17.87 |
| spend 15 Sept | $12.09 |
| spend 16 Sept | $21.75 |
| 3-day total | $51.72 |
| current burn | **$0/hr — no pod running** |

**Assumption, recorded because it changes the experiment:** since the balance
cannot be read, the budget floor is enforced as a *spend cap* instead. Total
additional spend for this mission is capped at ~$25 (≈5.5 H200-hours at
$4.59); stop starting runs at $20 spent; reserve the remainder for wrap-up.
Replace this with the real balance when available.

### Pods

One pod at a time, per instruction.

| pod | GPU | state |
|---|---|---|
| `ol4lcn14lp2om3` | B200 | **terminated** after archiving |
| `79s4ud0jutluin` | A40 | **terminated** after archiving |
| `pb4q90qlukwfxr` | H200 | terminated earlier at user request |
| `f1czcx72t1c06m` | H200 | **vanished** — 404 within ~1h of creation, not terminated by me. Secure Cloud, `Low` stock; presumed reclaimed. Model download had not finished. |

Archives, both MD5-verified on the pod and again locally before termination:

- `pod-artifacts/b200-run12/b200-artifacts.tgz` — `8258b039…`, 419 entries,
  3 transcripts, runs 12/13 sglang + sidecar + MCP + web logs, both repos.
- `pod-artifacts/a40-qwen/a40-artifacts.tgz` — `6fe25ad8…`, 353 entries,
  Qwen sglang log, sidecar, both agents' `.vibe` and repos.

**Lesson applied:** the H200 burned ~$4.59/hr while I did inventory and
reporting. All remaining non-run work is off-GPU, so it is being done first;
a pod is provisioned only when there is something to run.

---

## Prerequisite 8 — did Qwen3-14B get a fair test?

**No. Qwen had 4 runs with a writable checkout, and its best legitimate score
was 4 of 33.**

`fixture/` is `chmod a-w` on disk to protect the ground truth, and
`repo_tarball` preserves modes, so early runs handed every agent a read-only
checkout. The agents could not edit source at all. `seed()` gained the
`chmod -R u+w` fix mid-session (working tree, before run 7).

Evidence — `edit`+`write_file` calls across all graded attempts per run:

| run log | time | graded | edit+write | note |
|---|---|---|---|---|
| swarm-1789568701 | 15:25 | 0 | **0** | read-only |
| swarm-1789569268 | 15:35 | 0 | **0** | read-only |
| swarm-1789569369 | 15:49 | 3 | **0** | read-only |
| swarm-1789570268 | 16:04 | 2 | **0** | read-only |
| swarm-1789571249 | 16:26 | 8 | **0** | read-only |
| swarm-1789572475 | 16:28 | 0 | **0** | read-only |
| swarm-1789572836 | 16:34 | 0 | **0** | read-only |
| swarm-1789573441 | 17:08 | 9 | 12 | first writable run |
| swarm-1789575475 | 17:43 | 0 | 0 | writable; crashed on `ATTEMPT_FAILED` |
| swarm-1789581031 | 19:12 | 2 | 17 | writable |
| swarm-1789582838 | 19:43 | 4 | 13 | writable |
| swarm-1789584361 | 20:08 | 2 | 14 | writable |
| swarm-1789590770 | 21:56 | 19 | 48 | **Mistral Small 4**, B200 |
| swarm-1789595893 | 23:05 | 3 | 41 | **Mistral Small 4**, H200 |

Zero edits across 13 graded attempts in the first seven runs is not a model
result; it is a harness fault.

**Qwen's fair sample:** 4 runs, 17 graded attempts. Best was 31/33 on run
17:08 — **rejected** by the gutted-validator gate (it deleted behaviour in
`email_check.py`). Best legitimate: **4/33**.

Qwen also never ran on a harness where memory worked: the step hook was dead
until run 13, and `thought` held tool-argument JSON throughout. Any claim
about Qwen and memory from these runs is unsupported. **Not rerunning Qwen**,
per instruction — reporting only.

---

## Prerequisites 1 and 2 — done, committed

- `9df8fe1` — real reasoning in `thought` via `harness/reasoning_relay.py`,
  plus the hook write-queue split. Test fails if `thought` is the serialised
  tool input.
- `ca68992` — `success` means the full suite passed; `advanced` and
  `tests_passed` stored separately; `outcome_schema=2`; `_render` shows
  `tests_passed`. All 10 existing traces stamped `outcome_schema=1`; 2 of
  them had `success=true` with `tests_passed<33`.
- `350c8e7` — concurrency fix and blocking-loop guard (pre-existing work,
  committed now).

### Graph state after prerequisite 2

187 steps across 10 traces. **4 steps (2%) have real reasoning**; the other
183 hold tool-argument JSON. **One trace is a genuine full-suite success and
it contains a single step.** The existing graph is therefore not usable as
distillation input — the distiller needs data from runs made after `9df8fe1`.

---

## AIP

Source: `~/Documents/GitHub/workshop-agent-memory-90/.claude/skills/aip/`.
A complete package with a real validator, so nothing is reconstructed from
the paper.

- `scripts/validate.py` — end-to-end: frontmatter (`name`, `description`,
  `metadata.aip.spec`, `metadata.aip.schemaId`), required `source/` with a
  bundled `*.schema.json`, `$id` match, AIP-compliance checks, then the body's
  fenced YAML validated against the schema. Exit 0/1, JSON Lines diagnostics
  on stderr — directly usable for the repair loop.
- `assets/aip-schemas/procedure.schema.json` — required `purpose`,
  `trigger_when`, `steps`; steps require `name` and `description`, optional
  `depends_on`, `parallel`, `one_of`, `script`, `inputs`, `outputs`.

Paper for background: arXiv:2606.04781v2, Blumenfeld & Webber.

**Assumption to record:** using the workshop package's validator verbatim
rather than writing one from the paper, so the skill format matches what the
team already uses.

---

## Outstanding (not started)

Prerequisites 3–7, and the mission proper:

3. Stamp traces/skills with model, GPU, harness commit, writable-checkout.
4. Eligible-trace filter + count.
5. Separate attempt vs distillation metrics.
6. Stop-for-victory off.
7. AIP validator integration + ~2,000-token skill cap.
- Disable per-step injection and warm's memory MCP tools during attempts.
- Skill load at attempt start; ingestion + distillation after each attempt.
- Skill versioning, graph provenance, repair loop.

---

## 2026-09-17 — prerequisites 3, 4, 6, 7 done (off-GPU, no pod running)

| commit | what |
|---|---|
| `05de965` | provenance stamping (3), eligible-trace filter (4), stop-for-victory switch (6) |
| `3d5b720` | AIP skill v0 scaffold + vendored workshop validator (7) |
| `5cb66e6` | versioned skill manager: validate, size cap, graph provenance (7) |

141 tests pass.

### Prereq 4 result — ZERO eligible traces

```
total 10 | has_provenance 0 | right_model 0 | writable 0 | schema2 0
eligible 0 | eligible_with_reasoning 0
```

Every existing trace fails all three filters. **Consequence for the design:**
the distiller has nothing to learn from on the first run, so skill v0 must be
an empty scaffold. It is — `test_v0_carries_no_migration_answer` fails if the
scaffold ever contains `pydantic_settings`, `field_validator`,
`email_validator` and similar. The first eligible trace will be produced by
the first warm attempt on this harness.

### AIP validator — two rules learned by running it

Assumptions recorded per prereq 7, using the workshop package's validator
verbatim rather than writing one from the paper:

1. `metadata.aip.spec` must be a **URL** (must contain a scheme). A bare
   `"0.3a3"` is rejected. Set to the paper URL.
2. The body must be **exactly one fenced YAML block with no surrounding
   prose**, so all rationale lives in YAML comments inside the block.
3. The validator requires `name` to equal the containing **folder name**, so
   candidates are staged in a temp dir named after the skill. Staging as
   `.staging-x` fails for the wrong reason and masks real errors.

Size cap: 2,000 approx tokens (4 chars/token), rejection reason `too_large`.

### Still outstanding

- Ingestion of the attempt transcript after the clock (real reasoning +
  honest verdict), replacing per-tool-call writes.
- The distillation turn itself: query eligible traces, read current skill,
  write improved version, up to 2 repair turns on validator failure.
- Skill load into Vibe at warm attempt start + hash logged at load.
- Disable per-step injection and warm's memory MCP read tools during attempts.
- Prereq 5: separate attempt vs distillation metrics.
- Then: provision one H200 and start the iteration loop.

### Next

Distiller + ingestion, then skill loading, then the first run.

---

## 2026-09-17 (later) — transcript review, budget reset, skill loading solved

### Budget, re-read from the API

| | |
|---|---|
| balance | **$50 loaded by the operator today.** Still not readable through the API; treated as a $50 cap. |
| spend 13 Sept | $18.12 |
| spend 14 Sept | $17.87 |
| spend 15 Sept | $12.09 |
| spend 16 Sept | $38.77 |
| spend 17 Sept (to now) | $27.02 |
| H200 SXM | $4.59/hr secure, $3.59/hr community, availability MEDIUM |
| pods running | **none — `list-pods` returns `[]`, $0/hr** |

Using **secure** H200 at $4.59: the provisioning script is tuned for it, and
the one pod that vanished mid-download was a Low-stock secure instance — a
community pod that loses a 113 GB model download costs more than the $1/hr it
saves. Recorded here per the "record any change" rule; no change made.

Floor: stop starting runs below **$12** remaining (one ~1.5h run plus 30 min
of wrap-up).

### How Vibe loads a skill — verified locally, no pod

The riskiest unknown in the mission, settled at $0 by installing
`mistral-vibe==2.25.4` into a throwaway py3.13 venv and driving its own
`SkillManager`:

- Vibe discovers **`$VIBE_HOME/skills/<name>/SKILL.md`** (`GLOBAL_SKILLS_DIR`
  in `core/config/harness_files/_paths.py`). The harness already gives every
  agent its own `VIBE_HOME`, so warm gets the skill and cold cannot see one.
- **Our AIP `SKILL.md` parses unmodified.** Vibe's `SkillMetadata.metadata` is
  `dict[str, str]` with a `str(v)` coercion, so the nested `metadata.aip`
  block survives rather than erroring. Discovery reported no config issues.
- **`/pydantic-v2-migration <task text>` as the first user message makes Vibe
  itself load the skill**: `parse_skill_command` returned the full 1,684-char
  body with the task as `extra_instructions`, and `_inject_invoked_skill`
  appends a real `skill` tool call + result to the message list before the
  model's first turn (`core/agent_loop/_loop.py:2307`). Deterministic loading
  through Vibe's own surface — no patch, and no reliance on the model choosing
  to call the `skill` tool.

Two constraints this imposes on the distiller, to enforce in `propose()`:
`name` must match `^[a-z0-9]+(-[a-z0-9]+)*$`, and `description` is capped at
**1024 characters** by Vibe (v0 is 301). A skill the AIP validator accepts but
Vibe rejects would load nothing and look like a model that ignored it.

Also noted: Vibe's skill search path includes `~/.agents/skills`. Harmless on
the pod, where each agent has its own 0700 home, but it is the same
operator's-home reach recorded earlier for the `skill` tool.

### Skill loading, built and verified against the real Vibe

**154 tests pass** (was 141). Not committed — the operator has asked that this
tree stay uncommitted from here on.

| where | what |
|---|---|
| `orchestrator/skills.py` | `body_of()` + `SkillVersion.body_sha` — Vibe loads the markdown body, so the frontmatter cannot be part of "which version ran" |
| `swarm/agent_workspace.py` | `install_skill()` (writes `$VIBE_HOME/skills/<name>/SKILL.md`, wipes the old version, **reads the file back** and fails if the bytes differ), `loaded_skill_text()`, `has_skills_dir()` |
| `orchestrator/vibe_agent.py` | `_task_prompt(skill_command=...)` prefixes `/<name> `; `migrate_codebase(skill_name=...)` |
| `swarm/run.py` | installs the skill for warm before the clock, hash-checks it, refuses to start if a **cold** agent has a skills directory, and reports after the clock whether the skill reached each warm model |
| `tests/test_skill_loading.py` | 10 tests, no pod needed |

**Verified end to end against mistral-vibe 2.25.4 itself**, not against my
reading of it. The harness's real 3,200-character warm prompt was fed to
Vibe's own `SkillManager.parse_skill_command`:

```
PARSED: pydantic-v2-migration
task survived: True          # "migrate this codebase" intact
pytest error survived: True  # the fed-back traceback intact
extra chars: 3177 of 3200    # everything after the prefix passes through
marker present: True         # Vibe's render_skill_result emits <skill_content>
cold parses as skill: False  # same prompt without the prefix: not an invocation
harness body inside what Vibe rendered: True
```

So the load is deterministic and it is Vibe's own mechanism, not a patch: a
prompt beginning `/<skill-name>` makes Vibe append a real `skill` tool call
and result before the model's first turn. The alternative — leaving the model
to call the `skill` tool when it judges the skill relevant — is the same bet
this project already lost with the memory tools (0 calls across 15 sessions
while the prompt told it to use them).

**A constraint this creates, recorded before it bites.** Vibe answers a
second load of the same skill in one conversation with "already loaded
earlier in this conversation. Reuse those instructions"
(`_skill_already_loaded`). Warm resumes its session between attempts, so
after distillation writes a new version the resumed agent would keep working
from the superseded text while the run recorded the new number. **The attempt
after a skill change must start a fresh session.** Noted at the `resume =`
line in `migrate_codebase`; the distillation step has to honour it.

### One thing dropped after checking

I added a Vibe-compatibility gate to `propose()` (name pattern, 1024-char
description) and then removed it: the AIP validator already enforces exactly
those limits, because both implement the same Agent Skills frontmatter rules.
A test now pins the equivalence instead, so the claim stays true if either
side drifts. `VIBE_NAME_RE` / `VIBE_MAX_DESCRIPTION` survive as the record of
Vibe's side.

### Design consequence for the remaining work

`AgentWorkspace.run_vibe` returns Vibe's whole streamed stdout, and
`stream_entries()` already parses it — so **post-attempt ingestion can read
the attempt's complete stream, reasoning included**, with no transcript
slicing and no per-tool-call graph write. That is what makes the mission's
"graph writes happen at ingestion" cheap rather than awkward, and it means
warm's attempts can drop the `post_tool` hook, the sidecar write path and the
reasoning relay entirely: they exist only because the hook fires before Vibe
flushes `messages.jsonl`, which is not a problem once the writing happens
after the attempt ends.

---

## 2026-09-17 — design decision: no session is ever resumed

**Both arms start a fresh Vibe session on every attempt.** `resume` in
`migrate_codebase` is now the constant `False`; it was
`attempt > 1 and last_ended_cleanly`.

**Why.** Vibe refuses to reload a skill into a conversation that already
contains it — `_skill_already_loaded` matches the `<skill_content>` marker
and the tool returns *"already loaded earlier in this conversation. Reuse
those instructions."* That is correct for an unchanged skill and wrong the
moment distillation writes a new version: a resumed warm agent would keep
working from the superseded text while the run recorded the new number.

Fixing that for warm alone would have been worse than the bug. Warm would
restart each attempt while cold carried its conversation forward, so the arms
would differ in **two** ways — the skill, and whether the agent remembers its
last attempt — and any difference in results could be attributed to either.
The skill is meant to be the only thing warm carries between attempts.

**What it costs.** Neither arm accumulates conversation across attempts. Both
begin each attempt from the task plus the previous attempt's verdict; warm
additionally from a procedure it wrote itself. That is the comparison the
experiment is actually for — whether a distilled skill carries more than a
transcript would. It also removes a confound that was never controlled:
whether a session resumed depended on `_ended_cleanly`, which depends on how
the *previous* attempt happened to stop, so the arms' resume rates were a
function of server load.

`last_ended_cleanly` is still computed and is now reported on `ATTEMPT_DONE`.
It was only ever visible through the resume decision, and "did the agent stop
on its own terms or get cut off" is worth keeping.

Pinned by `test_no_attempt_ever_resumes`, which reads the source and fails on
any assignment to `resume` other than `False`.

---

## 2026-09-17 — skills are directories, and the arms must match

**159 tests pass.** Tree uncommitted, on the local machine.

### The whole skill package travels, and is verified as the agent

`install_skill` now takes the whole directory, not `SKILL.md`. An AIP skill
carries `source/` (the schema its own `schemaId` resolves against) and may
carry `scripts/`, `references/` and `assets/`; a procedure whose steps have
`script:` entries is useless if the scripts did not travel, and the failure is
quiet — the model reads a step it cannot perform and improvises.

- `skills.package()` collects the tree, excluding `__pycache__`/`.pyc`/
  `.DS_Store` so the version hash does not change when the skill has not.
- `skills.dir_sha()` hashes `path -> sha(content)` pairs, so a file renamed to
  another's content does not collide and the value is order-independent.
- `SkillVersion.dir_sha` identifies the version; `body_sha` stays the only
  thing a transcript can be checked against, because the frontmatter never
  reaches the model.
- Everything under `scripts/` is installed mode 0700, the rest 0600 — the
  agent's own files, unreadable by any other agent on the host.
- **Verification runs as the agent user, not root.** `find -exec sha256sum`
  plus `test -x` per script: the claim that matters is "the agent can read
  this and execute that", not "root wrote these bytes". Missing, unexpected
  and differing files are each named in the error.

Current package: `SKILL.md` + `source/procedure.schema.json`, `dir_sha`
`e77db7780125`, `body_sha` `ce1e5133fcda`.

### Arm parity is asserted from the machine, before the clock

`assert_arms_match` compares warm's and cold's actual setup — hook files
present, MCP server names, `disabled_tools`, and the tool list Vibe really
loaded — and refuses to start on any difference outside a named list. Both
arms now make a cheap probe call first, because `loaded_tools` reads the
newest session's `meta.json` and cold never had one, so the tool lists could
not be compared at all. That is exactly how warm-only `web` survived two runs.

`KNOWN_ARM_DIFFERENCES` currently holds three entries — `hook_files`,
`config_names`, `tools` — all caused by warm writing to the graph *during*
attempts through the `post_tool` hook and the reasoning relay. They are
printed on every run as a confound. The list is deleted, not shortened, when
ingestion moves those writes after the attempt.

### Pod: none running, and none until the remaining work is done

`list-pods` returns `[]`; burn is **$0/hr**. Nothing to stop.

Estimate to the next run: **3–4 hours**, so a pod would be idle for all of it.

| remaining | estimate |
|---|---|
| ingestion from `stream_entries` + tests | 45–75 min |
| remove warm's hook/relay/MCP; `KNOWN_ARM_DIFFERENCES` to empty | ~30 min |
| distillation turn (own `VIBE_HOME`, memory MCP, third counting proxy, repair loop) + tests | 60–90 min |
| prereq 5 metrics | ~30 min |
| provision + 113 GB model download | 40–60 min |

**Risk of not holding a pod:** H200 availability is MEDIUM overall but LOW in
every individual data centre, and one secure H200 already vanished mid-download
on 16 Sept. If none is free when the code is ready, the options are to wait,
or to take a community H200 at $3.59/hr. Holding one now would cost ~$16 to
avoid that, which is a third of the remaining balance.

### Next

Ingestion from `stream_entries`, then the hook/relay removal with
`KNOWN_ARM_DIFFERENCES` going to empty, then the distillation turn, then
prereq 5's metrics, then the local rehearsal, then provision one H200.

---

## 2026-09-17 — second H200 lost overnight; pod loss is now a planning input

**A second H200 died before running a single test.** Hourly billing is
unambiguous: a pod at $4.63/hr all-in was billed continuously from
**23:00 UTC 16 Sept to 05:50 UTC 17 Sept**, then nothing. Roughly 7 hours and
**$31.60**, for no data.

That is two H200s lost in two days, neither terminated by me:

| pod | GPU | fate |
|---|---|---|
| `f1czcx72t1c06m` | H200 secure | 404 within ~1h of creation, Low stock, model download unfinished |
| (overnight, 16→17 Sept) | H200 | ran ~7h, stopped ~05:50 UTC, no tests run |

**Treated as a planning input from here, not an accident.** Every hour a pod
is held without running a measured attempt is an hour that may be lost
outright. The rules that follow from it:

- No pod is provisioned until the code it will run has passed the local
  rehearsal (below). GPU time goes on runs, not on plumbing.
- Runs are executed back to back inside one pod session, because each
  provision costs ~1 hour and ~$4.60. Restarting is the expensive event.
- Artefacts are copied off and verified **after every run**, not at the end.
  Everything lost overnight was lost because nothing had been produced yet;
  next time there will be runs worth keeping.
- A pod is never left up while I am doing something that is not a run.
- If a pod disappears: record what was lost, re-read the balance, and report
  before provisioning a replacement.

### 1. B200 and A40 archives — verified present locally, today

Re-checked rather than trusted. MD5s match what was recorded before the pods
were terminated, and the contents match the manifest:

| archive | MD5 | entries | transcripts |
|---|---|---|---|
| `pod-artifacts/b200-run12/b200-artifacts.tgz` | `8258b03977f0d11ea0eb6b47bb354a0e` | 419 | 3 |
| `pod-artifacts/a40-qwen/a40-artifacts.tgz` | `6fe25ad80dd7d798ee34526f5c16e2e0` | 353 | 4 |

Both contain `root/sglang.log`, the sidecar and MCP logs, and the agents'
`.vibe` trees. Nothing from those two pods is lost.

### 2. Balance and budget

**The exact balance is not readable.** There is no balance endpoint in the
RunPod MCP surface — checked again today; it exposes billing *history* only
(`list-billing`), plus pods, endpoints, templates and volumes. The figure has
to come from the dashboard.

Measured instead:

| | |
|---|---|
| spend 17 Sept (UTC, to 11:00) | **$27.02**, all of it the pod that died |
| spend 16 Sept | $38.77 |
| last billed hour | 05:00–06:00 UTC 17 Sept, $3.86 (partial) |
| burn now | **$0/hr, no pods** |
| H200 SXM | $4.59/hr secure, $3.59/hr community, +~$0.04/hr disk |

Planning on **$50**, the top-up, since the overnight burn preceded it.

**Cost model**, from measured times in this project:

| item | wall-clock | cost @ $4.63/hr |
|---|---|---|
| provision + 113 GB weights + sglang up | 45–75 min | $3.50–5.80 |
| 4-request control test | 5 min | $0.39 |
| one run: setup ~5 min, 600s attempts, ingestion + distillation off the clock | 20–25 min | $1.55–1.93 |
| wrap-up: copy off, verify, terminate | 30 min | $2.30 |

**Does the programme fit?** Yes, with room.

| plan | runs | pod time | cost |
|---|---|---|---|
| 3 clean consecutive runs only | 3 | 1h + 1.25h + 0.5h | **$12.90** |
| realistic: 4 debug/fix runs first | 7 | 1h + 2.9h + 0.5h | **$20.40** |
| pessimistic: 10 runs, two provisions | 10 | 2h + 4.2h + 0.5h | **$30.90** |

Against $50 that is **$29.60 of margin** on the realistic plan — about 6.4
further H200-hours, or one complete re-provision plus five more runs. The
constraint is not money, it is pod availability.

Floor stays at **$12 remaining**: one more run plus 30 minutes of wrap-up.

### 4. Which runs count

A run counts toward "clearly working" only if **`KNOWN_ARM_DIFFERENCES` is
empty** for it. While that list has entries, warm and cold differ in hooks,
MCP servers and tool lists, so the run can diagnose the machinery but cannot
be one of the three. The run banner prints the list either way, so a debug
run is never mistaken for a clean one after the fact.

### 5. Both arms get the same feedback — now enforced through the call path

This was **not** true when checked. `migrate_codebase` called
`_task_prompt(..., memory_enabled=mem is not None)`, which gave warm three
extra numbered steps and a closing note about memory tools. The existing
parity test missed it because it passed the same `memory_enabled` to both
sides; the asymmetry lived at the call site, not in the function.

Fixed by extracting `attempt_prompt(last_error, skill_name)` — what
`migrate_codebase` now calls, and what the test now exercises. It passes
`memory_enabled=False` for both arms always: in this design warm has no
memory tools during an attempt, so instructions for them would be tokens
spent on a capability it does not have, warm-only.

Verified across four feedback shapes (none, an import error, a mixed
pass/fail summary, and a 20,000-character output that gets trimmed):

    attempt_prompt(feedback, SKILL) == "/pydantic-v2-migration " +
    attempt_prompt(feedback, None)

The grader's pytest output reaches both arms in the same place and format,
under the same `The test suite still fails:` heading. Since neither arm
resumes a session, that verdict is the *only* thing either carries from its
last attempt — and warm additionally carries the skill. A second test asserts
neither prompt mentions memory tools.

**160 tests pass.**

---

## 2026-09-17 — steps 1 and 2 done: ingestion in, hook/relay/MCP out

**171 tests pass.** Tree uncommitted, local.

### The fake model server came first, and it paid for itself immediately

`tests/fake_model_server.py` is a scripted OpenAI-compatible server: a list
of turns, each with reasoning, text and tool calls, served over SSE exactly
as SGLang would. It was built ahead of schedule (it is item 5's
prerequisite) because ingestion needed the **real** shape of Vibe's
`--output streaming` output, and guessing formats has already cost this
project twice (`tools` vs `tools_available`; `turn_id` vs `turnId`).

So: real `mistral-vibe` 2.25.4, real skill directory, fake model. It ran
clean — exit 0, 3 model calls — and the captured stream is now
`tests/data-vibe-stream.jsonl`, the fixture every ingestion test runs on.

That run also proved the skill path end to end on a real binary: the stream
contains an `effect` entry titled `skill` whose output holds
`<skill_content name="pydantic-v2-migration">` and the full v0 body.

**Ground truth, per turn, in this order:**

```
{"type":"reasoning","turnId":…,"text":"the model's thought"}
{"type":"message",  "turnId":…,"role":"assistant","content":[{"type":"text",…}]}
{"type":"effect",   "turnId":…,"id":"<tool_call_id>","title":"bash",
                    "detail":{"toolName":"bash","input":{…}},
                    "state":{"status":…,"outputText":…,"error":{"message":…}}}
```

One correction to an assumption I had made: **`turnId` does not identify a
model turn.** All nine entries of the captured session shared one — it
identifies the *user's* turn. Ingestion therefore groups on the model's own
reason → speak → act cadence, closing a step at each tool call, rather than
on turn id. A design keyed on `turnId` would have written one giant step
per attempt.

### 1. Ingestion (`orchestrator/ingest.py`)

`thought` = the reasoning entry plus the assistant text; `action` = tool and
arguments; `observation` = output or the error. Runs after `complete_trace`,
so steps attach to a trace whose verdict is already honest, and a
half-finished ingestion still leaves the right outcome.

- A turn with **no** tool call is still a step — that is where "the
  migration is complete" lives, the claim the grader then contradicts.
- Failed tool calls are written with `ToolCallStatus.ERROR`, not skipped. An
  attempt that spent six turns fighting `edit` is what a later distillation
  should find; recording only successes makes the graph a highlight reel.
- The skill-load effect is extracted, never written as a step.
- Observations capped head-and-tail at 2,000 chars: the head holds the first
  failure, the tail holds pytest's summary line.
- A graph write that fails is logged and skipped. This runs *after* grading;
  raising would throw away a verdict to save a step.

Verified on the real stream: 3 steps, **3 with genuine reasoning**, 2 tool
calls, 1 failure recorded as one. The old remote path stored
`'{"pattern": "pydantic", "path": "/home/agent-warm-0/repo"}'` in `thought`
for every step.

**Off the clock, for real.** `migrate_codebase` accumulates `off_clock` and
adds it back to the deadline, so both arms get the same *attempt* time even
though warm does more work per round. Cold has no `mem`, so it accumulates
none — the asymmetry is exactly one variable and it is visible. Without
this, "off the clock" would be a figure of speech: a shared wall-clock
deadline charges warm's bookkeeping to warm's own thinking time.

`test_verdict_timeout_is_the_reserve_as_a_floor_not_a_ceiling` pins the
grading timeout by exact source string, so it had to be updated for
`deadline + off_clock`. The property it guards is unchanged and **both
negative assertions were kept**, plus two more (neither a bare clock nor a
bare reserve, in either form).

### 2. KNOWN_ARM_DIFFERENCES is now empty

Warm no longer gets `enable_memory` for its attempts. Gone from the attempt
path: the neo4j-agent-memory MCP server (~16 tools), both `hooks.toml`
files, the ~3.3s-per-tool-call hook latency, and the reasoning relay (which
drops out automatically — it is gated on `relay_port`, which only
`enable_memory` set).

**Warm's machine is now cold's machine plus a skill.** Both arms probe Vibe
once before the clock so their tool lists can actually be compared.

Two reporting changes that would otherwise have lied:

- The old summary guard printed "the step hook wrote nothing — warm's graph
  is empty" whenever the hook counter was zero. That is now *always* true
  and no longer means anything, so the summary reports ingestion instead:
  steps written, how many carry reasoning, failed tool calls recorded.
- A **non-zero** hook counter is now the alarm: it means a `hooks.toml`
  survived on a reused pod and warm is paying latency cold is not.

---

## 2026-09-17 — steps 3, 4, 5 done. The rehearsal passes 27/27

**192 tests pass. `scripts/rehearse_loop.py` passes 27/27.** Tree
uncommitted, local. Still no pod, $0/hr.

### 3. The distillation turn (`orchestrator/distill.py`)

Runs once per attempt, off the clock, after the verdict — the only moment
the agent has something new and *true* to write down. Five decisions, each
with a failure behind it, are in the module docstring; the load-bearing
ones:

- **It writes a file, not a fenced block.** A SKILL.md *is* a fenced
  ```yaml block, so asking for one inside a code fence nests fences.
- **Its own `VIBE_HOME`**, which is where the memory MCP server now lives
  and nowhere else. That separation is the whole of
  `KNOWN_ARM_DIFFERENCES` being empty.
- **Its own working directory**, not the repo: this Vibe has `write_file`
  and `bash`, and pointed at the checkout it would edit code between
  attempts and the next grading run would score edits no attempt made.
- **Its own counting proxy** (`--distill-proxy`, port 8823), because Vibe
  surfaces no per-call usage and a third endpoint is the only place
  "what did the skill cost to produce" exists apart from "what did the
  attempt cost".
- **Rejections get the validator's own JSON Lines back**, up to 2 repair
  turns; then the previous version stays live and the rejection is logged.

`propose()` now takes an **OS file lock** across read-version → validate →
write. Two warm agents finishing together both read vN and both write
vN+1, and one silently overwrites the other. A test races two proposals
and asserts exactly one wins.

### 4. Metrics (`orchestrator/metrics.py`)

Per-arm and per-attempt, derived **only** from the event log, so it can be
re-run against `runs/<id>.jsonl` and a metrics bug cannot corrupt the
record it describes. Attempt tokens and distillation tokens never merge.
`ATTEMPT_START` now records the skill version *in use*, because
distillation changes it between attempts and a run-level number would
attribute attempt 1's result to a version that did not exist yet.

The cross-run table (`runs/cross-run.md`) marks each run `yes` or
`NO (debug)` on whether `KNOWN_ARM_DIFFERENCES` was empty — so a debugging
run can never be read later as evidence.

### 5. The rehearsal, and the four real bugs it caught

`scripts/rehearse_loop.py` drives **`migrate_codebase` itself**, unwrapped,
with three things swapped: the model (scripted server), the host (bash and
a temp dir instead of ssh and /home), the grader (scripted pytest output).
Everything else is shipped code — real Vibe, real skill install, real
`/skill-name` loading, real stream parsing, real ingestion, real
distillation, real validator, real metrics.

    27/27 checks passed

**Bugs it found, in order. Two were mine in the shim; two were real and
would each have cost a pod run:**

1. **`NameError: name 'resolved' is not defined`** (`vibe_agent.py`).
   `resolved = success or advanced` was deleted when trace outcomes were
   made honest — that conflation is what let a trace claim success at
   `tests_passed=32` — but a reference to it survived in the
   `MEMORY_WRITE` emit. **Every warm attempt would have died here**, after
   grading, inside the memory block. Now written out as
   `if success or advanced:`.

2. **Vibe's `write_file` refuses to overwrite**: *"File '...' already
   exists. Use edit to modify it."*
   (`vibe/core/tools/builtins/write_file.py:141`). The distiller seeded
   the current skill at its output path so the model could edit a copy —
   which meant **every distillation would have failed**, the file keeping
   its old contents and the proposal being rejected for still being
   version N. Replaced `seed_distillation` with `clear_distilled`, called
   before *every* turn including repairs, and the prompt now says the file
   does not exist yet.

3. (shim) `_TRANSCRIPT_DUMP` expands `~`, which is right on the pod under
   `su -` and wrong locally. Nine attempts ran and none completed.

4. (shim) `ScriptedResult` lacked `create_ms`, which `SandboxResult` has.

The rehearsal also forced two improvements to the fake server itself: tool
call ids must match `^[a-zA-Z0-9]{9}$` (mistral_common), and one flat
script cannot serve this harness — an attempt and a distillation turn
interleave and a repair turn re-runs one of them, so the server now routes
by prompt and keeps a position per script. Without that the distiller was
served the attempt's `bash ls -la`.

Also confirmed by the rehearsal: the live skill stays at **v0
`e77db7780125`** after a run that advanced a *copy* to v2 — the rehearsal
cannot advance the real skill.

## RESUME HERE — 2026-09-17, pod `qsr86rh76c24dy`

**A POD IS UP AND BILLING. DO NOT PROVISION ANOTHER.**

| | |
|---|---|
| pod id | **`qsr86rh76c24dy`** (`msf-h200-distill-2`) |
| GPU / DC | NVIDIA H200, 251 GB, **24 vCPU**, US-NC-1, SECURE |
| **host CUDA** | **13.0** — required, see below |
| cost | **$4.59/hr**, created 2026-09-17 12:26 UTC |
| image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`, 300 GB disk |
| ssh | `ssh -i ~/.ssh/msf-pod -p 13517 root@103.196.86.37` |
| model endpoint | `https://qsr86rh76c24dy-30000.proxy.runpod.net` (RunPod exposes each HTTP port directly — no tunnel; the ssh.runpod.io proxy does NOT support `-L`, scp or non-PTY commands) |

### The first pod was wrong, and why

`vgmeu8ag0uzp4y` was created with `minCudaVersion: "12.8"` — a FLOOR — and
the scheduler gave a 12.8 host. `sglang[all]==0.5.14` pins
`torch==2.11.0+cu130`, so it installed cleanly and then died with
`No accelerator ... available` while `nvidia-smi` looked healthy.
Terminated, ~$0.40 and 20 minutes lost, nothing else (no weights had
downloaded).

The archived **working** B200 pod settles it — identical wheels, different
host:

```
torch 2.11.0+cu130 cuda 13.0 available True  cap (10, 0)   <- worked
torch 2.11.0+cu130 cuda 13.0 available False              <- 12.8 host
```

Use **`gpu.allowedCudaVersions: ["13.0"]`**. Written up in
NOTES-hard-won.md under "SGLang version pins".

### State on the pod (setup running detached, started 12:29 UTC)

- `/opt/swarm/` 0711 with `id_fix_proxy.py`, `hook.py` (renamed from
  `memory_step_hook.py` — the name `agent_workspace.HOOK_PATH` expects)
  and `reasoning_relay.py`, all 755.
- `/root/`: `provision.sh`, `provision_memory.sh`, `provision_web.sh`,
  `podsetup.sh`.
- `podsetup.sh` running under `nohup setsid`: venv at **`/root/sglang-venv`**
  (PEP 668 — system pip is refused on ubuntu 24.04), `sglang[all]==0.5.14`,
  **a CUDA gate that aborts before the 113 GB download if
  `torch.cuda.is_available()` is False**, then the server.
  Logs: `/root/setup.log`, `/root/sglang.log`.

### Next steps, in order

1. **CONFIRMED at 12:31 UTC:** install rc=0, and the CUDA gate passed with
   `torch 2.11.0+cu130 cuda 13.0 available True cap (9, 0)` — the same line
   the archived working B200 logged, bar the capability (9,0 Hopper vs
   (10,0) Blackwell). sglang is downloading the weights now.
   Check: `tail -5 /root/sglang.log`, `du -sh /root/.cache/huggingface`,
   then `curl -s localhost:30000/v1/models`. ~20-40 min from 12:31.
2. `bash /root/provision.sh 1` — agent users, MaxSessions 100, and the
   **three counting proxies 8821/8822/8823** (added this session).
3. **4-request control test** before any run, to separate server problems
   from harness ones.
4. Runs, back to back:

```
.venv/bin/python swarm/run.py --repo ./fixture \
  --install "pip install -r requirements-v2.txt" \
  --test "python -m pytest tests -q" \
  --arms both --swarm-size 1 --deadline-s 600 --no-stop-for-victory \
  --model mistralai/Mistral-Small-4-119B-2603 --auto-compact 128000 \
  --ssh-host 103.196.86.37 --ssh-port 13517 --ssh-key ~/.ssh/msf-pod
```

5. After EVERY run: copy `runs/`, `skills/versions/`, the agents' `.vibe`
   trees and `sglang.log` locally, verify, update this section.

### State of the code (all local, uncommitted, 201 tests pass)

Everything through mission step 5 is done and rehearsed. `git status` shows
the modified/new files; `scripts/rehearse_loop.py` passes **32/32** and
costs nothing — **run it before any change goes near the pod.**

    .venv/bin/python scripts/rehearse_loop.py --vibe <py3.12+venv>/bin/vibe

A py3.13 venv with `mistral-vibe==2.25.4` is needed for that (Vibe needs
3.12+, this project's venv is 3.11):

    uv venv --python 3.13 /tmp/vibetest
    VIRTUAL_ENV=/tmp/vibetest uv pip install mistral-vibe==2.25.4

### What the first real run is actually testing

The first distillation is the first evidence about whether Mistral Small 4
can write a schema-valid AIP skill. If it fails validation repeatedly:
**improve the prompt (clearer format, add a minimal worked example) — do
not loosen the validator.** The repair loop already hands back the
validator's own JSON Lines diagnostics.

---

### Still to do — and exactly where to pick up

**No pod is running. `list-pods` returns `[]`. Burn $0/hr.** Nothing is at
risk if this session is interrupted here; that is deliberate, and it is
why the pod was not provisioned at the end of a long working session.
Two H200s have already been lost while nothing was running on them.

6. Provision ONE on-demand H200 (secure, $4.59/hr), run
   `swarm/provision.sh`, wait for the 113 GB model, then the **4-request
   control test** before any run. Then runs back to back:

       swarm/run.py --repo ./fixture \
         --install "pip install -r requirements-v2.txt" \
         --test "python -m pytest tests -q" \
         --arms both --swarm-size 1 --deadline-s 600 \
         --no-stop-for-victory \
         --model mistralai/Mistral-Small-4-119B-2603 --auto-compact 128000 \
         --ssh-host H --ssh-port P --ssh-key K

   New flag since the last run: `--distill-proxy` (default port 8823).
   **`swarm/provision.sh` must start a third counting proxy on 8823**, or
   distillation tokens report as zero — that is the one provisioning
   change this work requires.

   Copy `runs/`, the agents' `.vibe` trees, `skills/versions/` and
   `sglang.log` off after EVERY run, and verify, before the next one.

7. Wrap-up per the mission.

Before provisioning, re-run the rehearsal — it costs nothing and it has
already caught two bugs that would each have wasted a pod run:

    .venv/bin/python scripts/rehearse_loop.py --vibe <py3.12+ venv>/bin/vibe

### 3 and 6 — still to do

The local rehearsal (item 3) cannot be completed before ingestion and
distillation exist, since those are most of what it would exercise. Order:
ingestion → hook/relay removal → distillation → metrics → **rehearsal against
a scripted fake model server** → provision. The pod-protection steps (item 6)
are recorded above and go into the run procedure when the first pod is
provisioned.

---

## Runs on pod `qsr86rh76c24dy` (H200, CUDA 13.0)

Setup took ~25 min end to end: weights downloaded in ~4 min (24 vCPU,
fast link), server up 12:34 UTC. Control test: **4/4 concurrent, 225
tok/s aggregate, 56.3 tok/s each, no empty responses** — so the 0.5.15/16
`tool_choice="auto"` failure mode is absent, as expected on 0.5.14.

### Run 1 — `swarm-1789649753`. Both arms converged; distillation crashed

| | warm | cold |
|---|---|---|
| tests passed | **33/33** | **33/33** |
| attempts | 1 | 1 |
| turns | 60 | 102 |
| attempt seconds | 131.2 | 168.5 |
| attempt tokens in/out | 1,745,783 / 6,958 | 3,915,049 / 12,278 |

**`arms match exactly: 10 tool(s) each, hooks none`** — `KNOWN_ARM_DIFFERENCES`
empty, so this run counts. Skill v0 (565 tokens) reached the model.
Ingestion wrote **58 steps, 39 with the model's own reasoning**, 3 failed
tool calls recorded. Entity extraction: 239 entities, 347 TOUCHED edges.

**The headline finding: Mistral Small 4 solves this fixture in ONE
attempt, on both arms.** That changes the experiment's shape — there is no
within-run iteration to improve, so skill versions can only advance one
per run. Three clean runs is therefore the minimum for three versions,
not a bonus.

**Bug 1 (cost the distillation):**
`AttributeError: 'AgentWorkspace' object has no attribute
'seed_distillation'` — renamed to `clear_distilled` when I found that
Vibe's `write_file` will not overwrite, but `swarm/run.py`'s closure still
called the old name. The rehearsal missed it because it calls `distill()`
directly rather than through the runner's closure, and its fake had been
updated with the rename. Fixed, plus a test that asserts every workspace
method the distiller needs exists **on the real class** and that the
runner never names the old one.

### Run 2 — killed at once by my own fix

`UnboundLocalError: cannot access local variable 'passed'`. Adding
`tests_passed=passed` to `ATTEMPT_DONE`, I anchored on the first match of
a two-line pattern and patched the **`ATTEMPT_ABORTED`** emit instead —
which fires before grading. Both arms died in seconds.

Real fix: `success`/`signature`/`passed` are now derived **above** the
`ATTEMPT_DONE` emit rather than below it. `result` is already the Daytona
result at that point, so nothing waits; the values are assigned once.
Without this, metrics reported `0 passed` for a run where both arms
scored 33 of 33.

**Lesson worth keeping:** two runs were lost to edits that were not
rehearsed. The rehearsal costs nothing and takes 90 seconds — run it after
every change, before the pod sees it.

### Runs 4-6 — the distiller's real failure mode was YAML, not reasoning

Mistral Small 4 writes AIP whose *content* is fine and whose *YAML* is
not. Two distinct mistakes, one per run, each burning all three turns of
the repair budget:

| run | what it wrote | validator said |
|---|---|---|
| 4 | `- Leaving type: ignore comments in the codebase` | `{'Leaving type': '...'} is not of type 'string'` — an unquoted colon makes a YAML **mapping** |
| 5 | `- "BaseSettings has been moved" errors appear` | `expected <block end>` — quotes wrapped only part of the item, so a scalar is followed by stray text |

Run 5 is the interesting one: it is the model **over-correcting** after
run 4's rule. Handing back the validator's own diagnostics was not enough
either time — it made the same class of mistake on every repair turn.

**Fix, per instruction, in the prompt and not the validator:** both real
failures are now in the prompt as before/after counter-examples, plus a
minimal worked example of the whole file, and the repair prompt decodes
the two error strings into what they actually mean.

**Run 6 result: two accepted distillations in one run.** v1→v2 and v2→v3,
one repair turn each, 40s and 35s. The skill also got *shorter* —
v1 1,718 tokens, v3 **989** — so the model is condensing rather than
padding, which is what the size cap was there to force.

### Skill versions so far

| version | tokens | how |
|---|---|---|
| v0 | 565 | hand-written scaffold, no task knowledge (archived as `v000-*`) |
| v1 | 1,718 | run 3, accepted first try |
| v2 | ~ | run 6 attempt 1, 1 repair |
| v3 | 989 | run 6 attempt 2, 1 repair |

**Three versions advanced, all schema-valid, all written by the agent.**

### Sidecar respawn

The sidecar died silently between runs 3 and 4 — log ended at
"listening", no traceback — and run 4 failed preflight with "step-memory
sidecar not answering". It now runs under `/opt/swarm/sidecar-keepalive.sh`,
which respawns it and logs the exit code. Note when restarting things by
pattern: `pkill -f sidecar_main` matches the ssh command line containing
that string and kills the invocation itself -- use `[s]idecar_main`.

### Who writes the skill (new, `--distill-writer`)

`orchestrator/writers.py` splits the distiller in two:

- `agent` (default) — the warm model rewrites its own skill through Vibe,
  with memory tools it chooses to use. **This is the mission's claim.**
- an OpenAI model id, e.g. `gpt-5` — a stronger model is handed the traces
  and writes the procedure. The claim becomes "a strong model can distil a
  usable procedure from these traces", which is **not self-improvement**
  and must be reported as a different result. The run banner says so, and
  the writer is stamped in the metrics.

The external writer is handed the traces **in its prompt** (an API call
has no MCP tools), so it is given a selection rather than choosing one —
another asymmetry to state when comparing the two.

`gpt-6-astra` is not available on this key (138 models listed; no `astra`,
no `gpt-6`). The strongest available are `gpt-5-pro`, `gpt-5`, `gpt-5-codex`.
Default set to `gpt-5`.

**Worth knowing before switching:** the prompt fix made the agent succeed
twice in a row, so the external writer may no longer be needed for
validity. It remains available.

---

## Who is winning, after 8 graded runs (2026-09-17)

**Warm leads on convergence and nothing else clearly.**

    warm converged 8/8        cold converged 5/8
    warm fewer tokens/attempt 5/8
    warm fewer turns/attempt  5/8

Per ATTEMPT, not per run -- cold often ran more attempts, and raw run
totals flattered warm badly. Normalised, warm's token advantage spans
**14% to 138%** of cold, which is not a finding.

### The skill version does not predict the gap

| skill | warm tokens/attempt vs cold |
|---|---|
| v0 (forbidden from containing any task knowledge) | 45%, 138% |
| v1 | 53%, 122%, 80% |
| v3 | 18% |
| v4 | 102%, **14%** |

If distilled *content* drove the gap, v0 would sit near 100% and later
versions below it. It does not: the two v4 runs came in at 102% and 14%,
and v0 already shows 45%.

**So warm-vs-cold cannot answer whether AIP helps.** It confounds three
things at once -- memory, the procedure-shaped prompt prefix, and skill
content -- and warm converged 2/2 on the empty scaffold, so whatever is
helping was there before anything was distilled. Cold's own variance is
large on identical work (54-102 turns/attempt).

### The controlled test, now built

`scripts/ab_skill.py`: **warm on v0 vs warm on v5.** Same model, same
prompt shape, same tools, same machine, warm-only, distillation OFF so
the pinned version cannot change mid-run. Pairs are **alternated**
(A/B/B/A/A/B) so session drift -- server warmth, Daytona latency -- does
not load onto whichever version ran second.

New flags: `--skill-version N` loads `skills/versions/vNNN-*.md`;
`--no-distill` skips the distillation turn. The runner warns if a version
is pinned while distillation is still on, because the first acceptance
would supersede it and the run would silently stop being controlled.

### Fixes in this batch

- **An external writer's tokens were reported as zero.** An OpenAI call
  does not pass through the pod's counting proxy, so `distil tokens 0`
  for run 9 meant "never measured", not "free". The runner now reads the
  writer's own counters when the writer is external, and the proxy when
  it is the agent. Two tests, one of them pinning the source.
- **`pgrep -f` / `pkill -f` self-matching cost three stalls.** A
  monitoring loop's own `zsh -c` command line contains the pattern, so
  `until ! pgrep -f "swarm/run.py"` never exits, and `pkill -f
  sidecar_main` killed the ssh invocation that contained the string.
  Use a bracket pattern (`[s]warm/run.py`) or key on a log line instead.
- Run 9's summary was lost when its process died after distillation. The
  metrics were rebuilt from `runs/<id>.jsonl` -- which is exactly why
  `metrics.collect()` is pure over the event log.

### gpt-5.5 as the distiller

`gpt-5.5-2026-04-23` is available and wrote **v5 with zero repair turns**.
Mistral Small 4 needed a repair turn on every acceptance and failed
outright on 3 of 7. It only ever writes the skill: both arms' agents stay
on the pod's Mistral Small 4, and GPT is reached after the clock stops,
never appearing in an agent's config or tool list.

(My earlier "no gpt-6/astra available" was from a list I had truncated to
12 entries -- gpt-5.5 was there all along.)

---

## PLANNED, not yet done: a task that cannot be one-shotted

Every run so far has been won on attempt 1. Mistral Small 4 solves this
fixture in a single attempt on both arms, so there is no within-run
iteration for a skill to improve, and the skill can only advance one
version per run. That is why the numbers above are so noisy: warm never
has to come back and do better.

**The experiment the harness is actually built for needs a task that
fails on a one-shot.** Something hard enough that attempt 1 reliably
falls short, so warm accumulates real failures, distils them, and the
skill grows into an instruction booklet that later attempts follow --
with cold starting from nothing every time.

What that task needs to be:

- **Reliably unsolvable in one attempt** by this model at this deadline,
  but solvable in several. If it is never solvable the run measures
  nothing; if it is always solvable on attempt 1 we are back here.
- **A real suite as the oracle**, with the same anti-gaming gates -- no
  shimming an old API, no emptying a function body to go green.
- **Several independent failure surfaces**, so there is something to
  learn per attempt rather than one trick that ends it.
- **Held out from the current fixture**, so no distilled skill has seen
  it. The v0-through-v5 skills are all about this Pydantic migration and
  would have to be reset to v0 for a new task.

Candidates worth costing: a larger migration across many more files; a
migration plus a behavioural change the tests pin; or the same Pydantic
job on a repo big enough that one attempt cannot cover it.

The measurement to watch then is **attempts-to-converge over runs**, not
tokens: warm should need fewer attempts as its booklet fills in, and cold
should need the same number every time.

## 2026-09-17 — the self-improvement loop was open at its last inch

Found while reading the A/B sweep's event logs: **every** run recorded
`skill_version: 5`, including the three pinned to v0 with
`--skill-version 0`. The installs themselves were correct and distinct
(v0 `dir e77db7780125`, 565 tokens; v5 `dir d378158b6751`, 1647 tokens,
both verified on the pod as the agent user), so the A/B comparison is
sound — but the label written next to every result was wrong.

Chasing the label found the real bug underneath it.

### What was broken

`orchestrator/vibe_agent.py` read the version from
`skills.current(skill_name).version` once per attempt. That answers
*"what is newest on the orchestrator's disk"*, which is a different
question from *"what did the model read"*. The two diverge in both
directions:

- **Pin a version** and every attempt is logged as the newest one while
  the agent runs the pinned one.
- **Distil between attempts** and an attempt is credited to a version
  that never reached the pod.

The second case is not just a label. `skills.propose()` writes the
accepted version to the orchestrator's disk and moves the live pointer —
and **nothing installed it into the agent's `$VIBE_HOME/skills`**.
`install_skill` was called exactly once, at run setup (`run.py:562`).
So attempt N+1 re-read the *same* procedure it had already used.

**The skill could never improve within a run.** Only across runs, via
the next run's setup install. Eight runs did not expose it because every
one of them converged on attempt 1 — the single multi-attempt warm run
(660694) spent its second attempt on the version it started with, while
the event log said otherwise.

This is precisely what the can't-one-shot-it task is meant to measure,
so it would have invalidated that experiment from its first run.

### Fixed

| where | change |
|---|---|
| `skills.py` | `_propose_locked` returns `files=package(skill_name)`. It was the one `SkillVersion` producer with `files` empty — an accepted version the caller could not install, and `dir_sha` silently falling back to SKILL.md alone |
| `agent_workspace.py` | `install_skill(..., version=)` records `installed_skill_version` / `installed_skill_sha`, set **after** every verification passes so a failed install leaves the last verified version recorded |
| `agent_workspace.py` | refuses a package without `SKILL.md`. The tree is recreated, so an empty dict does not fail — it *uninstalls* the skill and returns the hash of nothing |
| `vibe_agent.py` | reads `workspace.installed_skill_version`, never the registry |
| `run.py` | installs the accepted version onto the pod after each acceptance, verifying the body hash; a mismatch prints loudly and the run continues on the last verified version rather than dying |
| `rehearse_loop.py` | the same install-after-accept, mirroring run.py |

### The check that was passing for the wrong reason

The rehearsal already had *"attempt 1 used the starting version and
attempt 2 the distilled one"*, and it had been green for two runs. It
read the event log, which read `skills.current()` — so it confirmed the
orchestrator's pointer had advanced and said nothing about what the
agent could read. The bug satisfied the test designed to catch it.

Added alongside it: **"the improved skill reached the agent's own skills
directory"**, which sha256s `SKILL.md` *in the agent's `$VIBE_HOME`* and
compares it to the live version's bytes. That one cannot pass without
the loop being closed. Same lesson as the memory-tools gap in run 9:
verify the wire, not the wrapper.

Tests 212 → 218 (six added, all in `tests/test_skill_loading.py`).
Rehearsal 32/32 → 33/33.

### Effect on the running A/B

None. The sweep runs `--no-distill`, so the install-after-accept path is
never entered, and `skill_version` is a log field with no control flow
on it. Runs p0/p1 and p2's v0 ran on pre-fix code, p2's v5 on post-fix;
the pinned installs are byte-identical across both, verified by hash in
each run's banner.

The clean-run counter resets again with these changes.

## 2026-09-17 — A/B result: warm on v0 vs warm on v5

The comparison warm-vs-cold cannot make. Six warm-only runs, distillation
off, `--skill-version` pinned, everything else identical — same model,
same prompt shape, same tools, same pod. Only the skill's **content**
differed, verified by hash in every run's banner: v0 `dir e77db778`,
565 tokens, 1 step; v5 `dir d378158b`, 1647 tokens, 9 steps, derived
from 9 traces.

| pair | slot | version | tests | attempts | turns | prompt tokens |
|---|---|---|---|---|---|---|
| 0 | 1 | v0 | 33 | 1 | 93 | 3,438,442 |
| 0 | 2 | v5 | 33 | 1 | 58 | 1,594,312 |
| 1 | 1 | v5 | 33 | 1 | 71 | 2,343,619 |
| 1 | 2 | v0 | 33 | 1 | 78 | 2,571,991 |
| 2 | 1 | v0 | 33 | 1 | 70 | 2,370,784 |
| 2 | 2 | v5 | 33 | 1 | 70 | 2,039,387 |

|  | v0 | v5 | gap |
|---|---|---|---|
| converged | 3/3 | 3/3 | none |
| turns/attempt | 80 | 66 | v5 17% fewer |
| prompt tokens/attempt | 2,793,739 | 1,992,439 | v5 29% fewer |
| tokens per turn | 34.9k | 30.2k | v5 13% fewer |

### What holds up

**Tokens separate completely.** Every v5 run used fewer prompt tokens
than every v0 run — v5's worst (2.34M) is below v0's best (2.37M). Exact
one-sided permutation p = 1/20 = **0.050**, which is the *floor* for
three against three: this design cannot produce a smaller number even in
principle.

**Turns do not.** 17% lower, but the sets overlap (v5 {58, 70, 71}, v0
{70, 78, 93}) and p = 0.15.

**Convergence is unaffected.** Both versions passed 33/33 on attempt 1,
every run. On this fixture the skill changes what the work *costs*, not
whether it gets done — which is the same ceiling the warm-vs-cold runs
hit, and the reason the can't-one-shot-it task matters.

### Two things that cut the result down

**1. A position confound, and it favours v5.** Alternating order pair by
pair only balances with an *even* number of pairs. With 3 the order went
AB/BA/AB, so v0 ran first twice and v5 once — and the second slot
measured **24% cheaper** than the first (2.07M vs 2.72M), an effect
larger than the one being measured.

Stratifying by slot, the separation survives — in slot 1 v5's single run
is below both v0 runs, in slot 2 both v5 runs are below v0's — but the
p-value goes from 0.050 to **0.111**.

`scripts/ab_skill.py` now refuses an odd `--pairs` (default 4) unless
`--allow-unbalanced` is passed, records each run's slot alongside its
numbers, and prints the per-run lines so the means cannot be read
without the spread.

**2. One outlier carries much of the gap.** Pair 0's v0 run at 3.44M is
the most expensive run in the sweep. Drop pair 0 entirely and v5's
advantage falls from **29% to 11%**.

### Verdict

Suggestive, not established: the distilled skill looks like it reduces
token cost by somewhere between 10% and 30% with no effect on whether
the task is solved. Establishing it needs 4+ balanced pairs. Worth
doing — but the can't-one-shot-it task is the higher-value run, because
it tests the claim the harness was built for rather than a cost margin
on a task both versions already win.

## 2026-09-17 — run 10: the loop closed, and cost the run its best attempt

First run with install-after-accept. **The skill advanced within the
run**: attempt 1 on v5, attempt 2 on v6, attempt 3 on v7, each version
distilled from the attempt before it and installed on the pod before the
next started. gpt-5.5 accepted 3/3 with 0 repairs.

| arm | passed | attempts | turns | attempt tokens | distil tokens |
|---|---|---|---|---|---|
| warm | 33 | 3 | 176 | 5,624,436 in / 24,791 out | 37,374 in / 5,992 out |
| cold | 33 | 2 | 118 | 3,058,137 in / 15,523 out | — |

Warm needed one more attempt than cold and spent ~1.8x the tokens. n=1,
and warm's attempt 2 on the fresh v6 took only 26 turns — but it is not
a result in warm's favour and should not be reported as one.

### Two bugs, both found in the event log rather than the summary

**1. A timed-out attempt ingested nothing, and it was the attempt that
passed.** Attempt 3 ran 59 turns, took the suite from 32 to 33/33 — the
only passing warm attempt — hit its 103s timeout, and wrote **0 steps**.

`invoke_vibe_async` collected output with `proc.communicate()`, which
buffers inside the coroutine; the timeout cancelled it and every byte
Vibe had streamed went with it. The transcript is no substitute:
`messages.jsonl` carries `role`, `content`, `tool_calls` and
**no reasoning field**, so rebuilding steps from it would write actions
with empty thoughts — which `test_no_step_stored_tool_argument_json_as_
its_thought` already forbids for good reason.

Fixed by draining stdout/stderr as the bytes arrive, so a timeout
returns the partial stream and the completed turns survive. A line cut
in half is skipped by `stream_entries`; the turn before it is kept.

Two traps in the fix, both caught by the existing suite:

- `wait_for(shield(f))` raises `CancelledError`, not `TimeoutError`, so
  the first version re-raised and unwound the agent loop — precisely
  what `test_timeout_returns_rather_than_raises` was written for.
- `contextlib.suppress(Exception)` does not catch `CancelledError`
  (it derives from `BaseException`), so awaiting the cancelled gather
  raised straight through the handler.

**This matters most for the task that cannot be one-shotted.** There,
attempts that run out of clock are the *normal* case, and they carry the
failure information the distiller needs. Every one of them would have
ingested nothing.

**2. The skill-reached check reported a false negative on a working
loop.** It compared the transcript against the version the *run* started
on, and printed:

    warm-0: skill loaded but it is NOT v5 -- Vibe served different text
    skill v5 (889196a26d19, 1647 approx tokens) reached 0/1 warm agent(s)

Both wrong, and the second reads in the record as a skill that never
reached the model — the exact failure the check exists to detect. Warm
had loaded v7 correctly. The stated explanation ("a resumed session
replays the version it first loaded") is also impossible now: no session
is ever resumed.

Replaced with `skills.identify(text)`, which returns which archived
version's body is in the transcript, compared against the version that
agent's **last attempt** started on. The summary now prints
started-vNN..ended-vNN rather than naming one version a distilling run
does not have.

Tests 218 → 223. Rehearsal 33/33. Clean-run counter resets.

### Still open

- `INGESTED` for a timed-out attempt is now non-zero, but this needs
  confirming on the pod before it is believed — the fix is verified by
  a behavioural test against a hanging process, not yet by a real run.
- The blocking-loop guard still reports 28.6s at `run.py:637` plus two
  ~4s callbacks in `agent_worker`. Before the clock, low priority.
- Entity extraction hit its 240s bound for both calls again. Off the
  clock and unused by distillation, but it is 8 minutes per run.

## 2026-09-17 — run 11, and the size cap is about to bind

Warm on v8. **Warm won this one clearly**, and by more than run 10 lost:

| arm | passed | attempts | turns | attempt tokens |
|---|---|---|---|---|
| warm | 33 | 1 | 83 | 2,842,745 |
| cold | 33 | 2 | 162 | 5,390,107 |

Warm converged first time on 53% of cold's tokens. Distillation accepted
v9, 0 repairs, 12,345 in / 2,146 out on gpt-5.5.

### Neither of run 10's fixes was actually exercised

Being precise, because the summary line looks like confirmation and is
not:

- The checklist printed `warm-0: skill v8 reached the model` and
  `1/1 warm agent(s)`. That is the OLD code path — run 11 launched
  before the edit landed — and it passed only because warm converged on
  attempt 1, so the version never advanced mid-run and the old baseline
  happened to be right.
- No attempt timed out, so the stream-drain fix was never touched.

**Both fixes remain unconfirmed on the pod.** Confirming them needs a
warm run with more than one attempt *and* an attempt cut by the clock.
Run 12 is the first run carrying both.

### The 2,000-token cap is about to stop the loop

| version | tokens |
|---|---|
| v5 | 1,647 |
| v6 | 1,609 |
| v7 | 1,754 |
| v8 | 1,816 |
| v9 | 1,839 |

161 tokens of headroom left, and the trend is +50-60 per accepted
version. Two or three more runs and every proposal is rejected
`too_large`, the previous version stays live, and the loop looks like it
is working while it has quietly stopped. The rejection IS logged
(`DISTILLED.reason`), so it will not be silent — but it will be terminal.

The cap is not a bug: the skill is prompt prefix on every warm attempt,
so it is a per-attempt cost, and it is the warm arm's token count that
is the headline number. The prompt now tells the writer its current size
and exact remaining headroom, and that appending is not available near
the limit — delete steps that did not help, merge steps that always run
together, cut anti-patterns that stopped recurring.

**Open question for the operator, not resolved here:** the
instruction-booklet experiment wants a skill that GROWS with accumulated
failures. A 2,000-token ceiling may be the wrong constraint for that
task, and raising it trades measured token cost against how much
procedure the booklet can carry. Not changing it unilaterally — the
mission set ~2,000 and it is a measurement parameter, not an
implementation detail.

Tests 223 → 224.

## 2026-09-17 — skill cap raised to 13,000 tokens

Was 2,000 (~1,500 words), now **13,000 (~10,000 words)**, per the
operator: the target is an instruction booklet, not a summary.

Timing: v11 came in at **1,990 tokens**. One more version and every
proposal would have been rejected `too_large` with the previous version
staying live — a loop that looks like it is working and has stopped.

**What raising it costs, recorded because it changes the headline
metric.** The skill is prompt prefix on every warm attempt and Vibe
re-sends the conversation each turn, so a skill of S tokens adds roughly
S x turns to the arm's prompt-token total. At 60-90 turns/attempt:

| cap | added per attempt | vs 2-3M baseline |
|---|---|---|
| 2,000 | ~0.15M | noise |
| 13,000 | ~1.0M | a third of the attempt |

So **warm's token count stops being a fair comparison against cold**, and
**attempts-to-converge becomes the measure** — which is what the harder
task needs anyway. Any write-up comparing token counts across the cap
change is comparing two different experiments.

The writer is now told its current size and exact remaining headroom, and
that appending is not available near the limit: delete steps that did not
help, merge steps that always run together, cut anti-patterns that stopped
recurring. `test_an_oversized_proposal_is_rejected` now sizes its padding
off the cap — it had silently stopped testing anything when the cap moved,
because its 8,000-token padding became legal.

## 2026-09-17 — choosing the repo for the long-run experiment

Measured, not guessed. Scored four framework candidates and three
consumer-style ones by how many INDEPENDENT pydantic v1->v2 failure
surfaces their own code contains (22 surfaces probed), plus suite size.

| candidate | src LOC | tests | pydantic files | surfaces |
|---|---|---|---|---|
| aiogram 2.25.1 | 25,254 | 203 | 1 | 1/22 |
| sqlmodel 0.0.8 | 1,775 | 112 | 1 | 7/22 |
| fastapi 0.99.1 | 6,311 | 1,466 | 9 | 9/22 |
| datamodel-code-generator 0.21.5 | 8,599 | 317 | 15 | 10/22 |
| starlite 1.51.14 | 28,645 | 913 | 48 | 17/22 |
| **prefect 2.10.21** | **86,621** | **4,413** | **85** | **19/22** |

### Two disqualifiers worth keeping

**1. A dependency pinned to pydantic v1 makes the task unsolvable.**
`starlite 1.51.14` scored 17/22 and looked like the winner until its
dependencies were read: `pydantic-openapi-schema` and
`pydantic-factories` are both pinned to v1. The agent cannot migrate code
it does not own, so no amount of work on the repo makes the suite pass.
That is why upstream rewrote to msgspec in Litestar 2.0 rather than
migrating. **Check transitive pins before scoring anything.**

**2. Framework internals-integrators force the forbidden anti-pattern.**
fastapi, sqlmodel and starlite all hook private pydantic APIs
(`ModelField`, `pydantic.fields`). Upstream's answer in each case was a
compatibility shim — `fastapi/_compat.py` — which is exactly the
"shimming the old API is not a migration" gate this project already
rejects. **Prefer CONSUMERS of pydantic** (models, settings, validators)
over integrators.

### Recommendation: Prefect 2.10.21, scoped

`pydantic >= 1.10.0, < 2.0.0` is the repo's OWN pin — the agent changing
it is part of the task, same as the current fixture. No third-party dep
pins v1 (`fastapi >= 0.93` resolves to a v2-compatible release). Upstream
did migrate Prefect to v2, so the task is known-achievable.

Surfaces present in its own code: `.dict()/.json()` x102, `@validator`
x65, `from_orm/orm_mode` x48, `parse_obj/parse_raw` x44, `__fields__`
x39, `class Config` x29, `@root_validator` x26, `__root__` x14,
`schema()` x10, `PrivateAttr` x10.

**Raw size is not the difficulty lever — reachable surfaces per attempt
is.** 4,413 tests is not "hard", it is "never converges", which measures
nothing. So scope the oracle to a test subset and use that as the dial:

| target | tests | surfaces it forces |
|---|---|---|
| `tests/test_settings.py` | 94 | BaseSettings -> pydantic-settings |
| `tests/server/schemas` | 152 | validators, root_validators, Config, `__root__` |
| `tests/_internal` | 159 | schema bases, PrivateAttr |
| `tests/events` | 76 | nested models, serialisation |

~481 tests across four independent targets. Switch on one for the easy
end, all four for the hard end. `tests/server/schemas/test_filters.py`
imports a DB session and should be excluded.

### Not yet known, and it needs GPU time

- **Where the difficulty band is.** The target curve is: attempt 1
  reliably fails, early runs converge in 3-6 attempts, mature-skill runs
  in 1-2. That is the improvement curve the demo shows. Finding it means
  cold-arm-only calibration runs per subset — cheap, since cold needs no
  distillation.
- **Install cost per attempt.** 39 runtime deps including `kubernetes`,
  `docker`, `cryptography`, `asyncpg`, `sqlalchemy`. The grader installs
  in a fresh Daytona sandbox after EVERY attempt, so this multiplies.
  Measure before committing; a wheel cache or a pre-baked sandbox image
  may be required.
- **The skill resets to v0.** v0-v11 are all specific to the current
  Pydantic fixture. That is the right call for the demo anyway: the
  history starts empty and the booklet is visibly built from failures.

## 2026-09-17 — a second fixture, and everything that had to become per-fixture

The small fixture is exhausted as an experiment: runs 11-14 all went
warm-1-attempt vs cold-2-attempts, which is the ceiling. A skill cannot
show improvement on a task that is already won on the first try.

### scripts/make_fixture.py — fixtures are now generated, not hand-built

Keyed on a **real merged migration PR**, which supplies all three pieces
at once: source at the base commit (what the agent edits), tests at the
merge commit (an oracle the agent cannot satisfy by editing), and the
merged source as the answer key. Someone has already proved the
destination is reachable.

Validated by regenerating the existing fixture: it reproduces
`fab70e4e -> c15d24e4` and scores it 7/22 surfaces, 33-test oracle.

### The ladder, measured with one ruler

| candidate | files | diff | surfaces | oracle | touched | sensitivity |
|---|---|---|---|---|---|---|
| fastapi-mail#195 (current) | 6 | +506/-440 | 7/22 | 33 | 1 | 3% |
| pandera#1253 | 20 | +334/-146 | 6/22 | 570 | 38 | 7% |
| **openapi-python-client#779** | **40** | **+726/-618** | **6/22** | **445** | **216** | **78%** |
| hera#795 | 73 | +439/-643 | 10/22 | 85 | 14 | 16% |
| ariadne-codegen#186 | 108 | +619/-552 | 6/22 | 401 | 79 | 20% |
| zenml#2543 | 345 | +6517/-4393 | - | - | - | - |

**Sensitivity — what fraction of the oracle touches migrated code — beats
raw size.** pandera has a 570-test suite of which 38 touch the migration:
most of it passes no matter what the agent does. openapi-python-client is
216 of 277 (445 collected), so the oracle actually grades the work.

Chose **openapi-python-client#779**: 6.7x the files, 13x the oracle, and
the tests exercise the change. zenml stays on the ladder as the next rung.

### Disqualifiers found the expensive way

- **starlite 1.51.14** scored 17/22 and was the leader until its
  dependencies were read: `pydantic-openapi-schema` and
  `pydantic-factories` are both pinned to v1. The agent cannot migrate
  code it does not own, so the suite can never pass. Upstream rewrote to
  msgspec rather than migrate.
- **prefect 2.10.21** scored 19/22 with no dependency trap, and still
  fails: `filterwarnings = error` in its pytest config turns every
  pydantic deprecation into a failure, and its own tests call `.dict()`,
  `parse_obj` and `__fields__`. It has no merged migration commit to take
  cleaned-up tests from, so the oracle would have to be edited -- at
  which point it stops being independent.
- **Framework internals-integrators** (fastapi, sqlmodel, starlite) hook
  private pydantic APIs and upstream answered each with a compatibility
  shim. That is the exact anti-pattern `v1_shim_files` rejects. Prefer
  CONSUMERS of pydantic.

### The fixture is verified at both ends, and the pins are load-bearing

With the human's own merged answer in place the suite must be 100%, or
the fixture is unsolvable and every run measures noise:

| deps | reference answer scores |
|---|---|
| unpinned (pydantic 2.13.5, click 8.2) | 24 failed, 421 passed |
| pydantic 2.1.1, click 8.2 | 19 failed, 426 passed |
| pydantic 2.13.5, click <8.2 | 5 failed, 440 passed |
| **pydantic >=2.1.1,<2.10, click <8.2** | **445 passed, 0 failed** |

The 19 that survived pinning pydantic were all `tests/test_cli.py` hitting
a typer/click API change -- nothing to do with the migration, and they
would have read as "the agent did not finish". Baseline with the
pre-migration source fails hard at collection: `` `const` is removed, use
`Literal` instead ``.

### What had to become per-fixture (and why each was a latent bug)

| was | now | what sharing would have done |
|---|---|---|
| `FIXTURE_DIR` hardcoded | `MSF_FIXTURE_DIR`, default unchanged | "try a harder repo" was a code change |
| `INCLUDED_RELATIVE_PATHS = ["fastapi_mail", ...]` | read from the manifest | baked the WRONG package into the image; every attempt graded against a directory the agent never edited |
| `.snapshot_state.json` | `.snapshot_state-<fixture>.json` | a saved `mode=snapshot` state hands back the other fixture's image |
| `skills/versions/` | `versions-<fixture>/` for non-default | a second lineage starting at v0 writes `v001-...md` over the first fixture's v1 |

Also added `needs_editable_install` to the manifest: this fixture's
`__init__.py` calls `importlib.metadata.version(__package__)`, so an
un-installed copy raises `PackageNotFoundError` before a single test runs.
`pip install -e . --no-deps` -- editable so uploaded files are what
execute, `--no-deps` so the pre-migration `pydantic = "^1.6.1"` pin cannot
drag v1 into a v2-only sandbox.

### Reverting

`.backup/REVERT.md`. The original fixture, its snapshot state and its
whole v0-v13 lineage are untouched; the only shared file that changed is
the live `SKILL.md`, and its last fastapi-mail value is kept in two
places. One `cp` reverts it.

**One cosmetic casualty:** run 14's summary reads `started v12 ... ended
v0`. It actually distilled v13 -- the live file was reset while that run
was still doing after-clock work. The event log and `v013-...md` are
correct. Operator error, and the reason for the per-fixture split above.

### scripts/plot_curve.py

Four panels over successive runs on one fixture: attempts-to-converge
(the headline), best tests passing, skill size and version, tokens per
attempt. Cold is the flat control for drift. Marks runs that do not count
and annotates arms that never converged, so a missing convergence cannot
be read as a fast one.

Tests 224. Skill reset to v0 for this fixture; lineage in
`skills/versions-oapi/`.

## 2026-09-18 — oapi run 1: the fixture lands in the right band

| arm | best passing /445 | attempts | turns | attempt tokens | converged |
|---|---|---|---|---|---|
| warm (v0 -> v4) | **311** | 5 | 300 | 8,871,113 | no |
| cold | **0** | 2 | 176 | 5,948,153 | no |

**This is the task the harness was built for and never had.** Everything
that was wrong with the small fixture is fixed at once:

- **Not one-shottable.** Attempt 1 scored 0. On the old fixture attempt 1
  scored 33/33 in four of the last five runs.
- **Partial credit exists.** 311 of 445 is a real measurement. The old
  oracle was 33 tests that moved as a block, so every run was 32 or 33.
- **Within-run iteration happens.** Five warm attempts, the skill
  advancing v0 -> v1 -> v2 -> v3 -> v4 between them, each attempt reading
  the version distilled from the one before. That is the loop the
  install-after-accept fix opened, doing the thing it exists to do.
- **Cold is a real control.** 0 of 445 across both its attempts.

### The raised cap was load-bearing, immediately

| version | tokens |
|---|---|
| v0 | 565 |
| v1 | 1,954 |
| v2 | 2,612 |
| v3 | 2,755 |
| v4 | 3,524 |

**v1 alone would have been rejected under the old 2,000 cap**, and the
run would have spent five attempts on the empty scaffold. The booklet is
growing at ~600 tokens a version on a task with real material to record,
against ~60 on the exhausted one.

### Honest reads on run 1

- **Neither arm converged**, so attempts-to-converge is undefined here.
  Best-tests-passing is the curve's usable metric until a run finishes.
- **Warm got 5 attempts to cold's 2** in the same budget. Not an unfair
  clock: both had 900s of attempt time and warm used 716s, cold 671s.
  Cold simply spent ~335s per attempt against warm's ~143s.
- **Warm regressed on attempt 5**, from 311 back to 0 on skill v3. One
  attempt, no explanation yet, and worth watching: a booklet that grows
  every attempt can encode a wrong turn as confidently as a right one.
- One distillation was rejected `invalid_schema` (attempt 1); 4 of 5
  accepted.

Cost: ~28 min per run, ~$2.10 at $4.59/hr.

## 2026-09-18 — cross-fixture contamination, found in the booklet's own words

Runs 1-2 on the new fixture are **discarded**. The cause is in the skill
v9 wrote about itself:

> "Attempt 3 regressed on **a different repository** because a Project
> model rejected..."

`eligible_traces` filtered on model, writability and outcome schema --
but not on WHICH CODEBASE a trace came from. So the new fixture's very
first distillation reported **25 eligible traces before that fixture had
produced a single one**. All 25 were the old fixture's. Every booklet
version on the new task was distilled from a mixture of two codebases.

Not fatal to the harness, fatal to the claim: "the agent improved by
distilling ITS OWN attempts on THIS codebase" is precisely what those 25
traces make unprovable. It is the same seeding the project forbids by
hand, arriving through the graph instead.

### Fixed

| where | change |
|---|---|
| `swarm/run.py` | every trace is stamped `prov_fixture` |
| `memory.py` | `eligible_traces(fixture=...)` adds `AND t.prov_fixture = $fixture`; default `None` keeps pre-property traces reachable deliberately |
| `distill.py` | passes the active fixture |

Two tests pin it, including that the stamp exists -- the filter is only
as good as what it filters on.

### What the discarded runs still tell us

They are void as a curve and sound as calibration, because the
contamination affected the SKILL, not the task or the oracle:

| run | warm best /445 | cold best /445 |
|---|---|---|
| 1 | 311 (5 attempts) | 0 (2 attempts) |
| 2 | 310 (5 attempts) | 431 (4 attempts) |

**Cold beat warm in run 2**, and both warm runs plateaued at ~310. The
per-attempt scores are near-binary -- 0 or ~310 -- and the reason is in
the booklet's own comments:

> "Attempt 5 ended with zero tests passing because tests.conftest could
> not import the package. The nested cause was IndentationError... This
> was another syntax regression, not a validation behavior failure."

**The zeroes are the agent's own syntax errors**, not migration failures.
It reaches ~310, then breaks collection with a bad edit, and since
attempts continue from the same tree, the damage persists. Run 1 went
0,0,0,311,0; run 2 went 0,310,0,0,0. Cold climbed 0,0,310,431.

That is a real dynamic and worth keeping in view: warm distils guards
against it (`compile-after-every-edit`, `run-fast-verification-after-
each-edit-group` are both in v9), so the clean series is a fair test of
whether those guards actually take hold.

Lineage reset to v0; the contaminated versions are kept in
`skills/versions-oapi-contaminated/` and the void logs in
`runs/contaminated/`. Tests 226.

## 2026-09-18 — clean series on openapi-python-client (fixture-scoped traces)

| run | skill at start | warm best /445 | warm att | cold best /445 | cold att |
|---|---|---|---|---|---|
| 1 | v0 | **445 (converged)** | 3 | 440 | 5 |
| 2 | v0 | **0** | 5 | **445 (converged)** | 4 |
| 3 | v5 | running | | | |

Run 1's distillation was rejected 3/3 (`invalid_schema`), so warm ran the
empty scaffold throughout and its win says nothing about distillation.
Run 2 accepted 5/5 (v1..v5) and warm scored zero on every attempt.

### The dominant failure mode is not the migration

Warm run 2, per attempt: 0, 0, 0, 0, 0 at 54, 59, 18, 40, 18 turns. The
v5 booklet names the cause itself:

> "Failed attempts corrupted Config classes and examples with broad regex
> rewrites, producing invalid code such as `extra = .allow` in example.py
> and preventing even conftest import. Fix the first traceback directly,
> grep for the same v1-only construct, verify syntax immediately, then run
> targeted tests before any wider cleanup."

**One catastrophic bulk edit poisons the entire run.** The checkout
persists across attempts by design, so a `sed`-style sweep that breaks
syntax leaves every later attempt starting from broken code, and the
collapsing turn counts show the agent unable to dig out. Both arms have
this property; in these two runs cold happened to avoid it and warm did
not.

That makes the outcome near-binary and enormously variable -- warm 445
then 0, cold 440 then 445 -- which is a property of the agent's editing
discipline, not of the skill. Any curve here needs enough runs that this
variance averages out, and two runs is not enough to claim anything in
either direction.

### Why run 3 is the first real test

It is the first run to START with a substantive booklet (v5, 3,213
tokens) whose leading guidance is precisely "do not begin with a broad
mechanical rewrite" and "verify syntax immediately". If distillation is
worth anything on this task, that is the mechanism it should work
through, and this is the first run in a position to show it.

### Two observability fixes

- Rejected proposals and the validator's own diagnostics are now written
  to `versions-<fixture>/rejected/`, and the `DISTILLED` event carries
  the first 400 chars of the diagnostic. Run 1 recorded three rejections
  as the single word `invalid_schema`, with the proposal discarded --
  nothing to fix the prompt from.
- That debug path was first rooted at `REPO_ROOT`, so the TEST SUITE
  wrote its own rejected proposals into `runs/rejected/`, where they read
  as evidence from a real run. Now under `versions_dir()`, which the
  tests monkeypatch into a tmp sandbox.

### Operator error, recorded

A local diagnostic called `skills.propose()` to reproduce the rejection
and bumped the live skill v0 -> v1 **while run 2 was in flight**. Caught
before run 2 distilled; live reverted to v0 and the lineage verified
clean, so run 2 is unaffected. Second instance of the same mistake (the
first cost run 14 its summary line): never mutate shared skill state
while a run is live. The diagnostic should have monkeypatched
`SKILLS_DIR` the way the tests do.

Tests 226.

## 2026-09-18 — run 3, and the pattern worth testing directly

| run | skill | warm per-attempt | warm best | cold per-attempt | cold best |
|---|---|---|---|---|---|
| 1 | v0 fixed (distil rejected 3/3) | 0, 310, **445** | 445 | 0, 0, 310, 310, 440 | 440 |
| 2 | v0 -> v5 | 0, 0, 0, 0, 0 | 0 | 0, 0, 311, **445** | 445 |
| 3 | v5 -> v9 | **311**, 0, 0, 0 | 311 | 0, 0, 0, 310, 436 | 436 |

**Cold is monotone in all three runs and lands 436-445 every time.** It
never goes backwards and it never fails to get most of the way.

**Warm is inconsistent**: 445, then 0, then 311. Its only converged run
is run 1 -- the run in which distillation was REJECTED 3/3 and the skill
stayed at the empty v0 scaffold for the whole run.

### Stating the pattern accurately

An earlier reading of this was overstated as "warm peaks then crashes".
Checked properly:

- warm run 3 is the only non-monotone sequence (311 -> 0 and never
  recovers);
- warm run 2 never peaked at all -- five attempts, zero throughout;
- warm run 1 is monotone and converged.

So the supported claim is the weaker one: **cold is consistent, warm is
not, and warm's single success came without a changing skill.** One
non-monotone run is an anecdote, not a mechanism.

### The hypothesis that is worth a controlled run

Every warm attempt after the first gets a DIFFERENT procedure -- v5, v6,
v7, v8 within run 3 alone. A changing procedure across attempts that
share one persistent checkout is a plausible destabiliser: each attempt
re-approaches a half-migrated tree under different instructions, and an
attempt that starts a new sweep on someone else's half-finished work is
exactly how the tree gets corrupted.

That is testable rather than arguable, and cheaper than more noisy runs:
hold the booklet FIXED for a whole run (`--no-distill --skill-version 9`)
and see whether warm behaves like cold. Same model, same fixture, same
oracle; the only change is whether the procedure moves mid-run.

- If fixed-booklet warm is monotone and lands 436-445, the instability is
  the CHANGING procedure, not the skill's content -- and the design fix
  is to distil between RUNS only, not between attempts.
- If it is still erratic, the instability is the agent's editing
  discipline and the skill is irrelevant to it.

Run 4 continues the series (v9 onward); run 5 is the controlled one.

## 2026-09-18 — run 4: warm's best run, and the first real sign of the curve

| arm | best /445 | attempts | turns | attempt tokens | converged |
|---|---|---|---|---|---|
| warm (v9 -> v11) | **445** | **2** | — | **3,844,747** | **yes** |
| cold | 442 | 5 | — | 9,234,793 | no |

Warm went 0 -> 445 in two attempts on **42% of cold's tokens**, while
cold spent five attempts and still did not converge. That is the
strongest single result the project has produced, and it came with the
most mature booklet yet (v9, 4,829 tokens).

### The four clean runs

| run | skill at start | warm best | warm att | cold best | cold att |
|---|---|---|---|---|---|
| 1 | v0 (distil rejected 3/3) | 445 | 3 | 440 | 5 |
| 2 | v0 | 0 | 5 | 445 | 4 |
| 3 | v5 | 311 | 4 | 436 | 5 |
| 4 | v9 | **445** | **2** | 442 | 5 |

Cold is flat: 440, 445, 436, 442 in 4-5 attempts, never converging in
three of four. Warm is erratic early and best at the end, which is the
shape the experiment predicts -- but runs 1 and 2 both started from v0
and produced 445 and 0, so **the variance is at least as large as the
trend**. Four runs cannot separate those.

### What run 5 is for

Booklet PINNED at v11, distillation OFF. It separates two explanations
of run 4 that four runs cannot:

- **the booklet's CONTENT is now good** -- then a pinned v11 should also
  converge fast, and distillation between attempts is unnecessary
  overhead;
- **run 4 was luck** -- then a pinned v11 looks like runs 2 and 3.

Either way it also tests the destabilisation hypothesis from run 3,
because the procedure cannot move mid-run.

## 2026-09-18 — run 5 (controlled): the mature booklet, held still, failed completely

Booklet PINNED at v11 (5,029 tokens, derived from 14 traces),
distillation OFF.

| arm | best /445 | attempts | per-attempt |
|---|---|---|---|
| warm (v11 fixed) | **0** | 5 | 0, 0, 0, 0, 0 |
| cold | 429 | 5 | 0, 0, 301, 420, 429 |

**This refutes both explanations of run 4.** A fixed mature booklet did
not converge fast, so run 4 was not "the content is now good"; and
holding the procedure still did not stabilise anything, so the run-3
destabilisation hypothesis does not survive either. Warm failed on every
attempt with the best skill the system has produced.

### The five clean runs, plainly

| run | booklet | warm best | cold best |
|---|---|---|---|
| 1 | v0 (distil rejected) | 445 | 440 |
| 2 | v0 -> v5 | 0 | 445 |
| 3 | v5 -> v9 | 311 | 436 |
| 4 | v9 -> v11 | 445 | 442 |
| 5 | v11 FIXED | 0 | 429 |

|  | warm | cold |
|---|---|---|
| mean best | **240** | **438** |
| range | 0-445 | 429-445 |
| converged | 2/5 | 1/5 |
| total failures (0) | **2/5** | **0/5** |

**Cold is better on this fixture, and it is not close.** Cold never once
failed to get most of the way; warm failed completely twice in five runs.
Warm's two wins are real (445 in 3 attempts, 445 in 2 attempts on 42% of
cold's tokens) but they are two of five, and the mean is what a user
would experience.

### What this does and does not say

It does NOT say distillation cannot work: the mechanism runs end to end,
the booklet contains genuinely correct, specific, self-diagnosed lessons,
and warm's two good runs are its two best results anywhere.

It DOES say that on this task the distilled procedure is not the
dominant term. The dominant term is whether the agent makes a
catastrophic bulk edit that breaks collection, and neither the presence
of a booklet, nor its maturity, nor holding it still prevents that. Run 5
is the cleanest evidence: best booklet, no churn, five failures.

A plausible reading, unproven: a long prescriptive procedure encourages
sweeping multi-file edits, which is exactly the behaviour that corrupts
the tree, while cold -- having nothing to follow -- fixes the first
traceback and re-runs. Cold's monotone 0 -> 301 -> 420 -> 429 in run 5 is
what that looks like. Testing it means varying booklet LENGTH, not
presence.

## 2026-09-18 — FINAL: six clean runs, the curve, pod terminated

Pod `qsr86rh76c24dy` **terminated** at 04:05 (verified: `list-pods`
returns empty). Artefacts at
`pod-artifacts/h200-qsr86/final/final.tgz`, MD5
`e050e8b3cd005e5fce55fa395fa3c35f`, verified equal on both ends, 63
entries. Curve at `runs/curve-oapi.png`.

### The six runs

| run | booklet | warm best | warm att | cold best | cold att |
|---|---|---|---|---|---|
| 1 | v0, distil rejected 3/3 | **445** | 3 | 440 | 5 |
| 2 | v0 -> v5 | 0 | 5 | **445** | 4 |
| 3 | v5 -> v9 | 311 | 4 | 436 | 5 |
| 4 | v9 -> v11 | **445** | 2 | 442 | 5 |
| 5 | v11 PINNED | 0 | 5 | 429 | 5 |
| 6 | v11 PINNED | **445** | 3 | **0** | 6 |

|  | warm | cold |
|---|---|---|
| mean best | 274/445 | 365/445 |
| range | 0-445 | 0-445 |
| converged | **3/6** | **1/6** |
| total failures | 2/6 | 1/6 |

### The result

**No reliable difference between the arms, because a failure mode
neither of them controls dominates the outcome.**

Both arms are bimodal: every run scores either ~440 or 0. A zero is not
a failed migration -- it is the agent breaking `import` with a bulk edit,
after which the persistent checkout means every later attempt starts
from broken code. Run 5 and run 6 are the same configuration (v11
pinned, no distillation) and produced warm 0 / cold 429 and warm 445 /
cold 0 respectively. That is the whole finding in two runs: identical
setup, opposite outcomes, and the coin lands on a different arm each
time.

Warm converged 3/6 against cold's 1/6, which is the only number pointing
warm's way, and at n=6 with this variance it is not a result.

### What was ruled out along the way

- **"The booklet's content is now good"** -- run 5 pinned the most mature
  booklet (v11, 5,029 tokens, 14 traces) and warm scored zero on all five
  attempts.
- **"A changing procedure destabilises the run"** -- same run: the
  procedure could not move, and warm still failed completely.
- **"Cold never catastrophically fails"** -- claimed after five runs,
  refuted by run 6 on the sixth.

### What is solid

- The loop runs end to end on a real 40-file migration with a 445-test
  oracle built from a real merged human PR: skill installed and verified
  per attempt, transcript ingested with real reasoning, booklet distilled
  and schema-validated, new version installed before the next attempt,
  arms verified identical every run.
- The booklet is genuinely self-taught and correct. v5 diagnosed its own
  catastrophe unprompted: *"Failed attempts corrupted Config classes with
  broad regex rewrites, producing invalid code such as `extra = .allow`
  ... Fix the first traceback directly, verify syntax immediately."*
  That is the right lesson, written by the system about itself.
- The fixture is calibrated: not one-shottable (attempt 1 scored 0 in
  every run), solvable (445/445 reached in 4 of 12 arm-runs), with
  partial credit that moves.

### The next experiment this points at

Not more runs of this design -- the variance swamps the effect. The
booklet knows the right lesson and the agent still does not follow it,
so the question is whether a SHORTER, purely-prohibitive booklet beats a
long prescriptive one. A 5,000-token procedure plausibly invites the
sweeping multi-file edits that cause the zeros, while cold, with nothing
to follow, fixes the first traceback and re-runs -- which is exactly
cold's monotone 0 -> 301 -> 420 -> 429 in run 5.

Test: pin v1 (1,962 tokens) against v11 (5,029) against v0 (565), warm
only, distillation off, >=6 balanced pairs. That varies length with
content held constant in kind, and it is the cheapest question left that
could change the design.

## 2026-09-18 — FIX: the best verified tree is kept across attempts

The six-run curve measured a coin flip, not a skill. Every run scored
~440 or 0, and a 0 was never a failed migration -- it was a bulk edit
that left a syntax error, so `import` failed, the suite stopped
collecting, and because attempts share ONE checkout every later attempt
began from broken code. Warm went 311 -> 0, 0, 0 in one run; cold went 0
six times in another. Runs 5 and 6 were the same configuration and
landed on opposite arms.

**The agents had no version control.** A developer keeps their best
working commit; these agents could only build forward on whatever the
last attempt left, however broken.

### What changed

| where | change |
|---|---|
| `agent_workspace.py` | `init_history()` (git repo + pristine commit), `checkpoint(label)`, `restore_best()` |
| `run.py` | `init_history()` for EVERY agent, right after `seed`, before the warm-only branch |
| `vibe_agent.py` | after each graded attempt: checkpoint if it improved, roll back if it regressed or was rejected |
| `events.py` | `RESTORED` is a declared event, so rollbacks are countable |

The rule is the developer's one: keep the best working version, start the
next change from it. Applied to **both arms identically**, decided on the
ORCHESTRATOR's own pytest verdict rather than the agent's belief, and
charged to `off_clock` because it is bookkeeping, not thinking.

A **rejected** attempt is rolled back too. Its tree shimmed `pydantic.v1`
or gutted a validator, so it is not a state to build on however many
tests it passes.

### Two details that would have made it a no-op

- **`git clean -fd`, not just `reset --hard`.** An attempt that ADDS a
  broken module leaves it untracked; a plain reset keeps it and the same
  ImportError greets the next attempt -- a restore that restores nothing.
  Pinned by a test and exercised in the rehearsal.
- **`RESTORED` had to be a declared event.** The existing
  `test_every_emitted_event_is_a_declared_event_type` caught the new emit
  immediately. A silent rollback is indistinguishable from an agent that
  recovered by itself, which would have been a worse lie than the bug.

### Verified

- 230 tests pass (4 new).
- Rehearsal **36/36**, including a new step-0 probe that breaks a tracked
  file AND adds an untracked broken one, then checks the rollback undoes
  both against real git as the agent user.
- That probe caught its own bug first: it assumed the fixture's layout in
  a rehearsal that never seeds a repo, so the redirect failed silently
  and the check passed against an empty string. Now self-contained.

### Not yet run on GPU

The pod is terminated and re-provisioning costs money, so this is
verified locally only. The next run is the test: if the zeroes disappear
and both arms become monotone, the curve starts measuring the booklet
instead of the coin flip. `RESTORED` counts say how often it fired.

## 2026-09-18 — post-fix run 1, and the hole in the rollback

New pod `flmxn2v5chlms2` (H200, CUDA 13.0, EUR-IS-4, $4.59/hr). Control
test 4/4 non-empty, all four concurrent in 2.1s, 119 tok/s.

| arm | per-attempt | best /445 |
|---|---|---|
| warm (v0 -> v4) | 0, 0, 432, **441** | 441 |
| cold | 0, 0, 0, 0 | 0 |

Warm was monotone and reached 441. Cold never started.

### The rollback never fired -- zero RESTORED events

The rule was "roll back if this attempt scored worse than the best so
far". **On a fixture whose baseline is 0, a tree the agent broke scores
exactly what the untouched tree scores**, so `passed < previous_best` is
never true and the mechanism is dead precisely where it is needed. Cold
went 0, 0, 0, 0 with `IndentationError: unexpected indent` as its
signature and not one rollback was emitted.

The first version fixed the case that is easy to see (peak, then crash)
and missed the case that is common (broken from the start, and 0 is
indistinguishable from "not migrated yet").

### Fixed: a syntax error is a regression by definition

The pre-migration fixture PARSES -- its failure is a pydantic error
raised at import, not a `SyntaxError` -- so a syntax error in a graded
tree can only have been introduced by the agent, whatever the test count
says.

    _SYNTAX_ERRORS = ("SyntaxError", "IndentationError", "TabError")
    broke_syntax = signature.startswith(_SYNTAX_ERRORS)
    checkpoint if   not rejected and not broke_syntax and passed > best
    roll back if    rejected or broke_syntax or passed < best

Pinned against a real signature captured from the pod
(`'IndentationError: unexpected indent'`) and against the fixture's own
baseline (`PydanticUserError: \`const\` is removed`), which must NOT trip
it. The three rollback reasons stay distinguishable in the log.

### Three test failures I caused fixing it, all of the same kind

Assertions pinned to exact source text, each broken by a formatting
change rather than a behaviour change: the condition string, the emit
call once it line-wrapped, and a fixed 1,800-char window that stopped
reaching the line it checked once the comment above it grew. All three
rewritten to assert on ordering and presence instead of layout. Source
assertions are worth keeping -- they caught two real bugs this session --
but they must not encode whitespace.

231 tests, rehearsal 36/36.

## 2026-09-18 — CODE FROZEN for the series

Every run this session has been separated from the last by a code change,
which means no two runs were strictly comparable and the series kept
resetting. Stopping that.

**Frozen as of 12:30.** Hash of the behavioural files in `.freeze-hash`.
No edits to `orchestrator/` or `swarm/` until the series is reported. A
bug found during the series gets WRITTEN DOWN and the series continues;
the only reason to stop is something that invalidates a run outright.

### What is comparable

| runs | behavioural code | usable for |
|---|---|---|
| r1, r2 | before the syntax-rollback rule | not comparable to the rest |
| **r3, r4** | identical to frozen | tests_passed, attempts |
| r5+ | identical to frozen | those + `v1_remaining` |

The scoping fix changed a recorded NUMBER, not agent behaviour, so r3 and
r4 are valid on the primary metrics. Their `v1_remaining` is on the
unscoped scale (93-basis, +29 constant) and will not be plotted beside
the scoped ones.

Target: r3..r8, six runs, no changes.

## 2026-09-18 — stopped mid-run to fix two known defects (r6 killed)

Running a series against known-broken instrumentation wastes money and
produces numbers nobody can use. r6 was killed ~1 minute in.

### Defect 1: the agents were handed version control by accident

`init_history()` put a plain `.git` INSIDE the checkout. Observed on r5:
a cold attempt took the migration from 64 remaining constructs down to
**11**, and the next attempt came back at **63 with no RESTORED event**
-- the agent reverted the tree itself. Nobody decided to give the agents
git; it arrived as a side effect of the checkpoint mechanism.

Fixed: the history is a BARE repo at `~/.history`, driven with
`--git-dir` / `--work-tree`. The checkout contains no `.git`, so the
harness can roll back and the agent cannot.

### Defect 2: cold's failures were undiagnosable

The error signature was written only on `MEMORY_WRITE`, which is
warm-only. So r5's cold arm -- five straight attempts at 0 -- carried no
record of WHY, and the one number it did carry (`tests_passed=0`) is
exactly the number that cannot separate "not started" from "broken".

Fixed: `error_signature` on every `ATTEMPT_DONE`, both arms.

### Also recorded, not yet explained

r5 cold reached `v1_remaining=9` against a 64 baseline (floor 3) and
still scored 0 tests. Something other than v1 constructs is blocking
import. Defect 2 is what makes that answerable next run.

### Series status

r1-r5 are now historical. The comparable series restarts at r6 on the
re-frozen code (`.freeze-hash` updated). 238 tests, rehearsal 36/36.

| run | warm best | cold best | converged |
|---|---|---|---|
| r1 | 441 | 0 | neither |
| r2 | 436 | 445 | cold |
| r3 | 443 | 445 | cold |
| r4 | 311 | 445 | cold |
| r5 | 445 | 0 | warm |

Warm 1/5, cold 3/5. Bimodal both ways; no trend.

---

## 2026-09-18 — "Vibe does not fire hooks" was my own path shim

**47/47 in `scripts/rehearse_loop.py`, twice in a row. 238 tests pass.**
Tree uncommitted, local. No pod, $0/hr.

### The claim I made, and why it was wrong

I reported that Vibe ran no `post_tool` hook at all in the rehearsal --
evidenced by a canary hook, one that only appends to a file, never firing.
That is a statement about **Vibe**, and it is false. Twenty lines against
the real binary and the fake model server fire the canary first time:

```
"message": "Running hook canary" ... "Hook canary completed", "status":"ok"
CANARY: True   fired
```

The rule this breaks is already written down (*verify the wire, not the
wrapper*): I concluded "the host cannot do this" from "it did not happen
in my harness", without once running the host on its own. Vibe's own
`notice` stream entries (`hook_run_started`, `hook_started`,
`hook_completed`, with `status`) say per hook whether it ran and whether
it succeeded -- a better instrument than a canary file, and free.

### What was actually broken: `LocalHost._map` was not idempotent

```
python3: can't open file
'/…/rehearse-yuwxcu27/var/folders/…/rehearse-yuwxcu27/opt/swarm/reasoning_relay.py'
…
BrokenPipeError: [Errno 32] Broken pipe
```

`MSF_RELAY_PATH` and `MSF_HOOK_PATH` are deliberately set to files
*already* under the rehearsal root, because Vibe executes those itself and
they can never be mapped. So `{root}/opt/swarm/reasoning_relay.py` reached
`_map`, which blindly rewrote the `/opt/swarm/` inside it and produced a
doubled prefix. The relay never started, its end of `vibe | relay` closed,
and **Vibe died of a broken pipe on its first tool call** -- warm only,
every attempt, no error anywhere the harness looked. `_map` now refuses to
rewrite anything already inside the root.

The same trap was live in the distillation prompt: `out_path` is built as
`str(root) + distill_skill_path()`, so the distiller was being *told* to
write to a doubled path. It passed only because the scripted model writes
to the real path regardless of what the prompt says. Fixed by the same
guard.

### And the arms were sharing one scripted model queue

`FakeModelServer` repeats its final turn once exhausted. Both arms ran
concurrently against a single `"attempt"` script, so cold drained the
turns that make tool calls and warm was served the terminal turn. Warm
therefore made **zero tool calls**, which on its own is enough to produce
"no hook ever fired". One script per arm now, routed on the agent's own
checkout path -- Vibe puts `absolute path: /home/agent-<label>/repo` in
the system prompt -- and an unroutable call **raises** rather than
quietly draining the other arm's queue. `loaded_tools()`'s pre-clock probe
gets its own script for the same reason.

### Where the live write path now stands

```
attempt 1: source=live_hook steps=3
attempt 2: source=live_hook steps=3
```

Both attempts written to Aura **by Vibe's own `post_tool` hook while the
agent worked**, not back-filled: steps carry the model's reasoning (not
tool-argument JSON), tool calls are recorded, the canary fired, the run's
session holds only the run's messages, and entity extraction completes on
it. `hooks.toml` is warm-only and the fingerprint still proves it.

### Two bugs of mine caught before the pod, not on it

- `StepMemoryService(retrieval=args.retrieval)` referenced `args` outside
  its scope in `swarm/sidecar_main.py`: the sidecar would have died on
  startup, and it fails open, so the run would have recorded 0 steps and
  0 errors.
- A probe used blocking `subprocess.run` on the event loop and froze the
  in-process sidecar it was dialling, then reported that the hook could
  not reach the sidecar.

---

## 2026-09-18 — Daytona and GPU spend closed; oapi's oracle is real

**243 tests, rehearsal 47/47.** No pod, $0/hr.

### The arm-parity gate was measuring the wrong claim

`counts_toward_clearly_working` required the arms to differ by the SKILL
alone, so with memory back on the attempt path every run stamped
`NO (debug)`. The claim has always been **warm + memory + skill vs cold**
— warm's memory server, `post_tool` hook and their tools are the
*treatment*, not a confound. The set is now `metrics.TREATMENT_DIFFERENCES`,
imported by `swarm/run.py` so "what the harness permits" and "what the
table counts" cannot drift. The teeth are untouched: `assert_arms_match`
still refuses to start on anything outside the set, which is what catches
the two confounds that actually happened (warm-only `web`; warm's three
extra prompt steps). The summary now names which difference disqualified a
run rather than only that one did.

### `scripts/grade_fixture.py` — the answer key, on the real grader

The cheapest high-value check in the repo, generalised off `fixture/` and
run against the hard fixture for the first time:

```
tree                         exit  passed   v1     s  signature
baseline (pre-migration)        4       0   64  10.8  PydanticUserError: `const` is removed
answer key (reference_v2)       0     445    3  11.3  -
```

**Green is reachable on `fixtures/oapi`, and the floor is 3, not 0.** It
grades through `SandboxPool.run_pytest` and reads the verdict through
`vibe_agent.tests_passed`/`error_signature`, so it cannot drift from how a
run is actually graded. It refuses to run against a stale snapshot.

Noted, not fixed: the generated manifest header says "277-test oracle"
while the suite reports 445 passed + 4 skipped — build-time metadata
counting test functions before parametrisation. Harmless, but the 445 is
the number to quote.

### GPU spend

`--gpu-usd-per-hour`, rate x the run's own length off the event log, in the
table (`$/hr`, `run s`, `GPU $`) and the summary. **Absent rate prints `-`,
never `$0.00`** — "nobody recorded this" and "it was free" are different
facts and the table is read months later. It is the RUN's cost: provisioning
and the 113 GB model download happen before the first event and are
excluded, which the summary line says out loud.

`tests/test_metrics.py::_events` had no `t` on any event, so it was not
shaped like a real log and any time-derived metric read as zero. Fixed in
the fixture, not worked around in the assertion.

---

## 2026-09-18 — the measurements now emit chart-ready data

**259 tests, rehearsal 52/52.** No pod, $0/hr.

### `orchestrator/series.py` — the data layer, not the plots

The figures get rebuilt as React components later, and the thing that has
to survive that port is the DATA plus the domain knowledge stuck to it. If
"the floor is 3, not 0" lives in a matplotlib call it gets retyped by hand
into TypeScript, and that is where it becomes a y-axis starting at zero.

So the module emits a self-describing document: every panel carries its
kind, axis labels, arm colours, reference lines, and a `caveat` string
saying what would make it misleading. `scripts/plot_series.py` is a thin
generic renderer that switches on `panel["kind"]` and knows nothing about
pydantic, memory or skills — a panel added to the series appears in the
figures with no renderer change. The React component reads the same
document.

Nine within-run panels (convergence, per-attempt score, work remaining,
token burn, efficiency, memory activity, skill history, stability,
timeline) and four across-run (best-by-run with a fitted trend,
attempts-to-converge, cost, skill growth).

Everything is off `runs/<id>.jsonl`, so a charting bug cannot corrupt the
record it draws and rerunning gives the same document. The one exception
is `.oracle-<fixture>.json` — a measurement of the FIXTURE, written by
`grade_fixture.py`, which is where the reference lines come from.

### The honesty is in the data, and it is tested

`tests/test_series.py` is 16 tests, each one a way a chart could lie while
still being "correct":

- No graded fixture → **no reference line**, never a plausible-looking one.
- `attempts_to_converge` is **None** when a run never converged, and is
  drawn as a gap. Substituting the attempt count turns "never got there"
  into "got there on the last attempt".
- Best-so-far is monotone (the harness rolls back) but the **raw** score
  survives on the point, so a rollback stays visible.
- Efficiency is a scatter, not tokens-per-test: 70% of attempts score 0
  and the ratio is undefined for them.
- The effect is **paired** warm-minus-cold with a bootstrap 95% CI, and
  `crosses_zero` is in the data rather than left to the reader's eye.
  Under three runs it is `None`, not a mean with no interval.
- A log with **no RUN_END** is marked incomplete. Two H200s have died
  mid-run; "warm plateaued" and "the pod vanished" are the same shape on
  a chart otherwise.

Validated against the real r1–r5 logs: it reproduces the recorded table
exactly, and reports `+148.2 [-57.6, +354.0] over 5 runs — CROSSES ZERO:
no difference shown`. Which is the correct reading of those five runs.

### Two gaps in the plumbing, closed

- **RUN_END was declared in EVENT_TYPES and never emitted.** The event log
  had no terminal marker at all. It now carries the GPU, the model, the
  rate and the spend, so a chart drawn months later does not need the
  run's console output.
- The series document is now written automatically at the end of a run
  (`runs/<id>-series.json`), wrapped so a charting bug can never fail a
  graded run. A plotting step that has to be remembered is one that gets
  skipped on the run that mattered.

### Renderer bugs worth knowing

A reference line at the top of the data range (the answer key IS the
maximum) put its label outside the axes, `tight_layout` gave up on the
whole figure, and the thing it then overlapped was the caveat — the one
element that must stay readable. Labels now sit inside the axes, and the
caption's reserved space is computed from how many lines it wraps to.

---

## RESUME HERE — 2026-09-18, pod `0atxu1sop5dhva`

**A POD IS UP AND BILLING. DO NOT PROVISION ANOTHER. Terminate it when
the run series is done:** `mcp__runpod__delete-pod id=0atxu1sop5dhva`

| | |
|---|---|
| pod id | **`0atxu1sop5dhva`** (`msf-h200-e2e`) |
| GPU / DC | NVIDIA H200, 251 GB, 24 vCPU, US-NC-1, SECURE |
| host CUDA | 13.0 (exact, via `gpu.allowedCudaVersions`) |
| cost | **$4.59/hr**, created 2026-09-18 17:55 UTC |
| image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`, 300 GB disk |
| purpose | the first end-to-end run on `fixtures/oapi` with memory live |

### Run 1 on the H200 — the loop works end to end, and found two bugs

**The full path ran for the first time:** SGLang/Mistral-Small-4 → Vibe with
the skill → `post_tool` hook → sidecar → Aura → ingestion → AIP distillation
→ new skill installed → next attempt runs on it → Daytona verdict.

```
warm  a1 v14  0 tests  7 v1 left   31 steps written LIVE by the hook, 0 errors
      distil -> v15 ACCEPTED (1 repair, 44.9s, 10 memory tool calls, 44 traces)
      a3 v16  311 tests  5 v1 left
cold  a4      445 tests  4 v1 left  -> CONVERGED
```

`v1_remaining` did exactly the job it was added for: warm's first attempt
scored 0 tests but had cut 64 surfaces to 7, against cold's 12. Two attempts
that both "scored 0" were nothing like each other.

#### Bug 1: `bridge` was a free variable — NameError on the first attempt

`_attempt_until_done` read `bridge`, which is a local of `main_async`. It
raised on the first real attempt, *after* provisioning, a 113 GB download
and the control test had been paid for. The rehearsal cannot catch it: it
drives `migrate_codebase` directly and never enters that wrapper.

Now caught statically. `test_no_function_references_an_undefined_global`
walks each module's symbol table and fails on any function-level global
that exists in no enclosing scope. It would also have caught the sidecar's
`args.retrieval` bug. The scan found no other instances.

#### Bug 2: cold was never a party to the attempt barrier

`agent_label=ws.label if warm else None`, so cold arrived as
`"anonymous"`, which is not one of the barrier's parties — `arrive()`
returned 0.0 every time. Cold never synchronised; **warm waited at
barrier 1 from t=195 to t=776 for an arm that never came**, and was
released only when cold LEFT on converging. Warm took 2 attempts while
cold took 4, on a shared GPU: precisely the contention confound
`orchestrator/sync.py` exists to remove.

Safe to pass cold its real label because every memory-side use of it is
additionally gated on `step_memory is not None`. And `arrive()` no longer
passes an unrecognised name through in silence — it counts it
(`AttemptSync.strangers`) and logs that the comparison is contaminated.
Silence is what let this survive a whole pod run.

**Run 1's wall-clock comparison is therefore void** and it is kept as a
plumbing proof only. The numbers above are real; warm-vs-cold timing from
it is not.

### Runs 2 and 3, and the finding that matters

Three runs, `fixtures/oapi`, Mistral-Small-4 on one H200, ~3.2h, ~$14.7.

| run | warm best | cold best | skill | distillations |
|---|---|---|---|---|
| 1 | 445 (converged) | 445 (converged) | v14 -> v16 | 2/4 accepted |
| 2 | 0 | 0 | v16 -> v20 | 4/4 accepted |
| 3 | **346** | **0** | v20 -> v24 | 4/4 accepted |

Warm-minus-cold over three runs: **+115 [0, +346]** — crosses zero, so
three runs show no effect. Say that, do not round it to the sign.

#### THE DISTILLATION LOOP HAS NO FITNESS TEST, AND IT DEGRADED THE SKILL

| | v14 | v20 |
|---|---|---|
| words | 3,439 | 686 |
| steps | 24 | 11 |
| warm's first attempt | 64 -> **7** surfaces | 64 -> **63** |

v14 was hard-won and specific to what actually goes wrong here:
`treat-zero-tests-as-collection-failure`,
`fix-collection-blockers-before-inventory`,
`compare-corrupted-files-to-git-diff`,
`prefer-small-hand-edits-over-import-rewrite-scripts`. v20 is a generic
textbook checklist that opens with `verify-pydantic-v2-dependency` and
`grep-for-const-and-v1-patterns-before-editing`. In run 2 warm spent
6.4M tokens over four attempts and moved `v1_remaining` from 64 to 63 —
it never reached an edit.

**Every one of those rewrites was accepted.** `skills.propose()` gates on
exactly three things: a token cap, AIP schema validity, and the version
number. Nothing asks whether the new skill is better than the one it
replaces, or even whether it kept what the old one knew. The model's
natural move is to tidy and generalise, and tidying is precisely what
destroys distilled experience.

This is [[memory-amplifies-your-success-criterion]] arriving exactly where
that note said it would. It is also the most valuable thing the pod test
produced, and it is a DESIGN question, not a bug to patch quietly: the
options are a fitness gate (hold the old version until the new one beats
it — costs an A/B per distillation), a content-loss guard (refuse a
rewrite that discards most of the previous steps), or picking the
best-scoring version per run rather than the latest. Not chosen here.

Run 3 is the encouraging one and the barrier fix is visible in it: both
arms start each attempt together, and warm climbed 0 -> 0 -> 311 -> 346
across v20 -> v21 -> v22 -> v23 while cold stayed at 0 for five attempts.

#### Two more harness bugs, both fixed

- **`bus.close()` ran ~100 lines before the new RUN_END emit**, so run 2
  died with "I/O operation on closed file" after everything had printed.
  The log now closes last.
- **The summary's "the step hook is still live ... this run cannot be
  compared" warning was a redesign leftover.** The hook firing IS warm's
  treatment; that line fired on every healthy run and contradicted
  `counts_toward_clearly_working`. The alarm is now the other way round.
- The gantt panel declared `y_starts_at_zero`, and a bottom=0 clamp on an
  inverted axis hid 11 of 12 spans — a correct-data panel that read as
  "only cold ever ran".

Entity extraction hit its 240s bound and was abandoned on run 3; the
run's own numbers are unaffected, the graph has fewer entity edges.

**Pod `0atxu1sop5dhva` TERMINATED. `list-pods` empty, $0/hr.** Artifacts in
`pod-artifacts/h200-0atxu/final.tgz`.

---

## 2026-09-18 — AIP was installed HALF, and that silently weakened everything

**266 tests, rehearsal 52/52.** No pod, $0/hr.

Asked directly whether AIP was used as shipped. It was not, and the
consequences were larger than "I wrote my own prompt".

### What was installed, and what that cost

`skills/_aip/` held exactly two files: `validate.py` and
`validate_schema.py`. Both were byte-identical to upstream v0.3a3
(verified by sha256 against the tag), so the answer looked like yes. The
rest of the package -- `SKILL.md`, `references/`, `assets/` -- was absent.
Two consequences, both silent:

**1. Every skill version, v0 through v24, was INVALID AIP.**
`validate.py` derives the expected `metadata.aip.spec` from the AIP
PACKAGE's own SKILL.md and, per its own docstring, the check "gracefully
skips" when it cannot read one. Our skills declared
`https://arxiv.org/abs/2606.04781` -- the paper. AIP requires
`https://github.com/zach-blumenfeld/aip/tree/v0.3a3`. With the package
installed the live skill fails outright:

```
aip_spec_mismatch: `https://arxiv.org/abs/2606.04781` does not match the
AIP version this validator targets
```

Every distillation this project ever "accepted" passed a gate quieter
than AIP's. The URL is now DERIVED from the installed package
(`skills.aip_spec_url()`), never typed, so bumping AIP propagates and
drift is caught -- which is what AIP's README describes.

**2. The distiller worked from my authoring instructions, not AIP's.**
Including, unconditionally and with ~10,500 of 13,000 tokens spare:
*"Rewriting to be denser is better than appending."* That is the
compression ratchet. It is gone. The prompt now hands over AIP's shipped
`SKILL.md` and `skill-creation-best-practices.md` in full, and states the
cap as "a ceiling, not a target".

### AIP already ships the fix I was about to invent

Section 6.3 is a completeness check: walk the source material line by
line against the compiled body and classify every item as Mapped, Schema
gap, Body drop, or Deliberate drop, recording deliberate drops with
rationale. That is the content-loss gate, and it is AIP's, not mine. The
prompt now names the current version as source material and says plainly
that anything not carried forward is knowledge the agent loses for good.

### The author was the wrong model, and the flag was already there

`--distill-writer` defaulted to `"agent"`. All three pod runs took the
default, so **Mistral-Small-4 rewrote its own procedure** -- against AIP's
explicit guidance ("use the largest frontier model available when using
the AIP skill ... for consuming the resulting skill, the opposite
holds"). `ExternalWriter` and the `gpt-5.5` default already existed; the
capability was built and never switched on. The default is now
`writers.author_model()`, read from **`OPENAI_AUTHOR`**.

Measured, one real authoring turn against the live v24, no GPU:

| author | words | steps |
|---|---|---|
| Mistral-Small-4 (v14 -> v15) | 3,439 -> **721** | 24 -> **11** |
| gpt-5.6-sol (v24 -> proposal) | 886 -> **2,300** | 14 -> **23** |

The frontier author grew the procedure and the proposal validated first
time. It did NOT record deliberate drops as comments, so 6.3 is being
followed in spirit but not in artifact -- worth checking again on the
next real run.

### The trace window was a tail, not the history

`eligible[-12:]`: with 44 eligible traces, two thirds of the evidence --
including the attempts the best version was written from -- never reached
the prompt. Now all of them; one line each, a few hundred tokens.

### Two mistakes of mine while fixing this

- I read `OPENAI_AUTHOR` as an API key. It is the MODEL ID
  (`gpt-5.6-sol`). Corrected: model from `OPENAI_AUTHOR`, key from
  `OPENAI_API_KEY`.
- The authoring probe ran without `MSF_FIXTURE_DIR`, so `propose()`
  promoted its output and archived it into `skills/versions/` -- the
  DEFAULT fixture's lineage -- which is exactly the cross-lineage
  collision `versions_dir()` exists to prevent. The version was built
  from fabricated trace stubs, so it was removed and the live skill
  restored to v24. **Any probe that calls `propose()` must set
  `MSF_FIXTURE_DIR`.**

### Consequence for the three pod runs

They stand as proof that the machinery works end to end. They are **not**
evidence about skill quality: the author was the wrong model, the
procedure was mine rather than AIP's, the evidence window was truncated,
and the validator's spec check was disabled. The skill-evolution series
has to restart from a run authored by the frontier model.

---

## RESUME HERE — 2026-09-18 21:53 UTC, pod `eowqxi3391tmsz`

**A POD IS UP AND BILLING. DO NOT PROVISION ANOTHER.**
Terminate when done: `mcp__runpod__delete-pod id=eowqxi3391tmsz`

| | |
|---|---|
| pod id | **`eowqxi3391tmsz`** (`msf-h200-aip`) |
| GPU / DC | NVIDIA H200, 188 GB, 20 vCPU, EUR-IS-5, SECURE |
| cost | **$4.59/hr**, created 2026-09-18 21:53 UTC |
| purpose | first run series with AIP installed whole and the FRONTIER author |
| author | `gpt-5.6-sol` via OPENAI_AUTHOR (NOT the attempt model) |
| skill at start | v24, valid under the shipped validator |
