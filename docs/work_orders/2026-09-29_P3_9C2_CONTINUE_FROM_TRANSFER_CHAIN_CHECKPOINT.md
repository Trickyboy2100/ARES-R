# P3.9C2 — Continue from local transfer-chain checkpoint to autonomous preplace demo

Date: 2026-09-29
Status: steering continuation order

## 0. Resume point

Do NOT reset or revert the current `.32` local work.

Expected local checkpoint supplied by the field run:

`7120c3f3aad17330d0af6ada1e39c60bc58fe7fb`

First verify that this commit is still the local HEAD (or an ancestor of the current local HEAD), inspect its diff, preserve unrelated dirty/untracked coworker files, run the full tests, and normally fast-forward push this checkpoint if remote history is compatible.

Do not mix unrelated files into that push.

## 1. Fixed station contract for the current Tray→Groove demo

The current physical base pose is the PLACE station.

For this demo the pickup/place stations are not a search problem:

```text
PLACE_STATION = current physical base pose
PICK_STATION  = PLACE_STATION translated BODY +Y by 0.40 m
return PLACE  = from PICK_STATION translated BODY -Y by 0.40 m
yaw           = 0 deg
```

Use the existing `config/manipulation_stations.json` created in the local checkpoint.

Base motion always invalidates the scene. After truthful `BaseMotionObserver SETTLED`, acquire a fresh atomic observation/scene before planning arm motion.

`navigate.align_for_manipulation` remains a generic future Skill, but the current demo must use the explicit station contract above unless the user later changes the station definition.

## 2. Preserve the P3.9C planning correction

`center` is a BODY Cartesian TCP target, not a fixed historical joint vector.

Historical center joints may only seed IK.

Evaluate the two equivalent two-finger grasp branches:

- `NORMAL`
- `FLIPPED_180`

over the semantic chain:

`pregrasp → grasp → lift → center → rear-preplace → preplace`

Choose the branch from whole-chain feasibility/cost, not from pick-only IK cost.

Once selected, keep the same symmetry branch through the task. Do not perform an unplanned 180-degree wrist flip after grasp.

## 3. Place-side semantic geometry

Use:

`rear_preplace = preplace shifted BODY X -0.15 m`

Then:

`center → rear_preplace → preplace`

Both are non-contact free-space motions and must use SceneAwareMotionService + cuRobo with the attached-object geometry and fresh PLACE scene.

Do not reintroduce the deleted single-joint cumulative-change limit.

Do not split a trajectory merely to evade an artificial joint-delta gate.

## 4. Required atomic Skill

Finish and use the runtime Skill:

`manipulation.plan_transfer_chain`

It must own the NORMAL/FLIPPED branch choice and return an immutable artifact such as `transfer_chain_selection.json`.

Required output fields:

- selected `grasp_symmetry_id`;
- branch scores for NORMAL and FLIPPED_180;
- selected pregrasp/grasp/lift orientation branch;
- selected center IK/yaw candidate;
- rear-preplace/preplace semantic goals;
- joint continuity metrics;
- singularity / joint-limit metrics;
- cuRobo validation state for each required segment;
- hard level-orientation validation result;
- scene rebind boundary at base movement;
- planner/collision/profile revisions.

Prototype scripts may remain diagnostics, but the commissioned Scheme must consume the Skill output rather than depend on one-off Codex logic.

## 5. Planning/execution lifecycle for this demo

Planning/execution order:

```text
PLACE_STATION (start)
→ base +Y 0.40 m
→ PICK_STATION SETTLED
→ fresh pick ObservationEpoch
→ plan_transfer_chain: evaluate NORMAL/FLIPPED
→ select branch
→ cuRobo current→pregrasp
→ contact grasp
→ initial lift
→ attach
→ cuRobo lift→center using selected branch
→ base -Y 0.40 m
→ PLACE_STATION SETTLED
→ fresh right_place_rightmost ObservationEpoch
→ rebind same symmetry branch in fresh scene
→ cuRobo center→rear_preplace
→ cuRobo rear_preplace→preplace
→ HOLD_ABOVE_PLACE
```

