#!/usr/bin/env bash
# ONE EXPERIMENT: N attempts on one checkout, then archive, then stop.
#
#   scripts/run_experiment.sh <ssh-host> <ssh-port> [attempts] [arms]
#
# The shape, which is the whole point of this script existing:
#
#   1. agents attempt
#   2. agents build a skill
#   3. agents continue FROM WHERE THEY LEFT OFF with the new skill
#   4. agents update the skill
#   5. agents go again
#   6. agents update the skill
#   7. the skill and everything around it is archived
#
# Then it stops. It does not run again, and nothing here loops.
#
# WHAT THIS REPLACES. `x12_series.sh` was a `while` loop calling run.py over
# and over. Every invocation calls AgentWorkspace.seed(), which is
# `rm -rf {repo_path}` plus a fresh unpack -- so each iteration threw the
# agent's code away and handed a better skill to a pristine checkout. On
# 2026-09-20 that ran 14 times, wrote 42 distillations and 81 skill files,
# and discarded cold's best state of the night (53 of 383 surfaces left) to
# restart at 383. Re-seeding is right ONCE, at the start of an experiment,
# which is exactly what one invocation already does.
#
# `python -u`: without it Python block-buffers stdout into the log and an
# overnight run is unobservable -- the log sat at 3 lines for four minutes
# while the run was live.
set -uo pipefail
cd "$(dirname "$0")/.."

HOST="${1:?ssh host}"
PORT="${2:?ssh port}"
ATTEMPTS="${3:-3}"
ARMS="${4:-both}"
KEY="${MSF_SSH_KEY:-$HOME/.ssh/msf-pod}"
FIXTURE="${MSF_FIXTURE_DIR:-fixtures/x12sdk}"
LOG="runs/experiment-$(date -u +%Y%m%dT%H%M%SZ).log"

echo "=== experiment: $ATTEMPTS attempt(s), arms=$ARMS, fixture=$FIXTURE ==="
echo "=== log: $LOG ==="

MSF_FIXTURE_DIR="$FIXTURE" .venv/bin/python -u swarm/run.py \
    --repo "./$FIXTURE" \
    --install "pip install -r requirements-v2.txt" \
    --test "$(.venv/bin/python -c "
import os,sys; sys.path.insert(0,'.')
os.environ.setdefault('MSF_FIXTURE_DIR','$FIXTURE')
from orchestrator.manifest import load_manifest; print(load_manifest()['test_command'])")" \
    --arms "$ARMS" --swarm-size 1 --attempts "$ATTEMPTS" \
    --model mistralai/Mistral-Small-4-119B-2603 --auto-compact 128000 \
    --gpu-usd-per-hour 4.59 \
    --ssh-host "$HOST" --ssh-port "$PORT" --ssh-key "$KEY" \
    2>&1 | tee "$LOG"

# Step 7. Derived from the event log, which is the only record that
# survives the pod dying mid-experiment.
EVENTS=$(grep -oE 'runs/swarm-[0-9]+\.jsonl' "$LOG" | tail -1)
if [ -n "$EVENTS" ]; then
    MSF_FIXTURE_DIR="$FIXTURE" .venv/bin/python scripts/archive_experiment.py "$EVENTS"
else
    echo "no event log in $LOG -- nothing archived"
fi
