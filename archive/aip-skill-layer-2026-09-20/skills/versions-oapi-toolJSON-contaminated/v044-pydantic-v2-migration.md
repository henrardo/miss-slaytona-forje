---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 without compatibility shims, preserving validation behavior, model optionality, aliases, schema metadata, parser behavior, inheritance, forward references, circular imports, syntax integrity, and the full test suite.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 44
    derived_from_traces:
      - "c997561c"
      - "cb2c25e1"
      - "ff6577e9"
      - "738b4882"
      - "23e5cd8a"
      - "0c9c470c"
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
      - "851f9d93"
      - "13f5ed82"
      - "93a1dc43"
      - "b0109ff8"
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 while preserving
  runtime behavior, validation semantics, model optionality, aliases, schema
  metadata, parser behavior, model inheritance, importability,
  forward-reference resolution, and tests. Remove obsolete APIs such as Field
  const, v1 Config classes, Extra enum configuration, parse_obj, and v1
  root-model declarations. Use native Pydantic v2 APIs, ConfigDict, and
  RootModel where appropriate; never use pydantic.v1 compatibility imports.
  Keep every function operational; an empty or stubbed function body is not a
  migration and is rejected even when tests appear green. Clear import-time
  blockers such as Field(const=True) before lower-priority configuration work,
  because one remaining class-definition error prevents conftest collection
  and conceals useful failures. In this codebase the first known blocker is
  Header.name and Header.param_in in header.py; migrate both to Literal while
  retaining Header(Parameter), then compile and fresh-import before doing any
  bulk Config migration. Preserve each model's original base class: changing
  an inherited model such as Header(Parameter) into Header(BaseModel) can
  discard fields and behavior, while referring to BaseModel without importing
  it causes a NameError that py_compile cannot detect. Likewise, removing
  Extra from an import while an unconverted class Config still evaluates
  Extra.allow or Extra.forbid causes a class-definition NameError that
  py_compile cannot detect. Convert each Config block and its imports as one
  atomic edit, then fresh-import the exact module and package entry point.
  Keep source syntactically valid by compiling each edited Python file
  immediately after every edit, scripted rewrite, formatter run, or
  import-sort operation, then import edited model modules in a fresh process
  before editing another file. A batch rewrite that introduces one
  IndentationError can reduce the suite to zero tests, so never trust a
  migration script's success message; compile every file it touched and stop
  at the first error before making further changes. In particular, replacing
  only the first line of a nested Config block with model_config while leaving
  its former attributes indented beneath it creates invalid source such as a
  standalone over-indented populate_by_name assignment. Convert the complete
  block structurally and validate the latest contents immediately. Preserve
  deliberate TYPE_CHECKING boundaries and resolve cyclic annotations without
  mutual runtime imports. Treat zero-argument model construction failures such
  as Config() raising ValidationError as evidence that v1 implicit optionality
  was not preserved; inspect every missing field and its callers before
  proceeding. Also reproduce the exact high-fan-out Project construction used
  by tests: Config() succeeding alone does not prove Project(...) accepts its
  historical minimal arguments. Resume useful pre-existing migration work from
  the working tree instead of assuming a clean checkout: inspect each diff,
  retain validated changes, and fix the current topmost blocker without
  erasing unrelated work. Keep discovery bounded: once the blocker, inventory,
  and project-specific migration evidence are known, begin small validated
  edits rather than repeatedly grepping, writing planning documents, or
  restarting the investigation. Continue through the entire migration ledger
  after each successful representative edit; a partially converted schema
  package and 310 or 311 passing tests are intermediate states, not completion.
  A sequence of compile-only edits with no collection or test invocation
  provides zero suite evidence and must not be reported as progress.
  Do not end an attempt after announcing a plan: use the available tools to
  make and validate at least the highest-priority safe edit.
trigger_when:
  - Pydantic v2 is installed but imports, model definitions, or tests fail.
  - PydanticImportError appears for BaseSettings or another relocated or removed API.
  - PydanticUserError reports that const was removed and Literal should be used.
  - PydanticUserError reports that a model with a __root__ field must use RootModel.
  - Importing conftest or application modules fails on Field(const=True).
  - Importing a model fails with NameError because Extra, BaseModel, ConfigDict, Literal, RootModel, or another class-definition dependency is not defined.
  - Importing conftest or a package schema module fails with a partially initialized module or circular import error.
  - A forward annotation is undefined during schema generation or model rebuilding.
  - Pytest collection fails with SyntaxError or IndentationError after migration edits.
  - An IndentationError points at a leftover Config attribute immediately below model_config.
  - A SyntaxError reports mismatched parentheses and dictionary braces in model_config or json_schema_extra.
  - A generated migration rewrite reports success but one of its output files no longer compiles.
  - Model configuration emits errors or warnings involving Config, Extra, schema_extra, or allow_population_by_field_name.
  - Optional model fields unexpectedly become required after upgrading Pydantic.
  - Config() or another formerly valid minimal model construction raises ValidationError for missing Optional fields.
  - Test fixtures fail while constructing a default configuration object before tested behavior runs.
  - Test fixtures fail while constructing Project with Config(), an OpenAPI object, and metadata.
  - AttributeError reports that a model or configuration class has no parse_obj.
  - AttributeError reports that EmailStr has no compatible validate method.
  - pydantic_core validation errors appear during model instantiation or parsing.
  - A dependency update to Pydantic v2 causes targeted or full-suite regressions.
  - A partially migrated or dirty working tree must be completed without losing valid edits.
