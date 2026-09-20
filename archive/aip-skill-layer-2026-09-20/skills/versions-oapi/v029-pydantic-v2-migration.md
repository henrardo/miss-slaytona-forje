---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 29
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49, 5e38ab12"
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
  passing suite.

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

do_not_use_when:
  - The codebase already uses native Pydantic v2 and its complete authoritative suite and quality gates pass
  - The task upgrades a dependency unrelated to Pydantic
  - The requested outcome is explicitly to retain Pydantic v1 rather than perform a native-v2 migration

anti_patterns:
  - Before beginning, read `references/migration-guardrails.md` and enforce every guardrail throughout the migration
  - Never redirect production imports to `pydantic.v1`; that preserves v1 rather than completing a native-v2 migration
  - Never empty, delete, replace with `pass`, or otherwise neutralize a validator or any function body merely to make imports or tests succeed
  - Never rewrite tests or fixtures solely to accept behavior that regressed during migration
  - Never treat a piped command such as `pytest | head`, `pytest | tail`, or `pytest | tee` as authoritative unless pipeline failure propagation is enabled and the real pytest exit status is captured
  - Never declare success from an import check, compilation, collection, focused tests, a warning-free run, or a partially passing suite
  - Never run an unreviewed regex or bulk rewrite across model files containing nested schema examples, dictionaries, or long configuration blocks
  - Never call `model_rebuild` on a typing alias, mapping alias, callback alias, or any object that is not an actual Pydantic model class
  - Never assume `Optional[T]` means an omittable field in Pydantic v2; omission requires a default such as `= None`
  - Never replace a mapping alias with `RootModel` without checking every caller for mapping operations, accepted inputs, and serialized shape

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the root once and use it consistently; avoid
      guessed absolute paths. Record Python and Pydantic versions, the current
      branch, tracked modifications, untracked files, and available migration
      requirement files. Do not install tools or alter dependencies yet.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Treat existing edits as evidence, not automatically as
      correct work. Compile modified Python files, inspect their diffs, and
      revert only demonstrably malformed migration edits without discarding
      unrelated user changes. If a broad script damaged a file, prefer restoring
      that individual file and reapplying a narrow conversion.
    inputs:
      - name: repository-state
        type: object
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Read `references/safety-and-baseline.md` and follow "Identify
      authoritative project commands." Inspect project metadata, CI workflows,
      task runners, and test configuration. Record the authoritative unit suite,
      integration suite, formatting, linting, and type-check commands. Note
      required environment variables such as task-runner guards instead of
      inventing alternate commands.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative test command directly and preserve its
      true exit code and complete output in a log. If output filtering is
      unavoidable, enable pipeline failure propagation and separately capture
      pytest's status. Do not infer success from a shell exit code produced by
      `head`, `tail`, or `tee`. Record collection count, pass count, failure
      count, error count, warnings, and the first complete traceback.
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
      collection blocker." Convert each constant field to a correctly typed
      `Literal` field while preserving whether it is a model field, its default,
      aliases, and accepted enum values. Do not turn required model data into
      `ClassVar`. Compile and import the containing model before continuing.
    inputs:
      - name: first-error
        type: string
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect project
      constraints." Determine supported Python versions, the intended Pydantic
      v2 range, dependency-manager expectations, lockfile policy, and whether
      supplied pre- and post-migration requirement files define the harness
      environment. Do not casually widen Python support or install a package
      manager globally.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Use the repository-provided target dependency set
      when available, then verify the imported Pydantic version in the same
      interpreter used for tests. Avoid replacing the prepared environment or
      invoking a stale lockfile that downgrades Pydantic back to v1.
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
      generated schema modules, package exports, templates, and dependency
      files. Include imports; `BaseModel` subclasses; dataclasses; validators;
      nested `Config`; `Extra`; removed `Field` arguments; aliases; strict
      types; parsing, construction, copying, dumping, JSON, and schema methods;
      model introspection; forward-reference calls; type aliases; root models;
      mutable defaults; optional fields; and zero-argument constructors. Keep
      searches non-fatal when no match is expected.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace imports, inheritance,
      annotations, aliases, package-level re-exports, recursive references,
      parser consumers, and serialization consumers. Inspect tests and shared
      fixtures to identify the actual constructor and output contracts,
      including models instantiated with no arguments and aliases accepted by
      field name.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: establish-behavioral-sentinels-before-batch-edits
    description: >
      Before converting many models, extract a small executable sentinel set
      from current callers and fixtures. Include every shared configuration
      object constructed with no arguments, representative alias and field-name
      construction, a model allowing extras, a model forbidding extras, a
      constant-field model, a recursive model, a mapping alias consumer, and
      representative dump/schema output. Run each sentinel under the target
      environment and record expected behavior from source and tests even when
      collection is blocked. A failing `Config()` or equivalent shared fixture
      is a migration blocker: inspect its defaults before making broad schema
      edits.
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
      slice plan." Order changes by dependency and failure surface: collection
      blockers, shared configuration and fixture constructors, model
      configuration, fields and requiredness, validators, entry points,
      serialization, special models, forward references, dependencies, and
      residual cleanup. Keep slices small enough to compile, import, run their
      sentinels, and test immediately. Prefer explicit edits over generated
      regex rewrites for files containing nested schema examples.
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

  - name: migrate-model-configuration-safely
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate model
      configuration safely." Convert nested v1 `Config` classes to
      `model_config = ConfigDict(...)`; map `Extra` values to string values,
      `allow_population_by_field_name` to `populate_by_name`, and
      `schema_extra` to `json_schema_extra`. Preserve every existing setting and
      the complete nested example dictionary. Place one syntactically complete
      configuration assignment inside the model rather than leaving detached
      fragments, duplicate configurations, or malformed parentheses. Compile
      each edited file before editing the next group.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Convert removed field arguments such as
      `const`, `min_items`, and `max_items` to native-v2 equivalents while
      preserving constraints. Distinguish constant model fields from class
      variables. Preserve aliases, strictness, defaults, and validation intent.
      Avoid unrelated renames or formatting churn.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: audit-requiredness-and-constructor-contracts
    description: >
      Explicitly audit every `Optional[T]` field and every constructor used by
      fixtures or public callers. In Pydantic v2, `Optional[T]` without a
      default accepts `None` but remains required. Add `= None` only where the
      v1 model or caller contract allowed omission. Reproduce failing
      constructors directly, especially shared fixtures such as a project
      `Config()` created with no arguments. Audit override fields, package
      metadata fields, URLs, descriptions, and other configuration options
      commonly declared `Optional` without defaults. Do not paper over
      missing-field errors in tests; restore the production model's intended
      defaults. Re-run all zero-argument constructor sentinels before
      proceeding.
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

  - name: audit-default-values-and-instance-isolation
    description: >
      Review list, dict, set, nested-model, and configuration defaults. Use
      `Field(default_factory=list)`, `Field(default_factory=dict)`, or an
      equivalent factory when each model instance must receive independent
      state. Preserve immutable scalar defaults. Add focused tests or direct
      checks proving that two instances do not share mutable state and that
      zero-argument construction still works where previously supported.
      Confirm default factories do not alter serialized output.
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
      without erasing behavior." Preserve pre/post timing, per-item behavior,
      default validation, cross-field dependencies, accepted inputs, returned
      values, and error behavior. Use native-v2 validator APIs and inspect
      actual call sites. Never delete, empty, bypass, replace with `pass`, or
      otherwise neutralize a validator or any other function body merely to
      make imports or tests pass.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Replace v1 entry points with native-v2
      methods where production code owns the call, including `parse_obj` with
      `model_validate`, and replace deprecated dumping methods where their
      semantics match. Preserve alias use, exclusion flags, JSON behavior,
      error translation, and any logic that depends on testing whether a model
      dump is empty. Do not perform blind global substitutions on unrelated
      objects that also define methods named `dict`, `json`, `copy`, or
      `construct`.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Handle model fields, fields-set
      introspection, JSON schema generation, private attributes, equality,
      dataclasses, generics, and root models according to actual repository
      use. For aliases such as `Dict[str, PathItem]`, preserve plain mapping
      behavior unless callers and serialization contracts require a model.
      If a `RootModel` is justified, update and test all mapping consumers
      explicitly rather than relying on accidental compatibility.
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
      Replace `update_forward_refs` with native-v2 rebuilding only where
      necessary. Determine the complete namespace needed by string annotations
      and recursive models. Rebuild actual `BaseModel` subclasses after all
      referenced symbols are imported, supplying an explicit namespace when
      module globals are insufficient. Do not call `model_rebuild` on typing
      aliases such as callback, paths, responses, security-requirement, or
      other mapping aliases. Avoid circular-import fixes that change public
      types. Validate package-level imports and representative recursive model
      construction after each change.
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
      Update the authoritative dependency declaration to the intended Pydantic
      v2 range and update generated requirement or lock artifacts only with the
      repository's normal tooling and compatibility policy. Do not leave
      `pyproject.toml`, requirements files, installed packages, and lockfiles
      disagreeing about the major version. Do not hand-edit a complex lockfile
      or install an unrelated package manager merely to regenerate it. Verify
      the test interpreter still imports the intended v2 version afterward.
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
      every edited Python file, import the affected module and package-level
      export, and run the relevant behavioral sentinels. Stop immediately on
      malformed imports, truncated annotations, duplicated configuration,
      detached schema dictionaries, missing delimiters, or undefined forward
      references. Repair or restore the affected file before editing another
      slice.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run the smallest focused test set that proves the converted
      behavior, then the containing test module. Capture the actual exit status.
      Keep each production fix narrow and do not combine unrelated speculative
      changes merely because several failures remain.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the complete authoritative unit suite once,
      preserve its full result, and group failures by root cause rather than by
      file count. Prioritize shared fixture and constructor failures because a
      single requiredness regression can produce many downstream failures.
    outputs:
      - name: post-collection-triage
        type: object

  - name: triage-a-partially-passing-suite
    description: >
      If hundreds of tests pass but the suite still fails, do not restart the
      migration or declare near-success. Compare failing and passing clusters.
      First inspect shared fixtures and constructors for v2 requiredness
      changes, especially `Optional` fields lacking `= None`; then inspect
      mutable defaults, alias population, recursive model rebuilding, exported
      type aliases, mapping-versus-`RootModel` behavior, and serialization
      shape. Reproduce the earliest shared failure directly, such as `Config()`,
      before examining its downstream failures. Use the first complete
      traceback from each distinct cluster and make one narrow production fix
      at a time.
    inputs:
      - name: post-collection-triage
        type: object
      - name: requiredness-audit
        type: object
      - name: default-audit
        type: object
    outputs:
      - name: partial-suite-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences." Use official documentation or a minimal local experiment
      for the installed target version, then encode the result in the smallest
      production change. Research must answer a concrete failing behavior and
      must not replace implementation or validation.
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
      after collection succeeds." Search again for v1-only and deprecated
      constructs because the initial blocker may have hidden later imports.
      Include `pydantic.v1`, `Extra`, nested model `Config`, `schema_extra`,
      `allow_population_by_field_name`, `const`, removed field constraints,
      deprecated parsing and dumping methods, `update_forward_refs`, malformed
      conversion artifacts, and function bodies replaced with `pass`.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review every changed file and diff hunk. Look for
      accidental test edits, unrelated formatting, path mistakes, generated
      helper files, broad-script damage, lost schema examples, duplicate
      configurations, truncated annotations, weakened validation, empty
      functions, and compatibility shims. Remove temporary scripts and reports
      that are not intended repository artifacts.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Run the authoritative command directly, without
      output truncation that masks its status. Record the exact command, exit
      code, passed, failed, errored, skipped, and warning counts. If any test or
      fixture fails, return to cluster triage; hundreds of passing tests do not
      satisfy this gate.
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
      gates." Run the repository's authoritative formatting, linting,
      type-checking, packaging, generation, and integration commands where
      available and relevant. Distinguish migration defects from unavailable
      external services, but do not silently omit a required gate.
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
      native-v2 verification." Confirm the runtime version, dependency
      declarations, absence of production `pydantic.v1` imports, absence of
      prohibited neutralized function bodies, residual v1 API inventory,
      package imports, zero-argument configuration construction, alias
      population, mutable-default isolation, representative recursive model
      construction, and expected serialization/schema shapes.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Walk the migration inventory,
      behavior map, sentinels, plan, residual inventory, changed files, and
      applicable procedure steps item by item. Classify every distinct item as
      migrated and verified, not applicable with evidence, intentionally
      unchanged with rationale, or unresolved. Treat missing coverage as a
      body drop and return to the relevant step. Confirm specifically that
      requiredness, defaults, validators, serialization, special models,
      forward references, dependency metadata, full-suite validation, and the
      two prohibited shortcuts were all checked.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Report changed behavior and files, the exact
      full-suite command and counts, quality-gate results, target Pydantic
      version, residual inventory, and any genuine external limitation. Claim
      completion only when the authoritative full suite passes, required
      quality gates pass or have an explicitly evidenced external limitation,
      native-v2 verification passes, and no unresolved provenance item remains.
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