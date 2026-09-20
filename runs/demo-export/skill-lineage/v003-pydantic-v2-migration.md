---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces:
      - "9e3ddb8a"
      - "d2ac33d9"
---

```yaml
# Completeness classification for the prior source skill:
# Mapped: the prior frontmatter name, description, AIP spec, and schemaId are
# preserved. The AIP version changed from 2 to 3 because the harness explicitly
# requires version 3. Trace 9e3ddb8a is preserved and trace d2ac33d9 is added.
# Mapped: purpose retains native-v2 migration, behavioral preservation, the ban
# on pydantic.v1, the ban on behavior-erasing no-ops, and the requirement to
# continue beyond investigation.
# Mapped: all four trigger_when entries are preserved.
# Mapped: both do_not_use_when entries are preserved.
# Mapped: every prior anti-pattern is preserved, including the fixture-specific
# evidence that pydantic.v1 can pass 32 of 33 tests without being a migration.
# Mapped: establish-repository-root-and-state remains a distinct step.
# Mapped: establish-the-failure remains a distinct step, including unpiped test
# execution, complete traceback capture, real exit-status checking, and
# classification of collection/import/test/zero-discovery outcomes.
# Mapped: inspect-project-constraints remains a distinct step.
# Mapped: inventory-the-pydantic-surface remains a distinct step and retains
# every named v1 API category from the prior source.
# Mapped: inspect-model-relationships-and-public-behavior remains a distinct step.
# Mapped: form-a-small-migration-plan remains a distinct step and now imposes an
# explicit edit gate so another attempt cannot stop after planning.
# Mapped: each of the thirteen prior migration execution steps remains distinct:
# imports/dependencies, configuration, fields, required/optional semantics,
# field validators, model/root validators, entry points, serialization/copying,
# schema generation, introspection, forward references, specialist model types,
# and semantic differences.
# Mapped: the prior requirement to read native-v2-api-migrations.md is preserved
# when that reference is present; the essential migration rules are also
# compiled inline so execution is not blocked if the reference is unavailable.
# Mapped: run-focused-tests-after-each-slice remains distinct and retains the
# instruction not to end a turn by merely announcing the next check.
# Mapped: inspect-and-review-the-diff remains distinct, including searches for
# pydantic.v1, emptied bodies, pass statements, disabled checks, and test deletion.
# Mapped: run-the-full-test-suite remains distinct, including real exit status,
# test counts, warnings, and zero-tests-as-failure.
# Mapped: run-project-quality-gates remains distinct.
# Mapped: perform-final-native-v2-verification remains distinct.
# Mapped: report-completion-with-evidence remains distinct.
# Mapped: all prior outputs are retained under their corresponding steps.
# Deliberate drop: none of the operational source procedure was dropped.
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so that
  imports, model construction, validation, parsing, serialization, generated
  schemas, and repository tests preserve intended behavior. Complete the
  migration without redirecting imports to pydantic.v1, without deleting or
  neutralizing validation or other function behavior, and without stopping
  after searches, investigation, or planning.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
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
    constant result, ellipsis, or no-op so the function still imports. The suite
    may go green while the behavior is gone, and this task explicitly rejects it.
  - Declaring the migration complete without running the repository's own full suite.
  - >
    Spending the entire attempt inventorying APIs without making edits. Use the
    first traceback to choose a migration slice, edit it, and immediately test it.
  - >
    Ending an execution turn after stating a plan, summary, or proposed next
    search. Once the blocking failure is understood, perform an actual edit and
    run a validating command in the same attempt.
  - >
    Piping the primary test command through head, tail, grep, tee, or another
    command without preserving pytest's status. A pipeline can hide pytest's
    exit code or truncate the actionable traceback.
  - >
    Treating a displayed exit code as proof that tests passed when output was
    piped, truncated, or produced by a downstream command.
  - >
    Assuming usages in tests are irrelevant. Tests reveal required public API,
    construction semantics, validation behavior, and compatibility expectations.
  - >
    Blindly replacing every old API name. Validator modes, Optional defaults,
    aliases, unions, equality, serialization, schema output, and coercion changed
    semantically and require behavior-aware edits.
  - >
    Updating only the first Field(const=True), class Config, parse_obj, or
    update_forward_refs occurrence. Inventory and migrate the complete production
    surface, then use tests to find semantic gaps.
  - >
    Editing generated templates merely because they contain words such as
    construct, copy, dict, json, or schema. Distinguish Pydantic APIs from
    unrelated template filters, domain methods, and generated client code.
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
  - >
    Treating deprecation warnings as proof of a native migration. Compatibility
    aliases may still execute under v2 while leaving the code on v1-style APIs.
  - >
    Fixing import-time errors by removing model fields, weakening types to Any,
    changing extra handling to permissive behavior, or catching and suppressing
    ValidationError without evidence that the public contract requires it.

steps:
  - name: establish-repository-root-and-state
    description: >
      Confirm the current directory and repository root with pwd and version-control
      metadata, then inspect git status before editing. Identify project metadata,
      the active Python interpreter, supported Python versions, and the exact
      installed Pydantic version. Preserve unrelated user changes. Run all later
      commands from this verified root instead of repeatedly using an error-prone
      absolute path.
    outputs:
      - name: repository-state
        type: object

  - name: establish-the-failure
    description: >
      Run the repository's documented test command. If none is documented, run
      `python -m pytest -x -vv` directly and inspect the first complete traceback.
      Do not pipe this primary command. If output must be captured, redirect both
      streams to a file, save the command's status, and inspect the file afterward;
      alternatively enable shell pipefail before tee and explicitly check
      PIPESTATUS. Record the command, actual status, collected-test count, and
      whether failure occurred during configuration, collection, import, or test
      execution. Treat zero collected tests as failure. For the known blocking
      error "`const` is removed, use `Literal` instead", proceed directly to the
      affected model after the minimum inventory needed to find every const field.
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
      Pydantic is declared, whether the requested target is native v2 only or
      genuine dual-major support, and whether companion packages such as
      pydantic-settings are available. Update dependency constraints and lock
      metadata when they still exclude v2. Follow the requested compatibility
      target; never introduce pydantic.v1 as an escape hatch.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-pydantic-surface
    description: >
      Search production code, tests, examples, and generation templates for
      Pydantic imports and v1 APIs. Include BaseModel, BaseSettings, Extra,
      class Config, ConfigDict, Field arguments, validator, root_validator,
      parse_obj, parse_raw, parse_file, from_orm, dict, json, schema, schema_json,
      copy, construct, __fields__, __fields_set__, update_forward_refs,
      GenericModel, __root__, constrained types, dataclasses, custom types,
      json_encoders, schema hooks, and direct ModelField access. Include removed
      Field arguments such as const, regex, min_items, max_items, unique_items,
      allow_mutation, and arbitrary extra keyword metadata. Use precise searches
      so unrelated domain methods and Jinja filters are not classified as
      Pydantic APIs. Record all production occurrences, but time-box this initial
      inventory: once the collection blocker and its sibling occurrences are
      known, make the first edit before pursuing optional searches.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read affected model modules, their bases, and relevant callers rather than
      relying on grep snippets. Map inheritance, aliases, discriminated unions,
      recursive references, enums, custom validators, arbitrary types, extra-field
      policy, generated JSON schema hooks, and calls to model APIs. Read tests
      that construct or serialize these models to identify behavior that must
      survive. Pay particular attention to aliased OpenAPI fields such as `in`,
      constant discriminator fields, and configuration inherited from shared
      base classes.
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
      forward references and generics, then semantic regressions. Put the slice
      blocking collection first. Name the exact files and focused tests for that
      slice. If `references/native-v2-api-migrations.md` exists, read the section
      matching the active slice; otherwise use the native-v2 rules compiled in
      the following steps. This plan is an execution checkpoint, not a stopping
      point: immediately perform the first edit and focused validation after
      producing it.
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
      Replace removed imports with native-v2 equivalents. Import BaseModel,
      Field, ConfigDict, field_validator, model_validator, TypeAdapter, and other
      supported APIs from pydantic itself. Move BaseSettings to pydantic-settings
      only when the project uses settings models, and add the dependency through
      the project's normal dependency manager. Replace GenericModel inheritance
      with BaseModel plus Generic where applicable. Do not import from
      pydantic.v1, do not retain a try/except fallback to pydantic.v1, and do not
      hide migration errors behind broad ImportError handling. After imports are
      changed, run a direct import of the affected package before broader tests.
    outputs:
      - name: import-and-dependency-edits
        type: list[string]

  - name: migrate-model-configuration
    description: >
      Replace inner `class Config` declarations with `model_config = ConfigDict(...)`
      while preserving inheritance and intent. Translate common settings:
      `extra = Extra.allow|ignore|forbid` to `extra="allow"|"ignore"|"forbid"`;
      `allow_population_by_field_name` to `populate_by_name`; `orm_mode` to
      `from_attributes`; `schema_extra` to `json_schema_extra`;
      `validate_all` to `validate_default`; `allow_mutation=False` to
      `frozen=True`; `anystr_strip_whitespace` to `str_strip_whitespace`; and
      renamed string length/case settings to their v2 names. Reassess removed
      options instead of silently dropping them. Preserve shared base-model
      configuration and verify extra handling, aliases, assignment validation,
      arbitrary types, enum values, and frozen behavior with tests.
    outputs:
      - name: configuration-edits
        type: list[string]

  - name: migrate-field-definitions
    description: >
      Replace every `Field(..., const=True)` with a `Literal[...]` annotation
      whose allowed value matches the old default, retaining aliases and
      defaults. For example, convert `name = Field(default="", const=True)` to
      `name: Literal[""] = ""`; for an enum discriminator, use
      `Literal[ParameterLocation.HEADER]` and retain `Field(alias="in")` if
      present. Import Literal from typing or typing_extensions according to the
      supported Python versions. Replace `regex` with `pattern`, `min_items` and
      `max_items` with `min_length` and `max_length`, and `allow_mutation=False`
      with a frozen field or model as appropriate. Move arbitrary JSON Schema
      metadata into `json_schema_extra`. For removed `unique_items`, select a
      type or validator that actually preserves uniqueness rather than deleting
      the constraint. Add explicit annotations to formerly unannotated model
      fields. Run an import check immediately after repairing collection blockers.
    outputs:
      - name: field-edits
        type: list[string]

  - name: preserve-required-and-optional-semantics
    description: >
      Audit every affected Optional, Any, and defaulted field. In v2,
      `Optional[T]` without a default is still required; add `= None` only when
      omission was accepted by the v1 model or required by the public contract.
      Conversely, do not add defaults merely to silence failures when a field is
      intended to remain required. Preserve default factories, validate defaults
      when needed, and verify aliases work for both input and output according to
      configuration. Test omitted, explicit-null, valid, and invalid values for
      representative fields.
    outputs:
      - name: optionality-edits
        type: list[string]

  - name: migrate-field-validators
    description: >
      Replace `@validator` with `@field_validator`, translating `pre=True` to
      `mode="before"` and keeping after-validation as the default. Replace
      `each_item=True` with validation expressed on the container's annotated
      item type or an explicit container validator. Replace v1 `field` and
      `config` arguments with `ValidationInfo` and `cls.model_fields[info.field_name]`
      where required. Preserve `always=True` behavior deliberately using
      `validate_default`, defaults, or an appropriate mode. Confirm decorator
      order and signatures, especially when `@classmethod` is present. Keep the
      complete validation body and its exceptions; never replace it with a bare
      return or no-op merely to make the module import.
    outputs:
      - name: field-validator-edits
        type: list[string]

  - name: migrate-model-and-root-validators
    description: >
      Replace `@root_validator(pre=True)` with
      `@model_validator(mode="before")` operating on incoming data. Replace
      post root validators with `@model_validator(mode="after")`, normally
      operating on and returning the model instance; account for assignment
      validation if enabled. Preserve cross-field checks, mutations, error
      messages, and exception types. If retaining a deprecated root_validator
      temporarily is unavoidable during an intermediate edit, satisfy v2's
      skip-on-failure rules and remove the deprecated form before completion.
      For models using `__root__`, migrate to RootModel when that matches the
      public behavior. Test both accepted and rejected cross-field combinations.
    outputs:
      - name: model-validator-edits
        type: list[string]

  - name: migrate-model-entry-points
    description: >
      Replace `Model.parse_obj(data)` with `Model.model_validate(data)`.
      Replace `from_orm` with `model_validate` plus `from_attributes=True`.
      For raw JSON, prefer `model_validate_json`; if old parse_raw behavior
      included other encodings or protocols, load the payload explicitly before
      model validation. Replace parse_file with explicit file I/O followed by
      validation. Use TypeAdapter for standalone types, lists, unions, and other
      non-model annotations. Preserve existing exception handling and ensure
      callers still receive the expected application-level error rather than
      suppressing ValidationError.
    outputs:
      - name: entry-point-edits
        type: list[string]

  - name: migrate-serialization-and-copying
    description: >
      Replace model `.dict()` with `.model_dump()`, `.json()` with
      `.model_dump_json()`, `.copy()` with `.model_copy()`, and `.construct()`
      with `.model_construct()` only where those methods are genuinely Pydantic
      APIs. Map include, exclude, by_alias, exclude_unset, exclude_defaults, and
      exclude_none deliberately. Account for v2's serialization of subclass
      fields, enums, decimals, datetimes, and custom serializers. Move suitable
      `json_encoders` behavior to field_serializer, model_serializer, or annotated
      serializers. Do not alter unrelated dictionaries, JSON utilities, Jinja
      constructs, or project-defined copy methods.
    outputs:
      - name: serialization-edits
        type: list[string]

  - name: migrate-schema-generation
    description: >
      Replace `.schema()` with `.model_json_schema()` and `.schema_json()` with
      explicit JSON encoding of the generated schema when necessary. Replace
      `schema_extra` with `json_schema_extra` and migrate custom schema hooks to
      supported v2 core-schema or JSON-schema hooks. Compare representative
      generated schemas for aliases, required fields, nullability, literals,
      references, discriminators, examples, descriptions, and additionalProperties.
      Preserve externally consumed OpenAPI behavior unless the task explicitly
      calls for a changed v2 contract.
    outputs:
      - name: schema-edits
        type: list[string]

  - name: migrate-model-introspection
    description: >
      Replace `__fields__` with `model_fields` and `__fields_set__` with
      `model_fields_set`. Replace uses of v1 ModelField metadata with v2 field
      information or core-schema facilities. Audit code that depends on model
      equality, private attributes, extra fields, or comparison with dictionaries,
      because v2 model equality is stricter. Update introspection logic based on
      its purpose rather than mechanically renaming attributes.
    outputs:
      - name: introspection-edits
        type: list[string]

  - name: migrate-forward-references-and-recursive-models
    description: >
      Prefer normal annotations enabled by supported Python syntax. Replace
      `update_forward_refs()` with `model_rebuild()` only where rebuilding is
      necessary, and pass an appropriate type namespace when names are not
      resolvable from module globals. Rebuild recursive model graphs after all
      related classes are defined. Verify actual nested validation and generated
      schema instead of accepting import success as proof that references resolve.
    outputs:
      - name: forward-reference-edits
        type: list[string]

  - name: migrate-generics-custom-types-and-dataclasses
    description: >
      Convert GenericModel patterns to native BaseModel and Generic patterns,
      preserving concrete parameterization behavior. Review constrained types and
      prefer Annotated constraints where appropriate. Migrate custom types from
      v1 validators and schema hooks to v2 core-schema and JSON-schema hooks
      without weakening validation. Audit Pydantic dataclasses for changed config,
      validation order, extra handling, and TypeAdapter usage. Treat these as
      specialist slices with focused tests rather than broad substitutions.
    outputs:
      - name: specialist-edits
        type: list[string]

  - name: run-focused-tests-after-each-slice
    description: >
      After each coherent edit, run the narrowest relevant test module or node
      with an unpiped command and inspect its real exit status. For a collection
      failure, first import the affected package or module, then rerun collection,
      then run its focused tests. Read the next complete traceback and classify
      it as an unconverted v1 occurrence, an incorrect mechanical migration, or
      a semantic v2 difference. Make the smallest behavior-preserving correction
      and retest. Maintain an execution loop of edit, import or focused test,
      traceback, correction, and retest. Do not end the attempt with a prose
      summary of what should be checked next while known failures remain.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: investigate-v2-semantic-differences
    description: >
      After obvious API removals are fixed, investigate semantic changes exposed
      by tests. Check union branch selection, stricter or changed coercion,
      preservation of input collection types, regex engine limitations, URL and
      DSN types, decimal and datetime serialization, alias population, equality,
      subclass serialization, extra fields, private attributes, default validation,
      error structures, and Optional requiredness. If available, consult
      `references/native-v2-api-migrations.md`, section `Investigate v2 semantic
      differences`. Prefer precise annotations, validators, serializers, or
      configuration that preserve the intended contract; do not globally loosen
      types or validation.
    outputs:
      - name: semantic-fixes
        type: list[string]

  - name: inspect-and-review-the-diff
    description: >
      Review git diff and repeat the Pydantic inventory searches. Confirm that
      edits are limited to the migration, all production v1 usages are resolved
      or consciously justified, imports are clean, and no behavior was erased.
      Explicitly search for `pydantic.v1`, fallback imports, newly introduced
      pass or ellipsis statements, bare validator returns, constant validator
      results, commented-out checks, swallowed ValidationError, weakened Any
      annotations, and broad test deletions. Review every automated replacement
      for typing, decorator order, configuration inheritance, aliases, and
      signatures. Revert unrelated formatting churn that obscures the migration.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-full-test-suite
    description: >
      Run the repository's complete documented test suite without an
      output-truncating pipeline. A successful import, collection pass, or focused
      test is not completion. Verify the command's actual zero status, the number
      of collected tests, the number passed, and warnings. Treat zero collected
      tests as failure unless the repository intentionally has no tests. If the
      suite fails, return to the focused edit-test loop and rerun the full suite
      afterward. Continue until the complete suite passes.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Run the repository's configured type checker, linter, formatter check,
      packaging or build command, and schema or generated-code checks used by CI.
      Resolve migration-induced warnings and errors, especially Pydantic
      deprecation warnings that identify remaining v1 APIs. Do not invent
      unrelated cleanup when a gate exposes a pre-existing failure; record it
      separately and verify the migration did not worsen it.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Confirm with the active repository interpreter that Pydantic major version
      2 is loaded. Search the final production tree for `pydantic.v1`, legacy
      Config classes, removed Field arguments, deprecated validators, parse_obj,
      old serialization methods, old introspection attributes, and unresolved
      forward-reference calls. Distinguish genuine Pydantic usage from unrelated
      names. Exercise representative valid and invalid inputs, omitted versus
      null fields, alias-based population, serialization, and generated schema.
      Confirm validator bodies still enforce their original rules. The final
      state must use native v2 behavior and retain validation logic, not merely
      import successfully.
    outputs:
      - name: native-v2-verification
        type: object

  - name: report-completion-with-evidence
    description: >
      Summarize changed migration areas, dependency changes, and intentional
      behavioral decisions. Report the exact full-suite and quality-gate commands,
      actual exit outcomes, and collected/passed test counts. Mention residual
      warnings, pre-existing failures, or unrun checks plainly. Do not claim
      completion unless the full suite passed under Pydantic v2 and final searches
      found neither pydantic.v1 shims nor behavior-erasing no-op implementations.
    outputs:
      - name: migration-report
        type: object
```