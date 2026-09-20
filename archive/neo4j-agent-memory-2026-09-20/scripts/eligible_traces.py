#!/usr/bin/env python3
"""How many traces may feed distillation, and why the rest may not.

Three filters, each for a fault already present in the graph:
  * prov_model      -- 109 of 187 steps were written by Qwen3-14B
  * prov_writable   -- seven runs gave agents a chmod a-w checkout
  * outcome_schema  -- `success` used to mean "passed OR advanced"

    python3 scripts/eligible_traces.py [--model mistralai/Mistral-Small-4-119B-2603]
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

from orchestrator.memory import ScopedMemory, build_settings  # noqa: E402

MODEL = "mistralai/Mistral-Small-4-119B-2603"


async def main(model: str) -> int:
    async with MemoryClient(build_settings()) as c:
        rows = await c.query.cypher(
            "MATCH (t:ReasoningTrace) OPTIONAL MATCH (t)-[:HAS_STEP]->(s:ReasoningStep) "
            "WITH t, count(s) AS steps, "
            "  sum(CASE WHEN s.thought IS NOT NULL AND NOT s.thought STARTS WITH '{' "
            "      THEN 1 ELSE 0 END) AS real "
            "RETURN t.user_identifier AS who, t.prov_model AS model, "
            "  t.prov_writable AS writable, t.metrics_json AS m, steps, real")
        total = len(rows)
        counts = {"total": total, "has_provenance": 0, "right_model": 0,
                  "writable": 0, "schema2": 0, "eligible": 0,
                  "eligible_with_reasoning": 0}
        for r in rows:
            try:
                m = json.loads(r["m"]) if r["m"] else {}
            except (json.JSONDecodeError, TypeError):
                m = {}
            if r["model"] is not None:
                counts["has_provenance"] += 1
            if r["model"] == model:
                counts["right_model"] += 1
            if r["writable"] is True:
                counts["writable"] += 1
            if m.get("outcome_schema", 0.0) >= 2.0:
                counts["schema2"] += 1
            if (r["model"] == model and r["writable"] is True
                    and m.get("outcome_schema", 0.0) >= 2.0):
                counts["eligible"] += 1
                if r["real"] > 0:
                    counts["eligible_with_reasoning"] += 1
        for k, v in counts.items():
            print(f"  {k:26s} {v}")
        if counts["eligible"] == 0:
            print("\nNO ELIGIBLE TRACES. Distillation has nothing to learn from "
                  "until a run completes on the current harness.")
        return 0


if __name__ == "__main__":
    m = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else MODEL
    raise SystemExit(asyncio.run(main(m)))
