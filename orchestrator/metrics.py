"""Per-run metrics, and the cross-run table that is the actual deliverable.

The mission asks for attempt cost and distillation cost to be reported
apart. They are two different claims -- "the skill made the agent cheaper"
and "the skill was cheap to produce" -- and a single token total answers
neither. Keeping them apart is why the distiller has its own counting
proxy: Vibe surfaces no per-call usage, so a separate endpoint is the only
place the split exists.

Everything here is derived from the event log, which is written whether or
not this runs. Nothing is recomputed from the graph or from a transcript,
so a metrics bug cannot corrupt the record it describes -- rerun it against
`runs/<run_id>.jsonl` and get the same numbers.

The cross-run table is append-only markdown. It is the artefact the
"clearly working" criteria are judged on, so it records the things that
decide whether a run counts -- in particular whether the arms were
identical apart from the skill, because a run where they were not can be
used for debugging and nothing else.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
CROSS_RUN = RUNS_DIR / "cross-run.md"

# THE TREATMENT, not a confound.
#
# The claim under test is "warm + memory + skill beats cold" -- it has never
# been "the skill alone". Warm therefore HAS the memory MCP server, the
# `post_tool` hook and the reasoning relay during its attempts, and those
# show up in the setup fingerprint as exactly these three keys.
#
# This briefly read as a disqualifying difference, because a redesign had
# moved memory off the attempt path and the gate was written for that. With
# memory back where it belongs, a gate that rejects its fingerprint rejects
# every valid run. The teeth are unchanged and live in `assert_arms_match`,
# which still REFUSES TO START on any difference outside this set -- the
# warm-only `web` server and warm's three extra prompt steps, the two that
# actually happened, are still caught before the clock.
#
# One definition, imported by swarm/run.py. Two copies would drift and then
# "what the harness permits" and "what the table counts" would be different
# questions wearing the same name.
TREATMENT_DIFFERENCES: frozenset[str] = frozenset(
    {"hook_files", "config_names", "tools"})

_HEADER = (
    "| run | gpu | $/hr | run s | GPU $ | skill v | skill tok | arm | "
    "passed | attempts | converged | attempt tok (in/out) | "
    "distil tok (in/out) | turns | attempt s | distil s | steps | counts |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


@dataclass
class ArmMetrics:
    arm: str
    tests_passed: int = 0
    attempts: int = 0
    converged: bool = False
    turns: int = 0
    attempt_seconds: float = 0.0
    attempt_prompt_tokens: int = 0
    attempt_completion_tokens: int = 0
    distil_seconds: float = 0.0
    distil_prompt_tokens: int = 0
    distil_completion_tokens: int = 0
    steps_ingested: int = 0
    # `None` means UNCOUNTED, and that is not the same fact as zero.
    #
    # The live-hook path emits `with_reasoning=None` on purpose: the hook
    # wrote the steps as the agent worked, back-fill never ran, and nothing
    # re-counts them. This used to be `int = 0` accumulated with
    # `event.get(...) or 0`, so every live run reported `0 w/ reasoning` --
    # which reads as total failure and is actually no information. Six pod
    # runs on 2026-09-18/19 were recorded that way, and the graph turned out
    # to hold 988 of 993 steps whose `thought` was tool-argument JSON. The
    # metric could not have told anyone either way.
    #
    # Now: zero stays zero, uncounted stays None, and `thought_fallbacks`
    # carries the live path's own answer (see StepMemoryService).
    steps_with_reasoning: int | None = None
    # Steps whose `thought` fell back to serialised tool input because no
    # reasoning had arrived from the relay. Counted at write time by the
    # sidecar, so it is available on the live path where `with_reasoning`
    # is not. `None` until a run reports it.
    thought_fallbacks: int | None = None
    skill_versions: list[int] = field(default_factory=list)
    distillations: int = 0
    distillations_accepted: int = 0
    memory_tool_calls: int = 0
    per_attempt: list[dict] = field(default_factory=list)


@dataclass
class RunMetrics:
    run_id: str
    gpu: str
    model: str
    commit: str
    skill_version: int
    skill_approx_tokens: int
    skill_dir_sha: str
    arms_identical: bool
    known_differences: list[str]
    arms: dict[str, ArmMetrics]
    # Seconds from the first event to the last, off the event log. This is
    # the RUN, not the pod: provisioning and the model download happen
    # before the first event and are not in it. Stated rather than fudged,
    # because "what did this run cost" and "what did today cost" are
    # different questions and only the first is derivable here.
    run_seconds: float = 0.0
    # 0.0 means "not supplied", not "free". A missing rate reports as `-`
    # rather than as $0.00, which would read as a measurement.
    gpu_usd_per_hour: float = 0.0

    @property
    def gpu_usd(self) -> float | None:
        if not self.gpu_usd_per_hour:
            return None
        return self.gpu_usd_per_hour * self.run_seconds / 3600.0

    @property
    def counts_toward_clearly_working(self) -> bool:
        """A run counts if the arms differed by the TREATMENT alone.

        The treatment is memory plus the skill it distils -- see
        TREATMENT_DIFFERENCES. Anything else is a confound and the run is
        debugging material only. Stated here rather than left to a reader
        of the table: the point of the criterion is that it is not
        re-litigated per run.
        """
        return set(self.known_differences) <= TREATMENT_DIFFERENCES


def collect(events: list[dict], *, run_id: str, gpu: str, model: str,
            commit: str, skill_version: int, skill_approx_tokens: int,
            skill_dir_sha: str, arms_identical: bool,
            known_differences: list[str],
            distil_usage: dict[str, dict] | None = None,
            gpu_usd_per_hour: float = 0.0) -> RunMetrics:
    """Fold the event log into per-arm numbers.

    `distil_usage` is the distillation proxy's own counters per arm, which
    only the runner can read -- everything else comes from events.
    """
    arms: dict[str, ArmMetrics] = {}

    def arm_of(event: dict) -> ArmMetrics:
        name = event.get("swarm") or "unknown"
        return arms.setdefault(name, ArmMetrics(arm=name))

    for event in events:
        kind = event.get("type")
        if kind == "ATTEMPT_DONE":
            arm = arm_of(event)
            arm.attempts += 1
            arm.turns += event.get("turns_used", 0) or 0
            arm.attempt_seconds += event.get("attempt_seconds", 0.0) or 0.0
            arm.attempt_prompt_tokens += event.get("attempt_prompt_tokens", 0) or 0
            arm.attempt_completion_tokens += (
                event.get("attempt_completion_tokens", 0) or 0)
            arm.tests_passed = max(arm.tests_passed,
                                   event.get("tests_passed", 0) or 0)
            arm.per_attempt.append({
                "attempt": event.get("attempt"),
                "skill_version": event.get("skill_version"),
                "tests_passed": event.get("tests_passed"),
                # Migration left to do, counted off the source. Carried
                # because `tests_passed` is 0 both for "not started" and
                # for "agent broke the package" -- 70% of graded attempts
                # -- so it is the only per-attempt number that separates
                # progress from damage. See orchestrator/surfaces.py.
                "v1_remaining": event.get("v1_remaining"),
                # The pair that answers "who wrote better code". The
                # oracle cannot: on fixtures/oapi it scores 0 / ~310 / 445
                # and the step to ~310 is "the package imports".
                "parse_ok": event.get("parse_ok"),
                "parse_total": event.get("parse_total"),
                # 0.0 = the untouched checkout, 1.0 = the merged PR. The
                # gradient measure, and it was being dropped here while
                # sitting correctly in the event log -- run 1 reported
                # best_closeness 0.000 for an arm the log had at 0.502.
                "closeness": event.get("closeness"),
                "turns": event.get("turns_used"),
                "seconds": event.get("attempt_seconds"),
                "prompt_tokens": event.get("attempt_prompt_tokens"),
                "completion_tokens": event.get("attempt_completion_tokens"),
                "ended_cleanly": event.get("ended_cleanly"),
            })
        elif kind == "INGESTED":
            arm = arm_of(event)
            arm.steps_ingested += event.get("steps", 0) or 0
            # Preserve the None. A single uncounted attempt makes the arm's
            # total uncountable, because adding the counted ones would
            # under-report and look like a partial failure.
            counted = event.get("with_reasoning")
            if counted is None:
                arm.steps_with_reasoning = None
            elif arm.steps_with_reasoning is not None:
                arm.steps_with_reasoning += counted
        elif kind == "STEP_WRITES":
            # The sidecar's own tally, emitted once per run. This is the
            # live path's answer to "did the model's reasoning reach the
            # graph", and the only one available when the hook wrote the
            # steps itself.
            arm = arm_of(event)
            arm.thought_fallbacks = event.get("thought_fallbacks")
            if event.get("thoughts_from_reasoning") is not None:
                arm.steps_with_reasoning = event["thoughts_from_reasoning"]
        elif kind == "DISTILLED":
            arm = arm_of(event)
            arm.distillations += 1
            arm.distil_seconds += event.get("seconds", 0.0) or 0.0
            arm.memory_tool_calls += event.get("memory_tool_calls", 0) or 0
            if event.get("accepted"):
                arm.distillations_accepted += 1
                if event.get("version") is not None:
                    arm.skill_versions.append(event["version"])
        elif kind == "FILE_DONE":
            arm = arm_of(event)
            arm.converged = arm.converged or bool(event.get("success"))

    for name, usage in (distil_usage or {}).items():
        arm = arms.setdefault(name, ArmMetrics(arm=name))
        arm.distil_prompt_tokens = usage.get("prompt_tokens", 0)
        arm.distil_completion_tokens = usage.get("completion_tokens", 0)

    return RunMetrics(
        run_id=run_id, gpu=gpu, model=model, commit=commit,
        skill_version=skill_version, skill_approx_tokens=skill_approx_tokens,
        skill_dir_sha=skill_dir_sha, arms_identical=arms_identical,
        known_differences=sorted(known_differences), arms=arms,
        run_seconds=max((e.get("t", 0.0) for e in events), default=0.0),
        gpu_usd_per_hour=gpu_usd_per_hour,
    )


def write(metrics: RunMetrics, *, runs_dir: Path | None = None) -> Path:
    """One JSON file per run, beside its event log."""
    directory = runs_dir or RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{metrics.run_id}-metrics.json"
    payload = asdict(metrics)
    payload["counts_toward_clearly_working"] = metrics.counts_toward_clearly_working
    # PROPERTIES ARE NOT FIELDS, so `asdict` drops them. `gpu_usd` was
    # therefore absent from every metrics file while the cross-run table,
    # which reads the property directly, showed it correctly -- so the
    # JSON and the table disagreed about what a run cost.
    payload["gpu_usd"] = metrics.gpu_usd
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def reasoning_verdict(thoughts: int, fallbacks: int, pushes: int) -> str | None:
    """Is the relay delivering? Returns the alarm, or None if it is.

    HERE rather than inline in `swarm/run.py` because the rehearsal drives
    `migrate_codebase` and never enters that file, so anything written
    there is untested until a pod pays for it. This is the judgement; the
    caller only prints it.

    "Most steps fell back" is the threshold rather than "any did", because
    a turn that genuinely carried no reasoning is a real thing and its
    fall-back is correct. A majority is not: on the 2026-09-18/19 series
    it was 988 of 993.
    """
    if not fallbacks or fallbacks < thoughts:
        return None
    return (
        "THE RELAY IS NOT DELIVERING. Most steps stored the TOOL INPUT as "
        f"their thought ({fallbacks} of {thoughts + fallbacks}). "
        "search_steps embeds thought+action, so this graph is searchable "
        "by what was typed and not by why, and the distiller's evidence is "
        "tool-argument JSON. Check that reasoning_relay.py is in the vibe "
        f"pipeline and that the model emits reasoning; the sidecar "
        f"received {pushes} push(es).")


def _reasoning_cell(a: ArmMetrics) -> str:
    """How many of this arm's steps carry the model's own reasoning.

    Three distinct answers, spelled differently, because collapsing them is
    what hid the 2026-09-18 series: `0 w/ reasoning` appeared on six runs
    where the number was never taken, and was read as a working graph
    because the previous runs' back-fill had reported real counts.

        n w/ reasoning          counted, and this is the count
        n w/ reasoning, m fell back to tool input
                                counted at write time by the sidecar
        reasoning UNCOUNTED     the hook wrote live and nothing tallied it
    """
    if a.steps_with_reasoning is None:
        return "reasoning UNCOUNTED"
    cell = f"{a.steps_with_reasoning} w/ reasoning"
    if a.thought_fallbacks:
        cell += f", {a.thought_fallbacks} fell back to tool input"
    return cell


def append_to_table(metrics: RunMetrics, *, path: Path | None = None) -> Path:
    """Add this run's rows to the cross-run table.

    Append-only, and it records whether the run counts. A table that only
    listed the numbers would let a debugging run -- one where warm had
    tools cold did not -- be read later as evidence.
    """
    target = path or CROSS_RUN
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(
            "# Cross-run summary\n\nAppend-only. A run counts toward "
            "\"clearly working\" only when `counts` is `yes`: the arms "
            "differed by the skill alone.\n\n" + _HEADER)
    elif _HEADER.splitlines()[0] not in target.read_text():
        with target.open("a") as handle:
            handle.write("\n" + _HEADER)

    counts = "yes" if metrics.counts_toward_clearly_working else "NO (debug)"
    rate = f"{metrics.gpu_usd_per_hour:.2f}" if metrics.gpu_usd_per_hour else "-"
    spend = f"{metrics.gpu_usd:.2f}" if metrics.gpu_usd is not None else "-"
    rows = []
    for name in sorted(metrics.arms):
        a = metrics.arms[name]
        rows.append(
            f"| {metrics.run_id} | {metrics.gpu} | {rate} | "
            f"{metrics.run_seconds:.0f} | {spend} | {metrics.skill_version} | "
            f"{metrics.skill_approx_tokens} | {a.arm} | {a.tests_passed} | "
            f"{a.attempts} | {'yes' if a.converged else 'no'} | "
            f"{a.attempt_prompt_tokens:,}/{a.attempt_completion_tokens:,} | "
            f"{a.distil_prompt_tokens:,}/{a.distil_completion_tokens:,} | "
            f"{a.turns} | {a.attempt_seconds:.0f} | {a.distil_seconds:.0f} | "
            f"{a.steps_ingested} ({_reasoning_cell(a)}) | "
            f"{counts} |"
        )
    with target.open("a") as handle:
        handle.write("\n".join(rows) + "\n")
    return target


def summarise(metrics: RunMetrics) -> str:
    """The lines printed at the end of a run."""
    lines = [
        f"metrics: skill v{metrics.skill_version} "
        f"({metrics.skill_approx_tokens} approx tokens, "
        f"{metrics.skill_dir_sha}) | counts toward clearly-working: "
        f"{'YES' if metrics.counts_toward_clearly_working else 'NO'}"
    ]
    if metrics.gpu_usd is not None:
        lines.append(
            f"  GPU: {metrics.gpu} at ${metrics.gpu_usd_per_hour:.2f}/hr x "
            f"{metrics.run_seconds:.0f}s = ${metrics.gpu_usd:.2f} for this "
            f"RUN -- provisioning and the model download are before the "
            f"first event and are not counted here")
    else:
        lines.append(
            f"  GPU: {metrics.gpu}, {metrics.run_seconds:.0f}s -- no hourly "
            f"rate given (--gpu-usd-per-hour), so spend is unknown, not zero")
    if metrics.known_differences:
        confounds = sorted(set(metrics.known_differences)
                           - TREATMENT_DIFFERENCES)
        lines.append(
            f"  arms differed in {metrics.known_differences} -- "
            + (f"CONFOUNDED by {confounds}, debugging run only"
               if confounds else "the treatment (memory + skill)"))
    for name in sorted(metrics.arms):
        a = metrics.arms[name]
        lines.append(
            f"  {a.arm}: {a.tests_passed} passed, {a.attempts} attempt(s), "
            f"{a.turns} turn(s), {a.attempt_seconds:.0f}s attempt / "
            f"{a.distil_seconds:.0f}s distil | attempt tokens "
            f"{a.attempt_prompt_tokens:,} in / "
            f"{a.attempt_completion_tokens:,} out | distil tokens "
            f"{a.distil_prompt_tokens:,} in / "
            f"{a.distil_completion_tokens:,} out"
        )
        if a.distillations:
            lines.append(
                f"    distillation: {a.distillations_accepted}/"
                f"{a.distillations} accepted, versions {a.skill_versions or '-'}, "
                f"{a.memory_tool_calls} memory tool call(s)"
            )
    return "\n".join(lines)
