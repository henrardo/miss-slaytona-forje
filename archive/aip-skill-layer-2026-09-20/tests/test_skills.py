"""A proposed skill must be valid, bounded, and never silently accepted.

The skill is loaded into every warm attempt, so a bad version is not a
wasted turn -- it is a poisoned arm for the rest of the run. These pin the
three rules in orchestrator/skills.py: validate before accepting, cap the
size, and never lose a rejection.
"""
from __future__ import annotations

import re
import shutil

import pytest

from orchestrator import skills


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the real skill package, so tests cannot damage the live one."""
    root = tmp_path / "skills"
    shutil.copytree(skills.SKILLS_DIR, root)
    monkeypatch.setattr(skills, "SKILLS_DIR", root)
    monkeypatch.setattr(skills, "VALIDATOR", root / "_aip" / "scripts" / "validate.py")
    return root


def _good_body(version: int) -> str:
    return f'''---
name: pydantic-v2-migration
description: A distilled procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2, written by the agent from its own graded attempts.
metadata:
  aip:
    spec: "{skills.aip_spec_url()}"
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


# The ARCHIVED v0 scaffold, not the live file. Distillation overwrites the
# live SKILL.md, so from the first accepted version onward these two tests
# would be reading the AGENT's skill and asserting things that are only
# true of the starting point. v1 legitimately contains `field_validator`
# and `model_config` -- the agent wrote them, which is the entire result.
#
# The property still has to hold, so it is checked against the thing it is
# about: skills/versions/v000-*.md, recovered from git and frozen.
V0 = skills.versions_dir() / "v000-pydantic-v2-migration.md"


def test_the_v0_scaffold_is_archived() -> None:
    """Without it, the two tests below silently start testing the agent's
    own output instead of the scaffold."""
    assert V0.exists(), (
        "the v0 scaffold is missing from skills/versions/. Recover it with "
        "`git show <commit>:skills/pydantic-v2-migration/SKILL.md`; the two "
        "tests below are meaningless without it.")
    meta = skills.parse_frontmatter(V0.read_text())
    assert (meta["metadata"]["aip"]["version"]) == 0


def test_v0_scaffold_is_valid(tmp_path) -> None:
    """The starting point must pass the real validator, or nothing else can."""
    staged = tmp_path / skills.SKILL_NAME
    shutil.copytree(skills.SKILLS_DIR / skills.SKILL_NAME, staged)
    (staged / "SKILL.md").write_text(V0.read_text())
    ok, diag = skills.validate(staged)
    assert ok, f"the v0 scaffold does not validate: {diag}"


def test_v0_carries_no_migration_answer() -> None:
    """The skill must come only from the agent's own distillation.

    v0 names the two gaming patterns the grader already rejects, which the
    agent is told anyway. It must not contain the actual fix -- if it did,
    warm's advantage would be mine, not the agent's."""
    text = V0.read_text().lower()
    for leak in ("pydantic_settings", "basesettings has been moved",
                 "field_validator", "model_validator", "model_config",
                 "email_validator", "validate_email", "configdict"):
        assert leak not in text, (
            f"v0 contains {leak!r} -- that is the migration answer, and it "
            f"must be distilled by the agent rather than written by hand"
        )


def test_a_valid_proposal_is_accepted_and_archived(sandbox) -> None:
    """Relative to whatever is live: the real skill advances every run, so
    a hard-coded `== 1` starts failing the moment the agent distils."""
    nxt = skills.current().version + 1
    result = skills.propose(_good_body(nxt), derived_from=["trace-a"])
    assert isinstance(result, skills.SkillVersion), getattr(result, "detail", result)
    assert result.version == nxt
    assert result.path.exists()
    assert skills.current().version == nxt


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
    huge = _good_body(before.version + 1).replace(
        "Run the suite and read the first error.",
                                 "padding " * 4000)
    result = skills.propose(huge, derived_from=[], max_tokens=2000)
    assert isinstance(result, skills.Rejection)
    assert result.reason == "too_large"
    assert skills.current().text == before.text


def test_a_proposal_with_the_wrong_version_is_rejected(sandbox) -> None:
    """Version must advance by exactly one, or provenance in the graph stops
    lining up with the files on disk."""
    result = skills.propose(_good_body(skills.current().version + 7),
                            derived_from=[])
    assert isinstance(result, skills.Rejection)
    assert result.reason == "wrong_version"


def test_rejection_keeps_the_proposal_for_the_repair_turn(sandbox) -> None:
    result = skills.propose("garbage", derived_from=[])
    assert isinstance(result, skills.Rejection)
    assert result.proposal == "garbage"


def test_anything_vibe_would_refuse_is_already_rejected(sandbox) -> None:
    """A skill Vibe will not parse is absent from available_skills, so the
    `/skill-name` prefix on warm's prompt loads nothing and the run reads as
    a model that ignored its own procedure.

    No separate Vibe gate exists, because both tools implement the same Agent
    Skills frontmatter rules. This is what makes that claim safe to rely on:
    the two inputs Vibe refuses must be refused here too.
    """
    live = skills.current().version
    over_cap = "x" * (skills.VIBE_MAX_DESCRIPTION + 1)
    long_desc = re.sub(r"description: .*", f"description: {over_cap}",
                       _good_body(live + 1), count=1)
    assert over_cap in long_desc, "the fixture's description line did not match"
    bad_name = _good_body(live + 1).replace("name: pydantic-v2-migration",
                                            "name: Pydantic_V2_Migration", 1)
    for label, proposal in (("description over Vibe's cap", long_desc),
                            ("name Vibe's pattern rejects", bad_name)):
        result = skills.propose(proposal, derived_from=[])
        assert isinstance(result, skills.Rejection), (
            f"{label} was ACCEPTED; Vibe would not have loaded it")
        assert result.reason == "invalid_schema"
        assert skills.current().version == live, "the live skill was advanced"


def test_v0_satisfies_vibes_limits() -> None:
    """The scaffold has to load in Vibe, not just validate against AIP."""
    meta = skills.parse_frontmatter(
        (skills.SKILLS_DIR / skills.SKILL_NAME / "SKILL.md").read_text())
    assert skills.VIBE_NAME_RE.match(str(meta["name"]))
    assert len(str(meta["description"])) <= skills.VIBE_MAX_DESCRIPTION


def test_body_is_what_vibe_puts_in_the_context() -> None:
    """Vibe loads SkillInfo.prompt -- the markdown body, not the file.

    Pinned against mistral-vibe 2.25.4's own parser
    (vibe/core/skills/parser.py: a `^-{3,}$` split with maxsplit=2, body =
    the third piece), checked by loading this project's SKILL.md through
    Vibe's SkillManager. The frontmatter never reaches the model, so a hash
    over the whole file cannot answer "did warm load this version?".
    """
    text = "---\nname: x\ndescription: y\n---\n\nbody line\n"
    assert skills.body_of(text) == "body line"
    live = skills.current()
    assert live.body_sha != live.sha
    assert skills.body_of(live.text).startswith("```yaml")


def test_yaml_block_is_extracted_from_chatty_output() -> None:
    """Models wrap answers in prose. A good proposal must not be rejected
    for packaging."""
    text = "Sure! Here is the improved skill:\n\n```yaml\npurpose: x\n```\n\nLet me know."
    assert skills.extract_yaml_block(text) == "purpose: x\n"
    assert skills.extract_yaml_block("no fence here") is None


def test_an_archived_version_can_be_loaded_for_a_controlled_run() -> None:
    """Warm-vs-cold cannot attribute a gap to skill CONTENT -- cold differs
    in more than the skill, and over 8 runs warm converged 8/8 against
    cold's 5/8 even on v0, which is forbidden from containing any task
    knowledge. Varying only the version isolates what distillation buys."""
    v0 = skills.archived(0)
    assert v0.version == 0
    assert v0.files["SKILL.md"] == v0.text.encode()
    # The rest of the package travels with it, or the validator's schema
    # reference goes missing.
    assert any(k.startswith("source/") for k in v0.files)
    # What `archived` must guarantee is that it reads the ARCHIVE, not the
    # live pointer -- so it is pinned against the file on disk. Comparing
    # it to `current()` instead only worked while the lineage happened to
    # have advanced, and broke the moment a fixture was reset to v0.
    on_disk = (skills.versions_dir() / "v000-pydantic-v2-migration.md").read_text()
    assert v0.text == on_disk
    live = skills.current()
    if live.version != 0:
        assert v0.dir_sha != live.dir_sha, (
            "archived(0) returned the live skill rather than the archive")


def test_a_missing_archived_version_says_what_is_available() -> None:
    import pytest as _pytest
    with _pytest.raises(FileNotFoundError, match="Available:"):
        skills.archived(999)


def test_the_aip_package_is_installed_as_shipped() -> None:
    """The whole package, not just the two validator scripts.

    Only `validate.py` and `validate_schema.py` were installed. The
    authoring half -- SKILL.md, the best-practices guide, the schemas --
    was missing, with two consequences that ran for the project's whole
    life:

      1. The distiller worked from format instructions written in this
         repo instead of AIP's own authoring procedure, including a
         "rewriting to be denser is better than appending" line that
         collapsed the skill from 24 steps to 11 in a single rewrite.
      2. `validate.py` derives the expected `metadata.aip.spec` from the
         PACKAGE's SKILL.md and "gracefully skips" the check when it
         cannot read one. Every version, v0 to v24, declared the arXiv
         paper URL and passed a check that never ran.
    """
    assert skills.AIP_DIR.is_dir(), f"no AIP package at {skills.AIP_DIR}"
    for rel in ("SKILL.md", "scripts/validate.py", "scripts/validate_schema.py",
                "references/skill-creation-best-practices.md",
                "references/author-schema.md",
                "assets/aip-schemas/procedure.schema.json"):
        assert (skills.AIP_DIR / rel).is_file(), f"AIP package missing {rel}"
    # The spec URL must be derivable, which is the thing whose absence
    # silently disabled the check.
    assert skills.aip_spec_url().startswith("https://github.com/zach-blumenfeld/aip/tree/v")


def test_the_live_skill_validates_under_the_shipped_validator() -> None:
    """The skill every warm attempt loads must actually be a valid AIP
    skill. This is the cheapest check in the repo and it was never made:
    with the package half-installed it passed while the live skill
    carried a `metadata.aip.spec` the validator would reject."""
    ok, diag = skills.validate(skills.SKILLS_DIR / skills.SKILL_NAME)
    assert ok, f"the live skill does not validate: {diag}"


def test_no_skill_hard_codes_the_spec_url() -> None:
    """Derived from the installed package, never typed.

    AIP's own README describes this: bumping the protocol version must
    propagate, and drift is caught rather than carried. A literal URL in
    a `spec:` assignment is a copy that goes stale the moment AIP is
    bumped -- and the copy that was here was wrong from the start, which
    is how every version v0..v24 declared the arXiv paper as the spec.

    Matches an ASSIGNMENT only. Prose that names the old URL while
    explaining the bug is the record, not a recurrence.
    """
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    # `spec: "http..."` or `spec="http..."`, i.e. a value being set.
    assign = re.compile(r"""spec\s*[:=]\s*["']https?://""")
    offenders = []
    for path in sorted(root.glob("orchestrator/*.py")) + sorted(root.glob("swarm/*.py")) \
            + sorted(root.glob("scripts/*.py")) + sorted(root.glob("tests/*.py")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if assign.search(line):
                offenders.append(f"{path.name}:{n}: {line.strip()[:70]}")
    assert not offenders, (
        "a spec URL is hard-coded; derive it with skills.aip_spec_url():\n  "
        + "\n  ".join(offenders))

    # And the live skill's own value must be the derived one.
    live = (skills.SKILLS_DIR / skills.SKILL_NAME / "SKILL.md").read_text()
    assert skills.aip_spec_url() in live
