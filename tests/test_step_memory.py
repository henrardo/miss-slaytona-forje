"""The per-step memory hook: Vibe's `post_tool` -> the agents' own graph writes.

This is the piece that makes "these agents share their reasoning" a statement
about the agents. Before it, every ReasoningStep in the graph was written by
`_replay_transcript_into_memory` -- the orchestrator reading Vibe's transcript
after the fact -- and every retrieval was a per-attempt prompt splice keyed on
the *previous* attempt's error. The agents themselves made zero write calls and
one read call, which errored.

What is asserted here is the contract on both sides, because both sides are
somebody else's and getting either wrong is silent:

* Vibe's side: "exit 0 + JSON on stdout", with the payload under
  `hook_specific_output.additional_context` (vibe/core/hooks/models.py). A hook
  that returns the right text under the wrong key does nothing at all, and
  looks exactly like a model that ignored its memory.
* the package's side: `search_steps` returns ReasoningStepWithContext, whose
  `parent_success` is how "did this work" reaches the model -- our own
  inference is not involved.

The sidecar is exercised directly with a fake ScopedMemory, and the hook client
against a real socket. Neither needs Neo4j: what can break here is the wiring,
and the wiring is what is tested.
"""
from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orchestrator.step_memory import StepMemoryService, _query_text
from orchestrator.vibe_agent import STEP_HOOK_SCRIPT


class _FakeStep:
    def __init__(self) -> None:
        self.id = "step-1"
        self.trace_id = "trace-1"


class _FakeMem:
    """Records what the sidecar asked of the package, and returns canned hits."""

    def __init__(self, hits: list | None = None) -> None:
        self.steps: list[dict] = []
        self.tool_calls: list[dict] = []
        self.searches: list[str] = []
        self._hits = hits or []

    async def add_step(self, trace_id, **kw):
        self.steps.append({"trace_id": trace_id, **kw})
        return _FakeStep()

    async def record_tool_call(self, step_id, *, tool_name, arguments):
        self.tool_calls.append(
            {"step_id": step_id, "tool_name": tool_name, "arguments": arguments}
        )

    async def search_steps(self, query, *, limit, success_only, threshold):
        self.searches.append(query)
        return self._hits


def _hit(*, action, thought, observation, success, trace_id="other-trace"):
    step = SimpleNamespace(
        action=action, thought=thought, observation=observation, trace_id=trace_id
    )
    return SimpleNamespace(
        step=step, similarity=0.9, parent_task="t", parent_outcome="o",
        parent_success=success,
    )


# --- the query is the CURRENT failure, not the task ------------------------


def test_query_prefers_the_error_over_the_output() -> None:
    """The discriminating query is what just went wrong.

    The task string is byte-identical for every agent in every run, so
    embedding it retrieves nothing; the error is what separates one attempt
    from another. This is the query an agent could not construct for itself,
    and the reason per-step retrieval is worth having at all."""
    assert _query_text("AttributeError: boom", "lots of stdout") == "AttributeError: boom"


def test_query_falls_back_to_the_tail_of_the_output() -> None:
    """pytest puts its summary last, so the tail is the informative end."""
    q = _query_text(None, "line1\nline2\n=== 3 failed, 30 passed ===")
    assert "3 failed, 30 passed" in q


def test_query_is_empty_when_nothing_happened() -> None:
    assert _query_text(None, "") == ""
    assert _query_text(None, None) == ""


# --- writes are the agent's own, at the step ------------------------------


def test_evidence_tool_writes_a_step_and_its_tool_call() -> None:
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    asyncio.run(svc.handle({
        "agent": "warm-0",
        "tool_name": "bash",
        "tool_input": {"command": "pytest -q"},
        "tool_output_text": "1 failed, 32 passed",
        "tool_error": None,
    }))

    assert len(mem.steps) == 1, "the agent's step was not recorded"
    step = mem.steps[0]
    assert step["action"] == "bash"
    assert "pytest -q" in step["thought"]
    assert "32 passed" in step["observation"]
    # Batched at complete_trace(generate_step_embeddings=True) -- inline
    # embedding would put an OpenAI round-trip in the agent's tool path on
    # every single tool call.
    assert step["generate_embedding"] is False
    assert mem.tool_calls == [
        {"step_id": "step-1", "tool_name": "bash", "arguments": {"command": "pytest -q"}}
    ]


