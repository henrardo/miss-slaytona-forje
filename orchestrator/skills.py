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

The skill also has to satisfy VIBE, which parses the same file with its own
schema and, on a mismatch, simply leaves the skill out of
`available_skills` -- at which point the `/skill-name` prefix on warm's
prompt stops being a skill load and becomes a stray line of text. That needs
no extra gate: both tools implement the same Agent Skills frontmatter rules,
so the AIP validator already rejects every name and description Vibe would.
VIBE_NAME_RE and VIBE_MAX_DESCRIPTION record Vibe's side of that so the
tests can hold the two together if either drifts.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
# The AIP package, installed as shipped: `git clone --branch v0.3a3
# https://github.com/zach-blumenfeld/aip.git`. The whole tree, not just the
# two validators -- the authoring skill is the half that was missing, and
# its absence is why the distiller was working from format instructions I
# wrote instead of the ones AIP ships. Verified byte-identical to the
# v0.3a3 tag.
AIP_DIR = SKILLS_DIR / "_aip"
VALIDATOR = AIP_DIR / "scripts" / "validate.py"
# AIP's own authoring procedure, handed to whoever writes a skill version.
AIP_SKILL = AIP_DIR / "SKILL.md"
AIP_BEST_PRACTICES = AIP_DIR / "references" / "skill-creation-best-practices.md"

# AIP's own convention, read off the installed package rather than typed
# here (validate_schema.AIP_SPEC_URL_PREFIX + the package's declared
# version).
_AIP_SPEC_URL_PREFIX = "https://github.com/zach-blumenfeld/aip/tree/v"


def aip_spec_url() -> str:
    """The `metadata.aip.spec` value the installed AIP validator demands.

    DERIVED, NEVER TYPED. Every skill version this project produced, v0
    through v24, carried `https://arxiv.org/abs/2606.04781` -- the paper,
    not the spec. AIP's validator computes the expected URL from the AIP
    package's OWN SKILL.md, and only the two validator scripts were
    installed, so that lookup returned None and the check "gracefully
    skipped" exactly as its docstring says it would. Every distillation
    this project ever accepted passed a gate quieter than AIP's.

    Deriving it means bumping the pinned AIP version updates the skills
    too, which is the drift-detection AIP's own README describes.
    """
    try:
        meta = parse_frontmatter(AIP_SKILL.read_text())
    except OSError as exc:
        raise RuntimeError(
            f"the AIP package is not installed at {AIP_DIR}. Install it as "
            f"shipped: git clone --depth 1 --branch <tag> "
            f"https://github.com/zach-blumenfeld/aip.git {AIP_DIR}"
        ) from exc
    version = ((meta.get("metadata") or {}).get("aip") or {}).get("version")
    if not version:
        raise RuntimeError(
            f"{AIP_SKILL} carries no metadata.aip.version, so the spec URL "
            f"the validator expects cannot be derived.")
    return f"{_AIP_SPEC_URL_PREFIX}{version}"
SKILL_NAME = "pydantic-v2-migration"

# Tokens, approximated at 4 chars each. ~13,000 tokens is about 10,000
# words -- the instruction booklet the experiment is actually trying to
# grow, rather than the 2,000-token summary it started as.
#
# WHAT THIS COSTS, so the number is chosen and not inherited. The skill is
# prompt prefix on every warm attempt, and Vibe re-sends the conversation
# each turn, so a skill of S tokens adds roughly S x turns to the arm's
# prompt-token total. At the observed 60-90 turns per attempt, 2,000
# tokens cost warm ~0.15M per attempt against a 2-3M baseline -- noise.
# At 13,000 it is ~1M, which is a third of the attempt. So raising the cap
# MOVES THE HEADLINE METRIC: warm's token count stops being a fair
# comparison against cold and attempts-to-converge becomes the measure,
# which is what the harder task needs anyway.
#
# It is still a hard ceiling. An over-cap proposal is rejected outright
# and the previous version stays live, so the distiller is told its
# current size and remaining headroom and told to consolidate rather than
# append (see orchestrator/distill.py).
DEFAULT_MAX_TOKENS = 13000

