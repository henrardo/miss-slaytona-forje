# AIP skill layer, archived 2026-09-20

Retired together with neo4j-agent-memory. Cognee replaces **both**: it owns
the memory layer *and* the skill lifecycle.

## What is here

| path | what it was |
|---|---|
| `skills/_aip/` | AIP v0.3a3, installed whole (`git clone --branch v0.3a3`). Its `scripts/validate.py` was the skill validator; `SKILL.md` was the authoring procedure handed to the distiller |
| `orchestrator/skills.py` | the version registry: `propose()`, `current()`, `archived()`, `package()`, lineage dirs, body/dir hashing |
| `orchestrator/distill.py` | the distillation turn: prompt building, `render_steps`, the repair loop, the progressive-disclosure pass |
| `orchestrator/writers.py` | `AgentWriter` / `ExternalWriter` — who authors the skill (`gpt-5.6-sol`) |
| `skills/live/` | the live package as it stood (v0 scaffold, restored) |
| `skills/versions*/` | **every distilled lineage**, 11 directories, oapi and x12sdk, including the two archived earlier today |
| `tests/` | `test_distill.py`, `test_skills.py`, `test_skill_loading.py` |
| `scripts/ab_skill.py` | the A/B skill harness |

## Why it was retired

Cognee ships the same loop as a documented product feature:

| ours | Cognee's, as shipped |
|---|---|
| `skills.package()` + `install_skill` | `remember(..., content_type="skills")`, or `skills_text=` + `skill_name=` |
| graded attempt -> `distill()` | `remember(SkillRunEntry(success_score=...))` — score is in [0.0, 1.0] |
| author a new version + validate + repair | `remember(..., skill_improvement={...})` -> `SkillImprovementProposal` |
| `propose()` accepting a version | `skill_improvement={"apply": True, "proposal_id": ...}` rewrites `skill.procedure` |
| `render_steps` feeding the author | `_find_recent_failure_runs(score_threshold=0.5, max_runs=5)` |

The structural difference to remember: **Cognee's skills live in the graph,
not on disk.** Our Vibe agents read `SKILL.md` from `$VIBE_HOME/skills/`, so
the harness now reads the improved procedure back out of Cognee and writes
the file, rather than owning the version registry itself.

## What is lost, and it should be stated

- **AIP conformance.** Cognee's skill format is its own; nothing in it
  validates `metadata.aip.version` or the progressive-disclosure contract.
  The standing instruction was "USING AIP AS SHIPPED" — that constraint is
  superseded by Henry's 2026-09-20 decision that Cognee replaces both
  layers, not quietly dropped.
- **The version lineage.** Cognee rewrites `skill.procedure` in place. There
  is no v001/v002/v003 archive unless the harness keeps writing one.
- Progressive disclosure and the `references/` tier, which the model never
  read anyway — see the memory note `why-the-skill-looked-useless`.
