"""Metrics must keep attempt cost and distillation cost apart.

They answer two different questions -- "did the skill make the agent
cheaper" and "what did the skill cost to produce" -- and one combined
total answers neither. The whole reason the distiller has its own counting
proxy is that Vibe surfaces no per-call usage, so a separate endpoint is
the only place the split exists.

The other property here is that a run which cannot be compared says so.
This project has already produced two warm-vs-cold comparisons that were
worthless (warm-only `web`; warm-only prompt steps) and were read as
results for days afterwards.
"""
from __future__ import annotations

import json

import pytest

from orchestrator import metrics as m


def _events() -> list[dict]:
    """A log shaped like a real one, `t` included.

    Every event `make_event` produces carries `t` -- seconds since the run
    started -- and the run's own length is read back off it. A fixture
    without `t` is not an event log, and a metric derived from it reads as
    a zero-length run.
    """
    return [
        {"t": 0.1, "type": "ATTEMPT_START", "swarm": "warm", "attempt": 1, "skill_version": 0},
        {"t": 315.0, "type": "ATTEMPT_DONE", "swarm": "warm", "attempt": 1,
         "tests_passed": 12, "turns_used": 9, "attempt_seconds": 310.0,
         "attempt_prompt_tokens": 120_000, "attempt_completion_tokens": 4_000,
         "skill_version": 0, "ended_cleanly": True},
        {"t": 316.0, "type": "INGESTED", "swarm": "warm", "attempt": 1, "steps": 9,
         "with_reasoning": 9, "tool_calls": 8, "failed_tool_calls": 1},
        {"t": 358.0, "type": "DISTILLED", "swarm": "warm", "attempt": 1, "version": 1,
         "accepted": True, "repairs": 0, "seconds": 42.0,
         "memory_tool_calls": 3, "eligible_traces": 0},
        {"t": 600.0, "type": "ATTEMPT_DONE", "swarm": "warm", "attempt": 2,
         "tests_passed": 33, "turns_used": 7, "attempt_seconds": 240.0,
         "attempt_prompt_tokens": 90_000, "attempt_completion_tokens": 3_000,
         "skill_version": 1, "ended_cleanly": True},
        {"t": 601.0, "type": "FILE_DONE", "swarm": "warm", "success": True, "attempts": 2},
        {"t": 905.0, "type": "ATTEMPT_DONE", "swarm": "cold", "attempt": 1,
         "tests_passed": 8, "turns_used": 11, "attempt_seconds": 300.0,
         "attempt_prompt_tokens": 100_000, "attempt_completion_tokens": 3_500,
         "skill_version": None, "ended_cleanly": True},
        {"t": 906.0, "type": "FILE_DONE", "swarm": "cold", "success": False, "attempts": 1},
    ]


def _collect(**over):
    kw = dict(run_id="swarm-1", gpu="H200", model="mistral", commit="abc1234",
              skill_version=1, skill_approx_tokens=520, skill_dir_sha="deadbeef",
              arms_identical=True, known_differences=[],
              distil_usage={"warm": {"prompt_tokens": 30_000,
                                     "completion_tokens": 2_000}})
    kw.update(over)
    return m.collect(_events(), **kw)


def test_attempt_and_distillation_tokens_never_merge() -> None:
    warm = _collect().arms["warm"]
    assert warm.attempt_prompt_tokens == 210_000
    assert warm.attempt_completion_tokens == 7_000
    assert warm.distil_prompt_tokens == 30_000
    assert warm.distil_completion_tokens == 2_000
    # The distiller's tokens must not have leaked into the attempt totals.
    assert warm.attempt_prompt_tokens != (210_000 + 30_000)


def test_cold_has_no_distillation_cost() -> None:
    """Cold never distils: no skill to improve, no graph to read."""
    cold = _collect().arms["cold"]
    assert cold.distil_prompt_tokens == 0
    assert cold.distil_seconds == 0.0
    assert cold.distillations == 0


def test_per_attempt_rows_record_the_skill_version_used() -> None:
    """Distillation changes the skill BETWEEN attempts, so a run-level
    version number would attribute attempt 1's result to the version that
    only existed after it."""
    warm = _collect().arms["warm"]
    assert [a["skill_version"] for a in warm.per_attempt] == [0, 1]
    assert [a["tests_passed"] for a in warm.per_attempt] == [12, 33]


def test_convergence_and_totals() -> None:
    result = _collect()
    assert result.arms["warm"].converged is True
    assert result.arms["cold"].converged is False
    assert result.arms["warm"].attempts == 2
    assert result.arms["warm"].turns == 16
    assert result.arms["warm"].steps_ingested == 9
    assert result.arms["warm"].skill_versions == [1]


