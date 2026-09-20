---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 34
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, registries, and domain behavior. Work from complete tracebacks,
  original function bodies, repository tests, and executable checkpoints
  rather than speculative bulk rewrites. Never satisfy the task by importing
  from pydantic.v1 or another v1 compatibility namespace. Never make code
  import by deleting, emptying, bypassing, or replacing a function body with a
  no-op. Preserve every validator's substantive checks, mutations, errors, and
  return behavior. Treat Python source as Python: use True and False, never
  JSON literals true and false. Do not confuse import success, successful
  collection, a zero-looking pipeline status, a green focused test, or
  warnings-only output with completion. Completion requires production code
  to compile, nonempty test collection to succeed, focused behavior tests to
  pass, the exact untruncated full-suite command to exit zero, and the final
  diff to pass static and behavior-preservation audits. Capture real command
  exit codes without piping pytest through head, tail, tee, or grep unless
  pipefail is enabled and the pytest status is explicitly preserved. Continue
  repairing until the full suite passes; never stop with a progress summary,
  migration plan, partial import success, collection errors, or known failing
  tests.

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
      `references/repository-assessment.md`. Run the repository's exact
      collection or full-suite command without truncating or masking its exit
      status. Save the complete first traceback, command, exit code, collected
      test count, and installed Python, Pydantic, pydantic-core, and
      pydantic-settings versions. If output must be written to a file, run the
      command directly with redirection, capture `$?`, and inspect the file
      afterward. A command ending in `| head`, `| tail`, `| grep`, or `| tee`
      does not establish a trustworthy baseline unless pipefail and explicit
      status preservation are used.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read and follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the repository root with `pwd`, inspect `git status --short`, and
      distinguish user changes, prior migration changes, generated files, and
      harness files. Never discard or overwrite unrelated user work. When a
      previous attempt left a partially migrated tree, inspect its full diff
      before continuing and use the base revision only as a semantic reference,
      not as permission to replace whole files. Do not create migration-plan
      files or repair scripts in the repository unless they are required
      deliverables; use temporary files outside the tree for disposable
      analysis.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read and follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect pyproject.toml, lock and
      requirement files, package exports, test configuration, CI commands,
      requirements-v2.txt or equivalent measured target notes, and tests added
      specifically for the migration. Treat tests that import helpers such as
      `_is_list_field` as public compatibility contracts even when the helper
      is underscore-prefixed. Record the exact full-suite command and expected
      collection size. Missing conventional files such as setup.py or
      requirements.txt are not errors when pyproject.toml defines the contract.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read and follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Ensure the active interpreter
      actually imports Pydantic 2 and all split packages required by the
      declared target, especially pydantic-settings. Update dependency metadata
      consistently rather than relying only on the preinstalled environment.
      Do not use pydantic.v1, a compatibility namespace, or dependency
      downgrades to make tests import.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read and follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search every production Python
      file, not only top-level models, for BaseSettings, Config, validator,
      root_validator, allow_reuse, each_item, always, pre, values and field
      signature parameters, __fields__, ModelField, SHAPE_LIST, field_info,
      extra metadata, regex, constr(regex=), min_items, max_items, dict, json,
      parse_obj, parse_raw, from_orm, copy, schema, schema_json, inherited
      unannotated field overrides, optional fields without defaults, and
      import-time registries. Count occurrences by category and file. Interpret
      grep exit code 1 as “no matches,” not a shell failure. Exclude docs and
      tests only when the migration contract says they are not production
      surfaces, while still reading tests for expected behavior.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read and follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Record imports, model constructors,
      accepted coercions, rejected inputs, exact error conditions, serialized
      forms, X12 output, field ordering, model immutability, settings
      environment behavior, reusable validator functions, list-field helpers,
      and generated registry keys. Inspect focused segment tests for both 4010
      and 5010 as well as parser, support, CLI, loop initializer, repeatable
      segment, settings, and complete transaction tests. Do not infer that a
      helper may be removed merely because its name begins with an underscore.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Before rewriting validators or shared model code, capture the original
      source for every affected function and class from the current working
      tree or, when that file is already partially migrated, from the
      appropriate base revision while preserving unrelated user changes.
      Record each decorator, signature, branch, raise, mutation, field-order
      dependency, and return. Use this semantic snapshot during review;
      repeated attempts corrupted bodies through regex rewrites and then lacked
      a reliable source from which to restore behavior. Never replace a
      partially migrated file wholesale when it contains pre-existing user
      edits. Never empty a function body, replace it with `pass`, return an
      unconditional value merely to import, comment out its checks, or delete
      the validator to avoid an error.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read and follow `build-migration-ledger` in
      `references/repository-assessment.md`. Create one ledger entry per
      concrete occurrence, including file, symbol, old interface, semantic
      category, intended native-v2 replacement, dependent tests, status, and
      last executable checkpoint. Keep separate entries for decorators and
      their imports so a renamed decorator cannot be left undefined. Track
      4010 and 5010 implementations independently even when they look similar.
      Store disposable ledger data outside the repository unless the user asks
      for it as a deliverable.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read and follow `classify-migration-work` in
      `references/repository-assessment.md`. Order work by executable
      dependency: collection blockers, settings and shared model bases,
      inherited fields and constraints, reusable validator infrastructure,
      field validators, model validators, introspection and helpers, parsing
      and serialization, registries, then downstream behavior. Separate safe
      mechanical replacements from semantic rewrites. Any decorator migration,
      function signature rewrite, body transformation, inherited-field change,
      or metadata conversion is semantic and must be reviewed individually.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read and follow `create-small-edit-checkpoints` in
      `references/verification-and-repair.md`. Define a compile or import
      command and the narrowest relevant test for every edit cluster. Change
      one semantic category or one closely related file pair at a time. After
      each edit, inspect the diff and run its checkpoint before proceeding.
      Avoid long exploratory runs, repeated web research for already observed
      errors, and broad edits made without an immediate executable gate.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read and follow `repair-first-collection-blocker` in
      `references/migration-implementation.md`. Repair only the first complete
      collection traceback, rerun nonempty collection, and repeat until the
      next blocker is exposed. For the common PydanticUserError stating that a
      post `@root_validator` requires `skip_on_failure=True`, do not merely add
      that compatibility flag as the final migration. Convert the validator to
      native `@model_validator` with the correct mode, signature, body access,
      and return semantics. Do not declare progress complete after one module
      imports.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read and follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings imports to
      pydantic_settings, declare pydantic-settings in project dependencies,
      and convert settings Config behavior to SettingsConfigDict or supported
      model_config keys. Preserve case sensitivity, environment prefixes,
      dotenv behavior, defaults, caching, and validation. Replace Field
      `regex=` with `pattern=`. Import-test the settings module and construct
      settings under representative environment variables before proceeding.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read and follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Replace class Config with
      ConfigDict or appropriate settings configuration while preserving
      `extra`, enum value handling, immutability, assignment behavior,
      arbitrary types, aliases, population rules, and serialization. For
      frozen delimiter models use native frozen configuration rather than
      obsolete allow_mutation. Apply shared configuration at the correct base
      class so all segment and group subclasses retain behavior. Check for
      warnings that reveal ignored or renamed configuration keys.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read and follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires inherited
      model fields to be overridden with annotations. Convert assignments such
      as `segment_name = X12SegmentName.CR5` to annotated overrides such as
      `segment_name: X12SegmentName = X12SegmentName.CR5`; do not delete these
      domain identifiers or remove all subclass overrides. Search all model
      trees for similar unannotated overrides. Verify model_fields defaults,
      segment construction, X12 output, and registry keys after each cluster.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read and follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Replace `regex` with `pattern`
      in Field and constrained string declarations, and migrate `min_items` and
      `max_items` to native v2 length constraints where required. Move custom
      Field keywords such as `is_component=True` into
      `json_schema_extra={"is_component": True}` using Python booleans. Audit
      Optional fields carefully because `Optional[T]` without a default is
      still required in Pydantic v2; add `= None` only where v1 behavior and
      tests prove omission was allowed. Preserve aliases, defaults,
      default-factory behavior, decimal limits, list cardinality, field order,
      and JSON schema meaning.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read and follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove allow_reuse rather than
      passing it to v2 decorators. Preserve reusable callable identities and
      the class-level assignment pattern used to attach validators. Avoid
      shadowing Pydantic's `field_validator` import with a project partial of
      the same name; rename project wrappers explicitly if needed and update
      all imports atomically. Confirm decorator order, field names, validation
      mode, check_fields behavior, signatures, and return values with a
      minimal model before applying the pattern broadly.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read and follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each validator
      individually to `@field_validator`, choosing mode="before" only when the
      old validator used pre=True or genuinely needs raw input. Replace the v1
      `values` argument with ValidationInfo and use `info.data`, remembering
      that it contains only already-validated fields and therefore depends on
      field order. Replace field/config parameters with supported v2
      introspection. Preserve `always` behavior with validated defaults or an
      equivalent native design rather than silently dropping it. Validate
      shared date functions and organization-name checks against both valid
      and invalid fixtures. Do not perform a blind text replacement of
      decorator names while leaving v1 signatures unchanged.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Read and follow `migrate-model-validators` in
      `references/migration-implementation.md`. Classify every root validator
      before editing. Convert `pre=True` validators to
      `@model_validator(mode="before")` with a class-oriented signature that
      accepts and returns raw data; preserve dictionary mutations and wrapping
      of singleton repeatable segments. Convert post root validators to
      `@model_validator(mode="after")` instance methods that read attributes,
      perform every original check, and return `self`. Where assignment
      validation may pass an instance, handle the documented native-v2 input
      shape without weakening checks. Do not mechanically replace
      `values.get(...)` with attribute access across a whole file, do not leave
      `(cls, values)` signatures on after validators, and do not convert all
      validators to mode="before". Compare every migrated body with its
      semantic snapshot before running focused valid and invalid cases.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read and follow `close-validator-import-decorator-gap` in
      `references/migration-implementation.md`. Search production files for
      every legacy decorator and import after validator edits. Ensure every
      used `field_validator`, `model_validator`, and ValidationInfo symbol is
      imported from native Pydantic and that no stale validator,
      root_validator, or allow_reuse occurrence remains. Also detect malformed
      automated output such as duplicate decorator calls, missing indentation,
      bare decorators, duplicate mode arguments, decorator colons, or imports
      inserted inside unrelated blocks. Compile and import each affected
      module before moving on.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read and follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace __fields__, ModelField,
      SHAPE_LIST, `.shape`, `.type_`, `.field_info.extra`, and field `.name`
      assumptions with model_fields, FieldInfo annotations, typing.get_origin
      and get_args, field dictionary keys, and json_schema_extra. Handle
      Optional, Union, Annotated, and nested list annotations deliberately.
      Access model_fields on the model class, not instances, to avoid
      deprecation paths. Preserve component separators, field order, parser
      dispatch, nested X12 behavior, and schema metadata.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read and follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Implement or retain the public
      `_is_list_field` helper expected by tests, using native typing
      introspection rather than SHAPE_LIST. It must recognize direct and
      supported optional or annotated list fields without classifying scalar
      fields as lists. Use the same helper in the singleton-to-list model
      validator so the public helper and runtime behavior cannot drift.
      Exercise the loop-initializer and repeatable-segment tests explicitly.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read and follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 APIs with native
      model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and TypeAdapter only where semantics
      match. Preserve exclude flags, enum and Decimal handling, custom JSON
      encoding, aliases, delimiter injection, nested model traversal, CLI
      output, and X12 serialization order. Do not globally replace every
      `.dict()` call without proving the receiver is a Pydantic model; shared
      validation functions may receive either dictionaries or models and must
      preserve both paths. Run parser, support, CLI, and round-trip tests after
      this stage.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Exercise import-time and generated registries after introspection and
      inherited-field changes. Verify each registered segment key is derived
      from the annotated `segment_name` field default, no key becomes `None`,
      and 4010 and 5010 registries retain expected classes. Use model_fields
      directly and avoid class-instance deprecation paths. Registry import
      warnings are not harmless when they indicate lookup behavior changed.
      Compare registry cardinality and representative keys with the semantic
      snapshot or tests.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read and follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile every production Python
      file, not only recently edited files. Treat indentation errors, malformed
      decorators, undefined names, and syntax errors as evidence that an
      automated transformation must be reverted or repaired before further
      migration. Compilation is a gate, not completion.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read and follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import core models, settings,
      both base segment modules, representative transaction packages, and
      public helpers. Then run the exact untruncated collect-only command,
      capture its real exit code, and require a nonzero collected test count.
      Repair one complete traceback at a time until collection exits zero.
      “No tests ran,” an import-only smoke test, or output truncated through a
      successful downstream command does not pass this gate.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read and follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Run focused tests for settings,
      support utilities, base 4010 segments, base 5010 segments, list helpers,
      loop initializers, repeatable segments, parsing, serialization, and one
      representative transaction from each affected family. Use exact node IDs
      only after listing them; a pytest “not found” error is not a behavior
      result. Require both valid construction and expected rejection cases.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read and follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For each migrated validator,
      compare accepted inputs, rejected inputs, normalization, mutations,
      cross-field dependencies, exception types and messages where tested,
      defaults, and returned model state against the semantic snapshot.
      Specifically test ACH payment requirements, adjustment groups, date
      formats, organization names, duplicate segment codes, singleton
      repeatable segments, and transaction counts when those behaviors exist.
      A model that imports but no longer rejects invalid data fails this gate.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read and follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md` whenever an executable gate
      remains red. Use the first complete traceback, identify the owning
      migration-ledger entry, inspect the original function and current diff,
      make the smallest semantic repair, compile, rerun the narrow failing
      test, rerun collection when imports changed, and then rerun the broader
      focused set. Continue until green. Do not stop because the task is
      complex, time-consuming, or partially improved; do not end with “task
      completed,” a summary, or a plan while any known test is red.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read and follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and
      immediately after every automated transformation. Inspect the complete
      diff around every changed function, not only search counts. Compare
      transformed validator bodies to semantic snapshots and reject altered
      branches, missing returns, duplicated decorators, lost imports,
      indentation damage, JSON booleans in Python, accidental repository
      artifacts, or broad unrelated formatting churn. Prefer explicit edits or
      an AST-aware codemod over sed and regex for semantic rewrites.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Require no production imports
      from pydantic.v1 or another v1 compatibility namespace; no legacy
      BaseSettings import; no validator or root_validator decorators; no
      allow_reuse; no SHAPE_LIST, ModelField, __fields__, field_info.extra, or
      unsupported Field keywords; no malformed decorators; no empty, deleted,
      bypassed, or unconditional validator bodies; and no obsolete method use
      left without a documented compatibility reason. Search findings must be
      inspected in context rather than mass-replaced.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read and follow `run-full-suite` in
      `references/verification-and-repair.md` only after the static audit
      passes. Run the repository's exact full-suite command untruncated and
      without a status-masking pipeline. Capture command, complete output,
      collected count, passed, failed, skipped, warnings, duration, and real
      exit code. Require exit code zero and at least one collected test.
      Warnings about deprecated Pydantic interfaces, ignored constraints,
      class-based config, instance model_fields access, or changed serializer
      behavior must be investigated even when tests pass.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read and follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck the migration ledger against semantic snapshots, public
      contracts, settings behavior, parser and serializer round trips, schema
      metadata, registry contents, and representative invalid inputs. Confirm
      no tests were disabled, deselected unexpectedly, edited to weaken
      assertions, or skipped through collection loss. Native v2 behavior must
      replace v1 behavior without silently narrowing or broadening the domain
      contract.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect `git status --short`,
      the complete diff, and diff statistics. Confirm only intended files
      changed; no temporary plans, fixer scripts, logs, caches, or unrelated
      harness files were added; dependencies match imports; every ledger entry
      is resolved; all semantic snapshots were reviewed; production code
      compiles; collection is nonempty; focused tests and the exact full suite
      pass; and prohibited compatibility or no-op workarounds are absent.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read and follow `report-completion` in
      `references/verification-and-repair.md` only after the final gate.
      Report the native-v2 interfaces adopted, behavior-sensitive areas
      verified, exact full-suite command, collected and passed counts, exit
      code, remaining warnings or risks, and changed files. If any gate is
      red, do not claim completion; continue the iterative repair procedure or
      state the concrete external blocker and the last trustworthy checkpoint.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from pydantic.v1 or another Pydantic v1 compatibility namespace to make the migration pass.
  - Never delete, empty, bypass, comment out, or replace a validator or function body with a no-op merely to make the module import.
  - Never bulk-rewrite validator decorators, signatures, and bodies with sed or regex without per-function semantic review and immediate compile and test checkpoints.
  - Never convert every root validator to the same model_validator mode; classify pre and post behavior first.
  - Never leave a v1 `(cls, values)` body under a mode="after" model validator or treat an after-validator instance as a dictionary.
  - Never add `skip_on_failure=True` to deprecated root validators and mistake that temporary compatibility repair for a native-v2 migration.
  - Never rename decorators without updating and auditing their imports in the same checkpoint.
  - Never shadow Pydantic's field_validator or model_validator with a project helper of the same name.
  - Never remove inherited domain-field overrides such as segment_name to avoid PydanticUserError; annotate and preserve them.
  - Never use JSON literals `true`, `false`, or `null` in Python source.
  - Never globally replace `.dict()` or another common method without proving each receiver is a Pydantic model.
  - Never assume Optional means not required in Pydantic v2; verify omission behavior and defaults.
  - Never remove public or test-imported helpers such as `_is_list_field` because their names appear private.
  - Never trust an import smoke test, compile success, collect-only success, or one focused test as evidence that the migration is complete.
  - Never pipe pytest through head, tail, grep, or tee and report the downstream command's zero status as the pytest result.
  - Never treat zero collected tests, a missing pytest node ID, warnings-only output, or a command timeout as a green test gate.
  - Never stop after producing a migration plan, summary, ledger, or list of remaining work while the requested code migration is incomplete.
  - Never overwrite whole partially migrated files from git when doing so would discard unrelated user changes.
  - Never leave temporary migration plans, ad hoc fixer scripts, logs, or generated artifacts in the repository unless explicitly requested.
```