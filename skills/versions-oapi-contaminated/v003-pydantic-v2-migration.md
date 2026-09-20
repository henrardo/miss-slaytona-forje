---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the repository test suite.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces:
      - "2061360d"
      - "8476334f"
      - "ffc6166c"
      - "3077ae6d"
      - "a658584b"
      - "b6b67d44"
      - "1d461637"
      - "4cd39e71"
      - "44870605"
      - "9bd89033"
---

```yaml
# The latest failed attempt got many tests passing but still failed collection
# because openapi_python_client schema/openapi_schema_pydantic/oauth_flow.py had
# an unclosed parenthesis. Treat any pytest collection SyntaxError as the top
# priority even when the summary says hundreds of tests passed.
purpose: >
  Migrate a Python project from Pydantic v1 APIs to real Pydantic v2 APIs,
  preserving validation behavior and running syntax, import, collection, and
  behavioral checks until the repository test suite passes without collection
  warnings or syntax errors.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - The suite fails after installing Pydantic v2 because BaseSettings validator root_validator Config schema_extra or EmailStr validation APIs changed
  - Imports fail with PydanticImportError PydanticUserError schema generation errors or config key warnings after a Pydantic upgrade
  - Pytest collection fails inside a Pydantic model module after edits to ConfigDict Field json_schema_extra validators or schema classes

do_not_use_when:
  - The requested solution is compatibility with both Pydantic v1 and v2 through the pydantic.v1 namespace
  - The codebase already uses Pydantic v2 APIs and the failing tests are unrelated to Pydantic
  - The task is only a dependency pin change without code migration

anti_patterns:
  - Do not import from pydantic.v1
  - Do not empty validators or function bodies just to make imports succeed
  - Do not stop after import checks because collection and behavioral tests can still fail
  - Do not ignore PluggyTeardownRaisedWarning when it wraps a conftest import or SyntaxError
  - Do not treat a pytest collection SyntaxError as a Pydantic behavior problem
  - Do not leave a partly edited Field ConfigDict or json_schema_extra dictionary uncompiled
  - Do not put json_schema_extra inside a Field call unless the original schema customization was field specific
  - Do not replace EmailStr.validate with EmailStr.model_validate because EmailStr has no model_validate method in Pydantic v2
  - Do not catch and suppress email_validator exceptions when tests expect EmailNotValidError to propagate
  - Do not quote only part of an error message in this skill file because YAML validation can read the item incorrectly

steps:
  - name: inventory-and-baseline
    description: >
      From the repository root, inspect dependency files and grep for Pydantic
      usage before editing. Run the suite or at least pytest collection to
      capture the first real failure. Record files using BaseSettings Config
      validator root_validator schema_extra json_encoders parse_obj dict json
      construct from_orm EmailStr.validate constrained types GenericModel
      Field extra keyword arguments or OpenAPI schema model customizations.

  - name: update-dependencies-for-v2
    description: >
      Change dependency metadata from Pydantic v1 to Pydantic v2. If the code
      uses BaseSettings, add pydantic-settings. If it uses EmailStr, keep or add
      email-validator. Do not pin back to Pydantic v1 and do not use pydantic.v1.
      Verify the installed versions with a short python or pip command before
      assuming the environment matches dependency files.

  - name: migrate-imports-with-small-edits
    description: >
      Update imports in the smallest coherent groups. Keep BaseModel EmailStr
      Field ConfigDict TypeAdapter field_validator model_validator and other
      Pydantic v2 imports explicit. When moving BaseSettings to
      pydantic_settings, update the class base at the same time so the module is
      never left importing BaseSettings under one name while inheriting from a
      different old alias.

  - name: migrate-basesettings
    description: >
      Replace BaseSettings imported from pydantic with BaseSettings from
      pydantic_settings. Import SettingsConfigDict when settings configuration
      is needed. Convert inner Config on settings classes to model_config using
      SettingsConfigDict, preserving env_file env_prefix case_sensitive extra
      and similar settings. Keep the class inheriting from BaseSettings after
      changing imports.

  - name: migrate-model-config
    description: >
      Convert inner Config classes on BaseModel subclasses to model_config
      dictionaries or ConfigDict. Preserve arbitrary_types_allowed when models
      contain non-Pydantic types such as UploadFile BytesIO Path file handles or
      framework classes. Rename schema_extra to json_schema_extra and
      allow_population_by_field_name to populate_by_name. Preserve extra allow
      forbid ignore validate_assignment frozen use_enum_values from_attributes
      and aliases when present.

  - name: migrate-schema-extra-with-syntax-guard
    description: >
      When migrating schema_extra or OpenAPI schema models, write a complete and
      balanced ConfigDict expression in one edit. A safe pattern is model_config
      equals ConfigDict with extra or populate settings and json_schema_extra as
      a nested dictionary, then close both the dictionary and the ConfigDict
      call. Immediately open the edited file around the changed block and run
      py_compile or compileall before touching another file. If pytest reports
      an unmatched parenthesis or brace in a schema file such as oauth_flow.py
      response.py security_scheme.py components.py or parameter.py, fix that
      syntax first and rerun compile before changing validation logic.

  - name: migrate-field-validators
    description: >
      Replace validator with field_validator. Add classmethod for field
      validators. Keep the original validator logic rather than returning the
      input unconditionally. For validators that used pre always each_item or
      values, read the local code and Pydantic v2 signature rules before
      translating. Use ValidationInfo only when the validator truly needs other
      values or config. Run a focused construction example for each migrated
      model.

  - name: migrate-cross-field-validators
    description: >
      Replace root_validator with model_validator. Use mode before only when the
      old logic truly needs the raw input dictionary. Use mode after when the old
      logic reasoned about parsed field values or enum members. In after mode,
      mutate or validate self and return self. When comparing enum fields,
      accept both enum members and their values if tests or callers pass either
      form.

  - name: migrate-email-validation
    description: >
      Keep EmailStr as a type annotation for model fields. For standalone email
      validation functions, do not call EmailStr.validate or
      EmailStr.model_validate. Prefer TypeAdapter of EmailStr with
      validate_python when Pydantic validation errors are expected. Prefer
      email_validator validate_email when existing tests expect
      EmailNotValidError or subclasses such as EmailSyntaxError. Let expected
      exceptions propagate instead of catching all exceptions and returning
      False.

  - name: migrate-constrained-types-carefully
    description: >
      Constrained helpers may still import but many projects are cleaner with
      Annotated plus Field constraints. For conint ge le, use Annotated int
      Field ge le. For constr min_length regex, use Annotated str Field
      min_length pattern. Preserve defaults and optionality exactly. After
      changing annotations, instantiate at least one model exercising valid and
      invalid boundary values.

  - name: migrate-renamed-model-methods
    description: >
      Replace parse_obj with model_validate, dict with model_dump, json with
      model_dump_json, construct with model_construct, copy with model_copy, and
      from_orm with model_validate plus from_attributes configuration when that
      code path is present. Only change call sites that exist in the repository.
      If test assertions depend on serialization aliases or excluded none
      values, pass the equivalent keyword arguments to the new method.

  - name: handle-openapi-schema-packages
    description: >
      For packages that model OpenAPI documents, inspect modules imported during
      tests or conftest before making broad replacements. Components Parameter
      Response RequestBody Schema OAuthFlow OAuthFlows SecurityScheme and
      similar files often contain schema_extra examples and extra allow config.
      Migrate one schema module at a time, compile it, then import the package
      schema namespace. A collection failure in tests conftest means package
      imports are broken and must be repaired before any test-specific diagnosis
      is useful.

  - name: run-fast-verification-after-each-edit-group
    description: >
      After each file or small group of edits, run python -m py_compile on every
      changed file or python -m compileall on the changed package. Then run a
      small import command for the package and the specific migrated models.
      This catches regressions like unclosed ConfigDict parentheses malformed
      json_schema_extra blocks and broken oauth_flow imports before pytest
      collection.

  - name: run-tests-and-follow-the-first-real-failure
    description: >
      Run the repository suite without truncating the final failure details. If
      the output includes a PluggyTeardownRaisedWarning or ConftestImportFailure,
      scroll to the nested SyntaxError or ImportError and fix that first. If
      collection fails with SyntaxError, open the reported file and line and fix
      syntax before interpreting any passing test count. If import fails, fix
      the migrated API import or model configuration. If behavioral tests fail,
      inspect the test and preserve the old behavior under Pydantic v2 rather
      than weakening validation. Rerun the focused failing test before the full
      suite.

  - name: final-check
    description: >
      Before finishing, grep for pydantic.v1, BaseSettings imported from
      pydantic, validator, root_validator, EmailStr.validate,
      EmailStr.model_validate and class Config in migrated model files. Any
      remaining occurrence needs a deliberate reason. Run compileall, pytest
      collection, and the full test suite. Report completion only when the suite
      passes and there is no collection SyntaxError hidden behind a warning.
```