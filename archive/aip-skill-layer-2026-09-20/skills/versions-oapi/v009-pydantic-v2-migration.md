---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 9
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, and repository tests preserve intended behavior. Complete
  the migration without redirecting imports to `pydantic.v1`; without deleting,
  emptying, bypassing, or neutralizing validators or any other function bodies;
  without corrupting source through broad mechanical edits; and without stopping
  after searches, investigation, planning, an import check, test collection, or
  a partially passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models
  - Models import successfully under Pydantic v2 but constructors, fixtures, or behavioral tests fail

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - >
    Before beginning any migration work, read
    `references/safety-and-baseline.md` for the mandatory anti-patterns and
    exact instructions governing repository setup, recovery, baseline testing,
    project constraints, initial blocker handling, inventory, behavior mapping,
    and executable planning.
  - Re-pointing application imports to `pydantic.v1`; this is not a native Pydantic v2 migration and is rejected even if tests pass
  - Emptying, replacing with `pass`, deleting, or otherwise neutralizing a validator or any function body merely so the module imports
  - Ending a turn after investigation or planning without making and validating the next safe edit
  - Treating successful import, collection, or 310 passing tests as completion while any test still fails or errors
  - Piping the authoritative test command through `head`, `tail`, or another command that masks pytest's nonzero exit status
  - Using broad regular-expression rewrites across nested `Config` classes or large schema-example literals without reviewing each resulting diff
  - Mixing a new `model_config` assignment with a legacy nested `class Config` on the same model
  - Moving `schema_extra` outside configuration or damaging its nested dictionary while converting it to `json_schema_extra`
  - Assuming `Optional[T]` supplies a default in Pydantic v2; without `= None`, the field remains required
  - Migrating only the first import-time error and failing to re-inventory the repository after collection succeeds
  - Running only narrow tests after a migration that changes validation semantics shared by many models
  - Reverting or overwriting pre-existing user changes merely to obtain a clean working tree
  - Suppressing deprecation warnings instead of replacing deprecated v1 APIs where the task requires native v2
  - Declaring success without checking dependency metadata, residual v1 APIs, the complete suite, and project quality gates

