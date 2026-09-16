"""Adapts Vibe's Mistral-flavoured wire protocol to a generic SGLang endpoint,
and counts tokens.

Deliberately minimal: every byte Vibe sends should reach SGLang unchanged
except for the two rewrites below, because "Vibe must stay vanilla" is this
project's first non-negotiable and a wire-level mutation is the easiest way to
break it invisibly. Both rewrites apply identically to every swarm, so neither
can contaminate the warm/cold comparison.

1. REQUEST SIDE -- `tool_choice: "required"` -> `"auto"`. A TRIPWIRE, not a
   fix: vanilla Vibe already sends "auto", so this must never fire. If
   `GET /usage` reports a non-zero `tool_choice_relaxed`, someone has patched
   the installed package and the run is compromised -- preflight() trips on
   it. See NOTES-hard-won.md, "The model must tool-call under plain
   tool_choice: auto", for the twelve runs this cost.

2. RESPONSE SIDE -- tool_call ids. Vibe generates OpenAI-style ids;
   mistral_common's validator requires `^[a-zA-Z0-9]{9}$` and rejects the
   conversation on the next turn. Rewritten here, response-side only, because
   Vibe then stores and echoes back the compliant id itself. NOTES-hard-won.md,
   "Mistral tool-call ids".

Token accounting lives here because this is the only place that sees every raw
SGLang response -- Vibe never surfaces per-call usage outside its own process.
Run one instance per swarm, same upstream, so `/usage` is a real per-swarm
total. The counters are CUMULATIVE since process start: snapshot before,
snapshot after, subtract (NOTES-hard-won.md, "/usage counters are cumulative").

No timeout on the forward: this blocks exactly as long as SGLang takes, which
is what Vibe would have done unmediated.

    python3 harness/id_fix_proxy.py [listen_port] [upstream_url]
    # defaults: 8899, http://localhost:30000
    # GET /usage -> {"prompt_tokens", "completion_tokens", "requests",
    #                "tool_choice_relaxed"}
"""

import http.server
import os
import json
import re
import secrets
import string
import sys
import urllib.request

LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
UPSTREAM = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:30000"

# MUST be set on every upstream request. RunPod's HTTPS pod proxy
# (*.proxy.runpod.net) returns 403 Forbidden to urllib's default User-Agent
# and 200 to anything else -- verified three ways against the same URL in the
# same second: curl's own UA 200, no UA at all 200, `-A "Python-urllib/3.12"`
# 403. So it is a User-Agent filter, not auth, not rate limiting, and not the
# pod.
#
# The symptom is brutal to read from the outside: both proxies answer their
# own port, then fail every forward, and preflight reports "not answering
# (RemoteDisconnected)" while a manual `curl` to the very same upstream
# succeeds. That cost one aborted run. Direct `http://localhost:30000` over an
# SSH tunnel never hits this, which is why it only appeared once the pod was
# reached through its HTTPS proxy instead.
_USER_AGENT = "miss-slaytona-forje/id_fix_proxy"

VALID_ID = re.compile(r"^[a-zA-Z0-9]{9}$")
ALPHABET = string.ascii_letters + string.digits

USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
RELAXED = {"tool_choice": 0}
CAPTURE_DIR = os.environ.get("PROXY_CAPTURE_DIR")


def make_short_id():
    return "".join(secrets.choice(ALPHABET) for _ in range(9))


def tally_usage(obj):
    usage = obj.get("usage")
    if isinstance(usage, dict):
        USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
        USAGE["completion_tokens"] += usage.get("completion_tokens", 0) or 0
        USAGE["requests"] += 1


def relax_tool_choice(req_json):
    """`required` -> `auto`, so the model is allowed to end a turn with a
    plain text message. See the module docstring for the confirmed
    enforcement behaviour this compensates for. Returns the (possibly
    unchanged) request dict."""
    if isinstance(req_json, dict) and req_json.get("tool_choice") == "required":
        req_json["tool_choice"] = "auto"
        RELAXED["tool_choice"] += 1
    return req_json


# Ceiling on a single turn's generation. OFF by default -- see
# NOTES-hard-won.md, "Don't inject max_tokens into every request". Opt in with
# PROXY_MAX_TOKENS=2048 for a specific experiment; do not leave it on.
MAX_TOKENS = int(os.environ.get("PROXY_MAX_TOKENS", "0"))


