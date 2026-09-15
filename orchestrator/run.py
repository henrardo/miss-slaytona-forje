#!/usr/bin/env python3
"""M4 (Sec. 8), simplified single-pass demo: both swarms, real Daytona
sandboxes, real Neo4j memory, a real self-hosted model via SGLang, run in
parallel against one shared model server, timed, tokens/cost tracked.

The model is a parameter (--model), not a property of the design. The
final demo target is Mistral Small 4; the default here is whatever cheap
stand-in is currently serving on the pod. One hard requirement on any
choice: it must emit tool calls under plain `tool_choice: "auto"`, because
that is what vanilla Vibe sends and the agent loop can only end a turn on a
text-only assistant message. A model that needs forcing cannot be used
here -- see harness/id_fix_proxy.py for the full account of why.

Memory is agent-callable (neo4j-agent-memory's own MCP server, registered
into Vibe as its README says -- `uvx "neo4j-agent-memory[mcp,openai]" mcp
serve`; the openai extra is needed because the package's default embedder is
OpenAI and [mcp] alone does not pull the client in) AND deterministic
(a fresh get_context() splice before every attempt) together -- modeled on
workshop-agent-memory-scripts/memory_agent_mvp.py's actual loop, not a
subset of it: that script's `what_you_remember` system prompt runs on every
turn regardless of whether the model calls a tool, every message gets
registered via add_message, and every tool call gets a reasoning step via
report_step. Both halves are present here (see
orchestrator/vibe_agent.py's migrate_codebase()); the steps come from
replaying each attempt's Vibe session transcript afterward, since we don't
control Vibe's internal loop the way that script controls pydantic_ai's.

Memory isolation is no longer `read_gate` -- that revision still let cold
agents write ReasoningTrace nodes to the shared graph (start_trace/
complete_trace were called unconditionally for every agent, warm and cold
alike; only the read tools were gated). Confirmed live: cold-0..cold-3 each
had traces in Neo4j after a run, which isn't an isolated baseline. Now cold
agents are constructed with mem=None throughout (see main_async below) and
never get a `memory` MCP block registered at all -- zero reads, zero
writes, zero Neo4j contact, a true baseline arm.

Writes are never taken on the model's say-so: a reasoning trace is closed
with the verdict of an independent pytest run in a fresh Daytona sandbox,
and trace-level success means "this attempt cleared the error it was handed"
-- see migrate_codebase().

One real, known trade-off: the orchestrator can't emit a MEMORY_READ event
per Vibe-internal tool call, since reasoning steps come from a post-hoc
replay of each attempt's session transcript rather than an inline call. That
replay is complete (every tool call from that attempt), just not real-time.

Two id_fix_proxy instances must already be running, one per swarm, both
forwarding to the same SGLang server -- this is how per-swarm token usage is
actually measured, since Vibe itself never surfaces per-call usage outside
its own process (Sec. 12: tokens come from each response's `usage` object,
and the proxy is the only thing that sees every raw response).

Requires: DAYTONA_API_KEY in the environment, NEO4J_URI/NEO4J_PASSWORD (or
their defaults) reachable, a snapshot already built via
scripts/build_snapshot.py, harness/.venv pip-installed with mistral-vibe,
`daytona login` already run locally, and both proxies up on
WARM_PROXY_URL/COLD_PROXY_URL below.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

from daytona import AsyncDaytona
from dotenv import load_dotenv
from neo4j_agent_memory import MemoryClient

# `daytona`'s own SDK lazily loads .env internally, but only inside
# AsyncDaytona()'s constructor -- too late for main()'s own preflight check
# on DAYTONA_API_KEY, which runs first. Load it explicitly here so both see
# the same resolved environment, instead of depending on that internal,
# undocumented timing.
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.vibe_agent import (
    VIBE_BIN,
    HARNESS_DIR,
    MigrationResult,
    _collect_file_contents,
    ensure_agent_venv,
    error_signature,
    migrate_codebase,
    render_config,
    tests_passed,
)
from orchestrator.events import EventBus
from orchestrator.manifest import FIXTURE_DIR, load_manifest
from orchestrator.memory import ScopedMemory, build_settings, graph_counts, reset_graph
from orchestrator.sandbox import SandboxPool
from orchestrator.snapshot import is_stale, load_state, pool_kwargs_from_state

# Sec. 9.3: "Daytona org limits start at roughly 10 vCPU... will not fit
# the starting cap" at swarm_size=6 (12 concurrent agents x 1 vCPU each).
# Confirmed live: 12 agents starting simultaneously hit a hard
# "Total CPU limit exceeded. Maximum allowed: 10" 400 from Daytona, losing
# 2 of 24 (file, swarm) work items outright (a file whose agent dies this
# way is now requeued instead of silently vanishing -- see agent_worker's
# except clause). 4 a side (8 total) is the spec's own suggested fallback,
# with real margin under the 10-vCPU cap rather than sitting exactly on it
# (5 a side = 10 total would likely work most of the time but leaves zero
# room for a sandbox from a previous sweep not yet fully released, or any
# other concurrent account activity). This one is a real, externally
# confirmed limit, not a guess -- unlike the constants removed below.
# Overridable via --swarm-size. The demo's own mechanic is 4 a side; smaller
# values exist to separate "the harness is broken" from "the GPU is saturated",
# which is not a distinction the full-size run can make. See main().
SWARM_SIZE = 4

# Exceptions that mean "this harness is wrong", not "the network hiccuped".
# Every one of these is raised by Python itself when code calls something in a
# way that can never work, so the same call will fail identically on retry.
# See agent_worker, and run 27 for what treating them as transient costs.
_HARNESS_BUGS = (TypeError, AttributeError, NameError, ImportError, AssertionError)

DEFAULT_HARD_DEADLINE_S = 300.0
DEFAULT_MODEL = "Qwen/Qwen3-8B"
# 32k window. Vibe compacts once the conversation passes this, so it has to
# leave room for the tool schemas (~2k) plus whatever one tool returns.
#
# Raised from 12,000 once the two things that forced a low value were fixed:
# the fed-back pytest output is now bounded at 6,000 characters (~1,500
# tokens) by _trim_error_for_prompt, where it used to arrive at 43,000, and
# stored tool results are capped as well. 12,000 had become actively harmful
# to the warm arm, which carries the retrieved-memory block: measured on run
# 50, warm averaged 12,838 prompt tokens per call against cold's 11,336 --
# warm sitting just above the threshold and cold just below it, so warm
# compacted on 18.1% of its messages against cold's 10.6%, and completed 8
# attempts to cold's 17. The memory block is the thing being measured, so the
# headroom moves rather than the block.
#
# 18,000 still leaves ~14k for the reply and the tool surface. Both swarms get
# the same value, so it cannot skew the comparison.
AUTO_COMPACT_THRESHOLD = 18000

# Every agent gets its own VIBE_HOME (see vibe_home_for) -- separate config,
# separate session logs, so `--continue` always resumes that agent's own
# session and never a sibling's.
#
# Agent checkouts live OUTSIDE this repository, one isolated tree each.
#
# They used to live at harness/run-{swarm}-{i}/, i.e. inside the same tree as
# fixture/ (the pristine v1 source), fixture/reference_v2/ (the answer key)
# and all seven sibling agents -- with Vibe running --trust/--auto-approve
# over it. That is not a hypothetical exposure; the 2026-09-13 run did all
# three things:
#   * four warm agents edited fixture/fastapi_mail/config.py itself,
#     corrupting the pristine source every later run seeds from (and
#     corrupting it *wrongly*, dropping the `as Settings` alias);
#   * warm-0, warm-1 and warm-3 each wrote into harness/run-cold-1/ --
#     a warm agent editing a cold agent's codebase, which by itself
#     invalidates the warm/cold comparison for that run;
#   * one agent ran grep against fixture/reference_v2/, the answer key.
# The agents were not being adversarial. They were handed absolute paths in
# the fed-back pytest output, walked up from them, and found a tree full of
# pydantic-v1 code that looked like more of their own task.
#
# Moving the checkouts out of the repo removes the fixture, the answer key
# and this project's own source from reach entirely. Siblings still share a
# parent, so this is containment by construction rather than a sandbox --
# check_containment() below is the backstop that makes any remaining
# crossing loud instead of silent.
# SHORT on purpose. This used to be `tempfile.gettempdir() / "miss-slaytona-
# forje-agents"`, which on macOS expands to
# /var/folders/r9/py7xygs97mdfz1lxk_gyfmlw0000gp/T/... -- a 20-character random
# blob the agent has to reproduce exactly, every time, by hand.
#
# It has to reproduce it by hand because every file path it uses is absolute:
# Vibe's own read_file description says "Use absolute paths", and run 13's
# transcripts contain 9 absolute file paths and 0 relative ones. Two of those
# 9 (22%) were typos -- `gyfmlw00000gp` for `gyfmlw0000gp`, one zero too many --
# and both were `edit` calls on cold-1's schemas.py. The writes went to a
# directory that does not exist, so they failed, and cold-1's schemas.py was
# still pristine v1 at the end of the run. The agent believed it had made the
# edit; the orchestrator uploaded the unedited file to Daytona; the suite
# failed on a change the agent had already "made". Nothing in the run output
# said so, and check_containment() reported it as a containment violation,
# which invalidated the whole run's comparison.
#
# 118 characters down to 47, with nothing random in the middle. Still outside
# this repository, so the containment property that moved these checkouts out
# of the tree in the first place is unchanged.
#
# .resolve() stays load-bearing: on macOS /tmp is a symlink to /private/tmp,
# and Vibe records a session against its *resolved* cwd. Launching it with the
# unresolved spelling made `--continue` look up a cwd it had never seen and die
# with "No previous sessions found" -- warm-0 once burned 27 consecutive
# 8-second attempts that way, which also faked a 2.05x token ratio.
AGENT_ROOT = Path(os.environ.get("M4_AGENT_ROOT", "/tmp/msf-agents")).resolve()


def run_dir(swarm: str, agent_id: int) -> Path:
    return AGENT_ROOT / f"{swarm}-{agent_id}"


def clear_session_logs(swarm: str, agent_id: int) -> None:
    """Delete this agent's Vibe session transcripts from previous runs.

    A run is a fresh experiment and its checkout is reseeded to pristine v1
    (see seed_repo), but VIBE_HOME persisted, so transcripts accumulated
    forever -- 14 to 17 session directories per agent by run 34.

    That is a pure warm-swarm handicap, and a growing one.
    _replay_session_messages() globs every transcript under VIBE_HOME, and the
    `replayed` line-offset dict is a local in migrate_codebase() that starts
    empty each run. So on attempt 1 of every run each warm agent replayed every
    message it had ever produced, in any earlier run, into the current run's
    trace: measured at 476 messages over 16 transcripts, 118.6s of memory work
    on warm-1 alone, against a 600s budget. Cold has mem=None and pays none of
    it, which is most of why cold consistently got more attempts (11 vs 7 in
    run 34).

    It also corrupted the data: tool calls from a run days earlier were being
    attached as ReasoningSteps to a trace keyed on today's error.

    Within a run the directory still persists, which is what `--continue`
    needs; only history from previous runs goes."""
    logs = vibe_home_for(swarm, agent_id) / "logs" / "session"
    if logs.is_dir():
        shutil.rmtree(logs, ignore_errors=True)


def vibe_home_for(swarm: str, agent_id: int) -> Path:
    """A SIBLING of the agent's checkout, never a child of it.

    This used to be `run_dir(swarm, agent_id) / ".vibe"`, which put Vibe's own
    session transcripts inside the directory the agent was told to search --
    and `messages.jsonl` is one JSON object per line, with lines up to 210,108
    characters. So:

        agent edits config.py, writes about BaseSettings
          -> its transcript now contains "BaseSettings"
          -> agent greps "BaseSettings" to find what else to migrate
          -> grep matches its own transcript and returns a 64,000-char line
          -> the 32,768-token context window is gone in one tool result

    Measured in run 11: seven greps returned ~64k chars each, `max_matches: 10`
    made no difference because a single match *is* a 210k line, and 827,189
    characters of tool results were produced across 75 results. Eight agents
    managed 15 attempts between them in 411 seconds.

    The placement was never necessary. `get_vibe_home()` (vibe/utils/paths.py)
    reads $VIBE_HOME directly and session logs go to $VIBE_HOME/logs/session,
    so the home can be anywhere. An earlier comment here claimed `<cwd>/.vibe`
    was forced because Vibe's project layer checks it first -- that layer only
    wins when such a file *exists* (core/config/layers/project.py:113), which
    was true of harness/'s stale leftover config and is not true of a freshly
    seeded checkout that has no .vibe at all."""
    return AGENT_ROOT / f"{swarm}-{agent_id}.vibe"


def repo_dir_for(swarm: str, agent_id: int, package_path: str) -> Path:
    return run_dir(swarm, agent_id) / package_path


_IGNORE_JUNK = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def seed_repo(swarm: str, agent_id: int, package_path: str, tests_path: str) -> None:
    """Lays down this agent's local checkout: the real thing a user would
    have open, not a fragment of one.

    Three things go in, and all three matter:

    * `<package_path>/` -- the pydantic v1 source. The only thing Vibe is
      expected to edit, and the only thing uploaded to Daytona for the
      independent check (see _collect_file_contents).
    * `<tests_path>/` -- the real (post-migration) suite. Seeded read-only
      in spirit: the agent may read it, but edits to it are never uploaded,
      so the Daytona oracle always runs the pristine suite and cannot be
      gamed. Without this the agent was being handed pytest tracebacks
      naming `tests/conftest.py` and had no such file to open -- 524
      consecutive failed `read_file` calls in one observed session, all on
      paths that could not exist on the machine it was running on.
    * `requirements-v2.txt` -- so "what version am I targeting" is
      answerable from the checkout rather than guessed.

    Then `git init` + one commit. This is not decoration: Vibe's project
    context (vibe/core/system_prompt.py) is *only* the absolute path plus
    `git status`. In a bare directory the model is told nothing at all about
    what it is looking at. A real user's Vibe session runs against a real
    checkout, so this makes the agent's environment match one instead of
    being a stripped-down approximation of it.

    Wipes any prior copy first, so a stale edit from an earlier run never
    leaks into a fresh one."""
    dst = run_dir(swarm, agent_id)
    for rel in (package_path, tests_path):
        target = dst / rel
        if target.exists():
            # tests/ is left read-only at the end of seeding (see below), and
            # rmtree cannot remove a directory it has no write bit on. Restore
            # write on the way out so a reseed is not blocked by the previous
            # run's own protection.
            for path in [target, *target.rglob("*")]:
                path.chmod(path.stat().st_mode | 0o200)
            shutil.rmtree(target)
        shutil.copytree(FIXTURE_DIR / rel, target, ignore=_IGNORE_JUNK)
    shutil.copy2(FIXTURE_DIR / "requirements-v2.txt", dst / "requirements-v2.txt")

    # fixture/ is chmod a-w on disk, because agents have repeatedly found and
    # edited it despite living outside this repo -- twice they rewrote
    # fastapi_mail/config.py, and once left schemas.py holding
    # `@model_validator(mode='after')("attachments")`, which is not valid
    # Python. Directory placement is not containment when the agent has bash
    # and --trust; a read-only source is.
    #
    # But shutil.copytree/copy2 preserve mode, so the agent's own checkout
    # would inherit r-xr-xr-x and every edit would fail. Restore write on the
    # copy only: the agent owns its checkout, nobody owns the fixture.
    for path in dst.rglob("*"):
        path.chmod(path.stat().st_mode | 0o200)

    # ...except the test suite, which is the oracle and is therefore read-only.
    #
    # This is not a guard bolted on for safety -- it is making the checkout
    # tell the truth. _collect_file_contents() uploads only <package_path> to
    # Daytona, so an edit to tests/ is silently discarded: the agent believes
    # it fixed something and the suite it is graded by never sees the change.
    #
    # Measured in run 15: 32 of 64 `edit` calls -- half of every edit made in
    # the run -- targeted tests/conftest.py. They failed with "String to
    # replace not found in file", because conftest.py is already v2 and has no
    # pydantic import at all. It appears in the traceback only as the top frame
    # of the import chain:
    #
    #     tests/conftest.py:7: in <module>
    #         from fastapi_mail.email_utils import DefaultChecker
    #     fastapi_mail/config.py:5: in <module>
    #         from pydantic import BaseSettings as Settings
    #     E   PydanticImportError: `BaseSettings` has been moved ...
    #
    # The agent reads that top-down and goes to work on the first file named.
    # Read-only means it now gets an immediate, accurate "permission denied"
    # instead of a misleading string-match failure, and learns in one turn that
    # the suite is not its to change -- which is also true of most real
    # migrations.
    for path in (dst / tests_path).rglob("*"):
        path.chmod(path.stat().st_mode & ~0o222)
    (dst / tests_path).chmod((dst / tests_path).stat().st_mode & ~0o222)

    # A real checkout has a .gitignore; this is that. `git status` is most of
    # what Vibe puts in the system prompt, so build junk showing as untracked
    # reads to the agent as part of the codebase it was asked to migrate.
    # Vibe's own files no longer need listing -- vibe_home_for() puts them in
    # a sibling directory, outside the checkout entirely.
    (dst / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n")

    if not (dst / ".git").exists():
        subprocess.run(["git", "init", "-q", "."], cwd=dst, check=True)
    # Identity in the repo config, not just on the seeding commit. The seed
    # commit below passes `-c user.email=...` inline, which configures nothing
    # persistent -- so every commit the *agent* then tried failed with "Please
    # tell me who you are". Run 15 burned six turns that way across four
    # agents. Committing is not part of the task, but an agent that decides to
    # commit should not be punished for it by a hole in the harness's setup.
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.name", "demo"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A", package_path, tests_path, "requirements-v2.txt", ".gitignore"],
                   cwd=dst, check=True)
    subprocess.run(
        ["git", "-c", "user.email=demo@example.com", "-c", "user.name=demo",
         "commit", "-q", "--allow-empty", "-m", "fastapi-mail at pydantic v1"],
        cwd=dst, check=True,
    )


WARM_PROXY_URL = "http://127.0.0.1:8899"
COLD_PROXY_URL = "http://127.0.0.1:8900"


# RunPod A40, this session's rate -- see the top PROGRESS SUMMARY in the
# spec for how this pod was chosen. Update if the GPU tier ever changes.
GPU_COST_PER_HOUR = 0.49


def fetch_usage(proxy_url: str) -> dict:
    with urllib.request.urlopen(f"{proxy_url}/usage", timeout=5) as resp:
        return json.loads(resp.read())


def usage_delta(before: dict, after: dict) -> dict:
    """THIS run's usage, not the proxy's lifetime total.

    id_fix_proxy's /usage counters are cumulative and never reset -- they count
    everything since that proxy process started. Reading them once at the end
    and reporting the result as "this run used N tokens" is reading an odometer
    and calling it a speed.

    It silently corrupted the entire run 12-17 series: reported LLM calls rose
    45 -> 104 -> 321 -> 526 -> 601 -> 648 -> 665 and were presented as a 13x
    throughput improvement, when the real per-run figures were
    104, 217, 205, 75, 47, 18 -- throughput falling, not rising. Every
    cross-run comparison drawn from those numbers was wrong, and the token
    ratio (the demo's headline result) was wrong in the same way whenever a
    proxy outlived a run.

    Snapshot before, snapshot after, subtract."""
    return {k: after.get(k, 0) - before.get(k, 0) for k in ("prompt_tokens", "completion_tokens", "requests")}


async def agent_worker(
    *,
    swarm: str,
    agent_id: int,
    pool: SandboxPool,
    mem: ScopedMemory | None,
    vibe_home: Path,
    vibe_cwd: Path,
    repo_dir: Path,
    test_command: str,
    deadline: float,
    bus: EventBus,
    results: list,
    baseline_signature: str | None = None,
    baseline_passed: int = 0,
) -> MigrationResult:
    """One agent, one whole-codebase task -- no queue, nothing to claim: all
    N agents in a swarm are given the identical prompt ("migrate this
    codebase") and each works it independently in its own sandbox, matching
    the actual demo mechanic (one prompt, sent concurrently to a swarm).

    Sec. 8: "A crashed agent coroutine is logged and does not take down the
    run." A transient failure (e.g. Daytona's CPU cap, hit when many agents
    request a sandbox at once) can still raise out of migrate_codebase
    before its own retry loop even starts (sandbox creation itself failing).
    There's no other agent to hand the work to anymore -- each agent's task
    is identical, not a claimed unit -- so this agent just retries its own
    attempt, bounded only by the run's deadline.

    `mem` is None for every cold agent -- passed straight through to
    migrate_codebase(), which skips every memory call entirely when it's
    None. Returns its MigrationResult (in addition to appending to
    `results`) so main_async's run_swarm() can act on it directly -- e.g.
    stopping the rest of this swarm's agents the moment one converges."""
    session_id = f"{swarm}-{agent_id}" if mem is not None else None

    async def emit(event_type: str, **kw):
        return await bus.emit(event_type, swarm=swarm, agent=agent_id, **kw)

    # What this agent had achieved the last time migrate_codebase() returned.
    # The deadline path used to report MigrationResult(False, 0), throwing away
    # the agent's real attempt count and progress -- run 30 printed "0 attempts"
    # for both swarms after 21 cold and 5 warm ATTEMPT_STARTs, because no agent
    # reached the end of its own loop before the clock ran out.
    best = MigrationResult(False, 0)

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append((swarm, agent_id, best))
            return best
        try:
            result = await migrate_codebase(
                pool=pool,
                repo_dir=repo_dir,
                test_command=test_command,
                deadline=deadline,
                emit=emit,
                vibe_home=vibe_home,
                vibe_cwd=vibe_cwd,
                mem=mem,
                session_id=session_id,
                baseline_signature=baseline_signature,
                baseline_passed=baseline_passed,
            )
            results.append((swarm, agent_id, result))
            return result
        except _HARNESS_BUGS as exc:
            # Not transient, and retrying it cannot help: the next attempt runs
            # the same broken call and raises the same way. Run 27 lost its
            # entire warm swarm to one of these -- ScopedMemory.add_step() was
            # missing a keyword its caller had started passing -- and because
            # this clause treated it like Daytona's CPU cap, all four agents
            # spun for the full 565s, burning 140 LLM calls for 0 completed
            # attempts and reporting a token ratio that measured the bug.
            # Loud and immediate is the only useful behaviour here.
            print(f"  [{swarm}-{agent_id}] HARNESS BUG, not retrying: {exc!r}")
            traceback.print_exc()
            result = MigrationResult(False, 0)
            results.append((swarm, agent_id, result))
            return result
        except Exception as exc:
            # Genuinely transient: Daytona's per-org CPU cap when many agents
            # request a sandbox at once, a dropped connection, a timeout.
            print(f"  [{swarm}-{agent_id}] {exc!r} -- retrying")


async def run_swarm(swarm: str, tasks: list[asyncio.Task]) -> None:
    """Stop for victory: the moment one agent in this swarm converges, cancel
    the rest of its sandboxes instead of letting them keep grinding for the
    remainder of the run's deadline. Swarms are independent of each other --
    warm stopping early doesn't affect cold, and vice versa -- so the
    warm/cold comparison for whichever swarm converges first is still real,
    just no longer padded by agents that kept working after the answer was
    already found."""
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is not None:
                print(f"  WARNING: a {swarm} agent coroutine raised: {exc!r}")
                continue
            if task.result().success:
                print(f"  [{swarm}] an agent converged -- stopping the rest of this swarm")
                for other in pending:
                    other.cancel()
                if pending:
                    await asyncio.wait(pending)
                return


async def main_async(hard_deadline_s: float, model: str, reset_memory: bool = False) -> int:
    manifest = load_manifest()
    state = load_state()
    pool_kwargs = pool_kwargs_from_state(state)

    run_id = f"m4-{int(time.time())}"
    bus = EventBus(run_id)
    deadline = time.monotonic() + hard_deadline_s

    # One render per agent, not per swarm: each warm agent's memory MCP
    # server registration needs its own pending-patterns file. Cold agents
    # get memory_enabled=False -- render_config never writes a
    # neo4j-agent-memory MCP block for them, so they have no path to Neo4j
    # (not a gated one; none at all).
    #
    # seed_repo gives each agent its own real local checkout of the v1
    # source (Sec. 6, corrected 2026-09-13) -- what Vibe actually edits,
    # with its own native tools. Daytona never sees this directly; it's
    # only used by migrate_codebase() to run and validate.
    package_path = manifest["package_path"]
    tests_path = manifest["tests_path"]
    for i in range(SWARM_SIZE):
        seed_repo("warm", i, package_path, tests_path)
        seed_repo("cold", i, package_path, tests_path)
        clear_session_logs("warm", i)
        clear_session_logs("cold", i)
        render_config(
            WARM_PROXY_URL, model, vibe_home=vibe_home_for("warm", i),
            active_model_alias="qwen-warm", auto_compact_threshold=AUTO_COMPACT_THRESHOLD,
            memory_enabled=True,
        )
        render_config(
            COLD_PROXY_URL, model, vibe_home=vibe_home_for("cold", i),
            active_model_alias="qwen-cold", auto_compact_threshold=AUTO_COMPACT_THRESHOLD,
        )

    # Every MCP server, actually started, before the clock starts. Checked on
    # one warm and one cold config because they differ: warm registers
    # neo4j-agent-memory as well as web, and a broken memory server is exactly
    # the failure that reads as "the model didn't use memory".
    for swarm in ("warm", "cold"):
        problems = await check_mcp_servers(vibe_home_for(swarm, 0))
        for problem in problems:
            print(f"PREFLIGHT ({swarm}): {problem}")
        if problems:
            return 1

    if reset_memory:
        deleted = await reset_graph()
        print(f"  --reset-memory: deleted {deleted} node(s) from the shared graph")
    before_counts = await graph_counts()
    print(f"  graph at start: {before_counts or '(empty)'}")

    mem_settings = build_settings()
    results: list[tuple[str, int, MigrationResult]] = []
    test_command = manifest["test_command"]

    async with AsyncDaytona() as client, MemoryClient(mem_settings) as mem_client:
        pool = SandboxPool(client, run_id=run_id, **pool_kwargs)
        await pool.sweep()

        # Force the embedding model to load and the vector indexes to be
        # touched once, before the clock starts. neo4j-agent-memory loads
        # sentence-transformers lazily on first use, so without this the very
        # first warm agent pays a multi-second, *synchronous* model load on
        # the shared event loop -- which stalls the cold agents too, putting
        # warm's memory setup cost straight into cold's wall-clock. Paid once
        # here, outside the measured window, where it belongs.
        warmup_mem = ScopedMemory(mem_client, user_identifier="warm")
        await warmup_mem.get_context("warmup")
        # The write path too, not just the read path. The extraction pipeline
        # loads spaCy's en_core_web_sm and GLiNER's gliner_medium-v2.5 on first
        # use -- measured at 12.8s -- and that load would otherwise land on
        # whichever warm agent stored the first message, inside the measured
        # window. Same reasoning as the get_context warmup above.
        await warmup_mem.add_message(
            "warmup", "assistant",
            "Warmup message: migrating fastapi_mail config.py from pydantic "
            "BaseSettings to pydantic_settings for Pydantic v2.",
        )

        # The suite's starting state, measured rather than assumed. Every
        # agent's checkout is a byte-identical copy of the same pristine
        # fixture, so one Daytona run covers all 2N of them, and it is paid
        # here -- before `wall_start`, outside the measured window.
        #
        # It exists because attempt 1 otherwise has no error signature to key
        # its trace on and falls back to the task description. Every attempt-1
        # trace ever written then carries that one identical string, so a
        # later run's attempt-1 query matches all of them at similarity 1.00
        # and they crowd out the traces worth having. Measured on run 27: four
        # of warm-0's five retrieved traces were "Migrate this codebase from
        # pydantic v1 to v2 / No edit was made", and the one carrying the real
        # config.py fix came fifth, at 0.80, truncated. Keyed on the real
        # starting error instead, every trace in the graph is keyed on a
        # failure -- which is what get_similar_traces is being asked to tell
        # apart.
        #
        # Deliberately NOT fed into attempt 1's prompt: that would hand the
        # agent its first error before it has looked, changing the task. It is
        # used only to key the trace, to seed the query, and to give
        # `tests_passed` a measured baseline instead of an assumed zero.
        baseline_result = await pool.run_pytest(
            file_contents=_collect_file_contents(repo_dir_for("warm", 0, package_path)),
            test_command=test_command,
        )
        baseline_signature = error_signature(baseline_result.output)
        baseline_passed = tests_passed(baseline_result.output)
        print(f"  baseline: {baseline_passed} tests passing | {baseline_signature or 'no error signature'}")

        await bus.emit(
            "RUN_START", run_id=run_id, package=manifest["package_path"],
            test_command=test_command, model=model,
        )

        warm_tasks = [
            asyncio.ensure_future(agent_worker(
                swarm="warm", agent_id=i, pool=pool,
                mem=ScopedMemory(mem_client, user_identifier="warm"),
                vibe_home=vibe_home_for("warm", i), vibe_cwd=run_dir("warm", i),
                repo_dir=repo_dir_for("warm", i, package_path),
                test_command=test_command, deadline=deadline, bus=bus, results=results,
                baseline_signature=baseline_signature, baseline_passed=baseline_passed,
            ))
            for i in range(SWARM_SIZE)
        ]
        # mem=None: cold agents never call a single memory method, so they
        # never touch Neo4j at all -- not gated reads, no contact.
        cold_tasks = [
            asyncio.ensure_future(agent_worker(
                swarm="cold", agent_id=i, pool=pool,
                mem=None,
                vibe_home=vibe_home_for("cold", i), vibe_cwd=run_dir("cold", i),
                repo_dir=repo_dir_for("cold", i, package_path),
                test_command=test_command, deadline=deadline, bus=bus, results=results,
                baseline_signature=baseline_signature, baseline_passed=baseline_passed,
            ))
            for i in range(SWARM_SIZE)
        ]

        run_started_at = time.time()
        wall_start = time.monotonic()
        warm_usage_before = fetch_usage(WARM_PROXY_URL)
        cold_usage_before = fetch_usage(COLD_PROXY_URL)
        await asyncio.gather(
            run_swarm("warm", warm_tasks), run_swarm("cold", cold_tasks),
        )
        elapsed_s = time.monotonic() - wall_start

        crossings, lost_edits = check_containment(run_started_at)
        if lost_edits:
            print()
            print("  edits that never landed (agent wrote to a nonexistent path):")
            for problem in lost_edits:
                print(f"     {problem}")
        if crossings:
            print()
            print("  !! CONTAINMENT VIOLATION -- this run's warm/cold comparison is NOT valid:")
            for problem in crossings:
                print(f"     {problem}")
            print()

        leaked = await pool.sweep()
        if leaked:
            print(f"  WARNING: swept {leaked} sandbox(es) not accounted for locally")

        warm_results = [r for (s, _a, r) in results if s == "warm"]
        cold_results = [r for (s, _a, r) in results if s == "cold"]
        warm_usage = usage_delta(warm_usage_before, fetch_usage(WARM_PROXY_URL))
        cold_usage = usage_delta(cold_usage_before, fetch_usage(COLD_PROXY_URL))

        await bus.emit(
            "RUN_END",
            warm_passed=sum(r.success for r in warm_results),
            cold_passed=sum(r.success for r in cold_results),
            warm_tokens=warm_usage["prompt_tokens"] + warm_usage["completion_tokens"],
            cold_tokens=cold_usage["prompt_tokens"] + cold_usage["completion_tokens"],
        )

    bus.close()

    warm_tokens = warm_usage["prompt_tokens"] + warm_usage["completion_tokens"]
    cold_tokens = cold_usage["prompt_tokens"] + cold_usage["completion_tokens"]
    warm_passed = sum(r.success for r in warm_results)
    cold_passed = sum(r.success for r in cold_results)
    gpu_cost = (elapsed_s / 3600.0) * GPU_COST_PER_HOUR
    token_ratio = (cold_tokens / warm_tokens) if warm_tokens else float("nan")

    print()
    print("=" * 60)
    # Denominator is SWARM_SIZE, not len(results): "stop for victory" cancels
    # the rest of a swarm the moment one agent converges, and a cancelled
    # agent never appends a result. Reporting 1/1 when three siblings were
    # cancelled reads as "everyone succeeded" -- it was 1 of 4.
    print(f"WARM (shared memory):  {warm_passed}/{SWARM_SIZE} agents converged"
          f" | {warm_usage['requests']} LLM calls"
          f" | {warm_usage['prompt_tokens']} prompt + {warm_usage['completion_tokens']} completion"
          f" = {warm_tokens} tokens")
    print(f"COLD (no memory):      {cold_passed}/{SWARM_SIZE} agents converged"
          f" | {cold_usage['requests']} LLM calls"
          f" | {cold_usage['prompt_tokens']} prompt + {cold_usage['completion_tokens']} completion"
          f" = {cold_tokens} tokens")
    print(f"token_ratio (cold/warm): {token_ratio:.3f}")

    # What each swarm actually achieved, which the token ratio alone does not
    # say. Run 28 reported token_ratio 1.543 -- apparently a 35% saving for
    # warm -- while warm had made 71 LLM calls to cold's 132: cheaper because
    # it did less. Cost per completed attempt is the comparable figure, and
    # errors_cleared is the progress one. Both are read off the orchestrator's
    # own independent pytest runs.
    def _depth(label: str, rs: list[MigrationResult], usage: dict) -> None:
        attempts = sum(r.attempts for r in rs)
        cleared = [r.errors_cleared for r in rs] or [0]
        tokens = usage["prompt_tokens"] + usage["completion_tokens"]
        per_attempt = tokens / attempts if attempts else float("nan")
        print(
            f"  {label:5} errors cleared: best {max(cleared)}, total {sum(cleared)}"
            f" | best tests passing {max((r.best_passed for r in rs), default=0)}"
            f" | {attempts} attempts | {per_attempt:,.0f} tokens/attempt"
        )

    print()
    print("progress (neither swarm converging makes this the comparable measure):")
    _depth("warm", warm_results, warm_usage)
    _depth("cold", cold_results, cold_usage)
    print(f"wall-clock: {elapsed_s:.1f}s")
    print(f"GPU cost (this run, ${GPU_COST_PER_HOUR}/hr): ${gpu_cost:.4f}")
    print(f"event log: runs/{run_id}.jsonl")
    return 0


def check_containment(run_started_at: float) -> list[str]:
    """Did any agent edit something that was not its own checkout?

    Scans each agent's own Vibe transcript for `edit`/`write_file` calls
    whose target lies outside that agent's directory. This is a validity
    check on the *result*, not a guard on the run: a warm agent that edits a
    cold agent's code, or the shared fixture, has broken the one comparison
    this demo exists to make, and that has to be shouted rather than left for
    someone to notice in a diff three runs later. Also re-checks the fixture
    hash, since a corrupted fixture silently poisons every future run's seed.

    Returns (problems, lost_edits). `problems` empty means the run's arms
    stayed separate; `lost_edits` are writes to paths that do not exist, which
    are a real bug but not a breach -- see the note at that branch."""
    problems: list[str] = []
    lost: list[str] = []
    for swarm in ("warm", "cold"):
        for i in range(SWARM_SIZE):
            # Both spellings: on macOS $TMPDIR is /var/folders/... which
            # resolve()s to /private/var/folders/.... Vibe tells the agent the
            # resolved form, but a path the model reconstructs itself may use
            # the other one, and comparing against only one of them would
            # flag an agent's writes to its own checkout as a violation.
            # A false CONTAINMENT VIOLATION is expensive here -- it says
            # "throw this run away" -- so match either.
            own_dir = run_dir(swarm, i)
            own = {str(own_dir), str(own_dir.resolve())}
            logs = vibe_home_for(swarm, i) / "logs" / "session"
            if not logs.is_dir():
                continue
            for transcript in logs.rglob("messages.jsonl"):
                if transcript.stat().st_mtime < run_started_at:
                    continue
                for line in transcript.read_text(errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for call in msg.get("tool_calls") or []:
                        fn = call.get("function", {})
                        if fn.get("name") not in ("edit", "write_file"):
                            continue
                        args = str(fn.get("arguments") or "")
                        for token in re.findall(r'"file_path"\s*:\s*"([^"]+)"', args):
                            if not token.startswith("/") or any(
                                token.startswith(prefix) for prefix in own
                            ):
                                continue
                            # Vibe's own per-session scratchpad. Its system
                            # prompt explicitly directs the agent to put
                            # temporary artifacts there ("draft scripts,
                            # throwaway repro tests, working notes"), so a
                            # write there is the agent following instructions,
                            # not escaping its checkout. Path is minted per
                            # session by Vibe, so match on the name.
                            if "vibe-scratchpad-" in token:
                                continue
                            # A path whose parent directory does not exist is a
                            # hallucinated path, not a breach: the write failed,
                            # so nothing outside this agent's checkout was
                            # touched and the comparison is still valid. It is
                            # still a real bug -- the agent believes it made an
                            # edit that never landed, and the orchestrator then
                            # uploads the unedited file to Daytona -- so it is
                            # reported, just not as grounds for discarding the
                            # run. Run 13 had two of these (cold-1 writing to
                            # ".../gyfmlw00000gp/..." with one zero too many)
                            # and they invalidated the whole comparison.
                            if not Path(token).parent.exists():
                                lost.append(
                                    f"{swarm}-{i} edit LOST -- wrote to a path that does not "
                                    f"exist: {token}"
                                )
                                continue
                            problems.append(f"{swarm}-{i} wrote outside its own checkout: {token}")
    stale, message = is_stale()
    if stale:
        problems.append(f"fixture/ changed during the run -- {message}")
    return sorted(set(problems)), sorted(set(lost))


# One representative, side-effect-free tool per server, with arguments that are
# valid but harmless. Listing a tool is not the same as the tool working.
_SMOKE_TESTS: dict[str, tuple[str, dict]] = {
    "neo4j-agent-memory": ("memory_get_context", {"query": "pydantic BaseSettings moved"}),
    "web": ("lookup", {"query": "what package provides validate_email in python"}),
}


async def _smoke_test_tool(session, server_name: str, tools) -> list[str]:
    """Actually call a tool and check the answer is not an error.

    `list_tools` succeeding proves only that the server process started and can
    describe itself. It proved exactly that, twice, while the tool underneath
    was dead:

      * harness/web-tools/server.py raised ModuleNotFoundError on import for an
        entire run series -- Vibe reported it only as "MCP stdio discovery
        failed: Connection closed" and the tool silently vanished from the
        model's tool list.
      * `uvx "neo4j-agent-memory[mcp]"` (without the openai extra) started
        cleanly, published all 16 tools, and answered every embedding-backed
        call with "Error getting context: OpenAI package not installed". The
        two tools an agent would actually retrieve with returned an error
        string instead of memories.

    Neither is visible in a run's output. Both look identical to a model that
    chose not to call the tool. So: call it, read the answer."""
    names = {t.name for t in tools}
    spec = _SMOKE_TESTS.get(server_name)
    if spec is None or spec[0] not in names:
        return []
    tool_name, arguments = spec
    try:
        result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=120)
    except Exception as exc:
        return [f"MCP {server_name}: calling {tool_name} raised {exc!r}."]
    text = " ".join(
        getattr(block, "text", "") or "" for block in (result.content or [])
    ).strip()
    low = text.lower()
    if getattr(result, "isError", False) or low.startswith("error") or "not installed" in low:
        return [
            f"MCP {server_name}: {tool_name} is listed but does not work -- it answered "
            f"{text[:200]!r}. Agents will call it and get that string back instead of a result."
        ]
    print(f"  MCP {server_name}: {tool_name} answered {len(text)} chars -- working")
    return []


async def check_mcp_servers(vibe_home: Path) -> list[str]:
    """Start every MCP server registered in `vibe_home`'s config and list its
    tools. Returns problems; empty means every server came up and published at
    least one tool.

    This is the "verify the wire" rule in code. A server that raises on import
    dies before it speaks protocol, and the only symptom anywhere is that its
    tools are missing from the request body -- which is indistinguishable, from
    the outside, from a model that chose not to call them. The one time that
    happened it produced two confident wrong conclusions: that this codebase
    had a step no agent could bootstrap, and that small models don't use
    memory tools. Both were a dead server."""
    import tomllib

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    config = vibe_home / "config.toml"
    if not config.exists():
        return [f"{config} does not exist -- render_config was never called."]
    servers = tomllib.loads(config.read_text()).get("mcp_servers") or []
    if not servers:
        return ["no MCP servers registered at all -- expected at least `web`."]

    problems: list[str] = []
    for entry in servers:
        name = entry.get("name") or entry.get("alias") or "<unnamed>"
        command = entry.get("command")
        if not command:
            continue  # http/sse transports aren't started by us
        params = StdioServerParameters(
            command=command,
            args=list(entry.get("args") or []),
            env={**os.environ, **(entry.get("env") or {})},
        )
        try:
            # The smoke test has to run INSIDE both context managers -- leaving
            # it outside closes the transport first and every call comes back
            # ClosedResourceError, which reads exactly like a broken server.
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=90)
                    tools = (await session.list_tools()).tools
                    if not tools:
                        problems.append(f"MCP server {name!r} started but published no tools.")
                    else:
                        print(f"  MCP {name}: {', '.join(t.name for t in tools)}")
                        problems.extend(await _smoke_test_tool(session, name, tools))
        except Exception as exc:
            problems.append(
                f"MCP server {name!r} did not start ({exc!r}). Its tools will be "
                f"silently absent from every agent's tool list. Command: "
                f"{command} {' '.join(entry.get('args') or [])}"
            )
    return problems


