---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 without compatibility shims, preserving validation behavior, model optionality, aliases, schema metadata, parser behavior, imports, syntax integrity, and the full test suite.

metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 26
    derived_from_traces:
      - "c997561c"
      - "cb2c25e1"
      - "ff6577e9"
      - "738b4882"
      - "23e5cd8a"
      - "7ec14fc1"
      - "fbadf6f2"
      - "bcd6adbe"
      - "512a80b8"
      - "ccc3a201"
      - "2bcb35cc"
      - "093a5290"
      - "1ce8fd14"
      - "66c5f797"
      - "f7f84cae"
      - "5fd83784"

---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 while preserving
  runtime behavior, validation semantics, model optionality, aliases, schema
  metadata, and tests. Remove obsolete APIs such as Field const, v1 Config
  classes, Extra enum configuration, and parse_obj. Use native Pydantic v2
  APIs and ConfigDict, never pydantic.v1 compatibility imports. Keep every
  function operational; an empty or stubbed function body is not a migration.
  Keep the source syntactically valid throughout the work by compiling each
  edited Python file before editing another file or invoking pytest.
trigger_when:
  - Pydantic v2 is installed but imports, model definitions, or tests fail.
  - PydanticImportError appears for BaseSettings or other relocated or removed APIs.
  - PydanticUserError reports that const was removed and Literal should be used.
  - Importing conftest or application modules fails on Field(const=True).
  - Pytest collection fails with a SyntaxError after migration edits.
  - Model configuration emits errors or warnings involving Config, Extra, schema_extra, or allow_population_by_field_name.
  - Optional model fields unexpectedly become required after upgrading Pydantic.
  - AttributeError reports that a model or configuration class has no parse_obj.
  - AttributeError reports that EmailStr has no compatible validate method.
  - pydantic_core validation errors appear during model instantiation or parsing.
  - A dependency update to Pydantic v2 causes targeted or full-suite regressions.
anti_patterns:
  - Re-pointing imports to pydantic.v1 or otherwise using a Pydantic v1 compatibility shim.
  - Emptying, stubbing, deleting, or replacing a function body merely so its module imports.
  - Changing application behavior to avoid implementing the migration.
  - Leaving v1 class Config blocks in migrated models.
  - Leaving extra = Extra.allow or extra = Extra.forbid in model configuration.
  - Using allow_population_by_field_name instead of populate_by_name.
  - Using schema_extra instead of json_schema_extra.
  - Using Field(const=True) instead of a Literal annotation.
  - Forgetting to import Literal or ConfigDict where they are used.
  - Treating every Optional annotation as optional in Pydantic v2 without providing a default.
  - Blindly adding None defaults to fields that were intentionally required.
  - Replacing EmailStr with str when email validation is part of the required behavior.
  - Calling EmailStr.validate directly under its Pydantic v1 calling convention.
  - Leaving parse_obj, schema, dict, json, or other deprecated model APIs without checking their v2 replacements.
  - Running an unreviewed regex or sed rewrite across nested Config blocks or large schema_extra dictionaries.
  - Generating migration scripts that can corrupt indentation, quoting, braces, or parentheses.
  - Continuing batch edits after any generated rewrite produces a syntax error.
  - Appending guessed closing delimiters to repair syntax instead of restoring the intended structure.
  - Repairing a malformed ConfigDict call without comparing it to the original complete Config block.
  - Making broad edits before reading the task, dependency files, tests, and complete traceback.
  - Migrating BaseSettings before confirming that the repository actually uses it.
  - Fixing one reported v1 symbol while leaving the rest of the repository uninventoried.
  - Running tests before verifying that all changed files compile and critical modules import.
  - Treating pytest collection output as the primary syntax checker after editing Python files.
  - Trusting truncated pytest output or a targeted test as proof that the suite passes.
  - Stopping with deprecation warnings or forbidden v1 imports merely because tests are green.
