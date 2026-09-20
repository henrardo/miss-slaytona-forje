---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 15
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, forward references, and repository tests preserve intended
  behavior. Complete the migration without redirecting imports to `pydantic.v1`;
  without deleting, emptying, bypassing, replacing with `pass`, or neutralizing
  validators or any other function bodies; without corrupting source through
  broad mechanical edits; and without stopping after searches, research,
  investigation, planning, an import check, test collection, or a partially
  passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models
  - Models import successfully under Pydantic v2 but constructors, fixtures, schemas, or behavioral tests fail
  - Most tests pass after an upgrade but a shared model, fixture, forward reference, or optionality regression still causes failures

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning any migration step, read `references/migration-guardrails.md` and avoid every anti-pattern listed there throughout the migration.
  - Never re-point production imports to `pydantic.v1`; that is compatibility deferral, not a native-v2 migration.
  - Never empty, delete, bypass, replace with `pass`, or otherwise neutralize a validator or any function body merely to make imports or tests pass.
  - Do not end a turn after inventory, research, planning, or announcing the next edit; execute the next safe action in the same turn.
  - Do not claim success from an import check, successful collection, focused tests, or a large passing subset when the authoritative suite has not passed.
  - Do not pipe test output through `head` or `tail` without preserving the test process exit status; a successful pipeline status can conceal a failed suite.
  - Do not install Poetry or another package manager merely because configuration mentions it when the repository already supplies usable direct commands.
  - Do not run unreviewed repository-wide regex, `sed`, or generated rewrite scripts across multiline model configuration.
  - Do not treat a rewrite script's changed-file count as proof of correctness; compile and inspect every affected file.
  - Do not reset modified files before determining whether they contain pre-existing user work.
  - Do not alter tests to conceal migration regressions unless repository evidence establishes an intentional behavior change.
  - Do not call `model_rebuild()` on type aliases, dictionaries, unions, or other objects that are not Pydantic model classes.
  - Do not leave temporary migration scripts, unsolicited reports, or generated noise in the working tree.

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the root with `pwd`, inspect repository files,
      record Python and installed Pydantic versions, and run `git status
      --short`. Use the confirmed root or repository-relative paths for every
      later command rather than repeatedly typing an assumed absolute path;
      path typos have caused edits and checks to target nonexistent directories.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Inspect `git diff`
      before editing. Classify modifications as pre-existing user work, a prior
      migration attempt, or generated noise. Preserve user work. For prior
      migration edits, compile all changed Python files immediately and repair
      the first syntax error before making further semantic changes. Inspect
      malformed imports, missing commas, unclosed `ConfigDict(` calls, duplicated
      configuration, and misplaced closing delimiters. Do not reset a file
      merely because it is difficult to repair unless its changes are known to
      belong solely to the failed migration and all useful behavior is
      reconstructed afterward.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`. Inspect `pyproject.toml`, lock files,
      requirements files, task definitions, CI workflows, contributor
      instructions, pytest configuration, and environment-variable checks.
      Prefer a supplied post-migration requirements file when one exists. Record
      required variables such as task-runner guards rather than mistaking their
      absence for a migration failure. Use direct project commands when they
      work; do not install Poetry or other tooling merely because it is
      mentioned in configuration.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`. Activate or install the intended
      Pydantic v2 dependency set first when the active interpreter still imports
      v1, then immediately verify the version using that same interpreter.
      Recheck after dependency operations because package installation can
      silently replace the active Pydantic version. Run the authoritative
      baseline command without `head`, `tail`, or a status-masking pipeline. If
      output must be captured, enable `pipefail`, use `tee`, and inspect the
      underlying process status. Record the actual exit code, collection count,
      passing count, and complete first traceback.
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
      follow "Act immediately on a const collection blocker" in
      `references/safety-and-baseline.md`. Replace the constant field with an
      accurately typed `Literal[...]` and preserve its default when callers may
      omit it. For enum constants, use the actual enum member in the `Literal`,
      not a lookalike string. Update imports, compile the edited file, run the
      smallest collection or import check that reaches it, and return to the
      complete inventory rather than repeatedly researching the same documented
      change.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`. Determine supported Python versions,
      the intended Pydantic v2 range, dependency and lock files that must agree,
      generated-code constraints, public compatibility requirements, warning
      policy, and whether integration tests are separate. Do not widen or
      narrow dependency bounds without repository evidence. Update all
      authoritative dependency declarations and lock artifacts required by the
      project rather than leaving metadata that still resolves Pydantic v1.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      Follow "Inventory the complete Pydantic surface" in
      `references/safety-and-baseline.md`. Search production code, tests,
      fixtures, generators, templates, and documentation-backed examples for
      Pydantic imports and v1 constructs. Include `Extra`, nested model
      `Config`, `schema_extra`, `allow_population_by_field_name`, `orm_mode`,
      `validate_all`, `Field(const=...)`, `min_items`, `max_items`,
      `unique_items`, `regex`, validators, root validators, `parse_obj`,
      `parse_raw`, `from_orm`, `dict`, `json`, `copy`, `construct`, `schema`,
      `__fields__`, `__fields_set__`, forward-reference updates, root models,
      dataclasses, generic models, aliases, strict types, and direct model
      construction. Distinguish the project's own classes named `Config` and
      non-Pydantic methods from Pydantic APIs. Treat a no-match grep exit as a
      useful inventory result rather than a task failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`. Map inheritance, recursive models,
      aliases, type aliases, module import order, forward references, generated
      schemas, extra-field behavior, fixture construction, public parsing and
      serialization expectations, and package-level re-exports. For every
      `Optional` field, distinguish nullable from omittable. Record tests that
      define constant-field, version-validation, alias-population, extra-field,
      default, equality, error-type, and schema behavior before changing them.
      Pay special attention to shared configuration models used broadly in
      fixtures: one requiredness regression can produce hundreds of failures.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Follow "Form an executable slice plan" in
      `references/safety-and-baseline.md`. Order work into small coherent
      slices: restore syntax, unblock collection, migrate shared configuration,
      migrate fields and validators, migrate entry points and serialization,
      resolve forward references, then fix semantic regressions. Each slice
      must name files, expected behavior, syntax command, focused test, and
      rollback or repair strategy. Start with one representative model before
      repeating a conversion shape. Begin executing immediately; do not end a
      turn after merely presenting the plan or saying that the next action will
      migrate files.
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
      configuration safely." Convert nested model `Config` settings to
      `model_config = ConfigDict(...)`, including `extra='allow'`,
      `populate_by_name=True`, and `json_schema_extra=...` where behavior
      requires them. Keep the configuration inside the intended model and
      preserve complete multiline schema examples. Remove obsolete `Extra`
      imports only after all uses are converted. For multiline examples,
      preserve every brace, bracket, comma, and parenthesis and place the
      closing `ConfigDict` parenthesis before leaving the file. Migrate one
      representative model first, compile it, inspect its exact diff, and only
      then repeat the verified shape. Never trust a bulk rewrite that reports
      files changed without compiling and reviewing every changed file.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Follow "Migrate fields, annotations, and optionality" in
      `references/native-v2-conversions.md`. Replace removed field constraints
      with native-v2 equivalents such as `Literal` for constants and
      `min_length` or `max_length` for collection lengths. Preserve required,
      omitted, nullable, alias, and default semantics deliberately. In v2,
      `Optional[T]` without a default remains required; add `= None` when
      omission was valid behavior, especially for shared configuration fields
      and fixture-constructed models. Replace mutable defaults with
      `Field(default_factory=...)` where appropriate, but verify construction,
      equality, isolation, and serialization instead of applying the rewrite
      mechanically. Do not confuse an OpenAPI property named `minItems` with
      the Pydantic constraint argument `min_items`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Follow "Migrate validators without erasing behavior" in
      `references/native-v2-conversions.md`. Translate v1 validators to
      `field_validator` or `model_validator` only after documenting their
      ordering, pre/post mode, reuse, values access, error type, mutation
      behavior, and interaction with defaults. Preserve function bodies and
      externally observed errors. Where a `Literal` changes the kind or timing
      of an error, retain custom compatibility behavior required by repository
      tests, such as explicit version validation. Never make a validator empty,
      delete it, replace it with `pass`, return unvalidated input solely to
      bypass behavior, or otherwise neutralize it to obtain a green import or
      suite.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Convert model parsing to native-v2
      entry points such as `model_validate`, and migrate serialization,
      copying, construction, and schema calls where the old API is actually
      exercised. Preserve aliases, exclusion flags, JSON behavior, exception
      handling, return types, and error conversion at public boundaries. Do not
      change similarly named non-Pydantic methods or Jinja template methods
      found by broad text search. Prefer native-v2 APIs rather than leaving
      deprecated calls merely because compatibility shims still execute.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Follow "Migrate schema, introspection, and special models" in
      `references/native-v2-conversions.md`. Update model field introspection,
      root models, dataclasses, generics, strict types, private attributes, and
      generated JSON schema only where inventory shows them. Resolve recursive
      and cross-module forward references with `model_rebuild()` after relevant
      symbols and package exports are imported. Rebuild only actual Pydantic
      model classes, never aliases such as dictionaries, unions, callbacks,
      paths, responses, or security-requirement mappings. Supply an explicit
      type namespace when imported aliases cannot otherwise resolve. Test the
      package's normal import order and public entry point, not only isolated
      direct-module imports.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After every coherent edit, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." First run `py_compile` or `compileall` on every changed Python
      file; a syntax failure blocks all further semantic migration. Then import
      the affected package path, run the narrowest relevant tests, and inspect
      `git diff --check` plus the exact slice diff. Repair the first failure and
      repeat until the slice is syntactically valid and behaviorally focused.
      This gate is mandatory after scripted, regex, import-list, or multiline
      configuration edits because a missing comma or unclosed `ConfigDict(`
      prevents collection and obscures all later behavior.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the relevant suite unpiped and group failures
      by shared cause instead of editing tests one at a time. Prioritize shared
      configuration and construction failures, then forward references,
      optionality/default regressions, custom version validation, aliases,
      validation differences, serialization, and schema differences. Use one
      representative failing test to verify each fix before rerunning the
      broader failure group. Record actual passing and failing counts rather
      than treating collection as success.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Compare
      v1-intended behavior with v2 behavior for optional-but-required fields,
      coercion, unions, strict types, equality, extras, aliases, defaults,
      validator ordering, error classes and locations, schema generation, and
      serialization. Fix the model or compatibility boundary rather than
      weakening assertions unless repository evidence shows the expected
      behavior intentionally changed. Use fixture failures as evidence about
      public construction semantics, not as an invitation to edit fixtures
      indiscriminately.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`. Rerun the complete v1-surface
      searches after imports and collection work. Classify every remaining hit
      as a required migration, a non-Pydantic false positive, an intentional
      public compatibility reference, or documentation that must be updated.
      Remove unused compatibility imports and verify explicitly that no
      production import points to `pydantic.v1`. Search for emptied or
      neutralized function bodies as well as deprecated APIs.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`. Review every changed file and
      run `git diff --check`. Look specifically for missing commas, malformed
      imports, unclosed configuration expressions, duplicated or misplaced
      `model_config`, lost schema examples, accidentally deleted methods,
      emptied or neutralized function bodies, unrelated formatting churn,
      mutable-default changes, temporary files, and dependency files that
      disagree. Recompile all changed Python files after review. If a mechanical
      rewrite touched many files, inspect each resulting configuration block
      rather than sampling only one.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the complete authoritative
      suite with the intended Pydantic v2 interpreter and every
      repository-required environment variable. Do not truncate output in a way
      that masks status, and verify the actual process exit code. If integration
      tests are separately configured, run them or explicitly account for them
      according to project instructions. A large passing subset, including
      hundreds of passing tests, is not completion; continue until the full
      authoritative suite exits successfully.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's formatter
      check, import sorter check, linter, type checker, compile gate, packaging
      or generation checks, and warning-sensitive commands where configured.
      Distinguish unavailable optional tooling from a failing configured gate.
      Fix migration-caused failures and rerun the affected gate plus the full
      suite whenever code changes.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`. Confirm the runtime imports the
      intended v2 version; dependency metadata agrees; no production import
      uses `pydantic.v1`; no removed v1 configuration or APIs remain
      unintentionally; no validator or other function body was emptied,
      deleted, bypassed, replaced with `pass`, or neutralized; changed files
      compile; package imports work from the public entry point; representative
      construction, omitted optional fields, parsing, serialization, schema,
      alias, extra-field, version-validation, and recursive-model behavior
      works; and the complete suite and quality gates pass.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`. Walk the baseline evidence,
      migration inventory, behavior map, prior failed edits, source procedure,
      and execution trace line by line. Classify every distinct item as Mapped,
      Schema gap, Body drop, or Deliberate drop. Repair every Schema gap or Body
      drop before completion, and record a concrete rationale for every
      Deliberate drop. Verify that all original 24 procedure steps remain
      represented and that learned safeguards for syntax recovery, active
      environment drift, truthful pipeline status, shared optional defaults,
      custom version validation, package import order, and forward-reference
      type namespaces are included.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`. Report the installed Pydantic
      version, dependency changes, principal native-v2 conversions, syntax and
      import checks, focused tests, complete suite command with exit status and
      counts, quality gates, residual-inventory result, native-v2 guardrail
      checks, and any limitations. Do not claim completion from collection or a
      subset. Keep the working tree free of temporary migration scripts,
      temporary inventory files, and unsolicited summary documents unless the
      repository explicitly requires them.
    outputs:
      - name: migration-report
        type: object
```