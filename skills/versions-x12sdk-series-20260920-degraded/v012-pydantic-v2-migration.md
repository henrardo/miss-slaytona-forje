---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 12
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from complete tracebacks and
  executable checkpoints rather than speculative bulk rewrites. Never satisfy
  the migration by importing from pydantic.v1 or another v1 compatibility
  namespace, and never make code import by deleting, emptying, bypassing, or
  replacing a function body with a no-op. Before editing, read
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
      Enter the verified repository root and run the repository's own exact
      full test command immediately, before editing. Before this step through
      repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, identify the VCS root, list the repository root, and inspect git
      status before constructing absolute paths or editing. When performing
      this step, follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, every requirement
      file, tox or nox configuration, CI workflows, pytest configuration,
      README development instructions, package exports, and any explicit
      post-migration requirements file before editing. When performing this
      step, follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set. When performing this step,
      follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces. When performing this
      step, follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Build a concrete in-memory or scratch checklist grouped into dependencies
      and settings, shared model configuration, inherited field overrides,
      field definitions and requiredness, reusable validator infrastructure,
      field validators, model validators, field introspection, public helpers,
      parsing, serialization, schemas, and tests. When performing this step,
      follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a
      speculative repository-wide rewrite. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models exist. Before this step through
      migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Inspect subclasses that override fields declared by a Pydantic base
      model. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
      When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where actually
      used: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. When performing this
      step, follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile all production Python files, then import settings, shared models,
      support utilities, parsers, both major-version segment modules, and
      representative transaction modules. Before this step through
      report-completion, read `references/validation-and-completion.md`.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant file or node after each changed subsystem:
      settings, support utilities, base models, parser, 4010 segments, 5010
      segments, loop initializers, transaction models, and serialization.
      When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases, or
      validation order, compare the v1 intent expressed by tests, fixtures,
      documentation, original code, and git history with v2 behavior instead
      of weakening tests. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Repeat the shortest failing import, collection target, or focused test
      until it passes, then expand scope one layer at a time. When performing
      this step, follow `references/validation-and-completion.md`.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement. When performing this
      step, follow `references/validation-and-completion.md`.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for pydantic.v1 and equivalent compatibility
      imports, BaseSettings imported from pydantic, v1 validator and
      root_validator decorators, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, removed Field regex and arbitrary extras,
      unannotated inherited field overrides, and obsolete parsing or
      serialization entry points. When performing this step, follow
      `references/validation-and-completion.md`. Re-read
      `references/guardrails-and-provenance.md` and reconcile every inventory
      item with the final source.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active. When performing this
      step, follow `references/validation-and-completion.md`.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted or bypassed logic. When performing this step,
      follow `references/validation-and-completion.md`. Re-read
      `references/guardrails-and-provenance.md` during this inspection.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the complete final diff once more. When
      performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact collection and full-suite
      commands, true process exit statuses, and final pass, fail, error, skip,
      xfail, and warning counts. When performing this step, follow
      `references/validation-and-completion.md` and re-read
      `references/guardrails-and-provenance.md`.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Re-pointing imports to pydantic.v1 or another Pydantic v1 compatibility namespace; this is explicitly rejected even when tests pass.
  - Emptying, deleting, bypassing, or replacing a validator or function body with pass, an unconditional return, or another no-op merely so the module imports; this is explicitly rejected even when tests pass.
```