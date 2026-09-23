# P3.7 — Arbitrary-target Scene-Aware Motion

Date: 2026-09-23

Read first:

~~~text
docs/architecture/2026-09-23_SCENE_AWARE_MOTION_STACK.md
docs/architecture/2026-09-23_ARBITRARY_TARGET_SKILL_SCHEME_STACK.md
~~~

## 0. Goal

Remove fixed A/B target dependence from the low-level motion path.

The robot must be able to:

~~~text
after any base pose / scene change
→ fresh local scene
→ accept an arbitrary reachable BODY target point/pose at runtime
→ plan collision-aware motion through the observed pointcloud world
→ execute
~~~

A/B stays only as a regression/demo preset.

## 1. Confirm current scene generalization

Before target refactor, verify P3.6 D1 evidence:

- fresh Pixel Pro scan;
- new pointcloud SHA;
- new SceneSnapshot;
- no manual obstacle coordinates;
- no box/dock special-case logic;
- generic SceneAwareMotionService;
- real execution.

Report:

~~~text
FRESH_SCENE_GENERIC_OBSTACLE_PATH = YES/NO
~~~

If NO, stop and fix scene coupling first.

## 2. Generic runtime MotionGoal

Implement a versioned target contract independent of A/B.

Minimum:

~~~text
frame = BODY
position_m = [x,y,z]

orientation.mode:
  LEVEL_YAW_FREE
  LEVEL_YAW_TARGET
  CURRENT
  EXPLICIT

optional:
  yaw_target
  position_tolerance
  orientation_tolerance
  source
~~~

No hidden fallback to A/B coordinates.

## 3. LEVEL_YAW_FREE constraint

This is the default constraint for the next demo.

Required semantics:

- gripper/TCP remains level relative to the ground/BODY horizontal plane;
- roll/pitch level condition is maintained throughout the planned trajectory;
- yaw about BODY +Z may vary during planning;
- final yaw may be planner-selected unless upper layer supplies LEVEL_YAW_TARGET.

Implement using a generic orientation constraint interface suitable for future tasks.

Do not hard-code this only inside the A/B client.

Dense path validation must report:

- max level/tilt error;
- yaw range;
- final yaw.

## 4. Arbitrary target ART interface

Add generic commands, exact syntax may adapt:

~~~text
motion plan right --xyz X Y Z --orientation LEVEL_YAW_FREE
motion preview
motion execute
motion stop
motion status
~~~

Optional:

~~~text
motion plan right --xyz X Y Z --orientation LEVEL_YAW_TARGET --yaw DEG
~~~

Targets must come from command/runtime input.

## 5. Arbitrary target UI

Update minimal scene-aware UI:

- BODY XYZ editable target;
- optional 3D target marker placement/click if practical;
- orientation selector;
- yaw target shown only for LEVEL_YAW_TARGET;
- Plan/Preview/Execute;
- current scene epoch and plan binding.

A/B controls move to a separate Demo/Regression panel.

## 6. Target validity

For every arbitrary goal:

1. check target finite / BODY frame;
2. solve IK;
3. reject unreachable target;
4. reject hard-invalid endpoint;
5. plan from actual live state;
6. collision-aware cuRobo in current fresh scene;
7. validate hard execution constraints;
8. execute exact bound trajectory.

No automatic substitution of a nearby A/B target.

## 7. Arbitrary point-pair demo

The demo must not use the configured A/B pair.

Select or input at runtime at least three distinct reachable target points P/Q/R in the current working volume.

Requirements:

~~~text
P, Q, R not loaded from A/B config
positions materially different
LEVEL_YAW_FREE active
fresh scene semantics preserved
~~~

Test sequence:

~~~text
current → P
P → Q
Q → R
R → P
~~~

At least one scene contains an arbitrary visible obstacle such that cuRobo trajectory bends around observed geometry.

If obstacle placement changes:

- old scene/plan invalidates;
- fresh scan is required.

## 8. USER ACTION — arbitrary obstacle for arbitrary-target demo

Ask only when backend P/Q/R planning is ready.

~~~text
USER ACTION

目的：
验证“任意目标点 + 任意新场景点云”底层避障能力。

你现在做：
在相机可见且机器人工作区内随意放一个障碍物，不提供坐标；不要移动底盘和左臂。

完成后回复：
“任意目标避障场景已放置”

安全边界：
障碍放稳，不接触机器人。
~~~

Codex then chooses/uses runtime P/Q target inputs so the requested motion meaningfully crosses the occupied region; do not rely on a target pair that naturally moves away from the obstacle.

## 9. Base-move regression

Verify logically and, if convenient, physically:

~~~text
base movement
→ scene invalid
→ base settled
→ scene REQUIRED
→ arbitrary motion request
→ automatic fresh scan
→ plan
~~~

No fixed A/B assumption.

## 10. Acceptance

Report:

~~~text
FRESH_SCENE_GENERIC_OBSTACLE_PATH = YES/NO
ARBITRARY_RUNTIME_TARGET_READY = YES/NO
NO_FIXED_AB_DEPENDENCE = YES/NO
LEVEL_YAW_FREE_READY = YES/NO
LEVEL_YAW_FREE_DENSE_VALIDATION = YES/NO
ART_ARBITRARY_TARGET_READY = YES/NO
UI_ARBITRARY_TARGET_READY = YES/NO
ARBITRARY_POINT_PAIR_EXECUTED = YES/NO
ARBITRARY_OBSTACLE_AVOID_EXECUTED = YES/NO
BASE_MOVE_THEN_ARBITRARY_TARGET_AUTO_SCAN = YES/NO
~~~

Also report:

- runtime target coordinates and sources;
- scene epochs;
- max level error;
- yaw variation;
- path clearance;
- scan/scene/plan/execute time;
- commit SHA.

## 11. Scope

P3.7 is FREE-SPACE motion only.

Do not yet implement contact/grasp/place behavior.

That begins in P3.8.

## 12. Git policy

Small commits.
No force-push.
Keep coworker AMR changes isolated.
Push only as clean fast-forward or established replay workflow.
Leave .32/GitHub aligned.
