---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, or behavioral failures.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 7
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, validation, parsing, serialization, generated schemas,
  and repository tests preserve intended behavior. Complete the migration
  without redirecting imports to `pydantic.v1`; without deleting, emptying,
  bypassing, or neutralizing validators or other function bodies; without
  corrupting source through broad mechanical edits; and without stopping after
  searches, investigation, planning, an import check, collection, or a partially
  passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete suite passes
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - >
    Rewriting imports to `pydantic.v1`, adding fallback imports that select
    `pydantic.v1`, or otherwise routing production code through the v1
    compatibility namespace. The grader rejects this even if the tests pass.
  - >
    Replacing a validator or any other function body with `pass`, ellipsis, a
    bare return, an unconditional constant result, or another no-op so the
    function still imports. Emptying a function body is explicitly rejected
    even if the suite becomes green.
  - >
    Removing validation decorators, commenting out checks, weakening model
    fields to `Any`, suppressing `ValidationError`, removing fields, or making
    extra-field handling permissive merely to avoid failures.
  - Declaring the migration complete without running the repository's own complete test suite.
  - >
    Spending the entire attempt inventorying APIs without making edits. Use the
    first complete traceback to choose a migration slice, edit it, and validate
    it immediately.
  - >
    Ending an execution turn after stating a plan, summary, proposed next
    search, or list of remaining work. While a known blocker remains, perform
    the next edit and validating command instead.
  - >
    Piping the primary test command through `head`, `tail`, `grep`, `tee`, or
    another command without preserving pytest's status. A downstream command
    can report exit zero while pytest failed.
  - >
    Treating a displayed exit code as proof that tests passed when output was
    truncated, piped, or produced by a downstream command.
  - >
    Treating zero collected tests, successful package import, successful test
    collection, or hundreds of passing tests alongside any failure as a
    passing suite.
  - >
    Assuming usages in tests are irrelevant. Tests define required public APIs,
    construction semantics, invalid-input behavior, aliases, serialization,
    equality, schema output, and compatibility expectations.
  - >
    Blindly replacing every old API name. Validator modes, Optional defaults,
    aliases, unions, equality, serialization, schema output, and coercion
    changed semantically and require behavior-aware edits.
  - >
    Updating only the first `Field(const=True)`, `class Config`, `parse_obj`,
    or `update_forward_refs` occurrence. Inventory and migrate the complete
    production surface, then use tests to locate semantic gaps.
  - >
    Editing generated templates merely because they contain words such as
    `construct`, `copy`, `dict`, `json`, or `schema`. Distinguish Pydantic
    methods from domain methods, Jinja filters, and generated-client code.
  - >
    Changing tests to accept broken production behavior. Modify tests only when
    the task explicitly requires native-v2 expectations and the previous
    assertion genuinely encodes a changed external contract.
  - >
    Running broad regular-expression substitutions over nested `Config`
    classes, validators, or large `schema_extra` dictionaries without reviewing
    each resulting file. Regex edits can leave orphaned dictionary bodies,
    duplicate configuration, and invalid indentation.
  - >
    Inserting `model_config` beside a legacy `class Config` while leaving
    indented `schema_extra` content behind. Replace the complete configuration
    block as one syntactic unit and compile the file immediately.
  - >
    Continuing with a broad automated edit after its expected match is absent,
    or trying successively wider replacements without rereading the actual file.
  - >
    Using a mistyped, stale, or duplicated repository path. Establish the root
    once, change into it, and use repository-relative paths thereafter.
  - >
    Treating Pydantic deprecation warnings as proof of a native migration.
    Compatibility aliases can execute under v2 while leaving v1-style APIs in
    production.
  - >
    Repeatedly consulting general migration documentation after the repository
    traceback already identifies the next concrete edit. Prefer repository
    evidence and focused tests over redundant research.
  - >
    Making many unvalidated edits before checking syntax or imports. A malformed
    intermediate file obscures the original migration failures and wastes the
    remaining execution budget.
  - >
    Declaring the task complete because one module imports after fixing
    `Field(const=True)`. Import success is only the first validation gate.
  - >
    Resetting all tracked changes because the working tree is dirty. Prior
    migration edits or user work may be valuable; inspect and preserve them,
    reverting only a specifically identified malformed edit when safe.
  - >
    Repairing syntax by deleting a large model configuration or JSON-schema
    example. Preserve the original configuration payload and move it intact to
    its native-v2 location.
  - >
    Running the full suite repeatedly while an import-time syntax error is
    known. Compile and import the affected module first, then collect and run
    focused tests before returning to the full suite.

