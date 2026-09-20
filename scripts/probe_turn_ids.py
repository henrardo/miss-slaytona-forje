#!/usr/bin/env python3
"""Does Vibe emit a DISTINCT `turnId` per turn? Answered locally, for free.

This is the decisive experiment for the 2026-09-20 finding that
`ReasoningStep.thought` is cumulative within an attempt: thought lengths
climbed 267 -> 1537 across ~28 turns and never reset. `note_turn()` clears
pending reasoning only when the turn id CHANGES, so cumulative growth
implies the sidecar saw one unchanging turn id. Two candidates:

    (a) Vibe emits one turnId for a whole agent run on this build, or
    (b) note_turn is not reaching the sidecar.

This script settles (a) without a GPU. It runs the REAL vibe binary against
`tests/fake_model_server.py` with a scripted multi-turn conversation and
reports the turnId on every streamed entry.

    .venv/bin/python scripts/probe_turn_ids.py --vibe /tmp/vibetest/bin/vibe

WHY THIS IS NOT ANOTHER SELF-CONFIRMING FIXTURE. The thing under test is
Vibe's own turn accounting, which is Vibe's behaviour and not the model's:
the fake server only decides how many turns there are. That is exactly the
distinction the relay bug turned on -- there, the fixture's *model shape*
(proper `reasoning` entries) was wrong for Mistral, and the assertion
depended on it. Here the assertion is "N model turns produce N distinct
turn ids", which no model-shape difference can fake.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from fake_model_server import FakeModelServer, Turn  # noqa: E402
from swarm.agent_workspace import _CONFIG_TEMPLATE  # noqa: E402

MODEL = "probe-model"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vibe", default=os.environ.get("REHEARSE_VIBE", ""),
                    help="path to a vibe binary (python 3.12+ venv)")
    ap.add_argument("--turns", type=int, default=4)
    ap.add_argument("--save", type=Path, default=None,
                    help="write the captured stream here, as a test fixture")
    args = ap.parse_args()
    if not args.vibe or not Path(args.vibe).exists():
        print("need --vibe /path/to/vibe (python 3.12+ venv)")
        return 2

    # Each scripted turn issues one tool call, so Vibe must run a real tool
    # loop and start a new turn to continue -- the shape the pod runs in.
    script = [Turn(text=f"Step {i}: looking at the tree.",
                   reasoning=f"Reasoning for turn {i}.",
                   tools=[("bash", {"command": f"echo turn-{i}"})])
              for i in range(1, args.turns)]
    script.append(Turn(text="Done."))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "repo").mkdir()
        (root / "repo" / "hello.txt").write_text("hi\n")
        vibe_home = root / ".vibe"
        vibe_home.mkdir()

        with FakeModelServer(script) as server:
            (vibe_home / "config.toml").write_text(_CONFIG_TEMPLATE.format(
                auto_compact=128000, model_base=server.base_url, model=MODEL))
            cmd = (f"cd {shlex.quote(str(root / 'repo'))} && "
                   f"VIBE_HOME={shlex.quote(str(vibe_home))} "
                   f"{shlex.quote(args.vibe)} --prompt 'List the files.' "
                   f"--auto-approve --trust --output streaming < /dev/null")
            proc = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                                  text=True, timeout=300)

    entries = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            pass

    if not entries:
        print("NO STREAMED ENTRIES -- vibe produced nothing parseable.")
        print((proc.stdout or proc.stderr)[-800:])
        return 1

    if args.save:
        args.save.write_text("".join(
            l + "\n" for l in proc.stdout.splitlines() if l.strip().startswith("{")))
        print(f"saved {args.save} ({len(entries)} entries)\n")

    print(f"vibe: {args.vibe}")
    print(f"scripted model turns: {args.turns}")
    print(f"streamed entries: {len(entries)}\n")
    print(f"{'#':>3}  {'type':<10} {'role':<10} turnId")
    ids: list[str] = []
    for n, e in enumerate(entries, 1):
        tid = e.get("turnId")
        if tid:
            ids.append(tid)
        print(f"{n:>3}  {str(e.get('type')):<10} {str(e.get('role')):<10} "
              f"{tid}")

    distinct = len(set(ids))
    print(f"\nentries carrying a turnId: {len(ids)} / {len(entries)}")
    print(f"DISTINCT turn ids: {distinct}")
    print("counts per id:", dict(Counter(ids)))
    print()
    if distinct <= 1:
        print("RESULT: Vibe emitted ONE turn id for the whole run. Candidate "
              "(a) CONFIRMED -- note_turn can never fire, and "
              "set_pending_reasoning accumulates for the entire attempt. The "
              "fix belongs in the relay/sidecar, not in note_turn.")
    else:
        print("RESULT: Vibe emits distinct turn ids. Candidate (a) REFUTED "
              "-- the turn boundary exists in the stream, so the accumulation "
              "is downstream: note_turn is not reaching the sidecar, or is "
              "not being applied before the reasoning push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
