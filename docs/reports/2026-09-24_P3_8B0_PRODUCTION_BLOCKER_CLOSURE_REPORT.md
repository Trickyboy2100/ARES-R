# P3.8B0 Production Blocker Closure Checkpoint

Date: 2026-09-24  
Branch: `feat/e2e-v0-integration-20260917`  
Scope: implementation and planning-only evidence; no arm or gripper motion.

## Result

```text
AMR_COMPLETION_OBSERVER_READY = YES
BASE_SETTLED_NOT_EMITTED_ON_ACCEPT_ONLY = YES
MANIPULATION_OBSERVATION_TRANSACTION_READY = YES
RIGHT_PICK_TARGET_EPOCH_BOUND = YES
RIGHT_PLACE_RIGHTMOST_PROFILE_READY = NO
TARGET_CONTACT_POLICY_READY = YES
PREGRASP_TO_GRASP_PLANNING_READY = YES
PREPLACE_TO_PLACE_PLANNING_READY = YES
ATTACHED_OBJECT_GEOMETRY_READY = YES
ATTACHED_OBJECT_CUROBO_READY = YES
ATTACHED_OBJECT_SAFETY_VALIDATION_READY = YES
LOCAL_TCP_SCENE_DELTA_READY = YES
GRASP_VERIFICATION_V1_READY = YES
SKILL_ADAPTERS_READY = YES
READY_FOR_P3_8B_FULL_SCHEME_PLANNING = NO
```

P3.8B has not started because its entry gate requires every P3.8B0 blocker to
be closed.  The only remaining concrete item is the EpicPro binding and pose
semantics for `物料放置最右点`.

## Closed production boundaries

### AMR completion

`BaseMotionObserver` now requires observed geometric motion followed by a
versioned consecutive-stability window.  Request acceptance and an `IDLE`
label cannot emit `base_settled()`.  The P3.8A pickup and placement movement
logs are replayed in the test suite.

### Atomic manipulation observation

The production transaction now performs:

```text
read both arms before
→ commissioned Epic right_pick detection
→ fresh Pixel Pro BODY scene
→ read both arms after
→ verify joint stability
→ register detection ID and pointcloud in one ObservationEpoch
→ freeze one SceneSnapshot
```

Live evidence:

- transaction: `worklog/evidence/2026-09-24-p3-8b0/right_pick_epoch_bound_20260924T153204/manipulation_observation.json`
- observation: `OBS_P3_LIVE_1790235135850487379`
- snapshot: `SCENE_566c05ac66b5470f8185cbf640adb518`
- detection: `e20a920d-81bf-4c33-ad76-fdd21f0370af`
- pointcloud target binding: `support_06_component_00_protruding`
- detection-to-AABB distance: `0.0 m`
- target policy in the free-space compiled world: `HARD`

The target primitive is present both in target provenance and as a hard cuRobo
cuboid for current-to-pregrasp motion.  Only the dedicated contact corridor
may selectively permit tool/gripper contact.

### Contact and attachment

`TargetContactPolicy` implements monotonic Cartesian interpolation, continuous
IK, dense geometry checks, hard non-target collision, hard arm-link/target
collision, and tool/gripper target contact only in the terminal corridor.

Attached-object geometry is calculated from
`inverse(T_body_tcp) * T_body_object`, converted to a conservative link6-local
envelope, revision-bound, and consumed by the cuRobo sphere model and the
independent dense validator.  The same artifact can generate the BODY spheres
required by `DualArmSafetyKernel`; attach/detach continues to invalidate plans
through `WorldModel`.

### Grasp verification and task parameters

The reusable comparator uses a BODY-aligned 15 cm TCP neighborhood, configurable
within 10–20 cm.  It reports `PASS`, `CHANGED_EXPECTED`,
`CHANGED_UNEXPECTED`, or `UNKNOWN`, and grasp verification requires both an
expected local scene change and stable delayed gripper readback.  Gripper
readback alone never proves a grasp.

The versioned task profile owns 30/40/50 mm pregrasp candidates, preplace
height, +5 mm place offset, BODY lift z=1.20 m, 50/40/20% gripper settings,
and the local scene-delta policy.  Skill adapters delegate all free-space
motion to `SceneAwareMotionService`; obstacle avoidance is not duplicated.

## Remaining Epic binding

Read-only ATOM APIs exposed the complete graph named `物料放置最右点`, version
1.3.2, its `EpicProOutput`, and its X-axis/LOWEST pick-point sorting rule.
Evidence is at:

`worklog/evidence/2026-09-24-p3-8b0/rightmost_project_readonly.json`

The ATOM graph does not expose the EpicPro mapping from graph name to
space/object/camera, nor the output Euler/contact-axis semantics.  Therefore
`320,2,3,1,1,0` remains the explicitly named uncommissioned profile
`right_place_rightmost_candidate`.  The smallest remaining action is one
EpicPro UI screenshot/export proving that binding and its pose-axis settings.

## Verification

`.32` full suite after the current implementation checkpoint:

```text
Ran 487 tests
OK (skipped=1)
```

No AMR command was needed for this checkpoint.  Pixel Pro and both JAKA arms
were read only; no arm or gripper command was sent.
