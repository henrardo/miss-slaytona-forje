"""The distillation turn: the warm model rewrites its own skill.

Once per attempt, off the clock. The model that just failed (or passed) is
given its current procedure and the tools to query what it did, and asked
to write a better procedure. Nothing here writes migration knowledge: the
prompt below contains no Pydantic API, no import path, no validator name.
If the skill ever contains the answer, the agent put it there.

FIVE DECISIONS, each with a failure behind it.

  * THE MODEL WRITES A FILE, NOT A FENCED BLOCK. A SKILL.md *is* a fenced
    ```yaml block, so asking for one inside a code fence means nesting
    fences, and the first thing that breaks is the parser on our side. It
    writes `SKILL.md` into its own working directory and we read it back.

  * THAT DIRECTORY IS NOT THE REPO. A distiller with `write_file` pointed
    at the agent's checkout would edit the code between attempts, and the
    next grading run would score edits no attempt made.

  * ITS OWN VIBE_HOME. The memory MCP server lives here and nowhere else,
    so warm's ATTEMPTS stay free of it -- that separation is the whole of
    KNOWN_ARM_DIFFERENCES being empty. It also has no skills directory: a
    distiller that could `/pydantic-v2-migration` itself would be reading
    its own output as an instruction.

  * ITS OWN COUNTING PROXY. Distillation tokens are reported separately
    from attempt tokens, and the only way to separate them is a different
    endpoint, because Vibe does not surface per-call usage.

  * AN INVALID PROPOSAL GETS THE VALIDATOR'S OWN WORDS BACK. Up to two
    repair turns, then the previous version stays live and the rejection is
    recorded. Paraphrasing a schema error loses the JSON pointer that says
    which field is wrong.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from orchestrator import ingest, skills
from orchestrator.writers import AgentWriter

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2
# The API's hard ceiling on ONE message, read off a live 400 on 2026-09-20:
#   "Invalid 'messages[1].content': string too long. Expected a string with
#    maximum length 10485760, but got a string with length 11818940"
# A transport limit, not an opinion about how much the author can read, and
# not a licence to compress the model's evidence. See the guard in distill().
MAX_MESSAGE_CHARS = 10_485_760
# Distillation is one model turn plus a few tool calls. Ten minutes is far
# past anything legitimate and short enough that a wedged turn does not eat
# a pod session.
DISTILL_TIMEOUT_S = 600.0

_MEMORY_TOOL_MARKERS = ("memory", "trace", "step", "neo4j")


def is_memory_tool(name: str) -> bool:
    return any(m in (name or "").lower() for m in _MEMORY_TOOL_MARKERS)


@dataclass
class DistillResult:
    """One distillation turn, whatever happened."""
    accepted: skills.SkillVersion | None
    rejection: skills.Rejection | None
    seconds: float
    repairs: int
    memory_tool_calls: int
    eligible_traces: int
    proposal_chars: int
    note: str = ""
    queries: list[str] = field(default_factory=list)

    @property
    def version(self) -> int | None:
        return self.accepted.version if self.accepted else None


def render_steps(steps: list[dict]) -> str:
    """Every step, as text, for a writer that cannot query the graph.

    NO CAP, AND THAT NOW MEANS NO CAP. There was a `limit=120` on the
    number of steps, and stacked on top of a `per_trace=40` in trace_steps
    it meant the author saw at most 120 of the 993 steps the last series
    wrote. Both were mine; AIP specifies neither, and they made section 6.3
    -- walk the source material line by line and classify every item as
    Mapped / Schema gap / Body drop / Deliberate drop -- structurally
    impossible, because nothing can classify what it was never shown.

    The step COUNT cap went then. Three per-field ones stayed, also mine:
    thought[:300], action[:200], observation[:200]. They survived because
    the docstring above said "no cap" and nobody re-read the code under it.

    While thoughts were cumulative (see harness/reasoning_relay.py) the 300
    was catastrophic rather than merely lossy: every step's thought began
    with the same sentence, so 300 characters of it WAS that sentence, and
    the author was handed one identical line per step. That is why 81
    accepted skill versions changed nothing across the 2026-09-20 run.

    With thoughts now per model turn the 300 is an ordinary truncation of
    real reasoning -- and still wrong. The operator's rule: "The
    compression should never be a limit on the model. It should be a
    subsequent step." That subsequent step exists and is AIP's own:
    progressive disclosure relocates detail into `references/` AFTER a
    version is accepted. Shrinking the author's evidence up front is not
    compression, it is blindness.

    200 characters of observation is the same mistake in a smaller place:
    it is shorter than almost every traceback this project grades on.
    """
    lines = []
    for st in steps:
        thought = (st.get("thought") or "").strip().replace("\n", " ")
        action = (st.get("action") or "").strip()
        obs = (st.get("observation") or "").strip().replace("\n", " ")
        lines.append(f"  - [{'pass' if st.get('suite_passed') else 'fail'}] "
                     f"{thought}\n      action: {action}"
                     f"\n      result: {obs}")
    return "\n".join(lines)


def build_prompt(current: skills.SkillVersion, *, attempt: int,
                 tests_passed: int, suite_passed: bool, error: str | None,
                 eligible: list[dict], out_path: str,
                 steps: list[dict] | None = None,
                 has_graph_tools: bool = True) -> str:
    """What the distiller is told. Deliberately free of task knowledge.

    It states the job, the evidence available, the format, and the two
    things the grader rejects outright -- all of which the migrating agent
    is already told in its own prompt. It does not say what to write.
    """
    # EVERY eligible trace, not the last 12.
    #
    # The skill is supposed to accumulate what all previous runs learned,
    # and a writer shown only the tail is being asked to improve a
    # procedure against a fraction of the evidence that produced it. With
    # `[-12:]` and 44 eligible traces, two thirds of the history -- which
    # included the attempts the best version was written from -- was not
    # in the prompt at all. One line each, so the whole corpus costs a few
    # hundred tokens against a 13,000-token budget.
    history = "\n".join(
        f"  - trace {t['id'][:8]}: {t['steps']} step(s), "
        f"tests_passed={int((t.get('metrics') or {}).get('tests_passed', 0))}, "
        f"suite_passed={bool(t.get('suite_passed'))}"
        for t in eligible
    ) or "  (none yet -- this is the first attempt on this harness)"

    verdict = ("the full suite PASSED" if suite_passed
               else f"the suite FAILED with {tests_passed} test(s) passing")
    if has_graph_tools:
        evidence = (
            "  - Your own past attempts are recorded in a reasoning graph. "
            "You have\n    memory tools; use them to look up what you "
            "tried, what the reasoning\n    was, and which steps failed. "
            "Search for the errors you hit.")
    else:
        # A tool-less writer is handed a selection instead of choosing
        # one. Worth remembering when comparing the two writers.
        rendered = render_steps(steps or [])
        evidence = ("  - The reasoning steps from those attempts, in order:\n"
                    + (rendered or "    (none recorded yet)"))
    aip = skills.AIP_SKILL.read_text()
    practices = skills.AIP_BEST_PRACTICES.read_text()
    return f"""You have just finished attempt {attempt} of a coding task, and {verdict}.

