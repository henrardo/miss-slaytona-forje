---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 50
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the complete repository suite passes. Preserve public APIs, validation
  timing, error behavior, parsing, serialization, metadata, registries, helper
  exports, and generated-model behavior. Work from complete tracebacks and
  original function bodies rather than mechanical decorator replacement.
  Before starting and throughout the migration, read and enforce
  `references/core-rules.md`. Never claim completion from successful imports,
  collection, compilation, or a focused subset alone.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, or duplicated decorator arguments

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
      `establish-the-failure` and follow it. Run the repository's real test
      command from the repository root and retain the complete output and real
      exit status. Do not pipe pytest through `head`, `tail`, `grep`, or `tee`
      unless `set -o pipefail` is active and the pytest status is captured
      separately; those pipelines repeatedly disguised failing suites as exit
      zero. Record Python, Pydantic, pydantic-settings, pytest, collection,
      pass, fail, error, and warning counts. Preserve the first complete
      traceback rather than summarizing only its last line.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Resolve the repository
      root once, use it consistently, and verify every absolute path before an
      edit; do not alternate similar paths such as agent-warm, agent-worm,
      agent-wam, agent-wrap, or agent-wrap-up. Capture `git status --short` and
      `git diff`. Treat existing tracked modifications as evidence that may
      contain user work or a partial migration. Do not discard, overwrite, or
      reset them without authorization. Ignore only known harness artifacts
      such as an untracked `.vibe/` directory.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject metadata,
      lock and requirement files, CI workflows, supported Python versions,
      package entry points, test configuration, requirements-v2 guidance,
      changelog notes, and repository documentation. Use the repository's
      actual command and dependency contract rather than assuming setup.py or
      requirements.txt exists. Record whether the suite intentionally treats
      warnings as errors and whether tests encode post-migration helper APIs.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Ensure the interpreter running
      tests actually imports Pydantic 2 and pydantic-settings from the intended
      environment. Re-check versions after editable installs because a broad
      install can silently downgrade Pydantic. Update project dependency
      metadata as well as the live environment; a green run under Pydantic 1
      does not validate a Pydantic 2 migration.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      generated modules, and registries for all v1 surfaces, including
      BaseSettings, Config, validator, root_validator, allow_reuse, values and
      field callback parameters, __fields__, ModelField, field_info.extra,
      SHAPE_LIST, Field regex/min_items/max_items, constr regex, parse_obj,
      dict, json, schema, copy, construct, from_orm, and class-level registry
      introspection. Search multiline imports and bare decorators separately;
      a grep that only matches one-line imports is insufficient. Record each
      occurrence by file, symbol, migration family, and test coverage.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Inventory public
      imports and tested helpers, including X12Config, X12Delimiters,
      X12Segment, X12SegmentGroup, parser and reader classes, CLI output,
      x12 serialization, segment registries, and `_is_list_field`. A helper
      imported from `x12sdk.models` must remain available from that module even
      if its implementation is shared elsewhere. Record tests for single-item
      wrapping, repeatable segments, model construction, aliases, settings,
      serialization, and transaction parsing.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing a validator,
      copy its complete original body, decorator, signature, field order
      assumptions, return value, and covered tests into the migration ledger.
      Recover originals from git when a partial migration has damaged them.
      Never preserve an import by deleting or emptying a validator body: a
      `pass`, unconditional `return`, commented-out implementation, or removed
      assignment is not a migration. Capture positive and negative examples so
      later tests verify behavior rather than importability alone.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Build a durable checklist with one
      row per affected symbol: original API, intended v2 API, semantic risk,
      owning tests, edit status, import status, focused-test status, and
      full-suite status. Include malformed partial edits and missing public
      helpers as first-class work rather than only counting textual v1 names.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Group work into dependency and
      settings changes, shared model configuration, inherited fields, field
      constraints, reusable validators, field validators, before/after model
      validators, metadata and introspection, parsing and serialization,
      public helpers, generated registries, and malformed-source recovery.
      Order work by collection blockers first, then shared infrastructure, then
      model families, then behavioral regressions.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Use small, reviewable edit
      batches. After each batch compile the changed files, import their modules,
      and run the nearest focused tests. Save the diff before broad edits.
      Prefer exact edits or AST-aware transformations over repository-wide sed.
      If automation is justified, dry-run it, inspect representative before and
      after bodies, and keep an explicit changed-file list.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Repair syntax,
      indentation, duplicated arguments, malformed decorators, damaged import
      blocks, invalid lowercase `true`, corrupted regex literals, and partial
      script output before semantic migration. Compare suspicious files with
      git originals. Compile every repaired file immediately. Do not layer new
      replacements over malformed source.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix exactly the earliest
      complete traceback first, then rerun collection to expose the next one.
      Typical initial blockers include BaseSettings imports, removed Field
      arguments, missing SHAPE_LIST, undefined decorator names, invalid
      inherited field overrides, and missing public helpers. Do not fan out
      into dozens of speculative edits before collection advances.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Pin native
      `pydantic>=2,<3` and add `pydantic-settings` using constraints consistent
      with repository guidance. Import BaseSettings and SettingsConfigDict from
      pydantic_settings. Translate settings Config semantics, including
      case-sensitivity and environment behavior, into `model_config`. Replace
      `Field(regex=...)` with `Field(pattern=...)` without altering the regex.
      Test default settings and environment overrides.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Replace v1 Config
      classes with ConfigDict while preserving frozen/immutability,
      use_enum_values, extra handling, aliases, assignment validation, default
      validation, arbitrary types, and serialization behavior. Distinguish the
      immutable delimiter model from mutable segment models. Test assignment,
      hashing, extra-field rejection, enum values, and defaults rather than
      relying on warning-free imports.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic 2 requires an
      annotation when a subclass overrides an inherited model field. Locate
      bare assignments such as `segment_name = X12SegmentName.CR5` and convert
      them to annotated overrides, preserving the field and default; do not
      delete all subclass segment_name declarations. Verify representative
      imports from every version family and ensure registry keys still resolve
      to the intended segment classes.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Translate regex to pattern,
      constr regex to pattern, min_items/max_items to min_length/max_length,
      and arbitrary Field metadata to `json_schema_extra` with valid Python
      values such as `True`. Preserve requiredness carefully: in Pydantic 2,
      `Optional[T]` without `= None` is still required. Do not globally add
      defaults without checking the original contract. Exercise boundary,
      required, optional, default, decimal, date, enum, and list-cardinality
      cases.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `allow_reuse`; do not create a partial that passes it to Pydantic 2's
      field_validator. Preserve the callable signatures expected by every use.
      Where shared functions need sibling data, adapt them deliberately to
      ValidationInfo or wrap them per field. Verify reusable date validators,
      hierarchical validators, duplicate-code validators, and dynamically
      assigned validators in loop and transaction modules.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert validator to
      field_validator one function at a time. Map `pre=True` to mode before.
      Replace `values` with ValidationInfo and use `info.data`, remembering it
      contains only already-validated fields in declaration order. Preserve
      always/default behavior with validate_default or a model validator when
      appropriate. Add or retain @classmethod only in a form accepted by the
      decorator. Test missing, present, invalid, and cross-field cases for each
      migrated validator.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root validator,
      decide from its complete body whether it consumes raw input or validated
      model state. Record `before` only for raw mapping transformations and
      `after` for checks over constructed fields. Identify dynamically assigned
      root validators separately. Never infer mode from a mechanical search or
      assign mode before to every validator.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. A before model validator
      receives raw input and returns raw input; preserve `cls, values` mapping
      logic. An after model validator normally receives `self`, reads
      attributes, raises on invalid combinations, and returns `self`. Rewrite
      each body accordingly rather than merely renaming the decorator.
      Preserve validators for adjustments, dates, amounts, names, duplicate
      qualifiers, loop totals, and segment counts. Never empty a function body
      to make the module import.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every Python
      file, compare decorator names with imports and helper assignments.
      Search separately for field_validator, model_validator, validator,
      root_validator, and dynamically assigned validators. Ensure edits did not
      shadow the imported field_validator with a helper of the same name,
      remove needed imports, duplicate import-list entries, or leave undefined
      decorators. Compile and import all affected modules.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields and translate ModelField assumptions to FieldInfo,
      annotation, get_origin/get_args, and json_schema_extra. Preserve component
      metadata used by parser and X12 serialization. Guard optional
      `json_schema_extra` before calling `.get`. Update class registries that
      read segment_name defaults and test the actual generated maps.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Implement or preserve
      `_is_list_field` using FieldInfo annotations plus get_origin/get_args,
      including Optional/Union and Annotated forms as required by repository
      fields. Export it from `x12sdk.models` because tests and downstream code
      import it there. Use the same helper in the before validator that wraps a
      single repeatable segment into a list. Test list, optional-list,
      non-list, and single-dict inputs across discovered loop classes.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict, json,
      parse_obj, schema, copy, and construct only where production behavior
      remains equivalent, using model_dump, model_dump_json, model_validate,
      model_json_schema, model_copy, and model_construct as appropriate.
      Preserve exclude flags, enum and Decimal handling, delimiter behavior,
      aliases, CLI JSON encoding, nested models, and X12 field order. Adapt
      code that accepts either dictionaries or model instances instead of
      blindly calling model_dump.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time registry
      generation at the ends of large segment modules. Replace class
      `__fields__` access with `model_fields` while preserving exact keys and
      class values. Compare registry sizes, representative segment mappings,
      and parser lookups against the original. Do not delete segment_name
      fields or registry code merely to avoid Pydantic errors.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile over
      the complete production package after every automated edit and before
      collection. Treat syntax, indentation, duplicated decorator arguments,
      and malformed import blocks as stop-the-line failures.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core models,
      settings, both top-level segment families, every transaction package, and
      public helpers; then run full pytest collection with an unmasked exit
      status. Collection success is a gate to behavioral testing, not evidence
      of completion. Record collected count and investigate any reduction from
      baseline.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run tests for settings,
      support functions, 4010 segments, 5010 segments, repeatable segments,
      loop initializers, parsing, serialization, CLI, and representative
      transaction families. Use exact node IDs only after confirming they
      exist. Do not stop because a subset reports roughly 56 or 57 passes; past
      attempts reached that point while the suite still failed.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare success values,
      coercion, requiredness, ordering, defaults, validation errors, and X12
      output against semantic snapshots. Specifically test validators that
      depend on sibling fields, model validators that aggregate repeated
      segments, component metadata, list wrapping, and settings environment
      handling.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Fix one coherent failure
      cluster at a time: read the full traceback, inspect the complete current
      and original function, make the smallest semantic edit, compile, import,
      run the focused test, then rerun the broader affected group. Keep the
      migration ledger current. Continue until the full suite, not merely
      collection or imports, is green.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every automated replacement
      in the diff. Look for malformed decorators such as duplicated mode
      arguments, accidental comments, altered unrelated regex code, lowercase
      JSON booleans in Python, missing indentation, erased imports, empty
      bodies, all-before validator conversions, and unintended files outside
      the repository. Revert or repair each unsafe transformation.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      residual v1 imports and APIs, deprecated configuration, undefined
      decorators, malformed metadata, SHAPE_LIST, __fields__, field_info.extra,
      allow_reuse, regex arguments, and deprecated serialization calls.
      Explicitly fail the audit if production imports `pydantic.v1`, because
      compatibility redirection is not a native migration. Explicitly inspect
      validator bodies for pass-only, comment-only, or unconditional-return
      stubs.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's complete suite without output truncation,
      timeout-induced cancellation, or pipeline status masking. Capture the
      exact command, exit status, collected count, pass count, skip count,
      warning count, duration, and complete failure output. If it fails, return
      to iterative repair; do not write a completion summary.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm all public and test
      contracts from the inventory: settings, model configuration, inherited
      fields, validators, parser behavior, serializers, registries, helper
      exports, CLI output, and representative transactions. Ensure the final
      implementation is native Pydantic 2 and contains no disabled logic.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect `git diff --check`,
      complete diff, changed-file list, and working-tree status. Remove
      temporary migration scripts, plans, summaries, and artifacts unless they
      are requested deliverables. Verify only intended repository files
      changed. Rerun the static audit and full suite after the final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only when compilation,
      imports, full collection, focused semantic checks, static audit, full
      suite, behavior verification, and final diff gate all pass. Include the
      exact full-suite command and counts, changed files, major semantic
      migrations, and any remaining non-failing warnings. If any gate is red,
      report the migration as incomplete and continue working when tools and
      time remain; never substitute a progress summary for implementation.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not redirect production imports to `pydantic.v1`; the target is native Pydantic v2.
  - Do not empty, comment out, replace with `pass`, or reduce a validator or helper to an unconditional return merely to make imports succeed.
  - Do not mechanically rename every root_validator to model_validator without classifying raw-input versus model-instance semantics.
  - Do not convert every model validator to mode before; after validators must usually accept and return self.
  - Do not pass allow_reuse to Pydantic v2 validators or hide it inside a functools.partial alias.
  - Do not shadow Pydantic's field_validator or model_validator with a helper of the same name.
  - Do not globally delete segment_name overrides; annotate inherited field overrides and preserve registry semantics.
  - Do not globally add `= None` to Optional fields without checking original requiredness.
  - Do not use lowercase `true` or `false` in Python metadata.
  - Do not replace regex text with pattern using an unrestricted transformation that can corrupt unrelated `re.compile` code or quoting.
  - Do not run broad sed or regex edits across the repository without a dry run, checkpoint, compilation, and full diff audit.
  - Do not trust a shell pipeline's zero exit status when pytest output was piped through head, tail, grep, or tee without pipefail.
  - Do not treat successful imports, compileall, collection, a single test, or a 56–57-test subset as completion.
  - Do not stop after creating a migration plan, ledger, summary, or report; those are controls for implementation, not substitutes for it.
  - Do not overwrite pre-existing tracked changes or use git restore/reset without authorization.
  - Do not guess repository paths or repeatedly use near-miss absolute paths.
  - Do not remove public helpers such as `_is_list_field`; preserve their documented import locations and behavior.
  - Do not assume `Optional[T]` means an optional input in Pydantic 2; requiredness depends on the default.
  - Do not replace every `.dict()` blindly; preserve callers that accept both mappings and model instances and preserve serialization options.
  - Do not alter generated registries without comparing representative keys, values, and sizes against the original behavior.
  - Do not leave decorator names in a file unless the corresponding native Pydantic v2 symbol is imported or deliberately defined.
  - Do not claim that warnings are harmless until the repository warning policy and complete suite have been checked.
  - Do not create migration artifacts outside the repository and present them as task completion.
```