#!/usr/bin/env bash
# Second provisioning stage: the memory layer on the swarm host.
#
# Layout and modes:
#
#   /opt/swarm/              0711 root -- TRAVERSABLE, not listable. An agent
#                                         can reach a path it is told about and
#                                         cannot enumerate the directory.
#   /opt/swarm/hook.py       0755 root -- the post_tool hook client. Agents
#                                         execute it. Stdlib-only, no secrets:
#                                         it knows a port, not a password.
#   /opt/swarm/.venv/        0700 root -- sidecar + memory server. Credentials
#                                         live here at runtime.
#   /opt/swarm/orchestrator/ 0700 root -- reused harness modules.
#
# NO STDIO SHIM FOR THE MEMORY MCP SERVER, and that is the point. A `#!` shim
# must be READABLE to be executed (the kernel reads it to find the
# interpreter), so a shim carrying `--password=` hands the credential to any
# agent that runs `cat` on it. Instead the server runs ONCE, as root, over
# loopback HTTP, and agents are given a URL. Both sides support it:
# neo4j-agent-memory's `mcp serve --transport http`, and Vibe's
# `mcp add --transport http --url`. The credential is then never in an agent's
# config, filesystem, or -- since Vibe echoes a server's launch command into
# every tool result -- its context.
set -euo pipefail

: "${NEO4J_URI:?}" "${NEO4J_PASSWORD:?}" "${OPENAI_API_KEY:?}"
EMBEDDING="${EMBEDDING_MODEL:-openai/text-embedding-3-small}"
MCP_PORT="${MCP_PORT:-8811}"
# Pinned to the version the orchestrator resolves locally. The pod first
# installed 0.6.0 against a local 0.5.0 and that is exactly how a "works on my
# machine" split starts -- 0.6.0 is where `client.graph.execute_read` was
# scheduled for removal.
NAM_VERSION="${NAM_VERSION:-0.5.0}"

mkdir -p /opt/swarm/mcp
rm -f /opt/swarm/mcp/memory-server   # the credential-bearing shim, deleted
chmod 711 /opt/swarm

echo "=== sidecar + memory server venv (neo4j-agent-memory==$NAM_VERSION) ==="
if ! /opt/swarm/.venv/bin/python -c "import neo4j_agent_memory as m; assert m.__version__=='$NAM_VERSION'" 2>/dev/null; then
    rm -rf /opt/swarm/.venv
    python3 -m venv /opt/swarm/.venv
    /opt/swarm/.venv/bin/pip install -q --upgrade pip
    /opt/swarm/.venv/bin/pip install -q \
        "neo4j-agent-memory[mcp,openai]==$NAM_VERSION" httpx python-dotenv
fi
/opt/swarm/.venv/bin/python -c "import neo4j_agent_memory as m; print('  neo4j-agent-memory', m.__version__)"
chmod 700 /opt/swarm/.venv /opt/swarm/orchestrator 2>/dev/null || true

# THE TWO SCRIPTS THE MEMORY PATH IS MADE OF. Both are uploaded and
# sha256-verified by swarm.agent_workspace.install_host_scripts before a run
# starts; this only asserts the state it leaves, because a missing one is
# silent in opposite and equally misleading ways:
#
#   hook.py missing   -> the post_tool hook cannot run, fails open, and the
#                        run records 0 steps and 0 errors
#   relay missing     -> the hook runs fine and EVERY step stores its tool
#                        input as the agent's thought. `steps_written`
#                        climbs, the graph fills, and it is worthless.
#
# This file used to `chmod 755 /opt/swarm/hook.py` -- which assumes the file
# is already there -- and never mention the relay at all. Six runs shipped
# that way.
for script in hook.py reasoning_relay.py; do
    if [ ! -f "/opt/swarm/$script" ]; then
        echo "  FAIL: /opt/swarm/$script is missing. Run the harness, which"
        echo "        uploads it from harness/ and verifies its sha256."
        exit 1
    fi
    chmod 755 "/opt/swarm/$script"
    echo "  $script $(sha256sum "/opt/swarm/$script" | cut -c1-12)"
done

echo "=== memory MCP server, as root, loopback HTTP on :$MCP_PORT ==="
# Credentials via ENVIRONMENT, never as flags. `ps` is world-readable on
# Linux, so `--password X` in argv is visible to every agent on the host --
# measured: two processes were exposing it this way. The CLI documents
# NEO4J_PASSWORD as an accepted env var, so the flag buys nothing.
pkill -f "mcp serve" 2>/dev/null || true
setsid env NEO4J_URI="$NEO4J_URI" NEO4J_PASSWORD="$NEO4J_PASSWORD" \
           OPENAI_API_KEY="$OPENAI_API_KEY" nohup \
    /opt/swarm/.venv/bin/neo4j-agent-memory mcp serve \
        --transport http --host 127.0.0.1 --port "$MCP_PORT" \
        --embedding "$EMBEDDING" --backend bolt \
    > /opt/swarm/mcp-server.log 2>&1 < /dev/null &
