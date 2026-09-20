# Anti-patterns

- Rewriting imports to pydantic.v1 so the old API keeps working. This can
  make most tests pass while avoiding the requested migration, and the
  grader rejects it.
- Replacing a validator body with a bare return, pass, or other no-op so the
  function still imports. A green suite does not justify deleting behavior,
  and the grader rejects this.
- Declaring the migration complete without running the full repository test suite.
- Piping pytest through head, tail, or grep without preserving the pytest
  exit status. A pipeline can report exit code zero even when collection or
  tests failed.
- Performing broad regex replacements across validator bodies. A failed
  attempt changed values.get calls inside model validators to info.data.get
  even though no info variable existed, and produced invalid semantics.
- Converting every root_validator to the same model_validator form.
  Before and after validators receive different values and require different
  signatures.
- Adding classmethod mechanically to every model_validator. An after model
  validator should normally be an instance method in modern Pydantic v2.
- Treating deprecation warnings as proof that compatibility behavior is
  correct. Deprecated v1 APIs may import while field requirements,
  coercion, ordering, or validator behavior has changed.
- Using an automated migration tool without inspecting its diff. Mechanical
  edits are only a starting point for repository-specific validation logic.
- Assuming Optional[T] remains optional without a default. In Pydantic v2,
  Optional controls whether None is valid; it does not make the field
  non-required.
- Importing a Pydantic symbol under a name already used by a project helper,
  such as importing field_validator and then assigning a helper named
  field_validator to a partial of itself.
- Inverting list-detection logic while replacing SHAPE_LIST. For a wrapper
  that should process list fields, continue when the annotation is not a
  list, not when it is a list.
- Spending the migration on repeated planning or web searches instead of
  making a small coherent change and rerunning collection or focused tests.