---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 23
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
  behavior. Do not confuse an import success, successful collection, a
  zero-looking pipeline status, or a green focused test with completion.
  Completion requires production code to compile, test collection to succeed,
  focused behavior tests to pass, the exact untruncated full-suite command to
  exit zero, and the final diff to pass static and behavior-preservation audits.

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
      Read `references/repository-assessment.md` and follow its
      `establish-the-failure` instructions. Run the repository's exact test
      command without `head`, `tail`, `grep`, or an unchecked `tee` pipeline.
      Capture the command, true exit status, complete traceback, collection
      count, and Pydantic/Python versions. If output must be saved, redirect it
      to a file, save `$?` immediately, and inspect the file separately; never
      treat the exit status of a display command as the test status.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Follow `confirm-location-and-working-tree` in
      `references/repository-assessment.md` before changing anything. Confirm
      the absolute repository path once and reuse it to avoid similarly named
      path mistakes. Record tracked, modified, and untracked files. Do not
      discard pre-existing user changes, and do not mistake artifacts created
      by earlier attempts for intentional source.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Follow `inspect-repository-contract` in
      `references/repository-assessment.md`. Inspect the actual dependency,
      packaging, test, lint, and typing configuration before assuming files
      such as setup.py or requirements.txt exist. Read migration-specific
      dependency files and tests because they may encode the required
      post-migration contract, including public helper names and native-v2
      prohibitions.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Follow `make-runtime-match-target` in
      `references/repository-assessment.md`. Verify imports resolve against the
      intended environment and record exact installed versions of pydantic,
      pydantic-core, pydantic-settings, Python, and pytest. Install or update
      only dependencies required by the repository contract. Do not begin a
      native-v2 migration while tests are silently running against v1.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Follow `inventory-v1-surface` in
      `references/repository-assessment.md`. Search the entire production tree,
      not only top-level modules, for imports, decorators, model configuration,
      settings, constraints, metadata, serialization, parsing, introspection,
      inherited field overrides, and dynamic model registration. Include bare
      decorators such as `@root_validator`, decorator factories assigned to
      class attributes, multiline imports, `allow_reuse`, `regex`, constrained
      types, `__fields__`, `field_info.extra`, `.dict`, `.json`, `parse_obj`,
      and non-annotated overrides such as `segment_name = ...`.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Follow `inventory-public-and-test-contracts` in
      `references/repository-assessment.md`. Read tests that import internal or
      public helpers, inspect fixtures and expected validation failures, and
      record serialization and ordering expectations. Treat helpers such as a
      list-field detector as migration contracts even if they do not exist in
      the current implementation; collection failures can reveal required
      compatibility surfaces that a search of production code misses.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Follow `classify-migration-work` in
      `references/repository-assessment.md`. Group findings into dependencies
      and settings, shared model configuration, inherited fields, field
      definitions, reusable validators, field validators, model validators,
      introspection, public helpers, parsing, and serialization. Order the plan
      by import and collection blockers, but preserve a checklist for every
      inventory item so later progress does not hide unmigrated files.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md`, then follow
      `create-small-edit-checkpoints`. Make one semantic class of change at a
      time and define its compile, import, collection, and focused-test
      checkpoint before editing. Prefer explicit edits over repository-wide
      regex or sed transformations. If automation is justified, first test it
      on one file, inspect the diff and syntax, then apply it narrowly and audit
      every changed occurrence before continuing.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md`, then follow
      `repair-first-collection-blocker`. Use the first complete traceback to
      repair only the earliest causal blocker, then rerun the smallest command
      that reproduces it with its true exit status. Do not summarize completion
      after an import check; continue until collection exposes the next real
      blocker.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Follow `update-dependencies-and-settings` in
      `references/migration-implementation.md`. Move BaseSettings to
      pydantic-settings, add the declared dependency, migrate settings Config
      behavior to SettingsConfigDict or equivalent native-v2 configuration,
      and replace removed Field keywords such as `regex` with `pattern`.
      Preserve environment variable case sensitivity, defaults, validation,
      caching, and public settings access. Import and instantiate the settings
      model before proceeding.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Follow `migrate-shared-model-configuration` in
      `references/migration-implementation.md`. Convert inner Config classes to
      ConfigDict without losing enum handling, immutability, validation,
      arbitrary-type, assignment, or extra-field behavior. Apply configuration
      deliberately to each shared base class; do not assume a change to one
      base covers unrelated settings or delimiter models. Import and construct
      representative base models after the edit.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Follow `migrate-inherited-field-overrides` in
      `references/migration-implementation.md`. Pydantic v2 requires every
      override of a base-model field to remain annotated. Search all model
      subclasses for assignments such as `segment_name = X12SegmentName.CR5`
      and change them to an appropriate annotated field such as
      `segment_name: X12SegmentName = X12SegmentName.CR5`. Do not fix only the
      first traceback location; scan the complete production tree, compile the
      touched modules, and import both major model families before proceeding.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Follow `migrate-field-definitions` in
      `references/migration-implementation.md`. Replace removed constraint
      names consistently, including Field `regex` to `pattern` and constrained
      string `regex` to `pattern`. Move custom Field extras such as
      `is_component` into `json_schema_extra` using valid Python values
      (`True`, not JSON's `true`). Preserve aliases, defaults, optionality,
      lengths, decimal bounds, list cardinality, schema output, and domain
      meaning. Compile and import after each family of field changes.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Follow `migrate-reusable-validator-infrastructure` in
      `references/migration-implementation.md`. Remove v1-only `allow_reuse`
      and migrate shared decorator factories without shadowing Pydantic's
      `field_validator`. Determine whether each reusable function expects raw
      mappings, ValidationInfo, or model instances and adapt its interface
      explicitly. Preserve reuse at every call site; never make imports pass by
      deleting the decorator, validator call, or function body.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Follow `migrate-field-validators` in
      `references/migration-implementation.md`. Convert each v1 validator
      individually to `field_validator`, choose `mode="before"` only when the
      original consumed raw input, and use ValidationInfo with `info.data`
      instead of treating the third argument as the old values dictionary.
      Preserve field order dependencies, always/run-on-default behavior,
      coercion, return values, and raised errors. Add `@classmethod` only in a
      decorator order accepted by Pydantic v2. Exercise both valid and invalid
      focused examples after each validator family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Follow `migrate-model-validators` in
      `references/migration-implementation.md`. Convert every root validator
      according to its actual semantics rather than by textual substitution.
      A before model validator receives raw input data and must return the data;
      an after model validator normally receives `self`, reads attributes, and
      must return `self`. Rewrite old `values.get(...)` access only after
      selecting the mode. Handle decorator-factory assignments separately.
      Preserve every conditional, mutation, duplicate check, required-field
      check, exception, and return path. Never generate invalid forms such as
      `@model_validator(pre=True)`, `@model_validator(mode="after")(...)`, or a
      bare `@model_validator`. Compile immediately after each file and run
      focused valid and invalid cases before continuing.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Follow `repair-field-introspection` in
      `references/migration-implementation.md`. Replace `__fields__` and
      ModelField assumptions with `model_fields` and inspect v2 field
      annotations, defaults, aliases, and `json_schema_extra`. Use
      `typing.get_origin` and `typing.get_args` where shape or optional/list
      detection is required. Update dynamic segment registries and parsers as
      well as model methods; do not replace names mechanically where the v1 and
      v2 field objects expose different semantics.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Follow `preserve-list-field-helper` in
      `references/migration-implementation.md`. Implement or preserve the
      public list-field helper required by tests using v2 annotations, including
      Optional[List[T]], unions, and Annotated forms where present. Use this
      same helper in repeatable-segment wrapping so public behavior and internal
      initialization cannot drift. Run its direct tests and representative
      scalar-versus-list model construction cases.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Follow `migrate-parsing-and-serialization` in
      `references/migration-implementation.md`. Replace v1 serialization and
      validation APIs with native-v2 equivalents only where behavior is
      equivalent: model_dump, model_dump_json, model_validate, and
      model_validate_json as appropriate. Preserve exclude flags, aliases,
      enum output, custom JSON encoders, nested model handling, delimiter
      metadata, segment ordering, and X12 rendering. Update recursive helpers
      that may receive either mappings or BaseModel instances. Compare concrete
      serialized and rendered outputs, not only absence of warnings.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Follow `compile-production-code` in
      `references/verification-and-repair.md`. Compile every production Python
      file before running pytest. Treat SyntaxError, IndentationError, malformed
      decorators, invalid Python literals, and missing imports as transformation
      damage to repair immediately. Do not rely on tests to discover syntax
      errors one imported module at a time.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Follow `run-import-and-collection-gate` in
      `references/verification-and-repair.md`. Import settings, shared models,
      both major segment modules, representative transaction packages, and
      public helpers, then run the repository's complete collect-only command.
      Record the true exit code without truncating or piping away failures.
      Collection success is a gate to behavior testing, not completion.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Follow `run-focused-behavior-tests` in
      `references/verification-and-repair.md`. Start with tests nearest the
      repaired blocker: settings, support helpers, segment models, repeatable
      list initialization, parsing, serialization, and transaction models.
      Run both acceptance and rejection cases because migrations can make
      validators silently stop running while happy-path tests remain green.
      Capture true exit codes and exact failure counts.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Follow `compare-validation-semantics` in
      `references/verification-and-repair.md`. For every migrated validator
      family, compare representative valid input, invalid input, omitted
      optional/defaulted input, raw input requiring coercion, and dependent
      field ordering. Verify the same domain invariants remain enforced even
      where Pydantic v2 changes error locations or wording. Investigate any
      validator that is no longer exercised.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Follow `repair-iteratively-to-green` in
      `references/verification-and-repair.md`. At each iteration, read the
      complete first causal traceback, classify it against the migration
      inventory, make the smallest semantic fix, compile the touched files,
      rerun the reproducer, and then rerun collection or the relevant focused
      group. Do not restart broad exploration, write progress summaries, or end
      the task while failures remain.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Follow `audit-automated-edits` in
      `references/verification-and-repair.md` after iterative repairs and after
      every automated transformation. Inspect the complete diff and search for
      duplicated decorator arguments, lost indentation, removed imports still
      referenced, lowercase JSON booleans in Python, altered function
      signatures, empty bodies, unexpected file creation, and broad unrelated
      replacements. Recompile after the audit.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then follow
      `run-static-migration-audit` in
      `references/verification-and-repair.md`. Search the entire production tree
      for pydantic.v1 compatibility imports and all inventoried v1 APIs,
      including BaseSettings from pydantic, validator, root_validator,
      allow_reuse, v1 Config classes, removed constraint keywords, __fields__,
      field_info.extra, and deprecated serialization calls. Distinguish
      comments from executable usage, but resolve every executable occurrence
      before the full suite.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Follow `run-full-suite` in `references/verification-and-repair.md` only
      after the static audit passes. Run the exact repository full-suite command
      directly and untruncated. If logging is necessary, redirect output and
      preserve the test process's exit status; do not use `| head`, `| tail`, or
      an unchecked `tee`. Record pass, fail, error, skip, warning, and duration
      counts. Any nonzero exit returns to iterative repair.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Follow `verify-behavior-preservation` in
      `references/verification-and-repair.md` after a green full-suite run.
      Recheck representative validation failures, settings behavior, parsing,
      model dumping, X12 rendering, metadata-driven components, repeatable
      segments, and dynamic registries. Confirm no function was emptied,
      bypassed, replaced with a no-op, or made unreachable merely to obtain a
      green import or suite.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then follow
      `final-diff-and-status-gate` in
      `references/verification-and-repair.md`. Inspect git status and the full
      diff, remove temporary plans and repair scripts unless intentionally part
      of the deliverable, rerun production compilation and the static audit,
      and verify the final full-suite result belongs to the current diff. Reject
      the result if it contains pydantic.v1 imports, empty or no-op function
      bodies, accidental test edits, malformed automated rewrites, or
      unexplained unrelated changes.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Follow `report-completion` in
      `references/verification-and-repair.md`. Report only verified facts:
      dependency and API migrations performed, behavior-sensitive adaptations,
      exact compile, collection, focused-test, static-audit, and full-suite
      commands with true results, and any remaining warnings or risks. Do not
      claim success from imports, collection, partial tests, truncated output,
      or work that ended before the full suite passed.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, `pydantic.v1.*`, or another Pydantic v1 compatibility namespace to make the migration pass.
  - Never delete, empty, bypass, replace with `pass`, or otherwise turn a function or validator body into a no-op merely to make code import or tests pass.
  - Never perform blind repository-wide decorator replacement; validator mode, signature, input type, and return type must be migrated from semantics.
  - Never treat `@root_validator` as textually equivalent to `@model_validator`; before validators return raw data, while after validators normally receive and return the model instance.
  - Never stop after an import succeeds, collection succeeds, one focused test passes, or a subset reports green.
  - Never pipe authoritative test commands through `head`, `tail`, `grep`, or unchecked `tee` and then report the pipeline's display-command status as the test status.
  - Never use lowercase JSON literals such as `true` or `false` in Python source.
  - Never fix only the first non-annotated inherited field override; scan every model subclass for the same Pydantic v2 construction error.
  - Never remove or rename a public helper required by tests without preserving its contract and all internal call sites.
  - Never assume a failed grep command is a task failure or a successful grep command proves migration completeness; interpret search results explicitly.
  - Never create temporary migration plans or one-off rewrite scripts and leave them in the final diff without a documented repository purpose.
  - Never declare completion while production compilation, complete collection, the static native-v2 audit, the untruncated full suite, or final behavior verification remains unrun or failing.
```