> SUPERSEDED FOR EXECUTION BY P3.6.
> Retain this file as P3.5 scene-agnostic evidence/test design. The next implementation step is the control-layer refactor in docs/work_orders/2026-09-23_P3_6_SCENE_AWARE_MOTION_CONTROL.md.

# P3.5 — Scene-agnostic scan → reconstruct → cuRobo → execute demo

Date: 2026-09-23

## Goal

Prove that the right-arm A/B avoidance demo is driven by each fresh Pixel Pro scan, not by the current dock/box layout.

Runtime contract:

~~~text
fresh Pixel Pro scan
→ CAMERA→BODY
→ whole-robot self-filter
→ generic residual cleanup
→ generic support/object decomposition
→ multi-primitive obstacle world
→ fresh inactive-left-arm geometry
→ fresh SceneSnapshot
→ persistent cuRobo start→goal planning (no explicit waypoint)
→ dense validation
→ supervised execution
~~~

No obstacle coordinates, object ID, dock ID, box pose or historical SceneSnapshot may be supplied manually to the runtime planner.
A/B endpoints may remain fixed. P3.5 generalizes the ENVIRONMENT, not the task target.

## Entry gates

Finish and consolidate P3.4 first.

Require:

~~~text
FAST_CAMERA_PATH_READY = YES
FAST_SCENE_PIPELINE_READY = YES
PERSISTENT_PLANNER_READY = YES
FAST_PLANNER_PROFILE_READY = YES
AB_SPEED_PROFILE_COMMISSIONED = YES
~~~

Before P3.5, preserve/push the current local field code while excluding coworker AMR dirty changes.

## Speed-config consistency

Current field evidence includes successful A/B motion at 0.20 rad/s with A/B-specific tracking stop 1.5 deg.
The older site config still contains a 0.10 rad/s ceiling. Do not leave this contradiction hidden.

Create an explicit versioned A/B-demo-only profile, for example:

~~~text
scope = RIGHT_AB_DEMO_ONLY
max_velocity_rad_s = 0.20
tracking_stop_deg = 1.5
state = COMMISSIONED_FROM_SITE_TEST_20260923
~~~

Do not silently raise unrelated motion modes. Bind the profile to the actual successful run evidence.

## Runtime hard-code audit

Audit the production A/B scan/scene/plan path and remove runtime dependence on:

- fixed SceneSnapshot IDs;
- observed_support_03 or any specific cluster ID;
- fixed box coordinates;
- fixed dock coordinates;
- current_base evidence paths;
- fixed obstacle count;
- fixed primitive IDs;
- special-case deletion of the current box/dock.

Runtime inputs must be only:

- fresh camera data;
- commissioned transforms/config;
- current robot state;
- generic scene-processing parameters;
- versioned A/B target contract.

Output: SCENE_RUNTIME_HARDCODE_AUDIT = PASS/FAIL.

## Canonical generic live-scene backend

Create one backend function/service call named build_live_planning_scene (name may adapt to current code style).

It returns:

- pointcloud frame/SHA;
- calibration revision;
- current robot/inactive-arm revisions;
- support surfaces;
- generic obstacle primitives;
- unknown occupied primitives;
- SceneSnapshot ID/digest;
- stage timings;
- validity state.

No planner call may use a stale or invalid scene.

## Generic obstacle behavior

The world must be reconstructed from observed geometry, not object recognition.

Expected supported examples when visible:

- cardboard box;
- bottle/container;
- arbitrary block;
- irregular tool/object;
- one or multiple objects;
- moved object at a new location;
- empty corridor.

Occluded/unseen space remains conservative.

## One-command backend

Add/finish ART backend command:

~~~text
demo ab run-next
~~~

Semantics:

~~~text
verify current endpoint / actual start
→ fresh fast scan
→ build generic live scene
→ persistent planner update_world
→ direct cuRobo start→goal solve
→ dense independent validation
→ package using commissioned A/B-demo speed profile
→ preflight
→ execute
→ verify arrival
→ invalidate scene/trajectory
~~~

Keep separate commands too:

~~~text
demo ab scan
demo ab plan-next
demo ab preview
demo ab execute-next
demo ab stop
demo ab status
~~~

## Arbitrary-scene validation battery

### S0 CLEAR
Fresh empty/clear corridor. Plan and execute successfully.

### S1 random box placement
User places the existing box at a new arbitrary position and does NOT provide coordinates.
System must scan and infer the obstacle itself.

### S2 move same box again
Move it to a clearly different arbitrary location. Old pose must not be reused.

### S3 different ordinary object
No object-specific code. Generic reconstruction must plan/execute or fail closed if truly blocked.

### S4 two obstacles
Both must enter the same fresh collision world. No single-box assumption.

### S5 blocked
Physical or explicitly-labelled synthetic block. Must fail with no stale/fallback execution.

Record scene SHA, primitive count, planning time, clearance, trajectory hash and execution result for every scenario.

## USER ACTION policy

Ask one action at a time.

USER ACTION 1:

~~~text
目的：验证系统不依赖固定场景或已知障碍坐标。
你现在做：在相机可见、右臂 A/B 工作区内，把规则盒子随意放到一个新位置。不要告诉软件坐标；保持左臂和底盘不动。
完成后回复：随机盒子场景已放置
安全边界：盒子放稳，不移动机器人。
~~~

USER ACTION 2 after S1 passes:

~~~text
把盒子换到另一个明显不同的位置，不告诉软件坐标。
完成后回复：第二随机场景已放置
~~~

Then request one different object or two objects only after S1/S2 pass.

## Acceptance

~~~text
SCENE_RUNTIME_HARDCODE_AUDIT = PASS
FRESH_SCENE_REQUIRED_EVERY_LEG = YES
NO_MANUAL_OBSTACLE_COORDINATES = YES
NO_OBJECT_SPECIFIC_AVOIDANCE_CODE = YES
CLEAR_DYNAMIC_SCENE = PASS
MOVED_BOX_SCENE_1 = PASS
MOVED_BOX_SCENE_2 = PASS
DIFFERENT_OBJECT_SCENE = PASS or documented fail-closed
MULTI_OBJECT_SCENE = PASS or documented fail-closed
BLOCKED_SCENE_FAIL_CLOSED = PASS
~~~

## Latency

Use the optimized P3.4 backend and report capture, scene-build, persistent-plan and scan→trajectory p50/p95, plus full leg scan→arrival.
Target demo quality: scan→trajectory preferably <=15–20 s. Do not reuse stale scenes just to meet latency.

## What arbitrary scene means today

P3.5 supports static scenes during one scan-plan-execute leg, obstacles visible in the Pixel Pro field of view, the current reachable A/B workspace, and generic observed geometry represented by the multi-primitive pipeline.

P3.5 does not yet claim moving-human reactive avoidance, guaranteed free space behind occlusions, arbitrary cabinet insertion into unseen cavities, whole-room mapping, nvblox/ESDF reactive planning, or left-arm execution.

## Visual evidence

For every scenario save one comparable view containing BODY pointcloud, reconstructed obstacle primitives, both arms, A/B, planned TCP path, limiting object/clearance and scan/scene/plan timing.

## Git policy

Small commits; no force-push; no coworker AMR dirty changes.
After P3.4 consolidation and P3.5 tests pass, normal fast-forward push is allowed only if remote HEAD is unchanged; otherwise use the established relay/replay workflow.
Leave .32 and GitHub aligned.