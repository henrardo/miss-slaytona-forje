---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 31
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49, 5e38ab12, 651026ff"
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
  - Never redirect production imports to `pydantic.v1`; that preserves v1 rather than completing a native-v2 migration
  - Never empty, delete, replace with `pass`, or otherwise neutralize a validator or any function body merely to make imports or tests succeed
  - Never rewrite tests or fixtures solely to accept behavior that regressed during migration
  - Never treat a piped command such as `pytest | head`, `pytest | tail`, or `pytest | tee` as authoritative unless pipeline failure propagation is enabled and the real pytest exit status is captured
  - Never interpret a shell exit code of zero from `pytest | head`, `pytest | tail`, `pytest | tee`, `grep ... || true`, or a similar pipeline as proof that pytest or the searched condition succeeded
  - Never declare success from an import check, compilation, collection, focused tests, a warning-free run, a pass count, or a partially passing suite
  - Never stop after writing a plan or summary; continue making validated edits until the authoritative suite and required quality gates pass
  - Never run an unreviewed regex or bulk rewrite across model files containing nested schema examples, dictionaries, long configuration blocks, forward references, or import lists
  - Never trust a bulk rewrite merely because it reports that files were changed; compile, inspect, import, and behavior-test every affected slice
  - Never call `model_rebuild` on a typing alias, mapping alias, callback alias, or any object that is not an actual Pydantic model class
  - Never assume `Optional[T]` means an omittable field in Pydantic v2; omission requires a default such as `= None`
  - Never replace a mapping alias with `RootModel` without checking every caller for mapping operations, accepted inputs, equality, iteration, indexing, and serialized shape
  - Never add required constructor arguments merely to satisfy Pydantic v2 if existing callers and fixtures intentionally omitted those arguments
  - Never edit tests before proving that the expected behavior itself should change; migration regressions belong in production code
  - Never install or replace project tooling merely because a preferred wrapper is unavailable when the repository already supplies a working authoritative command or requirements set
  - Never modify dependency declarations without reconciling lockfiles and the harness-provided target environment
  - Never repeatedly research a documented conversion while the current traceback already identifies an executable next edit
  - Never use misspelled or guessed repository paths; derive paths from `pwd`, `git rev-parse --show-toplevel`, and file discovery
  - Never overwrite an entire source file to repair a small migration defect unless the original content has been preserved and the complete replacement is reviewed against the diff

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the actual root with Git, record Python and
      Pydantic versions, inspect status, and distinguish pre-existing edits
      from edits made during this attempt. Use repository-relative paths after
      confirming the root; do not guess paths from prior attempts.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Compile and inspect the existing diff before continuing.
      Preserve valid work, but revert malformed generated edits file by file
      when the pristine version is available. Never discard user-authored
      changes or reset the whole tree indiscriminately.
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
      task definitions, test configuration, and harness-specific requirement
      files. Record the complete test command and quality commands rather than
      inventing substitutes.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative command without output-truncating pipes,
      capture its real exit status and complete output in a file if necessary,
      and record collection counts, pass counts, failures, errors, warnings,
      and the first actionable traceback. If output must be viewed through a
      pipe, enable pipeline failure propagation and separately preserve the
      underlying pytest exit code.
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
      collection blocker." Convert each constant field to an actual typed
      field using `Literal[...]` while preserving its default and alias. Do not
      turn model fields into `ClassVar` merely to silence Pydantic, because that
      removes them from validation and serialization. Compile and retry
      collection immediately after this narrow edit.
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
      range, dependency manager, lockfile policy, generated-code constraints,
      compatibility requirements, and whether supplied v1/v2 requirements
      files define the harness environment.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Use the repository or harness-provided v2
      requirements first. Verify the imported version in the same interpreter
      that runs tests. Avoid installing unrelated tooling or creating a second
      environment unless the authoritative project workflow requires it.
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
      exports, dependency files, and generated model packages for imports,
      `BaseModel`, nested `Config`, `Extra`, `schema_extra`, aliases,
      `allow_population_by_field_name`, removed `Field` arguments,
      `Optional` annotations, mutable defaults, validators, parsing and
      serialization methods, schema and field introspection, forward-reference
      rebuilds, type aliases, mapping aliases, root models, and public
      constructor calls. Record counts and file locations; do not end the turn
      after inventory.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace inheritance, recursive
      references, aliases, exports, constructors, fixtures, parser entry
      points, mapping-like aliases, and serialization consumers. For every
      model changed in bulk, determine what callers omit, pass by field name,
      pass by alias, index, iterate, compare, dump, or validate.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: establish-behavioral-sentinels-before-batch-edits
    description: >
      Before converting many models, read `references/safety-and-baseline.md`
      and follow "Establish behavioral sentinels before batch edits." Add or
      select focused existing tests for representative constructors,
      alias-based and name-based population, constant fields, extra-field
      behavior, schema generation, serialization, recursive OpenAPI parsing,
      mapping aliases, and shared fixtures. Include `Config()` or equivalent
      zero-argument construction when existing callers rely on it.
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
      slice plan." Order edits by blockers and dependency relationships:
      import and collection blockers, model configuration, field semantics,
      constructor compatibility, defaults, validators, parsing and
      serialization, recursive models, aliases, dependency metadata, then
      residual cleanup. Keep slices small enough to compile and test
      immediately. Begin the first edit in the same working session rather
      than stopping after planning.
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
      configuration safely." Convert nested `Config` classes to
      `model_config = ConfigDict(...)`, mapping `Extra.allow` to
      `extra="allow"`, `allow_population_by_field_name` to `populate_by_name`,
      and `schema_extra` to `json_schema_extra`. Preserve complete nested schema
      examples as a single value inside `ConfigDict`; do not strand
      `json_schema_extra` as an unannotated model attribute or duplicate
      configuration. Edit one structural pattern at a time and inspect every
      resulting import and closing delimiter.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Convert removed arguments according to
      their actual meaning: `const` to `Literal`, collection `min_items` and
      `max_items` to `min_length` and `max_length`, and other renamed
      constraints deliberately. Preserve aliases, defaults, strictness,
      validation constraints, and serialized names. Treat `Optional[T]`
      separately from omittability: add `= None` only where callers,
      fixtures, prior behavior, or the v1 model contract allowed omission.
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
      constructor contracts." Enumerate all `Optional[...]` fields without
      defaults and compare them with production call sites and fixtures. In
      particular, instantiate shared configuration and error models exactly as
      existing code does, including zero-argument `Config()` construction.
      Pydantic v2 makes `Optional[T]` without a default required; restore
      `= None` for fields intentionally omittable under v1. Run representative
      constructors directly and run every fixture-heavy test module before a
      broad suite. Do not wait for dozens of identical `Field required`
      failures to reveal this class of regression.
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

  - name: run-the-shared-fixture-constructor-gate
    description: >
      Before converting specialist recursive models or running the complete
      suite, execute the smallest tests that instantiate widely shared models
      and fixtures. If a fixture fails at setup with `ValidationError` or
      `Field required`, inspect the model definition first, not every dependent
      test. Compare each missing field against the v1 declaration and all
      call sites; restore omitted defaults such as `= None` where omission was
      intentional. Re-run the fixture test and constructor sentinel until they
      pass, because a single shared constructor regression can create failures
      across most of the suite.
    inputs:
      - name: requiredness-audit
        type: object
      - name: behavioral-sentinels
        type: object
    outputs:
      - name: shared-fixture-gate
        type: object

  - name: audit-default-values-and-instance-isolation
    description: >
      Before proceeding beyond constructor auditing, read
      `references/native-v2-conversions.md` and follow "Audit default values and
      instance isolation." Preserve observable default behavior while replacing
      mutable model defaults with `Field(default_factory=...)` where required.
      Test that separate instances do not share dictionaries, lists, or sets.
      Distinguish migration-required default changes from unrelated cleanup.
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
      without erasing behavior." Convert validators to native v2 decorators and
      signatures only when needed, preserving validation order, values,
      exceptions, side effects, and accepted inputs. Never remove, empty,
      bypass, replace with `pass`, or turn a validator or helper into a
      no-op merely to make imports succeed. Add focused valid and invalid cases
      around each migrated validator.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Replace model `parse_obj` with
      `model_validate`, `dict` with `model_dump`, `json` with
      `model_dump_json`, `copy` with `model_copy`, and `construct` with
      `model_construct` where the receiver is a Pydantic model. Preserve
      options such as aliases, exclusions, unset handling, and validation
      context. Do not mechanically rename unrelated methods with the same
      names.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Update schema and field introspection
      APIs and handle root models, dataclasses, generics, custom types,
      discriminated unions, recursive models, and arbitrary types according to
      their public contracts. Preserve plain typing aliases when callers expect
      ordinary dictionaries or lists. Convert an alias to `RootModel` only
      when a model wrapper is truly required and every caller and serialized
      shape is updated intentionally.
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
      references with the correct namespace." Call `model_rebuild` only on
      actual model classes after all referenced names are available. For
      recursive OpenAPI graphs, supply or arrange the complete namespace and
      rebuild at a stable package boundary after imports, rather than scattering
      premature calls through modules. Never invoke model methods on aliases
      such as callbacks, paths, responses, security requirements, or plain
      mappings. Validate a realistic recursive document, not merely an import.
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
      dependency metadata." Update the declared Pydantic range to the intended
      v2 range and reconcile requirements and lockfiles using the repository's
      normal tool when available. Do not silently leave a v1 lockfile beside a
      v2 declaration or replace a tested bounded range with an unjustified
      broad range.
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
      every edited file, import the narrow affected package, and inspect the
      diff before continuing. Treat malformed imports, duplicate configuration,
      missing delimiters, truncated examples, and unexpected warnings as edit
      failures. Revert or repair the current slice before touching more files.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run focused behavioral sentinels and the nearest affected test
      module. Capture the actual exit status. Do not substitute `head`, `tail`,
      or a pass count for the result.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the complete suite once to expose semantic
      clusters. Record the full summary and group failures by common root
      traceback, shared model, fixture, and migration category rather than
      fixing tests in file order.
    outputs:
      - name: post-collection-triage
        type: object

  - name: triage-a-partially-passing-suite
    description: >
      If hundreds of tests pass but the suite still fails, read
      `references/validation-and-completion.md` and follow "Triage a partially
      passing suite." Treat the remaining failures as high-signal evidence.
      First inspect setup errors and repeated `Field required` messages from
      shared fixtures; then constructor optionality and aliases; then recursive
      model rebuilds and unresolved annotations; then mapping-alias shape,
      schema, serialization, and isolated behavioral failures. Fix one root
      cause and rerun its smallest reproducer before rerunning the suite. A
      result such as 310 passing tests is not completion if any failure or
      error remains.
    inputs:
      - name: post-collection-triage
        type: object
      - name: requiredness-audit
        type: object
      - name: default-audit
        type: object
      - name: shared-fixture-gate
        type: object
    outputs:
      - name: partial-suite-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      When failures may reflect changed semantics, read
      `references/native-v2-conversions.md` and follow "Investigate v2 semantic
      differences." Build a minimal runtime reproduction under the installed
      v2 version and compare it with the intended v1 behavior or project tests.
      Consult documentation only for the specific uncertainty. Prefer a
      production-code compatibility fix that preserves public behavior; change
      an expectation only when the repository intentionally adopts a documented
      v2 behavior.
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
      after collection succeeds." Search again for v1 compatibility imports,
      nested model `Config`, `Extra`, removed field arguments, deprecated
      methods, `update_forward_refs`, stale configuration keys, unreviewed
      `Optional` fields without defaults, and accidental `pass` or empty
      function bodies. Classify every remaining match as migrated, intentional
      non-Pydantic usage, or unresolved work.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Check every changed file for unrelated rewrites,
      malformed imports, duplicated or misplaced configuration, truncated
      schema examples, changed aliases, altered defaults, dropped exports,
      test weakening, production `pydantic.v1` imports, empty function bodies,
      temporary scripts, and untracked artifacts. Compare large generated
      changes with their pristine source when possible.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Execute the authoritative unpiped command with the
      target v2 environment and preserve the real exit code and complete
      summary. If any test fails or errors, return to clustered triage; do not
      report completion based on the number that passed.
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
      gates." Run the repository's required formatter check, lint, type check,
      package or lock verification, generated-output checks, and any integration
      tests required by the task. Capture every command and exit status.
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
      native-v2 verification." Verify the runtime version, dependency
      declarations, residual inventory, representative model constructors,
      aliases, schemas, serialization, recursive validation, and instance
      isolation. Explicitly prove that production code does not import
      `pydantic.v1` and that no validator or other function body was emptied,
      replaced with `pass`, or neutralized to obtain green tests.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Walk the migration inventory,
      original failures, plan, behavioral map, and every distinct guardrail
      line by line against the completed diff and validation evidence. Classify
      each item as Mapped, Schema gap, Body drop, or Deliberate drop. Repair
      every Schema gap or Body drop before completion, and record a concrete
      rationale for every Deliberate drop. Confirm that constructor
      requiredness, shared fixtures, defaults, mapping aliases, forward
      references, dependency artifacts, production-import guardrails, and
      function-body integrity were not lost during compression or rewriting.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Report the files and semantic areas changed,
      exact authoritative suite command and result, quality-gate commands and
      results, runtime Pydantic version, dependency state, residual-inventory
      result, native-v2 guardrail verification, and any explicitly scoped
      limitations. Do not claim success unless the complete suite passes with
      zero failures and zero errors and all required gates pass.
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