---
name: pydantic-v2-migration
description: Migrate a Python codebase from Pydantic v1 APIs and semantics to native Pydantic v2, including models, configuration, fields, validators, parsing, serialization, forward references, dependencies, and tests. Use when a Pydantic v2 upgrade causes import, collection, validation, schema, fixture, constructor, syntax, or behavioral failures, including recovery from an incomplete or malformed prior migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 19
  derived_from_traces: "9e3ddb8a, d2ac33d9, f577bbbd, d9221446, 7685501b, 2987f213, eb757c7e, ee0d2860, c05f708c, 071e97ea"
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to native Pydantic v2 so imports,
  model construction, default construction, validation, parsing, serialization,
  generated schemas, aliases, root models, type aliases, forward references,
  fixtures, and repository tests preserve intended behavior. Complete the
  migration without redirecting production imports to `pydantic.v1`; without
  deleting, emptying, bypassing, replacing with `pass`, or otherwise
  neutralizing validators or any other function bodies; without weakening
  production behavior or rewriting tests merely to accept regressions; without
  corrupting source through broad mechanical edits; and without stopping after
  searches, research, investigation, planning, an import check, compilation,
  test collection, focused tests, or a partially passing suite.

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
  - Never redirect production imports to `pydantic.v1`, use a compatibility namespace as the migration, or hide unresolved v1 behavior behind an adapter.
  - Never empty, delete, bypass, replace with `pass`, or otherwise neutralize a validator or any other function body merely to make imports or tests pass.
  - Do not edit tests simply to accept behavior that changed accidentally; change tests only when the task explicitly changes the contract and repository evidence supports it.
  - Do not stop after inventory, research, a plan, or a summary. Continue using tools and making validated edits until the completion gates pass or a concrete external blocker is demonstrated.
  - Do not treat import success, syntax compilation, collection success, one focused test, or a partially passing suite as completion.
  - Do not pipe an authoritative test command through `head`, `tail`, `grep`, or an unguarded `tee`; those pipelines can hide the test runner exit status and truncate the decisive traceback.
  - Do not install or replace broad dependency environments before checking repository-provided requirements, lockfiles, and commands.
  - Do not run uncontrolled repository-wide regex or shell rewrites across nested Config blocks or schema examples; indentation-sensitive edits can silently corrupt Python.
  - Do not add `model_config` inside a nested v1 `Config` class, leave both configuration systems active, or strand a large `json_schema_extra` dictionary outside its intended assignment.
  - Do not convert ordinary mapping aliases to `RootModel` without checking callers, equality, iteration, indexing, serialization, and annotations.
  - Do not call `model_rebuild()` indiscriminately on every exported symbol; exported aliases such as dictionaries and unions are not model classes.
  - Do not use `ClassVar` as a substitute for a validated constant field when callers and schemas require the field to remain part of the model.
  - Do not weaken required fields to optional defaults solely because existing fixtures fail; first determine whether v1 supplied an implicit default or the fixture exposed a real contract.
  - Do not repeatedly perform generic web research after repository evidence identifies the next failure. Consult authoritative Pydantic documentation only for a specific unresolved semantic question.
  - Do not create migration summary files or unrelated artifacts unless the repository or user requests them.

