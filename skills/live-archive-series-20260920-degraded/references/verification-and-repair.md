# Verification and repair

## create-small-edit-checkpoints

Establish reversible checkpoints without overwriting unrelated changes. After each checkpoint, run `py_compile` or `compileall`, import the changed module, run focused tests, and inspect `git diff`. If a transform changes many files, sample the beginning, middle, and end of every affected pattern before proceeding.

## recover-malformed-partial-migration

Repair syntax from complete tracebacks before semantic migration. Prefer restoring only the malformed hunk from known-good source and reapplying a small correct edit; do not run another broad regex over damaged code. Compile every changed file immediately and inspect decorators and imports around each repair.

## compile-production-code

Compile every production Python file, not only recently edited modules. Treat indentation errors, malformed decorators, doubled arguments, invalid Python booleans, duplicate imports, and missing names as migration failures. Fix each from its complete traceback before proceeding.

## run-import-and-collection-gate

Import core models, settings, support, parsing, both versioned segment modules, representative transaction packages, and public helpers. Then run the complete collection command without truncation and require exit zero. Record collected test count and compare it with the expected repository count so silently lost tests cannot look green.

## run-focused-behavior-tests

Run focused tests for settings, shared models, both segment versions, loop initializers, repeatable segments, parsing, serialization, support helpers, registries, and each changed transaction package. Use actual pytest node IDs discovered by collection; a misspelled or nonexistent node is not a passing test.

## compare-validation-semantics

Compare valid construction, invalid construction, omitted optionals, defaults, extra fields, aliases, nested models, reusable validators, error locations, exception types, and messages against semantic snapshots and tests. A model that imports but makes formerly optional fields required, skips a validator, or changes `.x12()` output is not behavior-preserving.

## repair-iteratively-to-green

Work from the first complete failure, fix its root cause, rerun the smallest reproducer, then rerun the broader gate. Update the migration ledger after every repair. Do not batch unrelated fixes, repeatedly restart the migration, create summary files while tests are red, or stop because 56, 57, 58, or any other partial number of tests passes.

## audit-automated-edits

Review every line changed by scripts, regex, `sed`, or formatters. Reject broad substitutions that add duplicate imports, erase arguments, corrupt decorators, change all model validators to one mode, convert all optionals, alter unrelated regex code, or produce syntax such as doubled parentheses. Automated edits are acceptable only for proven mechanical patterns followed by compile, diff, and behavior checks.

## run-static-migration-audit

Search production code for all prohibited compatibility imports and remaining v1 interfaces. Distinguish documentation mentions from executable code. Also search for malformed partial migration artifacts, empty validator bodies, temporary scripts, migration summaries, and accidental generated files.

## run-full-suite

Run the exact complete repository or CI test command with no `-x`, no selected files, no output truncation, and no status-masking pipeline. Require the test process itself to exit zero. Capture total collected, passed, failed, skipped, xfailed, and warning counts.

## verify-behavior-preservation

Re-run representative positive and negative contract probes after the full suite: settings environment behavior, immutable delimiters, enum serialization, repeatable-segment wrapping, component separators, parser/model round trips, registry lookups, nested loop validation, and public helper imports.

## final-diff-and-status-gate

Inspect the complete diff and status, remove accidental summaries and temporary migration scripts unless requested, preserve pre-existing user changes, and verify dependency files agree. Explicitly reject any production `pydantic.v1` import and any function or validator whose body was emptied, bypassed, or reduced to a no-op to obtain green tests.

## report-completion

Report completion only when the final gate proves native v2 imports, successful compilation, complete collection, focused contract coverage, static audit success, and an untruncated full-suite exit code of zero. State the exact command and result. If any gate is red or unrun, report the remaining blocker instead of claiming success.