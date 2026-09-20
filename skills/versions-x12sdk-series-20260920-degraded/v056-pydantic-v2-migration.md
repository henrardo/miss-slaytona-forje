---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 56
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's complete, untruncated test command exits successfully.
  Preserve public APIs, validation timing, defaults, error behavior, parsing,
  serialization, helpers, and generated registries. Repair the repository in
  small verified checkpoints rather than applying speculative bulk rewrites.
  Never route production imports through pydantic.v1, never empty or bypass a
  function body merely to make imports succeed, and never report completion
  while collection, focused tests, static audits, or the full suite still fail.
  Before starting and throughout the migration, read and enforce
  `references/core-rules.md`.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, duplicated decorator arguments, or accidental edits outside Pydantic syntax

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
      command without truncating its output. If logging to a file, preserve the
      test process exit status explicitly; do not infer success from a pipeline
      ending in head, tail, tee, or grep. Capture the first complete traceback,
      collection count, pass count, fail count, warnings, command, and exit
      code. A command that prints failures but exits zero because its output was
      piped through head is not a valid baseline.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the exact
      repository path before every scripted or destructive operation. Record
      tracked changes and untracked files. Do not reset, checkout, overwrite,
      or clean pre-existing user work. Treat repeated path typos as a signal to
      stop and re-confirm the current directory rather than continuing edits.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject.toml,
      lockfiles, requirements files, CI workflows, package entry points,
      compatibility metadata, test configuration, and any supplied
      post-migration requirements file. Use the repository's declared command
      and dependency contract rather than inventing a setup.py, requirements.txt,
      or test target that does not exist.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Install or select the intended
      Pydantic v2 and pydantic-settings environment using the repository's
      package workflow. After every dependency installation, print and record
      the active Python executable, Pydantic version, pydantic-settings version,
      and package import location because editable installs and dependency
      resolution can silently downgrade Pydantic. Do not edit production code
      against a runtime that still imports Pydantic 1.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      scripts, generated modules, and package metadata for BaseSettings,
      class Config, validator, root_validator, allow_reuse, always, each_item,
      values and field validator parameters, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, regex, constr(regex=...), min_items,
      max_items, dict, json, parse_obj, parse_raw, from_orm, copy, schema,
      construct, private Pydantic imports, and pydantic.v1. Record file, line,
      symbol, enclosing class, and whether the use is public, internal,
      generated, or test-only.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include public
      settings, models, parser and reader classes, CLI output, x12 methods,
      serialization shape, field order, validation errors, convenience
      functions, test-imported private helpers such as _is_list_field, and
      registries built during module import. Search tests before renaming or
      relocating helpers. A helper imported directly by tests or downstream
      modules remains part of the migration contract even if its name begins
      with an underscore.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing each
      validator or serializer, retrieve its complete original body from the
      clean working-tree version or git baseline and record its fields,
      ordering assumptions, validation phase, accepted input forms, mutations,
      return type, and error text. If a prior partial migration malformed a
      function, use the original source as semantic evidence. Never reconstruct
      semantics from a truncated snippet, decorator name alone, or generic
      migration advice.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per
      migration site with original form, target native-v2 form, semantic risks,
      dependent tests, current status, and verification command. Include
      collection blockers, public helpers, inherited-field overrides,
      generated registries, field metadata consumers, reusable validators,
      parsing code, serialization code, and damaged partial edits.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by dependency:
      malformed syntax and imports, settings, shared model bases, inherited
      fields and constraints, reusable validator infrastructure, field
      validators, model validators, introspection, parsing and serialization,
      registries, then behavioral failures. Distinguish mechanical renames from
      semantic rewrites. Do not classify decorator migration as a global text
      substitution.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Work on one coherent
      surface at a time. After each edit, compile the changed file and run its
      narrowest import or focused test. Inspect git diff before broadening the
      change. If an automated transformation touches more locations than
      intended, restore only those migration-owned edits and replace the
      transformation with explicit edits.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile all
      production Python first. Search for malformed forms such as
      @model_validator(mode="before")pre=True), duplicated mode arguments,
      decorator calls with stray parentheses, imports damaged by sed, lowercase
      true or false in Python, broken regex literals, misplaced indentation,
      commented-out validator assignments, and empty bodies. Compare each
      damaged region with the git baseline and reapply the native-v2 change
      manually. Do not continue semantic migration on syntactically corrupted
      files.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the earliest
      complete traceback that prevents collection, then rerun collection to
      expose the next blocker. Prefer direct import probes for the implicated
      module. Do not summarize the migration or stop after making one import
      succeed; collection is only the first gate.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Change the dependency
      contract to native Pydantic v2 and add pydantic-settings when BaseSettings
      is used. Import BaseSettings and SettingsConfigDict from
      pydantic_settings, not pydantic. Translate settings Config semantics,
      including case sensitivity, environment prefixes, aliases, and dotenv
      behavior. Replace Field(regex=...) with Field(pattern=...) without
      damaging anchors or grouping. Import and instantiate the settings class
      after the edit, including environment-driven cases covered by tests.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate each inner
      Config class to ConfigDict or an equivalent v2 configuration while
      preserving extra handling, enum values, immutability, aliases,
      population rules, assignment validation, arbitrary types, and serializer
      behavior. Apply configuration to the correct shared base class rather
      than copying it indiscriminately into every subclass. Verify delimiter
      models remain immutable and hashable where required.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. In Pydantic v2, any
      subclass override of an inherited model field must retain an annotation.
      Find unannotated assignments such as
      `segment_name = X12SegmentName.CR5` and rewrite them with the inherited
      type rather than deleting the field or loosening the base model. Import
      each segment module after this pass and verify registry keys still use
      the intended segment names.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Translate regex to pattern,
      constr(regex=...) to constr(pattern=...), min_items and max_items to the
      correct v2 list constraints, and arbitrary Field metadata to
      json_schema_extra. Use Python `True`, never JSON `true`. Preserve
      `is_component` metadata because parsing and X12 serialization consume it.
      Do not globally add `default=None` to every Optional annotation:
      Optional controls accepted values, while a default controls requiredness.
      Change defaults only when original behavior or tests establish that the
      field was optional at construction time.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `allow_reuse`; do not create a functools.partial that passes
      allow_reuse to field_validator because v2 rejects it. Keep reusable
      validation logic as plain functions and bind it with native
      field_validator or model_validator decorators at the model site. Preserve
      callable names used by class attributes and imports. Verify reusable
      validators with direct valid and invalid examples before migrating their
      callers.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each v1 validator
      individually. Map pre=True to mode="before"; use ValidationInfo for
      already-validated peer data through `info.data`; preserve field order
      assumptions, always-like behavior, and validation of defaults explicitly.
      Add @classmethod where the chosen v2 decorator form requires it. Do not
      retain v1 signatures such as `(cls, value, values)` under
      @field_validator. For shared date validators, confirm the qualifier field
      is available at the same phase before changing code.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it consumes raw dictionaries, validated values, or model
      instances; whether it mutates input; whether it counts nested models;
      whether it must run after field failure; and what it returns. Classify
      raw-dictionary validators as mode="before". Classify validated-model
      invariants as mode="after". Do not infer the mode from the absence of
      `pre=True` alone without reading the body and callers.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. A mode="before" validator
      receives raw input and must return raw input. A mode="after" validator
      normally receives `self`, reads attributes instead of values.get, and
      returns `self`. Preserve original mutations and error messages. Rewrite
      reusable root-validator assignments explicitly rather than mechanically
      inserting decorators. Never decorate an old `(cls, values)` body with
      mode="after" and assume it remains valid. Never empty, comment out,
      replace with `pass`, or return early from a validator merely to make the
      module import.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every file,
      compare decorator names used in source with names imported from
      Pydantic. Remove stale validator and root_validator imports only after all
      uses are migrated. Add field_validator, model_validator, and
      ValidationInfo only where actually used. Compile and import every
      transaction family, not just the two top-level segment modules. Detect
      NameError failures caused by decorators whose imports were removed in an
      earlier partial pass.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields and adapt to FieldInfo rather than assuming v1 ModelField
      attributes such as shape, type_, name, or field_info exist. Read custom
      metadata from `field.json_schema_extra or {}`. Use typing.get_origin and
      typing.get_args for list, union, and optional annotations. Preserve field
      declaration order used by positional X12 parsing and output. Test
      introspection against concrete segment and loop classes.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Keep the repository's public
      `_is_list_field` helper importable from the module expected by tests and
      callers. Make it accept the annotation form passed by
      `model_fields[name].annotation`, including direct List values and unions
      containing a list. Use it in the before-model validator that wraps a
      single repeatable segment dictionary in a list. Verify both scalar-list
      detection and single-dictionary wrapping across representative loop
      models.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace v1 model
      methods with model_dump, model_dump_json, model_validate,
      model_validate_json, model_copy, model_json_schema, or model_construct
      only where semantics match. Preserve exclusion flags, enum output,
      aliases, defaults, decimal and date handling, delimiters, component
      fields, nested models, and X12 field ordering. Update CLI export,
      segment parsing, delimiter injection, count_segments, duplicate-code
      validators, and adjustment calculations. Do not replace every `.dict`
      token blindly; distinguish model methods from ordinary dictionaries.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit module-level loops that
      inspect model fields to build segment registries or parser maps. Replace
      `a.__fields__["segment_name"].default` with the corresponding safe
      model_fields access while retaining enum-to-key conversion and excluding
      abstract base classes. Confirm known 4010 and 5010 segment keys resolve to
      the correct classes. Treat an importable but empty or incomplete registry
      as a migration failure.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile over
      the complete production package and fail on any syntax or indentation
      error. Search again for malformed decorator fragments, accidental
      comments, invalid booleans, damaged patterns, duplicate imports, and
      suspiciously empty function bodies. Compilation success is necessary but
      not sufficient.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core settings,
      models, support, parsing, both top-level segment modules, every
      transaction package, public helpers, and registry modules. Then run the
      complete collection command without piping it through a truncating
      command. Record the genuine exit status and collected count. Do not move
      to behavioral tests until imports and collection succeed.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, support utilities, 4010 and 5010 segments, loop initializers,
      repeatable segments, parsing, serialization, registries, CLI output, and
      every validator family changed. Include valid and invalid fixtures. A
      subset pass does not authorize completion; use it only to localize the
      next repair.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare requiredness,
      accepted input types, normalization, validation order, defaults, model
      mutation, output shape, and error messages against semantic snapshots and
      tests. Pay special attention to Optional fields, default validation,
      before versus after model validators, peer-field access, nested model
      counting, and enum serialization. Reject changes that merely silence an
      error by weakening validation.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. On each failure, read the
      complete traceback, identify the earliest root cause, inspect the full
      original function and current diff, make the smallest coherent fix, then
      rerun compile, import, collection, and the narrow failing test. Keep
      working until the full suite is green. Do not end a turn with a progress
      summary while known failures remain and tools are available.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Inspect every hunk produced by sed,
      regex scripts, codemods, formatters, or batch replacements. Confirm that
      imports remain syntactically valid, decorator modes are correct,
      indentation is unchanged, regex literals retain meaning, Python booleans
      are valid, and unrelated code was not altered. Prefer AST-aware tools or
      explicit edits; a successful script exit does not prove a correct edit.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, validator,
      root_validator, allow_reuse, SHAPE_LIST, ModelField assumptions,
      __fields__, field_info.extra, unsupported Field(regex=...), malformed
      model_validator syntax, commented-out validator assignments, and empty
      bodies. Review any remaining v1 names in documentation or comments
      separately from executable code.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's complete canonical test command with no
      test selection, no `|| true`, no swallowed exit status, and no head or
      tail pipeline. Capture full output to a file if needed, but preserve the
      test process status using shell variables or pipefail. Record collected,
      passed, failed, skipped, xfailed, warnings, duration, and exit code.
      Continue repair unless the real exit code is zero.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Exercise public imports,
      settings construction, immutable delimiters, segment validation,
      repeatable-loop wrapping, parser lookup, X12 rendering, model dumping,
      registry lookup, CLI export, and representative invalid inputs. Confirm
      no validator, parser, serializer, helper, or registry was bypassed,
      emptied, deleted, or weakened merely to obtain green tests.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Review the complete diff and
      git status. Ensure dependency metadata names native v2 packages, no
      production import points to pydantic.v1, no migration scratch files were
      added unintentionally, no user changes were overwritten, no function body
      was emptied, and every changed behavior is justified by the ledger.
      Re-run compile, static audit, and the complete suite after any final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report the exact full-suite command and
      genuine result, runtime versions, major migration surfaces changed,
      public contracts verified, and any remaining warnings or risks. State
      completion only when compile, imports, collection, focused tests, static
      audit, full suite, behavior verification, and final diff review all pass.
      If blocked, report the current complete traceback and remaining ledger
      items instead of claiming success.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; that hides rather than completes the native-v2 migration.
  - Never empty, delete, comment out, replace with pass, or force an early return from a validator, parser, serializer, helper, or registry builder merely so imports or tests proceed.
  - Never convert every root_validator to one model_validator mode with a global replacement; classify each body as raw-input before validation or model-instance after validation.
  - Never leave a v1 `(cls, values)` function body under a v2 mode="after" decorator without rewriting its signature and field access.
  - Never pass `pre=True` or `allow_reuse=True` to native v2 decorators.
  - Never implement reusable field validators as `functools.partial(field_validator, allow_reuse=True)`.
  - Never use broad sed or regex replacements on decorators, imports, Optional fields, Field arguments, or regular expressions without reviewing every changed hunk.
  - Never globally add `default=None` to Optional fields; preserve requiredness from the original contract.
  - Never use JSON lowercase `true` or `false` in Python source.
  - Never remove inherited field annotations from subclass overrides such as `segment_name`.
  - Never discard `json_schema_extra` metadata consumed by parsing or X12 serialization.
  - Never remove or relocate a helper such as `_is_list_field` without checking direct test and downstream imports.
  - Never assume an importable registry is correct; verify representative keys and classes.
  - Never treat compile success, import success, collection success, or a focused subset as proof that the migration is complete.
  - Never truncate the authoritative test command through head or tail, and never accept a pipeline's final zero status as the test runner's status.
  - Never run `git checkout`, reset, clean, or restore over pre-existing user changes; restore only migration-owned damage with explicit scope.
  - Never create speculative setup.py or requirements.txt files when the repository uses another dependency contract.
  - Never stop after describing remaining work while tools and failing tests are still available.
```