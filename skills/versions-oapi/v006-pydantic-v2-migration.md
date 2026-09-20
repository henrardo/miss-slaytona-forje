---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 6
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so that
  imports, model construction, validation, parsing, serialization, generated
  schemas, and repository tests preserve intended behavior. Complete the
  migration without redirecting imports to pydantic.v1, without deleting,
  emptying, bypassing, or neutralizing validators or other function bodies,
  and without stopping after searches, investigation, planning, or a partial
  import check.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - >
    Rewriting imports to `pydantic.v1`, adding fallback imports that select
    `pydantic.v1`, or otherwise routing production code through the v1
    compatibility namespace. This is not a native-v2 migration even if most
    tests pass.
  - >
    Replacing a validator or any other function body with `pass`, ellipsis, a
    bare return, an unconditional constant result, or another no-op so the
    function still imports. Emptying a function body is explicitly rejected,
    even if the suite becomes green.
  - >
    Removing validation decorators, commenting out checks, weakening model
    fields to `Any`, suppressing `ValidationError`, removing fields, or making
    extra-field handling permissive merely to avoid failures.
  - Declaring the migration complete without running the repository's own complete test suite.
  - >
    Spending the entire attempt inventorying APIs without making edits. Use the
    first complete traceback to choose a migration slice, edit it, and validate
    it immediately.
  - >
    Ending an execution turn after stating a plan, summary, proposed next
    search, or list of remaining work. While a known blocker remains, perform
    the next edit and validating command instead.
  - >
    Piping the primary test command through `head`, `tail`, `grep`, `tee`, or
    another command without preserving pytest's status. A downstream command
    can report exit zero while pytest failed.
  - >
    Treating a displayed exit code as proof that tests passed when output was
    truncated, piped, or produced by a downstream command.
  - >
    Treating zero collected tests, successful package import, or successful
    test collection as a passing suite.
  - >
    Assuming usages in tests are irrelevant. Tests define required public APIs,
    construction semantics, invalid-input behavior, aliases, serialization,
    equality, and compatibility expectations.
  - >
    Blindly replacing every old API name. Validator modes, Optional defaults,
    aliases, unions, equality, serialization, schema output, and coercion
    changed semantically and require behavior-aware edits.
  - >
    Updating only the first `Field(const=True)`, `class Config`, `parse_obj`,
    or `update_forward_refs` occurrence. Inventory and migrate the complete
    production surface, then use tests to locate semantic gaps.
  - >
    Editing generated templates merely because they contain words such as
    `construct`, `copy`, `dict`, `json`, or `schema`. Distinguish Pydantic
    methods from domain methods, Jinja filters, and generated-client code.
  - >
    Changing tests to accept broken production behavior. Modify tests only when
    the task explicitly requires native-v2 expectations and the previous
    assertion genuinely encodes a changed external contract.
  - >
    Running broad regular-expression substitutions over nested `Config`
    classes, validators, or large `schema_extra` dictionaries without reviewing
    each resulting file. Regex edits can corrupt indentation and class bodies.
  - >
    Continuing with a broad automated edit after its expected match is absent,
    or trying successively wider replacements without rereading the actual file.
  - >
    Using a mistyped, stale, or duplicated repository path. Establish the root
    once, change into it, and use repository-relative paths thereafter.
  - >
    Treating Pydantic deprecation warnings as proof of a native migration.
    Compatibility aliases can execute under v2 while leaving v1-style APIs in
    production.
  - >
    Repeatedly consulting general migration documentation after the repository
    traceback already identifies the next concrete edit. Prefer repository
    evidence and focused tests over redundant research.
  - >
    Making many unvalidated edits before checking syntax or imports. A malformed
    intermediate file obscures the original migration failures and wastes the
    remaining execution budget.
  - >
    Declaring the task complete because one module imports after fixing
    `Field(const=True)`. Import success is only the first validation gate.

