---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 37
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49, 5e38ab12, 651026ff, 1b53fe8c, 671176f8, a6199c0d"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 while
  preserving intended validation, construction, requiredness, defaults,
  aliases, parsing, serialization, generated schemas, recursive models,
  fixtures, public APIs, dependency metadata, and repository behavior.
  Complete the migration without redirecting production imports to
  `pydantic.v1`; without deleting, emptying, bypassing, replacing with `pass`,
  or otherwise neutralizing validators or any other function bodies merely so
  imports or tests succeed; without weakening production behavior or rewriting
  tests to accept regressions; without corrupting source through broad
  mechanical edits; and without stopping after research, inventory, planning,
  an import check, compilation, collection, focused tests, or a partially
  passing suite. Treat a run with hundreds of passing tests and clustered
  failures as an actionable semantic migration stage, not near-enough success.
  Work in small executable slices: inspect, edit, compile, import, run the
  narrowest behavioral test, then continue immediately until the complete
  authoritative suite and project quality gates pass.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with Pydantic import, field, validator, or configuration errors after a Pydantic v2 upgrade
  - Test collection fails on removed Pydantic v1 arguments, methods, symbols, or semantics
  - A repository runs under Pydantic v2 but still relies on deprecated Pydantic v1 APIs
  - A prior migration attempt left partially converted, duplicated, truncated, or syntactically malformed models
  - Models import under Pydantic v2 but constructors, fixtures, aliases, schemas, serialization, or behavioral tests fail
  - Most tests pass but shared defaults, optionality, forward references, recursive aliases, root models, or exported types still fail
  - The installed Pydantic version disagrees with dependency declarations, requirements files, or lockfiles
  - A suite reaches hundreds of passing tests but still has clustered constructor, fixture, schema, or recursive-model failures
  - Shared fixtures fail because formerly omittable Optional fields became required under Pydantic v2

