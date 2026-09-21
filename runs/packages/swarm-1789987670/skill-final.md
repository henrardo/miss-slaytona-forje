# pydantic-v2-migration

Migrate a Python repository from Pydantic v1 to Pydantic v2. Do not mutate files, dependencies, environments, or other repository state during inspection. Do not use `pydantic.v1`, compatibility shims, weakened validation, test-only bypasses, or unrelated edits. Preserve behavior and do not claim completion until all available checks pass.

## Procedure

1. Inspect without editing.
   - Read repository instructions and identify supported Python versions, dependency tooling, tests, linting, and type-check commands.
   - Check the installed Pydantic version and run documented baseline checks.
   - Search source, tests, configuration, and dependency files for Pydantic imports and v1 APIs: `validator`, `root_validator`, inner `Config`, `parse_obj`, `parse_raw`, `dict`, `json`, `schema`, `from_orm`, `construct`, and `pydantic.v1`.
   - Inventory validators, settings models, serializers, dataclasses, generics, integrations, and model API calls.

2. Plan a narrow migration.
   - Group changes into dependencies/imports, configuration, validators, model APIs, settings, and integrations.
   - Record behavior to preserve: aliases, defaults, validation timing, errors, serialization, environment loading, ORM parsing, and extra-field handling.
   - Make only migration-related edits.

3. Update dependencies and imports.
   - Require Pydantic v2 and add `pydantic-settings` when settings models are used.
   - Replace v1 imports; never add `pydantic.v1`.
   - Explicitly import `ValidationInfo` from `pydantic` in every module that references it. Search the edited file for all `ValidationInfo` occurrences and verify each is defined before use.
   - After every edit involving imports, decorators, signatures, indentation, or multiline expressions, run `python -m compileall` on the affected files before running tests. If compilation fails, revert or repair only the immediately preceding edit; inspect delimiters, colons, indentation, decorator placement, truncation, and accidental replacements.

4. Migrate configuration.
   - Replace inner `Config` classes with `model_config = ConfigDict(...)`.
   - Translate renamed options and explicitly verify changed defaults.
   - Preserve aliases, extra handling, assignment validation, arbitrary types, immutability, serialization, and attribute-based parsing.

5. Migrate validators conservatively.
   - Replace `@validator` with `@field_validator`, choosing `mode='before'` or `mode='after'` to preserve timing.
   - Replace `@root_validator` with `@model_validator`, deliberately choosing its mode. A `before` validator receives raw input; an `after` validator receives a model instance.
   - Use valid v2 signatures and explicitly import every referenced `ValidationInfo`.
   - Treat `ValidationInfo` as an object, not a mapping. Use `info.data`, `info.config`, `info.context`, and `info.field_name`; never use `info.get(...)`, subscripting, `.keys()`, or `.items()` on it.
   - Search validator code for `.get(`, subscripting, `.keys()`, and `.items()`. Change a match only when it operates on `info`; preserve legitimate operations on user data.
   - Preserve ordering, normalization, exceptions, error behavior, and return values. Do not swallow exceptions or add unconditional returns.

6. Migrate model APIs.
   - Replace `parse_obj` with `model_validate`, `parse_raw` with `model_validate_json`, `dict()` with `model_dump()`, `json()` with `model_dump_json()`, `schema()` with `model_json_schema()`, and `construct()` with `model_construct()`.
   - Replace `from_orm` with `ConfigDict(from_attributes=True)` and `model_validate(...)` where appropriate.
   - Review equality, aliases, serialization, computed fields, private attributes, generics, dataclasses, custom serializers, and schema generation for v2 behavior.

7. Migrate settings and integrations.
   - Import `BaseSettings` and `SettingsConfigDict` from `pydantic_settings`.
   - Preserve environment prefixes, nested delimiters, dotenv files, secrets directories, and validation behavior.
   - Verify that FastAPI, SQLModel, database libraries, and other integrations support Pydantic v2.

8. Verify incrementally.
   - Compile affected files before each focused test run.
   - Run focused tests after each coherent change and fix the earliest meaningful traceback first.
   - For syntax or import failures, inspect and repair the smallest preceding edit before investigating later failures.
   - For validator failures, first check decorator mode, signature, explicit `ValidationInfo` imports, and dictionary-style `info` access.
   - Add regression tests only for confirmed v2 behavior. Never modify tests to conceal failures.

9. Perform final verification.
   - Run repository-wide compilation, configured linting, type checking, and the complete test suite.
   - Search for `pydantic.v1`, obsolete APIs and decorators, compatibility code, debug code, swallowed exceptions, undefined `ValidationInfo`, and dictionary-style `ValidationInfo` usage.
   - Review the complete diff for syntax errors, incomplete migrations, behavior changes, unrelated edits, and test bypasses.
   - Report every command and result. If any check cannot run, state the exact blocker and do not claim completion.