"""The chart data must not invent, flatten, or round away what it shows.

These charts are going to be screenshotted into a demonstration and then
rebuilt as React components. Both of those strip context, so the context
has to be IN the data: the floor that is 3 and not 0, the run that never
converged and therefore has no attempts-to-converge, the interval that
crosses zero. Each test here is one way a chart could lie while still
being "correct".
"""
from __future__ import annotations

import json

import pytest

from orchestrator import series as S


def _events(**over) -> list[dict]:
    """Two arms, warm improving over three attempts, cold never passing."""
    warm = [(1, 100, 60, 0), (2, 40, 55, 1), (3, 445, 3, 1)]
    cold = [(1, 0, 64, None), (2, 9, 61, None), (3, 9, 61, None)]
    out: list[dict] = []
    t = 0.0
    for arm, rows in (("warm", warm), ("cold", cold)):
        for attempt, passed, v1, version in rows:
            t += 100.0
            out.append({"t": t, "type": "ATTEMPT_START", "swarm": arm,
                        "agent": f"{arm}-0", "attempt": attempt,
                        "skill_version": version})
            out.append({
                "t": t + 90, "type": "ATTEMPT_DONE", "swarm": arm,
                "agent": f"{arm}-0", "attempt": attempt,
                "tests_passed": passed, "v1_remaining": v1,
                "skill_version": version, "turns_used": 7,
                "attempt_seconds": 90.0, "ended_cleanly": True,
                "exit_code": 0 if passed == 445 else 1,
                "error_signature": None if passed == 445 else "ImportError",
                "attempt_prompt_tokens": 10_000 * attempt,
                "attempt_completion_tokens": 500,
            })
    out.append({"t": 400.0, "type": "INGESTED", "swarm": "warm",
                "agent": "warm-0", "attempt": 1, "steps": 9,
                "with_reasoning": 9, "tool_calls": 8, "failed_tool_calls": 1})
    out.append({"t": 410.0, "type": "DISTILLED", "swarm": "warm",
                "agent": "warm-0", "attempt": 1, "version": 1,
                "accepted": True, "repairs": 0, "seconds": 40.0,
                "memory_tool_calls": 3, "eligible_traces": 2})
    out.append({"t": 500.0, "type": "RESTORED", "swarm": "warm",
                "agent": "warm-0", "attempt": 2, "from_passed": 40,
                "to_passed": 100, "reason": "regression"})
    out.append({"t": 900.0, "type": "FILE_DONE", "swarm": "warm",
                "agent": "warm-0", "success": True, "attempts": 3})
    out.append({"t": 900.0, "type": "FILE_DONE", "swarm": "cold",
                "agent": "cold-0", "success": False, "attempts": 3})
    out.extend(over.get("extra", []))
    return out


def _panel(doc: dict, panel_id: str) -> dict:
    return next(p for p in doc["panels"] if p["id"] == panel_id)


def test_every_panel_is_self_describing() -> None:
    """A component gets the panel and nothing else. If a key is missing
    there, the knowledge gets retyped by hand into TypeScript."""
    for doc in (S.within_run(_events()),
                S.across_runs([{"run_id": "a", "events": _events()}])):
        assert doc["schema_version"] == S.SCHEMA_VERSION
        for panel in doc["panels"]:
            for key in ("id", "title", "kind", "x_label", "y_label",
                        "series", "annotations", "caveat",
                        "y_starts_at_zero"):
                assert key in panel, f"{panel.get('id')} missing {key}"
            assert panel["caveat"].strip(), f"{panel['id']} has no caveat"
            for s in panel["series"]:
                assert s["colour"] and s["label"]


def test_reference_lines_are_omitted_not_invented(monkeypatch) -> None:
    """No graded fixture means no answer-key line.

    Drawing a plausible ceiling would put a number nobody measured on a
    chart that is then screenshotted, which is how the 33/33 that was
    really 29/33 survived.
    """
    monkeypatch.setattr(S, "oracle_for", lambda fixture: {})
    doc = S.within_run(_events(), fixture="nope")
    assert _panel(doc, "convergence")["annotations"] == []
    assert _panel(doc, "work_remaining")["annotations"] == []


