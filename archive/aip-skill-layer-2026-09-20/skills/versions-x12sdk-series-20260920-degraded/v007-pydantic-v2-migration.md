---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 7
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

anti_patterns:
  - >
    Rewriting imports to pydantic.v1, importing through another v1 compatibility
    namespace, or creating a shim that routes native code back to v1. This is
    rejected even if every test passes.
  - >
    Replacing a validator or any other function body with pass, ellipsis, a
    bare return, unconditional success, an immediate return followed by
    unreachable original logic, or any equivalent no-op merely so imports or
    tests succeed. A green suite does not justify deleting behavior.
  - >
    Converting root validators with a repository-wide textual replacement.
    A v2 before model validator receives raw input, while an after model
    validator normally receives and returns the model instance; changing only
    the decorator leaves v1 dict-based bodies semantically or syntactically
    wrong.
  - >
    Applying regex scripts or generated repair scripts to validator bodies
    without reviewing every resulting function against its original logic.
  - >
    Adding compatibility wrappers that imitate v1 validator signatures instead
    of porting each call site to native v2 FieldValidationInfo or model
    validation semantics.
  - >
    Fixing import-time errors by weakening annotations, removing constraints,
    changing required fields to optional defaults, or disabling validation
    without evidence that the old behavior intended that change.
  - >
    Assuming Optional[T] supplies a default in Pydantic v2. Optional controls
    whether None is valid; use an explicit default only when omission was
    accepted by the original contract.
  - >
    Assuming a zero exit status from `pytest ... | head`, `pytest ... | tail`,
    or a similar pipeline means pytest passed. The shell may report only the
    final filter's status and the traceback may be truncated.
  - >
    Treating grep exit status 1 for no matches as a task failure, or treating a
    successful grep as proof that runtime behavior is correct.
  - >
    Repeatedly probing guessed paths or misspelled repository roots instead of
    establishing the root once and using paths relative to it.
  - >
    Creating migration-plan files, one-off rewrite scripts, or other artifacts
    in the repository and leaving them in the final diff when they are not part
    of the requested deliverable.
  - >
    Editing tests first to accept altered behavior rather than preserving the
    production contract expressed by tests, fixtures, documentation, and
    history.
  - Declaring the migration complete without running the repository's exact full test suite.
  - Ending the attempt after an import succeeds, collection succeeds, one test file passes, or a partial count of passing tests is observed.
  - Ending with a summary of intended changes before collection and the full suite have passed.

