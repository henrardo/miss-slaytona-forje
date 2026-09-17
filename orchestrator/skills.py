"""Versioned AIP skills: validate, size-cap, persist, and record provenance.

The warm agent writes these itself, after each attempt, off the clock. This
module is the part that does not involve the model: it decides whether a
proposed skill is acceptable, what version it becomes, and how it is linked
back to the traces it came from.

Three rules, each one guarding a failure this project has already had:

  * VALIDATE BEFORE ACCEPTING. The validator is the workshop's own
    (skills/_aip/validate.py), used verbatim. An invalid proposal is
    rejected and the previous version stays live -- a skill is loaded into
    every subsequent attempt, so accepting a broken one poisons the arm
    rather than just wasting a turn.

  * CAP THE SIZE. A distiller asked to improve a document will lengthen it.
    The skill is prompt prefix on every warm attempt, so unbounded growth
    is unbounded token cost, and it is the arm whose token count is the
    headline number.

  * NEVER SILENTLY KEEP A REJECTION. Every rejection is written down with
    the validator's own diagnostics, because "the skill did not change" and
    "the skill could not be parsed" look identical from the outside.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
VALIDATOR = SKILLS_DIR / "_aip" / "validate.py"
SKILL_NAME = "pydantic-v2-migration"

# Tokens, approximated at 4 chars each. The mission starts this at ~2,000.
# It is a ceiling on what the agent pays to carry its own procedure into
# every attempt, not a target.
DEFAULT_MAX_TOKENS = 2000


@dataclass
class SkillVersion:
    version: int
    path: Path
    text: str
    sha: str
    approx_tokens: int
    derived_from: list[str]


@dataclass
class Rejection:
    """Why a proposal did not become the live version. Always recorded."""
    reason: str
    detail: str
    proposal: str


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def approx_tokens(text: str) -> int:
    return len(text) // 4


def versions_dir() -> Path:
    return SKILLS_DIR / "versions"


def current(skill_name: str = SKILL_NAME) -> SkillVersion:
    """The live skill. Falls back to the v0 scaffold on a fresh graph."""
    live = SKILLS_DIR / skill_name / "SKILL.md"
    text = live.read_text()
    meta = parse_frontmatter(text)
    aip = (meta.get("metadata") or {}).get("aip") or {}
    return SkillVersion(
        version=int(aip.get("version", 0)),
        path=live,
        text=text,
        sha=_sha(text),
        approx_tokens=approx_tokens(text),
        derived_from=list(aip.get("derived_from_traces") or []),
    )


def parse_frontmatter(text: str) -> dict[str, Any]:
    import yaml
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def validate(skill_dir: Path) -> tuple[bool, str]:
    """Run the AIP validator. Returns (ok, diagnostics).

    Diagnostics are the validator's own JSON Lines, handed to the distiller
    verbatim in a repair turn -- it is a better error message than anything
    paraphrased, and it is the contract the validator documents.
    """
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(skill_dir)],
        capture_output=True, text=True,
    )
    ok = proc.returncode == 0 and "INVALID" not in (proc.stdout or "")
    return ok, (proc.stderr or proc.stdout or "").strip()


def propose(
    body: str,
    *,
    derived_from: list[str],
    skill_name: str = SKILL_NAME,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SkillVersion | Rejection:
    """Accept `body` as the next version, or explain why not.

    Written to a scratch copy of the package first, so a rejected proposal
    never touches the live skill. Only on success is it promoted.
    """
    live_dir = SKILLS_DIR / skill_name
    cur = current(skill_name)
    next_version = cur.version + 1

    if approx_tokens(body) > max_tokens:
        return Rejection(
            reason="too_large",
            detail=(f"{approx_tokens(body)} tokens exceeds the {max_tokens} "
                    f"cap. The skill is prompt prefix on every warm attempt, "
                    f"so this is a per-attempt cost, not a one-off."),
            proposal=body,
        )

    # Staged under its OWN name in a temp parent: the validator requires
    # `name` to match the containing folder, so a ".staging-x" directory
    # fails for the wrong reason and would mask real errors.
    tmp_parent = Path(tempfile.mkdtemp(prefix="aip-stage-"))
    staged = tmp_parent / skill_name
    shutil.copytree(live_dir, staged)
    (staged / "SKILL.md").write_text(body)
    try:
        # Order matters for the repair message. If the frontmatter parsed,
        # a wrong version number is the more actionable complaint than a
        # schema dump. If it did not parse, the proposal is not a skill at
        # all and saying "expected version 1" would misdiagnose it.
        meta = parse_frontmatter(body)
        aip = (meta.get("metadata") or {}).get("aip") or {}
        if aip and int(aip.get("version", -1)) != next_version:
            return Rejection(
                reason="wrong_version",
                detail=(f"frontmatter metadata.aip.version is "
                        f"{aip.get('version')!r}; expected {next_version}"),
                proposal=body,
            )
        ok, diagnostics = validate(staged)
        if not ok:
            return Rejection(reason="invalid_schema", detail=diagnostics,
                             proposal=body)
        if not aip:
            return Rejection(
                reason="invalid_schema",
                detail="no metadata.aip frontmatter block",
                proposal=body,
            )
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)

    versions_dir().mkdir(parents=True, exist_ok=True)
    archived = versions_dir() / f"v{next_version:03d}-{skill_name}.md"
    archived.write_text(body)
    (live_dir / "SKILL.md").write_text(body)

    return SkillVersion(
        version=next_version, path=archived, text=body, sha=_sha(body),
        approx_tokens=approx_tokens(body), derived_from=list(derived_from),
    )


def extract_yaml_block(text: str) -> str | None:
    """The single fenced YAML block the validator requires.

    Models wrap answers in prose and in nested fences; this pulls the block
    out so a good proposal is not rejected for packaging."""
    m = re.search(r"```(?:yaml|yml)\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else None


async def record_in_graph(client, version: SkillVersion, *, provenance: dict) -> None:
    """(:Skill)-[:DERIVED_FROM]->(:ReasoningTrace), plus SUPERSEDES.

    Uses execute_write: the package's `query.cypher` refuses writes by
    design ("Only read-only Cypher queries are allowed").
    """
    await client.graph.execute_write(
        "MERGE (s:Skill {name: $name, version: $version}) "
        "SET s += $props "
        "WITH s "
        "OPTIONAL MATCH (p:Skill {name: $name, version: $version - 1}) "
        "FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | "
        "  MERGE (s)-[:SUPERSEDES]->(p))",
        {
            "name": SKILL_NAME,
            "version": version.version,
            "props": {
                "sha": version.sha,
                "approx_tokens": version.approx_tokens,
                **provenance,
            },
        },
    )
    for trace_id in version.derived_from:
        await client.graph.execute_write(
            "MATCH (s:Skill {name: $name, version: $version}) "
            "MATCH (t:ReasoningTrace) WHERE toString(t.id) = $tid "
            "MERGE (s)-[:DERIVED_FROM]->(t)",
            {"name": SKILL_NAME, "version": version.version, "tid": trace_id},
        )
