---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and getting the repository test suite green.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - b40bc778
      - 13f5ed82
      - c997561c
      - 36ec346f
---

```yaml
# Learned from the successful trace: do not begin with a broad mechanical
# rewrite. In this fixture the dependency was already set to Pydantic v2,
# and the real failures were a few v2 semantic changes left behind.
purpose: >
  Complete a real Pydantic v1 to v2 migration by using the test failures to
  identify remaining v1 assumptions, updating those assumptions directly,
  and verifying with targeted tests followed by the suite.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A repository has already bumped to Pydantic v2 but tests fail with Pydantic validation, config, schema, or forward reference errors
  - A suite fails because Pydantic v2 treats model definitions differently from Pydantic v1

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Do not repoint imports to pydantic.v1 because that is a compatibility shim rather than a migration
  - Do not empty a validator, hook, parser, or function body just to keep imports or tests green
  - Do not mass rewrite every Pydantic model before seeing the actual traceback
  - Do not use broad regex rewrites for Config classes with schema examples because it can corrupt nested dictionaries and create syntax errors
  - Do not replace StrictInt or StrictStr with imports of int or str from pydantic
  - Do not declare the migration complete after only import checks
  - Do not ignore deprecation warnings for schema_extra when the suite still exercises JSON schema generation

steps:
  - name: establish-current-state
    description: >
      Inspect pyproject.toml, requirements files, and the installed environment before changing code. Determine whether the project still depends on Pydantic v1 or has already been bumped to Pydantic v2. If it is still on v1, update the declared dependency to the task target. If it is already on v2, do not churn dependency files. Run the repository test suite or the failing test command and save the first actionable Pydantic error.

  - name: search-pydantic-surface-area
    description: >
      Search the source tree for Pydantic imports and v1-only patterns before editing. Useful searches are from pydantic import, import pydantic, class Config, Extra dot, allow_population_by_field_name, schema_extra, const equals, min_items, max_items, update_forward_refs, parse_obj, dict open paren, json open paren, and BaseSettings. Use these results as an edit checklist, not as permission to blindly rewrite whole files.

  - name: fix-optional-fields-without-defaults
    description: >
      In Pydantic v2, Optional[T] or T union None without a default is still a required field. When tests instantiate a model with missing optional settings and fail with field required validation errors, add an explicit default of None to fields that are semantically optional. In the learned fixture, Config needed project_name_override, package_name_override, and package_version_override changed from Optional[str] with no default to Optional[str] = None. Re-run the targeted failing test immediately after this change.

  - name: migrate-model-config-with-minimal-diffs
    description: >
      Convert v1 Config inner classes only where they still exist or fail. Replace extra = Extra.allow with model_config containing extra set to allow. Replace allow_population_by_field_name with populate_by_name set to true. Keep existing aliases and examples. Prefer direct, reviewed edits over generated regex when a Config contains nested schema examples.

  - name: rename-schema-extra
    description: >
      In Pydantic v2, schema_extra in model_config is renamed to json_schema_extra. Search the source tree for schema_extra and replace the model configuration key while preserving the value exactly. In the learned fixture, the remaining occurrences were in openapi_schema_pydantic model_config dictionaries and were safely handled by replacing the literal key schema_extra with json_schema_extra.

  - name: replace-field-const-with-literal
    description: >
      Pydantic v2 removed Field const. For fields declared with Field(..., const=True), remove the const argument and express the allowed value in the type annotation using Literal. Preserve the default value or required marker. Example pattern: change a string field constrained to a single OpenAPI location into a Literal type rather than relying on Field const.

  - name: handle-openapi-version-literals
    description: >
      If a field annotation is a quoted string containing a Literal expression, Pydantic v2 may treat it as an unresolved forward reference. Replace stringified Literal annotations with real typing.Literal annotations and import Literal from typing. For the OpenAPI schema model, use a normal Literal union for supported openapi versions instead of a quoted annotation.

  - name: rebuild-forward-referenced-models-after-imports
    description: >
      When validation fails because a model is not fully defined or a forward reference such as Operation is unresolved, call model_rebuild after all related models have been imported. A good location for mutually referring OpenAPI schema models is the package __init__.py after all from dot module imports. Rebuild the model that owns the string reference, then any aggregate model that depends on it, and finally the top-level model. In the learned fixture, rebuilding after all openapi_schema_pydantic imports fixed PathItem references to Operation and allowed OpenAPI validation tests to pass.

  - name: use-v2-method-names-when-tests-require
    description: >
      If tests or warnings expose v1 method usage, update BaseModel calls to v2 names. Common replacements are parse_obj to model_validate, dict to model_dump, json to model_dump_json, schema to model_json_schema, copy to model_copy, construct to model_construct, and update_forward_refs to model_rebuild. Keep compatibility wrappers only when the project deliberately supports both versions and tests require that behavior.

  - name: update-validators-carefully
    description: >
      If validator errors appear, migrate validators without weakening validation. Replace validator with field_validator and root_validator with model_validator where needed, adapting signatures to Pydantic v2. Do not delete checks, skip error branches, or return early merely to satisfy imports. Run the specific tests that cover the validator behavior.

  - name: run-targeted-tests-after-each-class-of-change
    description: >
      After each semantic fix, run the smallest failing test that demonstrated the problem. In the learned successful trace, a Config instantiation test confirmed the Optional default fix, then OpenAPI schema tests confirmed the Literal and model_rebuild fixes. Only proceed to broader edits after the targeted failure changes or disappears.

  - name: run-the-suite-and-clean-up
    description: >
      Run the full repository test suite before finishing. If failures remain, return to the first new traceback rather than broadening the migration blindly. Inspect git diff for accidental large rewrites, malformed model_config dictionaries, imports of pydantic.v1, imports of int or str from pydantic, and deleted behavior. The final state should pass tests using Pydantic v2 APIs directly.
```