---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 13
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e"
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
  - Redirecting imports to `pydantic.v1`; this is not a native Pydantic v2 migration and is rejected even if tests pass
  - Emptying, deleting, bypassing, replacing with `pass`, or otherwise neutralizing a validator or any function body merely to make imports or tests pass
  - Ending work after inventory, research, a plan, an import check, test collection, focused tests, or a partially passing suite
  - Running a test command through `head`, `tail`, or another pipeline and trusting the pipeline's zero status instead of the test process's real exit status
  - Treating `grep` exit status 1 for no matches as a migration failure rather than an expected search result
  - Repeatedly researching standard v2 replacements after the repository and traceback already establish the required conversion
  - Making a repository-wide regex or generated-script rewrite without first testing it on one representative file and reviewing its exact diff
  - Continuing after an edit without a syntax check, especially after changing multiline `ConfigDict` or `json_schema_extra` expressions
  - Assuming successful compilation proves imports, model construction, validation semantics, or forward references are correct
  - Assuming successful imports or collection prove the migration is complete
  - Installing unrelated tooling or replacing the project environment before inspecting the repository's supplied dependency and test instructions
  - Overwriting or reverting pre-existing user changes without identifying their provenance and preserving them
  - Repeatedly mistyping the repository path or constructing paths from memory instead of using the confirmed root
  - Converting `Optional[T]` mechanically without deciding whether the field is nullable, omittable, or both
  - Replacing mutable defaults mechanically without preserving construction and serialization behavior
  - Calling `model_rebuild()` blindly on every exported symbol, including type aliases that are not Pydantic models
  - Adding forward-reference rebuild calls without supplying the namespace needed to resolve aliases and recursively related models
  - Updating only production code when fixtures, tests, generators, or public compatibility behavior also encode Pydantic semantics
  - Declaring completion while deprecated v1 APIs, malformed edits, warnings that indicate ignored configuration, or unreviewed diffs remain

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the root with `pwd`, inspect repository files,
      record Python and installed Pydantic versions, and run `git status
      --short`. Use the confirmed root for every later command rather than
      retyping an assumed absolute path.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Inspect `git diff`
      before editing. Classify modifications as pre-existing user work, a prior
      migration attempt, or generated noise. Preserve user work. For prior
      migration edits, compile changed Python files immediately and repair the
      first syntax error before making further semantic changes. Do not reset a
      file merely because it is difficult to repair unless its changes are
      known to belong solely to the failed migration and the useful behavior is
      reconstructed afterward.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`. Inspect `pyproject.toml`, lock files,
      requirements files, task definitions, CI workflows, contributor
      instructions, and test configuration. Prefer the repository's supplied
      post-migration dependency set when one exists. Do not install Poetry or
      other tooling merely because it is mentioned if direct project commands
      are already available.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`. Activate or install the intended
      Pydantic v2 dependency set first when the active environment is still on
      v1, then verify the imported version. Run the authoritative baseline
      command without `head`, `tail`, or a status-masking pipeline. If output
      must be captured, use `tee` with `pipefail` or inspect `PIPESTATUS`.
      Record the actual test-process exit code and complete first traceback.
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
      omit it. Update imports, compile the edited file, run the smallest
      collection or import check that reaches it, and then return to the full
      inventory rather than repeatedly researching the same documented change.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`. Determine supported Python versions,
      the intended Pydantic v2 range, dependency and lock files that must agree,
      generated-code constraints, public compatibility requirements, and
      whether warnings are treated as errors. Do not widen or narrow dependency
      bounds without repository evidence.
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
      construction. Treat no-match searches as useful inventory results.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`. Map inheritance, recursive models,
      aliases, type aliases, module import order, forward references, generated
      schemas, extra-field behavior, fixture construction, and public parsing
      and serialization expectations. For every `Optional` field, distinguish
      nullable from omittable. Record tests that define constant-field,
      version-validation, alias-population, extra-field, default, and schema
      behavior before changing them.
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
      must name the files, expected behavior, syntax command, focused test, and
      rollback or repair strategy. Begin executing immediately; do not end a
      turn after merely presenting the plan.
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
      requires them. Remove obsolete `Extra` imports only after all uses are
      converted. For multiline schema examples, preserve every delimiter and
      place the closing parenthesis before leaving the file. Migrate one
      representative model first, compile it, inspect its diff, and only then
      repeat the verified shape. Never trust a bulk rewrite that reports files
      changed without compiling and reviewing them.
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
      with native v2 equivalents such as `Literal` for constants and
      `min_length` or `max_length` for collection lengths. Preserve required,
      omitted, nullable, alias, and default semantics deliberately. In v2,
      `Optional[T]` without a default remains required; add `= None` only when
      omission was valid behavior. Replace mutable defaults with
      `Field(default_factory=...)` where appropriate and verify construction,
      equality, and serialization tests rather than applying this mechanically.
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
      ordering, pre/post mode, reuse, values access, error type, and mutation
      behavior. Preserve function bodies and externally observed errors.
      Where a constrained `Literal` changes the kind or timing of an error,
      retain any custom compatibility behavior required by tests. Never make a
      validator empty, replace it with `pass`, delete it, or bypass it to
      achieve a green import or suite.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Convert model parsing to native v2
      entry points such as `model_validate`, and migrate serialization,
      copying, construction, and schema calls where the old API is actually
      exercised. Preserve aliases, exclusion flags, JSON behavior, exception
      handling, and return types. Do not change similarly named non-Pydantic
      methods or template methods found by broad text search.
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
      and cross-module forward references with `model_rebuild()` after the
      relevant symbols are imported. Rebuild only actual Pydantic model
      classes, not aliases such as dictionaries or unions, and pass an explicit
      type namespace when aliases cannot otherwise resolve. Test the import
      order used by the package, not only direct module imports.
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
      file; a syntax failure blocks all further migration work. Then import the
      affected package path, run the narrowest relevant tests, and inspect
      `git diff --check` plus the exact slice diff. Repair the first failure and
      repeat until the slice is syntactically valid and behaviorally focused.
      This gate is mandatory after scripted, regex, or multiline configuration
      edits because a single unclosed `ConfigDict(` prevents all collection.
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
      optionality/default regressions, validation differences, serialization,
      and schema differences. Use a representative failing test to verify each
      fix before rerunning the broader group.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Compare
      v1-intended behavior with v2 behavior for optional-but-required fields,
      coercion, unions, strict types, equality, extras, aliases, defaults,
      validator ordering, error locations, schema generation, and serialization.
      Fix the model or compatibility boundary rather than weakening assertions
      unless repository evidence shows the expected behavior intentionally
      changed.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`. Rerun the v1-surface searches
      after imports and collection work. Classify every remaining hit as a
      required migration, a non-Pydantic false positive, an intentional public
      compatibility reference, or documentation that must be updated. Remove
      unused compatibility imports and verify that no production import points
      to `pydantic.v1`.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`. Review every changed file and
      `git diff --check`. Look specifically for missing commas, malformed
      imports, unclosed configuration expressions, duplicated or misplaced
      `model_config`, lost schema examples, accidentally deleted methods,
      neutralized function bodies, unrelated formatting churn, mutable default
      changes, and dependency files that disagree. Recompile all changed Python
      files after review.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the complete authoritative
      suite with the intended Pydantic v2 environment and any repository-required
      environment variables. Do not truncate output in a way that masks status.
      If integration tests are separately configured, run or explicitly account
      for them according to project instructions. A large passing subset is not
      completion; continue until the full suite exits successfully.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's formatter
      check, import sorter check, linter, type checker, compile gate, packaging
      or generation checks, and warning-sensitive commands where configured.
      Fix migration-caused failures and rerun the affected gate plus the full
      suite when code changes.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`. Confirm the runtime imports the
      intended v2 version; no production import uses `pydantic.v1`; no removed
      v1 configuration or APIs remain unintentionally; no function body was
      emptied or neutralized; changed files compile; package imports work from
      the public entry point; representative construction, parsing,
      serialization, schema, alias, extra-field, and recursive-model behavior
      works; and the complete suite and quality gates pass.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`. Walk the baseline evidence,
      migration inventory, behavior map, prior failed edits, and this procedure
      line by line. Classify every distinct item as Mapped, Schema gap, Body
      drop, or Deliberate drop. Repair every Schema gap or Body drop before
      completion, and record a concrete rationale for each Deliberate drop.
      Verify that all original 24 procedure steps remain represented and that
      newly learned syntax, environment, optionality, and forward-reference
      safeguards are included.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`. Report the installed Pydantic
      version, dependency changes, principal native-v2 conversions, syntax and
      import checks, focused tests, complete suite command and result, quality
      gates, residual-inventory result, and any limitations. Do not claim
      completion from collection or a subset. Keep the working tree free of
      temporary migration scripts and unsolicited summary files unless the
      repository explicitly requires them.
    outputs:
      - name: migration-report
        type: object
```