steps:
  - name: establish-repository-root-and-state
    description: >
      Run `pwd`, identify the version-control root, change into that verified
      root, and inspect `git status --short` before editing. Record unrelated
      user changes and preserve them. Inspect the active Python executable,
      Python version, and installed Pydantic version with the same interpreter
      that will run tests. Use repository-relative paths for all later commands.
      Do not reset, clean, or overwrite unrelated work.
    outputs:
      - name: repository-state
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read project metadata and contributor documentation just far enough to
      identify the repository's documented test, lint, type-check, formatting,
      build, and dependency-management commands. Prefer those commands over
      invented equivalents. Note whether tox, nox, Poetry, uv, or another tool
      creates a different environment from the active shell.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Run the documented complete test command directly. If none is documented,
      run `python -m pytest -x -vv`. Do not pipe or truncate this primary run.
      If capture is necessary, redirect output to a file, save the command status
      immediately, and inspect the file afterward. If using `tee`, enable
      `pipefail` and inspect the test process status explicitly. Record the
      actual exit status, collected count, passed count, and whether failure
      occurred during pytest configuration, conftest import, collection, package
      import, or test execution. Zero collected tests is a failure. Preserve the
      first complete traceback rather than only its first or last lines.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback says ``const` is removed, use `Literal` instead`,
      inspect the complete affected model and its base class, then search the
      production tree for every `Field(..., const=True)` occurrence. Replace
      each constant field with an explicit annotation such as
      `name: Literal["value"] = "value"` or, for an enum discriminator,
      `param_in: Literal[ParameterLocation.HEADER] =
      Field(default=ParameterLocation.HEADER, alias="in")`. Preserve aliases,
      defaults, enum values, and field names. Add the `Literal` import.
      Pydantic v2 requires model fields to have type annotations, so do not
      merely delete `const=True`. Make this edit before conducting a broad
      optional inventory, then compile and import the affected module.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `pyproject.toml`, setup files, requirements files, lockfiles, tox or
      nox configuration, CI workflows, and migration-specific dependency files
      such as `requirements-v2.txt` when present. Determine where Pydantic is
      declared, whether the target is native v2 only or genuine dual-major
      support, and whether companion packages such as `pydantic-settings` are
      available. Update constraints and lock metadata if they still exclude v2.
      Never introduce `pydantic.v1` as an escape hatch.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      Search production code, tests, examples, and generation templates for
      Pydantic imports and v1 APIs. Include `BaseModel`, `BaseSettings`, `Extra`,
      `class Config`, `ConfigDict`, `Field` arguments, `validator`,
      `root_validator`, `parse_obj`, `parse_raw`, `parse_file`, `from_orm`,
      `dict`, `json`, `schema`, `schema_json`, `copy`, `construct`,
      `__fields__`, `__fields_set__`, `update_forward_refs`, `GenericModel`,
      `__root__`, constrained types, Pydantic dataclasses, custom types,
      `json_encoders`, schema hooks, and direct `ModelField` access. Search for
      removed or renamed field arguments including `const`, `regex`,
      `min_items`, `max_items`, `unique_items`, `allow_mutation`, and arbitrary
      extra keyword metadata. Use precise searches and inspect context so
      unrelated methods or template filters are not misclassified. Record every
      production occurrence, but time-box the inventory and return promptly to
      editing the active blocker.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read each affected model module, its complete base classes, and relevant
      callers rather than relying on grep snippets. Map inheritance, aliases,
      recursive references, discriminated unions, enums, custom validators,
      arbitrary types, extra-field policy, JSON-schema customization, and model
      API calls. Read tests that construct, reject, compare, dump, or generate
      schemas from these models. Pay particular attention to aliased OpenAPI
      fields such as `in`, constant discriminator fields, and configuration
      inherited from shared bases.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Group findings into small slices: dependencies and imports, model
      configuration, fields and annotations, optionality, field validators,
      model validators, parsing, serialization, schema generation,
      introspection, forward references, and specialist model types. Put the
      collection blocker first and name exact files plus the narrow validating
      command. The plan is not a stopping point: perform the first edit and
      validation in the same execution sequence.
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

  - name: execute-native-v2-api-migration-steps
    description: >
      When the migration inventory, behavior map, or traceback identifies model
      configuration, fields, optionality, validators, validation entry points,
      serialization, schema generation, introspection, forward references, or
      specialist model types, read `references/native-v2-api-migrations.md` and
      execute every applicable step in its native-v2 API migration section.
      When import and removed-API failures are resolved, read and execute its
      semantic-differences section. Return to the reference whenever subsequent
      tests expose another covered migration area.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: native-v2-api-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After each coherent edit, run a syntax check such as
      `python -m compileall -q` on the affected package, import the affected
      module, and run the narrowest relevant test module or node with an unpiped
      command. For an import-time blocker, progress through syntax, direct
      import, pytest collection, and focused tests. Inspect the real exit status.
      Classify the next traceback as an unconverted v1 occurrence, an incorrect
      mechanical edit, malformed source, or a semantic v2 difference. Make the
      smallest behavior-preserving correction and repeat. If an automated edit
      malformed a file, stop the batch, inspect the diff, restore only that edit
      safely, and repair the file before continuing. Do not end the attempt with
      a prose summary while a known failing command remains actionable.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Once the suite collects, rerun the precise production searches from the
      initial inventory. Collection success only proves that imported modules no
      longer fail immediately; lazy paths and unimported modules can still
      contain v1 APIs. Resolve every production occurrence or record a
      behavior-based reason that it is unrelated to Pydantic.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Review `git diff` file by file. Confirm edits are limited to the migration,
      imports are clean, type annotations and aliases remain correct, nested
      configuration dictionaries are intact, and no behavior was erased.
      Explicitly search for `pydantic.v1`, fallback imports, newly introduced
      `pass` or ellipsis statements, bare validator returns, unconditional
      validator results, commented-out checks, swallowed `ValidationError`,
      weakened `Any` annotations, removed fields, and broad test deletions.
      Review every automated replacement for indentation, syntax, decorator
      order, configuration inheritance, signatures, and unintended formatting
      churn. Preserve unrelated user changes.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Run the repository's complete documented suite without an
      output-truncating pipeline. Verify the command's actual zero status,
      collected count, passed count, skipped or failed count, and warnings.
      Successful import, collection, or focused tests are not completion. Treat
      zero collected tests as failure unless the repository intentionally has no
      tests. On failure, return to the focused edit-test loop, fix the next
      complete traceback, and rerun the full suite. Continue until it passes.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Run the repository-configured type checker, linter, formatter check,
      packaging or build command, and schema or generated-code checks used by
      CI. Resolve migration-induced errors and Pydantic deprecation warnings
      that identify remaining v1 APIs. If a gate exposes a demonstrably
      pre-existing unrelated failure, record it separately and verify the
      migration did not worsen it rather than performing unrelated cleanup.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Confirm with the repository's active interpreter that Pydantic major
      version 2 is loaded. Search the final production tree for `pydantic.v1`,
      legacy `Config` classes, `Extra`, removed `Field` arguments, deprecated
      validators, `parse_obj`, old serialization methods, old introspection
      attributes, and unresolved forward-reference calls. Distinguish genuine
      Pydantic usage from unrelated names. Exercise representative valid and
      invalid inputs, omitted versus null fields, alias and field-name
      population, serialization, and generated schema. Confirm each migrated
      validator still rejects the invalid cases it rejected before. Native-v2
      verification requires preserved behavior, not merely successful import.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-if-needed
    description: >
      When auditing how the accepted source procedure maps to this version, read
      `references/provenance.md` if it exists. The retained procedure includes
      repository establishment, unpiped baseline testing, project constraints,
      complete inventory, behavior mapping, executable planning, all native-v2
      migration areas, focused validation loops, semantic investigation, diff
      review, full-suite execution, quality gates, final verification, and
      evidence-based reporting.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Summarize changed migration areas, dependency changes, and intentional
      behavioral decisions. Report the exact full-suite and quality-gate
      commands, their actual exit outcomes, and collected and passed test counts.
      Mention residual warnings, pre-existing failures, or unrun checks plainly.
      Do not claim completion unless the full suite passed under Pydantic v2 and
      final searches found neither `pydantic.v1` shims nor behavior-erasing
      no-op implementations. If work remains, continue executing it instead of
      substituting a completion summary for the missing edits.
    outputs:
      - name: migration-report
        type: object
```