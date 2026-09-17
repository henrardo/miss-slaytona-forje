"""The step-memory sidecar, as a process on the swarm host.

Same StepMemoryService the old harness used, in the place it now belongs:
beside the agents instead of beside the orchestrator. The hook still reaches it
over a loopback socket -- it is simply a different loopback.

It also accepts two CONTROL requests the in-process version did not need,
because the orchestrator is no longer in the same process:

    {"control": "set_trace", "agent": "warm-0", "trace_id": "..."}
    {"control": "summary"}

The orchestrator reaches those through an SSH local port forward, so the
control channel is never exposed off the host.

Runs as root, not as an agent: it holds the Neo4j credentials, and the whole
point of the agent users is that they do not.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j_agent_memory import MemoryClient

from orchestrator.memory import ScopedMemory, build_settings
from orchestrator.step_memory import StepMemoryService


async def serve(port: int, agents: list[str]) -> None:
    async with MemoryClient(build_settings()) as client:
        service = StepMemoryService()
        for label in agents:
            service.register(label, ScopedMemory(client, user_identifier=label))

        actual = await service.start(port=port)
        print(f"sidecar listening on 127.0.0.1:{actual} for {agents}", flush=True)

        # The control channel shares the socket the hook uses. Wrapping
        # `handle` rather than adding a second listener keeps one code path for
        # "what does this port do", and the port is loopback-only either way.
        original_handle = service.handle

        async def handle(request: dict) -> dict:
            control = request.get("control")
            if control == "set_trace":
                # Drain the PREVIOUS attempt's writes before moving the
                # pointer, so the next attempt's retrieval sees a complete
                # predecessor. Queued items carry their own trace_id, so this
                # is about completeness, not misfiling.
                await service.set_trace_flushed(
                    request.get("agent") or "", request.get("trace_id"))
                return {"ok": True}
            if control == "flush":
                ok = await service.flush(float(request.get("timeout") or 120.0))
                return {"ok": ok, "queue": service.queue_report()}
            # Pushed by harness/reasoning_relay.py, on the pod, over
            # loopback, while Vibe is still running -- the only route that
            # gets the agent's reasoning to post_tool in time. See the
            # relay's docstring for why the operator-side path cannot.
            if control == "reasoning":
                service.set_pending_reasoning(
                    request.get("agent") or "", request.get("text") or "",
                    request.get("turn_id"))
                return {"ok": True}
            if control == "note_turn":
                service.note_turn(request.get("agent") or "",
                                  request.get("turn_id"))
                return {"ok": True}
            if control == "clear_trace":
                service.clear_trace(request.get("agent") or "")
                return {"ok": True}
            if control == "injections":
                return {"injections": service.injections}
            if control == "summary":
                return {
                    "summary": service.summary(),
                    "steps_written": service.steps_written,
                    "text_turns_written": service.text_turns_written,
                    "context_returned": service.context_returned,
                    "errors": service.errors,
                    "writes_queued": service.writes_queued,
                    "writes_flushed": service.writes_flushed,
                    "writes_dropped": service.writes_dropped,
                }
            return await original_handle(request)

        service.handle = handle  # type: ignore[method-assign]
        while True:
            await asyncio.sleep(3600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--agents", required=True,
                        help="comma-separated labels, e.g. warm-0,warm-1")
    args = parser.parse_args()
    asyncio.run(serve(args.port, [a for a in args.agents.split(",") if a]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
