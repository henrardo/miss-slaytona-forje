---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 60
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's complete, untruncated test command exits successfully.
  Preserve every validator body, public helper, parser, serializer, registry,
  field constraint, default, validation phase, and error contract. Never route
  production imports through pydantic.v1, and never empty, stub, comment out,
  weaken, or bypass a function merely to make imports or tests proceed. Treat
  collection as an intermediate gate rather than completion. Make small,
  reviewable edits; compile and test after each checkpoint; diagnose the first
  complete traceback instead of applying speculative global replacements.
  Before starting and throughout the migration, read and enforce
  `references/core-rules.md`.

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

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native migration

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real,
      complete test command without piping it through head, tail, grep, tee, or
      any command that can hide pytest's exit status. If output is large,
      redirect it to a file, save `$?` immediately, and inspect the file in
      separate commands. Record the exact command, exit code, runtime versions,
      collection count, pass count, and first complete traceback. Zero tests
      passing, successful imports, or successful collection is not a green
      suite.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      path before every scripted edit because similarly named temporary paths
      have caused repeated failures. Record tracked and untracked changes and
      distinguish pre-existing user work from migration edits. Do not reset,
      checkout, or overwrite unrelated work. Do not restore an entire package
      merely because one automated edit failed; recover only known damaged
      regions from an authoritative original.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject metadata,
      lock and requirements files, CI commands, supported Python versions,
      package layout, test configuration, generated code, and any provided
      post-migration dependency file. Treat repository-specific migration
      fixtures and tests as source-of-truth contracts. Do not assume setup.py or
      requirements.txt exists; discover files before reading them.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify Pydantic,
      pydantic-core, pydantic-settings, Python, pytest, and the imported package
      path in the same interpreter used by tests. Do not run an editable
      install against stale `pydantic<2` metadata after manually installing v2,
      because it can silently downgrade the runtime. Update dependency metadata
      first, then install the intended target set. Recheck versions after every
      install.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests, and
      generated modules for BaseSettings, class Config, validator,
      root_validator, allow_reuse, __fields__, ModelField, SHAPE_LIST,
      field_info.extra, regex constraints, constrained types, Optional fields
      without defaults, dict/json/copy/schema/parse methods, custom metadata,
      inherited field overrides, reusable validator factories, generated
      registries, and public helper imports. Also search for malformed partial
      migration forms such as `model_validator(pre=True)`,
      `model_validator(mode="before")pre=True)`, doubled parentheses, duplicate
      mode arguments, missing decorator imports, lowercase `true`, and comments
      that disabled executable validation.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Record all symbols
      imported by tests or users, including private-looking compatibility
      helpers such as `_is_list_field`, model class names, settings factories,
      CLI behavior, parser output, `.x12()` methods, registry maps, and expected
      validation errors. A helper used by tests is part of the migration
      contract even if it did not exist in the original upstream source.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before rewriting each
      validator or damaged function, capture its original import, decorator,
      signature, complete body, return value, field order assumptions, and
      tests. If the working copy is malformed, use `git show HEAD:path`,
      another trusted revision, or an untouched parallel implementation to
      recover the complete function. Never infer a replacement solely from a
      truncated traceback, and never empty or comment out the function body to
      make the module import.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per affected
      import, config class, field, validator, introspection call, serializer,
      parser, public helper, and registry. Record file and line, v1 behavior,
      intended v2 form, dependent tests, migration status, and verification
      command. Do not summarize dozens of validators as one untracked batch.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Classify work into collection
      blockers, settings and dependencies, shared model behavior, field
      definitions, field validators, before model validators, after model
      validators, reusable validators, introspection, serialization, parsing,
      registries, and public compatibility helpers. Order work so foundational
      shared behavior is repaired before dependent transaction modules, while
      still fixing only the first observable blocker at each test iteration.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Use small semantic batches,
      normally one shared concern or one validator family at a time. After each
      batch run compilation, the narrowest relevant import, and focused tests.
      Inspect the diff before continuing. Avoid repository-wide sed or regex
      rewrites of decorators, signatures, Optional fields, imports, regular
      expressions, or Field calls; these constructs require semantic
      classification and broad replacements repeatedly produced corrupted code.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      code first and repair SyntaxError, IndentationError, malformed imports,
      duplicate decorator arguments, lowercase JSON booleans in Python, damaged
      regex strings, and accidental non-Pydantic substitutions. Compare each
      repaired region with its authoritative original. Do not continue semantic
      migration while source syntax is unstable.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Use the first complete
      traceback, repair its root cause, compile, and rerun collection. Typical
      first blockers include BaseSettings imports, removed SHAPE_LIST,
      unsupported Field regex, unimported decorators, deprecated post
      root_validator behavior, and `model_validator(pre=True)`. Convert
      `@root_validator(pre=True)` to `@model_validator(mode="before")`; never
      spell it as `@model_validator(pre=True)`. Do not add
      `skip_on_failure=True` as the final migration when native v2
      `model_validator` is required.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Pin or range Pydantic 2
      consistently in project metadata and add pydantic-settings when settings
      are used. Import BaseSettings and SettingsConfigDict from
      `pydantic_settings`, migrate settings Config semantics such as
      case-sensitivity, and change `Field(regex=...)` to `Field(pattern=...)`.
      Preserve environment names, defaults, caching, and validation behavior.
      Verify settings import and representative valid and invalid
      instantiations before proceeding.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Replace class Config
      with ConfigDict/model_config while preserving extra handling, enum value
      behavior, immutability, aliases, assignment validation, arbitrary types,
      and population rules. Use `frozen=True` for immutable/hashable delimiter
      models where v1 used `allow_mutation=False`. Put shared configuration on
      the correct base model so descendants inherit the intended behavior.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      overridden model fields to remain annotated. Find subclass assignments
      such as `segment_name = X12SegmentName.CR5` and convert them to annotated
      overrides such as `segment_name: X12SegmentName =
      X12SegmentName.CR5`. Do not remove segment_name fields or bulk-delete
      subclass declarations; parsers and generated registries depend on their
      defaults.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Replace Field regex with
      pattern and constrained-string regex with pattern while preserving
      anchors. Migrate min_items/max_items and other renamed constraints where
      required. Preserve v1 Optional default behavior deliberately: in v2,
      `Optional[T]` without `= None` remains required, so compare original tests
      and model behavior before adding defaults. Move custom Field metadata
      such as `is_component=True` into
      `json_schema_extra={"is_component": True}` using valid Python booleans.
      Do not perform a repository-wide Optional rewrite.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      allow_reuse because v2 no longer accepts it. Do not shadow the imported
      `field_validator` with
      `functools.partial(field_validator, allow_reuse=True)`. Preserve reusable
      plain validation functions and attach them directly with v2 decorators,
      adapting their signatures only when required. Verify reuse in multiple
      model classes rather than testing only the helper import.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator
      individually to field_validator, preserve mode and field order, and use
      ValidationInfo when the v1 function read `values`, `field`, or config.
      Replace `values.get(...)` with `info.data.get(...)` only after checking
      that the referenced field is validated earlier. Preserve the complete
      body and return the validated value. Add `@classmethod` where appropriate.
      For reusable date validators, support the actual v2 call shape rather
      than assuming the third argument is still a dict.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it is pre/before or post/after, whether it expects raw
      input dictionaries or validated model instances, what it mutates, what it
      returns, and whether it is attached dynamically. Never convert all root
      validators to the same mode. A bare post `@root_validator` is not fixed by
      textual replacement alone.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre validators to
      `@model_validator(mode="before")` with a class/raw-values contract and
      return the values mapping. Convert post validators to
      `@model_validator(mode="after")` with an instance contract, replace
      dictionary access with attribute access, preserve all validation and
      mutation logic, and return `self`. Where assignment validation changes
      the permitted after-validator call shape, account for it explicitly.
      Do not leave v1 root_validator decorators, add deprecated
      skip_on_failure as a shortcut, use `pre=True` with model_validator, or
      retain `(cls, values)` under after mode.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search every Python
      file for validator decorators and dynamic validator calls, then ensure
      each referenced decorator is imported from pydantic in that file and no
      removed v1 name remains. Compile and import both shared segment modules
      and every transaction package that declares validators. This gate catches
      the recurring state where decorators were renamed but imports were not,
      or imports were changed while old decorators remained.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields and inspect FieldInfo annotation, json_schema_extra, default,
      and metadata using v2 APIs. Replace field_info.extra reads with guarded
      json_schema_extra reads. Remove ModelField and SHAPE_LIST dependencies.
      Use typing.get_origin/get_args for container detection and handle Optional
      or Union annotations deliberately. Test introspection against actual model
      classes rather than assuming FieldInfo resembles v1 ModelField.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or implement the
      public `_is_list_field` helper in the module from which tests and users
      import it, normally `x12sdk.models`. It must accept the v2 FieldInfo shape
      used by `model_fields`, identify direct list annotations reliably, and
      support the repeatable-segment before validator. Do not hide it in an
      unrelated support module or delete it because its name starts with an
      underscore. Run the dedicated loop-initializer tests.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict/json,
      parse_obj, copy, and schema APIs with model_dump, model_dump_json,
      model_validate, model_copy, and model_json_schema where production code
      owns the call. Preserve include/exclude, exclude_none, exclude_unset,
      aliases, enum serialization, delimiters, component fields, and CLI JSON
      output. Parsers must use model_fields and annotation/json_schema_extra,
      not v1 shape/type_/field_info.extra attributes. Update recursive segment
      counting and duplicate-code validators to handle both raw dictionaries
      and BaseModel instances without weakening validation.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect module-level loops
      that generate segment registries from class fields. Replace
      `Class.__fields__["segment_name"].default` with the corresponding
      model_fields access while preserving every registry key and value. Guard
      abstract/base classes correctly. Compare registry size and representative
      mappings before and after migration; successful module import alone does
      not prove parser discovery still works.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or equivalent over
      production code with its real exit status. Repair syntax and indentation
      before tests. Inspect every file touched by automation, especially large
      generated segment modules and transaction directories.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, support, parsers, both versioned segment modules, representative
      transaction packages, `_is_list_field`, and registry maps. Then run full
      test collection without output-truncating pipelines and require its real
      exit code to be zero. Continue on the first complete traceback until all
      intended tests collect.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run settings, support,
      shared-segment, loop-initializer, repeatable-segment, parser,
      serialization, CLI, and representative transaction tests. A passing
      import smoke test is insufficient. Record actual pass and failure counts
      and address failures one root cause at a time.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. For migrated validators,
      compare accepted input, rejected input, default handling, normalization,
      mutation, error location, and serialization with tests or captured v1
      behavior. Pay special attention to before/after timing, field ordering,
      missing Optional fields, enum conversion, repeatable segment wrapping,
      ACH/payment conditional requirements, dates, and adjustment grouping.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. For each iteration, capture
      the complete first failure, inspect the implicated original function and
      neighboring model, make the smallest semantic fix, compile, run the
      narrow test, then rerun the broader gate. Do not end the turn with a
      progress summary while tests fail, and do not repeatedly restart
      repository discovery after collection is already working.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review `git diff --check`, the
      complete diff, and searches for corruption signatures. Confirm automated
      edits did not alter unrelated regex usage, turn Python True into `true`,
      duplicate imports, add malformed parentheses, remove annotations, change
      every model validator to one mode, inject default=None indiscriminately,
      or damage ordinary variables named pattern, validator, or dict.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Require no production
      `pydantic.v1` imports; no BaseSettings import from pydantic; no v1
      validator/root_validator decorators; no allow_reuse; no unsupported
      model_validator `pre` argument; no SHAPE_LIST or ModelField dependency;
      no production __fields__/field_info.extra use; no malformed decorators;
      and no empty, stubbed, commented-out, pass-only, or unconditional-return
      validator body introduced by the migration. Investigate each remaining
      v1 method or deprecation rather than suppressing warnings wholesale.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's exact complete test command with no head,
      tail, grep, tee-status ambiguity, timeout truncation, or ignored return
      code. Redirect output only if the command's exit status is saved before
      any inspection command. Require all intended tests to collect and pass.
      If any fail, return to iterative repair rather than reporting completion.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Verify public imports,
      settings, parser discovery, X12 rendering, JSON/CLI serialization,
      repeatable-list normalization, custom metadata, generated registries,
      immutability, constraints, and representative validation errors. Confirm
      the migration did not merely make tests collect by deleting behavior.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Confirm the full suite's
      recorded exit code is zero, static audits are clean, compilation passes,
      diff check passes, no temporary migration scripts or summaries were added
      unintentionally, and only intended files changed. Preserve pre-existing
      user changes and report any unrelated dirty state separately.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report dependencies and code surfaces
      migrated, exact verification commands, collected and passed test counts,
      full-suite exit status, and any residual warnings or risks. Claim success
      only when the complete suite passes. If blocked, report the current
      complete traceback and remaining ledger items rather than saying the task
      is complete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to pydantic.v1 or use that compatibility namespace as the migration.
  - Never empty, stub, comment out, replace with pass, or add an unconditional early return to a function or validator merely to make imports or tests proceed.
  - Never convert decorators with repository-wide sed or regex without classifying each validator's phase, signature, inputs, body, and return contract.
  - Never map every root validator to mode before or every root validator to mode after.
  - Never use `@model_validator(pre=True)`; use `mode="before"` or `mode="after"` with the matching function contract.
  - Never treat `skip_on_failure=True` on deprecated root_validator as completion of a native v2 migration.
  - Never keep an after model validator with a `(cls, values)` dictionary contract; use an instance and return self.
  - Never pipe the decisive pytest command through head, tail, grep, or tee and then trust the pipeline's apparent zero status.
  - Never stop after imports, compilation, collection, one test file, or a small passing subset.
  - Never run an editable install against stale v1 dependency metadata and assume the runtime still contains Pydantic v2.
  - Never indiscriminately add `= None` to every Optional field; first preserve the repository's required-versus-optional contract.
  - Never remove inherited model fields or subclass segment_name declarations to silence Pydantic override errors; preserve them with annotations.
  - Never use lowercase JSON booleans such as `true` in Python source.
  - Never replace arbitrary occurrences of regex, pattern, dict, validator, Config, or Optional outside the exact Pydantic construct being migrated.
  - Never assume successful import proves generated registries, parser discovery, serialization, or validator execution still works.
  - Never delete or relocate a public compatibility helper such as `_is_list_field` without updating and verifying its public import contract.
  - Never overwrite the whole package, reset unrelated changes, or restore all files because one broad migration edit failed.
  - Never write migration plans, repair scripts, or summaries into the repository unless they are required deliverables; remove accidental artifacts before the final gate.
  - Never report completion while the full untruncated suite has a nonzero exit status.
```