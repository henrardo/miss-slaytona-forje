---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 25
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Preserve every validator's substantive checks and return
  behavior. Treat Python source as Python: use True and False, never JSON
  literals true and false. Do not confuse an import success, successful
  collection, a zero-looking pipeline status, or a green focused test with
  completion. Completion requires production code to compile, test collection
  to succeed, focused behavior tests to pass, the exact untruncated full-suite
  command to exit zero, and the final diff to pass static and
  behavior-preservation audits.

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
      `establish-the-failure` instructions. Run the repository's documented
      full-suite command before editing and save its complete stdout, stderr,
      and real exit status. Do not pipe the command through `head`, `tail`,
      `grep`, or `tee` unless `pipefail` is enabled and the pytest status is
      captured separately; a pipeline can report the reader's zero status while
      pytest failed. If output is large, redirect it to a file, capture `$?`,
      then inspect the file. Record the runtime Python, Pydantic,
      pydantic-core, pydantic-settings, and pytest versions. Read the entire
      first traceback, including its final exception and source location.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository root with `pwd` and version-control metadata. Record
      `git status --short` and the existing diff. Do not reset, checkout,
      overwrite, or otherwise discard pre-existing user changes. Distinguish
      harness or skill files from production changes, and use one verified
      absolute repository path consistently to avoid edits against misspelled
      paths.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Read pyproject.toml, lock and
      requirement files, package metadata, test configuration, CI commands,
      contributor instructions, and migration-specific requirement files.
      Inspect tests before guessing expected behavior. Treat comments such as a
      post-migration dependency set, public test imports, exact serialization
      fixtures, and collection tests as part of the contract. Do not assume
      setup.py or requirements.txt exists; discover files first.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Ensure the active interpreter
      actually imports native Pydantic 2 and all target dependencies, especially
      pydantic-settings when BaseSettings is used. Update declared dependency
      ranges and lock data consistently with the repository contract. Verify
      imports and versions in the same environment used by tests. Do not use
      pydantic.v1, a compatibility package, import aliases that conceal v1, or
      dependency downgrades as a migration shortcut.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search all production Python files,
      not only the first large segment module, for BaseSettings, class Config,
      validator, root_validator, allow_reuse, each_item, always, pre,
      __fields__, ModelField, field_info.extra, shape constants, Field extras,
      regex, min_items, max_items, constr, conlist, parse_obj, parse_raw,
      from_orm, copy, dict, json, json_encoders, schema, and update_forward_refs.
      Include decorator-assignment patterns such as
      `_validate = validator(...)(helper)`, imports from shared validator
      modules, dynamically constructed registries, transaction-specific loops,
      and test-only use of public helpers. Record file, symbol, use category,
      and expected behavior for every hit.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. List symbols imported by tests or
      downstream modules, including nominally private helpers such as
      `_is_list_field`. Record constructor behavior, accepted scalar versus
      list inputs, required and optional fields, enum representation, settings
      case sensitivity, field metadata, generated X12 output, JSON/dict output,
      aliases, error cases, and validator messages. Preserve public helper names
      and signatures unless the contract explicitly permits a breaking change.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Follow `classify-migration-work` in
      `references/repository-assessment.md`. Build an ordered plan that
      separates dependency/settings work, shared base models, inherited field
      overrides, constrained fields, reusable validator infrastructure, field
      validators, model validators, introspection, parsing, serialization,
      public helpers, and transaction-specific models. Prioritize blockers by
      traceback order, but identify shared fixes that safely resolve repeated
      failures. For each planned edit, state the v1 behavior to preserve and
      the focused check that proves preservation.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md`, then follow
      `create-small-edit-checkpoints`. Make one coherent migration category at
      a time and immediately run syntax compilation, the narrowest relevant
      import, collection, or focused test. Inspect `git diff` after each
      checkpoint. Avoid repository-wide sed or regex transformations over
      decorators, imports, function signatures, booleans, or bodies: v1
      validators with superficially similar syntax require different v2 modes
      and signatures. If automation is justified, first test it on a copy or
      dry-run list, review every changed hunk, compile all changed files, and
      revert the transformation if it produces malformed decorators,
      indentation, duplicate arguments, lost imports, or changed bodies.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md`, then follow
      `repair-first-collection-blocker`. Fix only the earliest genuine
      collection blocker, then rerun collection without truncating its output.
      Use the traceback as evidence rather than continuing a prewritten batch.
      Typical blockers include moved BaseSettings, removed Field arguments,
      non-annotated inherited field overrides, invalid decorators, bad
      reusable-validator arguments, and Python NameError caused by writing
      `true` or `false`. When converting `Field(is_component=True)`, write valid
      Python such as `Field(json_schema_extra={"is_component": True})`; never
      paste JSON boolean syntax into a .py file.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings imports to
      pydantic_settings and add the declared pydantic-settings dependency.
      Replace settings `Config` with `SettingsConfigDict` or an equivalent
      native v2 `model_config`, preserving case sensitivity, environment
      prefixes, env files, aliases, ignored extras, and nested delimiter
      behavior. Replace `Field(regex=...)` with `Field(pattern=...)`. Import and
      instantiate the settings model after the edit, test representative valid
      and invalid environment values, and confirm defaults are unchanged.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Replace model `Config` classes
      with `ConfigDict` while preserving immutability, enum values, assignment
      validation, extra handling, aliases, arbitrary types, string behavior,
      populate-by-name, and serialization. Convert `allow_mutation=False` to
      `frozen=True`. If defaults must undergo enum or custom validation, use
      `validate_default=True` where behavior requires it. Test the shared base
      model directly because one configuration error propagates through every
      subclass.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 rejects a subclass
      assignment that overrides an inherited model field without an
      annotation. Preserve the field and annotate the override, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`; do not remove every
      subclass `segment_name`, convert model fields to ClassVar, or weaken the
      base model merely to silence the error. Search for all unannotated
      overrides, import representative 4010 and 5010 modules, and verify that
      field order and emitted segment identifiers remain correct.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Replace removed arguments
      semantically: regex with pattern, min_items/max_items with
      min_length/max_length where appropriate, and custom Field extras with
      `json_schema_extra`. Preserve metadata keys consumed at runtime, including
      `is_component`, and use valid Python booleans `True` and `False`.
      Migrate constrained types using their v2 signatures, such as
      `constr(pattern=...)`, or Annotated constraints where suitable. Audit
      `Optional[T]`: in v2 it is still required unless a default such as None is
      supplied. Add or retain defaults only when repository behavior says the
      field is optional, never as a blanket collection fix. Test boundaries,
      patterns, requiredness, and schema metadata.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove `allow_reuse`, which is
      not accepted by v2 decorators. Replace v1 partial-decorator aliases with
      a clear native-v2 mechanism; do not shadow Pydantic's `field_validator`
      name with a custom partial and then import that alias as though it were
      the native decorator. Keep reusable business functions as ordinary
      helpers and attach them with native decorators, or add thin validators
      that adapt `ValidationInfo` or model instances into the helper's expected
      input. Verify every attachment target exists and that a helper reused
      across models retains all substantive checks.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each v1 `@validator`
      according to its behavior, not by textual substitution. Use
      `@field_validator(..., mode="before")` only for pre-validation and the
      default after mode otherwise. Replace `values` access with
      `ValidationInfo.data`, accounting for field declaration order and the
      fact that only already-validated fields are available. Preserve
      multi-field validators, default-validation behavior, and return values.
      For reusable date validators, accept either ValidationInfo or a deliberate
      adapter instead of treating the info object as a dict. Add `@classmethod`
      in the supported decorator order when needed, and run both passing and
      failing examples for each validator family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert every root validator
      individually. A pre root validator becomes
      `@model_validator(mode="before")`, receives raw input data, safely handles
      non-dict input where relevant, and returns the data. A post root validator
      normally becomes `@model_validator(mode="after")`, receives `self`,
      reads attributes from the instance, performs the same checks, and returns
      `self`. Do not leave an after validator with `(cls, values)` and dict
      access. Do not mechanically force all validators to before mode merely to
      avoid rewriting their logic. Preserve validator ordering, conditional
      requiredness, duplicate-code checks, count checks, and every raise path.
      Never delete or empty a validator body so the module imports.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__` with
      `model_fields` and update code for v2 `FieldInfo`; do not continue using
      `.type_`, `.shape`, `.field_info.extra`, or v1 shape constants. Read
      annotations from `FieldInfo.annotation`, metadata from
      `json_schema_extra`, and defaults from the v2 field object. Use
      `typing.get_origin` and `typing.get_args` to inspect list, union, and
      optional annotations. Update dynamic segment registries and parser field
      iteration without changing field order or skipping `segment_name`.
      Exercise both component and ordinary fields after the edit.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Preserve or implement the
      public `_is_list_field` helper expected by tests and callers. It must work
      on Pydantic v2 FieldInfo annotations and correctly recognize direct list
      fields and list members wrapped by Optional or Union without treating
      strings or unrelated containers as lists. Use it in the segment-group
      before validator so a single repeatable segment is wrapped once, while an
      existing list remains unchanged. Test the helper itself and loop-model
      initialization across both specification versions.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace model APIs deliberately:
      dict with model_dump, json with model_dump_json, parse_obj with
      model_validate, parse_raw with model_validate_json, copy with model_copy,
      and schema with model_json_schema where used. Preserve include/exclude,
      exclude_none, exclude_unset, aliases, enum output, date/Decimal handling,
      custom JSON encoding, and exact X12 formatting. Update parsers to use
      `model_fields`, annotations, and `json_schema_extra`. Do not globally
      replace every `.dict()` on unknown objects; confirm the receiver is a
      Pydantic model. Compare representative serialized structures and X12
      strings before and after.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile every production Python
      file, not only files imported by the current focused test. Stop on syntax,
      indentation, duplicate-keyword, malformed-decorator, lowercase-boolean,
      and missing-import errors. A successful import of one base module is not
      a substitute for this gate.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import shared models, settings,
      representative 4010 and 5010 segment modules, and affected transaction
      packages. Then run the complete collection command and capture its real
      exit status without output-truncating pipelines. Fix the first complete
      traceback and rerun until collection exits zero. Collection proves only
      that tests can start; it does not prove behavior.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run tests for settings, support
      utilities, base models, parsers, 4010 segments, 5010 segments,
      repeatable-loop initialization, serialization, and each transaction
      family touched. Run exact node IDs only after confirming they exist.
      Record test counts and actual exit codes. Include negative validation
      cases; imports and happy paths alone cannot reveal bypassed validators.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For every migrated validator
      family, compare accepted inputs, rejected inputs, normalized values,
      requiredness, validation order, exception type, and useful error text
      against tests or the pre-migration contract. Explicitly check electronic
      payment dependencies, date format qualifiers, adjustment groups,
      organization-name rules, duplicate segment codes, segment counts, and
      other cross-field business rules encountered in the repository.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md`. Work one failure at a time:
      capture the full traceback, identify the failed contract, make the
      smallest behavior-preserving change, compile the changed file, rerun the
      narrow failure, rerun collection when imports are affected, and
      periodically rerun the broader subset. Do not abandon the task to write a
      migration summary while any executable gate remains red.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and after
      every automated transformation. Review every changed hunk and search for
      `true`, `false`, duplicated decorator calls, decorators at column zero
      inside classes, leftover root_validator or validator names, lost Field
      imports, changed function parameters, pass-only bodies, unconditional
      returns, and deleted raise statements. Compare large generated or paired
      4010/5010 modules structurally without assuming they are identical.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      pydantic.v1 and all compatibility namespaces, BaseSettings imported from
      pydantic, class Config remnants that should be migrated, v1 decorators,
      allow_reuse, __fields__, ModelField, field_info.extra, shape constants,
      removed Field and constrained-type arguments, deprecated model methods,
      lowercase JSON booleans in Python, and temporary migration scripts or
      plans. Classify each remaining hit; do not ignore one because grep exits
      one when no matches are found.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Follow `run-full-suite` in `references/verification-and-repair.md` only
      after the static audit passes. Run the repository's exact documented
      full-suite command, untruncated and without a status-masking pipeline.
      Redirect output to a log if necessary, preserve the pytest exit status,
      and inspect the summary. Require exit zero and a credible nonzero test
      count. If it fails, return to iterative repair rather than reporting
      partial completion.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck representative valid and invalid constructions, settings loading,
      repeatable-segment wrapping, component parsing, model dumps, JSON output,
      X12 output, enum and date behavior, schemas, and public helper imports.
      Confirm no validator or helper was deleted, emptied, converted to a no-op,
      or bypassed simply to make imports or tests pass.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect `git diff --check`, the
      complete diff, and `git status --short`. Ensure dependencies and source
      changes are intentional, paired version modules are complete, no user
      work was overwritten, no scratch migration files remain, no pydantic.v1
      import exists, and no function body was emptied or neutralized. Rerun
      compilation and the exact full suite after any final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Follow `report-completion` in
      `references/verification-and-repair.md`. Report the native-v2 changes,
      behavior-preservation decisions, exact commands run, test counts, exit
      statuses, and any warnings that remain. Claim completion only when
      compilation, collection, focused tests, static audit, full suite,
      behavior verification, and final diff gate all passed. If any gate is
      unavailable or failing, state that plainly and do not call the migration
      complete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, another Pydantic v1 compatibility namespace, or a local alias that conceals such an import.
  - Never delete, empty, bypass, comment out, replace with `pass`, or otherwise neutralize a validator or function body merely to make code import or tests pass.
  - Never paste JSON literals `true`, `false`, or `null` into Python source; use `True`, `False`, and `None`.
  - Never apply a repository-wide textual decorator rewrite without classifying validator mode, signature, input shape, and return contract individually.
  - Never convert every root validator to `mode="before"` merely to retain dict-style code; after validators must normally operate on and return `self`.
  - Never leave a v2 after model validator with a v1 `(cls, values)` signature or dict access.
  - Never pass `allow_reuse` to Pydantic v2 field_validator or model_validator.
  - Never shadow the native `field_validator` or `model_validator` name with an incompatible custom partial.
  - Never remove inherited model fields such as segment identifiers merely to silence an override error; annotate behavior-preserving overrides.
  - Never blanket-add `= None` to Optional annotations without checking the repository's requiredness contract.
  - Never replace custom Field metadata without updating every runtime consumer to read `json_schema_extra`.
  - Never assume a successful import proves validators, parsing, or serialization still behave correctly.
  - Never treat successful collection as a passing suite.
  - Never infer pytest success from a command piped to head, tail, grep, or tee without preserving pytest's real status.
  - Never stop after a focused subset passes; run the exact untruncated full suite and require exit zero.
  - Never write a completion summary while collection, tests, static audit, or behavior checks remain red.
  - Never discard pre-existing working-tree changes or use checkout/reset as a substitute for careful repair.
  - Never leave temporary migration plans, one-off fixer scripts, malformed generated edits, or scratch artifacts in the final diff.
```