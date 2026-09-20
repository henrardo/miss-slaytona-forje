"""The remote pieces must satisfy the interfaces migrate_codebase calls.

swarm/run.py no longer has its own attempt loop, its own `tests_passed` or its
own `error_signature` -- it hands `migrate_codebase` a different Workspace and
a different step_memory and lets the tested function do the work. That removes
the drift, and it creates exactly two duck-typed seams, which is what this
pins:

  * AgentWorkspace must satisfy orchestrator.vibe_agent.Workspace
  * RemoteTraceBridge must offer every method migrate_codebase calls on
    step_memory

Both are structural, so a missing method is an AttributeError mid-run rather
than an import error. That is the same failure shape as `ScopedMemory.
search_steps`, which did not exist for a whole run: 24 steps written, 24
errors, 0 injections, indistinguishable from an empty graph.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from orchestrator import run as orchestrator_run
from orchestrator import vibe_agent
from orchestrator.events import EVENT_TYPES
from orchestrator.step_memory import StepMemoryService
from swarm import run as swarm_run
from swarm.agent_workspace import AgentWorkspace
from swarm.run import RemoteTraceBridge

WORKSPACE_METHODS = ("run_vibe", "snapshot", "collect_file_contents",
                     "assistant_turns_total", "tool_calls_total", "steps_used")


@pytest.mark.parametrize("method", WORKSPACE_METHODS)
def test_agent_workspace_satisfies_the_workspace_protocol(method: str) -> None:
    assert hasattr(AgentWorkspace, method), (
        f"AgentWorkspace is missing {method}(), which migrate_codebase calls "
        f"on its workspace"
    )


def test_local_workspace_satisfies_it_too() -> None:
    for method in WORKSPACE_METHODS:
        assert hasattr(vibe_agent.LocalWorkspace, method)


def _step_memory_methods_called() -> set[str]:
    """Every method migrate_codebase calls on `step_memory`."""
    src = inspect.getsource(vibe_agent)
    tree = ast.parse(src)
    called: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "step_memory"):
            called.add(node.func.attr)
    return called


def test_the_sweep_finds_something() -> None:
    """A sweep matching nothing is a green check over an unexamined file."""
    assert _step_memory_methods_called(), "no step_memory calls found"


def test_the_remote_bridge_offers_every_step_memory_method_used() -> None:
    missing = [m for m in _step_memory_methods_called()
               if not hasattr(RemoteTraceBridge, m)]
    assert not missing, (
        f"RemoteTraceBridge is missing {missing}; migrate_codebase calls these "
        f"on step_memory and duck typing makes it an AttributeError mid-run"
    )


def _emitted_event_names(mod) -> set[str]:
    """Every string literal passed as the first argument to an emit() call."""
    tree = ast.parse(inspect.getsource(mod))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn = node.func
        called = (fn.id if isinstance(fn, ast.Name)
                  else fn.attr if isinstance(fn, ast.Attribute) else None)
        if called != "emit":
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.add(first.value)
    return names


@pytest.mark.parametrize("mod", [vibe_agent, swarm_run, orchestrator_run])
def test_every_emitted_event_is_a_declared_event_type(mod) -> None:
    """An undeclared event type is a ValueError raised by the emitter.

    swarm/run.py's transient handler called emit("ATTEMPT_FAILED", ...) to
    record a Daytona failure. EVENT_TYPES does not declare that name, so
    make_event raised ValueError -- from inside the except clause, on the one
    path whose entire job is surviving a Daytona failure. Run 8's cold arm
    died on a 404 with 0 attempts while warm ran the full clock, and the run
    measured nothing.

    Emit sites are literals, so this is checkable without running anything."""
    undeclared = sorted(_emitted_event_names(mod) - EVENT_TYPES)
    assert not undeclared, (
        f"{mod.__name__} emits {undeclared}, which orchestrator.events."
        f"EVENT_TYPES does not declare; make_event raises ValueError on these "
        f"at runtime. Either declare them or do not emit them"
    )


def test_the_emit_sweep_finds_something() -> None:
    """A sweep matching nothing is a green check over an unexamined file."""
    assert _emitted_event_names(vibe_agent), "no emit() literals found"


def test_the_bridge_matches_the_real_services_names() -> None:
    """The bridge stands in for StepMemoryService, so anything it offers under
    a shared name must exist there too -- otherwise the two drift and the
    remote path silently does something the local one does not."""
    for name in ("set_trace", "clear_trace", "set_pending_reasoning",
                 "note_turn", "summary"):
        assert hasattr(RemoteTraceBridge, name)
        assert hasattr(StepMemoryService, name), (
            f"RemoteTraceBridge.{name} has no counterpart on StepMemoryService"
        )


def test_no_function_references_an_undefined_global() -> None:
    """Catch the NameError class statically, before a pod pays for it.

    `_attempt_until_done` read `bridge` as a free variable -- it is a local
    of `main_async` -- and raised NameError on the FIRST real attempt of
    the first pod run, after provisioning, a 113 GB model download and the
    control test had all been paid for.

    The rehearsal cannot catch this: it drives `migrate_codebase` directly
    and never enters `swarm/run.py`'s wrapper at all. Nor can import, nor
    any test that does not execute that exact line with that exact branch
    (warm, past the first attempt). A symbol-table walk catches all of it
    for free, and the same walk would have caught the sidecar's
    `args.retrieval`-out-of-scope bug.
    """
    import builtins
    import importlib
    import symtable
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    modules = {
        "swarm.run": "swarm/run.py",
        "swarm.agent_workspace": "swarm/agent_workspace.py",
        "swarm.sidecar_main": "swarm/sidecar_main.py",
        "orchestrator.vibe_agent": "orchestrator/vibe_agent.py",
        "orchestrator.distill": "orchestrator/distill.py",
        "orchestrator.series": "orchestrator/series.py",
        "orchestrator.metrics": "orchestrator/metrics.py",
    }
    problems: list[str] = []
    for modname, rel in modules.items():
        path = root / rel
        top = symtable.symtable(path.read_text(), str(path), "exec")
        module = importlib.import_module(modname)
        # Module attributes, builtins, and every name bound at module
        # level -- including ones bound inside `if`/`try`, which `dir()`
        # may miss when the branch did not run on this platform.
        known = set(dir(module)) | set(dir(builtins)) | set(top.get_identifiers())

        def walk(table, trail: str) -> None:
            for child in table.get_children():
                name = f"{trail}.{child.get_name()}" if trail else child.get_name()
                for sym in child.get_symbols():
                    if (sym.is_global() and not sym.is_assigned()
                            and sym.get_name() not in known):
                        problems.append(f"{rel}: {name}() -> {sym.get_name()!r}")
                walk(child, name)

        walk(top, "")
    assert not problems, (
        "these read a name that exists in no enclosing scope and will "
        "raise NameError when the line executes:\n  " + "\n  ".join(problems))
