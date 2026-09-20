---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 4
    derived_from_traces:
      - "9e3ddb8a"
      - "d2ac33d9"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so that
  imports, model construction, validation, parsing, serialization, generated
  schemas, and repository tests preserve intended behavior. Complete the
  migration without redirecting imports to pydantic.v1, without deleting or
  neutralizing validation or other function behavior, and without stopping
  after searches, investigation, or planning.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - >
    Rewriting imports to pydantic.v1 so the old API keeps working. This passes
    32 of 33 tests in this fixture and is not a migration.
  - >
    Replacing a validator or any other function body with a bare return, pass,
    constant result, ellipsis, or no-op so the function still imports. The suite
    may go green while the behavior is gone, and this task explicitly rejects it.
  - Declaring the migration complete without running the repository's own full suite.
  - >
    Spending the entire attempt inventorying APIs without making edits. Use the
    first traceback to choose a migration slice, edit it, and immediately test it.
  - >
    Ending an execution turn after stating a plan, summary, or proposed next
    search. Once the blocking failure is understood, perform an actual edit and
    run a validating command in the same attempt.
  - >
    Piping the primary test command through head, tail, grep, tee, or another
    command without preserving pytest's status. A pipeline can hide pytest's
    exit code or truncate the actionable traceback.
  - >
    Treating a displayed exit code as proof that tests passed when output was
    piped, truncated, or produced by a downstream command.
  - >
    Assuming usages in tests are irrelevant. Tests reveal required public API,
    construction semantics, validation behavior, and compatibility expectations.
  - >
    Blindly replacing every old API name. Validator modes, Optional defaults,
    aliases, unions, equality, serialization, schema output, and coercion changed
    semantically and require behavior-aware edits.
  - >
    Updating only the first Field(const=True), class Config, parse_obj, or
    update_forward_refs occurrence. Inventory and migrate the complete production
    surface, then use tests to find semantic gaps.
  - >
    Editing generated templates merely because they contain words such as
    construct, copy, dict, json, or schema. Distinguish Pydantic APIs from
    unrelated template filters, domain methods, and generated client code.
  - >
    Changing tests to accept broken production behavior. Modify tests only when
    the task explicitly requires Pydantic v2 expectations and the prior assertion
    encodes a genuinely changed external contract.
  - >
    Running broad automated substitutions without reviewing the diff for typing,
    decorator order, configuration inheritance, aliases, and validator signatures.
  - >
    Using a mistyped or stale repository path. Establish the current working
    directory once and run subsequent commands from that verified repository root.
  - >
    Treating deprecation warnings as proof of a native migration. Compatibility
    aliases may still execute under v2 while leaving the code on v1-style APIs.
  - >
    Fixing import-time errors by removing model fields, weakening types to Any,
    changing extra handling to permissive behavior, or catching and suppressing
    ValidationError without evidence that the public contract requires it.

