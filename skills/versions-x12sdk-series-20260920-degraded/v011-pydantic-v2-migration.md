---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 11
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 APIs while
  preserving validation, parsing, serialization, configuration, schemas,
  public helpers, and domain behavior. Work from complete tracebacks and
  executable checkpoints rather than speculative bulk rewrites. Never satisfy
  the migration by importing from pydantic.v1 or another v1 compatibility
  namespace, and never make code import by deleting, emptying, bypassing, or
  replacing a function body with a no-op. Before editing, read
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
      Enter the verified repository root and run the repository's own exact
      full test command immediately, before editing. Capture the complete
      command, complete first traceback, summary, and true process exit status.
      Do not pipe pytest through head, tail, grep, or another command that can
      hide pytest's exit status; if output must also be saved, use a log file
      and preserve the test process status. Distinguish collection errors from
      executed test failures and do not report a zero-test collection failure
      as a test run. Before this step through repair-first-collection-blocker,
      read `references/baseline-inventory-and-planning.md`.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: >
      Run pwd, identify the VCS root, list the repository root, and inspect git
      status before constructing absolute paths or editing. Record pre-existing
      tracked, untracked, and ignored changes and preserve them. Derive paths
      from the verified root instead of repeatedly typing fragile absolute
      paths. When performing this step, follow
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
      post-migration requirements file before editing. Treat a repository
      requirements-v2 or equivalent measured dependency set as evidence, not
      as a comment to ignore. Do not assume setup.py or requirements.txt exists;
      enumerate the root and use the files actually present. When performing
      this step, follow `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: >
      Install the project through its declared development or test workflow so
      tests use the intended target dependency set. Record Python, Pydantic,
      pydantic-core, pydantic-settings, and pytest versions from the same
      interpreter used for tests. Confirm imports resolve to this checkout and
      not a stale installed copy. Do not edit source merely to accommodate an
      accidental environment mismatch. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: >
      Search every production Python file, package export, executed example,
      test, and dependency declaration for v1 surfaces. Include imports and
      uses of BaseSettings, Config subclasses, validator, root_validator,
      allow_reuse, each_item, pre, always, values, field, config, __fields__,
      ModelField, SHAPE_LIST and other shape constants, field_info.extra,
      arbitrary Field extras, regex, constrained types, parse_obj, parse_raw,
      from_orm, dict, json, copy, schema, construct, json_encoders, and
      pydantic.v1 or equivalent compatibility namespaces. Search for inherited
      field overrides lacking annotations and Optional annotations without
      defaults because both can change behavior in v2. Use repository-wide
      searches whose no-match exit status is interpreted correctly rather than
      treated as a tool failure. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: >
      Search tests, __init__ exports, downstream-facing modules, examples, and
      documentation for names imported directly, including private-looking
      helpers such as `_is_list_field`. Record behavior asserted for required
      fields, defaults, coercion, aliases, error cases, output ordering,
      metadata, schemas, serialization, and repeatable-list wrapping. A helper
      imported by tests or callers remains part of the effective contract even
      if its name begins with an underscore. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: >
      Build a concrete in-memory or scratch checklist grouped into dependencies
      and settings, shared model configuration, inherited field overrides,
      field definitions and requiredness, reusable validator infrastructure,
      field validators, model validators, field introspection, public helpers,
      parsing, serialization, schemas, and tests. Associate each item with a
      focused import or test checkpoint and its original behavior source.
      Prefer a concise checklist over writing an unsolicited migration-plan
      document into the repository. Do not start a repository-wide mechanical
      rewrite before this classification. When performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: repair-first-collection-blocker
    description: >
      Start with the first complete baseline traceback rather than a
      speculative repository-wide rewrite. Make the smallest coherent native-v2
      repair that can expose the next blocker, then rerun the exact failing
      import, collection command, file, or node without truncating output.
      Continue only after recording the new checkpoint. Do not declare success
      after a module import while collection or the suite still fails. When
      performing this step, follow
      `references/baseline-inventory-and-planning.md`.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: >
      Change package metadata to the intended native Pydantic v2 range and add
      pydantic-settings when settings models exist. Import BaseSettings and
      SettingsConfigDict from pydantic_settings, convert settings Config to
      model_config, and preserve environment prefixes, env files, case
      sensitivity, ignored extras, aliases, defaults, and validation. Replace
      removed Field regex with pattern where appropriate. Test the settings
      import and representative construction immediately. Never redirect these
      imports to pydantic.v1. Before this step through
      migrate-parsing-and-serialization, read
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: >
      Convert BaseModel Config subclasses to ConfigDict/model_config on shared
      base classes before leaf models. Preserve frozen or mutability behavior,
      extra handling, enum values, assignment validation, arbitrary types,
      aliases, population by name, string transforms, default validation,
      attribute-based validation, and serializer behavior. Account for the fact
      that assignment validation can cause after model validators to receive an
      instance. Run shared-model imports and construction tests immediately.
      When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: >
      Inspect subclasses that override fields declared by a Pydantic base
      model. Add explicit compatible annotations to overrides such as
      `segment_name: X12SegmentName = X12SegmentName.CR5`; v2 rejects an
      unannotated assignment that shadows a model field. Repair every instance
      revealed by imports rather than special-casing only the first class.
      Preserve the original type and default, then rerun representative major
      version module imports. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: >
      Update removed Field arguments and constrained types using forms native
      to the installed Pydantic v2 version. Replace regex with pattern and move
      custom schema metadata such as is_component into json_schema_extra while
      preserving the key and value consumed by parsers and serializers.
      Preserve min/max constraints and decimal semantics. Explicitly review
      requiredness: in v2, Optional[T] without a default is still required, so
      add `= None` only when v1 behavior, fixtures, or tests establish that the
      field was optional. Do not mass-change requiredness merely to make model
      construction pass. Test representative fields and schemas immediately.
      When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: >
      Repair shared validator functions and registration helpers before their
      many call sites. Import field_validator from pydantic itself, remove
      allow_reuse because v2 does not accept it, and preserve modes, target
      fields, return values, and error behavior. A reusable validator must
      remain an executable function; do not replace it with a decorator object
      or delete its body. Validate one direct function call and one model call
      site before changing all consumers. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: >
      Replace each v1 validator only after reading and preserving its complete
      body. Map pre=True to mode="before"; otherwise use the appropriate
      default or explicit mode. Replace v1 values access with ValidationInfo
      and info.data only when field-order semantics make that valid. Replace
      field or config signature parameters with supported v2 forms. Preserve
      multi-field targets, check_fields behavior, return values, exceptions,
      and validation of defaults; use validate_default or an equivalent model
      configuration only when needed to preserve always=True behavior. Convert
      reusable date and identifier validators without changing their domain
      logic. Run a focused valid and invalid case after each validator family.
      When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: >
      Convert root_validator instances one at a time, including bare
      `@root_validator` declarations that simple replacement patterns miss.
      For mode="before", accept and return the incoming mapping or raw input
      while preserving every mutation and check. For mode="after", normally
      accept self, read attributes rather than mapping keys, and return self.
      Handle assignment-validation instances where configured. Preserve
      skip-on-failure intent and validation order. Do not mechanically rename
      the decorator while leaving an incompatible `(cls, values)` body, and do
      not mechanically rewrite every `values.get` without understanding scope.
      Run a valid and invalid focused case after each conversion. When
      performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: >
      Replace __fields__ access with model_fields at the class level and replace
      v1 ModelField assumptions with v2 FieldInfo plus standard typing
      inspection. Read custom metadata from json_schema_extra, guarding None.
      Use typing.get_origin and get_args and unwrap Annotated or Union forms as
      required instead of relying on removed numeric shape constants. Update
      dynamic segment registries and parsers as well as ordinary model methods.
      Confirm the registry contains the same segment keys and the parser sees
      fields in the same order. When performing this step, follow
      `references/native-v2-api-migration.md`.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: >
      If tests or callers import a helper such as `_is_list_field`, retain that
      exact public name and implement it with standard typing plus v2 FieldInfo
      data. Correctly recognize List[T], list[T], Optional[List[T]],
      Union[List[T], None], and Annotated wrappers as required by the codebase.
      Use the helper in repeatable-segment wrapping rather than duplicating
      inconsistent logic. Run the loop-initializer and repeatable-segment tests,
      including scalar-to-singleton-list and already-list inputs. When
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
      exclude, by_alias, exclude_unset, exclude_defaults, exclude_none, mode,
      custom encoder behavior, enum and Decimal output, delimiters, field order,
      and newline behavior. Do not replace a JSON-producing path with a Python
      dictionary without adapting its callers. Exercise parser-to-model and
      model-to-X12 or JSON round trips immediately. When performing this step,
      follow `references/native-v2-api-migration.md`.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: run-import-and-collection-gate
    description: >
      Compile all production Python files, then import settings, shared models,
      support utilities, parsers, both major-version segment modules, and
      representative transaction modules. Run pytest collection directly and
      require a successful process status and a nonzero expected test count.
      Resolve every import and collection error before broad behavior work.
      Capture full tracebacks; do not use output truncation that masks status.
      Before this step through report-completion, read
      `references/validation-and-completion.md`.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: >
      Run the smallest relevant file or node after each changed subsystem:
      settings, support utilities, base models, parser, 4010 segments, 5010
      segments, loop initializers, transaction models, and serialization.
      Include both accepted and rejected inputs so a validator that silently
      stopped running cannot appear correct. Record true exit status and counts
      for each checkpoint. Do not move to the next subsystem merely because a
      smoke import succeeds. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: >
      For failures involving coercion, defaults, missing fields, aliases, or
      validation order, compare the v1 intent expressed by tests, fixtures,
      documentation, original code, and git history with v2 behavior instead
      of weakening tests. Check Optional requiredness, default validation,
      strict numeric and string behavior, field ordering, model-validator
      timing, assignment validation, and serialized representations. Change
      tests only when the task explicitly changes the contract. When performing
      this step, follow `references/validation-and-completion.md`.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: >
      Repeat the shortest failing import, collection target, or focused test
      until it passes, then expand scope one layer at a time. For every failure,
      read the complete traceback, identify whether it is an environment,
      import, schema-build, validation, parsing, serialization, or assertion
      failure, make one coherent repair, and rerun. If a batch edit creates
      unrelated failures, revert that batch and perform smaller reviewed edits.
      Continue until collection and all focused subsystem tests are green;
      never end the task after describing remaining work.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: >
      Review the complete git diff, especially every file touched by sed,
      regex, generated scripts, or batch replacement. Inspect imports,
      decorators, signatures, indentation, return statements, function bodies,
      annotations, JSON booleans versus Python booleans, and metadata syntax.
      Remove temporary migration scripts and unsolicited planning artifacts.
      Confirm no edit duplicated imports, inserted text into the wrong block,
      or depended on stale line numbers. When performing this step, follow
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
      serialization entry points. Treat pydantic.v1 or any equivalent
      compatibility redirect as a failed migration even if tests pass. When
      performing this step, follow
      `references/validation-and-completion.md`. Re-read
      `references/guardrails-and-provenance.md` and reconcile every inventory
      item with the final source.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: >
      Run the exact full-suite command recorded at baseline, directly,
      untruncated, and with the target environment active. Capture the true
      process exit status and complete summary. A successful shell pipeline, a
      partial file run, successful collection, or an import smoke test is not a
      green full suite. If the suite fails, return to the shortest reproducer,
      repair, rerun affected focused tests, rerun collection when schema code
      changed, and then rerun the full suite. When performing this step, follow
      `references/validation-and-completion.md`.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: >
      After a green full suite, inspect every changed validator, helper, parser,
      and serializer for deleted or bypassed logic. Compare before and after
      function bodies and ensure each still performs its original checks and
      returns the correct object. Explicitly reject empty bodies, pass-only
      bodies, unconditional-success stubs, deleted raises, skipped validator
      registration, or code made importable by removing behavior. Also verify
      invalid-input tests, metadata consumers, dynamic registries, list
      wrapping, and round-trip output. Passing tests do not excuse
      pydantic.v1 imports or emptied function bodies. When performing this step,
      follow `references/validation-and-completion.md`. Re-read
      `references/guardrails-and-provenance.md` during this inspection.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: >
      Run git status and review the complete final diff once more. Confirm only
      intended project files changed, no pre-existing user work was overwritten,
      no temporary scripts or migration-plan files remain, dependency metadata
      agrees with the tested runtime, and all changed code uses native v2 APIs.
      Rerun any command affected by a final cleanup edit. When performing this
      step, follow `references/validation-and-completion.md`.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: >
      Report only verified work: files and native-v2 API categories migrated,
      dependency versions actually used, exact collection and full-suite
      commands, true process exit statuses, and final pass, fail, error, skip,
      xfail, and warning counts. State unresolved failures plainly instead of
      claiming completion. Do not summarize a migration as successful unless
      the static audit, behavior-preservation inspection, and exact full suite
      all passed. When performing this step, follow
      `references/validation-and-completion.md` and re-read
      `references/guardrails-and-provenance.md`.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Re-pointing imports to pydantic.v1 or another Pydantic v1 compatibility namespace; this is explicitly rejected even when tests pass.
  - Emptying, deleting, bypassing, or replacing a validator or function body with pass, an unconditional return, or another no-op merely so the module imports; this is explicitly rejected even when tests pass.
  - Ending after an import smoke test, successful collection, a focused test, or a written summary without running the exact full suite.
  - Piping pytest through head, tail, grep, or another command and reporting the pipeline's zero status as pytest success.
  - Treating zero collected tests or collection errors as zero failing tests.
  - Blindly replacing every validator with field_validator or every root_validator with model_validator without adapting signatures, modes, data access, and return values.
  - Replacing only root_validator forms containing parentheses and missing bare decorators.
  - Converting an after model validator while retaining a `(cls, values)` mapping body, or returning values instead of self.
  - Rewriting values.get mechanically without checking whether the validator receives a mapping, ValidationInfo, or a model instance.
  - Removing allow_reuse at call sites without first repairing and testing reusable validator infrastructure.
  - Importing field_validator from an internal module instead of the supported pydantic API.
  - Adding `= None` to every Optional field or otherwise weakening requiredness simply to make fixtures construct.
  - Ignoring unannotated inherited field overrides such as segment_name assignments that Pydantic v2 rejects.
  - Dropping custom Field metadata such as is_component instead of moving it to json_schema_extra and updating every reader.
  - Replacing __fields__ textually while retaining ModelField, shape, field_info.extra, or instance-level assumptions.
  - Removing a private-looking helper such as `_is_list_field` when tests, exports, or downstream callers import it.
  - Changing parser, serializer, X12, or JSON output semantics while only checking that model construction succeeds.
  - Performing repository-wide sed or regex edits without immediately inspecting the diff and running a focused checkpoint.
  - Using stale hard-coded absolute paths or guessed filenames instead of the verified repository root and files actually present.
  - Creating temporary fix scripts or migration-plan documents and leaving them in the final working tree.
  - Editing tests to accept weaker behavior instead of preserving the established validation contract.
  - Claiming completion from warnings, partial output, truncated logs, or commands whose true exit status was not captured.
```