# Migrate model configuration safely

Convert each nested v1 `Config` deliberately to `model_config = ConfigDict(...)`: `Extra.allow` to `extra="allow"`, `allow_population_by_field_name` to the appropriate native-v2 population option, and `schema_extra` to `json_schema_extra`. Preserve the complete existing example dictionary and all model-specific settings. Place `model_config` inside the model at class indentation, not inside a field annotation or example dictionary. Update imports precisely. Prove the pattern on one small model, compile it, inspect its diff, and only then repeat in small reviewed groups.

# Migrate fields, annotations, and optionality

Use `Literal` for constants, `min_length` and `max_length` for collection constraints, and native-v2 field options. Preserve aliases and strict types. Audit every `Optional[T]`: in v2 it is nullable but still required unless it has a default. Add `= None` only when callers, fixtures, or the v1 contract show omission is allowed. Avoid converting validated fields into `ClassVar` merely to silence a model error.

# Audit requiredness and constructor contracts

Enumerate direct model constructions in production and tests, especially configuration, OpenAPI, paths, parameters, responses, and shared fixtures. Compare each omitted argument with the migrated field declaration. Correct production declarations where v1 treated fields as omittable; do not patch every caller or fixture to supply meaningless `None` values.

# Run the default config constructor gate

Instantiate the repository's configuration model exactly as ordinary callers do, including a zero-argument constructor when supported. In the recurring project pattern, fields such as project, package, and version overrides annotated Optional must retain `None` defaults, while list and dictionary defaults must remain isolated between instances.

# Run the shared fixture constructor gate

Import or execute shared fixtures and representative direct constructors. A fixture failing during setup is a production contract signal, not permission to rewrite the fixture. Fix common model semantics first, then rerun the fixture gate.

# Audit default values and instance isolation

Check list, dictionary, set, and nested-model defaults. Prefer `Field(default_factory=...)` where required by intended behavior, but verify Pydantic v2's actual instance isolation before changing public schemas or equality behavior. Test two independent model instances and mutate one.

# Migrate validators without erasing behavior

Translate validator APIs and signatures while preserving execution order, pre/before behavior, cross-field access, errors, defaults, and side effects. Inspect the full original body before editing. Never delete, empty, replace with `pass`, or bypass a validator or helper function merely to make imports or tests pass. Add focused valid and invalid cases for every migrated validator.

# Migrate validation entry points and serialization

Replace `parse_obj` with `model_validate`, and migrate deprecated construction, copying, serialization, and schema methods only where they are Pydantic model operations. For emptiness checks such as `schema.dict().values()`, verify whether `model_dump()` must exclude unset or default values to preserve the original decision. Do not replace unrelated dictionary, JSON, or copy calls by textual pattern alone.

# Migrate schema, introspection, and special models

Convert field and schema introspection, generic models, dataclasses, private attributes, root models, and custom schema hooks with focused behavioral tests. Before replacing a dictionary type alias with `RootModel`, inspect every caller for indexing, iteration, `.items()`, equality, serialization, annotations, and parser expectations. Prefer retaining a plain alias when Pydantic v2 can validate it through the containing model and callers require a dict.

# Rebuild forward references with the correct namespace

Use `model_rebuild()` only on actual model classes. Ensure all recursive names and aliases are imported into the namespace where annotations are resolved before rebuilding. Avoid package-wide loops that call model APIs on dictionary aliases. Validate recursive OpenAPI models with a real nested input, not import success alone.

# Synchronize dependency metadata

Make the declared Pydantic v2 range agree with the compatibility target and supplied post-migration requirements. Regenerate lock or export artifacts only with the repository's supported tool and only when required. Review lockfile diffs for unrelated churn.

# Run a syntax and import gate after every edit slice

Compile every changed Python file, then import the narrow affected module and a top-level package entry point when practical. If compilation fails, stop adding edits and repair the first malformed file using its diff. Import success is a gate, not completion.

# Investigate v2 semantic differences

Reproduce the behavior in a minimal local probe, inspect installed-version documentation or migration guidance only for the unresolved question, and encode the intended contract in a focused test. Prioritize known differences in Optional requiredness, alias population, enum and strict coercion, union selection, extra handling, equality, serialization defaults, and JSON-schema output.