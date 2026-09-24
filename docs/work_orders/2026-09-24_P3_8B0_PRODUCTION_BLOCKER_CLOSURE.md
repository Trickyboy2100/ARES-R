# P3.8B0 — Close the six production blockers for real Tray→Groove execution

Date: 2026-09-24
Goal: turn the completed P3.8A audit into production code. This is implementation, not another broad audit.

Read first:

~~~text
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
docs/work_orders/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT.md
docs/reports/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT_REPORT.md
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

## 0. First action: preserve and publish P3.8A

The integration branch is still at the P3.7 report commit when this order was written. P3.8A evidence/report may still be local.

Before coding:

- preserve .32 dirty/untracked state;
- keep coworker AMR/gripper-exit changes isolated;
- run full tests;
- commit the P3.8A report/evidence cleanly;
- normal fast-forward push only if remote HEAD is compatible.

Do not lose the AMR field evidence or 5700 raw responses.

## 1. Blocker 1 — truthful AMR completion observer

Current problem: move_relative acceptance is asynchronous; status/IDLE is not arrival proof.

Implement a reusable BaseMotionObserver and integrate it below navigation/SceneAwareBase.

Required lifecycle:

~~~text
REQUESTED
→ MOTION_OBSERVED
→ SETTLING
→ SETTLED
or FAULT/TIMEOUT
~~~

Use observation, not controller labels alone.

Preferred generic evidence:

- fast Pixel Pro scene signatures / voxelized scene registration across time;
- optional stable Epic/landmark target when available;
- unchanged arm state;
- bounded settle window.

Require consecutive stable observations before `base_settled()` is emitted.

Make thresholds versioned/configurable and record evidence.

Replay-test the P3.8A pick/place AMR logs.

Exit:

~~~text
AMR_COMPLETION_OBSERVER_READY = YES
BASE_SETTLED_NOT_EMITTED_ON_ACCEPT_ONLY = YES
~~~

## 2. Blocker 2 — atomic ObservationTransaction (5700 + 5000 + robot state)

Implement one canonical transaction for a manipulation observation:

~~~text
read robot/tool state before
→ Epic 5700 detection
→ Pixel Pro 5000 pointcloud
→ read robot/tool state after
→ verify state stability/time bounds
→ commit detection artifact + pointcloud SHA + calibration/tool revisions into ONE ObservationEpoch
→ freeze SceneSnapshot / target bundle
~~~

Create a typed artifact such as ManipulationObservation / ObservationBundle.

It must bind:

- raw 5700 request/response;
- detection ID/profile/space/object/camera;
- canonical BODY target pose;
- pointcloud SHA;
- SceneSnapshot ID;
- calibration revision;
- tool revision;
- before/after joint state;
- timestamps.

`SceneAwareMotionService` and grasp planning must consume this bound artifact, never a loose live detection.

Exit:

~~~text
MANIPULATION_OBSERVATION_TRANSACTION_READY = YES
RIGHT_PICK_TARGET_EPOCH_BOUND = YES
~~~

## 3. Blocker 3 — prove and commission rightmost placement profile

P3.8A evidence says object 3 is the strongest geometric candidate, but 5700 alone cannot prove that it is the Epic solution named `物料放置最右点` or prove pose-axis semantics.

First try to obtain the mapping automatically/read-only from the Epic project/UI/backend/exported configuration on the local network.

Need to establish:

- flow/solution name;
- space ID;
- object ID;
- camera ID;
- 320 command;
- output frame;
- orientation convention;
- approach/contact axis;
- calibration/tool revision.

Current candidate to test, NOT to assume:

~~~text
space=2
object=3
camera=1
command=320,2,3,1,1,0
~~~

If the project mapping is not programmatically exposed, ask exactly one USER ACTION:

~~~text
USER ACTION — Epic右臂最右放置映射
请在 Epic WebUI 中选中右臂方案“物料放置最右点”，打开能显示/证明空间ID、物料/对象ID、相机ID或抓取配置的页面并截图/导出配置；不要修改方案。
完成后回复：最右放置映射已提供
~~~

Then validate orientation/contact axis against tool/board/groove geometry.

Only then create/commission a versioned `right_place_rightmost` profile.

Exit:

~~~text
RIGHT_PLACE_RIGHTMOST_PROFILE_READY = YES
~~~

## 4. Blocker 4 — TargetContactPolicy

Do not globally remove the target object from collision geometry.

Implement a separate contact-motion contract for the short pregrasp→grasp and preplace→place segments.

Concept:

~~~text
TargetContactPolicy:
  target_object_id
  allowed_contact_links = tool/gripper contact geometry only
  approach_axis
  max_approach_distance_m
  corridor_radius/width
  endpoint_tolerance
  non_target_collision = HARD
  arm_link_vs_target = HARD
  tool_vs_target = ALLOWED_ONLY_IN_CONTACT_CORRIDOR
~~~

Recommended implementation for V1:

