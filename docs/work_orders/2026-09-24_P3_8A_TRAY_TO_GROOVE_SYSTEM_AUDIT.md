# P3.8A — Tray→Groove system/interface audit before real manipulation

Date: 2026-09-24
Scope: AMR + camera sensing may move/run automatically after one USER ACTION. ARM AND GRIPPER MOTION FORBIDDEN.

Read first:

~~~text
docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md
docs/architecture/2026-09-23_SCENE_AWARE_MOTION_STACK.md
docs/architecture/2026-09-23_ARBITRARY_TARGET_SKILL_SCHEME_STACK.md
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

The local 2026-09-21 work order is an important source of historical interface findings, but current repo/field state is newer. Audit all claims against current .32 code and live read-only evidence.

## 0. Permissions for this audit

After USER ACTION 1, Codex is authorized to:

- read both JAKA arms, tools and TCPs;
- read both grippers;
- use Epic 5700 detections;
- use Pixel Pro/EpicEye pointcloud capture;
- start/read ART/WebUI/backend services;
- perform bounded AMR relative movements needed to audit the owner-requested pickup/place base positions;
- perform planning-only cuRobo/IK checks for either arm;
- save evidence and create local commits.

Codex is NOT authorized in P3.8A to:

- send any JAKA arm movement;
- enable ServoJ for either arm;
- move/open/close either gripper;
- execute a grasp, lift, place or retreat;
- modify controller safety settings;
- silently commission an Epic profile without evidence.

## 1. Preserve current field state

Before touching hardware:

1. record .32 branch/HEAD/ahead-behind;
2. list dirty/untracked files;
3. preserve coworker AMR + gripper-exit fixes;
4. verify current GitHub integration HEAD;
5. run full unit tests;
6. confirm P3.7 evidence paths and WebUI/ART state.

Do not reset/revert coworker changes.
Do not force-push.

## 2. Audit hardware state and control ownership

Read-only snapshot:

~~~text
right arm joints/TCP/tool ID/tool pose
left arm joints/TCP/tool ID/tool pose
right gripper position
left gripper position
AMR battery/map/state
camera 5700 reachability
Pixel Pro 5000 reachability
LocalScene status
SceneAwareMotion status
persistent planner status
~~~

Record exact adapters, binaries, revisions and ports actually used on .32.

Check that Terminal exit cleanup cannot move grippers.

Output:

~~~text
HW_STATE_AUDIT = PASS/FAIL
NO_ARM_MOTION_SENT = YES
NO_GRIPPER_MOTION_SENT = YES
~~~

## 3. Audit AMR interface before automatic movement

The current .32 may contain an uncommitted yaw degree/radian fix that differs from GitHub remote code.

Audit the EFFECTIVE local implementation:

- relative x/y semantics;
- yaw input unit;
- maxAngularspeed unit;
- sign convention;
- collisiondetection field;
- stop command;
- timeout behavior;
- whether a reliable map pose/current pose can be read;
- whether /task/state is usable or stale;
- how base_stationary is currently established.

Do not rely on old docs if live/effective code differs.

If x/y direction in BODY/room is uncertain, use the smallest practical bounded translation needed to establish sign before the intended 0.30/0.40 m audit motion.

## 4. USER ACTION 1 — authorize bounded AMR + camera audit

Ask exactly once:

~~~text
USER ACTION 1

目的：
允许自动审计甲方阶段 Demo 所需的底盘移动与相机检测接口。

你现在做：
确认底盘计划移动区域无人、无临时障碍；双臂和夹爪保持不动；电子秤料盘与放置凹槽/泊位处于可被 Epic 看到的现场状态；物理急停可用。

完成后回复：
底盘和相机audit现场已就绪

安全边界：
Codex可自动执行本工作单限定的底盘相对移动、AMR stop、5700检测和5000点云扫描；禁止机械臂和夹爪运动。
~~~

After this confirmation, do NOT ask again between ordinary audit moves/detections unless site state changes or a fault occurs.

## 5. Automatic pickup-base audit

Create an audit origin record before movement.

Then reproduce the owner intent:

~~~text
current base
→ approximately 0.30 m pickup-side translation
→ settle
→ verify stationary by observation
→ record PICK_BASE_POSE_V1 evidence
~~~

Do not guess the final axis from prose. Determine the actual relative x/y command that moves the base toward the electronic-scale loading-tray pickup side.

Evidence must include:

- AMR request payload;
- response;
- start/end timestamps;
- commanded translation;
- observed displacement / pointcloud change;
- base pose/revision if available;
- scene invalidation event;
- post-settle fresh pointcloud.

Do not use /task/state alone as arrival proof.

## 6. Epic 5700 material-pick audit

At PICK_BASE_POSE_V1:

1. determine the exact active Epic solution/profile corresponding to right-arm 物料抓取;
2. confirm space/object/camera IDs and command;
3. run multiple read-only detections (minimum 3 if stable);
4. save every raw 5700 response;
5. parse candidate poses;
6. bind tool/calibration/profile revision;
7. transform/relate the detection to BODY using current commissioned chain;
8. compare against the fresh Pixel Pro scene.

