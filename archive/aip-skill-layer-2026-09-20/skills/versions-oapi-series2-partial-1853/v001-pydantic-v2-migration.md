---
name: pydantic-v2-migration
description: Migrate Python codebases from Pydantic v1 to native Pydantic v2 APIs while preserving validation, parsing, serialization, and generated-code behavior. Use when upgrading Pydantic, resolving removed Field arguments such as const, converting model Config and validators, or fixing test-collection failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
  derived_from_traces: "aa72dee9, 4acc4c33"
---

```yaml
# Completeness classification for the previous version:
# Mapped: its purpose, both triggers, both exclusions, all three anti-patterns,
# and establish-the-failure step are retained and expanded below.
# Deliberate drop: the VERSION 0 empty-scaffold and experiment-seeding comments
# no longer describe version 1; retaining them would falsely claim that no
# migration knowledge has been distilled.
# Deliberate drop: derived_from_traces was an empty list because version 0 had
# no evidence. Frontmatter now records the two traces that informed version 1.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, schema generation, and
  generated-code behavior. Finish only when the repository's own tests pass,
  without redirecting imports to pydantic.v1, suppressing collection failures,
  or deleting behavior merely to make the suite green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, model construction, validator,
    serialization, schema, or removed-argument errors after a Pydantic v2 upgrade
  - Test collection fails before any tests run because a Pydantic v1 model is
    imported under Pydantic v2
  - A dependency change installs Pydantic v2 while application models and
    generated schemas still use Pydantic v1 APIs

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
    constant result, or no-op so the function still imports. The grader rejects
    behavior deletion even if the suite becomes green.
  - Declaring the migration complete without running the repository's full suite.
  - >
    Starting with a repository-wide regex rewrite before fixing the first import
    blocker. Broad substitutions can create malformed ConfigDict calls and make
    the original failure harder to isolate.
  - >
    Trusting a search result or migration summary without checking the installed
    Pydantic v2 runtime and official documentation. For example, StrictInt and
    StrictStr remain importable in supported Pydantic v2 releases even though
    some summaries incorrectly claim they were removed.
  - >
    Piping pytest through head without pipefail or checking pytest's real exit
    status. The pipeline may report success while collection has failed.
  - >
    Repeatedly reverting an entire migrated directory after one malformed file.
    This discards correct edits and causes the same initial blocker to recur.
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

steps:
  - name: preserve-repository-state
    description: >
      Locate the repository root and inspect git status before editing. Record
      pre-existing modifications and do not overwrite or revert user changes.
      Work from the actual root rather than assuming a path. Use git diff
      throughout, and restore only a specific edit proven wrong rather than
      checking out an entire migrated directory.
    outputs:
      - name: repository-state
        type: object

  - name: establish-runtime
    description: >
      Record the Python executable, Python version, installed Pydantic and
      pydantic-core versions, package manager, dependency files, lock files, and
      test command. Inspect project configuration for supported Python and
      Pydantic ranges. Resolve any mismatch between dependency metadata and the
      interpreter used for tests before interpreting failures.
    outputs:
      - name: runtime-facts
        type: object

  - name: establish-the-failure
    description: >
      Run the repository's own test command unchanged and capture the complete
      output and real exit status. If output must be shortened, redirect it to a
      file and inspect that file, or enable shell pipefail; never infer success
      from a head or tail process. When zero tests run, treat the earliest
      conftest or package-import exception as the active blocker rather than as
      a test failure.
    outputs:
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: verify-the-first-traceback
    description: >
      Follow the first traceback to the exact imported module, class body, field,
      decorator, or configuration statement. Read the surrounding model and its
      base classes before editing. In an import chain, fix the deepest actionable
      Pydantic error first; later errors are not yet observable.
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
      Optional fields without defaults; aliases; and custom serialization.
      Preserve the file-and-line inventory as a checklist.
    outputs:
      - name: migration-inventory
        type: list[object]

  - name: inspect-contract-tests
    description: >
      Read tests, fixtures, snapshots, and representative call sites for each
      affected model family. Record behavior that must survive: omitted versus
      null fields, coercion and strictness, aliases accepted as input, extra
      fields, error locations, parsed types, model equality, JSON/schema shape,
      and serialization flags. When tests are sparse, run small v1-compatible
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
      model configuration, fields and annotations, validators, model methods,
      root models, forward references, dependency metadata, and emitted code.
      Order batches by import dependency so collection can advance after each
      change. Prefer explicit edits for irregular model definitions. If a
      codemod such as bump-pydantic is available, use it only on a clean diff,
      inspect every change, and keep behavior tests as the authority.
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
      Replace every Field(..., const=True) with a genuine constant annotation
      using typing.Literal while preserving the original default and value type.
      For example, change name = Field(default="", const=True) to
      name: Literal[""] = "" and annotate enum constants with a Literal of the
      exact enum member. Import Literal from typing or typing_extensions as
      required by the supported Python versions. Do not merely remove const,
      because that silently permits values the v1 model rejected.
    outputs:
      - name: const-migration
        type: object

  - name: validate-first-import-gate
    description: >
      Compile the edited files, import the package entry point used by the test
      conftest, and rerun pytest collection without truncating its status. If
      collection still fails, record the new first traceback and fix that
      blocker before starting broad cleanup. Inspect git diff immediately for
      malformed imports, lost annotations, or unrelated edits.
    inputs:
      - name: const-migration
        type: object
    outputs:
      - name: first-import-gate
        type: object

  - name: migrate-model-configuration
    description: >
      Convert each inner class Config to model_config = ConfigDict(...) and add
      ConfigDict imports. Translate settings semantically: Extra.allow,
      Extra.ignore, and Extra.forbid become extra string values;
      allow_population_by_field_name becomes populate_by_name; schema_extra
      becomes json_schema_extra; orm_mode becomes from_attributes; and other
      still-supported settings retain their behavior. Preserve inherited config
      and callable schema customization. Do not apply a regex that assumes all
      Config classes have the same indentation, key order, or body shape.
    outputs:
      - name: config-migration
        type: object

  - name: check-configuration-batches
    description: >
      After each small group of configuration edits, run Python compilation,
      import the affected module and package root, instantiate one representative
      model, and inspect git diff. Correct syntax or semantics before processing
      the next group. This gate prevents a malformed ConfigDict rewrite from
      contaminating dozens of files.
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
      never fix an exception by dropping the argument without an equivalent.
    outputs:
      - name: field-keyword-migration
        type: object

  - name: preserve-required-and-nullable-semantics
    description: >
      Audit Optional and Union fields because Pydantic v2 treats a nullable
      annotation without a default as required. Add = None only where the v1
      contract allowed omission; leave intentionally required nullable fields
      required. Preserve explicit defaults and default factories, and verify
      model_fields_set plus exclude_unset serialization for behavior that
      distinguishes omitted values from explicit nulls.
    inputs:
      - name: behavior-contract
        type: object
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
      fields are present. Preserve each validator's complete body and tests;
      never replace it with a no-op or unconditional return.
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
      assignment validation where configured. Preserve skip-on-failure and
      error behavior rather than mechanically renaming the decorator.
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
      with supported public v2 imports. Review code that inspects errors(),
      loc, type, ctx, or message text because v2 error structures and wording can
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
      decorators, or v1 model methods.
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
      and circular imports before returning to pytest.
    outputs:
      - name: static-check-result
        type: object

  - name: run-collection-gate
    description: >
      Run pytest collection by itself and require a zero exit status with the
      expected tests discovered. Do not pipe away the status. If collection
      fails, fix the first traceback and repeat this gate; do not proceed on the
      theory that later test execution will clarify an import-time error.
    outputs:
      - name: collection-result
        type: object

  - name: run-focused-tests
    description: >
      Run the smallest tests covering the current migration batch, especially
      model parsing, invalid input, aliases, optional fields, serialization,
      schema output, and code-generation snapshots. For each failure, classify
      it as syntax/import, intentional v2 API difference, or behavior regression.
      Fix implementation regressions rather than weakening assertions by
      default.
    outputs:
      - name: focused-test-result
        type: object

  - name: run-full-suite
    description: >
      Run the repository's complete test suite using its documented command and
      retain the untruncated result and exit status. Iterate from the first
      actionable failure until all tests pass. A result with zero collected
      tests, skipped collection, ignored failures, or only a hand-picked subset
      is not success.
    outputs:
      - name: full-suite-result
        type: object

  - name: audit-for-forbidden-shortcuts
    description: >
      Search the final diff and repository for pydantic.v1 imports, newly added
      compatibility shims that expose the v1 API, disabled tests, broad warning
      suppression, empty or trivialized function bodies, removed validators,
      and constraints deleted without equivalents. Inspect every changed
      validator manually. Reject the migration even with green tests if it
      redirects to pydantic.v1 or empties behavior.
    inputs:
      - name: full-suite-result
        type: object
    outputs:
      - name: shortcut-audit
        type: object

  - name: audit-inventory-completeness
    description: >
      Walk the original migration inventory item by item and classify it as
      migrated, verified as valid in v2, intentionally unchanged with evidence,
      or still unresolved. Repeat searches for removed APIs and compare the
      final diff with the behavior contract. Resolve every unresolved item and
      rerun affected checks.
    inputs:
      - name: migration-inventory
        type: list[object]
      - name: behavior-contract
        type: object
    outputs:
      - name: inventory-audit
        type: object

  - name: final-clean-run
    description: >
      In the synchronized Pydantic v2 environment, rerun package import, test
      collection, and the full suite after the final edit. Confirm the real exit
      statuses, inspect git diff one last time for unrelated or reverted work,
      and report versions, commands, test counts, and any intentional behavior
      differences. Declare completion only when this clean run and the forbidden
      shortcut audit both pass.
    inputs:
      - name: shortcut-audit
        type: object
      - name: inventory-audit
        type: object
    outputs:
      - name: migration-evidence
        type: object
```