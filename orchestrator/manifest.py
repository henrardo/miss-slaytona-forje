"""Loads fixture/manifest.yaml -- the single place every script and (later)
the agent loop reads the file list and repo paths from.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "fixture"
MANIFEST_PATH = FIXTURE_DIR / "manifest.yaml"


def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())
