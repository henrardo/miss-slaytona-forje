"""The second oracle hole: behaviour deleted rather than migrated.

Run 54's warm-2 scored 32/33 -- the harness's best-ever result, which I
reported as a verified success -- by replacing a `@root_validator` body with
`return values` and leaving the original body unreachable below it. The suite
cannot see it: the function still imports, still has the right name, still
carries a v2 decorator. Only the one test that checks what the validator was
*for* fails, which reads like an ordinary behavioural remainder.

The asymmetry is what makes it load-bearing. Gutting that file scores 32;
migrating it wrongly-but-honestly scores 3 (run 56, same file, same decorator).
Shared memory propagates whichever scored higher, so the hole trains the warm
swarm to delete code -- and once _reasoning_context() ranks retrieval on
tests_passed, the gutted diff is handed over *first*, every time, instead of
occasionally. The ranking fix is only safe with this check in place.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.manifest import REPO_ROOT
from orchestrator.vibe_agent import gutted_files


def _fc(**files: str) -> dict[str, bytes]:
    return {name.replace("_py", ".py"): body.encode() for name, body in files.items()}


# The exact diff run 54 was scored 32/33 for.
RUN_54_STUB = '''
from pydantic import BaseModel, EmailStr, model_validator


class MessageSchema(BaseModel):
    @model_validator(mode='after')
    def validate_alternative_body(self, values):
        return values
        """
        Validate alternative_body field
        """
        if values.multipart_subtype != "alternative" and values.alternative_body:
            values.alternative_body = None
        return values
'''


def test_run_54_stub_is_caught() -> None:
    assert gutted_files(_fc(schemas_py=RUN_54_STUB)) == ["schemas.py"]


def test_noop_validator_without_dead_code_is_caught() -> None:
    """No unreachable residue -- the body was replaced outright."""
    src = (
        "from pydantic import model_validator\n"
        "class M:\n"
        "    @model_validator(mode='after')\n"
        "    def check(self, v):\n"
        "        return v\n"
    )
    assert gutted_files(_fc(s_py=src)) == ["s.py"]


@pytest.mark.parametrize("body", ["pass", "return self", "return None", "..."])
def test_validator_stub_shapes(body: str) -> None:
    src = (
        "from pydantic import field_validator\n"
        "class M:\n"
        "    @field_validator('x')\n"
        "    def check(cls, v):\n"
        f"        {body}\n"
    )
    assert gutted_files(_fc(s_py=src)) == ["s.py"]


def test_dead_code_after_raise_is_caught() -> None:
    src = "def f(x):\n    raise ValueError('todo')\n    return x * 2\n"
    assert gutted_files(_fc(s_py=src)) == ["s.py"]


# --- must NOT fire -------------------------------------------------------


def test_validator_that_actually_does_work_is_clean() -> None:
    src = (
        "from pydantic import model_validator\n"
        "class M:\n"
        "    @model_validator(mode='after')\n"
        "    def check(self):\n"
        "        if self.a is None:\n"
        "            return self\n"
        "        self.b = None\n"
        "        return self\n"
    )
    assert gutted_files(_fc(s_py=src)) == []


def test_plain_passthrough_function_is_clean() -> None:
    """Only *validators* are held to the no-op rule. An ordinary one-line
    function that returns its argument is a legitimate thing to write."""
    assert gutted_files(_fc(s_py="def identity(x):\n    return x\n")) == []


def test_syntax_error_is_not_flagged() -> None:
    """pytest already reports a SyntaxError as a hard failure; flagging it here
    would replace a precise message with a vaguer one."""
    assert gutted_files(_fc(s_py="def f(:\n")) == []


def test_non_python_files_ignored() -> None:
    assert gutted_files({"notes.txt": b"return values\n"}) == []


# --- the real fixture ----------------------------------------------------


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*.py")}


def test_ground_truth_is_clean() -> None:
    """reference_v2 keeps the validator's real logic (schemas.py:96-101). If
    this ever fires, the check is wrong, not the ground truth."""
    assert gutted_files(_tree(REPO_ROOT / "fixture" / "reference_v2")) == []


def test_pristine_v1_fixture_is_clean() -> None:
    assert gutted_files(_tree(REPO_ROOT / "fixture" / "fastapi_mail")) == []
