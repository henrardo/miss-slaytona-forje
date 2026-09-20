---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 38
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, generated registries, and domain behavior. Work from complete
  tracebacks, original function bodies, repository tests, and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task
  by importing from pydantic.v1 or another v1 compatibility namespace. Never
  make code import by deleting, emptying, bypassing, or replacing a function
  body with a no-op. Preserve every validator's substantive checks, mutations,
  errors, ordering assumptions, and return behavior. Treat Python source as
  Python: use True and False, never JSON literals true and false. Do not
  confuse import success, successful collection, a zero-looking pipeline
  status, one green focused test, warnings-only output, or a written migration
  summary with completion. Completion requires production code to compile,
  nonempty test collection to succeed, focused behavior tests to pass, the
  exact untruncated full-suite command to exit zero, and the final diff to pass
  static and behavior-preservation audits. Capture real command exit codes
  without piping pytest through head, tail, tee, or grep unless pipefail is
  enabled and the pytest status is explicitly preserved. Convert validators
  according to their individual signatures and semantics: a v1 pre root
  validator receives raw data, while a v2 after model validator normally
  receives and returns the model instance. Never perform a blind
  repository-wide decorator or method substitution. After each edited file,
  compile it, import its affected module, and run the smallest relevant test
  before editing another validator-heavy file. Continue repairing until the
  full suite passes; never stop with a progress summary, migration plan,
  partial import success, collection errors, known failing tests, an
  unexecuted proposed tool call, or a statement that the remaining work is too
  complex.

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
      Read and follow `establish-the-failure` in
      `references/repository-assessment.md`. Run the repository's canonical
      test command without truncating or masking its status. If output is too
      large, redirect it to a file, save `$?` immediately, and inspect the
      complete first traceback from that file. Record the exact command,
      Python and Pydantic versions, exit code, collection count, pass count,
      and first complete traceback. A pipeline ending in `head`, `tail`,
      `grep`, or `tee` does not establish the pytest status unless pipefail or
      `PIPESTATUS` is used correctly.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository root with `pwd`, inspect `git status --short`, and record
      all pre-existing modifications and untracked files. Do not overwrite,
      restore, or attribute those changes to the migration. If continuing a
      partially edited attempt, inspect its diff and compile affected files
      before adding more edits; repair or selectively revert mechanically
      corrupted migration edits rather than layering new transformations over
      invalid syntax.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Locate the actual dependency
      manifest, lock files, post-migration requirement files, test
      configuration, package entry points, supported Python versions, and
      canonical full-suite command. Do not assume setup.py or requirements.txt
      exists. Treat repository-specific migration fixtures and tests as source
      material, especially tests for repeatable segments, list-field helpers,
      serialization, and transaction registries.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Ensure the active interpreter
      actually imports Pydantic 2 and any split packages such as
      pydantic-settings. Update dependency metadata to the repository's target
      range before judging migration behavior. Do not use pydantic.v1,
      pydantic.v1.* imports, or any compatibility namespace as a shortcut.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search production code, tests,
      plugins, generated registries, and public exports for BaseSettings,
      class Config, validator, root_validator, allow_reuse, always, each_item,
      values or field parameters, __fields__, ModelField, SHAPE_LIST,
      field_info.extra, regex, constr(regex=...), min_items, max_items,
      parse_obj, parse_raw, from_orm, copy, dict, json, schema, construct,
      arbitrary Field keywords, unannotated inherited-field overrides, and
      Optional fields whose requiredness may change. Record every occurrence;
      do not equate an import-only grep with a complete inventory.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Identify public classes, methods,
      helpers, imports, command-line output, field metadata, parsing behavior,
      registry contents, and test-imported private helpers that must survive.
      In particular, retain helpers such as `_is_list_field` when repository
      tests or downstream code import them. Do not dismiss a leading
      underscore as permission to remove a tested symbol.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Before rewriting validators or shared model code, read and follow
      `preserve-original-semantics` in
      `references/repository-assessment.md`. Save the original source of every
      validator-heavy file with `git show HEAD:path` or an equivalent immutable
      baseline. For each validator, record whether it runs before or after
      field validation, its accepted arguments, keys or attributes read and
      written, exceptions raised, treatment of missing values, and return
      value. Preserve function bodies; migration is an API adaptation, not
      permission to delete validation logic.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Create one ledger row per file or
      tightly coupled behavior with its v1 surface, target v2 construct,
      relevant tests, current status, and executable checkpoint. Keep this
      ledger concise and operational; do not spend the implementation window
      producing a long standalone migration report instead of editing and
      testing code.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Separate mechanical changes from
      semantic changes. Mechanical candidates include BaseSettings imports,
      ConfigDict keys, renamed methods, and constraint keyword renames.
      Semantic work includes validator signatures and modes, requiredness,
      default validation, inherited fields, metadata interpretation,
      serializers, and registries. Never apply a mechanical batch operation to
      semantic work.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Work in dependency order and
      keep edits small: shared configuration, shared base models, reusable
      validation infrastructure, one validator-heavy module, parsing and
      serialization, then transaction-specific modules. After each file,
      run `python -m py_compile <file>`, import the affected module, and run
      the smallest relevant test. Stop and repair the first failed checkpoint
      before touching another validator-heavy file.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Fix only enough of the
      dependency chain to expose the next real blocker, then rerun nonempty
      collection. Common first blockers are BaseSettings imports, removed
      Field keywords, SHAPE_LIST imports, invalid Config keys, and missing
      decorator imports. Do not interpret `pytest tests/conftest.py
      --collect-only` returning “no tests collected” as collection success;
      collect the actual suite.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings to
      `pydantic_settings`, add the corresponding dependency, and translate
      settings Config behavior to SettingsConfigDict or the supported
      model_config form. Preserve case sensitivity, environment prefixes,
      dotenv behavior, aliases, and defaults. Rename Field `regex` to
      `pattern`; do not leave a v1 pin in the canonical manifest while testing
      against an unrelated globally installed v2 runtime.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Convert class Config to
      ConfigDict or the appropriate v2 configuration without changing domain
      behavior. Map settings such as `allow_mutation=False` to `frozen=True`,
      and preserve `extra`, enum handling, assignment validation, aliases,
      arbitrary types, and default validation. Watch inheritance: a base
      model's configuration affects every segment and loop, so compile and run
      representative construction and serialization tests immediately.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 rejects an
      unannotated subclass assignment that overrides an inherited field.
      Preserve fields such as `segment_name` by adding an explicit compatible
      annotation to each override, not by deleting all subclass declarations
      or weakening the base model. Search every model module for bare
      assignments to inherited Pydantic fields and test generated registries
      after correcting them.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Translate removed constraints
      deliberately: `regex` to `pattern`, `constr(regex=...)` to
      `constr(pattern=...)`, and collection `min_items` or `max_items` to
      `min_length` or `max_length`. Move arbitrary Field metadata such as
      `is_component=True` into `json_schema_extra={"is_component": True}` and
      use Python booleans. Audit Optional fields because `Optional[T]` without
      a default remains required in v2; add `= None` only when the original
      contract and tests say omission was allowed. Preserve aliases, bounds,
      decimal constraints, and schema extras.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove `allow_reuse`; v2 no
      longer needs it. Keep shared validator functions as plain reusable
      functions when model classes attach them with `field_validator(...)` or
      `model_validator(...)`. Do not create a local partial or alias named
      `field_validator` that shadows Pydantic's decorator. Adapt reusable
      function signatures to `ValidationInfo` only when the calling decorator
      supplies it, and update all call sites together.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each v1 `@validator`
      independently. Replace `values` with `ValidationInfo` and use
      `info.data` only for fields already validated in declaration order.
      Remove unsupported `field` and `config` parameters. Translate `pre=True`
      to `mode="before"` and explicitly preserve `always=True` or default
      validation semantics with model configuration or validated defaults.
      Handle `each_item` through item annotations or an equivalent validator.
      Add `@classmethod` only in the decorator order supported by v2. Test both
      valid and invalid cases; a module import does not prove validation still
      runs.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Before converting model validators, read and follow
      `classify-every-model-validator` in
      `references/migration-implementation.md`. For every v1 root validator,
      classify it as raw-input normalization, pre-validation cross-field
      checking, post-validation checking, mutation, reusable standalone
      validation, or a wrapper around another function. Record whether it must
      see absent or invalid fields and whether it returns a mapping or a
      model. Do not choose mode by text substitution.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert a v1
      `root_validator(pre=True)` to `model_validator(mode="before")` with a
      class-oriented raw-input signature that returns the input mapping or
      model. Convert a true post validator to `model_validator(mode="after")`
      with an instance signature, attribute access instead of `values.get`,
      mutation through supported instance behavior, and `return self`.
      Consider `mode="wrap"` only when it matches the original control flow.
      Preserve skip-on-failure behavior rather than mechanically adding a
      decorator argument unsupported by v2. Never leave an after validator
      written as `(cls, values)` or return a dict from it. Never empty its
      body merely to make imports succeed.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search all production Python
      files for both imports and uses of `validator`, `root_validator`,
      `field_validator`, and `model_validator`. Ensure every decorator is
      imported, every removed decorator import is gone, and transaction-
      specific modules were not missed. Treat grep exit 1 for “no matches” as
      an expected audit result, not a command failure requiring unrelated
      edits.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__` with
      class-level `model_fields` and update code that expected v1 ModelField
      attributes. Read annotations, defaults, aliases, and
      `json_schema_extra` from v2 FieldInfo. Do not access `model_fields` on an
      instance when class access is appropriate. Replace `field_info.extra`
      with `json_schema_extra` and preserve component-field behavior in both
      parsing and X12 serialization.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Replace removed shape
      constants such as SHAPE_LIST with an annotation-aware helper using
      `typing.get_origin` and, where necessary, unwrapping Annotated or Union.
      Preserve or add the repository's `_is_list_field` public helper if tests
      import it. Use the same helper in repeatable-segment normalization so a
      single dict or model is wrapped only for fields actually declared as
      lists. Test plain List, list, Optional[List], and non-list annotations
      represented by the repository.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 methods with v2
      equivalents only at Pydantic model call sites: `dict` with
      `model_dump`, `json` with `model_dump_json`, `parse_obj` with
      `model_validate`, `copy` with `model_copy`, and schema methods with
      their v2 forms. Do not perform repository-wide textual replacement that
      changes ordinary dictionaries or non-Pydantic APIs. Preserve exclude,
      alias, enum, unset, None, delimiter, decimal, date, and custom JSON
      encoder behavior. Run exact output assertions for CLI, dict/JSON, and
      X12 serialization.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      After introspection and inherited-field changes, read and follow
      `verify-generated-registries` in
      `references/migration-implementation.md`. Update registry-building code
      that reads field defaults through `__fields__` or ModelField. Verify
      expected segment keys, transaction model lookups, uniqueness, and
      import-time population for every supported version. An individual
      segment import can succeed while the generated registry remains empty or
      wrong.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Run compileall or py_compile
      across production code and fail on any syntax, indentation, or name
      error. Inspect failures caused by automated editing before proceeding.
      Compilation success is necessary but not sufficient.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import shared models, settings,
      both major segment modules, transaction modules, and public helpers.
      Then run the actual suite's collection command without truncation and
      require exit zero plus a nonzero collected-test count. Resolve the first
      complete collection traceback before running behavior tests.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Start with settings, shared
      support, segment tests for each version, repeatable-segment and loop
      initializer tests, parsing, serialization, registries, and the
      transaction family touched by the current edit. Preserve pytest's real
      exit code. A command targeting a nonexistent test is not evidence.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For every migrated validator
      family, execute at least one valid case and each invalid branch recorded
      in the semantic snapshot. Confirm the validator runs at the same stage,
      sees equivalent data, raises the intended error, and returns the
      expected model or value. Check omitted defaults and field-order
      dependencies explicitly.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate
      remains red. Always read the complete first traceback, form one
      hypothesis, make the smallest coherent edit, compile the edited file,
      rerun the narrow reproducer, and then rerun the next broader gate. Do
      not switch to unrelated searches, rewrite many files, or end the turn
      while a known failure remains. Continue until focused tests and the full
      suite are green.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Inspect `git diff
      --check`, the complete diff, every changed decorator, imports, function
      signatures, indentation, booleans, and return statements. Automated
      changes must have narrow file and syntax scopes, a predicted match count,
      a verified actual count, and immediate compilation. Revert a bad
      transformation before trying another.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Require no production imports
      from pydantic.v1, no legacy validator or root_validator decorators, no
      BaseSettings import from pydantic, no SHAPE_LIST, no unsupported
      allow_reuse, no stale `__fields__` or `field_info.extra`, no removed
      regex or collection keywords, no JSON booleans in Python, no malformed
      model_validator decorators, and no empty or no-op validator bodies
      introduced by the migration.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the exact canonical full-suite command untruncated and
      require its own exit code to be zero. If output is redirected, save the
      status before inspecting the log. Record collected, passed, failed,
      errored, skipped, and warning counts. Any collection error or failing
      test means the migration is incomplete.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Compare the final implementation against semantic snapshots and public
      contracts. Confirm settings, list wrapping, component parsing, X12
      serialization, validation errors, registries, CLI output, and public
      helper imports remain intact. A green suite does not authorize deleted
      checks or compatibility-layer imports.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Run `git diff --check`, inspect
      the entire final diff and status, distinguish migration changes from
      pre-existing work, and repeat the static audit if the diff changed after
      the green suite. Reject pydantic.v1 imports, empty functions, accidental
      scripts or migration-plan artifacts, malformed imports, broad unrelated
      rewrites, and claims unsupported by executed commands.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report the native-v2 changes, exact test commands and counts, static
      audit result, and any genuine residual warnings. Do not say “completed”
      if a command was not run, output was truncated with an unknown pytest
      status, tests failed, collection errored, or known work remains.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1` or another Pydantic v1 compatibility namespace to make native-v2 tests pass.
  - Never delete, empty, bypass, comment out, or replace a function or validator body with a no-op merely to make a module import.
  - Never blindly replace every `@validator` with `@field_validator` or every `@root_validator` with one model-validator mode.
  - Never run repository-wide sed or regex substitutions over semantic validator code, ordinary `.dict()` calls, or decorator signatures.
  - Never convert a post root validator to an after model validator while retaining `(cls, values)`, `values.get(...)`, or a dict return.
  - Never add `mode="before"` to every model validator to avoid understanding its original stage.
  - Never shadow Pydantic's `field_validator` or `model_validator` names with a local partial or compatibility wrapper.
  - Never use JSON literals `true`, `false`, or `null` in Python source.
  - Never delete inherited field declarations such as per-class segment names instead of annotating compatible overrides.
  - Never remove a tested public helper such as `_is_list_field` because it appears private.
  - Never treat an import-only check, compile-only check, or collection-only check as proof of behavioral correctness.
  - Never treat “no tests collected” as successful collection.
  - Never infer pytest success from a pipeline whose last command is `head`, `tail`, `grep`, or `tee`.
  - Never hide a failed command by appending `|| true` unless the command is an audit where no matches is the expected result and that expectation is recorded.
  - Never confuse grep exit 1 for no matches with evidence that the repository or migration failed.
  - Never stop after the first green focused test when other modules or the full suite remain untested.
  - Never end with a summary, plan, proposed edit, or unexecuted tool-call text while known failures remain.
  - Never create migration-plan files, one-off repair scripts, or unrelated artifacts in the repository unless they are required deliverables.
  - Never overwrite or revert pre-existing user changes discovered in the initial working-tree snapshot.
  - Never suppress validation errors, weaken field constraints, add broad arbitrary-types allowances, or change extra-field policy merely to obtain green tests.
  - Never add `= None` to every Optional field mechanically; preserve the repository's actual requiredness contract.
  - Never assume deprecation warnings are harmless when they identify an unmigrated native-v2 surface required by the task.
  - Never report completion without an exact untruncated full-suite exit code of zero and a final static and behavioral audit.
```