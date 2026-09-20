---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 74
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Preserve public APIs, validator bodies, validation timing, field requiredness,
  parser behavior, serializer behavior, settings behavior, helper functions,
  generated registries, and error behavior. Before editing and throughout the
  migration, read and enforce `references/core-rules.md`. Work from complete
  tracebacks and small verified edits rather than speculative bulk replacement.
  Treat each successful checkpoint as evidence, not completion. Never claim
  completion from successful imports, compilation, collection, a focused subset,
  a custom smoke script, a zero exit status produced by piping test output
  through `head`, `tail`, `tee`, or another command, or a textual summary that
  says tests passed without the repository's real command actually exiting zero.
  Never redirect production imports to `pydantic.v1`, and never empty, stub,
  bypass, or replace a function body merely to make imports or tests proceed.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, empty validator bodies, or broad search-and-replace damage
  - The first collection failure says that BaseSettings moved to pydantic-settings
  - Tests exercise repeatable list fields, inherited discriminator fields, generated segment registries, X12 serialization, or other behavior coupled to Pydantic field introspection
  - When deciding whether a partial or failed migration matches this procedure, read `references/core-rules.md` section `additional-triggers`.

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native v2 migration
  - The requested change is merely to suppress Pydantic deprecation warnings without preserving and testing behavior

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real command
      without truncating or piping away its status. Capture the exact command,
      true exit code, collection count, pass count, failure count, and first
      complete traceback. If collection stops at `BaseSettings`, record that as
      the first blocker instead of repeatedly rerunning the same unchanged
      command.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      path once and reuse it; do not guess similar paths. Record tracked,
      modified, staged, and untracked files. Never use `git checkout`, `git
      restore`, `git reset`, or equivalent to discard pre-existing or successful
      migration work unless the user explicitly authorizes it.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      Read `references/core-rules.md` section `execution-discipline` and follow
      it. Maintain one migration ledger and advance from the current blocker;
      do not restart assessment, rewrite the same migration plan, or produce a
      completion summary while the real suite is red. After each edit, inspect
      the changed lines and run the smallest meaningful gate.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: At this step, read `references/repository-assessment.md` section `inspect-repository-contract` and follow it.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify Pydantic and
      pydantic-settings versions immediately before tests. Avoid reinstalling
      broad extras in a way that silently downgrades Pydantic; after every
      dependency installation, print the effective versions again.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section `inventory-v1-surface`
      and follow it. Search production code, tests, package metadata, generated
      modules, and transaction-specific subpackages. Record every occurrence;
      do not assume top-level modules represent the entire migration surface.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Treat helpers imported
      by tests or downstream modules, including underscore-prefixed helpers such
      as `_is_list_field`, as public migration contracts unless evidence proves
      otherwise.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Retrieve original validator
      bodies, signatures, decorator modes, field declarations, and serialization
      behavior from the clean baseline or version control before converting
      malformed partial edits. Never infer a missing body from its name alone.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. For each item, record file,
      symbol, v1 construct, intended v2 construct, semantic risk, tests covering
      it, and status. Update this ledger after every verified checkpoint rather
      than creating new summary or plan files in the repository.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: At this step, read `references/repository-assessment.md` section `classify-migration-work` and follow it.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Prefer one coherent edit
      class at a time: settings, shared models, one validator family, one
      introspection path, or one registry. Do not combine repository-wide
      decorator, signature, optional-default, metadata, and serialization
      rewrites into one checkpoint.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read `references/verification-and-repair.md`
      section `recover-malformed-partial-migration` and follow it. Search for
      malformed forms such as duplicated mode arguments, dangling parentheses,
      invalid Python booleans, damaged imports, wrong indentation, decorators
      without imports, imports without uses, and partially rewritten
      signatures. Restore each damaged construct from its original semantics,
      then compile before proceeding.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the first complete
      traceback, then rerun collection to expose the next blocker. For the common
      `BaseSettings` failure, move the import to `pydantic_settings`, preserve
      settings configuration, replace removed `Field(regex=...)` with
      `Field(pattern=...)`, verify the settings class imports and instantiates,
      and immediately rerun collection.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update authoritative
      dependency metadata, not only the active environment. Use native
      `pydantic>=2,<3` and the compatible `pydantic-settings` package. Preserve
      environment-variable names, case sensitivity, defaults, caching, and
      settings instantiation behavior.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert each v1
      `Config` option deliberately to `ConfigDict`; do not carry removed keys
      such as `allow_mutation`. Preserve frozen/hashability, enum value handling,
      extra-field policy, aliases, population behavior, assignment validation,
      and arbitrary-type behavior.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. When Pydantic reports
      that a base field was overridden by a non-annotated attribute, add the
      correct annotation to the subclass override; do not delete discriminator
      fields or remove all subclass overrides. Search the entire model tree for
      equivalent declarations and verify generated registries still see their
      defaults.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed constraint
      keywords such as `regex` to `pattern` and move arbitrary field metadata
      into `json_schema_extra`. Preserve Python syntax and use `True`, not JSON
      `true`. Do not globally add `None` defaults to every `Optional` annotation:
      v1 optionality and default behavior must be recovered per field and tested.
      Do not weaken constraints merely to make models instantiate.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `allow_reuse` wrappers rather than shadowing Pydantic's
      `field_validator` with a recursive partial. Preserve the callable helpers
      and their external imports. Determine whether each helper should remain a
      plain validation function or become a decorated validator at its use site.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert signatures deliberately:
      replace v1 `values`/`field` access with `ValidationInfo` only where needed,
      preserve before/after timing, and keep every validation body intact.
      Validator functions reused through assignment may require explicit mode
      and decorator application; verify them with valid and invalid fixtures.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every
      `root_validator`, record whether it consumes raw input mappings or
      validated model state, whether it mutates data, and what it returns.
      Never determine `mode` through a repository-wide textual replacement.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. A `mode="before"` validator
      receives and returns input data; a `mode="after"` validator normally
      receives and returns `self`. Rewrite each signature and body consistently
      while preserving all checks and mutations. Do not leave v1 dict-oriented
      bodies behind an after-validator, and never empty or replace a validator
      body with an unconditional return to make imports succeed.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search all Python
      files for decorator names and imports in both directions. Every
      `field_validator`, `model_validator`, and `ValidationInfo` use must have
      the correct import; stale `validator`, `root_validator`, and
      `allow_reuse` imports or decorators must be gone from production code.
      Compile immediately after closing the gap.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      `model_fields` and inspect v2 `FieldInfo` annotations, defaults, and
      `json_schema_extra`. Do not translate v1 attributes mechanically:
      `shape`, `type_`, `field_info.extra`, and `SHAPE_LIST` require semantic
      replacements using `typing.get_origin`, `typing.get_args`, annotations,
      and v2 field metadata.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or restore the public
      `_is_list_field` helper in the module from which tests and users import it.
      It must recognize list annotations, including optional/union-wrapped list
      annotations where required by the contract. Use it consistently in
      repeatable-segment wrapping and verify that a single dict becomes a
      one-item list without changing already-list input.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace deprecated
      Pydantic APIs with native v2 APIs only after comparing output behavior.
      Preserve aliases, enum rendering, exclusion flags, delimiters, nested
      model traversal, JSON encoders, date and decimal handling, parser field
      ordering, and X12 output. Do not use method-name replacement as proof that
      serialized values remain equivalent.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect registry-building code
      that reads class fields or discriminator defaults at import time. Replace
      v1 introspection with `model_fields` without changing keys, ordering, or
      model membership. Verify representative 4010 and 5010 lookups, not merely
      module import.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile all production Python
      files. Treat malformed decorators, import-list damage, indentation errors,
      invalid booleans, and accidental substitutions outside Pydantic code as
      failed checkpoints that must be repaired before collection.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Run representative imports,
      then the repository's complete collection command without truncation.
      Record the true command status. Import success is only a diagnostic;
      collection must complete with the expected test count before focused
      behavior work proceeds.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Prioritize settings, shared
      models, validators, repeatable segments, inherited fields, parsing,
      serialization, and registries. Capture full failing tracebacks; do not
      pipe pytest through `head` or `tail`, because the pipeline can report the
      consumer's zero status instead of pytest's failure.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: At this step, read `references/verification-and-repair.md` section `compare-validation-semantics` and follow it.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work on the first complete
      failure, make the smallest semantic repair, rerun the narrow failing test,
      and then rerun the broader gate. Continue until green; do not stop because
      dozens of tests pass while collection errors or remaining failures exist.
      Do not end the turn with a plan, summary, or “task completed” statement
      while any required gate is red.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. If any script, regex, or `sed`
      command changed multiple files, inspect every changed hunk. Specifically
      check imports, decorators, signatures, indentation, string literals,
      regular expressions, optional defaults, annotations, and unrelated code.
      Revert only the bad hunk, never the whole working tree.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. The audit must reject
      production `pydantic.v1` imports, stale v1 decorators and settings imports,
      malformed decorators, empty or stubbed validation bodies, deprecated
      introspection that still executes, and unreviewed broad replacements.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact repository test command directly and untruncated.
      If logging is needed, preserve pytest's status explicitly or inspect it
      before proceeding. Record command, exit code, collected count, passed
      count, failed count, error count, skipped count, and warning count. The
      only passing result is the real command exiting zero.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Compare validation timing,
      requiredness, defaults, errors, parsing, serialization, helper imports,
      and registry behavior against semantic snapshots and tests. A greener suite
      caused by weakened constraints, globally optional fields, deleted
      validators, or bypassed code is migration failure.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Confirm the latest full-suite
      result exited zero, the diff contains only intentional migration changes,
      no temporary plans or summary artifacts were added, and no successful
      work was discarded. If any condition fails, return to iterative repair.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section `report-completion`
      and follow it. Report the exact successful command and counts, key
      behavior-preserving changes, and any remaining warnings only after the
      final gate passes. Never report success based on imports, compilation,
      collection, focused tests, a custom script, or an earlier run.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`, even temporarily as the proposed migration solution.
  - Never empty, stub, bypass, comment out, or replace a function or validator body with an unconditional return merely to make imports, collection, or tests pass.
  - Never perform blind repository-wide decorator replacement; classify validator timing and signatures first.
  - Never use broad `sed` or regex edits without inspecting every changed hunk and compiling immediately.
  - Never globally add `None` defaults to all `Optional` fields or otherwise weaken requiredness to reduce failures.
  - Never delete inherited discriminator overrides to silence annotation errors; annotate and preserve them.
  - Never remove public or test-imported helpers such as `_is_list_field`; migrate their implementation and preserve their import path.
  - Never overwrite Pydantic's `field_validator` name with a self-referential partial or retain `allow_reuse=True`.
  - Never treat import success, compilation, collection, focused tests, or a hand-written smoke script as full-suite success.
  - Never pipe the authoritative test command through `head`, `tail`, or an unchecked `tee` pipeline and then trust the resulting zero status.
  - Never repeatedly restart assessment or write new migration summaries instead of fixing the next recorded blocker.
  - Never use `git checkout`, `git restore`, or `git reset` to discard accumulated migration work or pre-existing user changes without explicit authorization.
  - Never reinstall dependencies without rechecking the effective Pydantic and pydantic-settings versions afterward.
  - Never declare completion while any collection error, failed test, malformed decorator, stale v1 production import, or unverified broad edit remains.
```