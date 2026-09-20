# Establish repository root and state

Resolve the root from the current working directory, record Python and installed Pydantic versions, inspect the top-level project files, and capture `git status --short` plus the initial diff. Store and reuse the resolved root instead of retyping absolute paths.

# Recover a partially edited working tree

Classify each modification as pre-existing user work, verified prior migration work, malformed prior migration work, or an edit made in this run. Preserve unknown and user-owned changes. Compile modified Python files before making more edits. Repair malformed files from their diff and original version rather than stacking new batch rewrites on top.

# Identify authoritative project commands

Inspect `pyproject.toml`, task runners, CI workflows, lockfiles, requirements files, contributor docs, and test configuration. Identify the complete suite, collection command, focused test syntax, formatting, linting, typing, and generation or integration gates. Do not invent a Poetry workflow when Poetry is unavailable and the harness supplies a working environment.

# Establish the unpiped baseline

Run the authoritative test or collection command without `head`, `tail`, or exit-masking pipelines. If output must be captured, use a method that preserves the test process exit status and inspect the saved output afterward. Record the exact command, exit code, collection status, pass count, failure count, warnings, and first actionable traceback.

# Act immediately on a const collection blocker

Inspect the intended constant values and convert fields to `Literal[...]` annotations with suitable defaults. For the known header pattern, preserve `name == ""` and `param_in == ParameterLocation.HEADER` as validated model fields rather than turning them into `ClassVar` attributes. Compile and import the narrow module immediately, then rerun collection.

# Inspect project constraints

Determine supported Python versions, target Pydantic range, packaging tool, generated-code constraints, public compatibility promises, and whether supplied pre- and post-migration requirements define the harness environment.

# Synchronize the target environment

Verify the interpreter actually imports the intended Pydantic v2 version. Prefer repository-provided post-migration requirements or the established environment command. Do not update dependency metadata merely to match an accidental local install, and do not install unrelated tooling unless the authoritative workflow requires it.

# Inventory the complete Pydantic surface

Search production code, tests, fixtures, package exports, templates, dependency metadata, and generated examples. Include BaseModel and RootModel definitions; `Extra`; nested `Config`; `schema_extra`; `allow_population_by_field_name`; removed `Field` arguments such as `const`, `min_items`, and `max_items`; validators; parsing and construction methods; `dict`, `json`, `copy`, and schema APIs; field introspection; aliases; forward references; recursive unions; type aliases; mutable defaults; Optional fields without defaults; and `pydantic.v1`. Treat no-match searches as inventory facts rather than tool failures.

# Inspect model relationships and public behavior

Trace model imports, inheritance, aliases, recursive references, package exports, parser entry points, fixtures, direct constructors, mapping assumptions, JSON-schema examples, and serialization consumers. Record where callers expect omitted optional fields, alias and field-name population, dictionary-like values, constant validation, extra-key retention, or default constructors.

# Establish behavioral sentinels before batch edits

Select fast checks for top-level import, the default configuration constructor, representative aliases such as `$ref` and `in`, extra-field retention, constant rejection, mutable-default isolation, OpenAPI validation, and shared fixtures. Capture current intended behavior from tests and callers.

# Form an executable slice plan

Order work by blockers and dependency structure: collection blockers; representative model configuration; field and requiredness semantics; parser entry points; shared fixtures; recursive and specialist models; dependency metadata; then residual cleanup. Every slice must name the files, intended behavior, compile/import check, and narrow test to run.

# Execute the first planned edit immediately

Do not end the turn after planning. Make one narrow production edit, compile it, import the affected module, and run its focused sentinel before moving to the next slice.