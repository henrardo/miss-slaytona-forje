---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 36
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, registries, and domain behavior. Work from complete tracebacks,
  original function bodies, repository tests, and executable checkpoints
  rather than speculative bulk rewrites. Never satisfy the task by importing
  from pydantic.v1 or another v1 compatibility namespace. Never make code
  import by deleting, emptying, bypassing, or replacing a function body with a
  no-op. Preserve every validator's substantive checks, mutations, errors, and
  return behavior. Treat Python source as Python: use True and False, never
  JSON literals true and false. Do not confuse import success, successful
  collection, a zero-looking pipeline status, a green focused test, or
  warnings-only output with completion. Completion requires production code
  to compile, nonempty test collection to succeed, focused behavior tests to
  pass, the exact untruncated full-suite command to exit zero, and the final
  diff to pass static and behavior-preservation audits. Capture real command
  exit codes without piping pytest through head, tail, tee, or grep unless
  pipefail is enabled and the pytest status is explicitly preserved. Convert
  validators according to their individual signatures and semantics: a v1
  pre root validator receives raw data, while a v2 after model validator
  normally receives and returns the model instance. Never perform a blind
  repository-wide decorator substitution. After each edited file, compile it,
  import its affected module, and run the smallest relevant test before
  editing another validator-heavy file. Continue repairing until the full
  suite passes; never stop with a progress summary, migration plan, partial
  import success, collection errors, known failing tests, or an unexecuted
  proposed tool call.

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
      test command without truncating or masking its exit status. Capture the
      first complete traceback, collection count, pass count, fail count,
      runtime versions, and exact command. If output is large, redirect it to
      a file, preserve `$?`, and inspect that file afterward; do not pipe the
      test command directly through `head`, `tail`, `tee`, or `grep`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Record
      the absolute repository path and every pre-existing tracked or untracked
      change. Do not overwrite, restore, or attribute existing user changes to
      the migration. Reuse the recorded absolute path exactly; path typos are
      command failures, not migration evidence.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect pyproject metadata,
      lockfiles, requirements files, test configuration, CI commands,
      supported Python versions, package exports, and any post-migration
      dependency fixture such as `requirements-v2.txt`. Do not assume
      `setup.py` or `requirements.txt` exists; discover the actual contract.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Confirm that the interpreter is
      loading Pydantic 2 and required companion packages such as
      pydantic-settings from the intended environment. Update declared
      dependencies consistently with the repository contract, but do not use
      pydantic.v1, compatibility imports, or an environment downgrade to hide
      migration failures.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search production code, package
      initializers, CLI code, generated registries, and tests for all relevant
      v1 interfaces, including BaseSettings, Config, validator,
      root_validator, allow_reuse, each_item, always, pre, values, field,
      ModelField, SHAPE_LIST, __fields__, field_info.extra, regex, min_items,
      max_items, parse_obj, parse_raw, from_orm, copy, dict, json, schema, and
      custom Field metadata. Record exact files, line numbers, decorator
      arguments, and function signatures instead of relying on aggregate
      counts or truncated grep output.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Treat tests importing private
      helpers, package exports, parser field order, X12 rendering, settings
      behavior, segment registries, and constructor conveniences as contracts.
      Explicitly record helpers such as `_is_list_field`; absence from the
      current production source can itself be the collection blocker the
      migration must repair rather than a reason to alter tests.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Before rewriting validators or shared model code, read and follow
      `preserve-original-semantics` in
      `references/repository-assessment.md`. Save or inspect the clean Git
      version of every affected function. For each validator, record its
      original mode, fields, ordering dependencies, accepted input shape,
      mutations, required-field checks, exceptions, and return value. A
      migration is invalid if a function body is deleted, emptied, replaced
      with `pass`, reduced to an unconditional return, or bypassed merely to
      make imports succeed.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Create one ledger row per
      migration site with file, symbol, v1 construct, intended v2 construct,
      semantic risks, test coverage, status, and checkpoint command. Keep
      root/model validators as individual rows; do not collapse dozens of
      validators into a single search-and-replace task.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Order work by dependency:
      collection blockers, settings, shared base models, inherited fields,
      field declarations, reusable validators, field validators, model
      validators, introspection, parsing and serialization, registries, then
      behavior regressions. Distinguish mechanical renames from semantic
      rewrites. Never classify decorator conversion as purely mechanical when
      the callable signature or data shape changes.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Define a compile, import, and
      focused-test checkpoint for every validator-heavy file and every shared
      base-model edit. Change one coherent unit at a time. If an automated
      transformation touches multiple files, inspect its complete diff and
      execute the checkpoints immediately before making another edit.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Repair only the first complete
      traceback, then rerun collection to expose the next blocker. For a
      PydanticUserError requiring `skip_on_failure=True` on a deprecated
      post `root_validator`, do not make that compatibility argument the final
      solution: migrate the validator to a native v2 `model_validator` with
      its body and behavior preserved. Do not stop after resolving imports.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings to
      pydantic-settings, migrate settings Config to SettingsConfigDict or the
      appropriate native configuration, and replace Field regex with pattern.
      Preserve environment naming, case sensitivity, defaults, validation,
      cache behavior, and extras. Compile and instantiate the settings model
      with representative valid and invalid values.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Replace class Config with
      ConfigDict while preserving extra handling, enum values, frozen or
      assignment behavior, population rules, and arbitrary-type settings.
      Check each base class separately; a configuration warning is evidence
      that the migration is unfinished, not harmless output.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires inherited
      model-field overrides to remain annotated. Add the correct annotation
      when a subclass changes a default such as `segment_name`; do not remove
      all subclass declarations or turn shared model fields into ClassVar
      merely to suppress an error. Verify construction, serialization, schema,
      and registry lookup for representative subclasses.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Replace removed constraints
      and keywords with native v2 equivalents, including regex to pattern and
      list constraints where applicable. Move arbitrary Field extras into
      `json_schema_extra` while preserving exact metadata keys used by parser
      and renderer code. Use valid Python literals such as True, never JSON
      `true`. Compile and import every edited module immediately.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove `allow_reuse`; migrate
      shared decorator factories and reusable functions intentionally rather
      than shadowing Pydantic's `field_validator` name accidentally. Confirm
      whether each reusable callable receives a value, ValidationInfo, raw
      dictionary, or model instance. Exercise reuse in at least two consuming
      models before proceeding.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each v1 validator
      individually. Replace `values` access with `ValidationInfo.data` only
      where equivalent, account for field-order availability, and select
      `mode: before` only when validation must run on raw input. Preserve
      always/default behavior deliberately and use `check_fields=False` only
      when inheritance genuinely requires it. A blind `@validator` to
      `@field_validator` rename without signature conversion is prohibited.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Before converting model validators, classify every remaining
      `root_validator` by `pre` mode and body semantics. Record whether the
      function expects a dictionary, mutates raw input, validates an assembled
      model, or returns a replacement. Confirm the exact decorator and
      signature to use for each row. Do not use a global sed, regular
      expression, or script to assign the same mode or signature to all model
      validators.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert v1
      `root_validator(pre=True)` to `model_validator(mode='before')` only when
      the function operates on raw input and returns that input mapping.
      Convert post root validators to native after validators that normally
      receive `self`, read attributes, and return `self`; rewrite dictionary
      access without changing required checks or error messages. Use a wrap
      validator only when its semantics require it. Preserve classmethod
      placement according to Pydantic v2's supported signatures. Compile,
      import, and run the focused behavior test after each edited class or
      tightly related group.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search all production Python
      files for old decorators, old imports, missing new imports, malformed
      decorator calls, duplicate modes, stray colons, and decorators at the
      wrong indentation. Confirm every decorator name is imported in the file
      where it is used and every removed import is genuinely unused. A zero
      grep match is useful only after compilation and imports also pass.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__`,
      ModelField, shape constants, `.type_`, `.name`, and
      `field_info.extra` using `model_fields`, annotations, typing origins and
      arguments, field names from iteration, and `json_schema_extra`.
      Preserve declaration order and metadata-driven component behavior.
      Never guess at a removed attribute by probing unrelated APIs and then
      hard-code an approximation.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Preserve or implement the
      repository's `_is_list_field` public/test contract using the field
      annotation, `typing.get_origin`, and union handling as required.
      Recognize list fields through Optional or other supported wrappers
      without misclassifying scalar fields. Use this same helper in repeatable
      segment initialization where appropriate, and run the dedicated loop
      initializer tests.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 serialization and
      construction APIs with native v2 APIs where behavior remains equivalent.
      Preserve aliases, unset/none exclusions, enum handling, custom JSON
      encoding, field order, delimiters, component parsing, and X12 text
      output. Do not perform a repository-wide `.dict(` or `.json(` textual
      replacement without checking receiver types and arguments.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      After introspection and inherited-field changes, read and follow
      `verify-generated-registries` in
      `references/migration-implementation.md`. Check import-time loops that
      inspect model classes, read `segment_name` defaults, or construct lookup
      maps. Verify representative 4010 and 5010 entries and ensure conditional
      expressions introduced during migration have correct precedence and
      never register `None` accidentally.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile the complete production
      package, not only recently edited files. Treat syntax errors,
      indentation errors, malformed decorators, NameError-causing imports,
      and invalid Python literals as immediate blockers. Repair and rerun
      until compilation exits zero.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import shared models, settings,
      both versioned segment modules, transaction packages, and public helpers.
      Then run untruncated test collection, preserve its real status, and
      require a nonzero collected-test count. Resolve collection errors one
      complete traceback at a time. Exit code 5 from selecting a file with no
      tests is not a successful suite gate.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run settings, shared model,
      support, 4010 segment, 5010 segment, repeatable-segment, loop
      initializer, parser, serializer, registry, and transaction tests that
      cover changed surfaces. Use real test node IDs discovered from
      collection; a pytest error stating that a requested node was not found
      is not a passing focused test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For every migrated validator
      class, exercise at least one valid case and each meaningful invalid
      branch from its semantic snapshot. Compare accepted values, normalized
      output, raised exception type, relevant message, and serialized form.
      Import success does not demonstrate validator preservation.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate
      remains red. Always inspect the complete first traceback, make the
      smallest semantic repair, run compile/import/focused checkpoints, then
      rerun the broader failing command. Do not abandon the attempt because
      the migration is complex, summarize partial progress instead of
      editing, or end with an intended tool call written as prose.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Inspect the full diff
      for changed imports, decorators, signatures, bodies, indentation,
      booleans, metadata, annotations, and return statements. Revert the
      transformation when it cannot be proven semantics-preserving; do not
      stack further automated edits on an unaudited diff.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Require no pydantic.v1 imports,
      no deprecated validator decorators or arguments, no removed field or
      settings APIs, no malformed transformations, no JSON booleans in Python,
      no empty/no-op migrated bodies, and no accidental generated helper
      files or migration notes unless the repository requests them. Interpret
      grep exit code 1 as “no match” only for searches where that is expected.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the repository's exact canonical full-suite command without
      truncation and capture pytest's own exit code. Require nonempty
      collection and zero failures and errors. Save complete output to a file
      when necessary, but never infer success from a pipeline command whose
      final process was `head`, `tail`, `tee`, or `grep`.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Compare the final implementations with semantic snapshots and original
      Git bodies. Confirm validators still execute all branches, constructors
      still normalize repeatable values, parser and renderer output remains
      stable, settings still honor environment behavior, and registries still
      contain expected models.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect `git diff` and
      `git status`, distinguish user changes from migration changes, rerun
      compilation and the static audit if the diff changed after the green
      suite, and verify that no temporary scripts, plans, logs, caches, or
      compatibility shortcuts were added. Do not claim completion while any
      known gate remains red.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report the migrated surfaces, exact full-suite command, collected and
      passing test counts, runtime versions, and any intentional warnings.
      Never report “successfully migrated” after only imports, collection,
      focused tests, or a partial suite, and never substitute a progress
      summary for unfinished implementation.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, pin or downgrade to Pydantic 1, or introduce another compatibility namespace to make tests pass.
  - Never delete, empty, bypass, comment out, or replace a validator or function body with `pass`, an ellipsis, a no-op, or an unconditional return merely to make the module import.
  - Never blindly replace every `root_validator` with the same `model_validator` mode or signature; classify and migrate each validator according to its original semantics.
  - Never use repository-wide sed or regex transformations on validator decorators, signatures, or bodies without an immediate full-diff audit and compile/import/focused-test checkpoint.
  - Never add `skip_on_failure=True` and treat the resulting deprecated `root_validator` as the completed native v2 migration.
  - Never remove inherited field declarations, convert model fields to ClassVar, or weaken validation solely to silence Pydantic errors.
  - Never use JSON literals `true`, `false`, or `null` in Python source.
  - Never trust a pytest command piped through `head`, `tail`, `tee`, or `grep` unless pipefail or explicit status capture proves pytest itself exited zero.
  - Never treat a grep exit code, import success, compile success, empty collection, warning-only run, or one passing focused test as proof that the complete suite passes.
  - Never stop with a plan, progress report, “task completed” statement, unexecuted pseudo-tool call, or explanation that the migration is too complex while failures remain.
```