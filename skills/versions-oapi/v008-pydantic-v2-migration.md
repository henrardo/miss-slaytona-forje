---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 8
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, validation, parsing, serialization, generated schemas,
  and repository tests preserve intended behavior. Complete the migration
  without redirecting imports to `pydantic.v1`; without deleting, emptying,
  bypassing, or neutralizing validators or other function bodies; without
  corrupting source through broad mechanical edits; and without stopping after
  searches, investigation, planning, an import check, collection, or a partially
  passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - >
    Before beginning any migration work, read
    `references/safety-and-baseline.md` for the mandatory anti-patterns and
    exact instructions governing repository setup, recovery, baseline testing,
    project constraints, initial blocker handling, inventory, behavior mapping,
    and executable planning.

steps:
  - name: establish-repository-root-and-state
    description: >
      Before editing, read `references/safety-and-baseline.md` and follow
      "Establish repository root and state."
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      When selecting repository commands, follow "Identify authoritative
      project commands" in `references/safety-and-baseline.md`.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      When establishing the baseline, follow "Establish the unpiped baseline"
      in `references/safety-and-baseline.md`.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `const` was removed, follow "Act
      immediately on a const collection blocker" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      When determining the compatibility target and dependency changes, follow
      "Inspect project constraints" in `references/safety-and-baseline.md`.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      When inventorying v1 APIs and affected code, follow "Inventory the
      complete Pydantic surface" in `references/safety-and-baseline.md`.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      After inventorying affected code, follow "Inspect model relationships and
      public behavior" in `references/safety-and-baseline.md`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Before beginning conversion slices, follow "Form an executable slice plan"
      in `references/safety-and-baseline.md`.
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
      When converting model configuration, read
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
      When converting fields, annotations, or optionality, follow "Migrate
      fields, annotations, and optionality" in
      `references/native-v2-conversions.md`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Before converting any validator, follow "Migrate validators without
      erasing behavior" in `references/native-v2-conversions.md`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      When converting parsing, validation entry points, or serialization,
      follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      When converting schema generation, introspection, forward references, or
      specialist model types, follow "Migrate schema, introspection, and special
      models" in `references/native-v2-conversions.md`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After every coherent edit, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice."
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Once the suite collects, follow "Repeat inventory after collection
      succeeds" in `references/validation-and-completion.md`.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Before full-suite completion testing, follow "Inspect and review the diff"
      in `references/validation-and-completion.md`.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      When running completion testing, follow "Run the complete test suite" in
      `references/validation-and-completion.md`.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Before claiming completion, follow "Perform final native-v2 verification"
      in `references/validation-and-completion.md`.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      When auditing an accepted source procedure, follow "Audit provenance and
      procedure completeness" in `references/validation-and-completion.md`.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      At completion or when reporting unresolved work, follow "Report completion
      with evidence" in `references/validation-and-completion.md`.
    outputs:
      - name: migration-report
        type: object
```