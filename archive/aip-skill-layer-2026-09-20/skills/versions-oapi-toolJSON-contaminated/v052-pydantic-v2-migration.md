---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to native Pydantic v2 without compatibility shims. Use when Pydantic v2 causes import, pytest collection, validation, Config, Field const, parser, optionality, alias, schema, inheritance, forward-reference, root-model, circular-import, or syntax failures during migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 52
    derived_from_traces:
      - "c997561c"
      - "cb2c25e1"
      - "ff6577e9"
      - "738b4882"
      - "23e5cd8a"
      - "0c9c470c"
      - "7ec14fc1"
      - "fbadf6f2"
      - "bcd6adbe"
      - "512a80b8"
      - "ccc3a201"
      - "2bcb35cc"
      - "093a5290"
      - "1ce8fd14"
      - "66c5f797"
      - "f7f84cae"
      - "5fd83784"
      - "851f9d93"
      - "13f5ed82"
      - "93a1dc43"
      - "b0109ff8"
      - "2aaa6423"
      - "c5a728fd"
      - "4d9915d1"
      - "9495aa8e"
      - "713902ba"
      - "532a7600"
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to native Pydantic v2 while
  preserving runtime behavior, validation semantics, model optionality,
  aliases, schema metadata, parser behavior, model inheritance, importability,
  forward-reference resolution, circular-import boundaries, and the complete
  test suite. Remove obsolete APIs such as Field const, v1 Config classes,
  Extra enum configuration, parse_obj, and v1 root-model declarations. Use
  Pydantic v2 APIs, ConfigDict, Literal, model validators, and RootModel where
  appropriate. Never re-point imports to pydantic.v1 or any other v1
  compatibility shim. Never make a function importable by deleting, emptying,
  stubbing, or replacing its operational body; both compatibility shims and
  emptied function bodies are rejected even if tests pass. Work from the
  current repository state, repair any malformed partial migration before
  expanding the change set, clear import-time blockers before lower-priority
  changes, validate every edit at syntax and runtime levels, preserve all
  deliberate inheritance and TYPE_CHECKING boundaries, and continue until
  collection, focused tests, the full suite, static checks, and residual-v1
  searches all pass.

trigger_when:
  - Before deciding whether this procedure applies, read `references/guardrails.md` for the complete trigger list.

anti_patterns:
  - Before editing or choosing a workaround, failing to read `references/guardrails.md` for all prohibited approaches.
  - Re-pointing imports to `pydantic.v1`, using a v1 compatibility package, or otherwise hiding unmigrated source behind a compatibility shim.
  - Emptying, stubbing, deleting, replacing with `pass`, or short-circuiting a function body merely to make the package import or tests pass.
  - Ending the attempt after describing the next action, creating a migration script, compiling one file, or passing only a focused test.
  - Treating a piped pytest command's exit status as authoritative when the pipeline can mask pytest's nonzero status.
  - Applying broad checkout, reset, or generated rewrites that erase validated work from the current or an earlier attempt.
  - Repeatedly writing ad hoc regex migration scripts instead of completing and validating bounded source edits.
  - Assuming py_compile success proves that Pydantic class construction, imports, forward references, or runtime behavior are valid.

