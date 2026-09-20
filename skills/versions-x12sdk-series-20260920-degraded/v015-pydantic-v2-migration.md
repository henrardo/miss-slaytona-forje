---
name: pydantic-v2-migration
description: Behavior-preserving procedure for migrating Python codebases from Pydantic v1 to native Pydantic v2, including dependencies, pydantic-settings, validators, model configuration, field metadata, parsing, serialization, introspection, collection, and iterative test-driven repair. Use when upgrading Pydantic, removing v1 APIs, or fixing schema, validation, parsing, collection, and test failures caused by Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 15
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving validation, parsing, serialization, settings, schemas, public
  helpers, and domain behavior. Work from complete tracebacks and executable
  checkpoints rather than speculative bulk rewrites. Never satisfy the task by
  importing from pydantic.v1 or another v1 compatibility namespace. Never make
  code import by deleting, emptying, bypassing, or replacing a function body
  with a no-op. Do not declare completion until production code compiles, test
  collection succeeds, focused behavior tests pass, the exact untruncated
  full-suite command exits successfully, and the final diff passes static and
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
    description: |
      Run the repository's documented full test command before editing. Capture:
      the exact command, Python and Pydantic versions, exit status, collection
      count, first complete traceback, and whether failure occurs during import,
      collection, or execution.

      Do not pipe a diagnostic command through `head`, `tail`, or `grep` and then
      treat the pipeline's status as the test status. Without `pipefail`, a
      failing pytest process can appear successful because the final filter
      exited zero. Prefer redirecting complete output to a temporary file:
      `python -m pytest -q > /tmp/pytest.log 2>&1; status=$?`; inspect the file
      separately and retain `$status`. If output must be piped, enable
      `set -o pipefail` and still preserve the complete log.

      Use the full traceback, including its final exception line. A truncated
      traceback is not an actionable baseline. If the suite cannot collect,
      record zero collected tests rather than interpreting that as test success.
    outputs:
      - {name: baseline, type: object}

  - name: confirm-location-and-working-tree
    description: |
      Confirm the repository root with `pwd`, inspect top-level files, and run
      `git status --short` before changing anything. Use the confirmed absolute
      path consistently; do not guess similarly spelled paths.

      Classify every existing modification and untracked file as user-owned,
      prior migration work, generated artifact, or unknown. Do not reset,
      checkout, overwrite, or discard user-owned changes. If the harness carries
      changes across attempts, inspect the current state rather than assuming a
      clean checkout. Record the starting diff so later audits can distinguish
      migration edits from pre-existing work.
    inputs:
      - {name: baseline, type: object}
    outputs:
      - {name: working-tree-state, type: object}

  - name: inspect-repository-contract
    description: |
      Read the actual dependency and test configuration before searching for
      conventional files. Inspect pyproject.toml, setup.cfg, setup.py,
      requirements variants, lockfiles, tox.ini, pytest.ini, CI workflows,
      package metadata, and repository documentation that exist. A missing
      setup.py or requirements.txt is not itself an error.

      Identify supported Python versions, package layout, exact full-suite
      command, lint/type-check commands, expected dependency bounds, and any
      post-migration requirements file supplied by the repository. Treat tests,
      fixtures, public imports, serialization snapshots, and documented APIs as
      behavioral contracts, not obstacles to bypass.
    inputs:
      - {name: working-tree-state, type: object}
    outputs:
      - {name: repository-contract, type: object}

  - name: make-runtime-match-target
    description: |
      Verify the active interpreter and installed versions with executable
      checks such as `python --version`, `python -c "import pydantic; print(...)"`
      and, when relevant, imports of pydantic-settings. Install or select the
      repository's intended post-migration dependency set before diagnosing v2
      behavior. Update declared dependencies consistently, normally to
      `pydantic>=2,<3` plus a compatible `pydantic-settings` bound when settings
      are used.

      Do not use the pydantic.v1 compatibility namespace, indirect aliases to
      it, or a downgrade to Pydantic 1. Those can turn imports green without
      completing a native migration and are disallowed even if tests pass.
    inputs:
      - {name: repository-contract, type: object}
    outputs:
      - {name: runtime-versions, type: object}

  - name: inventory-v1-surface
    description: |
      Search all production Python files, not only the first matching files.
      Build a file-and-line inventory for:
      - BaseSettings and settings Config classes
      - validator, root_validator, allow_reuse, pre=True, always=True, each_item
      - validator signatures using values, field, config, or ModelField
      - class Config and renamed or removed config keys
      - Field(regex=...), arbitrary Field extras, min_items, max_items
      - constrained types and assumptions about their runtime representation
      - __fields__, ModelField, SHAPE_LIST, field_info.extra, sub_fields, shape
      - parse_obj, parse_raw, from_orm, dict, json, schema, copy
      - custom encoders and JSON output paths
      - inherited fields overridden without annotations
      - dynamically generated model registries or field lookups
      - reusable validator decorators and helper partials
      - Optional fields that omit defaults
      - forward references and model rebuilding.

      Use syntax-aware searches or carefully quoted fixed-string searches where
      regular-expression metacharacters would be ambiguous. A grep exit code of
      one can mean no matches; do not report it as a command failure without
      interpreting the command.
    inputs:
      - {name: runtime-versions, type: object}
    outputs:
      - {name: migration-inventory, type: object}

  - name: inventory-public-and-test-contracts
    description: |
      Search tests and package exports for helpers, classes, and behavior that
      migration code must preserve. Include direct imports of internal-looking
      helpers, model_fields expectations, repeatable-list initialization,
      aliases, validation error cases, environment settings, X12 or other custom
      serialization, and exact JSON/dict output.

      In particular, detect public list-field helpers such as `_is_list_field`.
      If tests import one, preserve or implement it against v2 annotations
      instead of deleting it because its v1 implementation used SHAPE_LIST.
      Record representative positive and negative fixtures for validators and
      representative serialized output before editing.
    inputs:
      - {name: migration-inventory, type: object}
    outputs:
      - {name: public-contracts, type: object}

  - name: classify-migration-work
    description: |
      Convert the inventories into an ordered plan by semantic category:
      dependencies/settings, shared base models, inherited fields, field
      definitions, reusable validators, field validators, model validators,
      introspection/list helpers, parsing/serialization, and downstream models.

      For each validator, record whether it is field-level or model-level,
      before or after validation, which fields it reads, whether field order
      matters, whether defaults must be validated, and whether it returns raw
      input, a field value, or a model instance. Do not classify validator
      migration as mechanical decorator renaming.
    inputs:
      - {name: public-contracts, type: object}
    outputs:
      - {name: migration-plan, type: object}

  - name: create-small-edit-checkpoints
    description: |
      Divide work into small coherent checkpoints. After each checkpoint run:
      Python compilation for changed files, direct imports of affected modules,
      the narrowest relevant tests, and a diff review. Keep one failure class in
      focus at a time.

      Avoid repository-wide sed or regex rewrites of validator decorators,
      function signatures, return statements, imports, or bodies. If a
      mechanical transformation is genuinely uniform, first prove it on one
      occurrence, use a syntax-aware script when possible, inspect every changed
      hunk, compile immediately, and retain an easy rollback boundary.
    inputs:
      - {name: migration-plan, type: object}
    outputs:
      - {name: checkpoint-strategy, type: object}

  - name: repair-first-collection-blocker
    description: |
      Fix only the first complete import or collection blocker, then rerun the
      same import or collection command. Typical first blockers include
      BaseSettings relocation, removed imports such as SHAPE_LIST, missing
      decorator imports, invalid validator syntax, unannotated inherited field
      overrides, Field(regex=...), and stale allow_reuse arguments.

      Never stop after a small import smoke test. It is only a checkpoint and
      does not establish that downstream modules collect or behavior is intact.
    inputs:
      - {name: checkpoint-strategy, type: object}
    outputs:
      - {name: first-blocker-checkpoint, type: object}

  - name: update-dependencies-and-settings
    description: |
      Move BaseSettings imports to `pydantic_settings`. Replace settings
      configuration with SettingsConfigDict while preserving environment file,
      encoding, prefix, case sensitivity, nested delimiter, extra handling, and
      aliases. Example:
      `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.

      Replace `Field(regex=...)` with `Field(pattern=...)`. Instantiate settings
      under controlled test environments and verify defaults plus representative
      environment overrides. Do not assume a successful import proves settings
      parity.
    inputs:
      - {name: first-blocker-checkpoint, type: object}
    outputs:
      - {name: settings-checkpoint, type: object}

  - name: migrate-shared-model-configuration
    description: |
      Convert v1 `class Config` blocks to `ConfigDict` or the appropriate v2
      configuration while preserving behavior. Audit every key rather than
      transliterating blindly. Common mappings include:
      - allow_mutation=False to frozen=True
      - orm_mode=True to from_attributes=True
      - allow_population_by_field_name=True to populate_by_name=True
      - schema_extra to json_schema_extra
      - validate_all to validate_default
      - keep_untouched to ignored_types.

      Preserve extra-field policy, enum handling, aliases, assignment
      validation, arbitrary types, string normalization, strictness, and custom
      serialization. Put shared policy on common base models where inheritance
      previously supplied it, then test representative subclasses.
    inputs:
      - {name: settings-checkpoint, type: object}
    outputs:
      - {name: model-config-checkpoint, type: object}

  - name: migrate-inherited-field-overrides
    description: |
      Compile and import model-heavy modules to find PydanticUserError reports
      for fields overridden by non-annotated attributes. Add explicit
      annotations to genuine field overrides, for example
      `segment_name: X12SegmentName = X12SegmentName.CR5`.

      Search for every analogous override across the repository rather than
      repairing only the reported line. Do not annotate constants indiscriminately;
      use ClassVar only when the attribute is truly not a model field. Confirm
      that dynamic registries can still retrieve each inherited field default
      from `model_fields`.
    inputs:
      - {name: model-config-checkpoint, type: object}
    outputs:
      - {name: inherited-field-checkpoint, type: object}

  - name: migrate-field-definitions
    description: |
      Replace removed field arguments while preserving constraints:
      `regex` becomes `pattern`; list `min_items` and `max_items` become
      `min_length` and `max_length`. Move arbitrary custom Field metadata such
      as `is_component=True` into
      `json_schema_extra={"is_component": True}` and update every consumer to
      read `FieldInfo.json_schema_extra`.

      Audit Optional annotations carefully. In v2, `Optional[T]` without a
      default remains required; add `= None` only where v1 behavior and tests
      establish that omission was allowed. Verify constrained decimal, integer,
      string, literal, and collection behavior with boundary tests. Never insert
      non-Python values such as lowercase `true`.
    inputs:
      - {name: inherited-field-checkpoint, type: object}
    outputs:
      - {name: field-checkpoint, type: object}

  - name: migrate-reusable-validator-infrastructure
    description: |
      Remove `allow_reuse`; it is not accepted by v2 validators. Do not create a
      project helper named `field_validator` that shadows Pydantic's decorator.
      Import the decorator explicitly from pydantic and give project wrappers
      distinct names.

      Reusable validation functions should remain ordinary callables with
      signatures compatible with their use. Register field validators with
      `field_validator("name", mode="before" or "after")(callable)` and register
      model validators with `model_validator(mode="before" or "after")`. For
      shared cross-field functions that still consume and return dictionaries,
      prefer `mode="before"` or write explicit adapters; do not feed them a
      model instance accidentally. Exercise every reuse site, not just the
      helper module import.
    inputs:
      - {name: field-checkpoint, type: object}
    outputs:
      - {name: reusable-validator-checkpoint, type: object}

  - name: migrate-field-validators
    description: |
      Replace `@validator` with `@field_validator` one validator at a time.
      Map `pre=True` to `mode="before"`. Use ValidationInfo for sibling input:
      `def validate_value(cls, value, info: ValidationInfo)` and
      `info.data.get("other_field")`. Field order still controls which validated
      sibling fields are available, so use a model validator when the rule
      requires later fields or the complete model.

      Remove unsupported `field` and `config` signature parameters; obtain field
      metadata through `cls.model_fields[info.field_name]` and configuration
      through `info.config`. Re-evaluate `always=True`: use validate_default
      where validation of defaults is intended. Rework `each_item` using
      annotated item constraints or collection-level validation. Preserve the
      original return value and exception conditions. Test valid, missing,
      malformed, and boundary inputs.
    inputs:
      - {name: reusable-validator-checkpoint, type: object}
    outputs:
      - {name: field-validator-checkpoint, type: object}

  - name: migrate-model-validators
    description: |
      Replace each root validator semantically:
      - `@root_validator(pre=True)` becomes
        `@model_validator(mode="before")`; it receives raw input, normally a
        mapping, and must return raw input.
      - Post root validators become `@model_validator(mode="after")`; use
        `def validate_rule(self): ...; return self` and access fields as
        attributes.
      - Use `mode="wrap"` only when the original behavior genuinely surrounds
        core validation.

      Convert dictionary operations deliberately: `values.get("x")` usually
      becomes `self.x` in an after validator, but remains mapping access in a
      before validator. Preserve loops, conditional required-field rules,
      duplicate checks, nested model traversal, error messages where tests rely
      on them, and the final return. Do not perform textual substitutions such
      as `values.get` to `self.` across whole files.

      A decorator with a stray colon, `@model_validator(pre=True)`, an after
      validator retaining `(cls, values)`, or an after validator returning the
      old dictionary is not migrated. Compile after every group and run
      positive and negative tests for every changed validator.
    inputs:
      - {name: field-validator-checkpoint, type: object}
    outputs:
      - {name: model-validator-checkpoint, type: object}

  - name: repair-field-introspection
    description: |
      Replace class-level `__fields__` access with `model_fields` and instance
      explicit-field tracking with `model_fields_set` where appropriate.
      Pydantic v2 entries are FieldInfo objects; do not expect ModelField.shape,
      sub_fields, or field_info.

      Read custom metadata from
      `(field_info.json_schema_extra or {}).get("key")`. Derive list shape from
      annotations with `typing.get_origin` and `typing.get_args`, unwrapping
      Annotated and unions as needed. Update parsers, serializers, dynamic
      segment registries, and reflection loops together. For a dynamic default,
      use `model_cls.model_fields["field"].default` after verifying the field
      exists; do not silently substitute None and hide registry corruption.
    inputs:
      - {name: model-validator-checkpoint, type: object}
    outputs:
      - {name: introspection-checkpoint, type: object}

  - name: preserve-list-field-helper
    description: |
      Preserve any public `_is_list_field` or equivalent helper required by
      tests or package consumers. Implement it against v2 FieldInfo annotations,
      not removed SHAPE_LIST constants. It must identify `list[T]`,
      `typing.List[T]`, Annotated list forms, and list members inside
      Optional/Union while rejecting scalar and unrelated container fields.

      Use the helper in before model validation that wraps a single repeatable
      segment into a one-element list. The validator must tolerate non-mapping
      input where appropriate, avoid double-wrapping existing lists, preserve
      None, and return the original or copied input mapping. Test the helper
      directly and test construction of representative repeatable loop fields.
    inputs:
      - {name: introspection-checkpoint, type: object}
    outputs:
      - {name: list-helper-checkpoint, type: object}

  - name: migrate-parsing-and-serialization
    description: |
      Replace deprecated entry points according to intent:
      - parse_obj with model_validate
      - parse_raw with model_validate_json when JSON is intended
      - from_orm with model_validate plus from_attributes configuration
      - dict with model_dump
      - json with model_dump_json
      - schema with model_json_schema
      - copy with model_copy.

      Preserve include/exclude, aliases, exclude_none, exclude_unset,
      exclude_defaults, mode, and round-trip behavior. Do not blindly replace
      arbitrary `.dict()` or `.json()` calls belonging to normal mappings or
      other libraries.

      For custom domain serializers such as X12 output, iterate model_fields in
      stable declaration order but obtain values from the instance. Preserve
      delimiters, component metadata, enum values, Decimal/date formatting,
      nested list traversal, omitted trailing elements, and newline behavior.
      Compare representative output byte-for-byte with fixtures or the recorded
      baseline.
    inputs:
      - {name: list-helper-checkpoint, type: object}
    outputs:
      - {name: serialization-checkpoint, type: object}

  - name: compile-production-code
    description: |
      Run `python -m compileall` on the production package before broad imports.
      Compilation must exit zero. Repair syntax errors before investigating
      runtime errors. This catches malformed decorators, botched automated
      imports, invalid replacements, indentation damage, and unfinished edits
      that test collection may report less clearly.
    inputs:
      - {name: serialization-checkpoint, type: object}
    outputs:
      - {name: compilation-result, type: object}

  - name: run-import-and-collection-gate
    description: |
      Import foundational modules first, then both major model families or all
      plugin/transaction families, then run the exact untruncated collection
      command, normally `python -m pytest --collect-only -q`. Capture its real
      exit status and complete output.

      Collection is a mandatory gate. Do not call an import successful merely
      because one base module imports, and do not start broad behavior repair
      while collection still fails. Compare collected test count with the
      repository's expected scale so accidental deselection is visible.
    inputs:
      - {name: compilation-result, type: object}
    outputs:
      - {name: collection-result, type: object}

  - name: run-focused-behavior-tests
    description: |
      Run focused tests in increasing scope: settings and shared helpers; base
      models and serializers; each changed segment/model module; repeatable-list
      initialization; parsing; then each transaction or integration family.
      Use `-x` while diagnosing but rerun the whole focused file after the first
      failure is fixed.

      For every migrated validator include valid and invalid cases. A passing
      import or a handful of unrelated tests does not demonstrate validator
      preservation. Record commands, real exit statuses, pass counts, failure
      counts, and warnings.
    inputs:
      - {name: collection-result, type: object}
    outputs:
      - {name: focused-test-result, type: object}

  - name: compare-validation-semantics
    description: |
      Compare v1 contract evidence with v2 results for requiredness, default
      validation, coercion, field order, cross-field dependencies, nested error
      locations, exception types, aliases, extra fields, and assignment
      behavior. Check both accepted and rejected data.

      Treat a changed ValidationError path or message as potentially meaningful
      when tests or consumers assert it. Do not weaken a validator merely to
      make a fixture pass; determine whether the fixture, migration, or prior
      behavior is authoritative.
    inputs:
      - {name: focused-test-result, type: object}
    outputs:
      - {name: semantics-result, type: object}

  - name: repair-iteratively-to-green
    description: |
      Repeat this loop:
      1. Run the smallest command that reproduces the current first failure.
      2. Read the complete traceback and inspect nearby source plus the original
         pre-migration implementation.
      3. Form one concrete hypothesis.
      4. Make the smallest behavior-preserving edit.
      5. Compile and rerun the reproducer.
      6. Rerun the affected focused file.
      7. Periodically rerun collection and the broader suite.

      Prefer local, explicit repairs over adding compatibility wrappers that
      conceal many unrelated errors. If a change reveals a repeated pattern,
      inventory every occurrence before applying a reviewed transformation.
    inputs:
      - {name: semantics-result, type: object}
    outputs:
      - {name: iterative-repair-result, type: object}

  - name: audit-automated-edits
    description: |
      Inspect `git diff --check`, `git diff --stat`, and every changed hunk.
      Look specifically for duplicated or missing imports, decorators with
      invalid arguments or punctuation, lowercase JSON booleans in Python,
      changed indentation, partial string substitutions, deleted returns,
      changed validator modes, stale dictionary access in after validators,
      accidental annotations, and generated migration scripts or plan files
      that do not belong in the final patch.

      Revert or repair collateral edits without discarding legitimate
      pre-existing user changes. Recompile and rerun affected tests after audit
      fixes.
    inputs:
      - {name: iterative-repair-result, type: object}
    outputs:
      - {name: diff-audit, type: object}

  - name: run-static-migration-audit
    description: |
      Search production code for all inventoried v1 interfaces and classify
      every remaining match. Fail the gate for native imports from pydantic.v1,
      BaseSettings from pydantic, validator/root_validator decorators,
      allow_reuse, SHAPE_LIST, ModelField-dependent logic, `__fields__`,
      field_info.extra, Field(regex=...), unsupported Config keys, and
      unreviewed deprecated parse/serialization calls.

      Also search for prohibited bypasses: `pass`, ellipsis, unconditional early
      returns, broad exception swallowing, skipped tests, xfail additions,
      deleted assertions, monkeypatches that suppress validation, and function
      bodies emptied or replaced with no-ops. Inspect every changed function
      against its original body. A body may be structurally rewritten for v2,
      but its domain checks cannot disappear.
    inputs:
      - {name: diff-audit, type: object}
    outputs:
      - {name: static-audit, type: object}

  - name: run-full-suite
    description: |
      Run the repository's exact full-suite command without truncating,
      filtering, selecting only convenient files, or suppressing warnings that
      indicate incomplete migration. Capture complete output and the real exit
      status separately. Require exit zero and a plausible nonzero pass count.

      If the full suite fails, return to iterative repair; do not summarize
      partial success as completion. After the first green run, rerun any
      repository-required lint, formatting, type-check, or packaging commands.
    inputs:
      - {name: static-audit, type: object}
    outputs:
      - {name: full-suite-result, type: object}

  - name: verify-behavior-preservation
    description: |
      Compare the final implementation and outputs with the pre-migration
      contract. Verify settings overrides, representative model construction,
      every changed validator's invalid cases, repeatable-list wrapping, parser
      output, model dumps, JSON output, custom domain serialization, dynamic
      registries, field metadata, and public helper imports.

      Reject the migration even with green tests if it relies on pydantic.v1,
      weakens constraints, bypasses validation, empties function bodies, removes
      public helpers, silently changes serialized output, or modifies tests to
      conceal regressions. Add focused tests when existing coverage cannot prove
      a changed path.
    inputs:
      - {name: full-suite-result, type: object}
    outputs:
      - {name: behavior-verification, type: object}

  - name: final-diff-and-status-gate
    description: |
      Run final `git status --short`, `git diff --check`, diff review, production
      compilation, collection, static v1-interface search, focused critical
      tests, and the untruncated full suite. Confirm dependency files and source
      code agree on native Pydantic v2 and pydantic-settings.

      Ensure no temporary logs, ad hoc migration plans, one-off rewrite scripts,
      caches, or unrelated generated files remain unless the repository
      explicitly requires them. Preserve known pre-existing user files and list
      them separately from migration changes.
    inputs:
      - {name: behavior-verification, type: object}
    outputs:
      - {name: final-gate, type: object}

  - name: report-completion
    description: |
      Report only verified facts:
      - dependency and API migration summary
      - major semantic repairs
      - exact compile, collection, focused-test, and full-suite commands
      - real exit statuses and pass counts
      - static-audit result
      - behavior-preservation checks
      - remaining warnings or risks
      - pre-existing changes left untouched.

      Do not say "successfully migrated" after imports alone, after collection
      alone, after a truncated command, or while any gate is red. If interrupted,
      state the last verified checkpoint and current blocker rather than
      claiming completion.
    inputs:
      - {name: final-gate, type: object}
    outputs:
      - {name: migration-report, type: object}

anti_patterns:
  - Re-pointing imports to pydantic.v1, a compatibility namespace, or an alias that hides continued v1 use
  - Downgrading Pydantic or loosening dependency metadata to avoid native v2 migration
  - Emptying, deleting, bypassing, or replacing a function or validator body with pass, ellipsis, a no-op, or an unconditional return merely so imports succeed
  - Ending the turn after a summary, probe, or partial import without running the required validation gates
  - Treating zero collected tests as success
  - Piping pytest through head or tail and trusting the filter's zero exit status
  - Truncating tracebacks before the exception type and message
  - Assuming missing conventional files such as setup.py or requirements.txt are repository defects
  - Guessing repository paths or repeatedly using similarly misspelled absolute paths
  - Resetting or checking out files without first classifying existing user changes
  - Applying repository-wide sed or regex replacements to validators, signatures, imports, dictionary access, or return statements
  - Renaming root_validator to model_validator without selecting a mode and rewriting the function contract
  - Leaving mode="after" validators with cls-and-values signatures or returning dictionaries
  - Leaving mode="before" validators with instance-style attribute access
  - Using unsupported forms such as model_validator(pre=True), allow_reuse, or a colon after a decorator
  - Shadowing Pydantic's field_validator with a project partial or helper of the same name
  - Treating field order dependent ValidationInfo.data as a complete model
  - Replacing all values.get calls textually with self attributes
  - Removing domain checks, loops, duplicate detection, or conditional required-field logic during validator conversion
  - Adding `= None` to every Optional field without proving omission was allowed
  - Moving custom Field extras to json_schema_extra without updating all metadata consumers
  - Replacing `__fields__` with model_fields while retaining ModelField-only attributes such as shape, sub_fields, or field_info
  - Deleting a public helper such as `_is_list_field` because its v1 implementation depended on SHAPE_LIST
  - Silently returning None when a dynamic registry cannot find a required model field
  - Blindly replacing every dict or json method call regardless of the owning type
  - Changing custom serialization ordering, aliases, delimiters, enum values, date/Decimal formatting, or omission behavior without comparison
  - Editing or weakening tests, adding skips or xfails, or deleting assertions to manufacture a green suite
  - Declaring completion after smoke imports, collection, or a focused subset instead of the exact full suite
  - Leaving temporary rewrite scripts, logs, plans, syntax damage, or unrelated generated artifacts in the final patch
```