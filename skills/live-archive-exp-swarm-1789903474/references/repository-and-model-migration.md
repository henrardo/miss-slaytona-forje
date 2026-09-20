# Repository and model migration

## inspect-repository-and-task-contract

Read the repository root, pyproject.toml or other packaging files,
lockfiles, migration-specific requirement files, test configuration,
contribution guidance, and git status. Use existing post-migration
dependency files as evidence when present. Determine the supported
Python versions, exact test command, expected test count if documented,
and whether the working tree already contains changes that must be
preserved. Do not assume setup.py exists; list the root before opening
packaging files.

## establish-the-failure

Run the repository's own full test suite before editing and read the
first real traceback. Capture the command, exit status, collected test
count, and first failure. Run pytest directly or use shell pipefail and
tee; do not let a diagnostic head or tail command hide pytest's status.
If collection fails, record that zero executed tests is a collection
failure rather than evidence about runtime behavior.

## inventory-pydantic-surface

Search all production code and relevant tests for Pydantic imports and
v1 APIs. Include BaseSettings, validator, root_validator, parse_obj,
parse_raw, from_orm, construct, copy, dict, json, schema,
schema_json, __fields__, ModelField attributes such as type_,
outer_type_, shape, field_info.extra, Field(regex=...), class Config,
allow_mutation, orm_mode, allow_population_by_field_name, custom
json_encoders, constrained types, dataclasses, GenericModel, and
Optional annotations without defaults. Use rg or fixed-string searches
rather than malformed grep regular expressions. Save a file-by-file
checklist; the initial import count alone is not a complete inventory.

## update-dependency-metadata

Change every authoritative dependency declaration from a v1 pin to an
appropriate pydantic>=2,<3 range. Add pydantic-settings when the project
uses BaseSettings, and update lock or requirements files expected by the
repository. Do not rely on an ad hoc local pip install as the only
dependency change. Install the repository's intended post-migration
dependency set before interpreting subsequent errors.

## migrate-settings-first

Replace BaseSettings imports from pydantic with BaseSettings from
pydantic_settings. Keep Field imported from pydantic. Replace settings
class Config with SettingsConfigDict or the configuration form supported
by pydantic-settings, preserving case sensitivity, environment prefixes,
dotenv behavior, aliases, and other settings semantics. Replace
Field(regex=...) with Field(pattern=...). Run the smallest settings or
import test immediately because BaseSettings is commonly the first
collection blocker.

## migrate-base-model-configuration

Replace class Config on BaseModel subclasses with model_config using
ConfigDict. Translate settings deliberately: frozen replaces the old
immutability intent of allow_mutation=False; populate_by_name replaces
allow_population_by_field_name; from_attributes replaces orm_mode; and
use_enum_values, extra, validate_assignment, arbitrary_types_allowed,
and other behavior must remain equivalent. Put comments outside the
ConfigDict call rather than inserting a standalone string into its
arguments. Do not remove configuration merely to silence warnings.

## preserve-v1-optional-field-semantics

Audit fields annotated Optional[T], T | None, or Union[T, None]. In
Pydantic v2 these remain required unless they have a default. Add
'= None' where the v1 model intentionally allowed omission, while
retaining required nullable fields when that distinction is deliberate.
Pay special attention to large generated-looking segment models, where
this semantic change can create hundreds of validation failures after
collection succeeds.