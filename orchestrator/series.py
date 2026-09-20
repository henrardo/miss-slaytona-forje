"""Event logs -> chart-ready series. The data layer under every figure.

WHY THIS IS A MODULE AND NOT PART OF A PLOT SCRIPT. The figures are going
to be rebuilt as React components for the demonstration, and the thing
that must survive that port is the DATA and the domain knowledge attached
to it -- which reference lines a panel carries, what its floor is, what
makes it honest to read. If that lives in matplotlib calls it gets
retyped by hand into TypeScript, and the retyping is where "the floor is
3, not 0" quietly becomes a y-axis starting at zero.

So this emits a self-describing document. Every panel says what kind of
chart it is, what its axes mean, which series belong to which arm, what
its reference lines are and where they came from, and -- the part that
matters most -- what would make it misleading. `scripts/plot_series.py`
renders it with matplotlib; a component later renders the same document
without re-deriving anything.

TWO SCOPES.

    within-run   one run's attempts, warm vs cold. Answers "did the arms
                 behave differently THIS time".
    across-runs  the skill persists between runs -- run N distils from
                 its own graded attempts and run N+1 starts on it -- so
                 the run index is the real x axis of the experiment, and
                 cold is the flat control that says whether the task or
                 the server drifted underneath.

EVERYTHING COMES OFF `runs/<id>.jsonl`. Not the graph, not a transcript,
not the metrics file. The event log is written whether or not anything
downstream runs, so a charting bug cannot corrupt the record it draws,
and re-running this against the same log always produces the same
document. The one exception is the oracle reference
(`.oracle-<fixture>.json`, written by scripts/grade_fixture.py), which is
a measurement of the FIXTURE rather than of a run.

READING ANY OF IT HONESTLY. One run per point and no repeats. The
measured run-to-run spread at a FIXED skill version was 14%-138% on
tokens and 27-93 turns, so a trend over several runs is suggestive and
two adjacent points are not a result. Every panel carries its own
`caveat` string saying the specific version of this; the renderer is
expected to show it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"

SCHEMA_VERSION = 1

# Arm colours are named here, not in the renderer, so the matplotlib
# figure and the React component cannot disagree about which line is warm.
ARM_STYLE = {
    "warm": {"colour": "#c2410c", "label": "warm (memory + skill)"},
    "cold": {"colour": "#0369a1", "label": "cold (control)"},
}


def load_events(path: Path) -> list[dict]:
    """One run's events, in order. Blank and broken lines are skipped.

    A run killed mid-write leaves a partial final line; refusing to read
    the whole log because of it would throw away the run that is most
    worth looking at.
    """
    events = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def oracle_for(fixture: str) -> dict:
    """The fixture's own measured baseline and answer key, or {}.

    Written by scripts/grade_fixture.py. Absent means nobody has graded
    the answer key on this fixture, and a panel that would draw a
    reference line says so instead of inventing one.
    """
    path = REPO_ROOT / f".oracle-{fixture}.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def _arm(event: dict) -> str:
    return event.get("swarm") or "unknown"


def _by_arm(events: Iterable[dict], kind: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in events:
        if e.get("type") == kind:
            out.setdefault(_arm(e), []).append(e)
    return out


def _panel(id: str, title: str, kind: str, x: str, y: str, series: list[dict],
           *, caveat: str, annotations: list[dict] | None = None,
           y_zero: bool = True, **extra: Any) -> dict:
    return {"id": id, "title": title, "kind": kind, "x_label": x,
            "y_label": y, "series": series, "annotations": annotations or [],
            # Whether starting the y axis at zero is honest for this panel.
            # False where the interesting range is a narrow band near the
            # top and a zero-based axis flattens every difference into one
            # line -- which is how "445 vs 429" stops being visible.
            "y_starts_at_zero": y_zero, "caveat": caveat, **extra}


def _arm_series(label: str, arm: str, points: list[dict]) -> dict:
    style = ARM_STYLE.get(arm, {"colour": "#525252", "label": arm})
    return {"label": label or style["label"], "arm": arm,
            "colour": style["colour"], "points": points}


# ---------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------

def within_run(events: list[dict], *, run_id: str = "",
               fixture: str = "") -> dict:
    """Panels describing a single run's attempts."""
    oracle = oracle_for(fixture) if fixture else {}
    done = _by_arm(events, "ATTEMPT_DONE")
    ingested = _by_arm(events, "INGESTED")
    distilled = _by_arm(events, "DISTILLED")
    restored = _by_arm(events, "RESTORED")
    rejected = _by_arm(events, "ATTEMPT_REJECTED")
    aborted = _by_arm(events, "ATTEMPT_ABORTED")
    reads = _by_arm(events, "MEMORY_READ")
    arms = sorted(done)

    panels: list[dict] = []

    # 1. Convergence. BEST-SO-FAR, not per-attempt: the harness rolls back
    #    to the best tree, so best-so-far is what the agent actually still
    #    has. Per-attempt is panel 2 and they differ precisely where a
    #    rollback happened, which is the interesting place.
    best_series = []
    for arm in arms:
        best, points = 0, []
        for e in done[arm]:
            best = max(best, e.get("tests_passed") or 0)
            points.append({"x": e.get("attempt"), "y": best,
                           "raw": e.get("tests_passed")})
        best_series.append(_arm_series("", arm, points))
    ceiling = oracle.get("answer_key_passed")
    panels.append(_panel(
        "convergence", "Best tests passing so far", "step",
        "attempt", "tests passing (best so far)", best_series,
        annotations=([{"kind": "hline", "y": ceiling,
                       "label": f"answer key = {ceiling}",
                       "note": "the human's own merged PR, on this grader"}]
                     if ceiling else []),
        # A zero-based axis is right here: 0 is a real and common outcome.
        caveat="Monotone by construction -- the harness restores the best "
               "tree after a regression. A flat line means no attempt "
               "beat the first, not that nothing happened."))

    # 2. Per-attempt score. The bimodality lives here: measured over 77
    #    graded attempts, 70% scored exactly 0, 13% ~300, 17% >=420.
    panels.append(_panel(
        "attempt_score", "Tests passing, per attempt", "scatter",
        "attempt", "tests passing", [
            _arm_series("", arm, [{"x": e.get("attempt"),
                                   "y": e.get("tests_passed"),
                                   "signature": e.get("error_signature"),
                                   "ended_cleanly": e.get("ended_cleanly")}
                                  for e in done[arm]])
            for arm in arms],
        annotations=([{"kind": "hline", "y": ceiling,
                       "label": f"answer key = {ceiling}"}] if ceiling else []),
        caveat="0 means two opposite things -- migration not started, or "
               "the agent broke the package so the suite cannot import. "
               "Read this panel WITH v1_remaining, never alone."))

    # 3. Work remaining. The panel that separates progress from damage,
    #    which is why it exists at all -- see orchestrator/surfaces.py.
    floor = oracle.get("answer_key_v1_surfaces")
    start = oracle.get("baseline_v1_surfaces")
    notes = []
    if start is not None:
        notes.append({"kind": "hline", "y": start,
                      "label": f"pre-migration = {start}"})
    if floor is not None:
        notes.append({"kind": "hline", "y": floor,
                      "label": f"floor = {floor} (a COMPLETED migration)",
                      "note": "not zero: the merged PR still counts this "
                              "many, so the axis must not imply 0 is the "
                              "target"})
    panels.append(_panel(
        "work_remaining", "Pydantic v1 surfaces left in the package", "line",
        "attempt", "v1-only constructs remaining", [
            _arm_series("", arm, [{"x": e.get("attempt"),
                                   "y": e.get("v1_remaining")}
                                  for e in done[arm]
                                  if e.get("v1_remaining") is not None])
            for arm in arms],
        annotations=notes,
        caveat="A source count, not an oracle: reaching the floor does not "
               "mean the migration is correct, only that the v1 spellings "
               "are gone. The suite remains the only thing that decides."))

    # 3b. IS THE CODE INTACT, and how far along the path is it? The two
    #     measures that answer "who wrote better code", which
    #     `tests_passed` cannot: on fixtures/oapi it is 0 / ~310 / 445 and
    #     the step to ~310 is "the package imports". An agent that leaves
    #     58 of 64 v1 surfaces but fixes the import scores 310; one that
    #     migrates all but one file and leaves a stray indent scores 0.
    panels.append(_panel(
        "files_parsing", "Files in the package that still compile", "line",
        "attempt", "files parsing", [
            _arm_series("", arm, [{"x": e.get("attempt"), "y": e.get("parse_ok")}
                                  for e in done[arm]
                                  if e.get("parse_ok") is not None])
            for arm in arms],
        caveat="Read WITH work_remaining. Few surfaces left and files not "
               "parsing is 'did the work and broke it'; many surfaces and "
               "everything parsing is 'kept it valid by not doing it'. Both "
               "score 0 on the suite."))
    # ABSENT, not empty, when the fixture ships no reference answer. A
    # panel with no points reads as "the measure broke"; the honest
    # statement is that this fixture cannot support the measure.
    if any(e.get("closeness") is not None
           for arm in arms for e in done[arm]):
      panels.append(_panel(
        "closeness", "Distance travelled from v1 to the merged PR", "line",
          "attempt", "0 = untouched, 1 = the human's answer", [
              _arm_series("", arm, [{"x": e.get("attempt"), "y": e.get("closeness")}
                                    for e in done[arm]
                                    if e.get("closeness") is not None])
              for arm in arms],
          annotations=[{"kind": "hline", "y": 1.0, "label": "the merged PR"},
                       {"kind": "hline", "y": 0.0, "label": "untouched checkout"}],
          caveat="A normalised diff similarity, weighted by how much the "
                 "reference changed each file; files it left alone are "
                 "excluded. RAW similarity to the answer is useless here -- "
                 "the untouched tree scores 0.915 of it. Approximate: an "
                 "agent that migrates correctly in different words is "
                 "under-credited, so this ranks the arms against each other "
                 "rather than grading either."))

    # 4. Cost. Attempt tokens and distillation tokens are kept apart on
    #    purpose -- "the skill made the agent cheaper" and "the skill was
    #    cheap to produce" are two claims and one total answers neither.
    burn = []
    for arm in arms:
        total, points = 0, []
        for e in done[arm]:
            total += (e.get("attempt_prompt_tokens") or 0) + \
                     (e.get("attempt_completion_tokens") or 0)
            points.append({"x": e.get("attempt"), "y": total})
        burn.append(_arm_series("", arm, points))
    panels.append(_panel(
        "token_burn", "Cumulative attempt tokens", "line",
        "attempt", "tokens (prompt + completion)", burn,
        caveat="ATTEMPT tokens only. Distillation is off the clock and "
               "counted separately -- see the distillation panel. Warm's "
               "prompt carries the skill, so a bigger skill costs warm "
               "tokens on every turn and that is a real cost, not noise."))

    # 5. Efficiency. The scatter is the honest form: a ratio would divide
    #    by zero on the 70% of attempts that score 0.
    panels.append(_panel(
        "efficiency", "Score against spend, per attempt", "scatter",
        "tokens spent on the attempt", "tests passing", [
            _arm_series("", arm, [
                {"x": (e.get("attempt_prompt_tokens") or 0)
                      + (e.get("attempt_completion_tokens") or 0),
                 "y": e.get("tests_passed"), "attempt": e.get("attempt")}
                for e in done[arm]])
            for arm in arms],
        caveat="Deliberately not a tokens-per-test ratio: most attempts "
               "score 0 and the ratio is undefined for them, so a mean "
               "would be computed over the minority that happened to pass."))

    # 6. What memory actually did. "The graph was written" and "the agent
    #    read from it" are different claims and both have been silently
    #    false before, so both are counted.
    mem_points = []
    for arm in sorted(ingested):
        mem_points.append(_arm_series(
            f"{arm}: steps written", arm,
            [{"x": e.get("attempt"), "y": e.get("steps"),
              "with_reasoning": e.get("with_reasoning"),
              "tool_calls": e.get("tool_calls"),
              "failed_tool_calls": e.get("failed_tool_calls")}
             for e in ingested[arm]]))
    for arm in sorted(reads):
        mem_points.append({
            "label": f"{arm}: agent's own retrievals", "arm": arm,
            "colour": "#7c3aed",
            "points": [{"x": e.get("attempt"), "y": e.get("hits"),
                        "sources": e.get("sources")} for e in reads[arm]]})
    panels.append(_panel(
        "memory_activity", "Graph writes and agent retrievals", "bar",
        "attempt", "count", mem_points,
        caveat="Zero retrievals is a finding, not a gap in the chart: it "
               "means the agent had memory and chose not to use it. "
               "Writes happening while retrievals stay at 0 is the exact "
               "shape that went unnoticed for ~40 runs."))

    # 7. The skill's own history within the run.
    distil_points = []
    for arm in sorted(distilled):
        distil_points.append(_arm_series(
            f"{arm}: distillation", arm,
            [{"x": e.get("attempt"), "y": e.get("version"),
              "accepted": bool(e.get("accepted")),
              "repairs": e.get("repairs"),
              "seconds": e.get("seconds"),
              "memory_tool_calls": e.get("memory_tool_calls"),
              "eligible_traces": e.get("eligible_traces"),
              "reason": e.get("reason")}
             for e in distilled[arm]]))
    panels.append(_panel(
        "skill_history", "Skill version, and what each attempt ran on",
        "step", "attempt", "skill version", [
            _arm_series("", arm, [{"x": e.get("attempt"),
                                   "y": e.get("skill_version")}
                                  for e in done[arm]
                                  if e.get("skill_version") is not None])
            for arm in arms] + distil_points,
        y_zero=False,
        caveat="Distillation happens AFTER an attempt, so attempt N's "
               "result belongs to the version that existed before it. A "
               "rejected proposal leaves the version unchanged and is "
               "marked -- rejections are the interesting points."))

    # 8. Stability. Six runs once scored either ~440 or 0 and never in
    #    between; rollbacks are the mechanism that was missing, so how
    #    often they fire is a first-class number.
    stability = []
    for arm in arms:
        stability.append({
            "label": ARM_STYLE.get(arm, {}).get("label", arm), "arm": arm,
            "colour": ARM_STYLE.get(arm, {}).get("colour", "#525252"),
            "points": [
                {"x": "attempts", "y": len(done.get(arm, []))},
                {"x": "rolled back", "y": len(restored.get(arm, []))},
                {"x": "rejected (shim/gutted)", "y": len(rejected.get(arm, []))},
                {"x": "aborted (no turn)", "y": len(aborted.get(arm, []))},
                {"x": "ended cleanly",
                 "y": sum(1 for e in done.get(arm, [])
                          if e.get("ended_cleanly"))},
            ]})
    panels.append(_panel(
        "stability", "How attempts ended", "grouped_bar",
        "outcome", "attempts", stability,
        caveat="A rollback is not a failure -- it is the harness keeping "
               "the best tree after a regression. A silent rollback and an "
               "agent that recovered by itself look identical without this."))

    # 9. Timeline. The arms share a barrier; whether they actually ran
    #    together is a property of the run that no summary number carries.
    spans = []
    for arm in arms:
        spans.append(_arm_series("", arm, [
            {"start": (e.get("t") or 0) - (e.get("attempt_seconds") or 0),
             "end": e.get("t"), "label": f"attempt {e.get('attempt')}",
             "y": e.get("attempt")}
            for e in done[arm]]))
    for arm in sorted(distilled):
        spans.append({
            "label": f"{arm}: distillation (off the clock)", "arm": arm,
            "colour": "#7c3aed",
            "points": [{"start": (e.get("t") or 0) - (e.get("seconds") or 0),
                        "end": e.get("t"),
                        "label": f"distil after attempt {e.get('attempt')}",
                        "y": e.get("attempt")}
                       for e in distilled[arm]]})
    panels.append(_panel(
        "timeline", "When each arm was working", "gantt",
        "seconds since run start", "attempt", spans,
        # The y axis is a list of bars, not a quantity, so "starts at
        # zero" is meaningless here -- and actively wrong: the renderer
        # inverts this axis, and forcing ylim(bottom=0) on an inverted
        # axis collapses the view onto the first bar. Eleven of twelve
        # spans vanished and the panel read as "only cold ever ran".
        y_zero=False,
        caveat="Distillation bars are OFF the attempt clock -- the deadline "
               "is extended by their duration, so warm does not lose "
               "thinking time to bookkeeping. If the arms are not "
               "overlapping, they were not running concurrently and the "
               "wall-clock comparison is worthless."))

    # The run's own terminal event, when it has one. Its ABSENCE is the
    # information: no RUN_END means the run did not reach the end, which
    # for this project usually means the pod died. A chart drawn from a
    # truncated run must be able to say so.
    end = next((e for e in reversed(events) if e.get("type") == "RUN_END"),
               None)
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "within_run",
        "run_id": run_id,
        "fixture": fixture,
        "oracle": oracle,
        "arms": arms,
        "panels": panels,
        "completed": end is not None,
        "cost": {
            "gpu": (end or {}).get("gpu"),
            "model": (end or {}).get("model"),
            "gpu_usd_per_hour": (end or {}).get("gpu_usd_per_hour"),
            # None means "unknown", never zero -- see metrics.RunMetrics.
            "gpu_usd": (end or {}).get("gpu_usd"),
            "run_seconds": (end or {}).get("run_seconds"),
            "attempt_tokens": {
                arm: sum((e.get("attempt_prompt_tokens") or 0)
                         + (e.get("attempt_completion_tokens") or 0)
                         for e in done[arm]) for arm in arms},
            "note": ("GPU spend covers this RUN only; provisioning and the "
                     "model download happen before the first event."),
        },
        "incomplete_note": (
            None if end is not None else
            "NO RUN_END -- this log stops mid-run. Totals here are of what "
            "was recorded before it stopped, not of what the run intended."),
    }


