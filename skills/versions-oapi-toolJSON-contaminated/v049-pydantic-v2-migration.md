---
name: pydantic-v2-migration
description: Systematic procedure for migrating a Python codebase from Pydantic v1 to native Pydantic v2 without compatibility shims. Use when Pydantic v2 causes import, pytest collection, validation, Config, Field const, parser, optionality, alias, schema, inheritance, forward-reference, root-model, circular-import, or syntax failures during migration.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 49
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
  - Pydantic v2 is installed but package imports, model definitions, pytest collection, or tests fail.
  - An import raises PydanticUserError for removed Field arguments such as const.
  - Models still use class Config, Extra.allow, Extra.forbid, allow_population_by_field_name, schema_extra, or other Pydantic v1 configuration.
  - Code still calls parse_obj, parse_raw, dict, json, schema, copy, update_forward_refs, root_validator, validator, or other renamed Pydantic v1 APIs.
  - Optional fields, aliases, discriminators, validators, root models, forward references, or generated JSON schema behave differently under Pydantic v2.
  - A partial migration has left incomplete imports, unbalanced annotations, malformed indentation, or generated source that no longer compiles.
  - A partial Pydantic migration passes some tests but collection, the full suite, imports, or static checks still fail.
  - Before deciding whether this procedure applies, read `references/guardrails.md` for the complete trigger list.

anti_patterns:
  - Re-pointing imports to pydantic.v1 or otherwise using a Pydantic v1 compatibility shim; the grader rejects this even if tests pass.
  - Emptying, deleting, stubbing, replacing with pass, or otherwise disabling a function body merely to make imports or tests succeed; the grader rejects this even if tests pass.
  - Changing an inherited model such as Header(Parameter) into Header(BaseModel), which discards inherited fields and behavior.
  - Referring to BaseModel or ConfigDict without importing it; py_compile does not detect runtime NameError in class construction.
  - Removing Extra from imports while any unconverted class Config still evaluates Extra.allow or Extra.forbid.
  - Replacing only the first line of a nested Config block and leaving its attributes over-indented beneath model_config.
  - Leaving a partial import such as `from `, an unclosed annotation bracket, or another malformed edit in the working tree while continuing migration elsewhere.
  - Blaming Python caches, subprocess behavior, or Pydantic for a SyntaxError before inspecting the exact source, delimiter balance, and current diff around the reported line.
  - Using broad regular-expression rewrites for indentation-sensitive class bodies without a dry run, immediate diff review, and compilation of every touched file.
  - Trusting a migration script's success message instead of compiling and importing every file it changed.
  - Creating successive speculative migration scripts while known files remain malformed instead of repairing the first broken file directly.
  - Adding one-off migration scripts to the repository and leaving them in the final diff when they are not a requested project artifact.
  - Running destructive commands such as `git checkout <directory>/*.py` that erase validated migration work from the working tree.
  - Assuming the repository is clean, resetting unrelated changes, or discarding pre-existing work without inspecting its diff.
  - Treating py_compile as proof that class construction, annotation resolution, imports, aliases, or validation work.
  - Treating Config() success alone as proof that high-fan-out Project construction still accepts historical minimal arguments.
  - Blindly adding defaults to every annotation without checking historical behavior, callers, and tests.
  - Introducing mutual runtime imports to resolve cyclic annotations when TYPE_CHECKING and model_rebuild can preserve the import graph.
  - Repeatedly grepping, planning, restarting investigation, or writing speculative scripts after the current blocker and inventory are known.
  - Piping pytest through head, tail, or another command and then trusting the pipeline's zero exit status; this can hide pytest failure.
  - Treating grep exit status 1 for no matches as a failed migration command rather than examining whether no matches was expected.
  - Reporting compile-only edits as suite progress when collection or tests have not run.
  - Stopping after a representative model imports, after 310 or 311 tests pass, or while any migration-ledger item remains.
  - Ending the task after announcing a plan, after creating an unused rewrite script, or while a generated edit is malformed.
  - Before editing or choosing a workaround, failing to read `references/guardrails.md` for all prohibited approaches.

