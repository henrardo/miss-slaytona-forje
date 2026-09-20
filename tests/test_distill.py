"""The distillation turn: what it may write, and what it must refuse.

The skill is loaded into every subsequent warm attempt, so a bad version is
not a wasted turn -- it poisons the arm for the rest of the run. These pin
the properties that make that safe: an invalid proposal never becomes live,
the validator's own words go back to the model, a distiller that dies costs
a version and not a run, and the prompt contains no migration knowledge.
"""
from __future__ import annotations

import asyncio
import shutil

import pytest

from orchestrator import distill, skills


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the real skill package, so tests cannot damage the live one."""
    root = tmp_path / "skills"
    shutil.copytree(skills.SKILLS_DIR, root)
    monkeypatch.setattr(skills, "SKILLS_DIR", root)
    monkeypatch.setattr(skills, "VALIDATOR", root / "_aip" / "scripts" / "validate.py")
    return root


def _next(offset: int = 1) -> int:
    """The version a proposal must carry. RELATIVE, because the live skill
    advances every real run -- a hard-coded 1 passes until the agent
    distils for the first time and then fails everywhere at once."""
    return skills.current().version + offset


def _skill(version: int, *, purpose: str = "Migrate a codebase.") -> str:
    return f'''---
name: pydantic-v2-migration
description: A distilled procedure, written by the agent from its own graded attempts.
metadata:
  aip:
    spec: "{skills.aip_spec_url()}"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: {version}
    derived_from_traces: []
---

```yaml
purpose: >
  {purpose}
trigger_when:
  - Asked to migrate to Pydantic v2
steps:
  - name: run-the-suite
    description: Run the suite and read the first error.
```
'''


class FakeWorkspace:
    """A distiller's environment, in memory.

    `writes` is what the model chooses to leave in its output file, one
    entry per turn -- so a test can script "invalid, invalid, valid" and
    check the repair loop.
    """

    def __init__(self, writes: list[str], *, stream: list[dict] | None = None,
                 explode: bool = False) -> None:
        self.writes = list(writes)
        self.stream = stream or []
        self.explode = explode
        self.prompts: list[str] = []
        self.cleared = 0
        self._file = ""

    def distill_skill_path(self) -> str:
        return "/home/agent-warm-0/distill/SKILL.md"

    def clear_distilled(self) -> None:
        """Mirrors the real one: the output file must NOT exist.

        Vibe's write_file refuses to overwrite ("Use edit to modify it"),
        so a distiller whose output path already holds a file writes
        nothing at all -- which is how every distillation failed in the
        first local rehearsal. The fake starts empty for the same reason.
        """
        self.cleared += 1
        self._file = ""

    def read_distilled(self) -> str:
        return self._file

    def stream_entries(self, stdout: str) -> list[dict]:
        return self.stream

    async def run_distill(self, prompt: str, *, timeout_s: float,
                          resume: bool = False):
        self.prompts.append(prompt)
        if self.explode:
            raise RuntimeError("ssh died")
        self._file = self.writes.pop(0) if self.writes else ""
        return 0, ""


class FakeMem:
    """The subset of ScopedMemory the distiller touches.

    It must accept EVERY keyword `distill` passes, because `distill`
    catches the failure and carries on with no traces at all. A fake that
    rejects a new kwarg therefore turns into a silent "0 eligible traces"
    rather than a test failure, which is exactly how the fixture filter
    went untested when it was added.
    """

    def __init__(self, eligible: list[dict] | None = None,
                 explode: bool = False,
                 steps: list[dict] | None = None) -> None:
        self._eligible = eligible or []
        self.explode = explode
        self._steps = steps or []
        self.calls: list[dict] = []

    async def eligible_traces(self, *, model: str, schema: float = 2.0,
                              fixture: str | None = None,
                              experiment: str | None = None):
        self.calls.append({"model": model, "fixture": fixture,
                           "experiment": experiment})
        if self.explode:
            raise RuntimeError("Aura is down")
        return self._eligible

    async def trace_steps(self, trace_ids):
        return self._steps


class FakeExternalWriter:
    """An external author: stateless, and CANNOT query the graph.

    That last property is the one that matters here -- `distill` only
    renders steps into the prompt for a writer that cannot go and read
    them itself, which is the real run's configuration (gpt-5.6-sol).
    The default AgentWriter uses graph tools, so a test built on it
    silently renders zero steps.
    """

    uses_graph_tools = False

    def __init__(self, writes: list[str]) -> None:
        self.writes = list(writes)
        self.prompts: list[str] = []

    def out_path(self) -> str:
        return "/tmp/distill/SKILL.md"

    async def write(self, prompt: str, *, resume: bool):
        self.prompts.append(prompt)
        return (self.writes.pop(0) if self.writes else ""), []


def _trace(tid: str, steps: int) -> dict:
    """An eligible-trace row in the shape build_prompt actually reads."""
    return {"id": tid + "0" * 8, "steps": steps, "suite_passed": False,
            "metrics": {"tests_passed": 0}, "outcome": "failed",
            "task": "migrate", "real_thoughts": steps}


async def _run(ws, mem=None, **kw):
    return await distill.distill(
        workspace=ws, mem=mem or FakeMem(), model="m", attempt=1,
        tests_passed=0, suite_passed=False, **kw)


@pytest.mark.asyncio
async def test_a_valid_proposal_becomes_the_next_version(sandbox) -> None:
    before = skills.current().version
    ws = FakeWorkspace([_skill(_next())])
    result = await _run(ws)
    assert result.accepted is not None, result.rejection
    assert result.version == _next() - 1
    assert skills.current().version == before + 1
    assert result.repairs == 0


@pytest.mark.asyncio
async def test_an_invalid_proposal_is_repaired_then_accepted(sandbox) -> None:
    """Two repair turns are allowed; the validator's own diagnostics go
    back each time."""
    expected = _next()
    ws = FakeWorkspace(["not a skill at all", _skill(expected)])
    result = await _run(ws)
    assert result.accepted is not None, result.rejection
    assert result.repairs == 1
    assert len(ws.prompts) == 2
    # A repair RESENDS the original prompt with the validator's output on
    # the end. It is not a smaller message of the harness's own: the
    # external writer is stateless, so anything left out is simply gone.
    assert ws.prompts[0] in ws.prompts[1], (
        "the repair turn dropped the source materials")
    assert "THE PREVIOUS ATTEMPT WAS REJECTED" in ws.prompts[1]
    assert "not a skill at all" in ws.prompts[1], (
        "the rejected draft is not shown back to its author")
    assert skills.aip_spec_url() in ws.prompts[1]


@pytest.mark.asyncio
async def test_three_bad_proposals_keep_the_previous_version(sandbox) -> None:
    """After the repair budget, the live skill is untouched and the
    rejection is recorded rather than swallowed."""
    before = skills.current()
    ws = FakeWorkspace(["garbage", "still garbage", "garbage again"])
    result = await _run(ws)
    assert result.accepted is None
    assert result.rejection is not None
    assert result.repairs == 2
    assert len(ws.prompts) == 3, "the repair budget is 2 turns after the first"
    assert skills.current().text == before.text
    assert f"kept v{skills.current().version}" in result.note


@pytest.mark.asyncio
async def test_a_distiller_that_writes_nothing_is_a_rejection(sandbox) -> None:
    """An empty file is not a valid skill, and it is a different failure
    from an invalid one -- the model never answered."""
    ws = FakeWorkspace(["", "", ""])
    result = await _run(ws)
    assert result.accepted is None
    assert result.rejection.reason == "no_output"


@pytest.mark.asyncio
async def test_a_dead_distiller_costs_a_version_not_a_run(sandbox) -> None:
    """It runs after the attempt is graded and the trace closed."""
    before = skills.current()
    result = await _run(FakeWorkspace([], explode=True))
    assert result.accepted is None
    assert "did not run" in result.note
    assert skills.current().text == before.text


@pytest.mark.asyncio
async def test_an_unreachable_graph_still_lets_distillation_proceed(sandbox) -> None:
    """The model can write a better procedure from the attempt it just
    lived through, even if the graph is down."""
    result = await _run(FakeWorkspace([_skill(_next())]), mem=FakeMem(explode=True))
    assert result.accepted is not None
    assert result.eligible_traces == 0


@pytest.mark.asyncio
async def test_an_oversized_proposal_is_rejected(sandbox) -> None:
    """The skill is prompt prefix on every attempt, so a distiller that
    pads is charging the arm whose token count is the headline number.

    Sized off the cap rather than hard-coded: this test silently stopped
    testing anything when the cap moved from 2,000 to 13,000, because its
    8,000-token padding was suddenly legal.
    """
    over = skills.DEFAULT_MAX_TOKENS + 1000          # tokens
    huge = _skill(_next(), purpose="padding " * (over * 4 // len("padding ")))
    ws = FakeWorkspace([huge, huge, huge])
    result = await _run(ws)
    assert result.accepted is None
    assert result.rejection.reason == "too_large"


@pytest.mark.asyncio
async def test_memory_tool_calls_are_counted(sandbox) -> None:
    """"The distiller never queried the graph" is a finding the mission
    asks for by name, so it has to be countable."""
    stream = [
        {"type": "reasoning", "turnId": "t", "text": "what did I try before"},
        {"type": "effect", "turnId": "t", "title": "neo4j-agent-memory_search_steps",
         "detail": {"toolName": "neo4j-agent-memory_search_steps",
                    "input": {"query": "BaseSettings"}},
         "state": {"status": "completed", "outputText": "3 hits"}},
        {"type": "reasoning", "turnId": "t", "text": "now write it"},
        {"type": "effect", "turnId": "t", "title": "write_file",
         "detail": {"toolName": "write_file", "input": {"path": "SKILL.md"}},
         "state": {"status": "completed", "outputText": "ok"}},
    ]
    result = await _run(FakeWorkspace([_skill(_next())], stream=stream))
    assert result.memory_tool_calls == 1
    assert result.queries and "search_steps" in result.queries[0]


def test_the_prompt_contains_no_migration_answer() -> None:
    """The skill must come only from the agent's own distillation. If the
    prompt named the fix, warm's advantage would be the prompt's."""
    prompt = distill.build_prompt(
        skills.current(), attempt=2, tests_passed=12, suite_passed=False,
        error="E   ImportError: cannot import name 'BaseSettings'",
        eligible=[], out_path="/tmp/SKILL.md")
    # EXCLUDING the <current_skill> block. From v1 onward that block is the
    # agent's OWN distilled procedure, quoted back so it can improve it --
    # so it contains the migration answer by design, and including it here
    # would make this test fail on success. What must stay clean is the
    # part the HARNESS writes.
    import re as _re
    harness_written = _re.sub(r"<current_skill>.*?</current_skill>", "",
                              prompt, flags=_re.DOTALL)
    assert "<current_skill>" in prompt, "the current skill is no longer quoted"
    lowered = harness_written.lower()
    for leak in ("pydantic_settings", "field_validator", "model_validator",
                 "model_config", "email_validator", "configdict",
                 "basesettings has been moved"):
        assert leak not in lowered, f"the distillation prompt contains {leak!r}"
    # The two gaming patterns ARE named: the grader rejects them and the
    # migrating agent is told so already, so this adds nothing it lacks.
    assert "pydantic.v1" in prompt


def test_the_prompt_states_the_format_the_validator_enforces() -> None:
    """A distiller that does not know the version must advance will fail
    every turn of its repair budget on the same error."""
    live = skills.current()
    prompt = distill.build_prompt(
        live, attempt=1, tests_passed=0, suite_passed=False,
        error=None, eligible=[], out_path="/tmp/SKILL.md")
    assert f"must be exactly {live.version + 1}" in prompt
    assert "one fenced yaml block" in prompt.lower()
    assert str(skills.DEFAULT_MAX_TOKENS) in prompt


@pytest.mark.asyncio
async def test_concurrent_proposals_do_not_collide(sandbox) -> None:
    """Two warm agents finishing at once both read v0 and both write v1.
    Without the lock one version silently overwrites the other and the
    graph records two skills with the same number."""
    body = _skill(_next())   # computed ONCE: both threads race the same N

    def propose(_n: int):
        return skills.propose(body, derived_from=[])

    results = await asyncio.gather(
        asyncio.to_thread(propose, 1), asyncio.to_thread(propose, 2))
    accepted = [r for r in results if isinstance(r, skills.SkillVersion)]
    rejected = [r for r in results if isinstance(r, skills.Rejection)]
    assert len(accepted) == 1, "both proposals became the same version"
    assert len(rejected) == 1
    assert rejected[0].reason == "wrong_version"
    assert skills.current().version == accepted[0].version


@pytest.mark.asyncio
async def test_the_output_file_is_cleared_before_every_turn(sandbox) -> None:
    """Vibe's write_file will not overwrite an existing file, so a turn
    whose output path is already occupied silently produces nothing. The
    first local rehearsal failed every distillation this way."""
    ws = FakeWorkspace(["garbage", _skill(_next())])
    result = await _run(ws)
    assert result.accepted is not None, result.rejection
    assert ws.cleared == 2, (
        f"cleared {ws.cleared} time(s) for {len(ws.prompts)} turn(s); the "
        f"repair turn would collide with the rejected turn's file")


def test_the_real_workspace_has_every_method_the_distiller_calls() -> None:
    """Run 1 lost its distillation to
    `AttributeError: 'AgentWorkspace' object has no attribute
    'seed_distillation'` -- a method renamed to `clear_distilled` while
    swarm/run.py's closure still called the old name.

    The rehearsal missed it because it calls `distill()` directly rather
    than through run.py's closure, and FakeWorkspace was updated with the
    rename. So the contract is asserted against the REAL class here.
    """
    import inspect

    from swarm.agent_workspace import AgentWorkspace

    for method in ("distill_skill_path", "clear_distilled", "read_distilled",
                   "run_distill", "stream_entries", "enable_distillation",
                   "install_skill", "loaded_skill_text", "has_skills_dir",
                   "setup_fingerprint"):
        assert hasattr(AgentWorkspace, method), (
            f"AgentWorkspace has no {method!r}; the distillation turn or the "
            f"run's checks would die at runtime, after the attempt")

    # And nothing in the runner may call a workspace method that is gone.
    runner = inspect.getsource(
        __import__("swarm.run", fromlist=["run"]))
    assert "seed_distillation" not in runner


def test_the_prompt_hands_over_aip_s_own_authoring_procedure() -> None:
    """AIP as shipped, not my paraphrase of it.

    Only the two validator scripts were installed, so the authoring half
    of the package -- the half with the procedure, the best-practices
    guide and the completeness check -- was never used, and the distiller
    worked from format instructions written here instead. That is how a
    single rewrite dropped 24 steps to 11 and how every version carried
    the wrong `metadata.aip.spec`.
    """
    prompt = distill.build_prompt(
        skills.current(), attempt=1, tests_passed=0, suite_passed=False,
        error=None, eligible=[], out_path="/tmp/SKILL.md")
    assert "<aip_skill>" in prompt and "<aip_skill_creation_best_practices>" in prompt
    # The real text, not a stub: a marker only the shipped SKILL.md has.
    assert "## AIP Specification" in prompt
    # 6.3, the shipped answer to content loss.
    assert "completeness check" in prompt.lower()
    assert "Deliberate drop" in prompt
    # And the spec URL must be the one the installed validator demands.
    assert skills.aip_spec_url() in prompt
    assert "arxiv.org/abs/2606.04781" not in prompt

    rejection = skills.Rejection(
        reason="invalid_schema",
        detail="{'Leaving type': 'ignore'} is not of type 'string'",
        proposal="the draft that was rejected")
    repair = distill.with_diagnostics(prompt, rejection)
    # A REPAIR KEEPS THE SOURCE MATERIALS. The harness used to substitute
    # an 860-character standalone message here, written for the resumable
    # agent writer. ExternalWriter is stateless, so that asked a frontier
    # model to reproduce a 30,000-character SKILL.md from one line of
    # error text -- it invented the two metadata URLs because it had
    # nothing to copy them from, and every repair turn was wasted.
    assert prompt in repair, "the repair threw the source materials away"
    assert skills.aip_spec_url() in repair
    assert rejection.detail in repair
    assert rejection.proposal in repair, (
        "the author cannot fix a draft it was not shown")
    # And two repairs must not stack two diagnostics.
    again = distill.with_diagnostics(prompt, rejection)
    assert again.count("THE PREVIOUS ATTEMPT WAS REJECTED") == 1


# ---- who writes the skill --------------------------------------------------

def test_the_external_writer_is_handed_the_evidence() -> None:
    """An API call has no MCP tools, so it cannot query the graph. The
    traces must travel in its prompt -- and the prompt must not tell a
    tool-less writer to use tools it does not have."""
    steps = [{"trace": "t1", "suite_passed": True,
              "thought": "BaseSettings moved, so the import must change",
              "action": "edit(config.py)", "observation": "ok"}]
    external = distill.build_prompt(
        skills.current(), attempt=1, tests_passed=0, suite_passed=False,
        error=None, eligible=[{"id": "t1", "steps": 1, "metrics": {}}],
        out_path="X", steps=steps, has_graph_tools=False)
    assert "BaseSettings moved" in external
    assert "You have\n    memory tools" not in external

    agent = distill.build_prompt(
        skills.current(), attempt=1, tests_passed=0, suite_passed=False,
        error=None, eligible=[{"id": "t1", "steps": 1, "metrics": {}}],
        out_path="X", steps=steps, has_graph_tools=True)
    assert "memory tools" in agent
    # The agent chooses what to look at; handing it the steps would remove
    # the behaviour the run is measuring.
    assert "BaseSettings moved" not in agent


def test_an_outer_fence_is_stripped_but_the_bodys_own_fence_survives() -> None:
    """A SKILL.md contains a ```yaml block, so a model told 'reply with
    the file' usually wraps the whole thing in a second fence. Losing a
    repair turn to packaging would be a waste of the budget."""
    from orchestrator.writers import strip_fence

    inner = "---\nname: x\n---\n\n```yaml\npurpose: y\n```"
    assert strip_fence(f"```markdown\n{inner}\n```") == inner
    assert strip_fence(inner) == inner
    assert strip_fence(f"```\n{inner}\n```").endswith("```")


