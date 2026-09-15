"""Builds and tracks the Daytona snapshot (or ad-hoc image fallback) that
demo sandboxes run from. See scripts/build_snapshot.py for the CLI, and
Sec. 9.1 of the build spec for why the fixture is baked in ahead of time.
"""
from __future__ import annotations

import hashlib
import json
from typing import Callable

from daytona import (
    AsyncDaytona,
    CreateSandboxFromImageParams,
    CreateSnapshotParams,
    DaytonaForbiddenError,
    Image,
    Resources,
)

from orchestrator.manifest import FIXTURE_DIR, REPO_ROOT

SNAPSHOT_NAME_DEFAULT = "miss-slaytona-forje-fixture"
STATE_PATH = REPO_ROOT / ".snapshot_state.json"

# Everything the sandbox needs to run the suite as-is. Deliberately excludes
# fixture/reference_v2 (the migration answer key -- never baked into the
# snapshot) and requirements-v1.txt (irrelevant inside a v2-only sandbox).
# `fastapi_mail` is fixture/'s actual pydantic v1 source (checked out at
# sabuhish/fastapi-mail's pre-migration commit); `tests` is the post-
# migration (v2) test suite -- the real success oracle, not one we wrote.
INCLUDED_RELATIVE_PATHS = ["fastapi_mail", "tests", "requirements-v2.txt"]

# Build junk is neither part of the fixture's identity nor wanted in the
# sandbox. Leaving it in did both kinds of damage: `.pyc` files compiled
# against the *pre*-migration source were baked into the image and shipped
# on every attempt, and -- because `fixture_hash()` walked them too -- simply
# importing or running the fixture locally rewrote a `.pyc` and made the
# snapshot report itself STALE when nothing about the fixture had changed.
_JUNK_DIRS = {"__pycache__", ".pytest_cache"}


def _is_junk(relative_parts: tuple[str, ...], name: str) -> bool:
    return bool(_JUNK_DIRS.intersection(relative_parts)) or name.endswith(".pyc")


def fixture_hash() -> str:
    """Stable hash over every file baked into the snapshot, so a stale
    snapshot (built before a later fixture edit) can be detected up front."""
    digest = hashlib.sha256()
    for rel in sorted(INCLUDED_RELATIVE_PATHS):
        root = FIXTURE_DIR / rel
        paths = sorted(root.rglob("*")) if root.is_dir() else [root]
        for file_path in paths:
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(FIXTURE_DIR)
            if _is_junk(rel.parts, file_path.name):
                continue
            digest.update(str(rel).encode())
            digest.update(file_path.read_bytes())
    return digest.hexdigest()


def build_image() -> Image:
    image = Image.debian_slim("3.12").pip_install_from_requirements(str(FIXTURE_DIR / "requirements-v2.txt"))
    for rel in INCLUDED_RELATIVE_PATHS:
        if rel == "requirements-v2.txt":
            continue  # already consumed by pip_install_from_requirements above
        local_path = FIXTURE_DIR / rel
        remote_path = f"/repo/{rel}"
        image = (
            image.add_local_dir(str(local_path), remote_path)
            if local_path.is_dir()
            else image.add_local_file(str(local_path), remote_path)
        )
    return image.workdir("/repo")


def load_state() -> dict:
    if not STATE_PATH.exists():
        raise FileNotFoundError(f"no snapshot state at {STATE_PATH} -- run scripts/build_snapshot.py first")
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps({**state, "fixture_hash": fixture_hash()}, indent=2) + "\n")


def is_stale() -> tuple[bool, str]:
    """(stale, message) -- never built, or built from since-changed fixture
    contents. Safe to call with no Daytona client/credentials."""
    if not STATE_PATH.exists():
        return True, f"no snapshot recorded at {STATE_PATH} -- run build_snapshot.py first"
    state = json.loads(STATE_PATH.read_text())
    if state.get("fixture_hash") != fixture_hash():
        return True, "snapshot is STALE: fixture/ has changed since it was built"
    label = "image build cache (mode=image)" if state.get("mode") == "image" else f"snapshot {state.get('snapshot_name')!r}"
    return False, f"{label} is fresh"


async def register_or_warm(
    client: AsyncDaytona, name: str, cpu: int, memory: int, on_log: Callable[[str], None] = print
) -> dict:
    """Try to register a persisted, named Snapshot; on 403 (account not
    verified/upgraded for persisted snapshots -- sandbox create/delete still
    works fine), fall back to warming Daytona's ad-hoc image build cache:
    create and immediately delete one throwaway sandbox from the same Image,
    which Daytona then caches server-side by content hash. Returns the state
    dict to pass to save_state()."""
    image = build_image()
    resources = Resources(cpu=cpu, memory=memory)
    try:
        snapshot = await client.snapshot.create(
            CreateSnapshotParams(name=name, image=image, resources=resources), on_logs=on_log
        )
        on_log(f"snapshot ready: {snapshot.name} (state={snapshot.state})")
        return {"mode": "snapshot", "snapshot_name": name}
    except DaytonaForbiddenError as e:
        on_log(f"snapshot registration forbidden ({e}); this Daytona account likely needs")
        on_log("verification/a plan upgrade for persisted snapshots -- see app.daytona.io.")
        on_log("Falling back to warming the ad-hoc image build cache instead...")
        box = await client.create(
            CreateSandboxFromImageParams(image=image, language="python", ephemeral=True, resources=resources),
            timeout=180,
        )
        await client.delete(box)
        on_log("image cache warmed; sandbox creation from this Image will now be fast")
        return {"mode": "image", "cpu": cpu, "memory": memory}


def pool_kwargs_from_state(state: dict) -> dict:
    """Translate saved state into the snapshot_name=/image=+resources=
    kwargs SandboxPool expects, so callers never branch on mode themselves."""
    if state.get("mode") == "image":
        return {"image": build_image(), "resources": Resources(cpu=state.get("cpu", 1), memory=state.get("memory", 1))}
    return {"snapshot_name": state["snapshot_name"]}
