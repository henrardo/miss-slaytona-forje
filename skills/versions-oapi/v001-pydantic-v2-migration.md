---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "9e3ddb8a"
---

```yaml
# Completeness classification for the prior source skill:
# Mapped: its purpose is preserved and expanded in purpose.
# Mapped: both trigger_when entries are preserved and expanded.
# Mapped: both do_not_use_when entries are preserved.
# Mapped: all three anti_patterns are preserved, including the fixture-specific
# evidence that pydantic.v1 can pass 32 of 33 tests without being a migration.
# Mapped: establish-the-failure remains a distinct first execution step.
# Deliberate drop: the version-0 comments saying that no migration procedure had
# yet been distilled described the old empty scaffold, not migration behavior;
# version 1 now contains evidence-derived procedure and retaining those claims
# would be false.
# Deliberate drop: the old establish-the-failure sentence saying no steps had
# been distilled is obsolete for the same reason; its operational instructions
# to run the repository suite and read the first error are retained.
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so that
  imports, model construction, validation, parsing, serialization, generated
  schemas, and repository tests preserve intended behavior. Complete the
  migration without redirecting code to pydantic.v1, without deleting
  validation or other behavior, and without stopping after investigation.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - >
    Rewriting imports to pydantic.v1 so the old API keeps working. This passes
    32 of 33 tests in this fixture and is not a migration.
  - >
    Replacing a validator or any other function body with a bare return, pass,
    constant result, or no-op so the function still imports. The suite may go
    green while the behavior is gone.
  - Declaring the migration complete without running the repository's own full suite.
  - >
    Spending the entire attempt inventorying APIs without making edits. Use the
    first traceback to choose a migration slice, edit it, and immediately test it.
  - >
    Piping the primary test command through head, tail, grep, or another command.
    A pipeline can hide pytest's exit status and truncate the actionable traceback.
  - >
    Treating a command's displayed exit code as proof that tests passed when its
    output was piped or truncated.
  - >
    Assuming usages in tests are irrelevant. Tests reveal required public API,
    construction semantics, validation behavior, and compatibility expectations.
  - >
    Blindly replacing every old API name. Validator modes, Optional defaults,
    aliases, unions, equality, serialization, and coercion changed semantically
    and require behavior-aware edits.
  - >
    Updating only the first Field(const=True), class Config, parse_obj, or
    update_forward_refs occurrence. Inventory and migrate the complete production
    surface, then use tests to find semantic gaps.
  - >
    Editing generated templates merely because they contain words such as
    construct or schema. Distinguish Pydantic APIs from unrelated template filters,
    domain methods, and generated client code.
  - >
    Changing tests to accept broken production behavior. Modify tests only when
    the task explicitly requires Pydantic v2 expectations and the prior assertion
    encodes a genuinely changed external contract.
  - >
    Running broad automated substitutions without reviewing the diff for typing,
    decorator order, configuration inheritance, aliases, and validator signatures.
  - >
    Using a mistyped or stale repository path. Establish the current working
    directory once and run subsequent commands from that verified repository root.

steps:
  - name: establish-repository-root-and-state
    description: >
      Confirm the current directory, locate the repository root, inspect git
      status, and identify the project metadata and supported Python versions.
      Preserve unrelated user changes. Use the verified root for every later
      command rather than repeatedly spelling an absolute path that can be mistyped.
      Record the current Pydantic version with the repository's active interpreter.
    outputs:
      - name: repository-state
        type: object

  - name: establish-the-failure
    description: >
      Run the repository's own test suite and read the first complete error.
      Prefer the command documented by the project; otherwise run
      `python -m pytest -x -vv`. Do not pipe the command through `head`, `tail`,
      or `grep`, because that can report the pipeline consumer's status instead
      of pytest's and can hide the useful traceback. If terminal output is too
      large, redirect it to a file, preserve pytest's exit status, and read a
      bounded section from that file afterward. Distinguish collection failure,
      import failure, test failure, and absence of discovered tests.
    outputs:
      - name: first-error
        type: string
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object

  - name: inspect-project-constraints
    description: >
      Read pyproject.toml, setup.cfg, setup.py, requirements files, lockfiles,
      tox or nox configuration, and CI workflows as applicable. Determine where
      Pydantic is declared, whether the project must support only v2 or both major
      versions, and whether companion packages such as pydantic-settings are
      already available. Follow the requested compatibility target; do not
      introduce pydantic.v1 as an escape hatch.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-pydantic-surface
    description: >
      Search production code, tests, examples, and generation templates for
      Pydantic imports and v1 APIs. Include BaseModel, BaseSettings, Extra,
      class Config, Field arguments, validator, root_validator, parse_obj,
      parse_raw, from_orm, dict, json, schema, schema_json, copy, construct,
      __fields__, __fields_set__, update_forward_refs, GenericModel, constrained
      types, dataclasses, custom types, and direct ModelField access. Use searches
      precise enough to avoid confusing unrelated domain methods or Jinja filters
      with Pydantic APIs. Record every production occurrence before editing.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read the affected model modules rather than relying on search snippets.
      Map inheritance, aliases, discriminated unions, recursive and forward
      references, enums, custom validators, arbitrary types, extra-field policy,
      generated JSON schema hooks, and callers of model APIs. Read relevant tests
      to learn which construction, validation, serialization, and error behavior
      must survive. Tests are evidence, not irrelevant noise.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-a-small-migration-plan
    description: >
      Group findings into coherent slices: imports and dependencies, model
      configuration, fields and annotations, validators, parsing and serialization,
      forward references and generics, and semantic regressions. Start with the
      slice blocking test collection, then proceed through the remaining inventory.
      Plan concrete edits and tests; do not let planning consume the attempt without
      changing code.
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

  - name: migrate-imports-and-dependencies
    description: >
      Replace removed or relocated APIs with their native v2 homes. Import
      BaseModel, Field, ConfigDict, field_validator, model_validator, and related
      v2 APIs from pydantic as needed. Move BaseSettings usage to
      pydantic-settings only when the project uses settings models, and add the
      dependency consistently to project metadata and lockfiles. Use
      pydantic-extra-types for relocated specialist types only when required.
      Never redirect production or test imports to pydantic.v1.
    outputs:
      - name: import-and-dependency-edits
        type: list[string]

  - name: migrate-model-configuration
    description: >
      Replace v1 inner `class Config` declarations with `model_config =
      ConfigDict(...)` or an equivalent native v2 configuration that preserves
      inheritance and behavior. Translate common settings deliberately:
      `extra = Extra.allow|ignore|forbid` to `extra="allow"|"ignore"|"forbid"`;
      `allow_population_by_field_name` to `populate_by_name` or the installed
      v2 version's more specific validation-by-name setting;
      `orm_mode` to `from_attributes`;
      `schema_extra` to `json_schema_extra`;
      `allow_mutation=False` to `frozen=True`;
      `validate_all` to `validate_default`;
      and `anystr_strip_whitespace` to the corresponding string setting.
      Review arbitrary_types_allowed, use_enum_values, assignment validation,
      alias generation, protected namespaces, and ignored types instead of
      assuming old names still work. Remove imports such as Extra when no longer
      needed.
    outputs:
      - name: configuration-edits
        type: list[string]

  - name: migrate-field-definitions
    description: >
      Replace removed Field arguments while preserving constraints and generated
      schema. Translate `const=True` into a `Literal[...]` annotation with the
      intended default; for enum discriminators use a Literal of the exact enum
      member or wire value expected by validation. Translate `regex` to `pattern`,
      `min_items` and `max_items` to `min_length` and `max_length`, and move
      arbitrary JSON Schema additions into `json_schema_extra`. Review aliases,
      validation_alias, serialization_alias, discriminator, default factories,
      strictness, and excluded or frozen fields individually.
    outputs:
      - name: field-edits
        type: list[string]

  - name: preserve-required-and-optional-semantics
    description: >
      Audit every Optional or union-with-None annotation touched by the migration.
      In Pydantic v2, `Optional[T]` without a default is nullable but still
      required. Add `= None` only where v1 behavior and project tests show that
      omission was accepted; retain required nullable fields where omission must
      fail. Preserve default factories and distinguish missing, explicit null,
      and defaulted values because serialization and fields-set behavior depend
      on that distinction.
    outputs:
      - name: optionality-edits
        type: list[string]

  - name: migrate-field-validators
    description: >
      Convert `@validator` to `@field_validator` where appropriate. Map `pre=True`
      to `mode="before"` and preserve `always` behavior using defaults and
      validate_default configuration where necessary. Replace v1 signature
      parameters such as `values`, `field`, and `config` with supported v2
      signatures, using ValidationInfo and `info.data`, `info.field_name`, or
      `info.config` as appropriate. Preserve decorator order and classmethod
      behavior. Keep the actual validation logic intact; never empty a validator
      body merely to make import or signature errors disappear.
    outputs:
      - name: field-validator-edits
        type: list[string]

  - name: migrate-model-and-root-validators
    description: >
      Convert `@root_validator` to `@model_validator` with the correct mode.
      A before validator generally receives raw input and returns input data;
      an after validator generally receives the model instance and returns that
      instance. Account for assignment validation if enabled. Preserve ordering,
      cross-field checks, mutation, raised error types, and skip-on-failure intent.
      If a deprecated decorator is temporarily left in place while isolating a
      failure, do not call the migration complete until the native v2 path is
      implemented and tested.
    outputs:
      - name: model-validator-edits
        type: list[string]

  - name: migrate-model-entry-points
    description: >
      Replace `Model.parse_obj(data)` with `Model.model_validate(data)`,
      `parse_raw` with `model_validate_json` when input is JSON, and `from_orm`
      with `model_validate` plus `from_attributes=True`. Replace Pydantic v1
      `construct` with `model_construct` only when intentionally bypassing
      validation. Do not alter unrelated methods or template filters named parse,
      construct, copy, dict, json, or schema.
    outputs:
      - name: entry-point-edits
        type: list[string]

  - name: migrate-serialization-and-copying
    description: >
      Replace model `dict` calls with `model_dump`, `json` with
      `model_dump_json`, and `copy` with `model_copy` where they are Pydantic
      methods. Preserve include, exclude, by_alias, exclude_unset,
      exclude_defaults, exclude_none, round-trip, and update behavior. Check
      serializer output rather than assuming method renaming is behaviorally
      identical, especially for nested subclasses, enums, bytes, datetimes,
      computed fields, and custom encoders. Use field_serializer,
      model_serializer, or v2 serializer configuration when old json_encoders or
      overridden dict/json behavior no longer produces the required output.
    outputs:
      - name: serialization-edits
        type: list[string]

  - name: migrate-schema-generation
    description: >
      Replace `schema()` with `model_json_schema()` and `schema_json()` with an
      explicit serialization of the generated schema where needed. Migrate
      `schema_extra` and custom schema hooks to native v2 mechanisms. Compare
      aliases, required fields, nullable representation, discriminator mappings,
      references, definitions, examples, and additional-properties behavior
      against project expectations. Generated schema is part of the behavior for
      OpenAPI-oriented repositories.
    outputs:
      - name: schema-edits
        type: list[string]

  - name: migrate-model-introspection
    description: >
      Replace class-level `__fields__` access with `model_fields` and instance
      `__fields_set__` access with `model_fields_set`. Review code that relies on
      ModelField internals because v2 field metadata types differ. Prefer public
      v2 APIs for annotations, defaults, aliases, requiredness, and metadata.
      Update tests or callers only after confirming the new access preserves the
      intended public behavior.
    outputs:
      - name: introspection-edits
        type: list[string]

  - name: migrate-forward-references-and-recursive-models
    description: >
      Replace no-argument `update_forward_refs()` calls with `model_rebuild()`
      where explicit rebuilding is still necessary. Prefer resolvable modern type
      annotations and rebuild only after referenced types exist. For recursive,
      mutually dependent, or dynamically defined models, verify that the namespace
      is available and inspect model_rebuild failures rather than deleting the
      call. Exercise actual validation of recursive data after imports succeed.
    outputs:
      - name: forward-reference-edits
        type: list[string]

  - name: migrate-generics-custom-types-and-dataclasses
    description: >
      If present, replace GenericModel patterns with BaseModel plus Generic as
      supported by v2, and verify parametrized model behavior without relying on
      unsafe parametrized isinstance checks. Migrate custom types from
      `__get_validators__` or `__modify_schema__` to the appropriate core-schema
      and JSON-schema hooks when required. Review Pydantic dataclass configuration,
      TypeAdapter use, RootModel replacements for `__root__`, and constrained
      type definitions. Test each specialist path directly because mechanical
      substitutions are insufficient.
    outputs:
      - name: specialist-edits
        type: list[string]

  - name: run-focused-tests-after-each-slice
    description: >
      After each coherent edit, run the narrowest test module or test node that
      covers it, using an unpiped command and checking the real exit code. For a
      collection error, first verify that the affected module imports, then run
      its tests. Read the complete next traceback, classify it as another v1 API
      occurrence or a semantic v2 difference, and make the smallest behavior-
      preserving correction. Continue executing tools and edits; do not end the
      attempt with a statement about what should be checked next.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: investigate-v2-semantic-differences
    description: >
      When renamed APIs are exhausted but tests still fail, check Pydantic v2
      semantics explicitly: required Optional fields, stricter or changed type
      coercion, union selection, dictionary acceptance, iterable-to-dict removal,
      equality no longer matching plain dictionaries, private attributes,
      subclass serialization, alias values, enum handling, default validation,
      regex engine differences, input type preservation, and TypeError escaping
      validators. Preserve the project's intended contract rather than globally
      weakening validation to emulate every v1 coercion.
    outputs:
      - name: semantic-fixes
        type: list[string]

  - name: inspect-and-review-the-diff
    description: >
      Review git diff and repeat the Pydantic inventory searches. Confirm that
      edits are limited to the migration, all production v1 usages are resolved
      or consciously justified, imports are clean, and no function body was
      emptied. Specifically search for `pydantic.v1`, bare validator returns,
      newly introduced pass statements, commented-out checks, and broad test
      deletions. Review automated replacements line by line.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-full-test-suite
    description: >
      Run the repository's complete documented test suite without output-truncating
      pipelines. A successful import or focused test is not completion. Verify the
      number of collected and passed tests, the command's actual zero exit status,
      and any warnings. Treat zero collected tests as a failure unless the project
      intentionally has no tests. Fix failures and repeat until the full suite
      passes.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Run the repository's configured type checker, linter, formatter check,
      packaging or build command, and any schema or generated-code checks that CI
      uses. Resolve migration-induced warnings and errors, especially Pydantic
      deprecation warnings. Do not invent unrelated cleanup when a gate exposes
      pre-existing failures; record those separately and verify the migration did
      not worsen them.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Confirm with the active interpreter that Pydantic major version 2 is in use.
      Search the final production tree for `pydantic.v1` and unresolved v1 APIs.
      Verify representative valid and invalid model inputs, alias-based population,
      serialization, and generated schema for the migrated code paths. The final
      state must use native v2 behavior and retain validation logic, not merely
      import successfully.
    outputs:
      - name: native-v2-verification
        type: object

  - name: report-completion-with-evidence
    description: >
      Summarize changed migration areas, dependency changes, and any intentional
      behavior decisions. Report the exact full-suite and quality-gate commands,
      exit outcomes, and test counts. Mention residual warnings or unrun checks
      plainly. Do not claim completion unless the full suite passed under
      Pydantic v2 and the final searches found neither pydantic.v1 shims nor
      behavior-erasing no-op implementations.
    outputs:
      - name: migration-report
        type: object
```