# AIP'S OWN NUMBER, not one of mine.
#
# references/skill-creation-best-practices.md, "Structure large skills with
# progressive disclosure": "keeping `SKILL.md` under 500 lines and 5,000
# tokens -- just the core instructions the agent needs on every run. When a
# skill legitimately needs more content, move detailed reference material to
# separate files in `references/`."
#
# This is NOT a second cap. Nothing is rejected for exceeding it. It is the
# trigger for the relocation pass in orchestrator/distill.py: author freely
# first, then move detail out of the body and into `references/` with a
# load-when trigger, so the knowledge survives and only the per-turn cost
# falls. AIP's framing is the point -- "Body tokens cost every invocation;
# reference tokens cost only when loaded."
#
# The thing this replaces was a ratchet: my own prompt told the author
# "rewriting to be denser is better than appending" unconditionally, and one
# rewrite took the procedure from 24 steps to 11 with 10,500 of 13,000
# tokens still spare. Relocation, never deletion.
AIP_BODY_TARGET_TOKENS = 5000

# Vibe's own limits on a SKILL.md, copied from the installed package rather
# than guessed: vibe/core/skills/models.py, SkillMetadata.name (pattern) and
# .description (max_length). Verified against mistral-vibe 2.25.4 by loading
# this project's skill through Vibe's SkillManager.
VIBE_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VIBE_MAX_DESCRIPTION = 1024


# Build and editor droppings. They are not part of the skill, they differ
# between machines, and including them would make the version hash change
# without the skill changing.
_PACKAGE_EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache"}
_PACKAGE_EXCLUDE_NAMES = {".DS_Store"}
_PACKAGE_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

# Where AIP puts executable content. Everything under here is installed with
# the execute bit so the agent can actually run it; an AIP procedure whose
# steps have a `script:` is useless if the script is not executable.
SCRIPT_DIRS = ("scripts/",)


@dataclass
class SkillVersion:
    version: int
    path: Path
    text: str
    sha: str
    approx_tokens: int
    derived_from: list[str]
    files: dict[str, bytes] = field(default_factory=dict)

    @property
    def dir_sha(self) -> str:
        """Hash of the WHOLE skill package, not just SKILL.md.

        An AIP skill is a directory: SKILL.md plus `source/` (the bundled
        schema the validator resolves `schemaId` against) and optionally
        `scripts/`, `references/` and `assets/`. A version identified by
        SKILL.md alone would call two different packages the same version
        the moment a script or a reference changed underneath it.
        """
        return dir_sha(self.files or {"SKILL.md": self.text.encode()})

    @property
    def body_sha(self) -> str:
        """Hash of the part Vibe actually puts in the model's context.

        `sha` covers the whole file, frontmatter included. Vibe loads
        `SkillInfo.prompt`, which is the markdown body only, so this is the
        hash to compare a transcript against -- the checklist asks whether
        warm loaded the expected version, and the frontmatter never reaches
        the model to be checked.
        """
        return _sha(body_of(self.text))


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
    """Where this FIXTURE's skill lineage lives.

    Keyed on the active fixture because a skill is a procedure for a
    particular migration, and the version NUMBER is the only thing
    `propose` uses to name the next file. Shared, the two lineages
    collide destructively: starting a second fixture at v0 would write
    `v001-...md` straight over the first fixture's v1, and starting it
    from the first fixture's v12 would hand the new task a booklet
    written about a codebase it has never seen -- which is the seeding
    the experiment exists to avoid.

    The default fixture keeps the original path so nothing already
    recorded moves.
    """
    from orchestrator.manifest import FIXTURE_DIR
    if FIXTURE_DIR.name == "fixture":
        return SKILLS_DIR / "versions"
    return SKILLS_DIR / f"versions-{FIXTURE_DIR.name}"


def is_script(relative_path: str) -> bool:
    """Should this file be installed executable?

    Position, not extension: AIP's own layout puts runnable content in
    `scripts/`, and a `references/` note that happens to end in `.py` is
    documentation. Everything under `scripts/` gets the bit, including a
    data file a script reads -- harmless, and it keeps the rule to one
    sentence.
    """
    return relative_path.startswith(SCRIPT_DIRS)