steps:
  - name: load-guardrails
    description: >
      Before any migration edit, read `references/guardrails.md`. Read it again
      whenever considering recovery, automation, compatibility shims,
      destructive version-control commands, stopping criteria, or a workaround.
      Explicitly reject pydantic.v1 imports and empty or stubbed function bodies.

  - name: load-detailed-migration-playbook
    description: >
      Before inventorying or editing migration source, read
      `references/migration-playbook.md`. Read the relevant sections again
      whenever changing Config blocks, fields, optionality, parsers,
      serialization, validators, root models, constrained types, schema
      metadata, inheritance, TYPE_CHECKING boundaries, or forward references.

  - name: inspect-current-working-tree
    description: >
      Confirm the repository root and run git status and git diff before
      editing. Treat tracked modifications as potentially useful work from an
      earlier attempt. Inspect each changed file, retain changes that compile
      and preserve behavior, and repair the current topmost blocker without
      erasing unrelated work. Never broadly check out or reset a package
      directory. Ignore harness-owned untracked files unless the task requires
      them. Identify accidental migration scripts and other unrequested
      artifacts so they can be excluded from the final diff.

  - name: preserve-validated-progress
    description: >
      Maintain a short working ledger containing the active blocker, files
      already changed, and the validation completed for each file. Before any
      checkout, revert, generator, or bulk edit, compare the proposed scope
      against that ledger. Revert only a specific unvalidated hunk when
      necessary. Never restore an entire schema package merely because one
      generated file is malformed; doing so destroys validated migration work
      and returns subsequent attempts to the original blockers.

  - name: verify-source-is-syntactically-usable
    description: >
      Before importing the package or making new semantic changes, compile all
      currently modified Python files and then the relevant package. If any
      SyntaxError or IndentationError exists, make it the sole active blocker.
      Inspect the reported line plus preceding lines with line numbers, inspect
      the file's diff, and check bracket, quote, and import-statement balance.
      Syntax errors often point at the line after the real defect; for example,
      an annotation missing a closing bracket can make the next field appear
      invalid. Repair the smallest malformed hunk, compile again, and do not
      continue until the syntax gate passes.

  - name: capture-honest-baseline
    description: >
      Run the repository's documented test command or pytest collection without
      piping it through head, tail, tee without pipefail, or any command that
      masks pytest's status. Capture the real exit code and complete traceback.
      If collection is blocked, record the first syntax, import, or
      class-definition exception as the active blocker rather than claiming
      zero tests as a meaningful behavioral baseline. A grep with no matches
      may legitimately return status 1; interpret its output in context.

  - name: build-migration-ledger
    description: >
      Search production code and tests for Pydantic imports and models, Field
      arguments including const, nested class Config blocks, Extra enum use,
      allow_population_by_field_name, schema_extra, orm_mode, arbitrary type
      settings, validators, root validators, __root__, parse_obj, parse_raw,
      dict, json, schema, copy, update_forward_refs, constrained types,
      Optional annotations, aliases, discriminators, TYPE_CHECKING imports, and
      model inheritance. Record each affected file and construct as an explicit
      ledger. Include dependency declarations, parser call sites, generated
      schema models, fixtures, and high-fan-out constructors. Also record
      already-modified files and whether each currently compiles and imports.
      Do not stop after finding only the first match.

  - name: prioritize-import-time-blockers
    description: >
      Fix the earliest exception on the actual import path before bulk Config
      conversion or lower-priority warnings. One remaining syntax or
      class-definition error prevents tests/conftest.py from loading and
      conceals all later failures. Re-run the same fresh import or collection
      command after the smallest safe fix, then address the next revealed
      blocker.

  - name: migrate-header-const-fields-first
    description: >
      In this codebase, first inspect
      openapi_python_client/schema/openapi_schema_pydantic/header.py. Migrate
      both Header.name and Header.param_in away from Field(const=True) by using
      precise Literal annotations and v2-compatible defaults. Preserve every
      remaining Field argument, especially aliases such as alias="in", and
      preserve the exact Header(Parameter) inheritance. Import Literal and do
      not introduce an unimported BaseModel. Verify accepted values, rejected
      non-constant values, aliases, and inherited Parameter fields.

  - name: compile-after-every-source-edit
    description: >
      Immediately compile each edited Python file after every manual edit,
      scripted rewrite, formatter run, or import-sort operation. Stop at the
      first SyntaxError or IndentationError and inspect the latest file contents
      with line numbers and git diff before touching another file. Confirm the
      edit tool changed exactly the intended text; do not infer success from its
      message. Compilation is an early syntax gate only, not runtime validation.

  - name: fresh-import-after-every-model-edit
    description: >
      After compilation, start a fresh Python process and import the exact
      edited model module. Then import the package entry point used by tests,
      such as openapi_python_client.schema or tests/conftest.py. Fresh imports
      expose class-body NameError, PydanticUserError, annotation resolution,
      and circular-import failures that py_compile cannot detect. Do not rely
      on a module cached by the current process.

  - name: convert-config-blocks-atomically
    description: >
      Convert one complete nested class Config block at a time to a class-level
      model_config = ConfigDict(...) assignment. In the same atomic edit,
      import ConfigDict, translate all Config attributes, and remove Extra only
      when no remaining expression in that module uses it. Common mappings
      include Extra.allow to extra="allow", Extra.forbid to extra="forbid",
      allow_population_by_field_name to populate_by_name=True, schema_extra to
      json_schema_extra, orm_mode to from_attributes=True, and
      validate_assignment without renaming. Preserve model-specific differences
      rather than applying one universal configuration.

  - name: preserve-inheritance-and-field-contracts
    description: >
      For every model, compare the class declaration, annotations, defaults,
      Field metadata, aliases, discriminators, excluded fields, and inherited
      fields before and after migration. Preserve each original base class and
      mixin order. Exercise model_fields and representative construction so an
      importable but behaviorally truncated model cannot pass unnoticed.

  - name: preserve-v1-implicit-optionality
    description: >
      Inventory Optional and Union-with-None annotations that lack defaults.
      Pydantic v2 treats Optional[T] without `= None` as required, unlike the
      historical behavior relied on by many v1 models. Use tests, fixtures,
      callers, and prior construction behavior to decide which fields were
      omittable, then add explicit None defaults only where omission was
      historically valid. Treat zero-argument construction failures such as
      Config() raising ValidationError as evidence that this work is incomplete,
      and inspect every reported missing field.

  - name: validate-representative-model-behavior
    description: >
      For each converted model family, test valid construction, expected
      rejection, omission of historically optional fields, aliases in both
      input and output, extra-field policy, serialization, schema generation,
      inheritance, and nested references. Use representative project fixtures
      wherever possible. A print statement saying an import succeeded is not a
      behavioral test.

  - name: validate-and-complete-migration
    description: >
      Before collection or claiming progress from tests, read
      `references/validation-and-completion.md`. Follow every gate there after
      migration edits, and read it again after the final edit before declaring
      success. Completion requires native Pydantic v2 code, no compatibility
      shims, no emptied functions, a fully discharged migration ledger,
      successful fresh imports, successful collection, all focused and full
      tests passing, static checks passing, and a semantically reviewed final
      diff.

  - name: continue-until-gates-pass
    description: >
      Do not end after announcing the next action, creating a script, compiling
      one file, importing one representative model, or reaching a partial pass
      count. Use the available tools to make and validate the highest-priority
      safe edit, return to the active failure, and continue through the entire
      ledger. Never finish while a generated edit is malformed, while known
      inventory remains, or while the actual full-suite exit status is nonzero.
```