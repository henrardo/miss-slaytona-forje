---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and using the repository test suite to drive the work.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "58c00075"
      - "ff6577e9"
      - "e4110aa0"
---

```yaml
# Attempt 1 regressed by trying a broad mechanical rewrite of all schema files before
# reading the actual failures. That broke json schema examples and produced syntax
# errors. Prefer small edits driven by tracebacks and run focused tests after each edit.
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so that the
  repository's own test suite passes, without shimming pydantic.v1 and
  without deleting behaviour to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails after upgrading the pydantic dependency to version 2
  - Pydantic validation or model construction errors appear in an otherwise migrated codebase

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working is rejected
  - Emptying a validator or function body so it still imports is rejected
  - Broad regex rewrites of every model before seeing the first traceback can corrupt nested json schema examples
  - Do not assume pyproject still pins pydantic v1; inspect it first
  - Do not declare the migration complete after imports work; run focused tests and then the full suite
  - Do not leave schema_extra in model_config because pydantic v2 expects json_schema_extra
  - Do not leave Optional fields without defaults when callers instantiate the model with no value

steps:
  - name: inspect-dependency-and-run-first-failure
    description: >
      Read pyproject.toml or the requirements file before editing. If pydantic is
      still pinned to v1, change only the dependency constraint first, such as
      pydantic >=2.1.1,<2.10 for this fixture. Then run the repository test suite
      or the smallest failing test command and copy the first pydantic traceback.
      Work from that first failure rather than doing a full mechanical migration.

  - name: find-pydantic-surface-area
    description: >
      Search the source tree for from pydantic import, import pydantic, class
      Config, Extra, const=, allow_population_by_field_name, schema_extra,
      update_forward_refs, min_items, and max_items. Use this inventory to
      identify likely v1 constructs, but edit only the constructs implicated by
      failures or clearly incompatible with pydantic v2.

  - name: fix-required-optional-fields
    description: >
      If pydantic v2 reports missing fields for a BaseModel that used to be
      instantiable with no arguments, inspect fields annotated Optional or
      Union with None. In pydantic v2, Optional without a default is still
      required. Add explicit defaults such as project_name_override:
      Optional[str] = None, package_name_override: Optional[str] = None, and
      package_version_override: Optional[str] = None. Re-run the focused test
      that constructed the model.

  - name: migrate-model-config-carefully
    description: >
      Replace inner Config classes only when needed and preserve their contents.
      Use model_config dictionaries or ConfigDict. Convert extra = Extra.allow
      to extra allow, extra = Extra.forbid to extra forbid, and
      allow_population_by_field_name = True to populate_by_name True. When a
      Config class contains schema_extra, rename it to json_schema_extra and do
      not move or truncate the nested dictionary.

  - name: replace-field-const-with-literal
    description: >
      If Field uses const=True, remove const and express the allowed value in
      the type annotation with Literal. For example a header style field with a
      default simple should be typed as Literal[simple] and keep the same
      default. Search again for const= after editing.

  - name: handle-forward-references-after-all-imports
    description: >
      If pydantic v2 reports that a model is not fully defined or says to define
      a referenced model then call model_rebuild, inspect string annotations and
      circular model imports. In the OpenAPI schema package, PathItem has string
      references to Operation. The working fix is to call model_rebuild after
      all schema classes are imported in openapi_schema_pydantic/__init__.py,
      not inside the individual module before all names exist. Re-run the
      failing schema test immediately.

  - name: avoid-unnecessary-model-rebuild-edits
    description: >
      Do not add model_rebuild to a module just because it has imported models.
      Adding it inside open_api.py caused resolution problems because all
      referenced names were not loaded. Put rebuild calls in the package
      initializer after the relevant imports, or use the traceback to choose a
      smaller fix.

  - name: use-real-literal-types-not-stringified-unions
    description: >
      If an OpenAPI version field is annotated with a quoted union expression,
      pydantic v2 may treat it as a forward reference. Import Literal from
      typing and annotate the field directly as a Literal union rather than as
      a string expression. Then run the version validation test.

  - name: rename-schema-extra-everywhere
    description: >
      Search for schema_extra after functional failures are fixed. In pydantic
      v2, model_config should use json_schema_extra. A safe final replacement in
      the OpenAPI schema model files is to replace the exact key schema_extra
      with json_schema_extra, preserving the example dictionaries unchanged.
      Re-run grep to confirm schema_extra is gone from source models.

  - name: run-focused-then-full-suite
    description: >
      After each fix, run the specific failing test with -xvs to verify the
      traceback changed or disappeared. In this fixture useful checks included
      tests for Config construction, OpenAPI version validation, and callback
      parsing. Once focused tests pass, run the full suite. If the full suite
      fails, return to the new first traceback instead of broadening edits.
```