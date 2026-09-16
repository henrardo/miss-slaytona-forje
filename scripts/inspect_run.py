#!/usr/bin/env python3
"""What actually happened in a run. Defaults to the newest runs/m4-*.jsonl.

    python3 scripts/inspect_run.py [runs/m4-<id>.jsonl]

The printed summary at the end of a run is not enough to tell a real result
from a null one. Across the 40 runs recorded in runs/accumulation.csv every
summary looked plausible -- 4 attempts a side, a token ratio near 1.0 -- while
19 of the last 20 run logs contain ATTEMPT_DONE: 0 and SANDBOX_CREATED: 0,
meaning no attempt was ever graded and the oracle never ran.

The three gates below are the ones that distinguish those cases. Exits non-zero
if any of them fails, so this is usable as a check and not just a report.
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        path = Path(argv[1])
    else:
        candidates = sorted(glob.glob("runs/m4-*.jsonl"), key=lambda p: Path(p).stat().st_mtime)
        if not candidates:
            print("no runs/m4-*.jsonl found")
            return 1
        path = Path(candidates[-1])

    events = load(path)
    counts = collections.Counter(e["type"] for e in events)
    print(f"{path}  ({len(events)} events)")
    print()
    for name, n in sorted(counts.items()):
        print(f"  {name:18} {n}")

    start = next((e for e in events if e["type"] == "RUN_START"), {})
    end = next((e for e in events if e["type"] == "RUN_END"), {})
    if start:
        print()
        print(f"  model      {start.get('model')}")
        print(f"  deadline   {start.get('deadline_s')}s agents"
              f"  (+{start.get('setup_s')}s setup, outside the budget)")

    # --- the gates -------------------------------------------------------
    print()
    print("gates (a zero here means the run measured nothing):")
    gates = {
        "attempts graded (ATTEMPT_DONE)": counts["ATTEMPT_DONE"],
        "oracle ran (SANDBOX_CREATED)": counts["SANDBOX_CREATED"],
    }
    failed = [k for k, v in gates.items() if v == 0]
    for label, n in gates.items():
        print(f"  {'ok ' if n else 'FAIL'} {label}: {n}")

    # Memory is warm-only, so an absent MEMORY_READ is a finding, not a gate
    # failure, when the graph started empty.
    reads = [e for e in events if e["type"] == "MEMORY_READ"]
    hits = sum(e.get("hits", 0) for e in reads)
    srcs = sorted({s for e in reads for s in e.get("sources") or []})
    print(f"  {'ok ' if reads else '--  '} warm retrievals: {len(reads)} reads, "
          f"{hits} hits, sources={srcs or '[]'}")
    print(f"  {'ok ' if counts['MEMORY_WRITE'] else '--  '} memory writes: "
          f"{counts['MEMORY_WRITE']}")

    aborted = [e for e in events if e["type"] == "ATTEMPT_ABORTED"]
    if aborted:
        print()
        print(f"attempts ABORTED ({len(aborted)}) -- vibe completed no turn, so nothing was "
              f"graded. Usually a saturated endpoint:")
        for e in aborted[:8]:
            print(f"  {e.get('swarm')}-{e.get('agent')} attempt {e.get('attempt')}: "
                  f"vibe_exit={e.get('vibe_exit_code')} stop={e.get('vibe_stop')!r}")
        if len(aborted) > 8:
            print(f"  ... and {len(aborted) - 8} more")

    rejected = [e for e in events if e["type"] == "ATTEMPT_REJECTED"]
    if rejected:
        print()
        print("attempts rejected (green/improving suite, but not a migration):")
        for e in rejected:
            print(f"  {e.get('swarm')}-{e.get('agent')} attempt {e.get('attempt')}: "
                  f"pytest_passed={e.get('pytest_passed')} "
                  f"shimmed={e.get('shimmed')} gutted={e.get('gutted')}")

    # --- per-agent attempt detail ---------------------------------------
    print()
    print("per-agent:")
    per = collections.defaultdict(lambda: {"started": 0, "graded": 0, "best_exit": None})
    for e in events:
        key = f"{e.get('swarm')}-{e.get('agent')}"
        if e["type"] == "ATTEMPT_START":
            per[key]["started"] += 1
        elif e["type"] == "ATTEMPT_DONE":
            per[key]["graded"] += 1
            ec = e.get("exit_code")
            cur = per[key]["best_exit"]
            per[key]["best_exit"] = ec if cur is None else min(cur, ec)
    for key in sorted(per):
        d = per[key]
        print(f"  {key:8} {d['started']} started, {d['graded']} graded, "
              f"best exit_code {d['best_exit']}")

    # Why each attempt's Vibe turn ended, and how many turns it used. An
    # attempt with turns_used ~1 and no stop event did no work and should not
    # be counted as evidence of anything -- see FIXES-2026-09-15.md, "One open
    # bug". Before this was emitted, "8 turns, hit the limit" and "0 turns,
    # died" looked identical here.
    dones = [e for e in events if e["type"] == "ATTEMPT_DONE"]
    if any("vibe_stop" in e for e in dones):
        print()
        print("how each Vibe turn ended:")
        dead = 0
        for e in dones:
            turns = e.get("turns_used")
            flag = ""
            if isinstance(turns, int) and turns <= 1:
                flag = "  <-- NO WORK DONE"
                dead += 1
            print(f"  {e.get('swarm')}-{e.get('agent')} att={e.get('attempt')} "
                  f"turns={turns} resumed={e.get('resumed')} "
                  f"stop={e.get('vibe_stop')!r}{flag}")
        if dead:
            print(f"  WARNING: {dead} of {len(dones)} graded attempts did no work. "
                  f"Their verdicts are real but say nothing about the model.")

    if end:
        print()
        print(f"  RUN_END  {json.dumps({k: v for k, v in end.items() if k not in ('t', 'type')})}")

    # --- productivity per attempt -----------------------------------------
    #
    # The number that catches the prompt-order class of bug: an arm whose
    # attempts end after two turns racks up MORE graded attempts while doing a
    # quarter of the work, and every per-attempt metric then flatters it. Run
    # 28's token_ratio and the 4-a-side run of 2026-09-15 were both this.
    durs = collections.defaultdict(list)
    starts = [e for e in events if e["type"] == "ATTEMPT_START"]
    for d in (e for e in events if e["type"] == "ATTEMPT_DONE"):
        key = (d.get("swarm"), d.get("agent"), d.get("attempt"))
        s = next((x for x in starts
                  if (x.get("swarm"), x.get("agent"), x.get("attempt")) == key), None)
        if s:
            durs[d.get("swarm")].append(d["t"] - s["t"])
    if durs:
        print()
        print("attempt duration by arm (a big gap means one arm is stopping early):")
        for swarm in sorted(durs):
            v = sorted(durs[swarm])
            print(f"  {swarm:5} n={len(v):3}  median {v[len(v)//2]:6.0f}s"
                  f"  min {v[0]:6.0f}s  max {v[-1]:6.0f}s")

    if failed:
        print()
        print(f"VERDICT: this run measured nothing -- {', '.join(failed)}")
        return 1
    print()
    print("VERDICT: attempts were graded by the real oracle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