steps:
  - name: establish-repository-root-and-state
    description: >
      Read `references/safety-and-baseline.md` and follow "Establish repository
      root and state." Confirm the actual repository root, current directory,
      Python executable, Pydantic version and import location, branch, tracked
      modifications, untracked files, and available project metadata. Keep a
      stable absolute repository path and reuse it exactly; do not guess similar
      paths such as `agent-worm` or insert accidental spaces into `cd` commands.
    outputs:
      - name: repository-state
        type: object

  - name: recover-a-partially-edited-working-tree
    description: >
      If tracked files are already modified, follow "Recover a partially edited
      working tree" in `references/safety-and-baseline.md`. Inspect the diff and
      syntax before deciding what to preserve. Distinguish user work from prior
      migration edits, never discard unrelated changes, and repair malformed
      prior edits before layering additional conversions on top. Re-run status
      after recovery.
    outputs:
      - name: recovered-working-tree
        type: object

  - name: identify-authoritative-project-commands
    description: >
      Follow "Identify authoritative project commands" in
      `references/safety-and-baseline.md`. Inspect project configuration,
      workflows, task definitions, test configuration, migration requirement
      files, and contributor documentation. Prefer the repository's actual test
      and quality commands over invented substitutes. Record environment
      variables, path arguments, exclusions, and temporary-directory settings
      that are part of those commands.
    outputs:
      - name: project-commands
        type: object

  - name: establish-the-unpiped-baseline
    description: >
      Follow "Establish the unpiped baseline" in
      `references/safety-and-baseline.md`. Run the authoritative command without
      a status-masking output pipeline and capture its real exit code and full
      first traceback. If logging is necessary, use shell support such as
      `set -o pipefail` or inspect `PIPESTATUS`. Do not infer success from a
      wrapper command returning zero after `head`, `tail`, `grep`, or `tee`.
      Use the first actionable failure to begin editing instead of repeatedly
      rerunning the same unchanged command.
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
      `references/safety-and-baseline.md`. Replace each constant field with an
      actual `Literal[...]` annotation while preserving it as a model field,
      its default, aliases, and expected enum value. For example, migrate a
      fixed empty name to `name: Literal[""] = ""` and a fixed enum member to
      `param_in: Literal[ParameterLocation.HEADER] =
      ParameterLocation.HEADER`. Import `Literal` from the compatibility range
      appropriate to the project. Do not use `ClassVar`, which removes the
      value from Pydantic fields and changes validation and schema behavior.
      Compile and rerun collection immediately after the focused edit.
    outputs:
      - name: const-field-edits
        type: list[string]

  - name: inspect-project-constraints
    description: >
      Follow "Inspect project constraints" in
      `references/safety-and-baseline.md`. Determine supported Python versions,
      intended Pydantic v2 range, dependency manager, lockfile policy, generated
      code constraints, typing compatibility, public API expectations, and
      whether schema snapshots or generated fixtures are authoritative. Do not
      introduce syntax unavailable to the minimum supported Python version.
    outputs:
      - name: compatibility-target
        type: object
      - name: dependency-files
        type: list[string]

  - name: synchronize-the-target-environment
    description: >
      Ensure the active test interpreter actually uses the intended Pydantic v2
      dependency set. Prefer a repository-provided migration requirements file
      or existing environment command over ad hoc package installation. Recheck
      `sys.executable`, `pydantic.__version__`, and `pydantic.__file__`
      afterward. Update declared dependency constraints when required, but do
      not claim completion while a committed lockfile still resolves Pydantic
      v1 unless repository policy explicitly treats that lockfile as out of
      scope. Avoid installing an unrelated dependency manager or recreating the
      whole environment when the supplied environment is already suitable.
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
      `references/safety-and-baseline.md`. Search production code, generated
      sources, tests, templates, and documentation where relevant for imports,
      BaseModel subclasses, dataclasses, validators, fields, Config classes,
      `Extra`, aliases, schema metadata, parsing and serialization methods,
      construction methods, root models, generic models, forward references,
      type aliases, private attributes, field introspection, strict types, and
      custom schema hooks. Include at least `Field(const=...)`, `min_items`,
      `max_items`, `regex`, `allow_mutation`, `allow_population_by_field_name`,
      `schema_extra`, `orm_mode`, `validate_all`, `parse_obj`, `parse_raw`,
      `from_orm`, `dict`, `json`, `copy`, `construct`, `schema`,
      `update_forward_refs`, `__fields__`, and `__fields_set__`. Treat grep exit
      code 1 for no matches as information rather than a migration failure.
    outputs:
      - name: migration-inventory
        type: object

  - name: inspect-model-relationships-and-public-behavior
    description: >
      Follow "Inspect model relationships and public behavior" in
      `references/safety-and-baseline.md`. Trace imports, inheritance,
      recursive models, exported aliases, parser entry points, fixture
      constructors, aliases accepted by callers, defaults, serialization shape,
      dictionary-like behavior, and generated JSON Schema. Read representative
      tests before changing semantics. In particular, identify models whose
      defaults permit minimal fixture construction, fields whose aliases must
      also accept Python names, and mapping aliases consumed as ordinary
      dictionaries.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: behavior-map
        type: object

  - name: form-an-executable-slice-plan
    description: >
      Follow "Form an executable slice plan" in
      `references/safety-and-baseline.md`. Order work by the active failure:
      collection blockers first, then configuration and field conversions,
      validation entry points, forward references and special models, semantic
      regressions, and cleanup. Define a focused validation command for every
      slice. Keep slices small enough to review and revert. This plan is an
      execution aid, not a stopping point: begin the first edit in the same
      attempt instead of ending after presenting the plan.
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
      configuration safely." Convert nested v1 configuration to class-level
      `model_config = ConfigDict(...)`, mapping `Extra.allow` to
      `extra="allow"`, `allow_population_by_field_name` to `populate_by_name`,
      and `schema_extra` to `json_schema_extra`. Preserve all model-specific
      settings and schema examples. Remove obsolete `Extra` imports only after
      all uses are gone. For models with large schema-example dictionaries,
      edit one complete block at a time and inspect its opening and closing
      delimiters. Never leave both `class Config` and `model_config` as
      competing configurations. Compile each changed file before proceeding.
    inputs:
      - name: migration-plan
        type: object
    outputs:
      - name: configuration-migration-results
        type: object

  - name: migrate-fields-annotations-and-optionality
    description: >
      Follow "Migrate fields, annotations, and optionality" in
      `references/native-v2-conversions.md`. Convert removed constraints such
      as `min_items` and `max_items` to their v2 equivalents such as
      `min_length` and `max_length`; convert `const` fields to `Literal`; and
      preserve aliases, strictness, default factories, schema names, and
      requiredness. Audit every `Optional[T]` field because Pydantic v2 does not
      infer a default of `None`; add `= None` only when repository behavior or
      v1 construction semantics establish that the field is optional. Preserve
      required fields when the contract requires them. Replace mutable model
      defaults with `Field(default_factory=...)` when needed, including config
      collections, while preserving constructor behavior.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: field-migration-results
        type: object

  - name: migrate-validators-without-erasing-behavior
    description: >
      Follow "Migrate validators without erasing behavior" in
      `references/native-v2-conversions.md`. Translate v1 validators to
      `field_validator`, `model_validator`, or supported compatibility forms
      while preserving pre/post timing, per-item behavior, ordering, defaults,
      cross-field access, returned values, exceptions, and side effects. Read
      the complete original body before editing and compare the complete body
      afterward. Never delete, empty, replace with `pass`, short-circuit, or
      bypass a validator or any other function merely to make the module
      import. Add focused valid and invalid input tests when existing coverage
      does not prove preserved behavior.
    inputs:
      - name: behavior-map
        type: object
    outputs:
      - name: validator-migration-results
        type: object

  - name: migrate-validation-entry-points-and-serialization
    description: >
      Follow "Migrate validation entry points and serialization" in
      `references/native-v2-conversions.md`. Replace `parse_obj` with
      `model_validate` and migrate other deprecated methods only after checking
      their arguments and output contracts. Use `model_dump`,
      `model_dump_json`, `model_copy`, `model_construct`, and
      `model_json_schema` where appropriate. Preserve aliases, exclusion flags,
      JSON modes, custom encoders, exception handling, and validation error
      formatting. Do not mechanically replace unrelated `.dict()`, `.copy()`,
      or `.json()` calls belonging to normal Python objects.
    inputs:
      - name: migration-inventory
        type: object
    outputs:
      - name: parsing-and-serialization-results
        type: object

  - name: migrate-schema-introspection-and-special-models
    description: >
      Follow "Migrate schema, introspection, and special models" in
      `references/native-v2-conversions.md`. Update field introspection and
      forward-reference APIs, and handle recursive models, custom schema hooks,
      generic models, dataclasses, type adapters, root models, and exported type
      aliases deliberately. Prefer retaining a plain mapping alias when callers
      expect dictionary equality, indexing, iteration, and direct parser input;
      introduce `RootModel` only when root-model semantics are truly required.
      Call `model_rebuild()` only on actual Pydantic model classes and provide
      the required namespace when recursive names are not resolvable. Do not
      invoke model methods on dictionary, union, or callback aliases merely
      because they are exported from a schema package.
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
      slice." First compile the exact edited files or package, then run the
      smallest test that exercises the change, then rerun collection or the
      current failing command. Preserve real exit status. If compilation fails,
      stop adding migrations and repair the syntax from the reported line using
      the diff and surrounding source. Do not continue broad edits while files
      are malformed.
    outputs:
      - name: focused-test-results
        type: list[object]

  - name: triage-the-first-post-collection-suite
    description: >
      As soon as collection succeeds, read
      `references/validation-and-completion.md` and follow "Triage the first
      post-collection suite." Run the authoritative tests and group failures by
      root cause rather than patching each assertion independently. Prioritize
      shared model construction, missing defaults, alias population, forward
      references, mapping aliases, and fixture construction because one defect
      can produce many failures. Fix production code before changing tests
      unless repository evidence shows that the intended contract itself
      changed.
    outputs:
      - name: post-collection-triage
        type: object

  - name: investigate-v2-semantic-differences
    description: >
      After removed-API and import failures are resolved, follow "Investigate v2
      semantic differences" in `references/native-v2-conversions.md`. Check
      coercion, unions, enum handling, strict types, equality, serialization,
      alias precedence, optionality, defaults, extra fields, nested models, and
      JSON Schema differences against repository expectations. Use a minimal
      Python reproduction and authoritative Pydantic v2 documentation only when
      the observed repository behavior remains ambiguous. Apply the smallest
      behavior-preserving production change and rerun the focused regression.
    inputs:
      - name: focused-test-results
        type: list[object]
    outputs:
      - name: semantic-migration-results
        type: object

  - name: repeat-inventory-after-collection-succeeds
    description: >
      Follow "Repeat inventory after collection succeeds" in
      `references/validation-and-completion.md`. Re-run the complete v1-pattern
      searches after imports and collection work, because the initial scan may
      have been interrupted or obscured by syntax failures. Classify every
      residual occurrence as production usage, test usage, documentation,
      generated output, unrelated method name, or deliberate compatibility
      requirement. Remove stale production v1 APIs and imports without
      mechanically changing false positives.
    outputs:
      - name: residual-inventory
        type: object

  - name: inspect-and-review-the-diff
    description: >
      Follow "Inspect and review the diff" in
      `references/validation-and-completion.md`. Review every changed file and
      diff hunk for accidental deletions, duplicated imports, malformed import
      lists, missing commas, indentation damage, truncated schema examples,
      moved delimiters, unintended test changes, broad formatting churn,
      empty function bodies, `pass` substitutions, and unrelated artifacts.
      Compare validators and other nontrivial bodies before and after. Revert
      incidental edits and compile all changed Python files.
    outputs:
      - name: diff-review
        type: object

  - name: run-the-complete-test-suite
    description: >
      Follow "Run the complete test suite" in
      `references/validation-and-completion.md`. Run the complete authoritative
      suite unpiped with the required environment and arguments. Confirm its
      actual zero exit status and record the passed, failed, skipped, and error
      counts. A focused subset, collection-only run, ignored integration suite,
      or output ending in many dots is not proof of completion. If the suite
      fails, return to root-cause triage and continue editing rather than
      reporting a partial success.
    outputs:
      - name: full-suite-result
        type: object

  - name: run-project-quality-gates
    description: >
      After the complete suite passes, follow "Run project quality gates" in
      `references/validation-and-completion.md`. Run the repository's configured
      formatting checks, linting, type checking, generated-file checks, package
      build, and other CI-equivalent gates that are available. Use check modes
      where possible so validation does not rewrite unrelated files. Repair
      migration-caused failures and rerun the affected gate.
    outputs:
      - name: quality-gate-results
        type: list[object]

  - name: perform-final-native-v2-verification
    description: >
      Follow "Perform final native-v2 verification" in
      `references/validation-and-completion.md`. Verify the active interpreter
      imports the intended Pydantic v2 version, declared dependency files and
      lockfiles agree with the target, production code does not import
      `pydantic.v1`, removed v1 APIs are absent or explicitly justified, all
      changed Python files compile, and representative model validation,
      aliases, serialization, JSON Schema, and recursive-model behavior work.
      Explicitly search for emptied bodies and migration bypasses; passing tests
      do not excuse either.
    outputs:
      - name: native-v2-verification
        type: object

  - name: audit-provenance-and-procedure-completeness
    description: >
      Follow "Audit provenance and procedure completeness" in
      `references/validation-and-completion.md`. Walk the migration inventory,
      behavior map, original failure evidence, and every procedure step against
      the final diff. Classify each distinct item as migrated, verified
      unchanged, false positive, explicitly out of scope, or unresolved.
      Confirm every source requirement and guardrail remains represented and
      that no planned slice was abandoned after research or planning. Any
      unresolved item prevents completion unless a concrete external blocker is
      documented.
    outputs:
      - name: provenance-audit
        type: object

  - name: report-completion-with-evidence
    description: >
      Follow "Report completion with evidence" in
      `references/validation-and-completion.md`. Report the Pydantic version,
      files and behavior categories changed, exact authoritative suite command
      and result, quality-gate results, residual-search result, and any genuine
      limitations. Keep the report concise and evidence-based. Do not say
      "task completed" when the complete suite or required quality gates did not
      pass; instead report the exact blocker and the latest failing command.
    outputs:
      - name: migration-report
        type: object
```