"""Cheap structural checks on the orchestrator modules.

These exist because scripted edits to these files have twice silently broken
them in ways that only surface mid-run, minutes and a GPU-hour later:

* a regex splice replaced up to the next `def `, which matched the `def ` inside
  `async def migrate_codebase(` and dropped the `async` -- turning every
  `await` in the function body into a SyntaxError;
* `ScopedMemory.add_step()` drifted from its call site and took out an entire
  warm swarm (see test_scoped_memory_signatures.py).

Importing a module is enough to catch a SyntaxError, and asserting the
coroutine-ness of the functions the event loop awaits is enough to catch the
other. Both run in milliseconds.
"""
from __future__ import annotations

import importlib
import inspect

import pytest

MODULES = [
    "orchestrator.run",
    "orchestrator.vibe_agent",
    "orchestrator.memory",
    "orchestrator.sandbox",
    "orchestrator.events",
    "orchestrator.manifest",
    "orchestrator.snapshot",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize(
    ("module", "func"),
    [
        ("orchestrator.vibe_agent", "migrate_codebase"),
        ("orchestrator.vibe_agent", "_run_vibe"),
        # _replay_session_messages is gone: the agents write their own steps
        # through Vibe's post_tool hook now (orchestrator/step_memory.py), so
        # there is no transcript replay to await.
        ("orchestrator.step_memory", "StepMemoryService.handle"),
        ("orchestrator.run", "agent_worker"),
        ("orchestrator.run", "main_async"),
        ("orchestrator.memory", "graph_counts"),
        ("orchestrator.memory", "reset_graph"),
    ],
)
def test_awaited_functions_are_coroutines(module, func):
    # Dotted names so a method on a class can be named as well as a
    # module-level function (StepMemoryService.handle is awaited per tool call).
    fn = importlib.import_module(module)
    for part in func.split("."):
        fn = getattr(fn, part)
    assert inspect.iscoroutinefunction(fn), (
        f"{module}.{func} is awaited by the run loop but is not a coroutine "
        f"function. If an `async` was dropped, every `await` in its body is a "
        f"SyntaxError and the run dies on the first call."
    )


def test_localize_sandbox_paths_makes_paths_relative():
    """Long absolute paths are a typo surface; 11 of run 38's 66 failed edits
    were 'File does not exist'."""
    from pathlib import Path

    from orchestrator.vibe_agent import _localize_sandbox_paths

    out = _localize_sandbox_paths(
        "conftest '/repo/tests/conftest.py'\n/repo/fastapi_mail/config.py:5", Path("/x/y")
    )
    assert "/repo/" not in out
    assert "tests/conftest.py" in out
    assert "fastapi_mail/config.py" in out
