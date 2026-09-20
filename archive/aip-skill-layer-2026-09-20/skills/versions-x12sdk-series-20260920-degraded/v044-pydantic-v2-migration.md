---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 44
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
  returns the model instance. Treat assigned reusable validators such as
  `_validate_date = validator(...)(function)` as executable class definitions,
  not disposable formatting. Migrate their shared callable signatures before
  changing their decorators, and never comment out only the right-hand side or
  leave a dangling assignment. Never perform a blind repository-wide
  decorator, signature, import, metadata, constraint, model-method, boolean,
  or field-override substitution. Never use line-number edits against files
  that are changing. Never remove inherited field overrides merely to silence
  Pydantic; add compatible annotations and preserve their defaults. After
  each edited file, compile it, import its affected module, and run the
  smallest relevant test before editing another validator-heavy file. If an
  edit introduces syntax or indentation damage, stop migration work and
  restore that file's syntactic integrity from the diff and original source
  before doing anything else. Repair the first complete traceback before
  broadening scope. Continue repairing until the full suite passes; never stop
  with a progress summary, migration plan, partial import success, collection
  errors, known failing tests, an unexecuted proposed tool call, a
  user-visible fake tool call, or a statement that the remaining work is too
  complex.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, or malformed source

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's exact test
      command without output-truncating pipelines. Record the command, true
      exit status, environment versions, collected/pass/fail counts when
      available, and the first complete traceback including its final
      exception. If collection fails, that failure is the baseline; do not
      describe collection as working.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      path before every command batch. Inspect `git status`, `git diff`, and
      untracked files. Distinguish user work from failed migration edits.
      Preserve user work. If the tree already contains migration edits, use
      the diff and committed version as evidence; do not layer broad rewrites
      over unexplained damage.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: When executing this step, read `references/repository-assessment.md` section `inspect-repository-contract` and follow it.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the active interpreter,
      installed Pydantic version, pydantic-settings availability, and the
      dependency files used by CI. Do not infer the active environment from a
      dependency file alone.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      package metadata, dynamically imported modules, and generated registry
      code. Inventory imports, decorators, validator assignments, Config
      classes, settings, constraints, field extras, introspection, serialization
      methods, list-shape checks, inherited field overrides, and public
      compatibility helpers. Record exact file and symbol locations rather
      than only occurrence counts.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Treat imports made
      directly by tests as public contracts, including underscored helpers
      such as `_is_list_field`. Record model construction, error behavior,
      X12 rendering, settings, parsing, serialization, CLI output, and
      registry lookup expectations.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Capture each validator's
      complete original body and neighboring field order before editing it.
      Use the committed source when the working copy is malformed. Record
      whether the validator receives raw input, validated sibling data, or a
      model instance; what it mutates; which errors it raises; and what it
      returns. A migration is not allowed to erase these behaviors.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per actual
      occurrence, not one row per pattern. Include the v1 construct, intended
      v2 construct, semantic risks, relevant tests, edit status, compile
      status, import status, and focused-test status.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: When executing this step, read `references/repository-assessment.md` section `classify-migration-work` and follow it.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Use a per-file checkpoint:
      edit one coherent construct, compile the file, import the affected
      module, run its smallest relevant test, inspect the diff, and only then
      continue. Never postpone syntax checks until after editing both large
      segment modules.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, inspect changed Python files for syntax and
      structural damage left by earlier attempts. Run compileall and inspect
      every SyntaxError or IndentationError first. Compare damaged regions
      with `git diff` and the committed source. Restore missing decorators,
      assignments, indentation, imports, and function bodies while retaining
      valid user work. In particular, detect commented decorator assignments,
      orphaned expressions such as a bare `parse_x12_date`, decorators at
      column zero inside classes, duplicated decorator calls, JSON literals in
      Python, and imports removed while decorators remain. Compile each
      repaired file immediately. Do not proceed until production code compiles.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Repair only the first
      complete collection blocker, then rerun collection with the true exit
      status. A command piped to `head` that reports the pipeline consumer's
      zero status is not evidence of success.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Move BaseSettings to
      pydantic-settings, migrate settings configuration, and change `regex=`
      to `pattern=` where required. Keep dependency declarations consistent
      with the environment and repository's target files. Validate settings
      import, defaults, environment case handling, and invalid-value behavior.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Translate Config
      behavior deliberately, including frozen/hashable behavior, enum value
      handling, extra-field rejection, assignment validation, and arbitrary
      type settings. Do not merely silence deprecation warnings.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      annotations when subclasses override inherited model fields. Preserve
      declarations such as transaction segment-name defaults by adding the
      compatible annotation; do not delete all subclass overrides or convert
      them to untyped class attributes. Import every affected large segment
      module after this pass.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Migrate removed or renamed
      Field and constrained-type keywords individually. Put custom metadata in
      `json_schema_extra`, using Python booleans. Preserve length, numeric,
      optionality, requiredness, aliases, list cardinality, and schema output.
      Do not blanket-add `= None` to Optional fields without checking the v1
      contract and tests.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      `allow_reuse` rather than wrapping v2 decorators in a partial that still
      passes it. Migrate reusable callable signatures before attaching them.
      Audit assignment-style validators separately from `@decorator` methods.
      Preserve the assignment and callable body; never comment it out to make
      a class import.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator from its
      actual signature. Replace v1 `values` access with ValidationInfo data
      only when semantically equivalent, account for field-order availability,
      and choose before/after mode intentionally. Add classmethod where
      appropriate. Run valid and invalid focused cases for every changed
      validator family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. Before replacement,
      classify every root validator as raw-input normalization, pre-validation
      cross-field checking, post-validation checking, mutation, or reusable
      external callable. Record its target v2 mode and signature. Do not infer
      mode from a search-and-replace pattern.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert before validators to
      accept and return raw data. Convert after validators to accept and return
      the model instance, translating `values.get(...)` to attribute access
      without losing mutations or exceptions. Never leave a v1
      `(cls, values)` body beneath `mode="after"`. Never mechanically replace
      `values.get` with `getattr(self, ...)` across arbitrary bodies.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search all Python
      files for remaining v1 decorators, imports, `allow_reuse`, malformed v2
      decorators, undefined decorator names, and mixed signatures. Include
      nested transaction directories rather than relying on shallow shell
      globs. A grep exit status of one may mean no matches; interpret it
      explicitly rather than calling it a task failure.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace v1 field APIs with
      model_fields, FieldInfo annotations, json_schema_extra, and typing
      introspection while preserving order and field identity. Handle
      `json_schema_extra` being absent. Remove obsolete SHAPE_LIST and
      ModelField assumptions only after replacing their behavior.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. If tests or callers import a
      list-field helper such as `_is_list_field`, retain or implement that
      public symbol using `typing.get_origin`, including Optional/Union forms
      when required. Use the same helper in repeatable-segment normalization
      so the public contract and runtime logic cannot drift. Test scalar,
      list, optional-list, and non-list annotations.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Migrate model_fields,
      model_dump, model_dump_json, model_validate, and related APIs at call
      sites, not by blind textual replacement. Preserve enum representation,
      exclusion flags, aliases, delimiters, Decimal/date handling, recursive
      segment counting, CLI output, and X12 rendering. Keep compatibility
      methods only when they are part of the repository's public contract,
      not as a substitute for native v2 internals.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect import-time loops
      that derive segment registries from model fields. Migrate field-default
      lookup without changing keys, enum conversion, class selection, or
      import order. Assert representative registry entries from every version;
      module import alone is insufficient.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Compile all production Python
      files. Treat every syntax, indentation, and name-resolution problem as a
      stop-the-line failure. Repair the damaged file from its diff and
      semantic snapshot before running tests.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import shared models,
      settings, both versioned segment modules, and representative nested
      transaction modules. Then run untruncated collection and require exit
      zero with a nonzero collected count. Capture output to a file if needed,
      but preserve pytest's status.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run settings, shared model,
      support, versioned segment, repeatable-segment, loop-initializer,
      parsing, serialization, CLI, and registry tests relevant to changed
      code. A missing test node is not a pass; locate the actual test name.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. For each migrated validator
      family, exercise at least one accepted and one rejected case and compare
      normalized values, error locations, required-field behavior, mutations,
      and output with the semantic snapshot and tests.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Repair the first complete
      current traceback, rerun the narrowest reproducer, then rerun the gate
      that exposed it. Do not spend turns repeatedly inventorying already
      known patterns, researching settled API changes, or writing summaries
      while an executable failure remains.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every automated replacement
      in the diff. Reject changes that altered indentation, imports, unrelated
      methods, comments instead of code, decorator arguments, function
      signatures, field defaults, Python booleans, or only part of a
      multiline construct. Do not trust a script merely because it exited
      zero.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search for compatibility
      namespace imports, remaining v1 APIs, allow_reuse, obsolete Config and
      introspection patterns, malformed decorators, JSON booleans in Python,
      commented-out validator assignments, empty/no-op bodies, and generated
      temporary migration files.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite`
      and follow it. Run the exact repository full-suite command without
      truncating or masking its result. Require exit zero and record the real
      collected, passed, skipped, failed, and error counts. If it fails,
      return to iterative repair rather than reporting completion.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Verify settings, accepted
      and rejected model inputs, repeatable segments, nested loops, rendering,
      parsing, serialization, registries, and public imports. Confirm no
      validator or function was emptied, bypassed, commented out, or silently
      dropped.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the entire diff and
      status. Ensure dependency files are correct, no unrelated user files
      were overwritten, no scratch migration scripts or plans remain, no
      pydantic.v1 imports exist, and no substantive body is empty. Re-run
      compile, static audit, and the full suite after any final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report completion only if every prior
      gate is green. Include the exact full-suite command, its true exit
      status and counts, focused checks, key migrated surfaces, and any
      remaining non-failing warnings. If a gate is not green, continue work
      instead of producing a completion or progress summary.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never import from `pydantic.v1`, `pydantic.v1.*`, or another Pydantic v1 compatibility namespace to make the suite pass.
  - Never empty, delete, bypass, comment out, or replace a substantive function or validator body with `pass`, an unconditional return, or another no-op merely to make imports succeed.
  - Never comment out only part of an assignment-style validator and leave its callable expression as an indented bare statement.
  - Never blindly replace every root validator with the same model-validator mode or retain `(cls, values)` beneath an after validator.
  - Never use repository-wide sed or regex substitutions for decorators, signatures, imports, booleans, metadata, constraints, field overrides, or serialization methods without reviewing every changed occurrence.
  - Never use changing line numbers as the target for source edits.
  - Never remove subclass field defaults such as segment identifiers merely because Pydantic requires an annotation.
  - Never use JSON literals `true`, `false`, or `null` in Python source.
  - Never treat a pipeline's final command status as pytest's status; avoid truncating pytest output or explicitly preserve the pytest exit code with pipefail.
  - Never stop after compile success, import success, collection success, one focused test, a warnings-only excerpt, or a prose migration summary.
  - Never emit an unexecuted tool-call placeholder or claim an edit was made when the tool was not actually invoked.
  - Never abandon the repair because the remaining validators are numerous or complex; work one classified validator and one verified checkpoint at a time.
```