#!/usr/bin/env bash
# The web_lookup MCP server, on the swarm host, for BOTH arms.
#
# Runs ON the pod, as root. Idempotent.
#
# WHY IT EXISTS AT ALL: migrating fastapi_mail/email_utils/email_check.py
# means replacing `EmailStr.validate(email)` with the `email_validator`
# package. The traceback says only "EmailStr has no attribute validate" and
# never names another library, so a model that does not already know the
# package cannot derive it, and that file stays unreachable. Vibe's native
# `web_search` cannot fill the gap here: it calls Mistral's hosted API, and
# this repo's MISTRAL_API_KEY returns 429 on every call. It is disabled by
# name in config.toml; this is the working replacement.
#
# WHY IT IS REGISTERED FOR COLD TOO: it is a baseline capability, not a memory
# advantage. Give it to warm only and the arms differ in two things and every
# warm-vs-cold number is confounded.
#
# WHY HTTP ON LOOPBACK AND NOT STDIO: same reason as the memory server. Vibe
# echoes a stdio server's launch command into every tool result, and this one
# needs OPENAI_API_KEY. Held here in a root-only file instead, in a process
# the agents can reach but not read.
#
# WHY ITS OWN VENV: mistral-vibe pins mcp==1.28.1, fastmcp needs mcp>=2, and
# installing them together removes EVERY MCP server from the model's tool
# list. NOTES-hard-won.md, "MCP servers need their own venvs".
set -euo pipefail

WEB_DIR=/opt/swarm/web
PORT="${1:-8813}"
ENV_FILE=/opt/swarm/env

mkdir -p "$WEB_DIR"
chmod 711 /opt/swarm

# THE CREDENTIAL FILE, WRITTEN HERE IF IT DOES NOT EXIST YET.
#
# `SwarmHost.write_env_file` exists and is called by nothing, so on a cold
# pod this script died at `. /opt/swarm/env` with "No such file or
# directory" -- after building its venv, so it looked like a venv problem.
# The harness writes the file too, but not until a run starts, and this
# script is documented as running BEFORE that. So it writes its own, from
# the environment, and refuses to start without the key rather than serving
# a web tool that answers every call with an auth error.
if [ ! -f "$ENV_FILE" ]; then
    : "${OPENAI_API_KEY:?set OPENAI_API_KEY (or write /opt/swarm/env) before provisioning the web tool}"
    printf 'export OPENAI_API_KEY=%q\n' "$OPENAI_API_KEY" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "  wrote $ENV_FILE from the environment"
fi

# THE SERVER SOURCE, from wherever bring-up left it.
#
# `host_scripts()` installs this to $WEB_DIR -- but only once a RUN starts,
# which is after this script. On a cold pod it died with "File not found:
# /opt/swarm/web/server.py", which is the same class of fault as the
# credential file: a step that assumes something earlier put a file there
# and no earlier step does.
if [ ! -f "$WEB_DIR/server.py" ]; then
    for candidate in /root/harness/web-tools /root/web-tools; do
        if [ -f "$candidate/server.py" ]; then
            cp "$candidate/server.py" "$candidate/requirements.txt" "$WEB_DIR/"
            echo "  copied the web server from $candidate"
            break
        fi
    done
fi
[ -f "$WEB_DIR/server.py" ] || {
    echo "FAIL: no web server source. Upload harness/web-tools/ to /root/harness/web-tools first."
    exit 1
}
if [ ! -x "$WEB_DIR/.venv/bin/python" ]; then
    python3 -m venv "$WEB_DIR/.venv"
    "$WEB_DIR/.venv/bin/pip" install -q --upgrade pip
    "$WEB_DIR/.venv/bin/pip" install -q fastmcp openai
fi
# 0711 on the directory and 0600 on the key file: an agent can traverse to
# reach nothing it can read.
chmod 700 "$WEB_DIR"

pkill -f "web/server.py:server" || true
sleep 1
set -a; . /opt/swarm/env; set +a
cd "$WEB_DIR"
# `fastmcp run` imports the `server` object and serves it over the chosen
# transport. server.py is NOT edited: its own __main__ calls server.run(),
# which takes no CLI arguments and would serve stdio.
setsid nohup "$WEB_DIR/.venv/bin/fastmcp" run "$WEB_DIR/server.py:server" \
  --transport http --host 127.0.0.1 --port "$PORT" \
  > /opt/swarm/web-server.log 2>&1 < /dev/null &
sleep 6

echo "--- assertions ---"
grep -q "OPENAI_API_KEY" /opt/swarm/env || { echo "FAIL: no OPENAI_API_KEY in /opt/swarm/env"; exit 1; }
su - agent-warm-0 -c "cat /opt/swarm/env" 2>/dev/null && { echo "FAIL: an agent can read the key file"; exit 1; }
pgrep -f "web/server.py:server" >/dev/null || { echo "FAIL: web server not running"; tail -20 /opt/swarm/web-server.log; exit 1; }
echo "OK: web server on 127.0.0.1:$PORT, key unreadable by agents"
