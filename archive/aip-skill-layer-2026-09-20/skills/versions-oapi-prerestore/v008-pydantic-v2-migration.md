---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and getting the repository test suite green.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 8
    derived_from_traces:
      - b40bc778
      - 13f5ed82
      - c997561c
      - 36ec346f
      - 76a05f00
      - 2e474527
      - 7d7b64ad
      - 68c47457
      - 851f9d93
      - 1088e1bd
      - 1b16b6ed
---

```yaml
# Learned from the successful trace and later regressions: do not begin with a broad
# mechanical rewrite. In this fixture the dependency was already set to Pydantic v2,
# and the first useful error was Config() failing because Optional fields lacked
# explicit None defaults. Later failures came from broad schema rewrites that corrupted
# Config classes and from changing string forward references into direct imports,
# creating circular imports such as partially initialized path_item when importing
# PathItem. Work from the first import or setup traceback, fix one semantic class at a
# time, preserve intentional forward references, then verify with compile, targeted
# tests, migration grep audit, and the full suite.
purpose: >
  Complete a real Pydantic v1 to v2 migration by using the first failing
  traceback to identify remaining v1 assumptions, updating those assumptions
  directly, preserving file structure, aliases, examples, and intentional
  forward references, and verifying with syntax checks, targeted tests, a
  final migration grep audit, and then the full suite.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - A repository has already bumped to Pydantic v2 but tests fail with Pydantic validation, config, schema, or forward reference errors
  - A suite fails during import because Pydantic v2 rejects v1 model definitions
  - Pytest exits before collection with a PydanticUserError from a model class definition
  - Pytest setup fails because a Pydantic model cannot be instantiated with formerly optional fields omitted
  - Pytest cannot import conftest because a Pydantic model module has SyntaxError, IndentationError, unresolved forward references, or a circular import

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Do not repoint imports to pydantic.v1 because that is a compatibility shim rather than a migration
  - Do not empty a validator, hook, parser, or function body just to keep imports or tests green
  - Do not mass rewrite every Pydantic model before seeing the actual traceback
  - Do not replace whole files when a small field or config edit is enough
  - Do not start schema model rewrites while the first pytest error is Config instantiation failing
  - Do not treat a large failure count as permission to edit broadly because the setup error may be the real blocker
  - Do not use broad regex rewrites for Config classes with schema examples because it can corrupt nested dictionaries and create syntax errors
  - Do not run generated migration scripts over openapi_schema_pydantic files unless each changed region is immediately reviewed and compiled
  - Do not leave malformed fragments such as extra equals dot allow after converting Extra.allow
  - Do not leave model_config indented outside a class body after editing Field const or Config
  - Do not stop after changing only one const occurrence when grep still finds const equals elsewhere
  - Do not continue to Optional defaults, schema_extra, or forward references while pytest still fails during import on syntax or Field const
  - Do not replace StrictInt or StrictStr with imports of int or str from pydantic
  - Do not convert intentional string forward references between mutually importing schema modules into direct runtime imports
  - Do not fix a model is not fully defined error by adding imports that create a partially initialized module circular import
  - Do not call model_rebuild before all mutually referenced models are imported
  - Do not add model_rebuild into the individual module that still imports only part of the reference graph
  - Do not keep a stringified Literal annotation when Pydantic reports the model is not fully defined
  - Do not declare the migration complete after only import checks or a partially passing run
  - Do not stop at 311 passing tests or any other partial count when pytest still reports a failure
  - Do not ignore deprecation warnings for schema_extra when the suite still exercises JSON schema generation

steps:
  - name: establish-current-state
    description: >
      Inspect pyproject.toml, requirements files, and the installed environment before
      changing code. Determine whether the project still depends on Pydantic v1 or has
      already been bumped to Pydantic v2. If it is still on v1, update the declared
      dependency to the task target. If it is already on v2, do not churn dependency
      files. Run the repository test suite or the failing test command and save the
      first actionable Pydantic, setup, import, or syntax error plus the exact file and
      line from the traceback.

  - name: triage-the-first-real-error
    description: >
      When pytest prints many failures, scroll to the first error block and identify
      what prevents reliable execution. A setup error from Config() or a conftest
      import failure must be fixed before touching unrelated schema files. In the
      learned fixture, the full suite showed many failures, but the blocker was
      Config() raising field required errors for project_name_override,
      package_name_override, and package_version_override. Fix that kind of blocker
      first, then re-run the same targeted test to prove progress.

  - name: search-pydantic-surface-area
    description: >
      Search the source tree for Pydantic imports and v1-only patterns before editing.
      Useful searches are from pydantic import, import pydantic, class Config, Extra
      dot, allow_population_by_field_name, schema_extra, const equals, Field open
      paren, min_items, max_items, update_forward_refs, parse_obj, dict open paren,
      json open paren, BaseSettings, validator open paren, and root_validator. Also
      search for direct imports among mutually referenced OpenAPI schema modules before
      editing forward references. Use these results as an edit checklist, not as
      permission to blindly rewrite whole files.

  - name: recover-first-if-a-prior-edit-broke-syntax
    description: >
      If pytest fails before collection with SyntaxError or IndentationError in a
      Pydantic model file, stop all migration work and repair that file first. Read the
      exact file and nearby lines, inspect git diff for the file, and either restore the
      damaged region from the original version or rewrite only the malformed class
      block by hand. For damage like extra equals dot allow, replace it with a valid
      model_config dictionary inside the class, preserving examples and aliases. Run
      python -m compileall on the package or import the failing module before touching
      any other migration item.

  - name: unblock-imports-before-anything-else
    description: >
      If pytest cannot import conftest or the package, fix that import-blocking error
      before doing any larger migration work. For a PydanticUserError about const being
      removed, open the exact model named in the traceback and migrate that field
      immediately. For an ImportError mentioning a partially initialized module, inspect
      recent edits for direct imports that replaced intentional string forward
      references and revert those direct imports before adding any new migration edits.
      Re-run the same import or pytest command after the edit. Do not work on Optional
      defaults, schema_extra, model_rebuild, validators, or dependency metadata while
      the package still fails to import.

  - name: fix-optional-fields-without-defaults
    description: >
      In Pydantic v2, Optional[T] or T union None without a default is still a required
      field. When tests instantiate a model with missing optional settings and fail
      with field required validation errors, add an explicit default of None to fields
      that are semantically optional. In the learned fixture, Config needed
      project_name_override, package_name_override, and package_version_override
      changed from Optional[str] with no default to Optional[str] = None. Do this before
      broad schema edits if the first suite error is Config(). Re-run the targeted
      failing setup or Project test immediately after this change.

  - name: replace-field-const-with-literal-in-traceback-file
    description: >
      Pydantic v2 removed Field const. In the traceback file, change each field using
      Field with const true to a typing.Literal annotation and remove only the const
      argument. Preserve the original default value, alias, required marker, comments,
      inheritance, and model_config. Import Literal from typing if the module does not
      already import it. For a subclass such as Header extending Parameter, keep the
      subclass and only change the annotated field declarations that used const.

  - name: grep-and-fix-every-remaining-const
    description: >
      After the traceback file imports cleanly, grep the repository for const equals
      and fix every remaining Field const occurrence the same way. This is mandatory
      before running the full suite because one leftover const can stop collection and
      produce zero passing tests. Re-run grep after edits and continue only when no
      source occurrence remains. Ignore generated cache files and do not edit tests
      unless tests define Pydantic models that are part of the failing import path.

  - name: run-syntax-and-import-checks-after-every-edit
    description: >
      After changing imports, Field declarations, Optional defaults, or model_config,
      run a fast syntax or import check before making more migration changes. Good
      checks are python -m compileall for the edited package, python -c importing the
      edited module, or the same pytest command that previously failed during conftest
      import or setup. If the result is IndentationError, SyntaxError, another
      PydanticUserError, the same Config validation error, or a partially initialized
      module ImportError, stop and fix the exact file and line before continuing. This
      check would have caught the example.py corruption, the lingering Config() setup
      failure, and the path_item circular import immediately.

  - name: migrate-model-config-with-minimal-reviewed-diffs
    description: >
      Convert v1 Config inner classes only where they still exist or fail. Replace
      extra equals Extra.allow with model_config containing extra set to allow. Replace
      allow_population_by_field_name with populate_by_name set to true. Keep existing
      aliases and examples. Prefer direct, reviewed edits over generated regex when a
      Config contains nested schema examples. After editing a class, read the changed
      region and confirm model_config is inside the intended model class at the same
      indentation level as fields and methods, all braces are balanced, and no invalid
      fragments such as dot allow remain.

  - name: rename-schema-extra-after-imports-are-clean
    description: >
      In Pydantic v2, schema_extra in model_config is renamed to json_schema_extra.
      Search the source tree for schema_extra and replace the model configuration key
      while preserving the value exactly. Do this only after syntax, import, Config
      instantiation, and const failures are resolved. In the learned fixture, the
      remaining occurrences were in openapi_schema_pydantic model_config dictionaries
      and were safely handled by replacing the literal key schema_extra with
      json_schema_extra after imports already worked. Immediately re-run grep for
      schema_extra and a targeted schema test after the replacement.

  - name: handle-openapi-version-literals
    description: >
      If a field annotation is a quoted string containing a Literal expression,
      Pydantic v2 may treat it as an unresolved forward reference. Replace stringified
      Literal annotations with real typing.Literal annotations and import Literal from
      typing. For the OpenAPI schema model, use a normal Literal union for supported
      openapi versions instead of a quoted annotation. Do not add model_rebuild in the
      same module merely to compensate for a stringified Literal.

  - name: preserve-real-forward-references
    description: >
      Distinguish stringified Literal annotations from real forward references between
      models. Stringified Literal annotations should become real Literal types, but
      references such as PathItem fields pointing to Operation may need to remain quoted
      or guarded under TYPE_CHECKING to avoid runtime import cycles. If an edit creates
      an ImportError about PathItem or another model from a partially initialized
      module, revert the direct runtime import that created the cycle and restore the
      quoted annotation. Then handle Pydantic resolution with model_rebuild after the
      package imports all related models.

  - name: rebuild-forward-referenced-models-after-imports
    description: >
      When validation fails because a model is not fully defined or a forward reference
      such as Operation is unresolved, call model_rebuild after all related models have
      been imported. A good location for mutually referring OpenAPI schema models is
      the package __init__.py after all from dot module imports. Do not add imports to
      path_item or operation solely to satisfy model_rebuild if those imports make a
      circular dependency. Rebuild the model that owns the string reference, then any
      aggregate model that depends on it, and finally the top-level model. In the
      learned fixture, rebuilding after all openapi_schema_pydantic imports fixed
      PathItem references to Operation and allowed OpenAPI validation tests to pass.

  - name: use-v2-method-names-when-tests-require
    description: >
      If tests or warnings expose v1 method usage, update BaseModel calls to v2 names.
      Common replacements are parse_obj to model_validate, dict to model_dump, json to
      model_dump_json, schema to model_json_schema, copy to model_copy, construct to
      model_construct, and update_forward_refs to model_rebuild. Keep compatibility
      wrappers only when the project deliberately supports both versions and tests
      require that behavior.

  - name: update-validators-carefully
    description: >
      If validator errors appear, migrate validators without weakening validation.
      Replace validator with field_validator and root_validator with model_validator
      where needed, adapting signatures to Pydantic v2. Do not delete checks, skip
      error branches, or return early merely to satisfy imports. Run the specific
      tests that cover the validator behavior.

  - name: run-targeted-tests-after-each-class-of-change
    description: >
      After each semantic fix, run the smallest failing test that demonstrated the
      problem. In the learned successful trace, a Config instantiation test confirmed
      the Optional default fix, then OpenAPI schema tests confirmed the Literal and
      model_rebuild fixes. If a targeted test newly fails during conftest import with a
      partially initialized module, treat that as a regression from the last edit and
      repair the circular import before proceeding. If a targeted test passes after
      schema_extra or forward reference work, still continue to the final audit and
      full suite rather than stopping on the partial success.

  - name: run-final-audit-before-full-suite
    description: >
      Before the full suite, run a compact audit for migration leftovers and accidental
      damage. Compile the edited package, grep for pydantic.v1, const equals, class
      Config, Extra dot, allow_population_by_field_name, schema_extra,
      update_forward_refs, imports of int or str from pydantic, and obvious malformed
      fragments such as dot allow. Also instantiate core configuration models that
      tests create with defaults, especially Config(). Read git diff for any large
      model rewrites and confirm that schema example dictionaries, aliases, Optional
      defaults, subclass fields, quoted forward references, and package import order
      were preserved.

  - name: run-the-suite-and-clean-up
    description: >
      Run the full repository test suite before finishing. If failures remain, return
      to the first new traceback rather than broadening the migration blindly. A run
      with hundreds of passing tests is still a failed migration if pytest reports any
      failure or error. Inspect git diff for accidental large rewrites, malformed
      model_config dictionaries, indentation errors, remaining const equals
      occurrences, imports of pydantic.v1, imports of int or str from pydantic,
      direct imports that create schema circular dependencies, missing Optional None
      defaults, and deleted behavior. The final state should pass tests using Pydantic
      v2 APIs directly.
```