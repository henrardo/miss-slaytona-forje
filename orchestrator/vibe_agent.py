"""One agent, one whole-codebase task: "migrate this codebase from Pydantic
v1 to Pydantic v2."

The division of labour, which is the only thing about this module worth
holding in your head:

  Vibe   edits a real local checkout with its own native tools, unfiltered,
         exactly as a local `vibe` invocation would. It never registers or
         talks to Daytona, and it is never told how its work is checked.
  Here   calls Daytona directly between attempts (SandboxPool.run_pytest),
         uploading whatever the local tree currently looks like into a fresh
         disposable sandbox. That verdict -- not Vibe's exit status, not the
         model's claim -- decides success and feeds the next prompt.

Background on the failures that shaped this: NOTES-hard-won.md.
"""
from __future__ import annotations

import ast
import asyncio
import difflib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Awaitable, Callable

from neo4j_agent_memory.mcp._instructions import get_instructions
from neo4j_agent_memory.schema.models import TraceOutcome

from orchestrator.manifest import REPO_ROOT
from orchestrator.memory import EMBEDDING_MODEL, NEO4J_PASSWORD, NEO4J_URI, ScopedMemory
from orchestrator.sandbox import SandboxPool

HARNESS_DIR = REPO_ROOT / "harness"
VIBE_BIN = HARNESS_DIR / ".venv" / "bin" / "vibe"
VIBE_HOME = HARNESS_DIR / ".vibe"
CONFIG_TEMPLATE = HARNESS_DIR / "vibe-config.template.toml"
CONFIG_GENERATED = VIBE_HOME / "config.toml"

# The interpreter an agent's own shell gets: the fixture's pydantic-v2
# requirements and nothing else. Built once by ensure_agent_venv().
#
# Agents used to inherit the orchestrator's VIRTUAL_ENV, so `python -m pytest`
# in an agent's checkout resolved pydantic -- and neo4j, and the Daytona SDK --
# out of this project's own venv. Short path and .resolve() are both
# load-bearing; see NOTES-hard-won.md, "Keep the paths the model must retype
# short".
AGENT_ROOT = Path(os.environ.get("M4_AGENT_ROOT", "/tmp/msf-agents")).resolve()
AGENT_VENV = AGENT_ROOT / ".fixture-venv"
AGENT_PYTHON = AGENT_VENV / "bin" / "python"

# An empty HOME for the agents, so that "everything is enabled" does not mean
# "the agent can rewrite the operator's dotfiles".
#
# Vibe resolves its global skills directory as `Path.home() / ".agents" /
# "skills"` (core/paths/_agents_home.py), which on a developer machine is the
# real one. With `skill` enabled, warm-0 pulled the operator's installed
# `find-skills` skill into context as an ordinary project file and then:
#
#   * issued SIX `edit` calls against ~/.agents/skills/find-skills/SKILL.md
#     (all six missed on `old_string`, which is the only reason that file is
#     still intact -- one lucky match would have corrupted it), and
#   * at transcript line 52, tried to write the pydantic `validate_alternative_body`
#     fix INTO SKILL.md, having lost track of which file it was editing, and
#   * then burned ~20 turns looping over three skill paths, two of which 404.
#
# The fix is containment, not capability removal: every tool stays enabled and
# `skill` still works, but it resolves against a HOME that belongs to the run.
# `user_skills_dirs` returns [] when the directory does not exist, so the agent
# simply has no global skills -- and no path to the operator's.
#
# Set per agent rather than once, so an agent that does write into its HOME
# cannot reach a sibling's either.
AGENT_HOMES = AGENT_ROOT / ".homes"
# ...except the caches, which must stay shared and warm. The neo4j-agent-memory
# MCP server is launched with `uvx`, and uvx resolves the package through
# ~/.cache/uv (30GB of it here). Repointing HOME without this sends every agent
# to re-resolve and re-download the package on startup, off a network the run
# does not depend on and cannot rely on. UV_CACHE_DIR/XDG_CACHE_HOME are the
# documented overrides (`uv --help`: "[env: UV_CACHE_DIR=]").
_REAL_HOME = Path.home()
_SHARED_CACHE_ENV = {
    "UV_CACHE_DIR": str(_REAL_HOME / ".cache" / "uv"),
    "XDG_CACHE_HOME": str(_REAL_HOME / ".cache"),
}


def agent_home_for(vibe_home: Path) -> Path:
    """A private, empty HOME for one agent, keyed off its VIBE_HOME.

    Created if absent and otherwise left alone. Deliberately does NOT contain
    `.agents/`: its absence is what makes Vibe's global skills list empty."""
    home = AGENT_HOMES / vibe_home.name
    home.mkdir(parents=True, exist_ok=True)
    return home

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
# The `post_tool` hook client. Stdlib only and started once per tool call, so
# it runs under THIS interpreter (sys.executable) rather than the agent's
# fixture venv -- it needs no third-party package, and the fixture venv exists
# to run pytest, not to host harness code.
STEP_HOOK_SCRIPT = HARNESS_DIR / "memory_step_hook.py"

WEB_TOOLS_DIR = HARNESS_DIR / "web-tools"
WEB_TOOLS_PYTHON = WEB_TOOLS_DIR / ".venv" / "bin" / "python"
WEB_TOOLS_SERVER = WEB_TOOLS_DIR / "server.py"

# Where the MCP servers are launched FROM, as far as the model can see.
#
# Vibe prefixes every MCP tool result with the server's full launch command:
#
#   ok: True
#   server: stdio:/Users/.../miss-slaytona-forje/harness/web-tools/.venv/bin/python
#           /Users/.../miss-slaytona-forje/harness/web-tools/server.py
#   tool: lookup
#
# Two things came out of that on 2026-09-16, both measured:
#
#   * It is the first thing every agent reads, because step 2 of the task
#     requires web_lookup. It names the orchestrator's repo root, which is all
#     you need to reach `fixture/` -- the read-only ground truth -- and every
#     other agent's checkout. cold-0's NEXT action was an edit to
#     `<repo>/harness/fastapi-mail/schemas.py`; warm-0 ran `find <repo> -name
#     pyproject.toml` and then `chmod u+w <repo>/fixture/fastapi_mail/
#     fastmail.py`. warm-0 made 7 file operations that run, 7 of them outside
#     its own checkout.
#   * The memory server's line carried `--uri=` and `--password=` in plain
#     text, into the context of every warm agent, on every memory call --
#     defeating _STRIPPED_ENV, which removes exactly those two variables from
#     the agent's environment so it cannot reach the graph directly.
#
# So each server is launched through a single argument-less executable in a
# directory that contains nothing else. The echoed line becomes
# `stdio:/private/tmp/msf-mcp/web-server`, which names no code, no fixture, no
# sibling agent and no credential.
#
# NOT a symlink to the venv's python: a symlinked interpreter does not resolve
# its own site-packages (verified -- `ModuleNotFoundError: No module named
# 'fastmcp'`), so these are exec shims.
#
# Deliberately not under AGENT_ROOT: that directory holds every agent's
# checkout, so leaking its path would trade one sibling-visible path for
# another.
MCP_SHIM_DIR = Path("/private/tmp/msf-mcp")

