---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 19
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Treat an import success as only an early checkpoint: completion
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
      repository's exact test command without piping it through `head`, `tail`,
      `grep`, or another command that can hide pytest's exit status. If output
      is large, redirect it to a file, capture `$?` immediately, and inspect
      that file separately. Record the installed Python, Pydantic,
      pydantic-core, and pydantic-settings versions; the exact command; its
      actual exit code; collection status; pass/fail/error counts; the first
      complete traceback; and warnings. A command such as
      `pytest ... 2>&1 | head` reporting exit zero is not evidence that pytest
      passed.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Resolve
      the repository root once with `pwd` and reuse that verified path; do not
      repeatedly mistype or guess paths. Inspect `git status --short` and the
      current diff. Distinguish user changes from prior migration edits and
      untracked harness files. Never discard user work. If this is a fresh
      attempt, start from the supplied repository state rather than creating
      migration scripts, plans, or temporary source files unless they are
      required deliverables.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Follow `inspect-repository-contract` in
      `references/repository-assessment.md` before choosing dependency or test
      commands. Inspect pyproject.toml, lock files, requirements files,
      requirements-v2.txt or equivalent migration notes, CI configuration,
      test configuration, package exports, and repository documentation.
      Prefer the repository-declared commands and target versions. Do not
      assume setup.py or requirements.txt exists; list the root first. Treat
      tests and migration-specific requirement files as executable
      specifications, including tests for public helpers not present in the v1
      implementation.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Follow `make-runtime-match-target` in
      `references/repository-assessment.md` before diagnosing v2 behavior.
      Install or verify the target native Pydantic v2 dependency set, including
      pydantic-settings when settings models exist. Confirm imports resolve
      from the intended environment. Do not use pydantic.v1, a compatibility
      shim, or an old interpreter environment to make failures disappear.
      Re-run the baseline command after dependency changes so subsequent
      diagnoses describe the target runtime.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Follow `inventory-v1-surface` in
      `references/repository-assessment.md` before editing production Python
      files. Search all production Python files, not only the first matches,
      for BaseSettings; class Config; validator and root_validator imports and
      decorators; allow_reuse; each_item; pre and always; values, field, and
      config validator arguments; __fields__; ModelField; SHAPE_* constants;
      field_info.extra; Field(regex=...); constr(regex=...); arbitrary Field
      extras; min_items and max_items; parse_obj, parse_raw, from_orm, copy,
      dict, json, schema, and schema_json; custom encoders; GenericModel;
      dataclasses; private attributes; forward references; and equality or
      serialization assumptions. Save file names, line numbers, counts, and
      categories. Search again after every migration phase.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md` before deciding which interfaces
      may change. Read tests that exercise model constructors, invalid inputs,
      error locations, serialization, X12 or other custom rendering, field
      ordering, settings environment behavior, schema metadata, repeatable
      list wrapping, and public imports. Record helpers imported directly by
      tests or downstream modules, including list-field detectors such as
      `_is_list_field`. Preserve those interfaces unless the task explicitly
      changes them. Note that Pydantic v2 makes `Optional[T]` without a default
      required; identify where v1 behavior expected an omitted value to become
      None.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Follow `classify-migration-work` in
      `references/repository-assessment.md` before ordering the migration.
      Classify each inventory item as dependency/settings, shared model
      configuration, inherited field override, field declaration, reusable
      validator infrastructure, field validator, model validator,
      introspection, parsing/serialization, public helper, or test-only
      compatibility. Order work by import and collection blockers first, then
      shared infrastructure, then behavior. For every validator, explicitly
      classify it as before-field, after-field, before-model, or after-model
      and record whether its input is raw data or a constructed instance.
      Never treat decorator renaming as sufficient migration.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` before defining
      checkpoints, then follow its `create-small-edit-checkpoints`
      instructions. Use narrow checkpoints such as one shared module, one
      validator family, or one traceback. After each edit, run syntax
      compilation, the smallest relevant import, collection or focused test,
      and inspect the diff. Avoid repository-wide sed or regex rewrites of
      validators: v1 validators with superficially similar decorators can
      require different v2 signatures and return values. If automation is
      justified, preview matches, transform only a proven shape, compile
      immediately, and inspect every changed hunk.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` before the first migration
      edit, then follow its `repair-first-collection-blocker` instructions.
      Repair only the earliest complete import or collection traceback, then
      rerun collection to expose the next blocker. Common first blockers are
      BaseSettings relocation, removed imports, invalid Field keywords,
      unannotated inherited fields, stale validator names, and malformed
      decorator syntax. Never continue editing based on a truncated traceback,
      and never announce completion after an import smoke test.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Follow `update-dependencies-and-settings` in
      `references/migration-implementation.md` when settings or dependency
      migration begins. Change the project requirement to Pydantic >=2,<3 or
      the repository-specified v2 range and add pydantic-settings explicitly.
      Import BaseSettings and SettingsConfigDict from pydantic_settings.
      Convert settings Config behavior to `model_config` while preserving env
      file, prefix, case sensitivity, extra handling, nested delimiter, and
      encoding. Replace Field(regex=...) with Field(pattern=...). Validate
      actual environment-variable loading, defaults, and rejection behavior,
      not just class import.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md` when converting model
      configuration. Replace inner Config classes with ConfigDict or
      model_config and preserve every behavior intentionally: frozen replaces
      allow_mutation=False; populate_by_name replaces allow_population_by_field_name;
      from_attributes replaces orm_mode; use_enum_values, extra, validate_assignment,
      arbitrary_types_allowed, str transforms, alias behavior, and serialization
      settings must be considered separately. Put shared configuration on the
      correct base class so descendants inherit it. Do not keep both conflicting
      Config and model_config definitions.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md` when repairing inherited fields.
      Pydantic v2 rejects an unannotated attribute that overrides a model field.
      Add an explicit compatible annotation, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`, rather than changing
      the value into ClassVar or suppressing the error. Search all subclasses
      for unannotated overrides, not only the first failing class, and verify
      the field remains present in model_fields, parsing, dumps, and custom
      output.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Follow `migrate-field-definitions` in
      `references/migration-implementation.md` when converting field
      declarations and constraints. Replace regex with pattern in Field and
      constrained strings; replace min_items and max_items with min_length and
      max_length where appropriate; move custom Field extras such as
      `is_component=True` into
      `json_schema_extra={"is_component": True}` and update consumers to read
      that metadata. Preserve aliases, defaults, factories, strictness,
      decimal constraints, and field order. Review every `Optional[T]`: add
      `= None` only where omission was optional under the existing contract.
      Test boundaries and invalid inputs because v2 coercion and regex behavior
      can differ.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md` before converting validator
      reuse sites. Remove v1 partial wrappers and allow_reuse arguments.
      Keep reusable logic as ordinary functions with signatures compatible
      with the selected v2 decorator, or wrap it with a small explicit adapter.
      Import `field_validator` from pydantic directly rather than defining a
      same-named compatibility helper that shadows it. Preserve shared
      validator behavior and public imports. For validators assigned as class
      attributes, verify the decorated callable binds correctly in every model
      that reuses it.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Follow `migrate-field-validators` in
      `references/migration-implementation.md` whenever converting field
      validators. Replace `@validator` with `@field_validator`, using
      `mode="before"` only when the original used pre=True or requires raw
      input. Use the v2 signature `(cls, value, info: ValidationInfo)` and read
      already-validated siblings from `info.data`; do not retain a v1 `values`
      parameter. Respect field declaration order because info.data contains
      only prior validated fields. Handle always behavior through defaults,
      validate_default, or model validation according to the original
      semantics. Confirm each_item behavior explicitly rather than translating
      mechanically. Return the validated value on every successful path.
      Verify decorator names and imports together so no stale `@validator`
      remains and no NameError blocks collection.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Follow `migrate-model-validators` in
      `references/migration-implementation.md` whenever converting root or
      model validators. Convert `root_validator(pre=True)` to
      `model_validator(mode="before")` with a class method accepting and
      returning raw input, normally `(cls, data)`. Convert a post
      root_validator to an instance
      `model_validator(mode="after")` accepting `self`, reading attributes, and
      returning `self`. Do not leave a v1 `(cls, values)` dictionary body under
      an after-model decorator; do not mass-replace `values.get(...)` without
      understanding whether values is raw data or an instance. Preserve raised
      errors, conditional requirements, mutation, ordering, and missing-field
      behavior. If reusable dictionary-based root logic remains valuable,
      adapt `self` to the exact data shape deliberately and apply any result
      back safely. Treat the Pydantic 2.12+ warning about after validators on
      classmethods as a migration defect, not harmless noise.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Follow `repair-field-introspection` in
      `references/migration-implementation.md` when replacing v1 reflection
      APIs. Replace `__fields__` with class-level `model_fields` and account
      for FieldInfo rather than ModelField. Replace field_info.extra reads with
      `json_schema_extra`. Derive annotations through `field.annotation`,
      `typing.get_origin`, and `typing.get_args`; do not rely on removed
      `shape`, `type_`, `outer_type_`, or SHAPE_LIST constants. Where code
      maps segment names or other defaulted fields, read the FieldInfo default
      and handle undefined defaults explicitly. Test reflection-driven parsing,
      rendering, registration, and ordering.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Follow `preserve-list-field-helper` in
      `references/migration-implementation.md` when list detection or
      repeatable-field behavior exists. Preserve or implement the public
      `_is_list_field`-style helper expected by tests and production code.
      Detect `list[T]` and `typing.List[T]`, including list members inside
      Optional or Union annotations, by recursively inspecting origins and
      arguments. Use it in before-model wrapping logic so a single repeatable
      item becomes a one-element list while existing lists and None retain
      their meaning. Test every model field identified by the repository's
      loop-initializer or repeatable-segment tests; an importable helper alone
      is insufficient.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md` when changing parsing, dumping,
      schemas, copies, or custom serializers. Use model_validate,
      model_validate_json, model_dump, model_dump_json, model_copy, and
      model_json_schema as appropriate. Preserve the old include/exclude,
      exclude_none, exclude_unset, by_alias, enum, date, Decimal, delimiter,
      custom encoder, and nested model behavior. Update parser reflection to
      use model_fields and metadata from json_schema_extra. Do not blindly
      replace every `.dict()` call: ordinary dictionaries and third-party
      objects are not Pydantic models, and validator inputs may be either raw
      mappings or model instances. Keep custom X12 or other domain output
      byte-for-byte compatible where tests require it.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Follow `compile-production-code` in
      `references/verification-and-repair.md` before broad imports. Run
      compileall or py_compile across the complete production package after
      each automated edit and after each validator phase. Fix syntax,
      indentation, malformed decorators, accidental colons, duplicate imports,
      invalid replacement text, and undefined names before running tests.
      Compilation is a gate, not completion.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md` before broad behavior repair.
      Import representative shared models and each major version or transaction
      module, then run the full test collection command without truncating or
      piping away its status. Repair collection errors one complete traceback
      at a time. Confirm there are no stale validator/root_validator names,
      removed Pydantic imports, unannotated overrides, invalid Field arguments,
      or missing public helpers. Collection success proves only that tests can
      run.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md` after collection succeeds. Run
      the smallest tests for each migrated behavior: settings, shared models,
      each major segment module, reusable validators, loop initialization,
      parsing, custom serialization, and representative complete transaction
      fixtures. For a failing test, retain the full traceback and run the exact
      node id when it exists. Do not guess nonexistent test names. A group of
      passing segment tests does not substitute for loop, parser, and
      transaction tests.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Follow `compare-validation-semantics` in
      `references/verification-and-repair.md` after focused tests exercise
      migrated behavior. Compare valid and invalid examples around required
      versus optional fields, defaults, coercion, enum values, aliases,
      constrained strings and decimals, sibling-dependent validators,
      model-level conditions, error types and locations, list wrapping, and
      serialized output. Add or run targeted regression cases when existing
      tests do not distinguish a native v2 implementation from a bypassed or
      weakened validator.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` while any migration failure
      remains. Use the loop: run one untruncated failing command, identify the
      first causal traceback, inspect the involved source and test, make the
      smallest behavior-preserving edit, compile, rerun that exact test, then
      rerun the enclosing test file or collection gate. Keep a failure ledger
      so already-repaired categories are not repeatedly rediscovered. Do not
      stop because the suite reports some passing tests, including 57 passing;
      any failure or collection error means the migration is incomplete.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and after
      any automated transformation. Inspect `git diff --check`, diff statistics,
      and every changed hunk. Look for accidental global substitutions,
      duplicated decorators or classmethod lines, malformed signatures,
      lowercase `true` in Python, deleted logic, reordered fields, unexpected
      generated files, and comments that claim migration without implementing
      it. Remove temporary migration scripts and plan files unless the
      repository requires them. Recompile and rerun affected focused tests
      after corrections.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md` before the static audit, then
      follow `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      pydantic.v1 and other v1 compatibility imports, BaseSettings from
      pydantic, validator, root_validator, allow_reuse, class Config,
      __fields__, ModelField, SHAPE_ constants, field_info.extra,
      Field(regex=...), constr(regex=...), unsupported arbitrary Field extras,
      stale dict/json/parse APIs, and deprecated after-model classmethods.
      Classify every remaining match as a defect or an explicitly justified
      non-production occurrence. The audit must fail if a function body was
      emptied, changed to pass, replaced by an unconditional return, or skipped
      merely to make imports succeed.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Follow `run-full-suite` in `references/verification-and-repair.md` only
      after the static audit passes. Run the repository's exact full-suite
      command directly and untruncated. If logging is necessary, redirect to a
      file, save the test process exit status, and inspect the file afterward;
      do not infer success from the status of head, tail, tee, grep, or a shell
      pipeline without pipefail and explicit status handling. Record the exact
      command, exit code, pass/fail/error/skip counts, and warnings. If any
      failure remains, return to iterative repair rather than reporting a
      partial success.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Exercise representative end-to-end parsing and serialization fixtures,
      settings loading, invalid model construction, repeatable list wrapping,
      custom rendering, and public helper imports. Compare outputs with checked
      fixtures or the pre-migration contract. Confirm validators still execute
      rather than merely allowing models to import. Treat newly introduced
      Pydantic deprecation warnings in production code as unresolved migration
      work unless the repository explicitly permits them.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md` before completion. Re-run
      compilation, the static migration audit, `git diff --check`, the exact
      full suite, and representative end-to-end checks after the final edit.
      Inspect `git status --short` and the complete diff for unrelated changes,
      temporary files, missing dependency metadata, compatibility namespaces,
      deleted logic, no-op bodies, or weakened validation. Completion is
      forbidden unless every gate is green with a known exit status.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Follow `report-completion` in
      `references/verification-and-repair.md` when reporting the final or
      interrupted state. State the native v2 dependency and settings changes,
      major API migrations, behavior preserved, exact tests and audits run,
      their actual exit codes and counts, and any remaining warnings or risks.
      If interrupted or not green, report the current first failure and the
      next repair step; never say the migration is complete after imports,
      collection, a focused subset, a hidden pipeline status, or a suite with
      any failures.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, use another v1 compatibility namespace, or pin the runtime back to Pydantic v1 to obtain green tests.
  - Never empty, delete, bypass, comment out, replace with `pass`, or turn a function or validator body into an unconditional no-op merely to make a module import.
  - Never claim success from `pytest ... | head`, `pytest ... | tail`, or another pipeline whose displayed exit status belongs to the final pipeline process rather than pytest.
  - Never end after an import smoke test, successful collection, one focused file, or a partial suite with any failures; these are checkpoints only.
  - Never mechanically rename `root_validator` to `model_validator` without converting pre validators to raw-data before validators and post validators to instance after validators that return self.
  - Never retain a v1 field-validator signature using `values`, `field`, or `config`; use ValidationInfo and account for field order.
  - Never use repository-wide sed or regex rewrites for heterogeneous validators without previewing matches, compiling immediately, and auditing every changed hunk.
  - Never replace every `.dict()` call indiscriminately; first prove the receiver is a Pydantic model rather than a normal mapping or third-party object.
  - Never remove or privatize a helper imported by tests or downstream code, including list-field detection helpers, merely because Pydantic v2 no longer provides the old primitive.
  - Never suppress an unannotated inherited-field error with ClassVar when the attribute is intended to remain a serialized and validated model field.
  - Never leave custom metadata as arbitrary Field keyword arguments when consumers depend on it; migrate it to json_schema_extra and update the readers.
  - Never treat Pydantic deprecation warnings for v1 decorators, field extras, old introspection, or after-model classmethods as harmless evidence of a completed native v2 migration.
  - Never create summary documents, migration scripts, or speculative bulk edits instead of repairing and validating the production code.
  - Never repeatedly explore the repository or research generic migration guidance while a complete local traceback already identifies the next blocker.
```