"""Getting a skill into the model's context, and proving it got there.

Three separate things have to be true, and each can succeed while the next
fails silently:

  1. the file is written where Vibe looks,
  2. Vibe parses it and offers it,
  3. Vibe puts its text in the conversation.

This project has already paid for the equivalent gap once: run 9's memory
server was configured, running and answering, and the model was handed zero
memory tools -- which in the summary looked exactly like a model that chose
not to use memory. A skill that never loads looks exactly like a model that
ignored its own procedure, and the two have opposite fixes.

Nothing here needs a pod: the host is faked and every command it would run
over SSH is answered from a dict.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from orchestrator import cognee_layer as skills  # same role, new owner
from orchestrator import vibe_agent
from swarm.agent_workspace import AgentWorkspace, SwarmHost, _body_sha


class FakeHost(SwarmHost):
    """A pod's filesystem, in a dict.

    It answers the three commands `install_skill` actually runs -- the
    recursive `sha256sum` read-back, `test -x`, and `cat` -- from what was
    written to it, so the verification path is exercised rather than
    stubbed. `drop_on_readback` and `corrupt_on_readback` simulate the two
    ways a transfer goes wrong quietly.
    """

    def __init__(self) -> None:
        super().__init__(host="fake", port=22, identity=Path("/dev/null"))
        self.commands: list[str] = []
        self.files: dict[str, bytes] = {}
        self.modes: dict[str, str] = {}
        self.answers: dict[str, str] = {}
        self.drop_on_readback: set[str] = set()
        self.corrupt_on_readback: set[str] = set()
        self.executable = True

    def _answer(self, command: str):
        self.commands.append(command)
        for needle, reply in self.answers.items():
            if needle in command:
                return _Completed(reply)
        if "rm -rf" in command:
            root = command.split("rm -rf ", 1)[1].split()[0]
            for path in [p for p in self.files if p.startswith(root)]:
                del self.files[path]
            return _Completed("")
        if "sha256sum" in command:
            return _Completed(self._sha_listing(command))
        if command.startswith("test -x "):
            return _Completed("yes" if self.executable else "no")
        if command.startswith("cat "):
            return _Completed(self.files.get(command[4:], b"").decode())
        return _Completed("")

    def _sha_listing(self, command: str) -> str:
        root = command.split("cd ", 1)[1].split(" &&")[0].strip("'\"")
        lines = []
        for path, content in sorted(self.files.items()):
            if not path.startswith(root + "/"):
                continue
            rel = path[len(root) + 1:]
            if rel in self.drop_on_readback:
                continue
            if rel in self.corrupt_on_readback:
                content = content + b"tampered"
            lines.append(f"{hashlib.sha256(content).hexdigest()}  ./{rel}")
        return "\n".join(lines)

    def run(self, command: str, **kw):
        return self._answer(command)

    def run_as(self, agent_user: str, command: str, **kw):
        return self._answer(command)

    def put(self, data: bytes, dst: str, *, mode: str = "600",
            owner: str | None = None) -> None:
        self.files[dst] = data
        self.modes[dst] = mode


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout, self.stderr, self.returncode = stdout, "", 0


class _WS(AgentWorkspace):
    """Forwards the fake host's knobs so tests read as one object."""

    def __getattr__(self, item):
        if item in ("drop_on_readback", "corrupt_on_readback", "modes"):
            return getattr(self.host, item)
        raise AttributeError(item)

    def __setattr__(self, key, value):
        if key == "executable":
            self.host.executable = value
            return
        super().__setattr__(key, value)


@pytest.fixture
def ws() -> AgentWorkspace:
    return _WS(host=FakeHost(), label="warm-0", model="m")


