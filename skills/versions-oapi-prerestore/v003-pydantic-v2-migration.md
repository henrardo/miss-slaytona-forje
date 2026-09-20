---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and getting the repository test suite green.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces:
      - b40bc778
      - 13f5ed82
      - c997561c
      - 36ec346f
      - 76a05f00
      - 2e474527
---

```yaml
# Learned from the successful trace and the latest regression: do not begin with a broad
# mechanical rewrite. In this fixture the dependency was already set to Pydantic v2,
# and the real failures were a few v2 semantic changes left behind. The latest failed
# attempt regressed by leaving Field const usage in header.py, then earlier attempts
# also regressed by corrupting model_config indentation with broad regex rewrites.
# Fix the first import traceback directly, then run syntax and targeted tests.
purpose: >
  Complete a real Pydantic v1 to v2 migration by using the first failing
  traceback to identify remaining v1 assumptions, updating those assumptions
  directly, preserving file structure and indentation, and verifying with
  targeted tests followed by the full suite.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A repository has already bumped to Pydantic v2 but tests fail with Pydantic validation, config, schema, or forward reference errors
  - A suite fails during import because Pydantic v2 rejects v1 model definitions

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Do not repoint imports to pydantic.v1 because that is a compatibility shim rather than a migration
  - Do not empty a validator, hook, parser, or function body just to keep imports or tests green
  - Do not mass rewrite every Pydantic model before seeing the actual traceback
  - Do not replace whole files when a small field or config edit is enough
  - Do not use broad regex rewrites for Config classes with schema examples because it can corrupt nested dictionaries and create syntax errors
  - Do not leave model_config indented outside a class body after editing Field const or Config
  - Do not stop after changing only one const occurrence when grep still finds Field const elsewhere
  - Do not replace StrictInt or StrictStr with imports of int or str from pydantic
  - Do not declare the migration complete after only import checks
  - Do not ignore deprecation warnings for schema_extra when the suite still exercises JSON schema generation

steps:
  - name: establish-current-state
    description: >
      Inspect pyproject.toml, requirements files, and the installed environment before
      changing code. Determine whether the project still depends on Pydantic v1 or has
      already been bumped to Pydantic v2. If it is still on v1, update the declared
      dependency to the task target. If it is already on v2, do not churn dependency
      files. Run the repository test suite or the failing test command and save the
      first actionable Pydantic error and exact file and line from the traceback.

  - name: search-pydantic-surface-area
    description: >
      Search the source tree for Pydantic imports and v1-only patterns before editing.
      Useful searches are from pydantic import, import pydantic, class Config, Extra
      dot, allow_population_by_field_name, schema_extra, const equals, Field open paren,
      min_items, max_items, update_forward_refs, parse_obj, dict open paren, json open
      paren, and BaseSettings. Use these results as an edit checklist, not as
      permission to blindly rewrite whole files.

  - name: fix-import-blocking-errors-first
    description: >
      If pytest cannot import conftest or the package, fix that import-blocking error
      before doing any larger migration work. For a PydanticUserError about const being
      removed, open the exact model named in the traceback and migrate that field
      immediately. Re-run the same import or pytest command after the edit. Do not
      continue to Optional defaults, schema_extra, or forward references while the
      package still fails to import.

  - name: replace-all-field-const-with-literal
    description: >
      Pydantic v2 removed Field const. For every field declared with Field and const
      true, remove the const argument and express the allowed value in the type
      annotation using Literal. Preserve the default value, alias, required marker,
      class declaration, inheritance, comments, and surrounding model_config. Import
      Literal from typing where needed. After fixing the traceback file, grep the
      repository again for const equals and fix every remaining occurrence before
      running the suite. In discriminator models such as Header or Parameter
      subclasses, keep the existing class wrapper and only change the annotated field
      plus imports.

  - name: fix-optional-fields-without-defaults
    description: >
      In Pydantic v2, Optional[T] or T union None without a default is still a required
      field. When tests instantiate a model with missing optional settings and fail
      with field required validation errors, add an explicit default of None to fields
      that are semantically optional. In the learned fixture, Config needed
      project_name_override, package_name_override, and package_version_override
      changed from Optional[str] with no default to Optional[str] = None. Re-run the
      targeted failing test immediately after this change.

  - name: migrate-model-config-with-minimal-diffs
    description: >
      Convert v1 Config inner classes only where they still exist or fail. Replace
      extra = Extra.allow with model_config containing extra set to allow. Replace
      allow_population_by_field_name with populate_by_name set to true. Keep existing
      aliases and examples. Prefer direct, reviewed edits over generated regex when a
      Config contains nested schema examples. After editing a class, read the changed
      region and confirm model_config is inside the intended model class at the same
      indentation level as fields and methods.

  - name: rename-schema-extra
    description: >
      In Pydantic v2, schema_extra in model_config is renamed to json_schema_extra.
      Search the source tree for schema_extra and replace the model configuration key
      while preserving the value exactly. In the learned fixture, the remaining
      occurrences were in openapi_schema_pydantic model_config dictionaries and were
      safely handled by replacing the literal key schema_extra with json_schema_extra.

  - name: handle-openapi-version-literals
    description: >
      If a field annotation is a quoted string containing a Literal expression,
      Pydantic v2 may treat it as an unresolved forward reference. Replace stringified
      Literal annotations with real typing.Literal annotations and import Literal from
      typing. For the OpenAPI schema model, use a normal Literal union for supported
      openapi versions instead of a quoted annotation.

  - name: rebuild-forward-referenced-models-after-imports
    description: >
      When validation fails because a model is not fully defined or a forward reference
      such as Operation is unresolved, call model_rebuild after all related models have
      been imported. A good location for mutually referring OpenAPI schema models is
      the package __init__.py after all from dot module imports. Rebuild the model that
      owns the string reference, then any aggregate model that depends on it, and
      finally the top-level model. In the learned fixture, rebuilding after all
      openapi_schema_pydantic imports fixed PathItem references to Operation and
      allowed OpenAPI validation tests to pass.

  - name: run-syntax-and-import-checks-after-structural-edits
    description: >
      After any edit that changes imports, class declarations, Config, model_config,
      or Field const usage, run a fast syntax or import check before pytest. Good
      checks are python -m compileall for the edited package or python -c importing
      the edited module. If pytest fails while importing conftest with IndentationError,
      SyntaxError, or a PydanticUserError, stop and fix the exact file and line before
      making more migration changes. Earlier failed traces lost all tests because
      header.py and schema example dictionaries were left syntactically invalid.

  - name: use-v2-method-names-when-tests-require
    description: >
      If tests or warnings expose v1 method usage, update BaseModel calls to v2 names.
      Common replacements are parse_obj to model_validate, dict to model_dump, json to
      model_dump_json, schema to model_json_schema, copy to model_copy, construct to
      model_construct, and update_forward_refs to model_rebuild. Keep compatibility
      wrappers only when the project deliberately supports both versions and tests
      require that behavior.

  - name: update-validators-carefully
    description: >
      If validator errors appear, migrate validators without weakening validation.
      Replace validator with field_validator and root_validator with model_validator
      where needed, adapting signatures to Pydantic v2. Do not delete checks, skip
      error branches, or return early merely to satisfy imports. Run the specific
      tests that cover the validator behavior.

  - name: run-targeted-tests-after-each-class-of-change
    description: >
      After each semantic fix, run the smallest failing test that demonstrated the
      problem. In the learned successful trace, a Config instantiation test confirmed
      the Optional default fix, then OpenAPI schema tests confirmed the Literal and
      model_rebuild fixes. Only proceed to broader edits after the targeted failure
      changes or disappears.

  - name: run-the-suite-and-clean-up
    description: >
      Run the full repository test suite before finishing. If failures remain, return
      to the first new traceback rather than broadening the migration blindly. Inspect
      git diff for accidental large rewrites, malformed model_config dictionaries,
      indentation errors, remaining const equals occurrences, imports of pydantic.v1,
      imports of int or str from pydantic, and deleted behavior. The final state should
      pass tests using Pydantic v2 APIs directly.
```