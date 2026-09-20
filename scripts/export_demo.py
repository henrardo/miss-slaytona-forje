#!/usr/bin/env python
"""Collect one series into a self-describing bundle for the demo.

    scripts/export_demo.py runs/swarm-A.jsonl runs/swarm-B.jsonl ...

WHY A SCRIPT AND NOT A FOLDER OF FILES. Whoever builds the presentation
did not watch these runs and cannot know which numbers mean what. Three
of the measures here are actively misleading if read at face value, and
one of them -- `tests_passed` -- is the one a reader will reach for
first. So the bundle carries the caveats next to the data, in the same
JSON, rather than in a note somebody has to find.

Everything is derived from the EVENT LOGS, which are written as the run
happens and are the only record that survived the last pod dying. The
metrics files are a convenience; where the two disagree, the log wins.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def attempts(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("type") == "ATTEMPT_DONE"]


def series_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for n, path in enumerate(sorted(paths, key=lambda p: p.stat().st_mtime), 1):
        events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        done = attempts(events)
        if not done:
            continue
        distilled = [e for e in events if e.get("type") == "DISTILLED"]
        writes = [e for e in events if e.get("type") == "STEP_WRITES"]
        arms: dict[str, dict] = {}
        for e in done:
            a = arms.setdefault(e["swarm"], {"attempts": [], "turns": 0,
                                             "tok_in": 0, "tok_out": 0})
            a["attempts"].append({
                "attempt": e.get("attempt"),
                "tests_passed": e.get("tests_passed"),
                "v1_remaining": e.get("v1_remaining"),
                "parse_ok": e.get("parse_ok"),
                "parse_total": e.get("parse_total"),
                "closeness": e.get("closeness"),
                "turns": e.get("turns_used"),
                "seconds": e.get("attempt_seconds"),
                "broke_syntax": e.get("broke_syntax"),
                "error_signature": e.get("error_signature"),
                "skill_version": e.get("skill_version"),
            })
            a["turns"] += e.get("turns_used") or 0
            a["tok_in"] += e.get("attempt_prompt_tokens") or 0
            a["tok_out"] += e.get("attempt_completion_tokens") or 0
        for a in arms.values():
            last = a["attempts"][-1]
            # FINAL and BEST are different questions and mixing them is a
            # mistake that has already been made in this project's own
            # reporting: an arm's best v1_remaining and its best closeness
            # can come from DIFFERENT attempts, and quoting them together
            # describes a tree that never existed. `final` is the tree the
            # run actually ended with. `best` is per-measure and each
            # entry names the attempt it came from.
            a["final"] = {k: last[k] for k in
                          ("tests_passed", "v1_remaining", "parse_ok",
                           "closeness")}
            def _best(key, pick):
                vals = [(x[key], x["attempt"]) for x in a["attempts"]
                        if x.get(key) is not None]
                if not vals:
                    return None
                v, att = pick(vals, key=lambda t: t[0])
                return {"value": v, "attempt": att}
            a["best"] = {
                "tests_passed": _best("tests_passed", max),
                "v1_remaining": _best("v1_remaining", min),
                "parse_ok": _best("parse_ok", max),
                "closeness": _best("closeness", max),
            }
            a["converged"] = any(x["tests_passed"] == 445 for x in a["attempts"])
            a["attempts_to_445"] = next(
                (x["attempt"] for x in a["attempts"] if x["tests_passed"] == 445),
                None)
        rows.append({
            "run": n,
            "run_id": path.stem,
            "arms": arms,
            "distillations": len(distilled),
            "distillations_accepted": sum(1 for d in distilled if d.get("accepted")),
            "repairs": sum(d.get("repairs") or 0 for d in distilled),
            "skill_versions": [d.get("version") for d in distilled if d.get("accepted")],
            "step_writes": ({k: v for k, v in writes[0].items()
                             if k not in ("t", "type")} if writes else None),
        })
    return rows


CAVEATS = {
    "tests_passed": (
        "DO NOT USE AS THE HEADLINE. On fixtures/oapi this has three "
        "effective values: 0 (the package does not import), ~310-320 (it "
        "imports, one class of ValidationError remains) and 445 (solved). "
        "The step from 0 to ~310 is 'the package imports', not 'the "
        "migration is better'. Measured: an arm left 58 of 64 v1 "
        "constructs in place, fixed the import, and scored 310, while the "
        "other arm had cleared 56 of 64 and scored 0 for one stray "
        "indent. Use it only for 445 = solved."),
    "v1_remaining": (
        "How many Pydantic-v1-only constructs are left in the package, by "
        "regex on the source. 64 = untouched. 3 = the human's merged PR, "
        "which is the floor, not 0 -- the reference still contains two "
        ".json() calls inside generated-code strings and one unrelated "
        "class Config. Defined even when the tree does not parse, which "
        "is when it matters most."),
    "parse_ok": (
        "Files in the package that still compile, out of parse_total. "
        "Read WITH v1_remaining: few surfaces left and files not parsing "
        "is 'did the work and broke it'; many surfaces and everything "
        "parsing is 'kept it valid by not doing it'. tests_passed scores "
        "both of those 0."),
    "closeness": (
        "0.0 = the untouched checkout, 1.0 = the human's merged PR. A "
        "normalised diff similarity, weighted by how much the reference "
        "changed each file, excluding files it left alone. GOOD as a "
        "gradient on partial work. MISLEADING on finished work: in run 2 "
        "both arms passed all 445 tests, yet scored 0.533 and 0.319, "
        "because they solved it differently from the human and from each "
        "other. It ranks resemblance to one implementation, not "
        "correctness. Never present it as a quality score for a solved "
        "run."),
    "step_writes": (
        "thoughts_from_reasoning vs thought_fallbacks. A fallback means "
        "the step stored serialised tool input instead of the model's "
        "reasoning. The previous series ran at 988 fallbacks out of 993 "
        "and every other number looked healthy; this series runs at 0. "
        "Any non-trivial fallback count invalidates the warm arm for that "
        "run."),
    "comparison": (
        "Warm = memory + the distilled AIP skill. Cold = neither. Those "
        "are the only intended differences and the harness refuses to "
        "start if others appear. Warm's skill is re-authored after every "
        "attempt by gpt-5.6-sol from the graph, so the skill a run starts "
        "on is the previous run's output -- runs are NOT independent, "
        "which is the point of a series and a reason not to average "
        "them."),
    "not_shown": (
        "No statistical claim is made here. This is a handful of runs on "
        "one fixture with one model. Attempt counts differ between arms "
        "within a run, so per-attempt series are not aligned."),
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    out = REPO / "runs" / "demo-export"
    out.mkdir(parents=True, exist_ok=True)
    paths = [Path(p) for p in sys.argv[1:]]
    rows = series_rows(paths)

    bundle = {
        "fixture": "openapi_python_client (fixtures/oapi)",
        "task": "migrate the package from Pydantic v1 to Pydantic v2",
        "model": "mistralai/Mistral-Small-4-119B-2603, served by SGLang 0.5.14 on one H200",
        "skill_author": "gpt-5.6-sol (external, frontier)",
        "oracle": json.loads((REPO / ".oracle-oapi.json").read_text()),
        "runs": rows,
        "how_to_read": CAVEATS,
    }
    (out / "series.json").write_text(json.dumps(bundle, indent=2))

    for path in paths:                       # the raw record, always
        shutil.copy(path, out / path.name)
        m = path.with_name(path.stem + "-metrics.json")
        if m.exists():
            shutil.copy(m, out / m.name)
        s = path.with_name(path.stem + "-series.json")
        if s.exists():
            shutil.copy(s, out / s.name)
    for extra in ("cross-run.md",):
        src = REPO / "runs" / extra
        if src.exists():
            shutil.copy(src, out / extra)

    print(f"wrote {out}/series.json  ({len(rows)} run(s))")
    for r in rows:
        line = "  ".join(
            f"{a}: {d['final']['tests_passed']:>3}/{d['final']['v1_remaining']:>2}"
            f"/{d['final']['parse_ok']}p"
            for a, d in sorted(r["arms"].items()))
        print(f"  run {r['run']}  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
