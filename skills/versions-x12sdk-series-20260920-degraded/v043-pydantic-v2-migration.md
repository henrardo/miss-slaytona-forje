---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 43
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
    description: When executing this step, read `references/repository-assessment.md` section `establish-the-failure` and follow it.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: When executing this step, read `references/repository-assessment.md` section `confirm-location-and-working-tree` and follow it.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: When executing this step, read `references/repository-assessment.md` section `inspect-repository-contract` and follow it.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: When executing this step, read `references/repository-assessment.md` section `make-runtime-match-target` and follow it.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: When executing this step, read `references/repository-assessment.md` section `inventory-v1-surface` and follow it.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: When executing this step, read `references/repository-assessment.md` section `inventory-public-and-test-contracts` and follow it.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: When executing this step, read `references/repository-assessment.md` section `preserve-original-semantics` and follow it.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: When executing this step, read `references/repository-assessment.md` section `build-migration-ledger` and follow it.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: When executing this step, read `references/repository-assessment.md` section `classify-migration-work` and follow it.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: When executing this step, read `references/verification-and-repair.md` section `create-small-edit-checkpoints` and follow it.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: When executing this step, read `references/migration-implementation.md` section `repair-first-collection-blocker` and follow it.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: When executing this step, read `references/migration-implementation.md` section `update-dependencies-and-settings` and follow it.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: When executing this step, read `references/migration-implementation.md` section `migrate-shared-model-configuration` and follow it.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: When executing this step, read `references/migration-implementation.md` section `migrate-inherited-field-overrides` and follow it.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: When executing this step, read `references/migration-implementation.md` section `migrate-field-definitions` and follow it.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: When executing this step, read `references/migration-implementation.md` section `migrate-reusable-validator-infrastructure` and follow it.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: When executing this step, read `references/migration-implementation.md` section `migrate-field-validators` and follow it.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: When executing this step, read `references/migration-implementation.md` section `classify-every-model-validator` and follow it.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: When executing this step, read `references/migration-implementation.md` section `migrate-model-validators` and follow it.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: When executing this step, read `references/migration-implementation.md` section `close-validator-import-decorator-gap` and follow it.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: When executing this step, read `references/migration-implementation.md` section `repair-field-introspection` and follow it.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: When executing this step, read `references/migration-implementation.md` section `preserve-list-field-helper` and follow it.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: When executing this step, read `references/migration-implementation.md` section `migrate-parsing-and-serialization` and follow it.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: When executing this step, read `references/migration-implementation.md` section `verify-generated-registries` and follow it.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: When executing this step, read `references/verification-and-repair.md` section `compile-production-code` and follow it.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: When executing this step, read `references/verification-and-repair.md` section `run-import-and-collection-gate` and follow it.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: When executing this step, read `references/verification-and-repair.md` section `run-focused-behavior-tests` and follow it.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: When executing this step, read `references/verification-and-repair.md` section `compare-validation-semantics` and follow it.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: When executing this step, read `references/verification-and-repair.md` section `repair-iteratively-to-green` and follow it.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: When executing this step, read `references/verification-and-repair.md` section `audit-automated-edits` and follow it.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: When executing this step, read `references/prohibited-patterns.md`, then read `references/verification-and-repair.md` section `run-static-migration-audit` and follow it.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: When executing this step, read `references/verification-and-repair.md` section `run-full-suite` and follow it.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: When executing this step, read `references/verification-and-repair.md` section `verify-behavior-preservation` and follow it.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: When executing this step, re-read `references/prohibited-patterns.md`, then read `references/verification-and-repair.md` section `final-diff-and-status-gate` and follow it.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: When executing this step, read `references/verification-and-repair.md` section `report-completion` and follow it.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
```