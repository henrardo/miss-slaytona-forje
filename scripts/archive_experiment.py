#!/usr/bin/env python3
"""Archive one experiment: the attempts, the skills they wrote, the trees.

    scripts/archive_experiment.py runs/swarm-1789862280.jsonl

An EXPERIMENT is N attempts on one checkout -- attempt, distil a skill,
continue from where the agent left off, distil again, stop -- and then this.
It is the last step of the loop, not an optional extra: the skill lineage
lives in `skills/versions-<fixture>/` and keeps growing, so without an
archive there is nothing that says which versions belonged to which
experiment.

WHY NOT export_demo.py. That script bundles a SERIES -- many runs from a
pristine checkout each time -- and answers "does a better manual help a cold
start". This one bundles a single experiment and answers "did this agent get
further each attempt". Both are real; they are different questions, and the
run-vs-experiment confusion is exactly what produced 14 runs and 81 skill
files on 2026-09-20. The measurement caveats are shared, so they are
imported rather than restated.

Everything is derived from the EVENT LOG, which is written as the run
happens and is the only thing that survives a pod dying mid-experiment.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from export_demo import CAVEATS                      # noqa: E402
from orchestrator import skills                      # noqa: E402
from orchestrator.manifest import FIXTURE_DIR        # noqa: E402


def attempts_by_arm(events: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in events:
        if e.get("type") != "ATTEMPT_DONE":
            continue
        out.setdefault(e["swarm"], []).append({
            "attempt": e.get("attempt"),
            "skill_version": e.get("skill_version"),
            "tests_passed": e.get("tests_passed"),
            "v1_remaining": e.get("v1_remaining"),
            "parse_ok": e.get("parse_ok"),
            "parse_total": e.get("parse_total"),
            "closeness": e.get("closeness"),
            "turns": e.get("turns_used"),
            "seconds": e.get("attempt_seconds"),
            "broke_syntax": e.get("broke_syntax"),
            "error_signature": e.get("error_signature"),
        })
    return out


def skill_versions_used(arms: dict[str, list[dict]]) -> list[int]:
    """The versions this experiment's attempts actually ran on.

    Taken from the attempts, not from the directory listing: the lineage
    directory accumulates across experiments and a listing would sweep up
    versions that belong to someone else's run.
    """
    seen = {a["skill_version"] for atts in arms.values() for a in atts
            if a.get("skill_version") is not None}
    return sorted(seen)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    log = Path(sys.argv[1])
    if not log.exists():
        print(f"no event log at {log}")
        return 2
    run_id = log.stem
    out = REPO / "runs" / "experiments" / run_id
    out.mkdir(parents=True, exist_ok=True)

    events = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    arms = attempts_by_arm(events)
    if not arms:
        print(f"{log} records no graded attempt -- nothing to archive")
        return 1

    # The raw record first, so a failure below still leaves the evidence.
    for src in (log,
                log.with_name(log.stem + "-metrics.json"),
                log.with_name(log.stem + "-series.json")):
        if src.exists():
            shutil.copy(src, out / src.name)

    versions = skill_versions_used(arms)
    lineage = out / "skills"
    lineage.mkdir(exist_ok=True)
    copied: list[str] = []
    for v in versions:
        # v0 is the empty scaffold that ships in the repo, not an archived
        # version, so it has no file. Report what actually landed rather
        # than what was asked for.
        for path in skills.versions_dir().glob(f"v{v:03d}-*.md"):
            shutil.copy(path, lineage / path.name)
            copied.append(path.name)
    # The live package as the experiment left it: body AND the references/
    # tier, which is half the skill and is not in the version file.
    live = skills.SKILLS_DIR / skills.SKILL_NAME
    if live.is_dir():
        shutil.copytree(live, out / "skill-final", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))

    manifest = {
        "experiment": run_id,
        "fixture": FIXTURE_DIR.name,
        "shape": ("N attempts on ONE checkout: attempt, distil, continue "
                  "from where the agent left off, distil, stop. The code is "
                  "never reset between attempts."),
        "arms": {
            arm: {
                "attempts": atts,
                # Cold has no skill, so it reports none rather than a row
                # of nulls that reads like missing data.
                "skill_versions": [a["skill_version"] for a in atts
                                   if a.get("skill_version") is not None],
                "best_tests": max((a["tests_passed"] or 0) for a in atts),
                "best_v1_remaining": min(
                    (a["v1_remaining"] for a in atts
                     if a.get("v1_remaining") is not None), default=None),
                "final": atts[-1],
            }
            for arm, atts in sorted(arms.items())
        },
        "skill_versions_ran_on": versions,
        "skill_files_archived": sorted(copied),
        "trees": sorted(p.name for p in (out / "trees").glob("*.tgz")),
        "how_to_read": CAVEATS,
    }
    (out / "experiment.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"archived {run_id} -> {out}")
    for arm, a in sorted(manifest["arms"].items()):
        print(f"  {arm:5} {len(a['attempts'])} attempt(s), "
              f"skills {a['skill_versions']}, best {a['best_tests']} test(s), "
              f"best v1 {a['best_v1_remaining']}")
    print(f"  ran on skill version(s) {versions}, "
          f"{len(copied)} file(s) archived, "
          f"{len(manifest['trees'])} tree(s)")
    if manifest["trees"] and len(manifest["trees"]) < sum(
            len(a["attempts"]) for a in manifest["arms"].values()):
        print("  NOTE: fewer trees than attempts -- this experiment ran "
              "before per-attempt tree capture, or a write failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
