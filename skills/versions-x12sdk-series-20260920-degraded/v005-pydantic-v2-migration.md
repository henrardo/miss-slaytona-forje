---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 5
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from the repository's dependency
  contract, tests, fixtures, git history and diff, installed API signatures,
  and complete tracebacks. Repair in short, measurable loops until collection
  succeeds and the repository's exact full test suite passes. Do not claim
  success from imports, static searches, warning reduction, test collection,
  or a partial suite. Never redirect imports to pydantic.v1 or an equivalent
  v1 compatibility shim; this is rejected even if every test passes. Never
  empty, bypass, stub, or replace a function or validator body with
  unconditional success merely so it imports or tests turn green; this is
  rejected even if every test passes. Before editing, read
  `references/guardrails-and-provenance.md`; read it again when performing the
  static audit, behavior verification, and final report.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work

anti_patterns:
  - >
    Rewriting imports to pydantic.v1, importing through another v1 compatibility
    namespace, or creating a shim that routes native code back to v1. This is
    rejected even if every test passes.
  - >
    Replacing a validator or any other function body with pass, a bare return,
    unconditional success, an immediate return followed by unreachable original
    logic, or any equivalent no-op so the function still imports. A green suite
    does not justify deleting behavior.
  - Declaring the migration complete without running the repository's exact full test suite.
  - Ending the attempt after an import succeeds, collection succeeds, one test file passes, or a partial count of passing tests is observed.
  - Piping pytest through head, tail, grep, or tee and reporting the pipeline's zero status instead of pytest's real status.
  - Treating a command that displays pytest output but masks pytest's nonzero exit status as a successful test run.
  - Blindly replacing decorators across large files with sed or regex without adapting signatures, modes, data access, ordering, and return values.
  - Converting every root validator to mode after without deciding whether it consumes raw input or a constructed model.
  - Changing requiredness, coercion, aliases, output formatting, error behavior, or validation order without checking tests and fixtures.
  - Suppressing migration errors by weakening tests, deleting assertions, broadening field types, or disabling validation.
  - Adding generated migration plans, temporary rewrite scripts, or unrelated files to the final patch without a repository need.
  - Ending with a summary of intended changes before collection and the full suite have passed.