do_not_use_when:
  - The codebase already uses native Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task upgrades a dependency unrelated to Pydantic
  - The requested outcome is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning, read `references/migration-guardrails.md` and enforce every guardrail throughout the migration
  - Never re-point production imports to `pydantic.v1`, even as a temporary shortcut or compatibility layer
  - Never empty, delete, replace with `pass`, bypass, or neutralize a validator or any other function body merely to make imports or tests pass
  - Do not rewrite tests, fixtures, or expected values to conceal a production regression; change tests only when the intended public contract demonstrably changed and the task authorizes that change
  - Do not stop after writing a plan, inventory, summary, or research notes; execute the first safe edit in the same run and continue through validation
  - Do not stop after an import succeeds, files compile, tests collect, one focused test passes, or hundreds of tests pass while any authoritative test still fails
  - Do not pipe authoritative test commands through `head`, `tail`, or a pipeline that masks the test process exit status
  - Do not infer success from a shell command whose reported exit code belongs to `tee`, `head`, `tail`, `grep`, or `|| true`
  - Do not perform broad regex or `sed` rewrites over nested `Config` classes, large schema examples, imports, or parentheses without inspecting each resulting diff and compiling immediately
  - Do not generate and run unreviewed migration scripts across dozens of files; prove a transformation on one representative file first
  - Do not hand-insert closing parentheses by line number into large model files or JSON-schema examples
  - Do not overwrite complete source files from memory when a narrow edit is possible
  - Do not use `git checkout`, `git restore`, or resets on pre-existing user changes unless provenance is established and the exact files being discarded are known to be agent-owned
  - Do not edit from an assumed absolute path; resolve the repository root once and reuse it to avoid `agent-worm`, `agent-wrap`, and similar path mistakes
  - Do not install Poetry or replace the environment manager merely because an optional command is unavailable; use the repository's supplied environment and authoritative commands
  - Do not repeatedly research well-established conversions while a concrete traceback is waiting; consult documentation only for an unresolved semantic choice
  - Do not classify all test-only Pydantic API usage as irrelevant; tests and fixtures expose constructor, alias, serialization, and compatibility contracts that production must preserve
  - Do not convert dictionary type aliases such as paths, callbacks, responses, or security requirements into `RootModel` casually; first inspect all callers and preserve mapping behavior
  - Do not call `model_rebuild()` blindly on every exported symbol; type aliases are not models, and recursive models may require a complete namespace
  - Do not assume `Optional[T]` means omittable in Pydantic v2; add `= None` only where the established constructor contract permits omission
  - Do not preserve mutable defaults blindly or replace every mutable default mechanically; verify instance isolation and schema behavior
  - Do not declare completion without an unpiped full-suite result, quality-gate results, residual-v1 inventory, and diff review

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Resolve the root from the current working directory,
      record Python and installed Pydantic versions, inspect the top-level
      project files, and capture `git status --short` plus the initial diff.
      Store and reuse the resolved root instead of retyping absolute paths.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Classify each modification as pre-existing user work,
      verified prior migration work, malformed prior migration work, or an edit
      made in this run. Preserve unknown and user-owned changes. Compile modified
      Python files before making more edits. Repair malformed files from their
      diff and original version rather than stacking new batch rewrites on top.
    inputs:
      - name: repository-state
        type: object
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands." Inspect `pyproject.toml`, task runners,
      CI workflows, lockfiles, requirements files, contributor docs, and test
      configuration. Identify the complete suite, collection command, focused
      test syntax, formatting, linting, typing, and generation or integration
      gates. Do not invent a Poetry workflow when Poetry is unavailable and the
      harness supplies a working environment.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative test or collection command without
      `head`, `tail`, or exit-masking pipelines. If output must be captured, use
      a method that preserves the test process exit status and inspect the saved
      output afterward. Record the exact command, exit code, collection status,
      pass count, failure count, warnings, and first actionable traceback.
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
      collection blocker." Inspect the intended constant values and convert
      fields to `Literal[...]` annotations with suitable defaults. For the
      known header pattern, preserve `name == ""` and
      `param_in == ParameterLocation.HEADER` as validated model fields rather
      than turning them into `ClassVar` attributes. Compile and import the
      narrow module immediately, then rerun collection.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine supported Python versions, target Pydantic range,
      packaging tool, generated-code constraints, public compatibility promises,
      and whether supplied pre- and post-migration requirements define the
      harness environment.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Verify the interpreter actually imports the intended
      Pydantic v2 version. Prefer repository-provided post-migration
      requirements or the established environment command. Do not update
      dependency metadata merely to match an accidental local install, and do
      not install unrelated tooling unless the authoritative workflow requires
      it.
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
      Read `references/safety-and-baseline.md` and follow "Inventory the
      complete Pydantic surface." Search production code, tests, fixtures,
      package exports, templates, dependency metadata, and generated examples.
      Include BaseModel and RootModel definitions; `Extra`; nested `Config`;
      `schema_extra`; `allow_population_by_field_name`; removed `Field`
      arguments such as `const`, `min_items`, and `max_items`; validators;
      parsing and construction methods; `dict`, `json`, `copy`, and schema APIs;
      field introspection; aliases; forward references; recursive unions; type
      aliases; mutable defaults; Optional fields without defaults; and
      `pydantic.v1`. Treat no-match searches as inventory facts rather than tool
      failures.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace model imports, inheritance,
      aliases, recursive references, package exports, parser entry points,
      fixtures, direct constructors, mapping assumptions, JSON-schema examples,
      and serialization consumers. Record where callers expect omitted optional
      fields, alias and field-name population, dictionary-like values, constant
      validation, extra-key retention, or default constructors.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: establish-behavioral-sentinels-before-batch-edits
    description: >
      Before converting many models, read `references/safety-and-baseline.md`
      and follow "Establish behavioral sentinels before batch edits." Select
      fast checks for top-level import, the default configuration constructor,
      representative aliases such as `$ref` and `in`, extra-field retention,
      constant rejection, mutable-default isolation, OpenAPI validation, and
      shared fixtures. Capture current intended behavior from tests and callers.
    inputs:
      - name: behavior-map
        type: object
      - name: migration-inventory
        type: object
    outputs:
      - name: behavioral-sentinels
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order work by blockers and dependency structure: collection
      blockers; representative model configuration; field and requiredness
      semantics; parser entry points; shared fixtures; recursive and specialist
      models; dependency metadata; then residual cleanup. Every slice must name
      the files, intended behavior, compile/import check, and narrow test to run.
    inputs:
      - name: first-error
        type: string
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: migration-plan
        type: object

  - name: execute-the-first-planned-edit-immediately
    description: >
      After forming the plan, read `references/safety-and-baseline.md` and
      follow "Execute the first planned edit immediately." Do not end the turn
      after planning. Make one narrow production edit, compile it, import the
      affected module, and run its focused sentinel before moving to the next
      slice.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: first-edit-result
        type: object

  - name: migrate-model-configuration-safely
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert each nested v1 `Config` deliberately to
      `model_config = ConfigDict(...)`: `Extra.allow` to `extra="allow"`,
      `allow_population_by_field_name` to the appropriate native-v2 population
      option, and `schema_extra` to `json_schema_extra`. Preserve the complete
      existing example dictionary and all model-specific settings. Place
      `model_config` inside the model at class indentation, not inside a field
      annotation or example dictionary. Update imports precisely. Prove the
      pattern on one small model, compile it, inspect its diff, and only then
      repeat in small reviewed groups.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Use `Literal` for constants, `min_length`
      and `max_length` for collection constraints, and native-v2 field options.
      Preserve aliases and strict types. Audit every `Optional[T]`: in v2 it is
      nullable but still required unless it has a default. Add `= None` only
      when callers, fixtures, or the v1 contract show omission is allowed.
      Avoid converting validated fields into `ClassVar` merely to silence a
      model error.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: audit-requiredness-and-constructor-contracts
    description: >
      Before proceeding beyond field migration, read
      `references/native-v2-conversions.md` and follow "Audit requiredness and
      constructor contracts." Enumerate direct model constructions in
      production and tests, especially configuration, OpenAPI, paths,
      parameters, responses, and shared fixtures. Compare each omitted argument
      with the migrated field declaration. Correct production declarations
      where v1 treated fields as omittable; do not patch every caller or fixture
      to supply meaningless `None` values.
    inputs:
      - name: behavior-map
        type: object
      - name: field-migration-results
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: requiredness-audit
        type: object

  - name: run-the-default-config-constructor-gate
    description: >
      Before broad testing, read `references/native-v2-conversions.md` and
      follow "Run the default config constructor gate." Instantiate the
      repository's configuration model exactly as ordinary callers do,
      including a zero-argument constructor when supported. In the recurring
      project pattern, fields such as project, package, and version overrides
      annotated Optional must retain `None` defaults, while list and dictionary
      defaults must remain isolated between instances.
    inputs:
      - name: requiredness-audit
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: default-config-gate
        type: object

  - name: run-the-shared-fixture-constructor-gate
    description: >
      Before converting specialist recursive models or running the complete
      suite, read `references/native-v2-conversions.md` and follow "Run the
      shared fixture constructor gate." Import or execute shared fixtures and
      representative direct constructors. A fixture failing during setup is a
      production contract signal, not permission to rewrite the fixture. Fix
      common model semantics first, then rerun the fixture gate.
    inputs:
      - name: requiredness-audit
        type: object
      - name: behavioral-sentinels
        type: object
      - name: default-config-gate
        type: object
    outputs:
      - name: shared-fixture-gate
        type: object

  - name: audit-default-values-and-instance-isolation
    description: >
      Before proceeding beyond constructor auditing, read
      `references/native-v2-conversions.md` and follow "Audit default values and
      instance isolation." Check list, dictionary, set, and nested-model
      defaults. Prefer `Field(default_factory=...)` where required by intended
      behavior, but verify Pydantic v2's actual instance isolation before
      changing public schemas or equality behavior. Test two independent model
      instances and mutate one.
    inputs:
      - name: behavior-map
        type: object
      - name: requiredness-audit
        type: object
    outputs:
      - name: default-audit
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validators
      without erasing behavior." Translate validator APIs and signatures while
      preserving execution order, pre/before behavior, cross-field access,
      errors, defaults, and side effects. Inspect the full original body before
      editing. Never delete, empty, replace with `pass`, or bypass a validator
      or helper function merely to make imports or tests pass. Add focused valid
      and invalid cases for every migrated validator.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Replace `parse_obj` with
      `model_validate`, and migrate deprecated construction, copying,
      serialization, and schema methods only where they are Pydantic model
      operations. For emptiness checks such as `schema.dict().values()`, verify
      whether `model_dump()` must exclude unset or default values to preserve
      the original decision. Do not replace unrelated dictionary, JSON, or copy
      calls by textual pattern alone.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Convert field and schema
      introspection, generic models, dataclasses, private attributes, root
      models, and custom schema hooks with focused behavioral tests. Before
      replacing a dictionary type alias with `RootModel`, inspect every caller
      for indexing, iteration, `.items()`, equality, serialization, annotations,
      and parser expectations. Prefer retaining a plain alias when Pydantic v2
      can validate it through the containing model and callers require a dict.
    inputs:
      - name: migration-inventory
        type: object
      - name: behavior-map
        type: object
    outputs:
      - name: specialist-migration-results
        type: object

  - name: rebuild-forward-references-with-the-correct-namespace
    description: >
      When replacing `update_forward_refs`, read
      `references/native-v2-conversions.md` and follow "Rebuild forward
      references with the correct namespace." Use `model_rebuild()` only on
      actual model classes. Ensure all recursive names and aliases are imported
      into the namespace where annotations are resolved before rebuilding.
      Avoid package-wide loops that call model APIs on dictionary aliases.
      Validate recursive OpenAPI models with a real nested input, not import
      success alone.
    inputs:
      - name: behavior-map
        type: object
      - name: specialist-migration-results
        type: object
    outputs:
      - name: forward-reference-results
        type: object

  - name: synchronize-dependency-metadata
    description: >
      When updating dependency declarations, requirements, or lock artifacts,
      read `references/native-v2-conversions.md` and follow "Synchronize
      dependency metadata." Make the declared Pydantic v2 range agree with the
      compatibility target and supplied post-migration requirements. Regenerate
      lock or export artifacts only with the repository's supported tool and
      only when required. Review lockfile diffs for unrelated churn.
    inputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]
      - name: target-environment
        type: object
    outputs:
      - name: dependency-migration-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      During every edit step, read `references/native-v2-conversions.md` and
      follow "Run a syntax and import gate after every edit slice." Compile
      every changed Python file, then import the narrow affected module and a
      top-level package entry point when practical. If compilation fails, stop
      adding edits and repair the first malformed file using its diff. Import
      success is a gate, not completion.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run the narrowest behavioral test or sentinel associated with the
      slice, followed by collection or the next broader relevant test group.
      Record the true unmasked exit status. On failure, fix the first causal
      error and immediately rerun the same check.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the full unit suite early rather than
      converting every warning first. Cluster failures by shared cause:
      requiredness, aliases, defaults, extra handling, recursive resolution,
      serialization, validator semantics, or dependency drift. Fix the
      highest-leverage production cause and rerun its focused tests.
    outputs:
      - name: post-collection-triage
        type: object

  - name: triage-a-partially-passing-suite
    description: >
      If hundreds of tests pass but the suite still fails, read
      `references/validation-and-completion.md` and follow "Triage a partially
      passing suite." Treat 310 or 445 passing tests with remaining failures as
      evidence that broad migration is working, not as permission to stop.
      Inspect the first failure and setup errors, identify the shared model or
      fixture, and repair semantic clusters before unrelated deprecations.
      Continue until the complete suite exits zero.
    inputs:
      - name: post-collection-triage
        type: object
      - name: requiredness-audit
        type: object
      - name: default-audit
        type: object
      - name: shared-fixture-gate
        type: object
      - name: default-config-gate
        type: object
    outputs:
      - name: partial-suite-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences." Reproduce the behavior in a minimal local probe, inspect
      installed-version documentation or migration guidance only for the
      unresolved question, and encode the intended contract in a focused test.
      Prioritize known differences in Optional requiredness, alias population,
      enum and strict coercion, union selection, extra handling, equality,
      serialization defaults, and JSON-schema output.
    inputs:
      - name: focused-test-results
        type: list[object]
      - name: post-collection-triage
        type: object
      - name: partial-suite-triage
        type: object
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      After collection succeeds, read
      `references/validation-and-completion.md` and follow "Repeat inventory
      after collection succeeds." Search again for `pydantic.v1`, `Extra`,
      nested model `Config`, `const=True`, old constraint names,
      `schema_extra`, old population settings, deprecated model methods,
      obsolete validator decorators, field internals, and forward-reference
      APIs. Distinguish intentional compatibility references in documentation
      from executable production usage.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review every changed file and the diff summary. Look for
      truncated examples, duplicated configuration, malformed imports,
      accidental test edits, entire-file rewrites, temporary scripts,
      generated summaries, formatting noise, lost function bodies, `pass`,
      disabled validation, and unrelated dependency churn. Recompile all
      changed Python files after cleanup.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Execute the authoritative suite without output
      truncation or exit-masking pipelines. Capture the exact command, true exit
      code, collected count, passed count, failed count, skipped count, and
      warnings. If it fails, return to first-cause triage rather than reporting
      partial success.
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
      After the full suite passes, read
      `references/validation-and-completion.md` and follow "Run project quality
      gates." Run the repository's authoritative formatting, linting, typing,
      packaging, generation, and integration checks that are available in the
      established environment. Do not silently skip a required gate because an
      optional task runner is absent; execute its underlying documented command
      when possible and report genuine environment limitations precisely.
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
      native-v2 verification." Confirm the runtime imports Pydantic v2, package
      imports succeed, representative models validate and serialize correctly,
      aliases and constants behave as intended, recursive models rebuild, and
      production code contains no `pydantic.v1` redirection. Confirm no function
      or validator body was emptied, replaced with `pass`, or otherwise
      neutralized.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Account for every initial working
      tree change, every migration edit, and every temporary artifact. Verify
      that all planned slices were executed and validated, all residual
      inventory findings were classified, no user-owned changes were discarded,
      and no required migration concern was abandoned after planning.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Report the production changes, dependency
      target, exact full-suite command and result, quality-gate results,
      residual warnings or environment limitations, and native-v2 verification.
      Claim completion only when the authoritative suite exits zero and all
      required gates pass or a clearly identified external limitation remains.
      Do not substitute a prose summary for unfinished edits or failing tests.
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