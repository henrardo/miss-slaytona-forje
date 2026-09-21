#!/usr/bin/env python3
"""Re-score every saved attempt tree, with today's measures.

    .venv/bin/python scripts/regrade_trees.py

WHY THIS EXISTS. The measures changed under the runs. `v1_remaining` was
computed but not wired to the progress decision for one run; `closeness`
was the signal for two runs and was shown to fall on correct edits; and
`tests_passed` was reported for every run while being unable to report
anything but 0 for any tree with a single unimportable module, which is
most of them.

Every one of those, except the suite, reads only the tree -- and every
attempt's tree was saved (`_tree_writer`, one tarball per attempt). So the
whole series can be re-scored consistently, after the fact, with no pod,
no Daytona and no GPU. That is the difference between "we changed the
metric" and "we have to run it again".

The suite is NOT recomputed here: it needs a real pytest run in a fresh
sandbox, which is what scripts/regrade_suite.py is for.

Writes runs/regraded.json and runs/regraded.csv.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import surfaces                       # noqa: E402
from orchestrator.vibe_agent import _closeness          # noqa: E402

TREE = re.compile(r"^(?P<label>\w+)-(?P<idx>\d+)-a(?P<attempt>\d+)\.tgz$")


def tree_contents(tarball: Path) -> dict[str, bytes]:
    """The package files inside one saved tree, keyed as the grader keyed them."""
    out: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(tmp)
        root = Path(tmp)
        for path in root.rglob("*.py"):
            out[str(path.relative_to(root))] = path.read_bytes()
    return out


def main() -> int:
    rows = []
    for trees in sorted((REPO / "runs" / "experiments").glob("*/trees")):
        run_id = trees.parent.name
        for tarball in sorted(trees.glob("*.tgz")):
            m = TREE.match(tarball.name)
            if not m:
                continue
            files = tree_contents(tarball)
            if not files:
                continue
            package = "x12sdk" if any(k.startswith("x12sdk/") for k in files) \
                else None
            ok, total = surfaces.parses(files, within=package)
            rows.append({
                "run": run_id,
                "arm": m["label"],
                "attempt": int(m["attempt"]),
                "v1_remaining": surfaces.count(files, within=package),
                "parse_ok": ok,
                "parse_total": total,
                "closeness": _closeness(files, package),
                "files": len(files),
                # The two disqualifiers, recomputed rather than trusted:
                # a shimmed or gutted tree can score well on everything above.
                "v1_shim_files": len(surfaces.v1_shim_files(files, within=package))
                if hasattr(surfaces, "v1_shim_files") else None,
            })
    rows.sort(key=lambda r: (r["run"], r["attempt"], r["arm"]))
    (REPO / "runs" / "regraded.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (REPO / "runs" / "regraded.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"re-scored {len(rows)} tree(s) across "
          f"{len({r['run'] for r in rows})} run(s)")
    print(f"  runs/regraded.json, runs/regraded.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