steps:
  - name: establish-the-failure
    description: >
      Enter the verified repository root and immediately run the repository's
      own full test command directly. Before executing this step through
      repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`. Preserve the complete
      stdout, stderr, traceback, test counts, and pytest process exit status.
      Do not truncate output with head or tail. If output capture is necessary,
      use a mechanism that preserves the test process status, such as a direct
      subprocess invocation or a shell with pipefail, and record the pytest
      status rather than the last pipeline process. A collection error and zero
      executed tests are a failed baseline, not a passing run.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Confirm the current directory with pwd and list the repository root before
      constructing paths. Run git status, inspect tracked and untracked files,
      and review the existing diff. Distinguish pre-existing user changes from
      migration edits and do not overwrite or reset them. Reuse the confirmed
      root consistently; do not guess similar paths or silently continue after
      a failed cd or missing-file read.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, requirement files,
      tox/nox configuration, CI workflows, pytest configuration, README
      development instructions, and any post-migration requirements file before
      editing. Determine the authoritative dependency range, supported Python
      versions, extras needed for tests, exact full-suite command, and whether
      pydantic-settings is expected. Do not assume setup.py or requirements.txt
      exists; enumerate the root first and use the files the repository actually
      declares.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the target dependency set. Record Python, Pydantic,
      pydantic-core, pydantic-settings, pytest, and package versions from the
      same interpreter used by the suite. Confirm imports resolve to the working
      tree rather than a stale installed copy. Consult installed signatures or
      official documentation for the exact installed v2 release instead of
      guessing from memory.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search all production Python files, package exports, executed examples,
      tests, and dependency metadata for v1 interfaces. Include BaseSettings,
      class Config, validator, root_validator in both bare and called forms,
      allow_reuse, each_item, always, pre, values and field validator
      parameters, __fields__, ModelField, SHAPE_LIST and other internal shape
      constants, field_info.extra, regex, parse_obj, parse_raw, from_orm, dict,
      json, copy, schema, construct, json_encoders, orm_mode, allow_mutation,
      validate_all, populate_by_name equivalents, arbitrary custom Field
      keywords, and imports from pydantic submodules. Use searches as an
      inventory, not proof of semantic correctness.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, package exports, and downstream-facing modules for names
      imported directly, including private-looking helpers. Record helper names,
      constructor forms, required versus optional fields, aliases, expected
      errors, exact serialized X12 or JSON output, settings behavior, schema
      expectations, and model introspection assumptions. If tests import a
      helper such as `_is_list_field`, its name and behavior are part of the
      repository contract unless evidence says otherwise. Inspect fixtures and
      representative transaction files rather than inferring behavior solely
      from annotations.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Group findings into dependencies/settings, model configuration, fields
      and requiredness, field validators, model validators, reusable validator
      infrastructure, field introspection, public helpers, parsing,
      serialization, schemas, and tests. For every validator, record its old
      decorator arguments, input form, fields read, fields written, exception
      behavior, return value, and whether execution depends on field order.
      Identify duplicated 4010/5010 or transaction-family implementations that
      require equivalent changes, but do not assume superficially similar files
      are identical. Order work by collection blockers and shared foundations,
      then by focused behavioral failures.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback, not a repository-wide
      speculative rewrite. Make the smallest behavior-preserving native-v2
      change that removes that blocker, then rerun the failing import,
      collection command, or focused test and read the next complete traceback.
      Keep each checkpoint runnable. Do not end the attempt after the first
      successful import, and do not hide later errors by truncating test output.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models are present. Before executing this
      step through migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`. Import BaseSettings and
      SettingsConfigDict from pydantic_settings, move supported Config behavior
      to model_config, and preserve environment prefixes, dotenv behavior,
      aliases, case sensitivity, ignored extra values, defaults, and source
      precedence. Replace removed Field(regex=...) with pattern=... where the
      installed API requires it. Validate settings construction and
      environment overrides with focused tests.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Map each option intentionally, including
      extra handling, assignment validation, enum value behavior, arbitrary
      types, string transforms, alias population, frozen models, default
      validation, ORM/from-attributes behavior, and serialization settings.
      Preserve inheritance behavior and avoid duplicating configuration across
      every leaf. Annotate genuine class constants with ClassVar when v2 would
      otherwise interpret them as fields. When overriding an inherited field,
      retain an explicit compatible annotation rather than assigning an
      unannotated replacement.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native to
      the installed Pydantic v2 version. Preserve min/max lengths, numeric
      bounds, decimal constraints, strictness, aliases, descriptions,
      exclusions, defaults, and JSON schema metadata. Move custom metadata such
      as `is_component` into `json_schema_extra` and use valid Python values
      such as True, not JSON-only tokens such as true in Python source. Audit
      Optional carefully: `Optional[T]` without a default remains required in
      v2, so add `= None` only where fixtures and prior behavior prove omission
      was allowed. Do not broadly loosen types to bypass failures. Compile and
      import each edited model family after this change.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator helpers before converting every call site.
      Replace v1 decorator partials and allow_reuse patterns with direct native
      field_validator registration or ordinary validation functions compatible
      with v2. Confirm whether each reusable function receives only a value or
      also needs ValidationInfo. Preserve mode, target fields, exception types,
      and return values. Test one representative registration before applying
      the pattern broadly; importing field_validator from pydantic is valid,
      importing it from an internal or nonexistent pydantic.validators path is
      not.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading its body. Choose
      field_validator mode="before" when validation must see raw input and the
      default after mode when it must see converted values. Replace the v1
      `values` parameter with ValidationInfo and use info.data only for fields
      that have already validated; verify declaration order rather than assuming
      all sibling fields are present. Replace removed `field` and `config`
      parameters through cls.model_fields, info.field_name, and model_config as
      appropriate. Reproduce `always` behavior deliberately with default
      validation where needed. Handle each_item semantics explicitly rather
      than carrying the removed argument forward. Return the validated value on
      every successful path and retain every original condition and error.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      @root_validator declarations that simple replacement patterns miss. Use
      model_validator(mode="before") only for validators whose old pre=True body
      consumes and returns raw input mappings. Account for non-dict inputs if
      supported. Use mode="after" for post-validation invariants; receive the
      constructed instance, access attributes rather than values.get, preserve
      every condition and exception, and return self. Use a wrap validator only
      when the old behavior truly needs control around core validation. Do not
      merely rename the decorator while retaining a v1 signature. After each
      conversion, compare the original body from git diff or history against
      the new body line by line, and run positive and negative examples proving
      the invariant still executes.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level. Translate
      ModelField assumptions to v2 FieldInfo and typing annotations. Read custom
      metadata from json_schema_extra, handling None safely. Replace shape
      constants and private Pydantic internals with typing.get_origin,
      typing.get_args, and documented v2 APIs. Verify inherited fields, aliases,
      list fields, optional unions, annotated fields, nested groups, and
      component fields using focused examples.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      name and implement it using standard typing plus v2 FieldInfo data. It
      must identify direct and appropriately wrapped list annotations without
      relying on removed SHAPE_LIST constants. Exercise it against required
      lists, optional lists, inherited list fields, non-list fields, and any
      Annotated or union forms present in the repository. Use it in repeatable
      segment normalization so a single supplied segment is wrapped exactly
      where prior behavior required, while existing lists and absent values
      remain unchanged.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where used:
      model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Update parser field
      iteration to model_fields and preserve field order, aliases, exclusions,
      enum rendering, date and decimal formatting, delimiters, component
      separators, repeatable segments, newlines, and omission rules. Do not
      mechanically replace every `.dict()` or `.json()` without confirming the
      receiver is a Pydantic model and matching old include, exclude,
      exclude_none, exclude_unset, by_alias, and custom encoding behavior.
      Compare exact output strings and parsed model structures against fixtures.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile production files, then import settings, shared models, parsers,
      both major version segment modules, and representative transaction
      modules. Before executing this step through report-completion, read
      `references/validation-and-completion.md`. Run pytest collection directly
      and require a true zero exit status. Treat warnings about deprecated v1
      APIs, undefined annotations, custom Field keywords, shadowed fields, or
      serializer behavior as migration evidence rather than cosmetic noise.
      Continue repairing until the complete suite collects; collection alone is
      only a gate, never completion.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant file or node for each changed subsystem:
      settings, base models, parser, 4010 segments, 5010 segments, loop
      initializers, transaction models, and serialization. Run both accepting
      and rejecting cases for every changed validator, including omitted
      defaults and cross-field combinations. Preserve complete failure output
      and real process status. After a focused test passes, proceed to the next
      affected subsystem rather than stopping or summarizing early.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, or missing fields, compare v1
      intent with v2 behavior instead of weakening tests. Check Optional
      requiredness, validation of defaults, before-versus-after input types,
      field order and info.data visibility, enum storage, decimal and date
      coercion, union selection, extra-field behavior, aliases, assignment
      validation, nested model reconstruction, and exception location. Use
      fixtures, tests, git history, and small executable examples as the source
      of truth. Modify production behavior only when the evidence establishes
      the intended contract.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially files touched by batch
      replacement. For each changed decorator, compare the old and new
      signature, body, mode, field access, ordering assumptions, error paths,
      and return. Search for malformed imports, duplicate decorators, JSON
      literals inserted into Python, accidental path-specific scripts,
      indentation damage, immediate returns followed by unreachable code,
      validators reduced to returning their input, and removed logic. Revert or
      hand-repair unsafe generated edits before proceeding.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for forbidden and stale migration surfaces.
      Reject any pydantic.v1 or equivalent compatibility import. Find remaining
      BaseSettings-from-pydantic imports, class Config blocks, v1 validator and
      root_validator decorators, allow_reuse, __fields__, ModelField,
      SHAPE_LIST, field_info.extra, removed Field(regex=...) use, unsupported
      custom Field keywords, and deprecated model entry points. Inspect every
      hit in context because comments and intentional external APIs may produce
      false positives. Also detect suspicious pass statements, bare returns,
      unconditional argument returns, and unreachable original validator logic;
      explain legitimate cases and repair deleted behavior.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly and
      without output truncation. Do not append head, tail, grep, or an unchecked
      tee pipeline. Record the command, real process exit status, duration, and
      complete pass, fail, error, skip, xfail, and warning counts. If it fails,
      return to the smallest relevant repair loop, rerun focused tests, rerun
      collection when imports changed, rerun static and diff audits, and then
      run the exact full suite again. Repeat until its actual exit status is
      zero.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted logic. Compare against the pre-edit version
      with git diff or git show. Require each former rejection rule,
      normalization, wrapping rule, metadata lookup, and formatting branch to
      remain executable under native v2. Specifically reject functions whose
      bodies were emptied, validators that now only hand their argument or self
      back despite previously enforcing conditions, and original logic made
      unreachable by an inserted return or raise. Add or run targeted examples
      if the existing suite does not exercise a changed branch.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the final diff once more. Ensure only intended
      repository files changed; remove temporary plans, exploratory scripts,
      caches, and generated artifacts unless the repository explicitly needs
      them. Confirm dependency metadata matches the tested runtime, no user
      changes were overwritten, no compatibility shim was added, all public
      helpers remain available, all changed functions retain meaningful bodies,
      and the recorded green full-suite run occurred after the final code edit.
      If code changes after that run, repeat the necessary audits and full suite.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions used, exact collection and full-suite commands, true
      exit status, and final pass, fail, error, skip, and warning counts. Mention
      focused behavior checks and the static audit for forbidden compatibility
      imports and stubbed or unreachable bodies. Distinguish unresolved failures
      from warnings and do not say complete if collection failed, any tests
      failed, pytest status was masked, the full suite was not run after the
      final edit, pydantic.v1 remains, or any original function logic was
      removed rather than ported.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}
```