def test_aliased_tool_names_still_match() -> None:
    """Vibe publishes MCP tools as f"{alias}_{tool}", and the same suffix
    matching that bit the memory_calls counter applies here."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "some-server_bash",
        "tool_input": {}, "tool_output_text": "out", "tool_error": None,
    }))
    assert len(mem.steps) == 1


def test_an_unregistered_agent_is_ignored() -> None:
    """Cold agents have no hooks.toml, but a stray request must not write
    into the warm scope."""
    svc = StepMemoryService()
    assert asyncio.run(svc.handle({"agent": "cold-0", "tool_name": "bash"})) == {}


# --- reads come back as the step's own properties, uninterpreted -----------


def test_retrieved_steps_come_back_as_properties_not_as_a_verdict() -> None:
    svc = StepMemoryService()
    mem = _FakeMem(hits=[
        _hit(action="edit", thought='{"old_string": "EmailStr.validate"}',
             observation="AttributeError", success=False),
        _hit(action="edit", thought='{"new_string": "validate_email"}',
             observation="ok", success=True),
    ])
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    out = asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "bash",
        "tool_input": {}, "tool_output_text": "",
        "tool_error": "AttributeError: type object 'EmailStr' has no attribute 'validate'",
    }))

    ctx = out["additional_context"]
    # Queried on the error the agent is looking at right now.
    assert mem.searches == [
        "AttributeError: type object 'EmailStr' has no attribute 'validate'"
    ]
    # `success` is reported as the property it is, for both steps.
    assert "success: False" in ctx
    assert "success: True" in ctx
    assert "validate_email" in ctx
    assert svc.context_returned == 1
    # And the harness does not tell the model what to conclude from it.
    for editorial in ("WORKED", "did NOT work", "Another agent", "outcome unknown"):
        assert editorial not in ctx


def test_the_agent_never_reads_back_its_own_steps() -> None:
    """Without this the hook hands the agent its own just-written output as
    though it were another agent's experience."""
    svc = StepMemoryService()
    mem = _FakeMem(hits=[
        _hit(action="edit", thought="mine", observation="x", success=None,
             trace_id="trace-1"),
    ])
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    out = asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "bash", "tool_input": {},
        "tool_output_text": "", "tool_error": "boom",
    }))
    assert out == {}


def test_nothing_is_injected_when_the_graph_has_nothing() -> None:
    svc = StepMemoryService()
    mem = _FakeMem(hits=[])
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    out = asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "bash", "tool_input": {},
        "tool_output_text": "", "tool_error": "boom",
    }))
    assert out == {}


# --- failing open is not optional ----------------------------------------


def test_a_broken_graph_does_not_break_the_agents_tool_call() -> None:
    """This code runs inside the agent's tool-call path. If the graph is
    unreachable the correct outcome is that the edit still lands and the agent
    simply gets no memory this turn -- never that its tool appears to fail."""
    class _Exploding(_FakeMem):
        async def add_step(self, *a, **kw):
            raise RuntimeError("neo4j is down")

        async def search_steps(self, *a, **kw):
            raise RuntimeError("neo4j is down")

    svc = StepMemoryService()
    svc.register("warm-0", _Exploding())
    svc.set_trace("warm-0", "trace-1")
    out = asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "bash", "tool_input": {},
        "tool_output_text": "", "tool_error": "boom",
    }))
    assert out == {}
    assert svc.errors >= 1


# --- the hook client honours Vibe's contract -----------------------------


