---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 40
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, generated registries, and domain behavior. Work from complete
  tracebacks, original function bodies, repository tests, and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task
  by importing from pydantic.v1 or another v1 compatibility namespace. Never
  make code import by deleting, emptying, bypassing, commenting out, or
  replacing a function body with a no-op. Preserve every validator's
  substantive checks, mutations, errors, ordering assumptions, and return
  behavior. Treat Python source as Python: use True and False, never JSON
  literals true and false. Do not confuse import success, successful
  collection, a zero-looking pipeline status, one green focused test,
  warnings-only output, or a written migration summary with completion.
  Completion requires production code to compile, nonempty test collection
  to succeed, focused behavior tests to pass, the exact untruncated full-suite
  command to exit zero, and the final diff to pass static and
  behavior-preservation audits. Capture real command exit codes without
  piping pytest through head, tail, tee, or grep unless pipefail is enabled
  and the pytest status is explicitly preserved. Convert validators according
  to their individual signatures and semantics: a v1 pre root validator
  receives raw data, while a v2 after model validator normally receives and
  returns the model instance. Never perform a blind repository-wide decorator,
  signature, import, metadata, or model-method substitution. After each
  edited file, compile it, import its affected module, and run the smallest
  relevant test before editing another validator-heavy file. Repair the first
  complete traceback before broadening scope. Continue repairing until the
  full suite passes; never stop with a progress summary, migration plan,
  partial import success, collection errors, known failing tests, an
  unexecuted proposed tool call, a user-visible fake tool call, or a statement
  that the remaining work is too complex.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

