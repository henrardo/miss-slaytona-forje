# pydantic-v2-migration

## Objective

Migrate the repository from Pydantic v1 to Pydantic v2 without weakening validation or changing supported behavior. Do not mutate repository state until the baseline, inventory, and migration plan are recorded. Never use `pydantic.v1`, delete fields or validators, stub validator bodies, add unconditional returns, or claim completion from imports or test collection alone.

## Procedure

1. Establish a read-only baseline.
   - Inspect dependency files, lockfiles, Python support, generated-code workflows, and standard test, lint, and type-check commands.
   - Record installed versions of `pydantic` and `pydantic-settings`.
   - Run standard checks without editing files. Record the first traceback, failure count, warnings, and representative behavior for validation, settings, defaults, coercion, serialization, ORM loading, and error locations.

2. Create a complete migration inventory before editing.
   - Search source, tests, scripts, generated files, and configuration for all v1 surfaces, including `pydantic.v1`, `BaseSettings`, `class Config`, `validator`, `root_validator`, `allow_reuse`, `each_item`, `pre`, `always`, `parse_obj`, `parse_raw`, `from_orm`, `construct`, `copy`, `dict`, `json`, `Field(regex=...)`, collection constraints, constrained types, `GenericModel`, `__root__`, `orm_mode`, aliases, encoders, schema hooks, custom types, and validator aliases.
   - For each occurrence, record the class hierarchy, complete annotation, decorator arguments, original timing, signature, full body, field dependencies, call sites, defaults, coercion, exceptions, and expected error locations.
   - Identify generated sources and regeneration commands. Update sources or generators rather than patching generated output alone.
   - Keep a machine-readable inventory and remove entries only after replacement behavior is tested.

3. Upgrade dependencies through the project workflow.
   - Change Pydantic to a compatible v2 range and add `pydantic-settings` when settings are used.
   - Regenerate the lockfile and verify installed versions.
   - Remove v1 pins and compatibility imports.

4. Migrate configuration and settings.
   - Import `BaseSettings` and `SettingsConfigDict` from `pydantic_settings`.
   - Replace settings `Config` classes with `model_config = SettingsConfigDict(...)`, preserving prefixes, case sensitivity, env files, aliases, extra handling, and validation behavior.
   - Replace model `Config` classes with `ConfigDict` or an equivalent `model_config`, verifying every option against v2 semantics.
   - Test environment loading, aliases, defaults, extra fields, and invalid settings.

5. Migrate fields and model structure.
   - Replace removed field arguments, such as `regex` with `pattern`, while preserving requiredness and constraints.
   - Annotate every override of an inherited Pydantic field, for example `segment_name: str = ...`; never use an unannotated class attribute to override a field.
   - Review constrained types, `Annotated` constraints, root models, generics, dataclasses, private attributes, custom schemas, and generated models individually.

6. Migrate validators mechanically and preserve their complete logic.
   - Convert `@validator` to `@field_validator`, selecting `mode="before"`, `"after"`, or `"wrap"` from the original timing.
   - Convert `@root_validator(pre=True)` to `@model_validator(mode="before")`; convert post-root validators to an appropriate `after` or `wrap` validator.
   - Remove `allow_reuse`; never pass it to `field_validator` or `model_validator`.
   - Convert signatures explicitly. Use `ValidationInfo` through documented attributes such as `info.data` and `info.config`; never call `info.get(...)` or treat `ValidationInfo` as a mapping.
   - Preserve `always`, `each_item`, ordering, default handling, coercion, exception behavior, error types, locations, and cross-field invariants.
   - Preserve every substantive original validator body. Do not replace it with `return value`, `return self`, an unconditional success, unreachable original code, or an import-only stub.
   - For reused validators, use ordinary helper functions or correctly assigned validator methods. Do not disguise a v1 validator with a simple alias unless its signature and semantics are verified.
   - For post-model validators, use the v2 instance contract: validate and return the model instance, preserving the original checks. Do not pass `self.__dict__` to a v1-style function unless that function was explicitly rewritten and tested for the new contract.

7. Migrate APIs and integrations.
   - Replace `parse_obj` and `parse_raw` with `model_validate` and `model_validate_json`.
   - Replace `dict` and `json` with `model_dump` and `model_dump_json`, preserving include, exclude, alias, unset, default, none, and serializer options.
   - Replace `from_orm` with `model_validate` and set `from_attributes=True` where required.
   - Replace `construct` with `model_construct` only when bypassing validation is intentional; replace `copy` with `model_copy` and schema APIs with `model_json_schema`.
   - Review ORM adapters, custom serialization, computed fields, custom types, generics, dataclasses, and generated models for semantic changes.

8. Apply changes incrementally.
   - Edit one coherent module or category at a time, and inspect the exact original declaration, full validator body, hierarchy, annotations, and call sites before each edit.
   - After each batch, run import and collection checks, focused tests, and then broader tests. Stop at the first traceback and fix its actual cause.
   - Regenerate generated code through the documented workflow and test representative generated classes.
   - After every validator batch, search for `allow_reuse`, `ValidationInfo` mapping access, unconditional validator returns, unreachable original bodies, deleted validator bodies, v1 decorators, and unannotated inherited-field overrides.

9. Validate completion.
   - Run the complete standard test suite, linting, type checking, integration checks, generation checks, and fixture checks.
   - Re-run inventory searches for all v1 surfaces, unsupported decorator arguments, removed APIs, and suspicious validator stubs.
   - Compare results with the baseline for validation, configuration, serialization, ORM loading, errors, defaults, coercion, and generated output.
   - Report every command, result, unresolved limitation, and skipped check. Claim completion only when all required checks pass and no substantive validator logic was removed.