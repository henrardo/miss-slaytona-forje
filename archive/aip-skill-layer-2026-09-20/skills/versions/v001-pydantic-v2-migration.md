---
name: pydantic-v2-migration
description: Procedure this agent has distilled for migrating a Python codebase from Pydantic v1 to Pydantic v2. Version 0 is an empty scaffold containing no migration knowledge; every procedural step is written by the agent itself from its own graded attempts. Use when asked to migrate a codebase to Pydantic v2.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 1
    derived_from_traces:
      - 658c1c3c
      - 27b6c4e5
---

```yaml
# VERSION 1: DISTILLED FROM TWO SUCCESSFUL ATTEMPTS (658c1c3c, 27b6c4e5)
#
# Key lessons:
# - Do not re-point imports at pydantic.v1; migrate fully to v2 APIs.
# - Do not empty function bodies just to make imports work.
# - Always run the full test suite after each change.
# - BaseSettings moved to pydantic-settings; install and import from there.
# - @validator -> @field_validator; @root_validator -> @model_validator(mode='after').
# - conint(...) -> Annotated[int, Field(ge=..., le=...)]
# - EmailStr.validate(email) -> use EmailStr as a type; for programmatic validation, use email_validator.
# - Update pyproject.toml: pydantic>=2.0, add pydantic-settings>=2.0,<3.0, update email-validator>=2.0,<3.0.
# - Replace old Config class with model_config = ConfigDict(...).
# - Add model_config = ConfigDict(arbitrary_types_allowed=True) where needed.
# - Ensure all imports of EmailStr use from pydantic.networks import EmailStr.

purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so that the
  repository's own test suite passes, without shimming pydantic.v1 and
  without deleting behaviour to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with pydantic import or validator errors after a
    Pydantic v2 upgrade

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working. This
    passes some tests and is not a migration.
  - Replacing a validator body with a bare return so the function still
    imports. The suite goes green and the behaviour is gone.
  - Declaring the migration complete without running the suite.
  - Skipping dependency updates in pyproject.toml/pip requirements.

steps:
  - name: update-dependencies
    description: >
      Update dependency specifications to require Pydantic v2 and pydantic-settings.
      For pyproject.toml:
        pydantic = "^2.0"
        pydantic-settings = ">=2.0,<3.0"
        email-validator = ">=2.0,<3.0"
      Rebuild the environment (pip install -e . or equivalent).
    outputs:
      - name: pydantic-version
        type: string
      - name: pydantic-settings-installed
        type: boolean

  - name: find-pydantic-v1-usage
    description: >
      Search the codebase for Pydantic v1 usage patterns:
        - from pydantic import BaseSettings
        - from pydantic import validator, root_validator
        - from pydantic import conint, EmailStr
        - class Config:
            arbitrary_types_allowed = True
      Record all files and usages for migration.
    outputs:
      - name: files-with-pydantic-v1
        type: list
      - name: usages
        type: map

  - name: migrate-basesettings
    description: >
      For each file importing BaseSettings:
        - Change: from pydantic import BaseSettings as Settings
        - To: from pydantic_settings import BaseSettings as Settings
      Update any class definitions: class MyConfig(Settings) -> class MyConfig(BaseSettings).
      If using SettingsConfigDict, import it from pydantic_settings.
    outputs:
      - name: basesettings-migrated
        type: boolean

  - name: migrate-validators
    description: >
      For each file using @validator or @root_validator:
        - Change: from pydantic import validator, root_validator
        - To: from pydantic import field_validator, model_validator
        - Change: @validator("field")
        - To: @field_validator("field") and add @classmethod decorator; update signature to accept cls and value.
        - Change: @root_validator
        - To: @model_validator(mode="after") and change to instance method (remove @classmethod).
      Ensure model_config uses model_config = ConfigDict(...).
    outputs:
      - name: validators-migrated
        type: boolean

  - name: migrate-constrained-types
    description: >
      Replace Pydantic v1 constrained types with v2 equivalents:
        - from pydantic import conint, EmailStr
        - conint(gt=-1, lt=2) -> Annotated[int, Field(ge=0, le=1)]
        - Add: from typing import Annotated; from pydantic import Field
      Update field types accordingly.
    outputs:
      - name: constrained-types-migrated
        type: boolean

  - name: migrate-emailstr
    description: >
      For each file importing EmailStr:
        - Change: from pydantic import EmailStr
        - To: from pydantic.networks import EmailStr
      Remove EmailStr.validate(email) calls; if programmatic validation is needed, use the email_validator library directly.
      EmailStr remains valid as a type annotation in Pydantic v2.
    outputs:
      - name: emailstr-migrated
        type: boolean

  - name: migrate-config-classes
    description: >
      For models with a Config class:
        - Change: class Config:
                   arbitrary_types_allowed = True
        - To: model_config = ConfigDict(arbitrary_types_allowed=True)
      Import ConfigDict from pydantic if necessary.
    outputs:
      - name: config-migrated
        type: boolean

  - name: run-suite-and-fix-errors
    description: >
      Run the repository's test suite. For each error:
        - Read the traceback and the code at that location.
        - Apply the smallest possible change to fix the error using the migration steps above.
        - Re-run the suite until all tests pass.
      Expect errors related to:
        - Missing pydantic-settings import
        - Missing field_validator/model_validator imports
        - Incorrect validator signatures
        - Incorrect EmailStr usage
        - Missing Annotated/Field imports
      Do not skip any failing test.
    outputs:
      - name: suite-passed
        type: boolean
      - name: remaining-errors
        type: list

  - name: clean-up-and-verify
    description: >
      After the suite passes:
        - Remove any remaining # type: ignore comments added for migration.
        - Update documentation and examples to reflect v2 usage.
        - Ensure no pydantic.v1 imports remain.
      Re-run the suite once more to confirm stability.
    outputs:
      - name: migration-complete
        type: boolean
```