steps:
  - name: establish-the-failure
    description: >
      Read and follow `establish-the-failure` in
      `references/repository-assessment.md`. Run the repository's exact test
      command without truncating or masking its exit status. Record the command,
      exit code, collection count if available, and first complete traceback.
      If collection stops at `BaseSettings`, treat that import as the current
      blocker instead of continuing speculative inventory work.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository root once, capture `git status --short`, distinguish
      pre-existing changes from migration changes, and retain the exact root
      path to avoid repeated `warm`, `worm`, `wam`, or other path typos. Never
      discard user changes. Do not restart repository assessment after every
      failure; update the existing execution state.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect the files that actually
      exist before guessing names such as requirements.txt or setup.py. Capture
      dependency declarations, Python support, the authoritative test command,
      requirements-v2 or migration notes, package layout, and existing
      migration-specific tests. Do not create a prose migration-plan file in
      the repository unless the user requested one.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Confirm the active interpreter and
      installed versions of Pydantic, pydantic-settings, pytest, and relevant
      plugins. Use the target dependency set before interpreting failures. Do
      not assume the version declared in metadata is the version running.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Inventory production code,
      configuration, public APIs, and tests for BaseSettings, class Config,
      validator and root_validator, allow_reuse, ValidationInfo-incompatible
      signatures, __fields__, ModelField, shape constants, field_info.extra,
      arbitrary Field metadata, regex, min_items and max_items, constrained
      types, parse_obj, from_orm, copy, dict, json, schema, and generated
      registries. Count and list matches, but do not mechanically replace them.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Identify imported public helpers,
      including migration-added tests that expect symbols absent from the v1
      source, such as a list-field helper. Preserve model construction,
      requiredness, error behavior, X12 output, serialized dictionaries,
      settings environment behavior, registry contents, CLI output, and
      repeatable-segment normalization.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read and follow `preserve-original-semantics` in
      `references/repository-assessment.md`. Before rewriting each validator or
      shared model routine, save or inspect its original v1 body and tests.
      Record its input form, accessed sibling fields, mutation behavior,
      ordering dependency, raised errors, and exact return type. Git history is
      a source of truth when an in-progress edit has damaged the body.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Maintain an in-memory or temporary
      ledger of file, symbol, v1 construct, intended v2 construct, semantic
      risk, focused test, and status. Keep it outside production source unless
      the user asks for documentation. Reuse this ledger throughout the
      attempt rather than repeatedly starting a new plan.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Separate safe mechanical edits
      from semantic rewrites. Imports and method renames may be mechanical only
      after call-site review; validators, Optional requiredness, inherited
      fields, list detection, metadata, and registries are semantic work.
      Reject a batch edit if it cannot preserve syntax and behavior by
      construction.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Use one blocker or coherent file
      at a time. For every checkpoint, require compile, affected import, and
      smallest relevant test before proceeding. Prefer exact edits over sed or
      regex on validator-heavy files. Inspect `git diff --check` and the local
      diff immediately after any automated edit.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Fix only the first complete
      collection traceback, then rerun collection with its real exit code. For
      the common Pydantic 2 blocker, replace `from pydantic import
      BaseSettings` with `from pydantic_settings import BaseSettings`, migrate
      its configuration and Field pattern arguments, import the module, and
      rerun collection before touching thousands of validators.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Update every authoritative
      dependency surface to native Pydantic 2 and pydantic-settings without
      widening unrelated dependencies. Move BaseSettings imports to
      pydantic_settings; convert settings Config to SettingsConfigDict or an
      equivalent native v2 model_config; preserve case sensitivity, prefixes,
      environment files, aliases, defaults, and cached settings behavior.
      Replace Field(regex=...) with Field(pattern=...) and verify settings with
      direct construction and repository tests.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Convert each inner Config class
      to ConfigDict or the appropriate v2 configuration while preserving
      frozen or mutability behavior, enum value handling, extra-field policy,
      assignment validation, aliases, arbitrary types, population rules, and
      JSON encoders. Do not retain a class Config merely because it only emits
      a warning.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires inherited
      fields to be re-annotated when overriding defaults. Find unannotated
      assignments such as `segment_name = ...` and annotate them with the
      inherited field's type; never delete all subclass overrides, because
      registries and emitted segment names depend on their distinct defaults.
      Import representative base and subclass models after each repair.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Convert regex to pattern,
      min_items and max_items to min_length and max_length where appropriate,
      and constrained-type keyword changes such as constr(regex=...) to
      constr(pattern=...). Move custom Field extras such as `is_component`
      into `json_schema_extra` using valid Python booleans. Preserve Optional
      requiredness explicitly: `Optional[T]` without a default remains required
      in v2 unless `= None` is intentionally added and behavior tests support
      that change.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Inventory reusable validator
      functions and partial aliases before changing decorators. Remove
      allow_reuse, which is not a v2 field_validator argument. Preserve the
      project's exported validator helper names when they are public or widely
      imported, but avoid shadowing Pydantic's decorator accidentally. Adapt
      shared functions to the signatures actually supplied by v2 and test one
      direct reuse before converting every call site.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md` for each v1 field validator.
      Convert `values`, `field`, and `config` use deliberately to
      ValidationInfo and `info.data`; select mode="before" only when raw input
      semantics require it; account for field declaration order; and preserve
      always-like behavior explicitly. Ensure a reused date validator receives
      the correct sibling data rather than treating ValidationInfo as a dict.
      Compile and run the owning model's focused tests after each group.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read and follow `classify-every-model-validator` in
      `references/migration-implementation.md` before converting any root
      validator. Classify each as raw-input normalization, pre-validation
      cross-field checking, validated-model checking, or reusable external
      validation. Record whether the body expects a dict or model instance and
      whether it mutates values. Never infer mode solely from the old
      decorator text or perform a blanket root_validator substitution.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md` for each classified root
      validator. Use mode="before" with a classmethod-style raw-data contract
      for pre validators. For mode="after", normally accept `self`, read
      attributes with `self.field`, preserve mutations deliberately, and
      return `self`; do not leave a `(cls, values)` dict body under an after
      validator. Preserve every loop, condition, ValueError, and return.
      Never comment out a decorator or validator assignment merely to make an
      import succeed.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search all production Python
      files, including nested transaction packages, for remaining v1
      decorators, imports, allow_reuse arguments, malformed model_validator
      calls, and missing imports. An import renamed without its decorator, or a
      decorator renamed without a valid signature, is a failing checkpoint.
      Compile every touched file and import both major version segment modules.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace __fields__ with
      model_fields and translate v1 ModelField assumptions rather than merely
      renaming the attribute. Use field.annotation, defaults, metadata, and
      json_schema_extra with None-safe access. Repair parser field order,
      component metadata, serializer traversal, dynamic registry lookup, and
      any references to field.name, field.type_, shape, field_info, or extra.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Replace SHAPE_LIST and similar
      removed constants with a tested helper based on typing.get_origin and
      careful unwrapping of Annotated and Union or Optional forms. Preserve or
      add the expected public `_is_list_field` symbol when tests import it.
      Use the helper consistently in repeatable-segment normalization and test
      direct List, Optional[List], non-list, and constrained-list fields.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Convert dict, json, parse_obj,
      copy, schema, and related APIs at reviewed call sites to native v2
      methods. Preserve exclude, include, by_alias, exclude_none,
      exclude_unset, enum, date, Decimal, and JSON behavior. Do not blindly
      replace `.dict(` or `.json(` across the repository because non-Pydantic
      objects may expose those methods and model_dump_json differs from json
      in arguments and output handling.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read and follow `verify-generated-registries` in
      `references/migration-implementation.md`. Rebuild or inspect registries
      generated from model classes after field-introspection and inherited
      default changes. Verify expected segment keys, distinct subclass
      segment names, parser lookup, version-specific registrations, and absence
      of BaseModel or helper classes accidentally treated as domain models.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Run compileall over production
      code with a captured exit status. Treat indentation damage, malformed
      decorators, duplicate keyword arguments, invalid Python literals, and
      incomplete scripted edits as immediate failures. Do not proceed on
      compile errors.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import settings, shared models,
      support utilities, parsers, both versioned segment modules, and affected
      transaction modules. Then run untruncated `pytest --collect-only` and
      require exit zero plus a nonzero collected-test count. Running collection
      against conftest.py alone and receiving "no tests collected" is not a
      valid collection gate.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run the smallest tests covering
      settings, shared support, 4010 and 5010 segments, loop initializers,
      repeatable segments, parser behavior, serialization, CLI behavior, and
      each repaired transaction family. Preserve the pytest exit status; do
      not infer success from truncated stdout or a shell pipeline.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. Compare representative valid and
      invalid inputs against the semantic snapshots and tests. Check normalized
      values, exact requiredness, cross-field rules, duplicate detection,
      dates, component fields, list wrapping, error locations, and output
      ordering. Import success alone cannot establish semantic equivalence.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate is
      red. Read the first complete traceback, identify its earliest
      project-owned frame, make the smallest behavior-preserving repair, and
      rerun the same failing command. Only broaden testing after it passes.
      Continue until all gates are green; never end the turn with "ready",
      "task completed", a summary of partial work, or an unexecuted edit.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Inspect the exact
      diff, compile affected files, and search for malformed decorators,
      dropped imports, deleted annotations, lower-case booleans, altered
      indentation, commented-out validation, duplicated arguments, and
      unintended repository-wide method changes. Revert or repair a bad batch
      before stacking more edits on it.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, class Config,
      root_validator, v1 validator, allow_reuse, __fields__, ModelField,
      SHAPE_LIST, field_info.extra, unsupported Field extras, regex arguments,
      malformed model_validator decorators, empty or no-op function bodies,
      commented-out validators, and accidental JSON literals. Classify any
      intentional compatibility surface explicitly; do not silently ignore it.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the repository's exact full-suite command without head,
      tail, grep, tee, or a timeout that hides completion. If logging is
      necessary, redirect output to a file, capture `$?` immediately, then
      inspect the file separately. Require exit zero and record collected,
      passed, failed, skipped, and warning counts.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck public imports, settings, schema or metadata use, parser and X12
      output, serialization, repeatable-list normalization, registries, and
      representative invalid-input errors. Ensure no test was disabled,
      deselected unexpectedly, or made vacuous to obtain green.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Run git diff --check, inspect the
      complete diff and status, confirm only intended files changed, and rerun
      any gate affected by the final edits. Explicitly reject pydantic.v1
      imports, deleted or empty function bodies, commented-out logic, helper
      scripts or migration-plan debris, and claims of success unsupported by a
      recorded full-suite exit zero.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report the native-v2 migration areas changed, the exact validation
      commands and results, and any genuine residual warnings or risks.
      Otherwise continue repairing rather than reporting partial completion.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Do not import from pydantic.v1 or another Pydantic v1 compatibility namespace to make the suite collect.
  - Do not delete, empty, bypass, comment out, replace with pass, or otherwise neutralize a function or validator body to make a module import.
  - Do not stop after fixing BaseSettings; rerun collection immediately and continue through the next complete traceback until the full suite passes.
  - Do not repeatedly restart repository exploration, rewrite the same migration plan, or spend the attempt producing summaries instead of executing the next red gate.
  - Do not use broad sed or regex substitutions for root validators, field-validator signatures, inherited fields, or arbitrary `.dict()` and `.json()` calls.
  - Do not convert every root validator to the same model-validator mode or retain a dict-style `(cls, values)` body under a v2 after validator.
  - Do not remove subclass field defaults such as segment names merely to silence inherited-field errors; annotate and preserve them.
  - Do not use lower-case JSON booleans in Python source or assume a successful compile proves model construction works.
  - Do not trust a pipeline's final command status as pytest's status; avoid output-truncating pipelines or preserve pytest's status explicitly with pipefail or PIPESTATUS.
  - Do not treat zero tests collected, conftest-only collection, import success, one focused pass, warnings-only output, or a completion summary as a passing suite.
  - Do not emit a proposed tool call as prose, end with an unexecuted edit, or abandon the migration because semantic validator conversion is complex.
```