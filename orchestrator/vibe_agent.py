"""The migration loop (Sec. 6), M3 revision 2: Mistral Vibe (the harness
Devstral was actually post-trained around -- its own chat template hardcodes
a "Mistral Vibe" system persona) replacing dsh, which turned out to produce
unreliable/malformed tool calls against this model under generic OpenAI-style
"auto" tool-choice. See the plan this was built from for the full diagnosis.

Corrected 2026-09-13: edits are local, Daytona is only for running and
validating. An earlier revision routed everything -- reads, edits, and
checks -- through Daytona's MCP server, with `--enabled-tools 'daytona_*'`
disabling every one of Vibe's own native tools (edit/write_file/read_file/
bash). That meant Vibe had no real edit primitive, only a raw remote shell,
and it wasn't a deliberate choice -- it was never checked against what
`daytona_*` actually included (it swept in `daytona_computer_use_*`, a
GUI-automation tool with nothing to do with code, which three separate
agents got stuck in during an hour-long run). The actual, correct division:
Vibe runs locally, plain, no `--enabled-tools` filter at all -- its own
native tools operate on a real local checkout of the codebase in `vibe_cwd`.
Vibe never registers or talks to Daytona. This module's own
migrate_codebase() calls Daytona directly (via SandboxPool.run_pytest(),
Sec. 6) between attempts, uploading whatever the local tree currently looks
like into a fresh, disposable sandbox to run the real test suite -- that
result, not Vibe's own exit status, decides success and is what gets fed
back into the next attempt's prompt.

migrate_codebase() (Sec. 6, M4) gives one agent one whole-codebase task --
"migrate this codebase from Pydantic v1 to Pydantic v2" -- not a single
claimed file; see its own docstring and orchestrator/run.py's module
docstring for the memory wiring.
"""
from __future__ import annotations

import ast
import asyncio
import difflib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Awaitable, Callable

from neo4j_agent_memory.schema.models import TraceOutcome

from orchestrator.manifest import REPO_ROOT
from orchestrator.memory import EMBEDDING_MODEL, NEO4J_PASSWORD, NEO4J_URI, ScopedMemory
from orchestrator.sandbox import SandboxPool

HARNESS_DIR = REPO_ROOT / "harness"
VIBE_BIN = HARNESS_DIR / ".venv" / "bin" / "vibe"
VIBE_HOME = HARNESS_DIR / ".vibe"
CONFIG_TEMPLATE = HARNESS_DIR / "vibe-config.template.toml"
CONFIG_GENERATED = VIBE_HOME / "config.toml"

# The interpreter an agent's own shell gets, holding the fixture's pydantic-v2
# requirements and nothing else. Built once per machine by ensure_agent_venv().
#
# Before this existed, agents inherited the orchestrator's `VIRTUAL_ENV`
# wholesale, so `python -m pytest` in an agent's checkout resolved pydantic out
# of miss-slaytona-forje/.venv -- along with neo4j, the Daytona SDK and
# neo4j-agent-memory itself. That made the suite runnable locally by accident,
# and made the cold arm's "zero Neo4j contact" claim true only because no cold
# agent happened to try.
AGENT_ROOT = Path(os.environ.get("M4_AGENT_ROOT", "/tmp/msf-agents")).resolve()
AGENT_VENV = AGENT_ROOT / ".fixture-venv"
AGENT_PYTHON = AGENT_VENV / "bin" / "python"

# Stripped from every agent's environment, warm and cold alike. None of these
# are needed to do the task, and each one is a capability the agent should not
# have: DAYTONA_API_KEY reaches the sandboxes the orchestrator grades with,
# OPENAI_API_KEY is billable and is already delivered to the MCP servers that
# need it via `vibe mcp add --env` (so it does not have to be in the parent
# environment), and MISTRAL_API_KEY would let Vibe silently fall back to a
# hosted model instead of the local one this run is measuring.
_STRIPPED_ENV = ("DAYTONA_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY",
                 "NEO4J_URI", "NEO4J_PASSWORD", "NEO4J_USER")

# The web-search MCP server and the interpreter it runs under. Separate venv on
# purpose -- see the note at its registration in render_config().
WEB_TOOLS_DIR = HARNESS_DIR / "web-tools"
WEB_TOOLS_PYTHON = WEB_TOOLS_DIR / ".venv" / "bin" / "python"
WEB_TOOLS_SERVER = WEB_TOOLS_DIR / "server.py"

# neo4j-graphrag retrieval over the same graph, warm agents only. Its own venv
# for the same mcp-version reason as web-tools above.
GRAPHRAG_MCP_DIR = (
    HARNESS_DIR / "neo4j-mcp-experiments" / "servers" / "mcp-neo4j-vector-graphrag"
)

# The one thing this server does not ship, because it cannot: the Cypher that
# knows this graph's shape. It is a documented input (RETRIEVAL_QUERY) and must
# return `text`, `metadata` and `score`. `node` and `score` come from the vector
# search and must not be re-declared.
#
# Searches task_embedding_idx -- (:ReasoningTrace).task_embedding -- then walks
# HAS_STEP to the thought/action/observation chain, which is the part nothing
# else reads back: neo4j-agent-memory's own get_context returns each trace's
# task and outcome only.
GRAPHRAG_RETRIEVAL_QUERY = (
    "OPTIONAL MATCH (node)-[:HAS_STEP]->(s:ReasoningStep) "
    "WITH node, score, s ORDER BY s.step_number "
    "WITH node, score, collect(s)[0..8] AS steps "
    "RETURN 'Past attempt by ' + coalesce(node.session_id,'?') + "
    "'\\nIt started from: ' + coalesce(node.task,'') + "
    "'\\nHow it ended: ' + coalesce(node.outcome,'(no verdict)') + "
    "'\\nWhat it did:\\n' + reduce(acc = '', st IN steps | "
    "acc + '  - ' + coalesce(st.action,'?') + ': ' + "
    "coalesce(st.thought,'') + ' -> ' + coalesce(st.observation,'') + '\\n') "
    "AS text, "
    "{success: node.success, metrics: node.metrics_json} AS metadata, "
    "score"
)

# No fixed attempt cap -- migrate_codebase() retries until `deadline` (a shared,
# run-level wall-clock budget, Sec. 8's HARD_DEADLINE_S) passes, not until a
# small attempt count is exhausted. A per-file cap like the old MAX_ATTEMPTS=3
# starves a real agent of the iteration room it needs and produces results
# that say nothing about the model's actual ability -- see the spec's
# 2026-09-13(b) PROGRESS note under Sec. 6/Sec. 8 for the full reasoning.
#
# No per-invocation timeout either, beyond that same deadline. An earlier
# revision additionally wrapped every single vibe subprocess call in its own
# 180-second cap "for safety" -- a number never validated against this
# model's actual latency, and confirmed live (2026-09-13) to be firing on
# 100% of attempts: Vibe never once reached its own natural stopping point,
# so every result observed under that cap was an artifact of the cap, not
# of the model. The only real, load-bearing time limit is `deadline` itself;
# Vibe now gets exactly whatever is left of it, nothing invented on top.
# Likewise the independent pytest check below gets no timeout of its own --
# Daytona's own `process.exec` already defaults to unbounded (timeout=None)
# when none is given, which was the correct default to defer to all along.

Emit = Callable[..., Awaitable[Any]]


@dataclass
class MigrationResult:
    success: bool
    attempts: int
    # How far this agent actually got, so warm and cold can be compared when
    # neither converges -- which so far is every run.
    #
    # Raw token totals cannot do that job. Run 28 reported token_ratio 1.543,
    # which reads as "memory saved 35%", while warm had made 71 LLM calls to
    # cold's 132: warm was cheaper because it did less, not because it did
    # better. Per completed attempt warm actually cost more (113.6k vs 94.4k
    # tokens), and nothing in the summary said so.
    #
    # `errors_cleared` counts distinct pytest error signatures the agent moved
    # the suite through. On this fixture the failures are a chain -- each fix
    # reveals the next one -- so it is a genuine depth measure, and it is read
    # off the orchestrator's own independent test runs, never the model's
    # claims. `best_passed` is the high-water mark of tests passing.
    errors_cleared: int = 0
    best_passed: int = 0
    last_signature: str | None = None


