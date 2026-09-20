#!/usr/bin/env bash
# THE FALLBACK TOPOLOGY, not the default one. Read this before using it.
#
# A cognee process keeps its users, datasets and vector index in LOCAL
# SQLite and LanceDB; only the GRAPH is remote. So a cognee-mcp started
# here is NOT a window onto the harness's memory -- it is a second, empty
# memory that happens to write into the same Neo4j. Measured 2026-09-21
# with a fresh store against the same Aura:
#
#     default user id: ca938241-...      (its own, not the harness's)
#     datasets visible: ['podprobe']     (its own; the harness's were not)
#     recall(datasets=["msf-..."]) -> DatasetNotFoundError,
#         "Dataset names resolve only among the datasets you own"
#
# A warm agent on this server calls `cognee_recall` and gets nothing, all
# run, while the config, the server and every log line look healthy.
#
# THE DEFAULT IS NOW THE OTHER WAY ROUND: swarm/run.py runs cognee-mcp on
# the harness, beside the orchestrator and sharing its stores, and
# reverse-tunnels it onto this host's 127.0.0.1:8811. The agent's URL is
# unchanged and the Neo4j password never reaches the pod at all. Use this
# script only with `--cognee-on-pod`, and only to measure what the split
# costs -- the preflight will tell you plainly that the two memories are
# not one.
#
# The memory layer on the swarm host: Cognee, over loopback HTTP.
#
# Replaces provision_memory.sh (neo4j-agent-memory), archived under
# archive/neo4j-agent-memory-2026-09-20/. Runs ON the pod, as root.
# Idempotent.
#
# The security properties are carried over unchanged, because they were
# right and they were expensive to get right:
#
#   /opt/swarm/          0711 root -- TRAVERSABLE, not listable. An agent
#                                     reaches a path it is told about and
#                                     cannot enumerate the directory.
#   /opt/swarm/cognee/   0700 root -- the venv. Credentials live here at
#                                     runtime and no agent can read them.
#   /opt/swarm/env       0600 root -- the one credential file.
#
# NO STDIO SHIM, same reasoning as before: a `#!` shim must be READABLE to
# be executed, so a shim carrying a password hands it to any agent that
# runs `cat`. The server runs ONCE, as root, over loopback HTTP, and
# agents are handed a URL. Vibe supports it (`mcp add --transport http
# --url`) and so does cognee (`--transport http`).
#
# ITS OWN VENV, also unchanged: mistral-vibe pins mcp==1.28.1 and
# installing a second MCP stack beside it removed EVERY server from the
# model's tool list once already. See NOTES-hard-won.md.
set -euo pipefail

COGNEE_DIR=/opt/swarm/cognee
PORT="${1:-8811}"

: "${NEO4J_URI:?}" "${NEO4J_PASSWORD:?}" "${OPENAI_API_KEY:?}"

mkdir -p "$COGNEE_DIR"
chmod 711 /opt/swarm
chmod 700 "$COGNEE_DIR"

echo "=== cognee venv at $COGNEE_DIR ==="
if [ ! -x "$COGNEE_DIR/bin/cognee-mcp" ]; then
    python3 -m venv "$COGNEE_DIR"
    "$COGNEE_DIR/bin/pip" install -q --upgrade pip
    "$COGNEE_DIR/bin/pip" install -q "cognee[neo4j]==1.6.0" cognee-mcp
fi
"$COGNEE_DIR/bin/python" -c "import cognee; print('  cognee', cognee.get_cognee_version())"