def package(skill_name: str = SKILL_NAME) -> dict[str, bytes]:
    """The whole skill directory as relative path -> bytes.

    Everything AIP allows a skill to carry travels together: SKILL.md,
    `source/` with the bundled schema, and `scripts/`, `references/` and
    `assets/` if the distiller ever writes them. Shipping only SKILL.md
    would leave the agent holding a procedure whose steps reference files
    that are not there.
    """
    root = SKILLS_DIR / skill_name
    out: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if (set(rel.parts) & _PACKAGE_EXCLUDE_DIRS
                or path.name in _PACKAGE_EXCLUDE_NAMES
                or path.suffix in _PACKAGE_EXCLUDE_SUFFIXES):
            continue
        out[rel.as_posix()] = path.read_bytes()
    return out


def dir_sha(files: Mapping[str, bytes]) -> str:
    """One hash over a whole skill package.

    Over `path -> sha(content)` rather than over concatenated bytes, so a
    file RENAMED to the content of another does not hash the same, and so
    the value does not depend on iteration order.
    """
    import hashlib
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode())
        h.update(b"\0")
        h.update(hashlib.sha256(files[rel]).hexdigest().encode())
        h.update(b"\n")
    return h.hexdigest()[:12]


def archived(version: int, skill_name: str = SKILL_NAME) -> SkillVersion:
    """A specific past version, for holding the skill constant across runs.

    Exists for the one comparison warm-vs-cold cannot make. Cold differs
    from warm in more than the skill, so a gap between them cannot be
    attributed to skill CONTENT -- and measured over 8 runs it was not:
    warm converged 8/8 against cold's 5/8 even on v0, whose content the
    tests actively forbid containing any task knowledge.

    Varying only the version, with everything else fixed, is what isolates
    what distillation is actually worth.
    """
    path = versions_dir() / f"v{version:03d}-{skill_name}.md"
    if not path.exists():
        available = sorted(p.name for p in versions_dir().glob("v*.md"))
        raise FileNotFoundError(
            f"no archived skill v{version} at {path}. Available: {available}")
    text = path.read_text()
    meta = parse_frontmatter(text)
    aip = (meta.get("metadata") or {}).get("aip") or {}
    files = dict(package(skill_name))
    files["SKILL.md"] = text.encode()
    return SkillVersion(
        version=int(aip.get("version", version)), path=path, text=text,
        sha=_sha(text), approx_tokens=approx_tokens(text),
        derived_from=list(aip.get("derived_from_traces") or []), files=files)


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
        files=package(skill_name),
    )


_FRONTMATTER_BOUNDARY = re.compile(r"^-{3,}\s*$", re.MULTILINE)


def body_of(text: str) -> str:
    """The markdown body, split exactly as Vibe splits it.

    Mirrors vibe/core/skills/parser.py: a regex split on `---` boundaries,
    limited to two, body = the third piece. Reimplemented rather than
    imported because Vibe runs on the pod under python 3.12+ and the
    orchestrator does not; the regex and the maxsplit are the whole contract
    and a test pins them against the real thing.
    """
    parts = _FRONTMATTER_BOUNDARY.split(text.lstrip("﻿"), 2)
    return (parts[2] if len(parts) >= 3 else text).strip()


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
    references: dict[str, str] | None = None,
    replace: bool = False,
) -> SkillVersion | Rejection:
    """Accept `body` as the next version, or explain why not.

    `replace=True` targets the CURRENT version instead of allocating a new
    one, overwriting its archived file. One attempt must leave exactly one
    version behind, and without this it left two: the authored body, then
    AIP's progressive-disclosure pass reshaping that same body. Over the
    2026-09-20 experiment that turned 42 distillations into 81 numbered
    files and ran warm's attempts on v2, v4, v6, v8. Reshaping an accepted
    procedure is not a new procedure.

    Written to a scratch copy of the package first, so a rejected proposal
    never touches the live skill. Only on success is it promoted.

    `references` is AIP's second tier: {"references/x.md": text}, loaded by
    the agent on demand rather than on every turn. Passed here rather than
    written by the caller so that the relocation pass is validated as ONE
    package -- a body whose load-when trigger points at a file that did not
    travel is worse than a long body, and the validator is the only thing
    that sees both halves at once.
    """
    # ONE WRITER AT A TIME. With more than one warm agent, two distillation
    # turns finish at once, both read version N, and both write N+1 -- so
    # one version silently overwrites the other and the graph records two
    # skills with the same number and different content. The lock is held
    # across read-version-validate-write, not just the write, because the
    # race is in the read.
    #
    # An OS file lock rather than an asyncio one: propose() is synchronous
    # and may be called from separate processes (a rerun, a repair script),
    # and a lock that only covers this event loop would not be a lock.
    with _version_lock():
        return _propose_locked(body, derived_from=derived_from,
                               skill_name=skill_name, max_tokens=max_tokens,
                               references=references, replace=replace)


