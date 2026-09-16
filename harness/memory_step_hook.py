"""Vibe `post_tool` hook: relay one tool call to the step-memory sidecar.

Invoked by Vibe once per tool call, per its hook contract: the invocation
arrives as JSON on stdin, and a structured response is "exit 0 + JSON object on
stdout" (vibe/core/hooks/models.py). `hook_specific_output.additional_context`
is appended to the tool output the model sees, which is how a past agent's
experience reaches this agent on the turn it needs it.

STDLIB ONLY, AND DELIBERATELY TRIVIAL. This process is started for every single
tool call the agent makes, so it must cost ~nothing and must never be able to
break the call:

  * no imports from this project and none from neo4j_agent_memory -- importing
    the latter costs ~1.5s in a fresh process, before its embedder loads, which
    would be paid on every tool use.
  * no credentials. Vibe's executor passes no `env=`, so this inherits the
    AGENT's environment, which has NEO4J_URI/NEO4J_PASSWORD stripped on
    purpose. It needs a loopback port, not secrets.
  * FAILS OPEN. Any error -- sidecar down, socket refused, malformed reply,
    timeout -- prints `{}` and exits 0. A memory problem must never surface to
    the agent as a tool failure.

Usage, as written into $VIBE_HOME/hooks.toml by vibe_agent.render_config():

    python memory_step_hook.py <port> <agent-id>
"""
import json
import socket
import sys

# Generous relative to a loopback round-trip plus two graph queries, and well
# under the `timeout` set on the hook in hooks.toml -- whichever fires first,
# the agent proceeds.
TIMEOUT_S = 8.0


if __name__ == "__main__":
    payload = {}
    try:
        port = int(sys.argv[1])
        agent = sys.argv[2]
        invocation = json.loads(sys.stdin.read() or "{}")
        request = {
            "agent": agent,
            # Which hook fired. The same client serves both `post_tool` (one
            # step per tool call) and `post_agent` (the turns that called no
            # tool at all, which post_tool cannot see).
            "hook_event_name": str(invocation.get("hook_event_name") or ""),
            # Vibe's PostToolInvocation fields, passed through unchanged.
            "tool_name": invocation.get("tool_name"),
            "tool_input": invocation.get("tool_input"),
            "tool_output_text": invocation.get("tool_output_text"),
            "tool_error": invocation.get("tool_error"),
            "tool_status": str(invocation.get("tool_status") or ""),
            # These two are how the agent's REASONING reaches the graph. The
            # payload has no reasoning field, but `transcript_path` plus
            # `tool_call_id` is an exact join onto the assistant message that
            # issued this call, where `reasoning_content` lives. The sidecar
            # does the reading -- this stays a passthrough.
            "transcript_path": invocation.get("transcript_path"),
            "tool_call_id": invocation.get("tool_call_id"),
        }
        with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT_S) as s:
            s.settimeout(TIMEOUT_S)
            s.sendall((json.dumps(request) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        reply = json.loads(buf.decode() or "{}")
        context = reply.get("additional_context")
        if context:
            payload = {"hook_specific_output": {"additional_context": context}}
    except Exception:
        # Fail open -- see the module docstring.
        payload = {}
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)
