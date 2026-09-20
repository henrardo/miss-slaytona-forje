---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 52
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the complete repository suite passes. Preserve public APIs, validator
  timing, error behavior, parsing, serialization, metadata, and generated
  registries. Before starting and throughout the migration, read and enforce
  `references/core-rules.md`. Never route production imports through
  `pydantic.v1`, and never empty, stub, comment out, or bypass a function body
  merely to make imports or tests proceed.

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
      command without piping it through `head`, `tail`, `tee`, or another
      command that can hide pytest's exit status. Save the complete first
      traceback, collection count, pass count, failure count, command, and
      actual exit code. If output must be captured, redirect it to a file,
      preserve `$?`, and inspect the file afterward. Do not call a failed suite
      successful because a pipeline returned zero.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the exact
      repository path before every scripted batch operation. Record tracked,
      untracked, staged, and unstaged changes. Distinguish pre-existing user
      work from migration edits; never discard, reset, overwrite, or check out
      pre-existing work without authorization.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect dependency metadata,
      lock files, CI commands, package layout, test configuration,
      `requirements-v2.txt` or equivalent target notes, and public entry
      points. Treat repository-specific migration tests and comments as
      contracts rather than optional hints.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter,
      executable, pytest, Pydantic, pydantic-core, and pydantic-settings
      versions used by the test command. Recheck versions after editable
      installs because dependency resolution can silently downgrade Pydantic.
      Use native Pydantic v2; do not solve runtime mismatch with
      `pydantic.v1`.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests, and
      package metadata for every v1 surface, including multiline imports and
      decorator aliases. Inventory BaseSettings, Config classes, validators,
      validator factories, allow_reuse, Field extras and constraints,
      constrained types, model methods, field introspection, schemas,
      parsing, serialization, generated registries, and compatibility imports.
      Record file, symbol, line, semantic role, and likely v2 replacement.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include importable
      helpers even when their names begin with an underscore if tests or users
      import them. Record model constructors, settings behavior, `.x12()`,
      serialization output, validation errors, repeatable-segment coercion,
      registry contents, CLI behavior, parser behavior, and exported helpers
      such as list-field predicates.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing a validator,
      recover and read its complete original decorator, signature, body, field
      order assumptions, callers, tests, and return value. Use the clean
      committed source or saved checkpoint to recover intent when a partial
      migration has already malformed the working copy. Never infer a
      validator's semantics solely from its name.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Build a ledger with one row per
      migration site and columns for original construct, intended semantics,
      target construct, imports, signature changes, verification command,
      status, and observed failure. Keep it current so remaining work is not
      guessed from a single grep or traceback.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical renames from
      semantic conversions. Treat decorators, validator signatures,
      inheritance, defaults, metadata, list annotations, unions, registries,
      and model construction as semantic work requiring local inspection.
      Order work by collection blockers and dependency direction, not file
      size.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Work in small,
      reversible batches. After each file or coherent edit, run Python
      compilation and a direct import before proceeding. Prefer exact edits or
      a syntax-aware codemod over broad `sed` or regex replacement. Never run
      a repository-wide substitution until it has been tested on a copy,
      reviewed as a diff, and proven unable to alter unrelated syntax.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile every
      production Python file first. Repair syntax, indentation, malformed
      imports, and malformed decorators before semantic migration. Search for
      artifacts such as `@model_validator(mode="before")pre=True)`,
      duplicated `(mode=...)`, stray parentheses, imports inserted into the
      middle of another import, lowercase `true` or `false`, damaged regexes,
      and decorators at column zero. Recover the original local construct and
      rewrite it deliberately; do not stack another replacement over damaged
      text.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Use the complete
      traceback and fix only the earliest root cause. Recompile the edited
      file, directly import its module, and rerun collection after every fix.
      Do not report completion after an import smoke test or after only one
      focused file collects.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update all authoritative
      dependency declarations consistently. Import BaseSettings and
      SettingsConfigDict from `pydantic_settings`, preserve environment
      variable case sensitivity and defaults, and change Field `regex` to
      `pattern` without modifying unrelated `re.compile`, parser regexes,
      quoting, or grouping. Import and instantiate the settings model after
      editing.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate each
      Config option to ConfigDict deliberately, including frozen behavior,
      enum values, extra-field policy, assignment validation, aliases, and
      arbitrary types. Do not mix a Config class and model_config on one
      model. Add only configuration required to preserve established behavior;
      do not use broad ignored-types or extra-allow settings to suppress
      migration errors.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. In Pydantic v2 every
      subclass override of an inherited model field must remain annotated.
      Find unannotated assignments such as `segment_name = ...`, restore the
      inherited annotation, and preserve the original default. Do not remove
      discriminator or segment-name fields to silence the
      field-overridden-by-non-annotated-attribute error. Import all major model
      modules after this pass.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed Field and
      constrained-type arguments one construct at a time. Use
      `json_schema_extra={"is_component": True}` for project metadata and
      preserve consumers of that metadata. Use Python `True`, never JSON
      `true`. Review min/max item constraints, required Optional fields,
      defaults, decimal behavior, literals, aliases, unions, and patterns.
      Compile and import after each affected module.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      `allow_reuse` because v2 handles reuse differently. Do not shadow the
      imported `field_validator` name with a partial or local helper of the
      same name. Preserve every reusable validation function body and adapt
      its inputs explicitly. Where validators are attached dynamically, use
      the correct v2 decorator factory and verify every attachment by model
      construction tests.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator
      individually to `field_validator`; choose `mode="before"` only when the
      original pre-validation timing requires it. Replace v1 `values`,
      `field`, and `config` parameters with ValidationInfo or another valid v2
      signature. Use `info.data` only for fields already validated according
      to declaration order. Preserve always-like behavior and defaults with
      explicit tests rather than assuming a decorator rename is equivalent.
      Keep each original function body intact except for necessary API
      adaptation.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it is pre or post, whether it accepts raw dictionaries or
      model instances, which fields and aliases it reads, whether it mutates
      data, and what it returns. Do not apply one mode to all validators and
      do not mechanically turn every root validator into a before validator.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `@model_validator(mode="before")` operating on and returning raw input.
      Convert post root validators to `@model_validator(mode="after")`
      operating on and returning `self`, unless a documented wrap validator is
      required. Replace `values.get(...)` with instance access only for after
      validators. Preserve mutation, error messages, validation timing, and
      return behavior. Never retain a `(cls, values)` body under an after
      validator, and never add an invalid `@classmethod` arrangement.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every Python
      file, compare decorator names actually used with names imported from
      Pydantic. Detect multiline imports, aliases, duplicate imports, stale
      v1 imports, and missing field_validator, model_validator, or
      ValidationInfo names. Compile and directly import every affected module.
      A decorator replacement is incomplete until its import and signature
      are both valid.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      class-level `model_fields` and adapt to FieldInfo rather than performing
      blind attribute substitution. Replace `field_info.extra` with guarded
      `json_schema_extra` access. Use field annotations plus `typing.get_origin`
      and `get_args` instead of SHAPE_LIST or ModelField shape/type attributes.
      Verify handling of Optional, Annotated, Union, list subclasses, and
      forward references with focused tests.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve the public import
      location, name, and behavior of list-field helpers such as
      `_is_list_field`; do not move the helper to another module merely for
      convenience. Ensure both production coercion and tests call the same
      implementation. Test plain List, Optional[List], Annotated lists,
      non-list fields, and repeatable-segment wrapping.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace model methods
      with model_dump, model_dump_json, model_validate, model_json_schema, or
      model_copy where behaviorally equivalent. Preserve enum rendering,
      aliases, exclude flags, custom JSON encoding, delimiters, recursive
      segment counting, dict/model mixed inputs, CLI output, and `.x12()`
      ordering. Do not replace arbitrary object `.dict()` calls unless the
      object is proven to be a Pydantic model.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit import-time loops that
      discover model classes or read `segment_name` defaults. Adapt their
      FieldInfo access carefully and verify registry keys, values, counts, and
      exclusions against the original behavior. Guard non-model globals before
      accessing `model_fields`; do not damage generated mappings with broad
      text replacement.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile on
      the entire production package with a real nonzero failure status.
      Resolve every syntax and indentation error before testing. Search again
      for known malformed decorator, import, boolean, pattern, and parenthesis
      artifacts.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Directly import core
      settings, shared models, each version's segment modules, transaction
      modules, parsers, CLI modules, public helpers, and registries. Then run
      complete pytest collection without truncating output or masking status.
      Stay at this gate until collection is clean.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, base models, both segment versions, validator-heavy models,
      repeatable loops, list helpers, parser behavior, serialization, CLI
      output, and registries. A direct import proves only that import works; it
      does not prove validator or serialization behavior.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Exercise both valid and
      invalid examples from tests and semantic snapshots. Compare coercion,
      defaults, requiredness, enum values, cross-field timing, mutation, error
      messages where contractual, and serialized output. Treat warnings as
      evidence of remaining migration work when they identify v1 APIs.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Fix one root cause at a
      time using the first complete traceback. After each edit, compile the
      file, import the module, rerun the narrow failing test, rerun the related
      test file, rerun collection when import structure changed, and
      periodically rerun the full suite. Do not stop because a subset passes,
      collection succeeds, or progress is better than the baseline.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review the complete diff,
      especially every line touched by scripts, sed, regex, or generated
      edits. Detect duplicated imports, decorator corruption, accidental
      replacements inside regexes or parser code, lowercase booleans,
      annotation loss, commented validation, deleted bodies, unrelated files,
      temporary scripts, and migration reports accidentally written outside
      the repository.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      pydantic.v1, stale v1 imports and decorators, BaseSettings from
      pydantic, allow_reuse, SHAPE_LIST, ModelField assumptions, __fields__,
      field_info.extra, removed Config keys, Field regex, malformed decorators,
      invalid booleans, deprecated model APIs, missing decorator imports,
      pass-only or ellipsis-only functions, commented-out bodies, and broad
      exception suppression. Any `pydantic.v1` production import or emptied
      function body is a hard failure regardless of test results.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's complete authoritative suite with no
      output-truncating pipeline. Record command, true exit status, collected
      count, passed count, failed count, errors, skips, and warnings. If it
      fails or collection is incomplete, return to iterative repair rather
      than summarizing partial progress.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm public imports,
      settings, validation timing, repeatable-segment wrapping, parser output,
      `.x12()` output, serialization, CLI behavior, helpers, and registries
      remain compatible. Confirm no production compatibility shim,
      pydantic.v1 redirect, disabled validator, emptied body, or test-only
      workaround replaced the real migration.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Re-run compilation, complete
      collection, static audits, and the full suite after the last edit.
      Inspect git status and the full diff. Remove only migration-created
      scratch artifacts, preserve pre-existing user files, and verify
      dependency declarations match the tested runtime. Do not make another
      code edit after this gate without rerunning it.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only when the final
      gate is green. Include the exact full-suite command and counts, runtime
      versions, principal behavior-preserving changes, and any remaining
      non-migration warnings. If the suite is not green, report the migration
      as incomplete and continue working rather than presenting a success
      summary.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not redirect production imports to `pydantic.v1`, even temporarily as the submitted solution.
  - Do not empty, replace with pass or ellipsis, comment out, stub, or bypass any function or validator body merely to make imports, collection, or tests proceed.
  - Do not use broad repository-wide sed or regex replacement for decorators, imports, signatures, regex arguments, or model methods without testing the transformation, reviewing its complete diff, and compiling immediately.
  - Do not mechanically map every root validator to the same model-validator mode; classify pre and post semantics first.
  - Do not leave a v1 `(cls, values)` function body beneath an after model validator or a self-based body beneath a before model validator.
  - Do not assume replacing a decorator name completes the migration; imports, signatures, timing, return values, and tests must agree.
  - Do not move or delete a public helper because its name begins with an underscore when tests or callers import it from the original module.
  - Do not remove inherited fields, discriminator fields, segment names, metadata, or validators to silence Pydantic errors.
  - Do not use lowercase JSON booleans in Python or blindly replace every occurrence of `regex` with `pattern`.
  - Do not treat a zero pipeline status, successful import, successful collection, focused subset, or improved pass count as a passing full suite.
  - Do not end the task with a progress summary while any collection error, test failure, syntax error, stale prohibited construct, or semantic regression remains.
```