def test_hook_client_returns_vibes_exact_response_shape() -> None:
    """`hook_specific_output.additional_context` is the only key Vibe reads
    for a post_tool hook. Right text under the wrong key is indistinguishable
    from a model that ignored its memory."""
    async def serve_once() -> int:
        async def handler(reader, writer):
            await reader.readline()
            writer.write(json.dumps({"additional_context": "PRIOR STEP"}).encode() + b"\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]

        async def run_client():
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(STEP_HOOK_SCRIPT), str(port), "warm-0",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            payload = json.dumps({
                "hook_event_name": "post_tool", "session_id": "s",
                "transcript_path": "/x", "cwd": "/y",
                "tool_name": "bash", "tool_call_id": "c",
                "tool_input": {"command": "pytest"}, "tool_status": "ok",
                "tool_output": None, "tool_output_text": "1 failed",
                "tool_error": None, "duration_ms": 1.0,
            }).encode()
            out, err = await proc.communicate(payload)
            assert proc.returncode == 0, err.decode()
            return json.loads(out.decode())

        async with server:
            reply = await run_client()
        assert reply == {"hook_specific_output": {"additional_context": "PRIOR STEP"}}
        return 0

    assert asyncio.run(serve_once()) == 0


def test_hook_client_fails_open_when_the_sidecar_is_absent() -> None:
    """Nothing listening: the hook must still print valid JSON and exit 0, or
    every tool call the agent makes reports a hook failure."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]  # bound then closed -> refused

    result = subprocess.run(
        [sys.executable, str(STEP_HOOK_SCRIPT), str(dead_port), "warm-0"],
        input=json.dumps({"tool_name": "bash", "tool_output_text": "x"}),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}


def test_hook_client_imports_nothing_heavy() -> None:
    """It starts once per tool call. `from neo4j_agent_memory import
    MemoryClient` costs ~1.5s in a fresh process before its embedder loads,
    and Vibe's executor passes no env= -- so the client must be stdlib only
    and must not need credentials it deliberately does not have.

    Asserted on the parsed import statements, not on the text: the module's
    own docstring names the packages it avoids in order to explain why, and
    matching prose fails on the explanation."""
    import ast

    tree = ast.parse(Path(STEP_HOOK_SCRIPT).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported == {"json", "socket", "sys"}, (
        f"hook client must be stdlib-only; it imports {sorted(imported)}"
    )


# --- the step's thought must be the agent's REASONING --------------------


def _write_transcript(tmp_path: Path, *, tool_call_id: str, reasoning: str) -> Path:
    """A transcript shaped like Vibe's: the assistant message that issued the
    tool call carries `reasoning_content` beside `tool_calls`."""
    p = tmp_path / "messages.jsonl"
    p.write_text(
        json.dumps({"role": "user", "content": "migrate it"}) + "\n"
        + json.dumps({
            "role": "assistant",
            "content": "",
            "reasoning_content": reasoning,
            "tool_calls": [{
                "id": tool_call_id,
                "function": {"name": "edit", "arguments": "{}"},
            }],
        }) + "\n"
        + json.dumps({"role": "tool", "content": "done"}) + "\n"
    )
    return p


def test_the_step_records_the_agents_reasoning_from_the_stream() -> None:
    """`search_steps` embeds thought+action, so the thought has to be the
    agent's reasoning, not its tool input.

    The first attempt at this read `messages.jsonl` and joined on
    tool_call_id. It passed its unit test -- which handed it a transcript that
    already contained the message -- and failed 100% of the time live: Vibe
    flushes the transcript once per TURN, after the tool loop
    (agent_loop/_loop.py:2110), so at post_tool time the message that issued
    the call is still only in Vibe's memory. Verified against the graph: every
    step in that run recorded tool-input JSON.

    The reasoning arrives instead on Vibe's `--output streaming` channel, as
    its own `type="reasoning"` entry, pushed in by the orchestrator."""
    reasoning = "EmailStr.validate is gone in v2, so email_validator is the right package"
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    svc.set_pending_reasoning("warm-0", reasoning)

    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "edit",
        "tool_input": {"old_string": "EmailStr.validate"},
        "tool_output_text": "updated", "tool_error": None,
    }))
    assert mem.steps[0]["thought"] == reasoning


def test_reasoning_falls_back_to_the_tool_input_when_the_turn_had_none() -> None:
    """A turn can carry a tool call and no reasoning. The input is worse than
    reasoning and better than a null."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "edit",
        "tool_input": {"old_string": "xyz"},
        "tool_output_text": "updated", "tool_error": None,
    }))
    assert "xyz" in mem.steps[0]["thought"]


