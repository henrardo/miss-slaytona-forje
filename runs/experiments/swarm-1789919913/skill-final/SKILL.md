---
name: pydantic-v2-migration
description: Procedure distilled from graded migration attempts for upgrading a Python codebase from Pydantic v1 to native Pydantic v2 APIs while preserving validation, settings, field metadata, requiredness, parsing, and serialization behavior. Use when imports, validators, model fields, constraints, or tests fail after a Pydantic v2 upgrade.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces:
      - "81e12f5c"
      - "d08bc232"
      - "44425e0b"
---

```yaml
# Version 3 retains every procedure item and anti-pattern from version 2.
# It adds lessons from trace 44425e0b: fix collection blockers in complete
# equivalence classes, treat Optional-without-default failures as migration
# failures, annotate inherited field overrides, restore required shared helpers,
# avoid editing tests to conceal source defects, and validate each automated
# rewrite before attempting another broad transformation.
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs so
  that the repository's own test suite passes, without shimming pydantic.v1,
  bypassing validation, emptying function bodies, weakening tests, or deleting
  behavior to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, settings, field, schema, requiredness, introspection, or validator errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings from pydantic, class Config, validator, root_validator, __fields__, ModelField, SHAPE constants, or removed Field arguments
  - A dependency manifest still pins pydantic below version 2 while the requested task is a Pydantic v2 migration
  - Test collection fails on non-annotated inherited field overrides, constr(regex=...), or a missing helper introduced by a partial migration

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working. This can make nearly the entire fixture pass while avoiding the requested migration.
  - Adding a compatibility module that merely re-exports pydantic.v1 APIs under new local names.
  - Replacing a validator or any other function body with a bare return, pass, unconditional success, or other no-op so the function still imports. A green suite does not justify deleting behavior.
  - Removing validators, constraints, extra-field rejection, immutability, serialization logic, settings behavior, or parser safeguards merely to suppress failures.
  - Mechanically renaming decorators without adapting their signatures, input phase, return type, and access to sibling fields.
  - Converting every root validator identically; before and after model validators receive different inputs and require different implementations.
  - Leaving mode="after" model validators as class methods that still call values.get; native v2 after validators should normally inspect and return self.
  - Renaming a shared validator decorator or helper without migrating every reusable validator function that it decorates.
  - Importing field_validator from two places under the same name and accidentally shadowing either Pydantic's decorator or the project's helper.
  - Blindly replacing values with ValidationInfo while leaving validator bodies calling values.get instead of info.data.get.
  - Treating deprecation warnings as proof of migration completeness while deprecated v1-style APIs remain in production code.
  - Performing a repository-wide blind replacement before understanding project-specific base models and shared validator helpers.
  - Using a broad regular expression to rewrite validators without compiling and importing every changed module immediately afterward.
  - Searching only Field(regex=...) and missing constrained factories such as constr(regex=...).
  - Fixing only the first occurrence of a removed keyword instead of searching the complete repository for equivalent call sites.
  - Blindly replacing model.dict() with model_dump() inside validation logic when the body depends on nested values remaining model instances.
  - Exploring the repository repeatedly without making edits, running tests, or using failures to drive the next change.
  - Ending the task after inspection, dependency edits, syntax fixes, import success, or successful collection without completing the migration and running the suite.
  - Declaring the migration complete without running the repository's full test suite under an installed Pydantic v2 release.
  - Updating source imports but leaving packaging metadata pinned to pydantic below version 2.
  - Assuming Optional[T] remains optional without a default; in Pydantic v2 it is required unless a default such as None is supplied.
  - Dismissing a wave of missing-field failures on Optional annotations as bad test data; requiredness changed in Pydantic v2 and must be reconciled against v1 behavior.
  - Adding = None to every Optional annotation without checking whether the field was intentionally required but nullable.
  - Assuming deprecated dict, parse_obj, json, copy, schema, __fields__, or ModelField behavior is unchanged in code that depends on field metadata or ordering.
  - Silencing all warnings globally instead of removing actionable Pydantic migration warnings.
  - Modifying tests to accept broken behavior, deleting imports from tests, or weakening assertions unless the task explicitly requires a test API migration and the original behavioral expectation remains intact.
  - Piping pytest through head or another command without pipefail and then treating the pipeline's zero exit status as a passing test result.
  - Running only a conftest file, receiving zero collected tests, and treating successful collection as suite coverage.
  - Stopping at the first newly discovered removed keyword rather than searching all equivalent call sites and API forms.
  - Adding a helper solely because a test imports it without integrating that helper into the production behavior it represents.
  - Accessing model_fields through an instance, which is deprecated; use the model class when introspecting fields.
  - Replacing ModelField.type_ with FieldInfo.annotation and assuming hasattr(annotation, "x12") correctly handles Optional, Annotated, unions, and list element types.
  - Importing both Pydantic's field_validator and a project helper named field_validator into the same module.
  - Treating warnings from classmethod after-model validators as harmless when the validator still follows the v1 values-dictionary contract.
  - Performing repeated one-line fixes to collection errors without rerunning full collection to reveal the next repository-wide blocker.

steps:
  - name: establish-the-failure
    description: >
      Run the repository's own full test suite immediately in the intended
      environment and record the exact command, installed Pydantic version,
      collection errors, first complete traceback, collected count, and
      pass/fail count. If collection aborts, retain that as the baseline rather
      than reporting zero tests as useful coverage. Use the project's documented
      runner when available; otherwise start with pytest. Capture output without
      masking the exit status: do not pipe through head, tail, or tee unless the
      shell uses pipefail and the actual pytest status is retained. Do not spend
      the whole attempt inventorying files before obtaining this executable
      baseline.
      # The obsolete version-0 claim that no procedural step had been distilled
      # remains deliberately absent because this procedure is evidence-based.
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
      companion packages, exact tested versions, expected test counts, or known
      blockers. Record the normal test, lint, and packaging commands. If the
      environment still has Pydantic v1, install or select the repository's
      intended v2 dependency set before interpreting migration failures.
    outputs:
      - name: environment-inventory
        type: "object"

  - name: create-a-failure-ledger-and-work-plan
    description: >
      Create a short ledger containing each observed failure, its owning layer,
      affected files, intended native-v2 replacement, and verification command.
      Order work by shared dependencies: packaging and settings first, then base
      models and introspection, shared validator helpers, leaf validators,
      serialization, transaction families, and finally residue and quality
      gates. Record collection blockers as equivalence classes rather than
      isolated lines, such as all inherited field overrides without annotations,
      every regex keyword form, every missing shared helper, and every
      Optional-without-default declaration. Use the ledger to prevent repeated
      exploration and one-off patches where a shared abstraction is the source.
    outputs:
      - name: migration-plan
        type: "object"

  - name: inventory-v1-usage
    description: >
      Search production code, tests, documentation examples, and dependency
      metadata for Pydantic v1 surfaces. Include imports of BaseSettings,
      validator, root_validator, GenericModel, ModelField, SHAPE constants,
      pydantic.fields internals, and pydantic.v1; class Config; __fields__;
      field_info.extra; parse_obj, from_orm, dict, json, copy, schema, and
      construct; Field arguments such as regex, min_items, max_items, const, and
      allow_mutation; constrained factories such as constr, conlist, conint, and
      condecimal; validator options such as pre, always, each_item, and
      allow_reuse; custom __get_validators__ types; Optional annotations lacking
      defaults; and inherited fields overridden by assignments without type
      annotations. Search decorator forms both with and without parentheses,
      including @root_validator and @root_validator(). Search for tests importing
      production helpers that a partial migration may have removed. Group
      results by shared infrastructure, model families, tests, and documentation.
      The search is a checklist, not a substitute for editing and testing.
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
      tests and representative fixtures as the source of truth. In an X12-style
      repository, pay special attention to delimiter models, segment rendering,
      segment-group traversal, component-versus-repetition metadata, list-field
      detection, dynamic segment lookup, and the validator that wraps a bare
      repeatable segment dictionary in a list. Identify helper functions such as
      list-annotation detection that tests and parser logic expect to share.
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
      migration is still pending once the migration is implemented. Reinstall or
      otherwise refresh package metadata if tests use the installed project
      rather than the working tree.
    outputs:
      - name: dependency-changes
        type: "list[string]"

  - name: migrate-settings
    description: >
      Import BaseSettings and SettingsConfigDict from pydantic_settings rather
      than pydantic. Preserve case sensitivity, environment prefixes, dotenv
      behavior, nested delimiters, aliases, and cached construction. Replace
      removed Field(regex=...) constraints with Field(pattern=...) or an
      equivalent annotated constraint. Instantiate the settings object under
      controlled environment values and verify defaults, environment overrides,
      accepted values, and rejected values, not merely that the module imports.
      This import error is often the collection blocker, but fixing it is only
      the first migration layer.
    outputs:
      - name: settings-result
        type: "object"

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
      do not duplicate or contradict it. Do not place a former Config class
      docstring as a positional argument inside ConfigDict; comments belong
      outside the call.
    outputs:
      - name: configuration-migrations
        type: "list[object]"

  - name: compile-and-import-after-structural-edits
    description: >
      After changing imports, configuration, decorators, generated edits, or
      helper definitions, run Python compilation over the package and import the
      shared modules that test collection loads. Fix SyntaxError, NameError,
      duplicate or shadowed imports, stale decorator names, and malformed
      ConfigDict calls before proceeding. Then run full pytest collection or
      collect representative modules from every model family. Repeat this gate
      after every automated batch edit; a successful settings or conftest import
      alone does not prove base models or transaction modules import.
    outputs:
      - name: structural-gate-result
        type: "object"

  - name: annotate-inherited-field-overrides
    description: >
      Search subclasses for assignments that override fields declared on a
      Pydantic base model without repeating a type annotation. Pydantic v2
      rejects forms such as segment_name = X12SegmentName.CR5 when the base
      declares segment_name as a field. Preserve the field and add an explicit
      annotation, for example
      segment_name: X12SegmentName = X12SegmentName.CR5. Search every package,
      including transaction-specific subclasses, rather than fixing only the
      first class named in a collection traceback. Compile and collect all model
      modules after the batch.
    outputs:
      - name: inherited-field-overrides
        type: "list[object]"

  - name: migrate-field-definitions
    description: >
      Replace removed or renamed Field arguments while retaining the original
      constraint: regex becomes pattern; min_items and max_items become
      min_length and max_length for collections; const becomes Literal where
      appropriate; and allow_mutation moves to model configuration or supported
      field semantics. Apply the same audit to constrained factories:
      constr(regex=...) must become constr(pattern=...) or preferably an
      Annotated string with StringConstraints(pattern=...). Move custom Field
      extras into json_schema_extra, for example
      json_schema_extra={"is_component": True}, rather than relying on arbitrary
      keyword arguments. Review constrained-type factories and strict coercion
      behavior against Pydantic v2 signatures. Search the complete repository
      for each obsolete keyword after fixing its first occurrence. Do not weaken
      bounds, decimal precision, string lengths, literals, patterns, or list
      cardinality simply because the old declaration no longer imports.
    outputs:
      - name: field-definition-changes
        type: "list[object]"

  - name: correct-requiredness-and-defaults
    description: >
      Audit Optional and nullable fields explicitly. In Pydantic v2, Optional[T]
      or T | None without a default accepts None but remains required; add
      = None only where omission was valid under the repository's v1 behavior.
      Preserve required nullable fields where omission must still fail. Treat
      widespread missing-field failures on Optional declarations as a migration
      signal, not as defective fixtures. Review default factories and validators
      that relied on always=True; use validate_default configuration or a model
      validator only when defaults genuinely require validation. Add focused
      construction checks for omitted, None, valid, and invalid values on
      representative models. Use tests, v1 behavior, fixtures, and wire-format
      cardinality to guide broad Optional edits rather than adding defaults
      indiscriminately.
    outputs:
      - name: requiredness-changes
        type: "list[object]"

  - name: restore-and-migrate-shared-helpers
    description: >
      Identify production helpers imported by tests or other modules, including
      annotation classifiers such as _is_list_field. If a partial migration
      removed one, restore it with native-v2 behavior and use it in the
      corresponding production path rather than creating a test-only stub. A
      list-field helper should account for list, typing.List, Annotated wrappers,
      and nullable unions as required by repository annotations. Add direct
      checks covering bare lists, optional lists, annotated lists, non-list
      fields, and nested element types. Do not edit tests to remove a legitimate
      helper import merely to make collection continue.
    outputs:
      - name: shared-helper-result
        type: "object"

  - name: migrate-shared-validator-infrastructure
    description: >
      Locate reusable validator decorators and plain validation functions before
      converting leaf classes. Give the project helper a name that cannot shadow
      pydantic.field_validator, or import the Pydantic decorator under an
      explicit alias. Remove allow_reuse because native v2 no longer requires it.
      Update reusable field validator signatures to accept the value and, only
      when needed, ValidationInfo; replace old values lookups with info.data.
      Update reusable model-level validators according to their phase and input
      form rather than forcing old dictionary functions through a renamed
      decorator. Compile and exercise one direct use of every shared helper
      before migrating all call sites.
    outputs:
      - name: shared-validator-result
        type: "object"

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
      Do not add an unused ValidationInfo parameter mechanically. If a project
      exposes a shared validator decorator helper, migrate the helper and every
      validator signature together rather than leaving v1 call conventions
      hidden behind a renamed alias.
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
      needed before deciding whether a field is list-like. Reuse the repository's
      shared list-field helper where one exists. For repeatable segment coercion,
      wrap only a bare dictionary supplied for a list field; preserve existing
      lists, None, missing values, and unrelated dictionaries.
    outputs:
      - name: before-validator-changes
        type: "list[object]"

  - name: migrate-after-root-validators
    description: >
      Convert post @root_validator logic to @model_validator(mode="after") and
      rewrite it around the constructed model instance. Define it as an instance
      method unless a documented native-v2 use case requires another form.
      Access fields through self or getattr(self, name), perform the same
      cross-field checks or derived calculations, and return self. Do not retain
      cls, values, values.get(...), dictionary indexing, or a dictionary return
      merely because the decorator name changed. If a reusable rule naturally
      consumes a mapping, pass it an intentionally constructed view or rewrite
      the helper to consume the model; do not call model_dump blindly if the rule
      needs nested model instances. When assignment validation or construction
      pathways can pass different forms, handle them intentionally. Preserve
      exact business rules such as mutually required fields, balancing totals,
      segment counts, control numbers, and date relationships. Add a failing and
      passing example for each distinct cross-field rule before moving on.
      Eliminate classmethod-after-validator warnings rather than treating them as
      harmless.
    outputs:
      - name: after-validator-changes
        type: "list[object]"

  - name: preserve-validation-errors
    description: >
      Review validator exceptions under Pydantic v2. Raise ValueError,
      AssertionError, or PydanticCustomError for validation failures as
      appropriate; do not rely on TypeError being converted into a
      ValidationError because v2 propagates TypeError from validators. Keep
      meaningful messages and error locations where tests or callers depend on
      them. Fix incorrect validator signatures rather than catching broad
      exceptions around model construction.
    outputs:
      - name: validation-error-checks
        type: "list[object]"

  - name: replace-field-internals
    description: >
      Remove dependencies on pydantic.fields internals such as SHAPE_LIST,
      ModelField, field.shape, field.type_, outer_type_, and field_info.extra.
      Use model_fields, FieldInfo.annotation, typing.get_origin/get_args, and
      FieldInfo.json_schema_extra instead. Access model_fields on the class, not
      an instance, to avoid deprecation warnings. Account for Optional,
      Annotated, union, and collection annotations rather than checking only
      get_origin(annotation) is list when aliases or wrappers are possible.
      When traversing nested groups, inspect or unwrap the declared annotation
      safely, or use populated runtime values; do not assume an annotation itself
      exposes model methods. Preserve field declaration order wherever output
      format is positional. Add focused tests for field-name discovery, list
      detection, component metadata, dynamic segment lookup, and nested model
      traversal because these failures can corrupt parsing without an obvious
      import error.
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
      choose model_dump mode="python" or mode="json" deliberately. Remember that
      model_dump recursively turns nested models into mappings; validation code
      that needs nested attributes should keep the models or construct a
      purpose-specific view. Preserve include, exclude, by_alias, exclude_none,
      exclude_unset, and exclude_defaults options. Update tests or public
      examples that invoke removed entry points, but retain compatibility
      wrappers only when the package's public API explicitly promises them and
      those wrappers use native v2 internals.
    outputs:
      - name: model-entry-point-changes
        type: "list[object]"

  - name: preserve-custom-serialization
    description: >
      Test custom text or wire-format serializers independently of generic model
      dumping. In positional formats, iterate class model_fields in declaration
      order and fetch runtime values, or otherwise use a method that
      demonstrably preserves order. Read custom metadata from json_schema_extra,
      guarding a None metadata value before calling get. Preserve formatting for
      datetime, date, time, Decimal scale, enums, None, repeated values,
      components, custom delimiters, and trailing empty elements. When traversing
      nested segment groups, use runtime values or safely unwrap field
      annotations instead of relying on removed ModelField.type_. Do not
      serialize model configuration or private attributes as data fields.
      Compare byte-for-byte or string-for-string with representative round-trip
      fixtures.
    outputs:
      - name: serialization-checks
        type: "list[object]"

  - name: migrate-custom-types-and-generics
    description: >
      If the inventory found custom types using __get_validators__,
      __modify_schema__, GenericModel, or v1 schema hooks, migrate them to native
      v2 core-schema and JSON-schema hooks or BaseModel generics as required.
      Implement __get_pydantic_core_schema__ and
      __get_pydantic_json_schema__ only for types that need customization;
      prefer standard Annotated constraints when sufficient. Exercise both
      validation and generated JSON schema for each migrated custom type. Skip
      this step only when the inventory proves the repository has no such usage.
    outputs:
      - name: custom-type-result
        type: "object"

  - name: run-focused-tests-after-each-layer
    description: >
      After each coherent layer, run the smallest relevant real tests: settings
      tests after settings changes, collection and segment tests after
      base-model changes, then one transaction family at a time after validator
      changes. Stop on the first new failure, read the complete traceback and
      validation error details, fix the underlying semantic mismatch, and rerun
      the same test until green. Then rerun full collection so another
      repository-wide blocker is not hidden behind the fixed module. Do not
      truncate output in a way that loses the exception endpoint or masks the
      exit status. Keep the failure ledger current so repeated errors are
      addressed at their shared source instead of patched separately across
      dozens of models. Confirm that expected-invalid fixtures still fail;
      passing only valid fixtures can conceal deleted validation.
    outputs:
      - name: focused-test-results
        type: "list[object]"

  - name: import-every-model-family
    description: >
      Import every package and transaction/model family that dynamic loading can
      reach, not only the family exercised by the first focused test. Use the
      repository's discovery mechanism where possible so decorator variants,
      unannotated overrides, constrained factories, and stale imports in rarely
      loaded modules are exposed. Resolve every SyntaxError, removed argument,
      undefined old decorator, Pydantic usage error, and missing production
      helper before relying on broad test execution. A model family that has not
      imported under v2 is not migrated.
    outputs:
      - name: model-family-import-result
        type: "object"

  - name: search-for-migration-residue
    description: >
      Repeat the v1 API inventory after edits. Production code must contain no
      pydantic.v1 import or equivalent compatibility redirection. Investigate
      every remaining BaseSettings-from-pydantic import, @validator,
      @root_validator, class Config, __fields__, pydantic.fields internal,
      SHAPE constant, removed Field or constrained-type keyword, arbitrary
      custom Field extra, deprecated model method, classmethod after-model
      validator, and unannotated inherited field override. Search both multiline
      and single-line calls and decorator forms with optional parentheses.
      Distinguish harmless prose mentioning v1 from executable residue. Run
      imports with deprecation warnings visible and eliminate actionable
      Pydantic warnings rather than suppressing them.
    outputs:
      - name: residue-report
        type: "object"

  - name: audit-the-diff-for-behavior-deletion
    description: >
      Inspect git diff before the final suite. Compare every changed validator,
      helper, parser, and serializer with its original body and preserved-contract
      inventory. Reject any change that empties a function body, replaces logic
      with an unconditional return, removes a constraint without an equivalent,
      broadly catches validation errors, or skips a failing code path. Also
      reject any pydantic.v1 import, local v1 re-export, or dependency pin that
      permits the implementation to keep running solely on the old API. Check
      automated replacements for malformed decorators, stale parameters,
      duplicate imports, changed validation phase, and helpers added but not used
      by production code. Revert unrelated edits. Inspect test changes
      separately and reject deleted imports or weakened assertions that merely
      hide source defects.
    outputs:
      - name: behavior-audit
        type: "object"

  - name: run-full-quality-gates
    description: >
      Run the complete test suite under Pydantic v2, followed by the
      repository's configured lint, formatting, type-checking, and packaging or
      import checks. Run pytest directly or preserve its real exit status with
      pipefail. If the full suite exposes interactions absent from focused
      tests, return to the responsible migration layer, fix it, rerun focused
      tests, and then rerun the full suite. Record actual commands, Pydantic
      version, collected test count, pass count, failures, warnings, and skipped
      tests. Zero collected tests, collection aborts, a command whose exit code
      was masked by a pipeline, or an environment still using Pydantic v1 are
      failures, not successful validation.
    outputs:
      - name: full-quality-result
        type: "object"

  - name: verify-representative-behavior
    description: >
      Exercise representative valid and invalid models outside broad suite
      summaries. Verify settings loading; forbidden extras; frozen-model
      behavior; omitted versus nullable fields; annotated inherited defaults;
      Field and Annotated constraints; field and cross-field validation;
      repeatable-segment wrapping; optional-list detection; custom metadata
      lookup; model validation and dumping; and exact wire-format serialization
      with default and custom delimiters. Also verify at least one balancing or
      count rule that uses nested models, ensuring model_dump conversion did not
      change the rule's input representation. Compare serialized output to stable
      fixtures where available. This catches migrations that import and pass
      shallow tests while changing domain behavior.
    outputs:
      - name: behavioral-verification
        type: "list[object]"

  - name: report-completion-with-evidence
    description: >
      Summarize dependency changes, native v2 API migrations, preserved
      behavior, tests and quality gates run, final counts, and any remaining
      warnings or risks. State explicitly that no pydantic.v1 shim or equivalent
      compatibility redirection was introduced and no validator or other
      function body was emptied or converted to a no-op to obtain passing tests.
      Also state whether tests were modified and justify every such change; test
      weakening is not acceptable evidence of completion. If any tests cannot
      run, report the exact blocker and do not claim completion. Leave the
      working tree with the implementation changes present; inspection without
      edits is not a completed migration.
    outputs:
      - name: migration-report
        type: "object"
```