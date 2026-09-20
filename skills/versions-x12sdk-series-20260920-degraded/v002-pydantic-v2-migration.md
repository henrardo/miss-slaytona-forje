---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing collection, schema, validation, parsing, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 2
---

```yaml
# Completeness check against every distinct item in the current skill:
# Mapped: the frontmatter name remains pydantic-v2-migration.
# Mapped: the description still covers behavior-preserving native Pydantic v2
# migration and now names collection and pydantic-settings explicitly.
# Mapped: metadata.aip.spec and metadata.aip.schemaId are unchanged.
# Mapped: metadata.aip.version was advanced from 1 to the required value 2.
# Deliberate drop: metadata.aip.derived_from_traces was removed from frontmatter
# because AIP metadata extension values must not be a YAML list. Trace 92889e36
# remains acknowledged here, alongside the new evidence from trace b8a5567a.
# Mapped: the purpose retains native-v2, behavior-preservation, repository
# evidence, complete-suite, no-pydantic.v1, and no-emptied-function requirements.
# Mapped: all four trigger_when entries survive in substance.
# Mapped: all four do_not_use_when entries survive in substance.
# Mapped: every prior anti-pattern survives below.
# Mapped: establish-the-failure survives and now prohibits pipelines that hide
# pytest's exit status, a failure observed in trace b8a5567a.
# Mapped: inspect-repository-contract and make-runtime-match-target survive.
# Mapped: inventory-v1-surface and classify-migration-work survive, with explicit
# coverage for validator factories, test-imported helpers, and partial edits.
# Mapped: update-dependencies-and-settings survives.
# Mapped: migrate-shared-model-configuration survives.
# Mapped: migrate-field-definitions survives.
# Mapped: migrate-field-validators survives and now requires removing
# allow_reuse from factories, partials, decorators, and call sites.
# Mapped: migrate-model-validators survives.
# Mapped: repair-field-introspection survives and now includes preserving public
# helpers such as _is_list_field when tests or callers import them.
# Mapped: migrate-parsing-and-serialization survives.
# Mapped: run-import-and-collection-gate survives and is strengthened into
# repeated collection gates after migration batches.
# Mapped: run-focused-behavior-tests and compare-validation-semantics survive.
# Mapped: audit-automated-edits and run-static-migration-audit survive.
# Mapped: run-full-suite, verify-behavior-preservation, and report-completion survive.
# Mapped: every prior output and dependency edge remains represented.
# Mapped from trace b8a5567a: never pipe pytest through head or tail without
# preserving PIPESTATUS; the apparent exit code 0 concealed collection failure.
# Mapped from trace b8a5567a: successful imports and 57 passing tests were not
# completion because collection errors remained.
# Mapped from trace b8a5567a: allow_reuse remained reachable through shared
# field_validator wrappers even after some direct decorators were migrated.
# Mapped from trace b8a5567a: tests imported _is_list_field, so deleting or
# failing to recreate a compatibility-neutral public helper broke collection.
# Mapped from trace b8a5567a: unannotated inherited field overrides, regex=,
# removed imports, and constrained-field schema errors can block module import.
# Mapped from trace b8a5567a: repeated path typos and speculative web research
# consumed time that should have gone to the first complete local traceback.
# Deliberate drop: no migration behavior from the current skill was removed;
# duplicated wording was retained where it serves a separate execution gate.

purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas, public
  helpers, and domain behavior. Work from the repository's dependency contract,
  tests, fixtures, git diff, and complete tracebacks. Repair in short,
  measurable loops until collection succeeds and the repository's exact full
  test suite passes. Do not claim success from imports, static searches, warning
  reduction, or a partial suite. Never redirect imports to pydantic.v1 or an
  equivalent v1 compatibility shim. Never empty, bypass, or replace a function
  or validator body with unconditional success merely so it imports or tests
  turn green.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, schema, validator, settings, parsing, serialization, or model-construction errors after a Pydantic v2 upgrade
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
    unconditional success, or equivalent no-op so the function still imports.
    A green suite does not justify deleting behavior.
  - Declaring the migration complete without running the repository's exact full test suite.
  - Piping pytest through head, tail, grep, or tee and reporting the pipeline's zero status instead of pytest's real status.
  - Spending most of the attempt browsing files or migration documentation before executing a baseline test.
  - Assuming setup.py or requirements.txt exists instead of inspecting the files actually present.
  - Repeating web research for an error whose complete local traceback and installed API signature already identify the problem.
  - Blindly replacing decorators across large files with sed or regex without adapting signatures, modes, data access, ordering, and return values.
  - Converting every root_validator to model_validator(mode="after") while leaving a v1-style cls, values body.
  - Renaming validator imports while leaving allow_reuse in a wrapper, functools.partial, decorator factory, or call site.
  - Decorating a reusable validator twice without determining whether it should be a plain function, a class assignment, or a check_fields=False mixin validator.
  - Treating successful imports as proof that model construction, invalid-input rejection, and serialization remain correct.
  - Treating a nonzero number of passing tests as progress sufficient to stop while collection errors prevent the rest of the suite from running.
  - Updating only central models while leaving transaction-specific modules, reusable validators, parser introspection, settings code, or test-imported helpers on v1 assumptions.
  - Deleting a public helper because its old implementation used a removed Pydantic API instead of reimplementing its behavior with native Python typing.
  - Ignoring failed shell commands because grep returned 1 for no matches; distinguish expected no-match status from syntax, path, and command failures.
  - Relying on deprecation warnings as a migration strategy when the task requires native v2 APIs.
  - Changing requiredness, coercion, aliases, output formatting, error behavior, or validation order without checking tests and fixtures.
  - Globally adding None defaults to Optional fields without evidence that omission was previously allowed.
  - Running broad automated edits without reviewing the diff and testing immediately afterward.
  - Making repeated edits after an import failure without rerunning the exact import to expose the next concrete blocker.
  - Ending with a summary of intended changes before collection and the full suite have passed.

steps:
  - name: establish-the-failure
    description: >
      Enter the verified repository root and immediately run the repository's
      own full test command. Discover it from pyproject.toml, tox.ini, noxfile,
      Makefile, CI, or project documentation; default to
      `python -m pytest -q` only if no project-specific command exists. Run it
      directly, without `| head`, `| tail`, or another pipeline. If output must
      be captured, redirect it to a file and separately preserve the test
      process's status; with a shell pipeline, inspect PIPESTATUS rather than
      the last command's status. Record the exact command, Python and Pydantic
      versions, collection count, pass/fail/error/skip counts, actual exit
      status, and first complete traceback. A collection error is the baseline,
      even if dozens of tests passed before collection stopped.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Confirm the current directory with pwd and list the repository root before
      constructing paths. Use repository-relative paths thereafter to avoid
      errors such as agent-w0, agent-worm-0, or guessed filenames. Run git
      status and inspect the existing diff. The working tree may contain a
      partially completed earlier migration, so distinguish original user
      changes from migration edits. Do not reset, overwrite, or revert unrelated
      work. Record which files are already modified and whether the baseline
      reflects an in-progress migration.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect dependency and test configuration before editing. Read
      pyproject.toml and the requirements, lock, setup.cfg, tox, nox, CI, and
      migration-specific files that actually exist. Determine the intended
      Pydantic v2 range, Python range, test extras, and companion packages such
      as pydantic-settings. If the repository provides a post-migration
      requirements file, treat it as strong evidence and compare it with package
      metadata instead of guessing versions. Note generated-code conventions
      and package exports that constrain changes.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the target dependency set. Verify the interpreter path and
      versions of pydantic, pydantic-core, pydantic-settings, and relevant test
      tools with direct Python commands. Confirm the test command invokes that
      interpreter. Do not edit against an unknown environment or infer the
      project's dependency state from a globally installed Pydantic alone.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search all production Python files, package exports, executed examples,
      tests, and dependency metadata for v1 interfaces. Include BaseSettings,
      validator, root_validator, allow_reuse, Config subclasses, __fields__,
      ModelField, field_info.extra, SHAPE_ constants, regex=, schema_extra,
      orm_mode, allow_population_by_field_name, validate_all,
      validate_assignment, parse_obj, parse_raw, from_orm, dict(), json(),
      copy(), schema(), construct(), json_encoders, custom root models,
      GenericModel, constrained factories, and Optional annotations without
      defaults. Search for aliases and wrappers too: partial(field_validator,
      ...), locally re-exported validator names, decorator factories, assigned
      reusable validators, and multi-line imports. Locate every BaseModel
      subclass and every custom validator in version-specific and transaction
      directories. Save file and line locations; do not limit the search to
      import statements.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests and package exports for names imported directly from modules,
      including private-looking helpers. Record helpers such as list-field
      detectors, model base classes, validator functions, and constants that
      tests or downstream code expect to import. Read representative valid and
      invalid fixtures and exact serialized-output assertions. These contracts
      must survive even when their v1 implementation used removed internals;
      reimplement them with v2 FieldInfo and standard typing rather than
      deleting them.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Group findings into dependencies/settings, model configuration, fields
      and requiredness, field validators, model validators, reusable validator
      infrastructure, field introspection, public helpers, parsing,
      serialization, schemas, and tests. Prioritize shared base classes and
      validator factories because they affect many generated or
      transaction-specific models. Mark high-risk behavior: validator ordering,
      sibling-field access, default validation, list/repeating-field detection,
      custom metadata, aliases, string coercion, dates, decimal constraints,
      unannotated inherited field overrides, and exact X12 or other domain
      serialization. Divide the work into small batches, each followed by an
      import or collection gate.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback, not with a repository-
      wide speculative rewrite. Inspect the failing line, its imports, any
      wrapper it calls, and the installed API signature. Make the smallest
      native-v2 correction and rerun the exact failed import or collection
      command immediately. Continue one blocker at a time until the first
      affected module imports. If `field_validator` reports an unexpected
      allow_reuse argument, search all direct decorators, assigned validators,
      wrapper aliases, and functools.partial definitions before editing; remove
      the argument at its actual source rather than patching one visible class.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models are present. Import BaseSettings
      from pydantic_settings and replace settings Config classes with
      SettingsConfigDict or the installed version's supported native form.
      Preserve environment prefixes, case sensitivity, env-file behavior,
      aliases, defaults, and ignored types. Replace Field(regex=...) with
      Field(pattern=...). Run settings imports and the smallest settings tests
      immediately, then run collection to expose the next blocker.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Translate semantics rather than spelling:
      orm_mode becomes from_attributes; allow_population_by_field_name becomes
      populate_by_name or the installed version's validation-by-name setting;
      schema_extra becomes json_schema_extra; validate_all or default behavior
      may require validate_default. Preserve assignment validation, extra
      handling, arbitrary types, string normalization, frozen or mutability
      behavior, aliases, enum values, JSON behavior, and any v1 numeric-to-string
      coercion that fixtures prove is contractual. Handle protected namespace
      conflicts deliberately. Annotate class constants with ClassVar when they
      are not fields, and annotate inherited field overrides such as
      `segment_name: X12SegmentName = ...` because v2 rejects unannotated field
      overrides. Import shared models and rerun collection after this batch.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native to
      the installed Pydantic v2 version. Preserve every string length, numeric,
      decimal, collection, pattern, alias, and discriminator constraint. If a
      constrained factory or Field constraint causes schema-generation failure,
      replace only that annotation with an equivalent supported Annotated or
      Field form and test valid and invalid boundaries. Move custom Field
      metadata into json_schema_extra and later read it from
      FieldInfo.json_schema_extra. Audit requiredness explicitly:
      `Optional[T]` without a default remains required in v2; add `= None` only
      where fixtures or prior behavior establish that omission is allowed.
      Review mutable defaults and default factories. Import both major model
      families and rerun collection after the batch.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator helpers before converting every call site. Remove
      allow_reuse everywhere because v2 does not accept it: direct decorators,
      wrapper functions, functools.partial declarations, aliases, and assigned
      validators. Choose one valid reuse pattern intentionally. Prefer a plain
      validation function assigned in each model through field_validator, or a
      mixin validator with check_fields=False when inheritance requires it.
      Avoid applying field_validator to an object that is already decorated.
      Preserve each function body, return value, error message, and domain
      check. Import modules that consume the reusable validators and rerun
      collection before proceeding.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading its body. Map pre=True to
      mode="before"; use mode="after" for post-parsing checks. Remove
      allow_reuse rather than forwarding it. Replace v1 values, config, and
      field parameters with ValidationInfo where needed; read previously
      validated sibling data from info.data. Respect declaration order because
      info.data contains only fields already validated. Preserve always=True
      semantics with validate_default or an appropriate model-level design
      instead of assuming a decorator rename is equivalent. Update signatures
      such as `(cls, value, values)` to `(cls, value, info)` only when the body
      is correspondingly changed from values access to info.data. Keep all
      return statements and validation logic. Test representative models from
      each version-specific module and rerun collection.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time. For mode="before", accept
      and return the raw mapping or object and preserve wrapping,
      normalization, and cross-field preprocessing. For mode="after", normally
      accept the constructed model instance, inspect attributes, and return the
      instance. Do not leave a mode="after" validator with a v1-style
      `cls, values` dictionary contract or call `.get` on the model instance.
      If assignment validation can pass an instance, handle it intentionally.
      Preserve error messages when tests or callers depend on them. Validators
      for paired fields, conditional requirements, totals, hierarchy, or domain
      invariants must continue to enforce those rules. Never replace a body
      with a no-op. Run focused valid and invalid cases and collection after
      each related group.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level. Adapt code
      that expected v1 ModelField attributes because v2 entries are FieldInfo
      objects and do not expose v1 shape or field_info.extra APIs. Detect list
      or repeatable annotations with typing.get_origin and get_args over
      resolved annotations, recursively unwrapping Optional, Union, and
      Annotated forms rather than importing removed SHAPE_LIST constants. Read
      custom flags from FieldInfo.json_schema_extra. Update parser field-name
      enumeration, repeatable-segment wrapping, and shared serialization
      together so they agree on ordering and metadata.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      name and implement it using standard typing plus v2 FieldInfo data. Verify
      it returns true for direct lists and supported wrapped list annotations,
      false for scalars, and behaves correctly for the repository's actual
      model_fields entries. Use the helper consistently in pre-validation that
      wraps a single repeatable item into a list. Run the helper's direct tests
      and loop-initializer tests; a central model import is not sufficient.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where used:
      model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Do not mechanically
      replace dict calls that operate on ordinary Python dictionaries. Preserve
      aliases, exclude_none, exclude_unset, context, ordering, serializers, and
      exact domain output. Replace json_encoders with a native v2 mechanism only
      after checking how the repository invokes serialization. For custom X12
      or text serializers, compare complete strings or bytes against fixtures,
      including delimiters and line endings.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile production files, then import settings, shared models, parsers,
      both major version segment modules, and representative transaction
      modules. Run test collection without truncating output or masking status.
      Fix the first complete traceback and repeat until collection succeeds.
      Typical blockers include removed imports, allow_reuse hidden in a wrapper,
      invalid validator signatures, missing public helpers, unannotated field
      overrides, obsolete Field arguments, duplicate validators, and
      schema-generation failures. Record the collected test count. Successful
      central-model imports alone do not satisfy this gate.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant file or node for each changed subsystem:
      settings, base models, parser, 4010 segments, 5010 segments, loop
      initializers, transaction models, and serialization. Run commands
      directly or preserve their true exit status. For each failure, read the
      complete traceback and inspect the affected model, validator helper, and
      base classes before editing. Make the smallest behavior-preserving fix,
      rerun the exact failing test, then rerun its subsystem. Do not accumulate
      many speculative changes between tests.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, or missing fields, compare v1
      intent with v2 behavior instead of weakening tests. Check required versus
      nullable fields, union selection, number-to-string coercion, strictness,
      enum values, date and decimal handling, constrained boundaries, validation
      of defaults, validator order, and error locations. Add explicit native-v2
      configuration or validators only when repository fixtures demonstrate the
      old behavior is contractual. Exercise at least one valid and one invalid
      case for each changed high-risk validator.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially files touched by batch
      replacement. Inspect every changed decorator together with its function
      signature and body. Search for malformed decorator combinations,
      leftover imports, validators still named but no longer registered,
      mode="after" functions treating models as dictionaries, duplicate
      decoration, accidentally removed annotations, and bodies reduced to pass,
      a bare return, or unconditional success. Compare against the pre-edit
      version when a body changed. Revert unrelated formatting churn because it
      hides semantic errors.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for forbidden and stale migration surfaces.
      There must be no pydantic.v1 import, indirect v1 compatibility import, or
      deliberate shim routing native code to v1. Resolve remaining validator,
      root_validator, allow_reuse, BaseSettings-from-pydantic, __fields__,
      ModelField, field_info.extra, SHAPE_ constant, regex=, and obsolete Config
      uses unless a reviewed occurrence is demonstrably unrelated or supported
      v2 syntax. Search comments separately so comments do not conceal live
      matches. Treat grep exit 1 as no matches only when stderr is empty and the
      searched paths are valid.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly and
      without output truncation. Record its actual exit status, collection
      count, duration, and complete pass, fail, error, skip, and warning counts.
      Passing 57 tests is not completion if collection errors prevent other
      modules from loading. If anything fails, return to the smallest relevant
      repair loop, rerun the exact failing test and subsystem, rerun collection
      when imports changed, and then rerun the full suite. Continue until the
      suite passes or an external blocker is proven by reproducible command
      output.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted logic. Confirm no function was emptied,
      replaced with unconditional success, or bypassed. Confirm public helpers
      expected by tests remain importable. Exercise representative valid and
      invalid inputs for high-risk models, including cross-field checks,
      repeatable-list wrapping, defaults, date and decimal validation, and exact
      serialization. Confirm dependency metadata installs native Pydantic v2
      and that the successful test command used that environment.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the final diff once more. Ensure all changes are
      necessary for the migration, no user changes were lost, no debugging
      artifacts or captured test-output files remain, and dependency files are
      internally consistent. Re-run the static audit if this review causes any
      edit. Re-run the full suite after every final source or dependency change;
      an earlier green result does not validate later edits.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions used, exact collection and full-suite commands, true
      exit status, and final pass, fail, error, skip, and warning counts. Mention
      any remaining warnings or reproducible external blockers. State
      explicitly that no pydantic.v1 or equivalent compatibility shim was
      introduced and no validator or other function body was emptied or
      bypassed. If collection or the full suite is not green, describe the
      remaining blocker and do not call the migration complete.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}
```