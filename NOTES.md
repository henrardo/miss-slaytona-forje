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
