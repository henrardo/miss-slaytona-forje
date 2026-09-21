#!/usr/bin/env python3
"""Both swarms, in parallel, against one shared model server: real Daytona
sandboxes, real Cognee memory, a real self-hosted model via SGLang.

The one difference between the arms is memory, and it has TWO HALVES.
Warm agents get a `cognee` MCP block -- tools they may choose to call --
and a CogneeMemory, which wraps each attempt in `cognee.agent_memory` and
puts the procedure Cognee holds, plus whatever Cognee retrieved, in the
attempt prompt. Cold agents are constructed with `mem=None` throughout and
get neither, so they have zero contact with the graph: not gated reads,
none. Anything else that touches one arm and not the other is a bug,
latency included.

The voluntary half alone is not enough for a small model, and this project
has the evidence: 40 consecutive runs ended with zero agent-initiated
memory calls while every check reported green. `--memory-mode` selects
which halves are live, so "would it have gone and looked?" stays a
question a run can ask rather than an assumption baked into the harness.

The SCORE is not taken on the model's say-so: it is the verdict of an
independent pytest run in a fresh Daytona sandbox, and it is what Cognee
is handed as the skill run's success score.

`--model` must emit tool calls under plain `tool_choice: "auto"` and must be
able to end a turn with a text-only message. That is the one hard constraint
on model choice; NOTES-hard-won.md explains what forcing it costs.

Requires: DAYTONA_API_KEY, a reachable NEO4J_URI/NEO4J_PASSWORD, a snapshot
built via scripts/build_snapshot.py, harness/.venv with mistral-vibe, and both
id_fix_proxy instances up on WARM_PROXY_URL/COLD_PROXY_URL (two of them is how
per-swarm token usage is measured at all -- Vibe never surfaces per-call usage
outside its own process).
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
from typing import Any

from daytona import AsyncDaytona
from dotenv import load_dotenv

# `daytona`'s own SDK lazily loads .env internally, but only inside
# AsyncDaytona()'s constructor -- too late for main()'s own preflight check
# on DAYTONA_API_KEY, which runs first. Load it explicitly here so both see
# the same resolved environment, instead of depending on that internal,
# undocumented timing.
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.vibe_agent import (
    VIBE_BIN,
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
from orchestrator import cognee_layer as C
from orchestrator.sandbox import SandboxPool, install_cleanup_handlers
from orchestrator.snapshot import is_stale, load_state, pool_kwargs_from_state

# 4 a side (8 agents). Daytona's org CPU cap is the binding constraint, not a
# guess: 12 agents starting at once hit a hard "Total CPU limit exceeded.
# Maximum allowed: 10" 400 and lost work items outright. 8 leaves real margin
# for a sandbox from a previous sweep not yet released.
#
# Overridable via --swarm-size. Lower it to separate "the harness is broken"
# from "the GPU is saturated", which a full-size run cannot distinguish.
SWARM_SIZE = 4

# Exceptions that mean "this harness is wrong", not "the network hiccuped".
# Every one of these is raised by Python itself when code calls something in a
# way that can never work, so the same call will fail identically on retry.
# See agent_worker, and run 27 for what treating them as transient costs.
_HARNESS_BUGS = (TypeError, AttributeError, NameError, ImportError, AssertionError)

# Even for genuinely transient failures, an agent that cannot complete an
# attempt this many times in a row is not going to. See agent_worker's retry
# clause -- without a cap it span instantly for the whole deadline.
MAX_CONSECUTIVE_AGENT_FAILURES = 5

DEFAULT_HARD_DEADLINE_S = 300.0
DEFAULT_MODEL = "Qwen/Qwen3-8B"
# Vibe compacts past this, so it must leave room for the tool schemas plus
# whatever one tool returns, inside a 32k window.
#
# Raised from 12,000 because 12,000 penalised the arm under test: warm carries
# the retrieved-memory block, so it averaged 12,838 prompt tokens per call
# against cold's 11,336 -- warm just above the threshold, cold just below, so
# warm compacted on 18.1% of messages against cold's 10.6% and completed 8
# attempts to cold's 17. Move the headroom, not the block. Same value for both
# swarms.
#
# Raised again, 18,000 -> 24,000, once the turn leash came off. With an
# 8-turn cap an attempt ended before compaction mattered; unleashed, ONE
# attempt took four compactions, and compaction is not free here -- it is
# where the agent loses the work it has already done. Measured in that
# attempt's transcript: after each compaction it re-read a file it had
# already read and re-issued an edit it had already landed 26 messages
# earlier, and Vibe's compaction summary truncates the preserved user
# message mid-sentence, so the "do not import from pydantic.v1" instruction
# fell out of context and the agent promptly tried the shim (then reverted
# it unprompted).
#
# The model serves 32,768 (SGLang reports max_model_len=32768), so 18,000 was
# compacting with ~14k of headroom unused. 24,000 leaves ~8k, which covers the
# largest single `read_file` in this fixture (email_check.py, ~350 lines) plus
# a turn of output. Not higher than that: the failure this threshold exists to
# prevent is real and was measured at 35,516 tokens against a 32,768 limit,
# and a session that dies of overflow cannot be resumed OR compacted.
AUTO_COMPACT_THRESHOLD = 24000

# Every agent gets its own VIBE_HOME (vibe_home_for) and its own checkout
# (run_dir), both OUTSIDE this repository, so fixture/, the answer key in
# fixture/reference_v2/ and sibling agents are not reachable. They used to live
# under harness/ and agents reached all three -- see NOTES-hard-won.md,
# "Agents must stay in their own checkout".
#
# The path is short and has nothing random in it, and .resolve() is
# load-bearing: NOTES-hard-won.md, "Keep the paths the model must retype
# short". Do not make this a tempfile.mkdtemp().
AGENT_ROOT = Path(os.environ.get("M4_AGENT_ROOT", "/tmp/msf-agents")).resolve()


def run_dir(swarm: str, agent_id: int) -> Path:
    return AGENT_ROOT / f"{swarm}-{agent_id}"


def clear_session_logs(swarm: str, agent_id: int) -> None:
    """Delete this agent's Vibe session transcripts from previous runs.

    Within a run the directory persists, which is what `--continue` needs;
    only history from earlier runs goes. Without this, warm agents replayed
    every message they had ever produced into the current run's trace, and
    attached tool calls from days earlier to a trace keyed on today's error --
    NOTES-hard-won.md, "Clear session logs between runs"."""
    logs = vibe_home_for(swarm, agent_id) / "logs" / "session"
    if logs.is_dir():
        shutil.rmtree(logs, ignore_errors=True)


def vibe_home_for(swarm: str, agent_id: int) -> Path:
    """A SIBLING of the agent's checkout, never a child of it.

    Put the home inside the directory the agent searches and its own
    transcript becomes a grep target -- one match is a 210,000-character line,
    and a 32k context window is gone in one tool result. NOTES-hard-won.md,
    "VIBE_HOME must be a sibling of the checkout".

    Session logs go to $VIBE_HOME/logs/session, so the home can be anywhere."""
    return AGENT_ROOT / f"{swarm}-{agent_id}.vibe"


def repo_dir_for(swarm: str, agent_id: int, package_path: str) -> Path:
    return run_dir(swarm, agent_id) / package_path


_IGNORE_JUNK = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def seed_repo(swarm: str, agent_id: int, package_path: str, tests_path: str) -> None:
    """Lays down this agent's local checkout: the real thing a user would
    have open, not a fragment of one.

    What goes in:

    * `<package_path>/` -- the pydantic v1 source. The only thing Vibe is
      expected to edit, and the only thing uploaded to Daytona for the
      independent check (see _collect_file_contents).
    * `<tests_path>/` -- the real (post-migration) suite. Test SOURCE is left
      read-only: the agent may read it, but edits to it are never uploaded,
      so the Daytona oracle always runs the pristine suite and cannot be
      gamed. Without this the agent was being handed pytest tracebacks
      naming `tests/conftest.py` and had no such file to open -- 524
      consecutive failed `read_file` calls in one observed session, all on
      paths that could not exist on the machine it was running on.
    * `requirements-v2.txt` -- so "what version am I targeting" is
      answerable from the checkout rather than guessed.
    * ROOT_FILES -- the upstream repo's own root files, see below.

    Then `git init` + one commit. This is not decoration: Vibe's project
    context (vibe/core/system_prompt.py) is *only* the absolute path plus
    `git status`. In a bare directory the model is told nothing at all about
    what it is looking at. A real user's Vibe session runs against a real
    checkout, so this makes the agent's environment match one instead of
    being a stripped-down approximation of it.

    ROOT_FILES is the same argument taken seriously. The checkout used to be
    exactly `fastapi_mail/  tests/  requirements-v2.txt  .gitignore` -- no
    README, no pyproject.toml, no Makefile, nothing stating how the project is
    built or tested. `INCLUDED_RELATIVE_PATHS` had stripped all of it when the
    fixture was built. So the agent was dropped into a codebase with no
    conventions, and the harness compensated by hand: ~2,500 tokens of prompt
    telling it how to invoke pytest, which was us answering a question the repo
    should answer for itself. That prompt is gone (see _task_prompt), and these
    are what replace it -- not our words, the project's.

    They are real files from sabuhish/fastapi-mail at fab70e4, the same
    pre-migration commit `fastapi_mail/` comes from, and Vibe reads this kind
    of thing already: `read_file` surfaces per-directory AGENTS.md, and the
    Makefile here carries the project's own `test:` target
    (`pytest -vvv --cov ...`). pyproject.toml matters most of all -- it pins
    `pydantic = "^1.8"`, and the REAL migration (PR #195) changed exactly that
    line, so it is a legitimate part of the job the agent could not previously
    even see. reference_v2/pyproject.toml holds the post-migration version so
    the answer key is complete.

    Excluded on purpose, and each exclusion is a real limitation:

    * `poetry.lock` -- 104KB, and the real PR regenerated 899 lines of it.
      Regenerating it needs poetry and a network the sandbox does not have,
      and a 104KB file one `read_file` away from a 32k context window is a
      context bomb. So dependency resolution is out of scope here.
    * `docs/`, `examples/` -- examples/ imports fastapi_mail, so it is extra
      migration surface the Daytona oracle never checks. Including it would
      let an agent spend turns on work that cannot be graded.
    * `.github/` -- CI config for a CI that is not running.

    Note that an agent's pyproject.toml edit is NOT uploaded to Daytona either
    (_collect_file_contents takes package_path only). That is accurate rather
    than a gap: the sandbox installs from requirements-v2.txt and pytest reads
    no config from pyproject (there is no [tool.pytest.ini_options]), so the
    declaration genuinely cannot be verified by running the suite -- exactly as
    in the real repo.

    Wipes any prior copy first, so a stale edit from an earlier run never
    leaks into a fresh one."""
    # Real root files from the upstream pre-migration commit. Small on purpose;
    # see the docstring for what is deliberately left out.
    ROOT_FILES = (
        "README.md", "pyproject.toml", "CONTRIBUTING.md", "Makefile",
        "tox.ini", ".flake8", "LICENSE", "MANIFEST.in", "contributors.txt",
        "mkdocs.yml",
    )
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
    for name in ROOT_FILES:
        src = FIXTURE_DIR / name
        if src.exists():
            shutil.copy2(src, dst / name)

    # fixture/ is chmod a-w on disk, because directory placement is not
    # containment when the agent has bash and --trust: agents have twice
    # rewritten fastapi_mail/config.py in the pristine source, once leaving it
    # holding `@model_validator(mode='after')("attachments")`, which is not
    # valid Python. But copytree preserves mode, so restore write on the copy
    # -- the agent owns its checkout, nobody owns the fixture.
    for path in dst.rglob("*"):
        path.chmod(path.stat().st_mode | 0o200)

    # ...except the test suite, which is the oracle. This is not a safety
    # bolt-on, it is making the checkout tell the truth: _collect_file_contents
    # uploads only <package_path>, so an edit to tests/ is silently discarded
    # and the agent believes it fixed something the grader never sees.
    #
    # Measured in run 15: 32 of 64 `edit` calls -- half of every edit in the
    # run -- targeted tests/conftest.py, which is already v2 and has no
    # pydantic import at all. It appears in the traceback only as the top frame
    # of the import chain, and the agent reads that top-down. Read-only turns a
    # misleading "String to replace not found" into an immediate, accurate
    # permission error.
    #
    # ONLY the .py files, and this is not a detail. Locking the whole tree made
    # the local suite UNPASSABLE: four of the 33 tests write an attachment
    # fixture (`with open(attachement, "w")` in test_message.py:90 and three in
    # test_connection.py) into tests/txt_files/, so they failed with
    # PermissionError no matter what the agent did to the package. Verified
    # against the answer key -- fixture/reference_v2, the real merged
    # migration, scored 29/33 in a seeded checkout for this reason alone.
    #
    # Every one of those failures is unfixable from the package, and the prompt
    # tells the agent this suite is "the same suite your work is judged on" and
    # to "keep going until the suite passes". So the agent was instructed to
    # chase a green suite that its own checkout could not produce, while the
    # Daytona oracle -- which runs as root and ignores the mode bits -- could.
    # The two disagreed by four tests and nothing said so.
    #
    # Data files the suite writes into stay writable. Test SOURCE stays locked,
    # which is all the original measurement was about.
    for path in (dst / tests_path).rglob("*.py"):
        path.chmod(path.stat().st_mode & ~0o222)

    # A real checkout has a .gitignore; this is that. `git status` is most of
    # what Vibe puts in the system prompt, so build junk showing as untracked
    # reads to the agent as part of the codebase it was asked to migrate.
    # Vibe's own files no longer need listing -- vibe_home_for() puts them in
    # a sibling directory, outside the checkout entirely.
    (dst / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n")

    if not (dst / ".git").exists():
        subprocess.run(["git", "init", "-q", "."], cwd=dst, check=True)
    # Identity in the repo CONFIG, not just on the seed commit: the seed
    # commit's inline `-c user.email=...` configures nothing persistent, so
    # every commit the *agent* tried failed with "Please tell me who you are"
    # (six wasted turns across four agents in run 15). Committing is not part
    # of the task, but an agent that chooses to commit should not be punished
    # for it by a hole in our setup.
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.name", "demo"], cwd=dst, check=True)
    # ROOT_FILES are committed too, not left untracked. `git status` is most of
    # what Vibe puts in its system prompt, so an uncommitted README/pyproject
    # reads to the model as work in progress that someone just dropped in --
    # which is the opposite of "this is the project's existing convention".
    subprocess.run(["git", "add", "-A", package_path, tests_path, "requirements-v2.txt",
                    ".gitignore", *(n for n in ROOT_FILES if (dst / n).exists())],
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
    mem: Any | None,
    vibe_home: Path,
    vibe_cwd: Path,
    repo_dir: Path,
    test_command: str,
    deadline: float,
    bus: EventBus,
    results: list,
    baseline_signature: str | None = None,
    baseline_passed: int = 0,
    tests_total: int = 0,
    package_path: str | None = None,
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
    consecutive_failures = 0

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
                agent_label=session_id,
                tests_total=tests_total,
                package_path=package_path,
                skill_name=C.SKILL_NAME if mem is not None else None,
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
            #
            # Backed off, and counted. This used to retry instantly and
            # forever: any failure that raises immediately -- a missing `vibe`
            # binary is FileNotFoundError, which is an OSError and so not in
            # _HARNESS_BUGS -- turned this into a tight loop that printed until
            # the deadline and reported a normal-looking 0-attempt result.
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_AGENT_FAILURES:
                print(
                    f"  [{swarm}-{agent_id}] {exc!r} -- "
                    f"{consecutive_failures} consecutive failures, giving up on this agent"
                )
                traceback.print_exc()
                result = MigrationResult(False, best.attempts)
                results.append((swarm, agent_id, result))
                return result
            print(
                f"  [{swarm}-{agent_id}] {exc!r} -- retrying "
                f"({consecutive_failures}/{MAX_CONSECUTIVE_AGENT_FAILURES})"
            )
            await asyncio.sleep(min(30.0, 2.0 ** consecutive_failures))


async def run_swarm(swarm: str, tasks: list[asyncio.Task],
                    *, stop_on_success: bool = True) -> None:
    """Stop for victory: the moment one agent in this swarm converges, cancel
    the rest of its sandboxes instead of letting them keep grinding for the
    remainder of the run's deadline. Swarms are independent of each other --
    warm stopping early doesn't affect cold, and vice versa -- so the
    warm/cold comparison for whichever swarm converges first is still real,
    just no longer padded by agents that kept working after the answer was
    already found.

    `stop_on_success=False` disables it for MEASUREMENT runs. Ending a swarm
    the moment one agent converges truncates that arm's distribution: the
    converging agent stops early and the others never finish, so
    attempts-to-converge and tokens-per-run are censored for the winner and
    undefined for the rest. For a warm-vs-cold comparison both arms have to
    run their full course."""
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is not None:
                print(f"  WARNING: a {swarm} agent coroutine raised: {exc!r}")
                continue
            if task.result().success and stop_on_success:
                print(f"  [{swarm}] an agent converged -- stopping the rest of this swarm")
                for other in pending:
                    other.cancel()
                if pending:
                    await asyncio.wait(pending)
                return


async def main_async(hard_deadline_s: float, model: str, reset_memory: bool = False,
                     memory_mode: str = "hybrid",
                     cognee_mcp_url: str = "http://127.0.0.1:8811/mcp") -> int:
    manifest = load_manifest()
    state = load_state()
    pool_kwargs = pool_kwargs_from_state(state)

    run_id = f"m4-{int(time.time())}"
    bus = EventBus(run_id)
    setup_start = time.monotonic()
    # NOTE: `deadline` is deliberately NOT set here. It is set immediately
    # before the agents start (search for `deadline =` below).
    #
    # It used to be set on this line, so everything between here and the first
    # ATTEMPT_START came out of the agents' budget: eight render_config calls,
    # check_mcp_servers starting four MCP servers with 120s smoke tests against
    # OpenAI and Neo4j, the two memory warmups, and the baseline Daytona pytest.
    # Measured: RUN_START was stamped at t=68.9s, and every `--deadline-s 600`
    # run in runs/accumulation.csv reports a 533-546s wall-clock, because
    # `wall_start` was taken after setup while `deadline` was taken before it.
    # ~10% of every run was silently spent on preflight, and the summary said
    # otherwise.

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

    # NO SIDECAR, NO HOOK, NO RELAY. They existed so a per-tool-call hook
    # could reach a warm ScopedMemory over loopback instead of paying a
    # 1.5s package import per call. All three are retired with the old
    # memory layer, and so is the `step_memory` seam they were reached
    # through -- the agent writes what it chooses through its MCP server,
    # and what the harness writes it writes from here.
    dataset = C.configure()

    for i in range(SWARM_SIZE):
        seed_repo("warm", i, package_path, tests_path)
        seed_repo("cold", i, package_path, tests_path)
        clear_session_logs("warm", i)
        clear_session_logs("cold", i)
        render_config(
            WARM_PROXY_URL, model, vibe_home=vibe_home_for("warm", i),
            active_model_alias="qwen-warm", auto_compact_threshold=AUTO_COMPACT_THRESHOLD,
            # Writes the cognee `[[mcp_servers]]` block -- the VOLUNTARY
            # half of warm's treatment. The deterministic half is the
            # CogneeMemory handed to the agent worker below; neither
            # implies the other, and cold gets neither.
            memory_enabled=True,
            cognee_mcp_url=cognee_mcp_url,
            agent_label=f"warm-{i}",
        )
        render_config(
            COLD_PROXY_URL, model, vibe_home=vibe_home_for("cold", i),
            active_model_alias="qwen-cold", auto_compact_threshold=AUTO_COMPACT_THRESHOLD,
        )

    # Every MCP server, actually started, before the clock starts. Checked on
    # one warm and one cold config because they differ: warm registers
    # neo4j-agent-memory as well as web, and a broken memory server is exactly
    # the failure that reads as "the model didn't use memory".
    #
    # `skip` stops the second pass re-smoke-testing `web`. That smoke test is
    # a real, BILLED OpenAI hosted web_search call -- and the `web` server is
    # byte-identical in both arms, so the cold pass was re-proving the warm
    # pass's result at full price. Measured across today's runs: 30 web_lookup
    # calls in total, 16 of them this smoke test, i.e. over half of all web
    # spend went on proving a server was alive rather than on any agent's
    # question. Memory is still checked, because it is the thing that differs.
    smoke_tested: set[str] = set()
    for swarm in ("warm", "cold"):
        problems = await check_mcp_servers(
            vibe_home_for(swarm, 0), skip=smoke_tested
        )
        smoke_tested.add("web")
        for problem in problems:
            print(f"PREFLIGHT ({swarm}): {problem}")
        if problems:
            return 1

    if reset_memory:
        # SCOPED TO THIS DATASET, and that is less than it sounds: Cognee's
        # graph search is not dataset-scoped (measured -- see
        # cognee_layer), so a run on a shared instance can still retrieve
        # another fixture's lessons. swarm/run.py carries
        # `--reset-memory-everything` for when a series needs a genuinely
        # empty graph.
        await C.forget_everything(dataset=dataset)
        print(f"  --reset-memory: forgot dataset {dataset}")
    before_counts = await C.assert_ready()
    print(f"  graph at start: {before_counts or '(empty)'}")
    procedure = await C.ensure_skill(dataset=dataset)
    print(f"  skill: {len(procedure):,} chars in Cognee, dataset {dataset}")
    # THE CODEBASE AS A GRAPH, read back by warm through `code_brief`.
    # Deterministic, keyless, and re-ingested each run because the fixture's
    # tree is whatever the last experiment left it as.
    code_dataset: str | None = f"{dataset}-code"
    code_root = FIXTURE_DIR / manifest["package_path"]
    try:
        kinds = await C.ingest_code_graph(code_root, dataset=code_dataset)
        print(f"  code graph: {code_root.name} -> {code_dataset} {kinds}")
    except Exception as exc:
        code_dataset = None
        print(f"  code graph: ingestion failed ({exc!r}); continuing without it")

    results: list[tuple[str, int, MigrationResult]] = []
    test_command = manifest["test_command"]
    # None means "the run never got far enough to extract" -- distinct from 0,
    # which means extraction ran and found nothing. The summary prints the
    # difference.
    entities_extracted: int | None = None

    async with AsyncDaytona() as client:
        pool = SandboxPool(client, run_id=run_id, **pool_kwargs)
        # Wired, finally. sandbox.py has shipped this since M2 and nothing ever
        # called it, so a Ctrl-C or a SIGTERM mid-run left every live sandbox
        # running and billable -- the exact leak the module docstring says is
        # "the standard way to overspend on Daytona". The in-run `finally` in
        # SandboxPool.sandbox() does not help there: the interpreter is going
        # away, not unwinding.
        install_cleanup_handlers(pool)
        await pool.sweep()

        # Pay Cognee's first-use cost HERE, outside the measured window.
        # The first `recall` of a process resolves the default user, opens
        # the relational store, loads the embedder and touches the vector
        # index; landing that on the first warm attempt would put warm's
        # setup into the comparison, and -- because it is one event loop --
        # into cold's wall-clock too.
        #
        # The QUERY IS DELIBERATELY UNRELATED to the task. The warmup this
        # replaces once read "migrating fastapi_mail config.py from
        # pydantic BaseSettings to pydantic_settings for Pydantic v2",
        # which is the correct fix for the first file in the failure
        # chain, written into the warm arm's memory on every run and
        # nowhere in cold's. The thing that was only supposed to load a
        # model was handing warm part of the answer.
        try:
            await C.recall_node_set(
                dataset=dataset, node_set="warmup-nothing-is-here",
                query="Priya Raman met Tomas Nowak in Lisbon on Tuesday to "
                      "discuss the quarterly logistics review at Acme "
                      "Freight.")
        except Exception as exc:
            print(f"  cognee warmup failed ({exc!r}); the first warm attempt "
                  f"will pay it instead")

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

        setup_s = time.monotonic() - setup_start
        print(f"  setup: {setup_s:.1f}s (outside the agents' budget)")

        # The agents' clock starts HERE, not at the top of main_async. Every
        # agent and the whole loop share this one absolute timestamp.
        deadline = time.monotonic() + hard_deadline_s

        await bus.emit(
            "RUN_START", run_id=run_id, package=manifest["package_path"],
            test_command=test_command, model=model, setup_s=round(setup_s, 1),
            deadline_s=hard_deadline_s,
        )

        # One CogneeMemory per warm agent. The SESSION IS PER RUN AND PER
        # AGENT (`{run_id}:warm-{i}`), never the bare label: every trace
        # this project ever wrote landed in one session called "warm-0",
        # 98 runs of it, and everything that walked that session got
        # slower until it stopped finishing.
        warm_mems = {
            i: C.CogneeMemory(dataset=dataset, fixture=FIXTURE_DIR.name,
                              label=f"warm-{i}",
                              session_id=f"{dataset}:{run_id}:warm-{i}",
                              mode=memory_mode, code_dataset=code_dataset,
                              code_repo=code_root.name,
                              package=manifest["package_path"])
            for i in range(SWARM_SIZE)
        }

        warm_tasks = [
            asyncio.ensure_future(agent_worker(
                swarm="warm", agent_id=i, pool=pool,
                mem=warm_mems[i],
                vibe_home=vibe_home_for("warm", i), vibe_cwd=run_dir("warm", i),
                repo_dir=repo_dir_for("warm", i, package_path),
                test_command=test_command, deadline=deadline, bus=bus, results=results,
                baseline_signature=baseline_signature, baseline_passed=baseline_passed,
                tests_total=int(manifest.get("test_total") or 0),
                package_path=manifest["package_path"],
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
                tests_total=int(manifest.get("test_total") or 0),
                package_path=manifest["package_path"],
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

        # ONE LAST BRIDGE, after the agents' clock has stopped.
        #
        # `migrate_codebase` calls `improve` after each attempt, so in a
        # healthy run this is a no-op that reports `skipped -- no new
        # session entries`. It runs anyway because the attempt-level call
        # is inside the loop's own "never fatal" guard: an agent whose
        # last improve() failed, or which was cancelled between the
        # verdict and the bridge, would otherwise leave its final -- and
        # most informative -- trace in session memory only, where the
        # next run cannot see it.
        #
        # ENTITY EXTRACTION IS GONE FROM HERE, and that is a real change
        # rather than a deletion: the old layer ran spaCy + GLiNER +
        # OpenAI over every message in a 240s-bounded pass, because inline
        # extraction cost 2,071ms per message. Cognee extracts inside
        # `improve`, so what used to be a separate after-the-clock pass is
        # now one of its stages.
        entities_extracted = 0
        for i in range(SWARM_SIZE):
            try:
                bridged = await warm_mems[i].improve()
                stages = bridged.get("stages") or {}
                entities_extracted += sum(
                    sum(v for v in (s.get("counts") or {}).values()
                        if isinstance(v, int))
                    for s in stages.values() if isinstance(s, dict))
            except Exception as exc:
                print(f"  improve() failed for warm-{i}: {exc!r}")

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

    # Input and output, never just their sum. Prompt tokens dominate by ~36x
    # here, so a combined ratio is a prompt-token ratio wearing a disguise: the
    # 2026-09-16 run reported 0.867 combined while output was 1.001 -- i.e. the
    # two swarms generated the SAME amount and differed only in what they were
    # made to read. Those are opposite findings and the sum reported one of
    # them. Input is mostly context growth (retrieved steps, injected hook
    # output, a longer prompt); output is what the model actually produced.
    def _ratio(numerator: int, denominator: int) -> float:
        return (numerator / denominator) if denominator else float("nan")

    input_ratio = _ratio(cold_usage["prompt_tokens"], warm_usage["prompt_tokens"])
    output_ratio = _ratio(
        cold_usage["completion_tokens"], warm_usage["completion_tokens"]
    )

    print()
    print("=" * 60)
    # Denominator is SWARM_SIZE, not len(results): "stop for victory" cancels
    # the rest of a swarm the moment one agent converges, and a cancelled
    # agent never appends a result. Reporting 1/1 when three siblings were
    # cancelled reads as "everyone succeeded" -- it was 1 of 4.
    print(f"WARM (shared memory):  {warm_passed}/{SWARM_SIZE} agents converged"
          f" | {warm_usage['requests']} LLM calls"
          f" | in {warm_usage['prompt_tokens']:,} / out {warm_usage['completion_tokens']:,}"
          f" = {warm_tokens:,} tokens")
    print(f"COLD (no memory):      {cold_passed}/{SWARM_SIZE} agents converged"
          f" | {cold_usage['requests']} LLM calls"
          f" | in {cold_usage['prompt_tokens']:,} / out {cold_usage['completion_tokens']:,}"
          f" = {cold_tokens:,} tokens")
    print(f"ratio (cold/warm):  input {input_ratio:.3f}  output {output_ratio:.3f}"
          f"   [>1 = warm cheaper]")

    # What each swarm actually achieved, which the token ratio alone does not
    # say. Run 28 reported token_ratio 1.543 -- apparently a 35% saving for
    # warm -- while warm had made 71 LLM calls to cold's 132: cheaper because
    # it did less. Cost per completed attempt is the comparable figure, and
    # errors_cleared is the progress one. Both are read off the orchestrator's
    # own independent pytest runs.
    def _depth(label: str, rs: list[MigrationResult], usage: dict) -> None:
        attempts = sum(r.attempts for r in rs)
        cleared = [r.errors_cleared for r in rs] or [0]
        nan = float("nan")
        in_per = usage["prompt_tokens"] / attempts if attempts else nan
        out_per = usage["completion_tokens"] / attempts if attempts else nan
        print(
            f"  {label:5} errors cleared: best {max(cleared)}, total {sum(cleared)}"
            f" | best tests passing {max((r.best_passed for r in rs), default=0)}"
            f" | {attempts} attempts"
            f" | {in_per:,.0f} in + {out_per:,.0f} out per attempt"
        )

    print()
    print("progress (neither swarm converging makes this the comparable measure):")
    _depth("warm", warm_results, warm_usage)
    _depth("cold", cold_results, cold_usage)
    print(f"wall-clock: {elapsed_s:.1f}s agents (+{setup_s:.1f}s setup, outside the budget)")
    print(f"GPU cost (this run, ${GPU_COST_PER_HOUR}/hr): ${gpu_cost:.4f}")
    print(f"event log: runs/{run_id}.jsonl")

    # THE GATE, printed last, because everything above it can look healthy on a
    # run that measured nothing. 40 consecutive runs reported plausible token
    # ratios and 4 attempts a side while the oracle never ran once: one Vibe
    # invocation ate the whole deadline, so pool.run_pytest was called with
    # ~0s and raised, and every trace closed without a verdict. Nothing in the
    # summary said so. A zero here means throw the run away.
    graded = sum(1 for e in bus.events if e["type"] == "ATTEMPT_DONE")
    oracle = sum(1 for e in bus.events if e["type"] == "SANDBOX_CREATED")
    reads = [e for e in bus.events if e["type"] == "MEMORY_READ"]
    print()
    if graded and oracle:
        print(f"GATE ok: {graded} attempt(s) graded by {oracle} real Daytona run(s).")
    else:
        print(f"GATE FAILED: {graded} attempts graded, {oracle} oracle runs. "
              f"This run measured NOTHING -- discard it. Every number above is "
              f"an artifact of agents that never reached a verdict.")
    # THE TWO HALVES, REPORTED APART. `cognee.agent_memory` is the
    # harness's own deterministic retrieval; anything else is a tool the
    # agent chose to call. Summing them would answer "did warm have
    # memory" and destroy the answer to "did warm go and get it", which
    # is the question 40 runs of this project turned on.
    injected = [e for e in reads if "cognee.agent_memory" in (e.get("sources") or [])]
    chosen = [e for e in reads if e not in injected]
    if chosen:
        calls = sum(e.get("hits", 0) for e in chosen)
        srcs = sorted({s for e in chosen for s in e.get("sources") or []})
        # "calls", not "hits". This counts what the agent ASKED, which is not
        # what it got: the first agent-initiated read in this project's history
        # was `memory_get_context(session_id=null, query=null)`, and the server
        # answered with an OpenAI 400 ("input cannot be an empty string").
        # Reported as a hit at the time, which was wrong.
        print(f"     warm called its memory tools itself on {len(chosen)} "
              f"attempt(s), {calls} call(s), {srcs}")
    else:
        print("     warm never called a memory tool itself -- a finding "
              "about the model, not an error")
    print(f"     cognee retrieved for warm on {len(injected)} attempt(s), "
          f"{sum(e.get('chars', 0) for e in injected):,} chars injected")
    print(f"     improve() stage counts after the clock stopped: "
          f"{entities_extracted}")
    if not injected and not chosen:
        print("     WARM READ NOTHING, by either route -- warm == cold plus "
              "latency, and any token ratio above is a null result.")
    return 0 if (graded and oracle) else 1


def check_containment(run_started_at: float) -> tuple[list[str], list[str]]:
    """Did any agent edit something that was not its own checkout?

    Scans each agent's own Vibe transcript for `edit`/`write_file` calls
    whose target lies outside that agent's directory. This is a validity
    check on the *result*, not a guard on the run: a warm agent that edits a
    cold agent's code, or the shared fixture, has broken the one comparison
    this demo exists to make, and that has to be shouted rather than left for
    someone to notice in a diff three runs later. Also re-checks the fixture
    hash, since a corrupted fixture silently poisons every future run's seed.

    SCOPE, stated because it was previously overclaimed: this sees `edit` and
    `write_file` only. Vibe also ships `bash`, `git_bash` and
    `experimental_bash`, all enabled under --trust --auto-approve, and agents
    use bash constantly (7 of 22 calls in one measured session). An agent that
    writes with `sed -i` or `cat >` is invisible here. The real containment
    property is that fixture/ is chmod a-w on disk and each checkout lives in
    its own directory; this is a tripwire on the most common write path, not a
    sandbox.

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
    # cognee-mcp's own read tool, with the arguments its signature takes
    # (`query`, not `query_text`). An empty graph answers this with
    # "memory_warming_up" rather than an error, which passes -- correctly:
    # the question here is whether the server WORKS, not whether anything
    # has been remembered yet.
    "cognee": ("recall", {"query": "pydantic BaseSettings moved", "top_k": 3}),
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


async def check_mcp_servers(
    vibe_home: Path, *, skip: set[str] | None = None
) -> list[str]:
    """Start every MCP server registered in `vibe_home`'s config and list its
    tools. Returns problems; empty means every server came up and published at
    least one tool.

    `skip` names servers whose TOOL SMOKE TEST has already been paid for on
    another config. The server is still started and its tools still listed --
    that is the cheap half and the half that catches a dead import. What is
    skipped is calling a tool for real, which for `web` is a billed OpenAI
    hosted web_search.

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
                        if name in (skip or set()):
                            print(f"  MCP {name}: smoke test already paid for, "
                                  f"not calling it again")
                        else:
                            problems.extend(
                                await _smoke_test_tool(session, name, tools)
                            )
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
    parser.add_argument(
        "--memory-mode", choices=C.MEMORY_MODES, default="hybrid",
        help="WHICH HALVES OF WARM'S TREATMENT ARE LIVE. `hybrid` is both: "
             "the cognee MCP server the agent may call, and the procedure "
             "plus retrieved context the harness puts in its prompt. `mcp` "
             "is the tools alone, which measures whether the model goes "
             "and looks. `deterministic` is the injection alone, which "
             "measures the memory without the model's willingness to use "
             "a tool. `off` makes warm == cold.",
    )
    parser.add_argument(
        "--cognee-mcp-url", default="http://127.0.0.1:8811/mcp",
        help="Where cognee-mcp is listening. Start it with "
             "`cognee-mcp --transport http --host 127.0.0.1 --port 8811`.",
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
    # `return 1` used to sit INSIDE this loop, so only the first problem was
    # ever printed -- you fixed one thing, re-ran, and found the next.
    for problem in problems:
        print(f"PREFLIGHT: {problem}")
    if problems:
        return 1

    return asyncio.run(main_async(args.deadline_s, args.model, args.reset_memory,
                                  memory_mode=args.memory_mode,
                                  cognee_mcp_url=args.cognee_mcp_url))


if __name__ == "__main__":
    raise SystemExit(main())
