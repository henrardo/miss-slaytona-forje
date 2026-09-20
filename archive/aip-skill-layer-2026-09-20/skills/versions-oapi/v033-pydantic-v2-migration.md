---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 33
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49, 5e38ab12, 651026ff, 1b53fe8c"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving intended validation, construction, requiredness, defaults,
  aliases, parsing, serialization, generated schemas, recursive models,
  fixtures, public APIs, dependency metadata, and repository behavior.
  Complete the migration without redirecting production imports to
  `pydantic.v1`; without deleting, emptying, bypassing, replacing with `pass`,
  or otherwise neutralizing validators or any other function bodies merely so
  imports or tests succeed; without weakening production behavior or rewriting
  tests to accept regressions; without corrupting source through broad
  mechanical edits; and without stopping after research, inventory, planning,
  an import check, compilation, collection, focused tests, or a partially
  passing suite. Treat a run with hundreds of passing tests and clustered
  failures as an actionable semantic migration stage, not near-enough success.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, field, validator, or configuration errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, methods, symbols, or semantics
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted, duplicated, truncated, or syntactically malformed models
  - Models import under Pydantic v2 but constructors, fixtures, aliases, schemas, serialization, or behavioral tests fail
  - Most tests pass but shared defaults, optionality, forward references, recursive aliases, root models, or exported types still fail
  - The installed Pydantic version disagrees with dependency declarations, requirements files, or lockfiles
  - A suite reaches hundreds of passing tests but still has clustered constructor, fixture, schema, or recursive-model failures
  - Shared fixtures fail because formerly omittable Optional fields became required under Pydantic v2

