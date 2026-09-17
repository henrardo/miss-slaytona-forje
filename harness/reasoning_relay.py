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
    """Vibe carries entry text under several keys depending on the entry
    type; mirrors orchestrator.vibe_agent._entry_text."""
    for key in ("content", "text", "reasoningContent", "reasoning_content"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def main() -> int:
    port = int(sys.argv[1])
    agent = sys.argv[2]
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
        # `turnId`, not `turn_id`: Vibe serialises by alias. Getting this
        # wrong made the local note_turn a silent no-op for two runs.
        turn_id = entry.get("turnId")
        if turn_id is not None:
            _send(port, {"control": "note_turn", "agent": agent,
                         "turn_id": turn_id})
        if entry.get("type") == "reasoning":
            text = _text(entry)
            if text:
                _send(port, {"control": "reasoning", "agent": agent,
                             "text": text, "turn_id": turn_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
