---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 58
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's complete, untruncated test command exits successfully.
  Preserve every validator body, public helper, parser, serializer, registry,
  field constraint, validation phase, and error contract. Never route production
  imports through pydantic.v1, and never empty, stub, comment out, or bypass a
  function merely to make imports or tests proceed. Before starting and
  throughout the migration, read and enforce `references/core-rules.md`.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, duplicated decorator arguments, or accidental edits outside Pydantic syntax
  - Test commands were piped through head, tail, tee, or grep and therefore appeared successful despite pytest failing
  - A migration repeatedly cycles between import errors because broad search-and-replace changed decorators without adapting signatures and function bodies

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native migration

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without truncating the executing pipeline. If output is large,
      redirect the complete output to a file, save the test process's exit
      status, and inspect the file afterward; never use the exit status of
      `head`, `tail`, `tee`, or `grep` as the test result. Record the first
      complete traceback, collection count, passing count, failing count, and
      command exit status. Do not claim a baseline pass when zero tests ran.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the exact
      repository path before every destructive or batch operation. Inventory
      all pre-existing tracked, untracked, staged, and unstaged changes and
      distinguish them from migration edits. Never overwrite user work, run a
      wholesale checkout or reset, or restore an entire production directory
      merely to recover one damaged file.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Identify the authoritative
      dependency files, package layout, supported Python versions, CI command,
      test configuration, generated-code conventions, and any post-migration
      requirement file. Treat tests, changelog entries, and existing public
      imports as contracts rather than incidental implementation details.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter used by
      tests imports native Pydantic 2 and required split packages such as
      pydantic-settings. Re-check versions after editable installs because
      dependency resolution can silently downgrade Pydantic. Do not use
      pydantic.v1 to make the source import.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      fixtures, package metadata, and generated modules for every v1 surface,
      including multiline imports and decorator aliases. Record counts and
      exact locations before editing so later static audits can prove the
      inventory was closed rather than merely hidden.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include imported
      underscore-prefixed helpers, model field metadata, inherited fields,
      repeatable-list normalization, X12 rendering, parser registries, settings
      environment behavior, and validation error expectations. A helper used by
      tests is part of the required contract even if the pre-migration source
      accidentally lacks it.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. For each validator, capture
      its complete original decorator, signature, body, fields read, fields
      written, ordering assumptions, input phase, return type, and exceptions.
      Retrieve the clean original from version control when a partial migration
      has malformed it. Never infer semantics from a damaged decorator alone,
      and never delete or empty a body to remove an error.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Give every discovered occurrence
      a row containing file, symbol, v1 construct, intended v2 construct,
      semantic risk, dependencies, checkpoint command, and status. Add newly
      discovered failures to the ledger instead of abandoning the procedure or
      repeatedly rediscovering the same issue.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical low-risk
      renames from semantic migrations. Decorator changes, signatures,
      inherited fields, Optional requiredness, metadata, date parsing,
      serialization, list detection, and registries are semantic work and must
      be reviewed individually rather than handled by unbounded substitutions.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Work in small coherent
      batches and run compile/import/collection checks after each batch.
      Preserve a recoverable diff for each checkpoint. Do not combine unrelated
      validator, constraint, metadata, and serialization rewrites into one
      unreviewable operation.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Search explicitly for
      malformed forms such as `@model_validator(pre=True)`,
      `@model_validator(mode="before")pre=True)`, duplicated mode arguments,
      extra parentheses, invalid lowercase Python booleans, broken regex
      literals, damaged imports, indentation errors, and commented-out
      validator assignments. Compare suspect functions against the original
      source and restore their complete behavior. Compile touched files before
      proceeding.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix one complete
      traceback at a time, starting with syntax and import blockers. Re-run the
      smallest command that reproduces the blocker, then collection. Do not
      stop after a module imports, report completion while collection still
      fails, or replace an error with a compatibility shim forbidden by this
      procedure.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update every
      authoritative dependency declaration to native Pydantic 2 and add
      pydantic-settings where BaseSettings is used. Move BaseSettings and
      SettingsConfigDict imports to pydantic_settings, translate settings
      Config behavior exactly, and replace Field(regex=...) with
      Field(pattern=...) without corrupting the regular expression. Verify
      defaults, environment case sensitivity, aliases, and cached settings.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate every
      class-based Config option to ConfigDict or model_config while preserving
      enum conversion, extra-field policy, immutability, aliases, assignment
      validation, and arbitrary-type behavior. Do not leave Config and
      model_config together on the same inheritance path, and do not broaden
      extra-field acceptance to suppress errors.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic 2 requires an
      annotation when a subclass overrides an inherited model field. Find all
      unannotated assignments such as `segment_name = ...` and add the correct
      inherited annotation rather than deleting the field or changing it to an
      unvalidated class variable. Check dynamically discovered segment classes
      as well as directly imported models.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Translate removed constraints
      precisely, including regex to pattern and constrained type argument
      changes. Move custom Field extras such as `is_component` into
      json_schema_extra using valid Python values. Preserve Optional
      requiredness deliberately: in Pydantic 2 `Optional[T]` without a default
      remains required, so add `default=None` only when v1 behavior or tests
      prove omission was allowed. Never run a global Optional rewrite.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      allow_reuse because v2 handles reuse differently, but preserve each
      callable's registration and validation phase. Do not shadow the imported
      field_validator decorator with a partial of the same name. Verify every
      reusable date, identifier, duplicate-code, and loop validator against
      multiple models that consume it.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert validator to
      field_validator with the proper mode and classmethod form. Replace v1
      `values` access with ValidationInfo and `info.data` only where equivalent;
      account for field declaration order because `info.data` contains only
      previously validated fields. Preserve always/pre behavior deliberately.
      Test standalone decorator assignments as well as `@validator` methods.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. Classify every
      root_validator individually as before or after from its original timing
      and body. A v1 pre=True validator maps to mode="before" and receives raw
      input data. A v1 post validator normally maps to mode="after" and receives
      the model instance; it is not safe to label every root validator before
      merely because its old body expects a dictionary. Record validators
      attached by assignment as well as decorated methods.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre validators to
      `@model_validator(mode="before")` with a raw-data signature and return the
      raw data. Convert post validators to
      `@model_validator(mode="after")` with an instance signature, use
      attributes instead of dict-only `.get()` access, and return `self`.
      Preserve validation order and error behavior. Never pass `pre=True` to
      model_validator, never leave a bare `@model_validator`, and never perform
      a decorator-only replacement while retaining an incompatible body.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every Python
      file, compare decorators and decorator assignments with imported names.
      Ensure field_validator, model_validator, ValidationInfo, and any helper
      are imported exactly where used; remove stale validator and
      root_validator imports only after their final use is migrated. Compile
      every affected module to catch NameError and malformed multiline imports.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__,
      ModelField, SHAPE_LIST, field_info.extra, type_, name, and shape-dependent
      logic with model_fields, FieldInfo.annotation, typing.get_origin and
      get_args, json_schema_extra, and explicit field-name iteration. Handle
      Optional, Annotated, Union, list subclasses, forward references, and
      None metadata safely. Do not assume every json_schema_extra value is a
      non-null dictionary.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or implement the
      public `_is_list_field` helper in the module from which callers import
      it, not only in an unrelated support module. Use v2 FieldInfo annotations
      and typing introspection. Verify repeatable-segment wrapping for direct
      List, Optional[List], Annotated, and non-list fields, and keep the
      before-model validator's dict input unmodified except for intended
      single-item wrapping.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict, json,
      parse_obj, copy, schema, and related APIs with native v2 equivalents only
      after checking mode and output semantics. Preserve enum values, Decimal
      and date handling, unset/none exclusions, aliases, custom JSON encoding,
      delimiters, recursive segment counting, and X12 ordering. Do not replace
      arbitrary dictionary methods that are unrelated to Pydantic.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit module-bottom
      registries that inspect model classes or segment_name defaults. Replace
      class __fields__ access with model_fields without changing keys, enum
      normalization, filtering, or registration order. Import both major
      version segment modules and compare representative registry entries with
      their class field defaults.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile the complete production
      package, not only recently edited files. Treat syntax errors,
      indentation errors, malformed decorators, and missing names as blockers.
      Repair from the original source rather than commenting out the failing
      code.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, parser modules, both versioned segment modules, transaction
      modules, public helpers, and registries. Then run complete test
      collection and require a successful pytest exit with a nonzero expected
      item count. Capture untruncated output and the actual process status.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, shared models, 4010 and 5010 segments, loop initialization,
      repeatable segments, support utilities, parsing, serialization, and
      transaction validation. Run commands directly or capture their real exit
      status; a displayed traceback combined with shell exit zero from `head`
      is a failure, not a pass.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare valid construction,
      invalid construction, omitted Optional fields, before/after timing,
      normalized values, exception types, error locations, and serialized
      output against tests and semantic snapshots. Do not accept import success
      as proof that validators still run.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Use the loop: run the
      smallest real reproducer, read its complete traceback, inspect the full
      relevant original and migrated function, make one semantic fix, compile,
      rerun the reproducer, rerun collection, and periodically rerun the full
      suite. Continue until green; do not end with a progress summary, a plan
      for later, or a subset count while any required test fails.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every batch or scripted
      replacement in the diff. Search for edits to unrelated regex use,
      re.compile calls, strings, comments, booleans, import formatting,
      indentation, Optional fields, decorator modes, and function bodies.
      Revert only the specific bad hunk; never discard the entire migration
      directory to recover from one broad edit.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Re-run the original inventory
      searches plus malformed-pattern searches. Prove that no production import
      points to pydantic.v1, no forbidden v1 interface remains, all decorators
      have matching imports and signatures, no function body was emptied or
      replaced with pass/ellipsis solely to import, and no migration helper was
      added only outside its required public module.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's authoritative complete command without
      output truncation or pipeline status masking. If output must be captured,
      write it to a file and separately record pytest's exit status. Require
      exit zero, the expected collection count, and no collection errors,
      failures, or unexpected skips.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm public imports,
      model APIs, settings, parser behavior, X12 output, metadata-driven
      component handling, list wrapping, registry lookup, and representative
      validation errors. Treat warnings about deprecated v1 APIs as unfinished
      native migration work when they originate in production code.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the complete diff and
      working-tree status. Remove accidental migration plans, scratch scripts,
      summaries, or generated artifacts unless explicitly required. Verify
      dependency files and source changes are present, user changes remain
      intact, no pydantic.v1 routing exists, no function was hollowed out, and
      the final full-suite evidence is from the current tree.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only after every gate
      passes. Include the authoritative command, actual exit status, collected
      and passed counts, important behavior-preservation checks, and files
      changed. If any gate is not green, continue repairing rather than
      presenting partial progress as a completed migration.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to pydantic.v1, even temporarily as the submitted solution.
  - Never empty, stub, comment out, replace with pass or ellipsis, or otherwise bypass a function body so a module imports.
  - Never mass-replace root_validator with one model_validator mode; classify every validator from its original semantics.
  - Never change only a decorator while leaving an incompatible v1 signature and dictionary-based body.
  - Never use `@model_validator(pre=True)`, a bare `@model_validator`, duplicated mode arguments, or malformed decorator parentheses.
  - Never assume a v1 post root validator can become mode="before" merely because its old parameter is named values.
  - Never globally add `default=None` to Optional fields; preserve intentional required Optional fields.
  - Never globally replace every occurrence of regex, dict, json, copy, or Config without proving it is a Pydantic API use.
  - Never use broad sed or regex edits without immediately compiling, inspecting the diff, and testing every touched pattern.
  - Never trust the exit status of a pipeline ending in head, tail, tee, or grep as the pytest result.
  - Never declare success from import checks, collection alone, a focused subset, warnings-only output, or zero tests collected.
  - Never stop at a summary of remaining work; continue until the authoritative full suite passes.
  - Never run wholesale git checkout, restore, or reset over migration and user changes to recover from one malformed edit.
  - Never write migration summaries, repair scripts, or plans into the repository unless they are required deliverables.
  - Never relocate a required public helper such as `_is_list_field` to a different module without preserving its original import path.
  - Never use invalid JSON booleans such as `true` in Python source; use Python `True`.
  - Never suppress extra-field, inherited-field, or validation errors by weakening model configuration without contract evidence.
  - Never remove inherited model fields such as segment_name to avoid Pydantic 2 annotation requirements; annotate overrides correctly.
  - Never treat deprecated production APIs as complete native migration merely because Pydantic 2 still provides compatibility warnings.
```