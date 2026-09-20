---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use when a Pydantic v2 upgrade causes import, collection, syntax, validation, schema, fixture, constructor, alias, forward-reference, root-model, serialization, dependency, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 23
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b"
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
  - Before beginning any migration step, read `references/migration-guardrails.md` and avoid every anti-pattern listed there throughout the migration
  - Never re-point production imports to `pydantic.v1`, even temporarily as the submitted solution
  - Never empty, delete, bypass, replace with `pass`, or otherwise neutralize a validator, serializer, parser, constructor, function, or method merely to make imports or tests pass
  - Never rewrite or weaken tests merely to accept a production regression; change tests only when the task explicitly requires a legitimate public-contract update
  - Never claim success from an import check, compilation, collection, one focused test, a truncated test log, or a partially passing suite
  - Never pipe the authoritative test command through `head`, `tail`, `grep`, or a pipeline that masks its exit status; capture output separately while preserving the real command status
  - Never run broad regex, `sed`, or generated migration scripts over many source files without reviewing the proposed diff and compiling every changed file immediately afterward
  - Never continue editing additional files while any changed file has a syntax error, malformed import, unmatched delimiter, broken indentation, or invalid model configuration
  - Never install or replace package managers, regenerate lockfiles, or mutate the environment before identifying the repository's declared target and authoritative dependency workflow
  - Never convert a dictionary-like type alias to `RootModel` without checking every consumer for mapping operations and exact type expectations
  - Never call `model_rebuild()` indiscriminately on non-model aliases or before the complete forward-reference namespace is available
  - Never modify files outside the repository because of a mistyped path; verify the repository root before every scripted or batch edit

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the actual repository root with both the current
      directory and repository metadata, record Python and installed Pydantic
      versions, inspect the top-level layout, and run `git status --short`.
      Use one verified root path consistently; do not alternate among guessed
      paths such as similarly named home directories.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Treat existing changes as potentially valuable but
      potentially malformed. Inspect `git diff`, compile all modified Python
      files, and distinguish user-authored changes from failed migration edits.
      Preserve unrelated work. Revert only a specifically damaged file or
      hunk when its original is available and doing so will not discard valid
      user work. Do not layer a new batch migration over syntactically broken
      generated edits.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands." Inspect project metadata, CI workflows,
      task definitions, contributor documentation, test configuration, and
      lockfiles. Record the authoritative test command, focused-test form,
      formatter, linter, type checker, dependency manager, supported Python
      range, and whether integration or end-to-end suites are part of the
      required gate. Do not assume Poetry, tox, taskipy, or a particular pytest
      invocation merely because its configuration exists.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the
      unpiped baseline." Run the authoritative command directly and preserve
      its actual exit status. If output must be retained, redirect it to a file
      or use a mechanism with pipe-failure propagation, then inspect the file
      separately. Record the complete first traceback, collection status,
      number of collected and passing tests, warnings, and failure phase.
      A shell command ending successfully because `head`, `tail`, or `tee`
      succeeded is not a valid baseline.
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
      const collection blocker." Replace each constant field with a correctly
      typed `Literal[...]` field while preserving its default, alias, enum
      semantics, and constructor behavior. For example, use a literal empty
      string for a fixed header name and a literal enum member for a fixed
      parameter location. Do not turn validated constant fields into
      `ClassVar`, because that removes them from model input, validation, and
      serialization. Compile and import the affected module immediately.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine the intended Pydantic v2 range from the task,
      dependency files, supplied post-migration requirements, CI, and Python
      support policy. Inspect direct and transitive compatibility constraints,
      including plugins and frameworks. Record every declaration and lockfile
      that must agree; do not choose a version solely from the currently
      installed environment.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Use the repository's intended dependency workflow
      or a supplied migration requirements file. Verify the imported Pydantic
      version after synchronization. Update direct dependency metadata and its
      lockfile together when the repository requires both, but avoid unrelated
      dependency churn. Do not install a package manager merely to run a test
      if the active environment already supports the authoritative command.
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
      complete Pydantic surface." Search production code, package exports,
      generators, tests, fixtures, examples, templates, and dependency files.
      Inventory imports; `BaseModel` subclasses; nested `Config`; `Extra`;
      `schema_extra`; aliases; validators; dataclasses; generic models; root
      models; constrained and strict types; field arguments such as `const`,
      `min_items`, `max_items`, and `regex`; `parse_obj`, `from_orm`, `dict`,
      `json`, `copy`, `construct`, `schema`, and forward-reference APIs;
      `__fields__` introspection; validation errors; type aliases containing
      forward references; mutable defaults; and constructors that omit
      `Optional` fields. Treat grep exit code 1 for no matches as information,
      not as a migration failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace model imports and package
      re-exports, recursive references, type aliases, inheritance, aliases,
      schema examples, parser entry points, and downstream mapping or sequence
      operations. Inspect tests and fixtures to determine whether omitted
      values are intended to default, whether models accept field names as well
      as aliases, whether extra fields are retained, and whether aliases such
      as `Paths`, `Responses`, `Callback`, or security requirement mappings
      must remain ordinary dictionaries. Record behavior before selecting a v2
      representation.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order changes into small runnable slices: collection
      blockers; model configuration; field semantics and defaults; validators;
      parsing and serialization APIs; recursive aliases and model rebuilding;
      dependency metadata; then residual warnings and behavior failures.
      Name the files and focused checks for each slice. Begin executing the
      first slice in the same turn; do not end after producing a plan.
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
      configuration safely." Convert nested `Config` to `model_config =
      ConfigDict(...)`, preserving all behavior in one syntactically complete
      expression. Convert `Extra.allow`, `Extra.ignore`, and `Extra.forbid` to
      their string forms; `allow_population_by_field_name` to
      `populate_by_name`; `schema_extra` to `json_schema_extra`; and other
      renamed settings according to native v2 semantics. Keep large schema
      examples inside `json_schema_extra`, not as detached class assignments.
      Review each file individually. Immediately compile and inspect the diff
      after each file or tightly related batch.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Replace removed field arguments with v2
      equivalents, including `min_items` and `max_items` with `min_length` and
      `max_length`, and `regex` with `pattern` where applicable. Preserve
      aliases and constraints. In v2, `Optional[T]` without a default remains
      required; add `= None` only where prior constructors, fixtures, schema
      behavior, or tests establish that omission is allowed. Replace mutable
      model defaults with `Field(default_factory=...)` where independent
      instances are intended. Use `Literal` for validated constants rather
      than `ClassVar`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior." Translate field and root validators to
      `field_validator` and `model_validator` with the correct mode, input
      shape, ordering, defaults, and return value. Preserve every branch and
      error condition. If a validator depends on v1 coercion or ordering,
      reproduce the intended behavior explicitly and add or run a focused
      regression test. Never delete, empty, bypass, replace with `pass`, or
      neutralize a validator or any other function body to satisfy imports or
      tests.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Prefer native v2 APIs such as
      `model_validate`, `model_validate_json`, `model_dump`,
      `model_dump_json`, `model_copy`, `model_construct`, and
      `model_json_schema`. Import `ValidationError` from its supported v2
      location. Preserve options including aliases, excluded unset values,
      JSON mode, and ORM or attribute validation. Update production call sites
      first; deprecation warnings in tests may identify additional public
      compatibility expectations rather than permission to change behavior.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Convert field introspection and
      forward-reference APIs carefully. Use `RootModel` only for genuine root
      models whose consumers accept a model wrapper. Preserve ordinary mapping
      aliases when callers iterate, index, call `.items()`, or require a
      dictionary. For recursive aliases and exported models, ensure every
      referenced symbol is imported before rebuilding, then use
      `model_rebuild()` with an explicit `_types_namespace` when needed.
      Never invoke model methods on plain typing aliases. Import the public
      package after changing exports or rebuild order.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      Enforce this gate during every preceding and subsequent edit step, not
      only after all migration edits. After every single-file edit and every
      batch transformation, compile changed files with `py_compile` or the
      affected package with `compileall`. Then import the narrowest affected
      module and, when package exports or forward references changed, import
      the public package. Stop the slice immediately on syntax or import
      failure and repair it before editing additional files. Inspect the exact
      damaged lines and `git diff`; never continue while code contains joined
      field declarations, detached `json_schema_extra` assignments, missing
      commas, unmatched delimiters, malformed imports such as `ConfigDict
      Field`, truncated imports, or broken indentation. A successful compile
      is a gate, not completion.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      Read `references/validation-and-completion.md` and follow "Validate every
      edit slice." Run the smallest focused test that exercises the changed
      behavior, then the affected module or package tests. Preserve real exit
      status and inspect full tracebacks. If the focused test fails, repair the
      current slice before broadening scope. Do not count a command as passing
      merely because its output was truncated or its final pipeline process
      exited successfully.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run an untruncated suite and group failures by
      root cause rather than file count. Prioritize shared causes such as v2
      required-optionality changes, missing defaults in configuration models,
      alias population, unresolved forward references, dictionary aliases
      incorrectly converted to models, changed error locations, or
      serialization differences. Fix production behavior at the shared source
      and rerun one representative failure before the suite.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      Read `references/native-v2-conversions.md` and follow "Investigate v2
      semantic differences." Pay particular attention to required versus
      nullable fields, enum and union selection, strict types, equality,
      coercion, alias handling, extra fields, validation error locations,
      serialization mode, custom schema generation, and recursive type
      resolution. Reproduce uncertain behavior with a minimal local example
      using the installed target version, then apply the result to the
      repository's established contract.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Read `references/validation-and-completion.md` and follow "Repeat
      inventory after collection succeeds." Search again for all original v1
      patterns plus malformed migration artifacts, deprecated production APIs,
      `pydantic.v1`, removed field keywords, old configuration names, old
      forward-reference calls, and accidental `ClassVar` substitutions.
      Compare results with the initial inventory and account for every
      remaining match.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review `git diff --check`, changed-file status, the
      complete diff, and generated dependency changes. Look for accidental
      test edits, unrelated files, helper scripts left in the repository,
      malformed formatting, duplicated configuration, fields lost from
      models, neutralized functions, broad replacement damage, and files
      created outside the repository. Recompile all changed Python files after
      cleanup.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Run the authoritative suite without output
      truncation or status-masking pipelines. Record the exact command, exit
      code, collection count, passed count, skipped count, warnings, and
      failures. If the repository distinguishes unit, integration, or
      end-to-end suites, run every required suite or explicitly report any
      environment-blocked gate. Do not declare completion while any required
      suite fails.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Read `references/validation-and-completion.md` and follow "Run project
      quality gates." Run the repository's formatter check, linter, type
      checker, package build, generated-file checks, or equivalent CI gates.
      Apply formatting only through the project's configured tools and review
      resulting changes. Re-run affected tests after any quality-gate fix.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Read `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification." Confirm the runtime imports the intended v2
      version, dependency metadata and lockfiles agree, no production import
      references `pydantic.v1`, no removed v1 field or config APIs remain, no
      function body was emptied or neutralized, package imports succeed, and
      representative construction, alias, validation, serialization, schema,
      recursive-model, and mapping-alias behaviors work. The migration is not
      valid if tests are green only because production behavior or tests were
      weakened.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Walk the initial inventory,
      baseline failures, migration plan, source requirements, and every
      procedure step line by line. Classify each distinct item as mapped to a
      verified change, a genuine schema or tooling gap, a missed body or
      implementation item requiring correction, or a deliberate non-applicable
      item with rationale. Confirm all planned slices and outputs have evidence
      and that no source requirement disappeared during compression or
      rewriting.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Summarize production and dependency changes,
      behavioral compatibility decisions, exact validation commands and
      results, total passing tests, quality-gate results, residual warnings,
      and any environment-blocked checks. State completion only when the full
      required suite and native-v2 verification pass. Never report success
      based on intent, edits made, compilation alone, collection alone, or an
      incomplete test run.
    outputs:
      - name: migration-report
        type: object
```