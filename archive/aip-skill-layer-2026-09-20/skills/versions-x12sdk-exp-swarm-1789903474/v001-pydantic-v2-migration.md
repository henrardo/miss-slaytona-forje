---
name: pydantic-v2-migration
description: Procedure distilled from graded repository migrations for moving Python codebases from Pydantic v1 to native Pydantic v2 APIs. Use when upgrading Pydantic dependencies, BaseSettings, validators, model configuration, field introspection, serialization, schemas, or Optional-field behavior while preserving application behavior and making the full test suite pass.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "a2038b8e"
---

```yaml
# Deliberate drop: the version-zero statement that this procedure contains no
# migration knowledge is obsolete now that graded attempt a2038b8e has been
# distilled. The original purpose, triggers, exclusions, anti-patterns, and
# establish-the-failure step are all retained and expanded below.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, settings, and domain
  behavior. Finish only when the repository's full test suite passes without
  importing pydantic.v1, suppressing validators, or deleting behavior.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, configuration, field, schema, or validator errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings from pydantic, root_validator, validator, class Config, __fields__, dict, or schema
  - Dependency metadata still pins pydantic below version 2

do_not_use_when:
  - The codebase is already on Pydantic v2 and its full suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration

anti_patterns:
  - Before editing, read references/anti-patterns.md and avoid every listed anti-pattern.

steps:
  - name: inspect-repository-and-task-contract
    description: >
      When starting the migration, read the matching step in
      references/repository-and-model-migration.md and follow it.
    outputs:
      - {name: repository-context, type: object}

  - name: establish-the-failure
    description: >
      When establishing the baseline, read the matching step in
      references/repository-and-model-migration.md and follow it.
    outputs:
      - {name: baseline-result, type: object}
      - {name: first-error, type: string}

  - name: inventory-pydantic-surface
    description: >
      When inventorying Pydantic usage, read the matching step in
      references/repository-and-model-migration.md and follow it.
    inputs:
      - {name: repository-context, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: update-dependency-metadata
    description: >
      When changing dependencies, read the matching step in
      references/repository-and-model-migration.md and follow it.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: dependency-changes, type: object}

  - name: migrate-settings-first
    description: >
      When migrating settings, read the matching step in
      references/repository-and-model-migration.md and follow it.
    inputs:
      - {name: first-error, type: string}
    outputs:
      - {name: settings-migration, type: object}

  - name: migrate-base-model-configuration
    description: >
      When migrating BaseModel configuration, read the matching step in
      references/repository-and-model-migration.md and follow it.
    outputs:
      - {name: model-configuration-changes, type: object}

  - name: preserve-v1-optional-field-semantics
    description: >
      When auditing nullable or optional fields, read the matching step in
      references/repository-and-model-migration.md and follow it.
    outputs:
      - {name: optional-field-audit, type: object}

  - name: migrate-field-validators
    description: >
      Before changing field validators, read the matching step in
      references/validator-migration.md and follow it.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: field-validator-changes, type: object}

  - name: migrate-reusable-validator-helpers
    description: >
      When reusable validator helpers exist, read the matching step in
      references/validator-migration.md and follow it.
    outputs:
      - {name: reusable-validator-changes, type: object}

  - name: classify-and-migrate-root-validators
    description: >
      Before changing root validators, read the matching step in
      references/validator-migration.md and follow it.
    outputs:
      - {name: model-validator-changes, type: object}

  - name: check-validator-method-inheritance
    description: >
      When models inherit validators, read the matching step in
      references/validator-migration.md and follow it.
    outputs:
      - {name: validator-inheritance-audit, type: object}

  - name: replace-removed-field-shape-apis
    description: >
      When removed field-shape APIs occur, read the matching step in
      references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: annotation-introspection-changes, type: object}

  - name: migrate-model-field-introspection
    description: >
      When model-field internals are inspected, read the matching step in
      references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: field-introspection-changes, type: object}

  - name: preserve-runtime-model-traversal
    description: >
      When serializers or tree walkers traverse models, read the matching step
      in references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: traversal-changes, type: object}

  - name: annotate-overridden-model-fields
    description: >
      When imports report unannotated field overrides, read the matching step
      in references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: field-override-changes, type: object}

  - name: migrate-serialization-and-schema-calls
    description: >
      When migrating serialization or schema calls, read the matching step in
      references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: serialization-changes, type: object}

  - name: migrate-parser-model-discovery
    description: >
      When parsers discover model classes or fields, read the matching step in
      references/fields-serialization-and-parsing.md and follow it.
    outputs:
      - {name: parser-discovery-changes, type: object}

  - name: audit-coercion-and-constraint-changes
    description: >
      When collection succeeds and runtime validation is being checked, read
      the matching step in references/validation-and-completion.md and follow it.
    outputs:
      - {name: coercion-audit, type: object}

  - name: run-import-and-collection-gates
    description: >
      After each migration layer, read the matching step in
      references/validation-and-completion.md and follow it.
    outputs:
      - {name: collection-gate-results, type: object}

  - name: inspect-every-mechanical-diff
    description: >
      After any automated replacement or migration tool, read the matching
      step in references/validation-and-completion.md and follow it.
    outputs:
      - {name: diff-review, type: object}

  - name: iterate-on-focused-failures
    description: >
      While failures remain, read the matching step in
      references/validation-and-completion.md and follow it.
    outputs:
      - {name: focused-test-results, type: object}

  - name: run-the-full-suite
    description: >
      After focused tests pass, read the matching step in
      references/validation-and-completion.md and follow it.
    outputs:
      - {name: full-suite-result, type: object}

  - name: perform-forbidden-shortcut-audit
    description: >
      Before completion, read the matching step in
      references/validation-and-completion.md and follow it.
    outputs:
      - {name: shortcut-audit, type: object}

  - name: verify-behavior-beyond-test-status
    description: >
      After the full suite passes, read the matching step in
      references/validation-and-completion.md and follow it.
    outputs:
      - {name: behavior-verification, type: object}

  - name: report-completion
    description: >
      When all completion gates pass, read the matching step in
      references/validation-and-completion.md and follow it.
    inputs:
      - {name: full-suite-result, type: object}
      - {name: shortcut-audit, type: object}
      - {name: behavior-verification, type: object}
    outputs:
      - {name: migration-report, type: object}
```