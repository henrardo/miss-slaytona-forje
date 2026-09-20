"""Ingestion must store WHY, not what was typed.

The failure this replaces: on the remote path every ReasoningStep.thought
held tool-argument JSON --

    thought: '{"pattern": "pydantic", "path": "/home/agent-warm-0/repo"}'

-- because the post_tool hook fires before Vibe flushes its transcript, so
the only thing available at write time was the tool's own arguments.
`search_steps` embeds thought+action, so the graph was searchable by what
was typed rather than by why, and a graph like that is indistinguishable
from a working one until you read the nodes.

`tests/data-vibe-stream.jsonl` is a REAL stream from mistral-vibe 2.25.4,
captured by running the actual binary against the scripted fake server --
not a hand-written fixture of what the format was assumed to be. Two
earlier bugs in this project came from guessing a format (`tools` instead
of `tools_available`; `turn_id` instead of `turnId`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator import ingest as ing

STREAM = Path(__file__).parent / "data-vibe-stream.jsonl"


def real_stream() -> list[dict]:
    return [json.loads(line) for line in STREAM.read_text().splitlines()
            if line.strip().startswith("{")]


def test_the_fixture_is_a_real_vibe_stream() -> None:
    """If this file is ever replaced by something hand-written, the rest of
    these tests stop being evidence about Vibe."""
    entries = real_stream()
    kinds = {e.get("type") for e in entries}
    assert {"message", "reasoning", "effect"} <= kinds
    for entry in entries:
        # Vibe serialises by alias. `turn_id` here would mean the fixture
        # was written by hand, and the note_turn path already broke once on
        # exactly this.
        assert "turn_id" not in entry
        assert entry.get("turnId")


def test_every_step_carries_the_models_own_reasoning() -> None:
    result = ing.parse_stream(real_stream())
    assert result.steps, "no steps parsed from a real stream"
    assert result.steps_with_reasoning == len(result.steps)
    for step in result.steps:
        assert step.thought.strip()
        # The specific regression: the thought must not be the action.
        assert step.thought != step.action
        assert not step.thought.lstrip().startswith("{")


def test_thought_pairs_with_the_action_it_justifies() -> None:
    """Vibe emits reason -> speak -> act within a turn, so the reasoning
    immediately before a tool call is the reasoning FOR it."""
    steps = ing.parse_stream(real_stream()).steps
    assert "see what is here" in steps[0].thought
    assert steps[0].action.startswith("bash(")
    assert "read it before editing" in steps[1].thought
    assert steps[1].action.startswith("read_file(")


def test_a_turn_with_no_tool_call_is_still_a_step() -> None:
    """15% of this model's turns call no tool, and they include every turn
    where it decides it has finished -- the claim the grader contradicts."""
    steps = ing.parse_stream(real_stream()).steps
    final = steps[-1]
    assert final.action == "(no tool call)"
    assert "migration is complete" in final.thought


def test_failed_tool_calls_are_recorded_as_failures() -> None:
    """An attempt that spent six turns fighting `edit` is exactly what a
    later distillation should find. Recording only successes would make the
    graph a highlight reel."""
    result = ing.parse_stream(real_stream())
    failed = [s for s in result.steps if s.failed]
    assert len(failed) == 1
    assert result.failed_tool_calls == 1
    assert "Invalid arguments" in failed[0].observation


def test_the_skill_load_is_extracted_and_never_becomes_a_step() -> None:
    """Vibe reports the skill load as an ordinary tool effect. It is not the
    agent's reasoning, but it IS the proof the skill reached the model."""
    result = ing.parse_stream(real_stream())
    assert result.skill_content is not None
    assert '<skill_content name="pydantic-v2-migration">' in result.skill_content
    assert not any(s.tool_name == "skill" for s in result.steps)


def test_observations_are_stored_whole() -> None:
    """A pytest run can be 40,000 characters, and all of it is stored.

    There was a head-and-tail truncation at MAX_OBSERVATION_CHARS=2000.
    It was mine, the evidence for it came from a different code path
    (see tests/test_step_memory.py), and the package imposes no such
    limit -- the only real bound is the embedding model's own input size,
    which belongs to neo4j-agent-memory and not to this harness."""
    entry = {
        "type": "effect", "turnId": "t", "title": "bash",
        "detail": {"toolName": "bash", "input": {"command": "pytest"}},
        "state": {"status": "completed",
                  "outputText": "FIRST" + ("x" * 50_000) + "LAST"},
    }
    step = ing.parse_stream([{"type": "reasoning", "turnId": "t", "text": "run it"},
                             entry]).steps[0]
    assert len(step.observation) == len("FIRST") + 50_000 + len("LAST")
    assert step.observation.startswith("FIRST")
    assert step.observation.endswith("LAST")
    assert "omitted" not in step.observation
    assert ing.MAX_OBSERVATION_CHARS is None and ing.MAX_THOUGHT_CHARS is None


def test_an_empty_stream_yields_nothing_rather_than_raising() -> None:
    """A Vibe that died before its first turn must not take the attempt's
    verdict down with it."""
    result = ing.parse_stream([])
    assert result.steps == []
    assert result.skill_content is None


