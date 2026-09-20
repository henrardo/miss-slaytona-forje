---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the repository test suite.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - "2061360d"
      - "8476334f"
      - "ffc6166c"
      - "3077ae6d"
      - "a658584b"
      - "b6b67d44"
---

```yaml
# The most recent failed attempt regressed before collection with a SyntaxError
# in openapi_python_client/schema/openapi_schema_pydantic/parameter.py caused by
# a malformed edit. Put syntax verification before interpreting test failures.
purpose: >
  Migrate a Python project from Pydantic v1 APIs to real Pydantic v2 APIs,
  preserving validation behavior and running the repository tests until the
  suite passes.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - The suite fails after installing Pydantic v2 because BaseSettings validator root_validator Config schema_extra or EmailStr validation APIs changed
  - Imports fail with PydanticImportError PydanticUserError or schema generation errors after a Pydantic upgrade

do_not_use_when:
  - The requested solution is compatibility with both Pydantic v1 and v2 through the pydantic.v1 namespace
  - The codebase already uses Pydantic v2 APIs and the failing tests are unrelated to Pydantic
  - The task is only a dependency pin change without code migration

anti_patterns:
  - Do not import from pydantic.v1
  - Do not empty validators or function bodies just to make imports succeed
  - Do not stop after import checks because collection and behavioral tests can still fail
  - Do not treat a pytest collection SyntaxError as a Pydantic behavior problem
  - Do not leave a partly edited Field or json_schema_extra dictionary uncompiled
  - Do not replace EmailStr.validate with EmailStr.model_validate because EmailStr has no model_validate method in Pydantic v2
  - Do not catch and suppress email_validator exceptions when tests expect EmailNotValidError to propagate
  - Do not quote only part of an error message in this skill file because YAML validation can read the item incorrectly

steps:
  - name: inventory-and-baseline
    description: >
      From the repository root, inspect dependency files and grep for Pydantic
      usage before editing. Run the suite or at least pytest collection to
      capture the first real failure. Record files using BaseSettings Config
      validators root_validator schema_extra json_encoders parse_obj dict json
      construct from_orm EmailStr.validate or constrained types.

  - name: update-dependencies-for-v2
    description: >
      Change dependency metadata from Pydantic v1 to Pydantic v2. If the code
      uses BaseSettings, add pydantic-settings. If it uses EmailStr, keep or add
      email-validator. Do not pin back to Pydantic v1 and do not use pydantic.v1.

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
      allow_population_by_field_name to populate_by_name. Recheck indentation and
      braces around Field and json_schema_extra edits.

  - name: migrate-field-validators
    description: >
      Replace validator with field_validator. Add classmethod for field
      validators. Keep the original validator logic rather than returning the
      input unconditionally. For validators that used always pre each_item or
      values, read the local code and Pydantic v2 signature rules before
      translating. Run a focused construction example for each migrated model.

  - name: migrate-cross-field-validators
    description: >
      Replace root_validator with model_validator. Use mode before only when the
      old logic truly needs the raw input dictionary. Use mode after when the old
      logic reasoned about parsed field values or enum members. In after mode,
      mutate or validate self and return self. When comparing enum fields, accept
      both enum members and their values if tests or callers pass either form.

  - name: migrate-email-validation
    description: >
      Keep EmailStr as a type annotation for model fields. For standalone email
      validation functions, do not call EmailStr.validate or
      EmailStr.model_validate. Prefer TypeAdapter(EmailStr).validate_python when
      Pydantic validation errors are expected. Prefer email_validator
      validate_email when existing tests expect EmailNotValidError or subclasses
      such as EmailSyntaxError. Let expected exceptions propagate instead of
      catching all exceptions and returning False.

  - name: migrate-constrained-types-carefully
    description: >
      Constrained helpers may still import but many projects are cleaner with
      Annotated plus Field constraints. For conint ge le, use Annotated int
      Field ge le. For constr min_length regex, use Annotated str Field
      min_length pattern. Preserve defaults and optionality exactly.

  - name: migrate-renamed-model-methods
    description: >
      Replace parse_obj with model_validate, dict with model_dump, json with
      model_dump_json, construct with model_construct, copy with model_copy, and
      from_orm with model_validate plus from_attributes configuration when that
      code path is present. Only change call sites that exist in the repository.

  - name: repair-json-schema-customization
    description: >
      When migrating schema_extra or OpenAPI schema models, inspect the edited
      file around every json_schema_extra or Field block. Ensure dictionaries are
      balanced and nested under the correct call or model_config. If pytest
      reports unmatched brace or syntax error in a schema file, open that file
      at the reported line and fix the syntax before changing any Pydantic logic.

  - name: run-fast-verification-after-each-edit-group
    description: >
      After each group of edits, run python -m compileall on the changed package
      or at least python -m py_compile on changed files. Then run a small import
      command for the package and the specific migrated models. This catches
      regressions like unmatched closing braces before pytest collection.

  - name: run-tests-and-follow-the-first-real-failure
    description: >
      Run the repository suite without truncating the final failure details. If
      collection fails with SyntaxError, fix syntax first. If import fails, fix
      the migrated API import or model configuration. If behavioral tests fail,
      inspect the test and preserve the old behavior under Pydantic v2 rather
      than weakening validation.

  - name: final-check
    description: >
      Before finishing, grep for pydantic.v1, BaseSettings imported from
      pydantic, validator, root_validator, EmailStr.validate, and
      EmailStr.model_validate. Any remaining occurrence needs a deliberate
      reason. Run the full test suite and report completion only when it passes.
```