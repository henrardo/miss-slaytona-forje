---
name: pydantic-v2-migration
description: Procedure for migrating a Python codebase from Pydantic v1 to Pydantic v2 while preserving behavior and passing the repository test suite.
metadata:
  aip:
    spec: "https://arxiv.org/abs/2606.04781"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 6
    derived_from_traces:
      - "2061360d"
      - "8476334f"
      - "ffc6166c"
      - "3077ae6c"
      - "a658584b"
      - "b6b67d44"
      - "1d461637"
      - "4cd39e71"
      - "44870605"
      - "9bd89033"
      - "8ca6563d"
      - "b504db90"
      - "ff_attempt_1"
      - "ff_attempt_2"
---

```yaml
# Attempt 2 regressed at collection because an imported OpenAPI schema package
# still used Field const. The next attempt must search and migrate removed Field
# keyword arguments across the whole import graph, including packages imported by
# tests conftest, before treating a high passing count as near success.
# Earlier green traces remain useful: BaseSettings must move with its class base,
# UploadFile and BytesIO models need arbitrary_types_allowed, cross-field enum
# checks are often cleaner as after validators, and standalone email checks must
# use email_validator or TypeAdapter instead of EmailStr.model_validate.

purpose: >
  Migrate a Python project from Pydantic v1 APIs to real Pydantic v2 APIs,
  preserving validation behavior and running syntax, import, collection,
  focused behavioral, and full-suite checks until there are no collection
  failures, hidden syntax errors, or unexpected Pydantic v2 ValidationErrors.

trigger_when:
  - Asked to migrate a Python codebase from Pydantic v1 to Pydantic v2
  - The suite fails after installing Pydantic v2 because BaseSettings validator root_validator Config schema_extra const or EmailStr validation APIs changed
  - Imports fail with PydanticImportError PydanticUserError schema generation errors or config key warnings after a Pydantic upgrade
  - Pytest collection fails inside tests conftest or an imported schema package after edits to ConfigDict Field json_schema_extra validators or schema classes
  - Tests that used to construct Pydantic models with MagicMock sentinels arbitrary project objects UploadFile BytesIO paths or partial dictionaries now fail with ValidationError

do_not_use_when:
  - The requested solution is compatibility with both Pydantic v1 and v2 through the pydantic.v1 namespace
  - The codebase already uses Pydantic v2 APIs and the failing tests are unrelated to Pydantic
  - The task is only a dependency pin change without code migration

anti_patterns:
  - Do not import from pydantic.v1
  - Do not empty validators or function bodies just to make imports succeed
  - Do not stop after import checks because collection and behavioral tests can still fail
  - Do not stop after a high passing count if pytest collection or conftest import still fails
  - Do not stop after one focused test passes because another migrated behavior can still fail
  - Do not diagnose from a truncated pytest traceback or from the progress line alone
  - Do not ignore PluggyTeardownRaisedWarning when it wraps a conftest import SyntaxError ImportError PydanticUserError or ValidationError
  - Do not treat a pytest collection SyntaxError as a Pydantic behavior problem
  - Do not leave a partly edited Field ConfigDict Literal import or json_schema_extra dictionary uncompiled
  - Do not put json_schema_extra inside a Field call unless the original schema customization was field specific
  - Do not replace permissive storage fields with stricter BaseModel annotations when tests pass MagicMock or arbitrary helper objects
  - Do not replace EmailStr.validate with EmailStr.model_validate because EmailStr has no model_validate method in Pydantic v2
  - Do not catch and suppress email_validator exceptions when tests expect EmailNotValidError to propagate
  - Do not use a before model validator when the old root validator reasoned about parsed enum members or defaulted fields
  - Do not change tests or README examples to hide a migration regression unless the task explicitly asks for documentation updates

steps:
  - name: inventory-and-baseline
    description: >
      From the repository root, inspect dependency files and grep for Pydantic
      usage before editing. Run the suite or at least pytest collection with
      untruncated output to capture the first real failure. Record files using
      BaseSettings Config validator root_validator schema_extra json_encoders
      parse_obj dict json construct from_orm EmailStr.validate constrained types
      GenericModel Field extra keyword arguments arbitrary external classes or
      OpenAPI schema model customizations. Also inspect tests and fixtures that
      construct migrated models with MagicMock sentinel objects tmp paths
      UploadFile BytesIO or partial dictionaries, because those calls define
      behavior that must remain valid.

  - name: update-dependencies-for-v2
    description: >
      Change dependency metadata from Pydantic v1 to Pydantic v2. If the code
      uses BaseSettings, add pydantic-settings. If it uses EmailStr, keep or add
      email-validator. Do not pin back to Pydantic v1 and do not use pydantic.v1.
      Verify the installed versions with a short python or pip command before
      assuming the environment matches dependency files.

  - name: migrate-imports-with-small-edits
    description: >
      Update imports in the smallest coherent groups. Keep BaseModel EmailStr
      Field ConfigDict TypeAdapter field_validator model_validator Literal and
      other Pydantic v2 imports explicit. When moving BaseSettings to
      pydantic_settings, update the class base in the same edit so the module is
      never left importing BaseSettings under one name while inheriting from a
      different old alias. After each import edit, run a direct import command
      for that module before editing unrelated files.

  - name: migrate-basesettings
    description: >
      Replace BaseSettings imported from pydantic with BaseSettings from
      pydantic_settings. Import SettingsConfigDict when settings configuration
      is needed. Convert inner Config on settings classes to model_config using
      SettingsConfigDict, preserving env_file env_prefix case_sensitive extra
      and similar settings. Keep the class inheriting from BaseSettings after
      changing imports. If the old code used an alias such as Settings, either
      preserve the alias consistently or remove it consistently in both import
      and class definition.

  - name: migrate-model-config
    description: >
      Convert inner Config classes on BaseModel subclasses to model_config
      dictionaries or ConfigDict. Preserve arbitrary_types_allowed when models
      contain non-Pydantic types such as UploadFile BytesIO Path file handles
      framework classes project Config objects or test doubles. Rename
      schema_extra to json_schema_extra and allow_population_by_field_name to
      populate_by_name. Preserve extra allow forbid ignore validate_assignment
      frozen use_enum_values from_attributes aliases and default factories when
      present. For simple models with UploadFile or BytesIO fields, adding
      model_config with arbitrary_types_allowed is often required just for
      import and schema generation to succeed.

  - name: migrate-removed-field-keywords
    description: >
      Search the entire repository and any in-repo packages imported by tests
      conftest for Field calls using removed or renamed Pydantic v1 keyword
      arguments. In particular, replace const with a Literal annotation and a
      normal default, such as annotating a field as Literal of the fixed string
      instead of Field with const true. Import Literal from typing when needed.
      Replace regex with pattern, min_items with min_length, max_items with
      max_length, allow_mutation with frozen when equivalent, and move arbitrary
      extra schema keys into json_schema_extra. After this sweep, run pytest
      collection again because conftest can import schema modules that normal
      focused tests did not touch.

  - name: preserve-permissive-object-fields
    description: >
      When a Pydantic model is used as a lightweight container for already built
      objects, preserve that permissiveness under v2. If tests pass MagicMock or
      arbitrary objects for a field such as Project.openapi, do not require a
      nested BaseModel instance unless the old code actually validated it that
      way. Inspect how the field is used. If code only reads attributes or passes
      the object through, keep or change the annotation to Any or an appropriate
      loose protocol and enable arbitrary_types_allowed as needed. If the field
      truly should parse dictionaries into a nested model, add a validator that
      accepts existing instances and only parses mappings. After the change,
      rerun the exact fixture or constructor that failed before running the full
      suite.

  - name: migrate-schema-extra-with-syntax-guard
    description: >
      When migrating schema_extra or OpenAPI schema models, write a complete and
      balanced ConfigDict expression in one edit. A safe pattern is model_config
      equals ConfigDict with extra or populate settings and json_schema_extra as
      a nested dictionary, then close both the dictionary and the ConfigDict
      call. Immediately open the edited file around the changed block and run
      py_compile or compileall before touching another file. If pytest reports
      an unmatched parenthesis or brace in a schema file such as oauth_flow.py
      response.py security_scheme.py components.py parameter.py or header.py,
      fix that syntax first and rerun compile before changing validation logic.

  - name: migrate-field-validators
    description: >
      Replace validator with field_validator. Add classmethod for field
      validators. Keep the original validator logic rather than returning the
      input unconditionally. For validators that used pre always each_item or
      values, read the local code and Pydantic v2 signature rules before
      translating. Use ValidationInfo only when the validator truly needs other
      values or config. If an identical method name appears in multiple classes
      in the same file, edit each occurrence deliberately with enough context
      instead of relying on a replace that may hit the wrong class. Run a
      focused construction example for each migrated model.

  - name: migrate-cross-field-validators
    description: >
      Replace root_validator with model_validator. Use mode before only when the
      old logic truly needs the raw input dictionary. Use mode after when the old
      logic reasoned about parsed field values, enum members, defaults, or
      normalized attachments. In after mode, validate or mutate self and return
      self. When comparing enum fields, accept both enum members and their values
      if tests or callers pass either form. For message models with alternative
      multipart bodies, construct the same examples as the tests to ensure the
      validator rejects missing alternative_body and accepts valid enum inputs.

  - name: migrate-email-validation
    description: >
      Keep EmailStr as a type annotation for model fields. For standalone email
      validation functions, do not call EmailStr.validate or
      EmailStr.model_validate. Prefer TypeAdapter of EmailStr with
      validate_python when Pydantic ValidationError behavior is expected. Prefer
      email_validator validate_email when existing tests expect
      EmailNotValidError or subclasses such as EmailSyntaxError. Let expected
      exceptions propagate instead of catching all exceptions and returning
      False. If valid emails should return a boolean, call validate_email and
      then return True only after it succeeds.

  - name: migrate-constrained-types-carefully
    description: >
      Constrained helpers may still import but many projects are cleaner with
      Annotated plus Field constraints. For conint ge le, use Annotated int
      Field ge le. For constr min_length regex, use Annotated str Field
      min_length pattern. Preserve defaults and optionality exactly. After
      changing annotations, instantiate at least one model exercising valid and
      invalid boundary values.

  - name: migrate-renamed-model-methods
    description: >
      Replace parse_obj with model_validate, dict with model_dump, json with
      model_dump_json, construct with model_construct, copy with model_copy, and
      from_orm with model_validate plus from_attributes configuration when that
      code path is present. Only change call sites that exist in the repository.
      If test assertions depend on serialization aliases excluded none values
      enum values or JSON text formatting, pass the equivalent keyword arguments
      to the new method.

  - name: handle-openapi-schema-packages
    description: >
      For packages that model OpenAPI documents, inspect modules imported during
      tests or conftest before making broad replacements. Components Parameter
      Header Response RequestBody Schema OAuthFlow OAuthFlows SecurityScheme
      Project Config and similar files often contain schema_extra examples extra
      allow config permissive containers const discriminator fields and
      arbitrary helper objects. Migrate one schema module at a time, compile it,
      then import the package schema namespace and construct the models used by
      tests. A collection failure in tests conftest means package imports are
      broken and must be repaired before any test-specific diagnosis is useful.

  - name: investigate-validationerror-fully
    description: >
      If Pydantic v2 raises ValidationError after imports and collection work,
      rerun the focused failing test without piping through head and read every
      error location type input type and message. Open the model class and the
      test fixture together. Decide whether v2 is correctly enforcing an old
      constraint or whether the migration accidentally tightened behavior. For
      accidental tightening, restore the old API by adjusting annotations
      defaults ConfigDict or validators, not by changing tests and not by
      suppressing all validation. Reproduce the failing constructor in a short
      python command before rerunning the broader tests.

  - name: run-fast-verification-after-each-edit-group
    description: >
      After each file or small group of edits, run python -m py_compile on every
      changed file or python -m compileall on the changed package. Then run a
      small import command for the package and the specific migrated models, and
      construct at least one instance used by tests. For email checker changes,
      run one valid address and one invalid address in the same style as the
      tests and confirm invalid input raises the expected exception class. This
      catches regressions like unclosed ConfigDict parentheses malformed
      json_schema_extra blocks broken imports missing arbitrary_types_allowed
      remaining Field const usages and Project ValidationError failures before
      the full pytest run.

  - name: run-tests-and-follow-the-first-real-failure
    description: >
      Run the repository suite without truncating the final failure details. If
      the output includes a PluggyTeardownRaisedWarning or ConftestImportFailure,
      scroll to the nested SyntaxError ImportError PydanticUserError or
      ValidationError and fix that first. If collection fails with a removed
      Pydantic keyword message, grep for that keyword across the repository and
      migrate every imported occurrence before rerunning collection. If
      collection fails with SyntaxError, open the reported file and line and fix
      syntax before interpreting any passing test count. If import fails, fix the
      migrated API import or model configuration. If behavioral tests fail,
      inspect the test and preserve the old behavior under Pydantic v2 rather
      than weakening validation. Rerun the focused failing test after a fix, then
      rerun the full suite before finishing.

  - name: final-check
    description: >
      Before finishing, grep for pydantic.v1, BaseSettings imported from
      pydantic, validator, root_validator, EmailStr.validate,
      EmailStr.model_validate, class Config, Field const, Field regex,
      min_items and max_items in migrated model files and packages imported by
      tests conftest. Any remaining occurrence needs a deliberate reason. Run
      compileall, pytest collection, focused tests for previously failing
      constructors or email validators, and the full test suite. Report
      completion only when the full suite passes and there is no collection
      SyntaxError PydanticUserError or ValidationError hidden behind a warning.
```