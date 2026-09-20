# pydantic-v2-migration

Migrate the repository from Pydantic v1 to Pydantic v2 while preserving behavior. Do not use `pydantic.v1`, compatibility shims, disabled validation, or deleted functionality.

## Procedure

1. Inspect before editing:
   - Identify supported Python and Pydantic versions, dependency and lock files, package exports, entry points, models, settings, validators, serializers, and tests.
   - Search for `pydantic`, `BaseModel`, `BaseSettings`, `validator`, `root_validator`, `Config`, `parse_obj`, `parse_raw`, `from_orm`, `dict(`, `json(`, `schema(`, `construct(`, `__get_validators__`, and `__modify_schema__`.
   - Inspect project compatibility modules such as `support.py` for re-exported Pydantic symbols and update their exports as part of the migration.
   - Run the documented baseline test, lint, and type-check commands. Record failures and separate import/setup failures from behavioral failures.

2. Update dependencies and imports before diagnosing model failures:
   - Require a compatible Pydantic v2 release.
   - Add `pydantic-settings` whenever the project uses `BaseSettings`, install it in the development/test environment, and update dependency and lock files consistently.
   - Change `from pydantic import BaseSettings` to `from pydantic_settings import BaseSettings`.
   - Change imports of v2 symbols such as `field_validator`, `model_validator`, `ConfigDict`, and `ValidationInfo` to their correct modules, including project support modules when those modules intentionally re-export symbols.
   - Never use `pydantic.v1` or silently remove imports to make collection pass.
   - Preserve public import paths and exported names unless breaking changes are explicitly authorized.

3. Migrate configuration:
   - Replace inner `class Config` with `model_config = ConfigDict(...)`.
   - Translate `orm_mode` to `from_attributes`, `allow_population_by_field_name` to `populate_by_name`, and `validate_all` to `validate_default`.
   - Preserve settings sources, environment prefixes, aliases, nested settings, defaults, and validation behavior.

4. Migrate validators without removing behavior:
   - Replace `@validator` with `@field_validator`, choosing `before`, `after`, or `wrap` to preserve execution order and input semantics.
   - Replace `@root_validator` with `@model_validator`, preserving pre- versus post-validation behavior.
   - Update signatures and use `ValidationInfo` where field or configuration context is required.
   - Replace `each_item=True` with item-type validation and preserve `always=True` behavior using `validate_default` or an equivalent validator mode.
   - Update project-level validator re-exports and imports before running collection tests.

5. Migrate fields and class attributes:
   - Add explicit type annotations to every field, including fields overridden in subclasses. For example, replace `segment_name = "X"` with an appropriately typed declaration such as `segment_name: str = "X"`.
   - Mark intended non-fields with `ClassVar` or `PrivateAttr` rather than relying on unannotated class attributes.
   - Verify requiredness, optionality, aliases, constraints, and defaults after changing annotations.

6. Migrate parsing and serialization:
   - Replace `parse_obj`, `parse_raw`, and `from_orm` with `model_validate`, `model_validate_json`, and `from_attributes`-based validation as appropriate.
   - Replace `dict()` and `json()` with `model_dump()` and `model_dump_json()`, preserving include/exclude, aliases, unset/default handling, and `None` behavior.
   - Replace `schema()` and `schema_json()` with `model_json_schema()`.
   - Replace `construct()` with `model_construct()` only when bypassing validation is intentional.

7. Review v2 behavior changes:
   - Check unions, coercion, strictness, patterns, dataclasses, generic models, computed fields, private attributes, custom types, JSON encoders, and serialization hooks.
   - Replace `__get_validators__` and `__modify_schema__` with v2 core-schema or JSON-schema hooks where needed.
   - Preserve API responses, persisted formats, relied-upon exception behavior, and security-sensitive validation.

8. Iterate safely:
   - Run focused tests after each logical change, then the complete suite.
   - Fix the earliest actionable failure. Resolve dependency and import/collection errors before diagnosing behavioral failures.
   - Add or update regression tests for changed validation, settings, parsing, field overrides, and serialization behavior.
   - Search again for deprecated APIs, stale imports, unannotated subclass field overrides, and unintended `pydantic.v1` usage.

9. Finish verification:
   - Run the full test suite, linting, type checks, and project-specific checks.
   - Confirm dependency metadata, installed dependencies, and lock files are consistent.
   - Report remaining failures explicitly and do not claim completion unless checks pass or the user accepts documented exceptions.