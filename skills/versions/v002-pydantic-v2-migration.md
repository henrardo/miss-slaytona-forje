---
name: pydantic-v2-migration

description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2. Captures distilled knowledge from multiple migration attempts to ensure a complete and correct migration.

metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 2
    derived_from_traces:
      - 658c1c3c
      - 27b6c4e5
      - 39742bae
      - 56e98440
      - 7ba0c4f5
---

```yaml
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so the repository's
  own test suite passes, without shimming pydantic.v1 and without deleting
  behaviour to make tests green. This procedure captures lessons learned from
  multiple attempts to avoid common pitfalls.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with pydantic import or validator errors after a Pydantic v2 upgrade
  - BaseSettings has been moved to the pydantic-settings package error appears
  - AttributeError type object EmailStr has no attribute validate error appears

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working. This passes some tests and is not a migration
  - Replacing a validator body with a bare return so the function still imports. The suite goes green and the behaviour is gone
  - Declaring the migration complete without running the suite
  - Skipping dependency updates in pyproject.toml or pip requirements
  - Migrating files in an arbitrary order without checking for dependencies between them
  - Not handling EmailStr.validate email calls which were removed in v2
  - Forgetting to update pyproject.toml dependencies before importing v2 APIs

steps:
  - name: update-dependencies-first
    description: >
      Update dependency specifications to require Pydantic v2 and pydantic-settings.
      For pyproject.toml:
        pydantic = "^2.0"
        pydantic-settings = ">=2.0,<3.0"
        email-validator = ">=2.0,<3.0"
      For requirements.txt:
        pydantic>=2.0,<3.0
        pydantic-settings>=2.0,<3.0
        email-validator>=2.0,<3.0
      Rebuild the environment pip install -e . or equivalent and verify
      pydantic version is 2.x
    outputs:
      - name: pydantic-version
        type: string
      - name: pydantic-settings-installed
        type: boolean

  - name: find-all-pydantic-v1-usage
    description: >
      Search the codebase for Pydantic v1 usage patterns:
        - from pydantic import BaseSettings
        - from pydantic import validator root_validator
        - from pydantic import conint EmailStr
        - class Config arbitrary_types_allowed = True
        - EmailStr.validate email
      Record all files and usages for migration. Use grep to find:
        grep -r "from pydantic import BaseSettings" .
        grep -r "@validator" .
        grep -r "@root_validator" .
        grep -r "conint(" .
        grep -r "EmailStr.validate" .
        grep -r "class Config:" .
    outputs:
      - name: files-with-pydantic-v1
        type: list
      - name: usages
        type: map

  - name: migrate-dependencies-file-first
    description: >
      Update pyproject.toml or requirements files before making any code changes.
      This ensures the environment has the correct packages installed before
      importing v2 APIs. Commit this change separately
    outputs:
      - name: deps-updated
        type: boolean

  - name: migrate-basesettings-to-pydantic-settings
    description: >
      For each file importing BaseSettings:
        - Change: from pydantic import BaseSettings as Settings
        - To: from pydantic_settings import BaseSettings as Settings
      Update any class definitions: class MyConfig Settings -> class MyConfig BaseSettings
      If using SettingsConfigDict import it from pydantic_settings
      Verify no imports remain from pydantic import BaseSettings
    outputs:
      - name: basesettings-migrated
        type: boolean

  - name: migrate-emailstr-imports
    description: >
      For each file importing EmailStr:
        - Change: from pydantic import EmailStr
        - To: from pydantic.networks import EmailStr
      EmailStr remains valid as a type annotation in Pydantic v2 but the
      validate method was removed. Remove any EmailStr.validate email calls
      or replace with email_validator library for programmatic validation
    outputs:
      - name: emailstr-imports-migrated
        type: boolean

  - name: migrate-constrained-types
    description: >
      Replace Pydantic v1 constrained types with v2 equivalents:
        - from pydantic import conint EmailStr
        - conint gt=-1 lt=2 -> Annotated int Field ge=0 le=1
        - Add: from typing import Annotated from pydantic import Field
      Update field types accordingly. Remove any type ignore comments
      added for migration
    outputs:
      - name: constrained-types-migrated
        type: boolean

  - name: migrate-validators-to-v2-api
    description: >
      For each file using validator or root_validator:
        - Change: from pydantic import validator root_validator
        - To: from pydantic import field_validator model_validator
        - Change: validator field
        - To: field_validator field and add classmethod decorator update
          signature to accept cls and value parameters
        - Change: root_validator
        - To: model_validator mode=after and change to instance method
          remove classmethod
      Ensure model_config uses model_config = ConfigDict for models with
      Config classes
    outputs:
      - name: validators-migrated
        type: boolean

  - name: migrate-config-classes
    description: >
      For models with a Config class:
        - Change: class Config arbitrary_types_allowed = True
        - To: model_config = ConfigDict arbitrary_types_allowed=True
      Import ConfigDict from pydantic if necessary. Remove old Config classes
      after migration is complete
    outputs:
      - name: config-migrated
        type: boolean

  - name: run-suite-and-fix-errors-systematically
    description: >
      Run the repository's test suite. For each error:
        - Read the traceback and the code at that location
        - Apply the smallest possible change to fix the error using the migration
          steps above
        - Re-run the suite until all tests pass
      Expect errors related to:
        - Missing pydantic-settings import
        - Missing field_validator model_validator imports
        - Incorrect validator signatures
        - Incorrect EmailStr usage
        - Missing Annotated Field imports
        - EmailStr.validate method calls
      Do not skip any failing test. If a test passes unexpectedly verify
      the behavior is correct
    outputs:
      - name: suite-passed
        type: boolean
      - name: remaining-errors
        type: list

  - name: clean-up-and-verify-complete
    description: >
      After the suite passes:
        - Remove any remaining type ignore comments added for migration
        - Update documentation and examples to reflect v2 usage
        - Ensure no pydantic.v1 imports remain
        - Verify no EmailStr.validate calls remain
        - Check that all BaseSettings imports are from pydantic_settings
      Re-run the suite once more to confirm stability. If any test fails
      on re-run investigate immediately
    outputs:
      - name: migration-complete
        type: boolean
```
