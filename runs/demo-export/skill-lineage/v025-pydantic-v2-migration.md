---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 25
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving intended validation, construction, defaults, aliases, parsing,
  serialization, generated schemas, recursive models, fixtures, public APIs,
  dependency metadata, and repository behavior. Complete the migration without
  redirecting production imports to `pydantic.v1`; without deleting, emptying,
  bypassing, replacing with `pass`, or otherwise neutralizing validators or
  any other function bodies merely so imports or tests succeed; without
  weakening production behavior or rewriting tests to accept regressions;
  without corrupting source through broad mechanical edits; and without
  stopping after research, inventory, planning, an import check, compilation,
  collection, focused tests, or a partially passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, field, validator, or configuration errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, methods, symbols, or semantics
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted, duplicated, truncated, or syntactically malformed models
  - Models import under Pydantic v2 but constructors, fixtures, aliases, schemas, serialization, or behavioral tests fail
  - Most tests pass but shared defaults, optionality, forward references, recursive aliases, root models, or exported types still fail
  - The installed Pydantic version disagrees with dependency declarations, requirements files, or lockfiles

do_not_use_when:
  - The codebase already uses native Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task upgrades a dependency unrelated to Pydantic
  - The requested outcome is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning, read `references/migration-guardrails.md` and enforce every guardrail throughout the migration
  - Never re-point production imports to `pydantic.v1`, even as a temporary way to make tests green
  - Never empty a validator or any other function body, replace it with `pass`, remove its decorator, or return an unconditional value merely to make imports or tests pass
  - Never edit tests solely to accept a production regression; change tests only when the task explicitly requires new native-v2 API assertions and behavior remains equivalent
  - Never declare success after imports, compilation, collection, one focused test, or a partially passing suite
  - Never end a turn after inventory or planning when edits and validation remain possible
  - Never pipe the authoritative test command through `head`, `tail`, `grep`, or a pipeline that hides the test process exit status
  - Never treat a shell command with `|| true`, a failed grep, or a truncated log as proof that validation passed
  - Never run blind repository-wide regex or `sed` rewrites over nested configuration or schema dictionaries
  - Never assume a mechanical conversion is correct without compiling, importing, testing, and reviewing its diff
  - Never confuse the project model named `Config` with Pydantic's nested v1 `class Config`
  - Never install unrelated tooling or regenerate dependency files unless the repository's authoritative workflow requires it
  - Never add migration summaries, temporary scripts, logs, or other unrequested artifacts to the repository
  - Never discard pre-existing user changes; isolate migration edits from unrelated working-tree modifications
  - Never convert dict-like type aliases to `RootModel` unless callers and public behavior actually require a model wrapper
  - Never use `ClassVar` as a substitute for a validated constant field when the value must remain part of model input, output, or schema

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the real repository root once, use that exact
      path consistently, inspect Git status, Python and Pydantic versions, and
      preserve all pre-existing modifications. Record whether the current tree
      is clean, partially migrated, or already malformed.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Inspect the diff before touching it. Distinguish user work,
      valid prior migration progress, malformed bulk edits, and disposable
      generated artifacts. Repair or selectively restore individual damaged
      files; do not reset the whole tree or erase unrelated work.
    inputs:
      - name: repository-state
        type: object
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify authoritative
      project commands." Inspect project metadata, task definitions, CI
      workflows, test configuration, repository instructions, and migration
      requirements files. Prefer the repository's existing environment and
      commands. Record any required environment variables, excluded integration
      suites, quality gates, and the exact complete-suite command.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative collection or test command directly,
      preserving its real exit status and complete output in a file when
      needed. Do not use `head`, `tail`, or another masking pipeline. Capture
      the first actionable traceback, total collected tests when available,
      and whether failure occurs during import, collection, execution, or a
      quality gate.
    inputs:
      - name: project-commands
        type: object
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed, read
      `references/safety-and-baseline.md` and follow "Act immediately on a const
      collection blocker." Replace each validated constant with an accurate
      `Literal[...]` annotation and ordinary default, preserving model input,
      output, and schema behavior. Do not use `ClassVar` for fields that must
      remain model fields. Compile and import the affected module immediately.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine supported Python versions, intended Pydantic v2
      range, dependency-manager conventions, lockfile policy, and whether a
      supplied post-migration requirements file is the harness source of truth.
      Do not casually widen Python support or select APIs unavailable at the
      repository's minimum target version.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the target
      environment." Ensure the interpreter actually imports the intended
      Pydantic v2 version before diagnosing migration behavior. Use the
      repository-provided post-migration dependency set or dependency-manager
      workflow. Update declared dependency constraints and lockfiles only
      through the authoritative process; do not assume an edited pyproject
      changes the active environment.
    inputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]
    outputs:
      - name: target-environment
        type: object

  - name: inventory-the-complete-pydantic-surface
    description: >
      Read `references/safety-and-baseline.md` and follow "Inventory the complete
      Pydantic surface." Search production code, tests, fixtures, generated
      schema modules, exports, and dependency metadata for Pydantic imports,
      BaseModel subclasses, nested `class Config`, `Extra`, `schema_extra`,
      population settings, validators, root validators, constrained fields,
      `const`, `min_items`, `max_items`, `regex`, parse and serialization
      methods, model construction, schema introspection, forward-reference
      rebuilding, type aliases, root models, mutable defaults, and private or
      removed attributes. Record locations and expected behavior, not just
      counts.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace imports, re-exports, recursive
      dependencies, aliases, model inheritance, parser call sites, fixtures,
      constructors, schema examples, and serialization consumers. Determine
      which names are BaseModel classes versus plain aliases such as
      `Dict[str, PathItem]`; which fields may be omitted versus explicitly
      null; whether aliases may also be populated by field name; and what
      callers expect from defaults and dict-like values.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order small dependency-aware edit slices: collection
      blockers first, shared model configuration and fields next, then parser
      entry points, aliases and recursive models, focused behavioral failures,
      residual inventory, dependency metadata, and final gates. Associate every
      slice with a syntax check, import check, focused test, and diff review.
      Begin the first edit slice in the same run; do not stop after presenting
      the plan.
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
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert nested v1 configuration to native v2
      `model_config = ConfigDict(...)`, mapping `Extra.allow` to
      `extra="allow"`, `allow_population_by_field_name` to the compatible v2
      population setting, and `schema_extra` to `json_schema_extra`. Preserve
      each complete nested schema-example dictionary. Edit one model or a
      structurally identical reviewed group at a time; compile and inspect the
      resulting class indentation and parentheses before continuing.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Convert removed field arguments using
      native v2 equivalents, including `const` to `Literal` and collection
      `min_items` or `max_items` to length constraints where semantically
      equivalent. Audit every `Optional[T]`: in v2 it remains required unless
      it has a default, so add `= None` only when omission was accepted in v1.
      Preserve required fields, aliases, strict types, constraints, and schema
      semantics. Replace mutable defaults with factories when appropriate,
      while verifying equality and fixture expectations.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior." Convert validators only after documenting
      their accepted inputs, ordering, pre/post behavior, field dependencies,
      mutation, and errors. Use native v2 validator APIs and signatures while
      preserving logic. Never remove a decorator, replace a body with `pass`,
      truncate a body, return unconditionally, or otherwise neutralize
      validation merely to make the module import.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Replace production `parse_obj` with
      `model_validate`, and migrate model dict, JSON, copy, construct, and
      schema calls to native v2 methods when those objects are Pydantic models.
      Do not mechanically replace similarly named methods on unrelated
      objects. Preserve keyword arguments, aliases, exclusion behavior,
      validation-error handling, and parser return contracts.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Convert removed introspection APIs and
      forward-reference updates to supported v2 mechanisms. Handle recursive
      aliases, exported annotation namespaces, callbacks, paths, responses,
      references, and root models deliberately. Keep plain mapping aliases
      plain when callers expect normal dictionaries. When rebuilding recursive
      models, provide the complete namespace of classes and aliases actually
      referenced; do not call model methods on aliases that are not models.
    inputs:
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      During every edit step, read `references/native-v2-conversions.md` and
      follow "Run a syntax and import gate after every edit slice." Compile
      every changed Python file, import the narrow affected module, then import
      the package or relevant export boundary. If broad automation changed
      files, compile all touched files immediately and inspect the diff before
      making further edits. Fix syntax, duplicate configuration, malformed
      dictionaries, missing commas, undefined annotations, and import cycles at
      once rather than stacking more changes on broken source.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run the smallest tests proving the changed behavior, including
      constructor, omission/default, alias, schema, serialization, validator,
      parser, and recursive-model cases as applicable. Then rerun collection or
      the current first failing test. Preserve true exit codes and iterate until
      the slice passes before opening another broad slice.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the authoritative non-integration or complete
      suite unpiped and group failures by root cause. Prioritize shared causes
      such as required-optional regressions, missing config defaults, unresolved
      annotations, alias population, and changed serialization rather than
      patching individual tests independently.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences." Compare v1 expectations with native v2 behavior for
      optionality, unions, strict values, enums, equality, nested model
      coercion, extras, aliases, serialization, JSON schema, mutable defaults,
      and validation errors. Fix production behavior where equivalence is
      intended; do not silence the symptom in tests.
    inputs:
      - name: focused-test-results
        type: list[object]
      - name: post-collection-triage
        type: object
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Read `references/validation-and-completion.md` and follow "Repeat
      inventory after collection succeeds." Re-run the complete v1-pattern
      inventory because initial collection blockers may have hidden later
      modules. Classify every remaining match as migrated code, an intentional
      non-Pydantic use, documentation requiring an update, or an unresolved
      migration item. Search explicitly for `pydantic.v1`, removed methods,
      legacy configuration, removed field arguments, and deprecated warnings.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review every changed file and the diff statistic.
      Confirm there are no truncated schema examples, duplicated blocks,
      malformed imports, accidental test accommodations, empty function
      bodies, temporary scripts, logs, summaries, unrelated formatting churn,
      or user changes overwritten. Compare suspicious generated-schema files
      with the original before accepting them.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the complete
      test suite." Run the exact authoritative command without output-truncating
      pipelines and verify its real zero exit status, collected count, passed
      count, skips, warnings, and exclusions. A result with hundreds of passing
      tests but any failure is not completion. If the suite fails, return to
      root-cause triage and continue editing and validating.
    inputs:
      - name: project-commands
        type: object
      - name: diff-review
        type: object
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      Read `references/validation-and-completion.md` and follow "Run project
      quality gates." Run the repository's configured formatter check, import
      sorting check, linter, type checker, package build, or other CI-equivalent
      commands after the full suite passes. Distinguish migration regressions
      from unavailable external services, but do not omit a runnable local gate
      without reporting it.
    inputs:
      - name: project-commands
        type: object
      - name: full-suite-result
        type: object
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Read `references/validation-and-completion.md` and follow "Perform final
      native-v2 verification." Confirm the active runtime and dependency
      metadata target Pydantic v2; production code contains no `pydantic.v1`
      compatibility imports; required functions and validators retain real
      bodies; no unresolved legacy APIs remain; representative constructors,
      aliases, schemas, serialization, and recursive models work; and Git status
      contains only intended migration changes.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Account for every inventory item,
      planned slice, changed file, residual match, warning, and skipped gate.
      Classify each as migrated, verified intentional, still unresolved, or not
      applicable with evidence. Confirm every procedure step was executed
      rather than merely discussed, especially complete-suite validation and
      the prohibitions against `pydantic.v1` and emptied function bodies.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Summarize behavior-preserving production and
      dependency changes, list exact validation commands and outcomes, state
      the full-suite pass count and quality-gate results, identify any
      unavoidable skipped checks, and mention remaining warnings or risks.
      Report completion only when the complete suite and required gates pass;
      otherwise report the remaining blocker and continue if tools and time
      permit.
    inputs:
      - name: full-suite-result
        type: object
      - name: quality-gate-results
        type: list[object]
      - name: native-v2-verification
        type: object
      - name: provenance-audit
        type: object
    outputs:
      - name: migration-report
        type: object
```