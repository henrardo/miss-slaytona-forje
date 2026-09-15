"""The pydantic.v1 compatibility shim must never score as a migration.

Measured against the real fixture: rewriting every `from pydantic import ...`
to `from pydantic.v1 import ...` and changing nothing else gives **32 of 33
tests passing**. The suite's tests come from the post-migration commit but
never call a v2-only API, so they cannot see the difference. Without the check
these tests cover, the oracle is 97% gameable -- and since shared memory
propagates whatever the success criterion accepts, that diff would be handed
to every other warm agent at similarity 1.00.
"""
from __future__ import annotations

import pytest

from orchestrator.vibe_agent import v1_shim_files


def _fc(**files: str) -> dict[str, bytes]:
    """Keyword names use `__` for `/` and `_py` for `.py`, since neither a
    slash nor a dot is legal in a Python identifier."""
    return {
        name.replace("__", "/").replace("_py", ".py"): body.encode()
        for name, body in files.items()
    }


@pytest.mark.parametrize(
    "line",
    [
        "from pydantic.v1 import BaseSettings as Settings",
        "from pydantic.v1 import BaseModel, EmailStr, root_validator",
        "from pydantic.v1.fields import ModelField",
        "import pydantic.v1",
        "from pydantic import v1",
        "    from pydantic.v1 import EmailStr",  # indented, inside a function
    ],
)
def test_detects_every_shim_spelling(line):
    assert v1_shim_files(_fc(config_py=f"{line}\n")) == ["config.py"]


@pytest.mark.parametrize(
    "line",
    [
        "from pydantic import BaseModel, EmailStr",
        "from pydantic_settings import BaseSettings",
        "from pydantic import field_validator, model_validator",
        "import pydantic",
        "# from pydantic.v1 import BaseSettings  -- removed during migration",
        "V1_NOTE = 'we used to import pydantic.v1 here'",
    ],
)
def test_does_not_flag_a_real_migration(line):
    assert v1_shim_files(_fc(config_py=f"{line}\n")) == []


def test_reports_every_offending_file_sorted():
    contents = _fc(
        **{
            "fastapi_mail__config.py": "from pydantic.v1 import BaseSettings as Settings\n",
            "fastapi_mail__schemas.py": "from pydantic.v1 import BaseModel\n",
            "fastapi_mail__fastmail.py": "from pydantic import EmailStr\n",
        }
    )
    assert v1_shim_files(contents) == [
        "fastapi_mail/config.py",
        "fastapi_mail/schemas.py",
    ]


def test_ignores_non_python_files():
    assert v1_shim_files(_fc(notes_txt="from pydantic.v1 import BaseModel\n")) == []


def test_catches_the_diff_run_28_recorded_as_progress():
    """The exact edit warm agents retrieved at similarity 1.00 in run 28."""
    contents = _fc(
        **{"fastapi_mail__config.py": (
            "from jinja2 import Environment, FileSystemLoader\n"
            "from pydantic.v1 import BaseSettings as Settings\n"
            "from pydantic import DirectoryPath, EmailStr, conint\n"
        )}
    )
    assert v1_shim_files(contents) == ["fastapi_mail/config.py"]