def test_the_floor_is_carried_as_a_measurement(monkeypatch) -> None:
    """The completed migration still counts 3 surfaces, so a chart that
    implies 0 is the target is wrong by exactly that much."""
    monkeypatch.setattr(S, "oracle_for", lambda fixture: {
        "answer_key_passed": 445, "answer_key_v1_surfaces": 3,
        "baseline_v1_surfaces": 64})
    doc = S.within_run(_events(), fixture="oapi")
    lines = {n["y"]: n for n in _panel(doc, "work_remaining")["annotations"]}
    assert set(lines) == {64, 3}
    assert "COMPLETED" in lines[3]["label"]
    assert "not zero" in lines[3]["note"]
    assert _panel(doc, "convergence")["annotations"][0]["y"] == 445


def test_best_so_far_is_monotone_and_keeps_the_raw_score() -> None:
    """Warm's attempt 2 scored 40 after scoring 100 -- the harness rolls
    that back, so best-so-far is what the agent still has. The raw score
    must survive on the point, or the rollback becomes invisible."""
    warm = next(s for s in _panel(S.within_run(_events()), "convergence")
                ["series"] if s["arm"] == "warm")
    ys = [p["y"] for p in warm["points"]]
    assert ys == sorted(ys), "best-so-far went down"
    assert ys == [100, 100, 445]
    assert [p["raw"] for p in warm["points"]] == [100, 40, 445]


def test_a_run_that_never_converged_has_no_convergence_point() -> None:
    """Undefined, never the attempt count.

    Substituting the count turns "never got there" into "got there on the
    last attempt" -- the opposite claim -- and it would do it silently.
    """
    doc = S.across_runs([{"run_id": "a", "events": _events()}])
    rows = doc["rows"][0]["arms"]
    assert rows["warm"]["attempts_to_converge"] == 3
    assert rows["cold"]["attempts_to_converge"] is None
    assert rows["cold"]["attempts"] == 3, "the attempts still happened"
    panel = _panel(doc, "attempts_to_converge")
    cold = next(s for s in panel["series"] if s["arm"] == "cold")
    assert [p["y"] for p in cold["points"]] == [None]
    assert panel["undefined_points"] == 1
    assert "UNDEFINED" in panel["caveat"]


def test_attempt_and_distillation_costs_stay_apart() -> None:
    """Two claims, two numbers. The burn panel is attempts only."""
    doc = S.within_run(_events())
    warm = next(s for s in _panel(doc, "token_burn")["series"]
                if s["arm"] == "warm")
    # 10_500 + 20_500 + 30_500, cumulative.
    assert [p["y"] for p in warm["points"]] == [10_500, 31_000, 61_500]
    assert "off the clock" in _panel(doc, "token_burn")["caveat"]


def test_efficiency_is_a_scatter_not_a_ratio() -> None:
    """Most attempts score 0, so tokens-per-test is undefined for them and
    a mean would silently be taken over the ones that happened to pass."""
    panel = _panel(S.within_run(_events()), "efficiency")
    assert panel["kind"] == "scatter"
    assert "ratio" in panel["caveat"]


def test_rollbacks_are_counted_not_hidden() -> None:
    stability = _panel(S.within_run(_events()), "stability")
    warm = next(s for s in stability["series"] if s["arm"] == "warm")
    counts = {p["x"]: p["y"] for p in warm["points"]}
    assert counts["rolled back"] == 1
    assert counts["attempts"] == 3


def test_effect_needs_three_paired_runs_and_says_so() -> None:
    """Under three runs there is no interval, and "not computed" is the
    honest output -- not a mean with no uncertainty beside it."""
    few = S.across_runs([{"run_id": "a", "events": _events()},
                         {"run_id": "b", "events": _events()}])
    assert few["effect"] is None


