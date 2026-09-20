---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 28
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving intended validation, construction, requiredness, defaults,
  aliases, parsing, serialization, generated schemas, recursive models,
  fixtures, public APIs, dependency metadata, and repository behavior.
  Complete the migration without redirecting production imports to
  `pydantic.v1`; without deleting, emptying, bypassing, replacing with `pass`,
  or otherwise neutralizing validators or any other function bodies merely so
  imports or tests succeed; without weakening production behavior or rewriting
  tests to accept regressions; without corrupting source through broad
  mechanical edits; and without stopping after research, inventory, planning,
  an import check, compilation, collection, focused tests, or a partially
  passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, field, validator, or configuration errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, methods, symbols, or semantics
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted, duplicated, truncated, or syntactically malformed models
  - Models import under Pydantic v2 but constructors, fixtures, aliases, schemas, serialization, or behavioral tests fail
  - Most tests pass but shared defaults, optionality, forward references, recursive aliases, root models, or exported types still fail
  - The installed Pydantic version disagrees with dependency declarations, requirements files, or lockfiles
  - A suite reaches hundreds of passing tests but still has clustered constructor, fixture, schema, or recursive-model failures

do_not_use_when:
  - The codebase already uses native Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task upgrades a dependency unrelated to Pydantic
  - The requested outcome is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning, read `references/migration-guardrails.md` and enforce every guardrail throughout the migration

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
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree."
    inputs:
      - name: repository-state
        type: object
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands."
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline."
    inputs:
      - name: project-commands
        type: object
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
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints."
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment."
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
      Read `references/safety-and-baseline.md` and follow "Inventory the
      complete Pydantic surface."
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior."
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan."
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
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality."
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: audit-requiredness-and-constructor-contracts
    description: >
      Explicitly audit every `Optional[T]` field and every constructor used by
      fixtures or public callers. In Pydantic v2, `Optional[T]` without a
      default accepts `None` but remains required. Add `= None` only where the
      v1 model or caller contract allowed omission. Reproduce failing
      constructors directly, especially shared fixtures such as a project
      `Config()` created with no arguments. Do not paper over missing-field
      errors in tests; restore the production model's intended defaults.
    inputs:
      - name: behavior-map
        type: object
      - name: field-migration-results
        type: object
    outputs:
      - name: requiredness-audit
        type: object

  - name: audit-default-values-and-instance-isolation
    description: >
      Review list, dict, set, nested-model, and configuration defaults. Use
      `Field(default_factory=list)`, `Field(default_factory=dict)`, or an
      equivalent factory when each model instance must receive independent
      state. Preserve immutable scalar defaults. Add focused tests or direct
      checks proving that two instances do not share mutable state and that
      zero-argument construction still works where previously supported.
    inputs:
      - name: behavior-map
        type: object
      - name: requiredness-audit
        type: object
    outputs:
      - name: default-audit
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior."
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization."
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models."
    inputs:
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: rebuild-forward-references-with-the-correct-namespace
    description: >
      Replace `update_forward_refs` with native-v2 rebuilding only where
      necessary. Determine the complete namespace needed by string annotations
      and recursive models. Rebuild actual `BaseModel` subclasses after all
      referenced symbols are imported, supplying an explicit namespace when
      module globals are insufficient. Do not call `model_rebuild` on typing
      aliases such as callback or mapping aliases. Validate package-level
      imports and representative recursive model construction after each
      change.
    inputs:
      - name: behavior-map
        type: object
      - name: specialist-migration-results
        type: object
    outputs:
      - name: forward-reference-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      During every edit step, read `references/native-v2-conversions.md` and
      follow "Run a syntax and import gate after every edit slice."
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
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

  - name: triage-a-partially-passing-suite
    description: >
      If hundreds of tests pass but the suite still fails, do not restart the
      migration or declare near-success. Compare failing and passing clusters.
      First inspect shared fixtures and constructors for v2 requiredness
      changes, especially `Optional` fields lacking `= None`; then inspect
      mutable defaults, alias population, recursive model rebuilding, exported
      type aliases, mapping-versus-`RootModel` behavior, and serialization
      shape. Use the first complete traceback from each distinct cluster and
      make one narrow production fix at a time.
    inputs:
      - name: post-collection-triage
        type: object
      - name: requiredness-audit
        type: object
      - name: default-audit
        type: object
    outputs:
      - name: partial-suite-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences."
    inputs:
      - name: focused-test-results
        type: list[object]
      - name: post-collection-triage
        type: object
      - name: partial-suite-triage
        type: object
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
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff."
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite."
    inputs:
      - name: project-commands
        type: object
      - name: diff-review
        type: object
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the full suite passes, read
      `references/validation-and-completion.md` and follow "Run project quality
      gates."
    inputs:
      - name: project-commands
        type: object
      - name: full-suite-result
        type: object
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Read `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification."
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness."
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence."
    inputs:
      - name: full-suite-result
        type: object
      - name: quality-gate-results
        type: list[object]
      - name: native-v2-verification
        type: object
      - name: provenance-audit
        type: object
    outputs:
      - name: migration-report
        type: object
```