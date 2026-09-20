#!/usr/bin/env python3
"""Build a migration fixture from a REAL merged pydantic-v2 migration PR.

    scripts/make_fixture.py zenml-io/zenml 2543 --out fixtures/zenml

WHY A GENERATOR AND NOT A HAND-BUILT FIXTURE. The current fixture
(sabuhish/fastapi-mail#195) is 6 files and ~950 changed lines, and every
run on it is won in one or two attempts -- so there is no within-run
iteration for a distilled skill to improve against, and the warm-vs-cold
numbers are dominated by run-to-run noise. Fixing that means a harder
task, and finding the RIGHT harder task means trying several. Hand-building
each one is the reason only one exists.

THE RECIPE, taken from how the current fixture was made:

    source     the PR's BASE commit  -- the pre-migration state, the only
               thing the agent is allowed to edit
    tests      the PR's MERGE commit -- the post-migration suite, which is
               what makes it an independent oracle rather than something
               the agent could satisfy by editing
    reference  the merge commit's source -- the answer key, never shipped
               to the pod, used only to check the fixture is solvable

A merged human migration gives all three for free. That is the whole
reason to key off a PR rather than pick a repo and a version pair: someone
has already proved the destination is reachable, and their tests are the
oracle.

WHAT THIS DOES NOT DO. It does not judge whether the result is a GOOD
experiment. That needs measuring on real hardware -- see `--report`, which
prints the numbers to decide with (diff size, surfaces, test count) and
refuses to guess at the rest. Two failure modes it cannot see, both of
which have already disqualified a candidate:

  * a DEPENDENCY pinned to pydantic v1 makes the task unsolvable, because
    the agent cannot migrate code it does not own (starlite 1.51.14:
    pydantic-openapi-schema and pydantic-factories are both v1-pinned,
    which is why upstream rewrote to msgspec instead of migrating).
  * `filterwarnings = error` in the target's pytest config turns every
    pydantic deprecation into a failure. That makes for a STRONGER oracle
    -- the migration has to be clean, not merely working -- but only if
    the post-migration tests are themselves free of deprecated calls.
    Prefect 2.10.21 fails this: its own tests call `.dict()`, `parse_obj`
    and `__fields__`, and it has no merged migration commit to take
    cleaned-up tests from.

Both are reported, neither is worked around.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The same 22 probes used to score candidates. Each is an INDEPENDENT
# failure surface in a pydantic v1 -> v2 migration: a distinct thing that
# has to be understood, not another instance of the same substitution.
# Imported, not copied. A second table here would drift from the one
# the running harness counts with, and then "surfaces present in this
# fixture" and "surfaces left in this tree" would be different
# questions wearing the same name.
sys.path.insert(0, str(REPO_ROOT))
from orchestrator.surfaces import SURFACES  # noqa: E402

# A dependency pinned below pydantic 2 cannot be migrated by the agent, so
# the task has no solution. This is the starlite disqualifier.
_V1_PIN = re.compile(r"pydantic[^\n]*?<\s*2", re.I)


def run(argv: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(argv[:4])} failed: {result.stderr[-400:]}")
    return result.stdout


def pr_facts(repo: str, number: int) -> dict:
    payload = json.loads(run([
        "gh", "api", f"repos/{repo}/pulls/{number}", "--jq",
        "{base: .base.sha, merge: .merge_commit_sha, merged_at: .merged_at,"
        " title: .title, files: .changed_files, additions: .additions,"
        " deletions: .deletions, url: .html_url}",
    ]))
    if not payload.get("merge"):
        raise SystemExit(
            f"{repo}#{number} is not merged. An unmerged PR proves nothing "
            f"about the destination being reachable, which is the only "
            f"reason to build a fixture from a PR.")
    return payload


def changed_files(repo: str, number: int) -> list[str]:
    out = run(["gh", "api", f"repos/{repo}/pulls/{number}/files",
               "--paginate", "--jq", ".[].filename"])
    return [line for line in out.splitlines() if line.strip()]


def clone_at(repo: str, sha: str, dest: Path) -> None:
    """A full clone, then a checkout. `--depth 1` cannot reach an arbitrary
    sha, and the base commit of an old PR is usually far from any tip."""
    if dest.exists():
        shutil.rmtree(dest)
    run(["git", "clone", "--quiet", f"https://github.com/{repo}.git", str(dest)])
    run(["git", "checkout", "--quiet", sha], cwd=dest)


def surfaces_in(root: Path, paths: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for rel in paths:
        path = root / rel
        if not path.is_file() or path.suffix != ".py":
            continue
        text = path.read_text(errors="replace")
        for name, pattern in SURFACES.items():
            hits = len(re.findall(pattern, text, re.M))
            if hits:
                found[name] = found.get(name, 0) + hits
    return found


def count_tests(root: Path, paths: list[str]) -> int:
    total = 0
    for rel in paths:
        path = root / rel
        if path.is_file() and path.suffix == ".py":
            total += len(re.findall(r"^\s*(?:async )?def test_",
                                    path.read_text(errors="replace"), re.M))
    return total


def v1_pinned_dependencies(root: Path) -> list[str]:
    """Pins that would make the task unsolvable, and who holds them."""
    offenders = []
    for name in ("pyproject.toml", "setup.py", "setup.cfg",
                 "requirements.txt", "requirements-dev.txt"):
        path = root / name
        if path.is_file() and _V1_PIN.search(path.read_text(errors="replace")):
            offenders.append(name)
    return offenders


def errors_on_warnings(root: Path) -> bool:
    """`filterwarnings = error` makes every pydantic deprecation fatal."""
    for name in ("setup.cfg", "pyproject.toml", "pytest.ini", "tox.ini"):
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        block = re.search(r"filterwarnings\s*=\s*(.*?)(?:\n\s*\n|\n\[|\Z)",
                          text, re.S)
        if block and re.search(r"^\s*(?:\"|')?error", block.group(1), re.M):
            return True
    return False


def split_paths(paths: list[str], tests_dir: str) -> tuple[list[str], list[str]]:
    tests = [p for p in paths if p.startswith(tests_dir.rstrip("/") + "/")
             or p == tests_dir]
    source = [p for p in paths
              if p.endswith(".py") and p not in tests
              and not p.startswith(("docs/", ".github/", "scripts/"))]
    return source, tests


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="owner/name")
    ap.add_argument("pr", type=int)
    ap.add_argument("--out", type=Path, help="fixture directory to write")
    ap.add_argument("--package", help="source package dir (default: guessed)")
    ap.add_argument("--tests", default="tests", help="tests dir in the repo")
    ap.add_argument("--test-command", default="python -m pytest {tests} -q")
    ap.add_argument("--report", action="store_true",
                    help="measure and print only; write nothing")
    args = ap.parse_args()

    facts = pr_facts(args.repo, args.pr)
    paths = changed_files(args.repo, args.pr)
    source_paths, test_paths = split_paths(paths, args.tests)

    work = Path(args.out or REPO_ROOT / "fixtures" / args.repo.split("/")[-1])
    scratch = work.parent / f".{work.name}-build"
    scratch.mkdir(parents=True, exist_ok=True)
    base_dir, merge_dir = scratch / "base", scratch / "merge"

    print(f"{args.repo}#{args.pr}  {facts['title'][:70]}")
    print(f"  merged {facts['merged_at']}  {facts['url']}")
    print(f"  diff: {facts['files']} files, +{facts['additions']}/"
          f"-{facts['deletions']}")
    print(f"  base {facts['base'][:8]} -> merge {facts['merge'][:8]}")
    print(f"  of those: {len(source_paths)} source .py, {len(test_paths)} test files")

    print("  cloning base...", flush=True)
    clone_at(args.repo, facts["base"], base_dir)
    print("  cloning merge...", flush=True)
    clone_at(args.repo, facts["merge"], merge_dir)

    surfaces = surfaces_in(base_dir, source_paths)
    # TWO different numbers, and conflating them undercounts the oracle by
    # a factor of 33 on the current fixture. `tests_changed` is how much the
    # suite itself moved in the migration; `oracle_tests` is the WHOLE
    # post-migration suite, which is what actually grades an attempt -- and
    # its size sets the RESOLUTION of the progress signal. A 33-test oracle
    # moves in 3% steps; a 500-test one shows an attempt that fixed two
    # modules and broke none.
    tests_changed = count_tests(merge_dir, test_paths)
    oracle_tests = count_tests(
        merge_dir,
        [str(p.relative_to(merge_dir))
         for p in (merge_dir / args.tests).rglob("*.py")]
        if (merge_dir / args.tests).is_dir() else [])
    pins = v1_pinned_dependencies(base_dir)
    strict = errors_on_warnings(merge_dir)

    print(f"\n  SURFACES  {len(surfaces)}/{len(SURFACES)} present in the "
          f"pre-migration source")
    for name, hits in sorted(surfaces.items(), key=lambda kv: -kv[1]):
        print(f"     {hits:5d}  {name}")
    print(f"\n  ORACLE: {oracle_tests} tests in the whole post-migration "
          f"suite  ({tests_changed} of them in files the migration touched)")
    print(f"  pytest treats warnings as errors: {strict}"
          + ("   <-- stronger oracle: the migration must be CLEAN"
             if strict else ""))
    if pins:
        print(f"\n  *** pydantic<2 pin found in {', '.join(pins)}. If that pin "
              f"is the repo's OWN, changing it is part of the task. If a "
              f"DEPENDENCY holds it, the task has no solution -- check "
              f"before spending GPU time.")

    if args.report:
        print("\n--report: nothing written.")
        return 0

    if args.out is None and work.exists():
        raise SystemExit(f"{work} exists; pass --out explicitly to overwrite")

    package = args.package or _guess_package(base_dir, source_paths)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # Source at BASE: the pre-migration state, everything the agent may edit.
    shutil.copytree(base_dir, work, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__",
                                                  "*.pyc", ".pytest_cache"))
    # Tests at MERGE, overwriting: the post-migration suite is the oracle.
    tests_src, tests_dst = merge_dir / args.tests, work / args.tests
    if tests_dst.exists():
        shutil.rmtree(tests_dst)
    shutil.copytree(tests_src, tests_dst,
                    ignore=shutil.ignore_patterns(".git", "__pycache__",
                                                  "*.pyc", ".pytest_cache"))
    # Reference at MERGE: the answer key. Kept OUT of the tarball that
    # reaches the pod -- see swarm/run.py's exclude list -- and used only to
    # confirm the fixture is solvable.
    reference = work / "reference_v2"
    reference.mkdir()
    shutil.copytree(merge_dir / package, reference / package,
                    ignore=shutil.ignore_patterns(".git", "__pycache__",
                                                  "*.pyc"))

    (work / "manifest.yaml").write_text(
        f"# Built by scripts/make_fixture.py from a REAL merged migration:\n"
        f"# {args.repo}#{args.pr} -- {facts['title']}\n"
        f"# {facts['url']}\n"
        f"#\n"
        f"# {package}/ is at the PRE-migration commit ({facts['base'][:8]}).\n"
        f"# {args.tests}/ and reference_v2/ are at the MERGE commit\n"
        f"# ({facts['merge'][:8]}) -- the post-migration suite is the success\n"
        f"# oracle, the reference is the answer key and never reaches the pod.\n"
        f"#\n"
        f"# Nothing here is hand-tagged with which v1/v2 patterns appear\n"
        f"# where. The agent gets the whole codebase and one instruction.\n"
        f"#\n"
        f"# Measured at build time: {len(surfaces)}/{len(SURFACES)} migration\n"
        f"# surfaces, {oracle_tests}-test oracle, warnings-as-errors={strict}.\n"
        f'target_version: "pydantic>=2.0,<3.0"\n'
        f"package_path: {package}\n"
        f"tests_path: {args.tests}\n"
        f'test_command: "{args.test_command.format(tests=args.tests)}"\n'
    )
    print(f"\n  wrote {work}")
    print(f"  NEXT: pin requirements-v1.txt / requirements-v2.txt, then run "
          f"the cold arm alone to calibrate difficulty before any A/B.")
    return 0


def _guess_package(root: Path, source_paths: list[str]) -> str:
    """The top directory most of the changed source lives in."""
    from collections import Counter
    counts = Counter()
    for rel in source_paths:
        parts = Path(rel).parts
        if not parts:
            continue
        counts["/".join(parts[:2]) if parts[0] == "src" else parts[0]] += 1
    if not counts:
        raise SystemExit("could not guess the package dir; pass --package")
    return counts.most_common(1)[0][0]


if __name__ == "__main__":
    sys.exit(main())
