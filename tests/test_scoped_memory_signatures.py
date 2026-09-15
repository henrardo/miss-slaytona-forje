"""ScopedMemory is a thin pass-through over neo4j-agent-memory. These tests
assert it has not drifted from the methods it wraps.

Run 27 lost its entire warm swarm to exactly this drift: vibe_agent.py started
passing `observation=` to ScopedMemory.add_step(), the wrapper did not declare
it, and every warm agent raised

    TypeError: ScopedMemory.add_step() got an unexpected keyword argument
    'observation'

*after* completing its Vibe turn. The orchestrator's retry loop treated that
like a transient failure, so the run produced 140 LLM calls, 0 completed
attempts, and a token ratio that measured the bug rather than memory.

A signature comparison is enough to catch the whole class, and it needs no
Neo4j: the failure is a mismatch between two Python signatures, and that is
exactly what is checked here.
"""
from __future__ import annotations

import inspect

import pytest
from neo4j_agent_memory.memory.reasoning import ReasoningMemory

from orchestrator.memory import ScopedMemory


def _kwargs(func) -> set[str]:
    """Keyword-acceptable parameter names, ignoring `self` and **kwargs."""
    return {
        name
        for name, p in inspect.signature(func).parameters.items()
        if name != "self"
        and p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
    }


@pytest.mark.parametrize(
    ("wrapper_name", "wrapped", "required"),
    [
        # The thought-action-observation triple the reasoning layer is built
        # around. `observation` is the one that was missing.
        ("add_step", ReasoningMemory.add_step,
         {"thought", "action", "observation", "generate_embedding"}),
        ("complete_trace", ReasoningMemory.complete_trace,
         {"outcome", "success", "generate_step_embeddings"}),
    ],
)
def test_wrapper_accepts_what_the_package_accepts(wrapper_name, wrapped, required):
    wrapper_kwargs = _kwargs(getattr(ScopedMemory, wrapper_name))
    missing = required - wrapper_kwargs
    assert not missing, (
        f"ScopedMemory.{wrapper_name}() does not accept {sorted(missing)}, "
        f"which {wrapped.__qualname__}() does. Calling it with those raises "
        f"TypeError at runtime, inside an agent's retry loop, where it looks "
        f"like a transient failure."
    )


def test_add_step_call_sites_are_satisfied():
    """Every keyword vibe_agent.py actually passes must be accepted."""
    passed_by_caller = {"thought", "action", "observation", "generate_embedding"}
    assert passed_by_caller <= _kwargs(ScopedMemory.add_step)