# Cognee reads its configuration from the environment at import time and
# runs relational migrations on first import, so everything has to be set
# before the server starts -- not after.
#
# GRAPH only is remote. Vector (LanceDB) and relational (SQLite) are local
# files under the venv, which is 0700 root, so they are unreadable by
# agents by construction. Stating it because "the memory is in Aura" is
# false and a reader will otherwise assume it.
export GRAPH_DATABASE_PROVIDER=neo4j
export GRAPH_DATABASE_URL="$NEO4J_URI"
export GRAPH_DATABASE_NAME="${NEO4J_DATABASE:-neo4j}"
export GRAPH_DATABASE_USERNAME="${NEO4J_USERNAME:-neo4j}"
export GRAPH_DATABASE_PASSWORD="$NEO4J_PASSWORD"
export LLM_API_KEY="$OPENAI_API_KEY"
# Single-operator harness. Left on, every call needs a principal and the
# permission system becomes a confound in a memory experiment.
export ENABLE_BACKEND_ACCESS_CONTROL=false

echo "=== APOC gate ==="
# Without APOC cognee STILL WRITES -- it does not error -- but every node
# lands as a generic __Node__ and the typed model is silently lost. That
# failure looks like a successful run until someone reads the graph, so it
# is checked here rather than discovered later.
"$COGNEE_DIR/bin/python" - <<'PY'
import asyncio, sys
async def main():
    from cognee.infrastructure.databases.graph import get_graph_engine
    engine = await get_graph_engine()
    rows = await engine.query(
        "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc.' "
        "RETURN count(*) AS n", {})
    n = rows[0]["n"] if rows else 0
    print(f"  APOC procedures: {n}")
    if not n:
        sys.exit("FAIL: no APOC on this instance; every node would be __Node__")
asyncio.run(main())
PY

echo "=== cognee MCP server on 127.0.0.1:$PORT ==="
pkill -f "cognee-mcp" 2>/dev/null || true
sleep 1
# setsid: a plain `nohup ... &` inside an `ssh "..."` does NOT survive the
# session closing. Cost a silent non-start once already.
setsid env \
    GRAPH_DATABASE_PROVIDER=neo4j \
    GRAPH_DATABASE_URL="$NEO4J_URI" \
    GRAPH_DATABASE_NAME="${NEO4J_DATABASE:-neo4j}" \
    GRAPH_DATABASE_USERNAME="${NEO4J_USERNAME:-neo4j}" \
    GRAPH_DATABASE_PASSWORD="$NEO4J_PASSWORD" \
    LLM_API_KEY="$OPENAI_API_KEY" \
    ENABLE_BACKEND_ACCESS_CONTROL=false \
    "$COGNEE_DIR/bin/cognee-mcp" --transport http --host 127.0.0.1 --port "$PORT" \
    > /opt/swarm/cognee-mcp.log 2>&1 < /dev/null &

for _ in $(seq 1 60); do
    grep -q "Application startup complete" /opt/swarm/cognee-mcp.log 2>/dev/null && break
    sleep 2
done
grep -E "Running MCP server|startup complete|ERROR" /opt/swarm/cognee-mcp.log | tail -3 || true

echo "--- assertions ---"
# An agent must be able to REACH the server and not READ its credentials.
# Both halves matter: the old layer passed a reachability check while
# answering the handshake with 406 and handing the model zero tools.
FIRST_AGENT="$(getent passwd | awk -F: '/^agent-/{print $1; exit}')"
if [ -n "$FIRST_AGENT" ]; then
    su - "$FIRST_AGENT" -c "cat $COGNEE_DIR/bin/cognee-mcp" >/dev/null 2>&1 \
        && { echo "FAIL: an agent can read the cognee venv"; exit 1; }
    echo "  ok: agents cannot read the cognee venv"
    su - "$FIRST_AGENT" -c "cat /opt/swarm/env" >/dev/null 2>&1 \
        && { echo "FAIL: an agent can read the credential file"; exit 1; }
    echo "  ok: agents cannot read /opt/swarm/env"
fi
# No secret in any process argv: `setsid env` puts them in the
# environment, not the command line, and `ps` is world-readable.
if ps -eo args | grep -v grep | grep -q "$NEO4J_PASSWORD"; then
    echo "FAIL: the Neo4j password is visible in ps"; exit 1
fi
echo "  ok: no secret in any process argv"
echo "=== provisioned: cognee MCP on 127.0.0.1:$PORT ==="
