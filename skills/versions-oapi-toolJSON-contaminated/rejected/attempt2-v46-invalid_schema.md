---
name: pydantic-v2-migration
description: Migrate Python projects from Pydantic v1 to Pydantic v2 while preserving validation behavior, serialization contracts, settings, schemas, and framework integrations.
metadata:
  aip:
    version: 46
    spec: https://aip.dev/46
    schemaId: https://aip.dev/schemas/skill.schema.json
---

```yaml
title: Pydantic v2 migration
objective: Migrate a Python codebase from Pydantic v1 to Pydantic v2 with explicit compatibility checks and minimal behavioral regressions.
use_when:
  - 'A project must upgrade from Pydantic v1 to Pydantic v2.'
  - 'Dependency resolution reports conflicts involving Pydantic versions.'
  - 'Code uses deprecated Pydantic v1 validators, configuration, parsing, serialization, schemas, settings, or ORM features.'
  - 'A framework integration must be verified against Pydantic v2.'
do_not_use_when:
  - 'The project must remain on Pydantic v1 because a required dependency has no compatible release.'
  - 'The task only changes model fields and does not involve a Pydantic version migration.'
inputs:
  - 'The project source tree and dependency manifests.'
  - 'The supported Python versions and deployment environments.'
  - 'The current Pydantic version and intended Pydantic v2 target range.'
  - 'The test suite, type-checking configuration, and linting configuration.'
  - 'Representative validation inputs, serialized outputs, generated schemas, and API payloads.'
outputs:
  - 'Updated dependency constraints compatible with Pydantic v2.'
  - 'Migrated model, validator, settings, serialization, and schema code.'
  - 'Updated framework and plugin integrations.'
  - 'Tests covering behavior that could change during migration.'
  - 'A concise record of intentional compatibility changes and unresolved blockers.'
principles:
  - 'Preserve externally observable behavior unless a change is intentional and documented.'
  - 'Use native Pydantic v2 APIs for the final implementation rather than leaving broad compatibility shims indefinitely.'
  - 'Treat validation, serialization, and JSON schema generation as separate contracts.'
  - 'Prefer focused mechanical changes followed by behavior-specific review.'
  - 'Do not assume that code which imports successfully is behaviorally compatible.'
procedure:
  - 'Create a clean branch and record the baseline test, type-checking, linting, and schema-generation results before editing dependencies.'
  - 'Inventory all direct and transitive Pydantic consumers, including web frameworks, settings packages, data libraries, plugins, code generators, and internal shared packages.'
  - 'Inspect dependency constraints and confirm that every required package has a release compatible with the selected Pydantic v2 range.'
  - 'Identify whether the project imports pydantic.v1 or relies on a framework compatibility layer, and decide whether those imports are temporary migration aids or required long-term boundaries.'
  - 'Search for BaseModel, BaseSettings, GenericModel, dataclasses, root models, custom types, validators, configuration classes, parsing methods, serialization methods, schema methods, ORM mode, aliases, constrained types, and private attributes.'
  - 'Capture representative model behavior before migration, including accepted inputs, rejected inputs, error locations, error types, defaults, coercions, equality checks, serialized dictionaries, serialized JSON, and generated JSON schemas.'
  - 'Upgrade Pydantic and related packages in the dependency manifest, regenerate the lock file, and verify that dependency resolution does not silently downgrade or install incompatible framework versions.'
  - 'Run an automated migration tool such as bump-pydantic when appropriate, review every generated change, and do not treat automated output as sufficient validation.'
  - 'Replace parse_obj with model_validate and replace parse_raw or parse_file with explicit input loading followed by model_validate or model_validate_json as appropriate.'
  - 'Replace from_orm with model_validate and enable validation from attributes through ConfigDict when object attribute input is required.'
  - 'Replace dict with model_dump and replace json with model_dump_json, then review include, exclude, alias, unset, default, and null handling at every call site.'
  - 'Replace copy with model_copy and determine whether each call requires a deep copy or updated field values.'
  - 'Replace schema with model_json_schema and replace schema_json with explicit JSON encoding of model_json_schema when a JSON string is required.'
  - 'Replace update_forward_refs with model_rebuild and verify recursive and forward-referenced models after import initialization.'
  - 'Replace __fields__ access with model_fields and replace instance field metadata access with class-level model_fields where possible.'
  - 'Replace __fields_set__ access with model_fields_set.'
  - 'Replace class Config declarations with model_config using ConfigDict, translating each option according to Pydantic v2 semantics rather than renaming options blindly.'
  - 'Translate orm_mode to from_attributes, schema_extra to json_schema_extra, validate_all to validate_default, allow_population_by_field_name to populate_by_name or the target-version equivalent, and anystr options to their Pydantic v2 string configuration equivalents.'
  - 'Review extra-field behavior, assignment validation, frozen models, arbitrary type handling, enum value handling, alias population, ignored types, string normalization, and protected namespaces after configuration migration.'
  - 'Replace @validator with @field_validator and choose before, after, wrap, or plain mode based on when the old validator was intended to run.'
  - 'Replace @root_validator with @model_validator and explicitly account for whether the validator receives raw input, a model instance, or a validation handler.'
  - 'Remove unsupported validator parameters such as field and config, using ValidationInfo and model field metadata where equivalent context is needed.'
  - 'Review each validator flag, especially pre, always, each_item, allow_reuse, and skip_on_failure, because their Pydantic v2 equivalents may require structural changes.'
  - 'Move item-level validation into annotated type arguments when each collection item must be validated.'
  - 'Ensure validation failures use suitable exceptions and do not rely on TypeError being converted into a ValidationError.'
  - 'Review default values and default factories because defaults are not necessarily validated unless validate_default is enabled at the field or model level.'
  - 'Replace __root__ models with RootModel and update construction, validation, access, serialization, generics, and schemas for the root value.'
  - 'Replace GenericModel with BaseModel plus Generic where supported, and avoid parameterized generic classes in runtime isinstance checks unless a concrete subclass is defined.'
  - 'Review dataclass behavior, including validation order, extra fields, tuple input, configuration, TypeAdapter usage, and removal of assumptions about an underlying hidden model.'
  - 'Move BaseSettings imports to pydantic-settings, add the dependency explicitly, and migrate settings configuration to SettingsConfigDict.'
  - 'Review settings source priority, environment variable names, prefixes, aliases, case sensitivity, nested delimiters, dotenv loading, secret directories, command-line support, and custom settings sources.'
  - 'Move color and payment-card types to pydantic-extra-types when used, and add explicit dependencies for extracted type packages.'
  - 'Replace removed or discouraged constrained-type factories with Annotated metadata where practical, especially for reusable fields and type-checker compatibility.'
  - 'Review optional fields carefully because a nullable annotation does not necessarily imply that the field has a default or is not required.'
  - 'Review union behavior and coercion because Pydantic v2 may preserve an input that already matches a later union branch instead of coercing it through an earlier branch.'
  - 'Review numeric-to-string, iterable-to-dictionary, boolean, date, time, decimal, URL, and regex validation because coercion and implementation details differ from Pydantic v1.'
  - 'Replace custom type hooks based on __get_validators__ or __modify_schema__ with core-schema and JSON-schema hooks, or use Annotated helpers to isolate third-party types.'
  - 'Use TypeAdapter for validation, serialization, and schema generation involving non-model types such as unions, lists, typed dictionaries, dataclasses, and annotated aliases.'
  - 'Replace json_encoders where practical with @field_serializer, @model_serializer, @computed_field, or supported annotated serializers.'
  - 'Review subclass serialization because nested subclass fields may be omitted when the declared field type is a base model.'
  - 'Review private attributes, computed fields, equality comparisons, model hashing, and comparisons with dictionaries because model identity and equality semantics changed.'
  - 'Review alias behavior because a field without an alias no longer necessarily reports its field name through the alias property.'
  - 'Review JSON schema consumers for changes in required nullable fields, definitions, decimal representation, named tuple handling, input versus output schema mode, and customization hooks.'
  - 'Update FastAPI, SQLModel, Strawberry, Django integrations, command-line frameworks, test factories, IDE plugins, mypy plugins, and code generators to versions documented as compatible with Pydantic v2.'
  - 'If a staged migration is necessary, isolate pydantic.v1 imports behind clear module boundaries, prevent v1 and v2 model types from being nested in unsupported ways, and create a tracked plan for removing the compatibility layer.'
  - 'Run formatting, linting, static type checking, unit tests, integration tests, and package build checks after the mechanical migration.'
  - 'Add or update tests for accepted and rejected inputs, validator ordering, defaults, aliases, ORM or attribute input, settings sources, serialization options, custom types, schemas, and framework request or response behavior.'
  - 'Compare representative pre-migration and post-migration outputs using normalized snapshots, and review each difference rather than updating snapshots indiscriminately.'
  - 'Test supported Python versions in clean environments and verify production installation from the generated lock file or built artifact.'
  - 'Search again for deprecated Pydantic v1 APIs and fail the migration if unapproved compatibility imports or deprecated calls remain.'
  - 'Document intentional behavior changes, dependency minimums, temporary compatibility boundaries, rollout risks, and rollback instructions.'
  - 'Deploy through the normal staged rollout process and monitor validation failures, response serialization errors, settings-loading failures, and schema-dependent client issues.'
verification:
  - 'Dependency resolution installs the intended Pydantic v2 release and compatible versions of every integration package.'
  - 'No unapproved imports from pydantic.v1 remain.'
  - 'No deprecated Pydantic v1 API usage remains in application code.'
  - 'All automated tests, type checks, lint checks, and build checks pass in every supported environment.'
  - 'Representative valid inputs remain valid unless a stricter rule is intentional.'
  - 'Representative invalid inputs remain invalid with acceptable error locations and messages.'
  - 'Serialized payloads preserve required field names, omission rules, null handling, and custom encodings.'
  - 'Generated JSON schemas remain compatible with documented consumers or their changes are versioned and communicated.'
  - 'Settings load correctly from every supported source with the expected precedence.'
  - 'Framework request parsing, response serialization, dependency injection, and generated API documentation work end to end.'
failure_handling:
  - 'If dependency resolution fails, identify the blocking package and upgrade, replace, isolate, or defer it before changing application code.'
  - 'If behavior differs unexpectedly, reduce the case to one model and classify the difference as validation, serialization, configuration, schema, typing, or integration behavior.'
  - 'If a custom type fails, implement or adapt its Pydantic core-schema integration instead of adding broad arbitrary-type allowances without review.'
  - 'If a framework supports only Pydantic v1, stop the native migration or isolate that framework behind a documented compatibility boundary.'
  - 'If schemas change incompatibly, version the external contract or add explicit schema and serializer customization rather than masking the difference in snapshots.'
  - 'If rollback is required, restore both dependency and lock files together and revert any persisted-data or external-contract changes that depended on Pydantic v2 behavior.'
completion_criteria:
  - 'The project installs reproducibly with Pydantic v2.'
  - 'The supported test, lint, type-check, build, and integration matrices pass.'
  - 'Validation, serialization, settings, and schema contracts have been explicitly checked.'
  - 'Remaining compatibility code is approved, isolated, documented, and time-bounded.'
  - 'Intentional behavior changes and operational risks are documented for maintainers and consumers.'
```