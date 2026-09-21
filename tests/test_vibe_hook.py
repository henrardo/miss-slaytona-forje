"""Does Vibe actually run our hook, and does what it returns reach the model?

Everything else about the hook can be read off the source. These two cannot:
whether Vibe finds a `hooks.toml` where the harness writes it, and whether
`hook_specific_output.additional_context` ends up in the tool result the model
sees. Both have exactly the failure mode this project keeps having -- the
config is valid, the script is correct, nothing errors, and the model is
handed nothing.

So this runs the REAL vibe binary against the scripted model server, with a
hook that needs no network, and reads the answer out of Vibe's own transcript.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fake_model_server import FakeModelServer, Turn  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
VIBE = REPO_ROOT / "harness" / ".venv" / "bin" / "vibe"
MARKER = "COGNEE-HOOK-MARKER-ba9f2c"

# The shape harness/hooks/cognee_on_failure.py returns, with the recall
# replaced by a constant so this test needs no graph, no key and no network.
STUB_HOOK = f'''#!/usr/bin/env python3
import json, sys
inv = json.load(sys.stdin)
if inv.get("tool_status") == "success":
    raise SystemExit(0)
json.dump({{"hook_specific_output": {{"additional_context": "{MARKER}"}}}},
          sys.stdout)
'''

HOOKS_TOML = '''
[[hooks]]
name = "cognee-on-failure"
type = "post_tool"
match = "bash"
command = "{command}"
timeout = 10.0
'''


def _transcript_text(vibe_home: Path) -> str:
    logs = vibe_home / "logs" / "session"
    return "\n".join(p.read_text(errors="replace")
                     for p in sorted(logs.rglob("*")) if p.is_file())


@pytest.mark.skipif(not VIBE.exists(),
                    reason="needs harness/.venv with mistral-vibe")
def test_a_post_tool_hook_reaches_the_model(tmp_path) -> None:
    """One failing `bash` call, and the hook's text in the next prompt.

    `match = "bash"` is the tool the agents actually use: over the last forty
    runs, 4,767 `bash` calls against 9 `cognee_recall` calls. If a hook on it
    does not fire, the deterministic read does not exist.
    """
    vibe_home = tmp_path / ".vibe"
    vibe_home.mkdir(parents=True)
    hook = vibe_home / "hook.py"
    hook.write_text(STUB_HOOK)
    hook.chmod(0o755)
    (vibe_home / "hooks.toml").write_text(
        HOOKS_TOML.format(command=f"{sys.executable} {hook}"))

    workdir = tmp_path / "repo"
    workdir.mkdir()

    server = FakeModelServer([
        # A command that cannot succeed, so the hook's failure branch runs.
        Turn(text="Let me try the suite.",
             tools=[("bash", {"command": "exit 7"})]),
        Turn(text="Understood."),
    ])
    with server:
        (vibe_home / "config.toml").write_text(
            'active_model = "fake"\n'
            'disabled_tools = ["web_search"]\n'
            "\n[[providers]]\n"
            'name = "fake"\n'
            f'api_base = "{server.base_url}/v1"\n'
            'api_style = "openai"\n'
            'backend = "generic"\n'
            "\n[[models]]\n"
            'name = "fake-model"\n'
            'provider = "fake"\n'
            'alias = "fake"\n'
        )
        env = dict(os.environ)
        env["VIBE_HOME"] = str(vibe_home)
        env["HOME"] = str(tmp_path / "home")
        (tmp_path / "home").mkdir(exist_ok=True)
        proc = subprocess.run(
            [str(VIBE), "--prompt", "Run the test suite.",
             "--auto-approve", "--trust", "--output", "streaming"],
            cwd=workdir, env=env, capture_output=True, text=True,
            timeout=300, stdin=subprocess.DEVNULL)

    combined = (proc.stdout or "") + (proc.stderr or "") + _transcript_text(vibe_home)
    assert MARKER in combined, (
        "Vibe did not deliver the hook's additional_context.\n"
        f"exit={proc.returncode}\n"
        f"stderr tail: {(proc.stderr or '')[-1500:]}")
    # ...and it arrived appended to the tool result, not as a separate
    # message: `additional_context` on a post_tool hook is defined to extend
    # `tool_output_text`, and a model that sees it anywhere else is being
    # handed something this harness did not design.
    assert "exit 7" in combined or "7" in combined


@pytest.mark.skipif(not VIBE.exists(),
                    reason="needs harness/.venv with mistral-vibe")
def test_the_real_hook_is_a_valid_vibe_hook_command(tmp_path) -> None:
    """The shipped hook, run exactly as Vibe runs it, with no graph reachable.

    It must exit 0 and print nothing: an unreachable graph costs the memory,
    never the agent's tool call. This is the branch that fires when the
    reverse tunnel dies mid-run, which has happened.
    """
    hook = REPO_ROOT / "harness" / "hooks" / "cognee_on_failure.py"
    journal = tmp_path / "journal.jsonl"
    invocation = {
        "hook_event_name": "post_tool", "session_id": "s",
        "transcript_path": str(tmp_path), "cwd": str(tmp_path),
        "tool_name": "bash", "tool_call_id": "c1",
        "tool_input": {"command": "python -m pytest -q"},
        "tool_status": "failure", "tool_output": None,
        "tool_output_text": "E   PydanticUserError", "tool_error": "exit 1",
        "duration_ms": 1.0,
    }
    proc = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(invocation),
        capture_output=True, text=True, timeout=60,
        env={**os.environ,
             # A port nothing is listening on.
             "COGNEE_API": "http://127.0.0.1:1",
             "COGNEE_DATASET": "nowhere",
             "COGNEE_NODE_SET_FAILED": "nowhere-failed",
             "COGNEE_NODE_SET_WORKED": "nowhere-worked",
             "COGNEE_JOURNAL": str(journal),
             "COGNEE_HOOK_TIMEOUT": "1"})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", (
        "with no graph the hook must add nothing, not an error message")
    # It still says it ran, so a run where the tunnel was down is diagnosable
    # rather than indistinguishable from a run where nothing failed.
    entry = json.loads(journal.read_text().splitlines()[-1])
    assert entry["status"] == "failure" and entry["recalled"] == 0


def test_a_successful_command_costs_nothing_but_a_journal_line(tmp_path) -> None:
    """The hook runs on every `bash` call and most of them succeed. Warm
    paying a recall cold does not, per successful command, is latency the
    shared deadline charges to the arm under test."""
    hook = REPO_ROOT / "harness" / "hooks" / "cognee_on_failure.py"
    journal = tmp_path / "journal.jsonl"
    invocation = {
        "hook_event_name": "post_tool", "session_id": "s",
        "transcript_path": str(tmp_path), "cwd": str(tmp_path),
        "tool_name": "bash", "tool_call_id": "c2",
        "tool_input": {"command": "ls"}, "tool_status": "success",
        "tool_output": None, "tool_output_text": "a b c",
        "tool_error": None, "duration_ms": 1.0,
    }
    proc = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(invocation),
        capture_output=True, text=True, timeout=60,
        env={**os.environ,
             # Unreachable on purpose: a successful call must not dial it.
             "COGNEE_API": "http://127.0.0.1:1",
             "COGNEE_DATASET": "nowhere",
             "COGNEE_NODE_SET_FAILED": "nowhere-failed",
             "COGNEE_JOURNAL": str(journal),
             "COGNEE_HOOK_TIMEOUT": "30"})
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    entry = json.loads(journal.read_text().splitlines()[-1])
    assert entry == {"tool": "bash", "status": "success",
                     "input": {"command": "ls"}, "recalled": 0}


def test_the_harness_writes_the_hook_config_vibe_actually_reads() -> None:
    """The template and the install path, pinned together.

    `enable_hook` writes `$HOME/.vibe/hooks.toml`, which is where Vibe looks;
    the same code used to DELETE that file, and a template that drifts to
    `[[hook]]` or `type = "posttool"` parses to zero hooks with no error.
    """
    import tomllib

    from swarm.agent_workspace import _HOOKS_TEMPLATE

    parsed = tomllib.loads(_HOOKS_TEMPLATE.format(command="/bin/true"))
    assert len(parsed["hooks"]) == 1
    hook = parsed["hooks"][0]
    assert hook["type"] == "post_tool"
    assert hook["match"] == "bash"
    assert hook["command"] == "/bin/true"
    # Vibe's own model has to accept it, including the enum spelling.
    sys.path.insert(0, str(REPO_ROOT / "harness" / ".venv" / "lib"))
    src = (REPO_ROOT / "swarm" / "agent_workspace.py").read_text()
    assert 'f"{vibe_home}/hooks.toml"' in src, (
        "the config must land in $VIBE_HOME, where Vibe looks for it")
    assert "rm -f" not in src.split("def enable_hook")[1].split("def ")[0], (
        "enable_hook must not delete the file it just wrote")
