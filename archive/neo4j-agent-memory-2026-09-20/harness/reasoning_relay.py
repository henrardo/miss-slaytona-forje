"""Tee Vibe's streamed entries: stdout unchanged, reasoning to the sidecar.

WHY THIS EXISTS. `search_steps` embeds thought+action, so `ReasoningStep.
thought` decides whether a step is retrievable by *why* it was taken or only
by *what was typed*. On the remote path every step stored tool-argument JSON:

    thought: '{"pattern": "pydantic", "path": "/home/agent-warm-0/repo", ...}'

Two things caused that, and fixing either alone changes nothing.

  1. `RemoteTraceBridge.set_pending_reasoning` was a no-op stub, so the
     orchestrator's entry reader had nowhere to send what it read.
  2. More fundamentally, `AgentWorkspace.run_vibe` consumed the stream AFTER
     the subprocess exited. Vibe flushes `messages.jsonl` once per turn, after
     the tool loop, so at post_tool time the assistant message that issued the
     call exists only inside Vibe -- and the orchestrator's copy of the stream
     did not exist yet either. Reasoning could not reach the hook in time by
     any route that went through the operator's machine.

So the relay runs ON the pod, in the pipeline: Vibe writes an entry, the relay
forwards the reasoning half to the sidecar over loopback, and the tool call's
`post_tool` hook -- which fires moments later on the same host -- finds it
waiting. The operator still gets the byte-identical stream on stdout.

    vibe ... --output streaming | reasoning_relay.py <sidecar_port> <agent>

Stdlib only, line-buffered, and it never fails the pipeline: a sidecar that is
down costs the thought field, not the run.
"""
from __future__ import annotations

import json
import socket
import sys

TIMEOUT_S = 5.0


def _send(port: int, payload: dict) -> None:
    """Best effort. A dropped reasoning entry degrades retrieval quality; a
    raised exception here would kill the agent's whole invocation."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT_S) as s:
            s.settimeout(TIMEOUT_S)
            s.sendall((json.dumps(payload) + "\n").encode())
            s.makefile().readline()
    except Exception:
        pass


def _text(entry: dict) -> str:
    """Text out of one entry. Mirrors orchestrator.ingest._entry_text.

    `content` on a MESSAGE entry is a list of typed blocks, not a string --
    the earlier version here only accepted strings, so even once message
    entries were forwarded it would have extracted nothing from them.
    """
    value = entry.get("text")
    if isinstance(value, str) and value.strip():
        return value
    content = entry.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n\n".join(
            str(b.get("text", "")) for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


def main() -> int:
    port = int(sys.argv[1])
    agent = sys.argv[2]
    # MODEL TURNS, COUNTED HERE, because Vibe's `turnId` does not mark them.
    #
    # Measured 2026-09-20 with scripts/probe_turn_ids.py, driving the real
    # vibe 2.25.5 against tests/fake_model_server.py: a four-turn scripted
    # conversation produced ELEVEN streamed entries carrying ONE turnId.
    # `turnId` is the CONVERSATION turn -- one user prompt, one id -- and an
    # agent attempt is a single prompt, so it never changes for the whole
    # attempt.
    #
    # Everything downstream assumed otherwise. `note_turn()` clears pending
    # reasoning only when the id CHANGES, so it never fired, and
    # `set_pending_reasoning()` accumulates while the id is equal, so it
    # accumulated for the entire attempt: measured on Aura, step thoughts
    # climbed 267 -> 1537 characters and never reset, every step in a trace
    # opening with the same sentence. `render_steps` then truncates each
    # thought to 300 characters, so the skill author saw ONE IDENTICAL
    # SENTENCE PER STEP -- which is why 81 accepted skill versions changed
    # nothing.
    #
    # `orchestrator/ingest.py` -- the reference implementation, and correct
    # -- never used turnId for this. Its comment says it outright: "the
    # user's turn, not the model's. The model's own cadence is
    # reason-speak-act, and the act is what closes a step." It appends both
    # reasoning and assistant-message text to `thought_parts` and clears on
    # the tool effect.
    #
    # So the boundary is counted here instead: one model turn per
    # reason-speak-act cycle.
    #
    # THE KEY ADVANCES WHEN THE NEXT TURN BEGINS, NOT WHEN THIS ONE SPEAKS.
    # Advancing it on the assistant message looked right and broke the
    # rehearsal immediately: 0 thoughts from reasoning, 4 fall-backs to tool
    # input, 12 pushes received. The `effect` entry -- Vibe reporting the
    # tool running -- then carried the NEXT key, so note_turn deleted the
    # pending reasoning a moment before the post_tool hook could read it.
    # Under the old constant turnId nothing was ever deleted, which is why
    # the accumulation bug hid a second one underneath it.
    #
    # So: an `effect` arms the boundary, and the next reasoning or assistant
    # message trips it. Everything in one cycle -- reasoning, message, and
    # the effects of the tools that message called -- shares a key, which
    # also preserves the documented property that several tool calls decided
    # in one piece of reasoning share that reasoning.
    model_turn = 0
    saw_effect = False
    for line in sys.stdin:
        # Pass through FIRST and unmodified. The operator parses this stream
        # for turn counts and stop reasons, and the relay must be invisible
        # to it -- including when the json below fails to parse.
        sys.stdout.write(line)
        sys.stdout.flush()
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        kind = entry.get("type")
        is_assistant_message = (kind == "message"
                                and entry.get("role") == "assistant")
        # Trip the boundary armed by the previous cycle's tool call, BEFORE
        # this entry is keyed -- so the new turn's reasoning lands under the
        # new key and note_turn drops the old turn's.
        if saw_effect and (kind == "reasoning" or is_assistant_message):
            model_turn += 1
            saw_effect = False
        if kind == "effect":
            saw_effect = True
        # The key the sidecar groups reasoning by. Vibe's own `turnId` is
        # kept in it so a trace can still be tied back to the conversation,
        # but the part that CHANGES -- and therefore the part note_turn and
        # set_pending_reasoning key on -- is the model-turn counter above.
        turn_id = f"{entry.get('turnId')}#{model_turn}"
        _send(port, {"control": "note_turn", "agent": agent,
                     "turn_id": turn_id})
        # BOTH entry types, exactly as orchestrator/ingest.py does it --
        # that is the reference implementation, it is in this repo, and
        # this filtered on half of it.
        #
        # `type="reasoning"` is a hybrid reasoning model's separate channel.
        # Mistral-Small-4 on SGLang 0.5.14 does NOT use it: measured
        # directly against the pod, `reasoning_content` comes back None and
        # the model's reasoning arrives as ordinary assistant `content`
        # ("The user is experiencing a PydanticUserError... This typically
        # happens when...") alongside the tool call it justifies.
        #
        # So on this model the relay forwarded NOTHING, every step fell
        # back to serialised tool input, and the graph was searchable by
        # what was typed rather than by why. The rehearsal did not catch it
        # because its fake model emits proper `reasoning` entries -- a
        # fixture I wrote, validating my implementation against my own
        # assumption instead of against the model.
        if kind == "reasoning" or is_assistant_message:
            text = _text(entry)
            if text:
                _send(port, {"control": "reasoning", "agent": agent,
                             "text": text, "turn_id": turn_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