def preflight(model: str) -> list[str]:
    """Check, before spending a 10-minute GPU budget, the handful of things
    that have each silently consumed an entire run in this project.

    Every item here is something that already happened, not something that
    might. Each is cheap to check and impossible to notice from the printed
    summary afterwards -- which is exactly why they cost whole runs:

    * The SSH tunnel dies and port 30000 stops answering. One run produced
      token counts identical to the previous run because every agent made
      zero real LLM calls, retrying `Server disconnected` with backoff for
      the entire attempt.
    * A proxy isn't running, so `/usage` is unreachable and the run
      completes but reports nothing.
    * The proxy is pointed at a different model than `--model` says, so the
      results are attributed to the wrong thing.
    * Vibe has been hand-patched again. `tool_choice_relaxed` is a live
      counter of requests that arrived asking to force a tool call; vanilla
      Vibe never sends one, and a patched Vibe cannot terminate a turn at
      all (see harness/id_fix_proxy.py).
    * The Daytona snapshot predates a fixture edit, so the suite being run
      as the success oracle is not the suite in fixture/.
    * An MCP server dies on import, so its tools are silently absent from the
      model's tool list. This one cost five runs and two confident, wrong
      conclusions: harness/web-tools/server.py raised ModuleNotFoundError for
      the whole 2026-09-13 series, and Vibe reports that only as "MCP stdio
      discovery failed: Connection closed" -- which reads exactly like a model
      choosing not to call a tool. Nothing in the run output distinguishes the
      two. check_mcp_servers() below starts every registered server and lists
      its tools, so a dead one is loud before the clock starts.

    Returns a list of human-readable problems; empty means good to go."""
    problems: list[str] = []

    for label, url in (("warm", WARM_PROXY_URL), ("cold", COLD_PROXY_URL)):
        try:
            with urllib.request.urlopen(f"{url}/v1/models", timeout=10) as resp:
                served = {m["id"] for m in json.loads(resp.read()).get("data", [])}
        except Exception as exc:
            problems.append(
                f"{label} proxy at {url} is not answering ({exc!r}). Start it with "
                f"`python3 harness/id_fix_proxy.py {url.rsplit(':', 1)[1]} http://localhost:30000`, "
                f"and check the SSH tunnel: `curl localhost:30000/v1/models`."
            )
            continue
        if model not in served:
            problems.append(
                f"{label} proxy is serving {sorted(served)}, but --model is {model!r}. "
                f"These must match or the run is attributed to the wrong model."
            )
        try:
            with urllib.request.urlopen(f"{url}/usage", timeout=10) as resp:
                relaxed = json.loads(resp.read()).get("tool_choice_relaxed", 0)
            # Deliberately cumulative: this counter is a tripwire, not a rate.
            # A single relaxed request at any point since the proxy started
            # means the installed Vibe has been patched.
            if relaxed:
                problems.append(
                    f"{label} proxy has already relaxed {relaxed} tool_choice=required request(s). "
                    f"Vanilla Vibe never sends that; the installed package has been patched and "
                    f"agents will not be able to end a turn. Reinstall mistral-vibe."
                )
        except Exception as exc:
            problems.append(f"{label} proxy /usage is not answering ({exc!r}).")

    stale, message = is_stale()
    if stale:
        problems.append(f"{message} -- re-run scripts/build_snapshot.py.")

    return problems


