---
name: pydantic-v2-migration
description: Procedure distilled from graded migration attempts for upgrading a Python codebase from Pydantic v1 to native Pydantic v2 APIs while preserving validation and serialization behavior. Use when imports, settings, validators, model fields, constraints, or tests fail after a Pydantic v2 upgrade.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "81e12f5c"
---

```yaml
# Version 1 adds migration knowledge distilled from trace 81e12f5c.
# Deliberate drop from version 0: the statement that the procedure contains no
# migration knowledge is now false because this revision incorporates the
# failed attempt's repository evidence and corrective execution procedure.
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs so
  that the repository's own test suite passes, without shimming pydantic.v1,
  bypassing validation, or deleting behavior to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, settings, field, schema, or validator errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings from pydantic, class Config, validator, root_validator, __fields__, ModelField, or removed Field arguments
  - A dependency manifest still pins pydantic below version 2 while the requested task is a Pydantic v2 migration

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working. This can make nearly the entire fixture pass while avoiding the requested migration.
  - Adding a compatibility module that merely re-exports pydantic.v1 APIs under new local names.
  - Replacing a validator body with a bare return, pass, unconditional success, or other no-op so the function still imports. A green suite does not justify deleting behavior.
  - Removing validators, constraints, extra-field rejection, immutability, serialization logic, or settings behavior merely to suppress failures.
  - Mechanically renaming decorators without adapting their signatures, input phase, return type, and access to sibling fields.
  - Converting every root validator identically; before and after model validators receive different inputs and require different implementations.
  - Treating deprecation warnings as proof of migration completeness while deprecated v1-style APIs remain in production code.
  - Performing a repository-wide blind replacement before understanding project-specific base models and shared validator helpers.
  - Exploring the repository repeatedly without making edits, running tests, or using failures to drive the next change.
  - Ending the task after inspection or import success without changing the code and running the suite.
  - Declaring the migration complete without running the repository's full test suite under an installed Pydantic v2 release.
  - Updating source imports but leaving packaging metadata pinned to pydantic below version 2.
  - Assuming Optional[T] remains optional without a default; in Pydantic v2 it is required unless a default such as None is supplied.
  - Assuming deprecated dict, parse_obj, json, copy, __fields__, or ModelField behavior is unchanged in code that depends on field metadata or ordering.
  - Silencing all warnings globally instead of removing actionable Pydantic migration warnings.
  - Modifying tests to accept broken behavior unless the task explicitly requires a test API migration and the original behavioral expectation remains intact.

steps:
  - name: establish-the-failure
    description: >
      Run the repository's own full test suite immediately in the intended
      environment and record the command, installed Pydantic version, collection
      errors, first traceback, and pass/fail count. If collection aborts, retain
      that as the baseline rather than reporting zero tests as useful coverage.
      Use the project's documented runner when available; otherwise start with
      pytest. Do not spend the whole attempt inventorying files before obtaining
      this executable baseline.
      # Deliberate drop from version 0: the claim that no procedural step has
      # been distilled is obsolete; this version contains evidence-based steps.
    outputs:
      - name: first-error
        type: "string"
      - name: baseline-result
        type: "object"

  - name: confirm-the-target-environment
    description: >
      Inspect pyproject.toml, requirements files, lock files, CI workflows, and
      supported Python versions. Confirm that tests are actually executing with
      Pydantic 2.x by printing pydantic.__version__. Read migration-specific
      requirement files before changing dependencies; they may identify required
      companion packages or known blockers. Record the normal test, lint, and
      packaging commands. If the environment still has Pydantic v1, install or
      select the repository's intended v2 dependency set before interpreting
      migration failures.
    outputs:
      - name: environment-inventory
        type: "object"

  - name: inventory-v1-usage
    description: >
      Search production code, tests, documentation examples, and dependency
      metadata for Pydantic v1 surfaces. Include imports of BaseSettings,
      validator, root_validator, GenericModel, ModelField, SHAPE_* constants,
      pydantic.fields internals, and pydantic.v1; class Config; __fields__;
      field_info.extra; parse_obj, from_orm, dict, json, copy, schema, and
      construct; Field arguments such as regex, min_items, max_items, const, and
      allow_mutation; validator options such as pre, always, each_item, and
      allow_reuse; custom __get_validators__ types; and Optional annotations
      lacking defaults. Group results by shared infrastructure, model families,
      tests, and documentation. The search is a checklist, not a substitute for
      editing and testing.
    outputs:
      - name: migration-inventory
        type: "object"

  - name: inspect-shared-model-contracts
    description: >
      Read the project's base models, settings class, shared validator helpers,
      parser entry points, and serializers before changing leaf models. Record
      behavior that must survive: extra-field policy, enum storage, aliases,
      assignment validation, immutability and hashing, default validation,
      environment-variable case handling, ORM or attribute loading, arbitrary
      type handling, field order, custom metadata, repeatable-list coercion,
      date and Decimal formatting, and nested serialization order. Use existing
      tests and representative fixtures as the source of truth. In this X12-style
      repository, pay special attention to delimiter models, segment rendering,
      segment-group traversal, component-versus-repetition metadata, and the
      validator that wraps a bare repeatable segment dictionary in a list.
    outputs:
      - name: preserved-contracts
        type: "list[object]"

  - name: update-dependency-metadata
    description: >
      Change every authoritative runtime dependency declaration from the
      Pydantic v1 pin to an appropriate Pydantic v2 range, normally
      pydantic>=2,<3 unless the repository specifies a tighter supported floor.
      Move BaseSettings support to pydantic-settings and add that package to
      runtime dependencies when settings are part of the public package. Update
      requirement and lock files consistently rather than changing only the
      active virtual environment. Remove comments claiming that a future v2
      migration is still pending once the migration is implemented.
    outputs:
      - name: dependency-changes
        type: "list[string]"

  - name: migrate-model-configuration
    description: >
      Replace inner class Config declarations with model_config = ConfigDict(...)
      and import ConfigDict from pydantic. Translate settings configuration to
      SettingsConfigDict from pydantic_settings. Map allow_mutation=False to
      frozen=True, orm_mode=True to from_attributes=True,
      allow_population_by_field_name=True to populate_by_name=True, and preserve
      extra, use_enum_values, validate_assignment, arbitrary_types_allowed,
      alias behavior, and string normalization settings deliberately. For enum
      defaults whose stored value must be the enum value, consider
      validate_default=True because use_enum_values acts during validation.
      Resolve inherited configuration at shared base classes first so leaf models
      do not duplicate or contradict it.
    outputs:
      - name: configuration-migrations
        type: "list[object]"

  - name: migrate-settings
    description: >
      Import BaseSettings and SettingsConfigDict from pydantic_settings rather
      than pydantic. Preserve case sensitivity, environment prefixes, dotenv
      behavior, nested delimiters, aliases, and cached construction. Replace
      removed Field(regex=...) constraints with Field(pattern=...) or an
      equivalent annotated constraint. Instantiate the settings object under
      controlled environment values and verify both accepted and rejected cases,
      not merely that the module imports.
    outputs:
      - name: settings-result
        type: "object"

  - name: migrate-field-definitions
    description: >
      Replace removed or renamed Field arguments while retaining the original
      constraint: regex becomes pattern; min_items and max_items become
      min_length and max_length for collections; const becomes Literal where
      appropriate; and allow_mutation moves to model configuration or supported
      field semantics. Move custom Field extras into json_schema_extra, for
      example json_schema_extra={"is_component": True}, rather than relying on
      arbitrary keyword arguments. Review constrained-type factories and strict
      coercion behavior against Pydantic v2 signatures. Do not weaken bounds,
      decimal precision, string lengths, literals, or list cardinality simply
      because the old declaration no longer imports.
    outputs:
      - name: field-definition-changes
        type: "list[object]"

  - name: correct-requiredness-and-defaults
    description: >
      Audit Optional and nullable fields explicitly. In Pydantic v2, Optional[T]
      or T | None without a default accepts None but remains required; add
      = None only where omission was valid under the repository's v1 behavior.
      Preserve required nullable fields where omission must still fail. Review
      default factories and validators that relied on always=True; use
      validate_default configuration or a model validator only when defaults
      genuinely require validation. Add focused construction checks for omitted,
      None, valid, and invalid values on representative models.
    outputs:
      - name: requiredness-changes
        type: "list[object]"

  - name: migrate-field-validators
    description: >
      Convert @validator to @field_validator. Map pre=True to mode="before";
      use the default after mode otherwise. Remove allow_reuse because v2 no
      longer requires it. Add @classmethod where appropriate. Validators receive
      the candidate value and may receive ValidationInfo; replace the old values
      dictionary with info.data and old field/config parameters with
      info.field_name and model configuration access. Remember that info.data
      only contains fields already validated according to declaration order.
      Replace each_item=True with validation on the collection or constraints on
      the item type, preserving whether errors belong to individual elements.
      If a project exposes a shared validator decorator helper, migrate the helper
      and every validator signature together rather than leaving v1 call
      conventions hidden behind a renamed alias.
    outputs:
      - name: field-validator-changes
        type: "list[object]"

  - name: migrate-before-root-validators
    description: >
      Convert @root_validator(pre=True) to
      @model_validator(mode="before"). Keep it a class method that accepts and
      returns the raw input. Do not assume the input is always a mutable dict:
      guard non-dictionary inputs, and copy mappings before mutation when caller
      data should not be modified. Replace cls.__fields__ inspection with
      cls.model_fields and inspect each FieldInfo annotation using typing helpers
      such as get_origin and get_args. Unwrap Annotated and optional unions as
      needed before deciding whether a field is list-like. For repeatable segment
      coercion, wrap only a bare dictionary supplied for a list field; preserve
      existing lists, None, missing values, and unrelated dictionaries.
    outputs:
      - name: before-validator-changes
        type: "list[object]"

  - name: migrate-after-root-validators
    description: >
      Convert post @root_validator logic to @model_validator(mode="after") and
      rewrite it around the constructed model instance. Access fields through
      self, perform the same cross-field checks or derived calculations, and
      return self. Do not keep treating the input as a values dictionary. When
      assignment validation or construction pathways can pass different forms,
      handle them intentionally. Preserve exact business rules such as mutually
      required fields, balancing totals, segment counts, control numbers, and
      date relationships. Add a failing and passing example for each distinct
      cross-field rule before moving on.
    outputs:
      - name: after-validator-changes
        type: "list[object]"

  - name: preserve-validation-errors
    description: >
      Review validator exceptions under Pydantic v2. Raise ValueError,
      AssertionError, or PydanticCustomError for validation failures as
      appropriate; do not rely on TypeError being converted into a ValidationError
      because v2 propagates TypeError from validators. Keep meaningful messages
      and error locations where tests or callers depend on them. Fix incorrect
      validator signatures rather than catching broad exceptions around model
      construction.
    outputs:
      - name: validation-error-checks
        type: "list[object]"

  - name: replace-field-internals
    description: >
      Remove dependencies on pydantic.fields internals such as SHAPE_LIST,
      ModelField, field.shape, field.type_, and field_info.extra. Use
      model_fields, FieldInfo.annotation, typing.get_origin/get_args, and
      FieldInfo.json_schema_extra instead. Access model_fields on the class, not
      an instance, to avoid deprecation warnings. Account for Optional,
      Annotated, union, and collection annotations rather than checking only
      get_origin(annotation) is list when aliases or wrappers are possible.
      Keep field declaration order wherever output format is positional.
    outputs:
      - name: field-introspection-changes
        type: "list[object]"

  - name: migrate-model-entry-points
    description: >
      Replace behavioral uses of parse_obj with model_validate, from_orm with
      model_validate plus from_attributes configuration, construct with
      model_construct, copy with model_copy, schema with model_json_schema,
      dict with model_dump, and json with model_dump_json. Do not perform
      cosmetic replacements where callers depend on non-JSON Python objects:
      choose model_dump mode="python" or mode="json" deliberately. Preserve
      include, exclude, by_alias, exclude_none, exclude_unset, and exclude_defaults
      options. Update tests or public examples that invoke removed entry points,
      but retain compatibility wrappers only when the package's public API
      explicitly promises them and those wrappers use native v2 internals.
    outputs:
      - name: model-entry-point-changes
        type: "list[object]"

  - name: preserve-custom-serialization
    description: >
      Test custom text or wire-format serializers independently of generic model
      dumping. In positional formats, iterate class model_fields in declaration
      order and fetch runtime values, or otherwise use a method that demonstrably
      preserves order. Read custom metadata from json_schema_extra. Preserve
      formatting for datetime, date, time, Decimal scale, enums, None, repeated
      values, components, custom delimiters, and trailing empty elements. When
      traversing nested segment groups, use runtime values or safely unwrap field
      annotations instead of relying on removed ModelField.type_. Do not serialize
      model configuration or private attributes as data fields.
    outputs:
      - name: serialization-checks
        type: "list[object]"

  - name: migrate-custom-types-and-generics
    description: >
      If the inventory found custom types using __get_validators__,
      __modify_schema__, GenericModel, or v1 schema hooks, migrate them to native
      v2 core-schema and JSON-schema hooks or BaseModel generics as required.
      Implement __get_pydantic_core_schema__ and
      __get_pydantic_json_schema__ only for types that need customization; prefer
      standard Annotated constraints when sufficient. Exercise both validation
      and generated JSON schema for each migrated custom type. Skip this step
      only when the inventory proves the repository has no such usage.
    outputs:
      - name: custom-type-result
        type: "object"

  - name: run-focused-tests-after-each-layer
    description: >
      After each coherent layer, run the smallest relevant tests: settings tests
      after settings changes, shared model and segment tests after base-model
      changes, then one transaction family at a time after validator changes.
      Stop on the first new failure, read the complete traceback and validation
      error details, fix the underlying semantic mismatch, and rerun the same
      test until green. Keep a failure ledger so repeated errors are addressed at
      their shared source instead of patched separately across dozens of models.
      Confirm that expected-invalid fixtures still fail; passing only valid
      fixtures can conceal deleted validation.
    outputs:
      - name: focused-test-results
        type: "list[object]"

  - name: search-for-migration-residue
    description: >
      Repeat the v1 API inventory after edits. Production code must contain no
      pydantic.v1 import or equivalent compatibility redirection. Investigate
      every remaining BaseSettings-from-pydantic import, @validator,
      @root_validator, class Config, __fields__, pydantic.fields internal,
      SHAPE_* constant, removed Field keyword, and deprecated model method.
      Distinguish harmless prose mentioning v1 from executable residue. Run
      imports with deprecation warnings visible and eliminate actionable Pydantic
      warnings rather than suppressing them.
    outputs:
      - name: residue-report
        type: "object"

  - name: audit-the-diff-for-behavior-deletion
    description: >
      Inspect git diff before the final suite. Compare every changed validator
      and serializer with its original body and preserved-contract inventory.
      Reject any change that empties a function body, replaces logic with an
      unconditional return, removes a constraint without an equivalent, broadly
      catches validation errors, or skips a failing code path. Also reject any
      pydantic.v1 import, local v1 re-export, or dependency pin that permits the
      implementation to keep running solely on the old API. Revert unrelated
      edits and verify tests were not weakened to hide regressions.
    outputs:
      - name: behavior-audit
        type: "object"

  - name: run-full-quality-gates
    description: >
      Run the complete test suite under Pydantic v2, followed by the repository's
      configured lint, formatting, type-checking, and packaging or import checks.
      If the full suite exposes interactions absent from focused tests, return to
      the responsible migration layer, fix it, rerun focused tests, and then
      rerun the full suite. Record actual commands, Pydantic version, collected
      test count, pass count, failures, warnings, and skipped tests. Zero
      collected tests, collection aborts, or an environment still using
      Pydantic v1 are failures, not successful validation.
    outputs:
      - name: full-quality-result
        type: "object"

  - name: verify-representative-behavior
    description: >
      Exercise representative valid and invalid models outside broad suite
      summaries. Verify settings loading; forbidden extras; frozen-model behavior;
      omitted versus nullable fields; field and cross-field validation;
      repeatable-segment wrapping; custom metadata lookup; model validation and
      dumping; and exact wire-format serialization with default and custom
      delimiters. Compare serialized output to stable fixtures where available.
      This catches migrations that import and pass shallow tests while changing
      domain behavior.
    outputs:
      - name: behavioral-verification
        type: "list[object]"

  - name: report-completion-with-evidence
    description: >
      Summarize dependency changes, native v2 API migrations, preserved behavior,
      tests and quality gates run, final counts, and any remaining warnings or
      risks. State explicitly that no pydantic.v1 shim was introduced and no
      validator or function body was emptied to obtain passing tests. If any
      tests cannot run, report the exact blocker and do not claim completion.
      Leave the working tree with the implementation changes present; inspection
      without edits is not a completed migration.
    outputs:
      - name: migration-report
        type: "object"
```