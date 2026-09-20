# pydantic-v2-migration

Migrate the repository from Pydantic v1 to Pydantic v2 without mutating unrelated behavior, deleting public symbols, weakening tests, or importing `pydantic.v1`.

## Procedure

1. Inspect the repository and working tree before editing. Record supported Python versions, current and target Pydantic versions, dependency and lockfile constraints, package layout, test commands, and all Pydantic usage. Inventory imports, models, inherited fields, validators, configuration, settings, dataclasses, generics, custom types, serializers, schemas, introspection, and public helpers.
2. Run the documented full test suite before making changes. Save the exact command and result. Separate collection/import failures from runtime failures and identify pre-existing failures. Do not begin broad edits until the baseline is recorded.
3. Build a file-by-file migration checklist. Include every public class, function, helper, validator, field, configuration option, serializer, settings class, custom hook, and introspection API. Treat test imports of private-looking helpers as part of the compatibility surface; do not remove or rename them without an explicit breaking-change requirement.
4. Upgrade Pydantic and required companions such as `pydantic-settings` in dependency metadata and lockfiles, using versions compatible with supported Python versions. Keep dependency files consistent. Never use `pydantic.v1`.
5. Update imports deliberately. Import v2 model APIs from `pydantic`, and settings APIs from `pydantic_settings`. After each import group, run module imports or test collection. Ensure every decorator and helper still referenced by the module is imported; do not remove an import merely because the symbol is deprecated until all uses are migrated.
6. Migrate validators while preserving behavior, ordering, signatures, exception types, and error conditions:
   - Replace `@validator` with `@field_validator` and `@root_validator` with `@model_validator`.
   - Use `mode='before'` for raw-input behavior and `mode='after'` for validated-value behavior.
   - Apply required `@classmethod` usage and correct `ValidationInfo` or instance-method signatures.
   - Replace `each_item=True` with item-type validation or an explicit collection validator.
   - Preserve defaults, normalization, cross-field checks, and failure behavior; never delete or neutralize validation.
7. Migrate model declarations and configuration:
   - Annotate every overridden inherited field, including constant-like fields such as `segment_name`, with its intended type.
   - Replace inner `Config` with `model_config = ConfigDict(...)` when appropriate.
   - Translate options deliberately, including `orm_mode` to `from_attributes`, `allow_population_by_field_name` to `populate_by_name`, and `validate_all` to `validate_default`.
   - Review extra handling, assignment validation, aliases, strictness, arbitrary types, protected namespaces, defaults, and schema behavior.
8. Migrate fields, serialization, and entry points:
   - Update changed `Field` arguments and use `json_schema_extra` for schema metadata.
   - Replace `.dict()` and `.json()` with behaviorally equivalent `model_dump()` and `model_dump_json()` calls.
   - Replace parsing methods with `model_validate()` or explicit JSON loading, and replace `.from_orm()` with `from_attributes=True` where required.
   - Replace `__fields__` with `model_fields` or documented v2 inspection APIs.
   - Use field/model serializers or computed fields only when they preserve existing output, aliases, omission rules, and error behavior.
9. Migrate settings, dataclasses, generics, and custom types only when present. Preserve environment names, nested settings, constructors, validation order, schemas, serialization, and public symbols. Replace custom hooks with v2 core-schema APIs only as required.
10. After each logical change, run focused tests plus import/collection checks. Fix the earliest meaningful traceback before proceeding. For missing-name or missing-symbol errors, restore or correctly migrate the symbol and its callers; do not delete tests or compatibility helpers. For model-construction errors, inspect inherited annotations, defaults, aliases, and configuration before changing behavior.
11. For runtime failures after collection succeeds, compare v1 baseline behavior with v2 output and errors. Investigate model construction, field defaults, aliases, nested parsing, serialization, and validators independently. Do not treat a large failure count as evidence that tests should be changed; preserve fixtures and assertions unless the intended API explicitly changed.
12. Search the complete repository after migration for `pydantic.v1`, `@validator`, `@root_validator`, `class Config`, `.dict(`, `.json(`, `.parse_obj(`, `.parse_raw(`, `.from_orm(`, obsolete options, stale imports, and removed public helpers. Review every match manually rather than applying blind replacements.
13. Run the full suite with warnings and deprecations visible. Add or update focused regression tests for inherited field overrides, validators, aliases, defaults, settings, serialization, schemas, error behavior, and public helpers where coverage is missing. Never delete, skip, or weaken tests to obtain a pass.
14. Before completion, verify dependency metadata and lockfiles, successful imports and collection, absence of runtime `pydantic.v1` imports, preserved public symbols, resolved migration warnings, intentional-only diff, and a passing full suite. Report the exact final test command and result; do not claim success without it.