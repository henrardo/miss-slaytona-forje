---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 20
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, aliases, root models, type aliases, forward references,
  fixtures, and repository tests preserve intended behavior. Complete the
  migration without redirecting production imports to `pydantic.v1`; without
  deleting, emptying, bypassing, replacing with `pass`, or otherwise
  neutralizing validators or any other function bodies; without weakening
  production behavior or rewriting tests merely to accept regressions; without
  corrupting source through broad mechanical edits; and without stopping after
  searches, research, investigation, planning, an import check, compilation,
  test collection, focused tests, or a partially passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models
  - Models import successfully under Pydantic v2 but constructors, fixtures, schemas, aliases, or behavioral tests fail
  - Most tests pass after an upgrade but a shared model, fixture, forward reference, type alias, root model, or optionality regression still causes failures
  - The installed Pydantic version and declared dependency or lockfile disagree

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning any migration step, read `references/migration-guardrails.md` and avoid every anti-pattern listed there throughout the migration.

steps:
  - name: establish-repository-root-and-state
    description: >
      Before inspecting or editing the repository, read
      `references/safety-and-baseline.md` and follow "Establish repository root
      and state."
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree."
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Before choosing test or quality commands, read
      `references/safety-and-baseline.md` and follow "Identify authoritative
      project commands."
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Before editing in response to failures, read
      `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline."
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed, read
      `references/safety-and-baseline.md` and follow "Act immediately on a const
      collection blocker."
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Before selecting syntax, dependencies, or compatibility behavior, read
      `references/safety-and-baseline.md` and follow "Inspect project
      constraints."
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Before validating the migration under Pydantic v2, read
      `references/safety-and-baseline.md` and follow "Synchronize the target
      environment."
    inputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]
    outputs:
      - name: target-environment
        type: object

  - name: inventory-the-complete-pydantic-surface
    description: >
      Before forming the migration plan, read
      `references/safety-and-baseline.md` and follow "Inventory the complete
      Pydantic surface."
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Before changing model semantics, read
      `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior."
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Before beginning conversion edits, read
      `references/safety-and-baseline.md` and follow "Form an executable slice
      plan."
    inputs:
      - name: first-error
        type: string
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: migrate-model-configuration-safely
    description: >
      When migrating model configuration, read
      `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely."
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      When migrating fields, annotations, defaults, or optionality, read
      `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality."
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      When migrating validators, read
      `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior."
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      When migrating parsing, validation entry points, or serialization, read
      `references/native-v2-conversions.md` and follow "Migrate validation entry
      points and serialization."
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      When migrating schemas, introspection, forward references, aliases, or
      special models, read `references/native-v2-conversions.md` and follow
      "Migrate schema, introspection, and special models."
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After every coherent edit, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice."
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite."
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences."
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      After collection succeeds, read
      `references/validation-and-completion.md` and follow "Repeat inventory
      after collection succeeds."
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Before running the final complete suite, read
      `references/validation-and-completion.md` and follow "Inspect and review
      the diff."
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      After focused validation and diff review, read
      `references/validation-and-completion.md` and follow "Run the complete
      test suite."
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, read
      `references/validation-and-completion.md` and follow "Run project quality
      gates."
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Before declaring completion, read
      `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification."
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Before reporting completion, read
      `references/validation-and-completion.md` and follow "Audit provenance and
      procedure completeness."
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      At the end of the migration, read
      `references/validation-and-completion.md` and follow "Report completion
      with evidence."
    outputs:
      - name: migration-report
        type: object
```