steps:
  - name: establish-repository-root-and-state
    description: >
      Confirm the current directory and repository root with pwd and version-control
      metadata, then inspect git status before editing. Identify project metadata,
      the active Python interpreter, supported Python versions, and the exact
      installed Pydantic version. Preserve unrelated user changes. Run all later
      commands from this verified root instead of repeatedly using an error-prone
      absolute path.
    outputs:
      - name: repository-state
        type: object

  - name: establish-the-failure
    description: >
      Run the repository's documented test command. If none is documented, run
      `python -m pytest -x -vv` directly and inspect the first complete traceback.
      Do not pipe this primary command. If output must be captured, redirect both
      streams to a file, save the command's status, and inspect the file afterward;
      alternatively enable shell pipefail before tee and explicitly check
      PIPESTATUS. Record the command, actual status, collected-test count, and
      whether failure occurred during configuration, collection, import, or test
      execution. Treat zero collected tests as failure. For the known blocking
      error "`const` is removed, use `Literal` instead", proceed directly to the
      affected model after the minimum inventory needed to find every const field.
    outputs:
      - name: first-error
        type: string
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object

  - name: inspect-project-constraints
    description: >
      Read pyproject.toml, setup.cfg, setup.py, requirements files, lockfiles,
      tox or nox configuration, and CI workflows as applicable. Determine where
      Pydantic is declared, whether the requested target is native v2 only or
      genuine dual-major support, and whether companion packages such as
      pydantic-settings are available. Update dependency constraints and lock
      metadata when they still exclude v2. Follow the requested compatibility
      target; never introduce pydantic.v1 as an escape hatch.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-pydantic-surface
    description: >
      Search production code, tests, examples, and generation templates for
      Pydantic imports and v1 APIs. Include BaseModel, BaseSettings, Extra,
      class Config, ConfigDict, Field arguments, validator, root_validator,
      parse_obj, parse_raw, parse_file, from_orm, dict, json, schema, schema_json,
      copy, construct, __fields__, __fields_set__, update_forward_refs,
      GenericModel, __root__, constrained types, dataclasses, custom types,
      json_encoders, schema hooks, and direct ModelField access. Include removed
      Field arguments such as const, regex, min_items, max_items, unique_items,
      allow_mutation, and arbitrary extra keyword metadata. Use precise searches
      so unrelated domain methods and Jinja filters are not classified as
      Pydantic APIs. Record all production occurrences, but time-box this initial
      inventory: once the collection blocker and its sibling occurrences are
      known, make the first edit before pursuing optional searches.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read affected model modules, their bases, and relevant callers rather than
      relying on grep snippets. Map inheritance, aliases, discriminated unions,
      recursive references, enums, custom validators, arbitrary types, extra-field
      policy, generated JSON schema hooks, and calls to model APIs. Read tests
      that construct or serialize these models to identify behavior that must
      survive. Pay particular attention to aliased OpenAPI fields such as `in`,
      constant discriminator fields, and configuration inherited from shared
      base classes.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-a-small-migration-plan
    description: >
      Group findings into coherent slices: imports and dependencies, model
      configuration, fields and annotations, validators, parsing and serialization,
      forward references and generics, then semantic regressions. Put the slice
      blocking collection first. Name the exact files and focused tests for that
      slice. If `references/native-v2-api-migrations.md` exists, read the section
      matching the active slice; otherwise use the native-v2 rules compiled in
      the following steps. This plan is an execution checkpoint, not a stopping
      point: immediately perform the first edit and focused validation after
      producing it.
    inputs:
      - name: first-error
        type: string
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: execute-native-v2-migration-slices
    description: >
      For each active migration slice, read the matching section of
      `references/native-v2-api-migrations.md` immediately before editing and
      follow its migration instructions. Read only the sections relevant to the
      current inventory or traceback. Execute imports and dependencies,
      configuration, fields, required and optional semantics, field validators,
      model and root validators, entry points, serialization and copying, schema
      generation, introspection, forward references, and specialist model types
      as distinct slices.
    outputs:
      - name: import-and-dependency-edits
        type: list[string]
      - name: configuration-edits
        type: list[string]
      - name: field-edits
        type: list[string]
      - name: optionality-edits
        type: list[string]
      - name: field-validator-edits
        type: list[string]
      - name: model-validator-edits
        type: list[string]
      - name: entry-point-edits
        type: list[string]
      - name: serialization-edits
        type: list[string]
      - name: schema-edits
        type: list[string]
      - name: introspection-edits
        type: list[string]
      - name: forward-reference-edits
        type: list[string]
      - name: specialist-edits
        type: list[string]

  - name: run-focused-tests-after-each-slice
    description: >
      After each coherent edit, run the narrowest relevant test module or node
      with an unpiped command and inspect its real exit status. For a collection
      failure, first import the affected package or module, then rerun collection,
      then run its focused tests. Read the next complete traceback and classify
      it as an unconverted v1 occurrence, an incorrect mechanical migration, or
      a semantic v2 difference. Make the smallest behavior-preserving correction
      and retest. Maintain an execution loop of edit, import or focused test,
      traceback, correction, and retest. Do not end the attempt with a prose
      summary of what should be checked next while known failures remain.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: investigate-v2-semantic-differences
    description: >
      After obvious API removals are fixed, read
      `references/native-v2-api-migrations.md`, section `Investigate v2 semantic
      differences`, and follow it when tests expose behavioral differences.
    outputs:
      - name: semantic-fixes
        type: list[string]

  - name: inspect-and-review-the-diff
    description: >
      Review git diff and repeat the Pydantic inventory searches. Confirm that
      edits are limited to the migration, all production v1 usages are resolved
      or consciously justified, imports are clean, and no behavior was erased.
      Explicitly search for `pydantic.v1`, fallback imports, newly introduced
      pass or ellipsis statements, bare validator returns, constant validator
      results, commented-out checks, swallowed ValidationError, weakened Any
      annotations, and broad test deletions. Review every automated replacement
      for typing, decorator order, configuration inheritance, aliases, and
      signatures. Revert unrelated formatting churn that obscures the migration.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-full-test-suite
    description: >
      Run the repository's complete documented test suite without an
      output-truncating pipeline. A successful import, collection pass, or focused
      test is not completion. Verify the command's actual zero status, the number
      of collected tests, the number passed, and warnings. Treat zero collected
      tests as failure unless the repository intentionally has no tests. If the
      suite fails, return to the focused edit-test loop and rerun the full suite
      afterward. Continue until the complete suite passes.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Run the repository's configured type checker, linter, formatter check,
      packaging or build command, and schema or generated-code checks used by CI.
      Resolve migration-induced warnings and errors, especially Pydantic
      deprecation warnings that identify remaining v1 APIs. Do not invent
      unrelated cleanup when a gate exposes a pre-existing failure; record it
      separately and verify the migration did not worsen it.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Confirm with the active repository interpreter that Pydantic major version
      2 is loaded. Search the final production tree for `pydantic.v1`, legacy
      Config classes, removed Field arguments, deprecated validators, parse_obj,
      old serialization methods, old introspection attributes, and unresolved
      forward-reference calls. Distinguish genuine Pydantic usage from unrelated
      names. Exercise representative valid and invalid inputs, omitted versus
      null fields, alias-based population, serialization, and generated schema.
      Confirm validator bodies still enforce their original rules. The final
      state must use native v2 behavior and retain validation logic, not merely
      import successfully.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-if-needed
    description: >
      When auditing how the accepted source procedure maps to this version, read
      `references/provenance.md`.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Summarize changed migration areas, dependency changes, and intentional
      behavioral decisions. Report the exact full-suite and quality-gate commands,
      actual exit outcomes, and collected/passed test counts. Mention residual
      warnings, pre-existing failures, or unrun checks plainly. Do not claim
      completion unless the full suite passed under Pydantic v2 and final searches
      found neither pydantic.v1 shims nor behavior-erasing no-op implementations.
    outputs:
      - name: migration-report
        type: object
```