class FakeMem:
    """Records what would be written, and can be told to fail."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.steps: list[dict] = []
        self.tool_calls: list[dict] = []
        self.fail_on = fail_on

    async def add_step(self, trace_id, *, thought, action, observation=None):
        if self.fail_on == "add_step":
            raise RuntimeError("Aura is down")
        self.steps.append({"trace": trace_id, "thought": thought,
                           "action": action, "observation": observation})
        return type("S", (), {"id": f"step-{len(self.steps)}"})()

    async def record_tool_call(self, step_id, *, tool_name, arguments,
                               result=None, status=None):
        if self.fail_on == "record_tool_call":
            raise RuntimeError("Aura is down")
        self.tool_calls.append({"step": step_id, "tool": tool_name,
                                "args": arguments, "status": status})


@pytest.mark.asyncio
async def test_ingest_writes_every_step_and_its_tool_call() -> None:
    mem = FakeMem()
    result = await ing.ingest(mem, "trace-1", real_stream())
    assert len(mem.steps) == len(result.steps) == 3
    assert all(s["trace"] == "trace-1" for s in mem.steps)
    # Two tool calls; the no-tool turn records a step but no call.
    assert len(mem.tool_calls) == 2
    assert [c["tool"] for c in mem.tool_calls] == ["bash", "read_file"]


@pytest.mark.asyncio
async def test_a_failing_graph_never_loses_the_attempt() -> None:
    """Ingestion runs after the attempt is graded and the trace closed.
    Raising here would throw away a verdict to save a step."""
    result = await ing.ingest(FakeMem(fail_on="add_step"), "t", real_stream())
    assert len(result.steps) == 3, "parsing should still report what it saw"
    result = await ing.ingest(FakeMem(fail_on="record_tool_call"), "t",
                              real_stream())
    assert len(result.steps) == 3


@pytest.mark.asyncio
async def test_tool_call_status_distinguishes_the_failure() -> None:
    from neo4j_agent_memory.memory.reasoning import ToolCallStatus
    mem = FakeMem()
    await ing.ingest(mem, "t", real_stream())
    by_tool = {c["tool"]: c["status"] for c in mem.tool_calls}
    assert by_tool["bash"] == ToolCallStatus.SUCCESS
    assert by_tool["read_file"] == ToolCallStatus.ERROR


def test_a_timed_out_attempt_keeps_the_stream_it_already_produced() -> None:
    """The stream is drained as it arrives, not collected at the end.

    `proc.communicate()` buffers inside the coroutine, so cancelling it on
    timeout threw away everything Vibe had streamed. Run 10 attempt 3 is
    the measured case: 59 turns, the suite taken to 33/33 -- the only
    passing attempt in the run -- and ZERO steps ingested.

    The transcript is no substitute. messages.jsonl carries role, content
    and tool_calls and no reasoning field at all, so rebuilding steps from
    it would write actions with empty thoughts, which another test here
    already forbids.
    """
    import inspect

    from swarm.agent_workspace import AgentWorkspace

    src = inspect.getsource(AgentWorkspace.invoke_vibe_async)
    # The call, not the mention: the fix's own comment names
    # communicate() to explain why it is gone.
    assert "wait_for(proc.communicate()" not in src, (
        "communicate() discards buffered output when cancelled")
    assert "stdout=partial" in src
    assert "chunks" in src


def test_a_stream_cut_mid_line_still_yields_its_finished_turns() -> None:
    """A killed process leaves a partial last line. It must cost that one
    turn, not the whole attempt."""
    from orchestrator import ingest

    whole = (
        '{"type":"reasoning","turnId":"t1","text":"Check the imports first."}\n'
        '{"type":"effect","turnId":"t1","id":"abcdefghi","title":"bash",'
        '"detail":{"toolName":"bash","input":{"command":"grep -rn pydantic ."}},'
        '"state":{"status":"success","outputText":"models.py:1: import pydantic"}}\n'
        '{"type":"reasoning","turnId":"t1","text":"Now migrate BaseSettings."}\n'
        '{"type":"effect","turnId":"t1","id":"jklmnopqr","title":"edit",'
        '"detail":{"toolName":"edit","input":{"file_path":"/repo/settings.py"}},'
        '"state":{"status":"success","outputText":"edited"}}\n'
    )
    full = ingest.parse_stream(ingest_entries(whole))
    assert len(full.steps) == 2

    truncated = whole[:-40]           # killed part-way through the last line
    cut = ingest.parse_stream(ingest_entries(truncated))
    # The finished turn is intact, reasoning and action both.
    assert cut.steps[0].thought == "Check the imports first."
    assert "grep -rn pydantic" in cut.steps[0].action
    assert "models.py:1: import pydantic" in cut.steps[0].observation
    # The turn whose tool call was cut off survives as reasoning with no
    # action, which is the honest record: the model thought that and the
    # clock stopped it. What must NOT happen is the unparseable fragment
    # taking the finished turn down with it.
    assert len(cut.steps) == 2
    assert cut.steps[1].action == "(no tool call)"
    assert cut.steps[1].thought == "Now migrate BaseSettings."


def ingest_entries(stdout: str) -> list[dict]:
    """The same tolerant per-line parse the workspace does."""
    import json
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
