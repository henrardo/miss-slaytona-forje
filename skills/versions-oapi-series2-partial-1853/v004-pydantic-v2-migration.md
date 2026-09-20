---
name: pydantic-v2-migration
description: Migrate Python codebases from Pydantic v1 to native Pydantic v2 APIs while preserving validation, parsing, serialization, schema, generated-code, configuration defaults, and application behavior. Use when upgrading Pydantic, resolving removed Field arguments such as const, converting model Config or validators, or fixing collection and runtime failures under Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 4
  derived_from_traces: "aa72dee9, 4acc4c33, b844e705, d13d710e"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, schema generation,
  configuration defaults, fixture construction, and generated-code behavior.
  Finish only when the repository's own tests pass, without redirecting imports
  to pydantic.v1, suppressing failures, or deleting function behavior merely to
  make imports or tests succeed.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, model construction, validator,
    serialization, schema, or removed-argument errors after a Pydantic v2 upgrade
  - Test collection fails before any tests run because a Pydantic v1 model is
    imported under Pydantic v2
  - A dependency change installs Pydantic v2 while application models and
    generated schemas still use Pydantic v1 APIs
  - Collection succeeds but fixtures or ordinary constructors such as Config()
    fail because v1 implicit defaults became required fields in Pydantic v2
  - Hundreds of tests pass under Pydantic v2 but the remaining failures cluster
    around shared models, default construction, aliases, or serialization

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The requested outcome explicitly requires retaining Pydantic v1 rather than
    performing a native v2 migration

anti_patterns:
  - >
    Rewriting imports to pydantic.v1 so the old API keeps working. This can make
    nearly the entire suite pass while avoiding the requested migration, and the
    grader rejects it even if tests are green.
  - >
    Replacing a validator or any other function body with a bare return, pass,
    constant result, unconditional passthrough, or no-op so the function still
    imports. The grader rejects behavior deletion even if the suite becomes
    green.
  - Declaring the migration complete without running the repository's full suite.
  - >
    Treating a successful import or successful collection as proof that ordinary
    model construction works. Pydantic v2 can import a model successfully and
    then reject Config() because Optional fields without defaults are required.
  - >
    Using a high passing-test count, such as 310 passing tests, as evidence that
    the migration is complete while any failures or setup errors remain.
  - >
    Guessing from a truncated ValidationError. Re-run the failing test with a
    full traceback and inspect errors() or the complete message to identify
    every missing field and its model before editing.
  - >
    Adding = None to every Optional field mechanically. Nullable and optional
    are separate concepts in v2; some nullable fields are intentionally required.
  - >
    Starting with a repository-wide regex rewrite before fixing and validating
    the first import blocker. Broad substitutions can create malformed
    ConfigDict calls and make the original failure harder to isolate.
  - >
    Researching every symbol before acting on an explicit runtime error. Use the
    installed v2 exception, runtime introspection, and official documentation;
    spend research time only where semantics are uncertain.
  - >
    Trusting a search result or migration summary without checking the installed
    Pydantic v2 runtime and official documentation. For example, StrictInt and
    StrictStr remain importable in supported Pydantic v2 releases even though
    some summaries incorrectly claim they were removed.
  - >
    Piping pytest through head or tail without pipefail or checking pytest's real
    exit status. The pipeline may report success while collection has failed.
  - >
    Fixing only the first occurrence of a repeated removed API. Package
    initialization can expose the next identical blocker immediately, wasting
    an iteration that an exhaustive search would have prevented.
  - >
    Repeatedly reverting an entire migrated directory after one malformed file.
    This discards correct edits and causes the same initial blocker to recur.
  - >
    Generating ad hoc migration scripts before understanding the exact source
    forms they will rewrite. If automation is justified, test it on a clean diff
    and a representative file, inspect its patch, and stop if it damages syntax.
  - >
    Treating successful import of one leaf model as sufficient validation.
    Package initialization may import every model, and failures can occur later
    in the import graph.
  - >
    Changing defaults, aliases, accepted input types, extra-field behavior, or
    serialization output merely because the v2 spelling differs.
  - >
    Ignoring templates, fixtures, snapshots, examples, or code generators that
    emit Pydantic APIs. Regenerated output can reintroduce v1 syntax.
  - >
    Muting deprecation warnings globally instead of replacing deprecated APIs.
  - >
    Editing dependency metadata without confirming that the test interpreter is
    actually running the intended Pydantic major version.
  - >
    Counting previously passing tests as evidence of completion when the current
    invocation cannot construct shared fixtures, collect the expected suite, or
    return a zero exit status.