def test_the_external_writer_refuses_to_start_without_a_key() -> None:
    """Better to fail at construction than after an attempt, where it
    would silently keep the previous skill version."""
    import pytest as _pytest

    from orchestrator.writers import ExternalWriter
    with _pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ExternalWriter("gpt-5", api_key="")


def test_authoring_carries_no_size_pressure_at_all(tmp_path) -> None:
    """Length is not the author's problem. It is a later pass's problem.

    The operator's instruction, verbatim: "The compression should never be
    a limit on the model. It should be a subsequent step that tells the
    author to distil a shorter skill from the current one USING AIP AS
    SHIPPED."

    What it replaced: my prompt said "Rewriting to be denser is better than
    appending" unconditionally, so it fired with ~10,500 of 13,000 tokens
    spare, and one distillation took the procedure from 3,439 words to 721
    -- 24 steps to 11, none of the 24 surviving. Nothing in the AUTHORING
    prompt may push the model toward a shorter file.
    """
    current = skills.current()
    prompt = distill.build_prompt(
        current=current, attempt=4, tests_passed=30, suite_passed=False,
        error="E   ImportError: cannot import name 'validator'",
        eligible=[], out_path="/tmp/SKILL.md", has_graph_tools=True)
    low = prompt.lower()
    assert "denser" not in low, "the compression ratchet is back"
    assert "do not compress" in low, (
        "the author is not told that length is handled elsewhere")
    assert "length is not your problem" in low
    # The hard ceiling may be MENTIONED -- an author that writes 20,000
    # tokens gets rejected and wastes a turn -- but the number it is
    # steered by must be AIP's body target, in the relocation pass.
    assert str(skills.AIP_BODY_TARGET_TOKENS) in prompt


