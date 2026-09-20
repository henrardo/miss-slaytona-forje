#!/usr/bin/env bash
# Provision the swarm host: a shared read-only agent toolchain, and one
# unix user per agent.
#
# Runs ON the pod, as root. Idempotent.
#
# WHY A POD AND NOT A DAYTONA SANDBOX (measured 2026-09-16, see
# REDESIGN-2026-09-16.md): a Daytona sandbox can install and import Vibe, but
# its egress is SNI-filtered to an allowlist that does not include the served
# model or Neo4j Aura -- TCP 443 opens and the TLS handshake is reset -- and
# `domain_allow_list` is refused outright with "Network access is restricted
# and cannot be overridden at the sandbox level". So the agent cannot run
# there. On this pod the model is on localhost:30000, Aura's 7687 is open, and
# Daytona's own API is reachable, so the grader still works from here.
#
# WHY UNIX USERS AND NOT CONTAINERS: the pod has no docker, and it is already
# a container on a GPU host. One user per agent, each home mode 0700, gives
# what is actually needed -- an agent cannot read another agent's repo, and no
# agent can read the operator's machine at all, because the harness is not
# here.
set -euo pipefail

TOOLCHAIN=/opt/agent-toolchain
AGENT_COUNT="${1:-2}"

echo "=== shared toolchain at $TOOLCHAIN (read-only to agents) ==="
if [ ! -x "$TOOLCHAIN/bin/vibe" ]; then
    python3 -m venv "$TOOLCHAIN"
    "$TOOLCHAIN/bin/pip" install -q --upgrade pip
    # Vibe, and the packages an agent's own repo work needs at minimum. The
    # repo's own dependencies are installed per-agent, from whatever install
    # command the user supplies -- not from anything pinned here.
    "$TOOLCHAIN/bin/pip" install -q mistral-vibe
fi
# World-readable, nobody-writable: agents share one interpreter and cannot
# tamper with each other's toolchain.
chmod -R a+rX,go-w "$TOOLCHAIN"
"$TOOLCHAIN/bin/vibe" --version 2>/dev/null || "$TOOLCHAIN/bin/python" -c "import vibe; print('vibe', vibe.__version__)"

echo "=== uv, for the memory MCP server (uvx) ==="
if ! [ -x /usr/local/bin/uv ]; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh >/dev/null 2>&1 \
      || pip install -q uv
fi
command -v uv || command -v uvx || echo "WARNING: uv not on PATH"

echo "=== agent users ==="
for i in $(seq 0 $((AGENT_COUNT - 1))); do
    for swarm in warm cold; do
        u="agent-$swarm-$i"
        if ! id "$u" >/dev/null 2>&1; then
            useradd --create-home --shell /bin/bash "$u"
        fi
        # 0700: the whole point. An agent cannot list, read or traverse
        # another agent's home.
        chmod 700 "/home/$u"
        echo "  $u  home=/home/$u  mode=$(stat -c '%a' /home/$u)"
    done
done

echo "=== isolation check ==="
# Asserted, not assumed. Two agents, each trying to read the other's home.
a="agent-warm-0"; b="agent-cold-0"
su - "$a" -c "touch ~/canary && echo ok" >/dev/null
if su - "$b" -c "cat /home/$a/canary" 2>/dev/null; then
    echo "  FAIL: $b can read $a's home"
    exit 1
fi
echo "  ok: $b cannot read $a's home"
if su - "$b" -c "ls /home/$a" 2>/dev/null; then
    echo "  FAIL: $b can list $a's home"
    exit 1
fi
echo "  ok: $b cannot list $a's home"
su - "$a" -c "rm -f ~/canary"
echo "=== counting proxies (one per arm, plus distillation) ==="
# THREE, not two. Vibe never surfaces per-call usage outside its own
# process, so a separate endpoint per measured thing is the only place the
# number exists. 8821/8822 split warm from cold; 8823 exists so the
# distillation turn's tokens are reported apart from the attempt's --
# "the skill made the agent cheaper" and "the skill was cheap to produce"
# are two different claims and one total answers neither.
#
# Started here rather than by hand: they were launched manually from the
# README until now, and a missing one is invisible at run time -- the
# preflight reports "not answering" for 8821/8822, but a missing 8823
# simply reports zero distillation tokens, which reads as a distiller that
# cost nothing.
#
# Counters are cumulative and never reset (NOTES-hard-won.md), so the
# runner snapshots before and after and subtracts. Restarting a proxy
# between runs would therefore LOSE that baseline -- hence the "already
# listening, left alone" branch.
PROXY_SRC=/opt/swarm/id_fix_proxy.py
UPSTREAM=http://127.0.0.1:30000
if [ -f "$PROXY_SRC" ]; then
    for port in 8821 8822 8823; do
        if curl -sf --max-time 2 "http://127.0.0.1:$port/usage" >/dev/null 2>&1; then
            echo "  :$port already listening, left alone (counters preserved)"
            continue
        fi
        nohup python3 "$PROXY_SRC" "$port" "$UPSTREAM" \
            >"/var/log/proxy-$port.log" 2>&1 &
        sleep 0.5
        if curl -sf --max-time 5 "http://127.0.0.1:$port/usage" >/dev/null 2>&1; then
            echo "  :$port up"
        else
            echo "  FAIL: proxy on :$port did not answer /usage"
            tail -5 "/var/log/proxy-$port.log" || true
            exit 1
        fi
    done
else
    echo "  SKIP: $PROXY_SRC not present yet (copied by the runner's setup)"
fi

echo "=== sshd MaxSessions ==="
# The harness multiplexes every ssh call onto ONE master connection per pod
# (SwarmHost.argv, ControlMaster=auto), which cut a round trip from ~1.9s to
# ~0.4s. That moves the binding limit: separate connections were governed by
# MaxStartups, multiplexed channels are governed by MaxSessions, whose
# default is 10. Each agent holds a long-lived vibe channel plus up to two
# refresh channels, so 8 agents want ~24 and would silently queue or fail at
# the default.
if ! sshd -T 2>/dev/null | grep -q "^maxsessions 100$"; then
    sed -i "/^[[:space:]]*MaxSessions/d" /etc/ssh/sshd_config
    echo "MaxSessions 100" >> /etc/ssh/sshd_config
    # Reload, not restart: existing connections (including this one) survive.
    kill -HUP "$(cat /var/run/sshd.pid 2>/dev/null || pgrep -o sshd)" 2>/dev/null || true
    sleep 1
fi
echo "  maxsessions now: $(sshd -T 2>/dev/null | grep -i '^maxsessions' || echo unknown)"

echo "=== provisioned: $((AGENT_COUNT * 2)) agent users ==="
