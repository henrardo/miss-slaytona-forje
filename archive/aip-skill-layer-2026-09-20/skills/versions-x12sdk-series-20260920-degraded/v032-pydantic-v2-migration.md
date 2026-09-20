---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 32
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, registries, and domain behavior. Work from complete tracebacks,
  original function bodies, repository tests, and executable checkpoints
  rather than speculative bulk rewrites. Never satisfy the task by importing
  from pydantic.v1 or another v1 compatibility namespace. Never make code
  import by deleting, emptying, bypassing, or replacing a function body with a
  no-op. Preserve every validator's substantive checks, mutations, errors, and
  return behavior. Treat Python source as Python: use True and False, never
  JSON literals true and false. Do not confuse import success, successful
  collection, a zero-looking pipeline status, a green focused test, or
  warnings-only output with completion. Completion requires production code
  to compile, nonempty test collection to succeed, focused behavior tests to
  pass, the exact untruncated full-suite command to exit zero, and the final
  diff to pass static and behavior-preservation audits. Capture real command
  exit codes without piping pytest through head, tail, tee, or grep unless
  pipefail is enabled and the pytest status is explicitly preserved.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

steps:
  - name: establish-the-failure
    description: >
      Read and follow `establish-the-failure` in
      `references/repository-assessment.md`. Run the repository's exact
      documented suite from its root and save complete output plus the real
      exit status. Do not truncate or pipe the baseline command in a way that
      replaces pytest's status with head, tail, tee, or grep. If output must
      be saved and displayed, write it to a file and capture pytest's status
      before inspecting the file, or enable pipefail and verify PIPESTATUS.
      Record the first complete traceback, collection count, pass count, fail
      count, runtime versions, and exact command. A command that merely imports
      one module is not a baseline.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository path once and reuse it exactly; prior attempts repeatedly
      lost time to misspelled paths such as agent-worm, agent-wam, agent-wrap,
      and agent-w0. Capture `git status --short` and `git diff`. Treat existing
      tracked changes as user work unless provenance proves they are migration
      edits. Do not reset, checkout, or overwrite them merely to simplify the
      task. Record untracked files separately so temporary migration artifacts
      cannot be mistaken for repository deliverables.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect pyproject.toml, lock and
      requirements files, CI commands, test configuration, supported Python
      versions, package exports, requirements-v2.txt or equivalent target
      evidence, and repository-local migration tests. Check which files
      actually exist before reading setup.py or requirements.txt. Prefer the
      repository's measured target dependency set over guessed pins. Identify
      the authoritative full-suite command and whether migration-specific tests
      add public contracts absent from the pre-migration implementation.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Verify the interpreter used by
      tests imports native Pydantic 2 and all split packages required by the
      target, especially pydantic-settings. Print versions from that same
      interpreter. Do not infer runtime state from dependency text alone and
      do not use pydantic.v1 as a shortcut. Verify pytest is invoked through
      that interpreter when multiple environments are available.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search production code, tests,
      exports, and generated registries for BaseSettings, inner Config,
      validator, root_validator, allow_reuse, SHAPE_LIST, ModelField,
      __fields__, field_info.extra, regex, constr(regex=), min_items,
      max_items, parse_obj, parse_raw, from_orm, copy, dict, json, schema,
      custom Field extras, and validator functions expecting a v1 values
      dictionary. Search decorators independently from imports so a stale
      decorator cannot hide behind a partially migrated import block. Record
      every file and occurrence; do not rely on a single import grep or stop
      after the first large segments module.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Inventory public imports and
      helpers used by tests or consumers, including underscore-prefixed
      helpers such as `_is_list_field`, repeatable-segment coercion, metadata
      flags such as `is_component`, segment registries, enum serialization,
      frozen delimiter models, CLI output, parser output, and exact validation
      error behavior. A helper absent from production but imported by a
      migration test is required migration work, not permission to edit the
      test. Record representative valid and invalid fixtures for each
      behavior-sensitive surface.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Before rewriting validators or shared model code, capture the original
      source for every affected function and class from the current working
      tree or, when that file is already partially migrated, from the
      appropriate base revision while preserving unrelated user changes.
      Record each decorator, signature, branch, raise, mutation, and return.
      Use this semantic snapshot during review; repeated attempts corrupted
      bodies through regex rewrites and then lacked a reliable source from
      which to restore behavior. Never replace a partially migrated file
      wholesale when it contains pre-existing user edits.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Create a ledger with one row per
      migration surface: file, symbol, original v1 behavior, intended v2
      replacement, dependent tests, representative accepted and rejected
      examples, risk, status, and checkpoint command. Include paired 4010 and
      5010 implementations separately; similarity does not prove both have
      identical validators, imports, constraints, or line layouts.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Order work by executable
      dependency: collection blockers; dependencies and settings; shared base
      models; inherited fields and constraints; reusable validator
      infrastructure; field and model validators; introspection and metadata;
      parsing and serialization; registries and public helpers; focused
      behavior; full suite. Separate mechanical renames from semantic rewrites.
      Treat validators and model introspection as semantic rewrites even when
      their decorator or attribute rename appears mechanical.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Define a compile or import
      checkpoint after each small coherent edit and a focused test after each
      behavior change. Never plan an unreviewed repository-wide sed or regex
      rewrite of decorators, signatures, function bodies, imports, Field
      calls, or boolean literals. Automated edits must be narrow, idempotent,
      immediately diff-reviewed, compiled, and reverted or repaired before
      proceeding if malformed. Avoid line-number-based edits in large files
      because earlier edits shift lines and paired versions differ.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Repair only the earliest full
      traceback, rerun nonempty collection, then repeat. Do not announce
      success after resolving BaseSettings if collection next fails on a
      validator. When a decorator is named but not imported, determine whether
      it should be migrated rather than merely restoring the deprecated v1
      import. A bare post `@root_validator` error requiring
      `skip_on_failure=True` is evidence to perform a semantic
      `@model_validator` migration, not to accumulate compatibility patches.
      Continue until collection reaches the next planned migration layer.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Update every authoritative
      dependency declaration consistently to Pydantic 2 and add
      pydantic-settings where BaseSettings is used. Import BaseSettings and
      SettingsConfigDict from pydantic_settings, migrate settings Config to
      model_config, preserve case sensitivity and environment behavior, and
      change Field(regex=...) to Field(pattern=...). Validate settings imports
      and representative valid and invalid values immediately. Do not assume a
      successful config import proves the rest of the package can collect.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Convert inner Config classes
      to ConfigDict or equivalent model_config while preserving
      use_enum_values, frozen or immutability behavior, arbitrary type policy,
      extra handling, population rules, validation timing, and serialization.
      Configure shared base classes first so subclasses inherit stable v2
      behavior. Verify frozen delimiter models remain immutable and hashable.
      Do not silence inherited-field errors by changing extra policy or
      weakening the base model.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires an
      annotation when a subclass overrides an inherited model field. Preserve
      declarations such as `segment_name: X12SegmentName =
      X12SegmentName.CR5`; do not remove all subclass `segment_name` fields,
      turn them into ClassVar, or weaken the base field merely to silence
      `model-field-overridden`. Audit every unannotated inherited override and
      verify segment registries still derive the correct default. Search for
      unannotated assignments structurally rather than assuming only one known
      CR5 occurrence exists.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Migrate regex to pattern,
      constr(regex=...) to constr(pattern=...), and list constraints to their
      v2 forms without changing accepted values. Move custom Field extras such
      as `is_component=True` into
      `json_schema_extra={"is_component": True}` and use Python True, never
      lowercase JSON true. Preserve requiredness, Optional semantics, aliases,
      defaults, decimal constraints, generated schema, and X12 component
      splitting behavior. Compile immediately after metadata edits because
      lowercase `true` is syntactically valid as a name but fails at import.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Replace custom partial aliases
      around v1 validator with a clear v2 field-validator mechanism without
      shadowing the imported decorator. Remove allow_reuse because v2 no
      longer accepts it. Preserve reusable function call signatures and
      registration sites. Distinguish raw reusable validation functions from
      decorated class methods; do not decorate a function twice or create
      `@validator` plus `@field_validator` stacks. Verify each shared
      registration by importing a model that actually uses it.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each v1 @validator to
      @field_validator deliberately. Select mode="before" only when validation
      must inspect raw input. Replace the v1 values dictionary with
      ValidationInfo and `info.data`; field order still controls which prior
      values are available. Add @classmethod only in a valid v2 decorator
      arrangement. Preserve always-like behavior, target fields, returned
      values, errors, date parsing, and cross-field dependencies. Reusable
      date validators may need to accept either ValidationInfo or a mapping
      only when call sites genuinely require both; do not make them silently
      permissive. Test every migrated validator with accepted and rejected
      examples.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert each root validator
      one at a time using its semantic snapshot. A pre root validator becomes
      `@model_validator(mode="before")`, accepts raw mapping data, and returns
      that mapping. A post root validator normally becomes
      `@model_validator(mode="after")`, accepts `self`, reads attributes
      instead of `values.get`, and returns `self`. If existing reusable
      validation logic fundamentally consumes a mapping, use a carefully
      justified before validator or adapt data explicitly; do not label a
      dict-based body as after without rewriting it. Preserve every raise,
      conditional, mutation, and return. Never perform blind replacements
      that yield bare `@model_validator`, `@model_validator(pre=True)`,
      duplicated `(mode="before")`, invalid decorator colons, wrong
      indentation, `cls`/`self` mismatches, or bodies that still call
      `values.get` on a model instance.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search every production Python
      file for validator, root_validator, field_validator, and model_validator
      imports and decorator uses. Every decorator must be defined by a native
      v2 import, and no stale v1 decorator may remain. Specifically guard
      against a file importing model_validator while later classes still use
      `@root_validator`, which causes NameError during collection, and against
      deprecated post root validators that fail because skip_on_failure is
      absent. Check support modules, specialized transaction directories, and
      both top-level versioned segment modules. Compile and import both
      versioned segment modules after closing the gap.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace __fields__ with
      model_fields and adapt to FieldInfo rather than assuming v1 ModelField
      attributes such as shape, type_, name, or field_info.extra. Use
      annotation, get_origin, get_args, json_schema_extra, and each mapping key
      as appropriate. Repair parser field order, X12 serialization, component
      metadata, nested model discovery, and segment-name registries. Do not
      import removed SHAPE_LIST constants or probe unrelated Field functions
      for shape metadata. Remember that a model_fields value has no v1 `name`;
      the mapping key is the field name.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Implement and retain the public
      `_is_list_field` helper required by migration tests and use it in
      repeatable-segment coercion. Determine list-ness from the v2 field
      annotation with typing.get_origin and recursively account for Optional
      or Union list annotations where present. Verify every `_segment` model
      field annotated as List accepts a single dictionary or model instance
      and wraps it in a one-item list, while non-list fields are not wrapped.
      Test the helper directly as well as through model construction.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace dict, json, parse_obj,
      parse_raw, copy, and related v1 calls with model_dump,
      model_dump_json, model_validate, model_validate_json, model_copy, or a
      behavior-equivalent v2 API. Preserve exclude, exclude_none,
      exclude_unset, aliases, enum values, Decimal and date handling,
      delimiters, CLI JSON shape, segment counting, duplicate-code validators,
      parser component splitting, and nested model recursion. Do not apply a
      repository-wide textual `.dict(` replacement without checking whether
      the receiver is actually a Pydantic model. When code accepts either
      dictionaries or models, branch by type and preserve both paths.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Exercise import-time and generated registries after introspection and
      inherited-field changes. Verify each registered segment key is derived
      from the annotated `segment_name` field default, no key becomes `None`,
      and 4010 and 5010 registries retain expected classes. Use model_fields
      directly and avoid class-instance deprecation paths. Registry import
      warnings are not harmless when they indicate lookup behavior changed.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Run compileall over production
      code after each automated transformation and before collection. Treat
      syntax errors, indentation errors, malformed decorators, lowercase
      booleans, and missing names as edit corruption to repair immediately.
      Compilation is necessary but not evidence that Pydantic can construct
      model schemas, because decorator and field-definition errors often occur
      only during import.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import shared models, settings,
      support utilities, parser modules, and each major versioned segment
      package, then run the repository's full `pytest --collect-only` command
      without truncation. Require exit zero and a nonzero collected-test count.
      Repair the first complete traceback and repeat. Running collect-only on a
      conftest file may legitimately collect zero tests and is not the full
      collection gate. Collection success does not imply behavior success.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run settings, support,
      base-model, parser, 4010 segment, 5010 segment, repeatable-segment,
      loop-initializer, registry, CLI, and transaction tests in dependency
      order. Use exact node IDs obtained from collection; do not mistake
      "not found" for a behavior result. Capture the real status of every
      command. A focused group with dozens of passing tests is progress, not
      permission to stop before the full suite.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For each migrated validator,
      compare accepted values, rejected values, normalized output, mutation,
      defaults, error location, and serialized result against tests and the
      original semantic snapshot. Include ACH payment-field requirements,
      adjustment completeness, date-format qualification,
      organization-name rules, duplicate segment codes, transaction
      balancing, and list wrapping where present. An import-only checkpoint
      cannot establish semantic parity.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate
      remains red. Work on one complete traceback or one coherent failure
      family at a time: inspect source, its semantic snapshot, and relevant
      tests; make the smallest semantic repair; compile; rerun the narrow
      reproducer; rerun collection if imports changed; then rerun the affected
      focused group. Do not stop because time has been spent, because some
      tests pass, or because the remaining work appears repetitive. Never end
      a turn with a promised edit written as pseudo-tool syntax instead of
      actually applying and verifying it.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Inspect the complete
      diff and search for duplicated decorators, missing imports, invalid
      signatures, deleted fields, emptied bodies, accidental file-wide
      rewrites, malformed Python literals, comments claiming behavior that
      code does not implement, temporary migration scripts, and collateral
      changes. Compare each migrated validator body with its semantic
      snapshot. Do not defer this audit until the end.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      pydantic.v1, deprecated validator and root_validator uses, BaseSettings
      imported from pydantic, allow_reuse, SHAPE_LIST, __fields__,
      field_info.extra, v1 Config classes, regex arguments, lowercase boolean
      literals introduced into Python, invalid model_validator forms, and
      empty or no-op function bodies. Also search for duplicated mode
      arguments, bare model_validator decorators, decorator lines ending in a
      colon, and model-after bodies using `values.get`. Classify every match;
      do not accept grep exit one as a task failure when it means a prohibited
      pattern is absent.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the exact repository full-suite command untruncated and
      unfiltered, saving output separately if needed while preserving pytest's
      exit code. Require exit zero and at least one collected and passed test.
      Do not report the status of head, tail, tee, grep, timeout, or a shell
      loop as the suite status unless the underlying pytest status is
      explicitly captured. Zero passing tests is never success.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck validation rejection paths, model output, X12 serialization,
      parser round trips, component metadata, repeatable-segment wrapping,
      settings, registries, public imports, CLI output, and schema-sensitive
      consumers. Confirm no validator body or domain field was deleted,
      emptied, bypassed, or weakened solely to achieve green tests. Verify
      native Pydantic v2 is still imported at runtime.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Review `git status --short`,
      the complete diff, dependency metadata, all new files, and the final
      static searches. Ensure only intended migration changes remain; remove
      temporary plans and repair scripts unless they are intentional project
      artifacts. Re-run compile, nonempty collection, focused tests, and the
      exact full suite after any final edit. Compare final changes against the
      initial working-tree snapshot so user work is neither lost nor
      misreported.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report changed behavior surfaces, exact commands, real exit statuses,
      collected and passed counts, warnings or residual risks, and final
      working-tree state. If any gate is red, report the migration as
      incomplete and name the first unresolved traceback; never substitute a
      progress summary, comprehensive summary, "ready", or "task completed"
      statement for executable evidence.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from pydantic.v1 or another Pydantic v1 compatibility namespace to make the migration pass.
  - Never delete, empty, bypass, comment out, or replace a function or validator body with pass, an unconditional return, or another no-op merely to make imports or tests pass.
  - Never bulk-replace root validators with model validators without converting mode, signature, data access, mutation, and return semantics one validator at a time.
  - Never perform repository-wide sed or regex transformations without immediate diff review, compilation, and focused verification.
  - Never use line-number-based edits as the primary migration strategy in large changing modules.
  - Never remove inherited domain fields such as segment_name merely to silence Pydantic v2 field-override errors; add the required annotation and preserve registry behavior.
  - Never use lowercase true or false in Python source when constructing json_schema_extra or any other mapping.
  - Never restore a deprecated root_validator import merely to resolve a NameError when the task requires native v2 migration.
  - Never add skip_on_failure=True as the endpoint of a native-v2 migration; use the error to migrate the validator semantically.
  - Never assume an after model validator receives a dictionary or that a before model validator receives a constructed model.
  - Never leave decorators and imports inconsistent across large paired modules such as v4010 and v5010 segments.
  - Never stack old and new validator decorators or decorate a reusable function twice.
  - Never drop public helpers, including underscore-prefixed helpers imported by tests, because they look internal.
  - Never infer list fields from removed v1 shape constants; inspect v2 annotations and typing origins.
  - Never access v2 FieldInfo as though it were a v1 ModelField with shape, type_, name, or field_info.extra.
  - Never globally replace `.dict(`, `.json(`, or similar text without proving each receiver is a Pydantic model.
  - Never treat import success, compile success, collection success, warnings-only output, or one focused test as full migration success.
  - Never pipe the authoritative pytest command through head, tail, tee, or grep and then report the pipeline's last command status as pytest's status.
  - Never claim completion when zero tests passed, collection was empty, collection had errors, or the exact full suite was not run.
  - Never edit tests to conceal migration failures unless the repository contract explicitly requires a test migration and behavior remains preserved.
  - Never trust comments, migration plans, previous attempt summaries, or stale line numbers over executable source, semantic snapshots, complete tracebacks, tests, and the current diff.
  - Never stop after producing a migration plan, progress summary, or list of remaining edits; apply and verify the changes or explicitly report the task incomplete.
```