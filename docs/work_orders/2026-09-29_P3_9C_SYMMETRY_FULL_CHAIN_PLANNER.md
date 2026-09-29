# P3.9C — Implement symmetry-aware full-chain planner and automatic Scheme integration

Date: 2026-09-29
Mode: IMPLEMENTATION + PLANNING-ONLY FIRST

Read first:

- `docs/decisions/2026-09-29_P39C_SYMMETRY_AWARE_FULL_CHAIN_PLANNING.md`
- `docs/decisions/2026-09-29_P39B_MOTION_BASEALIGN_UI_POLICY.md`
- current local P3.9B work and diagnostics on `.32`.

## 0. Preserve current local P3.9B work

Do not throw away the useful P3.9B fixes already made locally:

- auto-align logic;
- center/preplace diagnostics;
- pointcloud attached-object de-dup;
- 55 mm pregrasp continuity fix;
- place detection recovery;
- diagnostic rendering;
- current WebUI/autostart work.

Record local HEAD/status and isolate incomplete experimental files before the new planner refactor.

## 1. Stop local greedy orientation decisions

Do not continue trying to solve current→center or center→preplace independently with a fixed historical orientation branch.

Implement one branch-selection layer that evaluates both 180-degree equivalent gripper orientations over the entire semantic manipulation chain.

## 2. Implement `GraspSymmetry`

Add a small typed representation:

`NORMAL` and `FLIPPED_180`.

Define the flip transform around the verified physical gripper symmetry axis.

Add tests proving the two transforms preserve the intended two-finger grasp semantics.

## 3. Make center a Cartesian goal

Refactor any center logic that consumes a single joint vector.

Center input must be:

- BODY TCP position;
- level/horizontal orientation policy;
- yaw-free or sampled yaw;
- selected grasp symmetry branch.

Historical center joints are seeds only.

Expose center in WebUI/ART as a semantic Cartesian task target, not a fixed pose execution branch.

## 4. Whole-chain candidate graph

Build a graph/lattice for each symmetry branch:

- pregrasp IK candidates;
- grasp IK candidates;
- lift candidate;
- center IK candidates;
- rear-preplace IK candidates;
- preplace IK candidates.

Maintain candidate IDs and lineage.

Edges carry:

- joint delta;
- singularity cost;
- joint-limit cost;
- orientation validity;
- later cuRobo feasibility state.

Use dynamic-programming/shortest-path style selection rather than one greedy IK at each node.

## 5. Full-chain scoring

At minimum compute:

- total joint L2/L1 travel;
- max stage joint delta;
- min singularity margin / max condition number;
- min joint-limit margin;
- branch orientation continuity;
- optional estimated duration.

Use the existing audit script result only as a seed; rerun from fresh robot/pick/place inputs.

## 6. cuRobo feasibility integration

After kinematic pruning, validate the best few chains with real cuRobo segments.

Required pick-side segment checks:

- current→pregrasp;
- post-lift→center.

Required place-side checks after fresh place scene/base alignment:

- center→rear-preplace;
- rear-preplace→preplace.

All use SceneAwareMotionService/curobo and current collision policy.

Do not direct MoveJ.

## 7. Hard horizontal orientation validation

Create/reuse an independent validator that samples the entire carried-object trajectory and verifies the horizontal/level manifold.

Reject any trajectory with large intermediate tilt even if cuRobo reports success.

The validator must report:

- max level error deg;
- where it occurs;
- symmetry branch;
- minimum world clearance;
- singularity metric along path if available.

## 8. Scene/base lifecycle

Global branch selection may persist across base move.

Exact trajectory may NOT persist across base move.

After place-base movement:

- invalidate old scene;
- fresh place observation;
- keep selected `grasp_symmetry_id`;
- regenerate/validate center→rear-preplace→preplace in the new scene.

If selected branch fails in the new scene, the runtime may re-evaluate the alternate symmetry only before grasp. Once the object is grasped, no unplanned 180-degree wrist flip is allowed.

## 9. Add Skill/TaskRuntime integration

Implement a reusable Skill/service:

`manipulation.plan_transfer_chain`.

Add it to SkillRegistry and Task Studio.

The Tray→Groove Scheme should call it during preparation and then bind its selected branch into downstream manipulation Skills.

Required outputs:

- `grasp_symmetry_id`;
- selected semantic target rotations;
- center candidate/IK ID;
- branch score;
- expected segment starts/goals;
- scene rebind boundaries;
- planner/collision revisions.

## 10. WebUI presentation

Task Studio/Run Monitor should show:

- selected grasp branch: NORMAL / FLIPPED_180;
- chain score;
- candidate comparison;
- center selected TCP orientation/yaw;
- segment feasibility;
- current fresh scene binding.

Do not expose low-level joint arrays as the primary user interface.

## 11. Planning-only acceptance first

Use current site state: object back at pickup start, no attachment.

Run fresh pick observation.

Evaluate NORMAL and FLIPPED_180.

Produce one comparison report/diagnostic plot showing:

- whole-chain candidate geometry;
- joint-space continuity;
- singularity margin;
- cuRobo segment results;
- selected branch.

Do not move hardware until the work-order acceptance flags are all YES.

## 12. Acceptance flags

Report:

`SYMMETRIC_GRASP_BRANCHES_EVALUATED = YES/NO`
`CENTER_IS_CARTESIAN_NOT_FIXED_JOINT = YES/NO`
`WHOLE_CHAIN_GRAPH_READY = YES/NO`
`WHOLE_CHAIN_BRANCH_SELECTED = YES/NO`
`SELECTED_BRANCH_PREGRASP_CUROBO_PASS = YES/NO`
`SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS = YES/NO`
`SELECTED_BRANCH_REAR_PREPLACE_PLAN_READY = YES/NO`
`SELECTED_BRANCH_PREPLACE_PLAN_READY = YES/NO`
`HARD_LEVEL_ORIENTATION_VALIDATOR_PASS = YES/NO`
`TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY = YES/NO`

## 13. Next physical run

After planning-only acceptance, the next physical demo must no longer rely on Codex choosing local recovery waypoints.

The Scheme/Skill runtime chooses the branch and executes the predetermined state machine.

Physical stop point remains HOLD_ABOVE_PLACE unless separately extended to descend/release.

## 14. Git

Small commits.
No force-push.
Keep golden first-pick fallback unchanged.
Preserve coworker dirty files.
Push only after tests + planning-only acceptance.