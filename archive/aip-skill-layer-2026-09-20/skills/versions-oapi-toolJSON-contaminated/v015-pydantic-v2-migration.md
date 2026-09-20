---
name: pydantic-v2-migration

description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the full test suite.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 15
    derived_from_traces:
      - '738b4882'
      - '60b979d0'
      - '56684b1d'
      - '403287a9'
      - '2a27ad5e'
      - '907a2e29'
      - '658c1c3c'
      - '27b6c4e5'
      - '39742bae'
      - '56e98440'
      - '7ba0c4f5'
      - '94239264'
      - '1aa4ff21'
      - '2467970a'
      - '088b88cf'
      - '32a6fafb'
      - '1b15299e'
      - '3e995050'
      - 'e9cd5820'
      - '2061360d'
      - '2be96149'
      - 'b504db90'
      - '8476334f'
      - '8ca6563d'
      - 'ffc6166c'
      - '60dbc5f7'
      - '3077ae6d'
      - '2d5b7635'
      - 'a658584b'
      - 'b6b67d44'
      - 'cf66f296'
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 without using the
  pydantic.v1 shim or deleting behavior. Preserve model validation, ConfigDict
  settings, Extra enum usage, json_schema_extra, populate_by_name, and all
  framework-specific types. Ensure the full test suite passes without v1 shims.

trigger_when:
  - Asked to migrate from Pydantic v1 to v2
  - Pydantic v2 is installed but BaseSettings import fails
  - PydanticImportError for BaseSettings appears
  - NameError that ConfigDict is not defined
  - Validation errors about Extra enum values
  - Tests fail after dependency update with model_config errors

anti_patterns:
  - Re-pointing imports to pydantic.v1
  - Emptying function bodies just so imports pass
  - Leaving v1 Config classes with class Config extra equals Extra.allow
  - Using Extra.allow instead of extra equals single quote allow single quote in model_config
  - Using allow_population_by_field_name instead of populate_by_name
  - Using schema_extra instead of json_schema_extra
  - Forgetting to import ConfigDict where model_config is used
  - Stopping after a targeted test passes instead of running the full suite
  - Making broad edits before reading failing tests and full tracebacks
  - Trusting truncated pytest output as the final result
  - Using wrong workspace path after a command fails
  - Not verifying all files compile before running tests

steps:
  - name: verify-pydantic-v2-dependency
    description: >
      Update pyproject.toml or requirements files to require Pydantic v2
      pydantic greater than or equal to 2.1.1 less than 2.10 and pydantic-settings greater than or equal to 2.0.0
      Verify installation by running python -c import pydantic print pydantic.__version__
      Confirm pydantic-settings is installed python -c import pydantic_settings

  - name: migrate-basesettings-imports
    description: >
      Replace BaseSettings imports from pydantic to pydantic_settings
      Import BaseSettings and SettingsConfigDict from pydantic_settings
      Keep import aliases and class inheritance consistent. Preserve env_file
      behavior and add arbitrary_types_allowed when needed for framework types

  - name: grep-for-v1-config-patterns
    description: >
      Search for v1 patterns class Config extra equals Extra dot allow
      allow_population_by_field_name schema_extra parse_obj conint constr confloat
      validator root_validator. Read files containing these patterns before editing

  - name: convert-class-config-to-model-config
    description: >
      Replace v1 class Config blocks with model_config equals ConfigDict open paren close paren
      Convert extra equals Extra.allow to extra equals single quote allow single quote
      and extra equals Extra.forbid to extra equals single quote forbid single quote
      Convert allow_population_by_field_name equals True to populate_by_name equals True
      Convert schema_extra equals open brace close brace to json_schema_extra equals open brace close brace
      Import ConfigDict from pydantic where model_config is used

  - name: preserve-arbitrary-types-allowed
    description: >
      Ensure arbitrary_types_allowed is set to true in model_config when models
      contain framework objects like FastAPI UploadFile Jinja2 Environment or
      other non-serializable types. This is critical for preserving behavior

  - name: update-parser-code-for-v2
    description: >
      Replace deprecated parser methods parse_obj to model_validate dict open paren close paren to model_dump
      schema open paren close paren to model_json_schema. Update any code that calls these methods

  - name: verify-all-files-compile
    description: >
      Run python -m py_compile on all Python files to catch syntax errors
      before running tests. Fix any compilation errors immediately

  - name: run-import-checks
    description: >
      After edits verify critical imports work from pydantic_settings import BaseSettings SettingsConfigDict
      from pydantic import ConfigDict Field EmailStr. Import key models and run small
      import tests to catch missing imports early

  - name: run-targeted-behavior-tests
    description: >
      Run tests for the most complex model behaviors email validation MIME assembly
      enum serialization constrained fields and settings loading. Confirm these
      critical paths work before running the full suite

  - name: run-full-test-suite
    description: >
      Run the complete test suite without truncating output. If failures remain
      read the complete traceback and relevant test before editing. Do not declare
      success until all tests pass and no v1 shim or workaround remains

  - name: grep-for-remaining-v1-patterns
    description: >
      After tests pass grep for pydantic.v1 imports BaseSettings from pydantic
      root_validator validator decorators conint constr parse_obj dict schema
      and EmailStr.validate EmailStr.model_validate. Remove any remaining v1 patterns
```
