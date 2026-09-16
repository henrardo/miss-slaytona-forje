"""Per-step memory, driven by Vibe's own `post_tool` hook.

This is what makes "these agents share their reasoning" a statement about the
AGENTS rather than about the orchestrator. It replaces two hand-rolled pieces:

  * `_replay_transcript_into_memory` -- which read Vibe's transcript AFTER an
    attempt ended and wrote the agent's steps on its behalf. Same information,
    minutes late, and written by us.
  * the per-attempt `get_context()` splice -- one retrieval per attempt, keyed
    on the PREVIOUS attempt's failure, pasted into the prompt. By turn five the
    agent was reading an answer to a question it had stopped asking.

Both existed because we do not own Vibe's agent loop. We do not have to: Vibe
ships `post_tool` hooks, configured in `$VIBE_HOME/hooks.toml`, and a hook may
return `hook_specific_output.additional_context`, which is appended to the
tool output the model sees. So the loop is:

    agent calls a tool
        -> Vibe invokes the hook with tool_name/tool_input/tool_output/tool_error
        -> this sidecar records that step in the graph  (add_step + record_tool_call)
        -> and searches the graph for what other agents hit here (search_steps)
        -> returns it as additional_context
    agent's next turn sees it

Read and write, at the step, keyed on what actually just happened. Nothing here
invents a mechanism: `post_tool` is Vibe's, `add_step`/`record_tool_call`/
`search_steps` are neo4j-agent-memory's, and `search_steps`' own docstring
calls step granularity "the right cut for case-based imitation prompting".

WHY A SIDECAR, AND NOT A SCRIPT IN hooks.toml
---------------------------------------------
Two hard constraints, both measured:

  * `from neo4j_agent_memory import MemoryClient` costs ~1.5s in a fresh
    process, before the embedder loads. A hook runs once PER TOOL CALL, so a
    self-contained script would add that to every single tool the agent uses.
  * Vibe's hook executor passes no `env=` (core/hooks/executor.py), so a hook
    inherits the AGENT's environment -- which has NEO4J_URI/NEO4J_PASSWORD
    stripped on purpose (_STRIPPED_ENV). Credentials must not be put back in
    an agent's environment just to let a hook connect.

So the hook is `harness/memory_step_hook.py`: stdlib only, no imports from
this project, one loopback socket round-trip. The client needs a port, not
secrets, and the client process starts in ~20ms. This sidecar holds the warm
MemoryClient with its embedder already loaded.

WARM ONLY. Cold agents get no hooks.toml at all, so no hook process, no
latency, no graph -- the same "not a gated path, no path" property the rest of
the arm separation has.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from orchestrator.memory import ScopedMemory

# Cap on anything handed to the graph or to an embedder. A `read_file`
# observation is an entire source file and a `bash` observation can be a full
# pytest log; embedding either is slow, and storing either is what previously
# filled a third of the graph with line-number "entities".
_OBS_CAP = 2000
_QUERY_CAP = 600
# Reasoning runs long on hybrid reasoning models -- 2,913 characters for a
# single turn, measured. Capped because it is embedded and because it is
# rendered back into another agent's context window, which is 32k.
_THOUGHT_CAP = 1500

# Tools whose RESULT is evidence -- something failed, passed, or changed.
# `read_file`/`grep` are exploration: their output is the file the agent asked
# for, which says nothing about whether an approach worked and is the most
# expensive thing to embed or to render back into a 32k window.
#
# This now governs the OBSERVATION ONLY, never whether the step is recorded.
# It used to skip the whole step for a non-evidence tool, and that was a
# straight conflation of "expensive observation" with "worthless step".
# Measured against the transcripts of the run it shipped in: 12 of 37 assistant
# turns issued only non-evidence calls, and dropping those steps threw away
# 23,930 characters of the agent's reasoning -- 36% of everything it thought.
# The reasoning behind "let me read schemas.py, the traceback points there" is
# the agent's reasoning whether or not the file that came back is worth
# storing.
_EVIDENCE_TOOLS = ("bash", "edit", "write_file", "git_bash", "experimental_bash")
# What an exploration tool's observation is reduced to. Enough to say what the
# agent looked at and what happened, not the file itself.
_EXPLORATION_OBS_CAP = 200

# Below this cosine similarity a "related" step is noise. The package's own
# default for search_steps.
_THRESHOLD = 0.7


# How much of the tail of a transcript to read when looking for the reasoning
# behind one tool call. The assistant message that issued it is normally the
# last one in the file, so this is generous by a wide margin; it exists only so
# a long session cannot turn into a multi-megabyte read inside the agent's
# tool-call path.
_TRANSCRIPT_TAIL_BYTES = 512 * 1024


def _cap(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def _query_text(tool_error: str | None, tool_output_text: str | None) -> str:
    """What this step is ABOUT, as search text.

    The error if there is one, otherwise the tail of the output -- pytest puts
    its summary last, so the tail is the informative end. This is the query the
    agent could never construct for itself: the task string is identical for
    every agent in every run (see _task_prompt) and retrieves nothing, while
    the current failure is what distinguishes one attempt from another.
    """
    if tool_error:
        return _cap(tool_error, _QUERY_CAP)
    tail = (tool_output_text or "").strip()
    return _cap(tail[-_QUERY_CAP:], _QUERY_CAP)


def _text_only_turns(transcript_path: str | None) -> list[str]:
    """Assistant turns in the transcript tail that called no tool.

    Their text is `content`, or `reasoning_content` when the model emitted
    only reasoning -- which it does often: 443 of run 23's 504 assistant
    messages were reasoning with no content at all.
    """
    if not transcript_path:
        return []
    try:
        path = Path(transcript_path)
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _TRANSCRIPT_TAIL_BYTES:
                fh.seek(size - _TRANSCRIPT_TAIL_BYTES)
                fh.readline()
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []

    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("role") != "assistant" or msg.get("tool_calls"):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        reasoning = msg.get("reasoning_content")
        if isinstance(reasoning, list):
            reasoning = " ".join(str(c) for c in reasoning)
        text = (str(content or "").strip() or str(reasoning or "").strip())
        if text:
            out.append(text)
    return out


def _render(hits: list) -> str | None:
    """Hand the retrieved steps over with their properties. Nothing else.

    `search_steps` returns ReasoningStepWithContext: thought, action,
    observation, and `parent_success`. `success` is a property of the step's
    trace, so it is reported as one -- not translated into "this WORKED" /
    "this did NOT work", which is this harness telling the model what to
    conclude, on a field it does not own. A trace still open has no verdict
    yet, and the honest rendering of that is an absent property rather than
    "outcome unknown".
    """
    lines: list[str] = []
    for h in hits:
        step = h.step
        lines.append("- step:")
        for label, value, limit in (
            ("thought", step.thought, 400),
            ("action", step.action, 200),
            ("observation", step.observation, 400),
        ):
            if value:
                lines.append(f"    {label}: {_cap(value, limit)}")
        # The rest of what search_steps returns. `parent_task` is the trace
        # this step belongs to and `similarity` is how close it is to the
        # query -- both were being dropped, which left the model unable to
        # tell a 0.71 match from a 0.98 one.
        if h.parent_task:
            lines.append(f"    task: {_cap(h.parent_task, 200)}")
        if h.similarity is not None:
            lines.append(f"    similarity: {h.similarity:.2f}")
        if h.parent_success is not None:
            lines.append(f"    success: {h.parent_success}")
    if not lines:
        return None
    return "Steps retrieved from the shared reasoning graph:\n" + "\n".join(lines)


class StepMemoryService:
    """Holds one warm ScopedMemory per warm agent and serves hook requests.

    The orchestrator registers an agent's CURRENT trace id as each attempt
    starts (`set_trace`); the hook only carries the session context Vibe gives
    it, which has no idea that attempts or traces exist.
    """

    def __init__(self) -> None:
        self._mem: dict[str, ScopedMemory] = {}
        self._trace: dict[str, Any] = {}
        # agent -> (turn_id, reasoning text) for the turn currently in flight.
        # See set_pending_reasoning() and note_turn().
        self._pending_reasoning: dict[str, tuple[str | None, str]] = {}
        self._server: asyncio.Server | None = None
        self.port: int | None = None
        # Counted so a run can say whether the hook actually did anything,
        # rather than leaving it to be reconstructed from Neo4j afterwards.
        self.steps_written = 0
        self.text_turns_written = 0
        self.context_returned = 0
        self.errors = 0
        # (agent, first 200 chars) of text-only turns already stored.
        # `post_agent` fires per Vibe invocation and reads the transcript tail,
        # which spans earlier attempts of a `--continue`d session, so without
        # this the same "the migration is complete" turn is stored once per
        # attempt for the rest of the run.
        self._seen_text_turns: set[tuple[str, str]] = set()

    def register(self, agent: str, mem: ScopedMemory) -> None:
        self._mem[agent] = mem

    def set_trace(self, agent: str, trace_id: Any) -> None:
        self._trace[agent] = trace_id

    def set_pending_reasoning(
        self, agent: str, text: str, turn_id: str | None = None
    ) -> None:
        """The reasoning behind the steps this agent is about to take, and the
        turn it belongs to.

        Pushed in by the orchestrator's reader of Vibe's `--output streaming`
        entries (vibe_agent._entry_consumer), because that is the only channel
        that carries it: Vibe flushes `messages.jsonl` once per turn, after the
        tool loop, so at post_tool time the assistant message that issued the
        call is still only in Vibe's memory. Reading the transcript tail
        therefore found nothing and every step recorded tool-input JSON as its
        thought -- measured at 100% of steps on a live run.

        Several tool calls in ONE turn share this text, which is correct: they
        were decided in the same piece of reasoning. Tool calls in a LATER turn
        must not, and `turn_id` is what tells them apart -- see note_turn()."""
        self._pending_reasoning[agent] = (turn_id, text)

    def note_turn(self, agent: str, turn_id: str | None) -> None:
        """Vibe has emitted an entry belonging to `turn_id`.

        Reasoning is held until the turn it belongs to ends, and this is what
        ends it. Without it, `_pending_reasoning` was only ever overwritten by
        the NEXT reasoning entry -- so a turn that issued tool calls while
        emitting no reasoning of its own silently inherited the previous turn's
        thought, and the documented fall-back to tool input became unreachable
        after an agent's first reasoning entry.

        Measured on the run that shipped it: the JSON fall-back fired 0 times
        in 141 steps, 73 steps (52%) shared a thought with an adjacent step,
        and one thought -- the session's first, "let me start by understanding"
        -- was attached to 20 consecutive `grep`/`read_file` calls. Since
        `search_steps` embeds thought+action, those 20 steps were near-
        duplicates in the vector index, describing an action none of them took.

        `turn_id` is on Vibe's `_PublicHistoryEntryBase`, so EVERY streamed
        entry carries it -- message, reasoning and effect alike. A `None` never
        invalidates: it means Vibe did not say which turn this was, which is
        not evidence that the turn changed."""
        if turn_id is None:
            return
        pending = self._pending_reasoning.get(agent)
        if pending is not None and pending[0] is not None and pending[0] != turn_id:
            del self._pending_reasoning[agent]

    def clear_trace(self, agent: str) -> None:
        self._trace.pop(agent, None)

    async def handle_agent_end(self, request: dict) -> dict:
        """The agent's turns that called no tool at all.

        `post_tool` cannot see them by construction, and they are not
        throwaway: measured on the transcripts of the run the hook shipped in,
        6 of 37 assistant turns issued no tool call and carried 9,785
        characters of reasoning -- 15% of everything the model thought. They
        are also, specifically, the turns where this model declares itself
        finished while the suite still fails ("The migration is now complete",
        "Would you like me to proceed with..."), which is the single most
        useful thing another agent could know about it.

        `post_agent` fires once when Vibe's loop ends and carries
        `transcript_path` (HookSessionContext) but no message content, so the
        tail of the transcript is read for assistant turns with no tool_calls.
        Keyed on the text so a re-fire cannot store the same turn twice.

        Recorded as a step with an explicit action, because it IS a step in the
        agent's reasoning -- the one where it decided to stop.
        """
        agent = request.get("agent") or ""
        mem = self._mem.get(agent)
        trace_id = self._trace.get(agent)
        if mem is None or trace_id is None:
            return {}
        try:
            for text in _text_only_turns(request.get("transcript_path")):
                key = (agent, text[:200])
                if key in self._seen_text_turns:
                    continue
                self._seen_text_turns.add(key)
                await mem.add_step(
                    trace_id,
                    thought=_cap(text, _THOUGHT_CAP),
                    action="(ended its turn without calling a tool)",
                    observation=None,
                    generate_embedding=False,
                )
                self.steps_written += 1
                self.text_turns_written += 1
        except Exception:
            self.errors += 1
        return {}

    async def handle(self, request: dict) -> dict:
        """One tool call. Returns {} or {"additional_context": "..."}.

        FAILS OPEN, always. This runs inside the agent's tool-call path: if
        the graph is slow, unreachable, or raises, the correct outcome is that
        the agent's edit still lands and it simply gets no memory this turn.
        A memory failure must never look to the agent like a tool failure.
        """
        agent = request.get("agent") or ""
        mem = self._mem.get(agent)
        if mem is None:
            return {}
        tool_name = request.get("tool_name") or ""
        is_evidence = any(tool_name.endswith(t) for t in _EVIDENCE_TOOLS)

        # EVERY tool call is recorded as a step; only the observation is
        # reduced for exploration tools. See _EVIDENCE_TOOLS.
        observation = _cap(
            request.get("tool_error") or request.get("tool_output_text"),
            _OBS_CAP if is_evidence else _EXPLORATION_OBS_CAP,
        )
        # ...and only evidence produces a retrieval query. Searching on the
        # contents of a file the agent just opened returns whatever else
        # mentions that file, which is not what it needs to know.
        query = (
            _query_text(request.get("tool_error"), request.get("tool_output_text"))
            if is_evidence else ""
        )
        trace_id = self._trace.get(agent)

        try:
            # WRITE first, so the graph records what happened even if the
            # search half fails.
            if trace_id is not None:
                # The agent's OWN reasoning for this step, delivered by the
                # orchestrator's reader of Vibe's streamed `type="reasoning"`
                # entries -- see set_pending_reasoning(). This is the field
                # that makes a step worth retrieving: `search_steps` embeds
                # thought+action, so with the tool input here instead, steps
                # were findable by what was typed and not by why.
                #
                # Falls back to the tool input when a turn carried no reasoning
                # (it happens) or when the stream is not being consumed.
                pending = self._pending_reasoning.get(agent)
                thought = (
                    _cap(pending[1] if pending else "", _THOUGHT_CAP)
                    or _cap(json.dumps(request.get("tool_input") or {}), 800)
                )
                step = await mem.add_step(
                    trace_id,
                    thought=thought,
                    action=tool_name,
                    observation=observation,
                    # Embedded in one batch by complete_trace(
                    # generate_step_embeddings=True) -- the pairing the
                    # package's docstring names for streaming recorders.
                    # Inline embedding would put an OpenAI round-trip in the
                    # agent's tool path, on every tool call.
                    generate_embedding=False,
                )
                await mem.record_tool_call(
                    step.id, tool_name=tool_name,
                    arguments=request.get("tool_input") or {},
                )
                self.steps_written += 1
        except Exception:
            self.errors += 1

        if not query:
            return {}
        try:
            hits = await mem.search_steps(
                query,
                limit=3,
                # Failures are the useful half here: three agents
                # independently rediscovering that `pydantic.model_validators`
                # does not exist is exactly what this is for.
                success_only=False,
                threshold=_THRESHOLD,
            )
        except Exception:
            self.errors += 1
            return {}

        # Drop this agent's own steps, including the one written a moment ago,
        # or the hook hands the agent back its own output as if it were
        # another agent's experience.
        own = {str(trace_id)} if trace_id is not None else set()
        fresh = [h for h in hits if str(getattr(h.step, "trace_id", "")) not in own]
        text = _render(fresh)
        if not text:
            return {}
        self.context_returned += 1
        return {"additional_context": text}

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                line = await reader.readline()
                if not line:
                    return
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    request = {}
                # One socket, two hook types. The client forwards Vibe's own
                # `hook_event_name` so the sidecar does not have to guess from
                # which fields happen to be present.
                if str(request.get("hook_event_name") or "").endswith("post_agent"):
                    response = await self.handle_agent_end(request)
                else:
                    response = await self.handle(request)
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
            except Exception:
                self.errors += 1
            finally:
                writer.close()

        self._server = await asyncio.start_server(serve, host, port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def summary(self) -> str:
        return (
            f"step hook: {self.steps_written} step(s) written by the agents "
            f"({self.text_turns_written} of them turns that called no tool), "
            f"{self.context_returned} injection(s) of prior agents' steps, "
            f"{self.errors} error(s)"
        )
