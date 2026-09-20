---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 48
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the complete repository suite passes. Before starting and throughout the
  migration, read and follow `references/core-rules.md`. Never redirect production
  imports to `pydantic.v1`, never make a validator or function body empty merely
  to restore imports, never report success from import smoke tests alone, and
  never stop while collection or tests still fail. Preserve original validation,
  parsing, serialization, public-helper, registry, and model-construction
  semantics while replacing v1 interfaces with native v2 equivalents.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, or decorators whose names are not imported
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without truncating away the traceback. If output must be captured,
      write it to a file and separately preserve the test process exit status.
      Do not treat the zero status of `head`, `tail`, `tee`, or another pipeline
      consumer as the pytest status; use `set -o pipefail`, inspect
      `PIPESTATUS`, or run pytest without a masking pipeline. Record collection,
      passing, failing, and error counts plus the first complete traceback.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Resolve the repository
      path once and reuse it exactly; do not alternate among mistyped paths.
      Distinguish pre-existing user changes from migration edits and never erase
      unrelated work.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect dependency metadata,
      requirements-v2 or equivalent migration evidence, CI commands, package
      layout, tests, changelog, and repository documentation before choosing
      edits. Prefer an existing post-migration dependency contract over guessed
      version bounds.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Confirm the interpreter running
      tests imports Pydantic 2 and pydantic-settings. Re-check versions after
      editable installs because dependency resolution can silently downgrade
      Pydantic. Do not modify application code against one major version while
      executing tests against another.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Inventory complete Python statements,
      not only single-line grep matches. Include multiline imports and decorators,
      settings, Config classes, constrained types, Field keywords, reusable
      validators, introspection, serialization, parsing, registries, tests, and
      public compatibility helpers.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Treat names imported
      directly by tests or users as migration contracts even when they are
      underscore-prefixed. Explicitly inventory helper functions such as
      `_is_list_field`, model field order, X12 rendering, settings behavior,
      repeatable-segment wrapping, parser lookup, and generated segment maps.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing each
      validator, recover its complete original body and classify what it reads,
      mutates, returns, and raises. A successful import obtained by commenting
      out a validator, replacing it with a no-op, or emptying its body is a
      migration failure rather than progress.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Record every affected file,
      original construct, native-v2 replacement, semantic risks, dependent
      tests, current status, and verification command. Keep unresolved items in
      the ledger instead of relying on memory.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical renames from
      semantic migrations. Decorator and signature changes, Optional behavior,
      model validators, metadata, constrained types, inherited fields, and
      introspection are semantic work and must not be handled by blind global
      replacement.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Limit each checkpoint to a
      coherent change, then compile and import the touched module before moving
      on. Avoid spending an entire attempt surveying, writing plans, or editing
      dozens of files without executing the next verification gate.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Inspect the actual
      working tree, not an assumed clean baseline. Repair syntax errors,
      malformed imports, duplicated decorators, invalid booleans such as
      lowercase `true`, damaged regex literals, indentation damage, accidental
      comments, and partially transformed signatures before applying more
      migration edits. Restore only damaged hunks, not unrelated user changes.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Repair the first complete
      collection traceback before broad edits. After every repair, rerun the
      narrowest import or collection command that reproduces it, then continue
      to the next blocker. A smoke import is only a checkpoint and never the
      completion criterion.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move BaseSettings to
      pydantic-settings, migrate settings configuration, change Field regex to
      pattern where applicable, preserve environment semantics, and update all
      dependency declarations consistently. Use native Pydantic 2 imports;
      importing production code from `pydantic.v1` is prohibited even if tests
      appear to pass.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert Config classes
      to ConfigDict or valid model_config values while preserving enum values,
      frozen or mutation behavior, extra-field policy, aliases, defaults, and
      inherited configuration. Verify representative model construction after
      this change.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      annotated overrides of inherited fields. Find every unannotated subclass
      assignment such as `segment_name = ...`, add the correct annotation, and
      preserve the field rather than deleting all subclass declarations.
      Verify class creation and registry defaults after each affected family.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Migrate removed Field and
      constrained-type arguments such as regex to pattern, preserve anchors and
      escaping exactly, migrate list constraints deliberately, and move custom
      metadata such as `is_component` into json_schema_extra using valid Python
      values. Audit Optional fields and defaults rather than assuming Optional
      means not required in v2.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      allow_reuse without creating recursive aliases or shadowing Pydantic's
      `field_validator`. Reusable validation functions must retain their
      business logic and receive the v2 context they require. Confirm every
      decorator factory used by segment modules is callable under Pydantic 2.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert validator to
      field_validator one function at a time. Replace v1 `values`, `field`, and
      `config` parameters with supported v2 signatures, usually ValidationInfo
      and `info.data`, while preserving ordering assumptions and pre-validation
      mode. Add classmethod only where appropriate. Do not mechanically rename a
      decorator while leaving an incompatible signature.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      decide from its original body whether it operates on raw input mappings or
      validated model instances. Record before versus after mode, expected
      argument type, mutation strategy, return type, ordering requirements, and
      affected failure behavior. Do not infer the mode from decorator spelling
      alone in an already damaged partial migration.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `model_validator(mode="before")` methods that accept and return input data.
      Convert post root validators to `model_validator(mode="after")` instance
      methods that inspect or mutate `self` and return `self`. Rewrite dict
      access only after confirming the mode. Preserve complete function bodies,
      error messages, and business rules; never insert `pass`, unconditional
      returns, or empty bodies just to make imports succeed.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Statistically compare
      decorator usage with imports in every production module. Every use of
      field_validator, model_validator, ValidationInfo, ConfigDict, or
      pydantic-settings must have a valid import; every removed v1 decorator
      import must have no remaining use. Compile and directly import both large
      versioned segment modules. A NameError such as undefined
      `field_validator` is a collection blocker and must be fixed before any
      further broad migration.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__, ModelField,
      SHAPE_LIST, type_, name, and field_info.extra usage with native v2
      model_fields, annotations, field names from iteration, and
      json_schema_extra. Account for Annotated, Optional, Union, list, and
      inherited annotations. Do not import removed internals merely to suppress
      an error.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Keep the public helper at the
      module path expected by tests and callers, including
      `x12sdk.models._is_list_field` when that is the contract. Implement it
      against Pydantic v2 FieldInfo annotations and support direct list,
      Optional list, Union list, and Annotated list forms. Avoid introducing a
      circular import by moving the helper into an unrelated module without
      preserving the original export. Test the helper directly before loop
      collection.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace v1 parsing and
      serialization methods with model_validate, model_dump, and
      model_dump_json only where equivalent. Preserve exclusion flags, enum and
      date output, aliases, delimiters, field order, custom JSON encoding, X12
      rendering, recursive segment counting, and support for dictionaries versus
      model instances. Do not globally rename unrelated uses of `dict`, `json`,
      `schema`, `pattern`, or regular-expression variables.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Verify import-time registries
      and maps that inspect model fields, especially segment-name defaults.
      Replace __fields__ access with model_fields without changing keys or
      values. Confirm representative registry lookups for both supported X12
      versions and ensure annotated inherited-field overrides remain discoverable.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or equivalent over
      production code after every batch transformation. Treat malformed imports,
      indentation errors, duplicated decorators, stray colons, broken strings,
      and accidental comment-outs as immediate blockers. Never continue semantic
      debugging while syntax is broken.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Directly import core
      models, settings, both versioned segment modules, representative
      transaction modules, and public helpers; then run complete test
      collection. Capture the real exit status. Do not claim collection works
      because one module imports or because command output was piped through a
      successful truncation command.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for settings,
      shared models, support utilities, both segment versions, repeatable
      segments, loop initialization, parsing, serialization, and transaction
      construction. Use `-x` only to isolate the next failure; subsequently run
      the entire focused file to expose sibling failures.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare accepted inputs,
      rejected inputs, coercion, defaults, validator ordering, error locations,
      messages where contractual, enum handling, and serialized output with the
      semantic snapshots. Passing imports and a handful of tests do not prove
      behavior preservation.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work from the first complete
      current traceback, make the smallest behavior-preserving fix, compile,
      rerun the narrow reproducer, and then rerun the broader gate. Continue
      until the full suite is green. Do not end the task with a summary, a plan,
      a progress report, or the phrase "task completed" while any collection
      error, failure, syntax error, or unverified ledger item remains.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every sed, regex, or scripted
      transformation in the diff. Specifically search for duplicated imports,
      malformed decorators, changed indentation, lowercase JSON booleans in
      Python, corrupted regex literals, unintended replacements of ordinary
      `pattern` or `dict` variables, missing function bodies, and deleted
      validation logic. Prefer targeted edits; revert an unsafe batch edit and
      reapply it narrowly rather than layering more regex repairs onto damage.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for all
      prohibited v1 APIs and for native-v2 decorators lacking imports. Also
      search for `pydantic.v1`, empty or pass-only migrated functions, commented
      validator assignments, stale root_validator or validator imports,
      allow_reuse, SHAPE_LIST, __fields__, field_info.extra, malformed source,
      and compatibility shims that bypass native v2 behavior. Explain any
      intentional residual match.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact complete repository test command without output
      truncation that masks status. Record collected, passed, failed, errored,
      skipped, and warning counts. The gate passes only when the command itself
      exits successfully, not when a downstream pipe exits successfully.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Verify public imports,
      settings, validation failures, parsing, serialization, X12 output,
      repeatable-segment wrapping, helper exports, registries, and representative
      transaction workflows. Confirm no production import points to
      `pydantic.v1` and no function was emptied or disabled to obtain green
      tests.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the complete diff and
      status for accidental scripts, migration plans, summaries, caches,
      environment files, or unrelated edits. Re-run compile, static audit,
      collection, and the full suite after the last source edit. The final gate
      fails if there is any unresolved ledger item, hidden test status, syntax
      damage, `pydantic.v1` import, empty migrated body, or failing test.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report only verified changes and include
      the exact successful full-suite command and counts, targeted behavior
      checks, static-audit result, runtime versions, and any intentional
      warnings. If the suite is not green, do not call the migration complete;
      instead continue the repair loop or clearly report the unresolved blocker
      and its complete traceback.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not import production code from `pydantic.v1`, even as a temporary shortcut or compatibility shim.
  - Do not empty, comment out, replace with pass, or add an unconditional return to a validator or function merely so the module imports.
  - Do not stop after import smoke tests, successful collection, one focused file, or a partial pass count; the complete suite is the completion gate.
  - Do not infer pytest success from a pipeline ending in head, tail, tee, grep, or another successful consumer.
  - Do not perform blind repository-wide decorator, regex, dict, json, schema, pattern, import, or signature replacements.
  - Do not migrate root validators by changing only the decorator; classify raw-data versus instance semantics and rewrite the signature and return value.
  - Do not delete inherited field declarations to silence Pydantic v2 annotation errors; annotate and preserve them.
  - Do not remove public underscore-prefixed helpers merely because they appear internal when tests or callers import them.
  - Do not move `_is_list_field` in a way that breaks `x12sdk.models._is_list_field` or creates a circular import.
  - Do not trust a passing compile or import check to prove runtime validation, serialization, parser, registry, or transaction behavior.
  - Do not continue broad edits after syntax corruption; recover the source and re-establish compile and import gates first.
  - Do not repeatedly survey or write summaries while a known executable next step remains; fix the first current traceback and rerun its gate.
  - Do not create migration summaries, temporary repair scripts, or plan files in the repository unless they are requested or part of the repository contract.
```