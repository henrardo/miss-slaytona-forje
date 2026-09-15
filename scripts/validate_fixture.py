#!/usr/bin/env python3
"""Validate the CFP fixture against the pydantic v1 -> v2 migration contract.

Run before every demo. Asserts, in order:
  1. Every file declared in manifest.yaml exists (source + tests).
  2. Every pattern declared for a file is actually present in that file.
  3. The full test suite passes under pydantic v1.
  4. The full test suite fails under pydantic v2 (pre-migration).
  5. The full suite runs in under MAX_SUITE_SECONDS, sequentially, under v1.

Requires two separate Python environments to already exist: one with
pydantic>=1.10,<2 and one with pydantic>=2.6 (see fixture/requirements-v1.txt
and fixture/requirements-v2.txt). Point at them with FIXTURE_V1_PYTHON /
FIXTURE_V2_PYTHON, or let this script fall back to .venvs/v1 and .venvs/v2
relative to the repo root.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.manifest import FIXTURE_DIR, MANIFEST_PATH, REPO_ROOT, load_manifest

MAX_SUITE_SECONDS = 25


def _decorator_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _has_decorator(tree: ast.Module, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and name in _decorator_names(node):
            return True
    return False


def _has_class_named(tree: ast.Module, name: str) -> bool:
    return any(isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(tree))


def _annotation_is_optional(annotation: ast.AST) -> bool:
    if isinstance(annotation, ast.Subscript):
        value = annotation.value
        if isinstance(value, ast.Name) and value.id == "Optional":
            return True
        if isinstance(value, ast.Attribute) and value.attr == "Optional":
            return True
    return False


def _has_implicit_optional(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and stmt.value is None and _annotation_is_optional(stmt.annotation):
                return True
    return False


PATTERN_CHECKS = {
    "P1_VALIDATOR": lambda source, tree: _has_decorator(tree, "validator"),
    "P2_DICT_JSON": lambda source, tree: bool(re.search(r"\.(dict|json)\(", source)),
    "P3_CONFIG_CLASS": lambda source, tree: _has_class_named(tree, "Config"),
    "P4_PARSE_OBJ": lambda source, tree: bool(re.search(r"\.(parse_obj|parse_raw)\(", source)),
    "P5_ROOT_VALIDATOR": lambda source, tree: _has_decorator(tree, "root_validator"),
    "P6_IMPLICIT_OPTIONAL": lambda source, tree: _has_implicit_optional(tree),
}


def check_files_exist(manifest: dict) -> list[str]:
    errors = []
    for entry in manifest["files"]:
        if not (FIXTURE_DIR / entry["path"]).exists():
            errors.append(f"missing source file: {entry['path']}")
        if not (FIXTURE_DIR / entry["tests"]).exists():
            errors.append(f"missing test file: {entry['tests']}")
    return errors


def check_patterns_present(manifest: dict) -> list[str]:
    errors = []
    for entry in manifest["files"]:
        src_path = FIXTURE_DIR / entry["path"]
        if not src_path.exists():
            continue
        source = src_path.read_text()
        tree = ast.parse(source, filename=str(src_path))
        for pattern in entry["patterns"]:
            check = PATTERN_CHECKS.get(pattern)
            if check is None:
                errors.append(f"{entry['path']}: unknown pattern {pattern!r} in manifest")
            elif not check(source, tree):
                errors.append(f"{entry['path']}: declared pattern {pattern} not found in source")
    return errors


def resolve_python(env_var: str, default_relative: str) -> str:
    override = os.environ.get(env_var)
    if override:
        return override
    candidate = REPO_ROOT / default_relative
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(
        f"no interpreter found: set {env_var} or create {default_relative} "
        f"(see fixture/requirements-v1.txt / requirements-v2.txt)"
    )


def run_suite(python_exe: str) -> tuple[int, float, str]:
    start = time.monotonic()
    result = subprocess.run(
        [python_exe, "-m", "pytest", "-q"],
        cwd=FIXTURE_DIR,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - start
    return result.returncode, elapsed, result.stdout + result.stderr


def main() -> int:
    errors: list[str] = []

    if not MANIFEST_PATH.exists():
        print(f"FAIL: manifest not found at {MANIFEST_PATH}")
        return 1
    manifest = load_manifest()

    print("[1/5] every manifest file exists...")
    file_errors = check_files_exist(manifest)
    errors.extend(file_errors)
    print("  OK" if not file_errors else "  FAIL:\n    " + "\n    ".join(file_errors))

    print("[2/5] every declared pattern is present...")
    pattern_errors = check_patterns_present(manifest)
    errors.extend(pattern_errors)
    print("  OK" if not pattern_errors else "  FAIL:\n    " + "\n    ".join(pattern_errors))

    try:
        v1_python = resolve_python("FIXTURE_V1_PYTHON", ".venvs/v1/bin/python")
        v2_python = resolve_python("FIXTURE_V2_PYTHON", ".venvs/v2/bin/python")
    except FileNotFoundError as e:
        print(f"[3-5/5] SKIPPED: {e}")
        errors.append(str(e))
        v1_python = v2_python = None

    v1_elapsed = None
    if v1_python:
        print(f"[3/5] full suite passes under pydantic v1 ({v1_python})...")
        v1_code, v1_elapsed, v1_output = run_suite(v1_python)
        if v1_code != 0:
            errors.append("suite does not pass under pydantic v1")
            print("  FAIL:\n" + v1_output)
        else:
            print(f"  OK ({v1_elapsed:.2f}s)")

        print(f"[4/5] full suite fails under pydantic v2 ({v2_python})...")
        v2_code, v2_elapsed, _ = run_suite(v2_python)
        if v2_code == 0:
            errors.append("suite unexpectedly passes under pydantic v2 (migration would be a no-op)")
            print("  FAIL: suite passed, expected failures")
        else:
            print(f"  OK, suite fails as expected ({v2_elapsed:.2f}s)")

        print(f"[5/5] full suite runtime under {MAX_SUITE_SECONDS}s (v1, sequential)...")
        if v1_elapsed > MAX_SUITE_SECONDS:
            errors.append(f"suite runtime {v1_elapsed:.2f}s exceeds {MAX_SUITE_SECONDS}s")
            print(f"  FAIL: {v1_elapsed:.2f}s")
        else:
            print(f"  OK ({v1_elapsed:.2f}s)")

    print()
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
