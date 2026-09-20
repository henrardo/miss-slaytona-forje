---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 28
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Preserve every validator's substantive checks and return
  behavior. Treat Python source as Python: use True and False, never JSON
  literals true and false. Do not confuse an import success, successful
  collection, a zero-looking pipeline status, or a green focused test with
  completion. Completion requires production code to compile, test collection
  to succeed, focused behavior tests to pass, the exact untruncated full-suite
  command to exit zero, and the final diff to pass static and
  behavior-preservation audits.

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
      `references/repository-assessment.md`. Run the repository's exact full
      test command without `head`, `tail`, or another pipeline that can hide
      pytest's exit status. If output is large, redirect it to a file, capture
      `$?` immediately, and inspect the complete first traceback from that
      file. Record the command, real exit status, collection count, first
      blocker, and installed Pydantic versions. A shell tool reporting exit
      zero for `pytest ... | head`, `pytest ... | tail`, or `pytest ... | tee`
      is not a passing baseline unless pipefail or PIPESTATUS proves pytest
      itself exited zero.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository path once with `pwd`, use that exact path thereafter, and
      inspect `git status --short` plus `git diff`. Distinguish user changes
      from migration changes and never discard user work. Do not repeatedly
      guess similar paths such as agent-warm, agent-worm, agent-wrap, or
      agent-wam. If the tree is clean, preserve that fact as a recovery point;
      if it is dirty, identify ownership of every pre-existing change before
      editing.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect dependency manifests,
      target requirement files, lockfiles, test configuration, package
      exports, and migration-specific tests before editing. Read repository
      artifacts such as `requirements-v2.txt` because they may encode the
      intended post-migration dependency set and measured expectations. Prefer
      listing files and reading bounded ranges over guessing filenames or
      loading multi-thousand-line modules in one call. Treat tests for public
      helpers, repeatable fields, serialization, and validation errors as part
      of the contract rather than obstacles to remove. Do not edit tests to
      conceal production migration failures unless the task explicitly
      requires a test API update and the original behavior remains covered.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Verify the active interpreter,
      Pydantic, pydantic-core, pydantic-settings, pytest, and package import
      locations. Install or select the repository's declared target
      environment before attributing errors to source code. Confirm imports
      resolve from the working tree rather than an unrelated installed copy.
      Do not use `pydantic.v1`, `pydantic.v1.*`, or a compatibility shim to
      make the old implementation appear migrated.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search production code for
      BaseSettings, class Config, validator, root_validator, allow_reuse,
      each_item, always, pre, values and field callback parameters, __fields__,
      ModelField, field_info.extra, shape constants, Field extras, regex,
      constr(regex=), conlist item arguments, min_items/max_items, Optional
      fields without defaults, parse_obj, parse_raw, from_orm, dict, json,
      copy, schema, and dynamic model registries. Save filenames and line
      numbers. Search imports, decorators, direct calls, helper partials, and
      aliases separately so a decorator count does not hide incompatible
      imports. Interpret grep exit one as “no matches” when appropriate, not as
      a migration failure.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Inventory imports and tests for
      helpers such as `_is_list_field`, model registries, loop initializers,
      custom X12 rendering, settings behavior, enum serialization, delimiters,
      component metadata, and validation errors. A helper imported by tests or
      downstream modules remains public even if its name starts with an
      underscore. Record representative valid and invalid fixtures for later
      semantic comparison. Include model defaults such as specialized
      `segment_name` values because registries and renderers may depend on
      them even when ordinary construction does not expose the dependency.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Order work by executable
      dependency: environment and imports, shared settings and base models,
      field definitions, validator infrastructure, individual validators,
      introspection and registries, parsing and serialization, specialized
      models, then tests. Identify the smallest current collection blocker.
      Do not spend the attempt writing a separate migration-plan document when
      the executable repair can begin. Use the inventory as a checklist and
      update it as each category becomes executable.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Make one coherent semantic
      change at a time and immediately compile or import the affected module.
      Before broad edits, save the relevant diff or use version control so a
      bad transformation can be reverted without losing good work. Set aside
      time for the full suite; do not consume the attempt on exhaustive
      browsing before the first repair. Prefer precise edits over generated
      migration scripts. If a codemod is available, treat its output as an
      untrusted draft and audit every hunk before continuing.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Repair only the first complete
      traceback and rerun the narrowest command that reproduces it. If the
      first blocker says `BaseSettings` moved, immediately migrate the settings
      import and dependency before exploring unrelated large model modules.
      Typical later blockers include removed Field arguments, inherited-field
      annotation errors, malformed decorators, missing public helpers, and
      syntax damage from automated edits. Continue until collection advances;
      an import smoke test alone is only a checkpoint.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Update every authoritative
      dependency declaration consistently to native Pydantic 2 and add
      pydantic-settings when BaseSettings is used. Import BaseSettings and
      SettingsConfigDict from `pydantic_settings`, translate settings Config
      behavior to `model_config`, and change `Field(regex=...)` to
      `Field(pattern=...)`. Preserve unrelated declared dependencies rather
      than replacing the dependency list wholesale. Verify environment-variable
      case sensitivity, defaults, aliases, and validation with focused
      construction tests. Re-run the original collection reproducer before
      touching the next category.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Translate each shared `Config`
      class to `ConfigDict` without dropping behavior such as use_enum_values,
      frozen/immutability, extra handling, population by name, assignment
      validation, arbitrary types, or serialization rules. Put shared behavior
      on the actual common base model so specialized models inherit it.
      Do not add permissive `extra="allow"` merely to silence annotation or
      schema errors unless the v1 contract genuinely allowed extras. Compile
      and instantiate representative base models after this edit.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires an
      annotation when a subclass overrides an inherited field. Convert
      assignments such as `segment_name = X12SegmentName.CR5` to annotated
      fields such as `segment_name: X12SegmentName = X12SegmentName.CR5`.
      Do not remove all subclass `segment_name` declarations; their defaults
      drive parsing, rendering, and registries. Do not solve this with
      ClassVar when the value is part of model data. Search globally for every
      unannotated override and import both major model families afterward.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Translate `regex` to
      `pattern`, including constrained-string factories; migrate list length
      and constrained-type arguments according to the installed v2 API; and
      preserve numeric, decimal, string, and collection bounds. Move custom
      Field extras such as `is_component` into
      `json_schema_extra={"is_component": True}` and update every reader of
      that metadata. Use Python `True`, never lowercase `true`. Review every
      `Optional[T]` field: in v2 it remains required unless it has `= None`;
      add defaults only where the v1 runtime or repository contract treated
      omission as valid. Confirm constrained values at their boundaries with
      one accepted and one rejected example.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove v1 `allow_reuse`;
      preserve reusable validator functions as ordinary substantive functions
      and register them with v2 decorators at the model declaration. Do not
      shadow Pydantic's `field_validator` import with a project partial of the
      same name. Before changing shared validators, enumerate every call site
      and determine whether it receives a raw mapping, a ValidationInfo
      object, or an already-built model. Preserve project helper names that
      callers import; rename only an internal decorator factory that conflicts
      with Pydantic and update all of its call sites together.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each validator
      individually, not with blind repository-wide substitution. Choose
      `mode="before"` only when the old validator required raw input. Replace
      v1 `values` access with `ValidationInfo.data`, and field metadata access
      with the validated field name plus `cls.model_fields` when needed.
      Remember that `ValidationInfo` is not a mapping: do not call `.get`
      directly on it. Preserve ordering assumptions, missing-value behavior,
      date parsing, error text where tested, and return values. Add
      `@classmethod` only in the form supported by Pydantic v2. For a
      validator registered by assignment, verify the wrapped reusable
      function's signature under v2 rather than assuming a decorator rename is
      sufficient. Compile and run a valid and invalid example after each
      validator family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md`. Classify every old
      root_validator by semantics before editing it. A pre root validator
      becomes `@model_validator(mode="before")`, accepts the raw mapping
      (normally `cls, values`), and returns that mapping. A post root validator
      becomes `@model_validator(mode="after")`, normally accepts `self`, reads
      attributes rather than `values.get`, and returns `self`. Account for
      assignment validation only if the model enables it. Do not merely rename
      the decorator while retaining an incompatible signature. Do not generate
      malformed forms such as
      `@model_validator(mode="before")(mode="before")`. Preserve every check,
      exception, mutation, and return path; never delete or empty a validator
      body to obtain an import. Compare each converted function against its
      pre-edit body before moving on.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__` with
      `model_fields` and rewrite logic that depended on v1 ModelField shape,
      name, type_, outer_type_, field_info, or extra attributes. Derive list
      structure from annotations with `typing.get_origin` and `get_args`,
      including Optional/Union wrappers and both `typing.List` and built-in
      `list`. Read custom metadata from `json_schema_extra`. Update dynamic
      segment registries to retrieve the annotated `segment_name` field
      default without constructing models or silently registering None.
      Inspect the actual v2 FieldInfo API instead of inventing replacements for
      removed shape constants.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Implement and retain the
      public `_is_list_field` helper expected by tests and use it in
      repeatable-segment initialization. It must recognize direct List
      annotations and list types nested in Optional/Union without treating
      strings or unrelated iterables as repeatable fields. Accept the field
      representation actually supplied by repository callers, not only a raw
      annotation chosen for convenience. Verify direct helper tests, required
      scalar fields, optional list fields, and construction where one
      repeatable segment is wrapped into a one-element list.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 model APIs with
      model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, and model_json_schema only where semantics match. Preserve
      include/exclude, exclude_none, exclude_unset, aliases, enum and Decimal
      handling, delimiters, component fields, custom JSON encoders, and X12
      field order. Do not apply a blind `.dict(` or `.json(` replacement to
      arbitrary objects. Where code accepts either dictionaries or models,
      retain both paths explicitly. Confirm whether downstream code needs
      Python-mode or JSON-mode dumps before choosing `model_dump` options. Run
      round-trip parser and exact-output tests, not just import checks.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile every production Python
      file with `python -m compileall` or an equivalent command before pytest.
      Repair syntax, indentation, malformed decorators, invalid lowercase
      literals, and broken imports immediately. Do not continue semantic edits
      while compilation is red. Compilation success is a gate, not completion.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Smoke-import shared models,
      settings, both major segment modules, transaction modules, dynamic
      registries, and public helpers, then run untruncated
      `pytest --collect-only`. Capture the real exit code without masking it
      through a pipeline. Verify collection found the expected nonzero number
      of tests. Fix the first complete traceback and repeat until collection
      exits zero.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run the smallest relevant tests
      for settings, support utilities, shared 4010 and 5010 segments, loop
      initializers, parsers, serialization, and the transaction family most
      recently changed. A nonexistent node id, an empty selection, or a command
      piped to `head` is not evidence. Record exact pass and failure counts,
      inspect warnings that identify remaining v1 APIs, and continue after the
      first green focused test.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For representative models,
      compare accepted valid inputs, rejected invalid inputs, defaults,
      coercion, normalized values, and serialized output against tests and the
      pre-migration contract. Explicitly test electronic-payment cross-field
      checks, dates, repeatable fields, adjustment groups, name requirements,
      inherited segment names, component metadata, settings, and registry
      lookup. Validate both omission and explicit None where requiredness may
      have changed. Passing imports cannot demonstrate these semantics.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate
      remains red. Use the loop: run one unmasked command, read its first full
      traceback, form one evidence-based hypothesis, make the smallest
      semantic edit, compile the touched module, rerun the reproducer, then
      periodically rerun collection and a wider subset. Keep working from the
      earliest failure rather than browsing unrelated files or repeatedly
      researching already-known API changes. Do not end the turn with “task
      completed,” a migration summary, or a future-tense promise while any
      gate is red.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Prefer AST-aware or
      narrowly scoped edits. If sed, regex, or a script changes multiple
      locations, inspect every changed hunk, compile every touched file, and
      search for duplicated arguments, decorator corruption, lost imports,
      indentation damage, lowercase booleans, invalid colons, unannotated
      overrides, and emptied bodies. Compare the transformed functions with
      their original versions. Revert a bad transformation rather than
      layering more global substitutions over it.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, validator,
      root_validator, allow_reuse, incompatible model-validator signatures,
      __fields__, field_info.extra, SHAPE_LIST, regex arguments, unsupported
      Field extras, lowercase true/false, malformed decorators, pass-only
      replacement bodies, and obsolete model API calls. Also inspect functions
      whose line count sharply decreased during migration. Classify intentional
      textual mentions separately from executable usage. The audit must find
      no compatibility imports and no behavior-removing no-ops.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the repository's exact complete test command once without
      truncation or a masking pipeline. Redirect to a log if needed, capture
      the command's own exit status immediately, then inspect the final summary
      and every failure. Zero collected tests, interrupted collection, an
      absent final summary, or a shell pipeline exit zero does not pass this
      gate. If red, return to iterative repair rather than reporting partial
      success.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck representative valid and invalid models, parser round trips,
      exact X12 rendering, settings, metadata-driven components, registries,
      repeatable initialization, and public helper imports. Review any warning
      increase for signs that v1 APIs remain. Compare each migrated validator
      family with its original logic. Green tests do not authorize deleting
      validators, dropping branches, or weakening constraints that lack direct
      coverage.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect `git status --short`,
      the complete diff, and a diff-stat. Remove only migration-generated
      scratch files, codemods, logs, and plan documents; preserve user files.
      Confirm dependency declarations are consistent, no accidental test edits
      remain, every substantive old function still has substantive behavior,
      no `pydantic.v1` import exists, compilation is green, collection is
      nonempty, static audit is clean, behavior checks are green, and the exact
      full suite exited zero.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report the dependency target, major semantic migrations, exact validation
      commands, full-suite pass count, and any genuine residual warnings.
      Never claim success from import checks, compilation, collection, focused
      tests, an incomplete run, a masked exit status, or work that merely moved
      imports to `pydantic.v1`.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, `pydantic.v1.*`, or another Pydantic v1 compatibility namespace to make the suite collect.
  - Never delete, empty, bypass, replace with `pass`, or otherwise turn a substantive function or validator into a no-op merely to make imports or tests proceed.
  - Never edit tests merely to hide production migration failures or reduce the expected test count.
  - Never use blind repository-wide decorator replacement for validator migration; decorator names, modes, signatures, inputs, and return values must be migrated together.
  - Never convert every root validator to the same model-validator mode; classify pre/raw-mapping and post/model-instance semantics separately.
  - Never retain `cls, values` mapping logic under an after model validator or use `self` under a before model validator without a demonstrated API reason.
  - Never call mapping methods such as `.get` on ValidationInfo; use `info.data` where field ordering permits.
  - Never remove inherited-field overrides such as specialized `segment_name` defaults to silence annotation errors; add explicit annotations.
  - Never convert model fields that drive parsing or registries into ClassVar merely to suppress Pydantic errors.
  - Never replace all `.dict(` or `.json(` text mechanically without proving each receiver is a Pydantic model and preserving call semantics.
  - Never run broad sed, regex, or generated-script transformations without inspecting every changed hunk and compiling every touched file immediately.
  - Never layer additional global substitutions over a transformation that already caused syntax, indentation, or decorator damage; revert it first.
  - Never use JSON literals `true`, `false`, or `null` in Python source; use `True`, `False`, and `None`.
  - Never treat `pytest ... | head`, `pytest ... | tail`, or a `tee` pipeline's apparent zero status as pytest's real exit status unless pipefail or PIPESTATUS is handled correctly.
  - Never treat import success, compilation, one focused passing test, successful collection, or partial pass counts as completion.
  - Never stop to write a progress summary, migration plan document, or “task completed” message while the full suite remains red.
  - Never repeatedly guess repository paths or filenames; establish the path once and inspect the tree before reading.
  - Never assume grep exit one is an execution failure when it simply means the prohibited pattern is absent.
  - Never add `= None` to every Optional field mechanically; preserve the repository's required-versus-omittable contract.
  - Never weaken constraints, remove validation branches, suppress exceptions, or change tested error behavior solely to obtain green tests.
  - Never discard public helpers such as `_is_list_field` because their names look private when repository tests or consumers import them.
  - Never shadow Pydantic's `field_validator` or `model_validator` with a project-defined partial or helper of the same name.
  - Never assume a reusable v1 validator keeps a valid signature after only changing its decorator.
  - Never register a dynamic model under None or construct required models merely to discover a class field default.
  - Never replace dependency lists wholesale and accidentally remove unrelated project requirements.
  - Never leave migration-generated scripts, plans, or scratch files in the final diff unless they are intentional maintained project artifacts.
  - Never declare completion without production compilation, clean nonempty collection, focused semantic tests, an untruncated full-suite exit zero, static migration audit, behavior audit, and final diff review.
```