steps:
  - name: establish-the-failure
    description: >
      Enter the verified repository root and run the repository's own full test
      command immediately, before editing. Run it directly and retain the full
      stdout, stderr, exit status, summary counts, and first complete traceback.
      Do not pipe it through head or tail. If logging with tee is necessary,
      enable pipefail or record the test process through PIPESTATUS so a filter
      cannot turn failure into exit zero. Distinguish collection errors from
      executed test failures and record the exact command for the final gate.
      Before this step through repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, list the repository root, identify the VCS root, and inspect git
      status before constructing absolute paths or editing. Use the confirmed
      root consistently; do not guess variants of the path. Separate
      pre-existing user changes and untracked files from migration changes, and
      never reset or overwrite unrelated work. If earlier automated edits have
      already corrupted a file, use status, diff, and git history to recover
      the original function bodies before attempting the v2 port.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, all requirement
      files, tox/nox configuration, CI workflows, pytest configuration, README
      development instructions, package exports, and any post-migration
      requirements file before editing. Do not assume setup.py or
      requirements.txt exists. Determine the authoritative install command,
      supported Python versions, exact full-suite command, intended Pydantic
      range, pydantic-settings requirement, and whether generated files or
      warnings are part of CI acceptance.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set. Record Python, Pydantic,
      pydantic-core, pydantic-settings, pytest, and project versions from the
      actual interpreter running tests. Verify imports resolve to the working
      tree rather than an unrelated installed copy. Use the repository's
      post-migration requirements when supplied; do not merely edit dependency
      metadata while continuing to test against a different environment.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces. Include BaseSettings,
      inner Config classes, validator and root_validator in both called and bare
      decorator forms, allow_reuse, pre and always flags, values and field
      callback parameters, __fields__, ModelField, field_info.extra, shape
      constants such as SHAPE_LIST, regex Field arguments, arbitrary Field
      extras, parse_obj, parse_raw, from_orm, dict, json, copy, schema,
      construct, and direct pydantic internals. Also search for unannotated
      overrides of inherited model fields, constrained types, Optional fields
      without explicit defaults, and custom helpers that inspect list fields.
      Save file and line locations rather than relying on counts alone.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`. Record expected exception types,
      validation messages where asserted, accepted coercions, missing/default
      behavior, aliases, serialized X12 output, schema metadata, environment
      variable behavior, and ordering. Treat these as compatibility contracts;
      do not delete a helper merely because its v1 implementation used a
      removed internal API.
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
      schemas, and tests. For each validator record its original decorator,
      mode, signature, complete body, fields read, fields changed, return value,
      and tests. Order work from shared infrastructure to leaf models, but let
      the first real collection traceback determine the immediate repair.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a speculative
      repository-wide rewrite. Make the smallest behavior-preserving native-v2
      change, rerun the failing import or collection node without truncation,
      and continue one blocker at a time. Read enough surrounding source to
      understand the class and inherited fields. For errors saying a base field
      was overridden by a non-annotated attribute, add the correct annotation
      to the override, for example `segment_name: X12SegmentName = ...`; do not
      remove the field or suppress Pydantic's model construction checks.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models exist. Import BaseSettings from
      pydantic_settings and use SettingsConfigDict or the installed version's
      documented native configuration. Preserve environment-file behavior,
      prefixes, case sensitivity, aliases, defaults, and ignored extras.
      Replace removed `Field(regex=...)` with `pattern=...` while preserving the
      pattern. Reinstall through the declared workflow and verify the settings
      import and representative environment parsing. Before this step through
      migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Map behavior intentionally, including
      extra handling, assignment validation, enum values, aliases, population
      by name, string normalization, frozen models, arbitrary types,
      from-attributes behavior, and default validation. Do not copy obsolete
      config keys blindly. Import ConfigDict explicitly and run shared-model
      import and construction checks after each base-class change.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version. Replace regex with pattern. Move
      project-specific Field metadata such as `is_component=True` into
      `json_schema_extra={"is_component": True}` using the Python boolean
      `True`, then update readers to use FieldInfo.json_schema_extra. Preserve
      aliases, lengths, numeric bounds, decimal behavior, defaults, factories,
      and schema output. Annotate every inherited field override. Audit every
      Optional field: in v2, `Optional[T]` without a default remains required;
      add `= None` only where the v1 model allowed omission. Prefer Annotated
      constraints where required by the installed version and test both valid
      and invalid boundaries.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites. Native v2 field validators do not accept allow_reuse;
      remove it rather than emulating it. Import field_validator from pydantic,
      not from pydantic.validators. Preserve each reusable function's value
      transformation and errors, and choose mode="before" only when it must see
      raw input. If validators rely on defaults, determine whether
      validate_default or a model validator is required. Do not create a wrapper
      whose only purpose is to retain the old `values`, `field`, or `config`
      callback signature.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body. Convert pre=True to mode="before" where raw input is required.
      Replace `values` access with ValidationInfo.data while respecting field
      declaration order: only previously validated fields are available there.
      Replace removed `field` or `config` arguments with supported
      ValidationInfo or `cls.model_fields[info.field_name]` access. Preserve
      transformations, conditional requirements, raised errors, and validation
      of defaults. Test positive, negative, missing, None, and coercion cases
      for each distinct pattern. Never solve signature errors by returning the
      input before the original body.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
      For mode="before", accept raw input, handle mapping versus model input
      deliberately, preserve all dict mutations and checks, and return the raw
      input. For mode="after", normally define an instance method receiving
      `self`, read and modify attributes rather than treating the model as a
      dict, preserve every branch and error, and return `self`. Account for
      assignment validation if enabled. Compare every converted body side by
      side with its original from the initial diff or git history. Run the
      closest tests after each validator or coherent class, not after a batch
      of dozens. Reject conversions that leave unreachable code or reduce a
      substantive validator to `return values` or `return self`.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection. Use `type(instance).model_fields` or the model class rather
      than deprecated instance access. Replace `field_info.extra` with
      `json_schema_extra or {}`. Preserve field declaration order because X12
      serialization and positional parsing may depend on it. Inspect actual
      installed objects interactively when uncertain rather than importing
      removed constants such as SHAPE_LIST from a guessed location.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data. Detect list origins robustly, including supported Optional or Union
      wrappers and inherited fields, without SHAPE_LIST or other v1 internals.
      Use the helper in repeatable-segment wrapping logic so a single supplied
      object is wrapped only for list fields, while existing lists, None, and
      unrelated scalar fields retain their behavior. Run the dedicated loop
      initializer tests and direct helper tests.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where actually
      used: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Preserve aliases,
      enum rendering, exclusion rules, decimal and date formatting, ordering,
      custom delimiters, component separators, newlines, and round trips. Do
      not mechanically replace custom methods named dict or json unless they
      are Pydantic calls. Verify parser field discovery uses model_fields and
      FieldInfo metadata, then compare representative parsed models and exact
      serialized X12 strings with fixtures.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile all production Python files, then import settings, shared models,
      support utilities, parsers, both major-version segment modules, and
      representative transaction modules. Run pytest collection for the whole
      suite directly and retain its real exit status and complete traceback.
      Fix every model-construction and collection error before broad execution.
      Import success alone is not a completion signal. Before this step through
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
      Use `-x` while diagnosing but preserve the full traceback. Record actual
      exit status and pass/fail/error counts. A passing focused test permits
      movement to the next repair; it never substitutes for the full suite.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases, or
      validation order, compare the v1 intent expressed by tests, fixtures,
      docs, and original code with v2 behavior instead of weakening tests.
      Explicitly test omitted versus None, before versus after values, default
      validation, assignment, nested models, list wrapping, constrained
      boundaries, and exact serialization. Change tests only when the task
      explicitly requires a documented contract change, not to hide migration
      regressions.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement. Compare changed
      validators against their original versions and look for malformed
      decorators, wrong signatures, duplicated imports, lower-case `true`,
      unannotated inherited-field overrides, broad Optional/default changes,
      immediate returns, unreachable original code, missing branches, and
      accidentally deleted bodies. Delete temporary migration plans and repair
      scripts unless they are requested deliverables. Revert unrelated churn
      without disturbing pre-existing user work.
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
      validators and changed functions reduced to pass, ellipsis, bare or
      unconditional returns, and returns or raises followed by unreachable
      original logic. Inspect every match manually because comments, custom
      methods, and legitimate names can create false positives; no-match grep
      status is expected, not an error.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active. Do not pipe through
      head or tail and do not report a pipeline filter's exit code as pytest's.
      Retain the final exit status and complete pass, fail, error, skip, xfail,
      and warning counts. If it fails, return to the earliest relevant repair
      step, add a focused regression check, and rerun collection, focused
      tests, audits, and the full suite. Continue until the exact command exits
      zero.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted or bypassed logic. Compare each changed
      function with its pre-migration version from git history or the initial
      diff and account for every conditional, mutation, error, and return.
      Reject pass, ellipsis, unconditional success, trivial argument
      pass-through replacing substantive logic, and original code stranded
      after return or raise. Confirm representative invalid data still fails
      and representative valid data still transforms and serializes correctly.
      A green suite cannot waive this gate.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the complete final diff once more. Confirm only
      intended project files changed, dependency declarations agree with the
      tested environment, no pydantic.v1 compatibility path exists, no
      temporary plans or rewrite scripts remain, all inherited field overrides
      are annotated, and all original validator behavior is represented by
      native-v2 code. If this review changes any file, rerun the relevant
      focused tests, static audit, exact full suite, and behavior verification.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact collection and full-suite
      commands, true process exit statuses, and final pass, fail, error, skip,
      xfail, and warning counts. Mention any intentional remaining warnings or
      compatibility surfaces with evidence. Do not claim completion if
      collection, the exact full suite, static audit, behavior-preservation
      audit, or final diff gate failed; instead report the current blocker and
      the last verified checkpoint.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}
```