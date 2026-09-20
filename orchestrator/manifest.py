"""Loads fixture/manifest.yaml -- the single place every script and (later)
the agent loop reads the file list and repo paths from.
"""
from __future__ import annotations

from pathlib import Path

import yaml

import os

REPO_ROOT = Path(__file__).resolve().parent.parent

# Which fixture this process is working against. `fixture/` (the small
# fastapi-mail migration) stays the default so nothing that referenced it
# changes behaviour; MSF_FIXTURE_DIR points the whole stack -- snapshot
# build, staleness hash, baseline, grader -- at another one.
#
# This exists because every run on the default fixture is won in one or two
# attempts, which leaves no within-run iteration for a distilled skill to
# improve against. Comparing fixtures needs more than one to be reachable,
# and hardcoding the path is what made "try a harder repo" a code change.
FIXTURE_DIR = Path(os.environ.get("MSF_FIXTURE_DIR")
                   or REPO_ROOT / "fixture").resolve()
MANIFEST_PATH = FIXTURE_DIR / "manifest.yaml"


def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())
