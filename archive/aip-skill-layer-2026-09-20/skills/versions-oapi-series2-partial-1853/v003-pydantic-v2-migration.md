---
name: pydantic-v2-migration
description: Migrate Python codebases from Pydantic v1 to native Pydantic v2 APIs while preserving validation, parsing, serialization, schema, generated-code, configuration defaults, and application behavior. Use when upgrading Pydantic, resolving removed Field arguments such as const, converting model Config or validators, or fixing collection and runtime failures under Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
  derived_from_traces: "aa72dee9, 4acc4c33, b844e705, d13d710e"
---

```yaml
# Completeness classification for the complete previous version:
# Mapped: frontmatter name, description, AIP spec, schema ID, and trace
# provenance are retained; the harness-required AIP version advances from 2 to 3.
# Mapped: purpose; all four previous trigger_when entries; all three
# do_not_use_when entries; every previous anti-pattern; every previous step,
# input, output, behavior-preservation requirement, validation gate, and
# completion condition are retained below.
# Mapped: the absolute prohibitions against pydantic.v1 imports and empty,
# trivialized, or no-op function bodies remain explicit in purpose,
# anti_patterns, validator migration, shortcut audit, and final acceptance.
# Mapped: preserve repository state, discover the actual root, inspect the
# installed runtime, distrust inaccurate secondary summaries, preserve pytest's
# real status, avoid broad regex rewrites, validate package initialization
# rather than one leaf import, and never revert an entire migrated directory
# because one edit is malformed.
# Mapped: removed Field(const=True) can prevent conftest import before tests run.
# The procedure retains exhaustive occurrence enumeration, one-batch conversion,
# residual search, behavioral rejection testing, public package import, and
# collection gates before unrelated migration work.
# Mapped: every prior migration category remains explicit: ConfigDict, field
# keywords, Optional semantics, coercion and unions, field and root validators,
# custom hooks, RootModel, model APIs, errors, serialization and schema output,
# forward references, dataclasses and settings, generators, dependencies,
# static checks, collection, focused tests, full tests, shortcut audit,
# inventory audit, and clean final run.
# Mapped and expanded from traces b844e705 and d13d710e: importing and collecting
# can succeed while Config() and other foundational no-argument constructors
# raise ValidationError. New early gates inspect complete tracebacks, enumerate
# v1 implicit-None fields, exercise default constructors used by fixtures, and
# prioritize shared application models before processing model families.
# Mapped and expanded from the 310-passing failed suites: a large passing count
# is not completion. The procedure now requires failure clustering, one full
# untruncated traceback per cluster, and immediate constructor/fixture smoke
# tests after edits to shared models.
# Mapped and expanded from failed automation attempts: scripts and codemods must
# run from the actual repository root, operate on a clean reviewed diff, compile
# representative files, and stop at the first malformed transformation.
# Body drop: none.
# Schema gap: none.
# Deliberate drop: none. Repetition that acts as a safety gate is intentionally
# retained because prior attempts repeatedly rediscovered the same blockers.

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
      Locate the repository root from the current environment and inspect git
      status before editing. Record pre-existing modifications and do not
      overwrite or revert user changes. Work from the actual root rather than
      assuming a path. Use git diff throughout, and restore only a specific edit
      proven wrong rather than checking out an entire migrated directory.
    outputs:
      - name: repository-state
        type: object

  - name: establish-runtime
    description: >
      Record the Python executable, Python version, installed Pydantic and
      pydantic-core versions, package manager, dependency files, lock files, and
      documented test command. Inspect project configuration for supported
      Python and Pydantic ranges. Resolve any mismatch between dependency
      metadata and the interpreter used for tests before interpreting failures.
    outputs:
      - name: runtime-facts
        type: object

  - name: establish-the-failure
    description: >
      Run the repository's own test command unchanged and capture complete output
      and the real exit status. If output must be shortened, redirect it to a
      file and inspect that file, or enable shell pipefail; never infer success
      from a head or tail process. Record collected, passed, failed, errored,
      skipped, and deselected counts only from the current invocation. When zero
      tests run, treat the earliest conftest or package-import exception as the
      active blocker. When many tests pass but failures remain, preserve the
      complete failure summary and select the earliest setup error or shared
      failure for full-traceback diagnosis.
    outputs:
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: verify-the-first-traceback
    description: >
      Follow the first full traceback to the exact imported module, model,
      constructor, class body, field, decorator, or configuration statement.
      Read the surrounding model, base classes, fixture, and caller before
      editing. In an import chain, fix the deepest actionable Pydantic error
      first. If the displayed exception is truncated, rerun only that test with
      verbose output and no traceback truncation, and inspect ValidationError
      errors() where useful. If the runtime explicitly reports a removed keyword
      such as const, accept that as the immediate diagnosis and search for all
      occurrences before browsing broad migration guidance.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: first-blocker
        type: object

  - name: inventory-pydantic-surface
    description: >
      Search source, tests, templates, examples, scripts, generated files, and
      configuration for Pydantic imports and v1-only patterns. Include Field
      arguments such as const and regex; class Config; Extra; schema_extra;
      allow_population_by_field_name; orm_mode; validate_assignment;
      arbitrary_types_allowed; validators and root validators; parse_obj,
      parse_raw, from_orm, dict, json, schema, copy, construct, and
      update_forward_refs; __root__; error_wrappers imports; constrained types;
      Optional fields without defaults; aliases; custom serialization; and
      no-argument model construction in fixtures or application code. Preserve
      every file and line in a checklist. Separate fatal import blockers,
      runtime constructor blockers, and deprecated-but-still-running APIs so the
      first two groups are handled before broad cleanup.
    outputs:
      - name: migration-inventory
        type: list[object]

  - name: inventory-v1-implicit-defaults
    description: >
      Enumerate every BaseModel field that is nullable but has no explicit
      default, especially Optional[T], Union[T, None], and T | None annotations.
      Use model_fields in the installed v2 runtime where models import, and
      inspect source where they do not. For each field, record whether v1 treated
      omission as None, whether callers omit it, whether tests require it, and
      whether aliases or default factories affect construction. Prioritize
      shared models instantiated with no arguments, including Config() and models
      created by broad fixtures. Do not change fields until required-versus-
      omittable intent is established.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: implicit-default-inventory
        type: list[object]

  - name: inspect-contract-tests
    description: >
      Read tests, fixtures, snapshots, and representative call sites for each
      affected model family. Record behavior that must survive: omitted versus
      null fields, no-argument construction, default values and factories,
      coercion and strictness, aliases accepted as input, extra fields, error
      locations, parsed types, model equality, JSON and schema shape, and
      serialization flags. When tests are sparse, run small v1-compatible
      examples only if an existing environment or historical output is
      available; do not introduce pydantic.v1 into production code.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: behavior-contract
        type: object

  - name: create-migration-plan
    description: >
      Group the inventory into small coherent batches: collection blockers,
      foundational application and configuration models, implicit defaults,
      model configuration, fields and annotations, validators, model methods,
      root models, forward references, dependency metadata, and emitted code.
      Order batches by import and fixture dependency so collection and ordinary
      construction can advance after each change. Fix every occurrence of the
      same fatal removed API in one batch, then gate it before moving on. Prefer
      explicit edits for irregular model definitions. If a codemod such as
      bump-pydantic is available, use it only from the actual repository root on
      a clean diff, inspect every change, and keep behavior tests authoritative.
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
      Before editing, enumerate every executable Python occurrence of
      Field(..., const=True), including multiple fields in one class. Replace
      each with a genuine constant annotation using typing.Literal while
      preserving the exact original default and value type. For example, change
      name = Field(default="", const=True) to name: Literal[""] = "", and
      annotate enum constants with a Literal of the exact enum member. Preserve
      any alias, description, or other Field metadata by retaining Field without
      const when metadata is still required. Import Literal from typing or
      typing_extensions according to supported Python versions. Do not merely
      remove const, because that silently permits values the v1 model rejected.
      After editing, repeat the exact search and require zero executable
      const=True occurrences.
    inputs:
      - name: migration-inventory
        type: list[object]
    outputs:
      - name: const-migration
        type: object

  - name: validate-const-contract
    description: >
      Compile every changed const file and instantiate representative models
      with both the allowed constant and a disallowed value. Require the allowed
      value to validate and the disallowed value to raise ValidationError.
      Import the module named by the original traceback, then import the public
      package path used by conftest. If another const error appears, the
      exhaustive search was incomplete; update the checklist and finish that
      batch before doing unrelated work.
    inputs:
      - name: const-migration
        type: object
    outputs:
      - name: const-contract-result
        type: object

  - name: validate-first-import-gate
    description: >
      Compile the edited files, import the package entry point used by the test
      conftest in a fresh process, and rerun pytest collection without truncating
      its status. If collection still fails, record the new first traceback and
      fix that blocker before broad cleanup. Inspect git diff immediately for
      malformed imports, lost annotations, changed defaults, or unrelated edits.
      Remember that passing this gate proves only import and collection, not that
      fixtures or no-argument model constructors work.
    inputs:
      - name: const-contract-result
        type: object
    outputs:
      - name: first-import-gate
        type: object

  - name: restore-foundational-construction
    description: >
      Exercise shared constructors used throughout the application and tests
      before migrating peripheral model families. Run the exact fixture setup or
      constructor from the first runtime error, including Config() when present.
      For a v1 nullable field whose omission historically produced None, add an
      explicit = None or Field(default=None) in v2. Keep a nullable field required
      when callers were required to provide it. Preserve default factories,
      aliases, enum defaults, nested models, and mutable-container behavior.
      After every edit to a shared model, inspect model_fields for required flags,
      instantiate it with no arguments and representative overrides, and rerun
      the smallest fixture or test that depends on it.
    inputs:
      - name: implicit-default-inventory
        type: list[object]
      - name: behavior-contract
        type: object
    outputs:
      - name: foundational-construction-result
        type: object

  - name: cluster-runtime-failures
    description: >
      After collection and foundational construction succeed, run the suite once
      to obtain the current failure set. Group failures by root cause rather than
      editing one test at a time: missing required defaults, configuration,
      alias population, extra-field handling, changed coercion, validators,
      serialization, schema, forward references, or generator snapshots. Open
      at least one complete traceback per cluster and fix the highest-fan-out
      implementation cause first. Re-run the cluster's focused tests after each
      fix, then refresh the suite summary because one shared-model correction
      may remove many failures.
    inputs:
      - name: foundational-construction-result
        type: object
    outputs:
      - name: failure-clusters
        type: list[object]

  - name: migrate-model-configuration
    description: >
      Convert each inner class Config to model_config = ConfigDict(...) and add
      ConfigDict imports. Translate settings semantically: Extra.allow,
      Extra.ignore, and Extra.forbid become extra string values;
      allow_population_by_field_name becomes populate_by_name; schema_extra
      becomes json_schema_extra; orm_mode becomes from_attributes; and other
      still-supported settings retain their behavior. Preserve inherited config
      and callable schema customization. Do not apply a regex that assumes all
      Config classes have the same indentation, key order, comments, or body
      shape.
    outputs:
      - name: config-migration
        type: object

  - name: check-configuration-batches
    description: >
      After each small group of configuration edits, run Python compilation,
      import the affected module and package root, instantiate one representative
      model, and inspect git diff. For application configuration models, also run
      their public default constructor and verify all expected defaults.
      Correct syntax or semantics before processing the next group. This gate
      prevents a malformed ConfigDict rewrite or newly required field from
      contaminating dozens of files. Do not respond to a local failure by
      reverting already validated files.
    inputs:
      - name: config-migration
        type: object
    outputs:
      - name: config-check
        type: object

  - name: migrate-field-keywords
    description: >
      Replace removed or renamed Field and constrained-type arguments according
      to the installed v2 API, including regex to pattern and collection
      min_items or max_items to min_length or max_length where applicable.
      Check aliases, validation_alias, serialization_alias, json_schema_extra,
      discriminators, and frozen behavior individually. Preserve constraints;
      never fix an exception by dropping an argument without an equivalent.
    outputs:
      - name: field-keyword-migration
        type: object

  - name: preserve-required-and-nullable-semantics
    description: >
      Complete the repository-wide audit of Optional, Union, and nullable fields
      because Pydantic v2 treats a nullable annotation without a default as
      required. Use the implicit-default inventory and call-site evidence. Add
      = None only where the v1 contract allowed omission; leave intentionally
      required nullable fields required. Preserve explicit defaults and default
      factories, and verify model_fields_set plus exclude_unset serialization
      for behavior that distinguishes omitted values from explicit nulls. Run a
      constructor matrix covering omission, explicit None, and a concrete value
      for representative fields in every affected model family.
    inputs:
      - name: behavior-contract
        type: object
      - name: implicit-default-inventory
        type: list[object]
    outputs:
      - name: field-presence-migration
        type: object

  - name: preserve-type-and-union-behavior
    description: >
      Test fields whose behavior depends on coercion, strict types, booleans,
      numbers, enums, URLs, dates, or Union branch order. Do not replace
      StrictInt, StrictStr, or another import merely because secondary guidance
      says it was removed; first check the installed v2 runtime and official
      API. Use Annotated, Field(strict=True), union_mode, or v2 constrained
      types only when needed to preserve the recorded contract.
    inputs:
      - name: behavior-contract
        type: object
    outputs:
      - name: type-semantics-migration
        type: object

  - name: migrate-field-validators
    description: >
      Convert @validator to @field_validator where native v2 conversion is
      required. Map pre=True to mode="before", retain always-like behavior only
      with the appropriate v2 mechanism, and update signatures that relied on
      ModelField, config, field, or values. Use ValidationInfo for validation
      context and inspect info.data carefully because only previously validated
      fields are present. Preserve each validator's complete function body,
      transformations, exceptions, side effects, and tests. Never replace it
      with a no-op, empty body, constant result, or unconditional passthrough.
    outputs:
      - name: field-validator-migration
        type: object

  - name: migrate-root-validators
    description: >
      Convert @root_validator to @model_validator with mode="before" when the
      function transforms raw input, or mode="after" when it validates the
      constructed model. Adapt signatures and return values deliberately:
      before validators operate on raw data and return data, while after
      validators normally operate on and return the model instance. Account for
      assignment validation where configured. Preserve skip-on-failure, every
      branch of the original function body, and error behavior rather than
      mechanically renaming the decorator.
    outputs:
      - name: root-validator-migration
        type: object

  - name: migrate-custom-validation-hooks
    description: >
      Inspect custom types and hooks such as __get_validators__,
      __modify_schema__, parse helpers, and direct pydantic-core integration.
      Migrate them to v2 core-schema or JSON-schema hooks only where the runtime
      or tests require it. Keep domain checks and error messages meaningful;
      successful import alone is not proof that custom validation still runs.
    outputs:
      - name: custom-hook-migration
        type: object

  - name: migrate-root-models
    description: >
      Replace v1 __root__ models with RootModel when present. Preserve the root
      type, validation, iteration or mapping helpers, serialization shape, and
      call-site expectations. Do not convert ordinary models that merely have a
      field named root.
    outputs:
      - name: root-model-migration
        type: object

  - name: migrate-model-apis
    description: >
      Replace deprecated model APIs at their call sites: parse_obj with
      model_validate, parse_raw with explicit decoding plus model_validate or
      model_validate_json, from_orm with model_validate under from_attributes,
      dict with model_dump, json with model_dump_json, schema with
      model_json_schema, copy with model_copy, construct with model_construct,
      and __fields__ with model_fields where appropriate. Preserve options such
      as by_alias, exclude_none, exclude_unset, include, exclude, and update.
      Verify return types and JSON formatting instead of doing blind renames.
    outputs:
      - name: model-api-migration
        type: object

  - name: migrate-errors-and-exception-handling
    description: >
      Replace internal v1 imports such as pydantic.error_wrappers.ValidationError
      with supported public v2 imports. Review code that inspects errors(), loc,
      type, ctx, or message text because v2 error structures and wording can
      differ. Update assertions only when the public v2 contract intentionally
      differs, not to conceal missing validation.
    outputs:
      - name: error-api-migration
        type: object

  - name: preserve-serialization-and-schema-output
    description: >
      Compare representative model_dump, model_dump_json, and
      model_json_schema results against the recorded contract. Migrate custom
      encoders to supported serializers or config while preserving aliases,
      enum values, excluded fields, computed output, and nested model behavior.
      Account for v2 subclass serialization and equality differences where the
      code relies on them.
    inputs:
      - name: behavior-contract
        type: object
    outputs:
      - name: serialization-migration
        type: object

  - name: rebuild-forward-references
    description: >
      Replace update_forward_refs usage with model_rebuild where needed and
      ensure recursive or mutually referring models resolve after all classes
      are imported. Import the package through its normal initialization path,
      not just leaf modules. Test at least one nested instance for each recursive
      model family.
    outputs:
      - name: forward-reference-migration
        type: object

  - name: migrate-dataclasses-and-settings
    description: >
      If the inventory contains pydantic dataclasses, BaseSettings, or related
      integrations, migrate them using their native v2 packages and lifecycle.
      BaseSettings may require pydantic-settings. Verify environment loading,
      aliases, post-init timing, extra handling, and TypeAdapter use rather than
      assuming BaseModel rules apply unchanged.
    outputs:
      - name: integration-migration
        type: object

  - name: update-generators-and-templates
    description: >
      Search code-generation templates and generator tests for every v1 pattern
      already migrated in checked-in Python. Update the source template rather
      than only generated output, regenerate representative artifacts when the
      repository supports it, and compare snapshots intentionally. Confirm that
      regeneration does not restore const=True, class Config, deprecated
      decorators, implicit v1-only defaults, or v1 model methods.
    outputs:
      - name: generator-migration
        type: object

  - name: update-dependencies
    description: >
      Update project metadata and lock files to a supported Pydantic v2 range,
      plus companion packages required by migrated integrations. Follow the
      repository's package-manager workflow and avoid unrelated upgrades.
      Reinstall or sync the test environment, then re-record the actual imported
      versions so tests cannot accidentally run against stale dependencies.
    outputs:
      - name: dependency-migration
        type: object

  - name: run-static-and-import-checks
    description: >
      Run the repository's formatter, linter, type checker, and Python
      compilation commands where configured. Import the public package and
      model package in a fresh process. Resolve unused v1 imports, missing
      Literal or ConfigDict imports, annotation errors, malformed class bodies,
      and circular imports before returning to pytest. Import success must be
      followed by shared default-constructor smoke tests; it is not a substitute.
    outputs:
      - name: static-check-result
        type: object

  - name: run-collection-gate
    description: >
      Run pytest collection by itself and require a zero exit status with the
      expected tests discovered. Do not pipe away the status. If collection
      fails, fix the first traceback and repeat this gate; do not proceed on the
      theory that later test execution will clarify an import-time error.
      Re-run residual searches for fatal removed APIs whenever collection reveals
      another occurrence of an already known pattern.
    outputs:
      - name: collection-result
        type: object

  - name: run-fixture-construction-gate
    description: >
      Run focused tests that execute broadly shared fixtures and constructors,
      not merely collection. Include the fixture that creates the project's
      default configuration or equivalent application model. If setup raises
      ValidationError, capture its complete field list, compare each required
      field with the v1 behavior contract, correct the model rather than the
      fixture unless the fixture was independently wrong, and repeat until setup
      succeeds. This gate specifically prevents a collection-clean but
      runtime-broken migration from reaching the full suite.
    inputs:
      - name: collection-result
        type: object
    outputs:
      - name: fixture-construction-result
        type: object

  - name: run-focused-tests
    description: >
      Run the smallest tests covering the current migration batch, especially
      default model construction, fixture setup, model parsing, rejected invalid
      input, aliases, optional fields, serialization, schema output, and
      code-generation snapshots. For each failure, classify it as syntax or
      import failure, missing-default regression, intentional v2 API difference,
      or another behavior regression. Fix implementation regressions rather than
      weakening assertions by default.
    outputs:
      - name: focused-test-result
        type: object

  - name: run-full-suite
    description: >
      Run the repository's complete test suite using its documented command and
      retain the untruncated result and exit status. Iterate from the first
      actionable failure or highest-fan-out failure cluster until all tests pass.
      A result with zero collected tests, setup errors, skipped collection,
      ignored failures, only a hand-picked subset, a nonzero status, or a stale
      count from an earlier invocation is not success. Hundreds of passing tests
      do not offset even one remaining failure or error.
    outputs:
      - name: full-suite-result
        type: object

  - name: audit-for-forbidden-shortcuts
    description: >
      Search the final diff and repository for pydantic.v1 imports, newly added
      compatibility shims that expose the v1 API, disabled tests, broad warning
      suppression, empty or trivialized function bodies, unconditional
      passthroughs, removed validators, and constraints deleted without
      equivalents. Inspect every changed validator and function body manually.
      Reject the migration even with green tests if it redirects imports to
      pydantic.v1 or empties behavior.
    inputs:
      - name: full-suite-result
        type: object
    outputs:
      - name: shortcut-audit
        type: object

  - name: audit-inventory-completeness
    description: >
      Walk the original migration inventory and implicit-default inventory item
      by item. Classify each as migrated, verified as valid in v2, intentionally
      unchanged with evidence, or still unresolved. Repeat searches for removed
      APIs, including const=True, and compare the final diff with the behavior
      contract. Recheck all no-argument constructors recorded in fixtures and
      call sites. Resolve every unresolved item and rerun affected checks.
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
    description: >
      In the synchronized Pydantic v2 environment, rerun public package import,
      foundational constructors, shared fixture setup, test collection, and the
      full suite after the final edit. Confirm the real exit statuses, expected
      collection count, passing count, and absence of failures and errors.
      Inspect git diff one last time for unrelated or reverted work, pydantic.v1
      imports, or deleted behavior, and report versions, commands, test counts,
      and any intentional behavior differences. Declare completion only when
      this clean run, inventory audit, and forbidden-shortcut audit all pass.
    inputs:
      - name: shortcut-audit
        type: object
      - name: inventory-audit
        type: object
    outputs:
      - name: migration-evidence
        type: object
```