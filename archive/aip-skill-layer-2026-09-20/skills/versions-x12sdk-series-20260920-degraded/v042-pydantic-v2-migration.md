---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 42
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, generated registries, and domain behavior. Work from complete
  tracebacks, original function bodies, repository tests, and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task
  by importing from pydantic.v1 or another v1 compatibility namespace. Never
  make code import by deleting, emptying, bypassing, commenting out, or
  replacing a function body with a no-op. Preserve every validator's
  substantive checks, mutations, errors, ordering assumptions, and return
  behavior. Treat Python source as Python: use True and False, never JSON
  literals true and false. Do not confuse import success, successful
  collection, a zero-looking pipeline status, one green focused test,
  warnings-only output, or a written migration summary with completion.
  Completion requires production code to compile, nonempty test collection
  to succeed, focused behavior tests to pass, the exact untruncated full-suite
  command to exit zero, and the final diff to pass static and
  behavior-preservation audits. Capture real command exit codes without
  piping pytest through head, tail, tee, or grep unless pipefail is enabled
  and the pytest status is explicitly preserved. Convert validators according
  to their individual signatures and semantics: a v1 pre root validator
  receives raw data, while a v2 after model validator normally receives and
  returns the model instance. Never perform a blind repository-wide decorator,
  signature, import, metadata, constraint, or model-method substitution.
  Never use line-number edits against files that are changing. After each
  edited file, compile it, import its affected module, and run the smallest
  relevant test before editing another validator-heavy file. Repair the first
  complete traceback before broadening scope. Continue repairing until the
  full suite passes; never stop with a progress summary, migration plan,
  partial import success, collection errors, known failing tests, an
  unexecuted proposed tool call, a user-visible fake tool call, or a statement
  that the remaining work is too complex.

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
      full-suite command without truncating or masking its status. Save the
      complete first traceback, command, exit code, collected-test count, and
      pass/fail/error counts. If collection fails, record that as the baseline;
      do not report zero passing tests as evidence that tests ran. Avoid
      `pytest | head`, `pytest | tail`, and `pytest | tee`; if diagnostic
      filtering is necessary, write output to a file while preserving pytest's
      exit status separately.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the absolute repository path once and reuse it to avoid mistyped paths.
      Capture `git status --short` and the initial diff. Distinguish user
      changes from changes made during this attempt. Never discard, overwrite,
      or restore pre-existing work without permission. If earlier failed
      migration edits are present, inspect their diff and either repair them
      deliberately or, only when authorized, restore a known-good baseline.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect pyproject.toml, lock and
      requirements files, package layout, test configuration, CI commands,
      supported Python versions, public imports, changelog notes, migration
      fixtures, and any post-migration dependency file. Do not assume setup.py
      or requirements.txt exists; list the repository before reading expected
      paths. Treat repository-specific tests and documented behavior as the
      contract.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Confirm the interpreter, Pydantic,
      pydantic-core, pydantic-settings, pytest, and package-under-test import
      locations. Ensure commands use the intended environment and local source
      tree. Update dependency metadata consistently rather than relying only on
      packages already installed in the harness.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search production code, tests,
      plugins, generated modules, and transaction-specific subpackages for
      BaseSettings, Config, validator, root_validator, allow_reuse, each_item,
      always, pre, values, field, config, skip_on_failure, __fields__,
      ModelField, field_info.extra, SHAPE_LIST, regex, min_items, max_items,
      parse_obj, parse_raw, from_orm, copy, dict, json, json_encoders,
      arbitrary Field extras, and unannotated field overrides. Record exact
      files and counts. Search decorator uses separately from imports so
      missing-import and stale-import defects cannot hide.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Record public model classes,
      settings classes, parser and reader APIs, serialization methods,
      exported helper functions, CLI output, schema metadata, registry keys,
      exception behavior, and tests that import internal compatibility helpers.
      In particular, preserve helpers such as `_is_list_field` when tests or
      users import them; a migration is not allowed to silently remove a
      public or tested symbol.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read and follow `preserve-original-semantics` in
      `references/repository-assessment.md`. Before changing a validator-heavy
      file, capture its original version from the working tree or git and map
      every validator to its fields, mode, inputs, mutations, errors, and
      return value. Preserve representative valid and invalid examples.
      Retain original function bodies as the source of truth even when a prior
      attempt produced malformed decorators or signatures. Never infer the
      intended body from an already-corrupted bulk rewrite.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Create one row per migration site
      with file, symbol, v1 construct, intended v2 construct, semantic risks,
      representative tests, current status, and verification command. Include
      dependency, settings, field constraints, model configuration,
      validators, introspection, parsing, serialization, helper, registry, and
      inherited-field work. Update the ledger after each verified edit.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Separate mechanical low-risk
      changes from semantic high-risk changes. Treat validator conversion,
      inherited field overrides, default validation, metadata access, generic
      type introspection, custom serialization, and generated registry logic
      as semantic work requiring individual review. Order repairs by executable
      blockers, then shared infrastructure, then leaf models.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Use semantic edits anchored by
      exact surrounding text, not mutable line numbers. For each file, define
      a checkpoint of syntax compilation, affected-module import, the smallest
      relevant test, and a diff review. Do not modify both large versioned
      segment modules simultaneously until one version's conversion pattern
      is proven.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Repair only the first complete
      import or collection traceback, then rerun collection to expose the next
      blocker. Compile the edited file before importing it. Syntax and
      indentation errors take precedence over Pydantic errors. If a prior edit
      left a bare expression such as `parse_x12_date`, a truncated assignment,
      duplicated decorator call, missing comma, or wrong indentation, restore
      the complete original statement before attempting semantic migration.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings to
      pydantic-settings, add the dependency to all authoritative dependency
      surfaces, convert settings configuration to SettingsConfigDict or the
      repository's validated equivalent, and rename Field regex to pattern.
      Preserve environment case sensitivity, prefixes, aliases, defaults, and
      loading behavior. Instantiate settings with representative environment
      variables before proceeding.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Convert inner Config classes to
      ConfigDict while preserving frozen or mutability behavior, extra policy,
      enum value handling, assignment validation, aliases, arbitrary types,
      population rules, JSON encoding, and default validation. Do not add a
      shared configuration option merely to silence a warning; prove its
      behavioral equivalence with tests.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires inherited
      model fields overridden by subclasses to remain annotated. Repair
      assignments such as `segment_name = ...` as typed field overrides, using
      the inherited annotation or an equivalent explicit annotation. Do not
      delete every subclass override and do not convert model fields to
      ClassVar merely to make imports succeed: segment names and discriminators
      often drive serialization, parsing, and registry generation. Search all
      model subclasses for unannotated overrides and test representative
      registry keys and serialized segment names.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Convert regex to pattern,
      constr regex to pattern, and list constraints to their v2 forms while
      preserving exact boundary behavior. Move arbitrary Field extras such as
      `is_component` into `json_schema_extra` using valid Python values such as
      `{"is_component": True}`. Never emit lowercase JSON booleans in Python.
      Confirm Optional/default semantics because `Optional[T]` without a
      default can remain required in Pydantic v2. Test minimum, maximum,
      pattern, decimal, and requiredness boundaries.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove v1 allow_reuse rather
      than passing it to v2 decorators. Preserve directly assigned reusable
      validators and shared validator functions. Do not shadow Pydantic's
      `field_validator` import with a project-level partial of the same name;
      use a distinct compatibility helper name if one is genuinely needed.
      Verify each shared validator receives the value and ValidationInfo shape
      expected by every call site.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md` for each v1 field validator.
      Convert decorators and signatures individually. Replace v1 `values` with
      ValidationInfo and `info.data` only when the validator depends on
      previously validated fields. Preserve pre behavior with mode="before";
      account for declaration-order availability in `info.data`. Decide
      explicitly how `always=True` and default validation map to v2
      `validate_default` behavior. Preserve multi-field and reusable validator
      semantics. Add `@classmethod` only in the supported decorator order.
      Compile, import, and run a valid and invalid example after each logical
      validator group.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read and follow `classify-every-model-validator` in
      `references/migration-implementation.md` before converting any root
      validator. Classify each as raw-input normalization, cross-field
      validation, mutation, aggregate validation, reusable function
      assignment, or mixed behavior. Record whether it must run before or
      after field validation, whether it may see dicts or instances, and which
      return type is required. Do not infer the mode from a global search and
      replace.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md` for each classified root
      validator. Convert v1 `pre=True` root validators to
      `@model_validator(mode="before")` functions that accept and return raw
      input. Convert post root validators to after validators that normally
      accept `self`, inspect attributes, and return `self`; do not mechanically
      retain `cls, values` dict logic in an after validator. Where preserving
      dict-oriented shared validator logic is safer, deliberately use a before
      validator and document why. Preserve mutations, all raised errors, and
      field-order behavior. Never leave `@model_validator` without a mode,
      duplicate calls such as `(mode="before")(mode="before")`, invalid
      `pre=True`, or unsupported `allow_reuse`.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search every production Python
      file for v1 decorator uses, v2 decorator uses, and their imports.
      Confirm no decorator is undefined, no stale v1 import remains, no import
      was inserted into the middle of another import block, and no specialized
      transaction module was missed. Compile every matched file. Import
      top-level and version-specific segment modules independently.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace __fields__ with
      model_fields and migrate ModelField assumptions to FieldInfo semantics.
      Read annotations with typing.get_origin and typing.get_args rather than
      removed shape constants. Read custom metadata from
      `json_schema_extra or {}` rather than `field_info.extra`. Treat fields
      retrieved from a class as named `(name, field)` pairs because v2
      FieldInfo objects do not carry every v1 attribute such as `.name` or
      `.type_`. Test component metadata, field ordering, nested model
      detection, and list detection.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Implement or preserve the
      tested `_is_list_field` helper using the field annotation and
      `typing.get_origin`, including Optional or Union wrappers where present.
      Use the helper both in repeatable-segment normalization and wherever
      tests import it. Do not replace removed SHAPE_LIST with a magic numeric
      constant. Verify a list field, optional list field, scalar field, and
      nested model field before proceeding.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Move dict/json/parse_obj and
      related calls to native v2 methods only where the receiver is proven to
      be a Pydantic model. Preserve exclusions, aliases, enum handling,
      custom delimiters, decimal/date output, nested structures, and CLI JSON
      output. Do not blindly replace `.dict(` or `.json(` across the
      repository because ordinary mappings and unrelated objects may use those
      names. Validate representative parse-serialize-parse round trips and X12
      output byte-for-byte.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read and follow `verify-generated-registries` in
      `references/migration-implementation.md`. Audit module-level loops that
      discover model classes and build segment registries. Replace
      `__fields__["segment_name"].default` with safe model_fields access while
      preserving enum-to-key conversion. Guard absent fields without silently
      registering `None`. Test known segment lookups from every supported
      version and ensure registry size and keys remain plausible.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Run compileall over production
      code and compile every recently edited large file directly. Repair
      indentation, malformed imports, dangling expressions, truncated
      assignments, duplicate decorators, syntax-invalid booleans, and
      accidental comments before any Pydantic debugging. Compilation success
      is required but is not completion.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import settings, shared models,
      support code, parser code, each versioned segment module, and affected
      transaction packages. Then run the exact untruncated collection command
      and require exit zero with a nonzero collected-test count. An import
      smoke test cannot substitute for collection.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run settings, shared model,
      support, segment, repeatable-segment, loop initializer, parser,
      serializer, and registry tests before the full suite. Use actual test
      node IDs obtained from collection; a "test not found" error is not a
      passing test. Preserve each command's real exit code.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. Compare representative valid
      and invalid inputs against semantic snapshots. Confirm requiredness,
      default validation, cross-field checks, mutations, exception classes,
      useful error locations, repeatable-segment wrapping, component metadata,
      and output formatting. A validator that no longer runs is a regression
      even if imports and positive-path tests pass.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate is
      red. Work on the first complete traceback, make the smallest
      semantics-preserving edit, then rerun compile, import, collection or the
      smallest failing test as appropriate. Do not accumulate speculative
      edits across unrelated files. After every two or three repairs, rerun a
      broader focused group to detect regressions.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Review the complete
      diff and search for malformed imports, invalid indentation, lowercase
      booleans, missing annotations, commented-out assignments, emptied
      bodies, decorator duplication, changed signatures, and replacements in
      unrelated APIs. Prefer an AST- or CST-aware transformation for repeated
      syntax. If using sed or regex, limit it to proven identical forms,
      inspect every changed hunk, compile immediately, and revert or repair
      unexpected matches before continuing.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Require no pydantic.v1 imports,
      no stale BaseSettings import from pydantic, no v1 validator decorators,
      no unsupported allow_reuse, no removed SHAPE_LIST or ModelField
      dependency, no stale field_info.extra access, no syntax-invalid JSON
      booleans, no malformed model_validator forms, no empty/no-op migrated
      function bodies, and no unexplained v1 method use. Treat findings as
      failures, not warnings.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the repository's exact canonical full-suite command without
      `head`, `tail`, `grep`, or a pipeline that masks status. Require exit
      zero, nonzero collected tests, and no collection errors. Record the
      command, exit code, pass count, skip count, warning count, and duration.
      If it fails, return to iterative repair rather than summarizing progress.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck public imports, settings behavior, schemas, registry contents,
      parsing, X12 serialization, JSON/CLI output, validator error behavior,
      helper availability, and representative round trips. Compare against
      original semantic snapshots and the migration ledger. Green tests do
      not authorize deleting behavior that was not covered.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect `git diff --check`,
      the complete diff, and final status. Confirm only intended files changed;
      no temporary scripts, migration ledgers, logs, generated caches, or
      unrequested planning documents remain; dependency files agree; no user
      changes were lost; and every ledger row is verified. Rerun compile,
      static audit, and the full suite after any final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report concise changed areas, the exact full-suite command and result,
      focused behavior checks, and any remaining non-blocking warnings. Never
      claim success while collection or tests fail, while work is merely
      planned, or after ending a turn without executing a proposed edit.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never re-point production imports to pydantic.v1 or any Pydantic v1 compatibility namespace.
  - Never delete, empty, comment out, bypass, or replace a function or validator body with a no-op merely to make imports or tests progress.
  - Never bulk-replace validator decorators or signatures without classifying each validator's mode, inputs, mutations, and return type.
  - Never run repository-wide substitutions for `.dict`, `.json`, imports, Field metadata, inherited annotations, or booleans without proving every match and auditing every hunk.
  - Never use lowercase `true`, `false`, or `null` in Python source.
  - Never remove all inherited `segment_name` or discriminator overrides; preserve them as annotated model fields when domain behavior depends on them.
  - Never use mutable line-number edits in large changing files; anchor edits by exact semantic context.
  - Never leave malformed decorators such as bare `@model_validator`, `pre=True`, duplicated mode calls, or unsupported `allow_reuse`.
  - Never treat `pytest | head`, `pytest | tail`, `pytest | tee`, or a shell pipeline's final zero status as proof pytest passed.
  - Never treat compilation, one successful import, collection success, one focused test, or warnings-only output as full completion.
  - Never stop after writing a plan, ledger, summary, or proposed tool call while executable gates remain red.
  - Never create fake tool-call text in a response instead of invoking the available tool.
  - Never abandon the migration as too complex after making partial edits; revert unsafe edits when authorized or continue the first-traceback repair loop to a verified green suite.
```