Your job now is to improve the written procedure you work from, so that
your next attempt goes better. This is the only thing you carry between
attempts: you will not remember this conversation.

Evidence you can use:
{evidence}
  - {len(eligible)} past attempts are eligible to learn from:
{history}
{f"  - The failure your last attempt ended on:{chr(10)}```{chr(10)}{error[:1500]}{chr(10)}```" if error else ""}

Write the improved procedure to `{out_path}`. That file does not exist
yet -- create it.

# HOW TO AUTHOR IT

Follow AIP's own authoring procedure, reproduced in full below. It is the
specification you are writing against, not a summary of one. Where it
describes interactive steps (asking which name to use, asking where to
install), those are already settled: the name is `{skills.SKILL_NAME}`,
the schema is the one bundled in the current skill's `source/`, and this
harness installs the result. Everything else applies as written --
including section 6.3, the completeness check.

<aip_skill>
{aip}
</aip_skill>

<aip_skill_creation_best_practices>
{practices}
</aip_skill_creation_best_practices>

# WHAT THIS HARNESS FIXES

  - `name` must stay `{skills.SKILL_NAME}`.
  - `metadata.aip.version` must be exactly {current.version + 1}.
  - `metadata.aip.spec` must be exactly `{skills.aip_spec_url()}`.
  - WRITE THE BEST PROCEDURE YOU CAN. Length is not your problem here.
    If the body ends up longer than AIP's {skills.AIP_BODY_TARGET_TOKENS}-token
    target, a SEPARATE pass afterwards will ask you to move detail into
    `references/` per AIP's progressive disclosure -- relocating it, not
    deleting it. So do not compress, do not merge steps to save room, and
    do not drop an anti-pattern because the file is getting long.
    (There is a {skills.DEFAULT_MAX_TOKENS}-token hard ceiling on the
    whole file, far above the target; the current version is
    {current.approx_tokens}.)
  - Two things this task's grader rejects however green the tests go:
    re-pointing imports at `pydantic.v1`, and emptying a function body so
    it still imports. Say so in the procedure.

