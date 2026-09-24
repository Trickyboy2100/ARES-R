# P3.8B0 Closure and P3.8B Planning Checkpoint

Date: 2026-09-24  
Branch: `feat/e2e-v0-integration-20260917`  
Scope: camera/AMR evidence and planning only; no arm or gripper command was sent.

## Result

- `AMR_COMPLETION_OBSERVER_READY = YES`
- `MANIPULATION_OBSERVATION_TRANSACTION_READY = YES`
- `RIGHT_PICK_TARGET_EPOCH_BOUND = YES`
- `RIGHT_PLACE_RIGHTMOST_PROFILE_READY = YES`
- `TARGET_CONTACT_POLICY_READY = YES`
- `ATTACHED_OBJECT_CUROBO_READY = YES`
- `LOCAL_TCP_SCENE_DELTA_READY = YES`
- `GRASP_VERIFICATION_V1_READY = YES`
- `READY_FOR_P3_8B_FULL_SCHEME_PLANNING = YES`
- `P3_8B_FULL_SCHEME_PLANNING_COMPLETE = NO`
- `READY_FOR_P3_8C_SUPERVISED_EXECUTION = NO`

## Live mapping and epochs

Epic UI command evidence confirms automatic profile switching. The commissioned profiles are:

- right pick: `320,2,1,1,1,0` (`space=2`, `object=1`, `camera=1`);
- rightmost placement: `320,2,3,1,1,0` (`space=2`, `object=3`, `camera=1`).

The latest pick target is in the requested BODY right-front region:

`[+0.691250, -0.187881, +0.988718] m`, where `+X=front` and `-Y=right`.

The latest atomic pick epoch is under:

`worklog/evidence/2026-09-24-p3-8b/pick_epoch_opening40_20260924T165823/`

The commissioned placement epoch is under:

`worklog/evidence/2026-09-24-p3-8b/place_epoch_20260924T155906/`

Both transactions bind the 5700 detection, Pixel Pro cloud, before/after dual-arm state,
SceneSnapshot ID/digest and point-cloud SHA. No joint change was observed during capture.

## AMR placement result

The base was translated left in bounded steps until the detected pick target moved from BODY
left-front to BODY right-front. The completion observer was corrected after the first live run:
an accepted AMR request or a short velocity pause can no longer be reported as settled. A move
now requires the expected displacement fraction or an explicit completion marker, followed by
five stable samples.

Further pure translation cannot solve the remaining grasp-end collision: target and dock move
together in BODY, so their relative geometry is unchanged.

## Pregrasp planning result

The original false block was traced to use of the full-opening gripper union while the task
commands 40 percent opening. A versioned mesh-derived 0..40-percent envelope is now selected;
unknown opening still fails closed to the full-opening union. The controller TCP remains a task
frame and is not added as physical collision material.

The correct pregrasp orientation semantics were also restored: the terminal IK pose is exact,
while the free-space cuRobo path may reorient. The subsequent contact Skill alone owns the
fixed-orientation straight corridor.

Successful real-scene, planning-only result:

- segment: `CURRENT -> PICK_PREGRASP_50MM`;
- artifact: `worklog/evidence/2026-09-24-p3-8b/planning/move_pregrasp_50mm_terminal_orientation_170938/`;
- cuRobo result: `SUCCESS`;
- start modeled clearance: `106.19 mm`;
- dense minimum modeled clearance: `2.94 mm`;
- central-plane TCP margin: `86.93 mm`;
- points: `441`;
- formal solve: `13.36 s` after initialization;
- independent CPU/URDF validation: collision-free.

## Remaining P3.8B blocker

At the exact Epic grasp pose the physical pinned gripper envelope overlaps a support-surface
primitive by about `17.2 mm` in the current sphere model. Removing the target object does not
remove this collision; the limiting object is the dock/support surface, not the grasp target.
Exact per-link mesh AABBs show that the collision is caused by the combination of a single
gripper-union abstraction and duplicated tool/scene inflation; with zero extra tool inflation,
the pinned component meshes do not overlap the already 7-mm-inflated scene support.

This must be resolved with a component-level gripper collision model used consistently by
cuRobo, dense validation and TargetContactPolicy. It must not be solved by deleting dock points,
moving the base again, allowing non-target contact, or silently weakening hard collision.

Until that model is in place, CONTACT_APPROACH, ATTACH, LIFT, transfer, place and retreat cannot
be packaged as a production planning-only Scheme, and P3.8C remains blocked.
