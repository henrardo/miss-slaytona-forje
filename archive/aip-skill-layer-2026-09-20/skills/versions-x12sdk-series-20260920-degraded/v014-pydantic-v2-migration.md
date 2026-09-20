---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 14
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from complete tracebacks and
  executable checkpoints rather than speculative bulk rewrites. Never satisfy
  the migration by importing from pydantic.v1 or another v1 compatibility
  namespace, and never make code import by deleting, emptying, bypassing, or
  replacing a function body with a no-op. Do not declare completion until
  production code compiles, test collection succeeds, focused behavior tests
  pass, the exact untruncated full-suite command exits successfully, and the
  final diff passes a behavior-preservation audit. Before editing, read
  `references/guardrails-and-provenance.md`; read it again during the static
  audit, behavior verification, and final report.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
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
      Before and while performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "establish-the-failure" exactly.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "confirm-location-and-working-tree" exactly.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "inspect-repository-contract" exactly.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "make-runtime-match-target" exactly.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "inventory-v1-surface" exactly.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "inventory-public-and-test-contracts" exactly.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      When performing this step, read
      `references/baseline-inventory-and-planning.md` and follow
      "classify-migration-work" exactly.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Before changing code, read
      `references/baseline-inventory-and-planning.md` and follow
      "create-small-edit-checkpoints" exactly.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      When repairing the first collection blocker, read
      `references/baseline-inventory-and-planning.md` and follow
      "repair-first-collection-blocker" exactly.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Before this step through migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`; for this step, follow
      "update-dependencies-and-settings" exactly.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-shared-model-configuration" exactly.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-inherited-field-overrides" exactly.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-field-definitions" exactly.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-reusable-validator-infrastructure" exactly.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-field-validators" exactly.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-model-validators" exactly.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "repair-field-introspection" exactly.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "preserve-list-field-helper" exactly.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      When performing this step, read
      `references/native-v2-api-migration.md` and follow
      "migrate-parsing-and-serialization" exactly.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Before broad imports, read `references/validation-and-completion.md` and
      follow "compile-production-code" exactly.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Before this step through report-completion, read
      `references/validation-and-completion.md`; for this step, follow
      "run-import-and-collection-gate" exactly.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "run-focused-behavior-tests" exactly.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "compare-validation-semantics" exactly.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "repair-iteratively-to-green" exactly.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "audit-automated-edits" exactly.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      During this step, re-read `references/guardrails-and-provenance.md`, then
      read `references/validation-and-completion.md` and follow
      "run-static-migration-audit" exactly.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "run-full-suite" exactly.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      During this step, re-read `references/guardrails-and-provenance.md`, then
      read `references/validation-and-completion.md` and follow
      "verify-behavior-preservation" exactly.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      When performing this step, read
      `references/validation-and-completion.md` and follow
      "final-diff-and-status-gate" exactly.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      During this step, read `references/validation-and-completion.md` and
      follow "report-completion" exactly, then re-read
      `references/guardrails-and-provenance.md` before reporting.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before editing and during the static audit, behavior verification, and final report, read `references/guardrails-and-provenance.md` and avoid every listed anti-pattern.
```