def test_a_run_confounded_beyond_the_treatment_does_not_count() -> None:
    """A debugging run must never be readable later as evidence.

    The treatment IS memory plus the skill, so warm having the memory
    server, the hook and their tools is what the run is for -- not a
    reason to discard it. Anything else still discards it.
    """
    assert _collect().counts_toward_clearly_working is True
    treatment = _collect(arms_identical=False,
                         known_differences=sorted(m.TREATMENT_DIFFERENCES))
    assert treatment.counts_toward_clearly_working is True
    # The two confounds that actually happened: a warm-only `web` server,
    # and warm's task prompt carrying three extra numbered steps.
    for confound in ("mcp_web", "task_prompt"):
        bad = _collect(arms_identical=False,
                       known_differences=["tools", confound])
        assert bad.counts_toward_clearly_working is False, confound


def test_the_harness_and_the_table_permit_the_same_set() -> None:
    """One definition. Two would drift, and then "the harness allowed it"
    and "the table counted it" would stop meaning the same thing."""
    from swarm.run import KNOWN_ARM_DIFFERENCES
    assert KNOWN_ARM_DIFFERENCES is m.TREATMENT_DIFFERENCES


def test_the_table_marks_which_runs_count(tmp_path) -> None:
    table = tmp_path / "cross-run.md"
    m.append_to_table(_collect(), path=table)
    m.append_to_table(_collect(run_id="swarm-2", arms_identical=False,
                               known_differences=["tools", "task_prompt"]),
                      path=table)
    text = table.read_text()
    assert text.count("| swarm-1 |") == 2, "one row per arm"
    assert "yes |" in text
    assert "NO (debug) |" in text
    # The header is written once, not per run.
    assert text.count("| run | gpu |") == 1


