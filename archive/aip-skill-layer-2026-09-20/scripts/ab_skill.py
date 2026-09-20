#!/usr/bin/env python3
"""Does the distilled skill actually help? Vary ONLY the skill version.

    scripts/ab_skill.py --pairs 3 --a 0 --b 5 --ssh-host H --ssh-port P

WHY THIS AND NOT WARM-VS-COLD. Measured over 8 runs, warm converged 8/8
against cold's 5/8 and used fewer tokens per attempt in 5/8 -- but the
same held on **v0**, whose content the test suite actively forbids from
containing any task knowledge. So the gap cannot be attributed to what
the agent distilled; warm differs from cold in memory, in the skill
prefix, and in skill content all at once.

This holds everything fixed and moves one thing. Both arms of the
comparison are WARM, same model, same prompt shape, same tools, same
machine. Only the archived skill version differs, and distillation is off
so the version under test cannot change mid-run.

ALTERNATED, not blocked. Running three of A then three of B would let
anything that drifts over the session -- KV cache state, server warmth,
Daytona latency -- load onto whichever arm went second. A/B/B/A spreads
that across both.

USE AN EVEN NUMBER OF PAIRS. Alternating the order pair by pair only
balances position when the pair count is even: with 3 pairs the order
goes AB/BA/AB, so A runs first twice and B runs first once. That is not
cosmetic. Measured over the first sweep, the second slot in a pair was
24% cheaper than the first, which is the same order as the effect being
looked for -- so the version that happened to get the second slot twice
gets a free advantage. The script refuses an odd count rather than
producing a number that has to be stratified afterwards to mean
anything.

Each run is a separate `swarm/run.py` invocation, so each gets its own
event log and metrics file and the pair can be compared afterwards from
runs/<id>-metrics.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"


def one_run(version: int, *, args, tag: str) -> Path:
    log = RUNS / f"ab-v{version}-{tag}.log"
    cmd = [
        str(REPO / ".venv/bin/python"), "-u", str(REPO / "swarm/run.py"),
        "--repo", str(REPO / "fixture"),
        "--install", "pip install -r requirements-v2.txt",
        "--test", "python -m pytest tests -q",
        # WARM ONLY. Cold is not the comparison here, and running it would
        # double the GPU cost while contending for the same server.
        "--arms", "warm", "--swarm-size", "1",
        "--deadline-s", str(args.deadline),
        "--no-stop-for-victory",
        "--model", args.model, "--auto-compact", "128000",
        "--skill-version", str(version), "--no-distill",
        "--ssh-host", args.ssh_host, "--ssh-port", str(args.ssh_port),
        "--ssh-key", args.ssh_key,
    ]
    print(f"  v{version} [{tag}] -> {log.name}", flush=True)
    with log.open("w") as handle:
        proc = subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT,
                              cwd=REPO)
    if proc.returncode != 0:
        print(f"    rc={proc.returncode} -- see {log}", flush=True)
    return log


def latest_metrics(after: float) -> dict | None:
    newest = None
    for path in RUNS.glob("swarm-*-metrics.json"):
        if path.stat().st_mtime < after:
            continue
        if newest is None or path.stat().st_mtime > newest.stat().st_mtime:
            newest = path
    return json.loads(newest.read_text()) if newest else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--a", type=int, default=0, help="baseline skill version")
    ap.add_argument("--b", type=int, default=5, help="skill version under test")
    ap.add_argument("--pairs", type=int, default=4,
                    help="even, so first/second position balances")
    ap.add_argument("--allow-unbalanced", action="store_true",
                    help="permit an odd --pairs; the result then needs "
                         "stratifying by position")
    ap.add_argument("--deadline", type=int, default=600)
    ap.add_argument("--model", default="mistralai/Mistral-Small-4-119B-2603")
    ap.add_argument("--ssh-host", required=True)
    ap.add_argument("--ssh-port", type=int, required=True)
    ap.add_argument("--ssh-key", required=True)
    args = ap.parse_args()

    if args.pairs % 2 and not args.allow_unbalanced:
        print(f"--pairs {args.pairs} is odd, so the A/B ordering cannot "
              f"balance: v{args.a} would run first "
              f"{args.pairs // 2 + 1} time(s) and v{args.b} "
              f"{args.pairs // 2}. The second slot in a pair measured 24% "
              f"cheaper than the first, which is larger than the effect "
              f"being looked for.\nUse an even --pairs, or "
              f"--allow-unbalanced and stratify by position when reporting.")
        return 2

    results: dict[int, list[dict]] = {args.a: [], args.b: []}
    for i in range(args.pairs):
        # Alternate the ORDER within each pair too, so neither version is
        # always the one that runs into a freshly-started server.
        order = [args.a, args.b] if i % 2 == 0 else [args.b, args.a]
        for slot, version in enumerate(order, start=1):
            started = time.time()
            one_run(version, args=args, tag=f"p{i}")
            metrics = latest_metrics(started)
            if metrics is None:
                print(f"    no metrics written for v{version} pair {i}")
                continue
            warm = metrics["arms"].get("warm") or {}
            # Which slot in the pair this ran in, kept with the numbers so
            # the report can stratify rather than assume it away.
            warm["_slot"] = slot
            warm["_pair"] = i
            results[version].append(warm)
            print(f"    v{version}: {warm.get('tests_passed')} passed, "
                  f"{warm.get('attempts')} attempt(s), "
                  f"{warm.get('turns')} turns, "
                  f"{warm.get('attempt_prompt_tokens', 0):,} in", flush=True)

    print("\n" + "=" * 64)
    print(f"{'version':<10}{'n':<4}{'converged':<11}{'turns/att':<12}{'tokens/att':>14}")
    for version, rows in results.items():
        if not rows:
            print(f"v{version:<9}{0:<4}no data")
            continue
        n = len(rows)
        atts = sum(max(r.get("attempts") or 1, 1) for r in rows)
        conv = sum(1 for r in rows if r.get("converged"))
        turns = sum(r.get("turns") or 0 for r in rows) / atts
        toks = sum(r.get("attempt_prompt_tokens") or 0 for r in rows) / atts
        print(f"v{version:<9}{n:<4}{conv}/{n:<9}{turns:<12.0f}{toks:>14,.0f}")
    # Every run, with its slot, because the means above hide both the
    # spread and the position each run got -- and the first sweep's
    # apparent 29% gap shrank to 11% when its single outlier pair was
    # dropped.
    print("\nper run (slot 1 = first in its pair, 2 = second):")
    for version, rows in results.items():
        for r in rows:
            print(f"  v{version} pair {r.get('_pair')} slot {r.get('_slot')}: "
                  f"{r.get('turns')} turns, "
                  f"{r.get('attempt_prompt_tokens', 0):,} in, "
                  f"converged={bool(r.get('converged'))}")
    print("\nOne number per version is a summary, not a result. With three "
          "runs each\nthe smallest one-sided p a permutation test can "
          "return is 0.05, and that\nonly if the two sets separate "
          "completely -- so read the per-run lines, check\nthe slots "
          "balance, and treat anything short of separation as noise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