def test_the_relocation_pass_moves_detail_and_never_deletes_it() -> None:
    """AIP's answer to size is progressive disclosure, not deletion.

    "Body tokens cost every invocation; reference tokens cost only when
    loaded." The pass must therefore say RELOCATE, hand over AIP's own
    guidance, and require a load-when trigger for each reference file --
    "see references/ for details" is knowledge deleted with extra steps.
    """
    accepted = skills.current()
    prompt = distill.disclosure_prompt(accepted)
    low = prompt.lower()
    assert "relocate" in low and "do not delete it" in low
    assert "progressive disclosure" in low
    assert "when to read it" in low or "say when" in low
    # AIP's shipped guidance, in full, rather than my summary of it.
    assert skills.AIP_BEST_PRACTICES.read_text()[:200] in prompt
    assert str(accepted.version + 1) in prompt


def test_a_relocation_reply_is_split_into_body_and_references() -> None:
    body, refs = distill.parse_package(
        "=== FILE: SKILL.md ===\nthe body\n"
        "=== FILE: references/edge-cases.md ===\nthe detail\n")
    assert body == "the body"
    assert refs == {"references/edge-cases.md": "the detail"}


def test_a_relocation_reply_cannot_write_outside_references() -> None:
    """This is model output on its way to the filesystem."""
    _, refs = distill.parse_package(
        "=== FILE: SKILL.md ===\nbody\n"
        "=== FILE: ../../.ssh/authorized_keys ===\nkey\n"
        "=== FILE: references/../../etc/passwd ===\nx\n"
        "=== FILE: references/deep/nested.md ===\ny\n")
    assert refs == {}