# THERE IS NO TURN LIMIT. `--max-turns` is not passed at all: the agent takes
# as many turns as it wants and ends its own attempt, which is what Vibe does
# when you run it yourself.
#
# It used to be `--max-turns 8`, and that was the single largest way this
# harness inserted itself between the model and the work. What it bought was
# an attempt that reliably ENDED so it could be graded (see NOTES-hard-won.md,
# "The loop must produce a graded attempt"); what it cost was every attempt
# ending mid-thought -- `stop='Turn limit of 8 reached'` on essentially all of
# them, i.e. the agent was never once the thing that decided it was finished.
# An 8-turn budget also cannot absorb a wasted turn, and turns do get wasted:
# in one measured attempt 9 of 13 tool calls were failed `edit`s, so the whole
# allowance went on retries.
#
# A Vibe run ends by itself when the model stops calling tools, so nothing is
# needed to make attempts terminate. The only bound left is the RUN's own
# wall-clock budget, minus the verdict reserve -- that is the run's deadline
# doing its job, not a cap on what the model may do, and an attempt cut by it
# is still graded on whatever the agent had achieved.
#
# Deliberately NOT overridable by an env var any more. A knob that reads
# "M4_TURNS_PER_ATTEMPT" invites tuning the agent's leash to make a number look
# better, and there is no value of it that belongs in a measurement of whether
# these agents can do the job on their own.
#
# Reserved for the Daytona verdict. Measured at ~45-70s (upload + create +
# pytest) on a 1-vCPU sandbox.
VERDICT_RESERVE_S = 120.0

Emit = Callable[..., Awaitable[Any]]

# Vibe's own end-of-run marker, printed on stdout in programmatic mode, e.g.
#   <vibe_stop_event>Agent completed</vibe_stop_event>
# Still matched (rather than keying on the return code) because Vibe does not
# always exit 0 when it stops for a legitimate reason -- `--max-turns`, back
# when this harness used it, stopped on a turn boundary and exited 1. The
# turn-limit pattern is kept only so a run made with an older config, or a
# Vibe that imposes its own ceiling, is still recognised as a clean stop.
_STOP_EVENT = re.compile(r"<vibe_stop_event>(.*?)</vibe_stop_event>", re.DOTALL)
_TURN_LIMIT_STOP = re.compile(r"<vibe_stop_event>Turn limit of \d+ reached</vibe_stop_event>")


def stop_reason(output: str) -> str:
    """Why Vibe's turn ended, for the ATTEMPT_DONE event.

    This is the one thing about an attempt that was completely invisible.
    `_run_vibe` captured Vibe's stdout, used it for one regex, and dropped it
    -- so an attempt that ended for an unexpected reason was indistinguishable
    from one that ran out of turns, which is the same blindness that made a
    dead MCP server look like a model declining to call a tool.

    Observed live once this was surfaced: every attempt in a run exited 1 with
    only 1-5 of its 8 turns used and no turn-limit marker, so no session ever
    resumed -- and nothing anywhere said why."""
    m = _STOP_EVENT.search(output or "")
    if m:
        return m.group(1).strip()[:120]
    # Under `--output streaming` the tail is a JSON history entry, so print
    # something readable from it rather than 400 characters of serialised
    # model. The tag itself still matches above when it fires: it is emitted
    # as ordinary assistant content (agent_loop/_loop.py:1872), so it appears
    # inside a streamed message entry rather than as a bare line.
    tail = [ln for ln in (output or "").strip().splitlines() if ln.strip()]
    if not tail:
        return "(no output)"
    last = tail[-1]
    try:
        entry = json.loads(last)
    except json.JSONDecodeError:
        return f"(no stop event) {last[:100]}"
    kind = entry.get("type") or "?"
    text = _entry_text(entry).replace("\n", " ").strip()
    return f"(no stop event) last entry {kind}: {text[:90]}" if text else \
           f"(no stop event) last entry {kind}"


def _ended_cleanly(exit_code: int | None, output: str) -> bool:
    """Is this session safe to `--continue` from?

    The question being asked is NOT "did vibe succeed". It is "is this
    session's history sane enough to replay into the model". A session that
    died of context overflow must not be resumed: resuming replays the same
    oversized history into the same 400, and compaction cannot run on a
    history already too large to send. Measured live: cold-3 spent 58 attempts
    at ~5s each in exactly that loop, every call rejected with "The input
    (35516 tokens) is longer than the model's context length (32768 tokens)".

    Two cases are clean:

    * exit 0 -- the model chose to stop, having emitted a text-only turn.
      With no turn leash this is how attempts normally end.
    * a turn limit fired -- the session is mid-task but structurally intact,
      ending on a completed turn. This harness no longer imposes one, but it
      exits 1 when it fires, so keying on the return code alone would refuse to
      resume and throw away everything the agent had learned. Kept for runs
      made against an older config.
    """
    return exit_code == 0 or bool(_TURN_LIMIT_STOP.search(output or ""))


@dataclass
class MigrationResult:
    success: bool
    attempts: int
    # How far this agent got, so the arms can be compared when neither
    # converges. Raw token totals cannot do that: run 28's token_ratio of
    # 1.543 read as "memory saved 35%" while warm had made 71 LLM calls to
    # cold's 132 -- cheaper because it did less. Per completed attempt warm
    # actually cost MORE.
    #
    # Both are read off the orchestrator's own independent test runs, never
    # the model's claims. `errors_cleared` counts distinct pytest error
    # signatures the agent moved the suite through, which is a real depth
    # measure here because the failures are a chain. `best_passed` is the
    # high-water mark of tests passing.
    errors_cleared: int = 0
    best_passed: int = 0
    last_signature: str | None = None


def _shim(name: str, argv: list[str]) -> Path:
    """An argument-less executable in MCP_SHIM_DIR that execs `argv`.

    Exists because Vibe echoes an MCP server's whole launch command back to the
    model on every tool result, so the command is part of the agent's context
    whether we like it or not. Behind this, the model sees one path in a
    directory holding nothing but these shims.

    `exec "$@"` via a quoted here-list rather than string interpolation:
    `--password=` can contain anything, and a shell-quoting bug here would
    either break the server or, worse, leak the argument into an error message.

    Mode 0700. That is not a boundary against the AGENT -- it runs as the same
    user and could read this file with `bash` if it went looking. What it stops
    is the credential arriving unbidden in the model's context on every single
    memory call, which is what was happening. Real isolation would need the
    server to run as another user, or the secret to reach it by a channel Vibe
    does not echo."""
    MCP_SHIM_DIR.mkdir(parents=True, exist_ok=True)
    MCP_SHIM_DIR.chmod(0o700)
    path = MCP_SHIM_DIR / name
    quoted = " ".join(shlex.quote(a) for a in argv)
    path.write_text(f'#!/bin/sh\nexec {quoted}\n')
    path.chmod(0o700)
    return path


