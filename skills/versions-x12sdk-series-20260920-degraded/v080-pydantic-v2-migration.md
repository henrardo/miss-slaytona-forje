---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or repairing import, syntax, schema, validation, parsing, collection, or test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 80
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Before editing and throughout the migration, read and enforce
  `references/core-rules.md`. Preserve every validator body and public contract:
  never redirect production imports through `pydantic.v1`, never empty or bypass
  a function merely to make imports succeed, and never report completion from
  import smoke tests or a partial passing count.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - When deciding whether a partial or failed migration matches this procedure, read `references/core-rules.md` section `additional-triggers`

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native v2 migration
  - The requested change is merely to suppress Pydantic deprecation warnings without preserving and testing behavior

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without truncating its output and preserve its actual exit status.
      Do not use `| head`, `| tail`, or `| tee` unless `set -o pipefail` is active
      and the test process status is captured separately. Record the complete
      first traceback, collection count, pass count, fail count, warning count,
      command, and exit code. A command whose pipeline exits zero while pytest
      failed is not a valid baseline.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the exact
      repository path before every edit. Inventory pre-existing tracked and
      untracked changes, distinguish harness files such as `.vibe/`, and do not
      reset, checkout, overwrite, or discard user changes. If the workspace is
      already partially migrated, treat its diff and failures as evidence rather
      than repeatedly restarting from HEAD.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      Read `references/core-rules.md` section `execution-discipline` and follow
      it. Work in small semantic units: inspect the complete original body,
      change one related construct, compile or import it, run the narrowest
      relevant test, inspect the diff, and only then continue. Use exact paths
      copied from `pwd`; repeated mistyped paths are a signal to stop and verify
      location. Do not narrate success or end the turn while tests remain red.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect dependency metadata,
      lockfiles, CI workflows, supported Python versions, extras, test settings,
      package entry points, requirements-v2 files, and repository-specific
      migration tests before editing production code. The full CI command is the
      completion authority unless the user specifies another command.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify versions using the same
      Python executable that will run tests. Install or update Pydantic v2 and
      `pydantic-settings` only when repository metadata requires it, then
      re-check imports and versions. Do not let an editable install silently
      downgrade Pydantic back to v1, and do not use `pydantic.v1` as a migration
      shortcut.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      generated registries, nested transaction packages, settings, parser and
      CLI code for every v1 interface. Include multiline imports and decorator
      aliases, not only single-line grep matches. Record malformed partial-v2
      syntax separately, including doubled decorators, missing imports,
      `@model_validator(mode="before")pre=True)`, extra parentheses, invalid
      indentation, lowercase `true`, and scripts or broad edits left by earlier
      attempts.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include public model
      classes, settings classes, parser behavior, `.x12()` output, CLI exports,
      validation errors, reusable validators, segment registries, and helpers
      imported directly by tests. In particular, preserve helpers such as
      `_is_list_field` even if they did not exist in the original v1 module but
      are required by migration-specific tests.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before rewriting each
      validator, read and retain its complete original body, decorator options,
      field order assumptions, mutation behavior, return value, exception type,
      error text, and validation timing. Use git source or a clean copy to
      recover bodies corrupted by a partial migration. Never replace a body with
      `pass`, `return self`, an unconditional value, a comment, or a no-op solely
      to make import or collection succeed.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one row per migration site
      with file, symbol, v1 construct, intended v2 construct, original semantics,
      affected tests, status, and latest failure. Include every validator and
      every reusable decorator assignment individually; a grep count is not a
      substitute for the ledger.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by dependency:
      syntax and imports, settings, shared base models, inherited fields and
      field declarations, reusable validation infrastructure, field validators,
      model validators, introspection, parsing and serialization, registries,
      then transaction-specific packages. Separate mechanical renames from
      semantic rewrites; only the former may be automated.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Establish reversible
      checkpoints without overwriting unrelated changes. After each checkpoint,
      run `py_compile` or `compileall`, import the changed module, run focused
      tests, and inspect `git diff`. If a transform changes many files, sample
      the beginning, middle, and end of every affected pattern before proceeding.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Repair syntax from
      complete tracebacks before semantic migration. Prefer restoring only the
      malformed hunk from known-good source and reapplying a small correct edit;
      do not run another broad regex over damaged code. Compile every changed
      file immediately and inspect decorators and imports around each repair.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the first complete
      collection traceback and rerun collection without output truncation.
      Continue until collection advances. Import smoke tests prove only that one
      module imports; they never prove the migration or suite is complete.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update all authoritative
      dependency declarations consistently. Import `BaseSettings` and
      `SettingsConfigDict` from `pydantic_settings`, keep `Field` in
      `pydantic`, replace settings `Config` with `model_config`, and preserve
      case sensitivity, environment names, defaults, and cache behavior.
      Replace removed `Field(regex=...)` with `pattern=...` and test both valid
      and invalid settings values.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert class-based
      `Config` to `ConfigDict` while preserving `extra`, enum handling,
      immutability, hashing, arbitrary types, assignment validation, aliases,
      and default validation. Use `frozen=True` for v1 immutability rather than
      retaining removed `allow_mutation=False`. Apply configuration to the
      correct base class so subclasses inherit intended behavior.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 rejects a
      subclass that replaces an inherited model field with an unannotated
      attribute. Find every such override, including registry keys such as
      `segment_name = X12SegmentName.CR5`, and add the correct annotation rather
      than deleting the field or weakening the base model. Compile and import
      both large versioned segment modules after this pass.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed field keywords
      and constrained-type arguments, including `regex` to `pattern`, without
      changing accepted values. Preserve custom metadata under
      `json_schema_extra` using valid Python values such as `True`, not JSON
      `true`. Audit every `Optional[T]`: in v2 it remains required unless it has
      `= None` or an equivalent default. Add defaults only where v1 behavior,
      fixtures, or public contracts prove omission was allowed; never perform a
      repository-wide Optional rewrite. Preserve numeric constraints and avoid
      changing a string field to an integer merely to satisfy a schema error.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      `allow_reuse`; v2 handles reuse differently. Do not shadow the imported
      `field_validator` with a partial of itself or import it from
      `pydantic.validators`. For validator functions imported and attached in
      many models, preserve the callable contract and attach them using native
      v2 decorators at each intended field or model boundary. Handle
      `check_fields=False` only when inheritance requires it. Test representative
      attachment sites in both version families.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each v1 `@validator`
      individually to `@field_validator`; do not use blind decorator
      substitution. Classify `pre`, `always`, multi-field, reused, and inherited
      behavior. Replace v1 `values` access with `ValidationInfo` and
      `info.data`, remembering that only previously validated fields are
      available. Use `mode="before"` only when the original used `pre=True`.
      Preserve validation of defaults with model configuration or field settings
      where required. Ensure the decorator name is imported wherever used, and
      remove stale `validator` imports only after all decorators are migrated.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every v1
      `@root_validator` and functional `root_validator(...)(function)`
      assignment, record whether it must inspect raw input before validation or
      a validated model after validation. Record whether the body expects a
      dictionary, model instance, nested dictionaries, nested model instances,
      or field-order-dependent data. Never infer mode from a search-and-replace
      rule, and never convert all root validators to one mode.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert v1 `pre=True`
      validators to `@model_validator(mode="before")` operating on raw input and
      returning the input mapping. Convert post validators to
      `@model_validator(mode="after")` operating on `self` and returning
      `self`; rewrite dictionary reads and writes to attribute access without
      changing the validation logic. Preserve every raise condition, mutation,
      calculation, and error message. Pay special attention to nested loops:
      post-validation children are model instances, so code that previously
      indexed dictionaries may need attribute access or a deliberate
      `model_dump()` boundary. Add `@classmethod` only where the v2 decorator
      contract requires it. After each conversion, instantiate a valid and
      invalid representative case.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Scan every production
      file for decorator uses and imports together. No file may use
      `@validator`, `@root_validator`, `validator(...)`, or
      `root_validator(...)`; no file may use `field_validator` or
      `model_validator` without importing the correct native v2 symbol. Compile
      and import both top-level versioned segment modules. Specifically prevent
      the observed regressions where v4010 raised `NameError: validator is not
      defined` and v5010 retained a post `@root_validator` requiring
      `skip_on_failure=True`.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      `model_fields`, `ModelField` assumptions with `FieldInfo` and type
      introspection, `field_info.extra` with guarded `json_schema_extra`, and
      removed `SHAPE_LIST` checks with `typing.get_origin` logic that handles
      `list`, `List`, `Optional[List[T]]`, and unions. Do not mechanically map
      obsolete attributes such as `type_`, `outer_type_`, `shape`, or `name`;
      derive each replacement from its use. Guard `json_schema_extra or {}`.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Implement or retain the public
      `_is_list_field` helper in the module from which tests and users import it.
      Make it accept v2 `FieldInfo` or its documented annotation input, unwrap
      optional and union annotations, and return true only for list fields.
      Reuse it in the before-model validator that wraps a single segment
      dictionary into a list. Test required lists, optional lists, non-list
      fields, a bare dictionary, an existing list, and `None`.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace v1 methods such
      as `dict`, `json`, `parse_obj`, and schema methods with native v2 methods
      only at genuine Pydantic model boundaries. Preserve `exclude`, alias,
      enum, delimiter, null, unset, decimal, date, and nested-model behavior.
      Update parser field iteration and component metadata lookup to v2 APIs.
      Do not call `model_dump()` on ordinary dictionaries, and when shared code
      can receive either a dictionary or model, branch explicitly. Test parser,
      CLI, `count_segments`, duplicate-code validation, and `.x12()` output.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time registries
      that enumerate segment classes or read field defaults. Replace
      `__fields__["segment_name"].default` with guarded v2 `model_fields`
      access, preserve exact registry keys and class values, and exclude base
      classes exactly as before. Import both version registries and compare
      representative entries and counts with the original contract.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile every production Python
      file, not only recently edited modules. Treat indentation errors, malformed
      decorators, doubled arguments, invalid Python booleans, duplicate imports,
      and missing names as migration failures. Fix each from its complete
      traceback before proceeding.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, support, parsing, both versioned segment modules, representative
      transaction packages, and public helpers. Then run the complete collection
      command without truncation and require exit zero. Record collected test
      count and compare it with the expected repository count so silently lost
      tests cannot look green.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for settings,
      shared models, both segment versions, loop initializers, repeatable
      segments, parsing, serialization, support helpers, registries, and each
      changed transaction package. Use actual pytest node IDs discovered by
      collection; a misspelled or nonexistent node is not a passing test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare valid construction,
      invalid construction, omitted optionals, defaults, extra fields, aliases,
      nested models, reusable validators, error locations, exception types, and
      messages against semantic snapshots and tests. A model that imports but
      makes formerly optional fields required, skips a validator, or changes
      `.x12()` output is not behavior-preserving.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work from the first complete
      failure, fix its root cause, rerun the smallest reproducer, then rerun the
      broader gate. Update the migration ledger after every repair. Do not batch
      unrelated fixes, repeatedly restart the migration, create summary files
      while tests are red, or stop because 56, 57, 58, or any other partial
      number of tests passes.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every line changed by scripts,
      regex, `sed`, or formatters. Reject broad substitutions that add duplicate
      imports, erase arguments, corrupt decorators, change all model validators
      to one mode, convert all optionals, alter unrelated regex code, or produce
      syntax such as doubled parentheses. Automated edits are acceptable only
      for proven mechanical patterns followed by compile, diff, and behavior
      checks.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for all
      prohibited compatibility imports and remaining v1 interfaces. Distinguish
      documentation mentions from executable code. Also search for malformed
      partial migration artifacts, empty validator bodies, temporary scripts,
      migration summaries, and accidental generated files.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact complete repository or CI test command with no
      `-x`, no selected files, no output truncation, and no status-masking
      pipeline. Require the test process itself to exit zero. Capture total
      collected, passed, failed, skipped, xfailed, and warning counts.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Re-run representative
      positive and negative contract probes after the full suite: settings
      environment behavior, immutable delimiters, enum serialization,
      repeatable-segment wrapping, component separators, parser/model round
      trips, registry lookups, nested loop validation, and public helper imports.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the complete diff and
      status, remove accidental summaries and temporary migration scripts unless
      requested, preserve pre-existing user changes, and verify dependency files
      agree. Explicitly reject any production `pydantic.v1` import and any
      function or validator whose body was emptied, bypassed, or reduced to a
      no-op to obtain green tests.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only when the final
      gate proves native v2 imports, successful compilation, complete collection,
      focused contract coverage, static audit success, and an untruncated
      full-suite exit code of zero. State the exact command and result. If any
      gate is red or unrun, report the remaining blocker instead of claiming
      success.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`, `pydantic.v1.*`, or another v1 compatibility namespace to make tests pass.
  - Never empty, comment out, bypass, replace with `pass`, or reduce a validator or function body to an unconditional return merely to make a module import.
  - Never treat successful imports, compilation, collection, a hand-written smoke script, or a partial passing count as proof that the suite passes.
  - Never pipe pytest through `head`, `tail`, or `tee` and then trust the pipeline's zero exit status without `pipefail` and explicit test-process status capture.
  - Never globally replace every root validator with the same model-validator mode; classify and migrate every validator from its original semantics.
  - Never use repository-wide `sed` or regex transformations for semantic changes such as validator signatures, dictionary-to-instance conversion, optional defaults, or nested model access.
  - Never remove a deprecated decorator import before migrating every decorator use in that file; audit imports and decorators together.
  - Never add `skip_on_failure=True` merely to retain deprecated post root validators; migrate them natively to correctly shaped model validators.
  - Never make every `Optional` field default to `None` in bulk; preserve whether omission was accepted from tests and original behavior.
  - Never delete an inherited field override to silence a Pydantic v2 error; annotate it correctly and preserve its registry or serialization role.
  - Never delete or relocate a public helper such as `_is_list_field` when tests or consumers import it directly.
  - Never assume `model_dump()` can replace `.dict()` on arbitrary values; distinguish models from dictionaries and preserve serialization options.
  - Never continue after an automated edit until production code compiles and the affected diff has been inspected for malformed decorators, indentation, imports, and literals.
  - Never repeatedly reset or checkout broad production paths after making progress; recover only the malformed hunk while preserving valid migration work and user changes.
  - Never write a migration summary or declare the task complete while collection or any focused or full-suite test remains red.
```