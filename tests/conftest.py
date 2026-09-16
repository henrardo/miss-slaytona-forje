"""Load .env before any orchestrator module is imported.

orchestrator.memory deliberately has no default NEO4J_URI/NEO4J_PASSWORD: a
default silently pointed the orchestrator at a local Neo4j while the agents'
MCP server used the hosted one, so the two halves of a run read different
graphs and the run log described the wrong server. See the comment there.

run.py calls load_dotenv() before its own imports. pytest is the other real
entry point, so it has to do the same thing -- and here, not inside individual
tests, because the variables are read at module import time and collection
imports every test module first.
"""
from dotenv import load_dotenv

load_dotenv()
