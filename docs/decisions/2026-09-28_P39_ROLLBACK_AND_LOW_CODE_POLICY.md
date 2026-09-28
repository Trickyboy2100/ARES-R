# P3.9 Compatibility and Low-Code Policy

Date: 2026-09-28
Status: hard implementation constraint

## 1. Known-good baseline

Known-good integration baseline:

`1b548882065dbec5a524c141cbf7141af7f1d9cc`

Commissioned first-pick demo:

- `demos/right_arm_epic_pick_lift_v1/demo.json`
- `scripts/run_first_pick_demo.py`

P3.9 must preserve this path as a working fallback.

## 2. Additive implementation only

The new Skill/Task runtime is a separate selectable path.

Legacy DemoRegistry and the first-pick demo remain available.

Do not migrate the commissioned demo into the new runtime in P3.9.

New config is additive and disabled by default until acceptance.

Recommended selector:

`task_runtime.enabled = false`

New runtime state must use separate paths and must not overwrite legacy demo runtime state or evidence.

## 3. Rollback requirements

Before P3.9 may merge to integration, all must be true:

- legacy demo definition unchanged;
- legacy first-pick entrypoint unchanged;
- frozen first-pick replay passes;
- full legacy tests pass;
- disabling the new runtime restores the legacy-only behavior;
- no old config key is removed or renamed;
- current speed/contact/TCP/calibration/AMR/gripper settings are unchanged.

Known-good Git rollback anchor remains the baseline SHA above.

No force-push or destructive data migration.

## 4. ART low-code commands

Minimum structured commands:

- `skill list`
- `skill show SKILL_ID`
- `scheme list`
- `scheme show SCHEME_ID`
- `scheme clone SOURCE NEW_ID`
- `scheme validate SCHEME_ID`
- `scheme save-draft SCHEME_ID`
- `task list`
- `task show TASK_ID`
- `task prepare TASK_ID`
- `task preview TASK_ID`
- `task status [RUN_ID]`
- `task stop [RUN_ID]`

Physical task execution remains locked until the supervised full-cycle gate is explicitly enabled.

## 5. WebUI Task Studio

P3.9 WebUI must provide an actual low-code Task Studio.

### Skill Palette

Show SkillRegistry entries with category, maturity, required resources and parameter schema.

### Scheme Builder

Allow the user to:

- create or clone a Scheme;
- add/remove Skill nodes;
- reorder nodes;
- edit execution dependencies;
- edit prepare-ahead dependencies;
- bind earlier outputs to later inputs;
- choose recovery behavior;
- set stage timeout;
- inspect resource locks.

A clear form/list editor is sufficient; drag-and-drop is optional.

### Parameter Inspector

Generate forms from Skill parameter schemas.

Normal user inputs are resource IDs, station IDs, semantic targets, named policies and typed SI quantities.

### Validation and preview

Buttons:

- Validate
- Preview DAG
- Save Draft
- Compile / Prepare
- Replay

Validation shows missing parameters, type/resource mismatch, dependency cycles, output-binding errors, unavailable providers and lock conflicts.

### Run Monitor

Show task run ID, current Skill, next stage PREPARING/PREPARED, scene epoch, planner mode, gripper/force state, cycle timer, event stream and Stop.

The UI is a client; it does not own task progression.

## 6. Versioned low-code lifecycle

Low-code editing produces declarative data, not Python code.

Lifecycle:

`DRAFT -> VALIDATED -> REPLAY_VERIFIED -> READY_FOR_SUPERVISED -> COMMISSIONED`

Draft editing must never mutate a commissioned Scheme in place.

Suggested paths:

- `schemes/drafts/`
- `schemes/commissioned/`

## 7. Acceptance scenario

Without editing Python:

1. clone Tray-to-Groove;
2. change a task parameter;
3. insert or reorder an observation/verification node;
4. validate the DAG;
5. save a new draft;
6. replay/preview against frozen evidence;
7. confirm the original Scheme and commissioned first-pick demo are unchanged.

Acceptance flags:

- `LEGACY_DEMO_UNCHANGED = YES`
- `ROLLBACK_PATH_READY = YES`
- `ART_LOW_CODE_READY = YES`
- `WEBUI_TASK_STUDIO_READY = YES`
- `SCHEME_DRAFT_VERSIONING_READY = YES`
- `ORIGINAL_SCHEME_UNCHANGED = YES`