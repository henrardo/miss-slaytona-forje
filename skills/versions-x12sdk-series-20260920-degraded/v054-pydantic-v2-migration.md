---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 54
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's complete, untruncated test command exits successfully.
  Preserve public APIs, validation timing, defaults, error behavior, parsing,
  serialization, helpers, and generated registries. Before starting and
  throughout the migration, read and enforce `references/core-rules.md`.
  Never substitute `pydantic.v1`, never empty a function merely to make imports
  succeed, and never report completion from imports, collection, or a focused
  subset alone.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, duplicated decorator arguments, or accidental edits outside Pydantic syntax

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
      command without piping it through `head`, `tail`, `grep`, or `tee` in a
      way that hides the test process exit status. Capture the complete first
      traceback, command, exit code, collection count, pass count, failure
      count, and installed Pydantic version. If output is large, redirect it to
      a file, preserve `$?` immediately, and inspect the file separately.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Resolve the repository
      path once and reuse it exactly; do not guess variants such as `agent-worm`
      or `agent-wrap`. Record every pre-existing tracked and untracked change.
      Do not overwrite, revert, or mix unrelated user work with migration
      edits. If the tree already contains a partial migration, treat its diff
      and HEAD versions as evidence rather than assuming either is correct.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject/setup
      metadata, lock and requirements files, CI commands, package layout,
      supported Python versions, settings dependencies, tests, changelog, and
      migration-specific fixtures such as `requirements-v2.txt`. Do not assume
      setup.py or requirements.txt exists. Identify the single authoritative
      full-suite command and the dependency files that must agree.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter used by
      tests imports native Pydantic 2 and, when settings are used,
      pydantic-settings. Do not trust dependency metadata alone, and do not
      switch between `python`, `python3`, and unrelated pip environments
      without proving they resolve to the same runtime. Re-run the version
      check after installation commands.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests, and
      generated modules for imports, decorators, validator factories,
      signatures, Config classes, field constraints, metadata, introspection,
      parsing, serialization, schema APIs, settings, and registries. Include
      decorator forms with and without parentheses and multiline imports.
      Record counts and file locations so the final static audit can prove that
      every occurrence was intentionally migrated.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Treat imports used by
      tests as public contracts, including helpers such as `_is_list_field`.
      Record model construction forms, accepted and rejected payloads,
      environment-variable behavior, error expectations, `.x12()` output,
      serialization output, parser behavior, list-wrapping behavior, registry
      contents, and CLI behavior. A helper missing from production code but
      imported by tests is migration work, not permission to delete the test.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. For every validator or
      helper being changed, recover and read its complete original body from
      HEAD or another trustworthy source before editing. Snapshot whether it
      receives raw dictionaries or model instances, which fields it reads,
      whether order matters, what it returns, what it raises, and whether it
      runs before or after field validation. Never infer a validator's mode
      from its old decorator name alone, and never replace a non-empty body
      with `pass`, `return values`, `return self`, or another no-op merely to
      make the module import.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per affected
      symbol or repeated family, with file, class, symbol, v1 construct,
      original signature and body source, intended v2 construct, expected
      timing, imports required, focused test, and status. Include malformed
      partial edits and public helpers. Update this ledger after every repair
      so repeated files are not rediscovered or migrated inconsistently.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical changes from
      semantic changes. Mechanical candidates include exact dependency,
      settings-import, method-rename, and metadata-key migrations after local
      verification. Validator modes, signatures, requiredness, inherited
      fields, union/list detection, defaults, and generated registries are
      semantic and require symbol-by-symbol reasoning. Plan changes in
      dependency order, beginning with syntax and collection blockers.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Work in small coherent
      batches and run compile/import/collection checks after each batch. Before
      any scripted replacement, inspect all matches, constrain it to exact
      syntax and files, preserve a diff, and inspect every changed hunk
      immediately. Prefer AST-aware or explicit edits over broad `sed` and
      regex rewrites. Never run a repository-wide replacement that inserts
      decorator arguments, changes every Optional field, rewrites arbitrary
      `regex` text, or edits imports without first proving all matches share
      identical semantics.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      code first and repair malformed decorators, imports, parentheses,
      indentation, Python booleans, regular expressions, and accidental source
      mutations before semantic migration continues. Explicitly search for
      artifacts such as `@model_validator(mode="before")pre=True)`,
      duplicated `(mode=...)`, extra closing parentheses, decorator names that
      are not imported, `true`/`false` in Python, and damaged non-Pydantic
      `re.compile` calls. Restore a damaged file or hunk from HEAD when that is
      safer than layering more regex repairs, while preserving verified user
      changes.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the first
      complete collection traceback, then rerun collection to expose the next
      blocker. Use direct imports only as a quick local check; collection is
      the gate. Do not summarize progress or end the task while collection or
      imports still fail.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Align all authoritative
      dependency metadata on native `pydantic>=2,<3` and add a compatible
      `pydantic-settings` dependency when BaseSettings is used. Import
      BaseSettings and SettingsConfigDict from `pydantic_settings`; migrate
      settings Config semantics and `Field(regex=...)` to the correct v2 form.
      Verify case sensitivity, defaults, environment names, coercion, caching,
      and settings construction with focused tests. Do not import production
      APIs from `pydantic.v1`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert each shared
      Config class to ConfigDict or an equivalent native-v2 configuration
      while preserving frozen/immutability, enum values, extra-field policy,
      aliases, validation of defaults, assignment behavior, arbitrary types,
      and serialization. Test the shared bases before touching every derived
      model because a base-class mistake multiplies across the repository.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      annotated overrides for inherited model fields. Locate subclass
      assignments such as `segment_name = X12SegmentName.CR5` and change them
      to annotated field overrides without deleting the discriminator or
      loosening its behavior. Do not remove all subclass `segment_name`
      definitions as a workaround. Import representative 4010 and 5010 segment
      families and verify registry keys after these changes.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Migrate `regex` to `pattern`,
      constrained-type keyword changes, min/max item constraints, and custom
      Field metadata intentionally. Preserve exact regular-expression
      semantics and requiredness. Do not assume `Optional[T]` means a default
      of None in v2, and do not mass-add `default=None`; compare constructors
      and tests first. Place custom metadata such as `is_component` in
      `json_schema_extra` using valid Python values, and preserve every
      length, numeric, literal, decimal, date, and list constraint.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      v1-style `allow_reuse` wrappers and partials rather than shadowing
      Pydantic's `field_validator` name with an incompatible helper. For each
      reusable function, determine whether v2 passes a value, ValidationInfo,
      raw dictionary, or model instance, and adapt the function once at its
      source. Test direct decorator assignment and reuse in multiple models.
      Keep ordinary domain validation helpers separate from decorator
      factories.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each v1 validator to
      `field_validator` with explicit mode where needed. Replace the v1
      `values` mapping with `ValidationInfo.data` only when the original timing
      guarantees the referenced fields are available; account for declaration
      order. Preserve multi-field validators, always/pre behavior, date
      parsing, returned values, and raised messages. Do not mechanically rename
      the decorator while leaving a v1 signature.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. Before changing a
      root-validator family, classify every occurrence as before/raw-dict,
      after/model-instance, wrapper, or reusable external validation. Record
      its expected argument and return type. Bare `@root_validator` is not
      automatically `mode="after"` unless its body is rewritten for an
      instance, and assigning all validators `mode="before"` is equally wrong.
      Inspect the entire body and its callers before selecting a mode.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre validators to
      `model_validator(mode="before")` operating on raw input and returning
      raw input. Convert post validators to
      `model_validator(mode="after")` operating on `self` and returning
      `self`, rewriting every dictionary lookup and mutation deliberately.
      Adapt reusable dictionary-oriented checks through explicit before-mode
      wrappers or native instance logic. Preserve skipped-on-field-failure
      behavior through v2 timing rather than copying unsupported arguments.
      Never leave a v1 `(cls, values)` body behind an after validator.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. For every Python
      module, compare used decorators and validator factories with imported
      names. Search separately for v1 decorators, v2 decorators, malformed
      decorator text, and stale imports. Compile and import representative
      modules from every transaction family. A decorator migration is
      incomplete if the source text changed but the required v2 name is not
      imported or a stale v1 name remains.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__`,
      ModelField, shape, type_, field_info.extra, and SHAPE_LIST usage with
      native v2 `model_fields`, FieldInfo annotations, `get_origin`/`get_args`,
      and `json_schema_extra` logic. Handle absent or None metadata safely.
      Preserve field order and distinguish list, optional-list, union, nested
      model, component, discriminator, and scalar fields. Do not import removed
      internals such as SHAPE_LIST merely because the name still appears in
      old code.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve the public location
      and semantics of helpers such as `x12sdk.models._is_list_field`.
      Implement list detection against v2 FieldInfo annotations, including
      Optional and Union wrappers, and use the same helper in repeatable
      segment wrapping where appropriate. Do not move it to another module if
      tests or users import it from models. Verify single-dictionary-to-list
      normalization and already-list input across representative loop models.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace model `dict`,
      `json`, parse_obj, copy, and schema APIs with native v2 equivalents only
      where the receiver is proven to be a Pydantic model; do not rewrite
      ordinary dictionaries, JSON-library calls, or regex variables. Preserve
      enum, alias, exclude, unset, None, decimal, date, delimiter, CLI, parser,
      and `.x12()` output behavior. Update field metadata access in parsing and
      recursive counting without assuming every item is a model.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit import-time code that
      scans model classes or reads discriminator defaults. Replace class
      `__fields__` access with `model_fields` while preserving exact registry
      keys and values. Guard abstract/base classes and classes without the
      discriminator field. Compare 4010 and 5010 registry sizes and
      representative entries with semantic snapshots; a successful import
      does not prove the registry is correct.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall over production
      code and fail on any syntax error. Inspect the exact source lines around
      each error and repair from known-good syntax or the original hunk. Do not
      continue semantic debugging while malformed Python remains.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import shared models,
      settings, common validators, representative 4010 and 5010 segments, and
      representative transaction modules, then run full collection without
      truncating output or masking status. Continue until collection exits
      zero and the expected tests are collected. Record deprecation warnings
      separately; do not confuse collection success with suite success.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, shared models, support utilities, 4010 segments, 5010
      segments, repeatable loop initialization, parsing, serialization,
      registries, and CLI behavior. A focused command must be allowed to finish
      and its real exit code must be checked. Passing 56 or 57 tests is
      progress, not completion, when the repository contains more tests.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. For each migrated validator
      family, exercise at least one accepted and one rejected payload and
      compare coercion, defaults, timing, error location, message meaning, and
      serialized result with tests or snapshots. Specifically test dependent
      field validators, pre-model checks, post-model invariants, optional
      fields, repeatable segments, dates, and discriminators.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work from the first complete
      current traceback, identify the smallest owning layer, inspect the
      original body and current diff, make one coherent repair, and rerun the
      narrowest reproducer followed by collection or the affected group.
      Maintain pass and collection counts after each cycle. Do not restart the
      migration from generic exploration, repeatedly research settled v2
      facts, or end the turn because some imports now work.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review the complete diff, not only
      expected files. Search for malformed decorators, duplicate imports,
      invalid booleans, broken regexes, unexpected Optional defaults, missing
      annotations, altered non-Pydantic code, indentation damage, generated
      scratch files, migration plans, and summaries accidentally added to the
      repository. Confirm every changed function retains substantive behavior.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      BaseSettings imported from pydantic, pydantic.v1, v1 validators,
      root_validator, allow_reuse, Config classes that should be migrated,
      SHAPE_LIST, ModelField, __fields__, field_info.extra, Field(regex=),
      constrained regex keywords, stale model dict/json/parse APIs, malformed
      decorators, and decorator/import mismatches. Investigate each remaining
      hit; comments and documentation may remain only intentionally.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the exact authoritative complete-suite command with no
      output truncation and preserve its exit code. If it fails, return to
      iterative repair rather than reporting a partial result. Do not treat a
      shell pipeline exit code of zero as proof that pytest passed. Record
      collected, passed, failed, skipped, xfailed, warning counts, duration,
      command, and exit status.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm public imports,
      settings behavior, accepted and rejected payloads, repeatable segment
      wrapping, parser output, serialization, `.x12()` output, registry
      contents, CLI behavior, immutability, enum handling, and error behavior.
      Resolve unexpected warning increases where they indicate stale v1 APIs.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Require compile success,
      collection success, focused behavior success, static-audit success, and
      full-suite exit zero. Inspect git status and the complete final diff.
      Reject production imports from `pydantic.v1`, empty/no-op replacements
      for formerly substantive functions, disabled tests, altered test
      expectations used to hide regressions, unrelated files, and temporary
      migration artifacts.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only after the final
      gate passes. Include the exact full-suite command and result, major
      behavior-preserving changes, static-audit result, and any intentional
      remaining warnings. If any gate is not green, report the current blocker
      and continue working rather than claiming success or producing a
      migration summary as a substitute for code completion.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; the goal is a native Pydantic v2 migration.
  - Never empty, bypass, or replace a substantive function body with a no-op merely so imports or tests proceed.
  - Never convert every root validator to the same model-validator mode without reading and classifying each complete body.
  - Never mechanically rename a validator decorator while retaining an incompatible v1 signature.
  - Never use broad repository-wide sed or regex replacements without enumerating matches, constraining the edit, and auditing every resulting hunk.
  - Never mass-add `default=None` to Optional fields or remove inherited discriminator fields to silence schema errors.
  - Never modify tests, skip tests, loosen assertions, or suppress validation solely to make the suite green.
  - Never trust a command piped through head, tail, grep, or tee unless the original test process exit status is explicitly preserved.
  - Never stop after import success, collection success, compile success, or a focused passing subset; require the complete suite to pass.
  - Never create migration summaries, plans, or repair scripts inside the repository unless the repository contract requires them.
  - Never repeatedly restart discovery after progress; maintain the migration ledger, current traceback, pass count, and next blocker.
  - Never guess repository paths or silently discard pre-existing working-tree changes.
  - Never treat syntactically valid source as semantically migrated without accepted and rejected behavior checks.
```