---
name: pydantic-v2-migration
description: Migrate Python repositories from Pydantic v1 APIs and semantics to native Pydantic v2, including recovery from incomplete or malformed migrations. Use for Pydantic upgrade failures involving imports, collection, model configuration, fields, validators, constructors, aliases, optionality, defaults, schemas, serialization, forward references, type aliases, root models, fixtures, dependencies, or partially passing test suites.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 27
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea, af1c4d30, 0bfc722b, 7bd863cc, 80c91e49"
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
  - Never re-point production imports to `pydantic.v1`, even as a temporary way to make tests green
  - Never empty a validator or any other function body, replace it with `pass`, remove its decorator, or return an unconditional value merely to make imports or tests pass
  - Never edit tests solely to accept a production regression; change tests only when the task explicitly requires new native-v2 API assertions and behavior remains equivalent
  - Never declare success after imports, compilation, collection, one focused test, or a partially passing suite
  - Never treat hundreds of passing tests as success while any authoritative test still fails or errors
  - Never end a turn after inventory or planning when edits and validation remain possible
  - Never pipe the authoritative test command through `head`, `tail`, `grep`, or a pipeline that hides the test process exit status
  - Never treat a shell command with `|| true`, a failed grep, a timeout, or a truncated log as proof that validation passed
  - Never run blind repository-wide regex or `sed` rewrites over nested configuration, schema dictionaries, annotations, or forward-reference expressions
  - Never assume a mechanical conversion is correct without compiling, importing, testing, and reviewing its diff
  - Never confuse the project model named `Config` with Pydantic's nested v1 `class Config`
  - Never assume `Optional[T]` remains optional in Pydantic v2; without an explicit default it is required
  - Never use `ClassVar` as a substitute for a validated constant field when the value must remain part of model input, output, or schema
  - Never convert dict-like type aliases to `RootModel` unless callers and public behavior actually require a model wrapper
  - Never pass unresolved type aliases, typing objects, or non-model exports to `model_rebuild`
  - Never replace a plain mapping expected by callers with a wrapper that requires `.root` access
  - Never preserve shared mutable defaults by accident; use `Field(default_factory=...)` where instances must not share state
  - Never install unrelated tooling or regenerate dependency files unless the repository's authoritative workflow requires it
  - Never add migration summaries, temporary scripts, logs, or other unrequested artifacts to the repository
  - Never discard pre-existing user changes; isolate migration edits from unrelated working-tree modifications
  - Never suppress deprecation warnings as a substitute for completing native-v2 conversions

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the real repository root, current branch, tracked
      and untracked changes, Python version, installed Pydantic version, and
      available package/test tooling before editing.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, read
      `references/safety-and-baseline.md` and follow "Recover a partially edited
      working tree." Determine which edits are pre-existing user work, which are
      migration edits, and which are malformed leftovers. Preserve valid user
      changes. Repair or narrowly revert damaged migration files only after
      inspecting their diffs and the repository version.
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
      task runners, contributor documentation, requirements files, lockfiles,
      and test configuration. Record separate commands for dependency setup,
      collection, focused tests, the complete suite, formatting, linting, and
      type checking. Do not install a package manager merely because one command
      mentions it when an equivalent repository-supported command is available.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish the unpiped
      baseline." Run the authoritative test or collection command directly and
      preserve its actual exit status. Capture the complete traceback in a file
      only through a mechanism that preserves the test process status. Identify
      the first actionable error rather than relying on a truncated `head` or
      `tail` view.
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
      collection blocker." Replace each validated constant field with an
      explicitly annotated `Literal[...]` field and preserve its default,
      alias, input validation, output, and schema presence. Do not convert it to
      `ClassVar` unless the original field was intentionally excluded from
      validation and serialization.
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
      range, dependency compatibility, generated-code constraints, public API
      compatibility, and whether lockfiles are expected to change.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Read `references/safety-and-baseline.md` and follow "Synchronize the
      target environment." Use the repository-provided post-migration
      requirements or package workflow when available. Verify the imported
      Pydantic version in the same interpreter used by tests. Update dependency
      declarations consistently, but do not regenerate lockfiles unless the
      repository workflow requires it.
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
      generated models, public exports, dependency files, and documentation for
      Pydantic imports and v1 constructs. Include `Extra`, nested `class
      Config`, `schema_extra`, `allow_population_by_field_name`, validators,
      root validators, `Field` constraints, `parse_obj`, `dict`, `json`,
      `copy`, `construct`, `schema`, `update_forward_refs`, `__fields__`,
      `__fields_set__`, aliases, root models, recursive aliases, strict types,
      dataclasses, type adapters, and model construction in tests. Record zero
      matches explicitly rather than treating a failed grep as command failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Read `references/safety-and-baseline.md` and follow "Inspect model
      relationships and public behavior." Trace model inheritance, aliases,
      recursive references, package exports, dict-like aliases, fixture
      construction, parser entry points, serialization consumers, generated
      schemas, and callers that depend on mapping behavior. For each field,
      record whether omission is valid, whether `None` is valid, and what
      default or factory callers expect.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Read `references/safety-and-baseline.md` and follow "Form an executable
      slice plan." Order narrow slices by dependency and first failure:
      collection blockers; configuration and fields; requiredness and defaults;
      validators; parsing and serialization; forward references and aliases;
      fixture and constructor behavior; then dependency metadata and quality
      gates. Each slice must name affected files, expected behavior, syntax and
      import checks, focused tests, and a rollback or repair point.
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
      configuration safely." Convert nested v1 configuration to
      `model_config = ConfigDict(...)` without moving or truncating adjacent
      schema dictionaries. Map `Extra.allow` to `extra="allow"`,
      `allow_population_by_field_name` to the appropriate native-v2 name and
      alias-population behavior, and `schema_extra` to `json_schema_extra`.
      Preserve all examples and nested JSON-schema data exactly. Compile and
      inspect each changed file before proceeding.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate fields,
      annotations, and optionality." Replace removed field arguments with their
      native-v2 equivalents, including `const` with validated `Literal`
      annotations and collection `min_items` or `max_items` with length
      constraints where semantically equivalent. Preserve aliases, numeric
      constraints, strictness, JSON-schema metadata, and validation behavior.
      Distinguish nullable from omittable fields rather than applying a
      repository-wide annotation rewrite.
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
      `Config()` created with no arguments. Do not paper over missing-field
      errors in tests; restore the production model's intended defaults.
    inputs:
      - name: behavior-map
        type: object
      - name: field-migration-results
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
      without erasing behavior." Translate validators to native-v2 decorators
      and signatures while preserving execution mode, ordering, defaults,
      cross-field logic, error messages where asserted, and return values.
      Never delete, empty, bypass, replace with `pass`, or make unconditional a
      validator or any other function body merely to make imports or tests
      succeed. Test valid and invalid inputs for each migrated validator.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate validation
      entry points and serialization." Prefer native-v2 methods such as
      `model_validate`, `model_dump`, `model_dump_json`, `model_copy`,
      `model_construct`, and `model_json_schema` where the receiver is a
      Pydantic model. Preserve options such as aliases, exclusions, unset
      handling, and JSON mode. Confirm that similarly named methods on
      non-Pydantic project objects are not rewritten.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Read `references/native-v2-conversions.md` and follow "Migrate schema,
      introspection, and special models." Handle field introspection,
      set-fields tracking, custom schema hooks, dataclasses, root models,
      recursive aliases, strict unions, and dict-like models individually.
      Preserve public mapping behavior. Keep a plain `Dict[str, T]` alias when
      callers expect a dictionary; use `RootModel` only when a model wrapper is
      truly part of the contract and update callers deliberately if approved.
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
      aliases such as callback or mapping aliases. Validate package-level
      imports and representative recursive model construction after each
      change.
    inputs:
      - name: behavior-map
        type: object
      - name: specialist-migration-results
        type: object
    outputs:
      - name: forward-reference-results
        type: object

  - name: run-a-syntax-and-import-gate-after-every-edit-slice
    description: >
      During every edit step, read `references/native-v2-conversions.md` and
      follow "Run a syntax and import gate after every edit slice." Compile all
      changed Python files, import the smallest affected module, then import its
      public package path. If generated schema dictionaries were edited,
      inspect surrounding delimiters and the entire diff before running tests.
      Stop the slice and repair syntax or import failures immediately.
    outputs:
      - name: syntax-and-import-results
        type: list[object]

  - name: validate-every-edit-slice
    description: >
      After syntax and imports pass, read
      `references/validation-and-completion.md` and follow "Validate every edit
      slice." Run the closest focused tests and direct behavioral probes for
      constructors, aliases, defaults, invalid input, serialization, and schema
      output. Preserve the command's exit status and continue iterating until
      the slice passes.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the complete suite unpiped, classify failures
      by shared root cause, and fix the highest-leverage production issue.
      Prioritize fixture setup errors because one zero-argument model
      construction failure can create many downstream failures. Re-run the
      smallest reproducer, the affected test module, and then the complete
      suite.
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
      shape. Use the first complete traceback from each distinct cluster and
      make one narrow production fix at a time.
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
      differences." Check requiredness, nullable fields, union ordering,
      coercion, equality, private attributes, alias population, serialization,
      enum handling, strict types, dataclass behavior, and validation errors.
      Compare behavior against the repository's tests and public contract
      rather than merely silencing the new error.
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
      after collection succeeds." Search again for forbidden compatibility
      imports and residual v1 APIs, including deprecated calls that no longer
      block collection. Classify every match as production usage, test-only
      compatibility assertion, documentation, unrelated project API, or false
      positive.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Read `references/validation-and-completion.md` and follow "Inspect and
      review the diff." Review every changed file for accidental truncation,
      malformed schema examples, duplicate configuration, lost validators,
      changed public exports, unrelated edits, temporary files, test weakening,
      and broad mechanical damage. Confirm no function body was emptied and no
      production import points to `pydantic.v1`.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Read `references/validation-and-completion.md` and follow "Run the
      complete test suite." Run the authoritative suite directly and unpiped.
      Record its command, exit code, passed, failed, error, skipped, and warning
      counts. If anything fails or errors, return to the first distinct root
      cause and continue the migration; a nonzero exit or incomplete run is not
      success.
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
      gates." Run repository-required formatting checks, linting, type
      checking, generated-file checks, and packaging checks. Do not apply broad
      autoformatting to unrelated files.
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
      native-v2 verification." Confirm the test interpreter imports the target
      Pydantic v2 version; dependency declarations agree; production contains
      no `pydantic.v1` imports; no removed v1 field/configuration APIs remain;
      validators and function bodies retain behavior; representative
      construction, validation, alias, serialization, schema, mapping, and
      recursive-model probes pass; and the final working tree contains no
      unrequested artifacts.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Read `references/validation-and-completion.md` and follow "Audit
      provenance and procedure completeness." Walk the migration inventory,
      baseline evidence, failure clusters, behavior map, edit plan, and every
      applicable instruction in this procedure line by line. Classify each
      distinct item as Mapped, Schema gap, Body drop, or Deliberate drop. Fix
      every Body drop before completion; address any Schema gap through the
      available procedure structure; and record a concrete rationale for every
      Deliberate drop. Confirm every planned slice has corresponding diff and
      validation evidence.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Read `references/validation-and-completion.md` and follow "Report
      completion with evidence." Summarize production changes, compatibility
      decisions, dependency changes, and any intentionally unchanged v1-like
      project APIs. Report exact commands and exit results for the complete
      suite and quality gates. Mention skipped or unavailable gates explicitly.
      Do not claim completion unless the authoritative suite passes, required
      quality gates pass, native-v2 verification passes, and the provenance
      audit has no unresolved Body drop or Schema gap.
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