def _live_package():
    """The v0 scaffold, read off disk exactly as `cognee_layer.live_skill`
    seeds Cognee from it.

    Built here rather than fetched from a registry: Cognee keeps no
    version registry -- it rewrites `procedure` in place -- so there is
    no `skills.current()` to ask. install_skill is still ours and is
    still what these tests are about.
    """
    from swarm.agent_workspace import _dir_sha

    text = skills.SEED_SKILL_PATH.read_text()
    files = {"SKILL.md": text.encode("utf-8")}
    schema = (skills.SEED_SKILL_PATH.parent / "source" / "procedure.schema.json")
    if schema.exists():
        files["source/procedure.schema.json"] = schema.read_bytes()
    # Over path -> sha PAIRS, exactly as install_skill does it, or the
    # comparison tests a different hash from the one under test.
    digests = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    return skills.SkillVersion(version=0, text=text, files=files,
                               body_sha=_body_sha(text),
                               dir_sha=_dir_sha(digests)), files


LIVE, PACKAGE = _live_package()


def test_the_whole_package_lands_where_vibe_looks(ws) -> None:
    """$VIBE_HOME/skills/<name>/, per Vibe's GLOBAL_SKILLS_DIR.

    Verified against mistral-vibe 2.25.4 by loading this exact SKILL.md
    through Vibe's own SkillManager: discovered, parsed, and returned by
    parse_skill_command("/pydantic-v2-migration ...").

    The whole DIRECTORY, not the one file: an AIP skill carries `source/`
    with the schema its own frontmatter references, and may carry
    `scripts/`, `references/` and `assets/`.
    """
    ws.install_skill(PACKAGE, name=skills.SKILL_NAME)
    root = f"/home/agent-warm-0/.vibe/skills/{skills.SKILL_NAME}"
    for rel, content in PACKAGE.items():
        if rel == "SKILL.md":
            # SKILL.md is RENDERED, not copied: `references/` is appended
            # to the body because the model never follows the relative
            # pointers AIP's disclosure pass leaves behind (measured, all
            # six attempts of swarm-1789903474). See inline_references().
            landed = ws.host.files[f"{root}/{rel}"]
            assert content.decode() in landed.decode(), (
                "the authored body must survive rendering intact")
            continue
        assert ws.host.files[f"{root}/{rel}"] == content, f"{rel} did not land"
    assert len(PACKAGE) > 1, "the fixture stopped exercising the multi-file case"
    assert any("source/" in k for k in PACKAGE), (
        "source/ is required by the AIP validator and must travel with the skill")


def test_installing_removes_the_previous_version(ws) -> None:
    """Vibe lists every skill it finds. A stale version left beside the new
    one is offered to the agent as an alternative procedure, and a deleted
    file would otherwise live on forever."""
    ws.install_skill(PACKAGE, name=skills.SKILL_NAME)
    wipes = [c for c in ws.host.commands if "rm -rf" in c and "skills" in c]
    assert wipes, f"the skills directory was not cleared: {ws.host.commands}"


def test_install_fails_loudly_if_a_file_did_not_land(ws) -> None:
    """Verifying what was sent proves nothing about what arrived."""
    ws.drop_on_readback.add("source/procedure.schema.json")
    with pytest.raises(RuntimeError, match="not the skill that was sent"):
        ws.install_skill(PACKAGE, name=skills.SKILL_NAME)


def test_install_fails_if_a_file_arrived_corrupted(ws) -> None:
    ws.corrupt_on_readback.add("SKILL.md")
    with pytest.raises(RuntimeError, match="differing="):
        ws.install_skill(PACKAGE, name=skills.SKILL_NAME)


def test_scripts_are_installed_executable(ws) -> None:
    """An AIP step with `script:` is useless if the script cannot run, and
    the failure is quiet -- the model improvises around it."""
    pkg = dict(PACKAGE)
    pkg["scripts/check.py"] = b"print('hi')\n"
    ws.install_skill(pkg, name=skills.SKILL_NAME)
    root = f"/home/agent-warm-0/.vibe/skills/{skills.SKILL_NAME}"
    assert ws.modes[f"{root}/scripts/check.py"] == "700"
    assert ws.modes[f"{root}/SKILL.md"] == "600"


