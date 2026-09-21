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
import functools
import json
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from orchestrator.cognee_layer import MEMORY_TOOLS_GUIDE, uses_mcp

from orchestrator.manifest import REPO_ROOT
from orchestrator import surfaces
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
#
# `STEP_HOOK_SCRIPT` used to sit here, naming harness/memory_step_hook.py --
# the post_tool client that wrote a ReasoningStep per tool call. The file is
# archived and the constant is gone; a path to a script that does not exist
# is how a hook fails silently.
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
# 120.0 was not enough twice running. Run 7 warm-0 and run 8 warm-0 both
# lost their only verdict to it: a cold Daytona pool took 46.5s just to
# create, and on run 8 the service was returning 404s and hanging. Grading
# is the only thing that decides success, and it comes out of a 1500s clock.
VERDICT_RESERVE_S = 240.0

# HOW MANY ABORTED STARTS AN ARM TOLERATES. An abort is Vibe exiting with
# no assistant turn -- nothing was asked of the model, so nothing was
# measured. Runs 8 and 10 each saw an arm abort on a transport error and
# retry without limit, because an abort is not an exception and
# MAX_CONSECUTIVE_AGENT_FAILURES never saw it: 126 in a row on run 8, 25
# minutes of an arm producing nothing.
#
# 20 at ~7s apart is a little over two minutes of patience, which covers a
# saturated model endpoint; past that it is the harness, and the run must
# say so instead of spinning. The recycle every 5 is the measured remedy
# for the one error that has caused this twice -- see
# AgentWorkspace.recycle_control_master.
MAX_CONSECUTIVE_ABORTS = 20
ABORT_RECYCLE_EVERY = 5

# HOW MANY PLAN-ONLY TURNS AN ATTEMPT IS RE-PROMPTED THROUGH. An attempt
# that called neither `edit` nor `write_file` changed nothing, so grading
# it spends a sandbox and ~40s of the shared clock to re-derive the
# identical verdict and burns one of the attempts being counted. Measured
# on runs 10 and 11: warm's a3 (28 turns) and cold's a2 (19 turns) each
# audited the tree thoroughly, diagnosed the failure, and ended "Task
# completed." without an edit.
#
# Two retries, then the attempt is graded anyway -- an agent that will not
# edit must not eat the deadline, and the refusal belongs on the record.
MAX_CONSECUTIVE_NOOPS = 2
# How many times one attempt may be resumed after a truncated turn. Three is
# enough for the observed failure (one bad turn, then the model carries on)
# and small enough that a serving layer emitting nothing but unparseable
# calls fails the attempt rather than spinning on it. See truncated_turn().
MAX_CONTINUATIONS = 3

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


# The model's tool call, arriving as ordinary text instead of a parsed
# `tool_calls` field. Mistral's wire format for a call is
# `[TOOL_CALLS]name[ARGS]{json}`; when the serving layer fails to lift it out
# of the content, Vibe sees an assistant message with nothing to execute and
# the turn simply ends.
_TOOL_CALL_LEAK = re.compile(r"\[TOOL_CALLS\]\s*(\w+)?")
# A turn that ends on a colon is a lead-in to an action that never arrived:
# "...move to the next task - fixing the deprecated Field usage:". Syntactic
# on purpose. The first version of this asked instead whether the text
# matched a list of completion phrases ("task completed", "migration
# complete", ...), which is guesswork about one model's wording: the
# rehearsal's fake model ends every turn with "Done.", so EVERY clean turn
# was judged truncated and resumed, and attempt 1's steps doubled from 3 to
# 6 while attempt 2's live-write accounting broke outright. A false positive
# is not free -- it replays work and corrupts the step counts -- so this
# stays narrow and misses truncations rather than inventing them.
_UNFINISHED_LEAD_IN = re.compile(r":\s*$")