steps:
  - name: establish-repository-root-and-state
    description: >
      Before editing, read `references/safety-and-baseline.md` and follow
      "Establish repository root and state." Confirm the actual repository root
      with `pwd` and version-control metadata; record Python and Pydantic
      versions; inspect `git status --short`; and identify all existing tracked
      changes. Use paths relative to the confirmed root to avoid editing a
      misspelled or nonexistent directory.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Inspect the diff
      before touching it. Distinguish pre-existing user work from failed
      migration edits, preserve user changes, and repair or selectively revert
      only edits known to have been introduced by the migration. Compile any
      previously edited modules before building further changes on them.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      When selecting repository commands, follow "Identify authoritative
      project commands" in `references/safety-and-baseline.md`. Read project
      metadata, CI configuration, contributor documentation, lock files, and
      test configuration. Record the authoritative full-suite, focused-test,
      formatter, linter, type-checker, and package commands rather than
      guessing. Note intentionally separate integration or end-to-end suites.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      When establishing the baseline, follow "Establish the unpiped baseline"
      in `references/safety-and-baseline.md`. Run the authoritative test command
      directly and preserve its real exit status. Do not use a pipeline ending
      in `head`, `tail`, `tee`, or `grep` unless pipefail is enabled and the
      pytest status is captured separately. Save the complete traceback, pass,
      fail, error, skip, and collection counts. If output is large, redirect it
      to a file while retaining the command's exit code, then inspect the file.
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
      explicit `Literal[...]` annotation and a matching default, including enum
      literals where applicable. Ensure every Pydantic field has a type
      annotation. Run compilation, an affected-module import, and the smallest
      relevant tests immediately before proceeding.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      When determining the compatibility target and dependency changes, follow
      "Inspect project constraints" in `references/safety-and-baseline.md`.
      Inspect `pyproject.toml`, requirements files, lock files, package extras,
      CI matrices, and any supplied post-migration dependency set. Decide
      whether the repository targets Pydantic v2 only or an explicitly requested
      compatibility range. Update authoritative dependency declarations
      consistently; do not solve a native-v2 task by pinning v1.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      When inventorying v1 APIs and affected code, follow "Inventory the
      complete Pydantic surface" in `references/safety-and-baseline.md`. Search
      application code, tests, fixtures, templates, scripts, generated-source
      inputs, and documentation that drives code generation. Include imports;
      `Extra`; nested `Config`; `schema_extra`;
      `allow_population_by_field_name`; `orm_mode`; `validate_all`; removed
      `Field` arguments such as `const`, `min_items`, `max_items`, and `regex`;
      `parse_obj`, `parse_raw`, `from_orm`, `dict`, `json`, `copy`,
      `construct`, `schema`, `update_forward_refs`; `__fields__`,
      `__fields_set__`; root models; dataclasses; generics; settings; validators;
      serializer hooks; aliases; and constrained types. Treat a no-match grep
      exit status as inventory information, not a fatal task failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      After inventorying affected code, follow "Inspect model relationships and
      public behavior" in `references/safety-and-baseline.md`. Map inheritance,
      unions, discriminators, recursive references, aliases, extras, schema
      generation, default constructors, fixtures, and downstream attribute
      access. For every affected field record whether omission is allowed,
      whether `None` is allowed, its default, alias behavior, and serialization
      name. Pay special attention to configuration models routinely instantiated
      as `Config()` and to tests using `model_construct`, because those expose
      requiredness and construction semantics that an import check cannot.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Before beginning conversion slices, follow "Form an executable slice plan"
      in `references/safety-and-baseline.md`. Order work by dependency and
      feedback speed: restore syntax, remove collection blockers, migrate shared
      model configuration, repair requiredness and fields, migrate validators,
      migrate entry points and serialization, rebuild recursive models, then
      address semantic failures. Each slice must end with compilation and a
      focused test or executable behavior check. Start executing the first slice
      in the same turn; planning is not a stopping point.
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
      When converting model configuration, read
      `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert one model or tightly related group at a
      time using `ConfigDict`. Typical mappings include `Extra.allow` to
      `extra="allow"`, `Extra.forbid` to `extra="forbid"`,
      `allow_population_by_field_name` to `populate_by_name`,
      `schema_extra` to `json_schema_extra`, `orm_mode` to
      `from_attributes`, `validate_all` to `validate_default`, and
      `allow_mutation=False` to `frozen=True`. Preserve model-specific
      differences and complete schema-example dictionaries exactly. Remove the
      legacy nested `Config` only after all of its behavior is represented;
      never leave both configuration styles on one model. Compile and inspect
      the diff after every group, especially files containing large nested
      schema examples.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      When converting fields, annotations, or optionality, follow "Migrate
      fields, annotations, and optionality" in
      `references/native-v2-conversions.md`. Replace removed field constraints
      with their v2 equivalents, such as `min_items` and `max_items` with
      `min_length` and `max_length`, and `regex` with `pattern`. Use
      `Literal[...]` for constants. Audit every `Optional[T]` field: in v2 it is
      required unless it has a default, so add `= None` only where omission was
      allowed in the prior public behavior. Do not mechanically make genuinely
      required nullable fields optional. Instantiate expected zero-argument
      models such as repository configuration objects and inspect
      `model_fields[name].is_required()` for ambiguous cases.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Before converting any validator, follow "Migrate validators without
      erasing behavior" in `references/native-v2-conversions.md`. Translate
      `@validator` and `@root_validator` to `@field_validator` and
      `@model_validator` with the correct before/after mode, signature, return
      value, and ordering. Preserve normalization, cross-field invariants,
      defaults, and exact error behavior. Adapt access from v1 `values` or model
      dictionaries to v2 validation info or model instances deliberately. Never
      delete a validator, replace its body with `pass`, return input
      unconditionally, or empty any other function merely to make imports
      succeed. Add or retain focused tests that prove each validator still
      accepts and rejects the intended cases.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      When converting parsing, validation entry points, or serialization,
      follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Replace `parse_obj` with
      `model_validate`, `from_orm` with `model_validate` plus
      `from_attributes=True`, `dict` with `model_dump`, `json` with
      `model_dump_json`, `copy` with `model_copy`, and `construct` with
      `model_construct` where equivalent. Preserve flags such as aliases,
      exclusions, unset/default omission, JSON mode, and round-trip behavior.
      Distinguish Python-object dumping from JSON-compatible dumping and test
      call sites rather than performing blind textual replacement.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      When converting schema generation, introspection, forward references, or
      specialist model types, follow "Migrate schema, introspection, and special
      models" in `references/native-v2-conversions.md`. Use `model_json_schema`,
      `model_fields`, `model_fields_set`, and `model_rebuild` where appropriate.
      Handle recursive imports only after related classes are defined. Review
      root models, generic models, dataclasses, settings models, discriminated
      unions, custom types, and custom core or JSON schema hooks individually;
      their v2 migrations are not safe global renames. Verify generated schema
      content where the repository depends on it.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Group the
      complete failing-test output by root cause instead of fixing failures in
      arbitrary file order. Check required-versus-nullable fields first,
      especially when fixtures fail at `Config()` or another default
      constructor. Then check coercion, union selection, enum values, equality,
      extras, aliases, default validation, serializer output, error locations,
      private attributes, and schema shape. Reproduce each cluster with the
      smallest direct model construction or validation example before editing.
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
      slice." First run syntax compilation on touched files, then import the
      affected module, exercise representative model construction and failure
      behavior, and run the narrowest relevant tests with an unmasked exit
      status. If a mechanical edit touched many files, stop and review the diff
      before adding more changes. A successful import is only an intermediate
      check, not completion.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, run the full authoritative suite and keep
      its complete output. Record all failure and error counts, not only the
      first traceback. Cluster failures by shared constructor, fixture, model,
      or semantic change. If hundreds of tests pass but many fail, treat the run
      as evidence of partial progress only. Prioritize setup errors and shared
      fixtures because one requiredness regression can fan out across many
      tests. After each root-cause fix, run its focused cluster and then rerun
      the full suite to reveal the next layer.
    outputs:
      - name: post-collection-triage
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Once the suite collects, follow "Repeat inventory after collection
      succeeds" in `references/validation-and-completion.md`. Repeat all v1 API
      searches across production code and relevant generation inputs. Search
      specifically for `pydantic.v1`, legacy `Config`, `Extra`, deprecated
      methods, removed `Field` arguments, old validator decorators, and
      `update_forward_refs`. Review dynamic or aliased Pydantic imports that
      simple searches may miss. Classify every remaining match as migrated,
      intentionally compatible, test-only, documentation-only, or unresolved.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Before full-suite completion testing, follow "Inspect and review the diff"
      in `references/validation-and-completion.md`. Review `git diff --check`,
      the changed-file list, and the complete patch. Confirm that edits are
      limited to the migration, imports are used, schema examples remain
      structurally intact, no function body was emptied, no test was weakened
      merely to pass, no user change was overwritten, and no file contains a
      malformed partial conversion. Compile all changed Python files.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      When running completion testing, follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the authoritative suite
      unpiped and require exit status zero. Run separately configured integration
      or end-to-end suites when available and feasible. Do not infer success
      from a truncated progress display or from the number of passing tests:
      any failure, error, collection error, unexpected skip, timeout, or masked
      nonzero status means the migration is incomplete.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's
      authoritative formatter check, linter, type checker, build or packaging
      check, and generated-file consistency check. Fix migration-caused issues
      and rerun affected tests after each fix. Do not substitute generic tools
      for project-declared commands without explaining why.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Before claiming completion, follow "Perform final native-v2 verification"
      in `references/validation-and-completion.md`. Confirm the runtime imports
      Pydantic v2, dependency metadata requests the intended v2 range, no
      production import points to `pydantic.v1`, and no forbidden compatibility
      shortcut remains. Re-run residual searches and explicitly verify expected
      default constructors, alias population, extra-field policy, serialization,
      schema generation, validators, and recursive models. Confirm no function
      body was emptied or behavior bypassed.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      When auditing an accepted source procedure, follow "Audit provenance and
      procedure completeness" in `references/validation-and-completion.md`.
      Walk the source material line by line against the compiled procedure and
      classify every distinct item as Mapped, Schema gap, Body drop, or
      Deliberate drop. Repair every Schema gap or Body drop before completion.
      Record every Deliberate drop with a concrete rationale; never shorten the
      procedure by silently discarding a prior step, warning, trigger,
      anti-pattern, or failure lesson.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      At completion or when reporting unresolved work, follow "Report completion
      with evidence" in `references/validation-and-completion.md`. State the
      files and behaviors changed, Pydantic version, exact test and quality-gate
      commands, exit statuses, and pass/fail/error/skip totals. Report remaining
      failures with their root-cause hypotheses and next executable action.
      Claim completion only when the complete suite and required quality gates
      pass and final native-v2 verification finds neither `pydantic.v1`
      redirection nor emptied function bodies.
    outputs:
      - name: migration-report
        type: object
```