# ---------------------------------------------------------------------
# Across runs -- the experiment's actual x axis
# ---------------------------------------------------------------------

def _linfit(xs: list[float], ys: list[float]) -> dict | None:
    """Least-squares trend with its p value, or None if underdetermined.

    Imported lazily: the run path must not depend on scipy, and a plotting
    dependency that a run imports is a plotting dependency that can stop a
    run from starting.
    """
    if len(xs) < 3:
        return None
    from scipy import stats
    fit = stats.linregress(xs, ys)
    return {"slope": float(fit.slope), "intercept": float(fit.intercept),
            "r_squared": float(fit.rvalue ** 2), "p_value": float(fit.pvalue),
            "stderr": float(fit.stderr), "n": len(xs)}


def _paired_difference(warm: list[float], cold: list[float]) -> dict | None:
    """Bootstrap CI on the per-run warm-minus-cold difference.

    Paired, because warm and cold share a run: the same server, the same
    hour, the same fixture. An unpaired test would throw that away and
    attribute run-to-run drift to the arms.
    """
    pairs = [(w, c) for w, c in zip(warm, cold)
             if w is not None and c is not None]
    if len(pairs) < 3:
        return None
    import numpy as np
    from scipy import stats
    diffs = np.array([w - c for w, c in pairs], dtype=float)
    res = stats.bootstrap((diffs,), np.mean, confidence_level=0.95,
                          n_resamples=10_000, method="percentile",
                          random_state=0)
    low, high = (float(res.confidence_interval.low),
                 float(res.confidence_interval.high))
    return {
        "mean_difference": float(diffs.mean()),
        "ci95": [low, high],
        "n_runs": len(pairs),
        # Said explicitly so nobody has to infer it from whether the
        # interval happens to look wide on a chart.
        "crosses_zero": bool(low <= 0 <= high),
    }


