---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the full test suite.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 9
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
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 without using the
  pydantic.v1 shim or deleting behavior. Preserve settings loading, model
  validation, enum serialization, arbitrary framework types, constrained fields,
  standalone email validation, and MIME assembly behavior.

trigger_when:
  - Asked to migrate from Pydantic v1 to v2
  - Pydantic v2 is installed but the project imports Pydantic v1 APIs
  - PydanticImportError for BaseSettings appears
  - EmailStr validate or model_validate errors appear
  - Validator decorator or root validator migration errors appear
  - Tests around email validation, message assembly, or model validation fail after import fixes

anti_patterns:
  - Re-pointing imports to pydantic.v1
  - Emptying function bodies just so imports pass
  - Treating EmailStr as a standalone validator in Pydantic v2
  - Calling EmailStr model_validate because EmailStr is a type annotation
  - Catching and swallowing email validation exceptions when tests expect them
  - Replacing every matching validate_email method without checking its class context
  - Migrating validators without checking whether they need before or after mode
  - Forgetting arbitrary_types_allowed for FastAPI UploadFile or other framework objects
  - Dropping use_enum_values when downstream code compares model fields to strings
  - Changing MIME assembly code before verifying schema enum serialization
  - Stopping after a targeted test passes instead of running the full suite
  - Making broad edits before reading the failing tests and full tracebacks

steps:
  - name: inspect-current-usage-and-tests
    description: >
      List Python files and dependency files, then grep for Pydantic v1 patterns:
      pydantic, BaseSettings, validator, root_validator, conint, class Config,
      EmailStr.validate, EmailStr.model_validate, use_enum_values, and
      pydantic.v1. Read the files containing these patterns and the tests that
      cover them before editing. In this project, the important files were
      config.py, schemas.py, email_utils/email_check.py, fastmail.py, msg.py, and
      tests for checker and message MIME behavior.

  - name: update-dependencies-before-code
    description: >
      Update dependency files to require Pydantic v2 plus split out packages:
      pydantic ^2, pydantic-settings ^2, and email-validator ^2. Then verify the
      environment by printing the Pydantic version and confirming
      pydantic-settings is installed. Do this before diagnosing BaseSettings import
      failures.

  - name: migrate-basesettings-correctly
    description: >
      Replace BaseSettings imports from pydantic with pydantic_settings. Keep the
      import alias and class inheritance consistent. A safe form is to import
      BaseSettings and SettingsConfigDict from pydantic_settings, inherit from
      BaseSettings, and move v1 Config settings into model_config. Include
      arbitrary_types_allowed when settings fields include objects such as Jinja
      Environment.

  - name: migrate-constrained-fields
    description: >
      Replace v1 constrained helpers such as conint with Annotated plus Field
      constraints. For a debug flag formerly constrained to zero or one, use
      Annotated int with Field ge zero and le one. Import Annotated from typing
      and Field from pydantic. Remove obsolete conint imports after the conversion.

  - name: preserve-model-config-options
    description: >
      Replace v1 class Config blocks with model_config or ConfigDict, but preserve
      every option that affected runtime values. For MessageSchema in this project,
      keep arbitrary_types_allowed true and use_enum_values true. The enum setting
      is required because message assembly compares subtype and multipart_subtype
      to string values. A regression without it made the alternative body plus
      attachment test see a plain text payload length instead of a two part
      alternative container.

  - name: migrate-field-and-model-validators
    description: >
      Replace validator with field_validator and add classmethod where the
      validator receives cls and a value. Replace root_validator with
      model_validator. Prefer after mode when the logic needs typed attributes on
      self and return self. Use before mode only when intentionally validating raw
      input dictionaries, and then handle both raw strings and enum instances.
      After changing enum config, retest validators because fields may now be
      strings rather than enum objects.

  - name: preserve-standalone-email-validation
    description: >
      Keep EmailStr as a field annotation, but do not call EmailStr.validate or
      EmailStr.model_validate. For standalone email checking, import validate_email
      from email_validator and call validate_email(email), then return true. If
      invalid email tests expect EmailNotValidError, let the email-validator
      exception propagate instead of catching it and returning false. Inspect each
      validate_email method separately because this codebase had multiple methods
      with the same name.

  - name: verify-imports-before-suite
    description: >
      After edits, run small import checks for ConnectionConfig, MessageSchema,
      DefaultChecker, FastMail, and the package exports. Import failures quickly
      expose stale aliases, missing SettingsConfigDict imports, and missing
      arbitrary_types_allowed before the full suite output becomes noisy.

  - name: verify-message-mime-behavior
    description: >
      Run the message tests that combine alternative_body, multipart_subtype
      alternative, and attachments. Confirm the recorded message has the expected
      nested MIME structure and that the alternative body container has two
      payload parts. If it behaves like a string payload or reports a text length,
      recheck MessageSchema use_enum_values and comparisons in msg.py before
      changing attachment code.

  - name: run-full-suite-and-search-for-remnants
    description: >
      After import checks and targeted tests, run the full test suite without
      truncating the final result. If failures remain, read the complete traceback
      and relevant test before editing. Before declaring completion, grep for
      pydantic.v1, BaseSettings imported from pydantic, root_validator, validator
      decorators, conint, EmailStr.validate, and EmailStr.model_validate. The
      migration is complete only when the full suite passes and no v1 shim or
      behavior-deleting workaround remains.
```