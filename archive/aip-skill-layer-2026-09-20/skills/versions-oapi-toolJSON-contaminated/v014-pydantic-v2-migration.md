---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and using focused tests to drive the work.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 14
    derived_from_traces:
      - '58c00075'
      - 'ff6577e9'
      - 'cb2c25e1'
      - 'd3d33e79'
      - '4669a6ea'
      - '4f0fd0b1'
      - 'ee903b87'
      - '424cdc2a'
      - 'current-attempt-2'
      - '3cda36f1'
      - 'current-attempt-3'
      - 'current-attempt-4'
      - 'current-attempt-5'
      - 'current-attempt-311-syntax-failure'
      - '60b979d0'
      - 'current-attempt-424-config-regression'
      - '56684b1d'
      - 'current-attempt-443-endpoint-regression'
      - 'current-attempt-0-passing-overmigration'
---

```yaml
# Failed attempts did too much mechanical migration after the project was already
# partly on Pydantic v2. That corrupted schema files and left zero tests passing.
# The reliable path is traceback-first, with tiny edits, compilation after each
# schema edit, and preserving parser behavior.
# A later successful path showed the first real blocker can be Config() under
# Pydantic v2, not dependency migration. Fix the exact missing optional defaults
# before touching schema files when that traceback appears.
# A repeated regression still ended with 424 tests passing but fixture setup
# errors from Config(). Passing count is not success. Treat setup ERRORS as
# higher priority than ordinary FAILURES, and fix Config optional defaults before
# any OpenAPI schema cleanup if Config() is in the traceback.
# An older regression used a script to change Config and schema_extra blocks in
# openapi_schema_pydantic/example.py and left a mismatched closing parenthesis
# during pytest collection. Treat any syntax error in a schema file as the top
# priority and restore a coherent class body before making semantic changes.
# The latest zero passing run repeated the broad migration mistake: it changed
# dependency pins, rewrote many schema modules, damaged schema_extra blocks, and
# only then tried an import. Do not make the second attempt a bigger script.
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so that the
  repository's own test suite passes, without shimming pydantic.v1 and without
  deleting behaviour to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails after upgrading the pydantic dependency to version 2
  - Pydantic validation or model construction errors appear in an otherwise migrated codebase
  - Pytest collection fails while importing models that depend on Pydantic
  - Parser tests fail after most of the suite passes
  - Endpoint parser contract tests fail after hundreds of tests pass
  - A mostly passing suite fails during fixture setup while calling Config with no arguments
  - Pytest collection fails with a SyntaxError in an OpenAPI schema model after a migration script
  - A run reports zero passing tests because pytest collection or imports failed

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working is rejected
  - Emptying a validator or function body so it still imports is rejected
  - Leaving a try block or except block with no real migrated body is rejected
  - Broad regex rewrites of every model before seeing the first traceback can corrupt imports and nested json schema examples
  - Do not assume pyproject still pins pydantic v1; inspect it first
  - Do not repeat the full dependency or schema migration when the repository already has pydantic version 2 constraints
  - Do not edit OpenAPI schema files when the traceback is Config missing optional override fields
  - Do not chase ordinary assertion failures before fixing pytest setup errors from Pydantic model construction
  - Do not declare the migration complete after imports work; run focused tests and then the full suite
  - Do not leave const in Field because pydantic v2 rejects it during import
  - Do not leave schema_extra in model_config because pydantic v2 expects json_schema_extra
  - Do not leave Optional fields without defaults when callers instantiate the model with no value
  - Do not remove a class Config header while leaving its indented schema_extra assignment behind
  - Do not wrap a preserved schema_extra example dictionary in a ConfigDict call unless the parentheses and braces are checked by py_compile
  - Do not run another migration script while pytest collection is broken
  - Do not trust a script that rewrites imports until py_compile has checked every changed file
  - Do not keep a file containing a line that is only from or import after automated edits
  - Do not replace parser validation with a broad success path that skips Schemas.from_data
  - Do not return GeneratorData when OpenAPI validation failed or Schemas.from_data returned GeneratorError
  - Do not add model_rebuild inside an individual schema module before all referenced models are imported
  - Do not ignore the exact file named by a pytest collection traceback even if a later grep seems empty
  - Do not migrate schema_extra or Config classes before fixing a collection-blocking const Field error
  - Do not count partial passing tests as progress when pytest collection still fails
  - Do not count hundreds of passing tests as success when parser contract tests still fail
  - Do not count hundreds of passing tests as success when Endpoint parser tests still fail
  - Do not count hundreds of passing tests as success when fixture setup still fails before test bodies run
  - Do not count zero passing tests as proof that every file is broken; usually the first import or syntax error stopped collection
  - Do not overwrite whole schema modules from memory; preserve the original imports, examples, aliases, and comments unless the traceback proves they must change
  - Do not continue from a SyntaxError in example.py, header.py, parameter.py, reference.py, or any schema module named by pytest collection
  - Do not change Endpoint.add_parameters to skip property_from_data, ignore ParseError, drop returned schemas, or append invalid parameters just to avoid Pydantic validation differences
  - Do not remove populate_by_name from aliased OpenAPI models such as Parameter, Header, MediaType, Schema, or OpenAPI
  - 'Do not quote an error message inside a list item in this skill file: use one plain scalar instead'

steps:
  - name: inspect-dependency-and-run-first-failure
    description: >
      Read pyproject.toml or the requirements file before editing. If pydantic is
      still pinned to v1, change only the dependency constraint first, such as
      pydantic >=2.1.1,<2.10 for this fixture. If the project already uses
      pydantic v2, do not repeat the full dependency or schema migration. Run the
      repository test suite or the smallest failing test command and copy the
      first full traceback. Work from that first failure rather than doing a full
      mechanical migration. If a file read or grep result looks unexpectedly
      empty, verify the command and inspect with another command before assuming
      there is no Pydantic usage.

  - name: treat-zero-tests-as-collection-failure
    description: >
      If the suite reports zero passing tests, assume pytest collection or import
      failed until proven otherwise. Read the first traceback and the last project
      file named in it. Do not start a broad migration to improve the pass count.
      In the failed run, zero passing tests came after schema files had been
      mass rewritten and example.py no longer parsed. The next attempt should
      restore or minimally repair the named file, run py_compile on it, and
      rerun the same pytest command before touching unrelated schema modules.

  - name: prioritize-errors-over-pass-count
    description: >
      After any full pytest run, inspect the ERRORS section before counting dots
      or fixing ordinary FAILURES. A run with hundreds of passing tests can still
      be blocked by a fixture setup error that prevents some test bodies from
      running. In this fixture, the suite reached 424 passing tests but still
      failed because tests/test___init__.py constructed Config() and pydantic v2
      treated optional override fields without defaults as required. A later run
      reached 443 passing tests but still had many TestEndpoint failures, so the
      endpoint parser contract was still broken. When setup errors mention
      Config(), fix config.py defaults and rerun that focused test before
      touching schema models or parser behavior. When failures cluster in
      TestEndpoint, stop schema migration and inspect parser/openapi.py and the
      exact tests.

  - name: classify-the-first-traceback
    description: >
      Decide whether the first actionable traceback is a collection blocker, a
      model construction validation error, a forward reference error, a syntax
      error from a prior edit, a fixture setup error, or a functional assertion
      failure. Fix only that class of error. In this fixture, if the traceback
      comes from tests/test___init__.py make_project and Config() reports
      project_name_override, package_name_override, and package_version_override
      as missing, skip schema edits and immediately fix config.py optional
      defaults. If the traceback is a PydanticUserError about const in header.py,
      fix header.py before any Config class, schema_extra, or parser work. If the
      traceback is a SyntaxError in example.py or another schema module, repair
      that exact file and run py_compile before making any other migration
      change. If most tests pass and failures are in tests/test_parser, stop
      editing schema models and inspect parser/openapi.py.

  - name: fix-required-optional-fields-early-when-traceback-names-config
    description: >
      If pydantic v2 reports missing fields for a BaseModel that used to be
      instantiable with no arguments, inspect fields annotated Optional or Union
      with None. In pydantic v2, Optional without a default is still required.
      Add explicit defaults for fields that are semantically optional. In this
      fixture, openapi_python_client/config.py needs project_name_override,
      package_name_override, and package_version_override to default to None
      because tests and production code call Config() with no arguments. Re-run
      the focused test or fixture that constructed Config before editing
      anything else, then rerun the full suite once focused setup passes.

  - name: fix-collection-blockers-before-inventory
    description: >
      If pytest cannot import tests/conftest.py, stop and fix only the exact
      project file named at the bottom of the traceback. A PydanticUserError
      saying const is removed and pointing at openapi_schema_pydantic/header.py
      means edit header.py first, not pyproject, not every schema module, and not
      schema_extra. A SyntaxError pointing at openapi_schema_pydantic/example.py
      means the previous schema_extra or model_config edit broke braces or
      parentheses and no tests can be trusted yet. Open the complete file, make
      the minimal repair, run py_compile on that file, then rerun pytest
      collection or the same focused command before continuing.

  - name: find-pydantic-surface-area-after-first-fix
    description: >
      Search the source tree for from pydantic import, import pydantic, class
      Config, Extra, const=, allow_population_by_field_name, schema_extra,
      update_forward_refs, parse_obj, dict, json, copy, construct, min_items,
      max_items, model_rebuild, bare import fragments, and quoted forward
      annotations. Treat the inventory as a checklist, not as permission for a
      mass rewrite. If grep appears to find nothing but the traceback names a
      construct, trust the traceback and inspect that file directly. For const,
      run grep on the repository source and on changed files before every full
      suite run.

  - name: replace-field-const-with-literal-first
    description: >
      If Field uses const=True, remove const and express the allowed value in the
      type annotation with Literal. For the OpenAPI Header model, import Literal
      from typing and change the style field from a plain string Field with
      const=True to a Literal of simple while keeping the same default value.
      Keep Field only if it still carries useful metadata. Search again for
      const= after editing, then run python -m py_compile on header.py and run a
      minimal import through tests/conftest.py or openapi_python_client.schema.
      In this fixture, header.py must be repaired before any broad schema
      migration because it blocks all pytest collection.

  - name: migrate-model-config-with-surgical-edits
    description: >
      Replace inner Config classes only when needed and preserve their contents.
      Use model_config dictionaries or ConfigDict. Convert Extra.allow to the
      extra value allow, Extra.forbid to the extra value forbid, and
      allow_population_by_field_name to populate_by_name. When a Config class
      contains schema_extra, move the entire nested dictionary into model_config
      as json_schema_extra. Verify that no orphan assignment such as an indented
      schema_extra block remains directly inside the model class. For files that
      contain example dictionaries, prefer the plain model_config dictionary form
      because it is easier to preserve nested braces than generating a
      ConfigDict call with mixed parentheses.

  - name: preserve-field-alias-population
    description: >
      For OpenAPI schema models with Python safe field names that map to reserved
      or spec names, preserve both alias metadata and field-name population.
      Examples include Parameter.param_in with alias in, Parameter.param_schema
      with alias schema, Header.param_schema, MediaType.media_type_schema,
      Reference.ref, and OpenAPI.openapi. In pydantic v2 this means keeping the
      Field alias and setting populate_by_name in model_config for models that
      tests or parser code instantiate with field names. After editing a model
      with aliases, run a quick constructor or model_validate check using both
      alias input and field-name input, and run the parser tests that construct
      oai.Parameter.model_construct with param_in and param_schema.

  - name: preserve-example-dictionaries-exactly
    description: >
      Schema files such as example.py, components.py, schema.py, contact.py,
      header.py, and info.py contain nested OpenAPI examples inside the old
      schema_extra structure. When renaming schema_extra, do not reconstruct
      those dictionaries from memory and do not use a regex that consumes only
      the first closing brace. Move or rename the outer key while leaving the
      nested example content unchanged. After the edit, inspect the final lines
      of each changed file and confirm that every opening brace, bracket, and
      parenthesis has a matching close. The earlier failed attempt stopped at a
      SyntaxError in example.py because this check was skipped.

  - name: prefer-small-hand-edits-over-import-rewrite-scripts
    description: >
      In the OpenAPI schema package, mass scripts repeatedly caused broken
      modules. They left orphaned example dictionaries, truncated imports,
      mismatched closing parentheses, and syntax errors in files such as
      reference.py, parameter.py, header.py, and example.py. Prefer editing one
      failing file or one exact key at a time. If a script is unavoidable, run it
      on a narrow file list, print the changed filenames, inspect git diff
      immediately, and compile before making any additional edits. Never replace
      a whole module with a guessed version when the needed change is a single
      default, key rename, or Field argument.

  - name: repair-collection-failures-before-continuing
    description: >
      If pytest collection fails with IndentationError, SyntaxError, or a
      traceback ending at an incomplete import, stop all semantic migration work.
      Open the exact file named by Python and also the last project file in the
      import chain. In this fixture, a traceback through parameter.py ending on a
      bare from pointed to a script-corrupted import, an IndentationError in
      reference.py meant the class body indentation was invalid, and a SyntaxError
      in example.py meant model_config parentheses did not match a preserved
      example dictionary. Fix or revert those files first, then run py_compile on
      them before returning to pydantic errors.

  - name: compare-corrupted-files-to-git-diff
    description: >
      When a schema module looks malformed after migration, use git diff for
      that file before editing further. A common corruption is class Header,
      Reference, Example, or another schema class containing model_config
      followed by a leftover indented schema_extra assignment or example
      dictionary. Another is an import line split down to only from. Another is a
      ConfigDict opening parenthesis wrapped around a dictionary that was already
      closed with braces. Restore a coherent import block and one coherent class
      body, or revert the file and redo only the needed Field or model_config
      change by hand.

  - name: use-real-literal-types-not-stringified-unions
    description: >
      If an OpenAPI version field is annotated with a quoted union expression,
      pydantic v2 may treat it as a forward reference. Import Literal from typing
      and annotate the field directly with Literal values or a real Union of
      Literal values rather than as a string expression. Then run the version
      validation test. Do not add model_rebuild in the same module as a guess;
      first verify whether the direct Literal annotation fixes the immediate
      version validation failure.

  - name: handle-forward-references-after-all-imports
    description: >
      If pydantic v2 reports that a model is not fully defined or says to define
      a referenced model then call model_rebuild, inspect string annotations and
      circular model imports. In the OpenAPI schema package, PathItem has string
      references to Operation. The working fix is to call model_rebuild after all
      schema classes are imported in openapi_schema_pydantic/__init__.py, not
      inside the individual module before all names exist. Re-run the failing
      schema test immediately.

  - name: avoid-unnecessary-model-rebuild-edits
    description: >
      Do not add model_rebuild to a module just because it imports models.
      Adding it inside open_api.py caused resolution problems because all
      referenced names were not loaded. Put rebuild calls in the package
      initializer after the relevant imports, or use the traceback to choose a
      smaller fix. If a model_rebuild call creates pytest collection errors,
      remove it and move the rebuild to the point where the package has imported
      every referenced model.

  - name: restore-generator-data-from-dict-contract
    description: >
      If tests/test_parser/test_openapi.py fails in GeneratorData.from_dict,
      inspect the whole function and compare it with the expected behavior in the
      tests before making schema edits. The function should validate the raw
      dictionary with the OpenAPI model, catch pydantic ValidationError and
      return the existing GeneratorError for invalid OpenAPI documents, call
      Schemas.from_data only after OpenAPI validation succeeds, immediately
      return the GeneratorError produced by Schemas.from_data, and return
      GeneratorData only with valid OpenAPI and valid schemas. A safe migration
      is replacing OpenAPI.parse_obj(data) with OpenAPI.model_validate(data)
      while keeping the try, except, and later Schemas.from_data flow intact.
      Do not widen the except to hide unrelated bugs unless the old code already
      did so. Run the invalid schema, invalid schemas, and success tests together
      after this edit.

  - name: keep-parser-error-output-compatible
    description: >
      When migrating parser error handling, compare the failing assertion rather
      than only the exception type. Pydantic v2 ValidationError strings and
      errors lists include different wording and extra fields, so preserve the
      repository's intended GeneratorError header and detail contract as closely
      as the tests require. The invalid empty dictionary case should not raise
      out of GeneratorData.from_dict and should not call Schemas.from_data after
      OpenAPI validation fails. The case where Schemas.from_data returns
      GeneratorError should propagate that object, not wrap it as a validation
      error and not convert it to success.

  - name: preserve-endpoint-parameter-contracts
    description: >
      If many failures remain in TestEndpoint after schema imports and
      GeneratorData tests pass, inspect Endpoint.add_parameters,
      Endpoint.add_request_body, and the corresponding tests before touching
      schema models again. Tests use model_construct, MagicMock, ParseError, and
      patched property_from_data to verify exact control flow. Preserve the old
      contract that property_from_data is called with the parameter name,
      required flag, parameter schema data, current schemas, and config; that a
      ParseError result is added to endpoint.errors rather than to parameter
      lists; that successful properties are appended to the correct path, query,
      header, or cookie list; and that returned property schemas are propagated.
      Do not let pydantic v2 model changes turn param_in or param_schema into
      missing attributes, aliases only, or raw extra fields. Run the individual
      failing TestEndpoint method with -xvs, then the whole TestEndpoint class.

  - name: verify-parser-mocks-still-see-calls
    description: >
      Parser tests use mocks for Schemas, property_from_data, request_body_from_data,
      and config, so do not rewrite parser methods in a way that bypasses those
      mocks or imports a different symbol inside the function. Use the module
      level symbols that tests patch. For invalid schema input, assert that
      Schemas.from_data was not needed after OpenAPI validation failed if the
      test expects that behavior. For valid OpenAPI input, assert that the mock
      was called with the parsed OpenAPI object and the config object. For
      endpoint parameter parsing, assert that property_from_data was called and
      that its ParseError result is stored exactly as the tests expect. Re-run
      all TestGeneratorData tests and all TestEndpoint tests before declaring
      parser work done.

  - name: rename-schema-extra-after-syntax-is-clean
    description: >
      Search for schema_extra after collection blockers, Config construction
      errors, and functional failures are fixed and after changed modules
      compile. In pydantic v2, model_config should use json_schema_extra. A safe
      final replacement in OpenAPI schema model files is to replace the exact key
      schema_extra with json_schema_extra while preserving the example
      dictionaries unchanged. If the code still has inner Config classes, first
      decide whether those classes need conversion at all; key renaming alone may
      not be enough. Re-run grep to confirm schema_extra is gone from source
      models, and open any file whose diff changed indentation around example
      dictionaries.

  - name: compile-import-and-scan-after-each-schema-edit
    description: >
      After changing any Pydantic model file, run python -m py_compile on the
      changed files or python -m compileall on the schema package. Then run a
      minimal import of the package that pytest imports, such as importing
      openapi_python_client.schema or the specific OpenAPI schema package. Also
      grep changed files for lines that are only from, only import, class Config
      leftovers, schema_extra leftovers, const leftovers, unmatched ConfigDict
      calls, and unexpectedly indented example blocks. This catches
      IndentationError, SyntaxError, truncated imports, removed Field arguments,
      mismatched parentheses, and unresolved names before the full test suite.

  - name: run-focused-then-full-suite
    description: >
      After each fix, run the specific failing test with -xvs to verify the
      traceback changed or disappeared. In this fixture useful checks included
      pytest collection through tests/conftest.py, tests for Config construction,
      OpenAPI version validation, callback parsing, GeneratorData.from_dict
      invalid schema handling, GeneratorData schemas error propagation,
      TestEndpoint.add_parameters_parse_error, all TestEndpoint tests, and
      successful parsing. Once focused tests pass and changed files compile, run
      the full suite. If the full suite fails, return to the new first traceback
      or setup error instead of broadening edits. If hundreds of tests pass but
      any fixture setup, collection, syntax, or parser contract failure remains,
      treat the run as failed and repair the named file or model before making
      more migration changes.
```