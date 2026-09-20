---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and using focused tests to drive the work.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 6
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
---

```yaml
# Recent failed attempts did too much mechanical migration after the project was
# already partly on Pydantic v2. That corrupted schema files and left zero tests
# passing. The reliable path is traceback-first, with tiny edits, compilation
# after each schema edit, and preserving parser behavior.
# Attempt 2 regressed by not fixing the exact collection traceback first. The
# traceback named header.py and PydanticUserError const is removed, but the edit
# sequence moved on to broad migration and left pytest unable to collect.
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

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working is rejected
  - Emptying a validator or function body so it still imports is rejected
  - Leaving a try block or except block with no real migrated body is rejected
  - Broad regex rewrites of every model before seeing the first traceback can corrupt imports and nested json schema examples
  - Do not assume pyproject still pins pydantic v1; inspect it first
  - Do not repeat a full v1 to v2 migration when the repository already has pydantic version 2 constraints
  - Do not declare the migration complete after imports work; run focused tests and then the full suite
  - Do not leave schema_extra in model_config because pydantic v2 expects json_schema_extra
  - Do not leave Optional fields without defaults when callers instantiate the model with no value
  - Do not remove a class Config header while leaving its indented schema_extra assignment behind
  - Do not run another migration script while pytest collection is broken
  - Do not trust a script that rewrites imports until py_compile has checked every changed file
  - Do not keep a file containing a line that is only from or import after automated edits
  - Do not replace parser validation with a broad success path that skips Schemas.from_data
  - Do not add model_rebuild inside an individual schema module before all referenced models are imported
  - Do not ignore the exact file named by a pytest collection traceback even if a later grep seems empty
  - Do not migrate schema_extra or Config classes before fixing a collection-blocking const Field error
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
      mechanical migration.

  - name: fix-collection-blockers-before-inventory
    description: >
      If pytest cannot import tests/conftest.py, stop and fix only the exact
      project file named at the bottom of the traceback. A PydanticUserError
      saying const is removed and pointing at openapi_schema_pydantic/header.py
      means edit header.py first, not pyproject, not every schema module, and not
      schema_extra. Open the complete file, make the minimal Field change, run
      py_compile on that file, then rerun pytest collection or the same focused
      command before continuing.

  - name: find-pydantic-surface-area
    description: >
      Search the source tree for from pydantic import, import pydantic, class
      Config, Extra, const=, allow_population_by_field_name, schema_extra,
      update_forward_refs, parse_obj, dict, json, copy, construct, min_items,
      max_items, model_rebuild, bare import fragments, and quoted forward
      annotations. Treat the inventory as a checklist, not as permission for a
      mass rewrite. If grep appears to find nothing but the traceback names a
      construct, trust the traceback and inspect that file directly.

  - name: replace-field-const-with-literal
    description: >
      If Field uses const=True, remove const and express the allowed value in the
      type annotation with Literal. For example a header style field with a
      default simple should import Literal and be annotated as Literal of simple
      while keeping the same default. Search again for const= after editing, but
      also compile and import the traceback file because previous attempts missed
      this exact header.py error. In this fixture, header.py should be repaired
      before any Config or schema_extra migration because it blocks all pytest
      collection.

  - name: fix-required-optional-fields
    description: >
      If pydantic v2 reports missing fields for a BaseModel that used to be
      instantiable with no arguments, inspect fields annotated Optional or Union
      with None. In pydantic v2, Optional without a default is still required.
      Add explicit defaults for fields that are semantically optional. In this
      fixture, Config needed project_name_override, package_name_override, and
      package_version_override to default to None. Re-run the focused test that
      constructed the model before editing anything else.

  - name: migrate-model-config-with-surgical-edits
    description: >
      Replace inner Config classes only when needed and preserve their contents.
      Use model_config dictionaries or ConfigDict. Convert Extra.allow to the
      extra value allow, Extra.forbid to the extra value forbid, and
      allow_population_by_field_name to populate_by_name. When a Config class
      contains schema_extra, move the entire nested dictionary into model_config
      as json_schema_extra. Verify that no orphan assignment such as an indented
      schema_extra block remains directly inside the model class.

  - name: prefer-small-hand-edits-over-import-rewrite-scripts
    description: >
      In the OpenAPI schema package, mass scripts repeatedly caused broken
      modules. They left orphaned example dictionaries, truncated imports, and
      syntax errors in files such as reference.py, parameter.py, header.py, and
      example.py. Prefer editing one failing file or one exact key at a time. If
      a script is unavoidable, run it on a narrow file list, print the changed
      filenames, inspect git diff immediately, and compile before making any
      additional edits.

  - name: repair-collection-failures-before-continuing
    description: >
      If pytest collection fails with IndentationError, SyntaxError, or a
      traceback ending at an incomplete import, stop all semantic migration work.
      Open the exact file named by Python and also the last project file in the
      import chain. In this fixture, a traceback through parameter.py ending on a
      bare from pointed to a script-corrupted import, and an IndentationError in
      reference.py meant the class body indentation was invalid. Fix or revert
      those files first, then run py_compile on them before returning to
      pydantic errors.

  - name: compare-corrupted-files-to-git-diff
    description: >
      When a schema module looks malformed after migration, use git diff for
      that file before editing further. A common corruption is class Header,
      Reference, Example, or another schema class containing model_config
      followed by a leftover indented schema_extra assignment or example
      dictionary. Another is an import line split down to only from. Restore a
      coherent import block and one coherent class body, or revert the file and
      redo only the needed Field or model_config change by hand.

  - name: use-real-literal-types-not-stringified-unions
    description: >
      If an OpenAPI version field is annotated with a quoted union expression,
      pydantic v2 may treat it as a forward reference. Import Literal from typing
      and annotate the field directly as a Literal union rather than as a string
      expression. Then run the version validation test. Do not add model_rebuild
      in the same module as a guess; first verify whether the direct Literal
      annotation fixes the immediate version validation failure.

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

  - name: preserve-generator-data-from-dict-behavior
    description: >
      If tests in tests/test_parser/test_openapi.py fail after most tests pass,
      inspect openapi_python_client/parser/openapi.py before touching schema
      models again. GeneratorData.from_dict must still validate the input
      dictionary into OpenAPI, catch pydantic ValidationError and return the
      existing GeneratorError shape for invalid OpenAPI documents, call
      Schemas.from_data for valid documents, propagate a GeneratorError returned
      by Schemas.from_data, and return GeneratorData only on success. The v2
      migration should change parse_obj to model_validate if desired, but it
      must not leave the try body blank, swallow all exceptions, skip
      Schemas.from_data, or return success for an invalid empty dict. Re-run
      TestGeneratorData focused tests immediately after editing this function.

  - name: keep-error-model-output-compatible
    description: >
      When migrating parser error handling, compare the failing assertion rather
      than only the exception type. Pydantic v2 ValidationError strings and
      errors lists include different wording and extra fields, so preserve the
      repository's intended GeneratorError header and detail contract as closely
      as the tests require. Do not expose raw pydantic internals if the previous
      code wrapped them in GeneratorError. Run the invalid schema, invalid
      schemas, and successful from_dict parser tests together before moving on.

  - name: rename-schema-extra-after-syntax-is-clean
    description: >
      Search for schema_extra after functional failures are fixed and after
      changed modules compile. In pydantic v2, model_config should use
      json_schema_extra. A safe final replacement in OpenAPI schema model files
      is to replace the exact key schema_extra with json_schema_extra while
      preserving the example dictionaries unchanged. Re-run grep to confirm
      schema_extra is gone from source models, and open any file whose diff
      changed indentation around example dictionaries.

  - name: compile-import-and-scan-after-each-schema-edit
    description: >
      After changing any Pydantic model file, run python -m py_compile on the
      changed files or python -m compileall on the schema package. Then run a
      minimal import of the package that pytest imports, such as importing
      openapi_python_client.schema or the specific OpenAPI schema package. Also
      grep changed files for lines that are only from, only import, class Config
      leftovers, schema_extra leftovers, const leftovers, and unexpectedly
      indented example blocks. This catches IndentationError, truncated imports,
      removed Field arguments, and unresolved names before the full test suite.

  - name: run-focused-then-full-suite
    description: >
      After each fix, run the specific failing test with -xvs to verify the
      traceback changed or disappeared. In this fixture useful checks included
      pytest collection through tests/conftest.py, tests for Config construction,
      OpenAPI version validation, callback parsing, GeneratorData.from_dict
      invalid schema handling, GeneratorData schemas error propagation, and
      successful parsing. Once focused tests pass and changed files compile, run
      the full suite. If the full suite fails, return to the new first traceback
      instead of broadening edits.
```