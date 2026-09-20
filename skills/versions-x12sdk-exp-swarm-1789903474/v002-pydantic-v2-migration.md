---
name: pydantic-v2-migration
description: Procedure distilled from graded repository migrations for moving Python codebases from Pydantic v1 to native Pydantic v2 APIs. Use when upgrading Pydantic dependencies, BaseSettings, validators, model configuration, field introspection, serialization, schemas, parser discovery, or Optional-field behavior while preserving application behavior and making the full test suite pass.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 2
    derived_from_traces: "a2038b8e,e29b052a"
---

```yaml
# Completeness classification for the previous procedure:
# Mapped — its purpose, four trigger categories, three exclusions, anti-pattern
# reference, and all 24 named steps are retained below. Their formerly external
# reference instructions are expanded inline so the procedure is self-contained.
# Deliberate drop — the obsolete comment describing a version-zero procedure
# with no migration knowledge is not an operational instruction.
# Schema gap — none.
# Body drop — none.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, settings, field order, and
  domain behavior. Finish only when the repository's full test suite passes
  without importing pydantic.v1, suppressing validators, emptying function
  bodies, or deleting behavior.

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
  - Blind global replacement of validators, values.get, decorators, or signatures across files
  - Converting every root_validator to the same model_validator mode without classifying its data contract
  - Adding classmethod to mode-after model validators; mode-after validators operate on self
  - Using info.data inside model_validator mode-before; its raw input is the values argument
  - Treating mode-after self as a dictionary and calling self.get
  - Importing two different callables under the same field_validator name
  - Checking field.annotation is list or directly reading annotation.__origin__; this misses Optional, Union, and annotated forms and may raise AttributeError
  - Reversing list-field logic so list annotations are skipped instead of wrapping their dictionary values
  - Continuing after an automated edit without reviewing the complete diff for collateral substitutions
  - Running only the first failing test and declaring completion
  - Piping pytest into head without pipefail and then trusting the pipeline's zero status
  - Treating deprecation warnings as proof of correctness or ignoring import and collection errors
  - Updating the installed environment while leaving project dependency metadata pinned to Pydantic v1
  - Passing unquoted dependency constraints containing less-than or greater-than signs to a shell, which can create stray redirection files
  - Editing tests to accommodate accidental migration regressions unless the task explicitly changes the public contract
  - Spending the attempt repeatedly researching standard migration facts instead of inspecting code, editing, and testing
  - Ending after planning or a partial edit without running collection and the full suite

steps:
  - name: inspect-repository-and-task-contract
    description: >
      Work from the repository root. Read the task, pyproject.toml and every
      requirements or lock file before editing. Inspect git status and the
      existing diff because the workspace may contain partial migration edits
      from an earlier attempt; do not assume it is clean. Identify the package
      layout, supported Python versions, test command, formatter or linter, and
      any post-migration requirements file. If a requirements-v2 file documents
      known-good versions or a reference pass count, treat it as task evidence.
      Record whether settings require the separate pydantic-settings package.
      Do not guess setup.py exists: list the root first. Remove only clearly
      accidental artifacts, such as files created by unquoted shell redirection,
      after confirming them in git status.
    outputs:
      - {name: repository-context, type: object}

  - name: establish-the-failure
    description: >
      Run the unmodified full suite once in the task's intended Pydantic v2
      environment and capture the command, package versions, collected-test
      count, exit status, and first traceback. Do not truncate the command with
      a pipeline that masks pytest's exit status. If output must be limited,
      write it to a file and inspect the file afterward, or enable pipefail.
      Distinguish collection errors from executed-test failures; zero passing
      tests usually means imports or model construction failed before behavior
      was exercised. Preserve the baseline for comparison.
    outputs:
      - {name: baseline-result, type: object}
      - {name: first-error, type: string}

  - name: inventory-pydantic-surface
    description: >
      Search all production Python files and dependency metadata, not merely the
      first grep page. Inventory BaseSettings, BaseModel, Field arguments,
      class Config, root_validator, validator, reusable validator decorators,
      allow_reuse, __fields__, pydantic.fields constants such as SHAPE_LIST,
      field_info, shape, type_, outer_type_, dict, json, schema, parse_obj,
      copy, construct, and unannotated overrides of inherited model fields.
      Also find Optional annotations without defaults, custom parser/model
      discovery, model tree walkers, and metadata such as is_component. Count
      occurrences and group files by migration concern. Use syntax-aware or
      carefully quoted searches; verify failed grep expressions rather than
      interpreting empty output as no matches.
    inputs:
      - {name: repository-context, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: update-dependency-metadata
    description: >
      Change every authoritative dependency declaration from the v1 pin to the
      task-supported Pydantic v2 range. Add pydantic-settings when BaseSettings
      is used, and keep python-dotenv or other required settings dependencies.
      Update lock files through the repository's package manager when present.
      Quote shell requirement strings such as "pydantic>=2,<3" so angle
      brackets cannot become redirections. Confirm installed versions using
      Python and inspect git status for accidental files. Dependency metadata,
      imports, and the test environment must agree before completion.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: dependency-changes, type: object}

  - name: migrate-settings-first
    description: >
      Replace `from pydantic import BaseSettings` with
      `from pydantic_settings import BaseSettings`. Keep Field imported from
      pydantic. Replace removed Field(regex=...) with Field(pattern=...).
      Convert settings configuration to SettingsConfigDict imported from
      pydantic_settings, preserving options such as case_sensitive, env
      prefixes, dotenv files, and extra handling. Clear settings caches during
      focused environment-variable tests when the project uses lru_cache.
      Import the settings module immediately after editing because BaseSettings
      is commonly the first collection blocker.
    inputs:
      - {name: first-error, type: string}
    outputs:
      - {name: settings-migration, type: object}

  - name: migrate-base-model-configuration
    description: >
      Replace class Config with model_config = ConfigDict(...) on BaseModel
      classes. Preserve use_enum_values, extra, frozen, assignment validation,
      aliases, arbitrary types, and population rules using their v2 names.
      Remove allow_mutation and express immutability with frozen=True. Do not
      place a class docstring as a positional expression inside ConfigDict.
      Use SettingsConfigDict for BaseSettings rather than assuming ConfigDict
      covers all settings behavior. Import each foundational model module after
      this layer.
    outputs:
      - {name: model-configuration-changes, type: object}

  - name: preserve-v1-optional-field-semantics
    description: >
      Audit every `Optional[T]` and `T | None` declaration. In Pydantic v2,
      nullable annotations without defaults remain required; Pydantic v1 often
      treated them as optional with an implicit None default. Add `= None`
      wherever omission was previously accepted, while retaining fields that
      are intentionally required but nullable. Use tests, model construction,
      parser behavior, and schemas to decide rather than applying a blind
      replacement. Pay special attention to large generated-looking segment
      models whose omitted trailing fields are part of valid input.
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
      mapping named values. Preserve always-like behavior deliberately, because
      defaults and validate_default differ in v2. Run focused tests for every
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
      functools.partial(field_validator)`. Alias the Pydantic import, or expose
      a small explicit wrapper, and remove obsolete allow_reuse. Preserve the
      original mode and validator function signature. If a decorated reusable
      validator is assigned as a class attribute in many models, test that the
      resulting descriptor remains registered after inheritance. Update helper
      checks from hasattr(item, "dict") to BaseModel or model_dump-aware checks.
    outputs:
      - {name: reusable-validator-changes, type: object}

  - name: classify-and-migrate-root-validators
    description: >
      Classify every root_validator before editing it. Convert pre=True
      validators that normalize raw mappings to
      `@model_validator(mode="before")`; keep a class-oriented signature such
      as `(cls, values)` and return the raw mapping. Convert post validators to
      `@model_validator(mode="after")`; use an instance method `(self)`, access
      attributes on self, and return self. If preserving dictionary-oriented
      post-validation logic is safer, use an explicitly justified wrap
      validator rather than pretending self is a dict. Account for assignment
      validation if enabled. Never insert info.data into a model validator
      unless its chosen signature actually receives ValidationInfo. Migrate and
      test validators in small groups because broad textual conversion can
      produce importable but semantically broken code.
    outputs:
      - {name: model-validator-changes, type: object}

  - name: check-validator-method-inheritance
    description: >
      Map validator method names through each model hierarchy. Pydantic v2
      treats an inherited validator with the same method name as overridden, so
      repeated generic names can silently suppress base validation. Rename
      methods where both base and subclass validators must execute, then add or
      run a focused invalid-input test proving each intended validator fires.
      Also check reusable decorated functions assigned under the same class
      attribute name.
    outputs:
      - {name: validator-inheritance-audit, type: object}

  - name: replace-removed-field-shape-apis
    description: >
      Remove imports of SHAPE_LIST and checks against ModelField.shape. Define
      one tested annotation helper using typing.get_origin and typing.get_args
      to recognize list fields, including list[T], typing.List[T], and list
      members inside Union or Optional where the domain requires them. A basic
      helper may return `get_origin(annotation) is list`; recurse through union
      arguments when optional list annotations occur. Use the helper both in
      production normalization and tests that inspect list-typed fields. In a
      before model validator, iterate cls.model_fields and wrap a dictionary
      value only when the corresponding annotation is list-like. Do not skip
      list annotations, do not access `annotation.__origin__` directly, and
      read the raw value from `values`, not undefined info.data.
    outputs:
      - {name: annotation-introspection-changes, type: object}

  - name: migrate-model-field-introspection
    description: >
      Replace __fields__ with model_fields on model classes or
      type(instance).model_fields. Treat each value as FieldInfo, not the v1
      ModelField API: use annotation rather than type_ or outer_type_, default
      for defaults, and json_schema_extra for custom metadata. Replace custom
      `Field(is_component=True)` metadata with
      `Field(json_schema_extra={"is_component": True})`, then read it from
      `field.json_schema_extra or {}`. Preserve declaration order because X12
      parsing and serialization are positional. Update every introspection
      site together so metadata writers and readers remain compatible.
    outputs:
      - {name: field-introspection-changes, type: object}

  - name: preserve-runtime-model-traversal
    description: >
      Rework serializers and tree walkers that used ModelField.name, type_, or
      shape. Iterate ordered model_fields names and inspect each actual
      attribute value at runtime. Traverse BaseModel instances, lists of model
      instances, and optional values without relying on removed field internals.
      Preserve distinctions between segment models and nested groups, preserve
      output order, and ensure Decimal, date, time, enum, delimiter, and
      component or repetition formatting remains byte-for-byte equivalent.
      Test both newline and compact output paths when they exist.
    outputs:
      - {name: traversal-changes, type: object}

  - name: annotate-overridden-model-fields
    description: >
      Search the entire package for subclasses that assign to an inherited
      model field without a type annotation. Pydantic v2 rejects declarations
      such as `segment_name = X12SegmentName.CR5` when the base class defines
      segment_name as a field. Add the intended annotation, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`, without changing the
      value. Fix all occurrences rather than only the first traceback and rerun
      imports after each batch.
    outputs:
      - {name: field-override-changes, type: object}

  - name: migrate-serialization-and-schema-calls
    description: >
      Replace BaseModel.dict with model_dump and schema with model_json_schema,
      preserving exclude, exclude_none, exclude_unset, alias, and serialization
      options. Replace other renamed model APIs only after checking their v2
      semantics. Update recursive utilities consistently, including hasattr
      guards. Use model_dump in parsers, CLI output, adjustment logic, and
      delimiter serialization where appropriate. Verify JSON encoding of Enum,
      Decimal, date, and datetime values; mode="python" versus mode="json" is a
      behavioral choice, not a mechanical rename.
    outputs:
      - {name: serialization-changes, type: object}

  - name: migrate-parser-model-discovery
    description: >
      Update dynamic parser discovery from `hasattr(class_value, "schema")` and
      `class_value.schema()` to an explicit BaseModel subclass check where
      possible and `model_json_schema()`. Exclude BaseModel itself and guard
      issubclass calls to actual classes. Update parser field-name and
      multi-value discovery to model_fields, annotation helpers, and
      json_schema_extra. Preserve field order and transaction-model detection
      using required header and footer properties. Exercise create_parser for
      every supported transaction family, not just one imported module.
    outputs:
      - {name: parser-discovery-changes, type: object}

  - name: audit-coercion-and-constraint-changes
    description: >
      Once collection succeeds, compare v1 expectations with v2 behavior for
      coercion and constraints: numbers to strings, iterable-to-dict behavior,
      unions, enums, Decimal scale, date parsing, regex or pattern handling,
      constrained types, and error types. Prefer explicit before validators or
      accurate annotations when legacy input coercion is part of the public
      behavior. Do not weaken constraints globally. Run representative valid
      and invalid model constructions, resource round trips, and X12 string
      comparisons.
    outputs:
      - {name: coercion-audit, type: object}

  - name: run-import-and-collection-gates
    description: >
      After each migration layer, run compileall or equivalent syntax checks,
      import the foundational settings and model modules, import both versioned
      segment modules, and execute pytest collection without truncating its exit
      status. Resolve errors in order: syntax, imports, model construction,
      collection, then executed tests. Collection success is only a gate, not
      completion. Record warning categories because they often reveal remaining
      v1 APIs, but prioritize errors that prevent tests from running.
    outputs:
      - {name: collection-gate-results, type: object}

  - name: inspect-every-mechanical-diff
    description: >
      After any codemod, script, search-and-replace, formatter, or bulk edit,
      inspect the complete git diff before testing further. Look specifically
      for values changed to info.data in model validators, undefined names,
      duplicate imports, field_validator shadowing, reversed conditions,
      misplaced classmethod decorators, malformed ConfigDict calls, changed
      indentation, and replacements inside unrelated functions. Use grep to
      search for the known bad fragments. Revert collateral edits and migrate
      the affected code deliberately. A script reporting files changed is not
      evidence that those changes are correct.
    outputs:
      - {name: diff-review, type: object}

  - name: iterate-on-focused-failures
    description: >
      Run the smallest meaningful failing test module without hiding the exit
      code, fix the underlying migration contract, rerun that test, then rerun
      collection to catch cross-module effects. Group failures by cause rather
      than patching assertions individually. For this style of repository,
      prioritize foundational model tests, versioned segment tests, reusable
      validation tests, parser creation, loop initialization, repeatable
      segments, model reader tests, and resource round trips. Keep a short
      failure ledger so fixed categories are not accidentally regressed.
    outputs:
      - {name: focused-test-results, type: object}

  - name: run-the-full-suite
    description: >
      After focused tests and collection pass, run the repository's canonical
      full suite with no `-x`, output truncation, or ignored exit status. Compare
      the number collected and passed with the repository evidence; investigate
      unexpectedly missing tests even when pytest exits zero. Run the configured
      linter or formatter check if available and inspect git diff and status.
      Repeat until the full suite passes from a fresh process.
    outputs:
      - {name: full-suite-result, type: object}

  - name: perform-forbidden-shortcut-audit
    description: >
      Search production code and dependency metadata for pydantic.v1,
      remaining v1-only imports, BaseSettings from pydantic, root_validator,
      validator, SHAPE_LIST, class Config, __fields__, field_info, type_,
      outer_type_, deprecated dict or schema calls, and obsolete dependency
      pins. Inspect changed function bodies to prove none were emptied,
      replaced with pass, commented out, or stripped of validation. Confirm no
      tests were skipped or deleted and no warning filters conceal migration
      problems. A green suite cannot override this gate: pydantic.v1 imports
      and emptied function bodies are explicit failure conditions.
    outputs:
      - {name: shortcut-audit, type: object}

  - name: verify-behavior-beyond-test-status
    description: >
      Manually exercise high-risk behavior not guaranteed by aggregate test
      status: settings loaded from environment, omitted Optional fields,
      invalid data rejected by inherited validators, repeatable dictionary
      values wrapped only for list fields, component and repetition delimiters,
      model discovery, recursive segment counting, CLI model serialization,
      parser creation, and parse-to-x12 resource round trips. Compare concrete
      outputs with pre-migration fixtures or documented examples. Confirm
      custom field metadata is both written and read through
      json_schema_extra.
    outputs:
      - {name: behavior-verification, type: object}

  - name: report-completion
    description: >
      Report the dependency ranges and major API migrations, the exact full
      test command and pass count, focused behavioral checks, and any remaining
      non-blocking warnings. State explicitly that the shortcut audit found no
      pydantic.v1 imports and no emptied or disabled function bodies. Mention
      files intentionally left unchanged and any environmental limitation.
      Do not claim completion if collection, the full suite, shortcut audit, or
      behavior verification is incomplete.
    inputs:
      - {name: full-suite-result, type: object}
      - {name: shortcut-audit, type: object}
      - {name: behavior-verification, type: object}
    outputs:
      - {name: migration-report, type: object}
```