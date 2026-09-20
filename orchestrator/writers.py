"""Who writes the skill: the agent itself, or a stronger external model.

These are not the same experiment, and the difference should be stated
rather than buried in a flag.

    AgentWriter    the warm agent rewrites its own procedure, on the same
                   served model, with memory tools it chooses to use. This
                   is the mission's original claim -- organic
                   self-improvement -- and the skill is the agent's own
                   work.

    ExternalWriter a larger model is handed the traces and asked to write
                   the procedure. The claim becomes "a strong model can
                   distil a usable procedure from these traces", which is
                   a different and also useful result. It is NOT
                   self-improvement, and any write-up has to say so.

The practical reason the second exists: Mistral Small 4 kept producing
AIP that was correct in substance and invalid as YAML -- an unquoted
colon in one run, a partially-quoted list item in the next -- burning
three turns each time. Whether that is worth fixing with a bigger writer
or a better prompt is the operator's call; both are available.

The external writer gets its evidence IN THE PROMPT, because an API call
has no MCP tools and cannot query the graph. That is another asymmetry
worth remembering when comparing the two: the agent chooses what to look
at, the external model is handed a selection.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def openai_url(base_url: str | None = None) -> str:
    """The completions endpoint, optionally against another host.

    An EXPLICIT PARAMETER, never an environment variable. The first
    version of this read `OPENAI_BASE_URL` -- which is the OpenAI SDK's
    own standard variable -- so the rehearsal setting it redirected every
    OpenAI client in the process, including neo4j-agent-memory's entity
    extractor and embedder, and the run died in `add_message` with
    "Failed to extract entities: Connection error." A process-wide switch
    to redirect one caller is not a seam, it is a trap.

    The seam exists so the rehearsal can drive the REAL ExternalWriter
    against `tests/fake_model_server`: this is the production default
    writer now, and both bugs that cost pod runs on 2026-09-18 were in
    code the rehearsal could not reach.
    """
    if not base_url:
        return OPENAI_URL
    return f"{base_url.rstrip('/')}/chat/completions"
DEFAULT_EXTERNAL_MODEL = "gpt-5.5-2026-04-23"
EXTERNAL_TIMEOUT_S = 300.0


def author_model() -> str:
    """Which model writes the skill. `OPENAI_AUTHOR`, or the default.

    A named environment variable rather than a flag default, because
    "which model authors the procedure" is a standing property of the
    experiment, not a per-invocation choice: AIP's own guidance is that
    authoring needs the largest frontier model available, while the
    resulting skill exists to make a SMALL model competitive. Getting
    this wrong silently invalidates a run's skill-quality evidence, and
    it already has -- three pod runs on 2026-09-18 let the 119B attempt
    model rewrite its own procedure, and it collapsed 24 steps to 11.
    """
    return os.environ.get("OPENAI_AUTHOR") or DEFAULT_EXTERNAL_MODEL


class AgentWriter:
    """The warm agent writes its own skill, through Vibe on the pod."""

    name = "agent"

    def __init__(self, workspace: Any) -> None:
        self._ws = workspace

    @property
    def uses_graph_tools(self) -> bool:
        return True

    def out_path(self) -> str:
        return self._ws.distill_skill_path()

    async def write(self, prompt: str, *, resume: bool) -> tuple[str, list[dict]]:
        """Returns (proposal, stream entries). The entries are how the
        memory-tool calls get counted."""
        self._ws.clear_distilled()
        _, stdout = await self._ws.run_distill(
            prompt, timeout_s=600.0, resume=resume)
        return self._ws.read_distilled() or "", self._ws.stream_entries(stdout)


class ExternalWriter:
    """A larger model writes the skill, over the API.

    Returns no stream entries: it has no tools, so `memory_tool_calls`
    is legitimately zero and the metrics say so rather than implying the
    writer chose not to query.
    """

    name = "external"

    def __init__(self, model: str | None = None,
                 api_key: str | None = None,
                 base_url: str | None = None) -> None:
        # The MODEL comes from OPENAI_AUTHOR. AIP's own guidance is that
        # authoring needs the largest frontier model available while
        # consumption does not, so which model authors is a deliberate,
        # separately-set choice rather than a constant in this file --
        # and all three runs of 2026-09-18 authored with the small local
        # model because the default was "agent" and nobody passed a flag.
        self.model = model or author_model()
        # `None` means "take it from the environment"; an explicit ""
        # means the caller has none, and must not silently fall back to
        # whatever happens to be exported.
        self._key = (os.environ.get("OPENAI_API_KEY", "")
                     if api_key is None else api_key)
        if not self._key:
            raise RuntimeError(
                "ExternalWriter needs OPENAI_API_KEY. Without it the "
                "distillation turn would fail after the attempt, silently "
                "keeping the previous skill version.")
        self._base_url = base_url
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    @property
    def uses_graph_tools(self) -> bool:
        return False

    def out_path(self) -> str:
        # It returns the file's content directly; the path is only ever
        # quoted in the prompt, so it names what it is rather than a
        # location on a machine this writer cannot see.
        return "the improved SKILL.md"

    async def write(self, prompt: str, *, resume: bool) -> tuple[str, list[dict]]:
        import asyncio
        text = await asyncio.to_thread(self._call, prompt)
        return text, []

    def _call(self, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content":
                 "You write AIP skill files. Reply with the file's exact "
                 "contents and nothing else: no explanation, no surrounding "
                 "code fence. Start at the opening `---` of the frontmatter."},
                {"role": "user", "content": prompt},
            ],
            # RETAINED ON THE PLATFORM, so the operator can read the exact
            # prompt and reply rather than take the harness's word for it.
            #
            # Chat Completions are not kept for the dashboard's Logs view
            # unless this is set. The symptom: the web tool's `gpt-4o-mini`
            # calls appeared there and the distiller's `gpt-5.6-sol` calls
            # did not, on the same project key -- because the web server
            # uses the Responses API (harness/web-tools/server.py:127) and
            # this uses Chat Completions. The calls were real and billing
            # the whole time; only this view was blind.
            #
            # `metadata` so a distillation is findable among them.
            "store": True,
            "metadata": {"source": "miss-slaytona-forje",
                         "role": "aip-skill-author"},
        }
        request = urllib.request.Request(
            openai_url(self._base_url), data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=EXTERNAL_TIMEOUT_S) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            raise RuntimeError(
                f"{self.model} refused the distillation call: "
                f"{exc.code} {detail}") from None
        usage = payload.get("usage") or {}
        self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
        text = (payload["choices"][0]["message"].get("content") or "").strip()
        return strip_fence(text)


def strip_fence(text: str) -> str:
    """Unwrap an outer ```markdown fence if the model added one.

    A SKILL.md contains its own ```yaml fence, so a model told "reply with
    the file" often wraps the whole thing in a second fence. The file must
    start at `---`, and the alternative to handling it here is losing a
    turn of the repair budget to packaging rather than content.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    # Drop the LAST fence line, not the first one found -- the body's own
    # ```yaml block closes with a fence too.
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "```":
            del lines[i]
            break
    return "\n".join(lines).strip()
