# P3.1 — Residual attribution + support/object decomposition + fresh CLEAR/AVOID recovery

Date: 2026-09-21

## 0. Why this phase exists

P3 planning-only produced a useful fail-closed checkpoint:

- residual cleanup works;
- fresh SceneSnapshot/SceneCompiler chain works;
- BLOCK fails safely with no fallback;
- CLEAR/AVOID still fail because:
  1. a repeatable robot-adjacent residual overlaps the active-arm start state by about 24.6 mm;
  2. the upright box and irregular dock/support structure merge into one large solid AABB, destroying real free space.

Do not jump to nvblox yet. First resolve these two geometry issues with the current deterministic pipeline.

## 1. Entry condition

Expected integration branch before P3.1:

~~~text
a4b3bac3ca8e099168cf26677d24656136406b8c
+ P3 checkpoint commit eafae083cc03f61c6b7162ea90130ce798b8cac6 after review/push
~~~

P3.1 is planning-only. No AMR/arm/gripper motion.

Camera capture and read-only robot state are allowed.

## 2. P3.1-A — explain the robot-adjacent residual, do not hide it

Reproduce the start-state collision on a fresh stationary scene.

For every residual cluster near the active arm:

1. compute nearest distance to:
   - exact active-arm planning collision geometry;
   - P2 OBB/self-filter geometry;
   - gripper/tool geometry;
   - chassis/body geometry;
2. label the nearest owning link/primitive;
3. render the raw BODY cloud, P2 filter geometry and the exact planning collision geometry together;
4. report whether the residual is caused by:
   - geometry mismatch between self-filter and planner;
   - stale/misaligned joint snapshot;
   - tool/TCP revision mismatch;
   - pointcloud noise/edge reflection;
   - missing robot-owned geometry;
   - genuine external obstacle.

Do NOT fix the problem by globally increasing the self-filter margin.

### Preferred correction

If the residual is robot-owned because planner geometry extends outside the P2 self-filter geometry, create one canonical ROBOT_OWNED_FILTER geometry derived from the UNION/SUPERSET of the validated robot geometry and the exact planning collision geometry, with an explicit sensor margin.

The same revision/provenance must be visible in:

- overlay;
- self-filter;
- planning scene.

Acceptance:

~~~text
fresh CLEAR start clearance > 0
known box retained
table retained
no arbitrary obstacle deletion
~~~

## 3. P3.1-B — generic support-surface / protruding-object decomposition

Goal: avoid turning a connected table/dock/box/cabinet structure into one solid AABB.

Implement a generic, scene-derived decomposition; do not hard-code this specific dock.

Pipeline:

~~~text
clean residual cloud
→ detect dominant support planes/surfaces in BODY
→ classify thin support slabs / structural surfaces
→ compute local height above support
→ cluster protruding components above support
→ split large connected residuals by height slices / spatial components
→ emit multiple conservative primitives instead of one cluster-wide AABB
~~~

### Required semantics

At minimum represent:

~~~text
SUPPORT_SURFACE
STRUCTURE
PROTRUDING_OBSTACLE
UNKNOWN_OCCUPIED
TARGET_FREE_VOLUME (future contract only; do not subtract unseen space)
~~~

For this phase, do not invent free space behind occlusions.

### Current demo expectation

The upright box should separate from the irregular dock/support structure.

The dock/support structure may remain represented by multiple conservative primitives, but its recesses/openings must not automatically be filled by one giant AABB if observed free-space evidence exists.

## 4. P3.1-C — multi-primitive obstacle output

Keep current SceneCompiler compatibility.

Preferred V0 output:

~~~text
one physical connected cluster
→ N small AABB/cuboid primitives
~~~

Use conservative inflation per primitive.

Do not require OBB support to finish P3.1.

Record:

- number of primitives;
- total occupied volume;
- comparison against old single-AABB occupied volume;
- preserved corridor/opening widths where observable.