sleep 12
# /proc/<pid>/environ is 0400 owned by the process user, so an agent cannot
# read root's environment -- unlike argv. Asserted, not assumed.
if su - agent-warm-0 -c "cat /proc/\$(pgrep -f 'mcp serve' | head -1)/environ" 2>/dev/null | tr '\0' '\n' | grep -q NEO4J_PASSWORD; then
    echo "  FAIL: an agent can read the server's environment"; exit 1
fi
echo "  ok: agents cannot read the server's environment"
if ps aux | grep -v grep | grep -qE '\-\-password|sk-proj'; then
    echo "  FAIL: a secret is still visible in ps:"; ps aux | grep -v grep | grep -oE '\-\-password [^ ]{0,4}|sk-proj' | head -3; exit 1
fi
echo "  ok: no secret in any process argv"
echo "  processes: $(pgrep -c -f 'mcp serve --transport http' || echo 0)"
echo "  log tail:"; tail -4 /opt/swarm/mcp-server.log | sed 's/^/    /'

echo "=== what an agent can and cannot do ==="
su - agent-warm-0 -c "test -x /opt/swarm/hook.py && echo '  ok: can execute hook.py'"
su - agent-warm-0 -c "test -r /opt/swarm/reasoning_relay.py && echo '  ok: can read reasoning_relay.py'" || {
    echo "  FAIL: the agent cannot READ the relay. python3 must read the"
    echo "        file to run it, so the vibe|relay pipeline would die and"
    echo "        take Vibe's stdout with it."; exit 1; }
if su - agent-warm-0 -c "ls /opt/swarm" 2>/dev/null; then
    echo "  FAIL: agent can list /opt/swarm"; exit 1
fi
echo "  ok: cannot list /opt/swarm"
if su - agent-warm-0 -c "cat /opt/swarm/.venv/bin/activate" 2>/dev/null >/dev/null; then
    echo "  FAIL: agent can read the sidecar venv"; exit 1
fi
echo "  ok: cannot read the sidecar venv"
if su - agent-warm-0 -c "grep -rl '$NEO4J_PASSWORD' /opt /home/agent-warm-0 2>/dev/null" | head -3; then
    echo "  ^^ FAIL: the Neo4j password is readable by the agent at the paths above"
else
    echo "  ok: the Neo4j password is not readable anywhere the agent can reach"
fi

# THE STEP-MEMORY SIDECAR. In this script because everything else the
# memory path needs is, and because a component started by a hand-typed
# ssh one-liner is a component whose arguments nobody can state later --
# the same gap that left hook.py and reasoning_relay.py off the pod
# entirely and cost the 2026-09-18/19 series its reasoning.
#
# Credentials from the FILE, never argv: `ps` is world-readable and every
# agent on this host can read it.
SIDECAR_PORT="${SIDECAR_PORT:-8812}"
SIDECAR_AGENTS="${SIDECAR_AGENTS:-warm-0}"
echo "=== step-memory sidecar on 127.0.0.1:$SIDECAR_PORT for $SIDECAR_AGENTS ==="
pkill -f "sidecar_main.py" 2>/dev/null || true
sleep 1
cd /opt/swarm
setsid env NEO4J_URI="$NEO4J_URI" NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}" \
           NEO4J_PASSWORD="$NEO4J_PASSWORD" OPENAI_API_KEY="$OPENAI_API_KEY" \
           PYTHONPATH=/opt/swarm nohup \
    /opt/swarm/.venv/bin/python /opt/swarm/swarm/sidecar_main.py \
        --port "$SIDECAR_PORT" --agents "$SIDECAR_AGENTS" \
    > /opt/swarm/sidecar.log 2>&1 < /dev/null &
for _ in $(seq 1 30); do
    sleep 2
    grep -q "sidecar listening" /opt/swarm/sidecar.log 2>/dev/null && break
done
if ! grep -q "sidecar listening" /opt/swarm/sidecar.log 2>/dev/null; then
    echo "  FAIL: the sidecar did not come up. Without it the post_tool"
    echo "        hook fails open on every tool call and warm's graph"
    echo "        stays empty while the run looks normal."
    tail -20 /opt/swarm/sidecar.log 2>/dev/null || echo "  (no log at all)"
    exit 1
fi
echo "  $(grep 'sidecar listening' /opt/swarm/sidecar.log | tail -1)"

echo "=== provisioned ==="