def test_metrics_are_written_beside_the_event_log(tmp_path) -> None:
    path = m.write(_collect(), runs_dir=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["counts_toward_clearly_working"] is True
    assert payload["arms"]["warm"]["distil_prompt_tokens"] == 30_000
    assert payload["skill_dir_sha"] == "deadbeef"


def test_collect_is_pure_and_rerunnable() -> None:
    """Derived from the event log only, so a metrics bug cannot corrupt
    the record it describes -- rerun it and get the same numbers."""
    first, second = _collect(), _collect()
    assert first.arms["warm"].per_attempt == second.arms["warm"].per_attempt
    assert first.arms["warm"].attempt_seconds == second.arms["warm"].attempt_seconds


def test_summary_states_whether_the_run_counts() -> None:
    assert "counts toward clearly-working: YES" in m.summarise(_collect())
    bad = m.summarise(_collect(arms_identical=False,
                               known_differences=["tools", "task_prompt"]))
    assert "counts toward clearly-working: NO" in bad
    assert "debugging run only" in bad
    # It must name WHICH difference disqualified the run, not just that
    # one did: "tools" is the treatment and "task_prompt" is the bug.
    assert "task_prompt" in bad


def test_the_summary_does_not_call_the_treatment_a_confound() -> None:
    """Warm having memory is the experiment, and must not read as a flaw."""
    line = m.summarise(_collect(arms_identical=False,
                                known_differences=sorted(m.TREATMENT_DIFFERENCES)))
    assert "counts toward clearly-working: YES" in line
    assert "the treatment (memory + skill)" in line
    assert "debugging run only" not in line


def test_provision_starts_a_proxy_for_every_measured_thing() -> None:
    """Three counting proxies, not two.

    Vibe surfaces no per-call usage, so each number that must be reported
    separately needs its own endpoint. A missing 8821/8822 is caught by
    the runner's preflight ("not answering"); a missing 8823 is NOT -- it
    reports zero distillation tokens, which reads as a distiller that cost
    nothing rather than one that was never measured. Hence the check here,
    against the script that is supposed to start it.
    """
    from pathlib import Path

    script = (Path(__file__).resolve().parent.parent
              / "swarm" / "provision.sh").read_text()
    for port, what in ((8821, "warm attempts"), (8822, "cold attempts"),
                       (8823, "the distillation turn")):
        assert str(port) in script, (
            f"provision.sh starts no counting proxy on {port} ({what})")
    # Restarting a proxy loses the cumulative baseline the runner
    # subtracts from, so an already-running one must be left alone.
    assert "already listening" in script
    assert "/usage" in script, "the script must verify each proxy answers"


def test_the_distillation_cost_is_not_silently_reported_as_zero() -> None:
    """A distillation cost of 0 must mean "measured 0", never "not measured".

    The old external writer kept its own token counters because an OpenAI
    call does not pass through the pod's counting proxy, and without them
    the distiller reported as free rather than as unmeasured. Cognee
    exposes no usage counter at all, so the runner reads the proxy -- and
    the comment at that call site has to keep saying which of the two
    zeros this is, because the distinction has been lost once already.
    """
    import inspect

    import swarm.run as runner
    src = inspect.getsource(runner.main_async)
    assert "proxy_usage(host, args.distill_proxy)" in src
    assert "never measured" in src, (
        "the zero-vs-unmeasured distinction must stay written down")


def test_after_clock_graph_work_is_bounded() -> None:
    """NOTHING AFTER THE MEASURED WINDOW MAY HOLD A RUN OPEN.

    Entity extraction WAS an OpenAI round trip per message, running after
    the clock: one run finished its agent work at t=214 and was still
    blocked in SSL 18 minutes later, stalling an A/B sweep. That pass is
    Cognee's job now and is gone.

    What replaced it is `improve()` -- the bridge from session memory into
    the graph, which the attempt loop also calls per attempt and which
    main_async calls once more per warm agent at the end, because an agent
    cancelled between its last verdict and its last bridge would otherwise
    strand its most informative trace. Same class of work, same risk, so
    the same rule: it runs under an explicit timeout.
    """
    import inspect

    import swarm.run as runner
    src = inspect.getsource(runner.main_async)
    assert "extract_entities_from_session" not in src, (
        "the after-clock extraction pass is Cognee's job now")
    assert "asyncio.wait_for(scopes[label].improve()" in src, (
        "the after-clock improve() call must be bounded -- an unbounded "
        "OpenAI round trip after the measured window cannot change a "
        "result but can hold a finished run open indefinitely")
    assert "timeout=ENTITY_TIMEOUT_S" in src


def test_progress_is_measurable_when_the_package_will_not_import() -> None:
    """`tests_passed` cannot separate progress from damage.

    Every one of the fixture's 445 tests imports the package, so the score
    is 0 both when the migration has not started and when the agent has
    broken the file. Measured over 77 graded attempts: 70% scored exactly
    0. A skill effect is invisible through that.
    """
    from orchestrator import surfaces

    broken = {"pkg/models.py": b"class Config:\n    extra = .allow\n"}
    assert surfaces.count(broken) > 0, (
        "a tree that does not even parse must still yield a count -- that "
        "is the whole point")

    started = {"pkg/a.py": b"class Config:\n    orm_mode = True\n",
               "pkg/b.py": b"@validator('x')\ndef v(cls, y): return y\n"}
    partly = {"pkg/a.py": b"model_config = ConfigDict(from_attributes=True)\n",
              "pkg/b.py": b"@validator('x')\ndef v(cls, y): return y\n"}
    done = {"pkg/a.py": b"model_config = ConfigDict(from_attributes=True)\n",
            "pkg/b.py": b"@field_validator('x')\ndef v(cls, y): return y\n"}
    assert surfaces.count(started) > surfaces.count(partly) > surfaces.count(done)
    assert surfaces.count(done) == 0


def test_the_counter_moves_on_the_real_fixture_and_bottoms_out() -> None:
    """Pinned against both ends of the actual migration, because a
    progress measure that does not move is worse than none."""
    import pathlib

    from orchestrator import surfaces

    def load(root):
        root = pathlib.Path(root)
        return {str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob("*.py")}

    pre = surfaces.count(load("fixtures/oapi/openapi_python_client"))
    post = surfaces.count(load("fixtures/oapi/reference_v2/openapi_python_client"))
    assert pre >= 60, f"pre-migration source should be rich in v1: {pre}"
    # NOT zero: the human's own answer keeps two `response.json()` calls in
    # generated-code strings and one unrelated `class Config`. The floor is
    # measured, not assumed, so that 3 is read as "done" and not "almost".
    assert post <= 5, f"the reference answer should bottom out: {post}"
    assert pre > post * 10


def test_the_fixture_scorer_and_the_harness_share_one_definition() -> None:
    """Two copies would drift, and then "surfaces in this fixture" and
    "surfaces left in this tree" become different questions with the same
    name."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "scripts" / "make_fixture.py").read_text()
    assert "from orchestrator.surfaces import SURFACES" in src
    assert "SURFACES = {" not in src, "make_fixture must not keep its own table"


def test_per_attempt_rows_carry_the_progress_count() -> None:
    events = _events()
    for e in events:
        if e["type"] == "ATTEMPT_DONE":
            e["v1_remaining"] = 40 if e["attempt"] == 1 else 12
    result = m.collect(events, run_id="r", gpu="g", model="m", commit="c",
                       skill_version=1, skill_approx_tokens=10,
                       skill_dir_sha="d", arms_identical=True,
                       known_differences=[], distil_usage={})
    assert [a["v1_remaining"] for a in result.arms["warm"].per_attempt] == [40, 12]


def test_the_progress_count_is_scoped_to_the_package() -> None:
    """Unscoped, the count is dominated by files the agent never edits.

    Measured on the oapi fixture: the whole shipped tree scores 93 and the
    package alone scores 64. The extra 29 are `end_to_end_tests/` and
    `integration-tests/` -- generated client code that no attempt touches,
    so it is a constant that never moves and swamps the signal. First run
    with the metric recorded warm at 35, 35, 33, 33 across four attempts
    that took the suite from 0 to 443.
    """
    import inspect

    import swarm.run as runner
    from orchestrator import vibe_agent

    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "within=package_path" in src
    assert "package_path" in inspect.signature(
        runner.agent_worker).parameters, (
        "the runner must be able to say which directory the migration is in")
    assert 'load_manifest().get("package_path")' in inspect.getsource(
        runner.main_async), "and it must come from the manifest, not a guess"


def test_gpu_spend_is_reported_and_an_absent_rate_is_not_zero() -> None:
    """Unknown spend must never render as $0.00.

    A run with no rate supplied and a run on a free GPU are different
    facts, and the table is read months later by someone who was not
    there. `-` says "nobody recorded this"; `0.00` says "it was free".
    """
    unknown = _collect()
    assert unknown.gpu_usd is None
    assert "no hourly rate given" in m.summarise(unknown)

    priced = _collect(gpu_usd_per_hour=3.59)
    assert priced.run_seconds > 0, "run length comes off the event log"
    assert priced.gpu_usd == pytest.approx(
        3.59 * priced.run_seconds / 3600.0)
    assert "$3.59/hr" in m.summarise(priced)


def test_the_table_carries_the_rate_and_the_spend(tmp_path) -> None:
    table = tmp_path / "cross-run.md"
    m.append_to_table(_collect(gpu_usd_per_hour=3.59), path=table)
    text = table.read_text()
    assert "| $/hr |" in text and "| GPU $ |" in text
    assert "| 3.59 |" in text
    # One column per header cell, or the markdown silently misaligns and
    # every number in the table is read against the wrong heading.
    header, _sep, *rows = [l for l in text.splitlines() if l.startswith("|")]
    assert all(r.count("|") == header.count("|") for r in rows)


def test_run_seconds_comes_off_the_event_log_not_the_clock() -> None:
    """Rerunnable: the same log must always give the same cost."""
    assert _collect().run_seconds == _collect().run_seconds


def test_the_relay_alarm_fires_when_most_thoughts_are_tool_input() -> None:
    """The judgement lives here, not inline in swarm/run.py.

    The rehearsal drives `migrate_codebase` and never enters that file, so
    anything written there is untested until a pod pays for it -- and the
    previous version of this alarm was gated on `not live`, which made it
    unreachable on the only path production uses. It stayed silent through
    six runs and 988 tool-JSON thoughts out of 993.
    """
    from orchestrator import metrics

    # The 2026-09-18/19 series, to scale.
    assert metrics.reasoning_verdict(5, 988, 0) is not None
    # A turn that genuinely carried no reasoning is a real thing.
    assert metrics.reasoning_verdict(200, 4, 200) is None
    assert metrics.reasoning_verdict(200, 0, 200) is None
    # A tie is already bad enough to say so.
    assert metrics.reasoning_verdict(100, 100, 0) is not None
    assert "0 push(es)" in metrics.reasoning_verdict(5, 988, 0)


def test_step_writes_reaches_the_arm_it_describes() -> None:
    """The counters are emitted once per run and have to survive the trip
    through the event log, which is the only record that outlives a pod."""
    from orchestrator import metrics

    collected = metrics.collect(
        [{"type": "STEP_WRITES", "swarm": "warm",
          "thoughts_from_reasoning": 180, "thought_fallbacks": 4,
          "reasoning_pushes": 175}],
        run_id="r", gpu="g", model="m", commit="c",
        skill_version=1, skill_approx_tokens=10, skill_dir_sha="s",
        arms_identical=True, known_differences=[])
    warm = collected.arms["warm"]
    assert warm.steps_with_reasoning == 180
    assert warm.thought_fallbacks == 4
    assert "180 w/ reasoning, 4 fell back" in metrics._reasoning_cell(warm)


def test_the_code_quality_pair_survives_into_the_metrics(monkeypatch) -> None:
    """`tests_passed` cannot answer "who wrote better code".

    On fixtures/oapi it has three values -- 0, ~310, 445 -- and the step
    from 0 to ~310 is "the package imports". The operator, verbatim: "an
    agent with shit code but a good import goes from 0-300+. This is not
    a test." The pair that can answer it is (v1 surfaces remaining, files
    that parse), and it has to reach the metrics file to be plottable.
    """
    from orchestrator import metrics

    collected = metrics.collect(
        [{"type": "ATTEMPT_DONE", "swarm": "warm", "attempt": 1,
          "tests_passed": 0, "v1_remaining": 16,
          "parse_ok": 28, "parse_total": 49, "turns_used": 60}],
        run_id="r", gpu="g", model="m", commit="c",
        skill_version=1, skill_approx_tokens=10, skill_dir_sha="s",
        arms_identical=True, known_differences=[])
    row = collected.arms["warm"].per_attempt[0]
    assert (row["v1_remaining"], row["parse_ok"], row["parse_total"]) == (16, 28, 49), (
        "the two measures that separate 'did the work and broke it' from "
        "'kept it valid by not doing it' are not recorded")


def test_parse_counts_are_defined_on_a_tree_that_does_not_parse() -> None:
    """Exactly when they are needed. An oracle that requires the package
    to import cannot say anything about the attempt that broke it."""
    from orchestrator import surfaces

    tree = {"pkg/good.py": b"x = 1\n",
            "pkg/broken.py": b"def f():\nreturn 1\n",
            "tests/t.py": b"y = 2\n"}
    assert surfaces.parses(tree, within="pkg/") == (1, 2)


def test_closeness_matches_both_path_spellings() -> None:
    """THE BUG THAT MADE RUN 1'S COLUMN USELESS.

    The local workspace keys files `openapi_python_client/config.py`; the
    remote one keys them `/repo/openapi_python_client/config.py`
    (AgentWorkspace.collect_file_contents). The first version of this used
    an exact `files.get(path)`, so on the pod it matched nothing, every
    file scored as unchanged, and closeness logged 0.000 for every attempt
    of both arms -- including a tree that had reached 310 passing tests.
    `v1_remaining` was unaffected because it matches on a substring, which
    is exactly why the fault was invisible next to it.
    """
    from orchestrator import surfaces

    base = {"pkg/a.py": b"class Config:\n    x = 1\n",
            "pkg/b.py": b"y = 1\n"}
    answer = {"pkg/a.py": b"model_config = ConfigDict()\nx = 1\n",
              "pkg/b.py": b"y = 1\n"}
    for prefix in ("", "/repo/"):
        tree = {f"{prefix}{k}": v for k, v in base.items()}
        done = {f"{prefix}{k}": v for k, v in answer.items()}
        assert surfaces.closeness(tree, base, answer, within="pkg") == 0.0, prefix
        assert surfaces.closeness(done, base, answer, within="pkg") == 1.0, prefix


def test_the_suite_is_run_so_that_it_actually_tests() -> None:
    """One unimportable module must not zero the whole suite.

    Every test in these fixtures imports the package, so without
    `--continue-on-collection-errors` a single syntax error anywhere
    aborts collection for all of them and pytest runs NOTHING: it prints
    "Interrupted: N errors during collection" and the grader records 0
    passing. 70% of graded attempts scored exactly 0 that way, including
    trees where 60 of 65 modules were migrated and importable -- so the
    number was a report on the worst file in the tree rather than a
    measurement of the migration.

    Verified directly on a two-module tree: without the flag 0 tests ran
    and pytest reported "Interrupted: 1 error during collection"; with
    it, 3 passed and the broken module was reported as one error.

    Success is unchanged. A collection error still makes the exit code
    non-zero, so a green suite still means every test passed AND every
    module imported.
    """
    from pathlib import Path

    import yaml

    # BY PATH, not through load_manifest: that resolves MSF_FIXTURE_DIR, so
    # the assertion would silently check whichever fixture happened to be
    # selected. Every fixture's command needs the flag.
    root = Path(__file__).resolve().parent.parent
    manifests = sorted(root.glob("fixtures/*/manifest.yaml"))
    manifests.append(root / "fixture" / "manifest.yaml")
    checked = 0
    for path in manifests:
        if not path.exists():
            continue
        command = (yaml.safe_load(path.read_text()) or {}).get("test_command")
        if not command:
            continue
        checked += 1
        assert "--continue-on-collection-errors" in command, (
            f"{path}: one bad file would zero the whole suite")
        assert command.startswith("python -m pytest"), path
    assert checked >= 2, f"only {checked} manifest(s) declared a test_command"