def test_install_fails_if_a_script_is_not_executable(ws) -> None:
    pkg = dict(PACKAGE)
    pkg["scripts/check.py"] = b"print('hi')\n"
    ws.executable = False
    with pytest.raises(RuntimeError, match="not executable"):
        ws.install_skill(pkg, name=skills.SKILL_NAME)


def test_install_returns_both_hashes(ws) -> None:
    """The directory hash identifies the version; the body hash is the only
    thing a transcript can be checked against, because the frontmatter never
    reaches the model."""
    got = ws.install_skill(PACKAGE, name=skills.SKILL_NAME)
    assert got["body"] == LIVE.body_sha
    assert got["dir"] == LIVE.dir_sha
    assert got["dir"] != got["body"] != LIVE.sha
    # And what the model actually read is reported separately, so the two
    # can never be confused. They differ exactly when there is something
    # to inline.
    has_refs = any(r.startswith("references/") for r in PACKAGE)
    assert (got["body_rendered"] != got["body"]) is has_refs
    assert (got["dir_rendered"] != got["dir"]) is has_refs



def test_cold_has_no_skills_directory(ws) -> None:
    ws.host.answers["test -d"] = "no"
    assert ws.has_skills_dir() is False
    ws.host.answers["test -d"] = "yes"
    assert ws.has_skills_dir() is True


def test_a_loaded_skill_is_found_in_the_transcript(ws) -> None:
    """Vibe wraps the injected skill in <skill_content name="...">
    (core/tools/builtins/skill.py: skill_content_marker)."""
    body = skills.body_of(LIVE.text)
    ws._cache = {"tree": {}, "sessions": [[
        {"role": "user", "content": f"/{skills.SKILL_NAME} Please migrate"},
        {"role": "tool", "name": "skill",
         "content": f'<skill_content name="{skills.SKILL_NAME}">\n'
                    f'# Skill: {skills.SKILL_NAME}\n\n{body}\n</skill_content>'},
    ]]}
    loaded = ws.loaded_skill_text(skills.SKILL_NAME)
    assert loaded is not None
    assert body in loaded, "the loaded text is not the version on disk"


def test_no_skill_in_the_transcript_reads_as_not_loaded(ws) -> None:
    """The distinction that matters: "the agent ignored its procedure" and
    "the procedure never reached it" have opposite fixes."""
    ws._cache = {"tree": {}, "sessions": [[
        {"role": "user", "content": "Please migrate"},
        {"role": "assistant", "content": "ok"},
    ]]}
    assert ws.loaded_skill_text(skills.SKILL_NAME) is None


def test_warm_prompt_starts_with_the_skill_command() -> None:
    """Vibe only treats a prompt as a skill invocation when it STARTS with
    `/<name>` (SkillManager.parse_skill_command). One leading character
    decides whether the skill is loaded or is a stray token."""
    warm = vibe_agent._task_prompt(None, memory_enabled=True,
                                   skill_command=skills.SKILL_NAME)
    assert warm.startswith(f"/{skills.SKILL_NAME} ")
    # The task must survive intact: Vibe splits once on whitespace and passes
    # the remainder through as extra_instructions.
    assert "migrate this codebase" in warm.lower()


def test_cold_prompt_has_no_skill_command() -> None:
    """Cold gets no skill, so the prefix would be a stray token pointing at a
    skill it does not have."""
    cold = vibe_agent._task_prompt(None, memory_enabled=False)
    assert not cold.startswith("/")


# ---- session policy --------------------------------------------------------
#
# Both arms start a fresh session on every attempt. Two reasons, and the
# second is the one that makes it apply to COLD as well:
#
#   1. Vibe will not reload a skill into a conversation that already has it
#      ("already loaded earlier in this conversation. Reuse those
#      instructions."), so after distillation a resumed warm agent would work
#      from the superseded text while the run recorded the new version.
#   2. Fixing that for warm alone would leave warm restarting while cold
#      carried its history forward -- two differences between the arms
#      instead of one, and no way to attribute a result to either.