def render_config(
    base_url: str,
    model: str,
    *,
    vibe_home: Path = VIBE_HOME,
    active_model_alias: str = "devstral-local",
    auto_compact_threshold: int | None = None,
    memory_enabled: bool = False,
) -> None:
    """Render a clean $vibe_home/config.toml: the hand-declared self-hosted
    provider/model route (confirmed against
    docs.mistral.ai/vibe/code/cli/offline-models), plus the `memory` MCP
    block if requested. No Daytona MCP registration -- Vibe edits the local
    checkout directly with its own native tools; Daytona is the
    orchestrator's own tool, called directly by migrate_codebase(), never
    exposed to Vibe. Starts from a deleted file each render so repeated
    runs never accumulate duplicate [[providers]]/[[models]] blocks.

    `vibe_home` defaults to the module constant so existing single-swarm
    callers (scripts/run_m3.py) are unaffected; pass a distinct path per
    swarm when running warm and cold agents against different proxy ports
    in parallel -- each needs its own config.toml, api_base, and session
    logs, not a shared one.

    `auto_compact_threshold` matters for small-context models (e.g. Qwen's
    32,768-token window): Vibe's own default (200,000) assumes a
    large-context model and never fires before the model's own context
    limit does. Omit for models where the default is already appropriate.

    `memory_enabled` is what gives this agent memory at all -- leave it False
    (as orchestrator/run.py does for every cold agent) and no
    neo4j-agent-memory MCP block is ever written, so that agent has no path to
    Neo4j whatsoever. This is not a read/write toggle; it's whether the tools
    exist in this agent's config.

    A `web` MCP block is registered for EVERY agent, warm and cold alike
    (harness/web-tools/server.py, published as `web_lookup`). Unlike
    memory, this is not part of the comparison -- it is a baseline
    capability the task actually requires. One of the three files to migrate
    needs `EmailStr.validate()` replaced with the `email_validator` package,
    and the traceback (`EmailStr has no attribute validate`) never names
    another library, so a model without lookup cannot get there: measured
    over 45 minutes, every agent plateaued at 2 of 3 files. Identical in
    both swarms, so it cannot skew warm vs cold.

    It is published as `web_lookup`, deliberately not `web_search`: Vibe
    names MCP tools `f"{alias}_{tool}"`, and `disabled_tools` (below) kills
    the native `web_search` by name *after* MCP registration, so reusing
    that name would silently disable this server's tool as well."""
    config_generated = vibe_home / "config.toml"
    vibe_home.mkdir(parents=True, exist_ok=True)
    if config_generated.exists():
        config_generated.unlink()
    # active_model MUST be written before any [[table]] array header -- TOML
    # parses bare `key = value` lines as belonging to the last-opened table,
    # so writing it after `vibe mcp add`'s [[mcp_servers]] block silently
    # attaches it to that entry instead of the top level (confirmed by
    # reproducing exactly this: Vibe fell back to its own built-in
    # Mistral-hosted default model and demanded MISTRAL_API_KEY).
    # `disabled_tools` belongs here, in the config, NOT on the command line.
    # _run_vibe used to pass `--disabled-tools web_search` and it silently
    # did nothing: the 2026-09-13 run made 24 `web_search` calls, all from
    # the main session, every one returning `429 web_search rate limit
    # reached`. Confirmed by capturing the actual request body -- with the
    # flag alone the tool is still in the `tools` array sent to the model;
    # with this config key it is gone. Same key, same effect, for every
    # agent in both swarms.
    # `disabled_skills` is Vibe's own config key, applied identically to both
    # swarms. Every builtin skill ships under vibe/plugins/builtins/vibe/skills
    # -- `vibe`, `skill-creator`, `create-plugin`, `worktree` -- and all four
    # document *how to use Vibe*, not how to do any user task. For a headless
    # agent given one migration they are pure noise.
    #
    # Measured in run 12: the agents' opening move was "I should check if there
    # are any existing skills that can help with this migration", and the
    # `vibe` skill returned 54,708 characters -- roughly 13,700 tokens, 42% of
    # Qwen3-8B's 32,768-token window -- five separate times. Skills accounted
    # for 284,428 of the run's 314,652 characters of tool results, 90%, while
    # the actual work (edit/grep/read_file) came to under 11,000.
    #
    # Not a small-model accommodation: Vibe's self-documentation is irrelevant
    # to a pydantic migration on any model. It is simply cheaper to be wrong
    # about on a 256k context than on a 32k one.
    # `task` is disabled on measured evidence, not preference, and identically
    # for both swarms.
    #
    # Run 14: five `task` calls spawned `explore` subagents that between them
    # accounted for 527 of the run's 673 messages -- 78% of the whole token
    # budget. The largest made 47 `read_file` calls and ~100 turns before
    # returning, as its finished answer:
    #
    #     from pydantic.main import BaseModel  # v2 import
    #
    # which is wrong (it is `from pydantic import BaseModel`). `explore`
    # subagents are read-only, so none of that could become an edit even if it
    # had been right, and the parent blocks while they run -- 17 attempts
    # started in the run, only 9 finished.
    #
    # `skill` goes with `disabled_skills`: with every skill disabled the tool
    # can only ever answer "Available skills: none", so offering it is offering
    # a guaranteed dead end. Run 15's agents called it 8 times, every call
    # inventing a skill they hoped existed -- "pydantic_v2_migration",
    # "pydantic_v2_migrator", "pydantic_v2_migrate".
    #
    # REVISIT ON THE TARGET MODEL. Unlike `web_search` (a dead API key) and
    # `disabled_skills` (Vibe's own docs, irrelevant to any user task), this
    # one is a judgement about *this* model: an 8B delegating its entire task
    # to a read-only explorer is a model-quality failure, and Mistral Small 4
    # at 256k context may well use subagents productively. It is disabled here
    # because a swarm that spends 78% of its budget on unusable output cannot
    # converge, and a demo that never converges measures nothing.
    config_generated.write_text(
        f'active_model = "{active_model_alias}"\n'
        'disabled_tools = ["web_search", "task", "skill"]\n'
        'disabled_skills = ["*"]\n'
    )

    env = dict(os.environ)
    env["VIBE_HOME"] = str(vibe_home)

    # Web search, for BOTH swarms. Not a memory advantage -- a baseline
    # capability the task genuinely requires, so it is registered identically
    # for warm and cold and cannot skew the comparison. See
    # harness/web_search_mcp_server.py for why the task is unsolvable without
    # it: one of the three files needs a package substitution the traceback
    # never names. MCP stdio servers inherit only a minimal curated env
    # (mcp.client.stdio.get_default_environment), so OPENAI_API_KEY has to be
    # passed explicitly via --env or the server starts up without it.
    # Launched from its OWN venv (harness/web-tools/.venv), not this process's
    # interpreter and not harness/.venv. fastmcp requires mcp>=2 while
    # mistral-vibe pins mcp==1.28.1, and installing them together breaks Vibe's
    # MCP subsystem outright ("cannot import name 'RequestContext'"), which
    # silently removes *every* MCP tool from the model. An MCP stdio server
    # shares nothing with its client but the protocol, so it gets its own
    # environment. See harness/web-tools/server.py.
    subprocess.run(
        [
            str(VIBE_BIN), "mcp", "add", "web",
            "--transport", "stdio",
            "--command", str(WEB_TOOLS_PYTHON),
            "--arg", str(WEB_TOOLS_SERVER),
            "--env", f"OPENAI_API_KEY={env['OPENAI_API_KEY']}",
        ],
        env=env,
        check=True,
        capture_output=True,
    )

    if memory_enabled:
        # neo4j-agent-memory's MCP server, registered exactly as its README
        # says to register it:
        #
        #     uvx "neo4j-agent-memory[mcp]" mcp serve --password <pw>
        #
        # That is the whole install. uvx fetches the package (with the [mcp]
        # extra) and runs it; nothing here is built, wrapped, vendored or
        # renamed. The only two additions are arguments the README itself
        # documents: --uri, because this project's Neo4j is the Docker
        # container on 7688 rather than the default 7687, and OPENAI_API_KEY,
        # because embeddings need it (MCP stdio servers inherit only a minimal
        # curated env -- mcp.client.stdio.get_default_environment -- so it has
        # to be passed explicitly or the server starts without it).
        #
        # Everything else that used to be on this command line is gone:
        # --profile core (dropped 10 of the 16 tools for no measured reason),
        # --transport stdio (already the default, and passed twice),
        # --session-strategy/--user-id, and a local .venv path in place of
        # uvx. Each was something I added that could be wrong, and none of it
        # was asked for. Before that it was worse: harness/memory_mcp_server.py,
        # a hand-written server exposing three tools that exist nowhere in the
        # package (recall_similar_migrations, recall_known_patterns,
        # record_pattern).
        #
        # Registered for warm agents only. A cold agent never gets this block,
        # so it has no path to Neo4j at all -- not a gated one, none.
        subprocess.run(
            [
                str(VIBE_BIN), "mcp", "add", "neo4j-agent-memory",
                "--transport", "stdio",
                "--command", "uvx",
                # [mcp,openai], not [mcp]. The README one-liner is
                # `uvx "neo4j-agent-memory[mcp]" mcp serve --password <pw>`,
                # and that is correct as far as it goes -- but the package's
                # default embedder is OpenAI text-embedding-3-small, and the
                # [mcp] extra does not pull the openai client in. Without it
                # the server starts fine, publishes all 16 tools, and answers
                # every embedding-backed call with:
                #
                #     Error getting context: OpenAI package not installed.
                #     Install with: pip install neo4j-agent-memory[openai]
                #
                # So memory_get_context and memory_search -- the two tools the
                # agent would actually retrieve with -- returned an error
                # string rather than memories, silently, for every run from the
                # switch to uvx onward. Caught only by calling the tool for
                # real rather than trusting that the server had come up.
                #
                # The MCP server builds its OWN client, so its embedder must match
                # this orchestrator's exactly or it opens the six vector
                # indexes at the wrong dimension and refuses to start with
                # EmbeddingDimensionMismatchError. Passed explicitly below
                # rather than left to either side's default. The extra has to
                # match the embedder too -- [mcp] alone does not pull in the
                # OpenAI client.
                # `--with httpx` works around a packaging bug in the published
                # package (seen on 0.6.0, which is what uvx resolves to).
                # `_connect_bolt()` imports neo4j_agent_memory.nams._unsupported,
                # which pulls nams/__init__ -> nams/client -> nams/transport ->
                # `import httpx`. So the *bolt* path needs httpx, but httpx is
                # declared only by the `nams` extra; [openai] brings openai 3.x,
                # which depends on httpx2, not httpx. The server therefore dies
                # on import with ModuleNotFoundError: No module named 'httpx'.
                #
                # Vibe reports that only as "MCP stdio discovery failed:
                # Connection closed" -- all 16 memory tools silently absent from
                # every warm agent, which is indistinguishable from a model that
                # chose not to call them. Caught by check_mcp_servers(), not by
                # anything in a run summary.
                #
                # httpx is supplied directly rather than by adding the `nams`
                # extra: the dependency is what is missing, and this project
                # does not use NAMS.
                # `--arg=--with`, not `--arg --with`: argparse reads a bare
                # `--with` as a flag of its own and fails with
                # "argument --arg: expected one argument". Same reason the
                # --uri/--password/--embedding args below use the = form.
                "--arg=--with", "--arg", "httpx",
                "--arg", "neo4j-agent-memory[mcp,openai]",
                "--arg", "mcp", "--arg", "serve",
                f"--arg=--uri={NEO4J_URI}",
                f"--arg=--password={NEO4J_PASSWORD}",
                # Both documented flags, both shown in `mcp serve --help`
                # (which uses this exact model as its example). `--backend
                # bolt` is pinned because the server otherwise switches itself
                # to the hosted NAMS service whenever MEMORY_API_KEY happens
                # to be in the environment, which is a different product.
                f"--arg=--embedding={EMBEDDING_MODEL}",
                "--arg=--backend=bolt",
                # The embedder is OpenAI's, and MCP stdio servers inherit only
                # a minimal curated environment, so the key has to be handed
                # over explicitly or every embedding-backed tool answers with
                # an error string instead of memories.
                "--env", f"OPENAI_API_KEY={env['OPENAI_API_KEY']}",
            ],
            env=env,
            check=True,
            capture_output=True,
        )

        # mcp-neo4j-vector-graphrag, run as shipped. Warm only, and inside this
        # `if` for that reason: it reads Neo4j, so a cold agent must not have it.
        #
        # Neo4j's own server for exposing neo4j-graphrag retrievers over MCP:
        # neo4j.com/blog/developer/neo4j-graphrag-retrievers-as-mcp-server/,
        # source at github.com/tomasonjo-labs/neo4j-mcp-experiments. Checked out
        # under harness/ and launched with `uv --directory ... run`, exactly the
        # invocation its README documents; uv resolves its deps from the repo's
        # own uv.lock, so it needs no venv of ours.
        #
        # It replaced a server I wrote by hand, which published two tools of my
        # own naming (`graph_reasoning`, `graph_entities`) around the same
        # retriever. This one is configured entirely through the environment --
        # INDEX_NAME, EMBEDDING_MODEL and RETRIEVAL_QUERY are its documented
        # inputs -- so the only thing left that is ours is the Cypher, which is
        # the one part that has to be.
        #
        # Publishes a single tool, `neo4j_vector`; Vibe prefixes MCP tools with
        # the server alias, so agents see `graphrag_neo4j_vector`.
        #
        # EMBEDDING_MODEL must match the embedder that wrote the vectors
        # (memory.py's EMBEDDING_MODEL) -- this server takes it in LangChain's
        # `provider:model` form.
        #
        # Every value goes via --env: MCP stdio servers inherit only a minimal
        # curated environment (mcp.client.stdio.get_default_environment), so
        # anything not listed here is simply absent in the server process.
        subprocess.run(
            [
                str(VIBE_BIN), "mcp", "add", "graphrag",
                "--transport", "stdio",
                "--command", "uv",
                "--arg=--directory", "--arg", str(GRAPHRAG_MCP_DIR),
                "--arg", "run", "--arg", "mcp-neo4j-vector-graphrag",
                "--env", f"NEO4J_URI={NEO4J_URI}",
                "--env", f"NEO4J_PASSWORD={NEO4J_PASSWORD}",
                "--env", f"NEO4J_USERNAME={os.environ.get('NEO4J_USERNAME', 'neo4j')}",
                "--env", f"NEO4J_DATABASE={os.environ.get('NEO4J_DATABASE', 'neo4j')}",
                "--env", f"OPENAI_API_KEY={env['OPENAI_API_KEY']}",
                "--env", "INDEX_NAME=task_embedding_idx",
                "--env", f"EMBEDDING_MODEL=openai:{EMBEDDING_MODEL.split('/')[-1]}",
                "--env", f"RETRIEVAL_QUERY={GRAPHRAG_RETRIEVAL_QUERY}",
            ],
            env=env,
            check=True,
            capture_output=True,
        )

    template = CONFIG_TEMPLATE.read_text()
    rendered = (
        template.replace("{{SGLANG_BASE_URL}}", base_url)
        .replace("{{SGLANG_MODEL}}", model)
        .replace('alias = "devstral-local"', f'alias = "{active_model_alias}"')
    )
    if auto_compact_threshold is not None:
        rendered += f"auto_compact_threshold = {auto_compact_threshold}\n"
    with config_generated.open("a") as f:
        f.write("\n" + rendered)