# THE COMPLETENESS CHECK IS NOT OPTIONAL

AIP section 6.3 tells you to walk the source material line by line
against what you compiled, and classify every distinct item as Mapped,
Schema gap, Body drop, or Deliberate drop. **The current version below is
source material.** It was written from graded attempts on this same
codebase, and anything in it that you do not carry forward is knowledge
this agent loses permanently -- it has no other memory of those attempts.

This has already happened here, and it is the single most expensive
mistake available to you: one rewrite took the procedure from 24 steps to
11 and none of the 24 survived, and the agent's next attempts stopped
making progress entirely. Drop something only when you can say why, and
say it in a YAML comment on the line where it used to be.

This is the current version. It is evidence, not a draft to replace:

<current_skill>
{current.text}
</current_skill>
"""


def with_diagnostics(prompt: str, rejection: skills.Rejection) -> str:
    """The SAME prompt, plus what the validator said. Nothing else.

    There was a `repair_prompt()` here that built a small standalone
    message -- 860 characters, the diagnostic and "write the corrected
    file again". It was written for `AgentWriter`, which resumes a Vibe
    session and therefore still holds the AIP package, the current skill
    and the evidence. `ExternalWriter` is stateless: every call is a fresh
    HTTP request. So once that became the default writer, a repair turn
    asked a frontier model to reproduce a 30,000-character SKILL.md from
    a one-line error, with no source materials at all. It invented the
    two metadata URLs because it had nothing to copy them from, and a
    single recoverable failure became a guaranteed three-call loss.

    AIP already prescribes the behaviour (SKILL.md 6.2): run the
    validator, and on a trivial error fix it and re-run -- with the source
    materials still in hand throughout. So the repair is the original
    prompt with the validator's own output appended, and this harness
    stops authoring a second prompt of its own.
    """
    return (f"{prompt}\n\n"
            f"# THE PREVIOUS ATTEMPT WAS REJECTED -- FIX IT AND RE-EMIT\n\n"
            f"Reason: {rejection.reason}\n\n"
            f"The validator's own output, verbatim:\n\n"
            f"{rejection.detail}\n\n"
            f"What you wrote last time:\n\n"
            f"{rejection.proposal}\n")


_REFERENCE_MARK = "=== FILE: "


def disclosure_prompt(accepted: skills.SkillVersion) -> str:
    """Ask the author to RELOCATE detail, not to delete it.

    A SEPARATE PASS, after a version has already been accepted, and this is
    deliberate. The previous arrangement put size pressure inside authoring:
    my prompt said "rewriting to be denser is better than appending"
    unconditionally, so it fired with 10,500 of 13,000 tokens spare, and one
    rewrite cut the procedure from 24 steps to 11 -- none of the 24
    surviving. Knowledge the agent had no other memory of, gone to hit a
    number.

    AIP already answers this and answers it differently. Its three tiers are
    metadata (always in context), body (on activation), `references/` (on
    demand), and its instruction is to "push detail into `references/`
    rather than letting SKILL.md bloat" because "body tokens cost every
    invocation; reference tokens cost only when loaded". That is relocation.
    Nothing is dropped, and the per-turn cost -- which is where warm's +14%
    token premium came from -- falls anyway.

    The pass runs only when the body is over AIP's own 5,000-token target,
    and if it fails or returns nothing usable the accepted version stands
    unchanged. A failed optimisation must never cost a good skill.
    """
    practices = skills.AIP_BEST_PRACTICES.read_text()
    return f"""The procedure below has been ACCEPTED and saved as version
{accepted.version}. Its content is correct. Do not add to it, remove
anything from it, or reword its instructions.

This is a RESHAPING of version {accepted.version}, not a new version. Keep
`metadata.aip.version` at {accepted.version} exactly -- a package stamped
with any other number is rejected.

