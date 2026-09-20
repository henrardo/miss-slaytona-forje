---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the full test suite.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 5
    derived_from_traces:
      - '658c1c3c'
      - '27b6c4e5'
      - '39742bae'
      - '56e98440'
      - '7ba0c4f5'
      - '94239264'
      - '1aa4ff21'
      - '2467970a'
      - '088b88cf'
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 without using the
  pydantic.v1 shim or deleting real behavior. Preserve validation semantics,
  especially settings loading, custom validators, arbitrary framework types,
  constrained fields, and standalone email validation.

trigger_when:
  - Asked to migrate from Pydantic v1 to v2
  - Pydantic v2 is installed but the project imports Pydantic v1 APIs
  - 'PydanticImportError: BaseSettings has been moved appears'
  - EmailStr.validate or EmailStr.model_validate errors appear
  - Validator decorator or root validator migration errors appear
  - Tests around email validation or model validation fail after import fixes

anti_patterns:
  - Re-pointing imports to pydantic.v1
  - Emptying function bodies just so imports pass
  - Treating EmailStr as a standalone validator in Pydantic v2
  - Catching and swallowing email validation exceptions when tests expect them
  - Migrating validators without checking whether they need before or after mode
  - Forgetting arbitrary_types_allowed for FastAPI UploadFile or other framework objects
  - Declaring success after import checks without running the full suite
  - Making broad edits before reading the failing tests

steps:
  - name: inspect-current-usage-and-tests
    description: >
      List Python files and dependency files, then grep for Pydantic v1 patterns:
      pydantic, BaseSettings, validator, root_validator, conint, class Config,
      EmailStr.validate, and pydantic.v1. Read the files containing these patterns
      and the tests that cover them before editing. In the successful attempts,
      reading config.py, schemas.py, email_utils/email_check.py, fastmail.py, and
      the relevant tests prevented wrong fixes.

  - name: update-dependencies-before-code
    description: >
      Update dependency files to require Pydantic v2 plus the packages split out
      from Pydantic:
      pydantic = ^2.0
      pydantic-settings = ^2.0
      email-validator = ^2.0
      Then verify the environment with a small command that prints pydantic version
      and confirms pydantic-settings is installed. Do this before diagnosing import
      failures, because BaseSettings migration depends on the new package.

  - name: migrate-basesettings-correctly
    description: >
      Replace BaseSettings imports from pydantic with pydantic_settings. Keep aliases
      consistent with the class definition; a common regression was importing
      BaseSettings but leaving class ConnectionConfig(Settings), or importing an
      alias and then inheriting from BaseSettings. Use one consistent form:
      from pydantic_settings import BaseSettings, SettingsConfigDict
      class ConnectionConfig(BaseSettings)
      Preserve settings configuration with model_config = SettingsConfigDict(...)
      rather than a v1 Config class. Include arbitrary_types_allowed when settings
      fields include objects such as Jinja Environment.

  - name: migrate-constrained-fields
    description: >
      Replace v1 constrained helper usage such as conint with Annotated and Field
      constraints. For example, a debug flag that was conint(gt=-1, lt=2) becomes
      Annotated[int, Field(ge=0, le=1)]. Import Annotated from typing and Field
      from pydantic. Keep the public field type behavior the same and avoid leaving
      obsolete conint imports behind.

  - name: migrate-model-config-and-arbitrary-types
    description: >
      Replace v1 class Config blocks with model_config. For BaseModel classes that
      contain non-Pydantic arbitrary types such as FastAPI UploadFile, add:
      model_config = ConfigDict(arbitrary_types_allowed=True)
      or an equivalent dict. This fixed schema import failures in the passing trace.
      Do not wait for the full suite if a simple import of the model already fails.

  - name: migrate-field-and-model-validators
    description: >
      Replace @validator with @field_validator and add @classmethod where the
      validator receives cls and a value. Replace @root_validator with
      @model_validator. Prefer mode='after' when the logic needs typed attributes
      on self, such as enum fields and related model fields. Use mode='before'
      only when intentionally validating the raw input dict, and then handle both
      raw strings and enum instances. For after validators, return self.

  - name: handle-emailstr-as-a-type-not-a-validator
    description: >
      Keep EmailStr as a field annotation, usually from pydantic, but do not call
      EmailStr.validate or EmailStr.model_validate. For standalone email checking
      functions, use the email-validator package directly:
      from email_validator import validate_email, EmailNotValidError
      validate_email(email)
      return True
      If invalid-email tests expect EmailNotValidError, let that exception propagate
      instead of catching it and returning False. This was the final fix that made
      the suite pass.

  - name: verify-incrementally-with-imports-and-targeted-tests
    description: >
      After migration edits, run import checks for the changed public modules before
      the full suite. For example, import ConnectionConfig, MessageSchema,
      DefaultChecker, FastMail, and package-level exports. Then run targeted failing
      tests to shorten feedback, especially email checker tests and message schema
      validator tests. Fix import errors before validator behavior failures.

  - name: run-full-suite-and-search-for-remnants
    description: >
      Run the full test suite without truncating the final result. If failures remain,
      read the complete traceback and the relevant test rather than guessing. Before
      declaring completion, grep for pydantic.v1, BaseSettings from pydantic,
      root_validator, @validator, conint, EmailStr.validate, and EmailStr.model_validate.
      The migration is complete only when the full suite passes and no v1 shim or
      behavior-deleting workaround remains.
```