# Warm agents only, because only warm has these tools registered. Qwen3-14B
# called them zero times in 45 messages when they were merely available:
# run 62 ended with graphrag_calls=0 and mem_calls=0 while the agent used
# bash/grep/edit/read_file throughout. The tools were verified present in the
# config and published by their servers, so this is the model not reaching for
# them, not a dead server. Telling it what they are for is the difference
# between a tool that exists and a tool that gets used.
_MEMORY_TOOLS_GUIDE = (
    "You share a knowledge graph with the other agents working on this same "
    "migration, now and in earlier runs. Read it before you guess.\n\n"
    "- `graphrag_neo4j_vector(query)` -- pass the error you are looking at, "
    "verbatim. Returns what previous agents did about that exact error: each "
    "step they took, what they were thinking, and what came back. Use it before "
    "retrying anything that has already failed once, so you try something new "
    "instead of repeating a dead end.\n"
    "- `memory_search` / `memory_get_context` -- the same graph, searched over "
    "stored messages rather than reasoning steps.\n\n"
    "Call `graphrag_neo4j_vector` first when an attempt fails. If it comes back "
    "empty or unhelpful, fall back to `web_lookup`."
)


def _task_prompt(
    last_error: str | None,
    memory_context: str | None = None,
    memory_enabled: bool = False,
) -> str:
    """One instruction, whole codebase, exactly what a real user would type:
    "migrate this codebase from Pydantic v1 to Pydantic v2." The code is in
    Vibe's own current directory -- no sandbox id, no Daytona tool
    instructions, nothing about how to check the work, because Vibe can't
    check it: the real test suite runs separately, in Daytona, by the
    orchestrator, after Vibe's own turn ends (see migrate_codebase()). Vibe
    just edits, using whatever native tools it has, same as any local run.

    The retry prompt adds two lines, and both are harness responsibilities
    rather than prompt-engineering the result:

    * "Keep going until the suite passes" -- agents were ending turns with a
      summary and an offer ("let me know if you'd like me to continue"),
      which is the model deciding it is finished when it is not. Nothing
      else in the loop tells it otherwise, so progress plateaued at 2 of 3
      files while agents politely stopped.
    * A pointer at `web_lookup` whenever an import path is in doubt.
      `email_check.py` needs `EmailStr.validate()` replaced with the
      `email_validator` package, and the traceback never names another
      library; measured over 45 minutes, the tool sat unused and every agent
      plateaued. An earlier wording triggered only on "an API that pydantic
      v2 removed", which is not the error the agents actually hit: run 25's
      dominant failure was `NameError: name 'model_validator' is not
      defined`, a v2 API the model failed to *import*, not one v2 removed.
      The condition never matched, so the model guessed the import path
      instead -- `from pydantic.model_validators import ...`, which does not
      exist -- and web_lookup was called twice in 88 tool calls. The trigger
      now names the three error classes verbatim. Both swarms get this line
      identically, so it cannot skew warm vs cold."""
    base = (
        "Please migrate this codebase from Pydantic v1 to Pydantic v2.\n\n"
        "You can run the test suite yourself, here, in this directory. Run it "
        "exactly like this:\n\n"
        "    python -m pytest tests -q -x --tb=short 2>&1 | tail -30\n\n"
        "Do that after every change rather than assuming an edit worked -- it "
        "is the same suite your work is judged on, and with -x it stops at the "
        "first failure, so while anything is still broken it answers in "
        "seconds. Keep the `2>&1 | tail -30`: pytest writes collection errors "
        "to stderr, so without it you get an empty result and a non-zero exit "
        "instead of the error message.\n\n"
        "Read the failing test before you decide how to fix it. The files under "
        "`tests/` are read-only -- never edit them -- but they are the "
        "specification: they say which exception type, which package and which "
        "behaviour the code is expected to produce, and that is often something "
        "no traceback and no web search will tell you.\n\n"
        "`edit` matches `old_string` byte-for-byte, so read the file with "
        "`read_file` and copy the lines out of it before editing. Do not type "
        "from memory or reconstruct what you think is there: 43% of edits in "
        "the last run failed, most of them because `old_string` did not appear "
        "in the file. Use real newlines in `old_string`, not the two characters "
        "backslash-n. If a string occurs more than once, pass "
        "`replace_all: true`. Use paths relative to this directory, like "
        "`fastapi_mail/config.py`."
    )
    # Block B (Sec. 6.1): retrieved traces/patterns, placed before Block C
    # since Block C invalidates the cache from that point anyway -- memory
    # costs nothing extra placed here.
    if memory_enabled:
        base += "\n\n" + _MEMORY_TOOLS_GUIDE
    if memory_context:
        base = memory_context + "\n\n" + base
    if last_error:
        base += (
            f"\n\nA previous attempt left the code in its current state, and the official test "
            f"suite (run separately, by the grader) still failed with:\n```\n{last_error}\n```"
            "\n\nKeep going until the suite passes. You are not done because an edit landed "
            "or a file looks right -- only a passing suite is done. Use `web_lookup` before "
            "editing whenever you do not already know, exactly, where a pydantic v2 name "
            "lives: any NameError, ImportError or ModuleNotFoundError naming a pydantic "
            "symbol means the import path you used does not exist, and a second guess at it "
            "is no more likely to be right than the first was. Some replacements are not "
            "renames at all but a different package entirely."
        )
    return base


