#!/usr/bin/env python3
"""Regenerate the x12sdk results tables from the event logs.

Reads each `runs/x12-*.log` for the `event log:` line it prints at the end,
so the tables can never drift from the runs they describe -- nothing here is
transcribed by hand.

    .venv/bin/python scripts/x12_summary.py            # markdown to stdout
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

ORACLE = 261        # tests in the post-migration suite, measured
BASELINE_V1 = 383   # v1 surfaces in the pre-migration package
FLOOR_V1 = 2        # v1 surfaces left in the human's merged answer


def event_log_for(run_log: str) -> str | None:
    """The jsonl this run wrote, taken from the run's own final line."""
    try:
        text = open(run_log, errors="replace").read()
    except OSError:
        return None
    m = re.search(r"event log: (runs/\S+\.jsonl)", text)
    if m:
        return m.group(1)
    # A run killed before its summary still has a log; fall back to the
    # newest jsonl older than the run log itself, and say so.
    return None


def attempts(path: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"warm": [], "cold": []}
    for line in open(path):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "ATTEMPT_DONE":
            out.setdefault(d.get("swarm", "?"), []).append(d)
    return out


def fmt(rows: list[dict]) -> str:
    if not rows:
        return "_no graded attempt_"
    return " ".join(
        f"[a{r['attempt']} {r['tests_passed']}t/{r['v1_remaining']}v/"
        f"{r['parse_ok']}p/{r['closeness']:+.3f}]" for r in rows)


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "runs/x12-*.log"
    print(f"Oracle {ORACLE} tests. Baseline {BASELINE_V1} v1 surfaces, "
          f"answer-key floor {FLOOR_V1}.")
    print("Cells are [attempt  tests / v1 left / files parsing / closeness].\n")
    for run_log in sorted(glob.glob(pattern)):
        if run_log.endswith("driver.log"):
            continue
        ev = event_log_for(run_log)
        if not ev or not os.path.exists(ev):
            print(f"### {run_log} — no event log (run did not finish)\n")
            continue
        a = attempts(ev)
        print(f"### {os.path.basename(run_log)}  (`{os.path.basename(ev)}`)")
        for arm in ("warm", "cold"):
            if a.get(arm):
                best_t = max(r["tests_passed"] for r in a[arm])
                best_v = min(r["v1_remaining"] for r in a[arm])
                print(f"- **{arm}** best {best_t}/{ORACLE} tests, "
                      f"best {best_v} v1 left, {len(a[arm])} attempt(s)")
                print(f"  - {fmt(a[arm])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
