# P3.9C — Symmetry-aware full-chain manipulation branch planning

Date: 2026-09-29
Status: owner steering decision

## 0. Why this exists

P3.9B has shown that local greedy planning can fail even when the workspace geometry is visually and collision-wise feasible.

The current blocker is not simply obstacle avoidance:

- current→center can produce collision-free candidates but fail the horizontal-orientation requirement;
- center→preplace is geometrically plausible;
- the two-finger gripper admits a 180-degree symmetric grasp orientation;
- choosing the grasp orientation locally can place the wrist on a poor joint/orientation branch for later center/preplace motion.

Therefore the manipulation task must choose the grasp/orientation branch using the whole downstream arm chain, not one stage at a time.

## 1. Important semantic correction: center is a Cartesian task target

`center` is NOT a historical fixed joint posture.

It means a BODY-frame TCP target/region near the robot chest used for safe base transfer.

The planner may choose any valid joint solution that:

- reaches the center TCP position;
- satisfies the required level/horizontal tool semantics;
- preserves the selected grasp symmetry branch;
- is collision-free;
- has acceptable singularity/joint margins;
- connects well to the previous and next task stages.

Historical center joints may be used only as seeds/priors.

## 2. Two-finger grasp symmetry

Represent the grasp as two equivalent discrete orientation branches:

`grasp_symmetry_id ∈ {0, PI_FLIP}`

where `PI_FLIP` is a 180-degree rotation about the verified gripper/grasp symmetry axis.

The exact axis must come from the current grasp/tool convention; do not assume an arbitrary RPY roll without checking.

Both branches must produce the same physical finger grasp semantics.

Once a branch is selected for a pick→transfer→place chain, keep it consistent through:

- pregrasp;
- grasp;
- lift;
- center;
- rear-preplace;
- preplace.

Do not switch 0↔PI mid-chain by an unplanned wrist flip.

## 3. Global-chain planning does NOT mean one monolithic trajectory across base motion

The base move changes the BODY/world relation and invalidates the scene.

Therefore:

- choose the global discrete grasp/orientation branch and semantic Cartesian goals across the whole task;
- plan each physical arm segment with cuRobo in the correct fresh scene/revision;
- rebind after base motion;
- preserve the chosen symmetry branch across the replan.

This is task-level branch optimization + segment-level cuRobo, not a single stale trajectory spanning base motion.

## 4. Chain to optimize

Candidate chain:

1. pregrasp;
2. grasp;
3. initial lift;
4. center Cartesian target;
5. base transfer;
6. rear-preplace target = preplace shifted BODY X- by 0.15 m;
7. preplace;
8. later placement descent/release.

For the current commissioning stop, optimize through step 7 and HOLD at preplace.

## 5. Candidate generation

For each grasp symmetry branch:

- generate multiple IK solutions at pregrasp/grasp/lift;
- generate multiple valid center IK solutions from the center Cartesian target;
- center yaw may be free within the horizontal/level constraint;
- generate multiple rear-preplace and preplace IK solutions under the same symmetry branch;
- reject joint-limit/singularity/collision-invalid candidates.

Do not bind center to one historical joint vector.

## 6. Whole-chain score

Score a candidate branch/IK chain using at least:

- total joint-space path length;
- maximum inter-stage joint change;
- minimum singularity margin / Jacobian condition metric;
- joint-limit margin;
- task-orientation error;
- expected cuRobo segment feasibility;
- collision clearance;
- optional predicted motion time.

Prefer the lowest-cost chain whose required cuRobo segments all validate.

Do not choose a branch from IK cost alone if cuRobo cannot realize the segment.

## 7. cuRobo execution rule

All non-contact point-to-point arm motions remain scene-aware cuRobo:

- current→pregrasp;
- lift→center;
- center→rear-preplace;
- rear-preplace→preplace if the task keeps it as a free-space segment.

Contact approach/place descent retain their contact semantics.

No direct MoveJ fallback.

## 8. Orientation hard constraint

`LEVEL_YAW_FREE` for carried-object transfer means:

- tool/grasp remains level/horizontal;
- yaw can be optimized;
- selected symmetry branch is preserved;
- intermediate trajectory orientation must satisfy the hard tolerance, not only the endpoint.

A path that is collision-free but flips/tilts 50–90 degrees is invalid.

Implement the hard check as part of the planner contract and independent trajectory validation.

## 9. TaskRuntime/Skill integration

This logic must become an offline planning Skill/service, not Codex hand-steering.

Recommended Skill:

`manipulation.plan_transfer_chain`

Inputs:

- pick observation;
- place semantic target/profile;
- center Cartesian target;
- rear-preplace offset;
- symmetry set;
- orientation policy;
- attached-object geometry policy;
- planner profile.

Outputs:

- selected symmetry branch;
- selected semantic poses / IK branch IDs;
- segment plans or prepare templates;
- branch score;
- required scene rebind points;
- invalidation rules.

Scheme then consumes the output automatically.

## 10. Current physical state assumption

The user reports the object has been returned to the original pickup start and is not currently held.

Do not reuse old attached-object state, old center scene, or old preplace scene.

Fresh observation and robot state are required before any new execution.

## 11. First acceptance

Before hardware motion, produce planning-only evidence for BOTH grasp branches:

- full kinematic chain;
- selected center IK solution;
- rear-preplace/preplace IK;
- singularity metrics;
- joint continuity metrics;
- scene-aware cuRobo feasibility for the current pick side;
- fresh place-side feasibility after base alignment or a clearly marked predicted/template check.

Required flags:

`SYMMETRIC_GRASP_BRANCHES_EVALUATED = YES`
`CENTER_CARTESIAN_MULTI_IK_READY = YES`
`WHOLE_CHAIN_BRANCH_SELECTED = YES`
`SELECTED_BRANCH_PREGRASP_CUROBO_PASS = YES`
`SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS = YES`
`SELECTED_BRANCH_CENTER_TO_REAR_PREPLACE_TEMPLATE_READY = YES`
`HARD_LEVEL_ORIENTATION_VALIDATOR_PASS = YES`

Only after these pass should the next supervised run begin.