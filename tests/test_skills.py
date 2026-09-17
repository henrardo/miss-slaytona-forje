"""A proposed skill must be valid, bounded, and never silently accepted.

The skill is loaded into every warm attempt, so a bad version is not a
wasted turn -- it is a poisoned arm for the rest of the run. These pin the
three rules in orchestrator/skills.py: validate before accepting, cap the
size, and never lose a rejection.
"""
from __future__ import annotations

import shutil

import pytest

from orchestrator import skills


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the real skill package, so tests cannot damage the live one."""
    root = tmp_path / "skills"
    shutil.copytree(skills.SKILLS_DIR, root)
    monkeypatch.setattr(skills, "SKILLS_DIR", root)
    monkeypatch.setattr(skills, "VALIDATOR", root / "_aip" / "validate.py")
    return root


def _good_body(version: int) -> str:
    return f'''---
name: pydantic-v2-migration
description: A distilled procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2, written by the agent from its own graded attempts.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: {version}
    derived_from_traces: []
---

```yaml
purpose: >
  Migrate a codebase from Pydantic v1 to v2 so its own suite passes.
trigger_when:
  - Asked to migrate to Pydantic v2
steps:
  - name: run-the-suite
    description: Run the suite and read the first error.
```
'''


def test_v0_scaffold_is_valid() -> None:
    """The starting point must pass the real validator, or nothing else can."""
    ok, diag = skills.validate(skills.SKILLS_DIR / skills.SKILL_NAME)
    assert ok, f"the v0 scaffold does not validate: {diag}"


def test_v0_carries_no_migration_answer() -> None:
    """The skill must come only from the agent's own distillation.

    v0 names the two gaming patterns the grader already rejects, which the
    agent is told anyway. It must not contain the actual fix -- if it did,
    warm's advantage would be mine, not the agent's."""
    text = (skills.SKILLS_DIR / skills.SKILL_NAME / "SKILL.md").read_text().lower()
    for leak in ("pydantic_settings", "basesettings has been moved",
                 "field_validator", "model_validator", "model_config",
                 "email_validator", "validate_email", "configdict"):
        assert leak not in text, (
            f"v0 contains {leak!r} -- that is the migration answer, and it "
            f"must be distilled by the agent rather than written by hand"
        )


def test_a_valid_proposal_is_accepted_and_archived(sandbox) -> None:
    result = skills.propose(_good_body(1), derived_from=["trace-a"])
    assert isinstance(result, skills.SkillVersion), getattr(result, "detail", result)
    assert result.version == 1
    assert result.path.exists()
    assert skills.current().version == 1


def test_an_invalid_proposal_keeps_the_previous_version(sandbox) -> None:
    before = skills.current()
    result = skills.propose("this is not a skill at all", derived_from=[])
    assert isinstance(result, skills.Rejection)
    assert result.reason == "invalid_schema"
    assert result.detail, "a rejection must carry the validator's diagnostics"
    assert skills.current().text == before.text, "the live skill was modified"


def test_an_oversized_proposal_is_rejected(sandbox) -> None:
    """The skill is prompt prefix on every attempt, so growth is per-attempt
    cost in the arm whose token count is the headline number."""
    before = skills.current()
    huge = _good_body(1).replace("Run the suite and read the first error.",
                                 "padding " * 4000)
    result = skills.propose(huge, derived_from=[], max_tokens=2000)
    assert isinstance(result, skills.Rejection)
    assert result.reason == "too_large"
    assert skills.current().text == before.text


def test_a_proposal_with_the_wrong_version_is_rejected(sandbox) -> None:
    """Version must advance by exactly one, or provenance in the graph stops
    lining up with the files on disk."""
    result = skills.propose(_good_body(7), derived_from=[])
    assert isinstance(result, skills.Rejection)
    assert result.reason == "wrong_version"


def test_rejection_keeps_the_proposal_for_the_repair_turn(sandbox) -> None:
    result = skills.propose("garbage", derived_from=[])
    assert isinstance(result, skills.Rejection)
    assert result.proposal == "garbage"


def test_yaml_block_is_extracted_from_chatty_output() -> None:
    """Models wrap answers in prose. A good proposal must not be rejected
    for packaging."""
    text = "Sure! Here is the improved skill:\n\n```yaml\npurpose: x\n```\n\nLet me know."
    assert skills.extract_yaml_block(text) == "purpose: x\n"
    assert skills.extract_yaml_block("no fence here") is None
