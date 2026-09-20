---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 8
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from the repository's dependency
  contract, tests, fixtures, git history, installed API signatures, complete
  tracebacks, and complete diff. Repair in short, measurable loops until
  collection succeeds and the repository's exact full test suite passes.
  Never infer success from imports, static searches, warning reduction, test
  collection, a partial suite, or a command whose output was truncated or
  piped in a way that concealed its exit status. Never redirect imports to
  pydantic.v1 or an equivalent v1 compatibility shim; that is not a native-v2
  migration and is rejected even if every test passes. Never empty, bypass,
  stub, or replace a function or validator body with unconditional success,
  and never place the original logic after an unconditional return or raise;
  silently deleting behavior is rejected even if every test passes. Before
  editing, read `references/guardrails-and-provenance.md`; read it again during
  the static audit, behavior verification, and final report.

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
      Enter the verified repository root and run the repository's own full test
      command immediately, before editing. Before this step through
      repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, list the repository root, identify the VCS root, and inspect git
      status before constructing absolute paths or editing.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, all requirement
      files, tox/nox configuration, CI workflows, pytest configuration, README
      development instructions, package exports, and any post-migration
      requirements file before editing.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Build a concrete checklist grouped into dependencies and settings, shared
      model configuration, inherited field overrides, field definitions and
      requiredness, reusable validator infrastructure, field validators, model
      validators, field introspection, public helpers, parsing, serialization,
      schemas, and tests.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a speculative
      repository-wide rewrite.
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
      base classes before leaf models.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where actually
      used: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct.
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
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases, or
      validation order, compare the v1 intent expressed by tests, fixtures,
      docs, and original code with v2 behavior instead of weakening tests.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for pydantic.v1 and equivalent compatibility
      imports, BaseSettings imported from pydantic, v1 validator and
      root_validator decorators, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, removed Field regex and arbitrary extras,
      and obsolete parsing or serialization entry points.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted or bypassed logic.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the complete final diff once more.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact collection and full-suite
      commands, true process exit statuses, and final pass, fail, error, skip,
      xfail, and warning counts.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}
```