steps:
  - name: establish-repository-root-and-state
    description: >
      Run `pwd`, identify the version-control root, change into that verified
      root, and inspect `git status --short` before editing. Record unrelated
      user changes and preserve them. Inspect the active Python executable,
      Python version, and installed Pydantic version with the same interpreter
      that will run tests. Use repository-relative paths for all later commands.
      Do not reset, clean, or overwrite unrelated work.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, inspect `git diff --check`,
      `git diff --stat`, and the diff of every modified Pydantic-related file
      before adding more edits. Run `python -m compileall -q` on the affected
      package immediately. Treat syntax and indentation errors as the first
      blocker. Open the complete malformed class and compare it with its version
      in the index using `git show HEAD:path` or `git diff`, without discarding
      unrelated valid changes. Repair orphaned `schema_extra` dictionaries,
      duplicated `model_config` assignments, partial `Config` removals, and bad
      indentation before migration work continues. If safe reconstruction is
      uncertain, restore only the affected file from the index and reapply its
      migration deliberately; never reset the whole repository. Compile after
      each repaired file. This gate is mandatory when a previous broad edit has
      touched many model files.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read project metadata and contributor documentation just far enough to
      identify the repository's documented test, lint, type-check, formatting,
      build, and dependency-management commands. Prefer those commands over
      invented equivalents. Note whether tox, nox, Poetry, uv, or another tool
      creates a different environment from the active shell.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      After the source compiles, run the documented complete test command
      directly. If none is documented, run `python -m pytest -x -vv`. Do not
      pipe or truncate this primary run. If capture is necessary, redirect
      output to a file, save the command status immediately, and inspect the file
      afterward. If using `tee`, enable `pipefail` and inspect the test process
      status explicitly. Record the actual exit status, collected count, passed
      count, and whether failure occurred during pytest configuration, conftest
      import, collection, package import, or test execution. Zero collected
      tests is a failure. Preserve the first complete traceback rather than only
      its first or last lines. A result such as 310 passed plus one import,
      collection, or execution failure is still a failed baseline.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback says ``const` is removed, use `Literal` instead`,
      inspect the complete affected model and its base class, then search the
      production tree for every `Field(..., const=True)` occurrence. Replace
      each constant field with an explicit annotation such as
      `name: Literal["value"] = "value"` or, for an enum discriminator,
      `param_in: Literal[ParameterLocation.HEADER] =
      Field(default=ParameterLocation.HEADER, alias="in")`. Preserve aliases,
      defaults, enum values, and field names. Add the `Literal` import.
      Pydantic v2 requires model fields to have type annotations, so do not
      merely delete `const=True`. Make this edit before conducting a broad
      optional inventory, then compile and import the affected module.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `pyproject.toml`, setup files, requirements files, lockfiles, tox or
      nox configuration, CI workflows, and migration-specific dependency files
      such as `requirements-v2.txt` when present. Determine where Pydantic is
      declared, whether the target is native v2 only or genuine dual-major
      support, and whether companion packages such as `pydantic-settings` are
      available. Update constraints and lock metadata if they still exclude v2.
      Never introduce `pydantic.v1` as an escape hatch.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: inventory-the-complete-pydantic-surface
    description: >
      Search production code, tests, examples, and generation templates for
      Pydantic imports and v1 APIs. Include `BaseModel`, `BaseSettings`, `Extra`,
      `class Config`, `ConfigDict`, `Field` arguments, `validator`,
      `root_validator`, `parse_obj`, `parse_raw`, `parse_file`, `from_orm`,
      `dict`, `json`, `schema`, `schema_json`, `copy`, `construct`,
      `__fields__`, `__fields_set__`, `update_forward_refs`, `GenericModel`,
      `__root__`, constrained types, Pydantic dataclasses, custom types,
      `json_encoders`, schema hooks, and direct `ModelField` access. Search for
      removed or renamed field arguments including `const`, `regex`,
      `min_items`, `max_items`, `unique_items`, `allow_mutation`, and arbitrary
      extra keyword metadata. Include unannotated model attributes because v2
      rejects fields lacking annotations. Use precise searches and inspect
      context so unrelated methods or template filters are not misclassified.
      Record every production occurrence, but time-box the inventory and return
      promptly to editing the active blocker. A search returning no matches is
      evidence, not a command failure requiring investigation.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read each affected model module, its complete base classes, and relevant
      callers rather than relying on grep snippets. Map inheritance, aliases,
      recursive references, discriminated unions, enums, custom validators,
      arbitrary types, extra-field policy, JSON-schema customization, and model
      API calls. Read tests that construct, reject, compare, dump, or generate
      schemas from these models. Pay particular attention to aliased OpenAPI
      fields such as `in`, constant discriminator fields, configuration inherited
      from shared bases, and tests using v2 APIs such as `model_construct`.
      Test-side v2 usage can reveal the required production API and is not
      irrelevant merely because it appears under `tests/`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Group findings into small slices: syntax recovery, dependencies and
      imports, model configuration, fields and annotations, optionality, field
      validators, model validators, parsing, serialization, schema generation,
      introspection, forward references, and specialist model types. Put the
      current collection or execution blocker first and name exact files plus
      the narrow validating command. Prefer one representative model conversion
      followed by validation before repeating a pattern. The plan is not a
      stopping point: perform the first edit and validation in the same
      execution sequence.
    inputs:
      - name: first-error
        type: string
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: migrate-model-configuration-safely
    description: >
      Convert each complete nested `class Config` block to a class-level
      `model_config = ConfigDict(...)` assignment. Import `ConfigDict` and remove
      `Extra` only after no use remains. Map `extra = Extra.allow`, `.ignore`,
      or `.forbid` to `extra="allow"`, `"ignore"`, or `"forbid"`;
      `allow_population_by_field_name` to `populate_by_name`;
      `orm_mode` to `from_attributes`; `allow_mutation=False` to `frozen=True`;
      `anystr_strip_whitespace` to `str_strip_whitespace`; and `schema_extra`
      to `json_schema_extra`. Preserve `arbitrary_types_allowed`,
      `validate_assignment`, `use_enum_values`, `str_min_length`,
      `str_max_length`, alias generators, ignored types, strictness, and all
      other intended settings under their v2 names. Preserve large schema
      examples intact instead of rewriting their nested contents. Place
      `model_config` at class indentation, never inside a field declaration or
      beneath an orphaned legacy block. Do not define both `Config` and
      `model_config` on the same model. Convert one structural pattern at a
      time, inspect the diff, and compile every touched file before continuing.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Replace removed field arguments according to intended behavior:
      `regex` with `pattern`, `min_items` and `max_items` with `min_length` and
      `max_length`, and constants with `Literal`. Investigate `unique_items`
      rather than deleting it; use a set type or a validator only when that
      preserves ordering and public behavior. Move arbitrary JSON Schema
      metadata into `json_schema_extra`. Replace field-level
      `allow_mutation=False` with `frozen=True` where equivalent. Annotate every
      model field and mark true constants as `ClassVar` when they are not model
      data. In v2, `Optional[T]` or `T | None` without a default remains
      required; add `= None` only when omission was previously allowed, and keep
      required-nullable fields required. Preserve aliases, default factories,
      default validation, constraints, discriminators, and omitted-versus-null
      behavior. Run focused valid, invalid, omitted, null, alias, and field-name
      construction tests after each group.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Convert `@validator` to `@field_validator` and `@root_validator` to
      `@model_validator` only after reading each function and its tests.
      Map `pre=True` to `mode="before"` and ordinary post-field validation to
      the default `"after"` mode. Replace `always=True` deliberately using
      validated defaults or an appropriate validator mode; do not assume a
      textual substitution. Adapt signatures because v2 uses
      `ValidationInfo`, `info.data`, and model instances or raw dictionaries
      depending on mode rather than v1 `values`, `field`, and `config`
      arguments. Preserve decorator order, including `@classmethod` where
      required. Account for assignment validation, exception behavior, and
      inheritance. Do not catch `TypeError` or `ValidationError` merely to make
      tests pass. Keep every validation check executable and prove with focused
      tests that representative invalid data is still rejected. Never replace a
      function body with a no-op, bare return, or unconditional value.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Replace production `parse_obj` with `model_validate`; migrate `parse_raw`
      and `parse_file` by explicitly loading the input and then calling
      `model_validate` or by using the appropriate v2 JSON validation API.
      Replace `from_orm` with `model_validate` only after enabling
      `from_attributes=True`. Replace Pydantic model calls to `dict`, `json`,
      `copy`, and `construct` with `model_dump`, `model_dump_json`,
      `model_copy`, and `model_construct`, preserving arguments such as
      `by_alias`, `exclude_none`, `exclude_unset`, `include`, and `exclude`.
      Do not alter unrelated domain methods, template helpers, or generated
      client methods with the same names. Check custom serializers and
      `json_encoders`; use v2 serializers when necessary and verify the exact
      emitted representation.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Replace genuine Pydantic `schema` and `schema_json` calls with
      `model_json_schema` and JSON encoding of that result as appropriate.
      Replace `__fields__` with `model_fields` and `__fields_set__` with
      `model_fields_set`, adjusting callers for v2 field metadata. Replace
      `update_forward_refs` with `model_rebuild`, resolving namespaces and
      recursive import order rather than suppressing errors. Migrate
      `GenericModel` to generic `BaseModel` patterns, `__root__` models to
      `RootModel`, and custom types from legacy validators or schema hooks to v2
      core-schema and JSON-schema hooks when encountered. Review constrained
      types, Pydantic dataclasses, equality assumptions, private attributes, and
      union behavior. Verify generated schema snapshots and recursive model
      construction rather than relying only on import success.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, classify remaining
      failures before editing. Check changed coercion, strictness, union
      selection, validator ordering, default validation, alias behavior,
      equality, serialization of subclasses, enum handling, dataclass timing,
      extra-field storage, and required-versus-nullable semantics. Use the
      failing test and the former model contract as the source of truth. Make
      the smallest native-v2 correction that preserves intended public behavior;
      do not broadly loosen models or rewrite tests to conceal the difference.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After each coherent edit, run `git diff --check`, then a syntax check such
      as `python -m compileall -q` on the affected package, import the affected
      module, and run the narrowest relevant test module or node with an unpiped
      command. For an import-time blocker, progress through syntax, direct
      import, pytest collection, and focused tests. Inspect the real exit status.
      Classify the next traceback as an unconverted v1 occurrence, an incorrect
      mechanical edit, malformed source, or a semantic v2 difference. Make the
      smallest behavior-preserving correction and repeat. If an automated edit
      malformed a file, stop the batch, inspect the diff and indexed version,
      restore only that edit safely, and repair the file before continuing. Do
      not end the attempt with a prose summary while a known failing command
      remains actionable.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Once the suite collects, rerun the precise production searches from the
      initial inventory. Collection success only proves that imported modules no
      longer fail immediately; lazy paths and unimported modules can still
      contain v1 APIs. Resolve every production occurrence or record a
      behavior-based reason that it is unrelated to Pydantic. Compile the entire
      production package again so a rarely imported malformed file cannot
      survive behind passing focused tests.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Review `git diff --check`, `git diff --stat`, and `git diff` file by file.
      Confirm edits are limited to the migration, imports are clean, type
      annotations and aliases remain correct, nested configuration and
      JSON-schema dictionaries are intact, and no behavior was erased.
      Explicitly search for `pydantic.v1`, fallback imports, newly introduced
      `pass` or ellipsis statements, bare validator returns, unconditional
      validator results, commented-out checks, swallowed `ValidationError`,
      weakened `Any` annotations, removed fields, and broad test deletions.
      Search for residual `schema_extra`, `Extra`, legacy `class Config`,
      duplicate `model_config`, and suspiciously indented dictionary entries.
      Review every automated replacement for indentation, syntax, decorator
      order, configuration inheritance, signatures, and unintended formatting
      churn. Preserve unrelated user changes.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Run the repository's complete documented suite without an
      output-truncating pipeline. Verify the command's actual zero status,
      collected count, passed count, skipped or failed count, and warnings.
      Successful import, collection, focused tests, or a large passing count
      such as 310 tests is not completion if any error remains. Treat zero
      collected tests as failure unless the repository intentionally has no
      tests. On failure, preserve the complete traceback, return to the focused
      edit-test loop, fix the next blocker, and rerun the full suite. Continue
      until it passes.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Run the repository-configured type checker, linter, formatter check,
      packaging or build command, and schema or generated-code checks used by
      CI. Resolve migration-induced errors and Pydantic deprecation warnings
      that identify remaining v1 APIs. If a gate exposes a demonstrably
      pre-existing unrelated failure, record it separately and verify the
      migration did not worsen it rather than performing unrelated cleanup.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Confirm with the repository's active interpreter that Pydantic major
      version 2 is loaded. Search the final production tree for `pydantic.v1`,
      legacy `Config` classes, `Extra`, removed `Field` arguments, deprecated
      validators, `parse_obj`, old serialization methods, old introspection
      attributes, and unresolved forward-reference calls. Distinguish genuine
      Pydantic usage from unrelated names. Run a final whole-package compile.
      Exercise representative valid and invalid inputs, omitted versus null
      fields, alias and field-name population, serialization, and generated
      schema. Confirm each migrated validator still rejects the invalid cases it
      rejected before. Native-v2 verification requires preserved behavior, not
      merely successful import.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      When auditing how an accepted source procedure maps to this version, walk
      the source material line by line and classify every distinct instruction
      as Mapped, Schema gap, Body drop, or Deliberate drop. Fix every Schema gap
      or Body drop before accepting the procedure, and record the rationale for
      every Deliberate drop. For this procedure, retain repository establishment,
      dirty-tree recovery, unpiped baseline testing, project constraints,
      immediate const handling, complete inventory, behavior mapping, executable
      planning, all native-v2 migration areas, focused validation loops,
      semantic investigation, diff review, full-suite execution, quality gates,
      final verification, and evidence-based reporting.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Summarize changed migration areas, dependency changes, repaired partial
      edits, and intentional behavioral decisions. Report the exact full-suite
      and quality-gate commands, their actual exit outcomes, and collected and
      passed test counts. Mention residual warnings, pre-existing failures, or
      unrun checks plainly. Do not claim completion unless the full suite passed
      under Pydantic v2 and final searches found neither `pydantic.v1` shims nor
      behavior-erasing no-op implementations. If work remains, continue
      executing it instead of substituting a completion summary for the missing
      edits.
    outputs:
      - name: migration-report
        type: object
```