- free-space current→pregrasp remains normal cuRobo with target present;
- final approach is a constrained Cartesian/IK segment;
- selective independent collision validator checks every sample;
- target remains hard for arm links;
- tool-target overlap/contact is allowed only inside the bounded final corridor;
- all non-target obstacles remain hard.

Do not require cuRobo itself to model contact if link-pair collision masking is not cleanly supported.

Exit:

~~~text
TARGET_CONTACT_POLICY_READY = YES
PREGRASP_TO_GRASP_PLANNING_READY = YES
PREPLACE_TO_PLACE_PLANNING_READY = YES
~~~

## 5. Blocker 5 — attached-object collision pipeline

Create a production attached geometry representation from the detected target primitive/cluster.

At the verified grasp state:

~~~text
T_tcp_object = inverse(T_body_tcp) * T_body_object
~~~

Build conservative TCP/link6-local collision geometry with lineage to the target SceneObject.

Use the SAME geometry in:

- SceneAwareMotion/cuRobo moving collision model;
- dense validator;
- SafetyKernel geometry samples;
- visualization/WebUI.

Practical V1 may convert the target OBB/AABB to link6/TCP-local collision spheres/cuboids, but must retain revision/provenance.

Attachment/detachment must invalidate old plans.

Exit:

~~~text
ATTACHED_OBJECT_GEOMETRY_READY = YES
ATTACHED_OBJECT_CUROBO_READY = YES
ATTACHED_OBJECT_SAFETY_VALIDATION_READY = YES
~~~

## 6. Blocker 6 — local TCP scene delta + grasp verification

Implement a reusable pre/post observation comparator around the live TCP.

Config:

~~~text
radius_m: 0.10–0.20
default initial demo radius: 0.15
~~~

Compare BODY-aligned voxel/primitives before and after gripper closure.

Output:

~~~text
PASS
CHANGED_EXPECTED
CHANGED_UNEXPECTED
UNKNOWN
~~~

Include:

- local occupied-volume/voxel change;
- target primitive disappearance/movement;
- unexpected new obstacle;
- gripper readback before/after and delayed repeat;
- optional post-lift persistence later.

Do not claim object presence from `has_object()` alone.

Exit:

~~~text
LOCAL_TCP_SCENE_DELTA_READY = YES
GRASP_VERIFICATION_V1_READY = YES
~~~

## 7. Parameterize the manipulation interfaces

Remove hidden task constants from production flow.

Create/version:

~~~text
pregrasp_distance_m = configurable 0.03–0.05
preplace_height_m
final_place_offset_m = 0.005
lift_target_z_m = 1.20
local_scene_delta_radius_m = 0.15 initial
gripper_prepare_percent = 50
gripper_pregrasp_percent = 40
gripper_release_percent = 20
~~~

Gripper percentage conversion must be a shared helper, not repeated arithmetic in task code.

## 8. Skill adapters, not duplicate motion code

Implement/reconcile Skill wrappers around existing services:

~~~text
navigate.go_to_station / registered_relative
observe.capture_scene
observe.detect_resource
manipulation.move_free
manipulation.approach
manipulation.grasp
manipulation.lift
manipulation.release
manipulation.retreat
execution.authorize
execution.execute_trajectory
~~~

Every free-space Skill calls SceneAwareMotionService.

Obstacle avoidance is not a Skill.

Do not yet implement the complete physical Scheme runner in P3.8B0.

## 9. Planning-only closure test using live camera/AMR

AMR and camera may be used automatically after the existing site authorization if still valid; arms/grippers remain stationary.

Revisit/re-establish pickup and placement audit positions as needed.

Required planning-only evidence:

- epoch-bound right-pick detection + scene;
- pregrasp 0.03/0.04/0.05 comparison through production interface;
- contact approach plan;
- simulated grasp attachment creation;
- lift-to-z=1.20 plan with attached object;
- visibility-clear right-front plan with attached object;
- epoch-bound rightmost-place detection;
- preplace free-space plan with attached object;
- vertical placement contact plan to +5 mm;
- release/detach/retreat simulated transition.

## 10. Exit gate

Report:

~~~text
AMR_COMPLETION_OBSERVER_READY
MANIPULATION_OBSERVATION_TRANSACTION_READY
RIGHT_PICK_TARGET_EPOCH_BOUND
RIGHT_PLACE_RIGHTMOST_PROFILE_READY
TARGET_CONTACT_POLICY_READY
ATTACHED_OBJECT_GEOMETRY_READY
ATTACHED_OBJECT_CUROBO_READY
LOCAL_TCP_SCENE_DELTA_READY
GRASP_VERIFICATION_V1_READY
SKILL_ADAPTERS_READY
READY_FOR_P3_8B_FULL_SCHEME_PLANNING
~~~

Do not stop at `PARTIAL` without naming the smallest concrete missing item.

## 11. Git

Small commits per blocker.
No force-push.
Keep unrelated coworker work isolated.
Push clean fast-forward subphases when safe.
Leave .32/GitHub aligned at completion.