One thing is wrong with its SHAPE: the body is {accepted.approx_tokens}
tokens, against AIP's target of {skills.AIP_BODY_TARGET_TOKENS}. The body
is re-sent on every single turn the agent takes, so every token in it is
paid tens of times per attempt.

Apply AIP's progressive disclosure, as described in its own best-practices
guide below. RELOCATE detail into `references/` files. Do not delete it.
If you cannot move something without losing it, leave it in the body.

<aip_skill_creation_best_practices>
{practices}
</aip_skill_creation_best_practices>

<current_skill>
{accepted.text}
</current_skill>

# WHAT TO SEND BACK

Every file, in this exact format, starting immediately with the first
marker line and with nothing before or after:

{_REFERENCE_MARK}SKILL.md ===
<the full SKILL.md, frontmatter included>
{_REFERENCE_MARK}references/<name>.md ===
<the full contents of that reference file>

Rules the harness enforces:

  - `metadata.aip.version` must be exactly {accepted.version + 1}.
  - `metadata.aip.spec` must be exactly `{skills.aip_spec_url()}`.
  - `name` must stay `{skills.SKILL_NAME}`.
  - Every `references/` file you write must be pointed at from the body,
    and the pointer must say WHEN to read it -- AIP is explicit that
    "Read `references/api-errors.md` if the API returns a non-200 status"
    beats "see references/ for details". A reference nothing loads is
    knowledge deleted with extra steps.
  - The body must still validate on its own as a complete AIP procedure.