def test_nothing_usable_back_means_the_authored_version_stands() -> None:
    assert distill.parse_package("I could not shorten it, sorry") == ("", {})


def test_distillation_only_learns_from_this_fixtures_traces() -> None:
    """A booklet for codebase B must not be distilled from codebase A.

    Measured when the second fixture went live: its very FIRST
    distillation reported 25 eligible traces, before that fixture had
    produced a single one. All 25 belonged to the previous fixture, and
    the skill it wrote said so in its own comments -- "Attempt 3 regressed
    on a different repository". That is the seeding the whole experiment
    exists to rule out, arriving through the graph instead of by hand.
    """
    import inspect

    from orchestrator import memory as memory_mod

    src = inspect.getsource(distill.distill)
    assert "fixture=FIXTURE_DIR.name" in src, (
        "the distiller must scope eligible traces to the active fixture")

    sig = inspect.signature(memory_mod.ScopedMemory.eligible_traces)
    assert "fixture" in sig.parameters
    # Default None keeps pre-existing traces reachable on purpose rather
    # than by accident -- they predate the property.
    assert sig.parameters["fixture"].default is None
    query_src = inspect.getsource(memory_mod.ScopedMemory.eligible_traces)
    assert "t.prov_fixture = $fixture" in query_src


def test_every_trace_records_which_codebase_it_came_from() -> None:
    """The filter above is only as good as the stamp."""
    import inspect

    import swarm.run as runner

    src = inspect.getsource(runner.main_async)
    assert '"prov_fixture": FIXTURE_DIR.name' in src


