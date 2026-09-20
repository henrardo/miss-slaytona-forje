---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, inherited fields, optional defaults, constraints, metadata, parsing, serialization, introspection, collection, public helpers, registries, malformed partial migrations, and iterative test-driven repair. Use when upgrading Pydantic or fixing import, syntax, schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 64
---

```yaml
purpose: >
  Perform a native, behavior-preserving Pydantic v1 to v2 migration by
  preserving original validator and serialization semantics, repairing one
  verified failure class at a time, and refusing shortcuts that merely make
  imports succeed. Before starting and throughout the migration, read and
  enforce `references/core-rules.md`. Do not route production code through
  `pydantic.v1`, empty or bypass function bodies, weaken tests, or declare
  success before the untruncated full suite exits zero.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A suite fails with Pydantic import, syntax, schema, validator, settings, parsing, serialization, collection, or model-construction errors after a Pydantic v2 upgrade
  - A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
  - Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1
  - A partial migration has left mixed v1 and v2 decorators, imports, signatures, metadata, malformed source, missing helpers, damaged generated registries, decorators whose names are not imported, or syntactically valid but semantically empty functions
  - Prior migration attempts achieved only partial collection or a small passing subset and then stopped
  - Automated replacements introduced malformed decorators, broken imports, invalid Python booleans, damaged regular expressions, indentation errors, duplicated decorator arguments, or accidental edits outside Pydantic syntax
  - Test commands were piped through head, tail, tee, or grep and therefore appeared successful despite pytest failing
  - A migration repeatedly cycles between import errors because broad search-and-replace changed decorators without adapting signatures and function bodies
  - Pydantic reports that post root validators require skip_on_failure or that model_validator rejects the pre argument
  - Tests import a public compatibility helper such as _is_list_field that disappeared during migration
  - Collection fails because a v1 post root_validator remains, or because a partial conversion produced model_validator(pre=True)
  - A repository contains hundreds of similar models where unsafe global replacements can silently damage unrelated Python syntax

do_not_use_when:
  - The codebase is already on native Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The user explicitly requires continued Pydantic v1 compatibility rather than a native v2 migration
  - The repository only consumes external Pydantic models and contains no migration work
  - The requested solution is to route production imports through pydantic.v1 instead of completing a native v2 migration

steps:
  - name: establish-the-failure
    description: >
      Read `references/repository-assessment.md` section
      `establish-the-failure` and follow it. Run the repository's real test
      command without a success-masking pipeline. If output must be captured,
      redirect it to a file, save the test process exit code, and inspect the
      file separately. Record the complete first traceback, collection count,
      pass count, failure count, warning summary, Python version, Pydantic
      version, and exact command. Do not treat a pipeline's zero status as a
      passing test run.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Read `references/repository-assessment.md` section
      `confirm-location-and-working-tree` and follow it. Confirm the repository
      root before every scripted edit. Inspect `git status --short` and the
      existing diff. Preserve user changes, distinguish pre-existing edits
      from migration edits, and do not run checkout, restore, reset, or another
      destructive command over work you did not create.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Read `references/repository-assessment.md` section
      `inspect-repository-contract` and follow it. Inspect dependency files,
      build metadata, lock files, CI commands, test configuration, package
      exports, CLI entry points, supported Python versions, requirements-v2 or
      equivalent migration notes, and repository documentation. Use the
      repository's actual contract rather than assuming setup.py,
      requirements.txt, or a particular environment manager exists.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Read `references/repository-assessment.md` section
      `make-runtime-match-target` and follow it. Ensure the interpreter that
      runs tests imports native Pydantic v2 and required companion packages
      such as pydantic-settings. Verify versions in that same interpreter.
      Avoid reinstall loops and do not let an editable install silently
      downgrade Pydantic because project metadata still pins v1.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Read `references/repository-assessment.md` section
      `inventory-v1-surface` and follow it. Search production code, tests,
      package exports, and generated registration code for every relevant v1
      surface: BaseSettings, Config, validator, root_validator, allow_reuse,
      pre, always, each_item, values/config/field signature parameters,
      __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, constrained
      types, Optional fields without defaults, parse_obj, parse_raw, from_orm,
      dict, json, copy, schema, construct, and reused validator assignment.
      Record file, line, owner model, migration category, and whether the use is
      public or internal. A grep exit code of one may mean no matches; it is not
      automatically a command failure.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Read `references/repository-assessment.md` section
      `inventory-public-and-test-contracts` and follow it. Record public model
      classes, settings classes, helpers, package exports, CLI behavior,
      parser and serializer methods, model construction conventions, aliases,
      error behavior, and helpers imported directly by tests. Explicitly
      include compatibility helpers such as `_is_list_field`; a helper absent
      from production code but imported by tests or users is still a contract.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: preserve-original-semantics
    description: >
      Read `references/repository-assessment.md` section
      `preserve-original-semantics` and follow it. Before converting each
      validator or helper, recover and save its original body from the clean
      source, git object, or pre-migration diff. Record validation phase,
      accepted input shape, field-order dependency, mutation behavior, return
      value, exception type and message, serialization effect, and tests.
      Never infer a validator's semantics only from its name or decorator.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: semantic-snapshots, type: object}

  - name: build-migration-ledger
    description: >
      Read `references/repository-assessment.md` section
      `build-migration-ledger` and follow it. Create a durable ledger with one
      row per dependency change, settings class, model configuration,
      inherited field override, field definition, validator, introspection
      site, serializer, parser, registry, and public helper. Track original
      semantics, intended v2 form, affected tests, current status, and
      verification evidence. Update this ledger after every checkpoint so
      work is not repeatedly rediscovered.
    inputs:
      - {name: semantic-snapshots, type: object}
    outputs:
      - {name: migration-ledger, type: object}

  - name: classify-migration-work
    description: >
      Read `references/repository-assessment.md` section
      `classify-migration-work` and follow it. Separate mechanical changes from
      semantic changes. Mechanical candidates include imports, method renames,
      and isolated metadata access. Semantic work includes every validator,
      inherited field behavior, requiredness, coercion, ordering, error
      behavior, serialization, and parser assumptions. Do not authorize a
      repository-wide replacement for semantic work.
    inputs:
      - {name: migration-ledger, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Read `references/verification-and-repair.md` section
      `create-small-edit-checkpoints` and follow it. Partition work into small,
      reversible checkpoints with an explicit validation command after each.
      Prefer one module or one migration category at a time. Save a diff before
      any repeated edit and compile immediately afterward. Do not accumulate
      dozens of unverified decorator conversions.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: recover-malformed-partial-migration
    description: >
      Before new migration edits, read
      `references/verification-and-repair.md` section
      `recover-malformed-partial-migration` and follow it. Compile production
      code and inspect the current diff for malformed decorators such as
      `@model_validator(mode="before")pre=True)`, duplicated mode arguments,
      missing parentheses, decorators at column zero, damaged imports,
      lowercase Python booleans, altered regular expressions, accidental
      replacement inside unrelated calls, and inserted or removed docstring
      delimiters. Restore the smallest damaged region from original source and
      reapply a reviewed edit; do not stack more regex replacements on corrupt
      code.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: syntax-recovery-checkpoint, type: object}

  - name: repair-first-collection-blocker
    description: >
      Read `references/migration-implementation.md` section
      `repair-first-collection-blocker` and follow it. Fix only the first
      complete import or collection traceback, then rerun compilation,
      targeted import, and collection. Repeat until collection advances.
      Import success is an intermediate gate, not proof of correct behavior.
      Never comment out decorators, validators, or assignments merely to reach
      the next error.
    inputs:
      - {name: syntax-recovery-checkpoint, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Read `references/migration-implementation.md` section
      `update-dependencies-and-settings` and follow it. Update project metadata
      to native `pydantic>=2,<3` and add a compatible pydantic-settings
      dependency where BaseSettings is used. Import BaseSettings and
      SettingsConfigDict from pydantic_settings. Convert settings Config
      options deliberately, preserve environment variable behavior and case
      sensitivity, and change Field(regex=...) to Field(pattern=...) without
      changing the regular expression. Test settings imports, defaults,
      validation, and environment overrides immediately.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Read `references/migration-implementation.md` section
      `migrate-shared-model-configuration` and follow it. Convert inner Config
      classes to ConfigDict or an equivalent native v2 model_config while
      preserving use_enum_values, extra handling, frozen or mutability
      behavior, aliases, assignment validation, arbitrary types, ORM
      behavior, and serialization configuration. Apply shared configuration to
      the intended base class only; do not introduce configuration that makes
      inherited field overrides disappear or changes every Optional field.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Read `references/migration-implementation.md` section
      `migrate-inherited-field-overrides` and follow it. Pydantic v2 requires
      annotations when a subclass overrides an inherited field. Locate
      unannotated assignments such as `segment_name = ...`, preserve their
      original type, and annotate them rather than deleting them or loosening
      protected namespace rules globally. Test representative base and
      subclass construction plus registry lookup after each group of fixes.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-definitions` and follow it. Convert removed Field and
      constrained-type arguments individually: regex to pattern, min_items and
      max_items to their v2 equivalents where required, and arbitrary Field
      metadata to json_schema_extra with valid Python values such as True, not
      JSON `true`. Preserve exact regex grouping and anchors. Audit Optional
      fields carefully because `Optional[T]` without `= None` remains required
      in v2; add a default only when the original public behavior or tests show
      omission was allowed. Never apply a global Optional rewrite.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Read `references/migration-implementation.md` section
      `migrate-reusable-validator-infrastructure` and follow it. Remove
      allow_reuse rather than passing it to v2 decorators. Replace v1 partial
      aliases only after tracing every assignment-style use such as
      `_validate_x = validator("x")(function)`. Keep the public helper name if
      modules import it, but ensure it wraps native field_validator correctly.
      Do not shadow the imported decorator with a recursive partial or move a
      public helper without preserving its import path.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-field-validators` and follow it. Convert each validator
      individually to field_validator, preserving before or after timing,
      multi-field application, default validation, and reuse. Translate
      `(cls, value, values)` or parameters named field/config to a valid v2
      signature using ValidationInfo and `info.data` only when the original
      logic depended on already-validated fields. Respect field order: if a
      rule needs later fields or the entire model, move the rule to a model
      validator instead of pretending info.data is complete. Run the relevant
      positive and negative tests after every logical group.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: classify-every-model-validator
    description: >
      Read `references/migration-implementation.md` section
      `classify-every-model-validator` and follow it. For every root_validator,
      classify whether it requires raw input dictionaries, fully validated
      model instances, assignment-time dual input, or is merely an
      assignment-style wrapper around a reusable dict function. Record whether
      it mutates input, returns a mapping, returns self, counts nested models,
      or depends on invalid fields being skipped. Do this before changing the
      decorator; never convert every root validator to the same mode.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-classification, type: object}

  - name: migrate-model-validators
    description: >
      Read `references/migration-implementation.md` section
      `migrate-model-validators` and follow it. Convert pre root validators to
      `@model_validator(mode="before")` with a classmethod that receives and
      returns raw input. Convert post root validators to
      `@model_validator(mode="after")` with an instance method that reads
      attributes and returns self. Adapt reusable dict validators through a
      small explicit wrapper when necessary. Do not use
      `model_validator(pre=True)`, do not carry skip_on_failure or allow_reuse
      into v2, and do not leave a v1-style `(cls, values)` body under an after
      validator. Preserve original errors, mutation, counting, and validation
      timing.
    inputs:
      - {name: model-validator-classification, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: close-validator-import-decorator-gap
    description: >
      Read `references/migration-implementation.md` section
      `close-validator-import-decorator-gap` and follow it. Search the entire
      production tree, not only top-level segment modules, for validator,
      root_validator, field_validator, and model_validator imports, decorators,
      and assignment-style calls. Ensure every used decorator is imported and
      every removed name is absent. Compile and import every affected module.
      Pay particular attention to loops.py, transaction_set.py, specialized
      segments.py, shared validators.py, and both version families.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: validator-consistency-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Read `references/migration-implementation.md` section
      `repair-field-introspection` and follow it. Replace __fields__ with
      model_fields at class-level introspection sites. Replace ModelField and
      field_info.extra assumptions with FieldInfo.annotation,
      json_schema_extra, metadata, and typing.get_origin/get_args as
      appropriate. Treat json_schema_extra as possibly None. Preserve field
      order, exclusions such as delimiters, nested-model detection, component
      separators, defaults, aliases, and registration keys. Do not assume
      FieldInfo has v1 attributes such as name, type_, shape, or field_info.
    inputs:
      - {name: validator-consistency-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      Read `references/migration-implementation.md` section
      `preserve-list-field-helper` and follow it. Preserve or reintroduce the
      public `_is_list_field` helper at the import path required by tests and
      users. Implement it against FieldInfo or annotations with
      typing.get_origin and handle direct list annotations plus unions such as
      Optional[List[T]]. Use the same helper in repeatable-segment wrapping so
      tests and production follow one definition. Test the helper against
      list, optional-list, scalar, and optional-scalar fields.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Read `references/migration-implementation.md` section
      `migrate-parsing-and-serialization` and follow it. Replace dict, json,
      parse_obj, parse_raw, from_orm, copy, schema, and construct only where
      the native v2 replacement preserves behavior. Use model_dump,
      model_dump_json, model_validate, model_validate_json, model_copy,
      model_json_schema, and model_construct as appropriate. Preserve include,
      exclude, by_alias, exclude_unset, exclude_none, enum, Decimal, date,
      delimiter, recursion, and output-mode behavior. Update parser
      introspection and segment construction together, then verify round trips
      and exact X12 output rather than merely checking imports.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: verify-generated-registries
    description: >
      Read `references/migration-implementation.md` section
      `verify-generated-registries` and follow it. Inspect module-level
      registries that iterate over model classes and derive keys from field
      defaults. Replace __fields__ access carefully with model_fields and
      verify the default still has the expected enum or string form. Compare
      registry size, keys, mapped classes, and representative parser lookups
      with the semantic snapshot. Do not delete registry construction just to
      make an import pass.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: registry-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Read `references/verification-and-repair.md` section
      `compile-production-code` and follow it. Run compileall or py_compile
      over all production modules after each automated edit. If compilation
      fails, stop semantic migration and repair the first syntax error from
      original source. Compilation must detect indentation errors, malformed
      decorators, damaged imports, invalid booleans, and broken expressions
      before pytest is used as the parser.
    inputs:
      - {name: registry-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Read `references/verification-and-repair.md` section
      `run-import-and-collection-gate` and follow it. Import the shared models,
      settings, support, parser, both base segment modules, representative
      loops and transaction sets, and public helpers. Then run untruncated
      pytest collection and retain its true exit code. Do not move on while
      collection reports errors, and do not interpret `--collect-only` exit
      code five for a test file with no tests as a migration success.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Read `references/verification-and-repair.md` section
      `run-focused-behavior-tests` and follow it. Run the smallest tests for
      the changed behavior: settings, shared models, support utilities,
      segment validators for both versions, repeatable loop initialization,
      parsing, serialization, registries, and representative transaction
      models. Capture full failures in files when output is large. A passing
      import or a subset of roughly fifty tests is not a completion signal.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      Read `references/verification-and-repair.md` section
      `compare-validation-semantics` and follow it. For each migrated validator
      and model family, exercise valid data, missing data, wrong types,
      conditional requirements, duplicates, cross-field dependencies,
      Optional omission, and serialization. Compare acceptance, rejection,
      normalized values, exception types, error locations, and useful message
      content with the original semantic snapshot. Investigate behavior
      changes even when tests do not yet cover them.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Read `references/verification-and-repair.md` section
      `repair-iteratively-to-green` and follow it. Work from the first complete
      current traceback, classify it as syntax, import, schema construction,
      validation semantics, parser, serializer, registry, or test-contract
      failure, make the smallest relevant edit, and rerun compilation,
      targeted import, collection, and focused tests. Update the ledger after
      each loop. Do not end the turn while tests still fail unless an external
      blocker prevents further work, and never replace execution with a
      progress summary.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Read `references/verification-and-repair.md` section
      `audit-automated-edits` and follow it. Review every scripted or bulk edit
      in the diff. Check decorator syntax and indentation, import blocks,
      Python True and False, regex text, Optional defaults, all touched
      function bodies, unrelated calls containing words such as regex or
      validator, and accidental files outside the intended set. Revert and
      redo any bulk edit whose correctness cannot be demonstrated
      mechanically.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `run-static-migration-audit` and follow it. Search production code for
      pydantic.v1, BaseSettings imported from pydantic, validator,
      root_validator, allow_reuse, model_validator(pre=...), invalid v2
      signatures, __fields__, ModelField, field_info.extra, SHAPE_LIST,
      Field(regex=...), constrained-type regex arguments, deprecated model
      methods, malformed decorators, lowercase JSON booleans, commented-out
      validation assignments, pass-only bodies, and tests modified to hide
      failures. Resolve every hit or document why it is not production
      migration debt.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Read `references/verification-and-repair.md` section `run-full-suite` and
      follow it. Run the repository's complete authoritative suite without
      head, tail, grep, or an unchecked tee pipeline. Capture output separately
      if necessary and preserve the pytest process status. Record total
      collected, passed, skipped, failed, errors, warnings, duration, and exact
      command. Continue repairing until the command itself exits zero.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      Read `references/verification-and-repair.md` section
      `verify-behavior-preservation` and follow it. Confirm public imports,
      settings behavior, model construction, validator timing, errors,
      Optional omission, enum and Decimal handling, repeatable segment
      wrapping, parsing, X12 serialization, CLI output, support utilities, and
      generated registries. Compare representative outputs and counts with the
      preserved snapshots. Native v2 behavior must be correct, not merely
      warning-free.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Re-read `references/prohibited-patterns.md`, then read
      `references/verification-and-repair.md` section
      `final-diff-and-status-gate` and follow it. Inspect git status and the
      complete diff. Ensure only intended files changed, no scratch migration
      plans or generated repair scripts were added unintentionally, dependency
      metadata matches the tested runtime, public helpers remain available,
      and no validator or function body was emptied, replaced with pass,
      commented out, or made to return unvalidated input solely to satisfy
      imports. Re-run compilation, static audit, collection, and the full suite
      after the final edit.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Read `references/verification-and-repair.md` section
      `report-completion` and follow it. Report dependency changes, major
      migration categories, behavior-preservation evidence, authoritative test
      command and true exit status, counts, remaining warnings, and any
      external blockers. Do not claim completion from import probes,
      compilation, collection, a focused subset, a piped command, or an
      interrupted run.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Before making any edit and again before declaring completion, read and enforce every anti-pattern in `references/prohibited-patterns.md`.
  - Never re-point production imports to `pydantic.v1`; that postpones the migration and is rejected even if tests pass.
  - Never empty, delete, comment out, bypass, or replace a function or validator body with pass, a constant return, raw-input return, or unconditional self return merely to make imports or tests pass.
  - Never convert every root_validator mechanically to the same model_validator mode; classify raw-input and instance-level semantics first.
  - Never leave a v1-style `(cls, values)` function under `@model_validator(mode="after")`.
  - Never use `@model_validator(pre=True)`, append `pre=True` after a converted decorator, duplicate mode arguments, or carry allow_reuse and skip_on_failure into native v2 decorators.
  - Never globally replace decorator names without adapting imports, signatures, bodies, assignment-style validators, and all nested modules.
  - Never run unchecked repository-wide sed or regular-expression edits across Python source; scope, preview, compile, and inspect every automated edit.
  - Never stack another broad replacement on malformed source; restore the damaged region and reapply a reviewed change.
  - Never change all Optional annotations to default None; requiredness is public behavior and must be migrated field by field.
  - Never remove inherited field assignments such as segment_name to silence Pydantic; preserve them with explicit annotations.
  - Never weaken model_config, protected namespaces, extra handling, or validation solely to suppress a schema error without proving semantic equivalence.
  - Never replace a constrained type with an unconstrained primitive merely to fix a removed keyword; preserve every constraint and exact regex.
  - Never translate Python metadata to `json_schema_extra` using JSON literals such as `true` or `false`.
  - Never assume `info.data` contains later fields; respect field order or use the appropriate model validator.
  - Never assume FieldInfo exposes v1 ModelField attributes such as name, type_, shape, or field_info.
  - Never remove or relocate a public helper such as `_is_list_field` because production code appears not to use it; inspect tests and exports first.
  - Never delete generated registry construction, parser discovery, or segment maps merely to make module import succeed.
  - Never treat compile success, an import probe, collection success, or a focused subset as a substitute for the full suite.
  - Never pipe pytest through head, tail, grep, or unchecked tee and then trust the pipeline exit code.
  - Never end an implementation turn with a migration summary while known test failures or collection errors remain repairable.
  - Never reinstall dependencies repeatedly without checking whether project metadata or editable installation is downgrading the tested runtime.
  - Never assume missing setup.py or requirements.txt is an error when pyproject.toml or another repository contract is authoritative.
  - Never overwrite pre-existing user changes with git checkout, restore, reset, or bulk regeneration.
  - Never modify tests to accept weakened validation, remove assertions, skip failures, or conceal migration regressions.
  - Never add scratch plans, repair scripts, summaries, or generated files to the repository unless they are required deliverables.
```