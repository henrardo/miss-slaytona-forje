# Prohibited patterns

- Never redirect production imports to `pydantic.v1`, `pydantic.v1.*`, or another v1 compatibility namespace to make tests pass.
- Never empty, comment out, bypass, replace with `pass`, or reduce a validator or function body to an unconditional return merely to make a module import.
- Never treat successful imports, compilation, collection, a hand-written smoke script, or a partial passing count as proof that the suite passes.
- Never pipe pytest through `head`, `tail`, or `tee` and then trust the pipeline's zero exit status without `pipefail` and explicit test-process status capture.
- Never globally replace every root validator with the same model-validator mode; classify and migrate every validator from its original semantics.
- Never use repository-wide `sed` or regex transformations for semantic changes such as validator signatures, dictionary-to-instance conversion, optional defaults, or nested model access.
- Never remove a deprecated decorator import before migrating every decorator use in that file; audit imports and decorators together.
- Never add `skip_on_failure=True` merely to retain deprecated post root validators; migrate them natively to correctly shaped model validators.
- Never make every `Optional` field default to `None` in bulk; preserve whether omission was accepted from tests and original behavior.
- Never delete an inherited field override to silence a Pydantic v2 error; annotate it correctly and preserve its registry or serialization role.
- Never delete or relocate a public helper such as `_is_list_field` when tests or consumers import it directly.
- Never assume `model_dump()` can replace `.dict()` on arbitrary values; distinguish models from dictionaries and preserve serialization options.
- Never continue after an automated edit until production code compiles and the affected diff has been inspected for malformed decorators, indentation, imports, and literals.
- Never repeatedly reset or checkout broad production paths after making progress; recover only the malformed hunk while preserving valid migration work and user changes.
- Never write a migration summary or declare the task complete while collection or any focused or full-suite test remains red.