def test_no_attempt_ever_resumes() -> None:
    """Pinned by reading the source, because the alternative is a live run.

    `resume` is passed straight to `--continue`; anything that makes it true
    again reintroduces both problems above at once.
    """
    import inspect

    from orchestrator import vibe_agent as va
    source = inspect.getsource(va.migrate_codebase)
    assignments = [line.strip() for line in source.splitlines()
                   if line.strip().startswith("resume =")]
    assert assignments == ["resume = False"], (
        f"migrate_codebase assigns resume as {assignments}. Both arms must "
        f"start every attempt fresh: a resumed session refuses to reload a "
        f"changed skill, and resuming one arm only makes the arms differ in "
        f"two ways."
    )


def test_the_prompt_is_the_only_difference_between_the_arms() -> None:
    """...and only by the `/skill-name` prefix, on every attempt.

    Tested through `attempt_prompt`, which is what migrate_codebase calls,
    rather than through `_task_prompt` with arguments a test chose -- the
    old asymmetry was invisible exactly because the call site passed
    `memory_enabled=mem is not None` while any test comparing prompts
    passed the same value to both.

    Warm's prompt used to carry three extra numbered steps and a closing
    note about memory tools: a longer prompt, more instructions and more
    tokens before warm started, on top of the difference being measured.
    """
    feedbacks = [
        None,                                    # attempt 1: no feedback yet
        "E   ImportError: cannot import name 'BaseSettings'",
        "=== 12 passed, 21 failed ===\nE   ValidationError: ...",
        "x" * 20_000,                            # long enough to be trimmed
    ]
    for feedback in feedbacks:
        warm = vibe_agent.attempt_prompt(feedback, skills.SKILL_NAME)
        cold = vibe_agent.attempt_prompt(feedback, None)
        assert warm == f"/{skills.SKILL_NAME} " + cold, (
            f"the arms' prompts differ by more than the skill prefix when "
            f"the previous attempt's feedback is {str(feedback)[:40]!r}")
        if feedback:
            # The grader's verdict reaches BOTH arms, in the same place and
            # the same format. It is the only thing either arm carries from
            # its last attempt, since neither resumes a session.
            assert "The test suite still fails:" in cold


def test_neither_arm_is_told_about_memory_tools_during_an_attempt() -> None:
    """Warm has none during an attempt: the graph is written afterwards,
    from the transcript. Instructions for tools the agent does not have are
    tokens spent on a capability it cannot use, and they are warm-only."""
    for skill in (None, skills.SKILL_NAME):
        prompt = vibe_agent.attempt_prompt("boom", skill)
        assert "memory tools" not in prompt.lower()
        assert "other agents" not in prompt.lower()


# ---- which version the agent is actually on ------------------------------
#
# Three separate things claimed to know the answer and only one of them
# could: the local registry's "newest", the run's banner, and the directory
# on the pod. The first two were what got reported, the third is what the
# model read.


def test_the_workspace_records_the_version_it_installed(ws) -> None:
    ws.install_skill(PACKAGE, name=skills.SKILL_NAME, version=LIVE.version)
    assert ws.installed_skill_version == LIVE.version
    assert ws.installed_skill_sha == _body_sha(LIVE.text)


def test_a_failed_install_does_not_claim_a_version(ws) -> None:
    """Recording the version before verification would leave the run
    reporting a procedure the agent never received."""
    ws.install_skill(PACKAGE, name=skills.SKILL_NAME, version=3)
    ws.drop_on_readback.add("SKILL.md")
    with pytest.raises(RuntimeError):
        ws.install_skill(PACKAGE, name=skills.SKILL_NAME, version=4)
    assert ws.installed_skill_version == 3, (
        "a broken install must leave the last VERIFIED version recorded, "
        "not the one it was trying to put there")


