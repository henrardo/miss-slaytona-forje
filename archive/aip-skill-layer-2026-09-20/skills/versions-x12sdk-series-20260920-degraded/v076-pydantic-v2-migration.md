---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or repairing import, syntax, schema, validation, parsing, collection, or test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 76
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
  bulk replacement. Treat every import, compilation, collection, or focused-test
  success as a checkpoint rather than completion. Never claim completion from a
  custom smoke script, a textual summary, or a zero status belonging to `head`,
  `tail`, `tee`, `grep`, or another pipeline consumer instead of the test
  process. Never redirect production imports to `pydantic.v1`. Never empty,
  stub, bypass, weaken, or replace a function body merely to make imports,
  collection, or tests proceed.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, empty validator bodies, or broad search-and-replace damage
  - The first collection failure says that BaseSettings moved to pydantic-settings
  - Tests exercise repeatable list fields, inherited discriminator fields, generated segment registries, X12 serialization, or other behavior coupled to Pydantic field introspection
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
      command without truncating its execution. If output must be captured, use
      a separate command whose saved status is the test process status, such as
      `python -m pytest > /tmp/baseline.log 2>&1; status=$?`; inspect the log
      afterward. Record the exact command, exit status, complete first
      traceback, collection count, pass count, and failure count. A pipeline
      ending in `head`, `tail`, `tee`, or `grep` does not establish the test
      status unless `pipefail` and the correct pipeline status are explicitly
      verified.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      path once and reuse it exactly; do not alternate among mistyped paths.
      Record tracked modifications, staged changes, and untracked files. Never
      discard pre-existing user work. If the tree already contains a partial
      migration, distinguish user changes from changes made during this run.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      Read `references/core-rules.md` section `execution-discipline` and follow
      it. Keep one active failure, one semantic hypothesis, and one small edit
      batch at a time. After each batch, run the narrowest meaningful import,
      compilation, collection, or focused test gate. Do not spend the run
      repeatedly rediscovering the same files, rewriting migration summaries,
      or announcing completion before the full-suite gate.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Identify the canonical test
      command from project metadata or CI, supported Python versions,
      dependency files, package layout, generated code, and migration-specific
      tests. Treat files such as `requirements-v2.txt`, changelogs, issue
      fixtures, and newly added tests as executable migration requirements, not
      optional commentary.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter used by
      the test command imports Pydantic 2 and any required companion packages,
      especially `pydantic-settings`. Update declared dependencies consistently
      with the repository contract. Do not infer the active version from a
      requirements file alone, and do not switch back to Pydantic 1 to make
      tests pass.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      plugins, generated registries, and transaction modules for v1 imports,
      decorators, configuration, settings, constraints, metadata,
      introspection, parsing, serialization, and copied validator helpers.
      Record file, symbol, usage category, and likely semantic risk rather than
      only counts.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include every symbol
      imported directly by tests or downstream modules, even underscore-prefixed
      helpers such as `_is_list_field`. Record model constructors, settings
      names, parser entry points, serializers, `x12()` methods, generated
      lookup maps, validation errors, field requiredness, and accepted input
      shapes.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. For every validator, copy or
      inspect the complete original decorator, signature, body, return value,
      field order dependency, and tests before editing. If a partial migration
      has damaged a body or decorator, recover the original from version
      control rather than guessing. Preserve bodies; migration changes API
      adaptation, not business rules.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Give every v1 occurrence and every
      public contract a ledger row containing original semantics, intended v2
      construct, affected tests, status, and verification evidence. Keep
      decorator conversion separate from body conversion so a renamed
      decorator cannot be mistaken for a completed validator migration.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by collection
      blockers, shared base models, field semantics, reusable validator
      infrastructure, local validators, introspection, parsing and
      serialization, generated registries, then behavior regressions. Do not
      begin repository-wide decorator replacement before each validator family
      is classified.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Prefer one subsystem or one
      validator family per batch. Record the verification command and result
      after every batch. If a batch creates syntax damage or increases
      collection failures, revert only that batch and retry more narrowly.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Search for malformed
      constructs such as duplicated decorator arguments, dangling
      `pre=True)`, extra parentheses, duplicated imports, lost indentation,
      lowercase JSON booleans in Python, damaged regex literals, undefined
      decorator names, and decorators whose imports were removed. Compile
      affected files before proceeding. Recover original bodies from version
      control; never replace them with `pass`, unconditional returns, or empty
      stubs.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the earliest
      complete collection traceback and rerun collection without truncating the
      test process. Continue until collection advances, then update the ledger.
      Do not summarize the migration or stop merely because one import works.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move `BaseSettings` to
      `pydantic_settings`, migrate settings configuration to
      `SettingsConfigDict`, preserve environment names, prefixes, aliases,
      case-sensitivity, source precedence, defaults, and cache behavior.
      Replace `Field(regex=...)` with `Field(pattern=...)` without altering the
      regex. Verify both import and settings instantiation.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Replace inner
      `Config` classes with `ConfigDict` while preserving `extra`,
      `use_enum_values`, immutability, assignment validation, aliases, and
      arbitrary-type behavior. Convert `allow_mutation=False` to `frozen=True`;
      do not retain removed configuration keys. Test shared base models before
      migrating their subclasses.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires a
      type annotation when a subclass overrides an inherited field. Add the
      correct annotation to constants and discriminators such as
      `segment_name: X12SegmentName = X12SegmentName.CR5`. Search all model
      subclasses for unannotated overrides. Do not remove discriminator fields
      globally or solve one error by weakening the base model annotation.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Audit every `Optional`
      annotation because Pydantic v2 treats `Optional[T]` without a default as
      required. Add `= None` only where v1 behavior or tests show omission was
      accepted; do not run a blind regex over all annotations. Rename
      `regex` to `pattern`, preserve constraint boundaries, use valid v2
      constrained types or `Annotated`, and move arbitrary `Field` metadata
      such as `is_component` to `json_schema_extra`. Use Python `True`, not
      JSON `true`.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      `allow_reuse`; v2 handles reuse differently. Preserve reusable validator
      functions as callable business logic and apply v2 decorators at model
      attachment points. Avoid shadowing the imported `field_validator` with a
      partial of itself. When shared functions expect v1 `values`, adapt them
      explicitly to `ValidationInfo.data` or provide a narrow wrapper rather
      than changing every caller speculatively.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each `@validator`
      independently to `@field_validator`; use `mode="before"` only when the
      original used `pre=True`. Replace the v1 `values` parameter with
      `ValidationInfo` and read already validated fields through `info.data`.
      Preserve field order assumptions, `always` behavior, return values, and
      error messages. Ensure each decorated method has a valid v2 signature and
      that every decorator name is imported from `pydantic`.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every
      `root_validator`, record whether it was pre or post, whether it consumes
      raw dictionaries or validated values, what it mutates, whether it relies
      on failed-field omission, and what it returns. Do not classify validators
      by decorator text alone; inspect the complete body and tests.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert v1
      `root_validator(pre=True)` to `model_validator(mode="before")` with a
      dictionary-oriented `cls, values` body and dictionary return. Convert
      post root validators to `model_validator(mode="after")` with an
      instance-oriented `self` body and return `self`, translating dictionary
      reads and writes to attribute access without changing business rules.
      Use wrap mode only when needed to preserve validation timing. Never
      convert every post validator to before mode merely because its original
      body expects a dictionary, and never perform decorator-only replacement
      while leaving an incompatible body signature.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search every Python
      file for v1 decorator names, decorator aliases, assignment-style
      validators, missing v2 imports, unused removed imports, `allow_reuse`,
      malformed decorators, and mismatched signatures. Compile and import each
      affected module. A decorator rename is incomplete until its import,
      mode, signature, body, and return contract all agree.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      `model_fields`, `ModelField` assumptions with v2 `FieldInfo` and typing
      introspection, and `field_info.extra` with
      `json_schema_extra or {}`. Preserve declaration order, exclusions,
      annotations, defaults, metadata, and nested-model detection. Remove
      `SHAPE_LIST` only after replacing its behavior with `get_origin` and
      suitable unwrapping logic.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Define or retain the public
      `_is_list_field` helper in the module from which tests and callers import
      it. Make it accept v2 field annotations and correctly identify
      `list[T]` and `typing.List[T]`, including relevant `Annotated` or union
      wrappers used by the repository. Use the same helper in the before-model
      validator that wraps a single dictionary into a repeatable list. Verify
      both the helper import and direct model construction from a bare dict.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace v1 APIs with
      `model_validate`, `model_dump`, `model_dump_json`, and `model_copy` where
      behavior is equivalent. Preserve exclusions, aliases, enum rendering,
      decimal and date formatting, delimiters, nested model handling, and
      custom X12 output. Do not mechanically replace an object's `dict()`
      unless it is known to be a Pydantic model; shared validators may receive
      dictionaries or model instances during assignment and construction.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Update class-level field
      lookups to `model_fields`, preserve discriminator default extraction and
      enum normalization, and verify generated maps contain the expected keys
      and classes. Do not remove registry construction because imports then
      succeed; parsers depend on the populated registry.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile the entire production
      package, not only edited files. Repair syntax, indentation, import, and
      undefined-name errors before running behavioral tests.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core settings,
      models, both versioned segment modules, parser entry points, transaction
      modules, and public helpers. Then run full test collection without
      truncating the process and require its actual zero status. Fix the first
      complete traceback and repeat until collection is clean.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Prioritize settings,
      shared models, segment validation, repeatable segment initialization,
      parser behavior, serializer output, registries, and representative
      transactions. Capture the actual exit status of each focused command.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare accepted and
      rejected inputs, required versus optional fields, defaults, coercion,
      validator ordering, error locations, error messages, and serialized
      output against snapshots, tests, or the original v1 implementation.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Maintain one active failure
      at a time: read the complete traceback, inspect original code and tests,
      form a semantic hypothesis, make the smallest repair, run the nearest
      gate, and update the ledger. Continue until the full suite, not merely a
      56- or 57-test subset, is green.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every scripted or
      search-and-replace edit in the diff. Reject accidental import damage,
      malformed decorator syntax, duplicated modes, changed regex quoting,
      lowercase booleans, lost annotations, broad Optional-default changes,
      altered function bodies, and unrelated generated summary files.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      `pydantic.v1`, `BaseSettings` imported from `pydantic`, deprecated
      validators, `allow_reuse`, `__fields__`, `SHAPE_LIST`,
      `field_info.extra`, removed Config keys, malformed decorators, and empty
      or stubbed bodies. Every hit must be migrated or explicitly justified as
      documentation or compatibility data.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact repository test command directly or capture its
      output while separately preserving its own exit status. Do not pipe it
      through output-truncating commands. Require zero exit status and record
      collected, passed, failed, skipped, and warning counts. If it fails,
      return to iterative repair rather than reporting partial success.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm public helpers,
      parsers, serializers, settings, model construction, repeatable fields,
      discriminators, registries, validators, and error behavior remain
      intact. Verify no production import points to `pydantic.v1` and no
      function body was emptied or bypassed.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the complete diff and
      status, remove only artifacts created by this run, preserve user files,
      and rerun affected gates after cleanup. Require evidence that dependencies
      and source changes are both present and that no migration plan or summary
      is being substituted for working code.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report the dependency changes,
      behavior-sensitive migrations, exact verification commands, and actual
      final counts. State incomplete status plainly if the complete suite did
      not exit zero. Never say all tests pass based on imports, compilation,
      collection, a smoke script, a focused subset, or output text from a
      command whose real status was not captured.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; this is not a native Pydantic v2 migration.
  - Never empty, stub, bypass, or replace a validator, parser, serializer, helper, or registry body merely to make imports or tests proceed.
  - Never run repository-wide decorator replacement before classifying every affected validator by timing, inputs, mutations, and return contract.
  - Never convert every post root validator to `mode="before"` just to keep a dictionary-shaped body.
  - Never use a broad regex to add defaults to every Optional field; requiredness is behavioral and must be audited.
  - Never remove inherited discriminator fields to silence an override error; annotate the subclass override.
  - Never remove generated registry logic because module import then succeeds.
  - Never shadow `field_validator` with a partial or compatibility shim that passes removed `allow_reuse` arguments.
  - Never treat successful import, compilation, collection, a smoke script, or a focused subset as proof the migration is complete.
  - Never infer test success from a pipeline ending in `head`, `tail`, `tee`, or `grep` without preserving and checking the test process status.
  - Never stop to write a migration summary while collection or tests still fail.
  - Never discard pre-existing user changes or reset the working tree without explicit authorization.
  - Never keep malformed partial-migration output such as duplicated modes, dangling `pre=True)`, extra parentheses, damaged imports, or changed indentation.
  - Never claim behavior preservation without checking Optional defaults, validator ordering, repeatable-list wrapping, metadata, serialization, and registries.
```