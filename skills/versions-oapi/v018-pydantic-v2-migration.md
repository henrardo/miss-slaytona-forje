---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 18
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, aliases, root models, type aliases, forward references,
  fixtures, and repository tests preserve intended behavior. Complete the
  migration without redirecting production imports to `pydantic.v1`; without
  deleting, emptying, bypassing, replacing with `pass`, or otherwise
  neutralizing validators or any other function bodies; without corrupting
  source through broad mechanical edits; and without stopping after searches,
  research, investigation, planning, an import check, compilation, test
  collection, focused tests, or a partially passing suite.

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
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state."
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
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed,
      follow "Act immediately on a const collection blocker" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Ensure the active test interpreter actually uses the intended Pydantic v2
      dependency set. Prefer a repository-provided migration requirements file
      or existing environment command. Recheck `sys.executable`,
      `pydantic.__version__`, and import location afterward. Update declared
      dependency constraints when required, but do not claim completion while a
      committed lockfile still resolves Pydantic v1 unless the repository
      explicitly treats that lockfile as out of scope.
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
      Follow "Inventory the complete Pydantic surface" in
      `references/safety-and-baseline.md`.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Follow "Form an executable slice plan" in
      `references/safety-and-baseline.md`.
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
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely."
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Follow "Migrate fields, annotations, and optionality" in
      `references/native-v2-conversions.md`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Follow "Migrate validators without erasing behavior" in
      `references/native-v2-conversions.md`.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Follow "Migrate schema, introspection, and special models" in
      `references/native-v2-conversions.md`.
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
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
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
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`.
    outputs:
      - name: migration-report
        type: object
```