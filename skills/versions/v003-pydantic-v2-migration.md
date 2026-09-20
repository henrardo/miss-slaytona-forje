---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 3
    derived_from_traces:
      - 658c1c3c
      - 27b6c4e5
      - 39742bae
      - 56e98440
      - 7ba0c4f5
      - 94239264
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so the repository's
  test suite passes without shimming pydantic.v1 or deleting behavior.

trigger_when:
  - Asked to migrate from Pydantic v1 to v2
  - BaseSettings has been moved to pydantic-settings package error appears
  - EmailStr validate method errors appear
  - Email validation tests fail

anti_patterns:
  - Rewriting imports to pydantic.v1
  - Replacing validator bodies with bare returns
  - Declaring migration complete without running the suite
  - Skipping dependency updates
  - Using EmailStr.validate in Pydantic v2
  - Not implementing proper email validation after removing EmailStr.validate

steps:
  - name: update-dependencies-first
    description: >
      Update pyproject.toml or requirements to require Pydantic v2 and pydantic-settings:
        pydantic = "^2.0"
        pydantic-settings = ">=2.0,<3.0"
        email-validator = ">=2.0,<3.0"
      Rebuild environment and verify pydantic version is 2.x
    outputs:
      - name: pydantic-version
        type: string

  - name: find-all-pydantic-v1-usage
    description: >
      Search for Pydantic v1 patterns: BaseSettings imports validator root_validator
      conint EmailStr class Config EmailStr.validate. Focus on email_utils/email_check.py
      and BaseSettings usage
    outputs:
      - name: files-with-pydantic-v1
        type: list

  - name: migrate-dependencies-file-first
    description: >
      Update dependency files before code changes to ensure correct packages are installed
    outputs:
      - name: deps-updated
        type: boolean

  - name: migrate-basesettings-to-pydantic-settings
    description: >
      Change BaseSettings imports from pydantic to pydantic_settings and update class definitions
    outputs:
      - name: basesettings-migrated
        type: boolean

  - name: migrate-emailstr-imports-and-validation
    description: >
      Change EmailStr imports to pydantic.networks. Remove EmailStr.validate calls.
      Implement proper email validation using email_validator library in email_check.py
    outputs:
      - name: emailstr-imports-migrated
        type: boolean
      - name: email-validation-implemented
        type: boolean

  - name: migrate-constrained-types
    description: >
      Replace Pydantic v1 constrained types with v2 equivalents using Annotated and Field
    outputs:
      - name: constrained-types-migrated
        type: boolean

  - name: migrate-validators-to-v2-api
    description: >
      Update validator and root_validator to field_validator and model_validator
    outputs:
      - name: validators-migrated
        type: boolean

  - name: migrate-config-classes
    description: >
      Update Config classes to use model_config = ConfigDict
    outputs:
      - name: config-migrated
        type: boolean

  - name: run-suite-and-fix-errors-systematically
    description: >
      Run test suite and fix each error using the migration steps. Expect errors related to
      missing imports incorrect validator signatures and email validation failures
    outputs:
      - name: suite-passed
        type: boolean

  - name: clean-up-and-verify-complete
    description: >
      Remove type ignore comments verify no pydantic.v1 imports remain check BaseSettings
      imports are from pydantic_settings and email validation is properly implemented
      Re-run suite to confirm stability
    outputs:
      - name: migration-complete
        type: boolean
```
