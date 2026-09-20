# Fields, serialization, and parsing

## replace-removed-field-shape-apis

Remove imports such as pydantic.fields.SHAPE_LIST and replace
ModelField shape checks with typing.get_origin-based logic. Handle
Annotated, Optional, Union, and nested list annotations as needed by the
repository rather than directly reading __origin__, which may be absent.
For code that wraps a dictionary into a one-item list, iterate
cls.model_fields and wrap only fields whose annotation resolves to a
list. Explicitly verify the branch direction: non-list fields must be
skipped.

## migrate-model-field-introspection

Replace __fields__ with model_fields, accessed on the model class when
practical. Replace ModelField.name with the dictionary key, type_ and
outer_type_ with annotations or actual field values, and
field_info.extra with FieldInfo.json_schema_extra. For custom metadata
such as is_component, declare it with
Field(json_schema_extra={"is_component": true}) and read it safely when
metadata is absent. Preserve declared field order because X12 and other
positional formats depend on it.

## preserve-runtime-model-traversal

For serializers or tree walkers that formerly selected fields by
hasattr(field.type_, "x12") or similar ModelField internals, prefer
iterating model_fields in declaration order and inspecting each actual
instance value. Handle None, lists, model instances, and nested groups
explicitly. This avoids brittle reconstruction of complex Optional and
collection annotations while preserving output order.

## annotate-overridden-model-fields

Import every model module and fix Pydantic v2 errors where a base field
is overridden by an unannotated class attribute. Add the proper type
annotation, for example
'segment_name: X12SegmentName = X12SegmentName.CR5', rather than hiding
the error with ClassVar when the value is genuinely serialized and
validated. Search for other unannotated overrides after fixing the first
occurrence.

## migrate-serialization-and-schema-calls

Replace BaseModel.dict with model_dump, json with model_dump_json,
parse_obj with model_validate, parse_raw with model_validate_json,
schema with model_json_schema, copy with model_copy, and construct with
model_construct where those APIs occur. Preserve arguments such as
exclude, exclude_none, exclude_unset, by_alias, and round_trip. Confirm
enum, Decimal, date, datetime, time, alias, and nested-model output still
matches application expectations rather than treating a renamed call as
sufficient.

## migrate-parser-model-discovery

When code discovers model classes through the presence of schema or by
inspecting schema properties, use BaseModel subclass checks or
model_json_schema as appropriate. Ensure unrelated imported classes are
not selected. For positional parsers, derive field names from
model_fields in declaration order and continue excluding metadata fields
such as delimiters exactly as before.