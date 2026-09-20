---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 11
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213"
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
  - Most tests pass after an upgrade but a shared model, fixture, or optionality regression still causes failures

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - >
    Before beginning migration work, read
    `references/safety-and-baseline.md` for the mandatory instructions governing
    repository setup, recovery, baseline testing, project constraints, initial
    blocker handling, inventory, behavior mapping, and executable planning.
  - Re-pointing application imports to `pydantic.v1`; this is not a native Pydantic v2 migration and is rejected even if every test passes
  - Emptying, replacing with `pass`, deleting, or otherwise neutralizing a validator or any function body merely so the module imports
  - Ending a turn after investigation, research, inventory, or planning without making and validating the next safe edit
  - Claiming the task is complete without actually editing the repository
  - Treating successful import, compilation, collection, or 310 passing tests as completion while any test still fails or errors
  - Piping the authoritative test command through `head`, `tail`, `grep`, or another command that masks pytest's nonzero exit status
  - Using `tee` without `set -o pipefail` and then trusting the pipeline exit status
  - Running a test command with output truncation and interpreting shell exit code 0 as a passing suite
  - Using broad regular-expression, shell-loop, or generated-script rewrites across nested `Config` classes or large schema-example literals without reviewing every resulting diff
  - Inserting punctuation or configuration delimiters by guessed line number in a large Python literal
  - Continuing bulk edits after compilation fails instead of restoring the affected file or repairing it from a reviewed diff
  - Mixing a new `model_config` assignment with a legacy nested `class Config` on the same model
  - Moving `schema_extra` outside configuration or damaging its nested dictionary while converting it to `json_schema_extra`
  - Assuming `Optional[T]` supplies a default in Pydantic v2; without `= None`, the field remains required
  - Migrating only the first import-time error and failing to re-inventory the repository after collection succeeds
  - Running only narrow tests after a migration that changes validation semantics shared by many models
  - Reverting or overwriting pre-existing user changes merely to obtain a clean working tree
  - Installing or replacing project tooling, lock files, or dependencies before checking the repository's existing environment and authoritative commands
  - Suppressing deprecation warnings instead of replacing deprecated v1 APIs where the task requires native v2
  - Assuming test-only use of a v2 API is irrelevant; tests are behavioral evidence and may reveal expected construction semantics
  - Repeatedly searching for known patterns without converting them and validating the conversion
  - Declaring success without checking dependency metadata, residual v1 APIs, the complete suite, and project quality gates

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the real repository root once, use that exact path
      consistently, inspect `git status --short`, record the current branch and
      pre-existing tracked or untracked changes, and identify the active Python
      and Pydantic versions. Do not guess similar paths such as `agent-worm`
      versus `agent-warm`. Do not treat skill or harness files as application
      changes.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Determine which
      changes predate this attempt and which are remnants of an incomplete
      migration. Compile modified Python files and inspect their diffs before
      building on them. Preserve valid user changes. If a prior broad rewrite
      malformed a file, restore only that file or hunk when provenance permits;
      never reset the whole working tree. Re-run status and compilation after
      recovery.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`. Inspect `pyproject.toml`, lock files,
      requirements files, tox/nox configuration, Makefiles, CI workflows, and
      repository documentation. Prefer the already provisioned environment.
      Do not install Poetry or regenerate a lock file merely because a command is
      unavailable; use the equivalent existing command unless the project
      explicitly requires installation. Record the full-suite, focused-test,
      compile, lint, formatting, and type-check commands.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`. Run the authoritative suite directly
      and preserve its real exit status. If output must be captured, redirect it
      to a file and inspect the file afterward, or use `set -o pipefail` with
      `tee`; never use `pytest ... | head` as the authoritative run. Record
      collection status, pass/fail/error counts, warnings, and the complete first
      traceback. A shell exit code from `head`, `tail`, or `tee` is not pytest's
      result.
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
      `references/safety-and-baseline.md`. Replace each constant field with an
      accurately typed `Literal[...]` annotation and its intended default. For
      example, preserve both the accepted value and default rather than merely
      deleting `const=True`. Search for every occurrence, edit the smallest
      affected model, compile it, import it, and run its focused tests before
      continuing.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`. Determine supported Python versions,
      the intended Pydantic v2 range, whether a post-migration requirements file
      or merge artifact defines the target, and whether dependency metadata and
      lock files must change. Do not arbitrarily broaden the dependency to a
      different range. Record compatibility constraints before using syntax such
      as `Literal`, newer unions, or version-specific `ConfigDict` keys.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      Follow "Inventory the complete Pydantic surface" in
      `references/safety-and-baseline.md`. Search application code, tests,
      generators, templates, and configuration for Pydantic imports and v1
      patterns. Include `Extra`, nested `class Config`, `schema_extra`,
      `allow_population_by_field_name`, `orm_mode`, `validate_all`,
      `Field(const=...)`, `min_items`, `max_items`, `regex`, `unique_items`,
      `allow_mutation`, `parse_obj`, `parse_raw`, `parse_file`, `from_orm`,
      `dict`, `json`, `copy`, `construct`, `schema`, `update_forward_refs`,
      `__fields__`, `__fields_set__`, old validators, dataclasses, generic
      models, root models, strict types, and settings usage. Distinguish genuine
      model API calls from unrelated methods with the same names. Use searches
      that tolerate zero matches rather than treating a normal grep exit code 1
      as a migration failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`. Read affected models, their base
      classes, aliases, recursive references, fixtures, parser entry points, and
      tests before changing them. Record whether extras are allowed, ignored, or
      forbidden; whether names or aliases populate fields; which fields are
      genuinely optional; expected coercion and strictness; serialization alias
      behavior; schema examples; and validator ordering. Treat tests using
      `model_construct` or other construction methods as evidence about intended
      defaults and bypassed validation, not as irrelevant code.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Follow "Form an executable slice plan" in
      `references/safety-and-baseline.md`. Order small, testable slices by the
      active blocker and model dependency graph: import blockers first, then
      configuration and field semantics, then validators and entry points, then
      schema and serialization behavior. Give each slice an edit target and an
      immediate compile/import/focused-test command. Planning is not a stopping
      point: execute the first safe slice in the same turn.
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
      configuration safely." Convert each model independently from a nested
      `class Config` to one `model_config = ConfigDict(...)`. Map `Extra.allow`,
      `Extra.ignore`, and `Extra.forbid` to string values; rename
      `allow_population_by_field_name` to `populate_by_name`; rename
      `schema_extra` to `json_schema_extra`; and map other keys according to
      native v2 semantics. Preserve the entire schema-extra dictionary exactly.
      Remove obsolete `Extra` imports only after all uses in that file are gone.
      Never leave both configuration styles on one model. Review the file diff
      and compile it before moving to the next configuration shape.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Follow "Migrate fields, annotations, and optionality" in
      `references/native-v2-conversions.md`. Replace `Field(const=True)` with
      `Literal` annotations, `min_items` and `max_items` with the appropriate
      length constraints, and removed field keywords with native v2 equivalents.
      Audit every `Optional[T]`: add `= None` only when omission was accepted in
      v1 or required by public behavior; do not mechanically default every
      optional annotation. Pay particular attention to shared configuration
      models and fixtures, where Pydantic v2 requiredness changes can cause a
      large fan-out of setup errors. Preserve aliases, defaults, factories,
      strictness, and serialization expectations.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Follow "Migrate validators without erasing behavior" in
      `references/native-v2-conversions.md`. Translate `@validator` and
      `@root_validator` to `@field_validator` and `@model_validator` only after
      recording their input shape, mode, ordering, reuse, and error behavior.
      Adapt signatures and return values to v2. Preserve every function body and
      invariant. Never delete, empty, replace with `pass`, short-circuit, or
      neutralize a validator or any other function merely to make imports or
      tests proceed. Add focused tests when existing coverage does not prove the
      preserved behavior.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Replace Pydantic model
      `parse_obj` calls with `model_validate`, and migrate raw/file parsing,
      ORM validation, `dict`, `json`, `copy`, and `construct` calls to native v2
      APIs where applicable. Preserve keyword arguments such as alias handling,
      include/exclude, unset/default exclusion, JSON mode, and context. Do not
      mechanically replace unrelated methods in templates or domain objects.
      Validate the parser's success path and validation-error path.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Follow "Migrate schema, introspection, and special models" in
      `references/native-v2-conversions.md`. Convert schema generation and field
      introspection to `model_json_schema`, `model_fields`, and the corresponding
      v2 interfaces. Replace `update_forward_refs` with `model_rebuild` where
      needed and verify recursive models after all related classes load. Handle
      root models, generic models, dataclasses, settings, private attributes,
      computed fields, and strict types according to their v2 contracts rather
      than ordinary-model assumptions.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Diagnose
      behavior rather than chasing warnings mechanically. Check required versus
      nullable fields, union selection, coercion, strict values, enum handling,
      aliases, extra fields, equality, custom types, regex behavior, serialization,
      JSON schema output, and exception structure. Use the failing constructor,
      fixture, or assertion to identify the intended contract, then fix the
      shared root cause rather than patching individual tests.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After every coherent edit, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." First compile the changed files, then import the affected module,
      run the smallest relevant tests, and inspect the diff. If compilation
      fails, stop adding changes and repair or safely restore the malformed file.
      An import check proves only importability, not migration completion. Once a
      slice passes, immediately proceed to the next planned slice or full-suite
      checkpoint; do not end the turn with only a plan or summary.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, run the full authoritative suite with an
      unmasked exit status and keep its complete output. Record all failure,
      error, pass, skip, and warning counts, not only the first traceback.
      Cluster failures by shared constructor, fixture, model, or semantic change.
      If hundreds of tests pass but any fail, treat the run as evidence of
      partial progress only. Prioritize setup errors and shared fixtures because
      one missing `= None` or configuration regression can fan out across many
      tests. After each root-cause fix, run its focused cluster and then rerun the
      full suite to reveal the next layer.
    outputs:
      - name: post-collection-triage
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`. Re-run the complete v1-pattern
      search because import blockers may have hidden later modules and earlier
      edits may have left obsolete imports or mixed configuration. Review each
      residual match in context and classify it as migrated, unrelated, required
      compatibility surface, or unresolved. Native-v2 completion must not rely
      on `pydantic.v1`.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`. Review `git diff --check`,
      changed-file lists, and each complete diff. Look for truncated dictionaries,
      duplicated configuration, misplaced parentheses, accidental line-number
      insertions, import churn, deleted logic, changed examples, unrelated
      dependency edits, and pre-existing changes accidentally overwritten.
      Compile all changed Python files after review.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the authoritative command
      without output-masking pipelines and verify its actual exit code. Do not
      substitute an import check, collection-only run, selected tests, or a count
      such as 310 passing tests for the complete suite. Continue the
      diagnose-edit-focused-test-full-suite loop until there are zero failures
      and zero errors, or report a concrete external blocker with preserved
      evidence.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's configured
      formatting check, linter, type checker, compile check, generated-file
      verification, and other CI-equivalent gates. Fix migration-caused failures
      and rerun affected gates. Do not invent unrelated quality requirements.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`. Confirm dependency metadata
      targets the intended Pydantic v2 range; no application import points to
      `pydantic.v1`; no removed v1 API remains unintentionally; no model combines
      `model_config` with nested `Config`; no validator or other function body
      was emptied or neutralized; changed files compile; and the complete suite
      and required quality gates pass. Search specifically for `pydantic.v1`,
      `Extra.`, legacy configuration keys, removed field arguments, deprecated
      entry points, and suspicious `pass` additions or deleted bodies.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`. When revising an accepted
      migration procedure, walk every source instruction and every observed
      failure lesson line by line. Classify each distinct item as Mapped, Schema
      gap, Body drop, or Deliberate drop. Repair every Schema gap or Body drop
      before finishing. Record a Deliberate drop with a reason at the source
      location; never shorten a proven procedure by silently removing steps,
      anti-patterns, validation gates, or gotchas.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`. Report changed files and the
      behavior preserved, the Pydantic v2 conversions made, the exact full-suite
      command and result, quality-gate results, and residual-search results. If
      blocked, state the blocker, current failure counts, last validated slice,
      and next executable action. Never say "Task completed" when tests were not
      run to a genuine zero-failure exit or when source remains malformed.
    outputs:
      - name: migration-report
        type: object
```