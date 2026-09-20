"""Turn one attempt's Vibe stream into reasoning steps in the graph.

WHY THIS REPLACES THE POST_TOOL HOOK. Writing a step per tool call meant a
loopback call, a queue and an Aura round trip inside the agent's own tool
path: ~3.3 seconds per call, warm only, charged to warm's wall-clock by a
deadline both arms share. It also could not see the model's reasoning,
because Vibe flushes `messages.jsonl` once per turn, AFTER the tool loop --
which is the entire reason `harness/reasoning_relay.py` exists. So every
step on the remote path stored tool-argument JSON in `thought`, and
`search_steps` embeds thought+action, making the graph searchable by what
was typed rather than by why.

Both problems disappear if the writing happens after the attempt ends. By
then Vibe has emitted its whole stream, and the stream contains what the
transcript does not.

THE STREAM, as captured from mistral-vibe 2.25.4 (not inferred -- see
NOTES.md, run against a scripted server so the shapes are ground truth):

    {"type": "reasoning", "turnId": ..., "text": "the model's thought"}
    {"type": "message",   "turnId": ..., "role": "assistant",
                          "content": [{"type": "text", "text": ...}]}
    {"type": "effect",    "turnId": ..., "id": "<tool_call_id>",
                          "title": "bash",
                          "detail": {"toolName": "bash", "input": {...}},
                          "state": {"status": "completed",
                                    "outputText": "...",
                                    "error": {"message": ...}}}

They arrive in that order within a turn: the model reasons, says what it is
about to do, then does it. So a step is

    thought      = the reasoning entry, plus the assistant text
    action       = the tool and its arguments
    observation  = what the tool returned, or the error it raised

which is the shape `add_step` was designed for, and the shape
`search_steps` can retrieve on.

A turn with no tool call is still a step. Those are 15% of this model's
turns and include every turn where it decides it has finished; dropping
them was how an earlier design lost the reasoning that mattered most.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Tool output can be an entire pytest run. The graph embeds thought+action,
# not observation, so a huge observation costs storage and prompt space at
# retrieval time without improving recall. The head carries the verdict.
# NO CAP. Was 2000. See orchestrator/step_memory.py for the audit: the
# evidence cited for these came from storing tool results as :Message
# nodes, which go through entity extraction; add_step does not.
MAX_OBSERVATION_CHARS = None
MAX_THOUGHT_CHARS = None

# Vibe reports the skill load as an ordinary tool effect. It is not the
# agent's reasoning and must not become a step -- but it IS the proof that
# the skill reached the model, so it is extracted rather than dropped.
SKILL_TOOL = "skill"


@dataclass
class Step:
    """One model turn, ready to be written."""
    turn_id: str | None
    thought: str
    action: str
    observation: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    failed: bool = False


@dataclass
class Ingestion:
    """What one attempt's stream contained."""
    steps: list[Step]
    skill_content: str | None
    turns: int
    tool_calls: int
    failed_tool_calls: int

    @property
    def steps_with_reasoning(self) -> int:
        return sum(1 for s in self.steps if s.thought)


def _entry_text(entry: dict) -> str:
    """Text out of one entry. `content` is a list of typed blocks."""
    if isinstance(entry.get("text"), str) and entry["text"].strip():
        return entry["text"]
    content = entry.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n\n".join(
            str(b.get("text", "")) for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


def _cap(text: str, limit: int | None) -> str:
    """Head and tail, so a truncated pytest run keeps both its summary line
    and the first failure."""
    text = text or ""
    if limit is None or len(text) <= limit:
        return text
    head, tail = limit * 2 // 3, limit // 3
    return f"{text[:head]}\n...[{len(text) - limit} chars omitted]...\n{text[-tail:]}"


def _observation(effect: dict) -> tuple[str, bool]:
    """What the tool returned, and whether it failed."""
    state = effect.get("state") or {}
    status = state.get("status")
    error = state.get("error") or {}
    if error.get("message"):
        return str(error["message"]), True
    output = state.get("outputText")
    if not output and isinstance(state.get("output"), dict):
        # bash puts the useful half in stdout when outputText is empty.
        out = state["output"]
        output = out.get("stdout") or out.get("output") or ""
    return str(output or ""), status not in (None, "completed")


