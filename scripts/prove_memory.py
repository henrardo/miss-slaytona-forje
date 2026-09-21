#!/usr/bin/env python3
"""Prove the memory loop closes, against the real graph, with no GPU.

    MSF_FIXTURE_DIR=fixtures/x12sdk .venv/bin/python scripts/prove_memory.py

Three simulated attempts on the real fixture. No model, no Vibe, no Daytona:
the verdicts are scripted, so the only thing under test is whether what the
grader concluded about attempt N reaches attempt N+1's prompt, split into the
half to repeat and the half to avoid.

The unit tests pin the same property against a fake `cognee`. This pins it
against Aura, LanceDB, OpenAI embeddings and cognee 1.6.0, which is where
every version of this has actually broken.

Writes into its own dataset and its own node sets and cleans them up, so it
is safe to run against the instance a real experiment is using.
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

# Three attempts, each with the verdict an independent suite would have
# returned. Attempt 2 moves the suite and attempt 3 breaks the tree, which is
# the shape every real run on x12sdk has had.
ATTEMPTS = [
    dict(helped=False, headline="The suite is no better than before this "
                                "attempt, so the changes below bought nothing.",
         evidence="--- a/x12sdk/v5010/segments.py\n"
                  "+++ b/x12sdk/v5010/segments.py\n"
                  "-from pydantic import BaseModel, validator\n"
                  "+from pydantic import BaseModel\n"
                  "+from pydantic.v1 import validator",
         tests_passed=0, tests_total=261, closeness=0.0185, v1_remaining=380,
         error_signature="E   PydanticUserError: `regex` is removed. "
                         "use `pattern` instead",
         rejected_because="MIGRATION NOT COMPLETE: these files still import "
                          "pydantic's v1 compatibility shim: "
                          "x12sdk/v5010/segments.py."),
    dict(helped=True, headline="More of the suite passes than before this "
                               "attempt (0 -> 60), so the changes below are "
                               "verified progress.",
         evidence="--- a/x12sdk/v5010/segments.py\n"
                  "+++ b/x12sdk/v5010/segments.py\n"
                  "-    npi: str = Field(..., regex=r'^\\d{10}$')\n"
                  "+    npi: str = Field(..., pattern=r'^\\d{10}$')\n"
                  "-    @validator('npi')\n"
                  "-    def check(cls, v):\n"
                  "+    @field_validator('npi')\n"
                  "+    @classmethod\n"
                  "+    def check(cls, v):",
         tests_passed=60, tests_total=261, closeness=0.0401, v1_remaining=295,
         error_signature="E   PydanticUserError: `allow_mutation` is removed"),
    dict(helped=False, headline="The suite is no better than before this "
                                "attempt, so the changes below bought nothing.",
         evidence="--- a/x12sdk/v4010/parsing.py\n"
                  "+++ b/x12sdk/v4010/parsing.py\n"
                  "-    def parse(self, raw):\n"
                  "+    def parse(self, raw)\n"
                  "         return self.model_validate(raw)",
         tests_passed=0, tests_total=261, closeness=-1.9748, v1_remaining=295,
         error_signature="E   SyntaxError: expected ':'"),
]


def rule(label: str) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}", flush=True)


async def main(args) -> int:
    dataset = args.dataset
    fixture = args.fixture or f"proof-{int(time.time())}"
    code_dataset = f"{dataset}-code"
    C.configure(dataset=dataset)
    failures: list[str] = []

    def check(claim: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {claim}"
              + (f"  -- {detail}" if detail else ""), flush=True)
        if not ok:
            failures.append(claim)

    rule("0. the graph")
    ready = await C.assert_ready()
    print(f"  {ready}")
    print(f"  dataset {dataset}, node sets {C.node_sets(fixture)}")

    rule("1. the fixture as a code graph (SearchType.CODE, keyless)")
    package = load_manifest().get("package_path")
    started = time.monotonic()
    code_root = FIXTURE_DIR / package
    kinds = await C.ingest_code_graph(code_root, dataset=code_dataset)
    print(f"  {FIXTURE_DIR.name}/{package} -> {kinds} in "
          f"{time.monotonic() - started:.1f}s")
    check("the code graph holds modules and symbols",
          bool(kinds.get("module")) and bool(kinds.get("symbol")), str(kinds))
    code = await C.code_brief(dataset=code_dataset, repo=code_root.name,
                              package=package)
    print("\n" + "\n".join(f"  | {line}" for line in code.splitlines()[:14]))
    check("the code brief names the package under migration",
          package in code, f"{len(code)} chars")

    rule("2. the skill Cognee holds")
    procedure = await C.ensure_skill(dataset=dataset)
    check("the seed procedure landed", len(procedure) > 200,
          f"{len(procedure):,} chars")

    # THE SESSION IS PER INVOCATION even when the dataset and the node sets
    # are reused, which is the whole point of the second run. `forget` does
    # not prune the session cache, so a REUSED session id distils nothing
    # ever again -- measured: 0 documents on three attempts, 1 per attempt
    # the moment the id changed.
    mem = C.CogneeMemory(dataset=dataset, fixture=fixture, label="warm-0",
                         session_id=f"{dataset}:{fixture}:{args.run}:warm-0",
                         mode="hybrid", code_dataset=code_dataset,
                         code_repo=code_root.name, package=package,
                         distil=not args.no_distill)

    # IS THIS A FIRST RUN ON THIS FIXTURE, OR A CONTINUATION?
    #
    # Read before anything is written. Every earlier version of this script
    # minted a fresh dataset and node-set prefix per invocation, so warm only
    # ever read back what that same invocation had written -- which proves
    # attempt N+1 reads attempt N and says nothing about run 2 reading run 1.
    # That second claim is the one the project rests on.
    worked_set, failed_set = C.node_sets(fixture)
    carried = {
        "worked": await C.recall_node_set(dataset=dataset,
                                          node_set=worked_set,
                                          query="pydantic v2 migration"),
        "failed": await C.recall_node_set(dataset=dataset,
                                          node_set=failed_set,
                                          query="pydantic v2 migration"),
    }
    continuation = bool(carried["worked"] or carried["failed"])
    print(f"  prior memory in these node sets: "
          f"worked {len(carried['worked'])} chars, "
          f"failed {len(carried['failed'])} chars "
          f"-> {'CONTINUATION run' if continuation else 'FIRST run'}")

    briefs: list[str] = []
    for i, attempt in enumerate(ATTEMPTS[:args.attempts], start=1):
        rule(f"3.{i} attempt {i}")
        # THE READ THIS ATTEMPT WOULD GET, before it is graded.
        query = (ATTEMPTS[i - 2]["error_signature"] if i > 1
                 else "Migrate this codebase from pydantic v1 to v2")
        brief = await mem.brief(query)
        briefs.append(brief)
        print(f"  brief for attempt {i}: {len(brief):,} chars, "
              f"recalled against {query!r}")
        for line in brief.splitlines():
            print(f"  | {line}")
        if i == 1 and not continuation:
            check("attempt 1 of a FIRST run has no outcome memory to read",
                  C.BRIEF_WORKED not in brief and C.BRIEF_FAILED not in brief)
            check("attempt 1 still gets the code graph",
                  C.BRIEF_CODE in brief)
        if i == 1 and continuation:
            # THE CLAIM THE PROJECT RESTS ON: a later RUN opens with the
            # earlier run's graded verdicts already in front of it, before it
            # has done anything itself. Warm's advantage on run 2 is not
            # "it will accumulate one" -- it is present in attempt 1.
            check("attempt 1 of a LATER run opens with the earlier run's "
                  "WORKED half", C.BRIEF_WORKED in brief)
            check("attempt 1 of a LATER run opens with the earlier run's "
                  "FAILED half", C.BRIEF_FAILED in brief)
            check("what it carries across is the diff, not a summary",
                  "pattern=" in brief or "field_validator" in brief
                  or "pydantic.v1" in brief)
            check("the procedure it opens with is the rewritten one, not the "
                  "seed scaffold",
                  "VERSION 0 IS DELIBERATELY EMPTY" not in
                  (await mem.procedure()),
                  f"{len(await mem.procedure()):,} chars")

        # THE WRITE, after the verdict.
        written = await mem.record(attempt=i, **attempt)
        print(f"  recorded: {written}")
        check(f"attempt {i} was filed under the grader's verdict",
              written["node_set"] == C.node_sets(fixture)[
                  0 if attempt["helped"] else 1],
              written["node_set"])
        bridged = await mem.improve()
        stages = {k: v["status"] for k, v in bridged["stages"].items()}
        print(f"  bridged: {bridged['status']} {stages}")

    rule("4. did the loop close?")
    later = briefs[-1] if len(briefs) > 1 else ""
    check("a later attempt is handed the WORKED half",
          C.BRIEF_WORKED in later)
    check("a later attempt is handed the FAILED half",
          C.BRIEF_FAILED in later)
    check("the verified fix is in the brief, as the diff",
          "pattern=" in later or "field_validator" in later)
    check("the rejected shim is in the brief",
          "pydantic.v1" in later or "MIGRATION NOT COMPLETE" in later)
    sizes = " -> ".join(str(len(b)) for b in briefs)
    if continuation:
        # SATURATED, BY DESIGN, and worth stating rather than discovering.
        # By a second run each half is already at MAX_BLOCK_CHARS, so the
        # brief cannot grow -- new documents DISPLACE old ones by relevance
        # to the failure this attempt is working on. The cap is there because
        # one uncapped version of this block reached 15,170 characters and
        # warm spent three attempts reporting on it.
        budget = 3 * C.MAX_BLOCK_CHARS
        check("the brief stays inside its budget as runs accumulate",
              all(len(b) <= budget for b in briefs), f"{sizes} (cap {budget})")
        check("it is still full on a later run, not emptied by displacement",
              all(C.BRIEF_WORKED in b and C.BRIEF_FAILED in b
                  for b in briefs), sizes)
    else:
        check("the brief grows as attempts accumulate",
              len(briefs[-1]) > len(briefs[0]), sizes)

    rule("5. is the read deterministic?")
    a = await mem.brief(ATTEMPTS[0]["error_signature"])
    b = await mem.brief(ATTEMPTS[0]["error_signature"])
    check("two identical briefs over one unchanged graph are identical",
          a == b, f"{len(a)} vs {len(b)} chars")

    rule("6. is another fixture's memory kept out?")
    other = C.CogneeMemory(dataset=dataset, fixture=f"{fixture}-other",
                           label="warm-0", session_id=f"{dataset}:other",
                           mode="hybrid")
    await other.record(attempt=1, helped=True,
                       headline="A DIFFERENT CODEBASE entirely.",
                       evidence="SENTINEL-OTHER-FIXTURE aardvark zygote",
                       tests_passed=1, tests_total=1, closeness=1.0,
                       v1_remaining=0, error_signature=None)
    leak = await mem.brief("aardvark zygote")
    check("a sibling fixture's node set does not reach this prompt",
          "SENTINEL-OTHER-FIXTURE" not in leak)

    rule("7. did the procedure change?")
    after = await C.current_procedure(dataset=dataset) or ""
    print(f"  {len(procedure):,} -> {len(after):,} chars")
    if args.no_distill:
        check("--no-distill left the procedure alone", after == procedure)
    else:
        check("Cognee rewrote the procedure from the grader's scores",
              after != procedure,
              "no proposal was drafted" if after == procedure else "")
        print("\n" + "\n".join(f"  | {line}" for line in
                               after.splitlines()[:30]))

    if args.keep:
        print(f"\nkept: dataset {dataset}, {code_dataset}")
    else:
        rule("8. cleanup")
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
    print("  every check passed: what the grader concluded about attempt N "
          "reaches attempt N+1, split into repeat-this and do-not")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=f"msf-proof-{int(time.time())}")
    p.add_argument("--fixture", default=None,
                   help="node-set prefix; defaults to a fresh one per run")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--run", default=str(int(time.time())),
                   help="label for this invocation; goes in the session id so "
                        "two runs over the same dataset do not share one")
    p.add_argument("--no-distill", action="store_true")
    p.add_argument("--keep", action="store_true",
                   help="do not forget the proof's datasets afterwards")
    raise SystemExit(asyncio.run(main(p.parse_args())))