def render_config(
    base_url: str,
    model: str,
    *,
    vibe_home: Path = VIBE_HOME,
    active_model_alias: str = "devstral-local",
    auto_compact_threshold: int | None = None,
    memory_enabled: bool = False,
    step_hook_port: int | None = None,
    agent_label: str | None = None,
) -> None:
    """Render a clean $vibe_home/config.toml: the self-hosted provider/model
    route (docs.mistral.ai/vibe/code/cli/offline-models) plus MCP servers.
    Deletes the file first, so repeated runs never accumulate duplicate
    [[providers]]/[[models]] blocks.

    One `vibe_home` per AGENT, not per swarm: each needs its own config,
    api_base and session logs so `--continue` resumes its own session.

    `auto_compact_threshold` -- Vibe's default (200,000) assumes a
    large-context model and never fires before a 32k model's own limit does.

    `memory_enabled` is the ONLY difference between the arms. False (every
    cold agent) means no neo4j-agent-memory MCP block is written at all, so
    that agent has no path to Neo4j -- not a gated one, none.

    `web` is registered for EVERY agent, warm and cold. It is not part of the
    comparison but a baseline capability the task requires: migrating
    email_check.py means replacing `EmailStr.validate()` with the
    `email_validator` package, and the traceback never names another library,
    so a model without lookup plateaus at 2 of 3 files. Published as
    `web_lookup`, deliberately not `web_search` -- Vibe names MCP tools
    f"{alias}_{tool}" and `disabled_tools` below kills the native `web_search`
    by name after MCP registration, which would take this server's tool with
    it."""
    config_generated = vibe_home / "config.toml"
    vibe_home.mkdir(parents=True, exist_ok=True)
    if config_generated.exists():
        config_generated.unlink()
    # active_model MUST come before any [[table]] header: TOML attaches a bare
    # `key = value` to the last-opened table, so writing it after `vibe mcp
    # add`'s [[mcp_servers]] block silently makes it a property of that server
    # and Vibe falls back to its built-in hosted default.
    #
    # NOTHING IS DISABLED except one tool that cannot work here, named below.
    #
    # `task` and `skill` used to be off, on a judgement about whether an 8B
    # should be delegating its task to a read-only explorer. That was a limit
    # on what the agent was allowed to try, decided by this harness rather than
    # by the agent, and it is gone. `disabled_skills = ["*"]` is gone with it.
    #
    # The exception is the NATIVE `web_search`, and it is not a judgement: it
    # is `vibe/core/tools/builtins/web_search.py`, which resolves
    # MISTRAL_API_KEY and calls Mistral's hosted conversations API. This run
    # serves a local model through SGLang and strips MISTRAL_API_KEY from the
    # agent's environment (see _STRIPPED_ENV), so the tool can only ever raise
    # "MISTRAL_API_KEY environment variable not set." Leaving it advertised
    # would not give the agent a capability, it would give it a trap. The
    # capability itself is present and working, as the `web_lookup` MCP tool
    # registered below for both swarms.
    #
    # disabled_tools belongs in the config, NOT on the command line --
    # `--disabled-tools web_search` leaves the tool in the `tools` array sent
    # to the model. Confirmed by capturing the request body both ways.
    config_generated.write_text(
        f'active_model = "{active_model_alias}"\n'
        'disabled_tools = ["web_search"]\n'
    )

    # $VIBE_HOME/hooks.toml -- Vibe's own per-step extension point, loaded by
    # core/config/harness_files/_harness_manager.py. WARM ONLY: a cold agent
    # gets no hooks.toml at all, so there is no hook process, no latency and no
    # path to the graph, matching how its MCP server is simply absent rather
    # than gated.
    #
    # This is what per-step memory runs on. See orchestrator/step_memory.py for
    # the loop and for why the command is a stdlib-only client rather than the
    # work itself.
    #
    # `match = "*"` on purpose: Vibe's matcher takes one glob per hook entry
    # (name_matches(tool_name, [hook.match or "*"]) in core/hooks/_post_tool.py),
    # so filtering to the evidence-producing tools here would mean one hooks.toml
    # entry per tool name and a second place to keep that list. The client costs
    # one loopback round-trip and the sidecar drops non-evidence tools in
    # _EVIDENCE_TOOLS, so the decision lives in exactly one place.
    #
    # `timeout` is the agent's protection, not ours: it bounds how long a slow
    # or wedged graph can sit in the agent's tool-call path. The client fails
    # open well before this, so the ceiling is belt-and-braces.
    hooks_file = vibe_home / "hooks.toml"
    if hooks_file.exists():
        hooks_file.unlink()
    if memory_enabled and step_hook_port is not None and agent_label:
        command = f"{sys.executable} {STEP_HOOK_SCRIPT} {step_hook_port} {agent_label}"
        hooks_file.write_text(
            "[[hooks]]\n"
            'name = "agent-memory-step"\n'
            'type = "post_tool"\n'
            'match = "*"\n'
            "timeout = 10.0\n"
            'description = "Record this step in the shared reasoning graph and '
            'surface what other agents hit here."\n'
            f'command = "{command}"\n'
            "\n"
            # post_tool cannot see a turn that called no tool -- and those are
            # 15% of this model's reasoning, including every turn where it
            # declares itself finished while the suite still fails. post_agent
            # fires when Vibe's loop ends and carries transcript_path, which is
            # enough to pick them up. No `match`: the field is only valid for
            # tool hooks (HookConfig._apply_defaults_and_constraints).
            "[[hooks]]\n"
            'name = "agent-memory-final-turn"\n'
            'type = "post_agent"\n'
            "timeout = 10.0\n"
            'description = "Record the turns this agent ended without calling '
            'a tool."\n'
            f'command = "{command}"\n'
        )

    env = dict(os.environ)
    env["VIBE_HOME"] = str(vibe_home)
    # The same private HOME the agent itself will run under (see AGENT_HOMES).
    # `vibe mcp add` resolves global config off HOME as well, so registering
    # servers under the real one and then running under a different one would
    # write the config in a place the agent never reads.
    env["HOME"] = str(agent_home_for(vibe_home))
    env.update(_SHARED_CACHE_ENV)

    # Web search, for BOTH swarms -- see the docstring. Two things that look
    # incidental and are not:
    #   * its OWN venv, because fastmcp needs mcp>=2 and mistral-vibe pins
    #     mcp==1.28.1, and installing both removes EVERY MCP tool from the
    #     model;
    #   * OPENAI_API_KEY via --env, because MCP stdio servers inherit only a
    #     minimal curated environment (get_default_environment).
    # NOTES-hard-won.md, "MCP servers need their own venvs".
    subprocess.run(
        [
            str(VIBE_BIN), "mcp", "add", "web",
            "--transport", "stdio",
            # See MCP_SHIM_DIR: the command is echoed to the model verbatim on
            # every tool result, so it must not name this repo.
            "--command", str(_shim("web-server", [
                str(WEB_TOOLS_PYTHON), str(WEB_TOOLS_SERVER),
            ])),
            "--env", f"OPENAI_API_KEY={env['OPENAI_API_KEY']}",
        ],
        env=env,
        check=True,
        capture_output=True,
    )

    if memory_enabled:
        # neo4j-agent-memory's MCP server, registered the way its README says
        # to -- `uvx "neo4j-agent-memory[mcp]" mcp serve --password <pw>`.
        # Nothing here is built, wrapped, vendored or renamed. Warm agents
        # only; a cold agent never gets this block, so it has no path to Neo4j
        # at all.
        #
        # Four deviations from the bare one-liner, each because the one-liner
        # does not work here. All four were silent failures -- the server came
        # up, published every tool, and answered with an error string:
        #
        #   [mcp,openai]  the default embedder is OpenAI's and [mcp] does not
        #                 pull the client in.
        #   --with httpx  packaging bug: _connect_bolt() imports
        #                 nams._unsupported -> nams/transport -> httpx, but
        #                 httpx is declared only by the `nams` extra, and
        #                 [openai] brings openai 3.x which uses httpx2.
        #   --embedding   the server builds its OWN client, so its embedder
        #                 must match this orchestrator's or it opens the six
        #                 vector indexes at the wrong dimension.
        #   --backend     pinned to bolt, or the server silently switches to
        #                 the hosted NAMS service if MEMORY_API_KEY is around.
        #
        # `--arg=--with`, not `--arg --with`: argparse reads a bare `--with` as
        # a flag of its own. Same for the = form on the args below.
        # NOTES-hard-won.md, "MCP servers need their own venvs".
        subprocess.run(
            [
                str(VIBE_BIN), "mcp", "add", "neo4j-agent-memory",
                "--transport", "stdio",
                "--command", str(_shim("memory-server", [
                    "uvx", "--with", "httpx",
                    "neo4j-agent-memory[mcp,openai]", "mcp", "serve",
                    f"--uri={NEO4J_URI}",
                    f"--password={NEO4J_PASSWORD}",
                    f"--embedding={EMBEDDING_MODEL}",
                    "--backend=bolt",
                ])),
                # Every one of these args used to be echoed to the model on
                # every memory call, `--password=` included. Behind a shim
                # instead -- see MCP_SHIM_DIR. The uvx invocation itself is
                # unchanged, argument for argument.
                "--arg", "mcp", "--arg", "serve",
                "--env", f"OPENAI_API_KEY={env['OPENAI_API_KEY']}",
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


# NOT OURS. This is neo4j-agent-memory's own MCP server instructions, imported
# and relayed verbatim -- "ALWAYS at conversation start: Call
# memory_get_context", "FOR complex tasks: Call memory_start_trace ...
# memory_record_step ... memory_complete_trace", and so on. Warm agents only,
# since only warm has that server registered.
#
# It has to be relayed by hand because VIBE DROPS IT. An MCP server returns
# `instructions` in its initialize result precisely so the host can put them in
# the model's system context -- the package's own docstring says "injected into
# the LLM's system context by the host" -- and the server sends 1,935
# characters of them (profile defaults to "extended", the 16-tool set we get).
# Vibe never reads the field: all three of its `session.initialize()` call
# sites discard the return value (core/tools/mcp/tools.py:156, :188, :418) and
# its descriptor model keeps only name/description/inputSchema/outputSchema
# (core/tools/mcp/descriptor_cache.py:41).
#
# That is the whole reason 40 consecutive runs ended with zero agent-initiated
# memory calls while the same agents used bash/grep/edit/read_file throughout.
# The tools were registered, the server was live and smoke-tested, the model
# was willing -- it was never told what the tools were for, because the one
# mechanism the package authors provided for telling it does not survive the
# host. It is not a model failure and it is not a wiring failure.
#
# So this is a passthrough, deliberately containing not one word of our own.
# The previous version of this constant was hand-written guidance, i.e. an
# unwitting reimplementation of a shipped payload -- and a worse one: it
# pre-formatted a call as `memory_search(query, memory_types=[...])`, and the
# model copied that into message CONTENT instead of making a tool call, ending
# an attempt after 2 turns having touched nothing. Do not write guidance here.
# If it needs to say something different, that belongs upstream in the package
# or in Vibe, not in this file.
_MEMORY_TOOLS_GUIDE = get_instructions("extended")


def _task_prompt(
    last_error: str | None,
    memory_enabled: bool = False,
) -> str:
    """The user's request, and nothing else of ours.

    The code is in Vibe's own current directory. Nothing here tells the agent
    how its work is graded, because it isn't graded here -- the real suite runs
    separately, in Daytona, after Vibe's turn ends.

    This used to be ~2,500 tokens: how to invoke pytest and why to pipe stderr,
    that `tests/` is the specification, that `edit` matches byte-for-byte
    including leading indentation, not to resend a failed edit, to prefer
    relative paths, which error classes should trigger a lookup, and "keep
    going until the suite passes". Every line of it was written off a real
    measurement, and every line of it was also us doing the agent's job for
    it -- teaching a coding agent to use its own editor, inside the harness
    whose whole point is that the agent can code. If the model needs to be
    told how `edit` matches, that belongs in `edit`'s own tool description,
    upstream in Vibe, where every Vibe user would get it. It does not belong
    here, where it silently becomes part of what this experiment claims to be
    measuring.

    So it is gone, and what remains is the sentence a user would type plus the
    operator's own ordering of the work. The failure modes the old prompt
    papered over are still observable rather than prompted away: failed-edit
    retry loops show up in ATTEMPT_DONE's `tools` counter, and a `pydantic.v1`
    shim shows up as ATTEMPT_REJECTED.

    NOT identical between swarms any more, by instruction. The warm list has
    three extra steps and a closing note, because they concern tools cold does
    not have -- telling an agent with no memory server to consult it is an
    instruction it cannot follow. The consequence is that the two arms now
    differ by more than the presence of memory: warm's list is longer, so warm
    reads more tokens before it starts and has more steps to work through. That
    is a real asymmetry in the comparison and it is deliberate."""
    steps = [
        "Review the entire codebase, so you understand how everything is connected.",
        # `web_lookup`, not `web_search`. Vibe's native web_search is killed by
        # name in every agent's config -- it routes through Mistral's hosted
        # API and this repo's key returns 429 on every call -- so an agent told
        # to use it finds no such tool. See harness/web-tools/server.py.
        "Use web_lookup to review the Pydantic docs, specifically those about "
        "migration.",
        "Plan the migration before you change any code.",
    ]
    if memory_enabled:
        steps += [
            "Use your memory tools to see what other agents have attempted before "
            "and what they failed on.",
            "Review your plan in light of previous agents' mistakes.",
        ]
    steps += [
        "Edit the plan in accordance with that new information.",
        "Make your edits.",
        # Was "Validate the code in Daytona", which the agent cannot do: that
        # suite runs in a sandbox the orchestrator owns, after this invocation
        # has already ended.
        #
        # Telling the agent to run the suite itself ("Run the test suite
        # yourself after each change and keep going until it passes") was tried
        # on 2026-09-16 and REVERTED: it moved pytest invocations from an
        # unverified baseline to 1 agent out of 4, once, and changed nothing
        # else -- 0 tests passing either way. It was also aimed at the wrong
        # target. The same run showed warm-0 making 7 file operations, 7 of
        # them OUTSIDE its own checkout, so an agent that did run the suite
        # would have been testing a directory it had not edited.
        "When you are finished, your code will be validated externally. You "
        "will receive the errors from the test suite.",
        "Review any errors.",
        "Now research those errors with web_lookup.",
    ]
    if memory_enabled:
        steps.append(
            "Use your memory tools to understand if any previous agent has "
            "received similar errors."
        )
    steps += [
        "Review the codebase again.",
        "Make a new plan to fix only these errors.",
        "Continue iteratively until the migration is complete.",
    ]
    base = (
        "Please migrate this codebase from Pydantic v1 to Pydantic v2.\n\n"
        + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    )
    if memory_enabled:
        base += (
            "\n\nNote: throughout your work, based on what you say and do, you "
            "will receive information about other agents' past attempts.\n\n"
            "You do not have to follow them. They are additional information "
            "for you to consider in light of your current actions."
        )
    # The task first, byte-identical for both swarms so SGLang's RadixAttention
    # can share the prefix across every agent in the run. (It once came second,
    # after a retrieved-memory block; warm-1 then spent three attempts
    # reporting on the memory instead of migrating anything, which is a
    # reasonable thing to do when you are handed a page of prose before you are
    # told what the job is.)
    #
    # There is no retrieved-memory block any longer. Warm gets the memory
    # server's own instructions and does its own retrieval -- see
    # migrate_codebase().
    if memory_enabled:
        base += "\n\n" + _MEMORY_TOOLS_GUIDE
    # The one thing the agent genuinely cannot see for itself: the verdict from
    # a suite that ran somewhere else, in Daytona, after its turn ended. Stated
    # and not editorialised -- the advice that used to follow it ("keep going
    # until the suite passes", which errors mean to look something up) was us
    # steering, and the agent can read a traceback.
    if last_error:
        base += (
            f"\n\nThe test suite still fails:\n```\n{last_error}\n```"
        )
    return base


def _entry_text(entry: dict) -> str:
    """Text out of one streamed history entry.

    A message's `content` is a list of ContentBlocks (`{"type": "text",
    "text": ...}`); a reasoning entry carries a flat `text`.
    """
    if entry.get("text"):
        return str(entry["text"])
    content = entry.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n\n".join(
            str(b.get("text", ""))
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


def _entry_consumer(
    mem: ScopedMemory,
    session_id: str,
    step_memory: Any | None,
    agent_label: str | None,
) -> Callable[[dict], Awaitable[None]]:
    """Consume Vibe's streamed history entries into memory, as they happen.

    This is the half of per-step memory the `post_tool` hook cannot supply,
    and between them nothing the old transcript replay captured is lost:

      * `type="message"`, role assistant -> short_term.add_message. The only
        source of :Message nodes, and so the only input to entity extraction
        (verified: add_step has no extraction path at all). Stored with
        extract_entities=False and extracted in one batch at end of run --
        see ScopedMemory.extract_entities_from_session.
      * `type="reasoning"` -> handed to the step hook as the pending thought
        for this turn. Reasoning entries complete BEFORE the tool calls they
        justify, so the most recent one is the reasoning behind the next step
        recorded. This replaces reading `messages.jsonl`, which could not
        work: Vibe flushes the transcript once per turn, after the tool loop,
        so at post_tool time the message that issued the call is not on disk.

    `user` entries are deliberately not stored. They are the orchestrator's
    own prompt, and storing them makes memory retrieve its own previous
    output -- attempt N's prompt embedding attempt N-1's memory block.
    Measured at 15,170 characters and growing before it was removed.
    """
    async def consume(entry: dict) -> None:
        kind = entry.get("type")
        # EVERY entry, of every type, reports the turn it belongs to: turn_id
        # lives on Vibe's _PublicHistoryEntryBase. That is what lets the step
        # hook tell "another tool call in the same turn" (share the reasoning)
        # from "a new turn that emitted none of its own" (do not). See
        # StepMemoryService.note_turn().
        if step_memory is not None and agent_label:
            step_memory.note_turn(agent_label, entry.get("turn_id"))
        if kind == "reasoning":
            text = _entry_text(entry)
            if text and step_memory is not None and agent_label:
                step_memory.set_pending_reasoning(
                    agent_label, text, entry.get("turn_id")
                )
            return
        if kind == "message" and entry.get("role") == "assistant":
            text = _entry_text(entry)
            if text:
                await mem.add_message(
                    session_id, "assistant", _cap(text), extract_entities=False
                )

    return consume


async def _run_vibe(
    task: str,
    timeout_s: float,
    *,
    vibe_home: Path = VIBE_HOME,
    cwd: Path = HARNESS_DIR,
    resume: bool = False,
    on_entry: Callable[[dict], Awaitable[None]] | None = None,
) -> tuple[int, str]:
    """Run Vibe exactly as a person would, and wait for it to finish.

    No `--max-turns`. The agent decides when it is done; a Vibe run ends by
    itself when the model stops calling tools. The attempt still gets graded
    afterwards, because Vibe returning is what the grader waits on.

    `timeout_s` is the RUN's remaining wall clock minus the verdict reserve,
    computed by the caller -- never an invented per-call number. It is not a
    leash on the agent: it is the point past which there would be no time left
    to find out what the agent achieved, and an attempt it cuts is still
    graded on the tree as it stands.

    `cwd` matters as much as `vibe_home`: Vibe's config resolution checks
    `<cwd>/.vibe/config.toml` first as a project-local layer, and that layer
    wins whenever the file exists. A freshly seeded checkout has no `.vibe`,
    which is what makes a sibling `vibe_home` safe -- but a stale one left in
    `cwd` will silently override a correctly-rendered config.

    No `--enabled-tools` filter and nothing disabled in config.toml either:
    Vibe gets its full native toolset, exactly as a local invocation would.
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
    # See AGENT_HOMES: a private empty HOME, so Vibe's global skills directory
    # (`~/.agents/skills`) is the run's and not the operator's. Caches stay
    # pointed at the real ones so `uvx` still starts the memory MCP server from
    # its existing 30GB cache instead of re-downloading.
    env["HOME"] = str(agent_home_for(vibe_home))
    env.update(_SHARED_CACHE_ENV)

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
        # `streaming`, not `text`: "newline-delimited JSON per message"
        # (cli/programmatic.py). Each completed history entry is written as one
        # JSON object as it happens, and the entry types are the reason this
        # matters (app_server/models.py):
        #
        #   type="message"    role, content, turn_id  -> the agent's messages
        #   type="reasoning"  text, turn_id           -> its ACTUAL reasoning
        #   type="effect"     tool_name, input, state -> its tool calls
        #
        # `text` gave only a human-readable blob at the end, which is why the
        # agent's reasoning had to be scavenged from `messages.jsonl`
        # afterwards -- and why that failed: Vibe saves the transcript once per
        # TURN (agent_loop/_loop.py:2110, after the inner tool loop), so when a
        # post_tool hook fires the message that issued the call is still only
        # in memory. Measured on a live run: every step fell back to recording
        # tool-input JSON as its `thought`, 100% of the time.
        "--output", "streaming",
        cwd=str(cwd),
        env=env,
        # DEVNULL, not inherited. Vibe calls get_prompt_from_stdin()
        # (cli/cli.py:463) unconditionally before it dispatches, and that
        # function does a blocking `sys.stdin.read()` for ANY stdin that is not
        # a TTY -- it exists so `echo "do this" | vibe -p` works.
        #
        # This subprocess used to inherit the orchestrator's stdin. Run it from
        # an interactive terminal and stdin is a TTY, isatty() short-circuits,
        # and nothing happens. Run it any other way -- `nohup`, `&`, a redirect,
        # CI, a supervising harness -- and stdin is a pipe that never reaches
        # EOF, so every single agent blocks inside that read forever, before its
        # first LLM call. Confirmed by stack-sampling a hung agent: the main
        # thread sits in _io_FileIO_readall_impl -> read(), and the proxy's
        # /usage shows 0 requests.
        #
        # The symptom is a run that burns its whole deadline with zero tokens,
        # which is indistinguishable from a dead endpoint -- the exact failure
        # class preflight() was written to catch, arriving from inside instead.
        # DEVNULL gives an immediate EOF, so the function returns None and Vibe
        # uses --prompt as it should.
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Read stdout LINE BY LINE as it arrives, rather than proc.communicate(),
    # which buffers to exit. The point of the streaming format is that entries
    # are consumable while the agent is still working; collecting them at the
    # end would be the transcript replay again with extra steps.
    #
    # stderr is drained concurrently. It has to be: it is a pipe, Vibe writes
    # warnings to it, and a full stderr pipe blocks the child mid-write while
    # we sit reading stdout -- a deadlock that looks exactly like a hung agent.
    lines: list[str] = []

    async def pump_stdout() -> None:
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip("\n")
            lines.append(line)
            if on_entry is None:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # not every line is an entry; ignore the rest
            try:
                await on_entry(entry)
            except Exception:
                # Consuming an entry must never kill the agent's invocation.
                pass

    async def pump_stderr() -> bytes:
        assert proc.stderr is not None
        return await proc.stderr.read()

    try:
        _, err = await asyncio.wait_for(
            asyncio.gather(pump_stdout(), pump_stderr()), timeout=timeout_s
        )
        await proc.wait()
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, f"vibe invocation timed out after {timeout_s:.0f}s"
    return proc.returncode, "\n".join(lines) + err.decode(errors="replace")


def _transcript_files(vibe_home: Path) -> list[Path]:
    """Every session transcript under this agent's VIBE_HOME, including the one
    a `--continue` resumed."""
    root = vibe_home / "logs" / "session"
    if not root.is_dir():
        return []
    return sorted(root.glob("*/messages.jsonl"))


def _assistant_turns_total(vibe_home: Path) -> int:
    """Assistant messages across ALL of this agent's sessions.

    Monotonic, which `_steps_used` is not: that one reads only the newest
    session (correctly, since that is what `--continue` resumes), so when an
    attempt starts a FRESH session its count legitimately drops. Comparing
    newest-before against newest-after would therefore mark a productive
    attempt as having done nothing whenever it did not resume -- which is most
    attempts. This is the total, so "did a turn complete" is just
    `after > before`."""
    total = 0
    for f in _transcript_files(vibe_home):
        for line in f.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("role") == "assistant":
                    total += 1
            except json.JSONDecodeError:
                continue
    return total


# Read-side memory tools, by their BARE package names. Matched as a suffix,
# because Vibe publishes an MCP tool as f"{server_alias}_{tool}" -- the config
# registers the server as "neo4j-agent-memory", so what actually lands in the
# transcript is `neo4j-agent-memory_memory_get_context`.
#
# This cost a finding. The first time an agent ever called memory for itself
# (warm-0, attempt 1, right after the package's own instructions started
# reaching the model) the counter read 0 and MEMORY_READ did not fire, because
# the filter tested `startswith("memory")` against a name beginning "neo4j-".
# The one event that exists to say "the agent retrieved something" reported
# nothing on the only occasion it had ever been true.
_MEMORY_READ_TOOLS = (
    "memory_get_context",
    "memory_search",
    "memory_get_conversation",
    "memory_get_entity",
    "memory_get_observations",
    "memory_list_sessions",
    "memory_export_graph",
    "graph_query",
)


def _is_memory_read(tool_name: str) -> bool:
    return any(tool_name.endswith(t) for t in _MEMORY_READ_TOOLS)


def _is_memory_tool(tool_name: str) -> bool:
    """Any memory tool, read or write -- the `memory_calls` counter.

    Suffix/substring match for the same aliasing reason as _is_memory_read.
    `graph_query` is included: read-only Cypher against the same graph is the
    package's own escape hatch and counts as the agent using its memory."""
    return "memory_" in tool_name or tool_name.endswith("graph_query")


def _tool_calls_total(vibe_home: Path) -> Counter:
    """Every tool the MODEL chose to call, by name, across all its sessions.

    Monotonic like `_assistant_turns_total`, and for the same reason.

    This exists because the most important fact about the warm arm was
    unmeasured: whether the agent ever *asks* for memory. The 16
    neo4j-agent-memory MCP tools are advertised to every warm agent (their
    descriptor is on disk under logs/mcp-descriptors) and the prompt tells it
    to call `memory_search` when an attempt fails. Counted afterwards off the
    transcripts: 36 edit, 20 read_file, 8 bash, 6 grep, 1 web_lookup, and
    *zero* memory_* calls across 15 sessions.

    So retrieval was happening only in the orchestrator, once per attempt, and
    nothing in the run log distinguished that from an agent doing it itself.
    Emitting this on ATTEMPT_DONE makes the difference visible while a run is
    happening instead of a week later."""
    counts: Counter = Counter()
    for f in _transcript_files(vibe_home):
        for line in f.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                name = fn.get("name") or tc.get("name")
                if name:
                    counts[name] += 1
    return counts


def _steps_used(vibe_home: Path) -> int:
    """Vibe's own `stats.steps` for the session that `--continue` will resume.

    `--max-turns` is CUMULATIVE over a resumed session, not per invocation.
    TurnLimitMiddleware tests `context.stats.steps - 1 >= max_turns` against
    the whole session's step count, and `--continue` restores that count along
    with the history. So a flat per-attempt allowance gives attempt 2 onward
    NO turns at all: attempt 1 spends the budget, and every later attempt
    trips the limit before its first completion call -- the agent appears to
    run, produces no tokens, changes nothing, and is still graded. Measured
    twice against the proxy's request counter, which did not move.

    `steps` is incremented in three places in core/agent_loop/_loop.py: once
    per user message (:2022), once per completed assistant turn (:2106), and
    once per compaction (:1780). Tool results do not count. So it is
    reconstructible from the transcript as `users + assistants`, and the
    allowance to pass for N further turns is `users + assistants + N`.

    Derived from the middleware arithmetic and then confirmed end to end: a
    session with 3 users and 3 assistants resumed with `--max-turns 8` ran
    exactly 2 further turns.

    Compaction is the one term this cannot see -- it bumps `steps` without
    writing a message. That direction is safe: it can only make an attempt
    slightly shorter than its allowance, never zero it.

    Counted off the transcript rather than tracked in a variable because the
    transcript is what Vibe itself restores from; an in-memory counter would
    drift the moment an attempt times out or is retried."""
    files = _transcript_files(vibe_home)
    if not files:
        return 0
    # The newest session directory is the one `--continue` resumes (names are
    # session_<YYYYMMDD>_<HHMMSS>_<id>, so lexical order is chronological).
    steps = 0
    for line in files[-1].read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("role") in ("user", "assistant"):
            steps += 1
    return steps


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
    tests_delta: int = 0,
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

    if tests_delta > 0:
        # The error signature is unchanged but MORE TESTS PASS, and the two
        # facts are independent: the first failure can stay identical while a
        # later test starts passing. Saying only "did NOT help" here put the
        # summary in direct contradiction with the trace's own success flag --
        # migrate_codebase() sets `resolved = success or advanced`, and
        # `advanced` keys on exactly this delta. Observed in the graph:
        # attempt 7 stored with success=True under a summary reading "This
        # change did NOT help". Retrieval ranks on the flag and a reader reads
        # the text, so the two disagreeing is worse than either being wrong.
        return (
            f"The suite still fails with the same first error:\n{prior_error}\n\n"
            f"But {tests_delta} more test(s) pass than before, so this change "
            f"did help -- it just did not get past that error:\n{diff}"
        )

    return (
        f"This change did NOT help. The suite still fails with the same error, "
        f"and no additional tests pass:\n"
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
    step_memory: Any | None = None,
    agent_label: str | None = None,
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
        get_context(...)    -> NOT called here. The agent calls
                               memory_get_context itself, over MCP, as its
                               server's instructions tell it to.
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
    last_ended_cleanly: bool = False
    # Seeded with the baseline so the starting failure is not counted as one
    # this agent cleared; errors_cleared subtracts one for it.
    seen_signatures: set[str] = {baseline_signature} if baseline_signature else set()
    best_passed: int = baseline_passed
    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        # An attempt is only worth starting if it can still afford its own
        # verdict. Starting one with less than that left is what produced 19
        # consecutive runs of ungraded work: Vibe ran, the clock expired, and
        # the Daytona check got 0.0 seconds and raised.
        if remaining <= VERDICT_RESERVE_S:
            break
        attempt += 1
        await emit("ATTEMPT_START", attempt=attempt)

        trace_id = None

        # What this attempt is actually up against. Attempt 1 has nothing to
        # go on yet; from attempt 2 it is the previous attempt's real failure,
        # as read by the orchestrator off its own independent pytest run.
        trace_task = last_signature or task_desc

        if mem is not None:
            assert session_id is not None
            # NO get_context() HERE ANY MORE, and that is the point.
            #
            # This used to call MemoryClient.get_context() itself and splice the
            # result into the prompt as a "What you remember:" block, once per
            # attempt. It retrieved real, cross-agent traces and it worked -- 17
            # reads, 3-5 hits each, sourced from warm-0/1/2/3 -- but it was the
            # orchestrator retrieving on the agent's behalf, and it is almost
            # certainly WHY the agent never retrieved anything itself. The
            # package's instructions say "ALWAYS at conversation start: Call
            # memory_get_context". An agent that already has a page of
            # remembered context at the top of its prompt has no reason to.
            #
            # It also made the claim wrong. "These agents retrieve each other's
            # reasoning" was carried by this function, not by the agents: 0
            # memory tool calls across 15 sessions while this splice ran on
            # every attempt. The graph was real, the retrieval was real, the
            # agency was ours.
            #
            # So the agent now does its own reading, with the tools it has and
            # the instructions their authors wrote (see _MEMORY_TOOLS_GUIDE).
            # MEMORY_READ is emitted from the agent's own calls instead, counted
            # off the transcript -- see ATTEMPT_DONE's `memory_calls`. If it
            # comes back zero now that the instructions actually reach the
            # model, that is the finding, and the fix for it is upstream in
            # Vibe, not another splice here.
            #
            # start_trace stays: a trace has to exist before steps can hang off
            # it, and the agent is separately instructed to open its own. Two
            # traces for one attempt is honest -- one is what happened, one is
            # what the agent chose to record.
            trace = await mem.start_trace(session_id, task=trace_task)
            trace_id = trace.id
            # Hand this attempt's trace to the step hook. Vibe's post_tool
            # payload carries the tool call and the agent's cwd, but nothing
            # about attempts or traces -- so the sidecar has to be told which
            # trace the steps it is about to receive belong to.
            if step_memory is not None and agent_label:
                step_memory.set_trace(agent_label, trace_id)

        task = _task_prompt(last_error, memory_enabled=mem is not None)
        before_snapshot = _snapshot(repo_dir)
        turns_before = _assistant_turns_total(vibe_home)
        tools_before = _tool_calls_total(vibe_home)
        try:
            # Resume only a session that ended cleanly -- see _ended_cleanly()
            # for what that means and why it is not an exit-code check.
            resume = attempt > 1 and last_ended_cleanly
            # Unleashed: the agent ends its own attempt. The only bound is
            # what is left of the RUN's clock after reserving the verdict --
            # see _run_vibe() on why that is the run's budget rather than a
            # cap on the agent.
            vibe_exit_code, vibe_output = await _run_vibe(
                task,
                timeout_s=max(1.0, deadline - time.monotonic() - VERDICT_RESERVE_S),
                vibe_home=vibe_home, cwd=vibe_cwd,
                resume=resume,
                on_entry=(
                    _entry_consumer(mem, session_id, step_memory, agent_label)
                    if mem is not None and session_id else None
                ),
            )
            last_ended_cleanly = _ended_cleanly(vibe_exit_code, vibe_output)

            # Did the agent actually take a turn? If Vibe exited without
            # completing one, the tree is byte-identical to the last attempt's,
            # so grading it spends a Daytona sandbox to re-derive a verdict we
            # already have, and records a trace saying "no edit was made" that
            # retrieval will later surface as if it were knowledge.
            #
            # This happens under load: the LLM calls fail, Vibe retries with
            # backoff and exits without a turn. Observed in one 2-a-side run --
            # 3 of warm-1's 4 attempts and 2 of cold-0's had a session
            # containing the prompt and ZERO assistant messages, each still
            # graded, each burning ~135s. It is the "Server disconnected"
            # failure the README lists, arriving one level down.
            #
            # Aborted rather than graded, and emitted so it is countable. The
            # trace is closed honestly: it is not a verdict on anything.
            #
            # This used to interpolate `ScopedMemory._NO_VERDICT`, a sentinel
            # that the deleted hand-rolled retrieval layer filtered on. Both
            # the constant and the filter went with that layer, and the
            # reference did not -- so every warm agent that hit this branch
            # died with AttributeError, and the run reported "0 attempts" for
            # the whole warm swarm. Plain text now, because nothing filters on
            # it any more and pretending otherwise is how that happened.
            # (An aborted attempt has no steps, so search_steps cannot surface
            # it regardless.)
            if _assistant_turns_total(vibe_home) <= turns_before:
                if mem is not None and trace_id is not None:
                    await mem.complete_trace(
                        trace_id,
                        outcome="no verdict; the agent completed no turn",
                        success=False,
                    )
                await emit(
                    "ATTEMPT_ABORTED",
                    attempt=attempt,
                    reason="vibe completed no assistant turn",
                    vibe_exit_code=vibe_exit_code,
                    vibe_stop=stop_reason(vibe_output),
                )
                attempt -= 1  # it did not happen; do not inflate the count
                await asyncio.sleep(5.0)  # don't spin on a saturated endpoint
                continue
            # NO TRANSCRIPT REPLAY HERE ANY MORE. The agent's steps were
            # already written, by the agent, as it took them -- Vibe's
            # `post_tool` hook calls add_step/record_tool_call at each tool
            # call (orchestrator/step_memory.py). This is the whole point: the
            # steps in the graph are now the agents' own, not ours read back
            # off their logs after the fact.
            #
            # What that also removed: the replay cost 45.5s per attempt on run
            # 47 (0.50s per message, almost all of it serialized OpenAI
            # embedding round-trips) against a Vibe turn of 20-40s, and only
            # warm paid it -- which is most of why cold completed 21-28
            # attempts per run across runs 44-47 while warm completed 8-10.
            # The hook pays one loopback round-trip per tool call instead, and
            # defers embedding to complete_trace's batch.
            file_contents = _collect_file_contents(repo_dir)
            # Gets its own reserved slice rather than `deadline - now`. That
            # expression is the bug that made this project measure nothing: by
            # the time Vibe had consumed the rest of the clock it evaluated to
            # 0.0, so the ONE thing that decides success never ran. The reserve
            # is granted even slightly past the deadline -- a verdict a few
            # seconds late is worth having; no verdict is worth nothing.
            result = await asyncio.wait_for(
                pool.run_pytest(file_contents=file_contents, test_command=test_command),
                timeout=VERDICT_RESERVE_S,
            )
            await emit("SANDBOX_CREATED", create_ms=result.create_ms)
        except asyncio.TimeoutError:
            # The run's shared clock expired mid-attempt. That is the deadline
            # doing its job, not a failure, and it must not discard what this
            # agent already achieved: agent_worker used to receive an exception
            # here, retry, immediately re-check the deadline and report
            # MigrationResult(False, 0). Run 30 printed "0 attempts" for both
            # swarms off the back of that, after 21 cold and 5 warm attempts had
            # actually started.
            if mem is not None and trace_id is not None:
                await mem.complete_trace(
                    trace_id,
                    outcome="ran out of time mid-attempt; no verdict for this one",
                    success=False,
                )
            break
        except Exception:
            if mem is not None and trace_id is not None:
                await mem.complete_trace(trace_id, outcome="error", success=False)
            raise

        tools_used = _tool_calls_total(vibe_home) - tools_before
        # MEMORY_READ now reports the AGENT's retrieval, not the orchestrator's.
        # It fires once per attempt in which the agent called a read-side memory
        # tool itself, and does not fire at all when it did not -- which is the
        # honest signal, and the one this event was always supposed to carry.
        # `hits` is how many such calls it made; `sources` names them, so a run
        # log distinguishes memory_get_context from graph_query.
        agent_reads = {k: v for k, v in tools_used.items() if _is_memory_read(k)}
        if agent_reads:
            await emit(
                "MEMORY_READ",
                attempt=attempt,
                hits=sum(agent_reads.values()),
                sources=sorted(agent_reads),
                chars=0,
                query=trace_task[:120],
            )
        await emit(
            "ATTEMPT_DONE",
            attempt=attempt,
            exit_code=result.exit_code,
            vibe_exit_code=vibe_exit_code,
            # Why Vibe's turn ended, and how many turns it actually used.
            # Without these two an attempt's shape is unknowable after the
            # fact: "8 turns, hit the limit" and "1 turn, died" look identical
            # in the event log, and they mean opposite things.
            vibe_stop=stop_reason(vibe_output),
            turns_used=_steps_used(vibe_home),
            resumed=resume,
            # What the agent chose to do with its turns, and -- the point of
            # the warm/cold comparison -- whether it ever asked the graph
            # anything itself. See _tool_calls_total().
            tools=dict(tools_used),
            memory_calls=sum(
                v for k, v in tools_used.items() if _is_memory_tool(k)
            ),
        )

        success = result.exit_code == 0
        signature = error_signature(result.output)
        passed = tests_passed(result.output)

        # Two holes the suite cannot see, because `tests/` comes from the real
        # merge commit and never calls a v2-only API:
        #
        #   * the pydantic.v1 compatibility shim -- rewriting every import to
        #     `from pydantic.v1 import ...` scores 32 of 33 (v1_shim_files);
        #   * behaviour deleted rather than ported -- a validator stubbed to
        #     `return values` also scores 32 of 33 (gutted_files).
        #
        # Both therefore GATE `success`: an attempt that does either has not
        # migrated the codebase, whatever pytest says, and must not be written
        # to shared memory as the exemplar every other warm agent retrieves.
        #
        # What they no longer do is rewrite `passed` and `signature`.
        #
        # Forcing `passed = 0` and replacing `signature` with a synthetic
        # sentence fed that sentence straight into `seen_signatures`, so
        # *gaming the oracle inflated `errors_cleared`* -- the metric the
        # summary uses to compare warm against cold when neither converges. A
        # shimmed attempt scored a cleared error for being caught. The real
        # tally and the real first-error line are kept intact so the progress
        # numbers stay honest, and the gate is reported on its own terms
        # instead of disguised as a pytest result.
        shimmed = v1_shim_files(file_contents)
        gutted = gutted_files(file_contents)
        if shimmed or gutted:
            success = False
            notes = []
            if shimmed:
                notes.append(
                    f"MIGRATION NOT COMPLETE: these files still import pydantic's v1 "
                    f"compatibility shim: {', '.join(shimmed)}.\n"
                    f"`from pydantic.v1 import ...` keeps the code on Pydantic v1; the task "
                    f"is to move it to v2. Import from `pydantic` (or `pydantic_settings`) "
                    f"and update the code to the v2 API instead."
                )
            if gutted:
                notes.append(
                    f"MIGRATION NOT COMPLETE: these files contain a function whose body "
                    f"was removed rather than ported: {', '.join(gutted)}.\n"
                    f"Either unreachable code follows a `return`/`raise`, or a validator "
                    f"now just hands its argument straight back. Stubbing a validator out "
                    f"makes the imports pass while silently dropping what it enforced. "
                    f"Port the original logic to the v2 API and keep it running."
                )
            # The agent is told plainly, in the same channel it gets every other
            # failure -- the fed-back pytest output. Identical for both swarms.
            # Notes go FIRST, ahead of the pytest output, not appended after
            # it. Appending put them ~85% of the way through a 5,655-character
            # prompt, buried at the end of a traceback -- and the agents
            # ignored them: in one 2-a-side run every one of the 9 graded
            # attempts was a shim, with cold-1 shimming on attempts 1, 2 AND 3
            # and warm-1 on 1 and 2. Checked rather than assumed: the
            # "MIGRATION NOT COMPLETE" block WAS present in attempt 2's
            # prompt, so the agent was told plainly and did it again.
            #
            # Whether it obeys at the top is untested, but the old placement
            # was incidental (it is where `+=` puts things) rather than chosen,
            # and this is the single most decision-relevant sentence in the
            # prompt: the suite says 32 of 33 and the work is still rejected.
            # It also now survives _trim_error_for_prompt's head/tail cut,
            # which the appended version only did by luck.
            result = replace(
                result,
                exit_code=1,
                output="\n\n".join(notes) + "\n\n" + result.output,
            )
            await emit(
                "ATTEMPT_REJECTED",
                attempt=attempt,
                shimmed=shimmed,
                gutted=gutted,
                pytest_passed=passed,
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
        #
        # `not rejected` is what the old `passed = 0` override was really for,
        # stated directly instead of by corrupting the tally: a shimmed or
        # gutted tree can pass 32 of 33, which would clear `passed >
        # last_passed` and be recorded as verified progress -- the one diff
        # that must never reach shared memory as an exemplar. Gating
        # `advanced` blocks that at the source, and leaves `signature` and
        # `passed` telling the truth for everything else.
        rejected = bool(shimmed or gutted)
        advanced = not success and not rejected and passed > last_passed
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
                            # The same delta `advanced` is computed from, so
                            # the stored summary and the stored success flag
                            # cannot contradict each other. See observed_fix().
                            tests_delta=passed - last_passed,
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
        #
        # Rejected attempts contribute to neither progress measure. Their
        # numbers are real pytest numbers, but they describe a tree that did
        # not migrate anything, so counting them would report "best tests
        # passing: 32" for a gutted validator -- which is how run 54 came to be
        # reported as the harness's best-ever result.
        if not rejected:
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
        # Not updated on a rejected attempt. A shimmed tree passing 32 would
        # otherwise raise the bar the agent has to beat above anything an
        # honest migration of the same file can reach, so the attempt that
        # un-guts the file and legitimately passes 30 would score as a
        # regression.
        if not rejected:
            last_passed = passed
        last_error = _trim_error_for_prompt(_localize_sandbox_paths(result.output, vibe_cwd))

    await emit("FILE_DONE", success=False, attempts=attempt)
    return MigrationResult(
        False, attempt,
        errors_cleared=max(0, len(seen_signatures) - 1),
        best_passed=best_passed,
        last_signature=last_signature,
    )
