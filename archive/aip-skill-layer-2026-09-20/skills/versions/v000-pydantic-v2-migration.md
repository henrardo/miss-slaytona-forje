---
name: pydantic-v2-migration
description: Procedure this agent has distilled for migrating a Python codebase from Pydantic v1 to Pydantic v2. Version 0 is an empty scaffold containing no migration knowledge; every procedural step is written by the agent itself from its own graded attempts. Use when asked to migrate a codebase to Pydantic v2.
metadata:
  aip:
    spec: "https://github.com/zach-blumenfeld/aip/tree/v0.3a3"
    schemaId: "https://raw.githubusercontent.com/zach-blumenfeld/aip/v0.3a3/assets/aip-schemas/procedure.schema.json"
    version: 0
    derived_from_traces: []
---

```yaml
# VERSION 0 IS DELIBERATELY EMPTY OF TASK KNOWLEDGE.
#
# The experiment measures whether a warm agent improves by distilling its
# own graded attempts. Seeding this file with the migration answer, or with
# anything from the cold arm, would measure the author instead. What
# follows states only the shape of the job and how success is judged --
# both of which the agent is told in its task prompt anyway. Every
# procedural step from v1 onward comes from the agent's own distillation.
purpose: >
  Migrate a Python codebase from Pydantic v1 to Pydantic v2 so that the
  repository's own test suite passes, without shimming pydantic.v1 and
  without deleting behaviour to make tests green.

trigger_when:
  - Asked to migrate a codebase from Pydantic v1 to Pydantic v2
  - A test suite fails with pydantic import or validator errors after a
    Pydantic v2 upgrade

do_not_use_when:
  - The codebase is already on Pydantic v2 and its suite passes
  - The task is to upgrade a dependency other than Pydantic

anti_patterns:
  - Rewriting imports to pydantic.v1 so the old API keeps working. This
    passes 32 of 33 tests in this fixture and is not a migration.
  - Replacing a validator body with a bare return so the function still
    imports. The suite goes green and the behaviour is gone.
  - Declaring the migration complete without running the suite.

steps:
  - name: establish-the-failure
    description: >
      Run the repository own test suite and read the first error. No step of
      this procedure has been distilled yet, so work from the traceback and
      the codebase rather than from this file.
    outputs:
      - {name: first-error, type: string}
```
