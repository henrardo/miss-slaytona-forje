#!/usr/bin/env python3
"""Prove Cognee's own loop closes, against the real graph, with no GPU.

    MSF_FIXTURE_DIR=fixtures/x12sdk .venv/bin/python scripts/prove_memory.py

Three simulated attempts on the real fixture. No model, no Vibe, no Daytona:
the verdicts are scripted, so the only thing under test is Cognee.

WHAT IS AND IS NOT UNDER TEST. The harness writes ONE thing per attempt -- a
SkillRunEntry carrying the grader's `success_score` and a `feedback` sign --
and reads back the procedure Cognee rewrote from it, plus one plain `recall`.
There used to be a prose document per attempt as well, written by the harness
into WORKED and DID-NOT-WORK node sets it invented; that is gone, so what
these checks watch is `improve_skill` and `distill_sessions` doing the work.

Writes into its own dataset and cleans up, so it is safe to run against the
instance a real experiment is using.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
os.environ.setdefault("LOG_LEVEL", "ERROR")

from orchestrator import cognee_layer as C  # noqa: E402
from orchestrator.manifest import FIXTURE_DIR, load_manifest  # noqa: E402

# Three attempts with the verdicts an independent suite would have returned.
# The shape every real x12sdk run has had: a rejected shim, then progress,
# then self-inflicted damage.
ATTEMPTS = [
    dict(helped=False, tests_passed=0, tests_total=261, closeness=0.0185,
         summary="The suite is no better than before this attempt. These "
                 "files still import pydantic's v1 compatibility shim: "
                 "x12sdk/v5010/segments.py.",
         error_signature="E   PydanticUserError: `regex` is removed. "
                         "use `pattern` instead"),
    dict(helped=True, tests_passed=60, tests_total=261, closeness=0.0401,
         summary="More of the suite passes than before this attempt "
                 "(0 -> 60), so this is verified progress.",
         error_signature="E   PydanticUserError: `allow_mutation` is removed"),
    dict(helped=False, tests_passed=0, tests_total=261, closeness=-1.9748,
         summary="The suite is no better and the tree no longer parses.",
         error_signature="E   SyntaxError: expected ':'"),
]


def rule(label: str) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}", flush=True)


async def main(args) -> int:
    dataset = args.dataset
    code_dataset = f"{dataset}-code"
    C.configure(dataset=dataset)
    failures: list[str] = []

    def check(claim: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {claim}"
              + (f"  -- {detail}" if detail else ""), flush=True)
        if not ok:
            failures.append(claim)

    rule("0. the graph")
    print(f"  {await C.assert_ready()}")
    print(f"  dataset {dataset}")

    rule("1. the fixture as a code graph (SearchType.CODE, keyless)")
    package = load_manifest().get("package_path")
    code_root = FIXTURE_DIR / package
    started = time.monotonic()
    kinds = await C.ingest_code_graph(code_root, dataset=code_dataset)
    print(f"  {FIXTURE_DIR.name}/{package} -> {kinds} in "
          f"{time.monotonic() - started:.1f}s")
    check("the code graph holds modules and symbols",
          bool(kinds.get("module")) and bool(kinds.get("symbol")), str(kinds))
    code = await C.code_brief(dataset=code_dataset, repo=code_root.name,
                              package=package)
    check("the code brief names the package under migration",
          package in code, f"{len(code)} chars")

    rule("2. the skill Cognee holds at the start")
    procedure = await C.ensure_skill(dataset=dataset)
    check("the seed procedure landed", len(procedure) > 200,
          f"{len(procedure):,} chars")
    seed_marker = "VERSION 0 IS DELIBERATELY EMPTY"
    check("it is the empty scaffold, carrying no migration knowledge",
          seed_marker in procedure)

    mem = C.CogneeMemory(dataset=dataset, fixture=FIXTURE_DIR.name,
                         label="warm-0",
                         session_id=f"{dataset}:{args.run}:warm-0",
                         mode="hybrid", code_dataset=code_dataset,
                         code_repo=code_root.name, package=package)

    sizes = [len(procedure)]
    briefs: list[str] = []
    for i, attempt in enumerate(ATTEMPTS[:args.attempts], start=1):
        rule(f"3.{i} attempt {i}")
        query = (ATTEMPTS[i - 2]["error_signature"] if i > 1
                 else "Migrate this codebase from pydantic v1 to v2")
        brief = await mem.brief(query)
        briefs.append(brief)
        print(f"  brief {len(brief):,} chars, recalled against {query!r}")
        for line in brief.splitlines():
            print(f"  | {line}")

        written = await mem.record(attempt=i, **attempt)
        print(f"  recorded: {written}")
        check(f"attempt {i}'s score reached Cognee",
              written.get("score") is not None, str(written.get("score")))
        bridged = await mem.improve()
        print(f"  bridged: {bridged['status']} "
              f"{ {k: v['status'] for k, v in bridged['stages'].items()} }")
        sizes.append(written.get("procedure_chars") or 0)

    rule("4. did Cognee's loop close?")
    print(f"  procedure after each attempt: {sizes} chars")
    after = await C.current_procedure(dataset=dataset) or ""
    check("Cognee rewrote the procedure from the grader's scores",
          after != procedure, f"{len(procedure):,} -> {len(after):,}")
    check("the rewrite carries migration knowledge the scaffold did not",
          seed_marker not in after and len(after) > len(procedure))
    check("the procedure never shrank below the scaffold",
          all(n >= len(procedure) for n in sizes[1:]), str(sizes))
    print("\n" + "\n".join(f"  | {line}" for line in after.splitlines()[:25]))

    rule("5. what a later attempt is handed")
    later = briefs[-1] if len(briefs) > 1 else ""
    check("a later attempt gets the code graph", C.BRIEF_CODE in later)
    check("...and whatever Cognee put in the graph",
          C.BRIEF_MEMORY in later,
          "empty means distill_sessions produced nothing retrievable")
    a = await mem.brief(ATTEMPTS[0]["error_signature"])
    b = await mem.brief(ATTEMPTS[0]["error_signature"])
    check("two identical reads over one unchanged graph are identical",
          a == b, f"{len(a)} vs {len(b)} chars")
    check("every block stays inside its budget",
          len(a) <= 3 * C.MAX_BLOCK_CHARS, f"{len(a)} chars")

    if args.keep:
        print(f"\nkept: {dataset}, {code_dataset}")
    else:
        rule("6. cleanup")
        for name in (dataset, code_dataset):
            try:
                await C.forget_everything(dataset=name)
                print(f"  forgot {name}")
            except Exception as exc:
                print(f"  could not forget {name}: {exc!r}")

    rule("VERDICT")
    if failures:
        for f in failures:
            print(f"  FAILED: {f}")
        print(f"\n{len(failures)} check(s) failed")
        return 1
    print("  every check passed: the grader's score reaches Cognee, Cognee "
          "rewrites the procedure from it, and a later attempt reads the "
          "rewrite")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=f"msf-proof-{int(time.time())}")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--run", default=str(int(time.time())),
                   help="label for this invocation; goes in the session id so "
                        "two runs over one dataset do not share a session")
    p.add_argument("--keep", action="store_true",
                   help="do not forget the proof's datasets afterwards")
    raise SystemExit(asyncio.run(main(p.parse_args())))