Do not descend or release in this commissioning run.

## 6. Hard horizontal orientation requirement

For carried-object free-space transfer:

- keep the tool/grasp level/horizontal along the full trajectory;
- yaw may be optimized;
- selected symmetry branch remains fixed;
- reject any trajectory with large intermediate tilt even if collision-free.

The hard orientation validator must be part of the Skill result and pre-execution gate.

Do not rely on a soft cuRobo orientation cost alone.

## 7. Candidate search policy

Do not brute-force many candidates with long one-shot planner processes.

Use:

1. multi-IK / graph pruning first;
2. keep only a small number of best full-chain candidates per symmetry branch;
3. persistent cuRobo `FAST → FALLBACK` on those candidates;
4. independent dense collision + orientation validation.

Bound the search and record why a branch failed.

## 8. Required planning-only gate before hardware

All must be YES:

```text
STATION_CONTRACT_BOUND = YES
SYMMETRIC_GRASP_BRANCHES_EVALUATED = YES
CENTER_IS_CARTESIAN_NOT_FIXED_JOINT = YES
WHOLE_CHAIN_BRANCH_SELECTED = YES
SELECTED_BRANCH_PREGRASP_CUROBO_PASS = YES
SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS = YES
PLACE_SCENE_REBIND_POLICY_READY = YES
SELECTED_BRANCH_CENTER_TO_REAR_PREPLACE_READY = YES
SELECTED_BRANCH_REAR_PREPLACE_TO_PREPLACE_READY = YES
HARD_LEVEL_ORIENTATION_VALIDATOR_PASS = YES
TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY = YES
NEW_DEMO_REPLAY_PASS = YES
```

If a place-side cuRobo result cannot be evaluated before base motion because a fresh PLACE scene is required, the runtime may prepare the semantic branch/template only; the exact place trajectory is generated after the real base return and fresh place scene.

## 9. Physical run gate

After all planning-only flags pass, ask one fresh authorization because the site state has changed since the previous supervised run (object was manually returned and old attached/scene state is invalid).

Use:

`USER ACTION — 批准P3.9C全链分支自动取料并执行到放置上方`

After approval, TaskRuntime must execute the predefined Scheme autonomously. Codex must not invent recovery waypoints mid-run.

Stop on:

- base settle failure;
- fresh observation failure;
- selected branch becoming invalid;
- cuRobo or hard orientation validation failure;
- grasp verification failure;
- controller/device fault;
- explicit Stop.

## 10. Report

Create/update:

`docs/reports/2026-09-29_P3_9C_TRANSFER_CHAIN_AUTONOMOUS_DEMO_REPORT.md`

Include:

- local/pushed checkpoint SHA;
- station contract used;
- NORMAL vs FLIPPED metrics;
- selected symmetry;
- center Cartesian solution;
- pick-side cuRobo results;
- place-side fresh-scene cuRobo results;
- orientation max error;
- base movement evidence;
- final `HOLD_ABOVE_PLACE`;
- total cycle timing;
- whether any Codex/manual waypoint intervention occurred (must be NO for acceptance).

## 11. Acceptance

Final demo acceptance:

```text
AUTONOMOUS_SCHEME_NO_CODEX_WAYPOINT_ASSIST = YES
PLACE_TO_PICK_BASE_MOVE = PASS
PICK_TO_PLACE_BASE_MOVE = PASS
WHOLE_CHAIN_BRANCH_SELECTION = PASS
PICK_GRASP_LIFT = PASS
LIFT_TO_CENTER_CUROBO = PASS
CENTER_TO_REAR_PREPLACE_CUROBO = PASS
REAR_PREPLACE_TO_PREPLACE_CUROBO = PASS
HOLD_ABOVE_PLACE = YES
```