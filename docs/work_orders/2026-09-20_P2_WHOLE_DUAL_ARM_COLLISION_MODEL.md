# P2 — Whole dual-arm collision model, self-filter, and mutual-arm avoidance substrate

## 0. Entry gate

P1 is complete and pushed. P1.5 Git realignment must finish first.

Require:

~~~text
DOT32_INTEGRATION_ALIGNED_WITH_GITHUB = YES
WORKTREE_CLEAN_FOR_P2 = YES
~~~

P2 does NOT recalibrate T_body_camera.

No AMR, arm, or gripper motion in P2.

## 1. P2 scope

P2 has three core outcomes:

~~~text
A. whole-robot geometry is correct in BODY
B. robot-owned points can be removed from BODY cloud
C. either arm can be treated as an obstacle for the other arm
~~~

Important distinction:

- P2 DOES include self-filter;
- P2 DOES include dual-arm mutual collision representation/checking;
- P2 does NOT yet run the final physical A↔B avoidance motion;
- P3 performs actual cuRobo planning/execution around real obstacles + inactive arm.

## 2. P2-A — audit and select the production robot/gripper assets

Use current ARES-R and pinned ARES assets first.

Known preferred source:

~~~text
ARES URDF
ARES STL meshes
ARES gripper model
ARES gripper mount relative to link6
ARES cuRobo sphere config
~~~

User/site clarification:

- the ARES gripper 3D model is considered geometrically close/usable;
- the gripper-to-arm-end relative mounting in ARES is considered basically correct;
- therefore ARES gripper geometry is the FIRST candidate for production use, not merely a fallback proxy.

Audit separately:

1. arm kinematics;
2. arm visual mesh;
3. arm collision spheres;
4. gripper visual/collision mesh;
5. gripper mount transform relative to link6;
6. current tool/TCP transform;
7. BODY left/right base transforms;
8. chassis/body geometry.

Classification:

~~~text
VALIDATED_EXISTING_MODEL
VALIDATED_AFTER_SITE_CHECK
CONSERVATIVE_PROXY
MISSING_BLOCKER
~~~

Do not replace validated kinematics just because another online Mini2 mesh exists.

If an external Mini2 model is used, compare joint origin/axis/link length/flange/base/mesh bounds before adopting it.

Output:

~~~text
docs/ROBOT_COLLISION_MODEL_AUDIT_2026-09-20.md
worklog/generated/robot_collision_model_manifest.json
~~~

## 3. P2-B — build one reusable whole-robot BODY geometry exporter

Create a canonical exporter:

~~~text
live/read-only joints
+ BODY arm-base transforms
+ arm link collision geometry
+ gripper/tool geometry
→ left/right BODY robot geometry
~~~

The same geometry source must be used for:

1. viewer overlay;
2. self-filter;
3. inactive-arm obstacle;
4. later cuRobo collision checks.

Do not maintain separate “display-only” and “planning-only” transforms.

Output should contain at minimum:

~~~text
left arm link geometry
left gripper/tool geometry
right arm link geometry
right gripper/tool geometry
base/chassis conservative geometry
central BODY exclusion
geometry revision
joint snapshot revision
tool/TCP revision
~~~

## 4. P2-C — visual overlay gate before filtering

Extend the P1 BODY viewer.

Display:

- raw BODY pointcloud;
- left arm link collision spheres/mesh proxy;
- right arm link collision spheres/mesh proxy;
- left gripper;
- right gripper;
- left/right base frames;
- chassis/body geometry if available;
- BODY central exclusion;
- current joints and geometry revision.

Required screenshot:

~~~text
raw BODY cloud + both arm models + both grippers
~~~

Acceptance:

- visible robot pointcloud should plausibly overlap the robot geometry;
- arm bases must appear in correct BODY positions;
- gripper/tool geometry must be at the correct link6/TCP side;
- no filtering yet.

## 5. P2-D — self-filter using the SAME whole-robot geometry

Self-filter rule:

~~~text
raw BODY cloud
- left arm owned geometry
- right arm owned geometry
- left gripper/tool owned geometry
- right gripper/tool owned geometry
- optional chassis/body owned geometry
= external environment cloud
~~~