@contextlib.contextmanager
def _version_lock():
    versions_dir().mkdir(parents=True, exist_ok=True)
    path = versions_dir() / ".lock"
    with open(path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _propose_locked(
    body: str,
    *,
    derived_from: list[str],
    skill_name: str = SKILL_NAME,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    references: dict[str, str] | None = None,
    replace: bool = False,
) -> SkillVersion | Rejection:
    live_dir = SKILLS_DIR / skill_name
    cur = current(skill_name)
    # `replace` rewrites the version that is already live; otherwise this
    # is the next one. Everything downstream -- the frontmatter check, the
    # archived filename, the returned SkillVersion -- keys off this single
    # number, so the two paths cannot drift.
    next_version = cur.version if replace else cur.version + 1

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
    # The relocation pass REPLACES the reference tier rather than adding to
    # it: a stale references/ file the new body no longer points at is dead
    # weight in the package and a trap for the next author, who reads the
    # directory as source material.
    if references is not None:
        shutil.rmtree(staged / "references", ignore_errors=True)
        for rel, text in references.items():
            dest = staged / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
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
        # No separate Vibe check here on purpose. Both tools implement the
        # same Agent Skills frontmatter rules, so the validator above already
        # rejects every name and description Vibe would refuse -- see
        # VIBE_NAME_RE and the tests that pin the two together.
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)

    versions_dir().mkdir(parents=True, exist_ok=True)
    archived = versions_dir() / f"v{next_version:03d}-{skill_name}.md"
    archived.write_text(body)
    (live_dir / "SKILL.md").write_text(body)
    if references is not None:
        shutil.rmtree(live_dir / "references", ignore_errors=True)
        for rel, text in references.items():
            dest = live_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)

    return SkillVersion(
        version=next_version, path=archived, text=body, sha=_sha(body),
        approx_tokens=approx_tokens(body), derived_from=list(derived_from),
        # The WHOLE package, read back after the write above, exactly as
        # `current()` and `archived()` return it. Left empty, this was the
        # one SkillVersion in the module that could not be installed: the
        # caller has an accepted version in hand and no files to ship, so
        # `dir_sha` silently fell back to SKILL.md alone and any attempt to
        # put it on the pod would have installed an empty directory.
        files=package(skill_name),
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


def identify(loaded_text: str, skill_name: str = SKILL_NAME) -> int | None:
    """Which archived version's body is present in this transcript text.

    The post-run checklist used to compare the transcript against the
    version the run STARTED on, which stopped being true the moment
    distillation worked: run 10 began on v5, its attempts loaded v5, v6
    and v7, and the check reported "skill v5 reached 0/1 warm agents" --
    a false negative that reads in the record as a skill that never
    reached the model, which is the exact failure it exists to detect.

    Highest version first: a later body is the more specific match, and
    reporting the earliest containing version would understate how far
    the skill had advanced.
    """
    for path in sorted(versions_dir().glob(f"v*-{skill_name}.md"), reverse=True):
        body = body_of(path.read_text()).strip()
        if body and body in loaded_text:
            return int(path.name[1:4])
    return None
