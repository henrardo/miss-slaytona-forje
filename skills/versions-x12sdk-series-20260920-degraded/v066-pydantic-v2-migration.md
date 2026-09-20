---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 66
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Before editing and throughout the migration, read and enforce
  `references/core-rules.md`. Preserve validator bodies, public APIs, parsing,
  serialization, generated registries, validation timing, and error behavior.
  Never route production imports through `pydantic.v1`, never empty or replace a
  function body merely to make imports succeed, and never report success from
  import checks, compilation, collection, a focused subset, or a piped command
  when the full suite has not passed.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, duplicated decorator arguments, or accidental edits outside Pydantic syntax
  - Test commands were piped through head, tail, tee, or grep and therefore appeared successful despite pytest failing
  - A migration repeatedly cycles between import errors because broad search-and-replace changed decorators without adapting signatures and function bodies
  - Pydantic reports that post root validators require skip_on_failure or that model_validator rejects the pre argument
  - Tests import a public compatibility helper such as _is_list_field that disappeared during migration
  - Collection fails because a v1 post root_validator remains, or because a partial conversion produced model_validator(pre=True)
  - A repository contains hundreds of similar models where unsafe global replacements can silently damage unrelated Python syntax
  - The first collection traceback says BaseSettings moved to pydantic-settings
  - Optional fields became required, inherited fields raise annotation errors, or model registries no longer discover segment classes after upgrading

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
      command without truncating its output. Capture the exact command, actual
      exit status, collection count, pass/fail/error counts, and first complete
      traceback. If output must be logged, redirect it to a file and inspect the
      file afterward. Do not use `pytest ... | head`, `tail`, `grep`, or an
      unguarded `tee`; those report the pipeline consumer's status instead of
      pytest's. If a pipeline is unavoidable, enable pipefail and record
      `PIPESTATUS`. Treat zero collected tests, import-only checks, and pytest
      exit code 5 as failures.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Verify the repository
      path before every scripted batch operation. Record tracked modifications,
      untracked files, branch, and diff before editing. Preserve user changes.
      Do not assume a prior attempt's dirty tree is correct, and do not use
      `git checkout`, `git restore`, or reset on paths containing user work
      merely to escape a difficult migration.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject/setup
      metadata, lock and requirements files, CI workflows, supported Python
      versions, test configuration, package layout, requirements-v2 or other
      migration fixtures, and repository documentation. Use the CI command as
      the source of truth when available. Note that a missing requirements.txt
      is not an error when pyproject.toml owns dependencies.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Confirm the interpreter running
      tests imports native Pydantic 2 and required split packages such as
      pydantic-settings. Update declared dependencies before relying on ad hoc
      environment installs. Reinstall the project only when the repository
      contract requires it, then recheck versions from the same interpreter used
      by pytest. Do not alternate between Pydantic 1 and 2 environments while
      diagnosing source failures.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code and tests for
      BaseSettings, class Config, validator, root_validator, allow_reuse,
      __fields__, ModelField, field_info.extra, SHAPE_LIST, Field(regex=),
      constr(regex=), min_items/max_items, parse_obj, parse_raw, from_orm,
      dict/json/copy/schema methods, custom reusable validator factories,
      generated registries, and direct imports from pydantic internals. Record
      files, line numbers, counts, and semantic categories; do not interpret a
      grep miss caused by a malformed pattern as proof the surface is absent.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Record public model,
      settings, parser, serializer, CLI, helper, and registry APIs imported by
      tests or users. Include private-looking helpers imported by tests, such as
      `_is_list_field`; their import path and behavior are part of the effective
      contract. Identify tests for single-dict-to-list wrapping, optional fields,
      exact X12 output, error behavior, settings environment variables,
      immutability, and registry discovery.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before converting each
      validator or helper, save its complete original decorator, signature,
      body, tests, ordering assumptions, and return convention. Use the clean
      committed source as a semantic reference when the working tree contains a
      malformed partial migration, but do not discard unrelated working changes.
      An importable stub is not a semantic snapshot.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per migration
      site with file, symbol, v1 construct, intended v2 construct, validator
      phase, fields read or written, expected return type, public contract,
      focused test, and status. Include every occurrence rather than only the
      first match in large segment or loop modules.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical renames from
      semantic rewrites. Mechanical examples include BaseSettings import,
      regex-to-pattern, and model method renames after call-site review.
      Semantic work includes validator signatures and modes, optional defaults,
      inherited field overrides, reusable validators, introspection, and
      registries. Never treat all root validators as the same kind of edit.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Divide work into reversible
      checkpoints: dependencies/settings, core models, shared validator
      infrastructure, one model family at a time, parsing/serialization, and
      registries. After each checkpoint run compilation plus the narrowest
      meaningful import or focused test. Do not migrate all 65 files before
      checking syntax.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      code and inspect every syntax error before semantic edits. Search for
      malformed forms such as `model_validator(pre=True)`,
      `model_validator(mode="before")pre=True)`, doubled parentheses,
      duplicated mode arguments, missing imports, invalid lowercase Python
      booleans, damaged regex literals, bad indentation, and comments that
      accidentally disabled validators. Compare suspicious functions against
      original source and restore full bodies. Never globally mutate arbitrary
      parentheses, quotes, `regex` text, or import blocks.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the earliest
      complete collection traceback, then immediately rerun the same untruncated
      collection command. When the traceback says BaseSettings moved, update
      the dependency declaration, import BaseSettings and SettingsConfigDict
      from pydantic_settings, migrate its Config, change Field(regex=) to
      Field(pattern=), run a direct config import, and rerun collection before
      exploring later model failures. Continue one blocker at a time; do not
      spend the attempt writing summaries while collection still fails.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Change the authoritative
      dependency metadata to native `pydantic>=2,<3` and add a compatible
      pydantic-settings dependency when BaseSettings is used. Import Field from
      pydantic and BaseSettings/SettingsConfigDict from pydantic_settings.
      Convert settings Config to `model_config = SettingsConfigDict(...)` while
      preserving case sensitivity, environment behavior, prefixes, and dotenv
      behavior. Verify the settings object and environment overrides directly.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Replace class Config
      with ConfigDict on each shared base model while preserving
      use_enum_values, extra handling, aliases, assignment validation,
      population rules, arbitrary types, and immutability. Translate
      `allow_mutation=False` to `frozen=True`; do not leave removed config keys
      inside ConfigDict. Decide whether defaults must be validated and set
      validate_default only when required by existing behavior.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Find subclasses that
      override inherited Pydantic fields without annotations, especially
      constant discriminator fields such as `segment_name = ...`. Add explicit
      compatible annotations rather than deleting the field or weakening base
      model validation. Import every annotation symbol used. Test representative
      subclasses and registry discovery after the change.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert Field(regex=) and
      constr(regex=) to supported pattern forms, and list constraints to
      min_length/max_length where appropriate. Preserve each original regex
      exactly, including anchors and grouping. Review Optional fields: in
      Pydantic 2 `Optional[T]` without a default remains required, so add
      `= None` only where v1 behavior or tests made omission valid. Do not
      perform a blind repository-wide Optional rewrite. Move arbitrary Field
      metadata such as `is_component` into
      `json_schema_extra={"is_component": True}` using valid Python booleans.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `functools.partial(validator, allow_reuse=True)` aliases and direct
      allow_reuse arguments. Import native field_validator/model_validator
      where decorators are defined or applied. Preserve reusable validation
      functions as functions and apply native decorators at model declaration
      sites. Avoid exporting a helper under the name `field_validator` if it
      shadows Pydantic's decorator or changes accepted arguments.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator
      individually to field_validator, selecting mode="before" only when the v1
      validator used pre=True or requires raw input. Replace the v1 `values`
      argument with ValidationInfo and read prior fields from `info.data`.
      Preserve field order dependencies, always/run-on-default behavior,
      exception types, return values, and multiple-field decorators. Add
      `@classmethod` where required. Do not mechanically rename the decorator
      while leaving a v1 signature.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      explicitly classify it as before or after from its original decorator and
      body. Record whether it receives raw mappings or validated instances,
      whether it mutates data, and which fields it reads. A bare v1 post
      root_validator is after; `pre=True` is before. Never convert every root
      validator to mode="before" or every one to mode="after".
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `@model_validator(mode="before")` methods that accept and return raw data.
      Convert post root validators to `@model_validator(mode="after")` methods
      that accept `self`, inspect attributes, and return `self`. Adapt shared
      dictionary-oriented validation functions deliberately rather than passing
      model instances into them. Remove skip_on_failure and allow_reuse only
      after preserving their effective behavior. Keep every validation branch
      and error message; never replace a difficult body with `pass`, `return
      values`, or `return self` unless that was its complete original behavior.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every file,
      compare decorator usage with imported names. Ensure field_validator,
      model_validator, ValidationInfo, and classmethod usage are consistent.
      Search for remaining validator/root_validator imports and decorators,
      malformed decorator calls, unsupported `pre` or `allow_reuse` arguments,
      and aliases that still point to v1 decorators. Compile and import each
      affected module immediately.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields and adapt code to Pydantic 2 FieldInfo rather than assuming
      v1 ModelField attributes such as name, type_, shape, or field_info.
      Retrieve custom metadata from `field.json_schema_extra or {}`. Use
      `typing.get_origin`, `get_args`, and union unwrapping for container and
      nested-model detection. Avoid deprecated instance-level model_fields
      access when class-level access is available.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Keep or restore the public
      `_is_list_field` helper at the import path expected by tests. Make it
      accept Pydantic 2 FieldInfo or annotations as required by callers, detect
      list origins through Optional/Union/Annotated wrappers, and return false
      for scalar fields. Use it in the before validator that wraps a bare dict
      into a one-element list for repeatable segments. Test both helper behavior
      and single-dict loop initialization.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace model.dict,
      json, parse_obj, parse_raw, copy, schema, and construct with appropriate
      v2 APIs only after reviewing arguments and expected output. Update parser
      field iteration to model_fields and json_schema_extra. Preserve enum,
      Decimal, date, exclusion, alias, unset, none, and delimiter behavior.
      Test exact X12 output, CLI JSON output, recursive segment counting, parser
      output delimiters, duplicate-code validators, and model discovery.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect module-level loops
      that build segment or transaction registries from model classes. Replace
      __fields__ access with model_fields without changing keys, enum handling,
      or discovery criteria. Guard intentionally abstract classes rather than
      swallowing errors. Confirm expected registry sizes and representative
      lookups for every supported X12 version.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile over
      all production modules, not only recently edited files. Repair every
      syntax and indentation error before running behavior tests. Compilation
      is a gate, not proof of completion.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import settings, core
      models, support utilities, both versioned segment modules, representative
      transaction modules, parser, CLI, and every public helper identified in
      the contract. Then run untruncated `pytest --collect-only` and require its
      actual exit code to be zero with the expected nonzero collection count.
      Fix one complete traceback at a time.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for settings,
      core models, support, 4010 segments, 5010 segments, repeatable segments,
      loop initializers, parsing, serialization, registries, and any validator
      family changed. Do not infer a test node name; list or inspect tests when
      necessary. Capture actual exit status and complete failure output.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare valid and invalid
      fixtures against the semantic snapshots. Check requiredness, defaults,
      coercion, field order, before/after timing, error locations and messages,
      mutation, extra handling, enum output, immutability, and nested errors.
      Treat passing imports with changed validation behavior as a failed
      migration.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Iterate in this order:
      compilation, imports, collection, one focused failure, affected subset,
      then full suite. After each edit rerun the narrow failing test and its
      surrounding module. Do not end the turn with a plan, summary, or
      "task completed" while any gate is red. If time is limited, prioritize
      executable repairs and tests over migration reports or new documentation.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every file touched by sed,
      regex, or scripts. Inspect git diff for damaged imports, unrelated
      replacements, lowercase true/false, malformed patterns, duplicated
      decorators, stripped classmethods, empty bodies, and indentation changes.
      Broad automated edits are acceptable only when narrowly scoped, previewed,
      mechanically validated, and followed by semantic review.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, class Config, v1
      decorators, allow_reuse, unsupported model_validator arguments,
      __fields__, ModelField, SHAPE_LIST, field_info.extra, removed constraints,
      deprecated model methods, malformed decorators, and suspiciously empty
      validator bodies. Every remaining match must be removed or explicitly
      justified as documentation or compatibility evidence outside production.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's complete real test command with no
      truncating pipeline and record command, exit code, collected count,
      passed, failed, errors, skipped, warnings, and duration. Success requires
      exit code zero and a credible nonzero test count. A focused subset with
      56 or 57 passing tests is progress, not completion.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Recheck public imports,
      helpers, settings environment behavior, parser and CLI output, exact X12
      serialization, list wrapping, registry contents, valid and invalid model
      construction, and warning policy. Verify migration-specific regression
      tests cover the failures repaired.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect final git status and
      diff, remove accidental scratch files and generated migration summaries
      unless requested, preserve pre-existing user files, and rerun compilation,
      static audit, and the full suite after final cleanup. Reject completion if
      production imports use pydantic.v1, any function body was emptied to make
      imports pass, the full suite was not run, or its actual exit code is
      nonzero.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report concise changed areas, exact
      verification commands, full-suite counts and exit status, static-audit
      result, and any remaining warnings or risks. State failure honestly if a
      gate is not green. Never claim completion based only on imports,
      compileall, collection, manual snippets, or selected tests.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not redirect production imports to `pydantic.v1`; the target is native Pydantic v2.
  - Do not empty, stub, comment out, or replace a function or validator body merely so the module imports.
  - Do not mechanically rename validator decorators without adapting signatures, modes, data access, and return values.
  - Do not convert every root validator to the same model_validator mode.
  - Do not use broad repository-wide sed or regex substitutions without previewing scope, compiling immediately, and auditing the diff.
  - Do not globally add `= None` to every Optional field; decide requiredness from prior behavior and tests.
  - Do not remove inherited discriminator fields to silence annotation errors; annotate compatible overrides.
  - Do not delete public helpers such as `_is_list_field` because their names look private.
  - Do not replace `is_component=True` metadata without updating all readers to json_schema_extra.
  - Do not assume `model_fields` has v1 ModelField attributes such as shape, type_, name, or field_info.
  - Do not damage regex literals while changing `regex` to `pattern`; preserve the original expression exactly.
  - Do not use lowercase JSON booleans in Python source.
  - Do not install Pydantic 1 to make tests pass when the declared target is Pydantic 2.
  - Do not repeatedly reinstall dependencies instead of repairing the source traceback.
  - Do not use a failed grep command, malformed regex, or wrong repository path as evidence that no migration sites remain.
  - Do not pipe pytest through head, tail, grep, or unguarded tee and then trust the pipeline exit code.
  - Do not treat pytest exit code 5, zero collected tests, or import-only smoke checks as success.
  - Do not stop after collection, compilation, one import, or a small focused subset passes.
  - Do not claim success without the complete repository test command exiting zero.
  - Do not spend the remaining attempt writing plans, ledgers, summaries, or reports while executable migration gates remain red.
  - Do not discard a dirty working tree wholesale to escape malformed edits; preserve user work and revert only proven migration damage.
  - Do not create migration scripts in temporary paths and run them without verifying their target file count and resulting diff.
  - Do not silence exceptions in generated registries or parsers to hide broken model discovery.
  - Do not report "all tests pass" from a custom Python snippet that did not run the test suite.
```