#!/usr/bin/env python
"""Read-only post-mortem across a series of runs.

    scripts/triage_runs.py runs/swarm-A.jsonl runs/swarm-B.jsonl ...

Answers the questions the headline score cannot, and says plainly when it
cannot answer one.

WHY IT EXISTS. On `fixtures/oapi` `tests_passed` has two effective
values: 0 (the package does not import) and ~310 (it does, and both arms
are then blocked on the same ValidationError). It ranks a nearly-finished
migration with one stray indent below an untouched checkout, and it
cannot separate the arms at all. Everything here is derived from the
event log, so it can be re-run against the record and gives the same
answer.

It draws no conclusions the data does not support: where a cause is
unknown -- the surface count collapsing between attempts, for instance --
it reports the transition and says the cause is not in the event log.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def attempts(events: list[dict], arm: str) -> list[dict]:
    return [e for e in events
            if e.get("type") == "ATTEMPT_DONE" and e.get("swarm") == arm]


def classify(signature: str | None) -> str:
    """What KIND of failure, which the score flattens to 0."""
    s = signature or ""
    if not s:
        return "none"
    if any(k in s for k in ("SyntaxError", "IndentationError", "TabError")):
        return "BROKE THE CODE"
    if "ImportError" in s or "NameError" in s or "ModuleNotFound" in s:
        return "import/name error"
    if "PydanticUserError" in s:
        return "not migrated yet"
    if "ValidationError" in s:
        return "migrated, behaviour differs"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+")
    args = ap.parse_args()

    regressions: list[str] = []
    kinds: Counter = Counter()
    print(f"{'run':>4} {'arm':5} {'att':>3} {'passed':>6} {'v1':>4} "
          f"{'turns':>5}  failure kind")
    for n, raw in enumerate(args.logs, 1):
        events = load(Path(raw))
        for arm in ("warm", "cold"):
            prev = None
            for e in attempts(events, arm):
                kind = classify(e.get("error_signature"))
                kinds[(arm, kind)] += 1
                v1 = e.get("v1_remaining")
                print(f"{n:>4} {arm:5} {e.get('attempt'):>3} "
                      f"{e.get('tests_passed'):>6} {v1 if v1 is not None else '-':>4} "
                      f"{e.get('turns_used'):>5}  {kind}")
                # A jump BACKWARDS in migration progress between attempts.
                # The harness never checkpoints at 0 passing, so nothing in
                # the event log explains these -- they are reported, not
                # attributed.
                if prev is not None and v1 is not None and v1 > prev + 20:
                    regressions.append(
                        f"  run {n} {arm}: attempt {e.get('attempt')} went "
                        f"{prev} -> {v1} surfaces (lost {v1 - prev})")
                if v1 is not None:
                    prev = v1
        print()

    print("FAILURE KINDS (the score calls all of these 0)")
    for (arm, kind), c in sorted(kinds.items()):
        print(f"  {arm:5} {kind:28} {c}")

    print("\nPROGRESS THROWN AWAY BETWEEN ATTEMPTS")
    if regressions:
        print("\n".join(regressions))
        print("  CAUSE NOT IN THE EVENT LOG. `checkpoint()` only fires when "
              "tests_passed beats the previous best, which never happens at "
              "0, so no `best` ref exists and `restore_best()` returns False "
              "-- the harness is not doing this. Needs the agents' own "
              "transcripts to attribute.")
    else:
        print("  none")

    rolled = sum(1 for raw in args.logs for e in load(Path(raw))
                 if e.get("type") == "RESTORED")
    print(f"\nRESTORED events across the series: {rolled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
