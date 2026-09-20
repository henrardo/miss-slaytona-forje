---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 62
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's complete, untruncated test command exits successfully.
  Preserve every validator body, public helper, parser, serializer, registry,
  validation phase, and public API unless the repository contract explicitly
  requires a change. Before starting and throughout the migration, read and
  enforce `references/core-rules.md`. Never use `pydantic.v1` as the migration
  solution, and never empty, stub, bypass, or replace a function body merely to
  make imports or tests proceed.

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
  - Pydantic reports that post root validators require skip_on_failure or that model_validator rejects the pre argument
  - Tests import a public compatibility helper such as _is_list_field that disappeared during migration
  - Collection fails because a v1 post root_validator remains, or because a partial conversion produced model_validator(pre=True)
  - A repository contains hundreds of similar models where unsafe global replacements can silently damage unrelated Python syntax

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native v2 migration

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without piping it through head, tail, grep, or tee. If output must
      be captured, redirect it to a file, save the test process exit status,
      then inspect the file separately. Record the complete first traceback,
      collection count, pass count, failure count, command, and exit status.
      A shell pipeline reporting exit 0 is not evidence that pytest passed.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Resolve the repository
      root once and reuse it; do not guess near-miss paths. Record every
      pre-existing tracked and untracked change. Never discard user changes or
      run a broad checkout merely because a partial migration became difficult.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject metadata,
      lock and requirement files, CI commands, supported Python versions,
      package entry points, repository documentation, and migration-specific
      fixtures such as a post-migration requirements file. Treat tests that
      import internal-looking helpers as evidence that those helpers are part
      of the repository's required contract.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter and
      imported Pydantic versions in the same environment used by tests. Install
      or update the target dependencies only through the repository's intended
      dependency workflow. Confirm native Pydantic v2 and pydantic-settings are
      importable before interpreting later failures.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests, and
      generated registration code for all v1 interfaces and malformed partial
      replacements. Include BaseSettings, Config, validator, root_validator,
      allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex,
      min_items, max_items, dict, json, parse_obj, copy, schema, constrained
      types, custom Field extras, unannotated inherited field overrides,
      Optional annotations, reusable validator assignments, and decorator names
      used without matching imports. Search for malformed forms such as
      model_validator(pre=True), model_validator(mode="before")pre=True),
      doubled parentheses, JSON `true` in Python, and damaged regex literals.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Record public model
      constructors, helper imports, settings behavior, parser outputs, X12
      serialization, CLI exports, generated segment registries, validation
      errors, and collection-time imports. Explicitly check whether tests
      import helpers such as `_is_list_field`; preserve their import location,
      signature, and behavior rather than moving or deleting them.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing each
      validator, recover and read its complete original decorator, signature,
      docstring, body, return value, call sites, and tests. Determine whether it
      operates on raw input dictionaries, already-validated dictionaries, or
      model instances. Do not infer semantics from the decorator name alone,
      and do not replace a body with `pass`, `return values`, `return self`, a
      no-op lambda, or commented-out code merely to restore imports.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create a durable ledger listing
      every affected file and symbol, its original semantics, intended v2
      equivalent, focused verification command, status, and current blocker.
      Update the ledger after each checkpoint so later repair does not restart
      discovery or repeatedly overwrite working changes.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by collection
      blockers, shared infrastructure, validator families, introspection,
      parsing and serialization, generated registries, then behavior failures.
      Group repeated models by pattern only after proving that their function
      bodies and validation phases are equivalent.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Work in reviewable
      micro-batches. After each batch, compile changed files and run the
      smallest import or focused test that exercises them. Do not modify both
      large versioned segment modules, every transaction package, and shared
      infrastructure in one unverified replacement.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      files to locate syntax damage. Compare malformed regions with the
      original source or semantic snapshots and repair them manually. Audit
      every prior automated replacement, including imports, decorator lines,
      regular expressions, booleans, indentation, comments, and generated
      registry expressions. Never stack another global replacement on top of
      malformed output.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Repair only the first
      complete traceback until collection advances, then repeat. For the common
      failures in this migration: replace a v1 post root_validator rather than
      adding skip_on_failure as the final solution, and replace
      `model_validator(pre=True)` with a correctly classified
      `model_validator(mode="before")` while adapting its signature and body.
      Do not announce completion when imports succeed but collection or tests
      still fail.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Set the native
      Pydantic v2 dependency range and add pydantic-settings when settings are
      used. Import BaseSettings from pydantic_settings, migrate settings Config
      to SettingsConfigDict, and change Field(regex=...) to Field(pattern=...)
      without altering the regular expression. Verify environment
      case-sensitivity and defaults with focused settings tests.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert each
      class-based Config to ConfigDict or the appropriate settings config while
      preserving frozen or immutability behavior, enum value handling, extra
      field policy, aliases, assignment validation, arbitrary types, and
      serialization behavior. Apply shared configuration at the correct base
      class rather than duplicating it inconsistently.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Find every subclass
      assignment that overrides an inherited Pydantic field without a type
      annotation, including constant segment names. Re-annotate it with the
      inherited type and preserve the default. Do not delete these fields or
      remove all subclass segment-name declarations; registries and
      serialization may depend on their defaults.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert regex to pattern,
      min_items and max_items to their v2 equivalents, arbitrary Field extras
      to json_schema_extra, and obsolete constrained-type arguments to valid v2
      forms. Use Python `True`, never JSON `true`. Audit Optional fields
      explicitly: in v2, Optional[T] without a default remains required, so add
      `None` only when v1 behavior and tests show the field was optional.
      Preserve Decimal, date, enum, length, and numeric constraints.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove the v1
      allow_reuse compatibility partial instead of passing allow_reuse to
      field_validator. Preserve reusable validation functions and assignment
      names. When the same callable is registered on many models, verify the v2
      decorator order and registration pattern with a minimal model before
      applying it broadly.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Replace validator with
      field_validator and adapt signatures deliberately. Replace v1 `values`
      access with ValidationInfo.data only when ordering guarantees the needed
      fields are available. Preserve pre behavior using mode="before", preserve
      always-like behavior only after testing defaults, and add @classmethod
      where appropriate. For validators registered by assignment, do not
      decorate a function that already carries incompatible validator metadata.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it is before or after validation, its expected input
      shape, whether nested values are dictionaries or models, whether it
      mutates input, and what it returns. A v1 `pre=True` validator normally
      maps to mode="before"; a post validator normally maps to mode="after",
      but its body must be rewritten to use the model instance. Never convert
      all root validators to one mode with sed or a regex.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert before validators to
      `@model_validator(mode="before")` with a class-oriented raw-data
      signature and return the input mapping. Convert after validators to
      `@model_validator(mode="after")` with an instance-oriented signature,
      use attributes instead of `values.get`, and return the model instance.
      Preserve every validation branch and error message. For reusable
      dictionary-based validators invoked by assignment, add a small wrapper
      only when needed to translate between model instances and the original
      function without losing mutations or errors.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. In every changed
      module, compare used decorators against imports. Remove obsolete
      validator and root_validator imports only after no decorators or
      assignment calls use them. Ensure field_validator, model_validator, and
      ValidationInfo are imported where used. Compile and import every affected
      module immediately; successful import of one shared module does not prove
      transaction-specific modules are valid.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields, ModelField assumptions with FieldInfo-aware logic, and
      field_info.extra with json_schema_extra. Treat json_schema_extra as
      possibly None. Use typing.get_origin and get_args for list and union
      detection. Verify field name, annotation, default, requiredness, metadata,
      and nested model extraction instead of mechanically renaming attributes.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. If tests or callers import a
      helper such as `_is_list_field`, keep it at the same public import path.
      Implement it against v2 annotations with get_origin and union handling,
      and use the same helper in repeatable-segment wrapping. Test direct lists,
      Optional[List[T]], unions containing lists, and non-list fields. Do not
      hide the helper in another module while tests still import it from the
      original one.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict, json,
      parse_obj, copy, and schema APIs with v2 methods only after checking each
      call's output contract. Preserve enum, Decimal, date, alias, exclude,
      unset, None, delimiter, CLI JSON, and recursive segment-count behavior.
      Update parser field introspection to model_fields and component metadata
      to json_schema_extra. Do not globally replace ordinary dictionary `.copy`
      or unrelated `.json` calls.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time segment
      registries and other generated maps that read field defaults. Migrate
      their field lookup to model_fields without changing keys or registered
      classes. Verify known segment names, both specification versions, and
      parser lookup. Do not remove registry-building code to avoid an import
      error.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile
      across production code with an unmasked exit status. Repair syntax,
      indentation, malformed decorators, damaged strings, and invalid Python
      literals before running behavioral tests.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import shared models,
      settings, both versioned segment modules, every transaction module, and
      public helpers. Then run complete pytest collection without truncating
      output or masking status. Continue until collection succeeds with the
      expected number of tests; zero collected tests is not success.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for settings,
      shared models, segment models, repeatable loop initialization, parsing,
      serialization, registries, CLI output, and transaction-specific
      validators. Always check the actual pytest exit code. Record passing
      counts as progress, but do not treat 56 or 57 passing tests with remaining
      errors as migration completion.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Exercise representative
      valid and invalid inputs around every migrated validator family. Compare
      accepted inputs, rejected inputs, error locations and messages, default
      behavior, mutation, list wrapping, and serialized output with the
      semantic snapshots and tests. Import success alone is insufficient.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Use the first complete
      traceback, make the smallest behavior-preserving repair, compile, run the
      narrow reproducer, then rerun collection or the relevant test group.
      Update the migration ledger after every cycle. Do not stop to write a
      migration summary while tests still fail, and do not repeatedly restart
      repository assessment after collection has already advanced.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every line changed by sed,
      regex, or scripts. Search for duplicated imports, invalid decorators,
      missing indentation, JSON booleans, corrupted regex and strings,
      accidental Optional default changes, removed annotations, no-op bodies,
      commented validators, and unrelated replacements. Prefer reverting one
      damaged hunk and reapplying it manually over adding corrective global
      replacements.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, v1 Config classes,
      validator, root_validator, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, regex arguments, deprecated serialization
      calls, malformed decorators, and empty or bypassed functions. Classify
      every remaining hit rather than assuming grep exit 1 is an execution
      failure.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact complete repository test command directly or
      with explicit status capture. Do not pipe it through head, tail, grep, or
      tee without pipefail and explicit status handling. Require the expected
      collection count, zero failures and errors, and process exit status zero.
      If it fails, return to iterative repair rather than reporting completion.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Verify public imports,
      settings, constructors, parser behavior, X12 output, CLI output, helper
      functions, validator errors, registries, and optional/default semantics.
      Confirm that no production import points to pydantic.v1 and no function
      was emptied, stubbed, bypassed, or changed to unconditional success.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Review git status and the full
      diff, separate intended migration files from accidental artifacts, ensure
      temporary plans and scripts are not left in the package, rerun compile,
      static audit, collection, and the complete suite after the final edit,
      and retain the unmasked exit statuses.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only when the final
      gate proves native Pydantic v2 usage and a green complete suite. Include
      runtime versions, exact commands, collection and pass counts, exit
      statuses, changed behavior-sensitive areas, and any remaining warnings.
      If anything remains failing, report the blocker and continue working
      rather than calling the migration successful.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; that is compatibility mode, not a native Pydantic v2 migration.
  - Never empty, stub, comment out, bypass, or replace a function or validator body with a no-op merely to make imports, collection, or tests proceed.
  - Never convert every root validator to the same model_validator mode with a global replacement.
  - Never change decorators without adapting signatures, data access, return values, and validation timing.
  - Never treat a command piped through head, tail, grep, or tee as passing unless the underlying test process exit status is explicitly captured and zero.
  - Never declare success after import smoke tests, successful collection alone, or a partially passing focused subset.
  - Never use repeated broad sed or regex replacements to repair damage introduced by an earlier broad replacement.
  - Never discard the working tree, overwrite pre-existing changes, or run checkout on a directory without first proving every discarded edit belongs to the current attempt.
  - Never remove inherited field declarations, public helpers, registry construction, validators, or parser logic merely because Pydantic v2 rejects their current form.
  - Never add `None` defaults to every Optional annotation without checking the original requiredness contract.
  - Never use JSON `true` or `false` in Python source.
  - Never mechanically replace every `.dict`, `.json`, `.copy`, or `.schema` call; distinguish Pydantic models from ordinary objects first.
  - Never assume two similarly named validators have equivalent bodies or validation phases.
  - Never stop after writing a summary or migration plan while the complete suite still fails.
```