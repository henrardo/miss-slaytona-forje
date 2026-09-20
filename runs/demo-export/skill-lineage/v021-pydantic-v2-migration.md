---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use when a Pydantic v2 upgrade causes import, collection, syntax, validation, schema, fixture, constructor, alias, forward-reference, root-model, serialization, dependency, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 21
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, aliases, root models, type aliases, forward references,
  fixtures, dependency metadata, and repository tests preserve intended
  behavior. Complete the migration without redirecting production imports to
  `pydantic.v1`; without deleting, emptying, bypassing, replacing with `pass`,
  or otherwise neutralizing validators or any other function bodies; without
  weakening production behavior or rewriting tests merely to accept
  regressions; without corrupting source through broad mechanical edits; and
  without stopping after searches, research, investigation, planning, an
  import check, compilation, test collection, focused tests, or a partially
  passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models
  - Models import successfully under Pydantic v2 but constructors, fixtures, schemas, aliases, or behavioral tests fail
  - Most tests pass after an upgrade but a shared model, fixture, forward reference, type alias, root model, or optionality regression still causes failures
  - The installed Pydantic version and declared dependency or lockfile disagree

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Re-pointing production imports to `pydantic.v1`, directly or through a compatibility wrapper, instead of completing a native-v2 migration
  - Emptying, deleting, bypassing, replacing with `pass`, or otherwise neutralizing a validator or any other function body merely to make imports or tests pass
  - Editing tests to accept a production regression instead of preserving the behavior the tests specify
  - Ending a turn after research, inventory, planning, or a summary while executable migration work remains
  - Claiming success after an import check, compilation, collection, a focused test, or a partially passing suite
  - Piping authoritative tests through `head`, `tail`, `grep`, or `tee` without `set -o pipefail`, then trusting the pipeline's zero exit code
  - Treating a failed `grep` with no matches as a task failure instead of using `|| true` where absence is expected
  - Running repository-wide regex or `sed` rewrites over nested `Config` classes or large `schema_extra` dictionaries without per-file review and immediate syntax validation
  - Generating migration scripts that mutate many files before proving the transformation on one representative file
  - Moving `json_schema_extra` data outside `ConfigDict`, concatenating it onto a field declaration, or losing delimiters and indentation around large dictionaries
  - Converting every dictionary type alias into `RootModel` without checking callers, iteration behavior, and public API compatibility
  - Calling `model_rebuild()` on plain typing aliases rather than only on Pydantic model classes
  - Adding speculative forward-reference rebuild calls before reproducing and understanding the actual namespace error
  - Assuming `Optional[T]` implies a default of `None` under Pydantic v2
  - Changing defaults, aliases, coercion, extra-field behavior, or constructor signatures without checking tests and call sites
  - Installing unrelated tools or replacing the project's environment manager when the supplied target requirements can synchronize the existing environment
  - Overwriting user changes, reverting the entire working tree, or confusing edits inherited from a prior attempt with the clean baseline
  - Suppressing warnings or exceptions globally instead of resolving migration-specific causes
  - Before beginning any migration step, read `references/migration-guardrails.md` and avoid every anti-pattern listed there throughout the migration

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the actual repository root with `pwd`, inspect
      its top-level files, record Python and installed Pydantic versions, and
      run `git status --short`. Use one canonical absolute root thereafter;
      copy it rather than retyping it to avoid path drift such as
      `agent-worm-0` versus `agent-warm-0`. Do not edit anything yet.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Inspect `git diff`, compile modified Python files, and
      classify each change as user-owned, known-good migration work,
      malformed prior-attempt work, or unrelated. Preserve user changes.
      Repair or narrowly revert only changes whose provenance and damage are
      established. Never reset the whole repository merely to obtain a clean
      state. Re-run `git status --short` and retain the classification for the
      final provenance audit.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands." Inspect `pyproject.toml`, task-runner
      configuration, CI workflows, tox/nox files, contributor documentation,
      and supplied requirements files. Identify the exact unit-test,
      integration-test, formatting, linting, typing, and lockfile commands.
      Prefer repository-defined commands over invented substitutes. Record
      environment variables such as `TASKIPY=true` when required to prevent a
      test plugin from recursively invoking project tasks.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the
      unpiped baseline." Run the authoritative test command directly and
      capture its real exit code. Do not pipe it through output-truncation
      commands. If logging is necessary, use `set -o pipefail` before `tee` and
      inspect `PIPESTATUS`. Distinguish dependency or plugin startup failures,
      syntax errors, collection errors, and test failures. Preserve the full
      traceback and identify the earliest actionable production-code failure,
      not merely the final pytest wrapper warning.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed,
      read `references/safety-and-baseline.md` and follow "Act immediately on a
      const collection blocker." Inspect the field, inheritance hierarchy,
      callers, and tests. Replace a genuine constant field with an actual
      annotated Pydantic field using `Literal[value]` and the intended default;
      do not turn it into `ClassVar` if validation, serialization, constructor
      acceptance, or inherited field overriding depends on it. For enum
      constants, use the precise enum member in the `Literal`. Compile and
      import the affected module immediately, then rerun collection to expose
      the next blocker.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine supported Python versions, the target Pydantic
      range, package-manager and lockfile expectations, and whether the task
      includes metadata updates. Inspect supplied post-migration requirements
      before choosing API syntax. Account for Python-version-sensitive typing,
      enum, and forward-reference behavior. Do not assume the globally
      installed version matches either project declarations or the intended
      test environment.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Install or activate the supplied target dependency
      set using the existing environment when possible, then verify Pydantic's
      imported version from the same interpreter used for tests. Update the
      direct dependency declaration to the required v2 range when the task
      requires it. Regenerate or update the lockfile with the project's normal
      package manager when available; otherwise report an unresolved lockfile
      mismatch rather than silently claiming completion. Do not install a new
      package manager merely to bypass the repository's intended setup unless
      the task explicitly requires it.
    inputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]
    outputs:
      - name: target-environment
        type: object

  - name: inventory-the-complete-pydantic-surface
    description: >
      Read `references/safety-and-baseline.md` and follow "Inventory the
      complete Pydantic surface." Search production code, tests, fixtures,
      templates, dependency files, and documentation for Pydantic imports and
      model subclasses; nested `Config`; `Extra`; `schema_extra`;
      `allow_population_by_field_name`; validators; `Field` options such as
      `const`, `min_items`, `max_items`, `regex`, and `unique_items`;
      `parse_obj`, `parse_raw`, `from_orm`, `dict`, `json`, `copy`,
      `construct`, `schema`, and forward-reference APIs; `__fields__`,
      root-model patterns, aliases, strict types, dataclasses, generics, and
      type adapters. Use searches whose no-match exit is tolerated. Separate
      production occurrences from tests and generated templates, but do not
      dismiss tests: they define intended behavior.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Map inheritance, imports, recursive
      references, type aliases, model exports, construction call sites,
      fixtures, alias-based input, serialization consumers, and generated
      schema expectations. Pay special attention to a child model overriding a
      parent field, dictionary aliases used as normal mappings, models exported
      through package `__init__` files, and project configuration models whose
      `Optional` fields were historically omittable. Record which behavior must
      remain stable before changing annotations or configuration.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order work by executable blockers: syntax and import
      failures first, then model configuration and removed field arguments,
      then validation entry points, forward references and special models,
      then semantic failures. Define small coherent slices, each with named
      files, expected behavior, a syntax/import gate, and focused tests.
      Begin executing the first slice in the same turn; do not end after
      presenting the plan.
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

  - name: migrate-model-configuration-safely
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert each nested v1 `Config` deliberately to a
      class-level `model_config = ConfigDict(...)`: map `Extra.allow` to
      `extra="allow"`, `allow_population_by_field_name` to `populate_by_name`,
      and `schema_extra` to `json_schema_extra`. Keep a large schema-example
      dictionary intact inside `ConfigDict`; preserve every brace, bracket,
      comma, and indentation level. Prove the conversion manually on one
      representative file before applying any automation. For repeated files,
      prefer syntax-aware or exact transformations over broad regex. Review
      every changed file and compile it immediately. Remove obsolete `Extra`
      imports only after their final use is gone.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Convert `min_items` and `max_items` to
      `min_length` and `max_length` where equivalent, removed regex options to
      their v2 equivalents, and constants to `Literal`. In Pydantic v2,
      `Optional[T]` without a default is still required: add `= None` only
      where historical constructors, fixtures, configuration parsing, or tests
      establish that omission is allowed. Preserve intentional required
      nullable fields. Preserve aliases and alias-based construction through
      `populate_by_name` where required. Replace mutable model defaults with
      `Field(default_factory=...)` when shared-state avoidance is intended, but
      do not casually alter externally visible defaults.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior." Translate v1 field and root validators to
      `field_validator` and `model_validator` only after understanding mode,
      ordering, values available, defaults, and expected exceptions. Preserve
      each validator's complete function body and observable behavior. Never
      remove decorators, replace bodies with `pass`, return input
      unconditionally, or delete checks merely to restore imports. Add focused
      tests or use existing tests for valid and invalid cases before and after
      each conversion.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Replace `parse_obj` with
      `model_validate`, `dict` with `model_dump`, `json` with
      `model_dump_json`, `copy` with `model_copy`, and `construct` with
      `model_construct` where the receiver is confirmed to be a Pydantic
      model. Preserve flags such as aliases, exclusions, and unset/default
      handling. Do not blindly replace similarly named methods on non-Pydantic
      objects or template helpers. Validate exception handling around
      `ValidationError` and ensure parser error reporting remains unchanged.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Convert schema and field
      introspection APIs to v2 equivalents. Use `model_rebuild()` only on
      Pydantic model classes and only after required names are present in their
      namespace; do not invoke it on aliases such as `Dict[str, PathItem]`.
      Preserve ordinary mapping aliases when callers expect mapping behavior.
      Introduce `RootModel` only when the old code represented a genuine root
      model and adapt all callers deliberately. For recursive models, resolve
      import order and namespaces in the narrowest correct location, then test
      package import and actual model validation rather than adding speculative
      rebuild loops.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      After every single-file edit and every batch transformation, compile the
      changed files with `py_compile` or the affected package with
      `compileall`. Then import the narrowest affected module and, when package
      exports or forward references changed, import the public package. Stop
      the slice immediately on syntax or import failure and repair it before
      editing additional files. Inspect the exact damaged lines and `git diff`;
      never continue a batch while code contains joined field declarations,
      detached `json_schema_extra` assignments, missing commas, unmatched
      delimiters, malformed imports such as `ConfigDict Field`, or broken
      indentation. A successful compile is a gate, not completion.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      Read `references/validation-and-completion.md` and follow "Validate every
      edit slice." After the syntax/import gate, run the closest focused tests
      for the changed behavior, then rerun the previously failing collection or
      test command. Use real command exit codes. If a command is piped for log
      capture, enable `pipefail`. Do not infer passing status from truncated
      output. Continue immediately to the next failing slice rather than
      ending the turn with a progress summary.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the broad non-integration suite without
      output truncation. Group failures by root cause rather than file count.
      Prioritize shared constructor and fixture failures, especially
      Pydantic-v2 required-field errors caused by `Optional` annotations
      without defaults. Fix production semantics first, rerun one
      representative failure, then rerun the group and broad suite.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      Read `references/native-v2-conversions.md` and follow "Investigate v2
      semantic differences." Once removed APIs and import blockers are gone,
      investigate coercion, union selection, enum handling, equality, nested
      validation, alias population, default validation, extras, serialization,
      schema generation, and required-versus-nullable behavior. Compare each
      failure with the pre-migration contract from tests and call sites.
      Prefer the narrowest production change that preserves intended behavior;
      do not globally loosen validation to make failures disappear.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Read `references/validation-and-completion.md` and follow "Repeat
      inventory after collection succeeds." Search again for all v1 APIs,
      deprecated configuration keys, removed field arguments,
      `pydantic.v1`, obsolete imports, stale forward-reference calls, and
      malformed migration remnants. Search production code separately from
      tests and documentation. Investigate every residual production match;
      absence of matches is expected and should not abort the workflow.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Run `git diff --check`, inspect `git diff --stat`, and
      review every changed hunk. Confirm no tests were rewritten merely to
      accept regressions, no function body was emptied or neutralized, no
      production import points to `pydantic.v1`, no broad script damaged
      formatting or schema examples, and no unrelated files or temporary
      migration summaries remain. Compile all changed Python files again.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Run the full authoritative repository suite,
      including integration or end-to-end tests when project configuration
      defines them and the environment supports them. Run it unpiped or with
      `pipefail`; report the exact command, exit code, passed count, failed
      count, skipped count, and any environment-caused exclusions. A suite
      with hundreds of passes and one failure is still a failed migration.
      Continue iterating until the suite exits zero or a genuine external
      blocker is demonstrated.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Read `references/validation-and-completion.md` and follow "Run project
      quality gates." After the complete suite passes, run the repository's
      configured formatter checks, lint, type checks, package/build checks,
      dependency consistency checks, and any generated-file validation.
      Repair migration-caused failures and rerun the affected gate. Do not
      silently reformat or regenerate unrelated files.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Read `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification." Verify the test interpreter imports the intended
      Pydantic v2 version; declared dependencies target v2; lockfiles are
      synchronized or explicitly reported; production contains no
      `pydantic.v1`; no removed v1 field or configuration APIs remain; public
      package imports succeed; representative model validation, aliases,
      serialization, schema generation, recursive references, and configuration
      loading work. Reconfirm that no validator or other function body was
      emptied, bypassed, or replaced with `pass`.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Reconcile final changes with the
      initial working-tree classification so user-owned edits remain intact.
      Walk this procedure and its source migration guidance line by line.
      Classify every distinct source item as Mapped, Schema gap, Body drop, or
      Deliberate drop. For a Schema gap, update the schema and revalidate the
      skill before use; for a Body drop, restore the missing instruction; for a
      Deliberate drop, record the exact item and rationale in
      `source/README.md`. Do not treat this audit as optional and do not
      compress away prior failure knowledge merely to shorten the procedure.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Report changed production and dependency
      areas, the native-v2 conversions made, exact validation commands and
      outcomes, full-suite counts, quality-gate results, residual warnings,
      lockfile status, and any tests that could not run for external reasons.
      State completion only after the complete authoritative suite and required
      gates pass. Keep the final report concise, but never substitute the
      report for unfinished edits or validation.
    outputs:
      - name: migration-report
        type: object
```