steps:
  - name: establish-clean-baseline
    description: >
      Read the task and inspect git status and git diff before editing. Record
      pre-existing changes so they are not overwritten. Identify the project
      test command, supported Python versions, package manager, and migration
      dependency files such as pyproject.toml, lock files, tox.ini, noxfile.py,
      requirements files, and requirements-v2.txt. Do not assume the globally
      installed Pydantic version is the version the project declares.

  - name: establish-syntax-baseline
    description: >
      Before making migration edits, compile the tracked production Python
      source and import the package if the current tree permits it. If a
      SyntaxError already exists, inspect git diff and the version-control
      baseline for that exact file before doing any further migration work.
      Distinguish pre-existing user changes from malformed migration changes.
      Restore only the damaged structure, preserving intentional user work.
      Do not continue until every currently edited production file either
      compiles or has been explicitly identified as a pre-existing failure.

  - name: inspect-project-specific-migration-contract
    description: >
      Read requirements-v2.txt and relevant comments in pyproject.toml or lock
      files before changing dependency constraints. If the repository supplies
      a post-migration dependency set or upper pins, treat it as the source of
      truth. Preserve intentional compatibility pins rather than upgrading
      unrelated dependencies. Confirm whether the task expects a lock-file
      update and use the repository's package manager to produce it.

  - name: verify-runtime-dependencies
    description: >
      Run a small command that prints pydantic.__version__ in the same
      environment used by tests and confirm it is 2.x. If the project contract
      explicitly requires Pydantic 2.7 or newer, verify version >=2.7.0;
      otherwise honor its declared Pydantic v2 range. Check pydantic-settings
      only when BaseSettings is actually used. Inspect sys.path and imports for
      accidental local modules or pydantic.v1 shims.

  - name: run-baseline-tests
    description: >
      Run the repository's canonical test command before editing when the
      current tree is executable. Capture the complete first traceback, warning
      summary, and test count. If collection fails, record the import or model
      definition that blocks collection. Read the failing test and production
      code before deciding on a change.

  - name: build-complete-v1-api-inventory
    description: >
      Search tracked Python files and relevant templates for all Pydantic
      imports and APIs, not only the first error. Include BaseModel,
      BaseSettings, ConfigDict, Extra, Field, EmailStr, validators, constrained
      types, parse_obj, schema, dict, json, class Config, const,
      allow_population_by_field_name, schema_extra, orm_mode, validate_all,
      anystr options, smart_union, fields configuration, and forward-reference
      methods. Inspect every match in context and distinguish production source,
      tests, templates, fixtures, generated golden records, and documentation.

  - name: grep-for-const-usage-in-field-definitions
    description: >
      Search for const=True, const with flexible whitespace, and Field calls
      containing const across all Python source and model-generating templates.
      Use commands equivalent to grep -R patterns for "const[[:space:]]*=" and
      "Field(.*const". Read each containing class, including inherited fields,
      before changing its annotation.

  - name: grep-for-emailstr-and-other-v1-types
    description: >
      Search for EmailStr, validator, root_validator, conint, constr, confloat,
      StrictInt, StrictStr, and direct calls to type validate methods. Determine
      whether each use performs real validation, represents only OpenAPI format
      metadata, or is dead compatibility code. Do not infer that an empty grep
      result succeeded when grep exits 1 for no matches.

  - name: grep-for-basesettings-imports
    description: >
      Search for imports and inheritance involving BaseSettings. Include
      multiline imports and aliases, not only the exact text "from pydantic
      import BaseSettings". If there are no matches, do not add
      pydantic-settings or invent a settings migration.

  - name: grep-for-config-class-usage
    description: >
      Find every nested class Config and read each complete block. Search
      separately for Extra.allow, Extra.forbid, allow_population_by_field_name,
      schema_extra, arbitrary_types_allowed, aliases, and parse_obj calls.
      Record the exact settings and large nested schema examples so none are
      dropped during conversion.

  - name: inventory-v2-optionality-changes
    description: >
      Inspect BaseModel fields annotated Optional[T], Union[T, None], or T |
      None. In Pydantic v2 these annotations remain required unless they have a
      default. Determine which fields were implicitly optional under Pydantic
      v1 and must become "= None" or Field(default=None, ...). Preserve fields
      that were deliberately required while accepting None. Also review default
      factories, aliases, mutable defaults, and inherited fields.

  - name: update-dependency-declarations
    description: >
      Change the project dependency from Pydantic v1 to the Pydantic v2 range
      required by the repository's migration contract. Add pydantic-settings
      only if migrated BaseSettings code requires it. Apply documented upper
      pins from the supplied post-migration dependency set. Update the lock file
      through the package manager rather than editing lock metadata by hand,
      then verify the resolved versions.

  - name: migrate-basesettings-imports
    description: >
      Where BaseSettings is genuinely used, import BaseSettings and
      SettingsConfigDict from pydantic_settings, update settings classes to use
      settings_config = SettingsConfigDict only if that is the repository's
      naming convention, otherwise use the documented model_config attribute,
      and translate environment-related Config options accurately. Never import
      BaseSettings from pydantic.v1. Keep aliases, prefixes, environment files,
      case sensitivity, and custom settings sources behaviorally equivalent.

  - name: replace-const-fields-with-literal-types
    description: >
      Replace each Field const constraint with a Literal annotation while
      retaining its default, alias, description, and other Field arguments.
      For example, change name = Field(default="", const=True) to
      name: Literal[""] = Field(default=""), and change
      param_in = Field(default=ParameterLocation.HEADER, const=True, alias="in")
      to param_in: Literal[ParameterLocation.HEADER] =
      Field(default=ParameterLocation.HEADER, alias="in"). Import Literal from
      typing. When overriding an inherited model field, include the explicit
      annotation because Pydantic v2 rejects unannotated field overrides.

  - name: convert-config-classes-carefully
    description: >
      Convert one model at a time from nested class Config to
      model_config = ConfigDict(...). Translate extra = Extra.allow to
      extra="allow", Extra.forbid to extra="forbid",
      allow_population_by_field_name=True to populate_by_name=True, and
      schema_extra to json_schema_extra. Preserve arbitrary_types_allowed and
      every other supported setting. Import ConfigDict and remove Extra only
      after its final use disappears. Make small structural edits; do not use a
      broad regex over multiline configuration or nested schema examples.

  - name: preserve-json-schema-metadata
    description: >
      When moving schema_extra to json_schema_extra, preserve the complete
      dictionary byte-for-byte in meaning, including examples, aliases, nested
      component names, and closing delimiters. Compile the file immediately
      after editing a large configuration block. If syntax breaks, restore the
      file or patch from the original diff rather than guessing parentheses.

  - name: validate-each-edited-file-immediately
    description: >
      After editing any Python file, run py_compile on that exact file before
      editing another file. If it fails, stop the migration batch and inspect
      the complete reported region together with the opening delimiter it
      references. Compare the edited file against git diff and, when useful,
      the baseline content from version control. Restore balanced braces,
      brackets, parentheses, strings, and indentation from the known structure;
      never append speculative delimiters. Re-run py_compile until the file
      passes, then import its module when feasible. This gate is mandatory for
      large json_schema_extra dictionaries and files modified by scripts.

  - name: constrain-mechanical-rewrites
    description: >
      Prefer explicit per-file edits for Config blocks and schema examples. If
      a mechanical script is justified for simple repeated changes, first run
      it against one representative file or a temporary copy, inspect the
      complete diff, compile the result, and only then consider another file.
      Stop at the first malformed result. Never run cleanup scripts on already
      damaged syntax, and never use regex to parse nested Python dictionaries
      or infer their closing delimiters.

  - name: preserve-population-by-alias-and-name
    description: >
      Models that expose aliased fields such as "in" must continue accepting
      the intended field names and aliases. Set populate_by_name=True only where
      the v1 model used allow_population_by_field_name or tests require the
      behavior. Test construction through both the alias and Python attribute
      name, plus serialization by alias where relevant.

  - name: preserve-arbitrary-types-allowed
    description: >
      Retain arbitrary_types_allowed=True in model_config for models containing
      framework or library objects such as FastAPI UploadFile, Jinja2
      Environment, callbacks, or other non-Pydantic types. Do not add it
      globally as a shortcut; apply it only to models whose prior configuration
      or actual fields require it.

  - name: restore-v1-optional-field-semantics
    description: >
      Add explicit None defaults to fields that were non-required under
      Pydantic v1 solely because they were annotated Optional. Use
      "field: Optional[T] = None" for plain fields and
      "field: Optional[T] = Field(default=None, alias=...)" when Field metadata
      is present. Do not alter required non-Optional fields or intentionally
      required nullable fields. Validate representative minimal model inputs
      after each related group of edits.

  - name: update-parser-code-for-v2
    description: >
      Replace BaseModel.parse_obj(data) with model_validate(data). Replace
      schema() with model_json_schema() where schema generation is intended.
      Replace dict() with model_dump(), json() with model_dump_json(), and
      parse_raw() with model_validate_json() where encountered and where their
      argument behavior is equivalent. Review include, exclude, alias, and
      exclude_none options rather than applying textual substitutions blindly.
      A call on a project class named Config must be assessed separately from a
      nested Pydantic configuration class.

  - name: migrate-validators
    description: >
      Replace @validator with @field_validator and @root_validator with
      @model_validator only where they occur. Translate pre, always,
      each_item, skip_on_failure, signatures, return values, and classmethod
      usage according to Pydantic v2 semantics. Add tests or run existing tests
      for invalid as well as valid inputs so validators are not merely
      importable.

  - name: update-emailstr-and-direct-type-validation
    description: >
      Do not call EmailStr.validate using the Pydantic v1 signature. If email
      validation is required, validate through TypeAdapter(EmailStr) or a
      containing BaseModel and preserve validation errors. If a project uses
      EmailStr only as an internal marker while intentionally accepting any
      OpenAPI string, replace that specific reference with str as required by
      its tests and design. Do not globally replace EmailStr with str because
      that silently removes validation.

  - name: update-constrained-and-removed-types
    description: >
      Review constrained types and removed or relocated helpers found in the
      inventory. Prefer Annotated with Field constraints where required by
      Pydantic v2, and retain strictness, bounds, lengths, patterns, and numeric
      behavior. Do not change StrictInt or StrictStr merely because they were
      included in the search if they remain supported and behaviorally correct.

  - name: update-forward-reference-rebuilds
    description: >
      Search for update_forward_refs and unresolved forward references. Replace
      obsolete rebuild calls with model_rebuild where necessary, after all
      dependent types are importable. Exercise imports of the package-level
      schema module so cyclic model definitions are checked together.

  - name: preserve-functions-and-error-paths
    description: >
      Inspect every edited function and ensure its original work remains
      implemented. Never replace a parser, validator, conversion function, or
      error handler with pass, an empty return, a constant success value, or a
      swallowed exception just to make collection succeed. The grader rejects
      empty function bodies even if imports and tests appear to pass. Preserve
      error types and useful context unless Pydantic v2 requires a deliberate,
      tested adaptation.

  - name: format-and-review-each-edit-batch
    description: >
      After each small batch, inspect git diff for duplicate ConfigDict imports,
      accidental json_json_schema_extra names, lost fields, malformed
      indentation, changed examples, unmatched delimiters, empty functions, and
      unrelated rewrites. Run the repository formatter or import sorter only on
      intended files and inspect its diff. Keep generated files consistent with
      their templates if both are part of the tested source. Do not mark a batch
      complete unless every edited file has passed its immediate compile gate.

  - name: verify-all-files-compile
    description: >
      Compile all relevant tracked Python files before running pytest. Prefer a
      null-delimited loop or compileall over shell expansion that may truncate
      or mishandle paths. Do not append "|| true": a compile failure must stop
      progress. Fix the first syntax error, re-run compilation, and continue
      until every relevant file compiles. A mismatch such as a closing
      parenthesis against an opening dictionary brace requires reconstructing
      the intended expression from the diff or baseline, not adding another
      parenthesis.

  - name: run-critical-import-checks
    description: >
      Import the package configuration, parser, top-level OpenAPI schema model,
      representative schema subclasses, and any settings model. If settings are
      used, verify "from pydantic_settings import BaseSettings,
      SettingsConfigDict". Verify ConfigDict and Field imports from pydantic;
      never attempt to import the built-in str from pydantic. Instantiate small
      representative models so class-definition errors and missing defaults are
      caught before pytest collection.

  - name: test-model-behavior-directly
    description: >
      Exercise representative cases for extra-field handling, required fields,
      formerly implicit optional fields, Literal constants, aliases,
      populate_by_name, arbitrary types, JSON schema examples, and parser
      validation. Check both accepted and rejected inputs. Confirm invalid
      values still fail rather than merely checking that valid imports work.

  - name: run-targeted-tests-iteratively
    description: >
      Run the smallest relevant tests for each failure category after its fix.
      Read complete tracebacks and relevant test assertions before editing.
      Resolve failures by root cause; do not weaken tests, suppress warnings
      indiscriminately, or bypass production code. Re-run the targeted group
      until it passes, then proceed to broader tests. If collection reports a
      SyntaxError, return to the compile gate immediately rather than changing
      model behavior or test configuration.

  - name: run-full-test-suite
    description: >
      Run the repository's complete canonical test suite with untruncated
      output. During diagnosis, using pytest -x with an informative traceback
      is acceptable, but repeat after each fix until no next failure remains.
      Finish with a run that does not stop early and verify its exit code,
      passed count, failures, errors, skips, and warnings. For this historical
      codebase, successful graded attempts reached 445 passing tests; if the
      collected count differs, explain it from the current repository rather
      than assuming partial success is complete.

  - name: run-static-and-package-checks
    description: >
      Run the repository's configured formatter check, import sorting check,
      linter, type checker, and package build when they are part of CI. Test in
      the declared dependency environment, not only the global interpreter.
      Resolve migration-introduced warnings and errors without unrelated
      refactoring.

  - name: scan-for-forbidden-residue
    description: >
      Search the final tree again for pydantic.v1, Field const, v1 Config
      classes, Extra enum configuration, allow_population_by_field_name,
      schema_extra, obsolete validator decorators, BaseSettings imported from
      pydantic, and deprecated parser calls. Inspect each remaining match;
      comments, documentation, fixtures, and compatibility tests still require
      an explicit decision. Confirm no production function was emptied or
      stubbed.

  - name: inspect-final-diff-and-retest
    description: >
      Review the complete final diff against the initial inventory. Confirm
      dependency changes are intentional, every original configuration option
      and schema example survived, optionality is correct, imports are clean,
      delimiters are balanced, and no generated or unrelated files were
      corrupted. Re-run per-file compilation, whole-tree compilation, critical
      imports, and the complete suite after the final edit. Declare success only
      when all required checks pass, native Pydantic v2 APIs are used, no
      pydantic.v1 shim remains, and all function bodies retain their behavior.
```