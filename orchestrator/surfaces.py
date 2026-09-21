"""How much pydantic v1 is left in a tree.

WHY THIS EXISTS. The test suite is the oracle, and it has one blind spot
that makes it unusable as a PROGRESS measure: every one of the fixture's
445 tests imports the package, so if the package does not import the
score is 0 -- and 0 means two opposite things.

    migration not started yet   the package raises PydanticUserError on
                                import. This is the STARTING state.
    agent destroyed the code    the package raises IndentationError on
                                import. This is the FAILURE state.

Measured over 77 graded attempts: 70% scored exactly 0, 13% scored ~300,
17% scored >=420. Three states, and seven attempts in ten land in the one
that cannot distinguish progress from damage. No skill effect is visible
through that.

This counts what is left to migrate by reading the SOURCE instead of
running it. It is defined when the package does not import, does not
parse, or does not exist, so it grades an attempt that fixed 12 of 40
sites as progress rather than as nothing.

THE FLOOR IS NOT ZERO, and the number is only readable against it.
Measured on this fixture: the pre-migration source counts 64 and the
human's own merged answer still counts 3 -- two `response.json()` calls
inside generated-code string literals (httpx, nothing to do with
pydantic) and one unrelated `class Config`. So 64 -> 3 is a COMPLETED
migration. Anything that reports this number must report the reference's
count beside it, or 3 reads as "almost done" when it means "done".

It is NOT an oracle and must never be used as one: the count going to
zero does not mean the migration is correct, only that the v1 spellings
are gone. The suite remains the only thing that decides success. This
decides whether an attempt MOVED.
"""
from __future__ import annotations

import re

# One definition, shared by the fixture scorer (scripts/make_fixture.py)
# and by the running harness. Two copies would drift, and then "surfaces
# present in this fixture" and "surfaces left in this tree" would be
# different questions wearing the same name.
#
# Each entry is a v1-ONLY spelling: something that must change for the
# migration to be real. Patterns that also match valid v2 code would make
# the count bottom out above zero and stop being readable.
SURFACES: dict[str, str] = {
    "class Config": r"^\s*class Config\b",
    "Extra./allow_mutation": r"\bExtra\.|allow_mutation",
    "Field(const/regex/items)":
        r"Field\([^)]*\b(?:const|regex|allow_mutation|min_items|max_items)\b",
    "update_forward_refs": r"\bupdate_forward_refs\b",
    "parse_obj/parse_raw/parse_file": r"\b(?:parse_obj|parse_raw|parse_file)\b",
    ".dict()/.json()": r"\.dict\(\)|\.json\(\)",
    "@validator": r"@validator\b",
    "@root_validator": r"@root_validator\b",
    "BaseSettings from pydantic": r"from pydantic import[^\n]*\bBaseSettings\b",
    "conint/constr/etc": r"\bcon(?:int|str|float|list|bytes|decimal)\s*\(",
    "__fields__": r"\b__fields__\b",
    "GenericModel": r"\bGenericModel\b",
    "__root__": r"\b__root__\b",
    "from_orm/orm_mode": r"\bfrom_orm\b|\borm_mode\b",
    "json_encoders": r"\bjson_encoders\b",
    "construct()": r"\.construct\(",
    "schema()/schema_json()": r"\.schema\(\)|\bschema_json\(",
    "validate_arguments": r"\bvalidate_arguments\b",
    "pydantic.fields/ModelField": r"\bpydantic\.fields\b|\bModelField\b",
    "SecretField": r"\bSecretField\b",
    "pydantic.v1 shim": r"\bpydantic\.v1\b",
}

_COMPILED = {name: re.compile(p, re.M) for name, p in SURFACES.items()}


def count(files: dict[str, bytes], *, within: str | None = None) -> int:
    """Total v1-only constructs left across the tree.

    `within` restricts to a path prefix -- the package, normally. The
    TESTS are post-migration and full of v2 spellings; counting them
    would add a constant that never moves and hide the signal.
    """
    return sum(breakdown(files, within=within).values())


def breakdown(files: dict[str, bytes], *,
              within: str | None = None) -> dict[str, int]:
    """Per-surface counts, so a stalled attempt says WHICH thing it left.

    Binary files and undecodable bytes are skipped rather than fatal: this
    runs on whatever the agent's tree currently is, which at the moment of
    interest is a tree that does not even parse.
    """
    out: dict[str, int] = {}
    for path, blob in files.items():
        if not path.endswith(".py"):
            continue
        if within and within not in path:
            continue
        try:
            text = blob.decode("utf-8", "replace")
        except Exception:
            continue
        for name, pattern in _COMPILED.items():
            hits = len(pattern.findall(text))
            if hits:
                out[name] = out.get(name, 0) + hits
    return out