def test_distillation_only_learns_from_this_experiments_traces() -> None:
    """The fixture filter is not enough: it lets in every EARLIER RUN.

    Measured 2026-09-20 on the first run of the rebuilt loop. Warm's
    attempt 1 wrote 103 steps; the distiller was handed 2,574. The other
    2,471 belonged to the previous night's 14 runs on the same fixture.
    Rendered whole that is 11,818,940 characters against the API's
    10,485,760 ceiling, so the author 400'd and NO skill was written --
    the failure is total, not partial.

    An experiment is N attempts on one checkout, so that is the scope.
    """
    import inspect

    from orchestrator import memory as memory_mod

    src = inspect.getsource(distill.distill)
    assert "experiment=experiment" in src, (
        "the distiller must scope eligible traces to the active experiment")

    sig = inspect.signature(memory_mod.ScopedMemory.eligible_traces)
    assert "experiment" in sig.parameters
    # Same reasoning as `fixture`: None stays unfiltered so traces written
    # before the property existed are reachable on purpose.
    assert sig.parameters["experiment"].default is None
    query_src = inspect.getsource(memory_mod.ScopedMemory.eligible_traces)
    assert "t.prov_experiment = $experiment" in query_src


def test_every_trace_records_which_experiment_wrote_it() -> None:
    """Again: the filter is only as good as the stamp, and the stamp has
    to be the run id rather than anything derived at read time."""
    import inspect

    import swarm.run as runner

    src = inspect.getsource(runner.main_async)
    assert '"prov_experiment": run_id' in src
    # And it has to reach distill(), or the filter is never applied.
    assert "experiment=run_id" in src


