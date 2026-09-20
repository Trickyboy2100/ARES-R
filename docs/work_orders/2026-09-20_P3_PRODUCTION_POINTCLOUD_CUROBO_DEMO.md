# P3 — Production pointcloud obstacle extraction → cuRobo A↔B demo

## 0. Entry gates

P2 is complete and pushed:

~~~text
integration HEAD:
a4b3bac3ca8e099168cf26677d24656136406b8c

ROBOT_COLLISION_OVERLAY_READY = YES
ARM_LINK_COLLISION_MODEL_READY = YES
GRIPPER_COLLISION_MODEL_READY = YES
WHOLE_ROBOT_COLLISION_MODEL_READY = YES
SELF_FILTER_READY = YES
INACTIVE_ARM_OBSTACLE_READY = YES
MUTUAL_ARM_COLLISION_CHECK_READY = YES
P3_ALLOWED = YES
~~~

No recalibration of T_body_camera in P3.

## 1. P3-A — clean residual environment cloud without deleting real obstacles

P2 self-filter output still contains sparse floating depth points. Treat this as an environment-cloud quality problem, not a frame-calibration problem.

Implement a conservative residual-cloud cleanup stage after self-filter:

~~~text
BODY raw cloud
→ whole-robot self-filter
→ support/table handling
→ sparse outlier cleanup
→ voxel
→ cluster
→ obstacle geometry
~~~

Preferred filters to evaluate:

1. radius outlier removal;
2. statistical outlier removal;
3. minimum cluster point/voxel count;
4. optional multi-frame persistence for isolated tiny clusters.

Do not apply aggressive filters blindly.

Acceptance requires:

- P1 known box retained;
- table/large fixtures retained as intended;
- small isolated flying points substantially reduced;
- known box AABB center/dims remain within previous hold-out error scale;
- no large “ghost AABB” generated from sparse noise.

Benchmark at least 2-3 conservative parameter sets and select one documented default.

## 2. P3-B — obstacle representation for cuRobo

For V0 production demo use deterministic obstacle geometry:

~~~text
clean residual clusters
→ conservative AABB/cuboid
→ inflation margin
→ SceneSnapshot
→ SceneCompiler
→ cuRobo world
~~~

Do not introduce nvblox/MPC in P3.

Include in the same planning world:

- cleaned real pointcloud obstacles;
- table/known geometry;
- inactive arm live collision geometry;
- inactive gripper/tool;
- chassis/body fixed geometry;
- central BODY exclusion.

Use the P2 recommended 20 mm self-filter margin as the starting point, but obstacle inflation is a separate parameter.

## 3. P3-C — define A/B targets in BODY

Create a versioned target contract:

~~~text
position = [x,y,z] BODY metres

orientation:
  explicit quaternion/RPY
  OR semantic BODY_FORWARD
~~~

If user omits orientation, resolve BODY_FORWARD through a versioned per-arm/tool canonical orientation profile. Do not invent arbitrary Euler angles.

Terminal:

~~~text
target pose set right x y z [roll pitch yaw]
target pose set left  x y z [roll pitch yaw]
target pose show
target pose clear
~~~

For the first demo prefer the arm with the stronger existing real cuRobo execution evidence unless current geometry/clearance favors the other arm.

## 4. P3-D — planning-only A↔B CLEAR / AVOID / BLOCK

Each leg must use a fresh scene:

~~~text
robot settled
→ fresh camera scan
→ CAMERA→BODY
→ self-filter
→ residual cleanup
→ obstacle extraction
→ inactive-arm obstacle
→ fresh SceneSnapshot
→ cuRobo plan
→ preview
~~~

No reuse of a trajectory after a new scan or robot/tool revision.

Three scenes, same A/B pair where practical:

### CLEAR

No obstacle in the corridor.

Expected:

~~~text
plan succeeds
trajectory is relatively direct
~~~

### AVOID

Place a real physical box in the corridor and rescan.

Expected:

~~~text
same goal
plan succeeds
trajectory differs materially from CLEAR
minimum clearance remains positive
~~~

### BLOCK

Place/represent an obstacle configuration that fully blocks the route/goal.

Expected:

~~~text
planning fails safely
no fallback trajectory
~~~

BLOCK may remain planning-only and can be produced with an explicitly labelled synthetic augmentation if a safe physical arrangement is inconvenient.

## 5. P3-E — visualization

Required viewer/preview must show:

- whole dual-arm robot;
- active arm;
- inactive arm as obstacle;
- grippers/tools;
- cleaned BODY cloud;
- obstacle AABBs;
- A and B markers;
- planned TCP path;
- sampled robot states if available;
- minimum clearance;
- scene revision;
- calibration revision;
- geometry revision;
- self-filter margin;
- obstacle inflation;
- scan timestamp.

Generate a side-by-side or comparable CLEAR vs AVOID visualization.

## 6. P3-F — planning timing

Measure separately:

- camera capture;
- CAMERA→BODY;
- self-filter;
- outlier cleanup;
- voxel/cluster/AABB;
- SceneSnapshot/SceneCompiler;
- cuRobo world update;
- cuRobo planning;
- total sense→plan.

Report p50/p95 where enough repetitions are feasible.

P3 does not need to optimize these yet; P5 handles optimization.

## 7. P3-G — supervised real execution gate

Planning-only must pass first.

Only then may P3 request separate user authorization for a single real execution.

Execution requires:

- explicit operator authorization for that one motion;
- fresh start state;
- same scene revision used for planning;
- T_body_camera revision match;
- robot geometry revision match;
- inactive-arm revision match;
- tool/TCP revision match;
- commissioned speed profile;
- SafetyPermit;
- physical E-stop available;
- no planner fallback;
- no automatic retry.

First real demo should be sequential, one active arm at a time.

## 8. User-action policy

When a physical obstacle placement is needed, ask exactly one action.

Example:

~~~text
USER ACTION 1
目的：采集真实 AVOID 场景。
你现在做：把 P1 使用的规则盒子放到 A→B 直线路径中间，保持机器人不动。
完成后回复：已放置。
安全边界：不移动底盘、机械臂或夹爪。
~~~

## 9. Exit criteria

Planning-only stage report:

~~~text
RESIDUAL_CLOUD_CLEANUP_READY = YES/NO
REAL_OBSTACLE_SCENE_READY = YES/NO
CLEAR_PLAN_READY = YES/NO
AVOID_PLAN_READY = YES/NO
BLOCK_PLAN_READY = YES/NO
READY_FOR_SUPERVISED_CLEAR = YES/NO
READY_FOR_SUPERVISED_AVOID = YES/NO
~~~

Include:

- outlier filter comparison;
- known-box retention after cleanup;
- CLEAR/AVOID/BLOCK planner result;
- path deviation CLEAR→AVOID;
- minimum clearance;
- timing;
- screenshots;
- tests;
- local commit SHA.

## 10. Push policy

Commit locally on:

~~~text
feat/e2e-v0-integration-20260917
~~~

Then STOP.

Do not push P3 automatically. Return to ChatGPT for review and explicit push/execution instruction.
