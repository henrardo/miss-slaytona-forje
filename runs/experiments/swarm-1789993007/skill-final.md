# pydantic-v2-migration

Migrate the repository from Pydantic v1 to Pydantic v2 without using `pydantic.v1`, deleting behavior, weakening tests, or mutating state outside the requested code changes.

## Procedure

1. Inspect before editing:
   - Identify Python and Pydantic versions, package layout, configuration, documented test command, and generated or fixture data.
   - Search for Pydantic imports, `BaseModel`, validators, `Config`, constrained types, settings, schema and serialization calls, ORM usage, private imports, and compatibility shims.
   - Run the complete existing test suite and record the first traceback and failure count. Preserve this baseline.

2. Diagnose failures before changing code:
   - For import errors, inspect the defining module, `__all__`, call sites, and import graph. Determine whether each symbol is public, stale, renamed, circularly imported, or incorrectly assumed to exist. Do not recreate private symbols merely to make imports pass.
   - For `KeyError` or lookup failures, trace the key from its source through normalization, parsing, and mapping tables. Verify that migration changes preserve accepted input forms, case, aliases, defaults, and initialization order; do not patch the lookup with arbitrary fallback values.
   - Distinguish dependency/API errors from application behavior regressions and retain the original traceback for comparison.

3. Convert APIs systematically:
   - Import supported APIs from `pydantic`, never `pydantic.v1`.
   - Replace `@validator` with `@field_validator` and `@root_validator` with `@model_validator`, preserving mode, ordering, error behavior, and return values.
   - Replace `Config` with `model_config = ConfigDict(...)`, translating every setting explicitly.
   - Replace `parse_obj`, `parse_raw`, `dict`, `json`, and schema calls with `model_validate`, `model_validate_json`, `model_dump`, `model_dump_json`, and `model_json_schema` as appropriate.
   - Update settings, constrained types, ORM/object input, generics, dataclasses, serialization hooks, and removed APIs to supported v2 equivalents.

4. Preserve semantics:
   - Use `mode='before'` for raw-input validators, `mode='after'` for validated values, and `mode='wrap'` only when required.
   - Use `ValidationInfo` where v1 validator arguments were used. Return the validated value or model from every validator.
   - Preserve aliases, optionality, defaults, coercion, strictness, nested models, cross-field behavior, custom errors, serialized shapes, schema output, and domain lookup keys.
   - Do not replace logic with no-ops, broad exception handling, silent fallbacks, or compatibility shims.

5. Verify incrementally:
   - Run focused tests after each coherent change, then rerun the complete suite.
   - Add or update tests for validators, invalid inputs, aliases, serialization, nested models, defaults, object input, settings, schemas, and previously observed import or lookup failures.
   - Compare important v1-era outputs and errors with v2 results when compatibility is required. Do not delete tests, skip failures, weaken assertions, or alter fixtures solely to obtain a pass.

6. Finish only when:
   - The complete test suite passes.
   - No production code imports `pydantic.v1` or unsupported Pydantic internals.
   - All observed failures, including import and mapping-key failures, have behavior-preserving fixes and regression tests where appropriate.
   - Remaining deprecation warnings are understood and resolved when they indicate incomplete migration.
   - The final diff contains only necessary migration, test, and configuration changes.

## Prohibited shortcuts

- Do not use `pydantic.v1`.
- Do not restore obsolete private symbols without confirming their intended contract.
- Do not add arbitrary lookup fallbacks or suppress `KeyError` failures.
- Do not replace validator behavior with no-ops.
- Do not declare success without running the complete test suite.