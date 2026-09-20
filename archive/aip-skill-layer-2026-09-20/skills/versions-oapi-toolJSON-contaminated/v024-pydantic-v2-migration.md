---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the full test suite.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 24
    derived_from_traces:
      - '738b4882'
      - '23e5cd8a'
      - '7ec14fc1'
      - 'fbadf6f2'
      - 'bcd6adbe'
      - '512a80b8'
      - 'ccc3a201'
      - '2bcb35cc'
      - '093a5290'
      - '1ce8fd14'
      - '66c5f797'
      - 'f7f84cae'
      - '5fd83784'

---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 preserving behavior without v1 shims
  Update imports model configs parser methods and settings while keeping all validation logic intact
  Address Pydantic v2 deprecations including const keyword removal BaseSettings relocation v1 type removals
  and Config class migration Ensure all model configurations use ConfigDict and validation works with pydantic_core
trigger_when:
  - Pydantic v2 is installed but BaseSettings import fails
  - PydanticImportError appears for BaseSettings or v1 classes
  - model_config errors or Extra enum issues occur
  - Tests fail after dependency update with migration related errors
  - PydanticUserError const is removed use Literal instead
  - ImportError while loading conftest const keyword usage
  - AttributeError type object EmailStr has no attribute validate
  - pydantic_core._pydantic_core.Validation errors during model instantiation
  - AttributeError type object Config has no attribute parse_obj
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
  - Running tests before verifying all files compile
  - Not verifying all occurrences of const usage including Field(const=True)
  - Migrating BaseSettings before fixing all v1 type references
  - Fixing EmailStr.validate calls without replacing EmailStr with str
  - Migrating Config class without updating to ConfigDict
  - Leaving Config class with parse_obj method calls
steps:
  - name: verify-pydantic-v2-dependency
    description: >
      Ensure Pydantic v2 is installed and accessible
      python -c import pydantic print pydantic.__version__ should show >=2.7.0
      Ensure pydantic-settings is installed python -c import pydantic_settings print OK
      Verify no v1 shims exist in environment by checking sys.path for pydantic.v1

  - name: grep-for-const-usage-in-field-definitions
    description: >
      Search for all const usage including Field(const=True) patterns
      grep -rn const=True --include *.py . || true
      grep -rn Field.*const --include *.py . || true
      Read files containing these patterns to understand scope

  - name: grep-for-emailstr-and-other-v1-types
    description: >
      Search for v1 type usage that needs updating
      grep -rn EmailStr validator root_validator conint constr confloat --include *.py . || true

  - name: grep-for-basesettings-imports
    description: >
      Search for BaseSettings imports from pydantic
      grep -rn from pydantic import.*BaseSettings --include *.py . || true
      grep -rn from pydantic import BaseSettings --include *.py . || true

  - name: grep-for-config-class-usage
    description: >
      Search for v1 Config class usage
      grep -rn class Config: --include *.py . || true
      grep -rn parse_obj --include *.py . || true

  - name: migrate-basesettings-imports
    description: >
      Replace BaseSettings imports from pydantic to pydantic_settings
      Import BaseSettings and SettingsConfigDict from pydantic_settings only
      Do not import BaseSettings from pydantic v1
      Keep import aliases and class inheritance consistent

  - name: replace-const-field-with-literal-types
    description: >
      Replace all occurrences of const=True in Field() with Literal type annotations
      For fields like name = Field(default='' const=True) change to name: Literal[''] = Field(default='')
      For fields like param_in = Field(default=ParameterLocation.HEADER const=True alias='in') change to param_in: Literal[ParameterLocation.HEADER] = Field(default=ParameterLocation.HEADER alias='in')
      For Field(const=True) change to use Literal in type annotation
      Import Literal from typing where needed

  - name: convert-class-config-to-model-config
    description: >
      Replace v1 class Config blocks with model_config equals ConfigDict open paren close paren
      Convert extra equals Extra.allow to extra equals single quote allow single quote
      Convert extra equals Extra.forbid to extra equals single quote forbid single quote
      Convert allow_population_by_field_name equals True to populate_by_name equals True
      Convert schema_extra equals open brace close brace to json_schema_extra equals open brace close brace
      Import ConfigDict from pydantic where model_config is used
      Remove parse_obj method calls from Config classes
      Replace Config.parse_obj with direct model instantiation

  - name: preserve-arbitrary-types-allowed
    description: >
      Set arbitrary_types_allowed equals True in model_config when models contain framework objects
      This preserves behavior for FastAPI UploadFile Jinja2 Environment and similar types

  - name: update-parser-code-for-v2
    description: >
      Replace deprecated parser methods parse_obj to model_validate dict open paren close paren
      Replace schema open paren close paren to model_json_schema
      Update any code that calls these deprecated methods

  - name: update-v1-type-references
    description: >
      Replace EmailStr with str in type hints
      Replace validator with field_validator
      Replace root_validator with model_validator
      Update any imports of these v1 types

  - name: verify-all-files-compile
    description: >
      Run python -m py_compile on all Python files to catch syntax errors
      Fix any compilation errors immediately before proceeding
      python -m py_compile $(find . -name *.py -type f) 2>&1 || true

  - name: run-import-checks
    description: >
      Verify critical imports work from pydantic_settings import BaseSettings SettingsConfigDict
      from pydantic import ConfigDict Field str
      Import key models and run small import tests to catch missing imports early

  - name: run-full-test-suite
    description: >
      Run the complete test suite without truncating output
      pytest -xvs --tb=short
      Read the complete traceback and relevant test before editing
      Do not declare success until all tests pass and no v1 shim remains
```