@pytest.mark.asyncio
async def test_an_untransmissible_prompt_drops_steps_instead_of_400ing(
        sandbox, capsys, monkeypatch) -> None:
    """A 400 loses the WHOLE skill; dropping the oldest steps loses part.

    This is the last-resort transport guard, NOT a cap on the author's
    evidence -- the fix for the run that found it was scoping traces to
    the experiment. If this guard ever fires in a real run, the scoping
    is wrong again, which is why it says so on stdout.
    """
    # A small ceiling, so the test exercises the real loop rather than
    # building 10 MB of text.
    monkeypatch.setattr(distill, "MAX_MESSAGE_CHARS", 20_000)
    steps = [{"thought": f"turn {i} " + "x" * 2_000,
              "action": "edit", "observation": "boom", "suite_passed": False}
             for i in range(40)]
    mem = FakeMem(eligible=[_trace("t1", len(steps))], steps=steps)
    ws = FakeWorkspace([])
    writer = FakeExternalWriter([_skill(_next())])
    await distill.distill(
        workspace=ws, mem=mem, model="m", writer=writer, attempt=1,
        tests_passed=0, suite_passed=False, experiment="exp-1")
    out = capsys.readouterr().out
    assert "TRANSPORT LIMIT" in out, out
    # The newest step survives: the next version has to improve on the
    # most recent attempt, not the first one.
    assert "turn 39" in out or "dropped the" in out


