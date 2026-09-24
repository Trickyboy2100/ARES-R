# P3.8B1A — CONTACT_BYPASS_V1 first-pick checkpoint

Date: 2026-09-24

## Outcome

The first-pick planning-only package is ready. Ordinary free-space motion still
uses a fresh atomic observation, the full point-cloud world and cuRobo. The
stage policy is restricted to the reviewed right-arm contact/escape sequence.

~~~text
FINE_COMPONENT_MODEL_DEFERRED_TO_TODO = YES
CONTACT_BYPASS_V1_READY = YES
GENERIC_FREE_SPACE_STILL_FULL_COLLISION = YES
PREGRASP_TO_GRASP_BYPASS_PLAN_READY = YES
GRASP_VERIFICATION_READY = YES
INITIAL_100MM_BYPASS_LIFT_READY = YES
COARSE_ATTACHED_OBJECT_READY = YES
FIRST_PICK_EXECUTION_PACKAGE_READY = YES
FIRST_REAL_PICK_EXECUTED = NO
FIRST_100MM_LIFT_EXECUTED = NO
~~~

## Bound evidence

- observation: `OBS_P3_LIVE_1790240314185583744`
- scene: `SCENE_996b557dcced48bea877c15a34f1171d`
- point cloud: `34d82a87a77439ea55a9ddc49e9df1ee075a5ff1deb1be2efe42166ee6bf2eae`
- target BODY pose: `[0.691250308, -0.187880656, 0.988717850] m`
- pregrasp: existing successful 50 mm cuRobo trajectory
- contact: fixed-orientation straight 50 mm, dense continuous IK
- escape: straight BODY +Z 100 mm, dense continuous IK
- package SHA-256: `e7c9add3e52c57bedb63b5881e79c256b33c34990e8ce36b7e0d1cabbf2315e5`
- package evidence: `/home/yikun/ARES-R/worklog/evidence/2026-09-24-p3-8b1a/first_pick_package_20260924T174934/`

## Collision semantics

Only active-right-gripper/tool versus observed point-cloud collision is ignored
during the bounded approach/close/initial-lift stage. Link1–Link6 versus the
world, inactive-left-arm geometry, non-adjacent self collision, joint limits and
the BODY central exclusion remain hard. The bypass expires at the +100 mm lift
endpoint. The target primitive then becomes a revision-bound coarse attached
AABB; the package stops in HOLD and contains no placement action.

The opening-specific seven-component EG2-4C2 implementation and diagnostics
remain in the repository as optional `SELECTIVE_CONTACT_COMPONENTS_V2` work.
They are not a mandatory V1 execution gate.