Do not route through the default left_pick profile.

Current GitHub right_pick is historically 320,2,1,1,1,0; verify the live .32/Epic solution before treating it as canonical.

Output:

~~~text
RIGHT_PICK_5700_MAPPING_VERIFIED = YES/NO
RIGHT_PICK_DETECTION_REPEATABLE = YES/NO
RIGHT_PICK_BODY_TARGET_READY = YES/NO
~~~

## 7. Pregrasp parameter/interface audit

Introduce/audit the task-level parameter:

~~~text
pregrasp_distance_m
allowed commissioning range: 0.03–0.05
~~~

Do not choose a hidden global constant.

For each candidate 0.03 / 0.04 / 0.05 m, planning-only:

- derive verified approach direction from detection orientation/profile;
- derive pregrasp pose;
- IK;
- SceneAwareMotion free-space plan;
- report reachability, planner clearance, endpoint geometry and target provenance.

No arm motion.

Recommend an initial demo value based on current geometry, but leave it versioned/configurable.

## 8. Right-arm pregrasp/contact boundary audit

Audit the exact distinction:

~~~text
current → pregrasp
    generic SceneAwareMotion + full pointcloud collision world

pregrasp → grasp
    constrained CONTACT_TARGET approach
~~~

Do not solve the front-of-TCP entering the target obstacle box by deleting the target from the whole scene.

Design/verify a bounded contact policy:

- target object identity/provenance retained;
- tool-target intended contact may be allowed near final approach;
- arm links remain collision checked;
- non-target obstacles remain hard;
- final approach direction/length bounded;
- free-space trajectory cannot use target deletion as a shortcut.

Output:

~~~text
CONTACT_TARGET_POLICY_AUDITED = YES/NO
CONTACT_APPROACH_IMPLEMENTATION_GAP = <description>
~~~

Implementation may be code+tests in P3.8A, but no physical approach execution.

## 9. Gripper interface audit — read-only

Verify:

- right serial device;
- current position;
- min/max convention;
- mapping from user percentages to raw position;
- 50% -> expected raw target;
- 40% -> expected raw target;
- closed -> expected raw target;
- 20% -> expected raw target;
- readback/tolerance API;
- current has_object() semantics and its limitations;
- Terminal exit cleanup behavior.

Do NOT send any gripper movement.

Output:

~~~text
RIGHT_GRIPPER_PERCENT_MAPPING_READY = YES/NO
GRASP_VERIFICATION_GAP = <description>
~~~

## 10. Post-grasp scene-change audit

Prepare the required verification capability for the future physical grasp:

~~~text
pre-grasp scene
vs
post-close fresh observation
~~~

Audit/implement a generic local scene-delta function centered at the live TCP:

~~~text
radius_m configurable in 0.10–0.20
~~~

It must report:

- point occupancy change;
- new/missing local primitives;
- target-object movement/attachment expectation;
- unexpected nearby obstacle change;
- result PASS / CHANGED_EXPECTED / CHANGED_UNEXPECTED / UNKNOWN.

No grasp is executed in this audit.

Output:

~~~text
LOCAL_TCP_SCENE_DELTA_READY = YES/NO
~~~

## 11. Attached-object collision audit

After future grasp, free-space cuRobo motion must include the carried object.

Audit:

- current attachment representation;
- how a detected target cluster can produce a conservative attached geometry;
- how tool/attachment revision invalidates prior plans;
- how SceneAwareMotion passes attached-object geometry to planner/SafetyKernel;
- whether lift + transfer planning can be simulated now.

Output:

~~~text
ATTACHED_OBJECT_PIPELINE_READY = YES/NO
~~~

## 12. Lift / visibility-clear target planning audit

Planning-only, using a simulated attached object if necessary:

- target TCP z ≈ 1.20 m in BODY;
- then a right-front visibility-clear target near BODY azimuth -45 deg;
- exact radial distance selected by reachability/collision planning;
- no fixed hidden XYZ.

Check that this clears the Pixel Pro view sufficiently in the current geometric model.

No arm motion.

## 13. Automatic placement-base audit

After pickup-side camera audits are complete and while arms/grippers remain stationary:

~~~text
PICK_BASE_POSE_V1
→ approximately 0.40 m toward robot-right
→ settle
→ record PLACE_BASE_POSE_V1 evidence
~~~

Again verify actual x/y mapping rather than assuming prose direction.

Base movement must invalidate the old scene.

After settle, force a fresh Pixel Pro scene.

## 14. Epic 5700 rightmost-placement audit

This is a critical audit item.

The current GitHub right_place profile is historically uncommissioned and may NOT correspond to 物料放置最右点.

Determine from live Epic project/solution and 5700 behavior:

- exact solution/flow name;
- space ID;
- object ID;
- camera ID;
- exact 320 command;
- response pose frame;
- pose orientation convention;
- approach axis;
- calibration/tool revision required.