No image-space masks and no arbitrary hand-drawn exclusion regions as the production filter.

Use configurable margin and benchmark several values, for example:

~~~text
10 mm
20 mm
30 mm
~~~

Required evidence:

- raw cloud;
- overlay;
- filtered cloud;
- total removed points;
- left-arm removed points;
- right-arm removed points;
- gripper/tool removed points;
- table retention;
- P1 known-box retention;
- box AABB before/after.

Self-filter is considered ready only if robot points are substantially removed while table/box are preserved.

## 6. P2-E — dual-arm mutual avoidance substrate

This phase explicitly covers “双臂互相避障”的 geometry/collision foundation.

V0 policy:

~~~text
active arm:
  planned as a normal 6DoF cuRobo robot

inactive arm:
  live joints
  → BODY geometry
  → converted into active-arm planning world obstacle
~~~

Implement both directions:

~~~text
right active / left inactive obstacle
left active  / right inactive obstacle
~~~

Requirements:

- inactive-arm geometry must update from fresh joint state;
- inactive gripper/tool must also be included;
- active-arm path collision query must detect collision with inactive arm;
- central shared-space / 14 cm exclusion remains represented;
- scene revision changes when inactive arm joint/tool state changes.

## 7. P2-F — offline mutual-arm collision regression

No physical motion.

Create synthetic/offline tests that prove:

1. a known-clear active-arm configuration is collision-free with the inactive arm;
2. a deliberately overlapping active/inactive geometry is detected as collision;
3. moving the inactive-arm joint snapshot changes the obstacle geometry/revision;
4. the gripper participates in collision checking;
5. active-right and active-left paths are symmetric at the contract level.

This is where P2 verifies mutual avoidance logic.

Actual cuRobo A↔B path planning around the inactive arm is deferred to P3.

## 8. P2-G — gripper completeness decision

Because ARES gripper geometry is considered usable, prefer:

~~~text
ARES gripper mesh + mount transform
→ verify against current physical setup/tool/TCP
→ classify VALIDATED_AFTER_SITE_CHECK
~~~

If only the finger opening differs from the physical state, do not throw away the model. Use one of:

- live opening if available;
- conservative maximum-envelope geometry;
- fixed known opening for the selected demo.

Only fall back to a generic gripper box/sphere proxy if the ARES geometry is demonstrably inconsistent.

## 9. Terminal / viewer commands

Read-only commands should include or converge on:

~~~text
robot collision inspect
robot collision show
robot collision compare-arms

scene body-cloud show --robot
scene body-cloud self-filter
scene body-cloud self-filter-show

scene arm-obstacle show right
scene arm-obstacle show left
~~~

Names may follow current ART grammar, but all commands must use the same backend geometry service.

## 10. Performance measurements

Measure separately:

- whole-robot geometry export;
- transform of both arms to BODY;
- self-filter;
- inactive-arm world conversion;
- collision-query preparation.

Do not optimize prematurely, but record p50/p95 if easy to obtain.

## 11. Exit criteria

Report:

~~~text
ROBOT_COLLISION_OVERLAY_READY = YES/NO
ARM_LINK_COLLISION_MODEL_READY = YES/NO
GRIPPER_COLLISION_MODEL_READY = YES/NO
WHOLE_ROBOT_COLLISION_MODEL_READY = YES/NO
SELF_FILTER_READY = YES/NO
INACTIVE_ARM_OBSTACLE_READY = YES/NO
MUTUAL_ARM_COLLISION_CHECK_READY = YES/NO
P3_ALLOWED = YES/NO
~~~

Include:

- asset audit;
- geometry classification table;
- raw/overlay/filtered screenshots;
- self-filter statistics;
- P1 box retention;
- table retention;
- active-right/inactive-left collision regression;
- active-left/inactive-right collision regression;
- gripper collision regression;
- latency;
- tests;
- local commit SHA.

## 12. Push policy

Commit locally on:

~~~text
feat/e2e-v0-integration-20260917
~~~

Then STOP.

Do not push P2 automatically. Return to ChatGPT for review and explicit push instruction.
