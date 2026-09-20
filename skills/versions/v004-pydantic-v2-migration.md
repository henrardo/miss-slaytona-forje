---
name: pydantic-v2-migration

description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 4
    derived_from_traces:
      - 658c1c3c
      - 27b6c4e5
      - 39742bae
      - 56e98440
      - 7ba0c4f5
      - 94239264
      - 1aa4ff21
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so the repository's
  test suite passes without shimming pydantic.v1 or deleting behavior. This procedure
  has been validated against multiple codebases and captures what consistently works.

trigger_when:
  - Asked to migrate from Pydantic v1 to v2
  - BaseSettings has been moved to the pydantic-settings package error appears
  - EmailStr has no attribute validate error appears
  - Email validation tests fail
  - Validator decorator errors appear

anti_patterns:
  - Rewriting imports to pydantic.v1
  - Replacing validator bodies with bare returns
  - Declaring migration complete without running the suite
  - Skipping dependency updates
  - Using EmailStr.validate in Pydantic v2
  - Not implementing proper email validation after removing EmailStr.validate
  - Migrating BaseSettings before updating dependencies
  - Updating code before updating dependency files

steps:
  - name: update-dependencies-first
    description: >
      Update pyproject.toml or requirements to require Pydantic v2 and pydantic-settings:
        pydantic = "^2.0"
        pydantic-settings = ">=2.0,<3.0"
        email-validator = ">=2.0,<3.0"
      Rebuild environment and verify pydantic version is 2.x using:
        python -c "import pydantic; print(pydantic.__version__)"
    outputs:
      - name: pydantic-version
        type: string
      - name: pydantic-settings-installed
        type: boolean

  - name: find-all-pydantic-v1-usage
    description: >
      Search for Pydantic v1 patterns: BaseSettings imports validator root_validator
      conint EmailStr class Config EmailStr.validate. Focus on email_utils/email_check.py
      and BaseSettings usage. Use grep to find all occurrences:
        grep -r "BaseSettings\|root_validator\|conint\|EmailStr\.validate" .
    outputs:
      - name: files-with-pydantic-v1
        type: list

  - name: migrate-basesettings-to-pydantic-settings
    description: >
      Change BaseSettings imports from pydantic to pydantic_settings and update class definitions:
        from pydantic import BaseSettings as Settings
        =>
        from pydantic_settings import BaseSettings as Settings
      Update class inheritance:
        class ConnectionConfig(Settings)
        =>
        class ConnectionConfig(BaseSettings)
      Add model_config for SettingsConfigDict if needed:
        model_config = SettingsConfigDict(arbitrary_types_allowed=True)
    outputs:
      - name: basesettings-migrated
        type: boolean

  - name: migrate-emailstr-imports-and-validation
    description: >
      Change EmailStr imports to pydantic.networks. Remove EmailStr.validate calls.
      In email_utils/email_check.py replace EmailStr.validate(email) with proper
      email validation using email_validator library:
        from email_validator import validate_email, EmailNotValidError
        try:
            validate_email(email)
        except EmailNotValidError:
            raise ValueError(Invalid email)
    outputs:
      - name: emailstr-imports-migrated
        type: boolean
      - name: email-validation-implemented
        type: boolean

  - name: migrate-constrained-types
    description: >
      Replace Pydantic v1 constrained types with v2 equivalents using Annotated and Field:
        from pydantic import conint
        port: conint(gt=-1, lt=2)
        =>
        from typing import Annotated
        from pydantic import Field
        port: Annotated[int, Field(ge=0, le=1)]
    outputs:
      - name: constrained-types-migrated
        type: boolean

  - name: migrate-validators-to-v2-api
    description: >
      Update validator and root_validator to field_validator and model_validator:
        from pydantic import validator, root_validator
        @validator(field)
        def validate_field(cls, v): ...
        @root_validator
        def check_something(cls, values): ...
        =>
        from pydantic import field_validator, model_validator
        @field_validator(field)
        @classmethod
        def validate_field(cls, v): ...
        @model_validator(mode=after)
        def check_something(self): ...
    outputs:
      - name: validators-migrated
        type: boolean

  - name: migrate-config-classes
    description: >
      Update Config classes to use model_config = ConfigDict. Replace:
        class Config:
            arbitrary_types_allowed = True
        =>
        model_config = ConfigDict(arbitrary_types_allowed=True)
      Import ConfigDict from pydantic.
    outputs:
      - name: config-migrated
        type: boolean

  - name: run-suite-and-fix-errors-systematically
    description: >
      Run test suite and fix each error using the migration steps. Expect errors related to
      missing imports incorrect validator signatures and email validation failures.
      Fix errors in order: imports first then validators then email validation.
      Use grep to find remaining issues:
        grep -r "BaseSettings\|root_validator\|EmailStr\.validate\|conint" .
    outputs:
      - name: suite-passed
        type: boolean

  - name: clean-up-and-verify-complete
    description: >
      Remove type ignore comments verify no pydantic.v1 imports remain check BaseSettings
      imports are from pydantic_settings and email validation is properly implemented.
      Verify no EmailStr.validate calls remain. Re-run suite to confirm stability.
      Check for any remaining v1 patterns:
        grep -r "pydantic\.v1\|BaseSettings.*from pydantic\|EmailStr\.validate" . || true
    outputs:
      - name: migration-complete
        type: boolean
      - name: no-v1-remnants
        type: boolean
```