anti_patterns:
  - Re-pointing imports to pydantic.v1 or otherwise using a Pydantic v1 compatibility shim; the grader rejects this even if tests pass.
  - Emptying, stubbing, deleting, or replacing a function body merely so its module imports; the grader rejects this even if tests pass.
  - Ending the attempt after stating an intention or plan without making and validating migration edits.
  - Stopping after one blocker or a partial Config batch while known inventory items remain.
  - Treating 310 or 311 passing tests as completion when the suite still exits nonzero.
  - Treating successful py_compile checks without collection or tests as evidence that the suite passes.
  - Changing application behavior to avoid implementing the migration.
  - Assuming the working tree is disposable or clean without inspecting git status and each existing diff.
  - Restarting the migration from scratch when the working tree contains useful validated changes.
  - Changing a model's base class as a side effect of replacing Field const or Config syntax.
  - Replacing Header(Parameter) with Header(BaseModel), which loses inherited Parameter behavior and may introduce an undefined BaseModel name.
  - Assuming py_compile catches undefined names executed during class definition.
  - Removing an import without checking every remaining runtime use in class bases, fields, decorators, defaults, Config blocks, and rebuild calls.
  - Removing Extra from an import while any class Config in that module still evaluates Extra.allow or Extra.forbid.
  - Converting Pydantic imports independently from the configuration blocks that use them.
  - Replacing only the class Config declaration with model_config and leaving its indented body behind.
  - Leaving populate_by_name, json_schema_extra, or other former Config attributes as over-indented statements below model_config.
  - Leaving v1 class Config blocks in migrated models.
  - Leaving extra = Extra.allow or extra = Extra.forbid in model configuration.
  - Using allow_population_by_field_name instead of populate_by_name.
  - Using schema_extra instead of json_schema_extra.
  - Using Field(const=True) instead of a Literal annotation.
  - Leaving a BaseModel __root__ declaration instead of evaluating native RootModel.
  - Forgetting to import Literal, RootModel, ConfigDict, Extra, or BaseModel where still used.
  - Treating every Optional annotation as optional in Pydantic v2 without a default.
  - Blindly adding None defaults to fields that were intentionally required.
  - Fixing only the first missing field reported by Config().
  - Assuming Config() success proves the enclosing Project fixture can be constructed.
  - Dismissing fixture-construction ValidationError as a test problem.
  - Replacing EmailStr with str when email validation is required.
  - Calling EmailStr.validate directly under its Pydantic v1 convention.
  - Leaving parse_obj, schema, dict, json, or other deprecated model APIs without checking v2 replacements.
  - Solving a forward-reference error with reciprocal top-level imports in an existing model cycle.
  - Moving imports out of TYPE_CHECKING without mapping runtime import order.
  - Assuming TYPE_CHECKING imports make annotation names available to Pydantic at runtime.
  - Calling model_rebuild without checking its result or making referenced types available.
  - Fixing a circular import only in a leaf module without importing the package entry point used by tests.
  - Running an unreviewed regex or sed rewrite across nested Config blocks or large schema_extra dictionaries.
  - Generating migration scripts that can corrupt indentation, quoting, braces, parentheses, imports, or base classes.
  - Trusting a bulk migration script because it exits zero or prints success.
  - Applying a batch script to many files before one representative result has compiled, imported, and been reviewed.
  - Continuing batch edits after a generated rewrite produces a syntax, indentation, import, or class-definition error.
  - Editing another file before the latest edited Python file passes py_compile and, when importable, a fresh-process module import.
  - Treating py_compile from before the latest edit as validation of current contents.
  - Appending guessed delimiters instead of restoring intended structure.
  - Repairing ConfigDict without comparing it to the complete original Config block.
  - Replacing an entire model file to repair one block and losing fields, inheritance, examples, comments, or behavior.
  - Using shell redirection to overwrite a complete source file when a narrow edit or restoration is possible.
  - Running git restore :/ or git clean -fd as a generic recovery action, thereby deleting valid migration work, user changes, notes, or scripts.
  - Making broad edits before reading the task, dependencies, tests, complete traceback, and relevant history.
  - Migrating BaseSettings before confirming the repository uses it.
  - Fixing one v1 symbol while leaving the rest of the repository uninventoried.
  - Migrating lower-priority Config blocks while Field(const=True) still blocks collection.
  - Repeating exploratory greps after artifacts identify the exact migration commit instead of inspecting it.
  - Repeatedly probing an unavailable historical commit after git cat-file proves the object is absent.
  - Writing an unsolicited migration ledger into the repository instead of using an existing task mechanism or temporary notes.
  - Spending the attempt documenting an inventory without applying and validating migration edits.
  - Running tests before all changed files compile and critical modules import.
  - Treating pytest collection output as the primary syntax or class-definition checker.
  - Trusting truncated pytest output or a targeted test as proof the suite passes.
  - Piping pytest through head or another command that hides pytest's real exit status.
  - Stopping with deprecation warnings or forbidden v1 imports because tests are green.
