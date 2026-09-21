#!/usr/bin/env python3
"""Vibe `post_tool` hook: when the agent's own command fails, tell it what
memory knows about that failure.

Registered against `bash` for warm agents only. Vibe hands the hook one JSON
object on stdin (PostToolInvocation) and reads one JSON object back; with
`hook_specific_output.additional_context` set, Vibe appends that text to the
tool result the model sees. So this is a DETERMINISTIC READ at the one moment
it is worth most: the agent has just run something and it broke.

It is here because the voluntary half does not fire. Measured over the last
forty runs: 4,767 `bash` calls and 9 `cognee_recall` calls. The tools were
registered, the server was live; the model simply did not reach for them.

What it talks to: Cognee's own REST API (`POST /api/v1/recall`), which the
harness runs beside the orchestrator and exposes on this machine's loopback
through `ssh -R`. That indirection is not incidental -- a cognee process keeps
its users, datasets and vector index in LOCAL SQLite and LanceDB, so a second
cognee on this machine would be a second, empty memory writing into the same
Neo4j. No credential reaches this host.

Rules it must obey, because it runs inside the agent's clock:

  * a SUCCESSFUL command costs one process start and nothing else;
  * the graph being slow or gone must never block the agent -- short timeout,
    and any failure exits 0 with no output;
  * every invocation is appended to a journal the harness folds into the
    attempt's outcome document, so what the hook did is countable rather than
    inferred.

Environment, set per agent by the harness:
    COGNEE_API      base URL of the Cognee REST API
    COGNEE_DATASET  dataset to recall from
    COGNEE_JOURNAL  path to append one JSON line per invocation
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

TIMEOUT_S = float(os.environ.get("COGNEE_HOOK_TIMEOUT", "8"))
MAX_CHARS = int(os.environ.get("COGNEE_HOOK_MAX_CHARS", "1200"))
# Enough of the command and its output to rank a recall against, and no more:
# a 200 kB pytest log would be embedded in full to retrieve 1,200 characters.
QUERY_CHARS = 1500


def journal(entry: dict) -> None:
    path = os.environ.get("COGNEE_JOURNAL")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def recall(query: str) -> str:
    body = json.dumps({
        "query": query,
        "datasets": [os.environ.get("COGNEE_DATASET", "main_dataset")],
        "searchType": "CHUNKS",
        "onlyContext": True,
        "topK": 5,
    }).encode()
    request = urllib.request.Request(
        f"{os.environ['COGNEE_API'].rstrip('/')}/api/v1/recall",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        entries = json.loads(response.read().decode())
    out: list[str] = []
    for entry in entries or []:
        # A cold node set answers with a warming-up marker, not an empty list.
        if entry.get("source") == "system" or entry.get("kind") == "system":
            continue
        text = (entry.get("text") or "").strip()
        if text and text not in out:
            out.append(text)
    return "\n\n".join(out)


def main() -> int:
    try:
        invocation = json.load(sys.stdin)
    except Exception:
        return 0
    status = invocation.get("tool_status")
    if status == "success":
        journal({"tool": invocation.get("tool_name"), "status": status,
                 "input": invocation.get("tool_input"), "recalled": 0})
        return 0

    command = json.dumps(invocation.get("tool_input") or {})[:400]
    output = (invocation.get("tool_error")
              or invocation.get("tool_output_text") or "")
    query = f"{command}\n{output}"[:QUERY_CHARS]

    started = time.monotonic()
    try:
        text = recall(query)[:MAX_CHARS]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        # The agent must not pay for the graph being unreachable.
        text = ""
    elapsed_ms = int((time.monotonic() - started) * 1000)

    journal({"tool": invocation.get("tool_name"), "status": status,
             "input": invocation.get("tool_input"),
             "error": output[:400], "recalled": len(text),
             "hook_ms": elapsed_ms})
    if not text:
        return 0
    json.dump({"hook_specific_output": {
        "additional_context":
            "\n\n--- from your memory of this codebase ---\n" + text}},
        sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