def test_an_effect_that_crosses_zero_says_so_in_the_data() -> None:
    """The sign of the mean is not the result. Whether the interval
    contains zero is, and it must not be left to the reader's eye."""
    runs = [{"run_id": f"r{i}", "events": _events()} for i in range(3)]
    # Make cold beat warm in one run so the difference is not degenerate.
    swing = _events()
    for e in swing:
        if e.get("type") == "ATTEMPT_DONE" and e["swarm"] == "cold":
            e["tests_passed"] = 445
    runs.append({"run_id": "r3", "events": swing})
    effect = S.across_runs(runs)["effect"]
    assert effect["n_runs"] == 4
    low, high = effect["ci95"]
    assert low <= effect["mean_difference"] <= high
    assert effect["crosses_zero"] is (low <= 0 <= high)


def test_trend_fits_carry_their_own_p_value() -> None:
    """A slope with no p value on a five-point series is a decoration."""
    runs = [{"run_id": f"r{i}", "events": _events()} for i in range(4)]
    fits = _panel(S.across_runs(runs), "best_by_run")["fits"]
    for arm, fit in fits.items():
        assert {"slope", "p_value", "r_squared", "n"} <= set(fit), arm
        assert fit["n"] == 4


def test_the_document_is_pure_and_json_safe() -> None:
    """Rerun it against the same log and get the same document -- the same
    property metrics has, and for the same reason."""
    first = S.within_run(_events())
    second = S.within_run(_events())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_truncated_log_still_charts() -> None:
    """A run killed mid-write leaves a partial last line. That run is the
    one most worth looking at."""
    good = json.dumps({"t": 1.0, "type": "ATTEMPT_DONE", "swarm": "warm",
                       "attempt": 1, "tests_passed": 5})
    text = good + "\n\n" + '{"t": 2.0, "type": "ATT'
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "partial.jsonl"
        path.write_text(text)
        assert len(S.load_events(path)) == 1


def test_every_panel_kind_has_a_renderer() -> None:
    """A new panel must not silently render as "no renderer for kind"."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "plot_series", S.REPO_ROOT / "scripts" / "plot_series.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (S.REPO_ROOT / "scripts" / "plot_series.py").read_text()
    runs = [{"run_id": "a", "events": _events()}]
    kinds = {p["kind"] for p in S.within_run(_events())["panels"]}
    kinds |= {p["kind"] for p in S.across_runs(runs)["panels"]}
    for kind in kinds:
        assert f'"{kind}"' in source, f"plot_series.py cannot draw {kind!r}"


def test_a_log_with_no_RUN_END_is_marked_incomplete() -> None:
    """Two H200s have died mid-run. A truncated log must not render as a
    finished one -- "warm plateaued" and "the pod vanished" are different
    findings with the same shape on a chart."""
    doc = S.within_run(_events())
    assert doc["completed"] is False
    assert "NO RUN_END" in doc["incomplete_note"]
    assert doc["cost"]["gpu_usd"] is None


def test_cost_comes_off_the_terminal_event() -> None:
    events = _events() + [{
        "t": 1000.0, "type": "RUN_END", "gpu": "1x H200", "model": "m",
        "fixture": "oapi", "gpu_usd_per_hour": 3.59, "gpu_usd": 1.0,
        "run_seconds": 1000.0, "counts_toward_clearly_working": True}]
    doc = S.within_run(events)
    assert doc["completed"] is True
    assert doc["incomplete_note"] is None
    assert doc["cost"]["gpu"] == "1x H200"
    assert doc["cost"]["gpu_usd"] == 1.0
    # Per-arm token totals sit beside the GPU figure, because "what did it
    # cost" is both numbers and quoting one alone has misled before.
    assert doc["cost"]["attempt_tokens"]["warm"] == 61_500


def test_the_gantt_does_not_clamp_its_categorical_axis() -> None:
    """`y_starts_at_zero` on an inverted axis hides every bar but one.

    The timeline's y axis is a list of bars, not a quantity. With the
    clamp on, `ax.set_ylim(bottom=0)` after `invert_yaxis()` collapsed the
    view onto row 0: eleven of twelve spans vanished and the panel read as
    "only cold ever ran", from data that was completely correct.
    """
    doc = S.within_run(_events())
    timeline = _panel(doc, "timeline")
    assert timeline["kind"] == "gantt"
    assert timeline["y_starts_at_zero"] is False
    drawn = sum(len(s["points"]) for s in timeline["series"])
    assert drawn >= 6, f"only {drawn} spans in the timeline data"