def test_an_empty_package_is_refused_rather_than_uninstalling(ws) -> None:
    """install_skill recreates the tree, so an empty dict is not a no-op --
    it removes the skill and returns the hash of nothing. Warm would run
    with no procedure while the log still named a version.

    This is reachable: `propose` used to return a SkillVersion with no
    files at all.
    """
    ws.install_skill(PACKAGE, name=skills.SKILL_NAME, version=1)
    for bad in ({}, {"source/schema.json": b"{}"}):
        with pytest.raises(ValueError, match="SKILL.md"):
            ws.install_skill(bad, name=skills.SKILL_NAME, version=2)
    assert ws.installed_skill_version == 1
    body = ws.host.files[f"{ws.home}/.vibe/skills/{skills.SKILL_NAME}/SKILL.md"]
    assert PACKAGE["SKILL.md"].decode() in body.decode(), (
        "the real skill is still installed")


def test_the_attempt_loop_reads_the_workspace_not_the_registry() -> None:
    """Pinned by source because the failure is silent and inverted.

    `skills.current()` answers "what is newest on the orchestrator's disk".
    Under --skill-version every attempt was logged as the newest version
    while running the pinned one; with distillation on, an attempt was
    credited to a version that had not reached the pod. The numbers look
    fine either way -- they are just filed under the wrong procedure.
    """
    import inspect

    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert 'getattr(workspace, "installed_skill_version", None)' in src
    assert "_skills.current(skill_name).version" not in src, (
        "the registry pointer is not what the model read")


def test_an_accepted_version_is_installed_before_the_next_attempt() -> None:
    """The self-improvement loop was open at its last inch.

    `propose` writes the new version to the orchestrator's disk and moves
    the live pointer, but the agent reads $VIBE_HOME/skills on the pod,
    which was last written at run setup. So attempt N+1 re-read the SAME
    procedure -- the skill could not improve WITHIN a run, which is exactly
    what a task that cannot be one-shotted is meant to measure.
    """
    import inspect

    import swarm.run as runner

    src = inspect.getsource(runner.main_async)
    assert "if outcome.accepted is not None:" in src
    assert "install_skill(outcome.accepted.files" in src
    assert "version=outcome.accepted.version" in src




def test_the_checklist_compares_against_the_attempts_own_version() -> None:
    """Pinned by source. Comparing against the run's starting version
    printed 'skill v5 reached 0/1 warm agent(s)' for a run whose loop had
    just worked for the first time -- a false negative in the one check
    that exists to catch a skill never reaching the model."""
    import inspect

    import swarm.run as runner

    src = inspect.getsource(runner.main_async)
    assert "C.body_sha(loaded)" in src
    assert "last_version" in src
    assert "expected_body = skills.body_of(live_skill.text)" not in src, (
        "the run's starting version is the wrong baseline once the skill "
        "can advance mid-run")


# ---- keeping the best verified tree --------------------------------------


def test_the_grader_never_sees_the_checkpoint_history(ws) -> None:
    """`.git` is harness bookkeeping. Uploaded into the grading sandbox it
    would be megabytes per attempt and could shadow the real tree."""
    import inspect

    from swarm.agent_workspace import AgentWorkspace

    src = inspect.getsource(AgentWorkspace.tree)
    assert '".git"' in src