async def _run_vibe(
    task: str,
    timeout_s: float,
    *,
    vibe_home: Path = VIBE_HOME,
    cwd: Path = HARNESS_DIR,
    resume: bool = False,
) -> tuple[int, str]:
    """`timeout_s` is the caller's actual remaining run deadline, not an
    invented per-call cap -- if this fires, the run's own time budget is
    genuinely exhausted, not "vibe took longer than some arbitrary number
    we picked." A timeout here ends this one attempt; it is not a verdict
    on the model.

    `cwd` matters, not just `vibe_home`: Vibe's own config resolution
    (`HarnessFilesManager.config_file`) checks `<cwd>/.vibe/config.toml`
    FIRST, as a "project-local" layer, and only falls back to
    `VIBE_HOME`'s config.toml if that file doesn't exist -- the env var
    alone does not override an existing project-local config. Callers using
    a non-default `vibe_home` must pass a `cwd` whose own `.vibe` subfolder
    *is* that `vibe_home` (e.g. `vibe_home = cwd / ".vibe"`), or a stale
    `<cwd>/.vibe/config.toml` left over from another run silently wins
    instead. Confirmed by direct reproduction, not inferred: harness/'s own
    leftover `.vibe/config.toml` (stale Devstral config) overrode a
    correctly-rendered `vibe_home` every time, because HARNESS_DIR was
    still being used as `cwd` while `vibe_home` pointed elsewhere.

    No `--enabled-tools` filter: an earlier revision passed
    `--enabled-tools daytona_*` (plus `memory_*`), disabling every one of
    Vibe's own native tools (edit/write_file/read_file/bash) and forcing
    all work through a raw remote shell instead -- never deliberately
    decided, never checked against what the wildcard actually included.
    Omitting the flag restores Vibe's full native toolset, unfiltered,
    exactly as a local `vibe` invocation would have it; `memory_*` (our own
    registered MCP server) is included automatically since nothing is
    filtering it out.

    `web_search` is disabled, but in render_config()'s config.toml, not
    here. Passing `--disabled-tools web_search` on this command line was
    tried and does nothing: the 2026-09-13 run made 24 `web_search` calls
    anyway, all from the main session, every one returning `429 web_search
    rate limit reached` -- 32% of every tool error in the run. Confirmed by
    capturing the real request body both ways. The tool routes through
    Mistral's hosted API, and this repo's MISTRAL_API_KEY is exhausted
    (a bare `mistral-small-latest` completion 429s too), so it cannot
    succeed; a tool that always fails still costs a turn to call. Disabled
    identically for both swarms, so it cannot skew the comparison. If the
    key is ever topped up, drop the key from render_config.

    No other tool is filtered: every native tool (edit/write_file/read_file/
    bash/grep/task/skill/...) stays on, exactly as a local `vibe` run would
    have them.
    """
    env = dict(os.environ)
    # See _STRIPPED_ENV and AGENT_VENV. Stripped HERE and not in
    # render_config(), which legitimately needs OPENAI_API_KEY to hand to
    # `vibe mcp add --env` -- that writes it into this agent's config.toml, so
    # the MCP servers that need it still get it while the agent's own shell
    # does not.
    for key in _STRIPPED_ENV:
        env.pop(key, None)
    if AGENT_PYTHON.exists():
        env["VIRTUAL_ENV"] = str(AGENT_VENV)
        env["PATH"] = f"{AGENT_VENV / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env["VIBE_HOME"] = str(vibe_home)

    # `--continue` on every attempt after the first. Each attempt used to
    # spawn a brand-new Vibe session, so the agent threw away everything it
    # had learned and re-explored the same codebase from zero -- which is
    # most of why progress plateaued at 2 of 3 files: agents were not
    # getting stuck so much as repeatedly starting over. Vibe's own native
    # flag ("Continue from the most recent saved session"), and each agent
    # has its own VIBE_HOME, so it always resumes its own session and never
    # another agent's.
    resume_args = ["--continue"] if resume else []
    proc = await asyncio.create_subprocess_exec(
        str(VIBE_BIN),
        "--prompt", task,
        *resume_args,
        "--auto-approve",
        "--trust",
        "--output", "text",
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, f"vibe invocation timed out after {timeout_s:.0f}s"
    return proc.returncode, (stdout + stderr).decode(errors="replace")


def _transcript_files(vibe_home: Path) -> list[Path]:
    """Every session transcript under this agent's VIBE_HOME, including the one
    a `--continue` resumed."""
    root = vibe_home / "logs" / "session"
    if not root.is_dir():
        return []
    return sorted(root.glob("*/messages.jsonl"))


_MAX_OBSERVATION_CHARS = 2000


def _cap(text: str, limit: int = _MAX_OBSERVATION_CHARS) -> str:
    """Bound what one stored :Message holds.

    Every stored message is run through the extraction pipeline, and that cost
    scales with length -- measured: 140 ms at 100 chars, 381 ms at 2,000,
    644 ms at 8,000. One warm attempt's 45 stored messages totalled 492,928
    characters, with a tail of `role: "tool"` results (file dumps, pytest
    output) reaching 21,410 each. That tail, not the embedder, is what made
    the replay 591 ms per message and cost warm roughly half its attempts.

    A long tool result is also already stored a second time, capped, as the
    owning ReasoningStep's `observation` -- so the uncapped copy buys nothing.

    This is the same mistake this function's docstring already records in a
    different shape: an earlier revision stored the entire Vibe stdout as one
    :Message. Splitting per message fixed the blob; it did not bound the
    pieces. Every message still becomes its own node, so the
    Message-[:NEXT_MESSAGE]->Message chain is unchanged -- only how much text
    each node carries."""
    if len(text) <= limit:
        return text
    return text[:limit] + f" ...(truncated, {len(text) - limit:,} more chars)"


def _tool_results(lines: list[str]) -> dict[str, str]:
    """tool_call_id -> the tool's returned content, from a Vibe transcript.

    HAND-ROLLED STANDIN -- not part of neo4j-agent-memory. Vibe writes the
    call and its result as two separate lines (`role: assistant` carrying
    `tool_calls`, then `role: tool` carrying `tool_call_id` + `content`), so
    pairing them is this harness's job.

    Truncated at _MAX_OBSERVATION_CHARS: a single grep has returned 64,066
    characters in this harness, and an observation is embedded and can be
    replayed into a prompt. The head of the output carries the verdict."""
    out: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("role") != "tool":
            continue
        call_id = msg.get("tool_call_id")
        content = msg.get("content")
        if not call_id or not content:
            continue
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        content = str(content)
        if len(content) > _MAX_OBSERVATION_CHARS:
            content = content[:_MAX_OBSERVATION_CHARS] + " ...(truncated)"
        out[call_id] = content
    return out


async def _replay_session_messages(
    vibe_home: Path,
    replayed: dict[Path, int],
    mem: ScopedMemory,
    trace_id: Any,
    session_id: str,
) -> None:
    """HAND-ROLLED STANDIN -- not part of neo4j-agent-memory.

    memory_agent_mvp.py calls add_message and report_step *inside* its agent
    loop, because it owns that loop. We do not own Vibe's. This function is the
    substitute: after each attempt it reads Vibe's own session transcript
    (messages.jsonl) and loads what happened into memory afterwards. Same
    information, later. If Vibe ever exposes per-turn hooks, this goes away.

    It records TWO things, and both are individual nodes, never a blob:

    * every message -- each assistant turn, each tool result -- as its own
      :Message via short_term.add_message, so the graph holds the conversation
      the way the package models it (Message-[:NEXT_MESSAGE]->Message).
    * every tool call as a :ReasoningStep + :ToolCall.

    An earlier revision stored one summary line per attempt instead, on the
    grounds that storing messages caused context overflow. That diagnosis was
    wrong. What overflowed was storing the *entire Vibe stdout as a single
    message* -- one node holding a whole agent log, which short_term's
    get_context then replayed verbatim. Individual messages are small. Storing
    them properly is both what the data model wants and harmless.

    Storage is separate from retrieval: everything is recorded here, and what
    reaches the prompt is decided by migrate_codebase()'s get_context() call.

    Steps use generate_embedding=False and are embedded in one batch by
    complete_trace(generate_step_embeddings=True) -- the pairing the package's
    own docstring names for streaming recorders. Embedding inline meant one
    synchronous OpenAI round-trip per tool call on the shared asyncio loop, and
    since both swarms share that loop, the warm arm's memory latency landed on
    the cold arm's wall clock."""
    for messages_file in _transcript_files(vibe_home):
        lines = messages_file.read_text().splitlines()
        start = replayed.get(messages_file, 0)
        replayed[messages_file] = len(lines)
        # tool_call_id -> what the tool actually returned. Built from the whole
        # file rather than the new slice, because a call at the end of one
        # attempt has its result written at the start of the next; keyed on
        # Vibe's own tool_call_id, so this is a join, not a guess.
        results = _tool_results(lines)
        for line in lines[start:]:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = msg.get("role") or "assistant"
            content = msg.get("content")
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            # The model's actual reasoning, which Vibe stores in its own field
            # rather than in `content`. Qwen3 and Mistral Small 4 are both
            # hybrid reasoning models, so on the real demo config this is where
            # the thinking lives -- and reading only `content` dropped all of
            # it. Measured on run 19: 131,751 characters of reasoning against
            # 11,184 of content, i.e. 92% of everything the model generated was
            # being discarded before it reached the graph.
            reasoning = msg.get("reasoning_content") or ""
            if isinstance(reasoning, list):
                reasoning = " ".join(str(c) for c in reasoning)
            # The one message NOT stored: the orchestrator's own constructed
            # prompt. It already contains the "What you remember" block that
            # get_context() returned, so storing it makes memory retrieve its
            # own previous output -- attempt N's prompt embedding attempt N-1's
            # memory block, which embeds N-2's. Caught live at 15,170 chars and
            # growing. migrate_codebase() stores the canonical task line
            # instead. Every other message is stored as-is.
            if content and role != "user":
                await mem.add_message(session_id, role, _cap(str(content)))
            # A turn that is pure reasoning + tool call carries no `content` at
            # all -- 443 of run 23's 504 assistant messages were exactly that.
            # Without this the turn leaves no :Message behind and the
            # conversation chain has a hole where the agent was thinking.
            elif reasoning and role != "user":
                await mem.add_message(session_id, role, _cap(str(reasoning)))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                name = fn.get("name") or tc.get("name") or "unknown_tool"
                raw_args = fn.get("arguments")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"raw": raw_args}
                else:
                    args = raw_args or {}
                # `thought` is the model's own reasoning for this turn, not a
                # synthetic label. It used to be the literal string
                # f"Calling {name}", which made every ReasoningStep in the
                # graph interchangeable and made reasoning.search_steps() --
                # the package's step-level case-based retrieval -- useless,
                # since it embeds thought/action and every thought was the same
                # sentence. Falls back to the label only when the model emitted
                # neither reasoning nor content.
                # `observation` completes the thought-action-observation triple
                # the reasoning layer is built around, and it is the package's
                # own add_step parameter -- it was simply never passed. Its
                # absence is visible from Neo4j itself: the package's
                # step-embedding query selects s.observation, and the server
                # answered every batch with "the property `observation` does
                # not exist", so steps were being embedded on thought+action
                # alone. Without it a step records that the agent ran `bash`
                # and why, but never what came back, which is the half that
                # says whether the idea worked.
                step = await mem.add_step(
                    trace_id,
                    thought=(reasoning or content or f"Calling {name}"),
                    action=name,
                    observation=results.get(tc.get("id")),
                    generate_embedding=False,
                )
                await mem.record_tool_call(step.id, tool_name=name, arguments=args)