steps:
  - name: preserve-repository-state
    description: >
      Before beginning, read references/foundations.md and follow it through
      create-migration-plan.
    outputs:
      - name: repository-state
        type: object

  - name: establish-runtime
    description: Follow the loaded foundations procedure.
    outputs:
      - name: runtime-facts
        type: object

  - name: establish-the-failure
    description: Follow the loaded foundations procedure.
    outputs:
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: verify-the-first-traceback
    description: Follow the loaded foundations procedure.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: first-blocker
        type: object

  - name: inventory-pydantic-surface
    description: Follow the loaded foundations procedure.
    outputs:
      - name: migration-inventory
        type: list[object]

  - name: inventory-v1-implicit-defaults
    description: Follow the loaded foundations procedure.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: implicit-default-inventory
        type: list[object]

  - name: inspect-contract-tests
    description: Follow the loaded foundations procedure.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: behavior-contract
        type: object

  - name: create-migration-plan
    description: Follow the loaded foundations procedure.
    inputs:
      - name: migration-inventory
        type: list[object]
      - name: behavior-contract
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: remove-const-blockers
    description: >
      When beginning blocker removal, read references/early-blockers.md and
      follow it through cluster-runtime-failures.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: const-migration
        type: object

  - name: validate-const-contract
    description: Follow the loaded early-blockers procedure.
    inputs:
      - name: const-migration
        type: object
    outputs:
      - name: const-contract-result
        type: object

  - name: validate-first-import-gate
    description: Follow the loaded early-blockers procedure.
    inputs:
      - name: const-contract-result
        type: object
    outputs:
      - name: first-import-gate
        type: object

  - name: restore-foundational-construction
    description: Follow the loaded early-blockers procedure.
    inputs:
      - name: implicit-default-inventory
        type: list[object]
      - name: behavior-contract
        type: object
    outputs:
      - name: foundational-construction-result
        type: object

  - name: cluster-runtime-failures
    description: Follow the loaded early-blockers procedure.
    inputs:
      - name: foundational-construction-result
        type: object
    outputs:
      - name: failure-clusters
        type: list[object]

  - name: migrate-model-configuration
    description: >
      When beginning API and model migration, read
      references/migration-categories.md and follow it through
      migrate-dataclasses-and-settings.
    outputs:
      - name: config-migration
        type: object

  - name: check-configuration-batches
    description: Follow the loaded migration-categories procedure.
    inputs:
      - name: config-migration
        type: object
    outputs:
      - name: config-check
        type: object

  - name: migrate-field-keywords
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: field-keyword-migration
        type: object

  - name: preserve-required-and-nullable-semantics
    description: Follow the loaded migration-categories procedure.
    inputs:
      - name: behavior-contract
        type: object
      - name: implicit-default-inventory
        type: list[object]
    outputs:
      - name: field-presence-migration
        type: object

  - name: preserve-type-and-union-behavior
    description: Follow the loaded migration-categories procedure.
    inputs:
      - name: behavior-contract
        type: object
    outputs:
      - name: type-semantics-migration
        type: object

  - name: migrate-field-validators
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: field-validator-migration
        type: object

  - name: migrate-root-validators
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: root-validator-migration
        type: object

  - name: migrate-custom-validation-hooks
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: custom-hook-migration
        type: object

  - name: migrate-root-models
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: root-model-migration
        type: object

  - name: migrate-model-apis
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: model-api-migration
        type: object

  - name: migrate-errors-and-exception-handling
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: error-api-migration
        type: object

  - name: preserve-serialization-and-schema-output
    description: Follow the loaded migration-categories procedure.
    inputs:
      - name: behavior-contract
        type: object
    outputs:
      - name: serialization-migration
        type: object

  - name: rebuild-forward-references
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: forward-reference-migration
        type: object

  - name: migrate-dataclasses-and-settings
    description: Follow the loaded migration-categories procedure.
    outputs:
      - name: integration-migration
        type: object

  - name: update-generators-and-templates
    description: >
      When beginning generated-code, dependency, and final validation work, read
      references/validation-and-completion.md and follow it through
      final-clean-run.
    outputs:
      - name: generator-migration
        type: object

  - name: update-dependencies
    description: Follow the loaded validation-and-completion procedure.
    outputs:
      - name: dependency-migration
        type: object

  - name: run-static-and-import-checks
    description: Follow the loaded validation-and-completion procedure.
    outputs:
      - name: static-check-result
        type: object

  - name: run-collection-gate
    description: Follow the loaded validation-and-completion procedure.
    outputs:
      - name: collection-result
        type: object

  - name: run-fixture-construction-gate
    description: Follow the loaded validation-and-completion procedure.
    inputs:
      - name: collection-result
        type: object
    outputs:
      - name: fixture-construction-result
        type: object

  - name: run-focused-tests
    description: Follow the loaded validation-and-completion procedure.
    outputs:
      - name: focused-test-result
        type: object

  - name: run-full-suite
    description: Follow the loaded validation-and-completion procedure.
    outputs:
      - name: full-suite-result
        type: object

  - name: audit-for-forbidden-shortcuts
    description: Follow the loaded validation-and-completion procedure.
    inputs:
      - name: full-suite-result
        type: object
    outputs:
      - name: shortcut-audit
        type: object

  - name: audit-inventory-completeness
    description: Follow the loaded validation-and-completion procedure.
    inputs:
      - name: migration-inventory
        type: list[object]
      - name: implicit-default-inventory
        type: list[object]
      - name: behavior-contract
        type: object
    outputs:
      - name: inventory-audit
        type: object

  - name: final-clean-run
    description: Follow the loaded validation-and-completion procedure.
    inputs:
      - name: shortcut-audit
        type: object
      - name: inventory-audit
        type: object
    outputs:
      - name: migration-evidence
        type: object
```