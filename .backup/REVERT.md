# Reverting to the working fastapi-mail setup

Everything below is reversible. The original fixture, its snapshot state
and its whole 14-version skill lineage were never overwritten; the only
shared file that changed is the LIVE skill.

## The one thing that was overwritten

`skills/pydantic-v2-migration/SKILL.md` -- the live skill -- is shared by
every fixture. It was reset to v0 to start the openapi-python-client
lineage from empty. Its last fastapi-mail value (v13) is kept twice:

    .backup/SKILL-fastapi-mail-v13-LIVE.md
    skills/versions/v013-pydantic-v2-migration.md

To go back:

    cp skills/versions/v013-pydantic-v2-migration.md \
       skills/pydantic-v2-migration/SKILL.md

and run without `MSF_FIXTURE_DIR`. That is the whole revert.

## What was NOT touched

| thing | state |
|---|---|
| `fixture/` (fastapi-mail) | unmodified -- `git status` clean |
| `skills/versions/` (v0..v13) | intact, verified by mtime: v001 still 14:27 |
| `.snapshot_state.json` | still present, alongside the new per-fixture files |
| the default run command | unchanged; `MSF_FIXTURE_DIR` defaults to `fixture/` |

## Why the paths became per-fixture

`versions_dir()` and the snapshot state are now keyed on the active
fixture. Shared, two lineages collide destructively: a second fixture
starting at v0 writes `v001-...md` straight over the first fixture's v1,
and a saved `mode=snapshot` state hands back the other fixture's image,
so every attempt is graded against a package the agent never edited.
The default fixture keeps its original paths, so nothing already recorded
moved.

## One known cosmetic casualty

Run 14's summary reads `skill started v12 ... ended v0`. It actually
distilled v13. The live file was reset while that run was still doing its
after-clock work, so its closing `skills.current()` read the reset value.
The event log and `v013-...md` are correct; the summary line is not.
Operator error, not a code fault -- and the reason the per-fixture split
above exists.
