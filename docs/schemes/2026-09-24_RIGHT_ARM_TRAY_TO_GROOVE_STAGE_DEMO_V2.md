# Scheme draft — RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2

Date: 2026-09-24
Status: OWNER FLOW RECORDED; AUDIT BEFORE ARM/GRIPPER EXECUTION

## 0. Purpose

This document records the owner-confirmed staged customer demo after P3.7 arbitrary-target scene-aware motion.

Primary demo arm: right.
Left arm is not a manipulation arm for this customer demo, but may later be moved to a clearance/up pose if the audit shows it is required. No arm motion is authorized by this document.

Free-space arm movement must use SceneAwareMotionService + fresh LocalScene + cuRobo. Contact/approach phases use explicit manipulation/contact semantics.

## 1. Owner-requested physical sequence

### S0 — presentation posture

- Right arm: prepare an UP/clear presentation posture.
- Right gripper: 50% opening.
- Left arm: initially preserve current state; audit whether a dedicated UP/clear pose is required.
- No hard-coded joint pose. Posture is a semantic/named target resolved through motion planning.

### S1 — establish pickup base pose

- From the current AMR position, translate approximately 0.30 m to a pickup-friendly position in front of / slightly left of the electronic-scale loading tray.
- Record this as PICK_BASE_POSE_V1 with provenance.
- AMR motion invalidates the prior LocalScene.
- After settle, the next arm motion must require a new Pixel Pro scene.

Audit must determine the correct AMR x/y sign from the commissioned/local .32 interface. Do not infer room direction from stale documentation.

### S2 — 5700 material-pick target acquisition

- Call Epic port 5700 using the actual right-arm `物料抓取` solution/profile.
- Persist the raw response, profile/space/object IDs, pose frame, calibration/tool revision and timestamp.
- Convert the detected pose into the canonical target interface.
- Capture the fresh Pixel Pro local scene and bind semantic target + collision scene provenance.

Define a task parameter:

~~~text
pregrasp_distance_m
commissioning range: 0.03–0.05 m
~~~

The pregrasp point is generated from the detected grasp pose and its verified approach axis. The Scheme does not hard-code BODY +X even if the current commissioned pick profile is approximately +X.

### S3 — pregrasp preparation

- Right free-space target = detected grasp pose backed off by pregrasp_distance_m along the approach axis.
- Right gripper target = 40% opening after/at pregrasp preparation.
- Right arm free-space motion uses SceneAwareMotionService and cuRobo.

Left-arm policy is a versioned Scheme parameter:

~~~text
left_arm_policy = HOLD_CURRENT | CLEARANCE_UP
~~~

The owner also requested a possible future mode where left moves UP while right moves to pregrasp. The audit must determine whether the current dual-arm coordinator supports simultaneous planned execution. Do not silently require simultaneous motion for the first right-arm-only customer demo.

### S4 — contact approach and grasp

- From pregrasp, move the right TCP along the verified approach axis to the detected grasp pose.
- Close the right gripper to the grasp command.

This phase is NOT ordinary free-space obstacle avoidance.

The target object may occupy the final tool path. Therefore implement/contact-audit a CONTACT_TARGET policy:

- target object remains part of perception/scene provenance;
- surrounding environment remains hard collision geometry;
- arm links may not penetrate target/environment;
- only the intended tool/target contact pair may be relaxed/allowed inside a bounded final-approach corridor;
- no global deletion of the target or surrounding scene;
- free-space approach-to-pregrasp still uses normal scene-aware collision planning.

### S5 — post-grasp local scene verification

Immediately after gripper closure:

- acquire a new local scan / verification observation;
- compare against the pre-grasp scene;
- pay special attention to a configurable TCP-local neighborhood radius 0.10–0.20 m;
- classify expected change (target now attached/moved) vs unexpected nearby scene change;
- if the local change is unexpectedly large, stop the Scheme before lift.

After grasp verification, create/update an attached-object collision model and invalidate old free-space trajectories.

### S6 — lift and visibility-clear pose

- Move the grasped object vertically in BODY +Z until TCP z is approximately 1.20 m.
- Then move toward a right-front visibility-clear region so the right arm/object do not occlude the camera.

Represent the visibility-clear target semantically, not as one fixed XYZ:

~~~text
target_z_m = 1.20
body_azimuth_deg ≈ -45   # +X forward, -Y right
radial distance / exact target = runtime-planned and reachability-checked
~~~

Free-space portions use SceneAwareMotionService with attached-object geometry.

### S7 — establish placement base pose

- With arm/object in a safe carry/visibility-clear state, translate the AMR approximately 0.40 m toward robot-right.
- Record PLACE_BASE_POSE_V1 with provenance.
- Base movement invalidates the old local scene.
- After settle, require a new Pixel Pro scene.

### S8 — 5700 rightmost placement target acquisition

- Call Epic 5700 using the actual `物料放置最右点` solution/profile.
- Do NOT assume current `right_place` config maps to this solution.
- Audit and record exact space/object/profile/command mapping first.
- Convert the detected placement pose into the canonical ManipulationTargets interface.

### S9 — scene-aware move above placement