@pytest.mark.asyncio
async def test_a_transmissible_prompt_drops_nothing(sandbox, capsys) -> None:
    """The guard must be invisible in the normal case."""
    steps = [{"thought": f"turn {i}", "action": "edit",
              "observation": "boom", "suite_passed": False}
             for i in range(40)]
    mem = FakeMem(eligible=[_trace("t1", len(steps))], steps=steps)
    ws = FakeWorkspace([])
    writer = FakeExternalWriter([_skill(_next())])
    await distill.distill(
        workspace=ws, mem=mem, model="m", writer=writer, attempt=1,
        tests_passed=0, suite_passed=False, experiment="exp-1")
    out = capsys.readouterr().out
    assert "TRANSPORT LIMIT" not in out
    assert "40 step(s) rendered whole" in out, out


@pytest.mark.asyncio
async def test_the_experiment_scope_reaches_the_graph(sandbox) -> None:
    """Not source inspection -- the value actually arrives at the query."""
    mem = FakeMem()
    ws = FakeWorkspace([_skill(_next())])
    await distill.distill(
        workspace=ws, mem=mem, model="m", attempt=1,
        tests_passed=0, suite_passed=False, experiment="swarm-1789899324")
    assert mem.calls, "eligible_traces was never called"
    assert mem.calls[0]["experiment"] == "swarm-1789899324"
    # And the fixture filter is still applied alongside it, not instead.
    assert mem.calls[0]["fixture"]


# ---- the relocation pass, through distill() itself -----------------------