def _set_swarm_size(n: int) -> None:
    global SWARM_SIZE
    SWARM_SIZE = n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--deadline-s", type=float,
        default=float(os.environ.get("M4_HARD_DEADLINE_S", DEFAULT_HARD_DEADLINE_S)),
        help="Run-level wall-clock budget in seconds, shared across every agent (Sec. 8's HARD_DEADLINE_S).",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--swarm-size", type=int, default=SWARM_SIZE,
        help="Agents per swarm (default 4, the demo's own mechanic). Lower it to give "
             "each agent a larger share of one GPU: with 8 agents on a single A40 the "
             "card sits at 100%% utilisation and a single Vibe turn takes ~15s, so five "
             "of eight agents never finished one attempt in a 410s run.",
    )
    parser.add_argument(
        "--reset-memory", action="store_true",
        help="Wipe the Neo4j graph before starting. Use this to measure what four warm "
             "agents do for each other inside one run; omit it to measure a graph that has "
             "accumulated across runs. Both are real demos; they are different claims.",
    )
    args = parser.parse_args()
    _set_swarm_size(args.swarm_size)

    if not os.environ.get("DAYTONA_API_KEY"):
        print("DAYTONA_API_KEY is not set.")
        return 1
    if not VIBE_BIN.exists():
        print(f"{VIBE_BIN} not found -- run `cd harness && uv venv .venv && uv pip install mistral-vibe` first.")
        return 1
    problems = list(preflight(args.model))
    # Built before anything else touches it: every agent's shell resolves
    # `python` through it (see AGENT_VENV), so a missing one silently sends
    # them back to the orchestrator's venv.
    problems += ensure_agent_venv(FIXTURE_DIR / "requirements-v2.txt")
    for problem in problems:
        print(f"PREFLIGHT: {problem}")
        return 1

    return asyncio.run(main_async(args.deadline_s, args.model, args.reset_memory))


if __name__ == "__main__":
    raise SystemExit(main())
