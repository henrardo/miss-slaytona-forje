---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 75
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
    description: Read `references/repository-assessment.md` section `establish-the-failure` and follow it.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: Read `references/repository-assessment.md` section `confirm-location-and-working-tree` and follow it.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: Read `references/core-rules.md` section `execution-discipline` and follow it.
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
    description: Read `references/repository-assessment.md` section `make-runtime-match-target` and follow it.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: Read `references/repository-assessment.md` section `inventory-v1-surface` and follow it.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: Read `references/repository-assessment.md` section `inventory-public-and-test-contracts` and follow it.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: Read `references/repository-assessment.md` section `preserve-original-semantics` and follow it.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: Read `references/repository-assessment.md` section `build-migration-ledger` and follow it.
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
    description: Read `references/verification-and-repair.md` section `create-small-edit-checkpoints` and follow it.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: Before new migration edits, read `references/verification-and-repair.md` section `recover-malformed-partial-migration` and follow it.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: Read `references/migration-implementation.md` section `repair-first-collection-blocker` and follow it.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: Read `references/migration-implementation.md` section `update-dependencies-and-settings` and follow it.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: Read `references/migration-implementation.md` section `migrate-shared-model-configuration` and follow it.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: Read `references/migration-implementation.md` section `migrate-inherited-field-overrides` and follow it.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: Read `references/migration-implementation.md` section `migrate-field-definitions` and follow it.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: Read `references/migration-implementation.md` section `migrate-reusable-validator-infrastructure` and follow it.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: Read `references/migration-implementation.md` section `migrate-field-validators` and follow it.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: Read `references/migration-implementation.md` section `classify-every-model-validator` and follow it.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: Read `references/migration-implementation.md` section `migrate-model-validators` and follow it.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: Read `references/migration-implementation.md` section `close-validator-import-decorator-gap` and follow it.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: Read `references/migration-implementation.md` section `repair-field-introspection` and follow it.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: Read `references/migration-implementation.md` section `preserve-list-field-helper` and follow it.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: Read `references/migration-implementation.md` section `migrate-parsing-and-serialization` and follow it.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: Read `references/migration-implementation.md` section `verify-generated-registries` and follow it.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: Read `references/verification-and-repair.md` section `compile-production-code` and follow it.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: Read `references/verification-and-repair.md` section `run-import-and-collection-gate` and follow it.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: Read `references/verification-and-repair.md` section `run-focused-behavior-tests` and follow it.
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
    description: Read `references/verification-and-repair.md` section `repair-iteratively-to-green` and follow it.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: Read `references/verification-and-repair.md` section `audit-automated-edits` and follow it.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: Read `references/prohibited-patterns.md`, then read `references/verification-and-repair.md` section `run-static-migration-audit` and follow it.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: Read `references/verification-and-repair.md` section `run-full-suite` and follow it.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: Read `references/verification-and-repair.md` section `verify-behavior-preservation` and follow it.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: Re-read `references/prohibited-patterns.md`, then read `references/verification-and-repair.md` section `final-diff-and-status-gate` and follow it.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: Read `references/verification-and-repair.md` section `report-completion` and follow it.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
```