def test_several_calls_in_one_turn_share_that_turns_reasoning() -> None:
    """Reasoning entries complete before the tool calls they justify, so the
    latest one is the reasoning for the next steps -- and calls issued in the
    same turn were decided in the same piece of reasoning."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    svc.set_pending_reasoning("warm-0", "one plan, two edits", turn_id="t1")
    for old in ("a", "b"):
        svc.note_turn("warm-0", "t1")  # the effect entries for those calls
        asyncio.run(svc.handle({
            "agent": "warm-0", "tool_name": "edit",
            "tool_input": {"old_string": old},
            "tool_output_text": "ok", "tool_error": None,
        }))
    assert [s["thought"] for s in mem.steps] == ["one plan, two edits"] * 2


def test_a_new_turn_does_not_inherit_the_previous_turns_reasoning() -> None:
    """The breakage this run measured. `_pending_reasoning` was only ever
    replaced by the NEXT reasoning entry, so a turn that emitted none of its
    own silently reused the last one -- 52% of 141 steps shared a thought with
    a neighbour, and one thought was attached to 20 consecutive calls.

    turn_id is on Vibe's shared entry base, so any entry from a later turn is
    proof the earlier turn is over."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    svc.set_pending_reasoning("warm-0", "turn one's plan", turn_id="t1")
    svc.note_turn("warm-0", "t1")
    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "edit",
        "tool_input": {"old_string": "first"},
        "tool_output_text": "ok", "tool_error": None,
    }))

    # Turn two: an entry arrives for t2 and it emits no reasoning of its own.
    svc.note_turn("warm-0", "t2")
    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "edit",
        "tool_input": {"old_string": "second"},
        "tool_output_text": "ok", "tool_error": None,
    }))

    assert mem.steps[0]["thought"] == "turn one's plan"
    assert "turn one's plan" not in mem.steps[1]["thought"]
    assert "second" in mem.steps[1]["thought"], "should fall back to tool input"


def test_an_entry_with_no_turn_id_does_not_discard_the_reasoning() -> None:
    """turn_id is optional on Vibe's entry base. Absent means "Vibe did not
    say", which is not evidence that the turn changed -- treating it as such
    would throw away good reasoning for free."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    svc.set_pending_reasoning("warm-0", "still valid", turn_id="t1")
    svc.note_turn("warm-0", None)
    asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "edit",
        "tool_input": {"old_string": "x"},
        "tool_output_text": "ok", "tool_error": None,
    }))
    assert mem.steps[0]["thought"] == "still valid"


# --- nothing the replay captured may be silently dropped ----------------


def test_exploration_steps_are_recorded_whole_and_do_not_search() -> None:
    """A step is recorded for EVERY tool call, with its FULL observation.

    The observation used to be cut to 200 characters for grep/read_file
    and 2,000 otherwise. Both were mine. The evidence I cited -- 78 of 229
    :Entity nodes named '100->', '171->' -- is about storing tool results
    as :Message nodes, which go through entity extraction; `add_step` has
    no extraction path. And `add_step` embeds
    "Thought: ... Action: ... Observation: ..." (reasoning.py:546), so
    cutting the observation degraded the retrieval the cap claimed to
    protect.

    What `_EVIDENCE_TOOLS` still decides -- and all it decides -- is
    whether the step's output becomes a retrieval QUERY."""
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    whole_file = "x = 1\n" * 5000
    out = asyncio.run(svc.handle({
        "agent": "warm-0", "tool_name": "read_file",
        "tool_input": {"file_path": "fastapi_mail/schemas.py"},
        "tool_output_text": whole_file, "tool_error": None,
    }))

    assert len(mem.steps) == 1, "the exploration step was dropped again"
    assert mem.steps[0]["action"] == "read_file"
    # The file is stored WHOLE. No cap.
    assert mem.steps[0]["observation"] == whole_file
    # ...and exploration does not trigger a retrieval: searching on the
    # contents of a file the agent just opened returns whatever else mentions
    # that file, which is not what it needs.
    assert mem.searches == []
    assert out == {}