The current single-AABB result stays available as a fail-closed baseline/comparator.

## 5. P3.1-D — cleanup of sparse flying points

Retain the conservative P3 cleanup baseline.

Compare only a few safe parameter sets for:

- radius outlier removal;
- statistical outlier removal;
- minimum cluster voxel count.

Acceptance:

- sparse floating noise substantially reduced;
- known box retained;
- support/dock retained;
- no large ghost obstacle primitive from tiny noise.

Do not optimize for visual cleanliness alone.

## 6. P3.1-E — fresh CLEAR / AVOID / BLOCK recovery

After A-D pass, use fresh camera capture and fresh robot state for every scene.

### CLEAR

Same A/B target pair where possible.

Require:

- start clearance > 0;
- goal clearance > 0;
- plan succeeds;
- no residual robot-owned obstacle intersecting the start.

### AVOID

Ask user for one physical action only when ready:

~~~text
USER ACTION 1
目的：采集真实 AVOID 场景。
你现在做：把规则盒子放到 A→B 直线路径中间，保持机器人、底盘、双臂和夹爪不动。
完成后回复：已放置。
安全边界：不要移动机器人。
~~~

Require:

- same/freshly defined A/B contract;
- box is a separate obstacle primitive from dock/support;
- plan succeeds;
- path differs materially from CLEAR;
- positive minimum clearance.

### BLOCK

May reuse explicit provenance-labelled synthetic enclosure for fail-closed regression.

No fallback.

## 7. P3.1-F — visualization

Generate comparable views for:

1. raw/self-filtered/clean residual cloud;
2. old single-AABB baseline;
3. support/object decomposition;
4. multi-primitive world;
5. CLEAR path;
6. AVOID path.

Viewer should show:

- BODY axes;
- whole dual-arm model;
- inactive arm;
- table/support;
- dock structure;
- box obstacle;
- A/B;
- trajectory;
- minimum clearance;
- scene/calibration/geometry revisions.

## 8. P3.1-G — timing

Measure:

- capture;
- CAMERA→BODY;
- self-filter;
- residual cleanup;
- support segmentation;
- decomposition;
- primitive generation;
- SceneCompiler;
- cuRobo planning;
- total sense→plan.

No performance optimization beyond obvious bugs.

## 9. Exit gates

Report:

~~~text
ROBOT_ADJACENT_RESIDUAL_EXPLAINED = YES/NO
ROBOT_OWNED_FILTER_READY = YES/NO
SUPPORT_OBJECT_DECOMPOSITION_READY = YES/NO
MULTI_PRIMITIVE_OBSTACLE_WORLD_READY = YES/NO
CLEAR_PLAN_READY = YES/NO
AVOID_PLAN_READY = YES/NO
BLOCK_PLAN_READY = YES/NO
READY_FOR_SUPERVISED_CLEAR = YES/NO
READY_FOR_SUPERVISED_AVOID = YES/NO
~~~

Include:

- residual root cause;
- before/after start clearance;
- box-vs-dock separation evidence;
- old AABB vs multi-primitive occupied volume;
- CLEAR/AVOID path comparison;
- minimum clearances;
- timing;
- tests;
- local commit SHA.

## 10. Future route after P3.1

Do not implement in this phase, but preserve the architecture path:

~~~text
generic support/object decomposition
→ multi-AABB/OBB/convex debug world
→ hybrid known geometry + voxel/ESDF
→ nvblox/WorldBloxCollision
→ scene watchdog / reactive replanning
~~~

For cabinet/dock insertion tasks, later add explicit observed opening/pocket semantics. Never mark occluded unseen volume as free only because a task wants to enter it.

## 11. Push/execution policy

Commit locally on:

~~~text
feat/e2e-v0-integration-20260917
~~~

Then STOP.

Do not push automatically.
Do not execute arm motion.
Return to ChatGPT for review.