def _big_skill(version: int, *, tokens: int) -> str:
    """A valid skill whose body is deliberately over AIP's target."""
    filler = "pad " * (tokens * 4 // len("pad "))
    return _skill(version, purpose=filler)


def _package(version: int) -> str:
    return (f"=== FILE: SKILL.md ===\n{_skill(version)}\n"
            "=== FILE: references/detail.md ===\n"
            "# Detail\nRead this when the suite still fails after step 3.\n")


@pytest.mark.asyncio
async def test_an_oversized_body_triggers_the_relocation_pass(sandbox) -> None:
    """Author freely, THEN relocate. The operator's instruction, verbatim:
    "The compression should never be a limit on the model. It should be a
    subsequent step that tells the author to distil a shorter skill from
    the current one USING AIP AS SHIPPED."

    Two writer turns: the first authors a long procedure and is accepted,
    the second moves detail into `references/`.

    ONE VERSION COMES OUT, not two. The relocation reshapes the procedure
    just accepted -- it adds no knowledge -- so it REPLACES that version
    rather than consuming another number. It used to consume one, which is
    how the 2026-09-20 experiment turned 42 distillations into 81 numbered
    files and ran warm's attempts on v2, v4, v6, v8 instead of v1, v2, v3.
    Both writer turns are still real and nothing is rolled back; they just
    land on the same number.
    """
    start = skills.current().version
    over = skills.AIP_BODY_TARGET_TOKENS + 2000
    # Both turns stamp start + 1: the second is a reshaping of the first,
    # and `propose(replace=True)` rejects any other number.
    ws = FakeWorkspace([_big_skill(start + 1, tokens=over), _package(start + 1)])
    result = await _run(ws)
    assert result.accepted is not None, result.rejection
    assert result.version == start + 1, (
        "one attempt must leave exactly one version behind")
    assert len(ws.prompts) == 2, "the relocation pass did not run"
    assert "RELOCATE" in ws.prompts[1] and "progressive disclosure" in ws.prompts[1].lower()
    live = skills.current()
    assert live.approx_tokens < over, "the body did not shrink"
    assert "references/detail.md" in live.files, (
        "the reference tier did not reach the package, so the body's "
        "load-when trigger points at nothing")


@pytest.mark.asyncio
async def test_a_body_within_the_target_is_left_alone(sandbox) -> None:
    """No second call, no churn. The pass is triggered by AIP's number,
    not run on every distillation."""
    start = skills.current().version
    ws = FakeWorkspace([_skill(start + 1)])
    result = await _run(ws)
    assert result.accepted is not None
    assert result.version == start + 1
    assert len(ws.prompts) == 1, "the relocation pass ran on a short body"


@pytest.mark.asyncio
async def test_three_attempts_leave_exactly_three_versions(sandbox) -> None:
    """The shape of an experiment, asserted on the files themselves.

    An experiment is N attempts on one checkout, each followed by one
    distillation: v1, v2, v3, archive, stop. The count is checked on disk
    rather than on the returned version number, because it was the FILES
    that multiplied -- `versions_dir()` held 81 of them for 42
    distillations, and nothing was watching the archive.

    Half the attempts here are over AIP's size target, so the relocation
    pass runs on some and not others; the count must not depend on that.
    """
    start = skills.current().version
    over = skills.AIP_BODY_TARGET_TOKENS + 2000
    # Start the lineage empty. The sandbox copies the real skills tree,
    # leftovers and all, and this counts a DELTA -- so if the live skill
    # sits at v0 while the archive already holds v001..v015 from an older
    # fixture, three proposals OVERWRITE three files and the delta is 0.
    # That is an artefact of the copied tree, not the behaviour under
    # test; the behaviour is "one attempt leaves one file".
    for stale in skills.versions_dir().glob("v*.md"):
        stale.unlink()
    before = len(list(skills.versions_dir().glob("v*.md")))

    for n in range(1, 4):
        version = start + n
        turns = ([_big_skill(version, tokens=over), _package(version)]
                 if n % 2 else [_skill(version)])
        result = await _run(FakeWorkspace(turns))
        assert result.accepted is not None, result.rejection
        assert result.version == version, (
            f"attempt {n} landed on v{result.version}, expected v{version}")

    after = len(list(skills.versions_dir().glob("v*.md")))
    assert after - before == 3, (
        f"3 attempts wrote {after - before} version file(s); one attempt "
        f"must leave exactly one")

    # AND THE RELOCATION ACTUALLY LANDED. Without this the test passes for
    # the wrong reason: if the disclosure pass is REJECTED (which is what
    # happens when it is not allowed to replace, because it then stamps the
    # wrong version) the authored body stands, the count is still one per
    # attempt, and nothing looks wrong. Attempt 3 relocated, so the live
    # package must carry the reference tier.
    live = skills.current()
    assert "references/detail.md" in live.files, (
        "the relocation pass did not land -- one version per attempt is "
        "being achieved by the disclosure pass failing, not by replacing")


@pytest.mark.asyncio
async def test_a_failed_relocation_leaves_the_authored_version_live(sandbox) -> None:
    """A failed optimisation must never cost a good skill.

    The authored version is already saved and already valid when the pass
    runs; if the reply is unusable the accepted version simply stands.
    """
    start = skills.current().version
    over = skills.AIP_BODY_TARGET_TOKENS + 2000
    ws = FakeWorkspace([_big_skill(start + 1, tokens=over),
                        "I could not shorten it without losing detail."])
    result = await _run(ws)
    assert result.accepted is not None
    assert result.version == start + 1, "the authored version was lost"
    assert skills.current().version == start + 1
    assert "kept the body as authored" in result.note


@pytest.mark.asyncio
async def test_a_relocation_that_grows_the_body_is_refused(sandbox) -> None:
    """Not a shrink means it is a rewrite of an already-accepted
    procedure, which is the churn this pass exists to avoid."""
    start = skills.current().version
    over = skills.AIP_BODY_TARGET_TOKENS + 2000
    grown = (f"=== FILE: SKILL.md ===\n{_big_skill(start + 2, tokens=over + 500)}\n"
             "=== FILE: references/detail.md ===\nx\n")
    ws = FakeWorkspace([_big_skill(start + 1, tokens=over), grown])
    result = await _run(ws)
    assert result.version == start + 1
    assert "kept the body as authored" in result.note


def test_frontier_calls_are_retained_on_the_platform() -> None:
    """The operator must be able to read the actual prompt and reply.

    Chat Completions are not kept for the dashboard's Logs view unless
    `store` is set. The symptom was that the web tool's gpt-4o-mini calls
    appeared there and the distiller's gpt-5.6-sol calls did not, on the
    same project key -- the web server uses the Responses API and this
    uses Chat Completions. The calls were real and billing throughout;
    only that view was blind, which is indistinguishable from the author
    never having run.
    """
    import inspect

    from orchestrator.writers import ExternalWriter

    src = inspect.getsource(ExternalWriter._call)
    assert '"store": True' in src, (
        "frontier authoring calls are invisible on the platform again")
    assert '"metadata"' in src, (
        "without metadata a distillation cannot be found among them")