steps:
  - name: load-guardrails
    description: >
      Before any migration edit, read `references/guardrails.md`. Read it again
      whenever considering recovery, automation, compatibility shims,
      destructive version-control commands, stopping criteria, or a workaround.
      Explicitly reject pydantic.v1 imports and empty or stubbed function bodies.

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

  - name: establish-environment-and-dependency-target
    description: >
      Read pyproject.toml, lock or requirements files, and any migration-specific
      dependency manifests such as requirements-v1.txt and requirements-v2.txt.
      Record the installed Python and Pydantic versions and the intended
      post-migration dependency declaration. Confirm that tests are executing
      under Pydantic v2. Update the declared dependency to the intended v2
      range when required, but do not use dependency metadata as a substitute
      for source migration.

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

  - name: protect-config-block-structure
    description: >
      Replace the entire Config suite structurally. Never replace only `class
      Config:` while leaving its former attributes indented beneath a single
      model_config assignment; that produces malformed over-indented source.
      Review the exact post-edit block, compile it, and fresh-import it before
      converting another file. Ensure multiline dictionaries and schema
      examples remain inside ConfigDict under the correct keyword and retain
      balanced delimiters.

  - name: constrain-automation
    description: >
      Prefer small manual or syntax-aware edits for the roughly bounded set of
      schema modules. If automation is justified, make it deterministic, run it
      first in dry-run mode, restrict it to explicitly inventoried files, and
      inspect the complete diff. Compile every touched file immediately and
      stop the batch at the first error. Do not spend the attempt repeatedly
      authoring speculative regex migration scripts; once a script fails or
      corrupts indentation, revert only its unvalidated hunks and use a safer
      method. Do not run a second automated rewrite over files containing
      unreviewed changes from the first.

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

  - name: reproduce-high-fan-out-construction
    description: >
      Locate the exact Project or equivalent high-fan-out constructor used by
      tests and application code. Reproduce its historical minimal argument set
      in a fresh process after Config migration. Config() succeeding alone is
      insufficient: verify Project(...) still accepts its expected config,
      metadata, paths, and defaults and that downstream attributes retain their
      prior values.

  - name: migrate-parser-and-serialization-apis
    description: >
      Replace parse_obj with model_validate and parse_raw with
      model_validate_json where semantics match. Replace dict, json, schema,
      copy, and update_forward_refs with model_dump, model_dump_json,
      model_json_schema, model_copy, and model_rebuild as appropriate. Preserve
      aliases, exclusion flags, round-trip behavior, validation context, and
      error handling at each call site. Test through the real parser entry
      point, not only by constructing isolated models.

  - name: migrate-validators
    description: >
      Convert validator and root_validator usage to field_validator and
      model_validator with correct before, after, and wrap modes. Re-evaluate
      signatures, access to values or ValidationInfo, classmethod decoration,
      assignment validation, and exception behavior. Preserve validator order
      and semantics rather than performing name-only substitutions. Keep every
      validator and helper function operational; never empty a body to bypass a
      signature or import problem.

  - name: migrate-root-models-and-constrained-types
    description: >
      Replace v1 __root__ declarations with RootModel where they occur and
      update construction, validation, dumping, and callers accordingly.
      Migrate constrained-type factories whose v2 signatures changed to native
      v2 constraints or Annotated forms. Preserve externally visible values and
      generated schema rather than only making definitions importable.

  - name: preserve-schema-metadata
    description: >
      Translate schema_extra to json_schema_extra and preserve examples,
      descriptions, titles, aliases, discriminator metadata, and custom schema
      callbacks. Generate representative model_json_schema output and compare
      the important contract with the pre-migration expectation or fixtures.
      Resolve callable signature changes explicitly rather than dropping custom
      schema behavior.

  - name: preserve-type-checking-boundaries
    description: >
      Keep deliberate TYPE_CHECKING imports and string annotations that prevent
      runtime cycles. Do not solve a forward-reference problem by adding mutual
      top-level imports. Import only symbols safe at runtime, retain deferred
      annotations where needed, and use model_rebuild after the required
      namespace is available.

  - name: resolve-forward-references-systematically
    description: >
      Import the package from a fresh process after related model edits and
      instantiate representative nested models. For unresolved annotations,
      identify the ownership and import cycle, preserve the existing boundary,
      and rebuild models in dependency order with the correct type namespace.
      Validate both schema generation and nested model validation because a
      model may import successfully yet fail only when resolving annotations.

  - name: validate-representative-model-behavior
    description: >
      For each converted model family, test valid construction, expected
      rejection, omission of historically optional fields, aliases in both
      input and output, extra-field policy, serialization, schema generation,
      inheritance, and nested references. Use representative project fixtures
      wherever possible. A print statement saying an import succeeded is not a
      behavioral test.

  - name: run-collection-gate
    description: >
      After clearing import-time blockers and completing a coherent edit group,
      run pytest collection with its real exit code. Do not pipe output through
      head or tail. Fix every collection error before interpreting test counts.
      Read the complete traceback through the first project source line; a
      truncated traceback can conceal an incomplete import or malformed file.
      A sequence of compile-only edits with no collection invocation provides
      no suite evidence.

  - name: run-focused-tests
    description: >
      Run the smallest relevant tests for each migrated model, parser path,
      fixture constructor, schema contract, or validator. Include regression
      tests for discovered failures such as const fields, aliases, omitted
      Optional fields, minimal Project construction, and any syntax damage
      introduced by migration tooling. Confirm command exit status directly.

  - name: run-full-suite-repeatedly
    description: >
      Run the complete suite after each coherent migration tranche and again
      after the final edit. Use the repository's normal command without
      status-masking pipelines. Treat 310 or 311 passing tests with any
      remaining failure, collection error, or migration-ledger item as an
      intermediate state, not completion.

  - name: run-static-and-import-gates
    description: >
      Run compileall or compile every project Python file, then run configured
      formatting, import sorting, linting, and type checking. Fresh-import the
      top-level package, schema package, parser entry point, and test conftest.
      Resolve warnings that indicate obsolete Pydantic configuration or
      protected behavior rather than suppressing them indiscriminately.

  - name: audit-residual-v1-constructs
    description: >
      Re-run the migration ledger searches. Confirm there are no production
      imports from pydantic.v1, no Field const arguments, no obsolete class
      Config blocks, no Extra enum configuration, no unintended v1 API calls,
      and no v1 root-model or validator declarations. Distinguish expected
      textual mentions in migration documentation or tests from executable
      residual code.

  - name: inspect-final-diff-for-semantic-damage
    description: >
      Review the complete git diff file by file. Look for changed base classes,
      dropped fields or metadata, incomplete import statements, unbalanced
      annotations, empty function bodies, accidental pass or ellipsis
      statements, removed operational logic, broad formatting churn, malformed
      indentation, unintended dependency changes, generated migration scripts,
      and unrelated resets. Re-run the relevant compile, import, focused-test,
      and full-suite gates after every repair.

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