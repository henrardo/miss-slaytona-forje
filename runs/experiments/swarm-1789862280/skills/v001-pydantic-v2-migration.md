---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to Pydantic v2, including dependency updates, BaseSettings, validators, model configuration, field metadata, serialization, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing import, schema, validation, parsing, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "92889e36"
---

```yaml
# Completeness check against the complete version-0 source:
# Mapped: its purpose is retained and strengthened below.
# Mapped: both trigger_when entries and both do_not_use_when entries survive.
# Mapped: all three original anti-patterns survive verbatim in substance.
# Mapped: establish-the-failure survives as the first execution step.
# Deliberate drop: the comments saying version 0 is empty and that no procedure
# has yet been distilled described the old scaffold, not migration behavior.
# They are obsolete now that trace 92889e36 has supplied migration evidence.
# Deliberate drop: "work from the traceback and codebase rather than from this
# file" is replaced by the stronger rule to use both repository evidence and
# this procedure, because the procedure now contains learned task knowledge.
# Mapped: the prohibition on pydantic.v1 shims and deleted behavior is repeated
# in purpose, gates, and anti_patterns rather than weakened or implied.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, and domain
  behavior. Use repository evidence and short test-driven repair loops until
  the repository's own complete test suite passes. Do not claim success based
  only on imports, static searches, or a partial suite. Never redirect imports
  to pydantic.v1, and never empty or bypass a function body merely so it
  imports or tests turn green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, __fields__, field_info.extra, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository is only consuming Pydantic models and contains no migration work

anti_patterns:
  - >
    Rewriting imports to pydantic.v1 so the old API keeps working. This can
    make most tests pass while avoiding the requested migration and is rejected
    even if the suite is otherwise green.
  - >
    Replacing a validator or any other function body with a bare return, pass,
    unconditional success, or equivalent no-op so the function still imports.
    A green suite does not justify deleting behavior.
  - Declaring the migration complete without running the repository's full test suite.
  - Spending most of the attempt browsing files or migration documentation before executing a baseline test.
  - Assuming setup.py exists instead of inspecting pyproject.toml, setup.cfg, requirements files, lockfiles, tox.ini, and CI configuration.
  - Blindly replacing decorators across large files with sed or regex without adapting signatures, modes, value access, and return values.
  - Converting every root_validator to model_validator(mode="after") while leaving a v1-style cls, values function body.
  - Treating successful imports as proof that model construction and validation behavior are correct.
  - Updating only the obvious central models while leaving transaction-specific modules, reusable validators, parser introspection, or settings code on v1 APIs.
  - Ignoring failed shell commands because grep returned 1 for no matches; distinguish an expected no-match result from an actual command error.
  - Relying on deprecation warnings as a migration strategy when the task requires native v2 APIs.
  - Changing requiredness, coercion, aliases, output formatting, or validation order without checking repository tests and fixtures.
  - Running broad automated edits without reviewing the diff and testing immediately afterward.
  - Ending with a summary of intended changes before any tests have passed.

steps:
  - name: establish-the-failure
    description: >
      Enter the repository root and immediately run the repository's own test
      command. Discover that command from pyproject.toml, tox.ini, noxfile,
      Makefile, CI, or project documentation; default to `python -m pytest -q`
      only when no project-specific command exists. Record the exact command,
      Pydantic and Python versions, collection count, pass/fail count, and first
      complete traceback. If collection fails, that collection error is the
      baseline. Do not postpone this step for a full source review.
    outputs:
      - {name: baseline, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect dependency and test configuration before editing. Read
      pyproject.toml and any requirements, lock, setup.cfg, tox, nox, CI, and
      migration-specific files. Determine the intended Pydantic v2 range and
      companion packages such as pydantic-settings. If the repository provides
      a post-migration requirements file, treat it as evidence and compare it
      with package metadata rather than guessing versions. Check git status and
      preserve unrelated user changes.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project using its declared development or test workflow so
      tests actually run against the target dependency set. Verify versions
      with a direct Python command after installation. Do not edit source
      against an unknown environment, and do not infer success merely because a
      globally installed Pydantic happens to be version 2.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search all production Python files, tests, examples that are executed,
      and dependency metadata for v1 interfaces. Include imports and uses of
      BaseSettings, validator, root_validator, allow_reuse, Config subclasses,
      __fields__, ModelField, field_info.extra, SHAPE_ constants, regex=,
      schema_extra, orm_mode, allow_population_by_field_name,
      validate_assignment, parse_obj, parse_raw, from_orm, dict(), json(),
      copy(), schema(), construct(), json_encoders, custom root models,
      GenericModel, constrained collection factories, and Optional annotations
      without defaults. Also locate every BaseModel subclass and every custom
      validator, including transaction/version-specific directories. Save file
      and line locations; do not rely on searches limited to import statements.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: classify-migration-work
    description: >
      Group the inventory into dependencies/settings, model configuration,
      fields and requiredness, field validators, model validators, reusable
      validators, field introspection, parsing, serialization, schemas, and
      tests. Identify shared base classes first because their behavior affects
      many generated or transaction-specific models. Mark high-risk behavior:
      validator ordering, access to sibling fields, default validation,
      list/repeating-field detection, custom metadata, aliases, date parsing,
      decimal constraints, and exact X12 or other domain serialization.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models are used. Import BaseSettings from
      pydantic_settings and replace settings Config classes with
      SettingsConfigDict or the supported v2 configuration form. Preserve
      environment prefixes, case sensitivity, env-file behavior, aliases, and
      defaults. Replace Field(regex=...) with Field(pattern=...). Run the
      smallest settings and import tests immediately.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Translate options semantically rather
      than by spelling alone: orm_mode becomes from_attributes,
      allow_population_by_field_name becomes populate_by_name or the
      version-appropriate validation settings, schema_extra becomes
      json_schema_extra, and validate_all/default behavior may require
      validate_default. Preserve assignment validation, extra handling,
      arbitrary types, string normalization, frozen/mutability behavior, alias
      generation, and enum handling. Watch for protected namespace conflicts
      and class attributes that v2 now interprets as model fields.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed or changed Field arguments and constrained types using
      native v2 forms accepted by the installed version. Preserve every length,
      numeric, decimal, collection, pattern, alias, and discriminator
      constraint. Move custom Field metadata into json_schema_extra and read it
      from FieldInfo.json_schema_extra. Audit requiredness explicitly:
      `Optional[T]` without a default is still required in v2, so use
      `Optional[T] = None` only where repository behavior says omission is
      allowed. Do not globally add None defaults. Check mutable defaults and
      default factories.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator with field_validator only after reading its
      body. Map pre=True to mode="before"; use mode="after" for post-parsing
      field checks. Remove allow_reuse because v2 handles reuse differently.
      Keep reusable validator assignment patterns valid, including validators
      imported from shared modules. Replace values/config/field parameters with
      ValidationInfo where needed and read previously validated sibling data
      from info.data. Account for field declaration order: info.data contains
      only fields already validated. Preserve always=True semantics using
      validate_default or an appropriate model validator rather than assuming a
      decorator rename is equivalent. Keep return values and all domain checks.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time. For mode="before", accept
      and return the raw input mapping or object and preserve wrapping,
      normalization, and cross-field preprocessing. For mode="after", normally
      accept the constructed model instance, inspect attributes, and return the
      instance. Do not leave a mode="after" validator with a v1-style
      `cls, values` dictionary contract. If assignment validation means the
      input can be an instance, handle that intentionally. Preserve error
      messages where tests or callers rely on them. A validator that checked
      paired fields, conditional requirements, totals, hierarchy, or domain
      invariants must continue to perform the check; never replace its body with
      a no-op.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level. Adapt
      code that expected v1 ModelField attributes: v2 entries are FieldInfo
      objects and do not expose v1 shape or field_info.extra APIs. Detect list
      or repeatable annotations using typing origins and resolved annotations,
      including Optional/Union wrappers, rather than importing removed
      SHAPE_LIST constants. Read custom flags from json_schema_extra. Update
      parser field-name enumeration and shared serialization code together so
      they agree on ordering and metadata.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 entry points with native equivalents where the codebase uses
      them: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Preserve aliases,
      exclude_none/exclude_unset behavior, JSON encoders or serializers,
      context, ordering, and exact domain output. Do not mechanically replace
      dict() calls that are ordinary Python dictionaries. For custom text
      serializers, compare byte-for-byte or string-for-string against fixtures.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile production files and import the package's central models,
      settings, parsers, and representative version-specific modules. Then run
      test collection. Fix the first traceback completely before continuing.
      Typical collection blockers include removed imports, invalid validator
      signatures, unannotated class attributes, obsolete Field arguments,
      duplicate validator names, and schema-generation failures. Repeat until
      collection succeeds. Successful central-model imports alone are not this
      gate.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant test file or node for each changed subsystem:
      settings, base models, parser, segments, loops, transaction models, and
      serialization. For a failure, read the entire traceback and inspect the
      affected model plus its base classes before editing. Make the smallest
      behavior-preserving fix, rerun the exact failing test, then rerun the
      subsystem. Avoid accumulating many speculative changes between tests.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion or missing fields, compare v1 intent with
      v2 behavior instead of weakening tests. Check required versus nullable
      fields, union selection, number-to-string coercion, strictness, enum
      values, date and decimal handling, validation of defaults, validator
      order, and error locations. Add explicit v2 configuration or validators
      only when repository fixtures demonstrate the old behavior is part of
      the contract.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially any files touched by batch
      replacement. Inspect every changed decorator with its function signature
      and body. Search for malformed decorator combinations, leftover imports,
      validators still named but no longer decorated, mode="after" functions
      treating a model as a dictionary, and bodies reduced to pass or a bare
      return. Revert unrelated formatting churn because it hides semantic
      mistakes.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for forbidden or stale migration surfaces.
      There must be no pydantic.v1 imports and no deliberate compatibility shim
      that routes native code back to v1. Resolve remaining validator,
      root_validator, BaseSettings-from-pydantic, __fields__, ModelField,
      field_info.extra, SHAPE_ constant, regex=, and obsolete Config uses unless
      a reviewed occurrence is demonstrably unrelated or supported v2 syntax.
      Treat grep exit 1 as "no matches" only after confirming stderr is empty.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, without stopping
      after the first success. Record collection count and complete pass, fail,
      error, skip, and warning counts. If anything fails, return to the smallest
      relevant repair loop, then rerun both the focused tests and full suite.
      Continue until the suite passes or an external blocker is proven with
      reproducible command output.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Before completion, inspect changed validators and serializers for deleted
      logic. Confirm no function was emptied, replaced with unconditional
      success, or bypassed. Exercise representative valid and invalid inputs for
      high-risk domain models, including cross-field validation and exact
      serialization. Confirm dependency metadata installs Pydantic v2 and the
      runtime test command used that installation.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and API categories migrated, dependency
      versions used, exact test command, final counts, and any remaining
      warnings or external blockers. State explicitly that no pydantic.v1 shim
      was introduced and no validator or function body was emptied to obtain
      the result. If the suite is not fully green, do not call the migration
      complete.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: migration-report, type: object}
```