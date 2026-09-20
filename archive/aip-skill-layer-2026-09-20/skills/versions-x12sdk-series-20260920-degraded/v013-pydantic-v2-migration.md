---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 13
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from complete tracebacks and
  executable checkpoints rather than speculative bulk rewrites. Never satisfy
  the migration by importing from pydantic.v1 or another v1 compatibility
  namespace, and never make code import by deleting, emptying, bypassing, or
  replacing a function body with a no-op. Do not declare completion until
  production code compiles, test collection succeeds, focused behavior tests
  pass, the exact untruncated full-suite command exits successfully, and the
  final diff passes a behavior-preservation audit. Before editing, read
  `references/guardrails-and-provenance.md`; read it again during the static
  audit, behavior verification, and final report.

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

steps:
  - name: establish-the-failure
    description: >
      Enter the repository and run its own exact full test command immediately,
      before editing. Run it directly, without piping through head, tail, grep,
      tee, or another command that can hide pytest's exit status. Preserve the
      complete traceback, summary counts, warnings, command, and real process
      exit code. If collection fails, that is the baseline; do not summarize it
      as zero passing tests without retaining the collection error. Before this
      step through repair-first-collection-blocker, read
      `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, locate the VCS root, list the repository root, and inspect git
      status before constructing paths or editing. Use the verified root
      consistently; do not guess similar paths or repeatedly mistype directory
      names. Distinguish pre-existing user changes and untracked files from
      migration edits, preserve them, and record the starting diff. When
      performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: >
      Inspect pyproject.toml, setup configuration, lockfiles, every requirement
      file, tox or nox configuration, CI workflows, pytest configuration,
      README development instructions, package exports, and any explicit
      post-migration requirements file before editing. List files before trying
      conventional names such as setup.py or requirements.txt. Treat comments
      in target requirement files, tests, and issue-specific fixtures as
      executable migration requirements rather than generic documentation.
      When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set. Record Python, Pydantic,
      pydantic-core, pydantic-settings, pytest, and relevant plugin versions.
      Confirm imports resolve to the checked-out repository rather than another
      installation. Do not infer the environment from dependency metadata
      alone. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces. Include BaseSettings,
      Config subclasses, validator, root_validator, allow_reuse, always, each_item,
      pre, skip_on_failure, __fields__, ModelField, field_info.extra, SHAPE_LIST,
      Field regex and arbitrary extra keywords, constrained types, parse_obj,
      parse_raw, from_orm, dict, json, copy, schema, construct, json_encoders,
      inherited unannotated field overrides, Optional fields without defaults,
      and compatibility namespaces. Capture filenames and counts so the final
      static audit can prove every item was resolved. When performing this step,
      follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`. Record constructor behavior, required
      and optional fields, exception expectations, serialized output, aliases,
      ordering, schemas, environment-variable behavior, and helper signatures.
      Tests may encode new native-v2 helper contracts not present in the v1
      source; missing exported helpers are migration work, not tests to delete.
      When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Build a concrete checklist grouped into dependencies and settings, shared
      model configuration, inherited field overrides, field definitions and
      requiredness, reusable validator infrastructure, field validators, model
      validators, field introspection, public helpers, parsing, serialization,
      schemas, and tests. For every validator, record its mode, fields,
      signature, dependencies on sibling fields, return shape, and behavior.
      Order work from shared infrastructure to leaf models while retaining the
      first traceback as the immediate checkpoint. When performing this step,
      follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: >
      Establish a reversible editing discipline before changing code. Modify
      one semantic unit at a time, inspect its diff, compile or import it, and
      run the smallest relevant test. Preserve original validator bodies for
      side-by-side comparison. Do not create broad regex scripts that rewrite
      decorators, signatures, and bodies simultaneously. If an automated edit
      corrupts syntax or semantics, revert only that edit and redo it manually
      rather than layering more substitutions over damaged code.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a
      speculative repository-wide rewrite. Fix only enough of the shared
      dependency, import, syntax, model-definition, or validator issue to move
      collection forward. Re-run the exact failing import or collection target
      immediately and retain the next complete traceback. A NameError for an
      old decorator means the decorator call sites remain; do not merely remove
      its import. A SyntaxError means stop all semantic migration work and
      restore valid syntax first. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models exist. Import BaseSettings from
      pydantic_settings, use SettingsConfigDict or model_config for settings
      behavior, and preserve environment prefixes, case sensitivity, env-file
      handling, defaults, validation, and public settings imports. Convert
      removed Field regex arguments to pattern. Verify a real settings instance
      and environment override before continuing. Before this step through
      migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Preserve extra handling, population by
      field name, assignment validation, arbitrary types, enum behavior,
      attribute-based validation, whitespace handling, frozen or hashable
      behavior, aliases, and serialization. Replace allow_mutation=False with
      frozen=True where equivalent. Do not blindly copy removed or renamed
      keys. Import and instantiate each shared model after the change. When
      performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Inspect subclasses that override fields declared by a Pydantic base
      model. Pydantic v2 requires an annotation for an overridden model field;
      convert declarations such as `segment_name = value` to an explicitly
      annotated field while preserving the expected type and default. Search
      all model subclasses, not only the class named in the first traceback,
      and validate imports after each module. Do not annotate unrelated class
      constants as fields. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version. Replace regex with pattern and move
      custom schema metadata such as `is_component` into
      `json_schema_extra={"is_component": True}` using valid Python booleans.
      Preserve min/max lengths, numeric bounds, decimal constraints, aliases,
      defaults, factories, and schema output. Audit Optional annotations:
      `Optional[T]` without `= None` is required in v2, so add a default only
      when v1 behavior, fixtures, or domain rules prove omission was allowed.
      Verify representative valid and invalid values. When performing this
      step, follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites. Import field_validator directly from pydantic and do not
      shadow that name with a partial, wrapper, or local compatibility helper.
      Remove allow_reuse because v2 does not accept it. Preserve reusable
      validator function bodies, accepted signatures, classmethod behavior,
      validation mode, and each call site's target fields. Confirm reused date,
      time, and identifier validators execute on both valid and invalid values
      before changing leaf models. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body. Use field_validator with mode="before" only for validators that
      truly require raw input. Translate `values`, `field`, and `config`
      parameters to supported v2 signatures, normally using ValidationInfo and
      `info.data`; remember that `info.data` contains only fields already
      validated in declaration order. Preserve multi-field decorators,
      always-like default validation behavior, coercion, return values, and
      exception semantics. Test each converted validator directly. Do not
      leave `@validator` call sites after deleting the import. When performing
      this step, follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
      A pre root validator maps to model_validator(mode="before"), receives raw
      input that may not be a dict, and returns the input mapping or object. A
      post root validator normally maps to model_validator(mode="after"),
      receives `self`, reads attributes rather than `values.get`, and returns
      `self`. Preserve all cross-field checks, mutations, error messages,
      skip-on-failure intent, and return paths. Do not mechanically rename the
      decorator while leaving a v1 `(cls, values)` body unchanged. Compile,
      import, and test after every converted class. When performing this step,
      follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection. Read metadata from FieldInfo.json_schema_extra rather than
      field_info.extra. Replace shape constants such as SHAPE_LIST with
      get_origin and get_args logic that handles Annotated, Optional or Union,
      list, and inherited annotations. Preserve model-field declaration order
      used by X12 parsing and serialization. Avoid deprecated instance access
      to model_fields. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data. It must distinguish repeatable List fields from scalar, Optional,
      Union, and nested model fields in the forms used by the repository.
      Reuse it in repeatable-segment wrapping where appropriate. Run the
      helper's direct tests and loop-initializer tests before continuing. When
      performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: >
      Replace v1 model entry points with native equivalents where actually
      used: model_validate, model_validate_json, model_dump, model_dump_json,
      model_copy, model_json_schema, and model_construct. Preserve include,
      exclude, exclude_unset, exclude_none, aliases, enum and decimal handling,
      custom encoders, separators, newlines, and exact domain output. Update
      parser access from __fields__ to model_fields without changing segment
      order or component metadata. Do not rename APIs solely to silence
      deprecations unless behavior is checked with fixtures. When performing
      this step, follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: >
      Run compileall or py_compile across every production Python file before
      attempting broad imports. Resolve every SyntaxError, malformed import,
      duplicate insertion, invalid boolean literal, indentation error, and
      truncated decorator before proceeding. If a batch edit caused the
      failure, inspect every touched line and revert the batch rather than
      patching only the first reported syntax error.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: >
      Import settings, shared models, support utilities, parsers, both
      major-version segment modules, representative loops, and representative
      transaction modules. Then run pytest collection directly and untruncated.
      Repair NameError, PydanticUserError, schema-generation errors, and missing
      public imports one traceback at a time until collection exits zero.
      Importing one or two base modules is not evidence that the suite
      collects. Before this step through report-completion, read
      `references/validation-and-completion.md`.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant file or node after each changed subsystem:
      settings, support utilities, base models, parser, 4010 segments, 5010
      segments, loop initializers, transaction models, and serialization.
      Execute commands directly so failures are not converted to exit zero by
      output-truncation pipelines. Record real pass, fail, error, skip, xfail,
      and warning counts. Passing one focused file does not authorize stopping.
      When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases,
      validation order, or exception locations, compare the v1 intent expressed
      by tests, fixtures, documentation, original code, and git history with v2
      behavior instead of weakening tests. Determine whether the failure comes
      from Optional requiredness, validator order, raw versus parsed input,
      enum conversion, decimal constraints, assignment validation, or changed
      serialization. Make the narrowest behavior-preserving correction and add
      or retain a focused regression test. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Repeat the shortest failing import, collection target, or focused test
      until it passes, then expand scope one layer at a time. After each repair,
      compile the changed file, inspect its diff, rerun the local target, and
      periodically rerun collection. Never end the task because imports work,
      because collection works, because a subset passes, because tool time is
      running low, or because a migration summary can be written. Continue
      until the full-suite gate is reached. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement. Check decorators,
      imports, signatures, indentation, return statements, validator bodies,
      class boundaries, metadata dictionaries, and end-of-module registries.
      Remove migration scratch scripts and planning files unless they are
      intentional deliverables. Confirm no unrelated user change was reverted.
      When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: >
      Search production code again for pydantic.v1 and equivalent compatibility
      imports, BaseSettings imported from pydantic, v1 validator and
      root_validator decorators, allow_reuse, __fields__, ModelField,
      field_info.extra, SHAPE_LIST, removed Field regex and arbitrary extras,
      unannotated inherited field overrides, and obsolete parsing or
      serialization entry points. Treat grep exit one for no matches as a
      successful negative result, not a tool failure. Reconcile every initial
      inventory item with native replacement, justified retention, or a
      documented non-production occurrence. Re-read
      `references/guardrails-and-provenance.md` and follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active. Do not use `head`,
      `tail`, or a pipeline whose final process masks pytest's status. If the
      suite fails, capture the complete first actionable traceback and return
      to the iterative repair loop; do not report task completion. Repeat until
      the command itself exits zero. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer against its original implementation. Confirm no function
      body was deleted, emptied, replaced with pass, reduced to an unconditional
      return, guarded so it never runs, or otherwise bypassed merely to import.
      Confirm errors still occur for representative invalid data and valid X12
      output still matches fixtures. Re-read
      `references/guardrails-and-provenance.md` and follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status, review the complete final diff once more, compile
      production files again, and verify dependency metadata agrees with the
      runtime used for the green suite. Ensure no accidental planning document,
      repair script, cache, malformed file, compatibility import, or unrelated
      edit remains. If this gate changes code, rerun the relevant focused tests
      and the full suite. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact compilation, collection,
      focused-test, and full-suite commands, true process exit statuses, and
      final pass, fail, error, skip, xfail, and warning counts. Mention any
      justified remaining deprecated surface. Do not claim success if the full
      suite was truncated, masked by a pipeline, not run, or nonzero. Follow
      `references/validation-and-completion.md` and re-read
      `references/guardrails-and-provenance.md`.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Re-pointing imports to pydantic.v1 or another Pydantic v1 compatibility namespace; this is explicitly rejected even when tests pass.
  - Emptying, deleting, bypassing, or replacing a validator or function body with pass, an unconditional return, or another no-op merely so the module imports; this is explicitly rejected even when tests pass.
  - Replacing decorators repository-wide before understanding validator modes, signatures, field order, return values, and bodies.
  - Mechanically converting root_validator to model_validator while leaving a v1 `(cls, values)` post-validator body unchanged.
  - Removing validator or root_validator imports while old decorator call sites still exist, causing collection-time NameError failures.
  - Using broad sed or regex edits on large model modules without immediately compiling, importing, testing, and reviewing every changed hunk.
  - Layering more automated substitutions onto a syntactically corrupted file instead of reverting the bad edit and retrying narrowly.
  - Treating Optional annotations as optional input without checking whether an explicit `= None` default is required.
  - Moving arbitrary Field metadata without preserving it in json_schema_extra and updating all metadata readers.
  - Accessing model_fields through instances or preserving v1 ModelField and shape-constant assumptions.
  - Dropping private-looking helpers that tests or downstream modules import directly, including `_is_list_field`.
  - Weakening tests, validation rules, or domain constraints merely to accommodate changed v2 behavior.
  - Declaring success after a smoke import, collection, or a focused subset while the complete suite has not exited zero.
  - Piping pytest through head, tail, grep, or another command and mistaking the pipeline's zero exit status for a passing suite.
  - Reading only the first lines of a traceback and guessing at a migration-wide fix without preserving the complete error.
  - Repeatedly guessing repository paths, conventional filenames, or dependency state instead of verifying them once.
  - Writing a migration summary or ending the turn while known collection errors, syntax errors, failing tests, or unaudited edits remain.
  - Leaving generated migration plans, one-off repair scripts, caches, or other scratch artifacts in the final change without an explicit repository need.
```