def _collect_file_contents(repo_dir: Path) -> dict[str, bytes]:
    """Walks the local, currently-edited package directory and returns
    {dst_path_in_sandbox: bytes}, keyed under /repo/<package name>/... --
    this is what gets uploaded into a fresh Daytona sandbox for each
    validation check (SandboxPool.run_pytest). Known limitation: a file
    Vibe deletes locally isn't deleted in the sandbox too (the snapshot's
    own stale copy would still be there); not handled, since this migration
    task is edit-in-place, not file removal."""
    contents: dict[str, bytes] = {}
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_dir.parent)
        # Never ship build junk into the sandbox: a stale __pycache__/*.pyc
        # compiled against the pre-migration source shadows the edited .py
        # for any interpreter that trusts it, and it is pure upload weight
        # on every single attempt regardless.
        if "__pycache__" in rel.parts or rel.suffix == ".pyc":
            continue
        contents[f"/repo/{rel.as_posix()}"] = path.read_bytes()
    return contents


_ERROR_LINE = re.compile(r"^E\s+(\w[\w.]*(?:Error|Exception|Warning)\b.*)$", re.MULTILINE)

# pytest's own summary line, e.g. "=== 3 failed, 12 passed in 4.21s ===" or
# "=== 15 errors in 0.83s ===". Collection errors report `errors`, not `failed`.
_PYTEST_TALLY = re.compile(r"(\d+) (passed|failed|error|errors)\b")

# `from pydantic.v1 import X`, `import pydantic.v1`, `from pydantic import v1`.
_V1_SHIM = re.compile(
    r"^\s*(?:from\s+pydantic\.v1(?:\.\w+)*\s+import\b"
    r"|import\s+pydantic\.v1\b"
    r"|from\s+pydantic\s+import\s+(?:[^\n#]*\b)?v1\b)",
    re.MULTILINE,
)


def v1_shim_files(file_contents: dict[str, bytes]) -> list[str]:
    """Files importing pydantic's v1 compatibility shim, which is not a
    migration -- it is the opposite of one.

    This is a correctness check on the task, not a hint about the answer. The
    instruction is "migrate this codebase from Pydantic v1 to Pydantic v2" and
    the manifest pins `target_version: pydantic>=2.0,<3.0`; code that reaches
    into `pydantic.v1` is still running v1, just spelled differently.

    It is load-bearing because the test suite cannot see the difference.
    Measured directly: rewriting every `from pydantic import ...` in the
    fixture to `from pydantic.v1 import ...` and changing nothing else gives
    **32 of 33 tests passing** -- the suite's own tests were taken from the
    post-migration commit but never call a v2-only API, so they are blind to
    the shim. Without this check the oracle is 97% gameable, an attempt that
    shims everything scores as near-total success, and because shared memory
    propagates whatever the criterion accepts, that diff is then handed to
    every other warm agent at similarity 1.00. Run 28 recorded exactly that
    diff (`+from pydantic.v1 import BaseSettings as Settings`) as partial
    progress before this existed."""
    return sorted(
        name for name, blob in file_contents.items()
        if name.endswith(".py") and _V1_SHIM.search(blob.decode("utf-8", "replace"))
    )


_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)
_VALIDATOR = re.compile(r"(?:field_|model_|root_)?validator\b")


def _decorator_names(node: ast.AST) -> list[str]:
    out = []
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            out.append(target.attr)
        elif isinstance(target, ast.Name):
            out.append(target.id)
    return out


def _is_noop_validator(fn: ast.AST) -> bool:
    """A validator whose body does nothing but hand its input straight back."""
    if not any(_VALIDATOR.search(d) for d in _decorator_names(fn)):
        return False
    body = [s for s in fn.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str))]
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    # `...` is a bare Expr, not a Pass -- the shape left by an agent that
    # "migrated" a validator by writing a placeholder body.
    if (isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant)
            and only.value.value is Ellipsis):
        return True
    return (
        isinstance(only, ast.Return)
        and isinstance(only.value, (ast.Name, ast.Constant))
    )


