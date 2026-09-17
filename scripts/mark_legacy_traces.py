#!/usr/bin/env python3
"""Stamp traces written under the old success semantics so they can be excluded.

`success` used to mean `passed OR advanced` (vibe_agent.py, `resolved`), so a
trace could carry success=True under a summary reading "The suite still fails
with the same first error" -- present in the live graph at tests_passed=32.
`_render` shows that flag to the next warm agent, so memory reported failures
as successes.

Traces written from now on carry metrics.outcome_schema = 2, where success
means the full suite passed. This marks everything already in the graph as
schema 1. Nothing is deleted: the reasoning in those traces is still the only
record of what those agents did, and the distiller may want it -- it just has
to know which definition of "success" it is reading.

    python3 scripts/mark_legacy_traces.py [--apply]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j_agent_memory import MemoryClient  # noqa: E402

from orchestrator.memory import build_settings  # noqa: E402


async def main(apply: bool) -> int:
    async with MemoryClient(build_settings()) as c:
        rows = await c.query.cypher(
            "MATCH (t:ReasoningTrace) RETURN toString(t.id) AS id, "
            "t.metrics_json AS m, t.success AS ok")
        legacy = []
        for r in rows:
            try:
                m = json.loads(r["m"]) if r["m"] else {}
            except (json.JSONDecodeError, TypeError):
                m = {}
            if m.get("outcome_schema") is None:
                m["outcome_schema"] = 1.0
                legacy.append((r["id"], m, r["ok"], m.get("tests_passed")))
        print(f"{len(rows)} trace(s); {len(legacy)} without outcome_schema")
        suspect = [x for x in legacy if x[2] and (x[3] or 0) < 33]
        print(f"of those, {len(suspect)} have success=true with tests_passed<33 "
              f"-- the ones the old flag actively misreported")
        if not apply:
            print("\ndry run; pass --apply to write outcome_schema=1")
            return 0
        # c.query.cypher refuses writes by design ("Only read-only Cypher
        # queries are allowed"), so the write goes through the graph client.
        for tid, m, _, _ in legacy:
            await c.graph.execute_write(
                "MATCH (t:ReasoningTrace) WHERE toString(t.id) = $id "
                "SET t.metrics_json = $m",
                {"id": tid, "m": json.dumps(m)})
        print(f"stamped {len(legacy)} trace(s) with outcome_schema=1")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--apply" in sys.argv)))
