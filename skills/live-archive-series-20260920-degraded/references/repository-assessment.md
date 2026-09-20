# Repository assessment

## establish-the-failure

Run the repository's real test command without truncating its output and preserve its actual exit status. Do not use `| head`, `| tail`, or `| tee` unless `set -o pipefail` is active and the test process status is captured separately. Record the complete first traceback, collection count, pass count, fail count, warning count, command, and exit code. A command whose pipeline exits zero while pytest failed is not a valid baseline.

## confirm-location-and-working-tree

Confirm the exact repository path before every edit. Inventory pre-existing tracked and untracked changes, distinguish harness files such as `.vibe/`, and do not reset, checkout, overwrite, or discard user changes. If the workspace is already partially migrated, treat its diff and failures as evidence rather than repeatedly restarting from HEAD.

## inspect-repository-contract

Inspect dependency metadata, lockfiles, CI workflows, supported Python versions, extras, test settings, package entry points, requirements-v2 files, and repository-specific migration tests before editing production code. The full CI command is the completion authority unless the user specifies another command.

## make-runtime-match-target

Verify versions using the same Python executable that will run tests. Install or update Pydantic v2 and `pydantic-settings` only when repository metadata requires it, then re-check imports and versions. Do not let an editable install silently downgrade Pydantic back to v1, and do not use `pydantic.v1` as a migration shortcut.

## inventory-v1-surface

Search production code, tests, generated registries, nested transaction packages, settings, parser and CLI code for every v1 interface. Include multiline imports and decorator aliases, not only single-line grep matches. Record malformed partial-v2 syntax separately, including doubled decorators, missing imports, `@model_validator(mode="before")pre=True)`, extra parentheses, invalid indentation, lowercase `true`, and scripts or broad edits left by earlier attempts.

## inventory-public-and-test-contracts

Include public model classes, settings classes, parser behavior, `.x12()` output, CLI exports, validation errors, reusable validators, segment registries, and helpers imported directly by tests. In particular, preserve helpers such as `_is_list_field` even if they did not exist in the original v1 module but are required by migration-specific tests.

## preserve-original-semantics

Before rewriting each validator, read and retain its complete original body, decorator options, field order assumptions, mutation behavior, return value, exception type, error text, and validation timing. Use git source or a clean copy to recover bodies corrupted by a partial migration. Never replace a body with `pass`, `return self`, an unconditional value, a comment, or a no-op solely to make import or collection succeed.

## build-migration-ledger

Create one row per migration site with file, symbol, v1 construct, intended v2 construct, original semantics, affected tests, status, and latest failure. Include every validator and every reusable decorator assignment individually; a grep count is not a substitute for the ledger.

## classify-migration-work

Order work by dependency: syntax and imports, settings, shared base models, inherited fields and field declarations, reusable validation infrastructure, field validators, model validators, introspection, parsing and serialization, registries, then transaction-specific packages. Separate mechanical renames from semantic rewrites; only the former may be automated.