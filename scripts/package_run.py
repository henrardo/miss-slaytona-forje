#!/usr/bin/env python3
"""Bundle one run into something someone else can build a deck from.

    .venv/bin/python scripts/package_run.py runs/swarm-1789987670.jsonl

Everything is derived from the event log, so the bundle can be rebuilt at
any time and cannot disagree with the record. Nothing here decides how to
draw anything: `orchestrator/series.py` owns the panels and this script
only calls it, because the panels are the harness's own document and
editing them to flatter a run is exactly the temptation to remove.

Writes `-metrics.json` and `-series.json` if the run did not get to write
them itself. A run killed before RUN_END -- which is every run stopped
mid-convergence, including the one this script was written for -- has an
event log and nothing else.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import metrics as M       # noqa: E402
from orchestrator import series            # noqa: E402

# Per-attempt fields are flattened from these events onto the ATTEMPT_DONE
# row for the same (swarm, attempt), so one row is one graded attempt.
FOLD_IN = {
    "MEMORY_WRITE": "memory_write_",
    "ATTEMPT_REJECTED": "rejected_",
    "ATTEMPT_ABORTED": "aborted_",
    "DISTILLED": "distilled_",
    "INGESTED": "ingested_",
}

FILE_NOTES = {
    "jsonl": "every event, in order, with a `t` in seconds since the run "
             "started. The replayable record.",
    "series": "the harness's own chart document: panels, annotations, axis "
              "decisions and a caveat per panel. deck/src/charts/Panel.tsx "
              "renders this and decides nothing itself.",
    "metrics": "the per-run summary the cross-run table is built from.",
    "attempts.json": "one row per graded attempt, with the memory write, the "
                     "rewrite, any rejection and the ingest folded in. "
                     "Derived from the jsonl; nothing new.",
    "attempts.csv": "the same table, flat.",
    "experiment.json": "what the experiment was and how to read it.",
    "skill-final.md": "the procedure Cognee held when the run ended.",
    "trees/": "the package tree after every attempt, one tarball each. "
              "`closeness` and the v1 count can be recomputed from these.",
    "console.log": "stdout of the run, if it was captured.",
}


def load(path: Path) -> list[dict]:
    events = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def attempt_rows(events: list[dict]) -> list[dict]:
    rows: dict[tuple[str, int], dict] = {}
    for e in events:
        if e.get("type") != "ATTEMPT_DONE":
            continue
        row = {k: v for k, v in e.items() if k != "type"}
        rows[(e.get("swarm"), e.get("attempt"))] = row
    for e in events:
        prefix = FOLD_IN.get(e.get("type") or "")
        if prefix is None:
            continue
        row = rows.get((e.get("swarm"), e.get("attempt")))
        if row is None:
            continue
        for k, v in e.items():
            if k in ("type", "swarm", "agent", "attempt", "t"):
                continue
            row[f"{prefix}{k}"] = v
    return [rows[k] for k in sorted(rows, key=lambda k: (k[1], str(k[0])))]


def derived_documents(log: Path, events: list[dict], run_id: str,
                      fixture: str) -> list[Path]:
    """The two documents a run writes at RUN_END, for runs that never got there."""
    written = []
    end = next((e for e in events if e.get("type") == "RUN_END"), {})
    metrics_path = log.with_name(f"{log.stem}-metrics.json")
    if not metrics_path.exists():
        start = next((e for e in events if e.get("type") == "RUN_START"), {})
        # The run's own call fills these from the runner's arguments and
        # its arm fingerprint, neither of which is in the event log.
        # Recorded as absent rather than guessed: a fabricated commit or a
        # fabricated `arms_identical` would read as a measurement, and
        # `counts_toward_clearly_working` is computed from the latter.
        collected = M.collect(
            events, run_id=run_id,
            gpu=start.get("gpu") or end.get("gpu") or "(not recorded)",
            model=start.get("model") or end.get("model") or "",
            commit=start.get("commit") or "",
            skill_version=0, skill_approx_tokens=0, skill_dir_sha="",
            arms_identical=bool(start.get("arms_identical", False)),
            known_differences=list(start.get("known_differences") or []),
            gpu_usd_per_hour=float(end.get("gpu_usd_per_hour")
                                   or start.get("gpu_usd_per_hour") or 0.0))
        M.write(collected, runs_dir=log.parent)
        written.append(metrics_path)
    series_path = log.with_name(f"{log.stem}-series.json")
    if not series_path.exists():
        series_path.write_text(json.dumps(
            series.within_run(events, run_id=run_id, fixture=fixture),
            indent=2) + "\n")
        written.append(series_path)
    return written


def main(argv: list[str]) -> int:
    log = Path(argv[1]) if len(argv) > 1 else None
    if log is None:
        logs = sorted(Path("runs").glob("swarm-*.jsonl"))
        log = logs[-1] if logs else None
    if log is None or not log.exists():
        print("usage: package_run.py runs/swarm-<id>.jsonl")
        return 2

    run_id = log.stem
    events = load(log)
    rows = attempt_rows(events)
    if not rows:
        print(f"{log} records no graded attempt -- nothing to package")
        return 1
    fixture = next((e.get("fixture") for e in events if e.get("fixture")),
                   "x12sdk")

    out = REPO / "runs" / "packages" / run_id
    out.mkdir(parents=True, exist_ok=True)
    derived = derived_documents(log, events, run_id, fixture)

    shutil.copy(log, out / log.name)
    for name in (f"{run_id}-metrics.json", f"{run_id}-series.json"):
        src = log.with_name(name)
        if src.exists():
            shutil.copy(src, out / name)

    experiment = REPO / "runs" / "experiments" / run_id
    for name in ("experiment.json", "skill-final.md"):
        if (experiment / name).exists():
            shutil.copy(experiment / name, out / name)
    if (experiment / "trees").is_dir():
        trees = out / "trees"
        trees.mkdir(exist_ok=True)
        for tgz in sorted((experiment / "trees").glob("*.tgz")):
            shutil.copy(tgz, trees / tgz.name)

    (out / "attempts.json").write_text(json.dumps(rows, indent=2) + "\n")
    columns = sorted({k for row in rows for k in row})
    with (out / "attempts.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (json.dumps(v) if isinstance(v, (dict, list))
                                 else v) for k, v in row.items()})

    console = next((p for p in sorted((REPO / "runs").glob("experiment-*.log"),
                                      key=lambda p: p.stat().st_mtime,
                                      reverse=True)), None)
    if console is not None:
        shutil.copy(console, out / "console.log")

    counts: dict[str, int] = {}
    for e in events:
        counts[e.get("type") or "?"] = counts.get(e.get("type") or "?", 0) + 1
    present = {}
    for path in sorted(out.iterdir()):
        key = ("jsonl" if path.suffix == ".jsonl" else
               "series" if path.name.endswith("-series.json") else
               "metrics" if path.name.endswith("-metrics.json") else
               ("trees/" if path.is_dir() else path.name))
        if key in FILE_NOTES:
            present[path.name + ("/" if path.is_dir() else "")] = FILE_NOTES[key]
    (out / "MANIFEST.json").write_text(json.dumps({
        "run_id": run_id,
        "fixture": fixture,
        "events": len(events),
        "event_types": dict(sorted(counts.items())),
        "attempts": len(rows),
        "files": present,
    }, indent=2) + "\n")

    tgz = out.with_suffix(".tgz")
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(out, arcname=out.name)

    print(f"packaged {run_id} -> {out}")
    if derived:
        print(f"  generated (the run stopped before RUN_END): "
              f"{', '.join(p.name for p in derived)}")
    print(f"  {len(rows)} attempt(s), {len(events)} event(s), "
          f"{len(list((out / 'trees').glob('*.tgz'))) if (out / 'trees').is_dir() else 0} tree(s)")
    print(f"  {tgz} "
          f"({subprocess.run(['du', '-h', str(tgz)], capture_output=True, text=True).stdout.split()[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
