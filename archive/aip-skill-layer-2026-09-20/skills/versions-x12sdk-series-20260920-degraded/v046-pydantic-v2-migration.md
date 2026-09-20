---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 46
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, generated registries, and domain behavior. Work from complete
  tracebacks and original function bodies, make small reviewable edits, and
  prove correctness with collection, focused behavior tests, static audits,
  and the complete untruncated suite. Before starting and throughout the
  migration, read and follow `references/core-rules.md`.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, or damaged generated registries

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without truncating the execution. Capture the command, actual
      exit status, installed Python and Pydantic versions, collection count,
      pass/fail/error counts, and the first complete traceback. Do not pipe
      pytest through `head`, `tail`, `grep`, or `tee` unless `pipefail` or
      `PIPESTATUS` preserves pytest's status; displaying a truncated copy of
      saved output is acceptable, truncating the test process is not.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      root and inspect `git status` and `git diff` before editing. Distinguish
      user changes, prior migration changes, generated artifacts, and skill
      files. Never erase pre-existing work. If the tree contains a damaged
      partial migration, preserve its diff as evidence before restoring only
      demonstrably accidental edits.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Identify dependency
      manifests, lockfiles, CI commands, supported Python versions, package
      extras, test configuration, settings dependencies, and the authoritative
      full-suite command. Check repository-specific migration notes and
      post-migration requirement files before inventing dependency ranges.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Install the target dependency
      set through the repository's supported mechanism, then immediately
      re-check imported package paths and versions. Editable installs and
      extras can silently downgrade Pydantic; therefore verify Pydantic and
      pydantic-settings after every install command. Do not diagnose v2 source
      while the active interpreter is running v1.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      package initializers, generated registration code, and transaction
      subpackages. Inventory imports, decorators, Config classes, settings,
      constrained types, Field keyword changes, metadata, serialization,
      parsing, introspection, reusable validator factories, and calls to
      deprecated model methods. Record file and line locations; a zero-match
      grep exit status is evidence, not a command failure.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Treat imports used
      by tests or consumers as contracts even when their names are private,
      including list-field helpers. Record model construction behavior,
      aliases, schema metadata, output serialization, error behavior, settings
      environment semantics, transaction registries, and repeatable-segment
      normalization.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Retrieve every validator's
      original body and surrounding model from the clean revision before
      changing its decorator or signature. Snapshot representative valid and
      invalid inputs, serialized outputs, schemas, settings behavior, and
      registry contents when the v1 runtime is available. Never infer a
      validator's intended phase from its name alone.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Give each occurrence a ledger
      row containing file, symbol, v1 construct, intended v2 construct,
      original signature and body, dependencies on sibling fields, required
      imports, public contract, focused test, migration status, and verification
      status. Do not mark a row complete merely because its module imports.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work as environment and
      collection blockers, shared infrastructure, model definitions,
      validators, introspection and helpers, serialization and parsing,
      registries, then domain behavior. Separate mechanical candidates from
      semantic edits. Decorator and signature migrations are semantic edits
      even when their spelling looks repetitive.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Define checkpoints small
      enough to compile, import, inspect, and test independently. After each
      checkpoint inspect the diff and update the ledger. Do not migrate both
      large versioned model trees with an unreviewed global replacement.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      files, inspect every syntax error in context, and compare malformed
      regions with the clean revision. Repair duplicate decorators, damaged
      imports, missing indentation, invalid decorator calls, lowercase JSON
      booleans in Python, corrupted regex literals, accidental comments, and
      generated helper scripts. Prefer restoring a damaged function and
      remigrating it over layering more substitutions on corrupted source.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the first
      complete collection traceback, then rerun collection to reveal the next
      blocker. Typical early blockers include BaseSettings imports, removed
      Field keywords, SHAPE_LIST imports, invalid model configuration,
      missing validator imports, and unannotated field overrides. Continue
      until collection progresses; do not claim success from isolated imports.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move BaseSettings to
      pydantic-settings, add the dependency consistently to every authoritative
      manifest, migrate settings configuration, and change Field `regex` to
      `pattern` without altering the regex itself. Verify environment variable
      case behavior and cached settings access. Re-check the active versions
      after installation.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate each Config
      option deliberately to ConfigDict or model_config, preserving enum,
      extra-field, immutability, alias, assignment-validation, and arbitrary
      type behavior. Do not copy unsupported v1 keys or leave both Config and
      model_config on the same model.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      annotations when subclasses override inherited model fields. Add the
      correct annotation and preserve each default, especially discriminator
      or segment-name fields. Do not remove these fields to silence an import
      error; generated registries and serialization may depend on them.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Migrate removed Field and
      constrained-type keywords, list length constraints, patterns, defaults,
      optionality, aliases, and custom metadata. Remember that `Optional[T]`
      without a default remains required in v2. Move arbitrary Field metadata
      such as component markers into `json_schema_extra` using valid Python
      values, then verify both validation and schema output.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      allow_reuse wrappers rather than recreating them around v2 decorators.
      Distinguish raw reusable validation functions from already-decorated
      descriptors. Preserve the public helper name only when consumers import
      it, and ensure each call site applies `field_validator` exactly once.
      Reusing the same raw function across models is valid; stacking
      decorators or shadowing the imported decorator is not.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator from its
      original body. Replace v1 `values`, `field`, and `config` arguments with
      ValidationInfo only where needed, use `info.data` with awareness of field
      order, choose before or after mode deliberately, and preserve
      always-like behavior only when required. Add classmethod in the supported
      order when appropriate. Test missing, null, invalid, and valid inputs.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      record whether it requires raw input, validated fields, or wrap behavior.
      Record its expected input type, return type, failure-order dependency,
      mutation behavior, and whether it calls shared helpers. Never perform a
      blanket root-validator replacement.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. A before validator normally
      receives `cls, values`, treats values as raw input, and returns the
      mapping. An after validator normally receives `self`, reads attributes,
      and returns `self`. A wrap validator must call its handler correctly.
      Rewrite dictionary access only after selecting the phase. Preserve every
      branch, exception, helper call, and return. Never empty, comment out, or
      replace a function body with a no-op merely to make the module import.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every Python
      file, reconcile decorator usage with imports and remove obsolete names.
      Detect missing field_validator or model_validator imports, stale
      validator or root_validator imports, duplicate imports, malformed
      decorator arguments, and decorators accidentally changed without their
      function signatures. Compile and import each affected module family.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ and
      ModelField assumptions with model_fields and v2 FieldInfo APIs. Translate
      type, annotation, default, requiredness, alias, and metadata access
      intentionally; direct textual substitution is insufficient. Read custom
      metadata from `json_schema_extra` defensively when it may be None.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or implement the
      repository's public list-field helper used by repeatable-segment
      initialization. Base it on the field annotation with get_origin and
      correct handling of list, optional list, and annotated forms. Use the
      helper consistently in both production normalization and tests. Verify
      that single repeatable segments are wrapped once and existing lists are
      unchanged.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Migrate dict, json,
      parse_obj, copy, and schema APIs only where behavior remains equivalent.
      Verify enum output, aliases, exclude flags, unset and None handling,
      custom encoders, delimiter injection, nested models, and CLI JSON
      formatting. Do not perform a repository-wide `.dict(` replacement
      without confirming the receiver is a Pydantic model.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time loops
      that discover model classes or read field defaults. Adapt them to
      model_fields without changing registry keys or omitting classes. Compare
      registry sizes and representative entries with the semantic snapshots.
      Do not delete inherited discriminator fields or bypass registry
      generation to make imports pass.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile all production Python
      files after each structural checkpoint. Treat syntax, indentation,
      duplicate decorator, and malformed import failures as blockers. A
      successful compile does not prove Pydantic model construction, so proceed
      immediately to imports and collection.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, both versioned segment modules, transaction packages, and
      public helpers, then run complete test collection. Preserve the true exit
      status. Repeat one complete traceback at a time until collection succeeds
      and the expected test count is credible.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, shared support functions, 4010 and 5010 segments, repeatable
      segment initialization, parsing, serialization, registries, and each
      migrated validator family. Use exact collected node IDs. A pytest command
      that collected no requested test is not a passing test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare representative valid
      and invalid cases against snapshots or existing assertions, including
      defaults, coercion, requiredness, error locations, cross-field
      requirements, reusable date validators, nested loops, and serialized X12
      output. An import success or schema build is not semantic verification.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Use the cycle: run the
      smallest meaningful failing test, read the complete traceback, inspect
      the current and original source, make one coherent fix, compile/import,
      rerun the focused test, then rerun the broader affected group. Keep
      working until the full suite passes; do not stop to summarize progress
      while known failures, collection errors, or untested bulk edits remain.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Inspect every bulk-edit hunk and
      search for malformed imports, duplicate decorators, altered regex
      literals, invalid Python booleans, commented validation assignments,
      changed unrelated functions, removed annotations, and temporary scripts
      or plan files. Revert collateral changes and rerun affected gates.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      all inventoried v1 interfaces, malformed v2 decorator forms, stale
      imports, empty or no-op validator bodies, compatibility shims, deprecated
      methods, and temporary artifacts. Explicitly reject imports from
      `pydantic.v1`; this task requires native Pydantic v2, not a compatibility
      namespace.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's authoritative complete suite without
      output truncation or timeout shortcuts that terminate it early. Record
      the exact command, true exit status, collected count, passed count,
      skipped or xfailed count, warnings, and duration. Zero tests, only a
      focused subset, or a masked nonzero exit status does not satisfy this
      gate.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm that passing tests
      cover settings, validation, parsing, serialization, helpers, registries,
      CLI behavior, and both supported model versions. Review any changed
      warning or error behavior. Add or run targeted regression tests for
      migration fixes not exercised by the full suite.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Review `git diff --check`,
      the complete diff, and status. Confirm dependency files agree, no user
      changes were lost, no pydantic.v1 imports exist, no validation body was
      emptied or bypassed, no temporary migration files remain, and every
      ledger row has evidence. Rerun static audit and the full suite after any
      final code edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only after all gates
      pass. State the files and behavior migrated, exact full-suite command and
      result, focused regression coverage, static-audit result, runtime
      versions, and any remaining warnings or risks. If the suite is not green,
      report the migration as incomplete rather than describing it as
      successful.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not redirect production imports to `pydantic.v1`; native Pydantic v2 is the target.
  - Do not empty, comment out, replace with pass, or otherwise neutralize a function or validator body merely to make imports or tests proceed.
  - Do not use global sed or regex replacement for validator phases, signatures, function bodies, imports, annotations, regex literals, or metadata without a per-hunk semantic audit.
  - Do not convert every root validator to the same model-validator mode; classify raw-input, validated-instance, and wrap behavior separately.
  - Do not change a decorator without updating and testing its signature and return contract.
  - Do not recreate allow_reuse by shadowing or partially wrapping Pydantic v2's field_validator.
  - Do not remove inherited discriminator or segment-name fields to silence annotation errors; annotate overrides and preserve defaults.
  - Do not delete or rename public helpers, including underscore-prefixed helpers imported by tests, without preserving their contract.
  - Do not treat a successful import, compile, collect-only run, or focused subset as proof that the suite passes.
  - Do not pipe pytest into output-truncating commands in a way that masks its nonzero exit status.
  - Do not report a pytest command as passing when it collected zero requested tests.
  - Do not stop after producing a migration summary while failures, collection errors, unreviewed bulk edits, or untested files remain.
  - Do not trust an editable install or extras install to preserve the target Pydantic version; verify the active interpreter after every install.
  - Do not mutate tests to hide migration defects unless the test itself asserts a documented v1-only behavior whose intended v2 contract has been established.
  - Do not leave temporary migration plans, one-off repair scripts, generated caches, or malformed partial edits in the final diff.
```