def locations(files: dict[str, bytes], *,
              within: str | None = None) -> dict[str, dict[str, int]]:
    """Per-surface counts BY FILE, so the number becomes a work list.

    `breakdown` says an attempt left 42 constrained-type calls;
    this says 24 of them are in v4010/segments.py and 18 in
    v5010/segments.py. Run 5 is why the difference matters: warm cleared
    337 of 383 surfaces on attempt 2 and then moved one in eight
    attempts, because nothing named the 46 that were left. Its suite
    could not -- `condecimal(gt=...)` is valid, working v2 and raises
    nothing -- so no error signature named them, so Cognee never had the
    word to distil, and the final procedure had no step for constrained
    types at all.
    """
    out: dict[str, dict[str, int]] = {}
    for path, blob in files.items():
        if not path.endswith(".py"):
            continue
        if within and within not in path:
            continue
        try:
            text = blob.decode("utf-8", "replace")
        except Exception:
            continue
        for name, pattern in _COMPILED.items():
            hits = len(pattern.findall(text))
            if hits:
                out.setdefault(name, {})[path] = hits
    return out


def as_work_list(files: dict[str, bytes], *, within: str | None = None,
                 max_surfaces: int = 6, max_files: int = 3) -> list[str]:
    """`locations` as lines for a prompt, commonest surface first.

    Bounded, and it says what it dropped: a silent top-N reads as "that
    is all of it", which is the same mistake as reporting a count with no
    floor beside it.
    """
    found = locations(files, within=within)
    ranked = sorted(found.items(), key=lambda kv: -sum(kv[1].values()))
    lines = []
    for name, per_file in ranked[:max_surfaces]:
        shown = sorted(per_file.items(), key=lambda kv: -kv[1])
        where = ", ".join(f"{path} ({n})" for path, n in shown[:max_files])
        if len(shown) > max_files:
            where += f", and {len(shown) - max_files} more file(s)"
        lines.append(f"{sum(per_file.values())} x {name} -- {where}")
    if len(ranked) > max_surfaces:
        dropped = sum(sum(v.values()) for _, v in ranked[max_surfaces:])
        lines.append(f"{dropped} more across "
                     f"{len(ranked) - max_surfaces} other surface kind(s)")
    return lines


def parses(files: dict[str, bytes], *,
           within: str | None = None) -> tuple[int, int]:
    """(files that compile, files looked at). Source-level, never runs it.

    WHY THIS EXISTS, and it is the point of the whole measurement layer.
    `tests_passed` on fixtures/oapi has three values -- 0, ~310, 445 --
    and the step from 0 to ~310 is "the package imports". One stray
    indent takes a 95%-complete migration to 0; leaving 58 of 64 v1
    surfaces in place but fixing the import scores 310. It ranks import
    ability, not code.

    The operator, verbatim: "an agent with shit code but a good import
    goes from 0-300+. This is not a test. This is nonsense."

    So the pair that actually answers "who wrote better code" is
    (v1 surfaces remaining, files that parse): the first says how much of
    the migration exists, the second says whether it is intact. They are
    independent -- warm ran 16 surfaces at 28/49 parsing while cold ran
    63 at 49/49, which is "did the work and broke it" against "kept it
    valid by not doing it", and `tests_passed` scored both 0.

    Defined on a tree that does not parse, which is exactly when it is
    needed. `compile()` rather than `ast.parse` so the error class
    matches what pytest's collection hits.
    """
    ok = total = 0
    for path, blob in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        if within and within not in path:
            continue
        total += 1
        try:
            compile(blob.decode("utf-8"), path, "exec")
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        ok += 1
    return ok, total