def gutted_files(file_contents: dict[str, bytes]) -> list[str]:
    """Files where behaviour was *deleted* rather than migrated.

    The second oracle hole, and the more dangerous one, because unlike the v1
    shim it leaves no import to grep for. Found in run 54's warm-2 attempt,
    which scored 32 of 33 -- the best result the harness has ever recorded --
    and which I reported as a genuine, verified success. It was not. The agent
    hit a `@root_validator` it could not migrate and replaced it with a stub::

        -    @root_validator
        -    def validate_alternative_body(cls, values):
        +    @model_validator(mode='after')
        +    def validate_alternative_body(self, values):
        +        return values
                 \"\"\"

    `return values` fires immediately; the original docstring and body below
    it are unreachable. The function still exists, still has the right name and
    a v2 decorator, and imports cleanly -- so 32 tests pass. The 33rd is the
    one that checks what the validator was *for* (`assert 'alternative' is
    None`), which is why the failure looked like an ordinary behavioural
    remainder rather than the symptom it was. Ground truth
    (reference_v2/fastapi_mail/schemas.py:96-101) keeps the real logic.

    Deleting a validator scores 32; migrating it wrongly-but-honestly scores 3
    (run 56 warm-2, same file, same decorator, no stub). The oracle was paying
    ~10x more for destroying the code than for attempting it, and shared memory
    then propagates whichever diff scored higher -- so this hole actively
    trains the warm swarm to gut the file.

    Two signals, both structural, neither of which needs the v1 original:

    * unreachable statements after a terminator in the same statement list --
      never intentional, and the exact residue left by stubbing over a body.
    * a validator whose body is a bare `return <name>`/`pass`, which is a
      no-op regardless of how it got that way.

    Syntactically invalid files are not flagged: a SyntaxError is already a
    hard failure the suite reports on its own."""
    flagged = []
    for name, blob in file_contents.items():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(blob.decode("utf-8", "replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            dead = any(
                isinstance(stmt, _TERMINATORS) and stmt is not block[-1]
                for parent in ast.walk(node)
                for block in (getattr(parent, "body", None), getattr(parent, "orelse", None))
                if isinstance(block, list) and block
                for stmt in block
            )
            if dead or _is_noop_validator(node):
                flagged.append(name)
                break
    return sorted(flagged)


def tests_passed(pytest_output: str) -> int:
    """How many tests actually passed. The only progress measure that cannot be
    gamed by trading one error for another.

    `error_signature` changing is NOT progress. Run 21 proved that directly:
    an agent replaced

        from pydantic import BaseSettings as Settings
    with
        from pydantic_settings import BaseSettings, SettingsConfigDict

    which cleared `PydanticImportError` and introduced
    `NameError: name 'Settings' is not defined`, because it dropped the alias
    every later line in config.py depends on. The signature changed, so the
    attempt was scored as a success, the diff was written to shared memory as a
    verified fix, and warm agents then retrieved it -- at similarity 0.72, with
    the broken diff quoted verbatim -- and reproduced the same mistake. Four
    traces hit that NameError and none cleared it.

    Memory that propagates a wrong fix is worse than no memory, and the fault
    was in the success criterion, not the memory."""
    counts = dict((kind, int(n)) for n, kind in _PYTEST_TALLY.findall(pytest_output or ""))
    return counts.get("passed", 0)


def error_signature(pytest_output: str) -> str | None:
    """A stable fingerprint of *why* the suite is failing, so two attempts can
    be compared.

    Takes the first `E   SomeError: message` line pytest emits and strips the
    volatile parts (absolute paths, line numbers, hex ids). If that string
    changes between attempts, the specific failure the previous attempt was
    looking at is gone -- something real was fixed, even though the suite is
    still red.

    This is the orchestrator's own reading of its own independent test run.
    It is never the model's claim about its own work."""
    match = _ERROR_LINE.search(pytest_output or "")
    if not match:
        return None
    signature = match.group(1)
    signature = re.sub(r"(/[\w./-]+)+", "<path>", signature)
    signature = re.sub(r"0x[0-9a-f]+", "<addr>", signature)
    signature = re.sub(r"\b\d+\b", "<n>", signature)
    return signature.strip()


def _snapshot(repo_dir: Path) -> dict[str, str]:
    """Text of every source file, for diffing one attempt against the next."""
    out: dict[str, str] = {}
    for path in sorted(repo_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        out[path.relative_to(repo_dir).as_posix()] = path.read_text(errors="replace")
    return out


def observed_fix(
    before: dict[str, str],
    after: dict[str, str],
    *,
    prior_error: str | None,
    next_error: str | None,
    suite_passed: bool,
    max_lines: int = 90,
) -> str | None:
    """What this edit actually did to the suite, in words, plus the edit.

    Returned as text for TraceOutcome.summary, so it is what another agent
    reads when reasoning memory surfaces this trace. Nothing here is the
    model's claim: the orchestrator ran the suite itself, before and after,
    and diffed the tree itself.

    HAND-ROLLED STANDIN -- the wording is this harness's, not
    neo4j-agent-memory's. It matters more than it looks. An earlier revision
    emitted "stopped occurring after this change (verified by an independent
    test run)" for *every* attempt that produced a diff, whether or not
    anything had improved. Run 25 therefore recorded warm-2's

        -from pydantic import BaseModel, EmailStr, root_validator, validator
        +from pydantic import Model, EmailStr, root_validator, validator

    as verified -- a hallucinated symbol that immediately raised
    `ImportError: cannot import name 'Model' from 'pydantic'`. Shared memory
    propagates whatever the summary asserts, so an overclaiming summary
    teaches every other warm agent the wrong thing. The three cases below are
    kept distinct and are stated no more strongly than the evidence supports;
    "this changed nothing, do not repeat it" is as useful to retrieve as a
    fix, and is the honest reading far more often."""
    diff_lines: list[str] = []
    for name in sorted(set(before) | set(after)):
        chunk = list(
            difflib.unified_diff(
                before.get(name, "").splitlines(),
                after.get(name, "").splitlines(),
                fromfile=name, tofile=name, lineterm="", n=1,
            )
        )
        diff_lines.extend(chunk)
    if not diff_lines:
        return None
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + [f"... ({len(diff_lines) - max_lines} more lines)"]

    diff = "\n".join(diff_lines)

    if suite_passed:
        return f"This change made the full test suite pass:\n{diff}"

    if prior_error is None:
        # Attempt 1: there was no prior error to clear, so the only honest
        # statement is where the suite stands now.
        return (
            f"After this change the suite failed with:\n{next_error or 'an unknown error'}\n"
            f"{diff}"
        )

    if next_error and next_error != prior_error:
        # The diff is the whole tree's change for this attempt, so when an
        # attempt edits several files it contains BOTH the edit that cleared
        # `prior_error` and whichever edit caused `next_error`. Presenting that
        # as one undifferentiated "the change" invites a reader to copy all of
        # it. Observed in run 32's best trace: the same summary held the
        # correct `from pydantic_settings import BaseSettings as Settings` and
        # a wrong `EmailStr(email).validate()` that raised
        # `TypeError: EmailStr() takes no arguments`. The orchestrator cannot
        # tell which hunk did which -- it only ran the suite before and after --
        # so it says exactly that rather than implying the whole diff is good.
        return (
            f"This error:\n{prior_error}\n\n"
            "stopped occurring after the change below, but the suite then failed with:\n"
            f"{next_error}\n\n"
            "So this is partial progress, not a complete fix. Part of the diff below "
            "fixed the first error and part of it caused the second, and which is "
            "which was not determined -- do not copy it wholesale:\n"
            f"{diff}"
        )

    return (
        f"This change did NOT help. The suite still fails with the same error:\n"
        f"{prior_error}\n\nDo not repeat this change:\n{diff}"
    )


def ensure_agent_venv(requirements: Path) -> list[str]:
    """Build AGENT_VENV from the fixture's own v2 requirements, once.

    This is what lets an agent run the test suite itself, in its own checkout,
    in a few seconds -- instead of editing blind and waiting for the
    orchestrator's Daytona round-trip, which costs a whole attempt. Measured
    across runs 26-29 that round-trip gave each agent only 2-4 attempts in ten
    minutes against a failure chain five fixes long, so the agent was spending
    an entire attempt to learn one error.

    It changes nothing about how the work is graded: the orchestrator still
    runs the suite independently in a fresh Daytona sandbox and that verdict
    alone decides success and what reaches memory. The agent simply gets to
    check its own work first, which is what anyone migrating a codebase does.
    Both swarms get it identically, so it cannot skew warm against cold.

    Returns problems, for preflight to print; empty on success."""
    if AGENT_PYTHON.exists():
        return []
    AGENT_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(AGENT_VENV)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            [str(AGENT_PYTHON), "-m", "pip", "install", "-q", "-r", str(requirements)],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        return [
            f"agent venv: could not build {AGENT_VENV} from {requirements} "
            f"({exc.stderr.strip()[:300]}). Agents will fall back to whatever "
            f"`python` their PATH finds, which is the orchestrator's own venv."
        ]
    return []


# Roughly 1,500 tokens of a 32,768-token window. See _trim_error_for_prompt.
_MAX_ERROR_CHARS = 6000


def _trim_error_for_prompt(error_text: str, max_chars: int = _MAX_ERROR_CHARS) -> str:
    """Bound the pytest output that gets fed back into the next prompt.

    The orchestrator's own scoring keeps the full output -- error_signature(),
    tests_passed() and v1_shim_files() all still read it untouched. Only the
    copy handed to the model is trimmed.

    Measured on run 37: a single fed-back blob was 43,054 characters inside a
    44,322-character prompt -- 97% of the prompt, ~11,000 tokens, a third of
    this model's entire context window, re-sent on every attempt. cold-3 spent
    most of a run on near-identical ~49,000-character prompts. Nothing in that
    volume is new information: pytest repeats the same traceback per failing
    test, and the agent can rerun the suite itself now anyway.

    It also silently skewed the warm/cold comparison. The blob grows with the
    number of tests that actually ran, so an agent whose suite gets *further*
    produces a bigger prompt and burns more tokens. Cold consistently got
    further, which is part of why token_ratio favoured warm -- warm looked
    cheaper partly because its agents failed earlier.

    Head and tail are both kept: the head carries the first traceback and the
    error that matters, the tail carries pytest's summary line and tally."""
    text = error_text or ""
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    dropped = len(text) - max_chars
    return (
        f"{text[:head]}\n\n"
        f"... [{dropped:,} characters of repeated tracebacks omitted; "
        f"rerun the suite yourself to see them all] ...\n\n"
        f"{text[-tail:]}"
    )


def _localize_sandbox_paths(error_text: str, vibe_cwd: Path) -> str:
    """Rewrite Daytona's absolute paths into ones this agent can actually use.

    The suite runs in the sandbox at /repo, so its tracebacks name
    `/repo/tests/conftest.py` and `/repo/fastapi_mail/config.py`. Fed back
    verbatim, the model quite reasonably tries to open exactly those paths --
    which do not exist on the machine Vibe is actually running on. In one
    observed session that was 524 consecutive failed `read_file` calls, every
    one of them on a path that could never resolve.

    The prefix is stripped rather than swapped for `vibe_cwd`, so the paths
    come out RELATIVE -- `fastapi_mail/config.py`, not
    `/private/tmp/msf-agents/cold-1/fastapi_mail/config.py`. Vibe's cwd is the
    repo root, so both resolve, but the long one is a typo surface the agent
    keeps falling into: 11 of run 38's 66 failed edits were "File does not
    exist", including `fastapi-mail/config.py` for `fastapi_mail/` -- a hyphen
    for an underscore, 40 characters into a path the model had to reproduce
    exactly. This is the same failure that made 22% of edits vanish when
    AGENT_ROOT was a 118-character random $TMPDIR path; shortening what the
    model must copy is what fixed it then.

    Still a pure prefix translation, not interpretation: the text reports the
    same failure, named in a path-space the reader inhabits."""
    return (error_text or "").replace("/repo/", "")


REPLAY_GRACE_S = 120.0


async def _settle_replay(
    task: "asyncio.Task | None", grace_s: float = REPLAY_GRACE_S
) -> None:
    """Join a replay that was overlapped with the Daytona check, on the paths
    that bail out before the normal join.

    Without this the task is left pending when an attempt times out or raises:
    it keeps writing to Neo4j on behalf of a trace the loop has already closed,
    and asyncio logs "Task exception was never retrieved" for whatever it hits
    afterwards.

    It is ALLOWED TO FINISH, not cancelled. An earlier revision cancelled it
    outright, on the reasoning that its result is no longer wanted once the
    attempt has bailed. That reasoning was wrong, and it emptied the graph.

    The replay is the only thing that writes the reasoning steps and the
    messages -- everything an agent actually did. The trace itself is opened
    before the Vibe call and closed after, so a cancelled replay still leaves a
    :ReasoningTrace behind: a node with a task, an embedding, and nothing
    inside it. Retrieval then returns those, which is worse than returning
    nothing, because they cost tokens and say only that an attempt existed.

    Measured over 41 runs and 8 hours on 2026-09-15, every one of which took
    the timeout path: 168 traces, of which 160 had no verdict and only 4 had a
    single step between them -- 13 steps recorded in total, against the
    hundreds of tool calls the transcripts hold. The whole accumulated-memory
    series was flat because there was nothing in the graph to accumulate.

    `grace_s` bounds it so a stuck write cannot hang the run: the replay is
    ~0.5s per message and an attempt holds fewer than 200, so anything past two
    minutes is stuck rather than slow. Only then is it cancelled."""
    if task is None:
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=grace_s)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    except Exception:
        pass


async def migrate_codebase(
    *,
    pool: SandboxPool,
    repo_dir: Path,
    test_command: str,
    deadline: float,
    emit: Emit,
    vibe_home: Path = VIBE_HOME,
    vibe_cwd: Path = HARNESS_DIR,
    mem: ScopedMemory | None = None,
    session_id: str | None = None,
    baseline_signature: str | None = None,
    baseline_passed: int = 0,
) -> MigrationResult:
    """One agent, one local checkout, one whole-codebase task: "migrate this
    codebase from Pydantic v1 to Pydantic v2." Vibe edits `repo_dir` (a real
    local directory, e.g. vibe_cwd/fastapi_mail) with its own native tools,
    unrestricted -- see _run_vibe(). Daytona is only this function's own
    tool, called directly, never exposed to Vibe: after each Vibe turn, the
    current local file tree is uploaded into a fresh, disposable sandbox
    (SandboxPool.run_pytest) and the real test suite runs there. That
    result, not Vibe's own exit status, decides success and feeds
    `last_error` into the next attempt's prompt.

    Retries until the full test suite passes or `deadline` (an absolute
    time.monotonic() timestamp, shared across the whole run) is reached.
    There is no fixed attempt cap: a codebase still being worked on when the
    clock runs out is not "failed", it's just where the deadline caught it.

    `mem` is None for every cold agent -- every memory call below is skipped
    entirely for that swarm, not just gated.

    When `mem` is set (warm only), this loop is the deterministic half of
    workshop-agent-memory-scripts/memory_agent_mvp.py's main(), with one
    attempt standing in for one turn. All five of that script's memory calls
    are here, none of them optional and none of them the model's choice:

        add_message(user)   -> before the Vibe call
        start_trace(...)    -> before the Vibe call
        get_context(...)    -> spliced into the prompt (its `what_you_remember`)
        add_step/record_tool_call -> replayed from Vibe's own messages.jsonl
        add_message(assistant) + complete_trace(...) -> after the Daytona check

    Two deliberate differences from that script, both because this harness
    knows things a chat agent doesn't:

    * The trace is keyed on the *error signature* the attempt is working
      against, not on the task description. Every attempt here shares one task
      ("migrate this codebase"), so keying on it makes every trace embed the
      same string and get_similar_traces cannot tell them apart. The failure
      is what differs between attempts, so the failure is what gets embedded.
      Attempt 1 has no prior failure and uses the task description.

    * `complete_trace` is driven by an independent pytest run in a fresh
      Daytona sandbox, not by whether the agent raised. The workshop closes
      its trace on the agent's own say-so; here the trace's success flag is
      ground truth. Correspondingly, trace-level success means "this attempt
      cleared the error it was handed", not "the whole migration finished" --
      which is what makes get_similar_traces(success_only=True), the library
      default, return anything at all on a suite that stays red for most of a
      run. Suite-level completion is MigrationResult.success, reported
      separately by run.py."""
    task_desc = "Migrate this codebase from pydantic v1 to v2"
    last_error: str | None = None
    # Seeded from run.py's one pre-run pytest against the pristine fixture, so
    # attempt 1's trace is keyed on the error the suite *actually* starts with
    # rather than on the task description. See the baseline block in
    # main_async() for why that distinction decides whether retrieval returns
    # anything worth reading. Falls back to the task description only if the
    # baseline produced no signature at all.
    #
    # `last_error` is deliberately NOT seeded with it: that is the variable
    # that puts the failure into the prompt, and telling the agent its first
    # error before it has looked would change the task.
    last_signature: str | None = baseline_signature
    # Zero, not None. The starting state is known, not unknown: pristine v1
    # under pydantic v2 dies at collection and passes 0 tests (verified
    # directly against the fixture). Seeding this as None made `advanced`
    # unfalsifiable on attempt 1 -- and run 22's single best result in the
    # whole run, warm-2 reaching 32 of 33 passing on its first attempt, was
    # silently discarded because there was "no baseline to compare against".
    last_passed: int = baseline_passed
    last_vibe_exit: int | None = None
    # Seeded with the baseline so the starting failure is not counted as one
    # this agent cleared; errors_cleared subtracts one for it.
    seen_signatures: set[str] = {baseline_signature} if baseline_signature else set()
    best_passed: int = baseline_passed
    # How much of each session transcript has already been turned into
    # reasoning steps. Keyed by file and carried across attempts, because
    # `--continue` RESUMES the same session directory rather than creating a
    # new one -- so "directories that appeared since this attempt started",
    # which is what this used to key on, is empty for every attempt after the
    # first. Measured on run 23: 185 warm tool calls on disk, 70 ReasoningStep
    # nodes in Neo4j. Everything an agent did from attempt 2 onward was
    # invisible to memory.
    replayed_lines: dict[Path, int] = {}
    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        attempt += 1
        await emit("ATTEMPT_START", attempt=attempt)

        trace_id = None
        replay_task: asyncio.Task | None = None

        memory_context = None
        # What this attempt is actually up against. Attempt 1 has nothing to
        # go on yet; from attempt 2 it is the previous attempt's real failure,
        # as read by the orchestrator off its own independent pytest run.
        trace_task = last_signature or task_desc

        if mem is not None:
            assert session_id is not None
            # memory_agent_mvp.py's `what_you_remember`, which its framework
            # calls on every single turn regardless of what the model decides
            # to do. Here the orchestrator splices it in before every attempt.
            # The agent also has the neo4j-agent-memory MCP tools and may call
            # them itself; this is the floor under that, not a replacement for
            # it.
            #
            # Queried with `trace_task` -- the failure -- not with the task
            # description. Measured directly against the graph: the query
            # "Migrate this codebase from pydantic v1 to v2" retrieves 0
            # results, while the signature "PydanticImportError: `BaseSettings`
            # has been moved..." retrieves the matching trace. These are vector
            # searches, and a one-line task description is semantically far
            # from "here is what broke and how it was fixed".
            #
            # include_short_term=False: short_term.get_context(session_id=X)
            # replays the last N messages of session X verbatim, so anything
            # written with add_message comes straight back out into the next
            # prompt. On a 32,768-token model that is the context-overflow
            # loop that cost one agent 58 consecutive rejected attempts. The
            # agent re-reading its own prompts carries no information anyway --
            # what matters is the *other* agents' traces, and those arrive
            # through the reasoning section, which is not session-scoped.
            memory_context = await mem.get_context(
                trace_task, session_id=session_id, include_short_term=False,
            )
            if memory_context:
                memory_context = f"What you remember:\n{memory_context}"
            trace = await mem.start_trace(session_id, task=trace_task)
            trace_id = trace.id
            await mem.add_message(session_id, "user", trace_task)


        task = _task_prompt(last_error, memory_context, memory_enabled=mem is not None)
        before_snapshot = _snapshot(repo_dir)
        try:
            # Resume only a session that ended cleanly. A session that died
            # is usually one that outgrew the model's context window, and
            # resuming it replays the same oversized history straight into
            # the same 400: measured live, cold-3 spent 58 attempts and
            # ~5 seconds each in that loop, every call rejected with
            # "The input (35516 tokens) is longer than the model's context
            # length (32768 tokens)". Starting fresh is the only way out of
            # it, because compaction cannot run on a history that is already
            # too large to send. A clean exit still resumes, which is the
            # case that matters -- the agent keeps what it learned.
            resume = attempt > 1 and last_vibe_exit == 0
            vibe_exit_code, vibe_output = await _run_vibe(
                task, timeout_s=remaining, vibe_home=vibe_home, cwd=vibe_cwd,
                resume=resume,
            )
            last_vibe_exit = vibe_exit_code
            # Started here, awaited after the Daytona run below, so the two
            # overlap instead of running back to back. They are independent:
            # the replay reads Vibe's transcript and writes to Neo4j, the
            # Daytona check uploads `file_contents` and runs pytest, and
            # neither touches the other's data.
            #
            # Measured on run 47's own transcript: the replay is 45.5s per
            # attempt (0.50s per message, nearly all of it serialized OpenAI
            # embedding round-trips), against a Vibe turn of roughly 20-40s.
            # Paid serially it was most of an attempt's wall-clock, and it is
            # paid only by warm -- which is why cold completed 21-28 attempts
            # per run across runs 44-47 while warm completed 8-10, and why
            # warm cost 311-521k tokens per attempt against cold's 135-195k.
            # Nothing about what gets stored changes; only when it is waited on.
            replay_task = (
                asyncio.ensure_future(
                    _replay_session_messages(
                        vibe_home, replayed_lines, mem, trace_id, session_id
                    )
                )
                if mem is not None
                else None
            )

            file_contents = _collect_file_contents(repo_dir)
            # Bounded by the same shared run deadline as the Vibe call above,
            # not by a separate invented number. Previously this was the one
            # step outside the budget entirely, which is why a run asked for
            # 1200s took 1730.8s: eight agents each finishing a Vibe turn near
            # the boundary, then all starting an unbounded upload + sandbox
            # create + pytest afterwards. The check itself is unchanged; it
            # just can no longer run past the clock it belongs to.
            result = await asyncio.wait_for(
                pool.run_pytest(file_contents=file_contents, test_command=test_command),
                timeout=max(0.0, deadline - time.monotonic()),
            )
            await emit("SANDBOX_CREATED", create_ms=result.create_ms)
            # complete_trace(generate_step_embeddings=True) below needs every
            # step to exist, so the replay is joined before the verdict is
            # recorded -- overlapped, never skipped.
            if replay_task is not None:
                await replay_task
        except asyncio.TimeoutError:
            # The run's shared clock expired mid-attempt. That is the deadline
            # doing its job, not a failure, and it must not discard what this
            # agent already achieved: agent_worker used to receive an exception
            # here, retry, immediately re-check the deadline and report
            # MigrationResult(False, 0). Run 30 printed "0 attempts" for both
            # swarms off the back of that, after 21 cold and 5 warm attempts had
            # actually started.
            await _settle_replay(replay_task)
            if mem is not None and trace_id is not None:
                await mem.complete_trace(
                    trace_id,
                    outcome="ran out of time mid-attempt; no verdict for this one",
                    success=False,
                )
            break
        except Exception:
            await _settle_replay(replay_task)
            if mem is not None and trace_id is not None:
                await mem.complete_trace(trace_id, outcome="error", success=False)
            raise

        await emit(
            "ATTEMPT_DONE",
            attempt=attempt,
            exit_code=result.exit_code,
            vibe_exit_code=vibe_exit_code,
        )

        success = result.exit_code == 0
        signature = error_signature(result.output)
        passed = tests_passed(result.output)

        # The suite cannot tell a migration from a v1 shim -- shimming every
        # import scores 32 of 33 (see v1_shim_files). So the shim is caught
        # here, before any of this reaches the verdict or the graph, and it
        # overrides a green suite rather than merely annotating it.
        #
        # `passed` is forced to 0 as well as `success` to False: leaving the
        # tally intact would let a shimmed attempt clear `passed >
        # last_passed` and be written to shared memory as verified progress,
        # which is the one thing that must not happen with a diff every other
        # warm agent is about to retrieve.
        #
        # The agent is told plainly, in the same channel it gets every other
        # failure -- the fed-back pytest output. Identical for both swarms.
        shimmed = v1_shim_files(file_contents)
        if shimmed:
            success = False
            passed = 0
            signature = f"pydantic.v1 compatibility shim still imported by: {', '.join(shimmed)}"
            result = replace(
                result,
                exit_code=1,
                output=(
                    f"{result.output}\n\n"
                    f"MIGRATION NOT COMPLETE: these files still import pydantic's v1 "
                    f"compatibility shim: {', '.join(shimmed)}.\n"
                    f"`from pydantic.v1 import ...` keeps the code on Pydantic v1; the task "
                    f"is to move it to v2. Import from `pydantic` (or `pydantic_settings`) "
                    f"and update the code to the v2 API instead."
                ),
            )

        # The same override for the same reason, one hole over: code whose
        # behaviour was deleted instead of migrated. See gutted_files() -- this
        # is what actually produced run 54's 32/33, the best score the harness
        # ever recorded and one I wrongly reported as verified. `passed` is
        # forced to 0 here too, because 32 was precisely the problem: it beat
        # every honest attempt at the same file and would have been written to
        # shared memory as the exemplar.
        gutted = gutted_files(file_contents)
        if gutted:
            success = False
            passed = 0
            signature = f"behaviour deleted rather than migrated in: {', '.join(gutted)}"
            result = replace(
                result,
                exit_code=1,
                output=(
                    f"{result.output}\n\n"
                    f"MIGRATION NOT COMPLETE: these files contain a function whose body "
                    f"was removed rather than ported: {', '.join(gutted)}.\n"
                    f"Either unreachable code follows a `return`/`raise`, or a validator "
                    f"now just hands its argument straight back. Stubbing a validator out "
                    f"makes the imports pass while silently dropping what it enforced. "
                    f"Port the original logic to the v2 API and keep it running."
                ),
            )
        # An attempt that moves the suite onto a *different* failure has
        # demonstrably fixed the previous one. Still the orchestrator's own
        # independent test run deciding, never the model's say-so.
        #
        # This, not a green suite, is what trace-level success means. Requiring
        # a fully green suite is circular on this codebase: it cannot go green
        # until the hardest change lands, so the knowledge memory would be most
        # useful for is the knowledge it could never record. Confirmed live --
        # a 45-minute run ended with 67 traces and nothing worth retrieving in
        # any of them.
        # Strictly more tests passing than the previous attempt. A changed
        # error signature is not enough -- see tests_passed() for the run-21
        # case where that scored a regression as a fix and then taught it to
        # every other warm agent.
        advanced = not success and passed > last_passed
        if mem is not None:
            # TraceOutcome rather than a bare string, so the fix is retrievable
            # two ways: `error_kind` is written as a top-level indexed property
            # (agents on an identical codebase hit byte-identical signatures,
            # and an exact match beats a vector search on a string two agents
            # both have verbatim), while `summary` carries the diff that
            # cleared it and is what reasoning.get_context() surfaces.
            resolved = success or advanced
            await mem.complete_trace(
                trace_id,
                outcome=TraceOutcome(
                    success=resolved,
                    summary=(
                        observed_fix(
                            before_snapshot,
                            _snapshot(repo_dir),
                            prior_error=last_signature,
                            next_error=signature,
                            suite_passed=success,
                        )
                        or (
                            "suite passed" if success else
                            f"No edit was made. The suite still fails with:\n{signature}"
                        )
                    ),
                    error_kind=trace_task,
                    metrics={"attempt": float(attempt), "tests_passed": float(passed)},
                ),
                generate_step_embeddings=True,
            )
            if resolved:
                await emit("MEMORY_WRITE", error_kind=trace_task[:60], on=("pass" if success else "progress"))
            # The record of what happened, kept short on purpose. An earlier
            # revision stored the entire Vibe stdout here, and since
            # short_term.get_context() replays stored messages verbatim, the
            # transcript came straight back out into the next prompt. The
            # workshop stores str(result.output) -- one answer, not a log.
            await mem.add_message(
                session_id, "assistant",
                f"attempt {attempt}: " + ("suite passed" if success else (signature or "no change")),
            )

        # Distinct failures this agent has moved the suite through, counted
        # off the orchestrator's own test runs. The baseline signature is
        # seeded in, so clearing it counts once and only once.
        if signature and signature not in seen_signatures:
            seen_signatures.add(signature)
        best_passed = max(best_passed, passed)

        if success:
            await emit("FILE_DONE", success=True, attempts=attempt)
            return MigrationResult(
                True, attempt,
                errors_cleared=max(0, len(seen_signatures) - 1),
                best_passed=best_passed,
                last_signature=None,
            )

        last_signature = signature
        last_passed = passed
        last_error = _trim_error_for_prompt(_localize_sandbox_paths(result.output, vibe_cwd))

    await emit("FILE_DONE", success=False, attempts=attempt)
    return MigrationResult(
        False, attempt,
        errors_cleared=max(0, len(seen_signatures) - 1),
        best_passed=best_passed,
        last_signature=last_signature,
    )