- Plan with attached-object geometry to a runtime pre-place pose above the detected placement target.
- Initial vertical staging height may use 0.10 m as a candidate from the earlier work order, but remains a Scheme/config parameter.

### S10 — vertical placement

- Descend vertically in BODY -Z.
- Final TCP stop is detected placement pose + 0.005 m in BODY +Z.
- No arbitrary free-space detour is allowed during the final vertical contact/place segment.

### S11 — release and retreat

- Command gripper to 20% opening after placement.
- Retreat the right TCP away from the placement/contact region using a parameterized retreat direction/distance.
- Retreat the AMR after the arm reaches a safe posture.
- Verify scene/object result before declaring task complete.

## 2. Manipulation target interface

All key coordinates come from interfaces, not Scheme literals.

~~~text
ManipulationTargets:
  pick:
    grasp_pose
    approach_axis
    pregrasp_distance_m
  place:
    place_pose
    preplace_height_m
    final_stop_offset_m = 0.005
  lift:
    target_tcp_z_m = 1.20
  visibility_clear:
    body_azimuth_deg
    runtime_target_pose
  retreat:
    axis
    distance_m
  provenance:
    source_profile
    raw_detection_id
    observation_epoch
    scene_snapshot_id
    calibration_revision
    tool_revision
~~~

## 3. Skill boundary

Reuse the repository Skill architecture. Initial Scheme composition:

~~~text
navigate.go_to_station / navigate.move_relative_registered
observe.capture_scene
observe.detect_resource
manipulation.plan_to_pose / move_free
manipulation.approach
manipulation.grasp
manipulation.retreat / lift
manipulation.release
execution.authorize
execution.execute_trajectory
~~~

Composite Skills later:

~~~text
manipulation.pick
manipulation.place
manipulation.transfer_object
~~~

Obstacle avoidance itself is NOT a Skill. It is inherited from SceneAwareMotionService by every free-space motion Skill.

## 4. Scheme state machine

~~~text
PREPARE
→ PICK_BASE_MOVE
→ PICK_DETECT
→ PICK_SCENE_READY
→ MOVE_PREGRASP
→ CONTACT_APPROACH
→ GRASP
→ VERIFY_LOCAL_CHANGE
→ ATTACH
→ LIFT
→ VISIBILITY_CLEAR
→ PLACE_BASE_MOVE
→ PLACE_DETECT
→ PLACE_SCENE_READY
→ MOVE_PREPLACE
→ PLACE_DESCEND
→ RELEASE
→ RETREAT
→ VERIFY_RESULT
→ COMPLETE
~~~

Any base move, attachment change, tool revision change or explicit rescan invalidates plans according to LocalScene/SceneAwareMotion lifecycle.

## 5. Current known interface caveats to audit

- GitHub config currently still has `default_pick_profile=left_pick` and `default_place_profile=left_place`; right-arm task code must not accidentally use defaults.
- GitHub `right_pick` is commissioned; current GitHub `right_place` remains UNCOMMISSIONED and may not represent `物料放置最右点`.
- `.32` contains AMR yaw-unit changes not necessarily represented by current remote `amr_http.py`; audit the effective local implementation before movement.
- `base.positions` has historically been empty; PICK_BASE_POSE_V1 / PLACE_BASE_POSE_V1 need an evidence-backed persistence mechanism.
- The owner flow contains both `left arm holds current` and a possible `left arm moves UP concurrently`; audit support and make it an explicit policy, not an implicit behavior.

## 6. Execution staging

This document records the target Scheme only.

Current next phase is AUDIT: AMR movement + Epic/Pixel Pro sensing are allowed after one USER ACTION; arm and gripper motion are forbidden.

Arm/gripper execution starts only in a later reviewed work order.

## 7. P3.8A audited facts (2026-09-24)

The implementation must now use these evidence-backed facts:

~~~text
AMR effective local semantics:
  x+ forward
  x- backward
  y+ left
  y- right
  orientation degrees
  negative yaw clockwise
  maxAngularspeed rad/s

PICK_BASE_POSE_V1 audit move:
  relative y = +0.30 m

PLACE_BASE_POSE_V1 audit move from pickup pose:
  relative y = -0.40 m

right material-pick:
  profile right_pick
  command 320,2,1,1,1,0
  space=2 object=1 camera=1
  frame=right_arm_base_candidate
  orientation=ZYX
  approach_axis=+z
  state=COMMISSIONED

rightmost-placement current strongest candidate:
  object 3
  candidate command 320,2,3,1,1,0
  NOT YET COMMISSIONED
~~~

Important:

- AMR accepted/status IDLE is not completion. Use the production BaseMotionObserver before declaring a station reached.
- 5700 detection and Pixel Pro pointcloud must be committed into one ObservationEpoch before manipulation planning.
- rightmost-placement object 3 remains a candidate until the Epic solution mapping and pose/contact-axis semantics are proven.
- final contact must use TargetContactPolicy; target removal from the entire collision world is not acceptable.
- transfer after grasp must use attached-object collision geometry.
- left arm stays HOLD_CURRENT for the first right-arm customer demo; concurrent dual-arm execution is not required.