def across_runs(runs: list[dict]) -> dict:
    """Panels over a series of runs. `runs` is [{run_id, events, ...}].

    In order, oldest first. The order is the caller's: run ids are
    timestamps and other fixtures' runs are interleaved in runs/.
    """
    rows = []
    for index, run in enumerate(runs, start=1):
        done = _by_arm(run["events"], "ATTEMPT_DONE")
        file_done = _by_arm(run["events"], "FILE_DONE")
        distilled = _by_arm(run["events"], "DISTILLED")
        row: dict[str, Any] = {"index": index, "run_id": run.get("run_id", ""),
                               "arms": {}}
        for arm in sorted(done):
            attempts = done[arm]
            converged = any(e.get("success") for e in file_done.get(arm, []))
            # Undefined, NOT the attempt count, when a run never converged.
            # Substituting the count silently turns "never got there" into
            # "got there on the last attempt", which is the opposite claim.
            first_pass = next((e.get("attempt") for e in attempts
                               if e.get("tests_passed")
                               and e.get("exit_code") == 0), None)
            row["arms"][arm] = {
                "best_passed": max((e.get("tests_passed") or 0)
                                   for e in attempts) if attempts else 0,
                "attempts": len(attempts),
                "converged": converged,
                "attempts_to_converge": first_pass,
                "tokens": sum((e.get("attempt_prompt_tokens") or 0)
                              + (e.get("attempt_completion_tokens") or 0)
                              for e in attempts),
                "turns": sum(e.get("turns_used") or 0 for e in attempts),
                "best_v1_remaining": min(
                    [e["v1_remaining"] for e in attempts
                     if e.get("v1_remaining") is not None], default=None),
                # The headline the suite cannot give. Best = furthest
                # along the path this arm ever got in the run, whether or
                # not the tree happened to import at that moment.
                "best_closeness": max(
                    [e["closeness"] for e in attempts
                     if e.get("closeness") is not None], default=None),
                "final_closeness": next(
                    (e["closeness"] for e in reversed(attempts)
                     if e.get("closeness") is not None), None),
                "best_parse_ok": max(
                    [e["parse_ok"] for e in attempts
                     if e.get("parse_ok") is not None], default=None),
                "skill_version_at_start": next(
                    (e.get("skill_version") for e in attempts), None),
                "distillations_accepted": sum(
                    1 for e in distilled.get(arm, []) if e.get("accepted")),
                "distillations": len(distilled.get(arm, [])),
            }
        rows.append(row)

    arms = sorted({a for r in rows for a in r["arms"]})
    oracle = oracle_for(runs[0].get("fixture", "")) if runs else {}
    ceiling = oracle.get("answer_key_passed")

    def column(arm: str, key: str) -> list:
        return [r["arms"].get(arm, {}).get(key) for r in rows]

    xs = [float(r["index"]) for r in rows]
    panels: list[dict] = []

    headline = []
    fits = {}
    for arm in arms:
        ys = column(arm, "best_passed")
        headline.append(_arm_series("", arm, [
            {"x": r["index"], "y": y, "run_id": r["run_id"],
             "converged": r["arms"].get(arm, {}).get("converged"),
             "skill_version": r["arms"].get(arm, {}).get(
                 "skill_version_at_start")}
            for r, y in zip(rows, ys)]))
        fit = _linfit(xs, [float(y or 0) for y in ys])
        if fit:
            fits[arm] = fit
    panels.append(_panel(
        "best_by_run", "Best tests passing, run over run", "line",
        "run index (times the skill has been rewritten)",
        "best tests passing", headline,
        annotations=([{"kind": "hline", "y": ceiling,
                       "label": f"answer key = {ceiling}"}] if ceiling else []),
        y_zero=True, fits=fits,
        caveat="THE headline panel. The skill persists between runs and "
               "cold starts from nothing every time, so cold is the "
               "control that says whether the task or the server drifted. "
               "One run per point, no repeats: a trend over several is "
               "suggestive, two adjacent points are not a result."))

    converge = []
    undefined = 0
    for arm in arms:
        pts = []
        for r in rows:
            v = r["arms"].get(arm, {}).get("attempts_to_converge")
            if v is None:
                undefined += 1
            pts.append({"x": r["index"], "y": v})
        converge.append(_arm_series("", arm, pts))
    panels.append(_panel(
        "attempts_to_converge", "Attempts needed to pass the suite", "line",
        "run index", "attempts (gap = never converged)", converge,
        y_zero=True, undefined_points=undefined,
        caveat=f"{undefined} point(s) are UNDEFINED -- the run never "
               f"converged -- and are drawn as gaps, never as the attempt "
               f"count. This is the metric the design predicts should "
               f"fall; it is also the one most often undefined."))

    cost = []
    for arm in arms:
        cost.append(_arm_series("", arm, [
            {"x": r["index"], "y": r["arms"].get(arm, {}).get("tokens"),
             "turns": r["arms"].get(arm, {}).get("turns")} for r in rows]))
    panels.append(_panel(
        "cost_by_run", "Attempt tokens per run", "line",
        "run index", "tokens", cost,
        caveat="Warm's prompt carries the skill, and the skill grows. A "
               "rising warm line is the skill getting longer, which is a "
               "real cost of the method -- not an artefact to normalise "
               "away."))

    panels.append(_panel(
        "skill_growth", "Skill version reached, per run", "step",
        "run index", "skill version at the start of the run", [
            _arm_series("", arm, [
                {"x": r["index"],
                 "y": r["arms"].get(arm, {}).get("skill_version_at_start"),
                 "accepted": r["arms"].get(arm, {}).get(
                     "distillations_accepted"),
                 "proposed": r["arms"].get(arm, {}).get("distillations")}
                for r in rows])
            for arm in arms if arm == "warm"],
        y_zero=False,
        caveat="A version that does not advance means every proposal that "
               "run was rejected by the validator. Flat is informative."))

    effect = None
    if "warm" in arms and "cold" in arms:
        effect = _paired_difference(
            [float(v or 0) for v in column("warm", "best_passed")],
            [float(v or 0) for v in column("cold", "best_passed")])

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "across_runs",
        "n_runs": len(rows),
        "arms": arms,
        "oracle": oracle,
        "rows": rows,
        "panels": panels,
        # The single number the whole experiment is for, with its interval.
        # None when there are too few runs to say anything -- which is a
        # result to report, not a chart to leave empty.
        "effect": effect,
        "effect_note": (
            "Paired warm-minus-cold on best tests passing, bootstrap 95% CI "
            "over runs. Paired because both arms share a run, a server and "
            "an hour. An interval that crosses zero means this experiment "
            "has not yet shown a difference -- say that, do not round it "
            "to the sign of the mean."),
    }