def test_nothing_in_the_harness_can_roll_an_attempt_back() -> None:
    """Attempts CONTINUE. They never reset.

    The operator, verbatim: "I never asked you for a rollback. Not once.
    Not ever. They should just continue on each attempt. Never start from
    scratch. Never 'pick some random code you can't test'."

    There was a checkpoint/restore keyed on `tests_passed`. On
    `fixtures/oapi` that number has three values -- 0 (does not import),
    ~310 (imports), 445 (finished) -- so it cannot see how much of the
    migration exists. It fired twice in the 2026-09-18/19 series and both
    times discarded an 8-surface migration (the reference answer scores 3)
    to recover a 40- and a 55-surface tree that happened to import. Both
    hits landed on warm, the arm under test.

    Pinned by source because a rollback is SILENT: the run still produces
    numbers, they are just numbers for a tree nobody chose.
    """
    import inspect

    from swarm.agent_workspace import AgentWorkspace

    for name in ("checkpoint", "restore_best", "init_history"):
        assert not hasattr(AgentWorkspace, name), (
            f"AgentWorkspace.{name} is back. The attempt loop wired the "
            f"last one in through hasattr(), so merely defining these "
            f"re-enables the behaviour.")
    src = inspect.getsource(vibe_agent.migrate_codebase)
    assert "restore_best" not in src.replace("# ", ""), (
        "the attempt loop restores a tree again")
    assert 'emit(\n                        "RESTORED"' not in src
    assert '"RESTORED"' not in src, "the loop emits RESTORED again"


def test_a_broken_tree_is_reported_rather_than_reverted() -> None:
    """The replacement for the rollback is a FACT, not an action.

    `tests_passed` is 0 both when nothing has been migrated and when the
    agent has broken the package with a bad edit. The pre-migration source
    parses -- its failure is a pydantic error raised at import, not a
    SyntaxError -- so a syntax error in the graded tree can only be the
    agent's own. Recording that distinguishes the two; nothing acts on it.
    """
    import inspect

    src = inspect.getsource(vibe_agent.migrate_codebase)
    done = src[src.index('"ATTEMPT_DONE"'):]
    assert "broke_syntax=" in done[:4000], (
        "the failure KIND is no longer recorded, so a broken tree and an "
        "unstarted one are again the same event")


def test_every_attempt_records_why_it_failed() -> None:
    """Cold's failures were undiagnosable.

    The error signature was only written on MEMORY_WRITE, which is
    warm-only, so a run where cold scored 0 on five straight attempts
    carried no record of what went wrong -- and the one number that was
    recorded, `tests_passed=0`, is the number that cannot tell "not
    started" from "broken".
    """
    import inspect

    src = inspect.getsource(vibe_agent.migrate_codebase)
    done = src[src.index('"ATTEMPT_DONE"'):]
    assert "error_signature=signature," in done[:4000]


# ---- the memory path's own artifacts -------------------------------------


def test_the_pod_scripts_come_from_the_repo_and_are_hash_checked() -> None:
    """Nothing hand-placed. This is the 2026-09-18/19 root cause.

    `hook.py` and `reasoning_relay.py` have to be on the pod for warm's
    treatment to exist, and until now NOTHING in this codebase put them
    there: provision_memory.sh chmod'd a hook it assumed present, and
    provision.sh says of the proxy, in as many words, "copied by the
    runner's setup". There was no runner setup. All three were scp'd by
    hand during bring-up and their versions recorded, if at all, as prose
    in NOTES.md.

    The result was unfalsifiable rather than merely broken: the series
    wrote 993 reasoning steps of which 988 held serialised tool input, and
    because the relay's version on that pod was never recorded and the pod
    is gone, which copy ran cannot now be established.
    """
    import inspect

    from swarm import agent_workspace

    sources = set(agent_workspace.host_scripts())
    # The hook and the relay were the two that prompted this check --
    # until 2026-09-19 nothing in the codebase put them on the pod at all,
    # and the version running during a whole series could not afterwards
    # be established. Both are retired with the old memory layer; the
    # check itself is not, because the same silence would hide the next
    # missing file. What remains must still come from the repo and still
    # be hash-verified on arrival.
    assert {"id_fix_proxy.py", "web-tools/server.py"} <= sources
    for name in sources:
        assert (agent_workspace.HARNESS_DIR / name).is_file(), (
            f"{name} is uploaded from harness/ and is not there")
    src = inspect.getsource(agent_workspace.install_host_scripts)
    assert "sha256sum" in src and "does not match" in src, (
        "the upload is not verified, so a stale file on a reused pod is "
        "again indistinguishable from a fresh one")
    # And the runner must actually call it.
    assert "install_host_scripts(host)" in (
        Path("swarm/run.py").read_text())


