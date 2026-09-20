---
name: pydantic-v2-migration
description: Migrate Python projects from Pydantic v1 to Pydantic v2 while preserving validation behavior, serialization contracts, settings, and framework integrations.
metadata:
  aip:
    version: 46
    spec: https://aip.dev/specification
    schemaId: https://aip.dev/schemas/skill.schema.json
---

```yaml
goal: 'Migrate a Python codebase from Pydantic v1 to Pydantic v2 with minimal behavioral regressions.'
inputs:
  - 'The repository root or the paths containing Python source code.'
  - 'The supported Python versions and dependency constraints.'
  - 'The test, lint, type-check, and packaging commands used by the project.'
  - 'Any compatibility requirement for supporting Pydantic v1 and v2 simultaneously.'
outputs:
  - 'Updated source code using supported Pydantic v2 APIs.'
  - 'Updated dependency declarations and integration packages.'
  - 'Tests covering changed validation, serialization, schema, and settings behavior.'
  - 'A concise migration summary listing intentional behavior changes and remaining risks.'
procedure:
  preparation:
    - 'Inspect dependency files, lock files, continuous integration configuration, and framework versions before editing source code.'
    - 'Determine whether the project can migrate directly to Pydantic v2 or must temporarily use the pydantic.v1 compatibility namespace.'
    - 'Run the existing test suite and record baseline failures before making migration changes.'
    - 'Search the repository for imports from pydantic, pydantic.v1, pydantic_settings, and framework-specific Pydantic integrations.'
    - 'Search for BaseModel, BaseSettings, Config, validator, root_validator, parse_obj, parse_raw, from_orm, dict, json, schema, schema_json, copy, construct, GenericModel, custom root types, and constrained type factories.'
  dependencies:
    - 'Upgrade Pydantic to a compatible v2 release and update the lock file with the project package manager.'
    - 'Add pydantic-settings when the project uses BaseSettings or settings source customization.'
    - 'Verify that FastAPI, SQLModel, spaCy, and other Pydantic-dependent libraries support the selected Pydantic version.'
    - 'Avoid unrelated dependency upgrades unless they are required for Pydantic v2 compatibility.'
  automated_migration:
    - 'Run the official bump-pydantic tool when practical, then review every generated change rather than treating it as complete.'
    - 'Format generated edits using the project formatter before evaluating the diff.'
    - 'Use automated edits for mechanical renames but handle validators, configuration, custom types, and serialization semantics manually.'
  imports_and_model_methods:
    - 'Replace deprecated model methods with their Pydantic v2 equivalents.'
    - 'Replace parse_obj with model_validate.'
    - 'Replace parse_raw with model_validate_json when the input is JSON.'
    - 'Replace from_orm with model_validate and enable from_attributes in model configuration.'
    - 'Replace dict with model_dump and review include, exclude, alias, unset, default, and none options.'
    - 'Replace json with model_dump_json and verify output formatting and custom serialization.'
    - 'Replace schema with model_json_schema.'
    - 'Replace schema_json with JSON serialization of model_json_schema when a JSON string is required.'
    - 'Replace copy with model_copy and verify deep-copy requirements.'
    - 'Replace construct with model_construct only where bypassing validation is intentional and safe.'
    - 'Replace __fields__ access with model_fields and adjust code that depends on field metadata.'
  configuration:
    - 'Replace inner Config classes with ConfigDict assigned to model_config unless compatibility constraints require another approach.'
    - 'Translate orm_mode to from_attributes.'
    - 'Translate allow_population_by_field_name to populate_by_name or the appropriate validation settings for the selected Pydantic release.'
    - 'Translate anystr_strip_whitespace to str_strip_whitespace.'
    - 'Translate validate_all to validate_default and verify default-value behavior.'
    - 'Replace schema_extra with json_schema_extra.'
    - 'Replace keep_untouched with ignored_types.'
    - 'Review extra-field handling, frozen models, assignment validation, arbitrary types, alias behavior, and enum value handling.'
    - 'Remove unsupported configuration options only after identifying whether application code relied on them.'
  validators:
    - 'Replace validator with field_validator.'
    - 'Replace root_validator with model_validator.'
    - 'Choose before, after, wrap, or plain validation mode according to when the old validator expected to run.'
    - 'Use class methods where required by the selected validator mode and project style.'
    - 'Replace access to the old field and config keyword arguments with ValidationInfo and model field metadata.'
    - 'Preserve validator ordering and inheritance behavior with focused tests.'
    - 'Replace each_item validation with annotations or explicit collection handling when needed.'
    - 'Do not rely on TypeError being converted into ValidationError inside validators.'
    - 'Review always validation because standard type validation can also run on defaults in Pydantic v2.'
    - 'Use model_validator carefully during assignment validation because it may receive a model instance rather than an input mapping.'
  types_and_fields:
    - 'Replace conlist, constr, conint, condecimal, and similar constrained factories with Annotated metadata when this improves compatibility and static analysis.'
    - 'Review Field arguments and replace regex with pattern.'
    - 'Move arbitrary JSON Schema keywords from Field into json_schema_extra.'
    - 'Replace min_items and max_items with min_length and max_length where applicable.'
    - 'Review aliases because an unset alias no longer behaves exactly like the field name in all introspection code.'
    - 'Review Optional annotations because Optional does not by itself imply a default value of None.'
    - 'Review Any annotations because Any fields no longer receive an implicit None default.'
    - 'Review unions because Pydantic v2 preserves matching input types more aggressively and may short-circuit validation.'
    - 'Review integer-to-string coercion and iterable-to-dictionary coercion because permissive v1 conversions may no longer occur.'
    - 'Use Strict types or strict configuration only when strict behavior is part of the intended contract.'
  root_and_generic_models:
    - 'Replace models using __root__ with RootModel.'
    - 'Update construction, validation, dumping, and schema tests for every converted RootModel.'
    - 'Replace GenericModel inheritance with BaseModel plus Generic where supported.'
    - 'Avoid runtime checks against parameterized generic models unless a concrete subclass is introduced for that purpose.'
  custom_types:
    - 'Replace __get_validators__ with __get_pydantic_core_schema__ when maintaining a custom type.'
    - 'Replace __modify_schema__ with __get_pydantic_json_schema__.'
    - 'Prefer Annotated with BeforeValidator, AfterValidator, PlainValidator, WrapValidator, PlainSerializer, or WrapSerializer for reusable local behavior.'
    - 'Use TypeAdapter for validation and schema generation involving dataclasses, typed dictionaries, unions, primitives, and other non-BaseModel types.'
    - 'Keep custom core-schema implementations small and test both successful and failing inputs.'
  serialization:
    - 'Replace json_encoders with field_serializer, model_serializer, or an Annotated serializer where appropriate.'
    - 'Verify whether serializers should run in Python mode, JSON mode, or both.'
    - 'Test computed fields introduced with computed_field when they affect public output.'
    - 'Review subclass serialization because nested model fields may emit only fields declared by the annotated parent type.'
    - 'Verify aliases, exclusion flags, default omission, null omission, and round-trip requirements for every public payload.'
    - 'Compare API responses, persisted documents, messages, and cache entries against representative v1 fixtures.'
  dataclasses:
    - 'Review Pydantic dataclasses because validation and initialization order changed.'
    - 'Move logic that must run after validation into __post_init__.'
    - 'Remove reliance on __post_init_post_parse__.'
    - 'Use TypeAdapter for validation, serialization, or JSON Schema generation around dataclasses.'
    - 'Pass dataclass configuration explicitly instead of assuming that parent model configuration is inherited.'
    - 'Review extra-field behavior because Pydantic dataclasses no longer preserve unexpected fields in the same way.'
  settings:
    - 'Import BaseSettings from pydantic_settings.'
    - 'Import settings-specific source classes and settings configuration from pydantic_settings.'
    - 'Replace settings Config classes with SettingsConfigDict where appropriate.'
    - 'Review environment variable names, aliases, prefixes, case sensitivity, nested delimiters, secrets directories, and dotenv behavior.'
    - 'Rewrite custom settings sources to match the pydantic-settings interfaces used by the installed version.'
    - 'Add tests that isolate and restore environment variables.'
  errors_and_equality:
    - 'Update tests that assert exact validation error text because error types, locations, URLs, and wording changed.'
    - 'Prefer assertions on stable error attributes such as location and error type when exact prose is not part of the contract.'
    - 'Review model equality because models are no longer equal to dictionaries containing the same data.'
    - 'Review equality involving private attributes and generic model origins.'
    - 'Catch ValidationError only around operations that still wrap failures as ValidationError.'
  compatibility_strategy:
    - 'Use imports from pydantic.v1 only as a deliberate transition strategy and document why compatibility mode remains necessary.'
    - 'Do not mix v1 model classes and v2 model classes inside generic parameters or nested model graphs unless the combination is explicitly supported.'
    - 'Centralize compatibility imports when dual-version support is required.'
    - 'Test the complete supported dependency matrix when claiming simultaneous v1 and v2 support.'
    - 'Remove compatibility shims after downstream integrations and supported environments have migrated.'
  verification:
    - 'Run focused tests after each migration category to keep failures attributable.'
    - 'Run the complete test suite after source migration is complete.'
    - 'Run the project formatter, linter, static type checker, and documentation checks.'
    - 'Run packaging or build commands to detect missing runtime dependencies and import errors.'
    - 'Test model validation from Python objects, dictionaries, JSON text, and attribute-based objects where applicable.'
    - 'Test model dumping to Python values and JSON for public models.'
    - 'Test generated JSON Schema for models consumed by APIs, forms, clients, or documentation tools.'
    - 'Test settings loading with representative environment and secrets configurations.'
    - 'Test framework startup and at least one request path for each integration that constructs or serializes Pydantic models.'
    - 'Inspect warnings and eliminate Pydantic deprecation warnings unless a documented compatibility shim requires them.'
  completion:
    - 'Confirm that production source no longer uses unintended Pydantic v1 APIs.'
    - 'Confirm that dependency metadata expresses the actual supported Pydantic range.'
    - 'Confirm that public validation and serialization changes are tested or documented.'
    - 'Confirm that migration-only compatibility code has an owner and removal condition.'
    - 'Summarize changed behavior, verification commands, unresolved risks, and any required downstream updates.'
failure_handling:
  - 'If dependency resolution fails, identify the package constraining Pydantic before changing application code.'
  - 'If framework integration fails, verify framework compatibility and plugin versions before adding application-level workarounds.'
  - 'If validation behavior changes, create a minimal regression test that captures the intended contract before adjusting validators or annotations.'
  - 'If serialized output changes, determine whether the old representation is a public contract before restoring it with serializers.'
  - 'If tests depend on exact error messages, update them to stable structured assertions unless exact text is explicitly required.'
  - 'If a custom core schema is difficult to maintain, prefer Annotated validators or serializers and TypeAdapter composition.'
safety:
  - 'Do not weaken validation globally merely to make legacy tests pass.'
  - 'Do not bypass validation with model_construct for untrusted or externally supplied data.'
  - 'Do not silently change public API payloads, persisted formats, environment variable names, or generated schemas.'
  - 'Do not remove failing tests without replacing them with tests for the intended Pydantic v2 behavior.'
  - 'Do not claim completion while deprecation warnings, unresolved compatibility imports, or untested integration paths remain.'
```