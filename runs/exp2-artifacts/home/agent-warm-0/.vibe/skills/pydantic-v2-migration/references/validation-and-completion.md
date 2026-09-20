# Validation and completion

## audit-coercion-and-constraint-changes

Exercise representative model construction for strings, numbers,
Decimal values, enums, dates, lists, and unions. Pydantic v2 changed
coercion and union behavior, including number-to-string handling. Adjust
annotations, explicit before validators, or model configuration only
where the application contract requires the old accepted input. Retain
min_length, max_length, pattern, numeric bounds, and constrained-type
behavior. Do not loosen validation globally to make fixtures pass.

## run-import-and-collection-gates

After each migration layer, run compileall or an equivalent syntax
check, import affected modules, and run pytest collection or the smallest
focused test that reaches them. Fix syntax errors, undefined decorator
names, decorator signature errors, and model-construction errors before
editing deeper runtime logic. Keep the original baseline test count in
view; a drop in collected tests can indicate a hidden collection
problem.

## inspect-every-mechanical-diff

Review git diff after any automated replacement or migration tool.
Search for undefined info references, values.get left in after
validators, classmethod on after validators, accidental edits inside
comments or strings, malformed ConfigDict calls, inverted conditions,
no-op function bodies, and behavior removed along with deprecated APIs.
Revert and redo a file manually if the transformation is not locally
understandable.

## iterate-on-focused-failures

Run the smallest relevant failing test while fixing a coherent class of
errors, then rerun the broader module. Read the complete traceback and
assertion diff rather than only the final line. Classify each failure as
dependency, import, model construction, requiredness, validator phase,
coercion, introspection, parsing, serialization, or domain behavior so
the fix addresses the cause rather than the symptom.

## run-the-full-suite

Run the full repository test command without truncating its output and
require its actual exit status to be zero. Compare collected and passed
counts with the baseline and any repository-provided expected count.
Resolve warnings that reveal incomplete migration, especially deprecated
v1 decorators, class Config, __fields__, dict, schema, or custom Field
extras, even if warnings are not currently fatal.

## perform-forbidden-shortcut-audit

Search the final tree and diff for pydantic.v1, imports of removed v1
APIs, compatibility shims introduced solely to retain v1 behavior, and
validators or other functions whose bodies were emptied or reduced to
unconditional passthroughs. Confirm pydantic-settings is declared when
used and that packaging no longer pins Pydantic below version 2. Any
forbidden shortcut blocks completion even when tests pass.

## verify-behavior-beyond-test-status

Exercise representative end-to-end operations covered by the migrated
models: construct settings, parse a real fixture, validate an invalid
record, serialize a model, generate application output, and inspect a
schema if the project uses schemas. Confirm invalid data still fails for
the intended reason and application output retains ordering and
formatting. This catches validators that stopped running despite a
superficially green suite.

## report-completion

Summarize dependency changes, migrated API categories, non-obvious
semantic fixes, focused and full test commands, exact pass count, and
any remaining warnings. State explicitly that no pydantic.v1 imports or
emptied function bodies were used. Do not report completion if the full
suite, shortcut audit, or representative behavior checks failed.