If the body cannot honestly get under the target without losing
knowledge, send back the skill unchanged. That is an acceptable answer
and a better one than a shorter procedure that has forgotten something.
"""


def parse_package(text: str) -> tuple[str, dict[str, str]]:
    """Split a `=== FILE: path ===` reply into (SKILL.md, references).

    Returns ("", {}) on anything it does not recognise, which the caller
    treats as "the pass produced nothing" and keeps the accepted version.
    Only `references/` paths are honoured: this reply is model output, and
    it is about to be written to disk.
    """
    if _REFERENCE_MARK not in text:
        return "", {}
    body = ""
    references: dict[str, str] = {}
    chunks = text.split(_REFERENCE_MARK)
    for chunk in chunks[1:]:
        header, _, content = chunk.partition("\n")
        name = header.strip().removesuffix("===").strip()
        content = content.strip("\n")
        if name == "SKILL.md":
            body = content
        elif (name.startswith("references/") and name.count("/") == 1
                and ".." not in name and name.endswith(".md")):
            references[name] = content
    return body, references


async def relocate_into_references(
    accepted: skills.SkillVersion,
    *,
    writer: Any,
    derived_from: list[str],
) -> tuple[skills.SkillVersion | None, str]:
    """Run the disclosure pass. Returns (new version or None, a note).

    Never raises, and never leaves the skill worse: the relocated package
    is proposed through the same validator as any other version, and if it
    is rejected -- or comes back no smaller -- `accepted` simply stands.
    """
    try:
        reply, _ = await writer.write(disclosure_prompt(accepted), resume=False)
    except Exception as exc:
        return None, f"disclosure pass did not run: {exc!r}"
    body, references = parse_package(reply)
    if not body:
        return None, "disclosure pass returned no SKILL.md; kept the body as authored"
    if not references:
        return None, ("disclosure pass moved nothing into references/; "
                      "kept the body as authored")
    new_tokens = skills.approx_tokens(body)
    if new_tokens >= accepted.approx_tokens:
        # Not a shrink, so it is a rewrite of a procedure that was already
        # accepted -- exactly the churn this pass exists to avoid.
        return None, (f"disclosure pass returned {new_tokens} tokens against "
                      f"{accepted.approx_tokens}; kept the body as authored")
    # REPLACE, not a new version. This pass reshapes a procedure that has
    # already been accepted -- it adds no knowledge -- so it must not
    # consume a version number. It did, and one attempt therefore left two
    # numbered files behind: 42 distillations, 81 files, warm's attempts
    # running on v2/v4/v6/v8.
    outcome = skills.propose(body, derived_from=derived_from,
                             references=references, replace=True)
    if isinstance(outcome, skills.Rejection):
        return None, (f"disclosure pass rejected ({outcome.reason}); "
                      f"kept v{accepted.version}")
    return outcome, (f"progressive disclosure: body "
                     f"{accepted.approx_tokens} -> {outcome.approx_tokens} "
                     f"tokens, {len(references)} reference file(s)")


async def distill(
    *,
    workspace: Any,
    mem: Any,
    model: str,
    writer: Any | None = None,
    attempt: int,
    tests_passed: int,
    suite_passed: bool,
    error: str | None = None,
    max_repairs: int = MAX_REPAIRS,
    experiment: str | None = None,
) -> DistillResult:
    """Run one distillation turn and return what came of it.

    Never raises. It runs after the attempt is graded and the trace closed,
    so a distiller that dies costs a skill version, not a run -- and the
    previous version stays live, which is the safe direction.
    """
    started = time.monotonic()
    memory_calls = 0
    queries: list[str] = []
    repairs = 0
    proposal = ""

    try:
        # Scoped to THIS fixture AND THIS experiment. Unscoped by fixture,
        # the first distillation on a new codebase learns from the previous
        # one's 25 traces. Unscoped by experiment, it learns from every
        # earlier run on the same codebase -- 2,574 steps where the
        # experiment had written 103, which 400s the author outright.
        from orchestrator.manifest import FIXTURE_DIR
        eligible = await mem.eligible_traces(model=model,
                                             fixture=FIXTURE_DIR.name,
                                             experiment=experiment)
    except Exception as exc:
        logger.warning("distill: could not read eligible traces: %r", exc)
        eligible = []

    # Default: the agent writes its own skill. That is the mission's
    # claim, and swapping the writer changes what the run measures -- see
    # orchestrator/writers.py.
    writer = writer or AgentWriter(workspace)
    current = skills.current()
    out_path = writer.out_path()
    steps: list[dict] = []
    if not writer.uses_graph_tools and eligible:
        try:
            steps = await mem.trace_steps([t["id"] for t in eligible])
        except Exception as exc:
            logger.warning("distill: could not read trace steps: %r", exc)
    prompt = build_prompt(current, attempt=attempt, tests_passed=tests_passed,
                          suite_passed=suite_passed, error=error,
                          eligible=eligible, out_path=out_path,
                          steps=steps,
                          has_graph_tools=writer.uses_graph_tools)

    # WHAT THE AUTHOR IS ACTUALLY BEING HANDED. Reported, not capped.
    #
    # The three per-field caps in render_steps were removed on 2026-09-20
    # (they were mine, and the operator's rule is that compression must
    # never be a limit on the model). The obvious next move -- size the
    # uncapped prompt against real data before running -- turns out to be
    # impossible from the graph as it stands: every thought in it is a
    # CUMULATIVE blob from the relay bug, median 5,957 characters and 81%
    # of all rendered volume. Measuring that would be measuring the bug.
    #
    # Post-fix a thought is one model turn's reasoning, and nobody knows
    # what that costs for this model until one run produces it. So the
    # number is printed on every distillation instead of guessed at, and
    # the first real run answers the question. If it turns out to be a
    # problem, that is when a bound gets decided -- on evidence, and by
    # the operator.
    #
    # AND NOTE WHAT IS *NOT* CLAIMED HERE: that any particular size is too
    # big for the author to read. `DEFAULT_MAX_TOKENS = 13000` is the cap
    # on the body the author WRITES, and reading it as a limit on what it
    # can be SHOWN is a mistake already made once today.
    #
    # ONE number is now measured, and it is a transport limit rather than
    # a judgement about the model: the API refuses a single message longer
    # than MAX_MESSAGE_CHARS with a 400, observed live on 2026-09-20 at
    # 11,818,940 characters. That is not a reason to compress the model's
    # evidence -- the fix for that run was scoping traces to the
    # experiment, above -- but a 400 loses the WHOLE skill rather than the
    # oldest part of it, so this drops steps from the front until the
    # request is transmissible and says exactly how many went.
    print(f"  [distil] author prompt: {skills.approx_tokens(prompt):,} "
          f"approx tokens ({len(steps or []):,} step(s) rendered whole)")
    dropped = 0
    while len(prompt) > MAX_MESSAGE_CHARS and len(steps or []) > 1:
        # Oldest first: the most recent attempt is the one the next
        # version has to improve on.
        steps = steps[1:]
        dropped += 1
        prompt = build_prompt(current, attempt=attempt,
                              tests_passed=tests_passed,
                              suite_passed=suite_passed, error=error,
                              eligible=eligible, out_path=out_path,
                              steps=steps,
                              has_graph_tools=writer.uses_graph_tools)
    if dropped:
        print(f"  [distil] TRANSPORT LIMIT: dropped the {dropped:,} oldest "
              f"step(s) to fit {MAX_MESSAGE_CHARS:,} chars; "
              f"{len(steps):,} remain ({len(prompt):,} chars). This is a "
              f"transport bound, not a judgement about the author -- if it "
              f"fires, trace scoping is probably wrong again.")

    base_prompt = prompt
    rejection: skills.Rejection | None = None
    for turn in range(max_repairs + 1):
        # Before every turn, including repairs: Vibe's write_file will not
        # overwrite an existing file, so the output path must be absent or
        # the turn cannot produce anything.
        try:
            proposal, entries = await writer.write(prompt, resume=turn > 0)
        except Exception as exc:
            return DistillResult(
                None, None, time.monotonic() - started, repairs, memory_calls,
                len(eligible), len(proposal),
                note=f"the distillation turn did not run: {exc!r}")

        # What it actually asked the graph, off its own stream. The mission
        # asks for this explicitly: "distillation doesn't use the graph" is
        # a finding, not a bug to hide.
        for step in ingest.parse_stream(entries).steps:
            if step.tool_name and is_memory_tool(step.tool_name):
                memory_calls += 1
                queries.append(step.action[:200])

        if os.environ.get("DISTILL_DEBUG"):
            for st in ingest.parse_stream(entries).steps:
                print(f"      [distill] {st.action[:90]} -> "
                      f"{'FAILED ' if st.failed else ''}{st.observation[:140]!r}")
        if not proposal.strip():
            rejection = skills.Rejection(
                reason="no_output",
                detail=f"the distiller wrote nothing to {out_path}",
                proposal="")
        else:
            outcome = skills.propose(
                proposal, derived_from=[t["id"] for t in eligible])
            if isinstance(outcome, skills.SkillVersion):
                note = ""
                # THE COMPRESSION STEP, AFTER AUTHORING AND NEVER DURING IT.
                # The version above is already saved and already valid; if
                # this pass produces nothing it stays exactly as authored.
                if outcome.approx_tokens > skills.AIP_BODY_TARGET_TOKENS:
                    shorter, note = await relocate_into_references(
                        outcome, writer=writer,
                        derived_from=[t["id"] for t in eligible])
                    outcome = shorter or outcome
                return DistillResult(
                    outcome, None, time.monotonic() - started, repairs,
                    memory_calls, len(eligible), len(proposal),
                    queries=queries, note=note)
            rejection = outcome

        if turn < max_repairs:
            repairs += 1
            # The ORIGINAL prompt, every time, with the diagnostics on the
            # end -- never a smaller replacement. `base_prompt` and not
            # `prompt`, so two repairs do not stack two diagnostics.
            prompt = with_diagnostics(base_prompt, rejection)

    # KEEP THE EVIDENCE. Three distillations were rejected `invalid_schema`
    # in one run and the log held exactly that word -- no proposal, no
    # validator output, nothing to fix the prompt from. The rejected text
    # and the diagnostics are the only things that say WHY.
    if rejection is not None:
        try:
            # Under versions_dir(), which the tests monkeypatch into a
            # tmp sandbox. Rooted at REPO_ROOT instead, the test suite
            # wrote its own rejected proposals into runs/rejected/ and
            # they read as evidence from a real run.
            debug_dir = skills.versions_dir() / "rejected"
            debug_dir.mkdir(parents=True, exist_ok=True)
            stem = f"attempt{attempt}-v{current.version + 1}-{rejection.reason}"
            (debug_dir / f"{stem}.md").write_text(rejection.proposal or "")
            (debug_dir / f"{stem}.diagnostics.txt").write_text(rejection.detail or "")
        except Exception as exc:                      # never cost a run
            logger.warning("could not save rejected proposal: %r", exc)

    # Out of repair turns. The previous version stays live, which is why
    # `propose` never touches the live file until a proposal validates.
    return DistillResult(
        None, rejection, time.monotonic() - started, repairs, memory_calls,
        len(eligible), len(proposal), queries=queries,
        note=(f"kept v{current.version}: {rejection.reason} after "
              f"{repairs} repair turn(s)") if rejection else "")
