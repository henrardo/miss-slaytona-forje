---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 9
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
  silently deleting behavior is rejected even if every test passes. Preserve
  each validator's original conditions, exceptions, mutations, ordering
  assumptions, and return behavior. Prefer one verified semantic conversion
  at a time over repository-wide textual rewrites. Before editing, read
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
      full test command immediately, before editing. Run it directly and retain
      the complete output and true process status; do not pipe pytest through
      head, tail, grep, or another command whose zero status can mask pytest's
      failure. If output must be captured, use a method that preserves the
      original status, such as a file redirection or a pipe with pipefail.
      Record collection errors, test counts, warnings, runtime executable, and
      command. Do not treat zero collected or zero passed tests as progress.
      Before this step through repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, identify the VCS root, list the repository root, and inspect git
      status before constructing absolute paths or editing. Use the confirmed
      root consistently rather than repeatedly typing a guessed path. Record
      pre-existing modifications and untracked files so they are not mistaken
      for migration work or deleted. Inspect the current diff because an
      interrupted prior migration may have left partially converted files,
      temporary scripts, malformed replacements, or generated plans. Never
      assume the working tree is pristine merely because imports fail.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, every requirement
      file, tox or nox configuration, CI workflows, pytest configuration,
      README development instructions, package exports, and any explicit
      post-migration requirements file before editing. Determine the canonical
      install and test commands, supported Python range, intended Pydantic v2
      range, whether pydantic-settings is expected, and whether measured
      dependency pins are supplied. Check filenames with directory listings
      before reading them; a missing setup.py or requirements.txt is evidence
      about project layout, not a reason to guess or stop.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set. Confirm the Python,
      Pydantic, pydantic-core, pydantic-settings, and pytest versions from the
      same interpreter that runs tests. Do not edit against one environment
      while testing another. When an installed API signature is uncertain,
      inspect that exact installed version or consult its matching v2
      documentation rather than relying on memory.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces. Include imports of
      BaseSettings, validator, root_validator, ModelField, SHAPE_LIST, and
      pydantic.v1; Config subclasses; allow_reuse; pre, always, each_item, and
      skip_on_failure arguments; values, field, and config validator
      parameters; __fields__, field_info.extra, shape, sub_fields, and
      outer_type_; Field regex and arbitrary extra keywords; constrained
      types; parse_obj, parse_raw, from_orm, dict, json, copy, schema, and
      construct. Search decorator syntax separately for bare
      @root_validator and parameterized forms. Save a complete file-and-line
      inventory rather than relying on a short head sample.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`. Record expected constructor behavior,
      missing-versus-null behavior, exact validation errors where asserted,
      field ordering, aliases, schema metadata, X12 or other custom serialized
      output, parser behavior, and custom methods. Treat tests added for the
      migration as requirements, not obstacles to weaken. A helper absent from
      production but imported by tests must be restored with its exact name and
      intended v2 behavior.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Build a concrete checklist grouped into dependencies and settings,
      shared model configuration, inherited field overrides, field definitions
      and requiredness, reusable validator infrastructure, field validators,
      model validators, field introspection, public helpers, parsing,
      serialization, schemas, and tests. For each validator record its old
      mode, fields, signature, dependencies, complete body, and expected
      behavior before changing it. Mark high-fan-out base classes and support
      utilities for early repair. Mark mechanically similar files as separate
      checklist entries; similarity does not prove identical semantics.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a
      speculative repository-wide rewrite. Inspect the failing source region,
      its base class, relevant tests, and the original version from git before
      editing. If a prior automated edit damaged a function, recover its full
      original body from the pre-edit diff or git history and port that logic;
      do not make the import pass by returning the input unchanged. Apply the
      smallest coherent fix, rerun the exact failing import or collection
      command without truncation, and record the next blocker. Continue this
      error-driven loop while preserving the migration checklist.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models exist. Import BaseSettings and
      SettingsConfigDict from pydantic_settings, replace settings Config with
      model_config, and preserve env files, prefixes, case sensitivity, extra
      handling, and aliases. Replace removed Field(regex=...) with
      Field(pattern=...) where the installed v2 API requires it. Verify settings
      imports and instantiate representative settings with defaults and
      environment overrides. Do not use pydantic.v1 as a shortcut. Before this
      step through migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Preserve behavior for extra fields,
      assignment validation, enum values, aliases, arbitrary types, string
      normalization, ORM attribute loading, defaults, and population by name.
      Verify that each option uses its v2 name and belongs on the correct base
      class. Do not add broad permissive configuration merely to suppress
      errors. Rerun imports and focused base-model tests after each shared
      configuration change because it affects every descendant.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version. Move custom schema metadata such as
      is_component into json_schema_extra and use valid Python values such as
      True, not JSON tokens such as true. Preserve constraints and domain
      types; use Annotated forms where appropriate rather than silently
      widening types. Audit Optional annotations carefully because in v2
      Optional[T] without a default remains required; add = None only when the
      original contract allowed omission. Annotate every inherited field
      override, for example `segment_name: X12SegmentName = ...`; Pydantic v2
      rejects a non-annotated attribute that overrides a base model field.
      Search all model files for this pattern instead of fixing only the first
      reported class. Validate representative accepted, rejected, omitted,
      null, boundary, enum, decimal, and pattern values.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites. Replace v1 validator partials with native
      field_validator registration and remove unsupported allow_reuse rather
      than recreating it through a compatibility layer. Preserve mode,
      default-validation behavior, and reusable function signatures. Confirm
      whether the decorator receives a plain callable, classmethod, or already
      decorated function in the installed version. Test at least one model per
      shared date, time, numeric, identifier, and hierarchy validator so an
      import-only success cannot conceal validators that no longer execute.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body. Map pre=True to mode="before"; use ValidationInfo for info.data,
      field_name, context, or config instead of v1 values, field, and config
      parameters. Account for field-order dependence because info.data contains
      only fields already validated. Replace always=True only after deciding
      whether validate_default or a model validator is required. Rework
      each_item behavior explicitly rather than dropping it. Keep all original
      branches, errors, normalizations, and return values, and prove execution
      with valid and invalid examples. Never convert a validator to an
      unconditional `return value`, leave its logic after that return, or
      delete it simply because imports then succeed.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
      A mode="before" validator generally receives raw input and returns raw
      input; preserve dictionary mutations and pre-validation conditions. A
      mode="after" validator generally receives self, reads or updates
      attributes, and returns self; translate every values.get, membership
      test, loop, mutation, and error branch rather than merely changing the
      signature. Consider assignment-validation paths where input may already
      be an instance. Do not perform blind regex body conversion across large
      files: it can create early returns, unreachable original code, undefined
      values variables, or validators that silently do nothing. After each
      conversion, inspect the entire function and test both its passing and
      failing branches.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection. Use annotation, get_origin, get_args, and explicit unwrapping
      of Annotated and unions where needed instead of removed shape constants.
      Read custom metadata from json_schema_extra rather than
      field_info.extra. Preserve declaration order used by parsers and custom
      serializers, exclude synthetic fields intentionally, and test nested,
      optional, union, list, and component fields. Do not import SHAPE_LIST or
      other removed internals from a compatibility namespace.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data. Make it recognize the repository's actual repeatable annotations,
      including directly parameterized lists and any relevant Optional,
      Union, or Annotated wrappers, without classifying strings or unrelated
      collections as repeatable. Use it in the pre-model initializer so a
      single object supplied for a repeatable field is wrapped exactly once
      while existing lists and null values retain their established behavior.
      Run the dedicated loop-initializer tests and direct helper tests.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where actually
      used: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Use from_attributes
      when replacing ORM parsing and TypeAdapter when validating a non-model
      type. Preserve aliases, include and exclude behavior, exclusion of None
      or unset values, enum and decimal formatting, dates, nested models,
      ordering, separators, delimiters, and custom X12 or other domain output.
      Update parser access from __fields__ to model_fields without changing
      field-to-element alignment. Compare exact representative serialized
      strings and round trips, not merely object construction.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile all production Python files, then import settings, shared models,
      support utilities, parsers, both major-version segment modules, and
      representative transaction modules. Run pytest collection directly and
      require a nonzero expected test count with no collection errors. Resolve
      construction errors such as missing field annotations, removed Field
      arguments, bad decorator signatures, and undefined names one complete
      traceback at a time. Imports and collection are gates only, never proof
      that validation behavior survived. Before this step through
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
      Run commands without output-truncating pipelines and record their true
      status and counts. For validators, add or run examples that trigger every
      retained condition, including invalid combinations; a test that covers
      only successful construction cannot detect a validator reduced to a
      no-op. Continue short edit-test loops until each affected subsystem is
      green before widening scope.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases, or
      validation order, compare the v1 intent expressed by tests, fixtures,
      documentation, original code, and git history with v2 behavior instead
      of weakening tests. Check omitted versus explicit None, Optional
      requiredness, default validation, strictness, enum conversion, decimal
      limits, pattern matching, nested error locations, and before-versus-after
      execution. Prefer the smallest model change that restores documented
      domain behavior. Do not broadly loosen field types, extra handling, or
      validators to make fixtures pass.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement. Inspect complete
      functions around each match, not snippets alone. Look for lowercase true
      inserted into Python, malformed imports, duplicate decorators, missed
      bare decorators, wrong mode, self-versus-values confusion, changed
      indentation, accidental annotations, unconditional early returns,
      unreachable code, deleted branches, and temporary migration scripts or
      plans. Compare suspicious functions to their original git version.
      Revert and port manually when an automated transformation cannot be
      proven semantics-preserving.
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
      and obsolete parsing or serialization entry points. Search for
      non-annotated overrides of inherited model fields and inspect all
      json_schema_extra values. Also search changed functions for suspicious
      unconditional returns, pass-only bodies, ellipses, TODO stubs, broad
      exception swallowing, and original logic left after return or raise.
      Treat a no-match grep status as expected evidence, not a failed migration
      command. Re-read `references/guardrails-and-provenance.md` and reconcile
      every inventory item with the final source.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active. Do not substitute a
      hand-selected subset, collect-only run, import smoke test, or piped
      command. Capture the true process exit status and complete summary,
      including passed, failed, error, skipped, xfailed, and warning counts.
      Require actual passing tests; zero tests passing is failure. If the suite
      fails, return to the smallest relevant focused test, repair the first
      complete failure without regressing previous checkpoints, and rerun the
      full suite.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted or bypassed logic. Compare each changed
      function with its original body or pre-migration diff and account for
      every branch, mutation, raise, and return. Ensure before validators still
      return raw input, after validators return self only after executing all
      checks, and reusable validators are still registered and exercised.
      Explicitly reject pydantic.v1 imports, compatibility shims, pass-only
      implementations, unconditional-success replacements, and original logic
      made unreachable after return or raise even if tests are green. Re-read
      `references/guardrails-and-provenance.md` during this inspection.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the complete final diff once more. Confirm that
      only intended source, dependency, lock, and test changes remain; remove
      temporary migration plans and one-off rewrite scripts unless they are
      deliberate deliverables. Verify no user changes were overwritten, no
      source file was accidentally truncated, every inherited field override
      is annotated, every changed validator contains reachable original
      behavior, and no compatibility import remains. Rerun any check affected
      by cleanup and do not report completion if the working tree contradicts
      the test evidence.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact collection and full-suite
      commands, true process exit statuses, and final pass, fail, error, skip,
      xfail, and warning counts. State the static-audit result and explicitly
      confirm that no pydantic.v1 compatibility imports were introduced and no
      function or validator body was emptied, bypassed, or made unreachable.
      Mention remaining failures or warnings honestly and never call the
      migration complete when collection failed, tests were truncated, only a
      subset ran, zero tests passed, or behavior-preservation review is
      incomplete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}
```