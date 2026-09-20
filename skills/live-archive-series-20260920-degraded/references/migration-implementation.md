# Migration implementation

## repair-first-collection-blocker

Fix only the first complete collection traceback and rerun collection without output truncation. Continue until collection advances. Import smoke tests prove only that one module imports; they never prove the migration or suite is complete.

## update-dependencies-and-settings

Update all authoritative dependency declarations consistently. Import `BaseSettings` and `SettingsConfigDict` from `pydantic_settings`, keep `Field` in `pydantic`, replace settings `Config` with `model_config`, and preserve case sensitivity, environment names, defaults, and cache behavior. Replace removed `Field(regex=...)` with `pattern=...` and test both valid and invalid settings values.

## migrate-shared-model-configuration

Convert class-based `Config` to `ConfigDict` while preserving `extra`, enum handling, immutability, hashing, arbitrary types, assignment validation, aliases, and default validation. Use `frozen=True` for v1 immutability rather than retaining removed `allow_mutation=False`. Apply configuration to the correct base class so subclasses inherit intended behavior.

## migrate-inherited-field-overrides

Pydantic v2 rejects a subclass that replaces an inherited model field with an unannotated attribute. Find every such override, including registry keys such as `segment_name = X12SegmentName.CR5`, and add the correct annotation rather than deleting the field or weakening the base model. Compile and import both large versioned segment modules after this pass.

## migrate-field-definitions

Convert removed field keywords and constrained-type arguments, including `regex` to `pattern`, without changing accepted values. Preserve custom metadata under `json_schema_extra` using valid Python values such as `True`, not JSON `true`. Audit every `Optional[T]`: in v2 it remains required unless it has `= None` or an equivalent default. Add defaults only where v1 behavior, fixtures, or public contracts prove omission was allowed; never perform a repository-wide Optional rewrite. Preserve numeric constraints and avoid changing a string field to an integer merely to satisfy a schema error.

## migrate-reusable-validator-infrastructure

Remove `allow_reuse`; v2 handles reuse differently. Do not shadow the imported `field_validator` with a partial of itself or import it from `pydantic.validators`. For validator functions imported and attached in many models, preserve the callable contract and attach them using native v2 decorators at each intended field or model boundary. Handle `check_fields=False` only when inheritance requires it. Test representative attachment sites in both version families.

## migrate-field-validators

Convert each v1 `@validator` individually to `@field_validator`; do not use blind decorator substitution. Classify `pre`, `always`, multi-field, reused, and inherited behavior. Replace v1 `values` access with `ValidationInfo` and `info.data`, remembering that only previously validated fields are available. Use `mode="before"` only when the original used `pre=True`. Preserve validation of defaults with model configuration or field settings where required. Ensure the decorator name is imported wherever used, and remove stale `validator` imports only after all decorators are migrated.

## classify-every-model-validator

For every v1 `@root_validator` and functional `root_validator(...)(function)` assignment, record whether it must inspect raw input before validation or a validated model after validation. Record whether the body expects a dictionary, model instance, nested dictionaries, nested model instances, or field-order-dependent data. Never infer mode from a search-and-replace rule, and never convert all root validators to one mode.

## migrate-model-validators

Convert v1 `pre=True` validators to `@model_validator(mode="before")` operating on raw input and returning the input mapping. Convert post validators to `@model_validator(mode="after")` operating on `self` and returning `self`; rewrite dictionary reads and writes to attribute access without changing the validation logic. Preserve every raise condition, mutation, calculation, and error message. Pay special attention to nested loops: post-validation children are model instances, so code that previously indexed dictionaries may need attribute access or a deliberate `model_dump()` boundary. Add `@classmethod` only where the v2 decorator contract requires it. After each conversion, instantiate a valid and invalid representative case.

## close-validator-import-decorator-gap

Scan every production file for decorator uses and imports together. No file may use `@validator`, `@root_validator`, `validator(...)`, or `root_validator(...)`; no file may use `field_validator` or `model_validator` without importing the correct native v2 symbol. Compile and import both top-level versioned segment modules. Specifically prevent the observed regressions where v4010 raised `NameError: validator is not defined` and v5010 retained a post `@root_validator` requiring `skip_on_failure=True`.

## repair-field-introspection

Replace `__fields__` with `model_fields`, `ModelField` assumptions with `FieldInfo` and type introspection, `field_info.extra` with guarded `json_schema_extra`, and removed `SHAPE_LIST` checks with `typing.get_origin` logic that handles `list`, `List`, `Optional[List[T]]`, and unions. Do not mechanically map obsolete attributes such as `type_`, `outer_type_`, `shape`, or `name`; derive each replacement from its use. Guard `json_schema_extra or {}`.

## preserve-list-field-helper

Implement or retain the public `_is_list_field` helper in the module from which tests and users import it. Make it accept v2 `FieldInfo` or its documented annotation input, unwrap optional and union annotations, and return true only for list fields. Reuse it in the before-model validator that wraps a single segment dictionary into a list. Test required lists, optional lists, non-list fields, a bare dictionary, an existing list, and `None`.

## migrate-parsing-and-serialization

Replace v1 methods such as `dict`, `json`, `parse_obj`, and schema methods with native v2 methods only at genuine Pydantic model boundaries. Preserve `exclude`, alias, enum, delimiter, null, unset, decimal, date, and nested-model behavior. Update parser field iteration and component metadata lookup to v2 APIs. Do not call `model_dump()` on ordinary dictionaries, and when shared code can receive either a dictionary or model, branch explicitly. Test parser, CLI, `count_segments`, duplicate-code validation, and `.x12()` output.

## verify-generated-registries

Inspect import-time registries that enumerate segment classes or read field defaults. Replace `__fields__["segment_name"].default` with guarded v2 `model_fields` access, preserve exact registry keys and class values, and exclude base classes exactly as before. Import both version registries and compare representative entries and counts with the original contract.