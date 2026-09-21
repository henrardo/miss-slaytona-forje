# pydantic-v2-migration

## Purpose

Produce a repository-specific, read-only migration plan from Pydantic v1 to v2. Do not modify files, dependencies, lockfiles, caches, environments, generated artifacts, or any other state.

## Procedure

1. Inspect the repository without mutation.
   - Read project metadata, dependency and lock files, Python-version constraints, CI configuration, and documented commands.
   - Identify the configured Pydantic version and whether `pydantic-settings` is needed.
   - Search source, tests, configuration, and generated code for v1 imports and APIs, including `pydantic.v1`, `validator`, `root_validator`, `parse_obj`, `parse_raw`, `from_orm`, `dict()`, `json()`, `schema()`, `schema_json()`, `__fields__`, inner `Config`, `GenericModel`, `Field(regex=...)`, and custom validation, serialization, and schema hooks.
   - Record exact files, symbols, call sites, and relevant surrounding code. Never perform blind textual replacements.

2. Establish a migration inventory before proposing changes.
   - Group findings into dependencies, imports, configuration, validators, model APIs, declarations, integrations, and tests.
   - For each finding, record the current behavior, proposed v2 equivalent, affected callers, compatibility assumptions, and unresolved risks.
   - Preserve aliases, defaults, required-versus-optional semantics, validation order, coercion, error behavior, public serialization, and unrelated behavior.
   - Distinguish confirmed repository facts from assumptions and planned work. Never claim that edits, tests, or commands were completed when they were not.

3. Plan dependencies, imports, and configuration.
   - Select a Pydantic v2 release compatible with the repository and Python constraints. Plan `pydantic-settings` for settings models when required; never introduce `pydantic.v1` as a migration solution.
   - Replace inner `Config` with `model_config = ConfigDict(...)`, preserving supported options and documenting options with changed semantics.
   - Replace `GenericModel` with `BaseModel` plus `Generic[...]`.
   - For every `Annotated` use, verify an explicit import from `typing` or `typing_extensions`; list every missing, ambiguous, or unresolved import.
   - Treat dependency and lockfile changes as deferred, authorized actions only.

4. Plan every validator migration individually.
   - Replace `@validator` with `@field_validator`; use `mode="before"` when the v1 validator received raw input.
   - Replace `@root_validator(pre=True)` with `@model_validator(mode="before")` and post-validation root validators with `mode="after"`.
   - Verify decorator order, `@classmethod` requirements, field names, inheritance, signatures, return types, and execution order.
   - Ensure field validators return field values and after-model validators return the model instance.
   - Remove obsolete `field` and `config` parameters. Map required information to `ValidationInfo`, using `info.data`, `info.config`, or `info.context` only when available at that lifecycle stage.
   - Preserve accepted input shapes, ordering, defaults, coercion, cross-field invariants, exception types, and messages.
   - Re-scan for stale, undefined, or unimported `validator` and `root_validator` names.

5. Plan model API and serialization changes.
   - Replace `parse_obj` with `model_validate`, `parse_raw` with `model_validate_json`, and `from_orm` with `model_validate` plus `from_attributes=True` where appropriate.
   - Replace `dict()` and `json()` with `model_dump()` and `model_dump_json()`, preserving aliases, inclusion, exclusion, mode, and round-trip behavior.
   - Replace `schema()` and `schema_json()` with `model_json_schema()` and review every schema consumer.

6. Review declarations and integrations comprehensively.
   - Replace every `Field(regex=...)` with `Field(pattern=...)`; search the entire repository again, including tests and generated/configuration code, until no stale usage remains.
   - Review constrained types, unions, optional and required fields, defaults, discriminators, recursive models, dataclasses, enums, custom types, aliases, extra handling, assignment validation, equality, private attributes, and custom schema or serializer hooks.
   - Review FastAPI, ORM, CLI, settings, database, and serialization integrations for Pydantic v2 behavior.

7. Validate the plan without mutation.
   - Inventory every proposed introduced name and verify imports, decorators, signatures, return types, and referenced symbols before presenting it.
   - Check proposed snippets and files for syntax errors and non-printable characters. Reject U+0000–U+001F except permitted whitespace and U+007F–U+009F, especially characters that can produce invalid Python source.
   - Use only static inspection and parsing or compilation methods explicitly guaranteed not to create caches or artifacts. If safety cannot be established, describe the check as deferred instead of running it.
   - After each category, re-scan for stale APIs, stale `regex=`, missing `Annotated` imports, undefined names, accidentally removed names, malformed syntax, and duplicate or conflicting decorators.
   - Treat every validation error, `PydanticUserError`, `NameError`, syntax error, non-printable-character error, or changed test behavior as a blocking unresolved risk. Identify the affected model, input, field, likely semantic cause, and required follow-up; never mask or dismiss the error.
   - Pay special attention to errors involving required fields, validator signatures, `Field(pattern=...)`, model configuration, and serialization differences.
   - Specify targeted tests, formatting, linting, type checking, and the full suite for later authorized execution. Do not run mutating commands.

8. Produce the final report.
   - List exact proposed changes by file and symbol, compatibility assumptions, safe checks and their results, deferred commands, blocking risks, and confidence.
   - State explicitly that no files, dependencies, lockfiles, caches, or environment state changed.
   - Do not claim migration completion unless an authorized follow-up applies changes and all relevant checks pass.