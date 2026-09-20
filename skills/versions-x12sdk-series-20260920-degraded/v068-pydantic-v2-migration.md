---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 68
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Before editing and throughout the migration, read and enforce
  `references/core-rules.md`. Preserve every validator body, public API,
  parser, serializer, field default, generated registry, validation phase,
  accepted input shape, output representation, and error behavior unless the
  repository contract explicitly requires a change. Never route production
  imports through `pydantic.v1`; never empty, replace, comment out, or bypass a
  function body merely to make imports succeed; never use broad mechanical
  replacement for semantically different validators; and never report success
  from compilation, imports, collection, a focused subset, a hand-written
  smoke test, or a piped command when the full suite has not passed.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, or broad search-and-replace damage
  - Tests import migration-specific public helpers such as `_is_list_field`, or generated registries depend on Pydantic field introspection
  - When deciding whether a partial or failed migration matches this procedure, read `references/core-rules.md` section `additional-triggers`.

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native v2 migration

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without `head`, `tail`, or a pipeline that masks its exit code.
      Capture the command, actual exit status, collection count, pass count,
      failure count, warnings, and the first complete traceback. If output must
      be stored, redirect it to a file, save `$?` immediately, and then inspect
      the file. Treat zero collected tests, collection errors, and timeout as
      failures rather than progress.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the exact
      repository path once and reuse it to avoid near-match path errors. Record
      every tracked modification and untracked file before editing. Do not
      discard, overwrite, or broadly restore existing work. If the tree already
      contains migration edits, classify it as a partial migration and inspect
      its diff before deciding whether to repair or selectively restore files.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject metadata,
      lock and requirements files, CI commands, package extras, supported
      Python versions, test configuration, changelog, and migration-specific
      files such as `requirements-v2.txt`. Prefer the repository's declared
      post-migration dependency set over guesses. Record the exact full-suite
      command and whether editable installation or dependency refresh is
      required.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter,
      Pydantic, pydantic-core, pydantic-settings, pytest, and installed project
      versions in the same environment used for tests. A changed pyproject does
      not change an already-installed runtime. Refresh the environment using the
      repository's installation method when required, then verify versions
      again. Do not alternate silently between Pydantic 1 and 2 environments.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      plugin modules, transaction-specific packages, dynamically imported
      modules, and generated-registry code for all v1 interfaces. Include
      multiline imports and decorator aliases; simple single-line grep is not
      sufficient. Inventory BaseSettings, Config, validator, root_validator,
      allow_reuse, each reuse assignment, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, Field(regex=), constr(regex=), min_items,
      max_items, parse_obj, dict, json, schema, copy, construct, and all custom
      Field metadata.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Record exported model
      classes, helpers, settings classes, parser APIs, serializer APIs, CLI
      output, dynamically discovered classes, and every symbol imported
      directly by tests. Treat underscore-prefixed helpers imported by tests as
      public migration contracts. In this repository family, explicitly check
      whether `x12sdk.models._is_list_field` is required; defining it only in
      another module does not satisfy that contract.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing a validator,
      inspect its complete original body, decorator arguments, field order,
      signature, call sites, tests, and representative fixtures. If the working
      copy is malformed, recover the original body from git without restoring
      unrelated files. Snapshot behavior for validators, parsing, serialization,
      repeatable-segment wrapping, component delimiters, settings environment
      loading, and errors. Never infer semantics from a truncated excerpt.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per affected
      symbol or mechanical family with file, symbol, v1 construct, intended v2
      construct, original phase and signature, behavior contract, tests,
      migration status, and verification evidence. Give every validator its own
      classification rather than treating all root validators as one replaceable
      class.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate safe mechanical edits
      from semantic edits. Mechanical candidates include dependency pins,
      BaseSettings imports, and exact API renames whose arguments are unchanged.
      Semantic work includes every validator conversion, inherited-field
      override, optional/default decision, reusable validator, metadata reader,
      serializer, parser, and registry. Plan collection blockers before broad
      cleanup.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Use small, reviewable edit
      batches and run syntax or import checks after each. Never combine a
      repository-wide decorator rewrite, signature rewrite, constraint rewrite,
      and serialization rewrite into one checkpoint. Save the diff before and
      after any scripted edit so corruption is attributable and reversible.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read `references/verification-and-repair.md`
      section `recover-malformed-partial-migration` and follow it. Search for
      malformed forms such as `@model_validator(mode="before")pre=True)`,
      duplicate decorator arguments, decorators without calls, duplicate or
      missing imports, invalid Python booleans such as `true`, damaged regex
      strings, changed indentation, accidental docstrings, and commented-out
      validator registration. Compare each repair to the original source and
      retain complete bodies. Never use `git checkout` or restore on an entire
      package merely to undo one bad edit.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Repair one complete
      traceback at a time, then rerun collection or the smallest command that
      reproduces it. Prioritize syntax, import, class-construction, and missing
      public-symbol failures. For the recurring x12sdk failure family, check
      these exact blockers early: annotate any subclass assignment such as
      `segment_name = X12SegmentName.CR5` with the inherited field's type; add
      `model_validator` to each module that uses it; and restore
      `x12sdk.models._is_list_field` at its tested import location.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Pin native Pydantic 2 and
      add `pydantic-settings` where BaseSettings is used. Import BaseSettings and
      SettingsConfigDict from `pydantic_settings`; migrate settings Config to
      SettingsConfigDict while preserving case sensitivity, prefixes, env-file
      behavior, and defaults. Convert `Field(regex=...)` to
      `Field(pattern=...)` without changing the regular expression. Reinstall or
      refresh the runtime and verify versions after dependency changes.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Replace class Config
      with ConfigDict or SettingsConfigDict while preserving `extra`,
      frozen/hashability behavior, enum representation, alias behavior,
      assignment validation, arbitrary types, and default validation. Do not
      carry removed keys such as `allow_mutation`; express their intended
      behavior with supported v2 keys. Test shared base models before editing
      hundreds of subclasses.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires a
      type annotation when a subclass overrides an inherited field. Locate all
      unannotated overrides and add the correct inherited type, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`. Do not delete all
      segment-name declarations, turn model fields into ClassVar values, or
      weaken the base field merely to silence construction. Verify both the
      concrete class schema and serialized segment name.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert renamed constraints
      such as regex to pattern and min_items/max_items to the v2 equivalents.
      Preserve requiredness deliberately: in v2, `Optional[T]` without a default
      is still required. Add `= None` only when v1 behavior, tests, fixtures, or
      public contract show omission was allowed; never mass-add defaults to all
      Optional fields. Put custom metadata in
      `json_schema_extra={"is_component": True}` using valid Python values, then
      update readers accordingly.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `allow_reuse` wrappers without deleting validation. Inventory assignment
      forms such as `_validate_ref_segments = root_validator(allow_reuse=True)(fn)`
      and migrate each according to whether `fn` consumes raw values, a model,
      or a field value. Avoid shadowing Pydantic's `field_validator` with a
      partial of itself. Preserve shared callable signatures or add explicit,
      tested adapters rather than globally rewriting helper functions.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert `@validator` to
      `@field_validator` individually. Replace the v1 `values` mapping with
      ValidationInfo and `info.data` only where the original validator depended
      on prior fields. Preserve pre-validation using `mode="before"`, ordering,
      multi-field targets, always/default behavior, and return values. Remember
      that `info.data` contains only fields already validated in declaration
      order. Test reusable date validators and payment-format validators with
      valid and invalid fixtures.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it is a before validator operating on raw input mappings or
      an after validator operating on a constructed model. Record mutation,
      return type, dependent fields, reuse, error timing, and whether assignment
      validation can invoke it. Do not classify from decorator spelling alone;
      inspect the complete body and callers.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `@model_validator(mode="before")` with mapping-compatible signatures and
      return the raw mapping. Convert post root validators to
      `@model_validator(mode="after")` with instance-compatible signatures,
      access fields through the instance, and return the instance. Preserve the
      full body and error behavior. Do not mechanically decorate a `(cls,
      values)` dictionary body as after, do not attach `pre=True` to
      model_validator, and do not change every validator to before just because
      that avoids a signature error.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Scan every Python
      module, including versioned transaction packages, for decorator use and
      confirm the matching v2 import is present exactly once. Also confirm no
      stale v1 decorator imports remain. Compile immediately after this audit.
      A module using `@model_validator` without importing it is a collection
      blocker even if another similarly named module imports it.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      class-level `model_fields` and map each former ModelField property
      intentionally; do not blindly replace `.type_`, `.name`, `.shape`, or
      `.field_info.extra`. Use FieldInfo annotation, field names from iteration,
      typing inspection, and `json_schema_extra or {}`. Test component metadata,
      parser field order, inherited fields, union/list annotations, and fields
      whose metadata is absent.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Implement or preserve the
      tested `_is_list_field` helper at its original public import location.
      It must accept the object tests pass, normally `field.annotation`, and
      detect direct lists plus optional or union-wrapped lists using
      `typing.get_origin` and `typing.get_args`. Use it in the before validator
      that wraps one dictionary into a one-item list for repeatable segments.
      Test both repeatable and scalar fields; do not relocate the helper only to
      a support module or create a circular import.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict/json and
      parsing APIs with model_dump, model_dump_json, and model_validate where
      appropriate, preserving exclude flags, enum behavior, aliases, None
      handling, custom encoders, decimal/date output, and delimiters. Do not
      mechanically replace calls on values that may be plain dictionaries.
      Preserve parser field order and metadata-driven component splitting.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit import-time registries
      and dynamic class discovery that read field defaults. Replace class
      `__fields__` access with `model_fields`, retain segment-name normalization,
      exclude abstract base classes, and verify representative 4010 and 5010
      lookups. An import succeeding is insufficient if the registry is empty or
      maps the wrong segment keys.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile every production Python
      file, not only edited top-level modules. Treat malformed decorators,
      indentation errors, invalid booleans, damaged strings, and missing closing
      parentheses as failed migration checkpoints. Compilation is only a syntax
      gate and never completion evidence.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import representative core,
      versioned, transaction-specific, parser, settings, and public-helper
      modules, then run the repository's complete collection command without
      truncating its status. Require the expected tests to collect and zero
      collection errors. Continue on the first complete traceback; do not stop
      because three hand-picked imports succeeded.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for settings,
      shared models, 4010 segments, 5010 segments, loop initializers, repeatable
      segments, parsing, serialization, registries, support utilities, and each
      migrated validator family. Capture the actual exit code rather than the
      exit code of `head`, `tail`, `tee`, or grep.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare accepted and rejected
      inputs, default insertion, error locations, validator order, emitted X12,
      model dumps, settings loading, and repeatable-segment normalization to the
      semantic snapshots. Specifically probe missing Optional values, ACH
      payment requirements, paired identifiers, date formats, adjustment
      groups, and list-versus-dict input.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Use the loop: run a real
      command, read the complete first traceback, inspect the relevant original
      body and tests, make the smallest semantic repair, compile, rerun the
      focused reproducer, rerun collection when imports changed, and periodically
      rerun the full suite. Never replace debugging with another repository-wide
      sed or regex pass.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every scripted or bulk edit
      in the diff. Check decorators, imports, signatures, indentation, regex
      strings, defaults, type annotations, metadata, and function bodies.
      Ensure no replacement changed ordinary variables named `validator`,
      inserted duplicate imports, converted Python syntax into JSON syntax, or
      damaged non-Pydantic code.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Require no production
      `pydantic.v1` imports, stale BaseSettings imports, v1 validators,
      root_validator, allow_reuse, SHAPE_LIST, ModelField assumptions,
      `field_info.extra`, unsafe `__fields__`, malformed model_validator usage,
      or unsupported constraints. Manually classify any remaining dict/json
      calls rather than assuming every match is a BaseModel call.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact repository full-suite command without output
      truncation or masked status. Save the output and actual exit code. Require
      exit zero, expected collection count, and no hidden collection errors.
      Warnings must be reviewed for remaining migration debt even when they do
      not fail the command.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Compare full-suite evidence
      and semantic snapshots, then verify public helpers, parser and serializer
      output, settings, registries, repeatable segments, custom metadata, and
      errors. A green subset or custom smoke script is not a substitute for the
      full suite.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect git diff and status for
      accidental files, temporary migration plans, summaries, scripts, broad
      unrelated changes, deleted bodies, commented registrations, compatibility
      shims, and generated artifacts. Confirm dependency metadata and source
      edits agree. Do not erase pre-existing user changes while cleaning up.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section `report-completion`
      and follow it. Report changed behavior surfaces, exact validation commands,
      collected and passed test counts, actual full-suite exit status, warnings,
      and any residual risk. Claim completion only when the final gate contains
      native-v2 static-audit success and a complete full-suite exit of zero.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; that postpones rather than completes the native v2 migration.
  - Never empty, replace with `pass`, comment out, or bypass a validator, parser, serializer, registry, or helper body merely to make imports or tests proceed.
  - Never declare success after imports, compileall, collection, a focused subset, a hand-written smoke test, or a claimed test summary that did not run the real full suite.
  - Never pipe the decisive pytest command through `head`, `tail`, grep, or an unchecked `tee`; the pipeline can return zero while pytest failed.
  - Never perform repository-wide decorator replacement without classifying each validator as field, model-before, or model-after and preserving its complete body.
  - Never convert every root validator to `mode="before"` or every root validator to `mode="after"`; phase and signature are semantic.
  - Never retain `(cls, values)` dictionary logic under an after model validator or access `info.data` as though it were a complete model.
  - Never use broad sed or regex edits that can produce malformed decorators, duplicate imports, indentation damage, invalid booleans, or corrupted regular expressions.
  - Never mass-add `None` defaults to every Optional field; Optional type and omission default are separate contracts in Pydantic v2.
  - Never delete or convert inherited model fields to ClassVar merely to suppress an override error; annotate concrete overrides with their actual field type.
  - Never remove subclass `segment_name` fields wholesale; preserve their values and annotate only unannotated overrides.
  - Never define a required public helper only in a different module; preserve its tested import path, including underscore-prefixed helpers.
  - Never assume a metadata key still lives in `field_info.extra`; migrate both its writer and every reader to `json_schema_extra`.
  - Never assume `__fields__` to `model_fields` is a complete mechanical rewrite; replace ModelField properties according to their v2 meanings.
  - Never treat an import-time registry as verified merely because its module imports; assert representative keys and values.
  - Never use `git checkout` or restore on an entire package to undo a local mistake when it would discard valid migration progress or user changes.
  - Never overwrite a dirty working tree, ignore pre-existing edits, or create migration summaries and temporary scripts inside the repository without a repository need.
  - Never trust prose such as "all tests pass" without the exact full-suite command, expected collection count, and actual zero exit status.
```