def closeness(files: dict[str, bytes],
              baseline: dict[str, bytes],
              answer: dict[str, bytes],
              *, within: str | None = None) -> float:
    """How far along the v1 -> v2 path this tree is. 0.0 = untouched, 1.0 = the answer.

    NORMALISED AGAINST THE BASELINE, which is the whole trick. Raw
    similarity-to-answer is a dud and was measured as one: the UNTOUCHED
    pre-migration tree already scores 0.915, because these files are
    mostly boilerplate and the migration touches few lines. Every arm
    then lands between 0.914 and 0.920 and the column says nothing.

    So per file, progress is the fraction of the gap the reference had to
    close that this tree has closed:

        (sim(attempt, answer) - sim(baseline, answer)) / (1 - sim(baseline, answer))

    and files the reference DID NOT CHANGE are excluded outright -- they
    contribute a constant 1.0 that swamps the signal. Files are weighted
    by how much the reference changed them, so rewriting the one hard
    module counts for more than reformatting six easy ones.

    Approximate on purpose. An agent that migrates correctly in different
    words is under-credited, so this ranks arms against each other on one
    fixture; it is not a grade. The suite stays the only oracle of
    success, and (v1_remaining, parse_ok) stay the structural measures.
    Negative values are real and kept: a tree can be further from the
    answer than the baseline was.
    """
    import ast
    import difflib

    # KEYS DIFFER BY PATH PREFIX BETWEEN THE TWO PATHS THIS RUNS ON.
    # The local workspace returns `openapi_python_client/config.py`; the
    # remote one returns `/repo/openapi_python_client/config.py`
    # (AgentWorkspace.collect_file_contents). An exact `files.get(path)`
    # therefore matched NOTHING on the pod, every file scored as
    # unchanged, and run 1 reported closeness 0.000 for every attempt of
    # both arms -- including a tree that had reached 310 passing tests.
    # `v1_remaining` was unaffected because it matches on a substring.
    #
    # Normalised on the package segment, which is the one thing both
    # spellings share.
    def key(path: str) -> str:
        i = path.find(within) if within else -1
        return path[i:] if i >= 0 else path

    files = {key(k): v for k, v in files.items()}

    # NORMALISED THROUGH THE AST, so formatting is not mistaken for
    # divergence. Diffing raw lines made this measure worse than useless:
    # in run 4 cold produced a correct v2 migration of request_body.py
    # that collapsed a 40-line `ConfigDict(...)` into 10 lines, and the
    # file scored -5.19 "progress" -- the whole tree came out at -0.911
    # while passing 311 tests with 6 v1 surfaces left. `ast.unparse`
    # re-emits canonical source, so two files that differ only in layout
    # compare equal and only real structural change registers.
    #
    # Falls back to raw lines when a file does not parse, which is exactly
    # when this is most needed: a tree the agent has broken still has to
    # be measurable, and there the text is all there is.
    def lines(blob: bytes) -> list[str]:
        try:
            src = blob.decode("utf-8")
        except UnicodeDecodeError:
            return []
        try:
            return ast.unparse(ast.parse(src)).splitlines()
        except (SyntaxError, ValueError, RecursionError):
            return src.splitlines()

    total_weight = 0.0
    achieved = 0.0
    for path, want in sorted(answer.items()):
        if not path.endswith(".py"):
            continue
        if within and within not in path:
            continue
        was = baseline.get(path)
        if was is None or was == want:
            continue                      # the reference left it alone
        target = lines(want)
        base = difflib.SequenceMatcher(None, lines(was), target).ratio()
        if base >= 1.0:
            continue
        got = files.get(path)
        now = (difflib.SequenceMatcher(None, lines(got), target).ratio()
               if got is not None else base)
        # How much of this file the reference had to rewrite.
        weight = (1.0 - base) * max(len(target), 1)
        total_weight += weight
        achieved += weight * (now - base) / (1.0 - base)
    if not total_weight:
        return 0.0
    return round(achieved / total_weight, 4)


def reference_trees(fixture_dir, package_path: str) -> tuple[dict, dict]:
    """(pre-migration package, the human's merged answer), keyed alike.

    Read on the ORCHESTRATOR, at grading time, from the operator's own
    disk. The answer key is never on the pod and never reachable by an
    agent -- `fixture/` is chmod a-w and outside every agent's home for
    exactly this reason, and one 2026-09-13 run had an agent grep it.

    Returns ({}, {}) if either tree is absent, so a fixture without a
    reference answer simply reports no closeness rather than failing a
    run over a measurement.
    """
    from pathlib import Path

    fixture_dir = Path(fixture_dir)
    roots = (fixture_dir / package_path,
             fixture_dir / "reference_v2" / package_path)
    if not all(r.is_dir() for r in roots):
        return {}, {}
    out = []
    for root in roots:
        out.append({
            f"{package_path}/{p.relative_to(root)}": p.read_bytes()
            for p in sorted(root.rglob("*.py"))
            if "__pycache__" not in str(p)
        })
    return out[0], out[1]