steps:
  - name: establish-clean-baseline
    description: >
      Read the task and inspect pwd, git status, and git diff before editing.
      Record pre-existing changes so they are not overwritten. Read each
      modified production-file diff and classify it as useful migration work,
      malformed migration work, unrelated user work, or uncertain; preserve
      useful and unrelated changes. Identify the canonical test command,
      supported Python versions, package manager, and migration dependency
      files such as pyproject.toml, lock files, tox.ini, noxfile.py,
      requirements files, and requirements-v2.txt. Do not assume globally
      installed Pydantic matches the declared version. Resolve the repository
      root once and use that exact path consistently; copy it from pwd rather
      than retyping variable home-directory names. Do not add planning or
      ledger files to the repository unless the task requests them; use the
      runtime task tracker or temporary notes. Never use repository-wide
      restore or clean commands to recover from one malformed edit. Restore
      only explicitly identified files or hunks after reviewing their diffs.

  - name: establish-syntax-baseline
    description: >
      Before migration edits, compile tracked production Python source and
      import the package if the current tree permits it. If SyntaxError or
      IndentationError already exists, inspect git diff and the version-control
      baseline for that file. Distinguish pre-existing user changes from
      malformed migration changes. Restore only damaged structure while
      preserving intentional work. Do not continue until each currently edited
      production file compiles or is explicitly identified as a pre-existing
      failure.

  - name: clear-known-const-collection-blocker
    description: >
      If the traceback reports Field const in header.py, resolve it before
      history research, bulk inventory, Config migration, migration scripts, or
      writing a plan. After the baseline checks, make this the first production
      edit rather than ending the attempt with an announced migration plan.
      Read header.py and parameter.py completely. Keep Header(Parameter). Import
      Literal, change both Header.name and Header.param_in to explicitly
      annotated Literal fields, and preserve defaults and the "in" alias.
      Remove Extra only if the latest header.py has no remaining runtime use.
      Then immediately run py_compile on header.py, fresh-import Header and the
      package schema, instantiate valid values, reject invalid constants, and
      rerun conftest collection. Do not merely compile: Field(const=True) and
      undefined class-body names are runtime import failures. Search for and
      clear every remaining production or generating-template Field const
      before lower-priority migration work.

  - name: create-a-migration-ledger
    description: >
      Maintain a concise in-memory, temporary, or existing-task-system ledger
      of every file containing a v1 construct, exact constructs found, intended
      replacement, original base classes, edit status, latest py_compile
      status, fresh-process import status, model-rebuild status, and relevant
      tests. Include pre-existing modified files and whether their current
      hunks are retained, repaired, or intentionally untouched. Add later
      discoveries instead of relying on memory. Mark a file complete only after
      its latest contents compile, import where feasible, and have behavioral
      coverage. The ledger supports edits and must not become a substitute for
      making them.

  - name: inspect-project-specific-migration-contract
    description: >
      Read requirements-v2.txt and comments in pyproject.toml or lock files
      before changing dependency constraints. Treat a supplied post-migration
      dependency set or upper pins as the source of truth. Preserve intentional
      compatibility pins and avoid unrelated upgrades. Confirm whether a lock
      update is expected and use the repository package manager to produce it.

  - name: inspect-repository-history-for-the-intended-migration
    description: >
      Search git log, merge commits, dependency comments, and nearby tags for a
      known Pydantic v2 migration. If artifacts name a commit, first use git
      cat-file -e to determine whether the object exists locally. If available,
      inspect it immediately using git show --stat, git show --name-status, and
      path-limited git show. If a base is named, inspect the complete range and
      affected paths. In this historical repository, requirements-v2.txt may
      identify migration a6d7d7bb and pre-migration base be5b306d; verify the
      objects and use their diff as the primary project-specific plan when
      present. Use it as evidence for dependencies, RootModel conversions,
      optional defaults, parser APIs, inheritance, imports, rebuild order,
      cycle handling, and all changed paths. If the objects are absent from the
      single-commit seed repository, record that once and proceed from source,
      tests, existing working-tree diffs, and requirements-v2.txt rather than
      repeating history searches. Do not blindly cherry-pick or overwrite
      current work.

  - name: compare-working-tree-to-known-migration
    description: >
      When known migration objects exist, compare the current tree, HEAD, named
      base, and migration commit path by path. Classify each migration hunk as
      present, missing, conflicting with later work, or irrelevant. Prefer
      complete known-good hunks over reconstructing ConfigDict and
      json_schema_extra fragments. If using git apply, inspect a path-limited
      patch and run --check first. Never apply over uncommitted user changes
      without preserving them. Review the complete resulting diff and enforce
      per-file compile and import gates. If the objects do not exist, skip this
      step rather than attempting fabricated hashes or network retrieval not
      authorized by the task.

  - name: verify-runtime-dependencies
    description: >
      Print pydantic.__version__ in the same environment used by tests and
      confirm it is 2.x. If the project requires 2.7 or newer, verify >=2.7.0;
      otherwise honor its declared range. Check pydantic-settings only when
      BaseSettings is used. Inspect sys.path and imports for accidental local
      modules and forbidden pydantic.v1 shims. The existence of pydantic.v1 in
      the installed distribution does not authorize its use.

  - name: run-baseline-tests
    description: >
      Run the canonical test command before editing when the tree is executable.
      Capture the complete first traceback, warning summary, test count, and
      pytest exit code without piping through head. If collection fails, record
      the full import chain or model definition that blocks it. Read failing
      tests and production code before changing them. Treat conftest import
      failure as zero useful coverage regardless of a passing count from an
      earlier or partial invocation.

  - name: build-complete-v1-api-inventory
    description: >
      Search tracked Python and relevant templates for all Pydantic imports and
      APIs, including BaseModel, RootModel, BaseSettings, ConfigDict, Extra,
      Field, EmailStr, validators, constrained types, parse_obj, parse_raw,
      schema, dict, json, class Config, __root__, const,
      allow_population_by_field_name, schema_extra, orm_mode, validate_all,
      anystr options, smart_union, fields configuration, TYPE_CHECKING, quoted
      annotations, update_forward_refs, and model_rebuild. Inspect matches in
      context and distinguish production, tests, templates, fixtures, golden
      records, and documentation. Treat grep exit 1 as no matches only when
      stderr is empty and the path and command are correct. Perform this
      inventory once, update it from later failures, and then begin edits.

  - name: inventory-model-inheritance-and-runtime-names
    description: >
      Record every Pydantic model's original base-class expression and the
      import that binds each base at runtime. Also inventory names executed
      while defining classes: Field, ConfigDict, Extra, Literal, enum defaults,
      validators, decorators, and types used outside postponed annotations.
      Compare this map after every model edit. In this codebase Header inherits
      Parameter; replacing it with BaseModel is not part of the const migration.
      A NameError at class definition means compilation was insufficient:
      restore the intended base or missing import from baseline and history,
      then import the exact module and package entry point in fresh processes.

  - name: prioritize-import-time-blockers
    description: >
      Make the first production edit resolve the complete topmost import-time
      blocker. For the known const traceback, open the entire header.py and its
      parent parameter.py before editing. Change only the imports and the two
      constant field declarations: import Literal from typing; retain Field;
      remove Extra only if no longer used; retain class Header(Parameter);
      annotate name as Literal[""] with default ""; annotate param_in as
      Literal[ParameterLocation.HEADER] with its existing default and alias.
      Do not start Config conversions, parser changes, migration scripts, or
      repository documentation while this blocker remains. Immediately run
      py_compile on header.py, fresh-import Header, instantiate its valid
      values, verify an invalid constant is rejected, and fresh-import
      openapi_python_client.schema. Then search all tracked production and
      template files for every remaining Field const and clear them with the
      same gates before lower-priority configuration work.

  - name: map-the-schema-import-and-forward-reference-graph
    description: >
      Before changing imports in mutually referential models, map runtime and
      type-only edges among the package initializer and modules such as OpenAPI,
      Paths, PathItem, Operation, Callback, and dependencies. Read each complete
      module and package __init__.py, including rebuild calls. Record symbols
      needed during ordinary import, annotation evaluation, schema
      construction, and rebuilding. Treat "partially initialized module" as an
      import-graph failure, not proof another top-level import is needed.

  - name: grep-for-const-usage-in-field-definitions
    description: >
      Search for const=True, const with flexible whitespace, and Field calls
      containing const across Python source and model-generating templates. Use
      patterns equivalent to const[[:space:]]*= and Field(.*const. Read each
      containing class and inherited field before changing annotations. Run the
      search before edits and after the final edit; no production or generating
      template matches is a release gate.

  - name: grep-for-emailstr-and-other-v1-types
    description: >
      Search for EmailStr, validator, root_validator, conint, constr, confloat,
      StrictInt, StrictStr, and direct type validate calls. Determine whether
      each performs real validation, represents OpenAPI format metadata, or is
      dead compatibility code. Do not confuse grep exit 1 for no matches with a
      malformed command or path.

  - name: grep-for-basesettings-imports
    description: >
      Search imports and inheritance involving BaseSettings, including
      multiline imports and aliases. If there are no matches, do not add
      pydantic-settings or invent a settings migration.

  - name: grep-for-config-class-usage
    description: >
      Find every nested class Config and read each complete block. Search
      separately for Extra.allow, Extra.forbid, allow_population_by_field_name,
      schema_extra, arbitrary_types_allowed, aliases, and parse_obj. Record
      exact settings and large nested schema examples so conversion drops
      nothing. Pair every Extra import with all runtime uses in the same module;
      do not schedule import removal separately from conversion of its last
      Config user.

  - name: inventory-v1-root-models
    description: >
      Search for __root__, custom root validators, direct construction through
      __root__, methods delegated to __root__, and tests that compare, index,
      serialize, or validate root values. Determine each intended generic root
      type and public behavior before conversion. Include root models in cycles,
      because their annotations and rebuild order may define the circular-import
      boundary.

  - name: inventory-v2-optionality-changes
    description: >
      Inspect fields annotated Optional[T], Union[T, None], or T | None. In v2
      these remain required without a default. Determine which were implicitly
      optional in v1 and need = None or Field(default=None, ...), while
      preserving deliberately required nullable fields. Review factories,
      aliases, mutable defaults, and inherited fields. Search fixtures and call
      sites for zero-argument or minimal construction, especially Config() and
      Project(...), and record each constructor contract.

  - name: update-dependency-declarations
    description: >
      Change the dependency from Pydantic v1 to the v2 range required by the
      repository contract. Add pydantic-settings only if BaseSettings requires
      it. Apply documented upper pins; do not invent bounds from the global
      environment. Update lock files through the package manager and verify
      resolved versions.

  - name: migrate-basesettings-imports
    description: >
      Where genuinely used, import BaseSettings and SettingsConfigDict from
      pydantic_settings and translate settings to model_config. Never import
      BaseSettings from pydantic.v1. Preserve aliases, prefixes, env files, case
      sensitivity, and custom settings sources.

  - name: replace-const-fields-with-literal-types
    description: >
      Replace each Field const constraint with a Literal annotation while
      retaining default, alias, description, and other Field arguments. Change
      name = Field(default="", const=True) to
      name: Literal[""] = Field(default=""). Change a header location field to
      param_in: Literal[ParameterLocation.HEADER] =
      Field(default=ParameterLocation.HEADER, alias="in"). Import Literal.
      When overriding an inherited field, add the explicit annotation because
      v2 rejects unannotated overrides, but preserve the original class base:
      Header must remain Header(Parameter), not Header(BaseModel). Immediately
      compile, inspect the class declaration and imports against baseline,
      import the defining module and package schema in fresh processes,
      instantiate the valid constant, and verify another value is rejected.

  - name: convert-config-classes-carefully
    description: >
      Convert one model at a time from nested class Config to
      model_config = ConfigDict(...). Translate Extra.allow to extra="allow",
      Extra.forbid to extra="forbid", allow_population_by_field_name=True to
      populate_by_name=True, and schema_extra to json_schema_extra. Preserve
      arbitrary_types_allowed and every supported setting. Replace the complete
      Config block, not merely its declaration or first setting: every retained
      setting must be an argument in the ConfigDict call or another valid v2
      configuration form. No former Config attribute may remain over-indented
      under a completed model_config assignment. Treat conversion of the Config
      body and adjustment of the module's pydantic import as one atomic
      per-file change. Remove Extra only after searching the latest file
      contents and confirming its final runtime use is gone; if any class
      Config still uses Extra, retain the import until that class is converted.
      Do not alter class bases or unrelated imports. Use small structural edits,
      not broad regex over multiline configuration or nested examples. Compile
      and fresh-import the module immediately; a remaining class Config that
      refers to removed Extra will compile but fail during class definition.
      After a representative conversion passes, continue through every
      inventoried Config model rather than ending the attempt at the first
      successful batch.

  - name: use-a-delimiter-safe-config-conversion
    description: >
      For Config containing a large schema_extra dictionary, display or save
      the complete original block from working tree and baseline. Convert only
      the wrapper while preserving the complete dictionary. Keep the closing
      dictionary brace before the ConfigDict parenthesis. Inspect the full
      opening and closing region; ConfigDict(json_schema_extra={...}) requires
      both delimiters. Do not prefix-replace while leaving a parenthesis where a
      brace belonged. Also inspect the lines immediately after model_config:
      an indented populate_by_name or json_schema_extra assignment left from
      the old Config body is evidence of a partial conversion and must be
      repaired before any other file is edited.

  - name: preserve-json-schema-metadata
    description: >
      Preserve the complete schema_extra dictionary in meaning when moving it
      to json_schema_extra, including examples, aliases, component names, and
      delimiters. Compile immediately. If syntax breaks, restore from original
      diff or history rather than guessing parentheses.

  - name: migrate-root-models-without-changing-their-contract
    description: >
      Convert sole-field __root__ BaseModels to native RootModel with the
      correct generic root type, following history where available. Preserve
      iteration, item access, equality, mapping, validation, and serialization
      required by callers. Update __root__ access to root only where v2
      requires it. Do not delete convenience methods or replace the model with
      a bare collection. Compile, fresh-import, and directly test each root
      model before another edit.

  - name: validate-each-edited-file-immediately
    description: >
      After every operation changing a Python file, run py_compile on that exact
      file before editing another file. This includes direct edits,
      redirections, sed, scripts, formatters, and import sorters. Validation
      predating the latest modification does not count. If one command changes
      multiple Python files, obtain its complete touched-file list from git
      diff or status, not the script's claimed list, then compile every touched
      file immediately in a fail-fast loop before any additional edit. A zero
      exit from the rewrite command does not validate its output. If compilation
      fails, stop and inspect the complete expression, indentation, opening
      delimiter, git diff, and baseline; restore known structure rather than
      guessing. After compile succeeds, inspect changed class declarations,
      Config blocks, and imports, then import the edited model module in a fresh
      Python process whenever its dependencies permit. py_compile does not
      execute class bodies and therefore does not catch undefined BaseModel,
      undefined Extra, or changed inheritance. A fresh import failure is also a
      hard stop. For schema models, additionally import the package schema entry
      point before moving on.

  - name: recover-from-syntax-errors-before-any-other-work
    description: >
      Treat SyntaxError and IndentationError as hard stops. Do not inspect
      unrelated failures, edit another model, or run pytest while either
      remains. Read the complete file around the reported line and the whole
      enclosing class or expression, because Python may report a closing
      delimiter or indented model_config line while damage occurred earlier.
      If the reported line is a former Config attribute such as
      populate_by_name or json_schema_extra below model_config, reconstruct the
      entire original Config block and convert all of its settings into one
      valid ConfigDict expression; do not merely dedent or delete the reported
      line. Compare git diff and baseline, reconstruct the smallest intended
      change, compile it, and import through the package path used by tests. If
      unclear, revert only that attempted edit and redo it manually. Never
      launch a second rewrite script to repair output from the first.

  - name: recover-from-class-definition-name-errors
    description: >
      Treat NameError during module import as a hard stop even when py_compile
      passed. Read the complete traceback and inspect the failing class base,
      decorators, defaults, nested Config, and model_config expression. Compare
      the entire edited class and import section with baseline and the known
      migration patch. If a rewrite changed Header(Parameter) to
      Header(BaseModel), restore Parameter inheritance rather than merely
      importing BaseModel. If the original model genuinely inherits BaseModel,
      restore the native pydantic BaseModel import. If class Config still uses
      Extra.allow or Extra.forbid after the Extra import was removed, either
      restore Extra temporarily or, preferably, complete that exact ConfigDict
      conversion without touching another file; never redirect it to
      pydantic.v1. Then repeat py_compile, direct fresh-process module import,
      package schema import, and conftest collection. Do not continue broad
      migration while a class-definition NameError remains.

  - name: constrain-mechanical-rewrites
    description: >
      Prefer explicit per-file edits for Config blocks and examples. If a
      mechanical script is justified, preserve the pre-script diff, run it on
      one representative file or temporary copy, inspect the complete diff,
      compile, fresh-import, and compare model bases before another file.
      Process files one at a time with edit-review-compile-import gates. Stop at
      the first malformed or semantically altered result. Never use regex to
      parse nested dictionaries, indentation-sensitive class bodies, or infer
      delimiters, and never run cleanup scripts on damaged syntax. Check
      replacement ordering: a broad import substitution can consume the prefix
      of a more specific import and prevent the intended later rule. Never let
      an import-rewrite rule remove Extra, BaseModel, Field, or ConfigDict
      independently of verifying all current runtime uses in that same file.
      If a script unexpectedly touches multiple files, do not continue the
      migration: derive all touched files from git, compile all of them,
      fresh-import each touched model module, inspect each diff, and restore the
      batch if any result is malformed. Delete temporary migration scripts
      before completion unless the task explicitly asks to retain them.

  - name: preserve-population-by-alias-and-name
    description: >
      Aliased fields such as "in" must accept intended aliases and names. Set
      populate_by_name=True only where v1 used
      allow_population_by_field_name or tests require it. Test both
      construction paths and serialization by alias.

  - name: preserve-arbitrary-types-allowed
    description: >
      Retain arbitrary_types_allowed=True for models containing framework or
      library objects such as UploadFile, Jinja Environment, callbacks, or
      other non-Pydantic types. Do not add it globally; apply it only where
      prior configuration or fields require it.

  - name: restore-v1-optional-field-semantics
    description: >
      Add None defaults to fields non-required in v1 solely because they were
      Optional. Use field: Optional[T] = None or
      Field(default=None, alias=...). Do not alter required non-Optional or
      intentionally required nullable fields. Validate representative minimal
      inputs. Directly instantiate Config() because tests and Project fixtures
      rely on it. Inspect Config.model_fields and require historically optional
      fields to have is_required() false. If Config() raises ValidationError,
      read every error, compare all missing fields with history and callers,
      repair the whole optionality set, and rerun the Project fixture before
      broader tests. Then construct Project exactly as make_project does, using
      its OpenAPI mock, MetaType value, and Config instance; if that raises,
      inspect the complete Project validation error and restore defaults or
      accepted types according to its historical constructor contract rather
      than weakening validation globally.

  - name: update-parser-code-for-v2
    description: >
      Replace BaseModel.parse_obj(data) with model_validate(data), schema() with
      model_json_schema(), dict() with model_dump(), json() with
      model_dump_json(), and parse_raw() with model_validate_json() where
      argument behavior is equivalent. Review include, exclude, alias,
      exclude_none, mode, and serialization semantics rather than performing
      textual replacement. Search calls with arguments as well as zero-argument
      calls. Assess a project class named Config separately from nested
      Pydantic configuration.

  - name: migrate-validators
    description: >
      Replace @validator with @field_validator and @root_validator with
      @model_validator only where found. Translate pre, always, each_item,
      skip_on_failure, signatures, return values, and classmethod usage under
      v2 semantics. Test invalid and valid inputs so validators are not merely
      importable.

  - name: update-emailstr-and-direct-type-validation
    description: >
      Do not call EmailStr.validate with the v1 signature. If email validation
      is required, use TypeAdapter(EmailStr) or a containing BaseModel and
      preserve errors. If EmailStr is only an internal OpenAPI string marker and
      design intentionally accepts any string, replace that specific reference
      with str as tests require. Never globally replace EmailStr with str.

  - name: update-constrained-and-removed-types
    description: >
      Review constrained types and removed or relocated helpers. Prefer
      Annotated with Field constraints where v2 requires it, preserving
      strictness, bounds, lengths, patterns, and numeric behavior. Do not change
      supported StrictInt or StrictStr merely because inventory found them.

  - name: preserve-type-checking-import-boundaries
    description: >
      Keep imports under TYPE_CHECKING where runtime movement creates cycles.
      Use postponed or quoted annotations consistently with supported Python.
      TYPE_CHECKING does not bind runtime names: arrange central rebuilding
      after classes import, or supply the complete namespace supported by the
      installed v2 API. Do not alternate reciprocal imports between PathItem
      and Operation.

  - name: rebuild-cyclic-models-from-a-stable-module
    description: >
      Resolve cyclic models from a stable package initializer or module able to
      import participants in non-cyclic order. Import concrete classes first,
      then model_rebuild every dependent model with an explicit namespace when
      required. Include names such as PathItem, Operation, Callback, Parameter,
      and Reference, not only the first undefined annotation. Check rebuild
      success and validation through package import. Do not rebuild eagerly
      while a dependency is partially initialized.

  - name: update-forward-reference-rebuilds
    description: >
      Search update_forward_refs and unresolved references. Replace obsolete
      calls with model_rebuild where necessary after dependent types are
      importable. Account for changed arguments instead of mechanically
      renaming. Exercise package-level schema imports so cyclic definitions are
      checked together.

  - name: diagnose-partially-initialized-module-errors
    description: >
      Retain the full traceback and identify the first repeated module. Compare
      imports with baseline and known migration patch. Remove only the newly
      introduced eager edge closing the cycle, restore type-only annotations,
      and relocate rebuilding until all classes exist. Test the exact import
      used by tests, normally from openapi_python_client import schema as oai,
      not only a leaf import. Repeat until package, schema, and parser imports
      succeed in fresh processes.

  - name: preserve-functions-and-error-paths
    description: >
      Inspect every edited function and ensure its original work remains.
      Never replace a parser, validator, conversion function, or error handler
      with pass, ellipsis, NotImplementedError, an empty return, constant
      success, or swallowed exception merely to make collection succeed. The
      grader rejects empty or stubbed function bodies even if tests pass.
      Preserve error types and useful context unless v2 requires a deliberate,
      tested adaptation.

  - name: format-and-review-each-edit-batch
    description: >
      Inspect each small-batch diff for duplicate ConfigDict imports, removed
      imports with surviving runtime users, duplicate populate_by_name keys,
      json_json_schema_extra, lost fields, changed base classes, missing runtime
      imports, malformed or unexpected indentation, former Config attributes
      stranded below model_config, altered examples, unmatched delimiters,
      empty functions, reciprocal imports, and unrelated rewrites. Run
      formatter or import sorter only on intended files and inspect its diff.
      Because formatting changes contents, compile every affected file and
      fresh-import affected model files again. Keep generated files consistent
      with templates. Do not complete a batch until latest contents pass gates.

  - name: verify-all-files-compile
    description: >
      Compile all relevant tracked Python files before pytest, using compileall
      or a safe null-delimited loop. Never append || true. Fix the first error
      and repeat until all compile. Reconstruct mismatched expressions or
      indentation from diff or baseline, not guessed delimiters. Compilation is
      necessary but does not prove runtime names exist or the import graph is
      acyclic.

  - name: run-critical-import-checks
    description: >
      In fresh Python processes import the top-level package, schema alias used
      by tests, configuration, parser, OpenAPI, Paths, PathItem, Operation,
      Callback, Header, Components, Example, representative schema subclasses,
      and any settings model. Capture complete stderr and tracebacks. Verify
      ConfigDict, RootModel, Field, Extra where still used, and any genuinely
      used BaseModel imports from pydantic; never import built-in str from
      pydantic. Instantiate small models to catch class-definition errors,
      changed inheritance, unresolved annotations, missing defaults, and
      cycles. The package-level import is mandatory even if leaf imports pass.
      Run the same Config() and smallest Project fixture construction used by
      tests.

  - name: test-model-behavior-directly
    description: >
      Exercise extra handling, required and formerly optional fields, Literal
      constants, aliases, populate_by_name, arbitrary types, RootModel
      construction and dumping, cyclic PathItem-Operation-Callback data, JSON
      schema examples, and parser validation. Check accepted and rejected
      inputs. Verify Header still exposes and validates inherited Parameter
      fields. For models supporting minimal input, compare model_fields
      requiredness with historical construction and execute it directly.

  - name: run-collection-only-gate
    description: >
      Run pytest collection or the smallest command importing tests/conftest.py.
      Require pytest's own zero exit status and inspect complete output without
      a truncating pipeline. On SyntaxError or IndentationError, return to the
      compile and damaged-rewrite gates; inspect the named file before any
      other work and never accept zero collected tests as progress. On removed
      APIs, return to residue search; on NameError, return to runtime-name,
      surviving Config-use, and inheritance checks; on cycles, return to import
      graph and rebuild work. Do not count tests from an earlier run as evidence
      the current tree collects.

  - name: run-fixture-construction-smoke-tests
    description: >
      Execute high-fan-out fixtures and helpers. In this codebase inspect
      tests/test___init__.py make_project and require default Config() and
      minimal Project construction to succeed with
      openapi=MagicMock(title="My Test API"), meta=MetaType.POETRY, and
      config=Config(). Test the complete constructor rather than stopping after
      Config() succeeds. Setup-time ValidationError means tested code never ran;
      enumerate all missing or incompatible fields from the untruncated error,
      correct optionality and accepted types from history and caller contracts,
      and repeat before downstream work.

  - name: run-targeted-tests-iteratively
    description: >
      Run the smallest tests for each failure category after its fix. Read full
      tracebacks and assertions before editing. Resolve root causes without
      weakening tests, suppressing warnings indiscriminately, or bypassing
      production. Re-run until passing, then broaden. Return SyntaxError or
      IndentationError to the compile gate, NameError to class-definition
      import checks, and circular imports to graph and rebuild steps. When
      failures share fixture setup, fix that constructor first.

  - name: run-full-test-suite
    description: >
      Run the complete canonical suite with untruncated output. Pytest -x is
      acceptable during diagnosis, but finish without early stopping and verify
      pytest's actual exit code, passed count, failures, errors, skips, and
      warnings. Successful graded attempts in this historical codebase reached
      445 passing tests; if collection differs, explain it from the current
      repository. Around 310 or 311 passing, any nonzero exit, or conftest
      import failure is not completion. At that plateau, inspect the complete
      failure tail and continue the ledger rather than restarting discovery or
      reporting partial success.

  - name: run-static-and-package-checks
    description: >
      Run configured formatter check, import sorting check, linter, type
      checker, and package build when part of CI. Test in the declared
      dependency environment. Resolve introduced warnings without unrelated
      refactoring. If a fixer modifies Python, repeat immediate and whole-tree
      compilation, fresh critical imports, and tests.

  - name: scan-for-forbidden-residue
    description: >
      Search the final tree again for pydantic.v1, Field const, flexible const
      assignments, v1 Config classes, BaseModel __root__, Extra configuration,
      allow_population_by_field_name, schema_extra, obsolete validators,
      BaseSettings from pydantic, deprecated parser calls, and reciprocal
      runtime imports among cyclic models. Inspect each match; comments,
      documentation, fixtures, and compatibility tests need an explicit
      decision. Separately search for imports removed while names remain in
      executable class bodies and for suspiciously indented former Config
      settings following model_config. Confirm no production function was
      emptied or stubbed and no model base was accidentally changed. Green
      tests do not waive the bans on pydantic.v1 or empty function bodies.

  - name: inspect-final-diff-and-retest
    description: >
      Review the final diff against the initial inventory, inheritance map,
      runtime-name map, import graph, known migration evidence, ledger, and
      every pre-existing working-tree change classified at the start. Confirm
      intentional dependencies, preserved configuration and schema examples,
      correct optionality, RootModel behavior, clean imports, original model
      bases, rebuilt references, balanced delimiters, valid indentation, and no
      corrupted generated or unrelated files. Compare affected paths with the
      known migration range when available and account for differences. Remove
      unsolicited planning artifacts and temporary rewrite scripts. After the
      final edit rerun per-file and whole-tree compilation, fresh package and
      schema imports, Config() and high-fan-out fixtures, collection, behavioral
      checks, static checks, forbidden-residue scans, and the complete suite.
      Declare success only when all checks pass on final contents, native v2
      APIs are used, no pydantic.v1 shim remains, functions retain behavior,
      inheritance remains correct, no removed import has a surviving runtime
      user, and cyclic models import and validate.
```