---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 without compatibility shims, preserving validation behavior, model optionality, aliases, schema metadata, parser behavior, inheritance, forward references, circular imports, syntax integrity, and the full test suite.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 47
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
---

```yaml
purpose: >
  Migrate a Python project from Pydantic v1 to Pydantic v2 while preserving
  runtime behavior, validation semantics, model optionality, aliases, schema
  metadata, parser behavior, model inheritance, importability,
  forward-reference resolution, and tests. Remove obsolete APIs such as Field
  const, v1 Config classes, Extra enum configuration, parse_obj, and v1
  root-model declarations. Use native Pydantic v2 APIs, ConfigDict, and
  RootModel where appropriate; never use pydantic.v1 compatibility imports.
  Keep every function operational; an empty or stubbed function body is not a
  migration and is rejected even when tests appear green. Clear import-time
  blockers such as Field(const=True) before lower-priority configuration work,
  because one remaining class-definition error prevents conftest collection
  and conceals useful failures. In this codebase the first known blocker is
  Header.name and Header.param_in in header.py; migrate both to Literal while
  retaining Header(Parameter), then compile and fresh-import before doing any
  bulk Config migration. Preserve each model's original base class: changing
  an inherited model such as Header(Parameter) into Header(BaseModel) can
  discard fields and behavior, while referring to BaseModel without importing
  it causes a NameError that py_compile cannot detect. Likewise, removing
  Extra from an import while an unconverted class Config still evaluates
  Extra.allow or Extra.forbid causes a class-definition NameError that
  py_compile cannot detect. Convert each Config block and its imports as one
  atomic edit, then fresh-import the exact module and package entry point.
  Keep source syntactically valid by compiling each edited Python file
  immediately after every edit, scripted rewrite, formatter run, or
  import-sort operation, then import edited model modules in a fresh process
  before editing another file. A batch rewrite that introduces one
  IndentationError can reduce the suite to zero tests, so never trust a
  migration script's success message; compile every file it touched and stop
  at the first error before making further changes. In particular, replacing
  only the first line of a nested Config block with model_config while leaving
  its former attributes indented beneath it creates invalid source such as a
  standalone over-indented populate_by_name assignment. Convert the complete
  block structurally and validate the latest contents immediately. Preserve
  deliberate TYPE_CHECKING boundaries and resolve cyclic annotations without
  mutual runtime imports. Treat zero-argument model construction failures such
  as Config() raising ValidationError as evidence that v1 implicit optionality
  was not preserved; inspect every missing field and its callers before
  proceeding. Also reproduce the exact high-fan-out Project construction used
  by tests: Config() succeeding alone does not prove Project(...) accepts its
  historical minimal arguments. Resume useful pre-existing migration work from
  the working tree instead of assuming a clean checkout: inspect each diff,
  retain validated changes, and fix the current topmost blocker without
  erasing unrelated work. Keep discovery bounded: once the blocker, inventory,
  and project-specific migration evidence are known, begin small validated
  edits rather than repeatedly grepping, writing planning documents, creating
  speculative rewrite scripts, or restarting the investigation. Continue
  through the entire migration ledger after each successful representative
  edit; a partially converted schema package and 310 or 311 passing tests are
  intermediate states, not completion. A sequence of compile-only edits with
  no collection or test invocation provides zero suite evidence and must not
  be reported as progress. Never finish while a generated edit is malformed,
  while known inventory remains, or after merely announcing a plan: use the
  available tools to make and validate the highest-priority safe edit and
  continue until the final gates pass.
trigger_when:
  - Pydantic v2 is installed but imports, model definitions, or tests fail.
  - Before deciding whether this procedure applies, read `references/guardrails.md` for the complete trigger list.
anti_patterns:
  - Re-pointing imports to pydantic.v1 or otherwise using a Pydantic v1 compatibility shim; the grader rejects this even if tests pass.
  - Before editing or choosing a workaround, read `references/guardrails.md` for all prohibited approaches.
steps:
  - name: load-guardrails
    description: >
      Before any migration edit, read `references/guardrails.md`. Read it again
      whenever considering recovery, automation, compatibility shims, stopping
      criteria, or a workaround.
  - name: establish-and-execute-migration
    description: >
      At the start of the migration, read `references/migration-workflow.md`
      and follow its steps in order through dependency, model, configuration,
      parser, validator, optionality, import-graph, and forward-reference work.
      Return to the relevant step there whenever a compile, import, syntax,
      class-definition, fixture-construction, or circular-import failure occurs.
  - name: validate-and-complete-migration
    description: >
      Before collection or claiming progress from tests, read
      `references/validation-and-completion.md`. Follow every gate there after
      migration edits, and read it again after the final edit before declaring
      success.
```