def test_turns_that_called_no_tool_are_recorded(tmp_path: Path) -> None:
    """post_tool cannot see them, and they are 15% of the reasoning -- plus
    they are exactly where this model declares itself finished while the suite
    still fails."""
    t = tmp_path / "messages.jsonl"
    t.write_text(
        json.dumps({"role": "assistant", "reasoning_content": "r",
                    "tool_calls": [{"id": "1", "function": {"name": "edit"}}]}) + "\n"
        + json.dumps({"role": "assistant",
                      "content": "The migration is now complete."}) + "\n"
    )
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    asyncio.run(svc.handle_agent_end({
        "agent": "warm-0", "hook_event_name": "post_agent",
        "transcript_path": str(t),
    }))

    assert len(mem.steps) == 1
    assert "migration is now complete" in mem.steps[0]["thought"]
    assert "without calling a tool" in mem.steps[0]["action"]
    assert svc.text_turns_written == 1


def test_a_text_turn_is_not_stored_twice(tmp_path: Path) -> None:
    """post_agent fires per Vibe invocation and reads the transcript tail,
    which spans earlier attempts of a --continue'd session. Without
    de-duplication the same "I'm done" turn is stored once per attempt for the
    rest of the run."""
    t = tmp_path / "messages.jsonl"
    t.write_text(json.dumps({"role": "assistant", "content": "done"}) + "\n")
    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")

    for _ in range(3):
        asyncio.run(svc.handle_agent_end({
            "agent": "warm-0", "hook_event_name": "post_agent",
            "transcript_path": str(t),
        }))
    assert len(mem.steps) == 1


def test_post_agent_is_routed_by_vibes_own_event_name() -> None:
    """The client forwards `hook_event_name` so the sidecar does not have to
    infer which hook fired from whichever fields happen to be present."""
    src = Path(STEP_HOOK_SCRIPT).read_text()
    assert '"hook_event_name"' in src
    from orchestrator.step_memory import StepMemoryService as S
    assert hasattr(S, "handle_agent_end")


# --- the wire, not the model definition -----------------------------------


def test_the_consumer_reads_the_key_vibe_actually_emits() -> None:
    """Streamed entries are camelCase, so the consumer must read `turnId`.

    Vibe declares the field `turn_id` on `_PublicHistoryEntryBase` and
    serialises it with `model_dump(mode="json", by_alias=True)`, which emits
    `turnId`. The consumer was written against the declaration and read
    `turn_id`, so `.get()` returned None on every entry, `note_turn()` returned
    immediately, and the whole turn-boundary mechanism did nothing -- through
    two live runs, with every unit test green, because the tests handed
    `note_turn` synthetic values directly and never went through the consumer.

    Captured off a real session on the swarm host:

        message    turnId=b7e201f8-1f3b-41bd-886e-af78a4866d8c
        reasoning  turnId=b7e201f8-1f3b-41bd-886e-af78a4866d8c

    So this test drives the real `_entry_consumer` with wire-shaped entries and
    asserts the reasoning is actually attributed to its turn."""
    from orchestrator.vibe_agent import _entry_consumer

    svc = StepMemoryService()
    mem = _FakeMem()
    svc.register("warm-0", mem)
    svc.set_trace("warm-0", "trace-1")
    consume = _entry_consumer(mem, "warm-0", svc, "warm-0")

    # Turn 1 reasons, then calls a tool.
    asyncio.run(consume({"type": "reasoning", "text": "turn one's plan",
                         "turnId": "t-1", "generationStatus": "completed"}))
    asyncio.run(svc.handle({"agent": "warm-0", "tool_name": "edit",
                            "tool_input": {"old_string": "first"},
                            "tool_output_text": "ok"}))
    # Turn 2 emits an entry but no reasoning of its own.
    asyncio.run(consume({"type": "effect", "title": "edit", "turnId": "t-2",
                         "generationStatus": "completed"}))
    asyncio.run(svc.handle({"agent": "warm-0", "tool_name": "edit",
                            "tool_input": {"old_string": "second"},
                            "tool_output_text": "ok"}))

    assert mem.steps[0]["thought"] == "turn one's plan"
    assert "turn one's plan" not in mem.steps[1]["thought"], (
        "turn 2 inherited turn 1's reasoning -- the turnId key is wrong again"
    )