def cap_max_tokens(req_json):
    """Bound how long one turn may generate. Off unless PROXY_MAX_TOKENS is
    set -- see the constant above for why that default flipped."""
    if MAX_TOKENS and isinstance(req_json, dict) and not req_json.get("max_tokens"):
        req_json["max_tokens"] = MAX_TOKENS
    return req_json


DISABLE_THINKING = os.environ.get("PROXY_DISABLE_THINKING") == "1"


def disable_thinking(req_json):
    """Opt-in, off by default: ask Qwen3 to skip its reasoning pass.

    `enable_thinking` is Qwen's own chat-template switch, passed through
    SGLang's `chat_template_kwargs`; Vibe never sends it. Measured on run 19,
    92% of everything the model generated was reasoning (131,751 chars against
    11,184 of content), which is the whole throughput story on this pod.

    It should stay off for the real demo. Qwen3 is a cheap stand-in and the
    target is Mistral Small 4; tuning the pipeline around the stand-in's
    reasoning mode is optimising for a model the demo does not use. Enable it
    to answer one question -- can this harness converge when the model is not
    spending 92% of the clock thinking -- not as a standing setting."""
    if DISABLE_THINKING and isinstance(req_json, dict):
        kwargs = req_json.setdefault("chat_template_kwargs", {})
        if isinstance(kwargs, dict):
            kwargs["enable_thinking"] = False
    return req_json


def fix_tool_calls_in_obj(obj):
    """Walk a parsed response JSON chunk and replace any non-compliant tool_call id
    (in choices[].delta.tool_calls[] or choices[].message.tool_calls[]) with a fresh
    Mistral-compliant 9-char alnum id."""
    changed = False
    for choice in obj.get("choices", []):
        for key in ("delta", "message"):
            container = choice.get(key)
            if not container:
                continue
            for tc in container.get("tool_calls") or []:
                tc_id = tc.get("id")
                if tc_id and not VALID_ID.match(tc_id):
                    tc["id"] = make_short_id()
                    changed = True
    return changed


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req_json = json.loads(body)
        except Exception:
            req_json = None

        if req_json is not None and CAPTURE_DIR:
            # Debug aid only, off unless PROXY_CAPTURE_DIR is set: dumps each
            # request body so a real Vibe payload can be replayed/mutated
            # offline instead of guessed at.
            import os.path, time as _t
            with open(os.path.join(CAPTURE_DIR, f"req-{_t.time():.6f}.json"), "w") as f:
                json.dump(req_json, f)

        if req_json is not None:
            relax_tool_choice(req_json)
            disable_thinking(req_json)
            cap_max_tokens(req_json)
            # Always re-serialise. This used to be conditional on
            # `RELAXED["tool_choice"]` having changed -- i.e. the rewritten body
            # was only sent upstream when tool_choice had been relaxed. Vanilla
            # Vibe sends "auto", so that never fires, so any *other* mutation
            # was computed and then silently discarded: disable_thinking() ran
            # correctly, set chat_template_kwargs on the dict, and the original
            # unmodified bytes went to SGLang anyway. Run 20 was launched to
            # test thinking-off and measured 91% reasoning content, identical
            # to the run before it, because the flag never left this process.
            body = json.dumps(req_json).encode()

        is_stream = bool(req_json and req_json.get("stream"))

        req = urllib.request.Request(
            UPSTREAM + self.path, data=body,
            headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                status = resp.status
                headers = dict(resp.getheaders())
        except urllib.error.HTTPError as e:
            raw = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if is_stream:
            text = raw.decode(errors="replace")
            out_lines = []
            for line in text.split("\n"):
                if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        fix_tool_calls_in_obj(chunk)
                        tally_usage(chunk)
                        line = "data: " + json.dumps(chunk)
                    except Exception:
                        pass
                out_lines.append(line)
            new_body = "\n".join(out_lines).encode()
        else:
            try:
                resp_json = json.loads(raw)
                fix_tool_calls_in_obj(resp_json)
                tally_usage(resp_json)
                new_body = json.dumps(resp_json).encode()
            except Exception:
                new_body = raw

        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(new_body)))
        self.end_headers()
        self.wfile.write(new_body)

    def do_GET(self):
        if self.path == "/usage":
            body = json.dumps({**USAGE, "tool_choice_relaxed": RELAXED["tool_choice"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        req = urllib.request.Request(
            UPSTREAM + self.path, headers={"User-Agent": _USER_AGENT}, method="GET"
        )
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), Handler)
    print(f"id_fix_proxy listening on 127.0.0.1:{LISTEN_PORT} -> {UPSTREAM}")
    server.serve_forever()
