# CURRENT QUEUE — 2026-09-21

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed and pushed

### P0 — BODY-camera calibration
Completed. Production T_body_camera is COMMISSIONED.

### P1 — BODY pointcloud + viewer
Pushed.

### P1.5 — .32 Git realignment
Completed.

### P2 — whole dual-arm collision model + self-filter + mutual-arm substrate

Pushed at:

~~~text
a4b3bac3ca8e099168cf26677d24656136406b8c
feat(perception): add whole dual-arm collision substrate
~~~

## Current checkpoint awaiting push

### P3 planning-only checkpoint

Local commit on .32:

~~~text
eafae083cc03f61c6b7162ea90130ce798b8cac6
~~~

Result:

~~~text
RESIDUAL_CLOUD_CLEANUP_READY = TRUE
REAL_OBSTACLE_SCENE_READY = TRUE_WITH_CONSERVATIVE_AABB_LIMITATION
CLEAR_PLAN_READY = FALSE
AVOID_PLAN_READY = FALSE
BLOCK_PLAN_READY = TRUE
READY_FOR_SUPERVISED_CLEAR = FALSE
READY_FOR_SUPERVISED_AVOID = FALSE
~~~

This checkpoint is valuable and should be pushed after verifying it is a clean fast-forward from a4b3bac3 and excludes unrelated AMR dirty work.

## Active after checkpoint push

### P3.1 — residual attribution + support/object decomposition + fresh CLEAR/AVOID recovery

Execute:

~~~text
docs/work_orders/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION.md
~~~

Order:

~~~text
explain robot-adjacent residual
→ align self-filter ownership with exact planning geometry
→ generic support-surface / protruding-object decomposition
→ multi-primitive AABB world
→ sparse outlier cleanup validation
→ fresh CLEAR
→ real-box AVOID
→ BLOCK regression
→ supervised execution go/no-go
~~~

Do not jump directly to nvblox/MPC in P3.1.

## Recorded next

### P4
~~~text
docs/work_orders/2026-09-20_P4_WEBUI_TERMINAL_FRONTEND.md
~~~

### P5
~~~text
docs/work_orders/2026-09-20_P5_POINTCLOUD_THROUGHPUT_WATCHDOG.md
~~~

## Stage push policy

1. finish phase;
2. run tests;
3. local commit;
4. STOP and report;
5. do not push automatically;
6. user returns to ChatGPT;
7. push/execution only after review.

No force-push. No blanket reset/revert.

## User action rule

When physical user input is required, ask exactly one action:

~~~text
USER ACTION N
目的：
你现在做：
完成后回复：
安全边界：
~~~

## Current motion boundary

P3/P3.1 may capture camera and read robot state.

AMR/arm/gripper motion requires separate explicit authorization.
