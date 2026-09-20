---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 72
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration and continue
  until the repository's real, complete, untruncated test command exits zero.
  Preserve public APIs, validator bodies, validation timing, field requiredness,
  parser behavior, serializer behavior, settings behavior, helper functions,
  generated registries, and error behavior. Before editing and throughout the
  migration, read and enforce `references/core-rules.md`. Work from complete
  tracebacks and small verified edits rather than speculative bulk replacement.
  Never claim completion from successful imports, compilation, collection, a
  focused subset, a custom smoke script, a zero exit status produced by piping
  test output through `head` or `tail`, or a textual summary that says tests
  passed without the repository's real command actually exiting zero.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration contains mixed v1 and v2 decorators, missing imports, malformed decorators, damaged imports, changed function signatures, empty validator bodies, or broad search-and-replace damage
  - The first collection failure says that BaseSettings moved to pydantic-settings
  - Tests exercise repeatable list fields, inherited discriminator fields, generated segment registries, X12 serialization, or other behavior coupled to Pydantic field introspection
  - When deciding whether a partial or failed migration matches this procedure, read `references/core-rules.md` section `additional-triggers`.

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
      command without truncating or filtering its output. Capture output to a
      file, save the command's actual exit status, and inspect the file
      afterward; do not use `pytest ... | head`, `pytest ... | tail`, or a
      pipeline whose final command hides pytest's status. Record the complete
      first traceback, collection count, pass count, fail count, warning count,
      runtime versions, and exact command. If collection stops at BaseSettings,
      record that as the first blocker rather than spending the attempt on
      unrelated repository exploration.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      root once and reuse that exact path; avoid recurring near-miss paths such
      as `agent-worm`, `agent-wam`, or `agent-wrap`. Record tracked,
      untracked, staged, and pre-existing changes before editing. Never discard
      user work. Do not run `git checkout` or `git restore` on an entire source
      tree to recover one damaged file.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: set-execution-discipline
    description: >
      When beginning migration execution, read `references/core-rules.md`
      section `execution-discipline` and follow it. Maintain a short live
      ledger of the current blocker, intended edit, verification command, and
      result. Make one coherent edit at a time, immediately run syntax or import
      verification, and then rerun the smallest test that exposes the blocker.
      Continue using tools until the required gate passes; do not end a turn
      after announcing the next edit, emitting pseudo-tool syntax, writing a
      migration summary, or saying the task is complete without verification.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: execution-discipline, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect pyproject metadata,
      lock or requirement files, CI commands, supported Python versions, test
      configuration, package entry points, and any repository-provided
      post-migration requirements file. Prefer the repository's declared
      contract over assumptions. Do not repeatedly probe files such as
      setup.py or requirements.txt after the repository has shown they do not
      exist.
    inputs:
      - {name: execution-discipline, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Verify the interpreter used by
      the test command imports native Pydantic 2 and, when settings models
      exist, pydantic-settings. Reconcile dependency metadata and runtime
      deliberately. Do not blindly run editable installs, forced reinstalls,
      or broad pip upgrades that can downgrade Pydantic, disturb unrelated
      packages, or change the environment without explaining the need. Recheck
      versions after any installation.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      package metadata, and code generation paths for BaseSettings, class
      Config, validator, root_validator, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, regex, constr(regex=), min_items,
      max_items, parse_obj, parse_raw, from_orm, dict, json, copy, schema,
      arbitrary Field metadata, inherited field overrides, optional fields
      without defaults, dynamic registries, and reusable validator assignment.
      Distinguish executable code from documentation. Record every occurrence
      by file and semantic category instead of treating textual replacement as
      the migration plan.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Include imported
      underscored helpers when tests or downstream code rely on them, such as a
      public-in-practice `_is_list_field` helper. Record model constructors,
      exported classes, settings accessors, parser entry points, serializer
      output, CLI output, validation exceptions, field metadata, and generated
      registries. Treat tests for repeatable segment initialization and
      inherited discriminator fields as migration contracts, not incidental
      implementation details.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before changing each
      validator or helper, retrieve and retain its complete original body and
      signature from the clean working tree, current diff, or `git show
      HEAD:path`. Record whether it receives raw dictionaries or model
      instances, which fields it reads, whether field order matters, what it
      returns, and what errors it raises. Never infer a validator body from its
      name and never replace real validation logic with `return values`,
      `return self`, `pass`, a comment, or an empty function merely to make an
      import succeed.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create one ledger row per
      dependency, settings model, shared base model, field constraint,
      validator, introspection site, serializer, parser, helper, registry, and
      test contract. For validators include v1 decorator and mode, original
      signature, accessed fields, expected v2 decorator and signature, and a
      focused verification target. Keep the ledger as working evidence; do not
      add unsolicited migration-plan or summary files to the repository.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Order work by dependency and
      collection blockers first, then shared model configuration and
      introspection, reusable validators, field validators, model validators,
      field definitions, parsing and serialization, registries, focused
      behavior, and finally the full suite. If the repository is partially
      migrated, classify each affected file as clean v1, clean v2, or malformed
      mixed state before editing it.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. A checkpoint is a coherent
      edit followed by an actual syntax, import, collection, or focused-test
      command. Inspect `git diff --check` and the relevant diff after automated
      edits. Never batch-convert dozens of validators before confirming the
      transformation on representative before, after, field, reusable, and
      inherited-field cases.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      code and search for malformed forms such as
      `@model_validator(mode="before")pre=True)`, duplicated decorator calls,
      missing closing parentheses, broken multiline imports, accidental
      lowercase `true`, altered regex literals, indentation damage, decorator
      names without imports, and comments inserted into assignments. Compare
      damaged regions against `git show HEAD:path` and reconstruct them
      deliberately. Restore only a specific file when necessary and preserve
      already-correct edits; never reset the entire package.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Repair only the first
      complete collection traceback, then rerun collection with the real exit
      status. For the common BaseSettings blocker, immediately migrate that
      settings module and its dependency declaration before investigating
      downstream validators. Repeat until collection advances to a new
      traceback. Do not substitute isolated imports for this collection gate.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update the declared
      dependency range to native Pydantic 2 and add a compatible
      pydantic-settings dependency. Import `BaseSettings` and
      `SettingsConfigDict` from `pydantic_settings`, keep `Field` and model
      primitives from `pydantic`, convert settings Config options to
      `model_config`, and change `Field(regex=...)` to
      `Field(pattern=...)`. Preserve environment variable names, aliases,
      defaults, case sensitivity, caching, and public settings accessors. Run
      the settings tests or equivalent behavior checks immediately.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert every
      class-based Config to `ConfigDict` or the appropriate settings config.
      Map `allow_mutation=False` to `frozen=True` and preserve
      `use_enum_values`, `extra`, aliases, assignment validation, arbitrary
      type policy, and serialization behavior. Do not leave class Config in a
      base model because every generated subclass inherits its semantics.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      subclass overrides of inherited model fields to remain annotated. Find
      assignments such as `segment_name = X12SegmentName.CR5` and convert them
      to annotated overrides that preserve the original type and default.
      Audit all subclasses, not only the class named by the first traceback,
      and run imports for both major model families afterward. Do not remove
      discriminator fields to silence the error.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert `regex` to `pattern`,
      `constr(regex=...)` to its correct v2 pattern form or an equivalent
      annotated constraint, `min_items` and `max_items` to the correct v2
      length constraints, and arbitrary Field metadata to
      `json_schema_extra`. Use Python `True`, never JSON `true`, in source.
      Preserve decimal, integer, string, list, literal, enum, and date
      constraints exactly. Audit every `Optional[T]`: in v2 it remains required
      unless its default is explicitly `None`; add defaults only where v1
      behavior or tests prove omission was accepted. Never mass-add
      `default=None` to all Optional annotations.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove v1
      `allow_reuse` wrappers without deleting the reusable validation
      functions. Avoid rebinding an imported `field_validator` name to a
      partial of itself. Preserve assignment-style declarations such as
      `_validate_date = field_validator(...)(validate_date_field)` and ensure
      the shared function has a v2-compatible signature. Verify every module
      that imports the shared helper, because a helper named
      `field_validator` may be part of the repository's public contract.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Replace `@validator` with
      `@field_validator`, explicitly choose `mode="before"` or the default
      after mode from original behavior, and use `ValidationInfo` when the
      original validator read sibling values. Replace v1 `values.get(...)`
      access with `info.data.get(...)` only after confirming field ordering
      still makes those values available. Preserve multi-field decorators,
      `check_fields`, invocation timing, return values, and errors. Add
      `@classmethod` where the v2 form requires it. Validate representative
      positive, negative, and omitted-input cases after each family.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. Classify each original
      root validator independently as before or after based on its decorator,
      input type, body, and timing. Record whether it receives raw mappings,
      accesses already-built nested models, mutates values, or validates the
      completed model. Do not infer mode from a global replacement rule and do
      not convert every root validator to before or every one to after.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert a v1
      `root_validator(pre=True)` to `model_validator(mode="before")` operating
      on and returning raw input data. Convert a v1 post root validator to
      `model_validator(mode="after")` operating on and returning `self`, then
      translate dictionary access to attributes without changing logic.
      Account for assignment validation if enabled. Remove unsupported
      `allow_reuse`, `pre`, and `skip_on_failure` arguments only by expressing
      their intended behavior in the v2 form. Preserve complete bodies and
      exact errors; never make imports pass by emptying a function body.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search every
      production module for decorator use and ensure each decorator is
      imported from native Pydantic 2 in that module. Search separately for
      residual v1 imports, residual v1 decorators, malformed mixed decorators,
      unsupported decorator arguments, and aliases that shadow
      `field_validator` or `model_validator`. Compile and import all model
      families after closing the gap.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace `__fields__` with
      class-level `model_fields` and translate ModelField-era attributes using
      the actual v2 `FieldInfo` annotation, default, metadata, and
      `json_schema_extra`. Preserve component-field detection, list detection,
      field ordering, nested-model detection, and generated segment lookup.
      Guard optional metadata dictionaries before calling `.get`. Do not use
      deprecated instance-level model_fields access.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or reintroduce the
      repository's `_is_list_field` helper in the module from which tests and
      consumers import it. Implement list detection with `typing.get_origin`
      while correctly unwrapping supported unions or optional annotations.
      Use that same helper in repeatable-segment normalization so public helper
      behavior and model behavior cannot diverge. Verify direct helper tests
      and construction from both a bare dictionary and a list.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace model `dict`,
      `json`, `parse_obj`, `parse_raw`, `copy`, and schema APIs with their v2
      equivalents where production code calls them. Preserve exclusion flags,
      aliases, enum rendering, Decimal and date handling, delimiters, nested
      model traversal, newline behavior, CLI JSON output, and X12 output.
      Avoid replacing ordinary Python dictionary operations. Update shared
      recursive helpers to accept both mappings and BaseModel instances where
      the original validation phase could provide either.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Audit import-time registries
      that iterate over model classes and read field defaults. Use
      `model_fields["field"].default` or the correct v2 equivalent, preserve
      enum-to-key normalization, and ensure abstract or unrelated classes are
      excluded as before. Import both version families and assert known segment
      names resolve to the expected classes.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile
      over the entire production package with an unmasked exit status. Repair
      every syntax and indentation error before testing behavior. Compilation
      is only a gate and never evidence that the migration is complete.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import core settings,
      shared models, parser modules, both model-version families, transaction
      modules, and public helpers. Then run the repository's complete
      collection command without output truncation and capture its actual exit
      status. Fix the first complete traceback and repeat until collection
      succeeds. A successful isolated import does not replace successful
      collection.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run focused tests for
      settings, shared models, each segment family, repeatable list
      initialization, parser behavior, support helpers, serialization,
      registries, CLI output, and transaction-level validators. Use full
      output and real exit statuses. A focused subset is a diagnostic gate, not
      the completion gate.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. Compare valid construction,
      invalid construction, omitted Optional fields, extra fields, nested
      models, reusable validators, validator ordering, inherited
      discriminators, exception types, and important error locations against
      the saved v1 semantics and tests. Investigate unusually large cascades of
      required-field errors as likely optional-default regressions rather than
      patching fixtures blindly.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. For each failure, capture the
      complete traceback, identify the earliest production frame, inspect the
      original function body and current diff, make the smallest semantic edit,
      rerun the focused failing test, and periodically rerun collection and the
      full suite. Do not continue broad editing after the first newly
      introduced syntax or import failure.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every automated edit in the
      diff for damaged imports, duplicate decorators, wrong modes, empty
      bodies, changed regexes, misplaced defaults, lowercase booleans, comments
      inserted into code, accidental documentation changes, and unrelated
      artifacts. Run `git diff --check`, compilation, and focused tests after
      cleanup. Delete unrequested migration scripts, plans, and summaries from
      the repository.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search executable production
      code for pydantic.v1, BaseSettings imported from pydantic, class Config,
      validator, root_validator, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, unsupported regex or item constraints,
      deprecated serialization calls, malformed decorators, and empty
      validator bodies. Classify every remaining match rather than assuming a
      grep exit code alone proves correctness.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's exact complete test command in the target
      Pydantic 2 runtime, without `head`, `tail`, grep filtering, ignored
      failures, `|| true`, or a timeout that is mistaken for success. Capture
      the direct exit status and final totals. Continue repairing until the
      command exits zero; zero tests, collection-only success, and a partial
      pass count are failures of this gate.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm settings behavior,
      constructors, optionality, validation failures, parser and serializer
      output, public helpers, generated registries, CLI behavior, and
      transaction invariants. Ensure no production import points to
      `pydantic.v1` and no validator or helper body was emptied or bypassed.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect the complete diff,
      diff statistics, untracked files, dependency metadata, and final static
      audit. Verify only intended migration files changed, no source file was
      broadly reverted, no temporary script or summary was added, the full
      suite result belongs to the current working tree, and the recorded exit
      status is zero.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report the dependency and code changes,
      exact full-suite command, direct exit status, pass totals, focused
      semantic checks, and any remaining warnings. If any gate is incomplete,
      report the current blocker instead of claiming success. Do not say all
      tests pass based on imports, a custom smoke program, collection, or a
      truncated command.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never redirect production imports to `pydantic.v1`; the target is a native Pydantic v2 implementation.
  - Never empty, stub, bypass, comment out, or replace a validator or helper body merely so the module imports.
  - Never convert every root validator to the same model-validator mode; classify each validator from its original semantics.
  - Never use broad unreviewed sed or regex replacement across the package for decorators, imports, Optional defaults, regexes, or function signatures.
  - Never remove a decorator, field, discriminator, validation constraint, public helper, or test to make the suite green.
  - Never mass-add `default=None` to every Optional field; determine requiredness from v1 behavior and tests.
  - Never use JSON `true` or `false` in Python source; use `True` and `False`.
  - Never shadow Pydantic's `field_validator` or `model_validator` imports with incompatible partial functions.
  - Never repeatedly edit after introducing a syntax error; compile and repair the damaged checkpoint first.
  - Never run `git checkout` or `git restore` over the whole production package to recover one file.
  - Never install or downgrade dependencies blindly; verify the interpreter and dependency versions used by the real test command.
  - Never treat a command piped through `head`, `tail`, grep, tee without pipe-status handling, or `|| true` as evidence of test success.
  - Never claim completion from compilation, imports, collection, focused tests, custom verification scripts, or a partial pass count.
  - Never stop immediately after announcing an intended edit or emitting tool-call text; perform the edit and run its verification gate.
  - Never add migration plans, generated scripts, summaries, or other repository artifacts unless the user or repository contract requires them.
```