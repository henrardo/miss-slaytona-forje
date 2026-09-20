---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or repairing import, syntax, schema, validation, parsing, collection, or test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 78
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Preserve public APIs, validator bodies, validation timing, field requiredness,
  parser behavior, serializer behavior, settings behavior, helper functions,
  generated registries, and error behavior. Before editing and throughout the
  migration, read and enforce `references/core-rules.md`. Work from complete
  tracebacks, original source, and small verified edits rather than speculative
  bulk replacement. Treat every import, compilation, collection, focused-test,
  or partial-suite success as a checkpoint rather than completion. Preserve
  progress across checkpoints; do not restart repository assessment after each
  error or discard unrelated successful edits. Never claim completion from a
  custom smoke script, a textual summary, a subset of tests, a pass count below
  the full collection count, or a zero status belonging to `head`, `tail`,
  `tee`, `grep`, or another pipeline consumer instead of the test process.
  Never redirect production imports to `pydantic.v1`. Never empty, stub,
  bypass, weaken, or replace a function body merely to make imports,
  collection, or tests proceed.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, empty validator bodies, broad search-and-replace damage, or misleading partial test success
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
      command once without truncating its diagnostic output. If output must be
      captured, redirect it to a file, save the test process status in the same
      shell, and inspect the file afterward; do not pipe the test command to
      `head`, `tail`, `grep`, or `tee` and then mistake the consumer's zero
      status for pytest success. Record the complete first traceback, test
      command, exit status, collection count, pass count, fail count, error
      count, and installed Pydantic versions. A collection failure with zero
      executed tests is the baseline, not evidence that tests pass.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      root once and use it consistently; avoid near-miss paths such as
      `agent-worm`, `agent-wam`, or `agent-wrap`. Capture `git status`,
      distinguish pre-existing user changes from migration edits, and never
      erase user work. Do not use a broad `git checkout`, `git restore`, or
      reset against the package after useful migration edits have accumulated.
      If a generated edit damages one file, inspect its diff and restore only
      that file after preserving intentional changes.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      Read `references/core-rules.md` section `execution-discipline` and follow
      it. Keep a live progress ledger containing the current first failure,
      completed edits, last passing gate, remaining inventory, and exact next
      command. Resume from that ledger after each failure instead of repeatedly
      announcing the migration, re-reading the same top-level files, writing
      premature summaries, or ending the turn without executing the next
      repair. Make one coherent edit batch, run its narrowest useful gate,
      record the result, and continue.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect `pyproject.toml`,
      lock and requirement files, CI workflows, package layout, tests, public
      imports, supported Python versions, and any post-migration requirement
      file supplied by the repository. Use the project's actual installation
      and test commands. Do not assume `setup.py` or `requirements.txt` exists;
      enumerate packaging files before reading them. Treat migration-specific
      tests, including tests for repeatable segments and loop initializers, as
      part of the contract rather than optional guidance.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter used by
      the test command imports native Pydantic 2, pydantic-core, and
      pydantic-settings at versions compatible with repository metadata. Update
      dependency declarations before relying on editable installation. After
      installation, re-query versions because installing project extras can
      silently downgrade Pydantic. Do not use `pydantic.v1`, downgrade the
      runtime to make legacy code pass, or accept metadata that still pins
      `pydantic<2`.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      package metadata, and code-generation or registry paths for BaseSettings,
      inner Config classes, validator and root_validator, allow_reuse,
      __fields__, ModelField, field_info.extra, SHAPE_LIST, Field(regex=...),
      constrained-type regex arguments, arbitrary Field metadata, parse_obj,
      dict, json, schema, copy, construct, inherited unannotated field
      overrides, and decorator aliases. Search decorator applications
      separately from imports so missing-import and stale-decorator gaps are
      visible. Store file and line references rather than only counts.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Inventory exported
      model classes, settings classes, `.x12()` behavior, parser and CLI output,
      helper functions, reusable validators, registry maps, and public
      introspection helpers. Include helpers imported only by migration tests,
      such as a list-field classifier; absence from production call sites does
      not make a tested public import disposable. Record expected valid and
      invalid examples, error timing, and field requiredness.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing a validator,
      serializer, parser, helper, or registry, capture its complete original
      body and neighboring field order from clean source or the current diff.
      Classify whether it consumes raw input dictionaries, validated sibling
      values, or model instances. Record whether it mutates and returns values,
      returns a replacement, or raises a specific error. Never infer semantics
      from only a decorator name, and never delete a body because adapting it
      is difficult.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one row per affected symbol
      with file, original API, target API, original signature, validation phase,
      requiredness, metadata use, dependent tests, edit status, and last gate.
      Keep duplicate 4010 and 5010 implementations as separate rows even when
      their code is similar. Update rows after each verified edit so later
      attempts continue from proven progress rather than rediscovering work.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by collection
      blockers, shared infrastructure, validator semantics, introspection,
      parsing and serialization, generated registries, then behavior failures.
      Separate mechanical renames from semantic rewrites. Treat large segment
      modules as collections of individually classified validators, not as
      candidates for blind file-wide decorator substitution.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Define gates for each edit
      batch: compile the edited file, import the edited module, collect the
      affected tests, run the smallest behavior test, then update the ledger.
      Inspect `git diff --check` and the edited diff at each checkpoint. Do not
      queue dozens of speculative changes before the first import check.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Search for damaged
      syntax and transformations such as doubled decorator arguments,
      `@model_validator(mode="before")pre=True)`, missing parentheses,
      duplicated imports, lost imports, lowercase JSON booleans in Python,
      malformed regex replacements, indentation damage, empty functions, and
      scripts or summaries accidentally added to the repository. Compare each
      damaged function with clean source and restore its full body before
      adapting it. Compile every repaired file before proceeding.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the earliest
      complete import or collection traceback and its directly related shared
      cause. Re-run collection without truncating the traceback, record the new
      first blocker, and repeat. An import-only smoke test confirms one gate but
      cannot replace collection or behavior tests.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move BaseSettings to
      `pydantic_settings`, use SettingsConfigDict or equivalent native v2
      configuration, preserve case sensitivity and environment behavior, and
      migrate removed Field keywords such as `regex` to `pattern`. Keep
      pydantic-settings in dependency metadata. Import and instantiate the
      settings class with representative environment overrides before moving
      on.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert every inner
      Config class to native v2 model_config while preserving enum handling,
      extra-field policy, frozen or immutability semantics, aliases, assignment
      validation, arbitrary types, and default validation. Do not retain
      removed keys such as `allow_mutation`; map their behavior deliberately.
      Account for configuration inheritance and conflicts across shared base
      models before importing all subclasses.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. For each subclass that
      overrides a base model field, preserve it as an annotated field with a
      compatible type, for example `segment_name: X12SegmentName = ...`.
      Search for all unannotated overrides instead of repairing only the first
      class reported by Pydantic. Do not remove all `segment_name` declarations,
      convert them to ClassVar, or weaken the base field merely to silence the
      schema error; generated registries and serialization may depend on the
      field default.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed constraint
      keywords such as Field `regex` and constrained-string `regex` to their v2
      equivalents. Move arbitrary Field metadata into `json_schema_extra` and
      preserve consumers of flags such as `is_component`. Audit Optional
      annotations separately from defaults: in Pydantic v2,
      `Optional[T]` without a default remains required. Add `default=None` only
      where v1 behavior or tests prove omission was allowed; never apply a
      repository-wide Optional rewrite. Preserve min/max constraints, aliases,
      decimals, literals, and error behavior.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      `allow_reuse` because v2 handles reuse differently, but preserve each
      reusable validation function as a callable with its original logic.
      Replace legacy partial aliases with a native v2 helper only when all call
      sites remain valid. Do not shadow `field_validator` with an incompatible
      wrapper or import it from `pydantic.validators`; import native decorators
      from `pydantic`. Verify both decorator-style validators and validators
      registered by assigning decorated shared functions.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each v1 field validator
      individually. Map `pre=True` to `mode="before"` when applicable, add
      `@classmethod` where appropriate, replace the v1 `values` parameter with
      ValidationInfo, and read validated prior fields from `info.data`.
      Preserve field declaration order assumptions: `info.data` does not
      contain later fields. Adapt shared date validators and similar functions
      explicitly rather than passing ValidationInfo to a function expecting a
      dictionary. Run positive, missing-field, and invalid-value tests for each
      validator family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record pre or post phase, input shape, mutation, return value, dependent
      fields, and whether it is registered inline or through assignment.
      Before-mode validators normally receive raw dictionaries; after-mode
      validators normally receive model instances. Never classify all bare
      root validators with one regular expression or assume every validator
      should use `mode="before"` merely because dictionary bodies are easier to
      preserve.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `@model_validator(mode="before")`, retain raw dictionary signatures and
      dictionary returns, and add `@classmethod` where needed. Convert post root
      validators to `@model_validator(mode="after")`, rewrite dictionary access
      as model attribute access, and return `self`. Preserve all loops,
      arithmetic checks, cross-field requirements, error messages, and
      validator bodies. For reusable root validators, use a suitable before
      wrapper only when the shared function genuinely consumes a dictionary.
      Never leave an after validator with `(cls, values)` and `values.get(...)`,
      and never empty the body to make the module import.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search the entire
      production tree for both old decorator applications and old imports, then
      separately search for every `field_validator` and `model_validator`
      application whose module lacks the corresponding native import. Compile
      and import every affected module, including transaction-specific loops,
      segment modules, and transaction_set modules. Remove stale v1 imports
      only after all uses are migrated.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      `model_fields`, ModelField assumptions with FieldInfo and annotations,
      `field_info.extra` with guarded `json_schema_extra`, and SHAPE_LIST checks
      with typing-origin analysis. Handle Optional, Union, Annotated, list, and
      subclass annotations intentionally. Access `json_schema_extra` safely
      when it is None. Verify introspection on class objects and instances and
      remove deprecated instance-level model_fields access.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or restore the
      public `_is_list_field` helper in the module from which tests and users
      import it. Make it accept the actual v2 field object used by callers,
      inspect its annotation robustly, and return true for repeatable list
      fields, including optional or annotated list types where present.
      Reuse the same helper in before-validation wrapping logic. Do not move it
      to another module without preserving its original import path.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace model `dict`,
      `json`, parse, copy, schema, and construct APIs with native v2 equivalents
      only at model call sites; do not rewrite ordinary dictionaries or JSON
      library calls. Preserve exclude flags, enum output, aliases, delimiters,
      None handling, list wrapping, CLI output, recursive segment counting,
      and X12 rendering order. Update parser field metadata access and model
      discovery with native v2 introspection rather than relying on deprecated
      schema internals. Test round trips and exact serialized output.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time loops
      that discover model classes and derive keys from fields such as
      `segment_name`. Replace `__fields__` access with guarded model_fields
      access while preserving enum-to-string cleanup and registry contents.
      Verify both major-version registries contain expected keys and model
      classes; a successful module import alone does not prove registry
      completeness.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile the complete production
      package, not only recently edited modules. Treat every SyntaxError,
      IndentationError, malformed decorator, duplicate keyword, and missing
      import as a blocking failure. Inspect complete tracebacks and repair the
      source rather than commenting out the offending declaration.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, both major-version segment modules, transaction-specific loop
      modules, parsers, and tested public helpers. Then run full test collection
      to completion and record its true status and item count. Continue until
      collection exits zero. Do not stop when only a few targeted imports work
      or when collection reports errors after listing some tests.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run tests for shared models,
      settings, 4010 and 5010 segments, repeatable segments, loop initializers,
      support functions, parsing, serialization, CLI output, and each validator
      family touched. Run exact test node IDs only after confirming they exist;
      a pytest usage error or “not found” result is not a behavior test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare representative valid
      inputs, invalid inputs, missing optional and required fields, nested
      models, repeated segments, inherited defaults, cross-field constraints,
      and emitted errors against semantic snapshots and tests. Diagnose large
      waves of missing-field errors as possible requiredness drift before
      patching fixtures or adding defaults. Do not make every Optional field
      optional-by-default unless the original contract proves that behavior.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work from the first complete
      failing traceback, inspect the original function and its tests, make the
      smallest semantic fix, and rerun the narrow gate followed by the broader
      gate. Update the ledger after each result. Preserve prior passing changes
      and continue until no failures remain; do not end the task because time
      was spent, a summary was written, imports succeed, or 56 or 57 tests pass
      while the suite still contains failures or collection errors.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. If any script, regex, sed command,
      or broad replacement was used, inspect every changed hunk. Search for
      malformed decorators, duplicate imports, altered non-Pydantic code,
      lowercase booleans, corrupted regular expressions, comments replacing
      executable validators, changed indentation, empty bodies, and accidental
      files. Automated replacements may identify candidates but never prove
      semantic correctness.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      `pydantic.v1`, BaseSettings imported from pydantic, validator,
      root_validator, allow_reuse, inner Config, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, removed constraint keywords, malformed
      decorators, deprecated serialization calls, stubs, pass-only bodies, and
      disabled validation. Classify every remaining match rather than assuming
      grep exit one is an execution failure.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's exact complete test command without
      output truncation. Capture stdout and stderr to a file if needed, retain
      the test process exit code, and inspect the final summary. Require exit
      zero, zero collection errors, zero failed tests, and a pass count matching
      the collected suite after expected skips. A command piped to `head`,
      `tail`, `tee`, or `grep` cannot satisfy this gate unless pipe status is
      explicitly and correctly preserved.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Re-run representative public
      imports, valid and invalid model construction, settings overrides, parser
      round trips, exact X12 rendering, CLI serialization, list-field helper
      behavior, and registry lookups. Confirm no validator or public helper was
      emptied, bypassed, weakened, moved without compatibility, or replaced by
      a smoke-only implementation. Confirm production imports are native v2
      and never redirected to `pydantic.v1`.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the entire diff,
      `git diff --check`, and final status. Remove accidental migration plans,
      summaries, repair scripts, caches, and unrelated files unless explicitly
      requested. Re-run compile, static audit, and the complete suite after the
      final cleanup. Do not restore the package wholesale or discard verified
      migration work at this stage.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report the exact full-suite command,
      true exit status, collection and pass counts, skipped tests, static audit
      result, changed files, and any known residual warnings. State completion
      only when the final gate proves it. If the suite is not green, report the
      current first failure and continue repairing rather than presenting a
      migration summary as if the task were complete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`, even temporarily as the submitted solution.
  - Never empty, stub, comment out, bypass, or replace a validator, parser, serializer, helper, or registry body merely to make imports or tests proceed.
  - Never bulk-replace every root validator with the same model-validator mode; classify each validator from its original body and phase.
  - Never rewrite all Optional annotations to add defaults; preserve requiredness field by field.
  - Never remove inherited field declarations merely to silence Pydantic; preserve annotated overrides and registry behavior.
  - Never use broad sed or regex edits without compiling, importing, testing, and inspecting every changed hunk.
  - Never use a package-wide git checkout or restore to recover one damaged edit after verified migration progress exists.
  - Never mistake a pipeline consumer's exit zero, an import smoke test, collection-only success, or a partial test count for a passing full suite.
  - Never stop to write a completion summary while collection errors, failures, stale v1 APIs, malformed code, or unverified behavior remain.
  - Never repeatedly restart assessment instead of using the migration ledger and current first failure.
  - Never create repository-local migration summaries, plans, or one-off repair scripts unless the user requests them or they are required project artifacts.

# Completeness check against the previous skill:
# Mapped: purpose, all trigger_when and do_not_use_when entries, all 36 original
# procedure steps in their original order, every original reference-file load,
# every original input/output edge, and the original anti-pattern instruction.
# Mapped and strengthened from execution evidence: true pytest exit handling,
# progress preservation, malformed partial migrations, validator phase
# classification, inherited fields, Optional requiredness, list helpers,
# registries, static audits, full-suite gating, pydantic.v1 prohibition, and
# prohibition on emptying function bodies.
# Schema gap: none.
# Body drop: none.
# Deliberate drop: none.
```