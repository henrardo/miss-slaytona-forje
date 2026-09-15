#!/usr/bin/env python3
"""Drop neo4j-agent-memory's vector indexes (and optionally all data) so the
client can recreate them at the currently configured embedding dimensions.

Why this is needed: the indexes carry a fixed dimension, set when they were
first created. Change the embedding model and every client -- including the
package's own `neo4j-agent-memory mcp serve` -- refuses to start:

    EmbeddingDimensionMismatchError: Vector index dimension mismatch.
      Index 'entity_embedding_idx': expected 1536, found 384
      ... (all six indexes)

This repo originally created them at 384 (sentence-transformers/
all-MiniLM-L6-v2) and now uses OpenAI text-embedding-3-small at 1536, so the
old indexes have to go. Existing embeddings are not convertible between
models, so `--wipe` (the default) also clears the data they describe; pass
`--keep-data` to drop indexes only, leaving stale vectors that will not match
anything until they are re-embedded.

    python3 scripts/reset_memory_indexes.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from neo4j import AsyncGraphDatabase

from orchestrator.memory import NEO4J_PASSWORD, NEO4J_URI


async def reset(wipe: bool) -> None:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
    try:
        records, _, _ = await driver.execute_query(
            "SHOW INDEXES YIELD name, type WHERE type = 'VECTOR' RETURN name"
        )
        names = [r["name"] for r in records]
        for name in names:
            await driver.execute_query(f"DROP INDEX {name} IF EXISTS")
            print(f"  dropped vector index {name}")
        if not names:
            print("  no vector indexes present")
        if wipe:
            deleted, _, _ = await driver.execute_query(
                "MATCH (n) DETACH DELETE n RETURN count(n) AS n"
            )
            print(f"  deleted {deleted[0]['n']} node(s)")
        print("Indexes will be recreated at the configured dimensions on next connect.")
    finally:
        await driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--keep-data", action="store_true",
        help="Drop indexes only. Leaves embeddings that no longer match the configured model.",
    )
    args = parser.parse_args()
    asyncio.run(reset(wipe=not args.keep_data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
