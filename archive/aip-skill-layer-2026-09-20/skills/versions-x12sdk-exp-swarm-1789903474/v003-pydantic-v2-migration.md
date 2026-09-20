---
name: pydantic-v2-migration
description: Procedure distilled from graded repository migrations for moving Python codebases from Pydantic v1 to native Pydantic v2 APIs. Use when upgrading Pydantic dependencies, BaseSettings, validators, model configuration, field introspection, serialization, schemas, parser discovery, Optional-field behavior, or a damaged partial migration while preserving behavior and making the full test suite pass.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces: "a2038b8e,e29b052a,21c7853e"
---

```yaml
# Completeness classification for the previous procedure and graded evidence:
# Mapped — the previous purpose, all four trigger categories, all three
# exclusions, every anti-pattern, and all 25 operational steps are retained.
# Mapped — details formerly embedded in those steps remain below, including
# dependency quoting, BaseSettings migration, Optional defaults, validator
# signatures, inherited-validator collisions, list annotation handling,
# FieldInfo metadata, runtime traversal, serialization, parser discovery,
# coercion checks, collection gates, diff review, focused/full tests, forbidden
# shortcuts, behavioral verification, and completion reporting.
# Mapped — new graded-attempt evidence is incorporated through explicit recovery
# of damaged partial migrations, repository-wide scans for regex and imports,
# staged import gates for both versioned model families, and prohibitions
# against undefined info.data, duplicate field_validator imports, reversed
# list logic, unfinished plans, and trusting truncated pytest pipelines.
# Deliberate drop — none.
# Schema gap — none.
# Body drop — none.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, settings, field order, and
  domain behavior. Recover safely when an earlier partial migration left the
  worktree inconsistent. Finish only when the repository's full test suite
  passes without importing pydantic.v1, suppressing validators, emptying
  function bodies, deleting behavior, or leaving dependency metadata on v1.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, configuration, field, schema, or validator errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings from pydantic, root_validator, validator, class Config, __fields__, dict, or schema
  - Dependency metadata still pins pydantic below version 2

do_not_use_when:
  - The codebase is already on Pydantic v2 and its full suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration

anti_patterns:
  - Re-pointing imports to pydantic.v1; this evades rather than performs a native v2 migration and is forbidden even if tests pass
  - Emptying a validator or other function body, replacing it with pass, or removing its decorator merely to make imports or tests succeed
  - Disabling, deleting, or weakening validation without proving equivalent behavior
  - Blind global replacement of validators, values.get, decorators, signatures, regex, or model APIs across files
  - Converting every root_validator to the same model_validator mode without classifying its data contract
  - Adding classmethod to mode-after model validators; mode-after validators normally operate on self
  - Using info.data inside model_validator mode-before; its raw input is the values argument
  - Treating mode-after self as a dictionary and calling self.get
  - Referring to info when the validator signature does not receive ValidationInfo
  - Importing two different callables under the same field_validator name
  - Importing field_validator and then overwriting that name with functools.partial(field_validator)
  - Checking field.annotation is list or directly reading annotation.__origin__; this misses Optional, Union, and annotated forms and may raise AttributeError
  - Reversing list-field logic so list annotations are skipped instead of wrapping their dictionary values
  - Adding a helper demanded by tests without updating production callers to use the same semantics
  - Continuing after an automated edit without reviewing the complete diff for collateral substitutions
  - Compounding a visibly damaged partial migration instead of comparing it with the baseline and repairing malformed edits first
  - Resetting or discarding pre-existing user changes wholesale merely because the worktree is dirty
  - Fixing only the first base segments file while transaction-specific loops, segments, validators, and transaction sets still use v1 APIs
  - Running only the first failing test and declaring completion
  - Piping pytest into head without pipefail and then trusting the pipeline's zero status
  - Treating deprecation warnings as proof of correctness or ignoring import and collection errors
  - Updating the installed environment while leaving project dependency metadata pinned to Pydantic v1
  - Passing unquoted dependency constraints containing less-than or greater-than signs to a shell, which can create stray redirection files
  - Editing tests to accommodate accidental migration regressions unless the task explicitly changes the public contract
  - Spending the attempt repeatedly researching standard migration facts instead of inspecting code, editing, and testing
  - Ending after planning, creating a todo list, or making a partial edit without running collection and the full suite
  - Trusting a codemod's changed-file count as evidence that validator signatures and behavior remain correct

steps:
  - name: inspect-repository-and-task-contract
    description: >
      Work from the repository root. Read the task, pyproject.toml, and every
      requirements or lock file before editing. List the root rather than
      assuming setup.py exists. Identify package layout, supported Python
      versions, canonical test command, formatter or linter, and any
      post-migration requirements file. If requirements-v2 or equivalent
      documents known-good versions or a reference pass count, treat it as task
      evidence. Record whether settings require pydantic-settings. Inspect git
      status and the existing diff because the workspace may contain partial
      migration edits from an earlier attempt. Remove only confirmed accidental
      artifacts, such as files created by shell redirection.
    outputs:
      - {name: repository-context, type: object}

  - name: recover-or-preserve-partial-work
    description: >
      Before adding more edits, classify every existing changed file as
      intentional pre-existing work, correct migration work, malformed partial
      migration work, or unrelated work. Compare suspicious regions with HEAD
      or another repository baseline without resetting the whole worktree.
      Preserve user changes. Repair or selectively revert only malformed edits
      whose intended behavior can be established. Search immediately for known
      partial-migration damage: undefined info, info.data inside mode-before
      model validators, mode-after validators still accepting values,
      duplicate or shadowed field_validator imports, malformed ConfigDict
      calls, reversed list checks, missing imports for decorators already in
      use, and methods whose bodies were emptied. Do not proceed until
      foundational files are syntactically coherent.
    inputs:
      - {name: repository-context, type: object}
    outputs:
      - {name: worktree-classification, type: object}
      - {name: repaired-baseline, type: object}

  - name: establish-the-failure
    description: >
      Run the full suite once in the intended Pydantic v2 environment and
      capture the command, Python and package versions, collected-test count,
      exit status, and first traceback. Do not truncate the command with a
      pipeline that masks pytest's exit status. If output must be limited,
      redirect it to a file and inspect the file afterward, or enable pipefail.
      Distinguish collection errors from executed-test failures; zero passing
      tests usually means imports or model construction failed before behavior
      was exercised. Preserve this baseline for comparison.
    outputs:
      - {name: baseline-result, type: object}
      - {name: first-error, type: string}

  - name: inventory-pydantic-surface
    description: >
      Search all production Python files, tests that introspect public model
      APIs, and dependency metadata. Do not stop at the first grep page.
      Inventory BaseSettings, BaseModel, Field arguments including regex and
      custom extras, class Config, root_validator, validator, reusable
      validator decorators, allow_reuse, __fields__, pydantic.fields constants
      such as SHAPE_LIST, field_info, shape, type_, outer_type_, dict, json,
      schema, parse_obj, copy, construct, and unannotated overrides of inherited
      fields. Find Optional annotations without defaults, dynamic parser/model
      discovery, recursive model walkers, and metadata such as is_component.
      Search every versioned and transaction-specific loops.py, segments.py,
      validators.py, and transaction_set.py. Count occurrences and group files
      by concern. Use carefully quoted searches and verify failed grep
      expressions rather than treating empty output as no matches.
    inputs:
      - {name: repository-context, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: create-a-staged-migration-ledger
    description: >
      Turn the inventory into a short ledger ordered by dependency layer:
      metadata and settings; foundational models and helpers; shared
      validators; shared versioned segments; transaction-specific models;
      parser and CLI utilities; behavior and round trips. Record the expected
      import gate and focused tests for each layer. Work through this ledger
      instead of repeatedly restarting exploration or creating plans that are
      never executed. Mark a layer complete only after its import or focused
      test gate passes.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: update-dependency-metadata
    description: >
      Change every authoritative dependency declaration from the v1 pin to the
      task-supported Pydantic v2 range. Add pydantic-settings when BaseSettings
      is used, and preserve python-dotenv or other settings dependencies.
      Update lock files through the repository's package manager when present.
      Quote shell requirement strings such as "pydantic>=2,<3" so angle
      brackets cannot become redirections. Confirm installed versions with
      Python and inspect git status for accidental files. Dependency metadata,
      source imports, and the test environment must agree before completion.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: dependency-changes, type: object}

  - name: migrate-settings-first
    description: >
      Replace `from pydantic import BaseSettings` with
      `from pydantic_settings import BaseSettings`. Keep Field imported from
      pydantic. Replace every removed Field(regex=...) with Field(pattern=...)
      repository-wide, not only the first traceback. Convert settings
      configuration to SettingsConfigDict imported from pydantic_settings,
      preserving case sensitivity, environment prefixes, dotenv files, and
      extra handling. Clear settings caches during focused environment-variable
      tests when lru_cache is used. Import the settings module immediately
      after editing because BaseSettings is commonly the first collection
      blocker.
    inputs:
      - {name: first-error, type: string}
    outputs:
      - {name: settings-migration, type: object}

  - name: migrate-base-model-configuration
    description: >
      Replace class Config with model_config = ConfigDict(...) on BaseModel
      classes. Preserve use_enum_values, extra, frozen, assignment validation,
      aliases, arbitrary types, and population behavior using v2 names. Remove
      allow_mutation and express immutability with frozen=True. Do not place a
      class docstring as a positional expression inside ConfigDict. Use
      SettingsConfigDict for BaseSettings rather than assuming ConfigDict
      covers settings behavior. Import each foundational model module after
      this layer.
    outputs:
      - {name: model-configuration-changes, type: object}

  - name: preserve-v1-optional-field-semantics
    description: >
      Audit every Optional[T] and T | None declaration. In Pydantic v2,
      nullable annotations without defaults remain required; Pydantic v1 often
      treated them as optional with an implicit None default. Add `= None`
      wherever omission was previously accepted while retaining fields that are
      intentionally required but nullable. Decide from tests, parser behavior,
      model construction, and schemas rather than applying a blind
      replacement. Pay special attention to generated-looking segment models
      whose omitted trailing fields are valid input.
    outputs:
      - {name: optional-field-audit, type: object}

  - name: migrate-field-validators
    description: >
      Replace validator with field_validator one validator at a time. Preserve
      timing: pre=True becomes mode="before"; ordinary validators usually use
      the default after mode. Remove allow_reuse. Place @classmethod directly
      below @field_validator when the method accepts cls. Replace the v1 values
      argument with ValidationInfo only when other validated fields are needed,
      and read them through info.data. Remember that info.data contains only
      fields already validated according to declaration order. Do not replace
      values.get globally: mode-before model validators still receive a raw
      mapping named values. Preserve always-like behavior deliberately because
      defaults and validate_default differ in v2. Ensure every decorator used
      in a file is imported exactly once and run focused tests for each
      validator family.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: field-validator-changes, type: object}

  - name: migrate-reusable-validator-helpers
    description: >
      Inspect reusable validator functions and decorator factories separately
      from inline methods. Avoid name collisions such as importing
      field_validator and then assigning `field_validator =
      functools.partial(field_validator)`. Alias the Pydantic import, for
      example `_pydantic_field_validator`, or expose a small explicit wrapper.
      Remove obsolete allow_reuse while preserving mode and function
      signatures. If a decorated validator is assigned as a class attribute in
      many models, test that its descriptor remains registered after
      inheritance. Update helper checks from hasattr(item, "dict") to BaseModel
      or model_dump-aware checks.
    outputs:
      - {name: reusable-validator-changes, type: object}

  - name: classify-and-migrate-root-validators
    description: >
      Classify every root_validator before editing. Convert pre=True validators
      that normalize raw mappings to `@model_validator(mode="before")`; retain a
      class-oriented signature such as `(cls, values)` and return the raw
      mapping. Access that mapping through values.get, never undefined
      info.data. Convert post validators to
      `@model_validator(mode="after")`; use an instance method `(self)`, access
      attributes on self, and return self. Do not add @classmethod to an after
      validator. If dictionary-oriented post-validation logic truly must be
      retained, use an explicitly justified wrap validator rather than
      pretending self is a dictionary. Account for assignment validation when
      enabled. Migrate and test validators in small groups because broad
      textual conversion can create importable but semantically broken code.
    outputs:
      - {name: model-validator-changes, type: object}

  - name: check-validator-method-inheritance
    description: >
      Map validator method names through each model hierarchy. Pydantic v2
      treats an inherited validator with the same method name as overridden, so
      repeated generic names can silently suppress base validation. Rename
      methods where both base and subclass validators must execute, then add or
      run an invalid-input test proving each intended validator fires. Also
      check reusable decorated functions assigned under the same class
      attribute name.
    outputs:
      - {name: validator-inheritance-audit, type: object}

  - name: replace-removed-field-shape-apis
    description: >
      Remove imports of SHAPE_LIST and checks against ModelField.shape. Define
      one tested annotation helper using typing.get_origin and typing.get_args
      to recognize list fields, including list[T], typing.List[T], and list
      members inside Union or Optional where required. A basic helper can use
      `get_origin(annotation) is list`; recurse through union arguments when
      optional list annotations occur. Use the same helper in production
      normalization and tests that inspect list-typed fields. In a before model
      validator, iterate cls.model_fields and wrap a dictionary value only when
      the annotation is list-like. The condition must skip non-list fields, not
      list fields. Read the raw value from values, not undefined info.data, and
      never access annotation.__origin__ directly.
    outputs:
      - {name: annotation-introspection-changes, type: object}

  - name: migrate-model-field-introspection
    description: >
      Replace __fields__ with model_fields on model classes or
      type(instance).model_fields. Treat each value as FieldInfo rather than a
      v1 ModelField: use annotation instead of type_ or outer_type_, default for
      defaults, and json_schema_extra for custom metadata. Replace every
      `Field(is_component=True)` with
      `Field(json_schema_extra={"is_component": True})`, then read the marker
      from `field.json_schema_extra or {}`. Preserve declaration order because
      X12 parsing and serialization are positional. Update metadata writers and
      readers in the same layer and scan both shared version directories for
      all occurrences.
    outputs:
      - {name: field-introspection-changes, type: object}

  - name: preserve-runtime-model-traversal
    description: >
      Rework serializers and tree walkers that used ModelField.name, type_, or
      shape. Iterate ordered model_fields names and inspect each actual
      attribute value at runtime. Traverse BaseModel instances, lists of model
      instances, and optional values without removed field internals. Preserve
      distinctions between segment models and nested groups, output order, and
      Decimal, date, time, enum, delimiter, component, and repetition
      formatting byte-for-byte. Test newline and compact output paths when both
      exist.
    outputs:
      - {name: traversal-changes, type: object}

  - name: annotate-overridden-model-fields
    description: >
      Search the entire package for subclasses that assign to an inherited
      model field without a type annotation. Pydantic v2 rejects declarations
      such as `segment_name = X12SegmentName.CR5` when the base class defines
      segment_name as a field. Add the intended annotation, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`, without changing its
      value. Fix all occurrences rather than only the first traceback, and
      rerun imports after each batch.
    outputs:
      - {name: field-override-changes, type: object}

  - name: migrate-serialization-and-schema-calls
    description: >
      Replace BaseModel.dict with model_dump and schema with
      model_json_schema, preserving exclude, exclude_none, exclude_unset,
      aliases, and serialization options. Replace other renamed model APIs only
      after checking v2 semantics. Update recursive utilities consistently,
      including hasattr guards. Use model_dump in parsers, CLI output,
      adjustment logic, delimiter serialization, and segment counting where
      appropriate. Verify Enum, Decimal, date, and datetime behavior;
      mode="python" versus mode="json" is a behavioral choice, not a mechanical
      rename.
    outputs:
      - {name: serialization-changes, type: object}

  - name: migrate-parser-model-discovery
    description: >
      Update dynamic parser discovery from `hasattr(class_value, "schema")` and
      `class_value.schema()` to an explicit BaseModel subclass check where
      possible and model_json_schema(). Exclude BaseModel itself and guard
      issubclass calls to actual classes. Update parser field-name and
      multi-value discovery to model_fields, annotation helpers, and
      json_schema_extra. Preserve field order and transaction-model detection
      through required header and footer properties. Exercise create_parser for
      every supported transaction family rather than one imported module.
    outputs:
      - {name: parser-discovery-changes, type: object}

  - name: audit-coercion-and-constraint-changes
    description: >
      Once collection succeeds, compare v1 expectations with v2 behavior for
      numbers to strings, iterable-to-dict coercion, unions, enums, Decimal
      scale, date parsing, regex or pattern handling, constrained types, and
      error types. Prefer explicit before validators or accurate annotations
      when legacy coercion is part of the public behavior. Do not weaken
      constraints globally. Run representative valid and invalid model
      constructions, resource round trips, and exact X12 string comparisons.
    outputs:
      - {name: coercion-audit, type: object}

  - name: run-import-and-collection-gates
    description: >
      After each migration layer, run compileall or an equivalent syntax check,
      import settings and foundational models, import both shared versioned
      segment modules, then import every transaction package's loops, segments,
      and transaction_set modules. Execute pytest collection without truncating
      its exit status. Resolve errors in order: syntax, missing names and
      imports, model construction, collection, then executed tests. A missing
      model_validator import or a remaining Field(regex=...) must be fixed
      repository-wide before moving on. Collection success is a gate, not
      completion. Record warning categories because they reveal remaining v1
      APIs, but prioritize blockers first.
    outputs:
      - {name: collection-gate-results, type: object}

  - name: inspect-every-mechanical-diff
    description: >
      After any codemod, script, search-and-replace, formatter, or bulk edit,
      inspect the complete git diff before testing further. Search specifically
      for values changed to info.data in model validators, undefined info,
      duplicate imports, field_validator shadowing, reversed conditions,
      misplaced classmethod decorators, malformed ConfigDict calls, changed
      indentation, missing annotations, and replacements inside unrelated
      functions. Compare suspicious edits against the original implementation.
      Revert collateral edits and migrate the affected code deliberately. A
      script reporting files changed is not evidence of correctness.
    outputs:
      - {name: diff-review, type: object}

  - name: iterate-on-focused-failures
    description: >
      Run the smallest meaningful failing test module without hiding its exit
      code, fix the underlying migration contract, rerun that test, then rerun
      collection to catch cross-module effects. Group failures by cause rather
      than patching assertions individually. Prioritize foundational model
      tests, shared 4010 and 5010 segment tests, reusable validation tests,
      parser creation, loop initialization, repeatable segments, model reader
      tests, and resource round trips. Maintain a short failure ledger so fixed
      categories are not regressed. Continue through the ledger rather than
      stopping when a new first error appears.
    outputs:
      - {name: focused-test-results, type: object}

  - name: run-the-full-suite
    description: >
      After focused tests and collection pass, run the repository's canonical
      full suite with no -x, output truncation, or ignored exit status. Compare
      the collected and passed count with repository evidence; investigate
      unexpectedly missing tests even when pytest exits zero. Run the configured
      linter or formatter check if available, then inspect git diff and status.
      Repeat from a fresh process until the full suite passes.
    outputs:
      - {name: full-suite-result, type: object}

  - name: perform-forbidden-shortcut-audit
    description: >
      Search production code and dependency metadata for pydantic.v1,
      remaining v1-only imports, BaseSettings from pydantic, root_validator,
      validator, SHAPE_LIST, class Config, __fields__, field_info, type_,
      outer_type_, deprecated dict or schema calls, removed Field arguments,
      and obsolete dependency pins. Inspect every changed function body to
      prove none was emptied, replaced with pass, commented out, or stripped of
      validation. Confirm no tests were skipped, deleted, or changed merely to
      accept regressions and no warning filters conceal migration problems. A
      green suite cannot override this gate: pydantic.v1 imports and emptied
      function bodies are explicit failure conditions.
    outputs:
      - {name: shortcut-audit, type: object}

  - name: verify-behavior-beyond-test-status
    description: >
      Manually exercise high-risk behavior not guaranteed by aggregate test
      status: settings loaded from environment, omitted Optional fields,
      invalid data rejected by inherited validators, repeatable dictionaries
      wrapped only for list fields, component and repetition delimiters, model
      discovery, recursive segment counting, CLI serialization, parser
      creation, and parse-to-X12 resource round trips. Compare concrete outputs
      with pre-migration fixtures or documented examples. Confirm custom field
      metadata is both written and read through json_schema_extra.
    outputs:
      - {name: behavior-verification, type: object}

  - name: report-completion
    description: >
      Report dependency ranges and major API migrations, the exact full test
      command and pass count, focused behavioral checks, and remaining
      non-blocking warnings. State explicitly that the shortcut audit found no
      pydantic.v1 imports and no emptied or disabled function bodies. Mention
      files intentionally left unchanged and any environmental limitation. Do
      not claim completion if collection, the full suite, shortcut audit, or
      behavior verification is incomplete.
    inputs:
      - {name: full-suite-result, type: object}
      - {name: shortcut-audit, type: object}
      - {name: behavior-verification, type: object}
    outputs:
      - {name: migration-report, type: object}
```