Run read-only detections and save raw responses.

Create a candidate versioned profile such as right_place_rightmost only if evidence supports it.

Do NOT mark it COMMISSIONED merely because a response is repeatable.

Output:

~~~text
RIGHT_PLACE_RIGHTMOST_5700_MAPPING_VERIFIED = YES/NO
RIGHT_PLACE_RIGHTMOST_POSE_SEMANTICS_VERIFIED = YES/NO
RIGHT_PLACE_RIGHTMOST_PROFILE_COMMISSIONABLE = YES/NO
~~~

## 15. Placement geometry planning audit

Using detected placement target, planning-only:

- generate pre-place target above the detected target;
- keep preplace_height_m configurable (0.10 m is a candidate, not a hidden constant);
- final placement stop = detected target + BODY +Z 0.005 m;
- audit vertical approach feasibility;
- audit groove/opening geometry representation;
- verify the scene decomposition does not fill the intended opening with one monolithic AABB.

No arm motion.

## 16. Left-arm role and dual-arm concurrency audit

The owner flow contains two intentions:

1. right arm is the customer-demo manipulation arm and left may stay unchanged;
2. left may move UP/clear while right moves to pregrasp, potentially concurrently.

Do not choose silently.

Audit:

- current left pose;
- whether left physically occludes camera/right-arm workspace;
- planning-only candidate LEFT_UP/CLEAR pose;
- whether current dual-arm coordinator supports simultaneous left/right cuRobo execution;
- mutual-arm collision model;
- execution synchronization/abort semantics.

Output:

~~~text
LEFT_HOLD_CURRENT_FEASIBLE = YES/NO
LEFT_CLEARANCE_UP_NEEDED = YES/NO
DUAL_ARM_CONCURRENT_EXECUTION_READY = YES/NO
~~~

No left/right arm motion in P3.8A.

## 17. Skill/Scheme audit

Read current:

~~~text
docs/SKILL_CATALOG.md
docs/SKILL_LIBRARY_ARCHITECTURE.md
~~~

and the local 2026-09-21 work order.

Produce a matrix:

~~~text
Scheme step
→ Skill ID
→ existing implementation
→ reusable backend service
→ missing code
→ required inputs
→ verification/effect
~~~

At minimum audit:

- navigate.go_to_station / registered relative move;
- observe.capture_scene;
- observe.detect_resource;
- manipulation.plan_to_pose / move_free;
- manipulation.approach;
- manipulation.grasp;
- manipulation.retreat / lift;
- manipulation.release;
- execution.authorize;
- execution.execute_trajectory;
- composite manipulation.pick/place/transfer_object.

Obstacle avoidance remains below Skills in SceneAwareMotionService.

## 18. Audit return-to-origin

If the site remains clear and the effective AMR interface can safely reproduce the inverse relative transforms, return the base to the recorded AUDIT_ORIGIN after all camera audits.

If return cannot be verified, stop at PLACE_BASE_POSE_V1 and report exact final base state rather than guessing.

## 19. Required report

Create:

~~~text
docs/reports/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT_REPORT.md
~~~

Report:

~~~text
HW_STATE_AUDIT
AMR_EFFECTIVE_INTERFACE_VERIFIED
PICK_BASE_POSE_V1_RECORDED
RIGHT_PICK_5700_MAPPING_VERIFIED
RIGHT_PICK_BODY_TARGET_READY
PREGRASP_INTERFACE_READY
CONTACT_TARGET_POLICY_AUDITED
RIGHT_GRIPPER_PERCENT_MAPPING_READY
LOCAL_TCP_SCENE_DELTA_READY
ATTACHED_OBJECT_PIPELINE_READY
LIFT_VISIBILITY_CLEAR_PLAN_READY
PLACE_BASE_POSE_V1_RECORDED
RIGHT_PLACE_RIGHTMOST_5700_MAPPING_VERIFIED
RIGHT_PLACE_RIGHTMOST_POSE_SEMANTICS_VERIFIED
PLACEMENT_VERTICAL_PLAN_READY
LEFT_HOLD_CURRENT_FEASIBLE
LEFT_CLEARANCE_UP_NEEDED
DUAL_ARM_CONCURRENT_EXECUTION_READY
SKILL_SCHEME_AUDIT_READY
READY_FOR_P3_8B_PLANNING_ONLY_SCHEME
~~~

Also list every blocker as:

~~~text
BLOCKER
why
evidence
smallest next action
~~~

## 20. End state

P3.8A ends with:

- no arm motion;
- no gripper motion;
- full hardware/interface audit;
- bounded AMR + camera evidence;
- exact pick/place 5700 mappings or explicit blockers;
- planning-only target/approach/lift/place feasibility;
- Skill/Scheme implementation matrix.

Do not begin real grasp in P3.8A.

## 21. Git policy

Small commits.
Do not include unrelated coworker AMR work unless the owner explicitly asks to consolidate it.
Do not force-push.
If remote integration HEAD changes, use the established relay/replay workflow.