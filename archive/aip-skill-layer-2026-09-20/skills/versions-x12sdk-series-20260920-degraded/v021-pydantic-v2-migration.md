---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field constraints and metadata, parsing, serialization, introspection, collection, public helpers, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 21
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Do not confuse an import success, successful collection, or a
  green focused test with completion. Completion requires production code to
  compile, test collection to succeed, focused behavior tests to pass, the exact
  untruncated full-suite command to exit zero, and the final diff to pass static
  and behavior-preservation audits.

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
      Read `references/repository-assessment.md` and follow its
      `establish-the-failure` instructions. Run the repository's exact,
      documented full-suite command before editing. Preserve the complete output
      and real exit status. Do not pipe the command through `head`, `tail`,
      `grep`, or another command that masks pytest's status; redirect to a log
      and inspect the log separately if output is large. Record whether failure
      occurs during import, collection, or test execution, the first complete
      traceback, collected and passed counts, warnings that indicate v1 use,
      and the exact command and environment.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository root with `pwd` and version-control metadata, then capture
      `git status --short` and the existing diff. Distinguish user changes from
      migration changes and never discard, overwrite, or reset user work.
      Ignore harness or skill directories when assessing product changes. Do not
      create migration plans, repair scripts, or other scratch artifacts inside
      the repository unless the task requires them; use a temporary directory
      for diagnostics.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Read actual dependency, build,
      test, lint, type-check, and supported-Python configuration before guessing
      filenames or commands. Inspect `pyproject.toml`, lockfiles, requirement
      variants such as a post-migration requirements file, CI workflows,
      contributor documentation, and test configuration. Treat repository
      fixtures and tests as executable contracts, including newly added tests
      for public helpers. Do not assume `setup.py` or `requirements.txt` exists.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Verify the interpreter, Pydantic,
      pydantic-core, pydantic-settings, pytest, and package-under-test paths from
      the same environment used by the suite. Install or synchronize the
      repository's declared post-migration dependency set when permitted.
      Diagnose native v2 behavior only under Pydantic 2. Never route production
      imports through `pydantic.v1`, a compatibility module, or a locally
      invented v1 shim.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search all production Python files,
      including nested transaction or plugin packages, for imports and uses of
      BaseSettings, Config, validator, root_validator, allow_reuse, ModelField,
      SHAPE_* constants, __fields__, field_info.extra, Field(regex=),
      constrained-type regex arguments, min_items, max_items, dict, json,
      parse_obj, parse_raw, from_orm, copy, schema, json_encoders, custom
      encoders, GenericModel, dataclasses, and private Pydantic internals.
      Search multiline imports as well as decorators and call sites; a simple
      one-line grep is not a complete inventory. Record each occurrence by
      category and file instead of immediately editing it.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Read tests and imports for public
      classes, helper functions, settings behavior, error behavior, repeatable
      list handling, parsers, serializers, CLI output, and schema metadata.
      Include underscored helpers if tests or downstream modules import them;
      for example, a list-field helper remains part of the effective contract
      when tests import it. Record valid and invalid examples and expected
      serialized representations so migration work preserves behavior rather
      than merely suppressing import errors.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Follow `classify-migration-work` in
      `references/repository-assessment.md`. Classify inventory entries into
      dependency/settings, model configuration, inherited field overrides,
      field constraints and metadata, reusable validators, field validators,
      model validators, reflection, list detection, parsing, serialization, or
      public-contract repair. Order work from the first collection blocker
      outward, with shared infrastructure before callers. Mark each validator
      as before-field, after-field, before-model, or after-model based on its
      required data, not on a mechanical decorator substitution.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md`, then follow
      `create-small-edit-checkpoints`. Define a checkpoint after each coherent
      file or API family: compile the changed file, import the narrow module,
      collect the affected tests, and run the smallest behavior test that
      exercises the change. Keep only one newly introduced failure class in
      play. Never apply a repository-wide `sed`, regular-expression rewrite, or
      generated script to validators, signatures, indentation, or function
      bodies. A mechanical codemod is acceptable only for syntax with identical
      semantics, followed immediately by diff review and compilation.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md`, then follow
      `repair-first-collection-blocker`. Fix only the first complete traceback
      blocking import or collection and rerun the same command. Read the
      surrounding class, base class, tests, and shared helper before editing.
      Continue one blocker at a time until collection advances. Do not declare
      success after an import smoke test, do not summarize unfinished work, and
      do not end the task while the suite still fails.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Change the declared dependency
      contract to Pydantic 2 and add `pydantic-settings` when settings models
      exist. Import `BaseSettings` and `SettingsConfigDict` from
      `pydantic_settings`; migrate settings `Config` options to
      `model_config`. Convert removed field keywords such as `regex` to
      `pattern`. Test environment-variable names, case sensitivity, defaults,
      validation, caching, and any custom source ordering. Keep dependency files
      mutually consistent and avoid unrelated upgrades.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Replace inner v1 `Config`
      classes with `ConfigDict` or equivalent native-v2 configuration while
      preserving `use_enum_values`, extra-field behavior, population by field
      name, assignment validation, arbitrary types, immutability, aliases, and
      string normalization. Replace `allow_mutation = False` with frozen
      configuration. Decide whether defaults need validation; in v2,
      `use_enum_values` and validators may require `validate_default=True` to
      preserve default output. Verify inherited configuration rather than
      assuming it propagates identically.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 rejects replacing
      an inherited field with an unannotated class attribute. Find overrides
      such as `segment_name = ...` and add the correct annotation, normally the
      inherited field's type, without turning model fields into `ClassVar`.
      Preserve defaults, aliases, serialization order, and discriminator-like
      behavior. Compile and import after every repaired class family because a
      single unannotated override can block an entire module.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Convert `Field(regex=...)` and
      `constr(regex=...)` to `pattern`, and convert removed collection
      constraints such as `min_items` and `max_items` to native-v2 equivalents
      such as `min_length` and `max_length`. Move custom Field extras such as
      `is_component` into `json_schema_extra` and update every reader
      accordingly. Audit Optional annotations: `Optional[T]` without a default
      remains required in v2, so add `= None` only when the established contract
      says the field is optional. Preserve decimal, integer, length, pattern,
      alias, and schema behavior with positive and negative tests.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove `allow_reuse`; v2 no
      longer accepts it. Do not expose a local helper named `field_validator`
      that shadows Pydantic's decorator. Keep reusable business functions as
      ordinary functions with explicit, v2-compatible arguments, then register
      them at model fields with the real decorator. Inspect every reuse site,
      because a helper used both as a direct function and a validator may need
      a small adapter. Preserve function bodies and business checks completely;
      never replace a difficult validator with a no-op merely to make imports
      succeed.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each `@validator`
      deliberately to `@field_validator`, selecting `mode="before"` only when
      the function must inspect raw input. Use `ValidationInfo` and
      `info.data` instead of the v1 `values` argument; account for field order,
      because only already-validated fields appear there. Replace v1 `field` or
      `config` parameters with supported v2 mechanisms. Add `@classmethod`
      where appropriate and verify the decorator order. For validators that
      should run on defaults, configure default validation explicitly. Test
      missing, null, malformed, and cross-field-dependent values.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert each root validator
      independently. A before-model validator uses
      `@model_validator(mode="before")`, receives raw input through a class
      method, and returns the input mapping or object. An after-model validator
      normally receives `self`, reads attributes rather than dictionary keys,
      and returns `self`. Do not mechanically change a decorator while leaving
      a v1 `(cls, values)` body beneath it. Preserve every mutation, required
      field check, duplicate check, and exception. If assignment validation can
      invoke a validator with an instance, handle that documented v2 case.
      Compile and behavior-test each converted validator before moving on.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__` with
      `model_fields` and rewrite consumers for v2 `FieldInfo`; do not assume
      v1 attributes such as `shape`, `type_`, `name`, or `field_info.extra`
      still exist. Read annotations with `typing.get_origin` and `get_args`,
      field names from mapping keys, defaults from `FieldInfo`, and custom
      metadata from `json_schema_extra`. Update parser registries and
      import-time model scans carefully, then verify ordering and lookup keys.
      Prefer class-level `model_fields` access to deprecated instance access.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Preserve or restore the public
      list-field helper when tests or callers use it. Implement list detection
      from the v2 field annotation with `get_origin` and `get_args`, including
      direct lists and list members nested inside `Optional` or another union.
      Use that same helper in repeatable-segment wrapping so a singleton input
      becomes a one-item list only for list-valued fields. Test direct list,
      optional list, scalar, absent, already-list, and singleton-model cases.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 APIs with native-v2
      equivalents only after checking call semantics: `dict` with
      `model_dump`, `json` with `model_dump_json`, `parse_obj` with
      `model_validate`, `parse_raw` with explicit decoding plus validation or
      the supported replacement, `copy` with `model_copy`, and `schema` with
      `model_json_schema`. Preserve include, exclude, alias, unset, default,
      null, enum, date, decimal, delimiter, and custom-encoder behavior.
      Update CLI export and recursive segment-counting paths. Test both Python
      data and JSON-facing output; they need not use identical dump modes.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile every production Python
      file with the repository interpreter before broad imports. Treat syntax,
      decorator-call, and indentation errors as immediate regressions. This gate
      is mandatory after any automated edit. Review the actual changed lines
      when compilation fails; never stack further transformations on malformed
      code.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import the shared models,
      settings, parser, both major model families, and representative nested
      transaction modules, then run the exact untruncated collection command.
      Capture its true exit status. Repair the first complete traceback and
      rerun until collection exits zero. Import success is only a checkpoint:
      it does not prove validators execute correctly or satisfy the task.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run tests for settings, shared
      support, both model-version families, list initializers, parser behavior,
      serialization, CLI output, and the transaction modules touched by the
      diff. Run exact node IDs only after confirming they exist. Preserve the
      full failure output and status; do not infer success from truncated output
      or from a shell pipeline that exits zero.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For each migrated validator
      family, compare accepted values, rejected values, normalized output,
      defaults, missing versus null behavior, error locations, and
      serialization against tests and pre-migration intent. Pay special
      attention to field order in `info.data`, validators on defaults,
      after-model attribute access, date qualifiers, adjustment groups,
      duplicate-code checks, and repeatable singleton wrapping. A changed
      exception or silently skipped validator is a migration regression even if
      model construction no longer crashes.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md`. Loop on one complete failure at
      a time: identify the owning migration category, inspect nearby code and
      tests, make the smallest behavior-preserving edit, compile, rerun the
      narrow failing command, then rerun the relevant checkpoint. Revert an
      approach that broadens failures instead of piling fixes on top. Continue
      until focused tests and collection are green; do not stop to provide a
      progress summary while executable failures remain.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and after
      every automated transformation. Inspect `git diff --check`, the full diff,
      changed-file list, decorator syntax, imports, signatures, indentation,
      and function bodies. Confirm no class method lost indentation, no
      decorator acquired duplicate calls or invalid arguments, no annotation
      was deleted, and no source file was unintentionally reset. Remove scratch
      files and unrelated edits.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      `pydantic.v1`, BaseSettings from pydantic, v1 validator decorators,
      root_validator, allow_reuse, SHAPE constants, private ModelField APIs,
      __fields__, field_info.extra, removed constraint keywords, deprecated
      serialization calls, malformed model-validator decorators, and custom
      Field extras outside `json_schema_extra`. Inspect multiline imports.
      Any intentional compatibility use requires explicit task justification;
      native-v2 migration must not rely on the v1 namespace.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Follow `run-full-suite` in `references/verification-and-repair.md` only
      after the static audit passes. Run the repository's exact full-suite
      command without `head`, `tail`, selective paths, early-exit flags, or
      output pipelines that hide status. If output is large, redirect it to a
      log, save `$?` immediately, and inspect the log afterward. Record passed,
      failed, skipped, warning, and collection counts. Any nonzero status
      returns the process to iterative repair.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Exercise representative valid and invalid models, settings loading,
      repeatable lists, parser round trips, domain-string output, Python dumps,
      JSON dumps, schema metadata, and public helper imports. Confirm validator
      bodies still execute and enforce their original rules. A green suite does
      not permit imports from `pydantic.v1`, empty validators, deleted checks,
      unconditional returns, broad exception swallowing, or test weakening.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Re-run compilation, static
      searches, `git diff --check`, the untruncated full suite, and behavior
      smoke tests after the final edit. Inspect `git status --short` and the
      complete diff for accidental files, test modifications, no-op bodies,
      compatibility imports, debug output, generated repair scripts, and
      unrelated dependency churn. Completion is blocked unless every gate
      passes with a recorded zero status.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Follow `report-completion` in
      `references/verification-and-repair.md`. Report the dependency and API
      families migrated, the exact verification commands and their results,
      test counts, and any justified remaining warnings. If interrupted or
      blocked, report the first unresolved traceback, current failing command,
      and changed files rather than claiming completion. Never call the
      migration successful after imports alone, collection alone, a subset of
      tests, or a command whose real exit status was masked.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not import production code from `pydantic.v1` or any other v1 compatibility namespace to make the suite pass.
  - Do not delete, empty, bypass, replace with `pass`, or turn a function or validator body into a no-op merely to make imports or tests proceed.
  - Do not perform blind repository-wide decorator substitutions; field and model validators require semantic signature and return-value changes.
  - Do not run bulk `sed` or regex edits over Python indentation, validator bodies, or multiline imports.
  - Do not convert every model validator to `mode="before"` or every root validator to `mode="after"` without reading what data it needs.
  - Do not leave a before-model validator using an instance-style signature or an after-model validator using a v1 `(cls, values)` mapping body.
  - Do not pass v1-only arguments such as `pre=True` or `allow_reuse=True` to v2 decorators.
  - Do not shadow Pydantic's `field_validator` or `model_validator` with a local partial or registration helper.
  - Do not assume `Optional[T]` supplies a default in Pydantic v2.
  - Do not replace `__fields__` with `model_fields` while retaining v1 `ModelField` attributes such as `shape`, `type_`, `name`, or `field_info.extra`.
  - Do not move custom Field metadata to `json_schema_extra` without updating every metadata reader.
  - Do not add `ClassVar` to a value that must remain a serialized or validated model field.
  - Do not treat an import smoke test as evidence that validator behavior is correct.
  - Do not truncate test execution with `head` or `tail`, or report the exit code of `tee`, `grep`, or another pipeline stage as pytest's result.
  - Do not stop after collection or focused tests; run the exact full suite and preserve its real exit status.
  - Do not continue applying transformations after introducing syntax, indentation, or decorator-call errors; compile and repair immediately.
  - Do not weaken, skip, delete, or rewrite tests solely to make the migration green.
  - Do not create scratch migration plans, codemod scripts, or generated artifacts in the repository and leave them in the final diff.
  - Do not overwrite or reset pre-existing user changes.
  - Do not declare the task complete while any known migration failure, prohibited v1 pattern, accidental diff, or behavior regression remains.
```