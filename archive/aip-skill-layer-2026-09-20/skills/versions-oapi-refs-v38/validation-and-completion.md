# Validate every edit slice

Run the narrowest behavioral test or sentinel associated with the slice, followed by collection or the next broader relevant test group. Record the true unmasked exit status. On failure, fix the first causal error and immediately rerun the same check.

# Triage the first post-collection suite

Run the full unit suite early rather than converting every warning first. Cluster failures by shared cause: requiredness, aliases, defaults, extra handling, recursive resolution, serialization, validator semantics, or dependency drift. Fix the highest-leverage production cause and rerun its focused tests.

# Triage a partially passing suite

Treat 310 or 445 passing tests with remaining failures as evidence that broad migration is working, not as permission to stop. Inspect the first failure and setup errors, identify the shared model or fixture, and repair semantic clusters before unrelated deprecations. Continue until the complete suite exits zero.

# Repeat inventory after collection succeeds

Search again for `pydantic.v1`, `Extra`, nested model `Config`, `const=True`, old constraint names, `schema_extra`, old population settings, deprecated model methods, obsolete validator decorators, field internals, and forward-reference APIs. Distinguish intentional compatibility references in documentation from executable production usage.

# Inspect and review the diff

Review every changed file and the diff summary. Look for truncated examples, duplicated configuration, malformed imports, accidental test edits, entire-file rewrites, temporary scripts, generated summaries, formatting noise, lost function bodies, `pass`, disabled validation, and unrelated dependency churn. Recompile all changed Python files after cleanup.

# Run the complete test suite

Execute the authoritative suite without output truncation or exit-masking pipelines. Capture the exact command, true exit code, collected count, passed count, failed count, skipped count, and warnings. If it fails, return to first-cause triage rather than reporting partial success.

# Run project quality gates

Run the repository's authoritative formatting, linting, typing, packaging, generation, and integration checks that are available in the established environment. Do not silently skip a required gate because an optional task runner is absent; execute its underlying documented command when possible and report genuine environment limitations precisely.

# Perform final native-v2 verification

Confirm the runtime imports Pydantic v2, package imports succeed, representative models validate and serialize correctly, aliases and constants behave as intended, recursive models rebuild, and production code contains no `pydantic.v1` redirection. Confirm no function or validator body was emptied, replaced with `pass`, or otherwise neutralized.

# Audit provenance and procedure completeness

Account for every initial working tree change, every migration edit, and every temporary artifact. Verify that all planned slices were executed and validated, all residual inventory findings were classified, no user-owned changes were discarded, and no required migration concern was abandoned after planning.

# Report completion with evidence

Report the production changes, dependency target, exact full-suite command and result, quality-gate results, residual warnings or environment limitations, and native-v2 verification. Claim completion only when the authoritative suite exits zero and all required gates pass or a clearly identified external limitation remains. Do not substitute a prose summary for unfinished edits or failing tests.