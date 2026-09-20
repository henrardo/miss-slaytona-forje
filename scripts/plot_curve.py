#!/usr/bin/env python3
"""Plot the warm arm's improvement across successive runs on one fixture.

    scripts/plot_curve.py 'runs/oapi-*.log' --out runs/curve-oapi.png

WHAT THE CURVE IS. The skill persists BETWEEN runs: run N distils a new
version from its own graded attempts, and run N+1 starts on it. Cold starts
from nothing every time. So the x axis is the run index -- how many times
the booklet has been rewritten -- and cold is the flat control that says
whether anything about the task or the server drifted underneath.

WHICH METRIC LEADS, AND WHY IT CHANGED TWICE. Token cost led while the cap
was 2,000 tokens and the skill was ~5% of the prompt; at 13,000 a full
booklet is ~40% of it, so warm's token count is no longer comparable with
cold's NOR with warm's own earlier runs. Attempts-to-converge replaced it
-- and then most runs stopped converging at all (warm 2 of 5, cold 1 of
5), which leaves it undefined for the majority of points.

So BEST-TESTS-PASSING leads. It is defined for every run and it shows the
thing that actually varies here: warm is bimodal, landing either ~445 or
0, while cold lands 429-445 every single time. Attempts are kept in panel
2 because falling attempts is what the design predicted.

READING IT HONESTLY. One run per point and no repeats, so the run-to-run
spread seen on the small fixture (14%-138% on tokens, 27-93 turns at a
FIXED skill version) applies here too. A trend across several runs is
suggestive; two adjacent points are not a result. The panels say what they
are measuring and the caption says how many runs are behind them.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

# A run's log names its own event log; that is the only reliable link from
# "the Nth run I launched" to "the metrics file it wrote", because run ids
# are timestamps and other fixtures' runs are interleaved in runs/.
_EVENT_LOG = re.compile(r"event log: (?:.*/)?(swarm-\d+)\.jsonl")


def metrics_for(log: Path) -> dict | None:
    match = _EVENT_LOG.search(log.read_text(errors="replace"))
    if not match:
        return None                      # still running, or died before the end
    path = RUNS / f"{match.group(1)}-metrics.json"
    return json.loads(path.read_text()) if path.exists() else None


def series(rows: list[dict], arm: str, field: str, default=0):
    return [(r["arms"].get(arm) or {}).get(field, default) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", help="glob of run logs, in launch order")
    ap.add_argument("--out", type=Path, default=RUNS / "curve.png")
    ap.add_argument("--title", default="Warm-arm improvement across runs")
    ap.add_argument("--oracle", type=int, default=None,
                    help="total tests in the suite, for the pass-rate panel")
    args = ap.parse_args()

    logs = sorted(Path().glob(args.pattern))
    rows, labels = [], []
    for log in logs:
        m = metrics_for(log)
        if m is None:
            print(f"  skipping {log.name}: no metrics yet")
            continue
        rows.append(m)
        labels.append(log.stem.split("-")[-1])
    if not rows:
        raise SystemExit(f"no completed runs matched {args.pattern}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(1, len(rows) + 1))
    warm_c = "#1f77b4"
    cold_c = "#d62728"
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.suptitle(args.title, fontsize=14, y=0.98)

    # 1. THE HEADLINE on this fixture. Attempts-to-converge was the plan,
    #    but warm converged in only 2 of 5 runs and cold in 1, so it is
    #    undefined for most points. Best-tests-passing is defined always
    #    and shows the thing that actually varies: warm is BIMODAL (445 or
    #    0) while cold lands 429-445 every time.
    ax = axes[0][0]
    wb, cb = series(rows, "warm", "tests_passed"), series(rows, "cold", "tests_passed")
    ax.plot(x, wb, "o-", color=warm_c, lw=2, label="warm (distilled skill)")
    ax.plot(x, cb, "s--", color=cold_c, lw=2, label="cold (no memory, no skill)")
    if args.oracle:
        ax.axhline(args.oracle, color="grey", ls=":", lw=1.5)
        ax.annotate(f"whole suite ({args.oracle})", (x[0], args.oracle),
                    textcoords="offset points", xytext=(4, -13), fontsize=8,
                    color="grey")
    # Two different reasons a booklet can sit still, and conflating them
    # would hide the most informative run in the set: run 1's skill never
    # moved because every distillation was REJECTED, which is an accident;
    # runs 5-6 were pinned on purpose as a control.
    for xi, r in zip(x, rows):
        warm = r["arms"].get("warm") or {}
        if warm.get("skill_versions"):
            continue
        why = ("pinned\n(control)" if warm.get("distillations", 0) == 0
               else "distil\nrejected")
        ax.annotate(why, (xi, wb[xi - 1]), textcoords="offset points",
                    xytext=(0, 14 if wb[xi - 1] < 200 else -34),
                    ha="center", fontsize=7, color="#555")
    ax.set_xlabel("run")
    ax.set_ylabel("best tests passing (of 445)")
    ax.set_title("Best result per run  — the headline", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_ylim(-20, (args.oracle or max(wb + cb)) * 1.12)

    # 2. Attempts, kept because it is what the design predicted would fall.
    ax = axes[0][1]
    wa, ca = series(rows, "warm", "attempts"), series(rows, "cold", "attempts")
    ax.plot(x, wa, "o-", color=warm_c, lw=2, label="warm")
    ax.plot(x, ca, "s--", color=cold_c, lw=2, label="cold")
    for xi, r in zip(x, rows):
        for arm, col, dy in (("warm", warm_c, 9), ("cold", cold_c, -16)):
            a = r["arms"].get(arm) or {}
            if a.get("converged"):
                ax.annotate("converged", (xi, a.get("attempts", 0)),
                            textcoords="offset points", xytext=(0, dy),
                            ha="center", fontsize=7, color=col)
    ax.set_xlabel("run")
    ax.set_ylabel("attempts used")
    ax.set_title("Attempts  — only the marked runs reached a passing suite",
                 fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_ylim(bottom=0)

    # 3. MIGRATION LEFT TO DO, per attempt, across the whole series. This
    #    is the panel that exists because `tests_passed` is 0 for 70% of
    #    attempts and cannot tell "not started" from "broken". A falling
    #    line here is progress the oracle could not see.
    ax = axes[1][0]
    for arm, col, mark in (("warm", warm_c, "o"), ("cold", cold_c, "s")):
        xs, ys = [], []
        for i, r in enumerate(rows, start=1):
            for j, a in enumerate((r["arms"].get(arm) or {}).get("per_attempt", [])):
                v = a.get("v1_remaining")
                if v is None:
                    continue
                n = len((r["arms"].get(arm) or {}).get("per_attempt", [])) or 1
                xs.append(i + j / max(n, 1) * 0.8 - 0.4)
                ys.append(v)
        if xs:
            ax.plot(xs, ys, mark + "-", color=col, lw=1.2, ms=4,
                    alpha=0.85, label=arm)
    if ax.has_data():
        ax.axhline(3, color="grey", ls=":", lw=1.5)
        ax.annotate("floor: the human answer scores 3", (0.02, 3),
                    xycoords=("axes fraction", "data"),
                    textcoords="offset points", xytext=(0, 5),
                    fontsize=7.5, color="grey")
        ax.set_xlabel("run (attempts spread within each run)")
        ax.set_ylabel("v1 constructs left in the source")
        ax.set_title("Migration left to do — visible even at 0 tests passing",
                     fontsize=11)
        ax.legend(fontsize=8)
        ax.set_ylim(bottom=0)
    else:
        ax.text(0.5, 0.5, "no v1_remaining recorded yet\n(runs predate the "
                "progress metric)", ha="center", va="center",
                transform=ax.transAxes, fontsize=9, color="#777")
        ax.set_title("Migration left to do", fontsize=11)
    ax.grid(alpha=0.3)

    # 3b. The booklet itself, moved to share the cost panel's row.
    ax = axes[1][1]


    def per_attempt(arm):
        toks = series(rows, arm, "attempt_prompt_tokens")
        atts = [max(a or 1, 1) for a in series(rows, arm, "attempts")]
        return [t / a / 1e6 for t, a in zip(toks, atts)]
    size = [r.get("skill_approx_tokens", 0) for r in rows]
    ax.plot(x, size, "o-", color="#2ca02c", lw=2)
    ax.set_xlabel("run")
    ax.set_ylabel("skill size (approx tokens)", color="#2ca02c")
    ax.tick_params(axis="y", labelcolor="#2ca02c")
    ax.set_title("The distilled booklet, and what each attempt cost",
                 fontsize=11)
    ax.grid(alpha=0.3)
    twin = ax.twinx()
    twin.plot(x, per_attempt("warm"), "o--", color=warm_c, lw=1.4, ms=4,
              label="warm tokens/attempt")
    twin.plot(x, per_attempt("cold"), "s--", color=cold_c, lw=1.4, ms=4,
              label="cold tokens/attempt")
    twin.set_ylabel("prompt tokens per attempt (millions)")
    twin.legend(fontsize=7, loc="upper right")

    def summary(arm):
        best = series(rows, arm, "tests_passed")
        conv = sum(1 for r in rows if (r["arms"].get(arm) or {}).get("converged"))
        zeros = sum(1 for b in best if b == 0)
        return (f"{arm}: mean {sum(best)/len(best):.0f}/445, "
                f"range {min(best)}-{max(best)}, "
                f"converged {conv}/{len(rows)}, total failures {zeros}/{len(rows)}")
    axes[0][0].text(
        0.02, 0.04, summary("warm") + "\n" + summary("cold"),
        transform=axes[0][0].transAxes, fontsize=8, va="bottom",
        bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#bbb"))

    debug = [r["run_id"] for r in rows if not r.get("counts_toward_clearly_working")]
    caption = (
        f"{len(rows)} runs, one point each, no repeats. Warm keeps its "
        f"distilled skill between runs; cold starts from nothing every time.\n"
        f"BOTH ARMS ARE BIMODAL -- each scores either ~440 or 0, and a 0 is "
        f"the agent breaking `import` with a bulk edit, not failing the "
        f"migration. That failure mode, not the booklet, is the dominant "
        f"term here.\n"
        f"Token panel: the skill is prompt prefix on every request, so a "
        f"larger booklet raises warm's COUNT even where SGLang serves it "
        f"from prefix cache and the GPU recomputes nothing."
    )
    if debug:
        caption += f"\nNOT comparable (arm differences): {', '.join(debug)}"
    fig.text(0.5, 0.005, caption, ha="center", fontsize=8.5, color="#444",
             wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"wrote {args.out}  ({len(rows)} runs)")

    print(f"\n{'run':>4s} {'skill':>6s} {'tok':>6s} "
          f"{'warm att':>9s} {'warm pass':>10s} {'cold att':>9s} {'cold pass':>10s}")
    for i, r in enumerate(rows, start=1):
        w, c = r["arms"].get("warm") or {}, r["arms"].get("cold") or {}
        print(f"{i:4d} {r.get('skill_version', 0):6d} "
              f"{r.get('skill_approx_tokens', 0):6d} "
              f"{w.get('attempts', 0):9d} {w.get('tests_passed', 0):10d} "
              f"{c.get('attempts', 0):9d} {c.get('tests_passed', 0):10d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
