"""A scripted OpenAI-compatible server, so the loop can be rehearsed for free.

WHY. Every plumbing bug this project has had cost an hour of GPU time to
find: a hook with no shebang, an MCP client speaking the wrong HTTP dialect,
`tools` read instead of `tools_available`, a handler that raised inside its
own except clause. None of them needed a 119B model to reproduce -- they
needed a server that answers, and something to drive the real harness
against it.

So this serves `/v1/chat/completions` from a script: a list of turns, each
either tool calls or a final message. Vibe cannot tell it from SGLang, which
is the point -- the harness, Vibe, the hooks, the skill loading and the
ingestion all run exactly as they will on the pod.

    server = FakeModelServer([
        Turn(text="Let me look at the code", tools=[("bash", {"command": "ls"})]),
        Turn(text="Done."),
    ])
    with server:
        ...  # point an agent at server.base_url

Two details are not cosmetic:

  * TOOL CALL IDS MUST MATCH ^[a-zA-Z0-9]{9}$. mistral_common validates them
    and rejects anything else; the whole id_fix_proxy exists because of it.
    Getting this wrong here would produce a failure the real server also
    has, which is useful, but silently -- so the ids are generated correctly
    and `strict_ids=False` exists to reproduce the failure deliberately.

  * STREAMING IS SSE, and Vibe asks for it. A non-streaming-only fake would
    exercise a code path the real runs never take.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class Turn:
    """One model turn: some text, and zero or more tool calls."""
    text: str = ""
    tools: list[tuple[str, dict]] = field(default_factory=list)
    # Vibe's Mistral route can carry hidden chain-of-thought separately from
    # the visible content. Half of a real warm session's assistant messages
    # had no `content` at all, so this is where the thought actually lives.
    reasoning: str = ""
    # Seconds to wait before answering, for exercising timeouts.
    delay: float = 0.0


def _tool_call_id(n: int) -> str:
    """9 alphanumeric characters, per mistral_common's validator."""
    return f"call{n:05d}"[:9].ljust(9, "0")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - quiet by default
        pass

    @property
    def script(self) -> "FakeModelServer":
        return self.server.script  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": [
                {"id": self.script.model, "object": "model"}]})
            return
        if self.path.rstrip("/").endswith("/usage"):
            self._json(self.script.usage)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.script.requests.append(body)
        turn = self.script.next_turn(body)
        if turn.delay:
            time.sleep(turn.delay)
        # Rough, but it is the same shape of number the counting proxies
        # report, and the metrics tests need it to move.
        self.script.usage["prompt_tokens"] += sum(
            len(json.dumps(m)) for m in body.get("messages") or []) // 4
        self.script.usage["completion_tokens"] += (
            len(turn.text) + len(turn.reasoning)) // 4 + 8 * len(turn.tools)
        if body.get("stream"):
            self._stream(turn)
        else:
            self._json(self._completion(turn))

    def _completion(self, turn: Turn) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": turn.text}
        if turn.reasoning:
            message["reasoning_content"] = turn.reasoning
        if turn.tools:
            message["tool_calls"] = [
                {"id": self.script.tool_call_id(i), "type": "function",
                 "index": i,
                 "function": {"name": name, "arguments": json.dumps(args)}}
                for i, (name, args) in enumerate(turn.tools)
            ]
        return {
            "id": "chatcmpl-fake", "object": "chat.completion",
            "created": 0, "model": self.script.model,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "tool_calls" if turn.tools else "stop"}],
            "usage": dict(self.script.usage),
        }

    def _stream(self, turn: Turn) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def chunk(delta: dict, finish: str | None = None) -> None:
            payload = {"id": "chatcmpl-fake", "object": "chat.completion.chunk",
                       "created": 0, "model": self.script.model,
                       "choices": [{"index": 0, "delta": delta,
                                    "finish_reason": finish}]}
            self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
            self.wfile.flush()

        chunk({"role": "assistant", "content": ""})
        if turn.reasoning:
            chunk({"reasoning_content": turn.reasoning})
        if turn.text:
            chunk({"content": turn.text})
        for i, (name, args) in enumerate(turn.tools):
            chunk({"tool_calls": [{
                "index": i, "id": self.script.tool_call_id(i), "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }]})
        chunk({}, "tool_calls" if turn.tools else "stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeModelServer:
    """Serves a script of turns. Reusable as a context manager.

    When the script runs out it repeats its last turn, which must therefore
    be a terminal one (no tool calls) -- otherwise an agent would loop
    forever, which is a bug in the script rather than in the harness.
    """

    def __init__(self, turns: list[Turn] | None = None, *,
                 scripts: dict[str, list[Turn]] | None = None,
                 router: Any = None, model: str = "fake-model",
                 strict_ids: bool = True) -> None:
        """One flat script, or several routed by what the prompt asks for.

        A single queue cannot serve this harness: an attempt and a
        distillation turn interleave, and a repair turn re-runs one of
        them, so a flat queue drifts and the distiller ends up being served
        the attempt's `bash ls -la`. `router(body) -> key` picks the script
        by inspecting the request, and each script keeps its own position.
        """
        scripts = dict(scripts or {})
        if turns is not None:
            scripts.setdefault("default", list(turns))
        for name, script in scripts.items():
            if script and script[-1].tools:
                raise ValueError(
                    f"the last turn of script {name!r} makes tool calls, so "
                    f"the agent would never stop: a script repeats its final "
                    f"turn once exhausted"
                )
        self.scripts = scripts
        self.router = router
        self.model = model
        self.strict_ids = strict_ids
        self.requests: list[dict] = []
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self._indices: dict[str, int] = {k: 0 for k in scripts}
        self._index = 0
        self._lock = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def tool_call_id(self, i: int) -> str:
        n = self._index * 10 + i
        return _tool_call_id(n) if self.strict_ids else f"tool-call-{n}"

    @property
    def turns(self) -> list[Turn]:
        return self.scripts.get("default", [])

    @turns.setter
    def turns(self, value: list[Turn]) -> None:
        self.scripts["default"] = list(value)
        self._indices["default"] = 0

    def next_turn(self, body: dict | None = None) -> Turn:
        with self._lock:
            key = "default"
            if self.router is not None and body is not None:
                key = self.router(body) or "default"
            script = self.scripts.get(key) or []
            if not script:
                return Turn(text="")
            i = self._indices.get(key, 0)
            turn = script[min(i, len(script) - 1)]
            self._indices[key] = i + 1
            self._index += 1
            return turn

    @property
    def calls(self) -> int:
        return self._index

    @property
    def base_url(self) -> str:
        assert self._httpd is not None, "server not started"
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> "FakeModelServer":
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.script = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
