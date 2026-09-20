"""The remote pieces must satisfy the interfaces migrate_codebase calls.

swarm/run.py no longer has its own attempt loop, its own `tests_passed` or its
own `error_signature` -- it hands `migrate_codebase` a different Workspace and
a different step_memory and lets the tested function do the work. That removes
the drift, and it creates exactly two duck-typed seams, which is what this
pins:

  * AgentWorkspace must satisfy orchestrator.vibe_agent.Workspace
  * CogneeMemory must offer every method migrate_codebase calls on `mem`

Both are structural, so a missing method is an AttributeError mid-run rather
than an import error. That is the same failure shape as `ScopedMemory.
search_steps`, which did not exist for a whole run: 24 steps written, 24
errors, 0 injections, indistinguishable from an empty graph -- and as
`mem.complete_trace`, which outlived the object that had it and sat in the
one handler that runs when a run is already going wrong.

THE SECOND SEAM MOVED. It used to be `RemoteTraceBridge` against
`step_memory`: a sidecar on the pod that the post_tool hook wrote through.
There is no sidecar, no hook and no `step_memory` parameter; what warm is
handed now is a CogneeMemory, and the loop calls it for the procedure, for
what Cognee retrieved, and to bridge the session traces into the graph.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from orchestrator import run as orchestrator_run
from orchestrator import vibe_agent
from orchestrator.events import EVENT_TYPES
from swarm import run as swarm_run
from swarm.agent_workspace import AgentWorkspace
from orchestrator.cognee_layer import CogneeMemory

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


def _methods_called_on(name: str) -> set[str]:
    """Every method migrate_codebase calls on the local named `name`."""
    src = inspect.getsource(vibe_agent)
    tree = ast.parse(src)
    called: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == name):
            called.add(node.func.attr)
    return called


def test_the_sweep_finds_something() -> None:
    """A sweep matching nothing is a green check over an unexamined file."""
    assert _methods_called_on("mem"), "no mem.* calls found in the attempt loop"


def test_the_memory_offers_every_method_the_loop_calls() -> None:
    missing = [m for m in _methods_called_on("mem")
               if not hasattr(CogneeMemory, m)]
    assert not missing, (
        f"CogneeMemory is missing {missing}; migrate_codebase calls these on "
        f"`mem` and duck typing makes it an AttributeError mid-run -- which "
        f"is exactly how two dead `mem.complete_trace` calls survived a "
        f"migration in the handlers that run when a run is already failing"
    )


def test_the_step_memory_seam_is_gone() -> None:
    """Nothing writes the graph from the pod any more, so nothing should be
    calling a second writer.

    A `step_memory` reference that comes back is either the hook returning
    or a merge artefact; either way it is a second writer to keep in step
    with the first, and keeping them in step is what produced 993 steps of
    which 988 held serialised tool input."""
    assert not _methods_called_on("step_memory")
    assert "step_memory" not in inspect.signature(
        vibe_agent.migrate_codebase).parameters


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


def test_the_memory_answers_both_halves_of_the_treatment() -> None:
    """Warm's treatment is a mix, and each half has a named method.

    `wrap_attempt`/`retrieved` are the deterministic half -- Cognee's own
    `agent_memory` decorator around the attempt, and the text it
    retrieved. `procedure` is the skill the harness puts in the prompt.
    `improve` is the bridge from session memory into the graph, without
    which every trace written is visible to its own session and to
    nothing else. The MCP server is the voluntary half and needs no
    method here: the agent calls it itself.
    """
    for name in ("procedure", "wrap_attempt", "retrieved", "context",
                 "improve"):
        assert hasattr(CogneeMemory, name), name


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
        "orchestrator.vibe_agent": "orchestrator/vibe_agent.py",
        "orchestrator.cognee_layer": "orchestrator/cognee_layer.py",
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


def test_the_agents_memory_server_is_the_harnesss_by_default() -> None:
    """MEASURED 2026-09-21: a cognee process keeps its users, datasets and
    vector index in LOCAL SQLite/LanceDB and only the graph is remote. A
    second process sharing the same Aura reported a different default
    user, listed only its own datasets, and answered
    `recall(datasets=["msf-..."])` with DatasetNotFoundError.

    So a cognee-mcp on the pod is a second, EMPTY memory writing into the
    same Neo4j, and a warm agent talking to it retrieves nothing all run
    while every other check stays green -- this project's signature
    failure. The server runs on the harness and reaches the pod through
    `ssh -R`; the pod-side arrangement survives only behind an explicit
    flag.

    Asserted on the source because the alternative needs a pod, and the
    rehearsal cannot reach `main()` at all."""
    import inspect

    src = inspect.getsource(swarm_run.main)
    assert "local_cognee_mcp" in src and "reverse_tunnel" in src
    assert "args.cognee_on_pod" in src, (
        "the harness-side server must be the DEFAULT; the pod-side one is "
        "the flagged exception")
    # And it has to outlive the attempts, not just the preflight: entered
    # in main(), before the loop starts. (Matched on the CALL, not the
    # name -- a comment two lines above says "BEFORE asyncio.run".)
    assert src.index("local_cognee_mcp") < src.index("rc = asyncio.run(")


def test_preflight_proves_the_two_memories_are_one() -> None:
    """Every cheaper check passes on two separate memories sharing one
    Neo4j: the server answers, the tools register, the graph has nodes.
    Only a write on one side and a read on the other tells them apart, so
    that probe is the gate -- verified live, both ways: it passes against
    a shared-store server and fails against a pod-like one."""
    import inspect

    src = inspect.getsource(swarm_run.main_async)
    assert "assert_one_memory" in src
    probe = inspect.getsource(swarm_run.assert_one_memory)
    assert "cognee.remember" in probe and "call_tool" in probe, (
        "the probe must WRITE through the harness and READ through the "
        "agents' own server; anything else re-checks one side twice")
