---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 17
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, aliases, root models, type aliases, forward references,
  fixtures, and repository tests preserve intended behavior. Complete the
  migration without redirecting production imports to `pydantic.v1`; without
  deleting, emptying, bypassing, replacing with `pass`, or otherwise
  neutralizing validators or any other function bodies; without corrupting
  source through broad mechanical edits; and without stopping after searches,
  research, investigation, planning, an import check, compilation, test
  collection, focused tests, or a partially passing suite.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import or validator errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, configuration, methods, or symbols
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted or syntactically malformed Pydantic models
  - Models import successfully under Pydantic v2 but constructors, fixtures, schemas, aliases, or behavioral tests fail
  - Most tests pass after an upgrade but a shared model, fixture, forward reference, type alias, root model, or optionality regression still causes failures
  - The installed Pydantic version and declared dependency or lockfile disagree

do_not_use_when:
  - The codebase is already on Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task is to upgrade a dependency other than Pydantic
  - The requested solution is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning any migration step, read `references/migration-guardrails.md` and avoid every anti-pattern listed there throughout the migration.
  - Never re-point production imports to `pydantic.v1`; that hides rather than completes the migration.
  - Never make a function importable by deleting its implementation, emptying its body, adding `pass`, returning a placeholder, or disabling validation behavior.
  - Do not treat a piped command such as `pytest | head` or `pytest | tail` as evidence of success; the pipeline can report the consumer's zero status while pytest failed.
  - Do not stop after writing a plan or inventory. Continue in the same attempt with edits and validation unless blocked by missing access or an explicit user decision.
  - Do not stop after one import succeeds, collection succeeds, or a focused test passes.
  - Do not install or replace package managers merely because the preferred wrapper is unavailable; use the repository's available authoritative commands or the active environment.
  - Do not regenerate or hand-edit a lockfile blindly. Determine whether the task requires lockfile synchronization and use the repository's package manager when available.
  - Do not run unreviewed regex or shell rewrites across model files containing nested schema examples or large dictionaries.
  - Do not assume every `Dict[...]` alias should become a `RootModel`; preserve the public runtime shape expected by parsers and tests.
  - Do not invoke `model_rebuild()` on typing aliases or other non-model objects.
  - Do not add migration summaries, temporary scripts, generated reports, or unrelated artifacts to the repository unless requested.
  - Do not suppress Pydantic warnings merely to make output look clean; resolve relevant migration warnings and distinguish unrelated third-party warnings.
  - Do not declare success while tracked files are syntactically malformed, residual v1 APIs remain, the dependency metadata is inconsistent, or any authoritative gate has not run.

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the real root with `pwd` and repository metadata,
      record `git status --short`, Python and Pydantic versions from the same
      interpreter that will run tests, and the available package/test tools.
      Copy paths exactly; repeated `agent-warm` versus `agent-worm` path typos
      waste steps and can target the wrong tree.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Treat existing edits
      as potentially valuable work: inspect their diff and syntax before
      changing them. Revert only a specifically corrupted file after proving
      the corruption and understanding which valid edits will be lost; never
      reset the whole tree or discard user work.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`. Inspect project metadata, CI, task
      definitions, test configuration, and migration-specific requirements.
      Prefer the repository's complete test and quality commands. If a wrapper
      such as Poetry is unavailable, do not install it automatically; use an
      equivalent available command and record the deviation.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`. Run the authoritative command without
      `head`, `tail`, `grep`, or another pipeline that masks its status. If
      output must be retained, redirect it to a file, capture the original exit
      code, and then inspect the file separately. Record the complete first
      actionable traceback, not only its warning wrapper.
    outputs:
      - name: baseline-command
        type: string
      - name: baseline-result
        type: object
      - name: first-error
        type: string

  - name: act-immediately-on-a-const-collection-blocker
    description: >
      If the first traceback reports that `Field(const=True)` was removed,
      follow "Act immediately on a const collection blocker" in
      `references/safety-and-baseline.md`. Search all production and test model
      declarations for `const`, inspect each field's intended type, and replace
      the constraint with a correctly typed `Literal[...]` annotation while
      preserving its default and alias behavior. For enum constants, use the
      actual enum member in `Literal`, not a lookalike string. Remove an `Extra`
      import only if no remaining code in that file uses it. Compile the edited
      file and rerun collection immediately.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`. Determine supported Python versions,
      the intended Pydantic v2 range, whether a migration-specific requirements
      file exists, and which dependency declarations and lockfiles are in
      scope. Do not infer the target solely from the globally installed package.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Ensure the active test interpreter actually uses the intended Pydantic v2
      dependency set. Prefer a repository-provided migration requirements file
      or existing environment command. Recheck `sys.executable`,
      `pydantic.__version__`, and import location afterward. Update declared
      dependency constraints when required, but do not claim completion while a
      committed lockfile still resolves Pydantic v1 unless the repository
      explicitly treats that lockfile as out of scope.
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
      Follow "Inventory the complete Pydantic surface" in
      `references/safety-and-baseline.md`. Search production code, tests,
      fixtures, generated schema modules, templates, and documentation that
      defines behavioral contracts. Include imports; nested `Config`; `Extra`;
      `schema_extra`; population settings; `Field` constraints; validators;
      parsing, serialization, copy, construct, schema, and introspection APIs;
      dataclasses; generic and root models; private attributes; forward
      references; model rebuild calls; mutable defaults; aliases; strict types;
      and custom types. Treat grep exit 1 for no matches as information rather
      than a task failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`. Map inheritance, recursive imports,
      aliases, typing aliases, root-like mappings, default construction,
      parser consumers, fixtures, and tests before choosing conversions.
      Record whether optional annotations are required or default to `None`,
      whether aliases may populate by field name, and whether callers expect a
      plain mapping, model instance, `.root`, or another shape.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Follow "Form an executable slice plan" in
      `references/safety-and-baseline.md`. Order slices by the import graph and
      first failure: collection blocker, shared configuration pattern, fields,
      validators, entry points, special models, then semantic regressions.
      Keep each slice small enough to compile and test immediately. Finish
      planning by executing the first slice in the same turn.
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
      configuration safely." Convert nested v1 `Config` classes to
      `model_config = ConfigDict(...)`, mapping `Extra.allow` to
      `extra="allow"`, `allow_population_by_field_name` to the appropriate v2
      population setting, and `schema_extra` to `json_schema_extra`. Preserve
      complete large schema-example dictionaries and comments. Inspect every
      changed file after any automation; compile the entire affected package
      before proceeding.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Follow "Migrate fields, annotations, and optionality" in
      `references/native-v2-conversions.md`. Convert removed field arguments
      such as `const` and collection constraints to native v2 equivalents.
      Audit every `Optional[T]` that relied on v1's implicit `None`: add
      `= None` only when omission was intentionally valid. Preserve required
      fields, aliases, strictness, defaults, and validation constraints.
      Replace mutable model defaults with factories where behavior requires
      independent values, and test zero-argument construction used by fixtures.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Follow "Migrate validators without erasing behavior" in
      `references/native-v2-conversions.md`. Translate validators and their
      modes, ordering, signatures, always/default behavior, error semantics,
      and cross-field logic. Read each original body before editing and preserve
      its behavior. Never solve an import or signature error by deleting,
      emptying, bypassing, replacing with `pass`, or neutralizing a validator
      or any other function body.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Replace v1 methods with native v2
      methods where appropriate, including `parse_obj` with `model_validate`.
      Preserve include/exclude, alias, unset/default/none, JSON, copy, and
      construction semantics. Update mocks and tests only when they encode the
      renamed public API rather than masking a production regression.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Follow "Migrate schema, introspection, and special models" in
      `references/native-v2-conversions.md`. Handle schema generation,
      `model_fields`, fields-set access, custom types, dataclasses, generics,
      root models, mapping aliases, and forward references deliberately.
      Preserve plain typing aliases when callers require plain containers.
      Call `model_rebuild()` only on actual Pydantic model classes and provide
      the required namespace for recursive references; never call it
      indiscriminately on every export from a package.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: validate-every-edit-slice
    description: >
      After every coherent edit, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." First compile every changed Python file or package to catch
      malformed imports, missing commas, indentation damage, and unclosed
      `ConfigDict` calls. Then run the narrowest relevant import and tests,
      followed by the current first-failure command. Use unpiped commands and
      preserve their real exit codes.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run enough of the suite to group failures by root
      cause rather than editing each symptom independently. Prioritize shared
      causes such as newly required optional fields, invalid zero-argument
      fixtures, alias population, unresolved references, changed container
      shape, or mutable defaults. Do not report collection as migration
      completion.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Compare
      intended behavior rather than forcing old assertions to pass blindly.
      Pay special attention to union selection, enum and strict coercion,
      optionality, validation of defaults, equality, serialization, alias
      precedence, extra fields, recursive models, and error structure.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`. Search again for every v1
      construct because initial import failures can hide later modules. Include
      `pydantic.v1`, removed field arguments, `Extra`, nested model `Config`,
      renamed methods, old validator decorators, old introspection names, and
      stale forward-reference calls. Class names such as the application's own
      `Config` model are not automatically v1 configuration.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`. Review every changed file and
      the diff summary. Look for truncated schema examples, duplicated or
      misplaced config blocks, malformed imports, accidental repository
      artifacts, placeholder bodies, broad formatting churn, changed public
      container shapes, and unrelated edits. Compile again after corrections.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the authoritative full
      suite without piping, truncation, ignored directories, or an implicit
      early-exit option unless that is the repository's official command.
      Record the exact command, original exit code, and pass/fail/skip totals.
      A focused suite, `--collect-only`, or output ending in many dots is not
      full-suite evidence.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's formatter
      check, linter, type checker, packaging/build check, and other authoritative
      gates that are available and in scope. If a gate cannot run because a
      tool is unavailable, report that explicitly rather than installing or
      silently skipping it.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`. Confirm the active interpreter
      uses the target Pydantic v2 version, dependency declarations are
      consistent, production code contains no `pydantic.v1` imports, relevant
      v1 APIs and removed arguments are gone, changed packages compile, public
      imports work, function bodies remain implemented, and the full suite
      still passes after final cleanup.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`. Walk all migration source
      material, prior failure evidence, inventory items, and procedure steps
      line by line. Classify each distinct item as Mapped, Schema gap, Body
      drop, or Deliberate drop. Repair every Schema gap or Body drop before
      completion, and record a concrete rationale for every Deliberate drop.
      Verify specifically that all original procedure steps remain represented
      and that native-v2 and non-empty-function guardrails survived revision.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`. Summarize behavioral changes,
      list the exact full-suite and quality-gate commands with their real exit
      codes and totals, state the verified Pydantic version, mention any
      unavailable gate or remaining warning, and report residual-inventory and
      diff-review results. Do not claim success without a passing authoritative
      full suite and final native-v2 verification.
    outputs:
      - name: migration-report
        type: object
```