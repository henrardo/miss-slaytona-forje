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

# The procedure now lives in Cognee, so this script needs the graph
# credentials the run had. Without it the archive silently records
# everything EXCEPT the thing the experiment produced.
from dotenv import load_dotenv                       # noqa: E402

load_dotenv(REPO / ".env")

from export_demo import CAVEATS                      # noqa: E402
from orchestrator import cognee_layer as C           # noqa: E402
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


def skill_sizes(events: list[dict]) -> list[int]:
    """The procedure's size after each distillation, in characters.

    WHAT THIS REPLACES, and why it cannot come back. `skill_versions_used`
    read the version number each attempt ran on, out of a lineage
    directory on this machine. Cognee rewrites `procedure` IN PLACE and
    keeps no lineage, so there is no v5..v7 to archive and a counter
    invented here would read as more than we know. The size after each
    accepted proposal is the honest remnant -- it says the skill moved,
    and by how much.
    """
    return [e.get("procedure_chars") for e in events
            if e.get("type") == "DISTILLED" and e.get("procedure_chars")]


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

    sizes = skill_sizes(events)
    # THE PROCEDURE AS THE EXPERIMENT LEFT IT, pulled out of Cognee.
    #
    # This used to copy a directory of version files plus the live AIP
    # package. There is no file and no lineage now -- the skill lives in
    # the graph -- so the archive has to go and fetch it, and it must do
    # so BEFORE the next experiment's `--reset-memory` overwrites it.
    # Without this the only record of what the agents wrote is a
    # character count.
    copied: list[str] = []
    try:
        import asyncio

        dataset = C.configure(dataset=f"msf-{FIXTURE_DIR.name}")
        procedure = asyncio.run(C.current_procedure(dataset=dataset)) or ""
        if procedure:
            (out / "skill-final.md").write_text(procedure)
            copied.append("skill-final.md")
    except Exception as exc:                      # never lose the evidence
        print(f"  could not read the final procedure from Cognee: {exc!r}")

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
                # Always empty under Cognee, and kept so the shape of an
                # experiment.json does not change across the migration.
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
        "procedure_chars_after_each_distillation": sizes,
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
    print(f"  procedure after each distillation: {sizes} chars, "
          f"{len(copied)} file(s) archived, "
          f"{len(manifest['trees'])} tree(s)")
    if manifest["trees"] and len(manifest["trees"]) < sum(
            len(a["attempts"]) for a in manifest["arms"].values()):
        print("  NOTE: fewer trees than attempts -- this experiment ran "
              "before per-attempt tree capture, or a write failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
