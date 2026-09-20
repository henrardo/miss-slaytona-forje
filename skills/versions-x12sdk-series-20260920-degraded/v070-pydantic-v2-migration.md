---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 70
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Preserve public APIs, validator bodies, validation timing, parser behavior,
  serializer behavior, settings behavior, helper functions, generated
  registries, and error behavior. Before editing and throughout the migration,
  read and enforce `references/core-rules.md`. Never claim completion from
  successful imports, compilation, collection, a focused subset, a custom
  smoke script, or output piped through `head` or `tail`.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, empty validator bodies, or broad search-and-replace damage
  - When deciding whether a partial or failed migration matches this procedure, read `references/core-rules.md` section `additional-triggers`.

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
      command without truncating its output. Capture the command, actual process
      exit status, collection count, pass count, failure count, and first
      complete traceback. If output must be saved, redirect it to a file, store
      `$?` immediately, and inspect the file afterward; do not use a pipeline
      whose final command masks pytest's status.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Resolve the repository
      root once and use that exact path thereafter. Record all tracked,
      untracked, staged, and pre-existing changes. Do not discard, reset,
      overwrite, or `git checkout` user changes merely to simplify the
      migration. Treat an existing partial migration as evidence to audit, not
      as permission for destructive cleanup.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      Work continuously until the full-suite gate is green or a genuine
      external blocker is demonstrated. After every tool result, execute the
      next concrete diagnostic, edit, or validation action; do not repeatedly
      restate the plan, write celebratory summaries, or end the turn while a
      known failure remains. A successful import, compile, collection run, or
      focused test is only an intermediate checkpoint. Never print raw
      tool-call markup as prose. Use exact repository paths and re-read the
      affected lines before each edit.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Identify the canonical test
      command from project configuration or CI, supported Python versions,
      package metadata, dependency files, generated-code conventions, and
      public entry points. Inspect `requirements-v2.txt` or equivalent migration
      fixtures when present; such files may encode the expected target versions
      and measured suite behavior.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter,
      Pydantic, pydantic-core, pydantic-settings, pytest, and installed-project
      versions in the same environment used by the tests. Change dependencies
      through the repository's declared installation workflow. Do not
      repeatedly mutate the global environment or install editable packages in
      ways that silently downgrade Pydantic. Re-check versions immediately
      after installation.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      generators, and registries for all v1 surfaces, including multiline
      imports and decorator aliases. Record file and line locations rather than
      relying on counts alone. Distinguish documentation examples from runtime
      code, and distinguish already-correct v2 code from malformed partial
      conversions.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include public and
      test-imported helpers even when their names begin with an underscore.
      Explicitly inventory list-field helpers, parser and serializer methods,
      settings classes, custom X12 rendering, model registries, exception
      behavior, and direct test imports such as `_is_list_field`.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before converting a
      validator, recover and read its complete original body, signature,
      decorator options, field order assumptions, and call sites. Use `git
      show HEAD:path`, the clean baseline, or source history when a partial
      migration has damaged code. Never infer a validator body from its name,
      replace it with a stub, or delete logic merely to make imports succeed.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Track each affected symbol with
      its original semantics, intended v2 construct, dependencies, current
      state, validation command, and completion status. Include every validator
      individually rather than one row per large file.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by collection blockers
      and shared infrastructure first, then leaf models. Separate mechanical
      renames from semantic conversions. Treat validator conversion, optional
      defaults, inherited fields, metadata, and generated registries as
      semantic work requiring local review.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Make one coherent change
      class at a time and validate it before proceeding. Prefer exact edits over
      repository-wide substitutions. If automation is justified, first test it
      on one representative occurrence, inspect the diff, compile, and only
      then expand it. Never run an unreviewed regex across all Python files.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read `references/verification-and-repair.md`
      section `recover-malformed-partial-migration` and follow it. Search for
      malformed decorator fragments, duplicate imports, missing parentheses,
      accidental indentation changes, lowercase JSON booleans in Python,
      damaged regex literals, invalid annotations, temporary migration scripts,
      and comments that disable production logic. Restore only the damaged
      construct from a known-good source; do not revert unrelated work.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Use the first complete
      traceback, make the smallest correct change, then rerun the import or
      collection gate. Continue one blocker at a time instead of attempting a
      speculative full migration before the package imports.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move `BaseSettings` to
      `pydantic_settings`, declare `pydantic-settings` in package metadata, and
      translate settings configuration with `SettingsConfigDict` while
      preserving case sensitivity, environment names, defaults, and cache
      behavior. Replace `Field(regex=...)` with `Field(pattern=...)` without
      altering the expression. Validate imports and representative environment
      overrides immediately.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate every inner
      `Config` option deliberately to `ConfigDict`; do not mechanically copy
      removed keys. Preserve enum storage, extra-field policy, frozen/hashable
      behavior, aliases, assignment validation, arbitrary types, and default
      validation. Check all base classes because one shared configuration can
      affect hundreds of models.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. In Pydantic v2, every
      model-field override must retain an annotation. Repair unannotated
      subclass assignments such as `segment_name = ...` to annotated overrides
      with the correct inherited type. Search the entire model tree rather than
      deleting the inherited field or weakening the base annotation.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed constraint
      arguments such as `regex` to their v2 forms, preserve bounds and decimal
      semantics, and move arbitrary field metadata to
      `json_schema_extra`. Preserve Python booleans and valid Python syntax.
      Treat `Optional[T]` separately from `T = None`: add a default only where
      the v1 contract or tests established that the field was not required.
      Do not globally add `None` to every Optional annotation.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove the v1
      `allow_reuse` decorator wrapper without shadowing the imported v2
      `field_validator`. Preserve reusable plain validation functions and bind
      them with the actual v2 decorator at each model field. Verify helper
      signatures against representative call sites before applying them
      broadly.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each v1 `@validator`
      independently. Replace the v1 `values` dictionary with
      `ValidationInfo.data` only when that was its role, preserve `pre` as
      `mode: before`, preserve field ordering dependencies, and use
      `@classmethod` where required. Do not perform a decorator-only rename
      while leaving an incompatible signature.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every v1
      `root_validator`, record whether it is before or after validation, whether
      it consumes and returns raw mappings, whether it expects validated
      objects, whether it mutates values, and which failure timing it preserves.
      Do not infer mode from a bulk pattern.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert before validators to
      `@model_validator(mode="before")` with mapping-in/mapping-out behavior.
      Convert after validators to instance methods that inspect attributes and
      return `self`, unless the recovered original semantics require a
      documented wrap validator. Preserve every branch and exception. Never
      add both v1 and v2 decorator parameters, generate malformed forms such as
      chained decorator calls, or leave a `cls, values` v1 body under an after
      validator.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every production
      file, reconcile decorator usage with imports and remove stale v1 names.
      Search multiline imports as well as one-line imports. Compile and import
      each changed module so missing `field_validator` or `model_validator`
      names are caught before collection.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      `model_fields` and adapt to v2 `FieldInfo` rather than assuming v1
      `ModelField` attributes exist. Resolve annotations with `get_origin` and
      `get_args` where necessary. Read custom metadata from
      `json_schema_extra`, safely handling `None`. Verify class-level registry
      code and instance-level serialization separately.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or restore the
      public/test-imported `_is_list_field` helper in its expected module.
      Implement it against v2 field annotations, including Optional or Union
      wrappers around lists. Use the same helper in repeatable-segment wrapping
      logic and test it with list, optional-list, and non-list fields.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace v1 APIs with
      `model_validate`, `model_dump`, `model_dump_json`, `model_copy`, and
      `model_json_schema` only where behavior is equivalent. Preserve include,
      exclude, alias, unset, default, none, enum, decimal, date, delimiter, and
      custom X12 rendering behavior. Do not replace plain dictionary methods or
      unrelated `.json()` calls through global textual substitution.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Exercise import-time model
      registry construction after changing introspection. Verify every expected
      segment key is present, no key is `None`, and class defaults are read from
      v2 `model_fields`. Compare registry size and representative mappings with
      the semantic snapshot or tests.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile the complete production
      package, not only edited files. Treat every syntax or indentation error as
      evidence of an unsafe edit and repair it from the original construct
      before continuing.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core settings,
      models, both schema-version segment modules, parser modules, and
      transaction modules, then run the complete collection command. Record the
      real exit status and collected count. Do not treat pytest exit code 5,
      output piped into another process, or a truncated listing as success.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run tests for settings,
      shared models, both schema-version segments, repeatable segments, loop
      initializers, parsers, serializers, and registries. Use `-x` to shorten
      feedback only when the command's unmasked status and complete first
      traceback are retained.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Test valid and invalid
      representative payloads, missing versus explicit `None`, coercion,
      validator ordering, cross-field failures, extra fields, frozen models,
      aliases, settings environment overrides, error locations, and custom
      serialization. Passing import checks are not semantic evidence.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. For each failure, read the
      complete traceback and relevant original body, classify the failure, make
      the smallest behavior-preserving repair, rerun the narrowest relevant
      test, then rerun the broader gate. Continue immediately to the next
      blocker. Do not stop to report progress while any known failure remains.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Inspect the complete diff for every
      scripted or search-and-replace edit. Look specifically for changed
      validator bodies, malformed decorators, dropped imports, invalid regexes,
      accidental edits to non-Pydantic methods, lowercase booleans, comments
      replacing executable code, and broad Optional-default changes.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      remaining v1 imports and APIs, stale decorators, compatibility namespace
      imports, malformed partial conversions, temporary scripts, empty bodies,
      and deprecated introspection. Each hit must be migrated or explicitly
      proven unrelated.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact canonical full-suite command without `head`,
      `tail`, grep filtering, or a pipeline that masks status. If output is
      large, redirect it to a log, capture the test process status immediately,
      and inspect the log afterward. Proceed only when the process exits zero
      and the reported pass count is plausible relative to baseline collection.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Compare public imports,
      helpers, parser results, registry contents, X12 output, JSON and dict
      output, settings behavior, valid and invalid model behavior, and error
      timing with the recorded contracts. A green suite does not authorize
      removing public APIs or validation logic.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Review `git diff`, `git
      status`, dependency metadata, and generated artifacts. Confirm no
      unrelated files, migration summaries, scratch scripts, caches, or
      environment artifacts were added. Explicitly reject any production import
      from `pydantic.v1` and any function or validator body emptied, replaced
      with `pass`, reduced to an unconditional return, commented out, or deleted
      merely to make the package import.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section `report-completion`
      and follow it. Report only after every gate passes. Include changed
      behavior surfaces, exact full-suite command, actual exit status and test
      counts, static-audit result, and any remaining warnings. If an external
      blocker prevents completion, report the blocker with reproduced evidence
      and the last passing gate; never describe a failing or unrun suite as
      complete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never route production imports through `pydantic.v1`, even if that makes collection or tests pass.
  - Never empty, stub, comment out, or delete a function or validator body merely to make imports, collection, or tests pass.
  - Never bulk-rename decorators without classifying each validator's mode, signature, input type, output type, timing, and original body.
  - Never convert every root validator to the same model-validator mode.
  - Never place v1 parameters such as `pre` or `allow_reuse` on v2 decorators.
  - Never leave a v1 `cls, values` signature under an after model validator that must operate on an instance.
  - Never add `None` defaults to every Optional field through a repository-wide substitution.
  - Never globally replace `.dict()`, `.json()`, `regex`, `validator`, or `root_validator` without syntax-aware scope and complete diff review.
  - Never use broad `sed` or regex edits that can damage imports, parentheses, indentation, string literals, regular expressions, or unrelated methods.
  - Never use lowercase `true` or `false` in Python metadata dictionaries.
  - Never repeatedly install packages until versions happen to look correct; use the repository contract and verify the active environment after installation.
  - Never reset, checkout, or overwrite unrelated tracked changes or a user's partial migration without explicit authorization.
  - Never treat `compileall`, successful imports, collection, a focused subset, or a custom smoke script as proof that the full suite passes.
  - Never infer test success from a command piped to `head`, `tail`, `tee`, or grep unless the original test process status was captured correctly.
  - Never treat pytest exit code 5 or zero tests collected as migration success.
  - Never end the turn with a summary, plan, or claimed completion while a known traceback, failing test, or unrun full-suite gate remains.
  - Never create migration-summary documents, temporary repair scripts, or unrelated artifacts in the repository unless the task explicitly requests them.
  - Never remove a public or test-imported helper such as `_is_list_field`; migrate its implementation and preserve its import location.
  - Never weaken base annotations or delete inherited fields to avoid Pydantic v2 override errors; annotate subclass overrides correctly.
  - Never assume `Optional[T]` means the field has a default of `None`; preserve the original requiredness contract.
  - Never read v2 field metadata through v1 `field_info.extra`; use `json_schema_extra` and handle missing metadata safely.
  - Never assume v2 `FieldInfo` exposes v1 `ModelField` attributes such as `shape`, `type_`, or `name`.
  - Never skip generated registry verification after changing field introspection.
  - Never celebrate intermediate progress instead of executing the next migration action.
  # Completeness check: every distinct item from the prior SKILL.md is mapped above.
  # No prior step, trigger, exclusion, purpose clause, or anti-pattern was deliberately dropped.
```