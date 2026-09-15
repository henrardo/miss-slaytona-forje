#!/usr/bin/env python3
"""Web search MCP server, stdio transport. Registered for every agent, warm and
cold alike -- a baseline capability, not a memory advantage, so it must be
identical in both swarms or it becomes a confound.

One tool: `lookup(query)`, published to the model as `web_lookup` (Vibe names
MCP tools f"{alias}_{tool}" and this server is registered under alias "web").

    Deliberately not named `search`: render_config's `disabled_tools` kills
    Vibe's native `web_search` by name *after* MCP registration, so reusing
    that name would disable this server's tool too.

    Deliberately not offering a `fetch` either: Vibe already ships a native
    `web_fetch` (httpx + markdownify, no API key, no rate limit) and it works.
    An MCP tool named `fetch` would publish as `web_fetch` and collide with it.
    Reading a page is already covered; only search was missing.

Vibe's native `web_search` is the one that does not work here: it routes
through Mistral's hosted API, and this repo's MISTRAL_API_KEY returns
`429 Rate limit exceeded` on every call (re-confirmed 2026-09-13 against a
bare `mistral-small-latest` completion, so the key is exhausted outright, not
just the bundled feature). That tool stays disabled; this is the replacement.

Why any of this is needed: migrating
`fastapi_mail/email_utils/email_check.py` means replacing
`EmailStr.validate(email)` with a *different package* -- `email_validator`
(`validate_email`, `EmailNotValidError`, `.normalized`). The traceback says
`EmailStr has no attribute validate`, which never names another library, so a
model that does not already know the package cannot derive it. Without a
working lookup that file is unreachable and the demo cannot converge for
reasons that have nothing to do with agent memory.

=== WHY THIS LIVES IN ITS OWN VENV =========================================

This server runs from `harness/web-tools/.venv`, NOT from `harness/.venv`.

`mistral-vibe` pins `mcp==1.28.1`. `fastmcp` requires `mcp>=2`. Installing
fastmcp beside Vibe silently upgrades `mcp` to 2.2.0 and Vibe's own MCP
subsystem then fails to import at all:

    ImportError: cannot import name 'RequestContext' from 'mcp.shared.context'

-- which means *every* MCP server disappears, not just this one. An MCP stdio
server is a separate process talking JSON-RPC over a pipe; it shares nothing
with its client but the protocol. Giving it its own venv is what the
architecture already implies, and it keeps harness/.venv byte-vanilla, which
is a hard requirement of this project (see README.md).

A server that raises on import dies before it speaks protocol, and Vibe
surfaces that only as "MCP stdio discovery failed: Connection closed": the
tool silently vanishes from the model's tool list with nothing in the run
output to say so. That is exactly what happened across the 2026-09-13 run
series -- `fastmcp` and `openai` were missing from the venv this server was
launched with, every agent ran with no web access at all, and it read as a
model choosing not to search. orchestrator/run.py's preflight() now starts
every registered MCP server and lists its tools so this cannot recur.

Install:  cd harness/web-tools && uv venv .venv \
          && VIRTUAL_ENV=$PWD/.venv uv pip install -r requirements.txt

Required environment variable:
    OPENAI_API_KEY
Optional:
    WEB_SEARCH_MODEL   defaults to "gpt-5.2"
"""
from __future__ import annotations

import os

from fastmcp import FastMCP
from openai import AsyncOpenAI

MODEL = os.environ.get("WEB_SEARCH_MODEL", "gpt-5.2")

server = FastMCP("web")
_client: AsyncOpenAI | None = None

# The agents asking these questions are small models mid-migration. A prose
# summary that says "use EmailStr and install email-validator" is worse than
# useless to them -- it reads as confirmation that the pydantic-only approach
# they already tried is correct. What they need is the import line and the call
# signature. Answers are steered to that shape here rather than in each agent's
# prompt, so both swarms get it identically and neither is prompt-engineered.
ANSWER_STYLE = (
    "You are answering a coding agent mid-migration, not a human reader.\n"
    "Search the web and read the actual sources before answering.\n\n"
    "Answer with:\n"
    "1. The exact import line(s) needed.\n"
    "2. The exact replacement call, with its real signature and arguments.\n"
    "3. A minimal before/after code snippet.\n"
    "4. The source URLs you used.\n\n"
    "If the answer is that some API moved to a different package, say the "
    "package name explicitly and show how to call it -- do not just say the "
    "old name still works. If you are not sure, say so rather than guessing."
)


@server.tool
async def lookup(query: str) -> str:
    """Search the web and return a direct answer with source URLs. Use this
    whenever pydantic v2 has removed or moved something and you need to know
    what replaces it -- especially when the replacement may live in a different
    package, which a traceback will never tell you. Ask a specific question,
    e.g. "pydantic v2 replacement for EmailStr.validate()". Follow up with
    `web_fetch` on any URL whose detail you need."""
    response = await _get_client().responses.create(
        model=MODEL,
        instructions=ANSWER_STYLE,
        input=query,
        tools=[{"type": "web_search"}],
    )
    return response.output_text.strip() or "No results found."


def _get_client() -> AsyncOpenAI:
    """Lazily constructed. Building the client at import time makes a missing
    OPENAI_API_KEY a startup crash, which Vibe reports only as "Connection
    closed" -- indistinguishable from any other failure."""
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


if __name__ == "__main__":
    server.run()