do_not_use_when:
  - The codebase already uses native Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task upgrades a dependency unrelated to Pydantic
  - The requested outcome is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning, read `references/migration-guardrails.md` and enforce every guardrail throughout the migration
  - Never re-point production imports to `pydantic.v1`, even as a temporary shortcut or compatibility layer
  - Never empty, delete, replace with `pass`, or otherwise neutralize a validator, serializer, constructor, helper, or other function body merely to make imports or tests pass
  - Do not rewrite tests to accept a production regression; change tests only when the asserted API is intentionally and demonstrably changed by the migration contract
  - Do not treat `Optional[T]` as meaning omittable in Pydantic v2; an omittable field normally needs an explicit default such as `None`
  - Do not run broad regex or `sed` transformations across model files without inspecting representative inputs, reviewing the exact diff, compiling every touched file, and reverting malformed output immediately
  - Do not convert a mapping type alias to `RootModel` reflexively; that changes construction, iteration, indexing, equality, serialization, and the public runtime type
  - Do not declare success from an import check, successful collection, focused tests, or a suite with hundreds of passes and any remaining failures
  - Do not trust the exit status of a test command piped through `head`, `tail`, `tee`, or `grep` unless `pipefail` or the original command status is captured
  - Do not install or replace package managers merely because the preferred wrapper is unavailable; use the repository's existing environment and an equivalent authoritative command
  - Do not repeatedly research standard v2 renames after repository evidence already identifies the blocker; make the smallest behavior-preserving edit and validate it
  - Do not edit generated schema examples, large nested dictionaries, or class bodies with line-number insertion or unbounded text replacement
  - Do not discard pre-existing tracked changes, including work from an earlier migration attempt, before identifying their provenance and preserving valid edits
  - Do not leave temporary migration scripts, summaries, generated artifacts, or unrelated environment changes in the repository

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Resolve the actual repository root once, use paths
      relative to it, record Python and installed Pydantic versions, and inspect
      `git status --short`. Do not confuse unrelated untracked skill files with
      migration edits, and do not guess paths such as similarly named home
      directories.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Inspect `git diff`, compile touched Python files, and
      classify each existing edit as valid, malformed, unrelated, or uncertain.
      Preserve valid work. Revert only files or hunks proven malformed or
      unrelated; never use a broad checkout that silently discards good
      migration progress.
    inputs:
      - name: repository-state
        type: object
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands." Inspect project metadata, CI workflows,
      task definitions, test configuration, and repository documentation.
      Record the authoritative collection, focused-test, full-suite, formatting,
      lint, and type-check commands. If a wrapper such as Poetry or Taskipy is
      absent but the environment is already provisioned, use the equivalent
      direct command rather than installing a new tool without need.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative command without truncating its execution
      through `head` or `tail`. If output must be saved, use `tee` with
      `set -o pipefail` or capture `PIPESTATUS[0]`; otherwise a failing pytest
      process can appear successful because the final pipeline command exited
      zero. Preserve the full first traceback and summary. Distinguish
      collection errors, test failures, external integration failures, and
      infrastructure errors.
    inputs:
      - name: project-commands
        type: object
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed, read
      `references/safety-and-baseline.md` and follow "Act immediately on a const
      collection blocker." Replace each constant field with a typed `Literal`
      field and preserve its default and runtime value. For enum constants, use
      the enum member in both the `Literal` and default. For a subclass such as
      a header parameter, keep the fields as real model fields rather than
      converting them to `ClassVar`, because callers and serialization may rely
      on them. Compile and import the affected model immediately.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine supported Python versions, the intended Pydantic
      v2 range, dependency-manager conventions, generated-code constraints,
      public compatibility requirements, and whether supplied requirements
      files represent pre- and post-migration environments.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Use the repository-provided post-migration
      requirements or dependency mechanism when available, then verify the
      interpreter and imported Pydantic version in the same environment used by
      tests. Do not infer the active version solely from `pyproject.toml` or a
      stale lockfile.
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
      complete Pydantic surface." Search production code, exported schema
      modules, tests, fixtures, and dependency metadata for imports, BaseModel
      subclasses, Config classes, `Extra`, `Field` constraints, validators,
      serializers, parsing and construction methods, dump methods, schema and
      field introspection, dataclasses, generics, root models, aliases, forward
      references, `update_forward_refs`, and mutable defaults. Include at least
      `const`, `min_items`, `max_items`, `regex`, `allow_mutation`,
      `allow_population_by_field_name`, `schema_extra`, `parse_obj`, `dict`,
      `json`, `copy`, `construct`, `__fields__`, and `__fields_set__`. Treat a
      grep exit code of one for no matches as inventory data, not a task
      failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Map inheritance, module exports,
      recursive references, mapping aliases, model construction sites,
      fixture factories, aliases such as `$ref` and `in`, parser entry points,
      direct indexing or iteration, equality assumptions, and schema-generation
      consumers. Record behavior before deciding whether a construct should
      remain a type alias, become a model, or require an explicit rebuild.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: establish-behavioral-sentinels-before-batch-edits
    description: >
      Before converting many models, read `references/safety-and-baseline.md`
      and follow "Establish behavioral sentinels before batch edits." Create or
      identify focused checks for the default application `Config()`, shared
      fixture constructors, constant-field models, aliased fields populated by
      name and alias, extra-field preservation, recursive OpenAPI parsing,
      mapping-like aliases, serialization, schema generation, and independent
      mutable defaults. Prefer existing tests and short runtime probes; do not
      add throwaway tests that remain in the final diff.
    inputs:
      - name: behavior-map
        type: object
      - name: migration-inventory
        type: object
    outputs:
      - name: behavioral-sentinels
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order work by the active failure: collection blocker,
      configuration conversion, fields and requiredness, validators, parsing
      and serialization, special and recursive models, dependencies, then
      residual cleanup. Keep slices small enough to compile, import, and test
      immediately. Do not spend a turn only restating a plan; begin the first
      executable slice in the same work session.
    inputs:
      - name: first-error
        type: string
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: migrate-model-configuration-safely
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert each nested v1 `Config` to a class-level
      `model_config = ConfigDict(...)`; map `Extra.allow` to `extra="allow"`,
      `allow_population_by_field_name` to `populate_by_name=True`, and
      `schema_extra` to `json_schema_extra`. Keep the complete schema-extra
      dictionary inside `ConfigDict`, with balanced delimiters and class-level
      indentation. Update imports narrowly. Inspect files with large embedded
      examples individually rather than transforming them through a regex that
      cannot parse nested dictionaries.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Convert removed field arguments with
      behavior-preserving types and constraints: constants to `Literal`,
      collection `min_items` and `max_items` to `min_length` and `max_length`,
      and `regex` to `pattern` where applicable. Preserve aliases and ensure
      models accepting both aliases and Python field names use the intended v2
      configuration. Do not change unrelated OpenAPI property names such as
      model fields named `minItems`; only convert the Pydantic constraint
      keyword passed to `Field`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: audit-requiredness-and-constructor-contracts
    description: >
      Before proceeding beyond field migration, read
      `references/native-v2-conversions.md` and follow "Audit requiredness and
      constructor contracts." In Pydantic v2, `Optional[T]` without a default
      remains required. For every model field annotated Optional, compare
      constructor calls, fixtures, configuration loading, and v1 behavior to
      decide whether it must be `= None`. Prioritize shared models and default
      constructors. In this repository pattern, configuration override fields
      such as project-name, package-name, and package-version overrides are
      expected to be omittable by `Config()` and therefore require explicit
      `None` defaults unless project evidence proves otherwise. Do not blindly
      add defaults to semantically required nullable fields.
    inputs:
      - name: behavior-map
        type: object
      - name: field-migration-results
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: requiredness-audit
        type: object

  - name: run-the-default-config-constructor-gate
    description: >
      Before broad testing, instantiate the application's default configuration
      exactly as production and shared fixtures do, usually `Config()`. If it
      raises a v2 missing-field ValidationError, inspect every omitted field and
      repair requiredness according to the recorded constructor contract.
      Re-run the exact constructor and the smallest fixture-dependent test.
      This gate is mandatory because a top-level import can succeed while most
      tests later fail at fixture setup.
    inputs:
      - name: requiredness-audit
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: default-config-gate
        type: object

  - name: run-the-shared-fixture-constructor-gate
    description: >
      Before converting specialist recursive models or running the complete
      suite, read `references/native-v2-conversions.md` and follow "Run the
      shared fixture constructor gate." Execute fixture factories or equivalent
      constructors directly and run one test that consumes each high-fan-out
      fixture. A fixture setup error can account for many apparent failures;
      fix the shared constructor contract before triaging every dependent test.
    inputs:
      - name: requiredness-audit
        type: object
      - name: behavioral-sentinels
        type: object
      - name: default-config-gate
        type: object
    outputs:
      - name: shared-fixture-gate
        type: object

  - name: audit-default-values-and-instance-isolation
    description: >
      Before proceeding beyond constructor auditing, read
      `references/native-v2-conversions.md` and follow "Audit default values and
      instance isolation." Review list, dictionary, set, and nested-model
      defaults. Preserve the public default while using `Field(default_factory=...)`
      where construction or isolation requires it. Verify two instances do not
      share mutable state. Do not assume either v1 or v2 behavior without a
      focused check.
    inputs:
      - name: behavior-map
        type: object
      - name: requiredness-audit
        type: object
    outputs:
      - name: default-audit
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior." Translate validator decorators, signatures,
      modes, and error behavior while preserving the complete function body and
      call order. A validator that imports but no longer validates is a failed
      migration. Never delete, empty, replace with `pass`, or bypass a
      validator or helper to make collection succeed. Add focused valid and
      invalid probes around every migrated validator.
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
      `model_construct` where behavior and call signatures match. Preserve
      options such as aliases, exclusions, and unset handling. Update production
      call sites rather than relying on deprecated aliases. When code tests
      whether a schema model has any populated values, confirm whether
      `model_dump()` or `model_dump(exclude_unset=True)` matches the original
      intent.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Handle `model_fields`,
      `model_fields_set`, JSON schema APIs, dataclasses, generics, private
      attributes, type adapters, mapping aliases, and root models explicitly.
      Preserve the public interface of plain aliases such as
      `Dict[str, PathItem]`. Do not replace a mapping alias with `RootModel`
      unless all construction, indexing, iteration, equality, serialization,
      annotations, and callers are intentionally migrated too. Prefer a native
      v2 named type alias or `TypeAdapter` when validation needs a runtime
      adapter but callers still require mapping behavior.
    inputs:
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: rebuild-forward-references-with-the-correct-namespace
    description: >
      When replacing `update_forward_refs`, read
      `references/native-v2-conversions.md` and follow "Rebuild forward
      references with the correct namespace." Use `model_rebuild` only after
      all referenced classes and aliases are imported. For cross-module or
      recursively defined aliases, supply the correct `_types_namespace` rather
      than calling `model_rebuild()` blindly. Rebuild actual BaseModel classes,
      not plain typing aliases. Validate by importing the public schema package
      and parsing a representative recursive document, not merely by compiling
      the defining files.
    inputs:
      - name: behavior-map
        type: object
      - name: specialist-migration-results
        type: object
    outputs:
      - name: forward-reference-results
        type: object

  - name: synchronize-dependency-metadata
    description: >
      When updating dependency declarations, requirements, or lock artifacts,
      read `references/native-v2-conversions.md` and follow "Synchronize
      dependency metadata." Make the declared Pydantic range agree with the
      tested target and supported Python versions. Update lockfiles only with
      the repository's intended dependency tool and only when required. Verify
      no authoritative artifact still pins v1. Do not mistake archival
      pre-migration requirement files for active dependency declarations.
    inputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]
      - name: target-environment
        type: object
    outputs:
      - name: dependency-migration-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      During every edit step, read `references/native-v2-conversions.md` and
      follow "Run a syntax and import gate after every edit slice." Compile
      every touched Python file, import the narrow affected module, then import
      the public package path. If compilation fails, stop and repair or revert
      that slice before touching more files. Inspect the exact diff around
      ConfigDict and nested schema examples for missing commas, parentheses,
      brackets, duplicated configuration, malformed imports, and truncated
      bodies.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run the nearest focused tests plus the behavioral sentinels for
      constructors, aliases, extras, defaults, serialization, and recursive
      parsing. Use authoritative unmasked exit codes. Continue editing in the
      same session when a focused test reveals the next concrete migration
      issue; do not stop after describing it.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the broad local suite and group failures by
      shared root cause rather than file order. Separate configuration
      requiredness, alias population, recursive schemas, mapping aliases,
      serialization, mutable defaults, and unrelated integrations. Fix the
      highest-fan-out production cause first.
    outputs:
      - name: post-collection-triage
        type: object

  - name: triage-a-partially-passing-suite
    description: >
      If hundreds of tests pass but the suite still fails, read
      `references/validation-and-completion.md` and follow "Triage a partially
      passing suite." Treat the passing count as evidence that foundational
      conversion worked, not as completion. Inspect the first complete
      traceback and failure clusters. If many failures or errors originate in
      `Config()`, `make_project`, or another shared fixture, return immediately
      to requiredness and constructor gates. If failures center on OpenAPI
      validation, inspect aliases and forward namespaces. If they center on
      mapping operations, inspect accidental RootModel conversion.
    inputs:
      - name: post-collection-triage
        type: object
      - name: requiredness-audit
        type: object
      - name: default-audit
        type: object
      - name: shared-fixture-gate
        type: object
      - name: default-config-gate
        type: object
    outputs:
      - name: partial-suite-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences." Compare v1 intent, v2 behavior, current call sites, and
      tests before editing. Pay particular attention to Optional requiredness,
      coercion and strict types, union selection, enum values, equality,
      aliases, extra fields, defaults, serialization exclusions, dataclasses,
      and error shape. Use minimal runtime probes to isolate semantics; consult
      official documentation only when repository evidence and a probe do not
      resolve the question.
    inputs:
      - name: focused-test-results
        type: list[object]
      - name: post-collection-triage
        type: object
      - name: partial-suite-triage
        type: object
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      After collection succeeds, read
      `references/validation-and-completion.md` and follow "Repeat inventory
      after collection succeeds." Search again for all v1 constructs,
      deprecated method calls, old configuration names, compatibility imports,
      and missed test or fixture assumptions. Collection can hide code paths
      that the initial blocker prevented Python from importing.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review `git diff --check`, `git diff --stat`, and the
      full diff. Confirm each changed file belongs to the migration; no source
      file is truncated; function and validator bodies remain intact; no tests
      were weakened; imports are valid; examples remain structurally complete;
      temporary scripts and summaries are removed; and dependency changes are
      intentional. Compare unexpectedly large diffs against the index and
      restore then reapply narrowly if necessary.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Run the complete authoritative local suite with an
      unmasked exit status and retain its final pass, skip, failure, and error
      counts. Do not report success while any in-scope test fails. If external
      integration tests require unavailable services, report them separately
      only after the complete authoritative local suite passes and after
      confirming the project convention for those tests.
    inputs:
      - name: project-commands
        type: object
      - name: diff-review
        type: object
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the full suite passes, read
      `references/validation-and-completion.md` and follow "Run project quality
      gates." Run the repository's formatting check, lint, type check,
      compilation, packaging, and dependency consistency commands as
      applicable. Do not run auto-formatting over the entire repository unless
      that is the established project command and its resulting diff is
      reviewed.
    inputs:
      - name: project-commands
        type: object
      - name: full-suite-result
        type: object
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Read `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification." Verify the runtime imports Pydantic v2, active
      dependency declarations target v2, production code contains no
      `pydantic.v1` imports, residual v1 constructs are gone or explicitly
      justified, public schema imports work, default configuration and shared
      fixture constructors work, recursive parsing works, aliases and extra
      fields retain intended behavior, and no function body was emptied or
      neutralized.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Account for every source
      instruction, migration inventory item, pre-existing edit, and discovered
      failure mode as mapped, schema gap, body drop, or deliberate drop. A
      deliberate drop requires a recorded rationale. Confirm specifically that
      requiredness, `Config()` construction, shared fixtures, mutable defaults,
      aliases, recursive namespaces, type aliases, root-model decisions,
      dependency artifacts, unmasked test exits, native-v2 imports, intact
      function bodies, and full-suite completion were not lost during
      compression or rewriting.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Report the substantive production changes,
      exact full-suite command and result, quality-gate results, installed
      Pydantic version, residual skips or unavailable external checks, and
      native-v2 verification. Do not claim completion from a truncated output,
      a pipeline's final command status, collection alone, or a partial suite.
    inputs:
      - name: full-suite-result
        type: object
      - name: quality-gate-results
        type: list[object]
      - name: native-v2-verification
        type: object
      - name: provenance-audit
        type: object
    outputs:
      - name: migration-report
        type: object
```