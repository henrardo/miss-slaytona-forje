# pydantic-v2-migration

Migrate a Python repository from Pydantic v1 to v2 while preserving behavior, tests, public APIs, schemas, and error contracts. Do not use `pydantic.v1`, weaken tests, delete behavior, or claim success without verification. Do not mutate files or repository state until the user explicitly authorizes edits; begin with read-only inspection and verification.

## Procedure

1. Establish a read-only baseline.
   - Inspect `pyproject.toml`, lockfiles, supported Python versions, framework versions, and the installed Pydantic version.
   - Run documented tests, lint, type-check, and warning-check commands without changing files.
   - Record failures and group them by imports, fields, validators, configuration, parsing, serialization, settings, integrations, and compatibility assumptions.

2. Inventory v1 usage without changing files.
   - Search for `pydantic.v1`, `BaseSettings`, `GenericModel`, `@validator`, `@root_validator`, `@validate_arguments`, inner `Config` classes, `Field(`, `.dict(`, `.json(`, `.parse_obj(`, `.parse_raw(`, `.copy(`, `.schema(`, `.schema_json(`, `__root__`, `allow_reuse`, `outer_type_`, direct access to `__fields__`, and validator code calling `ValidationInfo` methods such as `.get()`.
   - Identify models, inherited fields, custom types, settings, dataclasses, serializers, framework integrations, generated schemas, and tests that depend on v1 behavior.

3. Plan each conversion before editing.
   - Preserve field types, defaults, aliases, requiredness, validation order, coercion, serialization output, schema shape, error locations, and public calling conventions.
   - For every inherited field override, retain a type annotation, such as `segment_name: str = ...`.
   - Replace v1 introspection deliberately with supported v2 APIs such as `model_fields` and `FieldInfo`; never access removed attributes such as `outer_type_`.
   - Make small, independently testable edits and preserve a rollback point for each coherent change.

4. Update imports and model declarations.
   - Import v2 APIs from `pydantic` and settings APIs from `pydantic_settings`; never use `pydantic.v1` as a shortcut.
   - Replace `GenericModel` with `BaseModel, Generic[...]`.
   - Replace `__root__` models with `RootModel[T]` and update callers to use `.root`.
   - Annotate every field declaration and every overridden inherited field.

5. Migrate validators without changing semantics.
   - Replace `@validator` with `@field_validator`, selecting `mode='before'`, `mode='after'`, or `mode='wrap'` to preserve timing.
   - Replace pre root validators with `@model_validator(mode='before')` and post root validators with `@model_validator(mode='after')` or `mode='wrap'` as needed.
   - Remove v1-only arguments, especially `allow_reuse`; never pass `allow_reuse` to `field_validator`.
   - Use `@classmethod` where required by the v2 API.
   - Treat `ValidationInfo` as an object, not a dictionary: use supported attributes such as `info.data`, `info.context`, `info.config`, `info.field_name`, and `info.mode`; replace patterns such as `info.get(...)` with explicit attribute access and appropriate `None` handling.
   - Ensure after-model validators return the model instance and preserve mutation, cross-field dependencies, exceptions, and error locations.
   - Reuse logic through helper functions or separately decorated methods; do not replace validators with no-op or bare-return stubs.

6. Migrate configuration and fields.
   - Replace inner `Config` with `model_config = ConfigDict(...)`.
   - Translate `orm_mode` to `from_attributes`, `allow_population_by_field_name` to `populate_by_name`, and other settings to their v2 names.
   - Replace removed `Field` arguments with v2 equivalents and use `json_schema_extra` for schema metadata.
   - Make aliases, strictness, coercion, extra-field handling, and assignment validation explicit.
   - Do not assume `FieldInfo` has v1 attributes such as `outer_type_`; derive required metadata from supported v2 APIs.

7. Migrate parsing, serialization, and schemas.
   - Replace `parse_obj` with `model_validate`, `parse_raw` with `model_validate_json`, `dict` with `model_dump`, `json` with `model_dump_json`, `copy` with `model_copy`, and `schema`/`schema_json` with `model_json_schema` plus appropriate JSON serialization.
   - Configure `from_attributes=True` for attribute-backed inputs.
   - Replace v1 serializer patterns with `field_serializer`, `model_serializer`, or `computed_field` while preserving output contracts.

8. Migrate settings and integrations.
   - Move `BaseSettings` to `pydantic_settings` and preserve prefixes, aliases, nested settings, environment parsing, and secrets behavior.
   - Update Pydantic dataclasses, custom `__get_validators__` types, FastAPI or other framework integrations, and generated schemas to their v2 APIs.

9. Validate each coherent edit.
   - Run focused tests after each category, then the full suite.
   - Treat `allow_reuse` errors, unannotated inherited-field overrides, `FieldInfo.outer_type_` failures, and invalid `ValidationInfo` dictionary access as migration defects; fix the implementation rather than suppressing errors.
   - Compare behavior with the baseline and add regression tests for validators, inheritance, aliases, serialization, schemas, settings, error locations, and edge cases.
   - Run linting, type checking, and warning checks; fix remaining v1 deprecations.

10. Finish only after clean verification.
   - Search again for `pydantic.v1`, obsolete APIs, `allow_reuse`, unannotated field overrides, `outer_type_`, invalid `ValidationInfo` usage, and other v1 constructs.
   - Run the complete documented suite in a clean environment with Pydantic v2 installed.
   - Report success only when tests, linting, type checks, warnings, and behavior comparisons pass; importability alone is insufficient.
   - If edits were not explicitly authorized, provide findings and an actionable patch plan without changing repository state.