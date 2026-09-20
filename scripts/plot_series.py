#!/usr/bin/env python
"""Render the panels in `orchestrator.series` with matplotlib.

    scripts/plot_series.py runs/swarm-123.jsonl --fixture oapi
    scripts/plot_series.py 'runs/swarm-*.jsonl' --across --fixture oapi

Writes, per invocation, into `runs/plots/`:

    <name>-<panel>.png / .svg   one figure per panel
    <name>.json                 the series document the figures came from

THE JSON IS THE POINT. The figures are for looking at now; the document
is what the React components will be built from later, and it carries the
axis labels, the reference lines, the arm colours and each panel's caveat
so none of that has to be retyped into TypeScript. Anything a chart needs
to be read honestly lives in the data, not in this file.

This renderer is deliberately thin and generic -- it switches on
`panel["kind"]` and knows nothing about pydantic, memory or skills. A
panel added to series.py appears here without changes. If a figure needs
special-casing to look right, the fix belongs in the series, because the
component will hit the same problem.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from orchestrator import series as S  # noqa: E402

OUT_DIR = S.REPO_ROOT / "runs" / "plots"
GREY = "#525252"


def _finish(fig, ax, panel: dict, out: Path) -> list[Path]:
    ax.set_xlabel(panel["x_label"])
    ax.set_ylabel(panel["y_label"])
    ax.set_title(panel["title"], loc="left", fontsize=12, fontweight="bold")
    # Never on a gantt: that axis is inverted and categorical, so a
    # bottom=0 clamp hides every bar but the first. Belt and braces with
    # the panel's own y_zero=False, because a future panel kind that
    # inverts its axis would hit this again.
    if panel.get("y_starts_at_zero") and panel["kind"] != "gantt":
        ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.25, linewidth=0.6)
    # Attempt and run numbers are counts. Left alone, matplotlib offers
    # "attempt 1.5", which is not a thing that exists.
    xs = [p.get("x") for s in panel.get("series", []) for p in s["points"]]
    if xs and all(isinstance(v, int) for v in xs):
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    for note in panel.get("annotations", []):
        if note.get("kind") == "hline" and note.get("y") is not None:
            ax.axhline(note["y"], color=GREY, linestyle="--", linewidth=1)
            # INSIDE the axes, below the line. Above it, the label for a
            # reference at the top of the data range (the answer key is
            # the maximum by definition) sticks out past the axes, and
            # tight_layout abandons the whole figure -- which overlaps the
            # caveat, the one thing that must stay readable.
            ax.annotate(note.get("label", ""), xy=(0.995, note["y"]),
                        xycoords=("axes fraction", "data"),
                        xytext=(0, -3), textcoords="offset points",
                        ha="right", va="top", fontsize=8, color=GREY,
                        annotation_clip=False, clip_on=True)
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(frameon=False, fontsize=9)
    # The caveat is rendered, not stored and forgotten. A panel whose
    # caveat is only in the JSON is a panel that will be screenshotted
    # without it.
    #
    # The space it needs is computed from how many lines it wraps to. A
    # fixed fraction made matplotlib give up on the layout for the three
    # panels with the longest caveats -- and giving up means it overlaps
    # the axis label, so the caveat is exactly what stops being readable.
    caption = textwrap.fill(panel["caveat"], 110)
    lines = caption.count("\n") + 1
    height = fig.get_size_inches()[1]
    reserved = min(0.4, (lines * 0.135 + 0.16) / height)
    fig.text(0.01, 0.01, caption, fontsize=7, color=GREY, va="bottom")
    fig.tight_layout(rect=(0, reserved, 1, 1))
    written = []
    for suffix in (".png", ".svg"):
        path = out.with_suffix(suffix)
        fig.savefig(path, dpi=160)
        written.append(path)
    plt.close(fig)
    return written


def _xy(points: list[dict]) -> tuple[list, list]:
    keep = [p for p in points if p.get("y") is not None]
    return [p["x"] for p in keep], [p["y"] for p in keep]


def render(panel: dict, out: Path) -> list[Path]:
    kind = panel["kind"]
    # A gantt grows a row per attempt, and a 22-attempt cold arm does not
    # fit a fixed canvas -- matplotlib warns and then overlaps the labels,
    # which is worse than a tall figure.
    rows = sum(len(s["points"]) for s in panel["series"]) if kind == "gantt" else 0
    fig, ax = plt.subplots(figsize=(8, max(4.6, 1.4 + 0.26 * rows)))

    if kind in ("line", "step"):
        for s in panel["series"]:
            xs, ys = _xy(s["points"])
            if not xs:
                continue
            drawer = ax.step if kind == "step" else ax.plot
            kw = {"where": "post"} if kind == "step" else {}
            drawer(xs, ys, marker="o", markersize=4, color=s["colour"],
                   label=s["label"], **kw)
            # Gaps are meaningful (see attempts_to_converge): mark where a
            # point was undefined so a missing marker is not read as a
            # missing run.
            for p in s["points"]:
                if p.get("y") is None:
                    ax.annotate("n/a", xy=(p["x"], 0), fontsize=7,
                                color=s["colour"], ha="center", va="bottom")
        for arm, fit in (panel.get("fits") or {}).items():
            xs = [p["x"] for s in panel["series"] if s["arm"] == arm
                  for p in s["points"]]
            if not xs:
                continue
            lo, hi = min(xs), max(xs)
            ax.plot([lo, hi],
                    [fit["intercept"] + fit["slope"] * lo,
                     fit["intercept"] + fit["slope"] * hi],
                    linestyle=":", linewidth=1.2,
                    color=S.ARM_STYLE.get(arm, {}).get("colour", GREY),
                    label=f"{arm} trend: {fit['slope']:+.1f}/run "
                          f"(p={fit['p_value']:.2f}, R²={fit['r_squared']:.2f})")

    elif kind == "scatter":
        for s in panel["series"]:
            xs, ys = _xy(s["points"])
            ax.scatter(xs, ys, s=42, color=s["colour"], label=s["label"],
                       alpha=0.85, edgecolor="white", linewidth=0.6)

    elif kind in ("bar", "grouped_bar"):
        groups = []
        for s in panel["series"]:
            for p in s["points"]:
                if p["x"] not in groups:
                    groups.append(p["x"])
        n = max(len(panel["series"]), 1)
        width = 0.8 / n
        for i, s in enumerate(panel["series"]):
            lookup = {p["x"]: p.get("y") or 0 for p in s["points"]}
            offsets = [groups.index(g) - 0.4 + width * (i + 0.5)
                       for g in groups]
            ax.bar(offsets, [lookup.get(g, 0) for g in groups], width=width,
                   color=s["colour"], label=s["label"])
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([str(g) for g in groups], fontsize=8)

    elif kind == "gantt":
        row = 0
        labels = []
        for s in panel["series"]:
            for p in s["points"]:
                start, end = p.get("start"), p.get("end")
                if start is None or end is None:
                    continue
                ax.barh(row, max(end - start, 0.1), left=start, height=0.6,
                        color=s["colour"])
                labels.append(f"{s['label']}: {p.get('label', '')}")
                row += 1
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.invert_yaxis()

    else:
        ax.text(0.5, 0.5, f"no renderer for kind={kind!r}", ha="center")

    return _finish(fig, ax, panel, out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+",
                    help="event log paths or globs, oldest first")
    ap.add_argument("--across", action="store_true",
                    help="one document over all the logs, run index on x")
    ap.add_argument("--fixture", default="oapi",
                    help="which fixture's measured oracle to draw as "
                         "reference lines (.oracle-<name>.json)")
    ap.add_argument("--name", default="",
                    help="output basename; defaults to the run id")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    paths: list[Path] = []
    for pattern in args.logs:
        found = sorted(Path(p) for p in glob.glob(pattern))
        paths.extend(found or [Path(pattern)])
    missing = [p for p in paths if not p.is_file()]
    if missing:
        print(f"ERROR: no such event log: {missing[0]}")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.across:
        runs = [{"run_id": p.stem, "fixture": args.fixture,
                 "events": S.load_events(p)} for p in paths]
        doc = S.across_runs(runs)
        name = args.name or f"across-{args.fixture}-{len(paths)}runs"
    else:
        if len(paths) != 1:
            print("ERROR: one log without --across, or use --across")
            return 2
        doc = S.within_run(S.load_events(paths[0]), run_id=paths[0].stem,
                           fixture=args.fixture)
        name = args.name or paths[0].stem

    if not doc.get("oracle"):
        print(f"note: no .oracle-{args.fixture}.json -- reference lines "
              f"(answer key, floor) are omitted rather than guessed. "
              f"Run scripts/grade_fixture.py to produce it.")

    doc_path = args.out_dir / f"{name}.json"
    doc_path.write_text(json.dumps(doc, indent=2) + "\n")
    written = [doc_path]
    for panel in doc["panels"]:
        written += render(panel, args.out_dir / f"{name}-{panel['id']}")

    print(f"{doc['scope']}: {len(doc['panels'])} panel(s), arms "
          f"{doc['arms']}")
    if doc.get("effect"):
        e = doc["effect"]
        print(f"effect (warm - cold, best passing): {e['mean_difference']:+.1f} "
              f"[{e['ci95'][0]:+.1f}, {e['ci95'][1]:+.1f}] over "
              f"{e['n_runs']} run(s)"
              + ("  -- CROSSES ZERO: no difference shown"
                 if e["crosses_zero"] else ""))
    elif doc["scope"] == "across_runs":
        print("effect: not computed -- fewer than 3 paired runs")
    for path in written:
        print(f"  {path.relative_to(S.REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