def parse_stream(entries: list[dict]) -> Ingestion:
    """Group a stream into steps, one per model turn.

    Entries are grouped by the tool call they precede, rather than by
    `turnId`: Vibe reuses one turn id for a whole multi-tool exchange (all
    nine entries of the captured session shared one), so turn ids identify
    the user's turn, not the model's. The model's own cadence is
    reason-speak-act, and the act is what closes a step.
    """
    steps: list[Step] = []
    skill_content: str | None = None
    thought_parts: list[str] = []
    turn_ids: set[str] = set()
    tool_calls = failed = 0

    def flush(effect: dict | None) -> None:
        nonlocal tool_calls, failed
        thought = "\n\n".join(p for p in thought_parts if p).strip()
        if effect is None:
            # A turn that called no tool: the model spoke and stopped. Still
            # a step -- this is where "I believe the migration is complete"
            # lives, and it is the claim the grader then contradicts.
            if thought:
                steps.append(Step(turn_id=next(iter(turn_ids), None),
                                  thought=_cap(thought, MAX_THOUGHT_CHARS),
                                  action="(no tool call)", observation=""))
            return
        detail = effect.get("detail") or {}
        name = detail.get("toolName") or effect.get("title") or "unknown"
        arguments = detail.get("input") if isinstance(detail.get("input"), dict) else {}
        observation, did_fail = _observation(effect)
        tool_calls += 1
        failed += bool(did_fail)
        steps.append(Step(
            turn_id=effect.get("turnId"),
            thought=_cap(thought, MAX_THOUGHT_CHARS),
            # The action reads as a call, because `search_steps` embeds
            # thought+action and "bash" alone distinguishes nothing on a
            # task where every agent runs bash dozens of times.
            action=f"{name}({json.dumps(arguments, sort_keys=True)[:500]})",
            observation=_cap(observation, MAX_OBSERVATION_CHARS),
            tool_name=name, arguments=arguments, failed=did_fail,
        ))

    for entry in entries:
        kind = entry.get("type")
        if entry.get("turnId"):
            turn_ids.add(entry["turnId"])
        if kind == "reasoning":
            thought_parts.append(_entry_text(entry))
        elif kind == "message":
            if entry.get("role") == "assistant":
                thought_parts.append(_entry_text(entry))
        elif kind == "effect":
            detail = entry.get("detail") or {}
            if (detail.get("toolName") or entry.get("title")) == SKILL_TOOL:
                # Not a step: this is Vibe loading the skill on the harness's
                # instruction, and it is the proof the skill reached the
                # model. Kept, not written.
                output = ((entry.get("state") or {}).get("output") or {})
                skill_content = output.get("content") or skill_content
                continue
            flush(entry)
            thought_parts = []
    flush(None)

    return Ingestion(steps=steps, skill_content=skill_content,
                     turns=len(turn_ids), tool_calls=tool_calls,
                     failed_tool_calls=failed)


async def ingest(mem, trace_id, entries: list[dict]) -> Ingestion:
    """Write one attempt's steps into the graph. Off the clock.

    Every step is written, including the ones whose tool call failed: an
    attempt that spent six turns fighting `edit` is exactly what a later
    distillation should be able to find, and recording only the successes
    would make the graph a highlight reel.

    A write that fails is logged and skipped rather than raised. This runs
    after the attempt has been graded, so losing a step costs recall in a
    later distillation; raising here would lose the attempt's verdict too.
    """
    from neo4j_agent_memory.memory.reasoning import ToolCallStatus

    result = parse_stream(entries)
    for step in result.steps:
        try:
            written = await mem.add_step(
                trace_id, thought=step.thought or None,
                action=step.action, observation=step.observation or None,
            )
        except Exception as exc:
            logger.error("ingest: add_step failed (%r); step lost: %.80s",
                         exc, step.action)
            continue
        if not step.tool_name:
            continue
        try:
            await mem.record_tool_call(
                written.id, tool_name=step.tool_name, arguments=step.arguments,
                result=step.observation or None,
                status=(ToolCallStatus.ERROR if step.failed
                        else ToolCallStatus.SUCCESS),
            )
        except Exception as exc:
            logger.error("ingest: record_tool_call failed (%r) for %s",
                         exc, step.tool_name)
    return result
