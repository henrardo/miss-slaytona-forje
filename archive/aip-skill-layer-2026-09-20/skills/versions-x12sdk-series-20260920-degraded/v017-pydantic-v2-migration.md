---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 17
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Do not declare completion after import smoke tests, collection,
  a focused subset, or a command whose status was hidden by a pipe. Completion
  requires production code to compile, test collection to succeed, focused
  behavior tests to pass, the exact untruncated full-suite command to exit zero,
  and the final diff to pass static and behavior-preservation audits.

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
      Read `references/repository-assessment.md` before establishing the
      baseline, then follow its `establish-the-failure` instructions. Run the
      repository's real test command without `head`, `tail`, or another
      pipeline that can replace pytest's exit status. Redirect complete output
      to a log when it is large, preserve the actual exit code, and inspect the
      first complete traceback. Record collected, passed, failed, and errored
      counts rather than treating collection output or an import error as a
      test result.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Resolve
      and reuse the canonical repository path instead of repeatedly typing
      similar absolute paths. Capture `git status --short` and the starting
      diff. Do not overwrite, revert, or mix pre-existing user changes with
      migration edits. Exclude generated caches and agent-support directories
      from source inventories.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Follow `inspect-repository-contract` in
      `references/repository-assessment.md` before choosing dependency or test
      commands. Read the actual dependency files, test configuration, CI
      commands, migration notes, and any post-migration requirements file.
      Treat comments describing a measured or human-merged target dependency
      set as evidence. Inspect tests added specifically for the migration;
      helpers imported directly by tests are public migration contracts even
      when their names begin with an underscore.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Follow `make-runtime-match-target` in
      `references/repository-assessment.md` before diagnosing v2 behavior.
      Verify the interpreter, Pydantic, pydantic-core, pydantic-settings, and
      pytest versions in the same environment used by the suite. Install from
      the repository's declared target dependency set when needed. Do not edit
      source around a missing package that the target dependency contract
      requires.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Follow `inventory-v1-surface` in
      `references/repository-assessment.md` before editing production Python
      files. Search every production package, not only the first files returned
      by `head`. Inventory imports and usages of BaseSettings, Config,
      validator, root_validator, allow_reuse, ModelField, SHAPE constants,
      __fields__, field_info.extra, regex constraints, min_items/max_items,
      parse_obj/parse_raw/from_orm, dict/json/copy/schema, custom Field extras,
      required Optional annotations, and unannotated overrides of inherited
      model fields. Keep file and line locations so the final static audit can
      prove the inventory was closed.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md` before deciding which interfaces
      may change. Read model, parser, serialization, settings, and migration
      regression tests. Record exact output formatting, aliases, enum handling,
      immutability, repeatable-list normalization, metadata-driven component
      parsing, validator error behavior, and directly imported helpers such as
      list-field detection. Search all call sites before renaming or removing a
      helper.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Follow `classify-migration-work` in
      `references/repository-assessment.md` before ordering the migration.
      Build a file-by-file matrix that distinguishes mechanical API renames
      from semantic conversions. Mark every validator by mode, available input
      type, required sibling fields, ordering assumptions, reuse pattern, and
      expected return type. Mark every Optional field whose v1 omission
      behavior requires an explicit `= None`. Prioritize collection blockers,
      shared base models, reusable infrastructure, and parser reflection before
      leaf transaction models.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` before defining
      checkpoints, then follow its `create-small-edit-checkpoints`
      instructions. Each checkpoint must change one coherent concern, compile
      affected files, import the affected module, run the smallest relevant
      test, and inspect `git diff --check` plus the local diff before proceeding.
      Do not create planning documents or migration scripts unless the
      repository requests them; spend the available execution budget repairing
      and validating production code.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` before the first migration
      edit, then follow its `repair-first-collection-blocker` instructions.
      Use the first complete traceback, make the smallest correct native-v2
      repair, and immediately rerun the exact failing import or collection
      command. Continue one blocker at a time. An exit-zero shell pipeline that
      merely printed pytest errors is not a repaired blocker.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Follow `update-dependencies-and-settings` in
      `references/migration-implementation.md` when settings or dependency
      migration begins. Move BaseSettings to `pydantic_settings`, add the
      declared dependency, convert settings configuration to SettingsConfigDict
      or the repository's native-v2 equivalent, and convert `regex` to
      `pattern`. Preserve environment prefix, case sensitivity, dotenv,
      encoding, extra-field, and default semantics. Verify settings import and
      instantiate settings under representative environment variables.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md` when converting model
      configuration. Replace inner Config classes with ConfigDict settings
      while preserving enum values, assignment validation, population by field
      name or alias, extra handling, arbitrary types, immutability, string
      behavior, and default validation. Put shared behavior on the correct base
      model so descendants inherit it. Never silence protected-namespace or
      shadowed-field errors without first determining the intended model
      contract.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md` when repairing inherited fields.
      Pydantic v2 requires an annotation when a subclass overrides an inherited
      model field. Convert declarations such as an unannotated constant
      `segment_name = ...` to an explicitly annotated model field of the
      inherited type, unless repository behavior proves it is a ClassVar.
      Search the entire package for analogous overrides and run imports after
      each coherent batch.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Follow `migrate-field-definitions` in
      `references/migration-implementation.md` when converting field
      declarations and constraints. Convert Field `regex` and constrained-string
      `regex` to `pattern`; convert list `min_items` and `max_items` to
      `min_length` and `max_length`; verify changed constrained-type signatures;
      and use Python `True`, not JSON `true`, in source. Move custom Field
      keywords into `json_schema_extra` while preserving the exact metadata
      keys consumed by parsing and serialization. Give omission-compatible
      Optional fields explicit `None` defaults. Test boundary values and
      omission behavior rather than trusting successful schema construction.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md` before converting validator
      reuse sites. Remove v1 `allow_reuse`; do not implement a broad wrapper
      that blindly forwards v1-only keyword arguments. Distinguish raw
      validation functions from already decorated descriptors. Keep decorator
      names from shadowing imported helpers, and verify every assignment-style
      reuse site. For reusable model validation functions, write an explicit
      adapter for the chosen before or after mode and test it at more than one
      call site.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Follow `migrate-field-validators` in
      `references/migration-implementation.md` whenever converting field
      validators. Replace `@validator` with `@field_validator` deliberately,
      map `pre=True` to `mode="before"`, and use ValidationInfo for sibling
      data. Replace `values.get(...)` with `info.data.get(...)` only after
      confirming field order makes that data available. Preserve always/default
      behavior with native-v2 configuration where required. Add `@classmethod`
      where appropriate, preserve the validated value return, and test valid,
      invalid, omitted, and cross-field cases. Never use an unrestricted
      search-and-replace over validator syntax or signatures.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Follow `migrate-model-validators` in
      `references/migration-implementation.md` whenever converting root or
      model validators. Convert each validator independently. A before model
      validator receives raw input, normally has `(cls, values)`, returns the
      raw mapping, and uses `@model_validator(mode="before")`. An after model
      validator normally receives `self`, reads attributes, and returns `self`.
      Do not mechanically relabel a v1 `(cls, values)` function as an after
      validator. Preserve failure ordering, defaults, aliases, nested-model
      inputs, and mutation behavior. Verify that every converted function still
      contains its original domain checks; deleting or emptying its body is
      prohibited even if imports then succeed.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Follow `repair-field-introspection` in
      `references/migration-implementation.md` when replacing v1 reflection
      APIs. Replace `__fields__` with `model_fields` and ModelField assumptions
      with FieldInfo and annotation inspection. Read custom metadata from
      `json_schema_extra`, treating missing metadata as an empty mapping. Check
      default, alias, annotation, requiredness, and ordering behavior at every
      reflection site, including module-level model registries. Do not retain
      SHAPE constants or infer list shape from removed v1 internals.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Follow `preserve-list-field-helper` in
      `references/migration-implementation.md` when list detection or
      repeatable-field behavior exists. Preserve or implement the repository's
      public list-field helper using native typing information such as
      `get_origin` and `get_args`, including Optional or Union wrappers and
      Annotated types as exercised by models. Use that helper in pre-validation
      that wraps a single repeatable segment into a list. Verify direct helper
      imports, list and non-list classifications, omitted values, existing
      lists, and single-object normalization.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md` when changing parsing, dumping,
      schemas, copies, or custom serializers. Use `model_validate`,
      `model_validate_json`, `model_dump`, `model_dump_json`,
      `model_json_schema`, and `model_copy` where their semantics match.
      Preserve aliases, exclude flags, enum representation, Decimal/date
      handling, custom JSON encoders, delimiter propagation, field order,
      component metadata, and exact domain output. Do not replace a custom
      serializer with a generic dump merely because both return dictionaries.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Follow `compile-production-code` in
      `references/verification-and-repair.md` before broad imports. Compile the
      complete production package, not a hand-picked file list. Treat syntax
      errors, malformed decorators, duplicate arguments, invalid Python
      literals, and indentation damage as transformation failures. Repair and
      recompile before attempting pytest.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md` before broad behavior repair.
      Import shared models, settings, parsers, both versioned segment modules,
      transaction packages, and registry modules. Then run untruncated
      `pytest --collect-only` using the repository command and preserve its
      actual exit code. Collection is a gate, not completion; zero executed
      tests or a list of node IDs does not prove behavior.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md` after collection succeeds. Run
      tests for settings, shared support, both versioned segment families,
      repeatable-list initialization, parsing, serialization, and the first
      transaction family affected by each validator conversion. Use exact node
      IDs only after confirming they exist. Do not stop after one file or after
      the first passing smoke test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Follow `compare-validation-semantics` in
      `references/verification-and-repair.md` after focused tests exercise
      migrated behavior. Compare accepted input, rejected input, defaults,
      coercion, validator ordering, error locations, aliases, model equality,
      and serialized output against tests and the pre-migration contract.
      Explicitly probe required-versus-optional fields, before-versus-after
      cross-field validation, repeatable lists, inherited discriminators, and
      metadata-driven component fields.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` while any migration failure
      remains. Keep a strict loop: run the smallest failing command without
      truncation, read the complete traceback, classify the root cause, make
      one coherent repair, inspect the diff, rerun that command, then rerun the
      nearest broader gate. If the same failure survives two edits, stop
      guessing and inspect the relevant source, tests, Pydantic signature, and
      model field metadata interactively. Continue until collection and all
      focused groups are green.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and after
      any automated transformation. Inspect every changed hunk produced by
      sed, regex, codemods, or scripts. Look for invalid decorator forms,
      decorators with the wrong mode, signatures inconsistent with their mode,
      removed domain checks, JSON literals in Python, altered unrelated files,
      accidental helper renames, duplicated imports, temporary scripts, and
      partial edits. Revert the transformation and edit deliberately if its
      output cannot be audited confidently.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md` before the static audit, then
      follow `run-static-migration-audit` in
      `references/verification-and-repair.md`. Re-run the original v1-surface
      inventory over production code and inspect every remaining match.
      Explicitly reject `pydantic.v1`, compatibility-namespace imports,
      BaseSettings from pydantic, v1 validators, allow_reuse, v1 field
      reflection, removed Field arguments, deprecated serialization calls when
      production uses them, empty function bodies, unconditional early
      returns, and validation logic replaced by pass or ellipsis. Run
      `git diff --check`.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Follow `run-full-suite` in `references/verification-and-repair.md` only
      after the static audit passes. Run the exact repository full-suite
      command without `head`, `tail`, `grep`, or a pipeline that masks its
      status. Capture complete output to a log if needed and separately print
      the saved exit status. Require exit zero and a nonzero executed-test
      count. If it fails, return to the iterative repair loop, rerun affected
      focused tests, and then rerun the complete suite.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Exercise representative end-to-end parsing and serialization fixtures,
      including both supported model versions when present. Confirm settings,
      validator errors, repeatable-list normalization, custom field metadata,
      delimiters, enums, dates, decimals, and exact domain output. A green suite
      does not excuse removed validation or bypassed code.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md` before completion. Inspect
      `git status --short`, the complete diff, diff statistics, and every
      modified production function. Remove only migration-created temporary
      files and generated artifacts. Preserve pre-existing user files. Re-run
      compile, static audit, and the exact full suite after any final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Follow `report-completion` in
      `references/verification-and-repair.md` when reporting the final or
      interrupted state. Report dependency changes, migrated API categories,
      behavior-preservation decisions, exact validation commands, actual exit
      statuses, and test counts. If work is incomplete, state the first
      unresolved traceback and the last verified gate; never describe imports,
      collection, partial tests, or unexecuted plans as successful completion.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1` or another Pydantic v1 compatibility namespace; the target is native Pydantic v2.
  - Never delete, empty, bypass, or replace a validator or other function body with `pass`, ellipsis, a no-op, or an unconditional early return merely to make imports or tests proceed.
  - Never mechanically replace every `root_validator` with the same `model_validator` mode; classify each validator and rewrite its signature, input access, and return value.
  - Never mechanically replace `values` with `self` or `info.data`; inspect whether the validator runs before or after validation and whether sibling fields are available.
  - Never run broad sed or regex transformations across validator bodies without immediately compiling and reviewing every changed hunk.
  - Never treat `pytest ... | head`, `pytest ... | tail`, or a similar pipeline's exit zero as pytest success.
  - Never truncate the only copy of a traceback; capture complete output before selecting excerpts.
  - Never claim success after imports, collection, a focused subset, zero executed tests, or a suite that was not run after the final edit.
  - Never fix a missing target dependency by rewriting source around it when repository metadata requires that dependency.
  - Never use JSON `true`, `false`, or `null` as Python source values.
  - Never discard custom Field metadata consumed by parsers or serializers; migrate it to native-v2 metadata and update every reader.
  - Never infer repeatable-list fields from removed SHAPE constants; preserve the public helper with native typing introspection and test Optional or Union annotations.
  - Never silence inherited-field errors by turning a real model field into an unverified ClassVar or by suppressing Pydantic diagnostics.
  - Never assume `Optional[T]` remains omittable in Pydantic v2 without an explicit default.
  - Never create summaries, plans, or temporary migration scripts in place of running the next validation gate.
  - Never overwrite or revert pre-existing user changes, and never leave migration-generated scratch files in the final diff.
```