def test_enabling_memory_registers_the_server_and_no_hook() -> None:
    """Warm gets an MCP server and nothing else.

    This used to assert that `enable_memory` proved the REASONING RELAY
    reached the sidecar before a run started -- a real check, bought with
    a real failure: the relay never errors, so without it every step
    stored its tool input as the agent's thought and the graph became
    searchable by what was typed rather than by why.

    There is no relay, no hook and no sidecar now; Cognee's agents call
    `remember` on its MCP server themselves. What must still be true is
    that enabling memory registers a server and does NOT quietly bring
    back a second writer.
    """
    import inspect

    from swarm.agent_workspace import AgentWorkspace

    from swarm.agent_workspace import _MCP_SERVER_TEMPLATE

    src = inspect.getsource(AgentWorkspace.enable_memory)
    assert "_MCP_SERVER_TEMPLATE" in src
    assert "streamable-http" in _MCP_SERVER_TEMPLATE, (
        "Vibe's `http` transport is its legacy SSE client and a "
        "streamable-HTTP server answers it with 406, registering zero "
        "tools while everything else looks healthy")
    # Matched on CODE, not prose: the docstring names the retired
    # mechanism on purpose, and a test that forbids mentioning it would
    # force the explanation out of the one file that should carry it.
    for gone in ("assert_relay_delivers(", "assert_hook_runs(",
                 'type = "{event}"', "hooks.toml\","):
        assert gone not in src, f"{gone} is back; the second writer returned"

def test_uncounted_reasoning_is_not_reported_as_zero() -> None:
    """`0 w/ reasoning` appeared on six runs where the number was never
    taken, and read as a broken graph. Uncounted is its own answer."""
    from orchestrator import metrics

    arm = metrics.ArmMetrics(arm="warm", steps_ingested=204)
    assert arm.steps_with_reasoning is None
    assert "UNCOUNTED" in metrics._reasoning_cell(arm)
    arm.steps_with_reasoning = 0
    assert "UNCOUNTED" not in metrics._reasoning_cell(arm)
    arm.steps_with_reasoning, arm.thought_fallbacks = 4, 200
    assert "200 fell back to tool input" in metrics._reasoning_cell(arm)


def test_a_memory_failure_cannot_restart_the_attempt_loop() -> None:
    """The agent has already worked and already been graded.

    `_attempt_until_done` retries transient failures by calling
    migrate_codebase again, which restarts its attempt counter at 1. So an
    exception escaping the post-verdict memory block does not cost a
    vector -- it costs the run's accounting. Observed 2026-09-19 run 6:
    warm's counter went 1, 2, 1 and FILE_DONE recorded one attempt where
    three had run, because text-embedding-3-small refused an oversized
    step ("Invalid 'input[75]': maximum input length is 8192 tokens").
    """
    import inspect

    src = inspect.getsource(vibe_agent.migrate_codebase)
    block = src[src.index("A MEMORY FAILURE MUST NOT END"):]
    assert "try:" in block[:1500]
    assert "MEMORY WRITE FAILED" in block, (
        "a swallowed memory failure must still be loud")
    # The guard has to COVER complete_trace, which is what raised. Sliced
    # on the handler's own line, not the words "except Exception" -- those
    # appear in the comment above, which made this assertion pass on an
    # empty slice.
    opened = block.index("\n        try:")
    handler = block.index("\n        except Exception as exc:")
    # The CALL SITE, not the word -- "complete_trace" also appears in the
    # comment above the guard, which made an earlier version of this pass
    # while asserting nothing.
    call = block.index("await mem.complete_trace(")
    assert opened < call < handler
