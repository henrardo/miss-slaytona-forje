# Validator migration

## migrate-field-validators

Replace @validator with @field_validator and remove allow_reuse. Use
mode="before" only when the old validator used pre=True; otherwise use
the default after mode. Add @classmethod in the decorator order expected
by Pydantic v2. Replace the old values argument with ValidationInfo only
when sibling-field access is actually needed, and read previously
validated fields from info.data. Remember that info.data contains only
fields validated earlier in model field order. Translate always=True
behavior with validate_default or model configuration after checking the
intended semantics. Preserve every validation branch and error message
unless tests or requirements demand a change.

## migrate-reusable-validator-helpers

Inspect project helpers that wrap validator or decorate reusable
functions. Avoid a name collision such as importing field_validator and
then assigning field_validator = functools.partial(field_validator).
Alias the Pydantic decorator, for example
pydantic_field_validator, or rename the project helper. Remove obsolete
allow_reuse and adapt reusable function signatures to the actual values
they consume. Verify imported decorated validators are still registered
when assigned on model classes, including inherited-field cases and any
need for check_fields=False.

## classify-and-migrate-root-validators

Review every root_validator individually. Convert pre=True validators
to @model_validator(mode="before") class methods that accept and return
the raw input object, normally a dictionary. Convert post validators to
@model_validator(mode="after") instance methods that inspect attributes
on self and return self. Do not retain values.get in an after validator,
and do not replace it with info.data. Account for the old
skip_on_failure behavior and assignment-validation cases. If an after
rule is substantially clearer as a before rule, only change its phase
after confirming coercion, defaults, aliases, and missing-field
semantics remain equivalent.

## check-validator-method-inheritance

Inspect validator names across base and derived models. Pydantic v2
treats an overridden validator method differently from two independently
named validators, so duplicate method names can silently suppress base
behavior. Rename methods where both base and derived validation must run,
while preserving intentional overrides. Import affected modules after
each coherent batch.