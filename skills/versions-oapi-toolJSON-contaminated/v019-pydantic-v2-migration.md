---
name: pydantic-v2-migration

description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the full test suite.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 19
    derived_from_traces:
      - '738b4882'
      - '23e5cd8a'
      - '403287a9'
      - 'ba98602c'
      - '907a2e29'
      - '2a27ad5e'
      - '512a80b8'
      - '7ec14fc1'
      - 'fbadf6f2'
      - 'ccc3a201'
      - '2bcb35cc'
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 preserving behavior without v1 shims.
  Update imports, model configs, parser methods, and settings while keeping all validation logic intact.
  Address Pydantic v2 deprecations including const keyword removal and v1 class Config removal.
trigger_when:
  - Pydantic v2 is installed but BaseSettings import fails
  - PydanticImportError appears for BaseSettings or v1 classes
  - model_config errors or Extra enum issues occur
  - Tests fail after dependency update with migration-related errors
  - 'PydanticUserError: `const` is removed, use `Literal` instead'
  - 'ImportError while loading conftest: const keyword usage'
anti_patterns:
  - Using pydantic.v1 imports or shims
  - Emptying function bodies to make imports pass
  - Leaving v1 class Config blocks with class Config extra equals Extra.allow
  - Using allow_population_by_field_name instead of populate_by_name
  - Using schema_extra instead of json_schema_extra
  - Forgetting to import ConfigDict where model_config is used
  - Stopping after a targeted test passes instead of running the full suite
  - Making broad edits before reading failing tests and full tracebacks
  - Trusting truncated pytest output as the final result
  - Ignoring Literal type usage where const was previously used
  - Using const=True in Field definitions
steps:
  - name: verify-pydantic-v2-dependency
    description: >
      Ensure pyproject.toml or requirements files require Pydantic v2 pydantic greater than or equal to 2.1.1 less than 2.10
      Verify installation python -c 'import pydantic; print(pydantic.__version__)'
      Ensure pydantic-settings is installed python -c 'import pydantic_settings'

  - name: grep-for-v1-patterns-before-editing
    description: >
      Search for v1 patterns and const usage across the codebase before making changes
      grep -r 'class Config extra equals Extra' --include '*.py'
      grep -r 'allow_population_by_field_name' --include '*.py'
      grep -r 'schema_extra' --include '*.py'
      grep -r 'parse_obj' --include '*.py'
      grep -r 'const=True' --include '*.py'
      Read files containing these patterns to understand scope

  - name: migrate-basesettings-imports
    description: >
      Replace BaseSettings imports from pydantic to pydantic_settings
      Import BaseSettings and SettingsConfigDict from pydantic_settings
      Keep import aliases and class inheritance consistent

  - name: migrate-pydantic-imports-to-v2
    description: >
      Replace imports from pydantic to pydantic v2 class names
      Import Field EmailStr validator root_validator conint constr confloat from pydantic
      Update any imports like EmailStr.validate to use v2 API

  - name: replace-const-field-with-literal-types
    description: >
      Replace all occurrences of const=True in Field() with Literal type annotations
      For fields like name = Field(default='', const=True) change to name: Literal[''] = Field(default='')
      For fields like param_in = Field(default=ParameterLocation.HEADER, const=True, alias='in') change to param_in: Literal[ParameterLocation.HEADER] = Field(default=ParameterLocation.HEADER, alias='in')
      Import Literal from typing where needed

  - name: convert-class-config-to-model-config
    description: >
      Replace v1 class Config blocks with model_config equals ConfigDict open paren close paren
      Convert extra equals Extra.allow to extra equals single quote allow single quote
      Convert extra equals Extra.forbid to extra equals single quote forbid single quote
      Convert allow_population_by_field_name equals True to populate_by_name equals True
      Convert schema_extra equals open brace close brace to json_schema_extra equals open brace close brace
      Import ConfigDict from pydantic where model_config is used

  - name: preserve-arbitrary-types-allowed
    description: >
      Set arbitrary_types_allowed equals True in model_config when models contain framework objects
      This preserves behavior for FastAPI UploadFile Jinja2 Environment and similar types

  - name: update-parser-code-for-v2
    description: >
      Replace deprecated parser methods parse_obj to model_validate dict open paren close paren
      Replace schema open paren close paren to model_json_schema
      Update any code that calls these deprecated methods

  - name: verify-all-files-compile
    description: >
      Run python -m py_compile on all Python files to catch syntax errors
      Fix any compilation errors immediately before proceeding

  - name: run-import-checks
    description: >
      Verify critical imports work from pydantic_settings import BaseSettings SettingsConfigDict
      from pydantic import ConfigDict Field EmailStr validator root_validator conint constr confloat
      Import key models and run small import tests to catch missing imports early

  - name: run-full-test-suite
    description: >
      Run the complete test suite without truncating output
      Read the complete traceback and relevant test before editing
      Do not declare success until all tests pass and no v1 shim remains
```