def _last_assistant_entry(output: str) -> dict | None:
    """The final assistant message in a streamed run, or None."""
    last = None
    for line in (output or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "message" and entry.get("role") == "assistant":
            last = entry
    return last


def truncated_turn(output: str) -> str | None:
    """Did the model mean to keep working and fail to say so parseably?

    THE FAILURE THIS EXISTS FOR, measured in experiment swarm-1789903474
    (x12sdk, 3 attempts each arm): three of the six attempts ended early
    because the final assistant message carried no executable tool call.

      * warm attempt 3 (14 turns) and cold attempt 3 (20 turns) ended with
        `[TOOL_CALLS]edit_file[ARGS]{"file_path": ...}` sitting in the
        message TEXT -- a real tool call the serving layer never lifted out.
      * warm attempt 2 (46 turns) ended `"...move to the next task - fixing
        the deprecated Field usage:"`, mid-sentence, with no tool call at
        all.

    Vibe reads "assistant message, no tool calls" as "the model is done" and
    ends the attempt, so warm looked like it plateaued at 304 surfaces on
    attempts 2 AND 3 with byte-identical results. It had not plateaued; it
    had been cut off. The 4-request control test cannot see this -- it runs
    at 551 tokens and these failures start around 20k of context.

    Returns a short reason to log, or None if the turn ended legitimately.
    """
    entry = _last_assistant_entry(output)
    if entry is None:
        return None
    # A parsed call means the turn ended for some other reason entirely.
    if entry.get("tool_calls"):
        return None
    text = _entry_text(entry)
    leak = _TOOL_CALL_LEAK.search(text or "")
    if leak:
        return f"tool call leaked into message text ({leak.group(1) or '?'})"
    if text and _UNFINISHED_LEAD_IN.search(text):
        return "turn ended on a lead-in to an action that never arrived"
    return None


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
class AttemptBudget:
    """How many attempts the whole EXPERIMENT has left. Shared and mutable.

    An experiment is N attempts on one checkout: attempt, distil a skill,
    continue from where the agent left off, distil again, stop. Attempts
    were bounded by the clock instead (`--deadline-s`), which is why runs
    came out anywhere between 2 and 4 of them.

    MUTABLE, AND DECREMENTED WHERE THE ATTEMPT STARTS, for one reason:
    `swarm/run.py:_attempt_until_done` re-enters `migrate_codebase` after any
    non-harness exception, and the local `attempt` counter restarts at 0
    there. That is the same reset that made run 6 of the 2026-09-19 series
    report one attempt where three had run. An integer argument would hand
    the retry a fresh allowance; a shared object cannot.

    Decremented on START, not on completion, so a crash loop consumes the
    budget instead of spinning inside it.
    """
    remaining: int

    def take(self) -> bool:
        """Claim one attempt. False when the experiment is out."""
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


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
    cognee_mcp_url: str = "http://127.0.0.1:8811/mcp",
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

    `memory_enabled` registers the cognee MCP server -- HALF of warm's
    treatment, the half the agent may or may not choose to use. False
    (every cold agent) means no block is written at all, so that agent has
    no path to the graph: not a gated one, none. The other half, the
    procedure and the retrieved context in the attempt prompt, is not
    configured here at all; it reaches the agent as prompt text from
    migrate_codebase.

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

    # NO hooks.toml, FOR EITHER ARM, and any that survives on a reused
    # machine is deleted here rather than tolerated.
    #
    # This wrote a `post_tool` hook so every tool call became a
    # ReasoningStep in the old memory layer, and a `post_agent` hook to
    # catch the turns that called no tool. Both are retired: the agent
    # writes what it chooses through its MCP server, and what the harness
    # writes it writes from its own process after the verdict. A leftover
    # hook would cost warm ~1.3-1.5s per tool call that cold does not pay
    # -- wall-clock the shared deadline charges to warm alone, which is a
    # confound in every number the run produces.
    hooks_file = vibe_home / "hooks.toml"
    if hooks_file.exists():
        hooks_file.unlink()

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
        # Cognee's MCP server, over loopback HTTP, registered the way its
        # own docs say to run it: `cognee-mcp --transport http --host
        # 127.0.0.1 --port 8811`. Warm agents only; a cold agent never
        # gets this block and so has no path to memory at all.
        #
        # STREAMABLE-HTTP, NOT "http". This is the one thing that must not
        # be simplified. Vibe's `--transport http` selects MCPHttp, its
        # LEGACY SSE client, which issues a bare GET; a streamable-HTTP
        # server answers that with 406 Not Acceptable and the agent
        # registers ZERO memory tools while everything else looks healthy.
        # That cost a whole run once. Cognee serves streamable-HTTP at
        # /mcp, exactly as the old server did, so the same rule applies.
        #
        # Written into config.toml rather than via `vibe mcp add`, because
        # `mcp add` IS the OAuth path and hardcodes auth={"type":"oauth"}
        # for a loopback server that knows nothing about OAuth. See
        # swarm/agent_workspace._MCP_SERVER_TEMPLATE for the full autopsy.
        #
        # No shim, no credentials: the URL is all the agent gets, and the
        # Neo4j password lives only in the server's own environment. The
        # old stdio registration had to hide four arguments -- including
        # `--password=` -- behind a shim because Vibe echoes a stdio
        # server's launch command into every tool result.
        with config_generated.open("a") as f:
            f.write(f'\n[[mcp_servers]]\nname = "cognee"\n'
                    f'transport = "streamable-http"\nurl = "{cognee_mcp_url}"\n')

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


# WHAT WARM IS TOLD IT HAS. Short, and deliberately not coaching.
#
# The previous layer relayed neo4j-agent-memory's OWN 1,935-character
# instructions verbatim, because Vibe DROPS a server's `instructions`
# field -- all three of its `session.initialize()` call sites discard the
# return value -- and that turned out to be why 40 consecutive runs ended
# with zero agent-initiated memory calls. The tools were registered, the
# server was live, the model was willing; it was never told what the
# tools were for.
#
# Cognee's MCP server sends NO instructions at all -- measured:
# `initialize()` returns `instructions=None` -- so there is nothing to
# relay and the tool descriptions are the whole of what the model gets.
# Whether that is enough is now an open question this harness can answer,
# and it is a fair one to ask: `remember`/`recall` are self-describing in
# a way `memory_start_trace`/`memory_record_step` were not.
#
# The text lives in cognee_layer so the constant has one home.
_MEMORY_TOOLS_GUIDE = MEMORY_TOOLS_GUIDE


def _task_prompt(
    last_error: str | None,
    memory_enabled: bool = False,
    skill_command: str | None = None,
    *,
    procedure: str | None = None,
    memory: str | None = None,
    verdict: str | None = None,
    no_edits_last_turn: bool = False,
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
        # BOTH ARMS, by decision. Warm has a code graph and cold does not,
        # so this is the step warm can act on more cheaply -- but it is
        # not an instruction that needs memory to follow, and a warm-only
        # sentence would be a second undeclared asymmetry on top of the
        # memory steps above. Any warm win after that would not be
        # attributable to memory, which is the only thing this measures.
        #
        # Earned by run 5: warm held the same 46 v1 surfaces for eight
        # attempts, 18 of them in a file its own code-graph block never
        # named, while re-reading the two files it already knew.
        "If you become stuck, look in places you have not looked before.",
        # BOTH ARMS. Measured on run 9: warm's first attempt ended "Given
        # the complexity and time, I'll stop here and summarize the
        # migration work completed so far", and its turn count then fell
        # 62 -> 37 -> 23 across three attempts while its memory grew
        # 2,302 -> 3,183 -> 4,063 characters. Cold's third attempt used 3
        # turns. Both arms were electing to stop, and a work list of 255
        # surfaces across 19 files reads as a reason to.
        #
        # The operator's words, verbatim.
        "There is no job too large for you.",
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
    # THE DETERMINISTIC HALF OF WARM'S TREATMENT, and the only two blocks
    # in this prompt the harness puts there on the agent's behalf.
    #
    # `procedure` is the skill as Cognee holds it, and it reaches the
    # model here because there is nowhere else for it to go: the AIP era
    # installed a SKILL.md and opened the prompt with `/<name>` so Vibe
    # loaded it deterministically, and Cognee keeps the procedure in the
    # graph instead. Leaving it to `cognee_recall` means warm runs
    # against its own distilled skill only on the attempts where it
    # chooses to go and fetch it -- which is not a memory experiment, it
    # is a tool-use experiment with the skill as the prize.
    #
    # `memory` is CogneeMemory.brief(): the code graph of this codebase, the
    # attempts the grader judged to have WORKED, and the attempts it judged to
    # have failed -- each under its own heading, because "here is some
    # retrieved prose" does not tell a model which paragraph to copy and which
    # to avoid. Capped per block, because the last uncapped version of this
    # reached 15,170 characters and warm spent three attempts reporting on it
    # instead of migrating anything.
    #
    # Both are reported per attempt (ATTEMPT_DONE.memory_chars) and both
    # are switchable off (`--memory-mode mcp`), because they are prompt
    # tokens warm reads and cold does not, and an unmeasured asymmetry in
    # this prompt has invalidated a run series before.
    if procedure:
        base += ("\n\nYour procedure for this task, as you last revised it:"
                 f"\n```\n{procedure.strip()}\n```")
    if memory:
        # DESCRIBES WHAT THE BLOCK ACTUALLY IS. It used to promise "the
        # WORKED section is verified progress; repeat it. The DID NOT WORK
        # section is verified waste" -- two node sets that were removed
        # when the harness's document layer came out. So warm was told to
        # look for two sections that did not exist, above three lines of
        # telemetry, for four attempts of run 7.
        base += ("\n\n## Your memory of this codebase\n\n"
                 "Two things, both measured rather than claimed: what the "
                 "code graph knows about this codebase, and what earlier "
                 "attempts on this same checkout did to it.\n\n"
                 f"{memory.strip()}")
    # The one thing the agent genuinely cannot see for itself: the verdict from
    # a suite that ran somewhere else, in Daytona, after its turn ended. Stated
    # and not editorialised -- the advice that used to follow it ("keep going
    # until the suite passes", which errors mean to look something up) was us
    # steering, and the agent can read a traceback.
    # THE THREE NUMBERS, ahead of the output they were measured from.
    #
    # The tally was already present, in the tail of the trimmed pytest
    # output. Warm read past it: on attempt 3 it wrote itself a
    # MIGRATION_SUMMARY.md opening "Successfully migrated the x12sdk
    # codebase from Pydantic v1 to Pydantic v2" with a row of ticks, while
    # 47 v1 surfaces remained and 202 of 261 tests failed. It then spent
    # attempts 3 and 4 re-reading that file and ending "Task completed."
    # without a single edit. A self-authored report outranked a tally
    # buried in 8,000 characters of tracebacks.
    #
    # Stated, not editorialised, and identical for both arms: these are
    # the grader's own counts from a suite that ran in Daytona after the
    # turn ended, which is the one thing the agent cannot measure for
    # itself. No instruction rides along with them.
    if verdict:
        base += f"\n\nThe independent grader measured your last attempt:\n{verdict}"
    if last_error:
        base += (
            f"\n\nThe test suite still fails:\n```\n{last_error}\n```"
        )
    # THE INSTRUCTION GOES LAST, after the evidence it is about.
    #
    # Measured on run 10, warm attempt 3. The prompt was 14,318 characters
    # and ended with 3,400 characters of pytest traceback -- the last thing
    # the model read was "3 errors in 0.69s". The sixteen numbered steps,
    # including "Make your edits", sat at character 0, thirteen thousand
    # characters earlier. Nine of those sixteen steps are review, plan or
    # research; one is editing.
    #
    # The transcript is the model following that faithfully: twenty-eight
    # turns of grep, then "Now let me create a comprehensive plan", then
    # "Task completed." with ZERO edits -- and a text-only assistant turn
    # is exactly Vibe's stop condition, so the attempt ended there. It
    # never compiled anything, while fourteen of its own files did not
    # parse. Turn counts across the run: 100, 25, 29.
    #
    # Nothing new is said here and no content is duplicated: the closing
    # line restates step 7 and step 16 of the list the operator wrote,
    # in the position where the model will actually act on them. Identical
    # for both arms.
    if last_error or verdict:
        base += ("\n\nNow make the edits. Work on the codebase itself rather "
                 "than on a plan or a report, and keep going until the suite "
                 "passes.")
    # SAID ONLY TO AN AGENT THAT JUST DECLINED, and it is a measurement:
    # zero `edit` and zero `write_file` calls in the turn that preceded
    # this one. Re-prompting with a byte-identical prompt would invite the
    # same plan-only turn -- and on runs 10 and 11 that turn was 19 to 28
    # turns of audit, so the invitation is expensive.
    if no_edits_last_turn:
        base += ("\n\nYour previous turn made no edits to any file. Do not "
                 "review or plan further. Change the code now.")
    # LAST, so it is the very first thing in the message. Vibe only treats a
    # prompt as a skill invocation when it STARTS with `/<name>`
    # (SkillManager.parse_skill_command: `stripped.startswith("/")`, then
    # `split(None, 1)` -- so the rest of the prompt arrives intact as
    # `extra_instructions`). When it matches, Vibe appends a real `skill`
    # tool call and its result to the conversation before the model's first
    # turn (_inject_invoked_skill), which is how the skill gets into context
    # deterministically instead of depending on the model choosing to call
    # the `skill` tool. This harness has already learned what that dependency
    # costs: agents made 0 memory-tool calls across 15 sessions while being
    # told to use them.
    #
    # It also means the prefix is not a patch. The loading is Vibe's, through
    # a documented surface; the harness only decides which skill and when.
    #
    # Cost: warm's prompt no longer shares a prefix with cold's, so
    # RadixAttention cannot reuse the cache across the arms. Warm's own
    # prefix is stable across its attempts, which is where the reuse matters.
    if skill_command:
        base = f"/{skill_command} " + base
    return base


def _stream_entries(stdout: str) -> list[dict]:
    """Vibe's streamed history entries, one JSON object per line.

    The same parse as AgentWorkspace.stream_entries; both exist because
    `swarm/` does not import from `orchestrator/`. A non-JSON line is
    skipped rather than fatal: Vibe writes progress text to the same
    stream, and an unparseable line must never cost an attempt its steps.
    """
    entries: list[dict] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def attempt_prompt(last_error: str | None, skill_name: str | None,
                   *, procedure: str | None = None,
                   memory: str | None = None,
                   verdict: str | None = None,
                   no_edits_last_turn: bool = False,
                   mcp_tools: bool = False) -> str:
    """The prompt for one attempt. IDENTICAL BETWEEN THE ARMS except for
    warm's memory: the tools it is told it has, the procedure it wrote,
    and what Cognee retrieved for this attempt.

    This is a function, rather than a call to `_task_prompt` at the one site
    that builds it, so the property can be tested directly instead of being
    asserted about the source.

    `mcp_tools` adds the three numbered memory steps and the tools guide.
    It is the agent being told what it has, and it only makes sense for an
    agent that has it -- telling an agent with no memory server to consult
    its memory is an instruction it cannot follow. That makes warm's
    prompt longer than cold's, which is a real asymmetry and is why the
    whole block is off under `--memory-mode deterministic`.

    `procedure` and `memory` are the deterministic half: the skill Cognee
    holds and what Cognee retrieved for this attempt. Both empty for
    cold, so cold's prompt is byte-identical to what it has always been.

    The feedback from the previous attempt -- the grader's own pytest
    output, trimmed by `_trim_error_for_prompt` -- is passed through
    unchanged for both arms, in the same place and the same format. Neither
    arm resumes a session, so this and warm's two blocks are the only
    things either of them carries from its last attempt.
    """
    # NO SKILL PREFIX. Warm's prompt used to open with
    # `/pydantic-v2-migration`, Vibe's command for loading a skill FILE
    # from $VIBE_HOME/skills. Cognee keeps the procedure in the graph, so
    # there is no file to name -- the text itself is passed in instead.
    # `skill_name` survives as the name of the skill whose procedure that
    # is, for the caller's own bookkeeping.
    _ = skill_name
    return _task_prompt(last_error, memory_enabled=mcp_tools,
                        procedure=procedure, memory=memory,
                        verdict=verdict,
                        no_edits_last_turn=no_edits_last_turn)


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


# _entry_consumer DELETED, and this is the note that goes with it.
#
# It consumed Vibe's streamed history entries as they arrived and fed two
# things the old memory layer needed: assistant messages into
# `short_term.add_message` (the only source of :Message nodes, and so the
# only input to entity extraction) and `type="reasoning"` entries into the
# step hook as the pending thought for the turn. Both are retired with
# that layer, and it had already decayed into a no-op that still cost an
# `on_entry` callback per entry.
#
# ONE FACT FROM IT IS WORTH KEEPING, because it cost two live runs: every
# streamed entry reports its turn as `turnId`, NOT `turn_id`. The writer
# dumps with `model_dump(mode="json", by_alias=True)` (cli/programmatic.py),
# so every multi-word field arrives camelCase, while the model declares it
# `turn_id`. Written the declared way, the whole mechanism silently did
# nothing and its unit tests -- which passed synthetic dicts -- passed.
# Read off the wire, not off the model definition.


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


# Read-side memory tools, by their BARE server names. Matched as a suffix,
# because Vibe publishes an MCP tool as f"{server_alias}_{tool}" -- the
# config registers cognee's server as "cognee", so what lands in the
# transcript is `cognee_recall`.
#
# This cost a finding once, under the previous server. The first time an
# agent ever called memory for itself the counter read 0 and MEMORY_READ
# did not fire, because the filter tested `startswith("memory")` against a
# name beginning "neo4j-". The one event that exists to say "the agent
# retrieved something" reported nothing on the only occasion it had ever
# been true. Hence suffix matching, and hence the old names below: a
# transcript from before 2026-09-20 is still read by scripts/inspect_run.py
# and must still count.
_MEMORY_READ_TOOLS = (
    # cognee-mcp 0.5.5, `cognee-mcp --transport http`
    "recall",
    "search",
    "get_document",
    "get_chunk_neighbors",
    "list_data",
    # neo4j-agent-memory, retired 2026-09-20. Kept so old runs still parse.
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
    # `web_lookup` must never match. Both arms have it, so counting it as a
    # memory read would report cold retrieving from a graph it cannot reach.
    if not (tool_name.startswith("cognee") or "memory" in tool_name
            or tool_name.endswith("graph_query")):
        return False
    return any(tool_name.endswith(t) for t in _MEMORY_READ_TOOLS)


def _is_memory_tool(tool_name: str) -> bool:
    """Any memory tool, read or write -- the `memory_calls` counter.

    Prefix/substring match for the same aliasing reason as _is_memory_read.
    `graph_query` is included: read-only Cypher against the same graph is the
    package's own escape hatch and counts as the agent using its memory."""
    return (tool_name.startswith("cognee") or "memory_" in tool_name
            or tool_name.endswith("graph_query"))


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


def _attempt_account(*, attempt: int, package_path: str | None,
                     tree: dict[str, bytes],
                     prev_tree: dict[str, bytes] | None,
                     prev_v1: int | None, prev_parse_ok: int | None,
                     started_from: str | None,
                     limit: int = 950) -> str:
    """What this attempt DID, measured off its tree. Cognee's only content.

    THIS STRING IS WARM'S MEMORY. `agent_memory` stores the decorated
    body's return value as the trace's `method_return_value`, that trace
    is what `persist_session_trace_after=1` bridges into the fixture's
    node set, and that node set is the only thing `recall` can read. So
    whatever this returns IS what a later attempt is handed.

    It used to return `f"attempt {n}: vibe exited {code} after {turns}
    assistant turn(s)"`. Measured on run 7, warm's fourth attempt was
    handed exactly this as its memory of the migration:

        migrate_codebase.<locals>._attempt_turn succeeded. Output:
        attempt 2: vibe exited 0 after 131 assistant turn(s); (no stop
        event) last entry message: Task completed.

    Three of those, one per prior attempt, and not a word about pydantic.
    "succeeded" is the decorator's word for "returned without raising",
    so every failed attempt read as a success. Warm went 323 -> 259 ->
    259 -> 303 v1 surfaces on that diet while cold, with no memory at
    all, went 383 -> 48 -> 1.

    Everything here is measured, not claimed: which files changed, how
    the surface counts moved, whether the tree still parses. The verdict
    proper does not exist yet -- the suite runs in Daytona after this
    returns -- so the failure the attempt STARTED from is named instead,
    which is what makes the entry retrievable against a later failure.

    Bounded well under Cognee's MAX_SERIALIZED_VALUE_LENGTH of 1,000,
    because a truncated last line reads as content that stops mid-fact.
    """
    parse_ok, parse_total = surfaces.parses(tree, within=package_path)
    v1_now = surfaces.count(tree, within=package_path)
    # THE OUTCOME FIRST, because Cognee renders every recalled trace as
    # "<function> succeeded. Output: <this string>" and that wording is
    # not ours to change. With the detail first, warm's memory opened with
    # "succeeded" and reached the contradiction ~600 characters later, at
    # the bottom of each entry. Whatever follows "Output:" has to be the
    # fact that settles whether the job is done.
    #
    # Only measured claims: a tree that parses may still fail to import
    # (run 8's cold arm was 65/65 parsing and died on a NameError), so a
    # clean parse is reported as nothing more than a clean parse.
    if parse_ok < parse_total:
        headline = (f"NOT DONE: {parse_total - parse_ok} of {parse_total} "
                    f"source file(s) do not parse, so the package cannot "
                    f"be imported and no test can pass.")
    elif v1_now:
        headline = (f"NOT DONE: {v1_now} Pydantic v1 surface(s) are still "
                    f"in the source.")
    else:
        headline = ("No v1 surfaces remain in the source; whether the "
                    "package behaves correctly is for the suite to say.")
    lines = [headline,
             f"Attempt {attempt} on the {package_path or 'package'} "
             f"Pydantic v1 -> v2 migration."]
    if started_from:
        lines.append(f"Started from the suite failing with: "
                     f"{started_from.strip()[:160]}")

    if prev_tree is not None:
        changed = sorted(path for path, blob in tree.items()
                         if prev_tree.get(path) != blob)
        if changed:
            shown = ", ".join(changed[:4])
            more = (f", and {len(changed) - 4} more"
                    if len(changed) > 4 else "")
            lines.append(f"Changed {len(changed)} file(s): {shown}{more}")
        else:
            lines.append("Changed no files.")

    # BOTH, or neither. `prev_v1` is seeded from the pristine tree so that
    # attempt 1 can be judged for progress, but `prev_tree` is None there --
    # and comparing against an empty breakdown made every surface present
    # read as newly added. Run 8's attempt 1 told warm "REINTRODUCED: 253 x
    # Field(const/regex/items), 42 x conint/constr/etc" about surfaces it
    # had never touched.
    if prev_v1 is not None and prev_tree is not None:
        lines.append(f"v1 surfaces {prev_v1} -> {v1_now}.")
        before = surfaces.breakdown(prev_tree, within=package_path)
        after = surfaces.breakdown(tree, within=package_path)
        cleared = {k: before[k] - after.get(k, 0) for k in before
                   if before[k] > after.get(k, 0)}
        added = {k: after[k] - before.get(k, 0) for k in after
                 if after[k] > before.get(k, 0)}
        if cleared:
            lines.append("Cleared: " + ", ".join(
                f"{n} x {k}" for k, n in
                sorted(cleared.items(), key=lambda kv: -kv[1])[:4]))
        if added:
            lines.append("REINTRODUCED: " + ", ".join(
                f"{n} x {k}" for k, n in
                sorted(added.items(), key=lambda kv: -kv[1])[:4]))
    else:
        lines.append(f"v1 surfaces remaining: {v1_now}.")

    left = surfaces.as_work_list(tree, within=package_path,
                                 max_surfaces=3, max_files=2)
    if left:
        lines.append("Still left: " + "; ".join(left))

    parse_note = f"{parse_ok} of {parse_total} source files parse"
    if prev_parse_ok is not None and prev_parse_ok != parse_ok:
        parse_note += f" (was {prev_parse_ok})"
    if parse_ok < parse_total:
        parse_note += " -- the package cannot be imported"
    lines.append(parse_note + ".")

    return _cap_text("\n".join(lines), limit)


def _cap_text(text: str, limit: int) -> str:
    """Whole lines only, so the last fact is never half a fact."""
    if len(text) <= limit:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        if sum(len(item) + 1 for item in kept) + len(line) > limit:
            break
        kept.append(line)
    return "\n".join(kept)


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
        # NO DOT-DIRECTORIES. `.pytest_cache` was upload weight; `.enola`
        # was worse -- the code-graph pipeline writes its snapshot to
        # `<repo>/.enola/` by default, and one ingest put 2.3 MB of
        # `facts.jsonl` and an extractor cache inside the tree the grader
        # scores, where `surfaces` counted it and `closeness` diffed it.
        # The snapshot now goes to a scratch directory; this is the second
        # line of defence, because nothing else notices.
        if any(part.startswith(".") for part in rel.parts[1:]):
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


@functools.lru_cache(maxsize=4)
def _reference_trees(package_path: str) -> tuple[tuple, tuple]:
    """Cached, because it is read once per graded attempt and the files
    do not change during a run. Tuples so lru_cache can hold them."""
    from orchestrator.manifest import FIXTURE_DIR
    base, answer = surfaces.reference_trees(FIXTURE_DIR, package_path)
    return tuple(base.items()), tuple(answer.items())


def _closeness(file_contents: dict[str, bytes],
               package_path: str | None) -> float | None:
    """`None` when the fixture ships no answer key -- which is a different
    fact from 0.0, and 0.0 is the score of an untouched checkout."""
    if not package_path:
        return None
    try:
        base, answer = _reference_trees(package_path)
        if not answer:
            return None
        return surfaces.closeness(file_contents, dict(base), dict(answer),
                                  within=package_path)
    except Exception as exc:                  # never cost a graded attempt
        # `print`, because this module has no logger -- which the
        # symtable test caught here before it reached a pod.
        print(f"  closeness could not be computed: {exc!r}")
        return None


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


# Errors that mean the agent's own edit left the tree unparseable. The
# pre-migration fixture parses cleanly, so any of these in a graded result
# is damage this attempt did.
_SYNTAX_ERRORS = ("SyntaxError", "IndentationError", "TabError")


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


def hook_activity(workspace) -> dict[str, Any]:
    """What the `post_tool` hook did during this attempt, from its journal.

    Optional on the Workspace: the local orchestrator and every cold agent
    have no hook, and a missing journal is normal rather than an error. The
    counts go on ATTEMPT_DONE and MEMORY_WRITE, because "the hook is
    registered" and "the hook did something" are different claims and a run
    where the second is false looks healthy in every other number.
    """
    reader = getattr(workspace, "read_hook_journal", None)
    if reader is None:
        return {}
    try:
        entries = reader()
    except Exception:
        return {}
    failed = [e for e in entries if e.get("status") != "success"]
    return {
        "hook_commands": len(entries),
        "hook_failures": len(failed),
        "hook_chars": sum(int(e.get("recalled") or 0) for e in entries),
        "hook_last_error": str((failed[-1].get("error") or ""))[:200]
                           if failed else "",
    }


def _attempt_headline(*, helped: bool, success: bool, advanced: bool,
                      rejected: bool, passed: int, last_passed: int) -> str:
    """One sentence saying what the grader concluded, for the top of the
    outcome document. The document's first line is what ranks in retrieval and
    what a reader skims, so it states the verdict rather than the metrics."""
    if success:
        return "The full test suite passed after this attempt."
    if rejected:
        return ("The suite was gamed rather than migrated, so this attempt "
                "was rejected whatever pytest reported.")
    if advanced:
        return (f"More of the suite passes than before this attempt "
                f"({last_passed} -> {passed}), so the changes below are "
                f"verified progress.")
    if helped:
        return "The grader judged this attempt to have helped."
    return ("The suite is no better than before this attempt, so the changes "
            "below bought nothing.")


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


class Workspace(Protocol):
    """Where one agent's files and Vibe process live.

    The attempt loop below is the same loop whether the agent runs on this
    machine or on a remote swarm host, so the six operations that differ are
    named here and nothing else changes. This exists because the alternative
    was a SECOND copy of migrate_codebase for the remote case, which had
    already started drifting: its own cruder `tests_passed` and
    `error_signature`, no trace keyed on the error signature -- a different
    graph, built a different way, from a parallel implementation of a
    function that already worked.
    """

    async def run_vibe(self, task: str, *, timeout_s: float, resume: bool,
                       on_entry: Any | None) -> tuple[int, str]: ...

    def snapshot(self) -> dict[str, str]: ...
    def collect_file_contents(self) -> dict[str, bytes]: ...
    def assistant_turns_total(self) -> int: ...
    def tool_calls_total(self) -> Counter: ...
    def steps_used(self) -> int: ...
    # Vibe's streamed history entries, parsed from the stdout run_vibe
    # returned. The whole input to ingestion -- see orchestrator/ingest.py.
    def stream_entries(self, stdout: str) -> list[dict]: ...

    # Which AIP version is installed HERE, or None. The attempt loop records
    # this rather than asking the skill registry, because the registry
    # answers "what is newest on the orchestrator's disk" and the agent runs
    # whatever reached its own VIBE_HOME.
    installed_skill_version: int | None

    # There is deliberately NO checkpoint/restore here. See the attempt
    # loop, "NO ROLLBACK": attempts continue from where the last one left
    # the tree, and an agent that breaks its own code fixes its own code.


@dataclass
class LocalWorkspace:
    """The original arrangement: a checkout on this machine, Vibe as a local
    subprocess. Every method delegates to the function that already did it."""

    repo_dir: Path
    vibe_home: Path = VIBE_HOME
    vibe_cwd: Path = HARNESS_DIR
    # Local runs install skills by hand, if at all; whoever does it sets
    # this, and None honestly means "no skill recorded here".
    installed_skill_version: int | None = None

    async def run_vibe(self, task: str, *, timeout_s: float, resume: bool,
                       on_entry: Any | None) -> tuple[int, str]:
        return await _run_vibe(task, timeout_s=timeout_s, vibe_home=self.vibe_home,
                               cwd=self.vibe_cwd, resume=resume, on_entry=on_entry)

    def snapshot(self) -> dict[str, str]:
        return _snapshot(self.repo_dir)

    def collect_file_contents(self) -> dict[str, bytes]:
        return _collect_file_contents(self.repo_dir)

    def assistant_turns_total(self) -> int:
        return _assistant_turns_total(self.vibe_home)

    def tool_calls_total(self) -> Counter:
        return _tool_calls_total(self.vibe_home)

    def steps_used(self) -> int:
        return _steps_used(self.vibe_home)

    def stream_entries(self, stdout: str) -> list[dict]:
        return _stream_entries(stdout)


async def migrate_codebase(
    *,
    pool: SandboxPool,
    test_command: str,
    deadline: float,
    emit: Emit,
    workspace: Workspace | None = None,
    repo_dir: Path | None = None,
    vibe_home: Path = VIBE_HOME,
    vibe_cwd: Path = HARNESS_DIR,
    mem: Any | None = None,
    session_id: str | None = None,
    baseline_signature: str | None = None,
    baseline_passed: int = 0,
    # The pristine tree's v1 surface count, so attempt 1 is judged against
    # the untouched checkout rather than against nothing. 383 on x12sdk.
    # None only where the caller has no fixture to count (the rehearsal).
    baseline_v1: int | None = None,
    agent_label: str | None = None,
    skill_name: str | None = None,
    # The denominator the grader's score is a proportion of. Read from the
    # fixture's manifest (`test_total`); 56 passing means nothing without it.
    tests_total: int = 0,
    usage_probe: Any | None = None,
    sync: Any | None = None,
    # Which directory the migration is IN. Scopes the progress count: the
    # fixture also ships `tests/`, `end_to_end_tests/` and
    # `integration-tests/`, which together contribute 29 constructs the
    # agent never touches -- a constant that swamps the signal and never
    # moves. Unset, the whole tree is counted.
    package_path: str | None = None,
    # How many attempts this EXPERIMENT still has. See AttemptBudget: it is
    # shared and mutable precisely so a retry cannot hand out a fresh three.
    # None means unbounded, which is what the local orchestrator and the
    # rehearsal still want.
    budget: "AttemptBudget | None" = None,
    # Called with (attempt, file_contents) just before each attempt is
    # graded, so the experiment can keep every tree and not only the last.
    on_attempt_tree: Any | None = None,
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

    WHEN `mem` IS SET (warm only), four things happen per attempt that do
    not happen for cold, and all four are Cognee's own surfaces:

        mem.procedure()     the skill as Cognee holds it, into the prompt
        mem.brief(error)    the code graph of this codebase, plus the
                            earlier attempts the grader judged to have
                            WORKED and those it judged to have failed,
                            each recalled from its own node set
        mem.wrap_attempt()  the attempt runs inside `cognee.agent_memory`,
                            which writes a session trace -- params, status,
                            return, error
        mem.record(...)     the graded outcome: one document into the
                            worked or failed node set, and a SkillRunEntry
                            that makes Cognee rewrite the procedure
        mem.improve()       bridges the session trace into the graph and
                            distils its lessons, after the verdict and off
                            the agent's clock

    None of them is the model's choice, which is the point: the MCP server
    is the half that is, and a run can have either or both
    (`--memory-mode`). What the agent chooses to `remember` on top is its
    own, and is counted rather than assumed -- see ATTEMPT_DONE's
    `memory_calls` against its `memory_chars`.

    THE VERDICT IS NEVER THE MODEL'S. An independent pytest run in a fresh
    Daytona sandbox decides success, and that number is what reaches Cognee
    as the skill run's score. Suite-level completion is
    MigrationResult.success, reported separately by run.py."""
    # Either a Workspace is supplied (remote swarm host) or one is built
    # from the local paths, which is exactly what this function did before.
    # Same loop, same graph, same events either way -- only where the files
    # live differs.
    if workspace is None:
        if repo_dir is None:
            raise ValueError('migrate_codebase needs workspace= or repo_dir=')
        workspace = LocalWorkspace(repo_dir=repo_dir, vibe_home=vibe_home,
                                   vibe_cwd=vibe_cwd)

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
    # NOT seeded, for the same reason `last_error` is not: on attempt 1 there
    # is no attempt of the agent's own to have measured.
    last_verdict: str | None = None
    # THE PREVIOUS ATTEMPT'S TREE, kept so the account warm reads can say
    # which files this attempt changed and which surfaces it cleared,
    # measured rather than taken from the model's word for it. None on
    # attempt 1, which reports its state without a comparison.
    last_tree: dict[str, bytes] | None = None
    last_parse_ok: int | None = None
    # Reset by any attempt that reaches the model; see MAX_CONSECUTIVE_ABORTS.
    consecutive_aborts = 0
    # Reset by any attempt that edits; see MAX_CONSECUTIVE_NOOPS.
    consecutive_noops = 0
    # Zero, not None. The starting state is known, not unknown: pristine v1
    # under pydantic v2 dies at collection and passes 0 tests (verified
    # directly against the fixture). Seeding this as None made `advanced`
    # unfalsifiable on attempt 1 -- and run 22's single best result in the
    # whole run, warm-2 reaching 32 of 33 passing on its first attempt, was
    # silently discarded because there was "no baseline to compare against".
    last_passed: int = baseline_passed
    # THE MEASURE `helped` KEYS ON, seeded at the baseline tree's own value.
    # None means "no answer key for this fixture", which is the one case
    # where the tests delta is still the best signal available.
    last_closeness: float | None = None
    # WHAT `advanced` KEYS ON. Seeded from the baseline tree, so attempt 1
    # is judged against the untouched checkout rather than against nothing.
    last_v1: int | None = baseline_v1
    last_ended_cleanly: bool = False
    # Seconds spent AFTER an attempt on work that is not the agent's:
    # ingestion, and later distillation. Added back to the deadline so the
    # two arms get the same amount of ATTEMPT time even though warm does
    # more work per round. Cold never accumulates any -- it has no `mem` --
    # so `off_clock` is the whole of the asymmetry, and it is visible.
    #
    # Without this the mission's "off the clock" would be a figure of
    # speech: a shared wall-clock deadline charges warm's bookkeeping to
    # warm's own thinking time.
    off_clock: float = 0.0
    # Seeded with the baseline so the starting failure is not counted as one
    # this agent cleared; errors_cleared subtracts one for it.
    seen_signatures: set[str] = {baseline_signature} if baseline_signature else set()
    best_passed: int = baseline_passed
    attempt = 0
    while True:
        remaining = (deadline + off_clock) - time.monotonic()
        # An attempt is only worth starting if it can still afford its own
        # verdict. Starting one with less than that left is what produced 19
        # consecutive runs of ungraded work: Vibe ran, the clock expired, and
        # the Daytona check got 0.0 seconds and raised.
        if remaining <= VERDICT_RESERVE_S:
            break
        # THE EXPERIMENT'S OWN BOUND, checked before the clock's. The
        # deadline is a safety net; this is the thing that decides how many
        # attempts an experiment gets. Claimed here, at the start, so the
        # retry wrapper cannot re-enter and hand out more -- see
        # AttemptBudget.
        if budget is not None and not budget.take():
            break
        attempt += 1
        # The version the agent is about to work from, read once per
        # attempt. Distillation changes it between attempts, so recording
        # it at the end would attribute the result to the wrong skill.
        #
        # Read off the WORKSPACE, not the local registry. This used to call
        # skills.current(), which answers a different question -- "what is
        # the newest version on the orchestrator's disk" -- and the two
        # diverge in both directions. Pin a version with --skill-version and
        # every attempt was logged as the newest one instead of the one
        # installed; distil between attempts and an attempt was credited to
        # a procedure that had not reached the pod. Either way the label was
        # not the skill the model read.
        # No version to report: Cognee rewrites the procedure in place
        # and keeps no lineage. Emitted as None rather than as a number
        # the harness invented, because "which skill produced this
        # result" now has one honest answer -- whatever Cognee held at
        # the time -- and a fabricated counter would read as more.
        skill_version = None
        await emit("ATTEMPT_START", attempt=attempt,
                   skill_version=skill_version)
        attempt_started = time.monotonic()
        off_clock_at_start = off_clock
        # THE CHECKOUT PERSISTS; THE AGENT'S OWN NOTES DO NOT. See
        # AgentWorkspace.clear_stray_home_files: a self-written
        # MIGRATION_SUMMARY.md declaring the migration complete cost run 5
        # three attempts. Both arms, so it cannot skew the comparison.
        # Absent on the local orchestrator's workspace, which gives each
        # attempt a fresh directory anyway.
        strays = getattr(workspace, "clear_stray_home_files", None)
        if strays is not None and attempt > 1:
            removed = strays()
            if removed:
                print(f"  [{agent_label}] cleared from home: "
                      f"{', '.join(removed)}")
        # What this attempt is actually up against. Attempt 1 has nothing to
        # go on yet; from attempt 2 it is the previous attempt's real failure,
        # as read by the orchestrator off its own independent pytest run.
        trace_task = last_signature or task_desc

        # THE PROCEDURE THE AGENT IS ABOUT TO WORK FROM, read once per
        # attempt because distillation rewrites it between attempts --
        # reading it at the end would attribute the result to the wrong
        # text. Off the agent's clock: it is a read the harness makes.
        #
        # NO TRACE IS OPENED HERE. The harness used to open one per
        # attempt and close it with the verdict, and pass its id to a
        # sidecar so a hook could hang steps off it. Cognee's decorator
        # records the attempt itself (see `_attempt_turn`), and what the
        # agent chooses to remember on top of that is its own `remember`
        # call -- so there is no trace id to mint, thread or close.
        procedure = ""
        if mem is not None:
            assert session_id is not None
            procedure_started = time.monotonic()
            try:
                procedure = await mem.procedure()
            except Exception as exc:
                # Not fatal, and loud. An attempt with no procedure is a
                # warm agent running as a cold one, which is a finding
                # about this run rather than a reason to end it -- but it
                # must never be silent, because warm-without-its-skill
                # looks exactly like warm-with-a-useless-skill in the
                # numbers.
                print(f"  [{agent_label}] could not read the procedure from "
                      f"Cognee ({exc!r}); this attempt runs without it")
            off_clock += time.monotonic() - procedure_started

        # Token counters at the attempt boundary, so ATTEMPT tokens can be
        # reported apart from distillation tokens. The sampling itself is
        # charged to off_clock: it is the harness measuring, not the agent
        # working, and it happens for both arms either way.
        probe_started = time.monotonic()
        usage_before = usage_probe() if usage_probe else {}
        off_clock += time.monotonic() - probe_started

        turns_before = workspace.assistant_turns_total()
        tools_before = workspace.tool_calls_total()

        # ONE ATTEMPT, AS A FUNCTION, so Cognee's own decorator can wrap it.
        #
        # `cognee.agent_memory` is the documented integration point
        # (guides/agent-session-traces): it retrieves before the call and
        # persists a session trace of the call afterwards -- parameters,
        # status, return value, error. Wrapping this body is what makes
        # warm's memory deterministic rather than a tool the model may or
        # may not reach for.
        #
        # `last_error` is the first parameter for a reason: it is what
        # `memory_query_from_method` names, so Cognee retrieves against
        # the failure this attempt is working on. Attempt 1 passes None,
        # Cognee derives no query and skips retrieval -- correct, and not
        # an error.
        #
        # `_marks` is how the harness keeps its off_clock accounting
        # honest across the decorator. Cognee's retrieval happens before
        # this body runs and its trace write after, both inside the same
        # await, so without the two stamps warm's bookkeeping would be
        # charged to warm's thinking time -- which is exactly the
        # asymmetry `off_clock` exists to prevent.
        _marks: dict[str, Any] = {}

        async def _attempt_turn(last_error: str | None = None,
                                *, attempt: int = 0) -> str:
            _marks["fn_started"] = time.monotonic()
            # THE BRIEF, ranked against what this attempt is actually up
            # against: the previous attempt's first failure, or the task
            # itself on attempt 1. Empty for cold (no `mem`), empty under
            # `--memory-mode mcp`, and empty on attempt 1 of the first run
            # on a fixture -- nothing has been graded yet.
            retrieved = (await mem.brief(last_signature or task_desc)
                         if mem is not None else "")
            task = attempt_prompt(
                last_error, skill_name,
                procedure=procedure if mem is not None else None,
                memory=retrieved or None,
                verdict=last_verdict,
                no_edits_last_turn=consecutive_noops > 0,
                mcp_tools=bool(mem is not None and uses_mcp(mem.mode)),
            )
            _marks["task"] = task
            _marks["memory_chars"] = len(retrieved)
            code, output = await _drive_vibe(task, attempt=attempt)
            _marks["fn_ended"] = time.monotonic()
            _marks["result"] = (code, output)
            # THE TREE, COLLECTED ONCE. After `fn_ended`, so the transfer
            # is charged to off_clock rather than to the agent's thinking
            # time, and stashed for the grader below so the attempt pays
            # for exactly one collection either way.
            tree = workspace.collect_file_contents()
            _marks["tree"] = tree
            # WHAT THIS ATTEMPT DID, and it is the whole of warm's
            # memory: the decorator stores this return value as the
            # trace's `method_return_value`, the trace bridges into the
            # fixture's node set, and that node set is all `recall` can
            # read. This used to return the exit code and a turn count,
            # which is what warm was reading back instead of the
            # migration. See `_attempt_account`.
            return _attempt_account(
                attempt=attempt, package_path=package_path, tree=tree,
                prev_tree=last_tree, prev_v1=last_v1,
                prev_parse_ok=last_parse_ok, started_from=last_signature)

        async def _drive_vibe(task: str, *, attempt: int) -> tuple[int, str]:
            # EVERY ATTEMPT STARTS A FRESH SESSION, IN BOTH ARMS.
            #
            # This used to be `attempt > 1 and last_ended_cleanly`: resume a
            # session that ended cleanly, so the agent kept its context
            # across attempts. Two things made that untenable.
            #
            # 1. A resumed session cannot reload a changed skill. Vibe
            #    checks whether the skill's marker is already in the
            #    conversation (_skill_already_loaded) and, if it is, answers
            #    "already loaded earlier in this conversation. Reuse those
            #    instructions." Correct for an unchanged skill; wrong once
            #    distillation has written a new version, because the agent
            #    would work from the superseded text while the run recorded
            #    the new number.
            #
            # 2. Fixing that for warm alone would make warm restart while
            #    cold carried its history forward, so the arms would differ
            #    in TWO ways instead of one, and any difference in their
            #    results could be attributed to either. The skill is meant
            #    to be the only thing warm carries between attempts.
            #
            # The cost is real and is the point: neither arm accumulates
            # conversation across attempts, so both start each attempt from
            # the task plus the previous verdict, and warm additionally from
            # a procedure it wrote itself. That is what the experiment is
            # trying to measure -- whether the distilled skill carries more
            # than a transcript would.
            #
            # `last_ended_cleanly` is still computed and now reported on
            # ATTEMPT_DONE rather than steering anything: whether the agent
            # stopped on its own terms is worth knowing, and it was only
            # ever visible through the resume decision.
            resume = False
            # Unleashed: the agent ends its own attempt. The only bound is
            # what is left of the RUN's clock after reserving the verdict --
            # see _run_vibe() on why that is the run's budget rather than a
            # cap on the agent.
            vibe_exit_code, vibe_output = await workspace.run_vibe(
                task,
                timeout_s=max(1.0, (deadline + off_clock) - time.monotonic()
                                   - VERDICT_RESERVE_S),
                resume=resume,
                on_entry=None,
            )
            # RECOVER A TRUNCATED TURN, WITHIN THIS ATTEMPT.
            #
            # See truncated_turn(): three of six attempts in
            # swarm-1789903474 ended because a tool call arrived as text.
            # `--continue` here resumes THIS attempt's own session, which is
            # a different thing from the cross-attempt resume banned above
            # and reopens neither of its two problems: the skill cannot have
            # changed inside one attempt, and both arms get this identically
            # so the arms still differ only in the treatment.
            #
            # Bounded, and every continuation is emitted. If this fires
            # constantly the serving layer is broken and that should be
            # loud, not absorbed.
            for _cont in range(MAX_CONTINUATIONS):
                why = truncated_turn(vibe_output)
                if why is None:
                    break
                left = (deadline + off_clock) - time.monotonic() - VERDICT_RESERVE_S
                if left <= 1.0:
                    break
                await emit("ATTEMPT_CONTINUED", attempt=attempt,
                           continuation=_cont + 1, reason=why)
                more_code, more_output = await workspace.run_vibe(
                    task, timeout_s=max(1.0, left), resume=True,
                    on_entry=None,
                )
                vibe_exit_code = more_code
                vibe_output = f"{vibe_output}\n{more_output}"
            return vibe_exit_code, vibe_output

        # WRAPPED PER ATTEMPT, warm only. The decorator's configuration is
        # fixed at decoration time and the session is per run, so this
        # cannot be a module-level `@cognee.agent_memory(...)`.
        turn = (mem.wrap_attempt(_attempt_turn) if mem is not None
                else _attempt_turn)
        try:
            call_started = time.monotonic()
            try:
                await turn(last_error, attempt=attempt)
                vibe_exit_code, vibe_output = _marks["result"]
            except Exception as exc:
                # A MEMORY FAILURE MUST NOT COST AN ATTEMPT, and the
                # decorator can raise in one place the wrapped function
                # cannot recover from: resolving the agent user, the
                # dataset scope and the connection all happen BEFORE the
                # body runs and are outside its own error handling.
                # (Retrieval and trace persistence both swallow their own
                # failures -- verified in cognee.modules.agent_memory.)
                #
                # So: if the body never ran, run it undecorated. If it did
                # run, its result stands -- losing it because bookkeeping
                # failed afterwards would throw away the agent's work.
                if "result" in _marks:
                    print(f"  [{agent_label}] cognee bookkeeping failed AFTER "
                          f"the attempt ran; keeping the attempt: {exc!r}")
                    vibe_exit_code, vibe_output = _marks["result"]
                else:
                    # WITH THE TRACEBACK. `ValueError('embedded null byte')`
                    # reached this branch once and the repr alone said
                    # nothing about which call raised it.
                    print(f"  [{agent_label}] cognee could not open this "
                          f"attempt's memory ({exc!r}); running it without "
                          f"retrieval or a trace")
                    traceback.print_exc()
                    await _attempt_turn(last_error, attempt=attempt)
                    vibe_exit_code, vibe_output = _marks["result"]
            # WHAT COGNEE SPENT, charged to the harness rather than to the
            # agent. The two stamps bracket the body, so everything outside
            # them inside this await is the decorator: retrieval before,
            # the session-trace write after.
            fn_started = _marks.get("fn_started", call_started)
            fn_ended = _marks.get("fn_ended", time.monotonic())
            memory_seconds = ((fn_started - call_started)
                              + max(0.0, time.monotonic() - fn_ended))
            off_clock += memory_seconds
            resume = False
            memory_chars = int(_marks.get("memory_chars", 0))
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
            if workspace.assistant_turns_total() <= turns_before:
                consecutive_aborts += 1
                await emit(
                    "ATTEMPT_ABORTED",
                    attempt=attempt,
                    reason="vibe completed no assistant turn",
                    vibe_exit_code=vibe_exit_code,
                    vibe_stop=stop_reason(vibe_output),
                    consecutive=consecutive_aborts,
                )
                attempt -= 1  # it did not happen; do not inflate the count
                # AN ABORT LOOP HAS TO END, AND IT HAS TO TRY TO HEAL.
                #
                # An abort is not an exception, so MAX_CONSECUTIVE_AGENT_
                # FAILURES never saw these and the loop had no exit at
                # all. Run 8's cold arm aborted 126 times in a row on
                # `mux_client_request_session: send fds failed` and run
                # 10's did it again -- 25 minutes of an arm that produced
                # nothing while the event log showed a cold agent that
                # simply would not work, which is indistinguishable from
                # the experiment's own result.
                #
                # Every ABORT_RECYCLE_EVERY tries, throw the ssh
                # multiplexing master away: that is the one thing measured
                # to clear this state, and `ControlMaster=auto` rebuilds
                # it on the next call. After MAX_CONSECUTIVE_ABORTS, stop
                # -- an arm that cannot start Vibe is a broken harness,
                # not a slow agent, and it must say so rather than spin.
                if consecutive_aborts % ABORT_RECYCLE_EVERY == 0:
                    recycle = getattr(workspace, "recycle_control_master",
                                      None)
                    if recycle is not None:
                        print(f"  [{agent_label}] {consecutive_aborts} "
                              f"consecutive aborts; recycling the ssh "
                              f"control master")
                        try:
                            recycle()
                        except Exception as exc:      # never cost the run
                            print(f"  [{agent_label}] recycle failed: {exc!r}")
                if consecutive_aborts >= MAX_CONSECUTIVE_ABORTS:
                    await emit("FILE_DONE", success=False, attempts=attempt,
                               reason=f"{consecutive_aborts} consecutive "
                                      f"aborts; vibe never started")
                    return MigrationResult(
                        False, attempt,
                        errors_cleared=max(0, len(seen_signatures) - 1),
                        best_passed=best_passed,
                        last_signature=last_signature,
                    )
                await asyncio.sleep(5.0)  # don't spin on a saturated endpoint
                continue
            consecutive_aborts = 0
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
            # ALREADY COLLECTED, inside the decorator, so the account warm
            # reads and the tree the grader scores are the same bytes.
            # Falls back for the paths that do not go through
            # `_attempt_turn` (an aborted attempt, the local orchestrator).
            file_contents = (_marks.pop("tree", None)
                             or workspace.collect_file_contents())
            # THE TREE THIS ATTEMPT PRODUCED, handed out before it is
            # graded. Free: the grader needs it anyway, so nothing extra is
            # collected or transferred. Only the FINAL tree was ever kept,
            # which is why per-attempt `closeness` could not be recomputed
            # after the 2026-09-19 or 2026-09-20 runs -- and it matters more
            # now that attempts accumulate on one checkout, so the series of
            # trees IS the experiment's record of progress.
            if on_attempt_tree is not None:
                try:
                    on_attempt_tree(attempt, file_contents)
                except Exception as exc:     # never cost an attempt
                    print(f"  [{agent_label}] could not archive attempt "
                          f"{attempt}'s tree: {exc!r}")
            # Gets its own reserved slice rather than `deadline - now`. That
            # expression is the bug that made this project measure nothing: by
            # the time Vibe had consumed the rest of the clock it evaluated to
            # 0.0, so the ONE thing that decides success never ran. The reserve
            # is granted even slightly past the deadline -- a verdict a few
            # seconds late is worth having; no verdict is worth nothing.
            #
            # A FLOOR, NOT A CEILING. A bare `timeout=VERDICT_RESERVE_S` caps
            # grading at 120s however much clock is left, and the handler below
            # reads that as "the shared clock expired" and breaks out of the
            # attempt loop for good. On run 7 warm-0 and cold-0 raced a cold
            # Daytona pool at t=46; cold-0 won (first create 46.5s, then 9.1s,
            # then ~1.5s once warm), warm-0 queued behind it, blew the 120s cap
            # and ended its run after ONE attempt with 1,060s unused. Taking
            # the max means the wait can only expire at or after the deadline,
            # which is the condition the handler already claims to detect.
            result = await asyncio.wait_for(
                pool.run_pytest(file_contents=file_contents, test_command=test_command),
                timeout=max(VERDICT_RESERVE_S,
                            (deadline + off_clock) - time.monotonic()),
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
            #
            # NOTHING TO CLOSE. Two `mem.complete_trace(...)` calls used to
            # live in these two handlers, and they outlived the object that
            # had the method -- so the one path that runs when a run is
            # already going wrong would have died with AttributeError.
            # Cognee's decorator has already recorded this attempt's trace,
            # with `status="error"` and the exception on it, before control
            # reaches here.
            break

        tools_used = workspace.tool_calls_total() - tools_before
        # AN ATTEMPT THAT CHANGED NOTHING IS NOT AN ATTEMPT.
        #
        # Measured on run 11, cold attempt 2, off the transcript: it opened
        # "Let me start by reviewing the codebase structure and
        # understanding the current state", ran seventeen reads and greps,
        # found that `_is_list_field` was missing, read the test that
        # imports it -- and then emitted "Task completed." with no edit at
        # all. It had diagnosed the bug and stopped. Warm's attempt 3 on
        # run 10 did the same in 28 turns.
        #
        # The numbered list is the task as the operator wrote it, and its
        # first step is "Review the entire codebase"; a model that
        # finishes the review reads that as finishing the job. Moving the
        # closing directive to the end of the prompt (verified present as
        # the last line) did not stop it.
        #
        # ON THE TREE, not on the tool counts. Counting `edit` and
        # `write_file` calls was the first version and it was wrong: cold
        # has migrated whole files through `bash` heredocs, so a
        # tool-count test would have re-prompted an agent that had just
        # done the work. Byte-comparing the tree is exact and cannot
        # care which tool did it.
        #
        # The harness declines to record it: grading a tree nobody touched
        # spends a Daytona sandbox and ~40s of the shared clock to
        # re-derive the identical verdict, and burns one of the attempts
        # the experiment counts. Capped, because an agent that will not
        # edit must not eat the deadline, and past the cap the attempt is
        # graded so the refusal itself reaches the record.
        unchanged = (last_tree is not None and file_contents == last_tree)
        if unchanged and consecutive_noops < MAX_CONSECUTIVE_NOOPS:
            consecutive_noops += 1
            await emit(
                "ATTEMPT_ABORTED",
                attempt=attempt,
                reason="attempt left the tree byte-identical",
                consecutive=consecutive_noops,
                turns_used=workspace.assistant_turns_total() - turns_before,
                tools=dict(tools_used),
            )
            attempt -= 1
            continue
        consecutive_noops = 0
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
        # THE OTHER HALF, reported the same way and kept separate.
        #
        # `sources=["cognee.agent_memory"]` rather than a tool name,
        # because this read is the HARNESS's: Cognee retrieved it before
        # the attempt and the loop put it in the prompt. Counting the two
        # together would answer "did warm have memory" while destroying
        # the answer to "did warm go and get it", which is the question
        # 40 runs of this project turned on.
        if memory_chars:
            await emit(
                "MEMORY_READ",
                attempt=attempt,
                hits=1,
                sources=["cognee.agent_memory"],
                chars=memory_chars,
                query=(last_error or trace_task)[:120],
            )
        probe_started = time.monotonic()
        usage_after = usage_probe() if usage_probe else {}
        off_clock += time.monotonic() - probe_started
        attempt_tokens = {
            k: usage_after.get(k, 0) - usage_before.get(k, 0)
            for k in ("prompt_tokens", "completion_tokens")
        }
        # Elapsed minus everything the harness did in the middle, so the
        # number is the agent's own time and is comparable between arms.
        attempt_seconds = ((time.monotonic() - attempt_started)
                           - (off_clock - off_clock_at_start))
        # Unpack the grader's verdict BEFORE the event that reports it.
        # These used to be derived after the emit, so ATTEMPT_DONE could not
        # carry `tests_passed` -- and metrics read 0 passed for a run where
        # both arms scored 33 of 33. `result` is already the Daytona result
        # here, so there is nothing to wait for.
        success = result.exit_code == 0
        signature = error_signature(result.output)
        passed = tests_passed(result.output)
        # HOISTED, so the distiller scores on the same number the event
        # log records. It was computed inline in the emit below and
        # therefore reached nothing else -- which is how the skill came
        # to be scored on `tests_passed`, a step function, while the
        # measure that tracks the actual migration sat unused one line
        # away. See cognee_layer.score_from_verdict.
        closeness = _closeness(file_contents, package_path)
        # HOISTED, because `advanced` keys on it now. It was computed inline
        # in the emit below and so reached nothing else -- the same shape of
        # mistake that left `closeness` unused by the scorer for a whole
        # series.
        v1_remaining = surfaces.count(file_contents, within=package_path)
        # HOISTED for the same reason, and for the verdict line below.
        parse_ok, parse_total = surfaces.parses(file_contents,
                                                within=package_path)
        # ONE READ of the hook's journal per attempt, before the events that
        # report it: `read_hook_journal` truncates the file, so a second
        # reader would find it empty and report a hook that never fired.
        hook_activity_seen = hook_activity(workspace)

        await emit(
            "ATTEMPT_DONE",
            attempt=attempt,
            # The grader's own number, not the agent's claim.
            tests_passed=passed,
            # HOW MUCH MIGRATION IS LEFT, counted off the source rather
            # than by running it. `tests_passed` is 0 both when nothing
            # has been migrated yet and when the agent has broken the
            # package -- 70% of 77 graded attempts scored exactly 0, so
            # the oracle cannot tell progress from damage. This can: it is
            # defined even when the tree does not parse, and it moves when
            # an attempt fixes 12 of 40 sites. Not an oracle; the suite
            # stays the only thing that decides success.
            v1_remaining=v1_remaining,
            # IS THE CODE INTACT? The other half of the pair, and the half
            # that was missing. `v1_remaining` says how much migration
            # exists; this says whether it still compiles. Together they
            # separate "did the work and broke it" (few surfaces, files
            # not parsing) from "kept it valid by not doing it" (many
            # surfaces, all parsing) -- which `tests_passed` scores 0 both
            # times. Measured mid-run on 2026-09-19: warm 16 surfaces at
            # 28/49 parsing, cold 63 at 49/49.
            parse_ok=parse_ok,
            parse_total=parse_total,
            # HOW FAR ALONG THE v1 -> v2 PATH, as a gradient. 0.0 is the
            # untouched checkout, 1.0 is the human's merged PR. Normalised
            # against the baseline because RAW similarity to the answer is
            # a dud -- the untouched tree already scores 0.915 and every
            # arm lands within 0.006 of it. Approximate, and ranks the
            # arms against each other rather than grading either; the
            # suite stays the oracle of success.
            closeness=closeness,
            # WHY it failed. This was only ever recorded on MEMORY_WRITE,
            # which is warm-only -- so cold's failures were invisible and
            # a run where cold scored 0 on five straight attempts could
            # not be diagnosed at all. Both arms, every attempt.
            error_signature=signature,
            # SELF-INFLICTED, by definition. The pre-migration source
            # parses -- its failure is a pydantic error raised at import,
            # not a SyntaxError -- so a syntax error in the graded tree can
            # only have come from the agent's own edit. Recorded because it
            # is the difference between "has not migrated it yet" and "broke
            # it with a bad edit", which `tests_passed` flattens to 0 both
            # times. Nothing acts on it: the agent fixes its own tree.
            broke_syntax=bool(signature and signature.startswith(_SYNTAX_ERRORS)),
            exit_code=result.exit_code,
            vibe_exit_code=vibe_exit_code,
            # Why Vibe's turn ended, and how many turns it actually used.
            # Without these two an attempt's shape is unknowable after the
            # fact: "8 turns, hit the limit" and "1 turn, died" look identical
            # in the event log, and they mean opposite things.
            vibe_stop=stop_reason(vibe_output),
            turns_used=workspace.steps_used(),
            # Wall-clock the AGENT spent, with the harness's own
            # bookkeeping subtracted -- see off_clock.
            attempt_seconds=round(attempt_seconds, 1),
            attempt_prompt_tokens=attempt_tokens.get("prompt_tokens", 0),
            attempt_completion_tokens=attempt_tokens.get("completion_tokens", 0),
            skill_version=skill_version,
            resumed=resume,
            # Did Vibe stop on its own terms, or was it cut off? This used
            # to decide whether the next attempt resumed; now that no
            # attempt ever resumes, it is the only remaining record of the
            # distinction, and it separates "the agent finished thinking"
            # from "the clock or the server ended it".
            ended_cleanly=last_ended_cleanly,
            # What the agent chose to do with its turns, and -- the point of
            # the warm/cold comparison -- whether it ever asked the graph
            # anything itself. See _tool_calls_total().
            tools=dict(tools_used),
            memory_calls=sum(
                v for k, v in tools_used.items() if _is_memory_tool(k)
            ),
            # WHAT THE HARNESS PUT IN FRONT OF THE MODEL, in characters:
            # the procedure Cognee holds plus whatever it retrieved for
            # this attempt. Zero for cold, always. Recorded per attempt
            # because it is the size of the one asymmetry between the
            # arms that costs tokens, and an unmeasured asymmetry in this
            # prompt has invalidated a run series before.
            memory_chars=memory_chars,
            procedure_chars=len(procedure),
            # WHAT THE DETERMINISTIC READ DID INSIDE THIS ATTEMPT. Zero for
            # cold, which has no hook, and zero for warm when nothing the
            # agent ran failed. Absent entirely where there is no journal.
            **hook_activity_seen,
        )


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
        notes: list[str] = []
        if shimmed or gutted:
            success = False
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
        # DID THIS ATTEMPT MOVE THE MIGRATION?
        #
        # On `v1_remaining`. That is the third measure this has keyed on and
        # the first that answers the question asked, so the two it replaces
        # are both worth writing down -- each was wrong in a way that read as
        # correct, and each punished warm for good work.
        #
        # `tests_passed` has two effective values on these fixtures: the
        # package imports or it does not. Warm's first pod attempt went
        # 0 -> 0 tests while clearly improving, and was recorded as a
        # failure.
        #
        # `closeness` is textual similarity to the human's merged PR. Warm's
        # second attempt made two correct edits --
        #
        #     -    class Config:
        #     -        allow_mutation = False
        #     -        frozen = True
        #     +    model_config = ConfigDict(frozen=True,)
        #
        #     -@field_validator(..., mode="before", allow_reuse=True)
        #     +@field_validator(..., mode="before")
        #     +@classmethod
        #
        # -- and closeness FELL, 0.0206 -> 0.0146, because the right answer
        # written with different whitespace is further from the reference
        # text. It stays the reported score, where ranking two arms against
        # one implementation is what it is for; it cannot decide whether an
        # attempt progressed.
        #
        # `v1_remaining` counts what must change for the migration to be
        # real, off the source, and is defined even when the tree does not
        # parse. Over the same two attempts it went 383 -> 309 -> 305 for
        # warm and 367 -> 367 for cold, which is what both arms did.
        #
        # The suite is still the oracle of DONE: `success` short-circuits
        # this, and a shimmed or gutted tree can never count as progress
        # whatever any measure says.
        if v1_remaining is not None and last_v1 is not None:
            moved = v1_remaining < last_v1
        elif closeness is not None:
            prior = last_closeness if last_closeness is not None else 0.0
            moved = closeness > prior
        else:
            moved = passed > last_passed
        advanced = not success and not rejected and moved

        # BARRIER 1: nobody starts off-clock work until BOTH arms have
        # finished attempt N.
        #
        # Warm and cold share one SGLang server. A distillation turn
        # running while the other arm is still working is load the other
        # arm did not have in its previous attempt, and per-stream
        # throughput on this hardware roughly halves under contention
        # (182.6 tok/s single, 320.1 across four). That difference would
        # land in the wall-clock comparison as if it were an effect of
        # memory.
        #
        # The wait is off_clock for whoever waits -- cold is not working
        # during warm's distillation, so it is not charged for it, and
        # both arms still get the same amount of ATTEMPT time out of the
        # shared deadline.
        if sync is not None:
            off_clock += await sync.arrive(agent_label or "anonymous")

        # A MEMORY FAILURE MUST NOT END THE AGENT'S RUN.
        #
        # This block was unguarded, so anything raised inside it escaped
        # into `_attempt_until_done`'s `except Exception`, which retries by
        # calling migrate_codebase AGAIN -- restarting the attempt counter
        # at 1 and losing the run's own accounting. Observed 2026-09-19,
        # run 6: warm's counter went 1, 2, 1 and FILE_DONE recorded one
        # attempt where three had run.
        #
        # What raised was the EMBEDDER, inside complete_trace(
        # generate_step_embeddings=True):
        #
        #     Invalid 'input[75]': maximum input length is 8192 tokens
        #
        # text-embedding-3-small's hard input limit, reached because steps
        # are now stored whole. That is a real constraint of the package,
        # reported as one -- but the agent had already done the work and
        # already been graded, and losing one vector is not a reason to
        # restart it.
        #
        # The write queue swallows its own failures for exactly this
        # reason (StepMemoryService._drain_forever). This is the same rule
        # applied to the memory calls that are awaited inline.
        try:
            if mem is not None:
                write_started = time.monotonic()
                written: dict[str, Any] = {}
                write_seconds = 0.0
                helped = bool(success or advanced)
                # WHAT THE GRADER CONCLUDED, and nothing else. One
                # SkillRunEntry: `success_score` from the independent suite
                # and `feedback` from whether it moved. Cognee turns those
                # into the procedure.
                #
                # The harness used to write a prose document per attempt
                # into its own WORKED/DID-NOT-WORK node sets as well --
                # verdict, metrics and the diff, in the harness's words.
                # Over five pod attempts that became three near-identical
                # "DID NOT WORK, same gutted file" documents saturating a
                # 2,500-character block, one of them 1,139 characters of
                # nothing because the attempt made no edits at all. It told
                # warm louder and louder that it had failed and never what
                # to do. Gone: the score is the signal.
                try:
                    written = await mem.record(
                        attempt=attempt,
                        tests_passed=passed,
                        tests_total=tests_total,
                        closeness=closeness,
                        helped=helped,
                        # THE PAIR, so the score Cognee ranks on has a
                        # gradient. Without these it fell back to clamped
                        # closeness and handed 0.0 to six consecutive
                        # attempts of run 12, four of them real progress.
                        v1_remaining=v1_remaining,
                        baseline_v1=baseline_v1,
                        parse_ok=parse_ok,
                        parse_total=parse_total,
                        # For the proposal to read, not for a later prompt:
                        # what the grader saw, in one line.
                        summary=_attempt_headline(
                            helped=helped, success=bool(success),
                            advanced=advanced, rejected=rejected,
                            passed=passed, last_passed=last_passed)
                        + (f" {' '.join(notes)}" if rejected else ""),
                        error_signature=signature,
                        latency_ms=int(attempt_seconds * 1000),
                    )
                    write_seconds = time.monotonic() - write_started
                    await emit(
                        "MEMORY_WRITE", attempt=attempt,
                        error_kind=(signature or trace_task)[:60],
                        on=("pass" if success else
                            "progress" if advanced else "no-progress"),
                        score=written.get("score"),
                        applied=written.get("applied"),
                        procedure_chars=written.get("procedure_chars"),
                        **hook_activity_seen,
                    )
                except Exception as exc:
                    # Loud. A deterministic half that writes nothing leaves
                    # warm == cold with extra latency, and every number in
                    # the summary still looks healthy.
                    print(f"  [{agent_label}] could not record attempt "
                          f"{attempt} in memory: {exc!r}")
                    await emit("MEMORY_WRITE", attempt=attempt,
                               error_kind=(signature or trace_task)[:60],
                               on="failed")
                off_clock += time.monotonic() - write_started

                # SESSION TRACES -> THE GRAPH, which is what `improve` is
                # for and the reason this call is not optional.
                #
                # Cognee's decorator wrote this attempt's trace into
                # SESSION memory. Session memory is scoped to one session
                # and is NOT graph-queryable: `recall(datasets=[...])`
                # against it answers `status='memory_warming_up'`, which
                # reads as a lost write and is not one. `improve` is the
                # documented bridge -- `persist_agent_traces` turns the
                # traces into graph nodes, `extract_agent_context` and
                # `distill_sessions` draw the lessons out of them.
                #
                # WITHOUT IT THE TRACES ARE WRITE-ONLY, and the whole
                # deterministic half degrades to "this agent can see its
                # own last five attempts" -- no cross-agent memory, no
                # second run, nothing in the graph for the code-graph or
                # skill queries to sit beside. That is precisely the shape
                # of failure this project keeps having: a memory system
                # that is fully wired and reads back empty.
                #
                # Off the clock, after the verdict, and never fatal.
                # INGESTED carries what the stages reported, so "nothing
                # reached the graph" is countable rather than inferred.
                ingest_started = time.monotonic()
                try:
                    bridged = await mem.improve()
                    stages = bridged.get("stages") or {}
                    persisted = (stages.get("persist_agent_traces") or {})
                    counts = persisted.get("counts") or {}
                    steps_written = sum(
                        v for v in counts.values() if isinstance(v, int))
                    await emit(
                        "INGESTED", attempt=attempt, steps=steps_written,
                        with_reasoning=steps_written, tool_calls=0,
                        failed_tool_calls=0, skill_loaded=bool(procedure),
                        source="cognee.improve",
                        stages={k: (v or {}).get("status")
                                for k, v in stages.items()},
                    )
                    if not steps_written:
                        # Loud, for the same reason every other empty-graph
                        # alarm in this file is loud: a deterministic half
                        # that writes nothing leaves warm == cold with
                        # extra latency, and every number in the summary
                        # still looks healthy.
                        print(f"  [{agent_label}] improve() bridged NO trace "
                              f"steps into the graph: "
                              f"{ {k: (v or {}).get('reason') for k, v in stages.items() if (v or {}).get('status') != 'completed'} }")
                except Exception as exc:
                    # Never fatal. The attempt is graded; losing this costs
                    # the next attempt some recall.
                    print(f"  [{agent_label}] improve() failed: {exc!r}")
                    await emit("INGESTED", attempt=attempt, steps=0,
                               with_reasoning=0, tool_calls=0,
                               failed_tool_calls=0, skill_loaded=bool(procedure),
                               source="cognee.improve")
                off_clock += time.monotonic() - ingest_started

                # THE SKILL, as `mem.record` left it. Cognee drafts the
                # rewrite from the SkillRunEntry's score and applies it in
                # place, so there is nothing to install and no version to
                # pin: the procedure Cognee returns next attempt IS the
                # rewritten one. Reported here rather than inside the write
                # so DISTILLED stays the event the metrics read.
                if written:
                    await emit(
                        "DISTILLED", attempt=attempt, version=None,
                        accepted=bool(written.get("applied")),
                        score=written.get("score"),
                        proposal_id=written.get("proposal_id"),
                        procedure_chars=written.get("procedure_chars"),
                        # The rewrite happens inside `mem.record`, so this is
                        # the whole write: the outcome document, the
                        # SkillRunEntry, and Cognee's proposal and its
                        # application. Reported so the summary can keep
                        # attempt time and bookkeeping time apart -- warm
                        # does more work per round than cold and an
                        # unattributed difference lands in the comparison.
                        seconds=round(write_seconds, 1),
                    )

        except Exception as exc:
            # Loud, and not fatal. The attempt stands, the verdict stands,
            # and the run continues; what is lost is this trace's closing
            # record. Silence here would be worse than the failure -- it
            # is how "the graph is fine" survived six runs of tool-JSON.
            print(f"  [{agent_label}] MEMORY WRITE FAILED after the verdict "
                  f"(attempt kept, run continues): {exc!r}")
        # BARRIER 2: neither arm starts attempt N+1 until the off-clock
        # work is done. Without this, cold would be released by barrier 1
        # and start its next attempt straight into warm's distillation --
        # which is the contention this is here to remove.
        if sync is not None:
            off_clock += await sync.arrive(agent_label or "anonymous")

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

        # NO ROLLBACK. THE AGENT CONTINUES FROM WHERE IT IS.
        #
        # There was a checkpoint/restore here. It was never asked for; I
        # added it, and the operator's instruction is explicit: "They should
        # just continue on each attempt. Never start from scratch. Never
        # 'pick some random code you can't test'."
        #
        # It also did measurable harm. It keyed on `tests_passed`, which on
        # `fixtures/oapi` has three values -- 0 (does not import), ~310
        # (imports) and 445 (finished) -- and is therefore blind to how much
        # of the migration exists. Two attempts in the 2026-09-18/19 series
        # were rolled back:
        #
        #   run 2 warm attempt 3   scored 0 at 8 v1 surfaces (floor is 3)
        #                          -> restored a 310-passing tree at 40
        #   run 5 warm attempt 2   scored 0 at 8, one syntax error
        #                          -> restored a 311-passing tree at 55
        #
        # Both hits landed on warm, the arm under test, and both discarded
        # the most complete migration the series produced in order to
        # recover a barely-migrated tree that scored better on a metric that
        # cannot see migration. A safety net that throws away the work it is
        # supposed to protect is worse than none.
        #
        # An agent that breaks its own tree now fixes its own tree, which is
        # what a developer does and what the next attempt's fed-back error
        # tells it to do. The failure KIND is still recorded, on
        # ATTEMPT_DONE's `broke_syntax` -- reported, never acted on.

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
            last_v1 = v1_remaining
            # Not updated on a rejected attempt, for the same reason
            # `last_passed` is not: a shimmed tree can score well, and
            # raising the bar to it would make the attempt that un-shims the
            # file and legitimately improves read as a regression.
            last_closeness = closeness
        # UPDATED ON EVERY ATTEMPT, rejected or not, because these two are
        # not a bar to beat -- they are what the next attempt's account
        # compares against, and it has to describe what actually happened.
        last_tree = file_contents
        last_parse_ok = parse_ok
        last_error = _trim_error_for_prompt(_localize_sandbox_paths(result.output, vibe_cwd))
        # Every number the grader has, and no gloss on any of them. The v1
        # count carries its starting value because a bare "47 remaining"
        # does not say whether that is nearly done or barely begun.
        # NAMED, not just counted. "46 surfaces remaining" is a number no
        # agent can act on; run 5's warm sat on the same 46 for eight
        # attempts. The breakdown is the same measurement, read out.
        work_list = surfaces.as_work_list(file_contents, within=package_path)
        last_verdict = (
            f"- {passed} of {tests_total} tests passing\n"
            f"- {v1_remaining} Pydantic v1 surfaces remaining in "
            f"{package_path or 'the package'}"
            + (f" (this checkout started at {baseline_v1})"
               if baseline_v1 is not None else "")
            + (":\n" + "\n".join(f"    {line}" for line in work_list)
               if work_list else "")
            + f"\n- {parse_ok} of {parse_total} source files parse"
        )

    await emit("FILE_DONE", success=False, attempts=attempt)
    return MigrationResult(
        False, attempt,
        errors_cleared=max(0, len(seen_signatures) - 1),
        best_passed=best_passed,
        last_signature=last_signature,
    )
