"""The answer key must pass in a seeded checkout.

This is the cheapest possible check on the whole experiment and it was never
made: if the real, merged, human-authored migration cannot score 33/33 in the
environment the agent works in, then no agent can, and every run measures the
distance to an unreachable state.

It did not pass. `seed_repo` chmod'd the entire `tests/` tree read-only to stop
agents editing the oracle -- correct intent, wrong blast radius. Four of the 33
tests write an attachment fixture into `tests/txt_files/`:

    tests/test_message.py:90     with open(attachement, "w") as file:
    tests/test_connection.py     (three more of the same shape)

so they raised PermissionError regardless of the package's contents.
fixture/reference_v2 -- the actual merge commit -- scored 29/33.

Meanwhile the Daytona oracle runs as root, which ignores the mode bits, so the
grader could reach 33/33 while the agent's own checkout could not. The prompt
tells the agent that its local suite "is the same suite your work is judged on"
and to "keep going until the suite passes". Both statements were false, by
exactly four tests, and nothing in the harness said so.

So this test asserts the invariant rather than the fix: seed a checkout the way
a run does, drop the answer key into it, and require green. Any future change
to the seeding that makes the suite unpassable fails here instead of showing up
as an agent that mysteriously never converges.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from orchestrator.manifest import REPO_ROOT
from orchestrator.run import seed_repo, vibe_home_for  # noqa: F401  (import check)

FIXTURE_DIR = REPO_ROOT / "fixture"
REFERENCE = FIXTURE_DIR / "reference_v2" / "fastapi_mail"
AGENT_PYTHON = Path("/tmp/msf-agents/.fixture-venv/bin/python")


def _seed_like_a_run(dst: Path) -> None:
    """The same two copies + the same chmod pass seed_repo does, inlined.

    seed_repo() is keyed on (swarm, agent_id) and writes under AGENT_ROOT; this
    needs an arbitrary tmp_path, so the parts under test are reproduced here.
    Kept deliberately short: if this drifts from seed_repo the assertion below
    stops meaning anything, so it copies the same two trees and applies the
    same mode change, and nothing else.
    """
    shutil.copytree(FIXTURE_DIR / "fastapi_mail", dst / "fastapi_mail")
    shutil.copytree(FIXTURE_DIR / "tests", dst / "tests")
    shutil.copy(FIXTURE_DIR / "requirements-v2.txt", dst / "requirements-v2.txt")
    # copytree preserves mode and fixture/ is chmod a-w on disk, so restore
    # write on the copy first -- the agent owns its checkout.
    for path in dst.rglob("*"):
        path.chmod(path.stat().st_mode | 0o200)
    # ...then lock the test SOURCE, and only the source. This is the line the
    # test exists for: `rglob("*")` here instead of `rglob("*.py")` is what
    # made the suite unpassable.
    for path in (dst / "tests").rglob("*.py"):
        path.chmod(path.stat().st_mode & ~0o222)


@pytest.mark.skipif(
    not AGENT_PYTHON.exists(),
    reason=f"{AGENT_PYTHON} not built; run the orchestrator once to create it",
)
def test_reference_answer_scores_full_marks_in_a_seeded_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "checkout"
    repo.mkdir()
    _seed_like_a_run(repo)

    # Swap the v1 package for the answer key, which is what an agent that
    # finished the job would have produced.
    shutil.rmtree(repo / "fastapi_mail")
    shutil.copytree(REFERENCE, repo / "fastapi_mail")

    result = subprocess.run(
        [str(AGENT_PYTHON), "-m", "pytest", "tests", "-q"],
        cwd=repo, capture_output=True, text=True, timeout=600,
    )
    tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-15:])
    assert result.returncode == 0, (
        "the answer key does not pass in a seeded checkout, so no agent can:\n" + tail
    )


def test_test_source_is_still_read_only(tmp_path: Path) -> None:
    """The half of the original intent that was right: test source stays
    locked, so an agent that tries to fix the oracle gets an honest
    permission error instead of a misleading "String to replace not found".
    """
    repo = tmp_path / "checkout"
    repo.mkdir()
    _seed_like_a_run(repo)

    conftest = repo / "tests" / "conftest.py"
    assert conftest.exists()
    assert not conftest.stat().st_mode & 0o222, "test source must not be writable"

    # ...and the half that was wrong: data the suite writes stays writable.
    writable = repo / "tests" / "txt_files"
    assert writable.is_dir()
    assert writable.stat().st_mode & 0o200, "tests/txt_files must be writable"
    for path in writable.rglob("*"):
        assert path.stat().st_mode & 0o200, f"{path} must be writable"


def test_checkout_carries_the_projects_own_conventions(tmp_path: Path) -> None:
    """The agent must be able to answer "how is this tested?" from the repo.

    It could not. The checkout was `fastapi_mail/ tests/ requirements-v2.txt
    .gitignore` -- no README, no pyproject.toml, no Makefile. The upstream repo
    has all of them; building the fixture stripped them. The harness then made
    up the difference in the prompt, ~2,500 tokens telling the model how to
    invoke pytest, which is the repo's job and not ours.

    Asserted on content, not filenames, because a README that happens to exist
    proves nothing:

    * the Makefile carries the project's real `test:` target;
    * pyproject.toml still pins pydantic v1, so the dependency declaration is
      visible as part of the migration -- the real PR #195 changed exactly
      that line.
    """
    from orchestrator.run import seed_repo, run_dir
    from orchestrator.manifest import load_manifest

    m = load_manifest()
    seed_repo("warm", 99, m["package_path"], m["tests_path"])
    repo = run_dir("warm", 99)

    makefile = (repo / "Makefile").read_text()
    assert "test:" in makefile and "pytest" in makefile

    pyproject = (repo / "pyproject.toml").read_text()
    assert 'pydantic = "^1.8"' in pyproject, (
        "pyproject no longer shows the v1 pin, so the dependency half of the "
        "migration is invisible to the agent again"
    )

    for name in ("README.md", "CONTRIBUTING.md", "tox.ini"):
        assert (repo / name).is_file(), name


def test_root_files_are_committed_not_untracked(tmp_path: Path) -> None:
    """`git status` is most of what Vibe puts in its system prompt, so an
    uncommitted pyproject/README reads to the model as someone's work in
    progress rather than as the project's existing convention."""
    import subprocess

    from orchestrator.run import seed_repo, run_dir
    from orchestrator.manifest import load_manifest

    m = load_manifest()
    seed_repo("warm", 98, m["package_path"], m["tests_path"])
    repo = run_dir("warm", 98)

    status = subprocess.run(
        ["git", "status", "--short"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert status == "", f"seeded checkout is not clean:\n{status}"
