"""Adapts Vibe's Mistral-flavoured wire protocol to a generic SGLang endpoint.

Two rewrites, both mechanical, both applied identically to every swarm so
neither can contaminate the warm/cold comparison:

1. REQUEST SIDE -- `tool_choice: "required"` -> `"auto"`. A GUARD, not a
   fix: as of 2026-09-13 the installed Vibe is byte-identical to the
   published wheel and already sends "auto", so this rewrite should never
   fire. `GET /usage` reports `tool_choice_relaxed`; if that counter is
   anything but 0, someone has re-patched Vibe and the run is compromised.
   It is kept because the failure it guards against is silent, total, and
   cost twelve full runs to find.

   The history: an earlier session hand-edited the *installed package*,
   changing `APIToolFormatHandler.get_tool_choice()` (core/llm/format.py:62)
   from "auto" to "required", to work around a model that would not
   spontaneously emit tool calls. Vibe's agent loop ends a turn only when
   the model returns an assistant message carrying *no* tool calls
   (core/agent_loop/_loop.py:2483,
   `if not resolved.tool_calls and not resolved.failed_calls: return`).

   SGLang enforces `tool_choice: "required"` with constrained decoding --
   confirmed directly against this pod, same model, same endpoint:

       tool_choice=None       -> finish=stop       tool_calls=[]     content='Hello! How can I assist you today?'
       tool_choice='auto'     -> finish=stop       tool_calls=[]     content='Hello! How can I assist you today?'
       tool_choice='required' -> finish=tool_calls tool_calls=['bash'] content=''

   ...for the prompt "Say hello. Do not use any tools." Under "required" the
   model is grammar-constrained into emitting a tool call on every single
   turn, so the loop's one and only exit condition can never be reached. The
   agent cannot stop. Confirmed in the transcripts: run-warm-0's last session
   has 576 assistant messages and 576 tool results -- not one text-only turn
   in the entire session -- 524 of them `read_file`, looping until the run
   deadline killed it. That is the whole of the "agents get nothing done"
   symptom, and every downstream oddity (600+ `skill` calls, 90M-token runs,
   zero completions across twelve runs) is a consequence of it.

   So the patch traded "the model never starts" for "the model can never
   stop", and the second failure is total. The real fix was to revert the
   package (it is now verified byte-identical to the wheel's own SHA-256
   manifest) and serve a model that calls tools under plain "auto", which
   is what Vibe was written against.

2. RESPONSE SIDE -- non-compliant tool_call ids.

Why that one exists: Vibe generates OpenAI-style tool_call ids ("call_" + 24 hex
chars). mistral_common's strict request validator
(protocol/instruct/validator.py) requires tool_call.id and tool_call_id to
match ^[a-zA-Z0-9]{9}$ exactly -- so a Vibe conversation that echoes its own
prior assistant tool_call.id back as a tool-result message's tool_call_id
gets rejected by SGLang on the very next turn. Root-caused via bisection
replay of captured request bodies down to a minimal reproducible curl case
(see notes/ for the full writeup). SGLang's own tool-call-parser generates
compliant 9-char ids, but Vibe's harness does not, and there is no known
Vibe-side config to change its id format.

This proxy sits between Vibe and SGLang, rewriting only the ids -- Vibe then
stores and echoes back the *rewritten* compliant id on its own, so no
request-side fix is needed for that one, only response-side.

Also tallies token usage (Sec. 12: "tokens[swarm]" comes from each
response's `usage` object). Vibe itself never surfaces per-call usage to
anything outside its own process, so this proxy -- the one place that
actually sees every raw SGLang response -- is where that has to be counted.
Run one instance per swarm (each on its own port, same upstream) so the
`/usage` endpoint gives a real per-swarm total, not a mixed one.

No timeout on the forward to UPSTREAM: an earlier revision hardcoded
timeout=180 (and timeout=30 on the GET passthrough) here, on top of the
plain SGLang round trip Vibe itself would have made unmediated -- neither
number was ever validated against how long a real completion call can take,
and a socket timeout isn't even caught by the one except clause below, so
it would have killed the request with no response sent back to Vibe at
all. Removed; this now blocks exactly as long as SGLang takes to answer.

Usage: run this on the same host as the SGLang server (or tunneled to it),
then point Vibe's config at this proxy's port instead of SGLang's port
directly.
    python3 harness/id_fix_proxy.py [listen_port] [upstream_url]
    # defaults: listen_port=8899, upstream_url=http://localhost:30000
    # GET /usage -> {"prompt_tokens": N, "completion_tokens": N, "requests": N}
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


# Ceiling on a single turn's generation. ON by default -- unbounded generation
# is a hazard for any reasoning model, not just this one. Override with
# PROXY_MAX_TOKENS=0 to restore vanilla behaviour.
MAX_TOKENS = int(os.environ.get("PROXY_MAX_TOKENS", "2048"))


def cap_max_tokens(req_json):
    """Bound how long one turn may generate. Vibe sends neither `max_tokens`
    nor `stop` -- confirmed by capturing a real request body -- so SGLang
    generates until the model emits EOS or fills the 32,768-token context.

    With a hybrid reasoning model that is effectively unbounded. Run 24 died
    exactly this way: SGLang showed `#running-req: 2, #queue-req: 0` with
    `#token` climbing steadily (11,634 -> 13,415 over 29 seconds) -- nothing
    queued, nothing stalled, just one turn generating for minutes. All eight
    agents were still inside their FIRST response when the 600s deadline
    killed them, so no session directory was ever written and the proxy
    tallied zero requests (usage is counted on the response, and no response
    ever came back). It looked exactly like a startup hang and was not one.

    2048 is generous for "some reasoning plus one tool call" and bounds a turn
    to ~34s at the 60 tok/s this pod sustains. Applied identically to both
    swarms, so it cannot skew warm against cold."""
    if MAX_TOKENS and isinstance(req_json, dict) and not req_json.get("max_tokens"):
        req_json["max_tokens"] = MAX_TOKENS
    return req_json


DISABLE_THINKING = os.environ.get("PROXY_DISABLE_THINKING") == "1"


def disable_thinking(req_json):
    """Opt-in, off by default: ask Qwen3 to skip its reasoning pass.

    Qwen3 is a hybrid reasoning model and emits `reasoning_content` before its
    answer. Measured over run 19's 83 assistant turns: 131,751 characters of
    reasoning against 11,184 characters of actual content -- **92% of every
    token the model generated was thinking**, 1,587 chars per turn versus 135.

    That is the whole throughput story on this pod. SGLang reports ~155 tok/s
    aggregate across 10 concurrent requests (~15 tok/s per agent) with
    `#queue-req: 0`, so nothing is waiting for admission -- the card is simply
    decoding, and 92% of what it decodes is discarded reasoning. Each turn
    spends roughly 26 seconds thinking to produce about 2 seconds of tool call.

    `enable_thinking` is Qwen's own chat-template switch, passed through
    SGLang's `chat_template_kwargs`. Vibe never sends it, so it is injected
    here -- identically for both swarms, so it cannot skew warm against cold.

    OFF BY DEFAULT, and it should stay off for the real demo. Qwen3 is a cheap
    stand-in; the target model is Mistral Small 4. Tuning the pipeline around
    the stand-in's reasoning mode is exactly the mistake of optimising for a
    model the demo does not use. Enable it (PROXY_DISABLE_THINKING=1) to answer
    one specific question -- can this harness converge at all when the model is
    not spending 92% of the clock thinking -- not as a standing setting."""
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
            UPSTREAM + self.path, data=body, headers={"Content-Type": "application/json"}, method="POST"
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
        req = urllib.request.Request(UPSTREAM + self.path, method="GET")
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
