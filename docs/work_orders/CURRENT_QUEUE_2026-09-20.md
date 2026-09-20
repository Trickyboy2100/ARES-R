# CURRENT QUEUE — 2026-09-20

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed and pushed

### P0 — BODY-camera calibration

Completed. Production T_body_camera is COMMISSIONED.

### P1 — BODY pointcloud + viewer

Pushed at:

~~~text
c5ed44515cbe4d5e298f74117f4ac02bbccb3f20
~~~

### P1.5 — .32 Git realignment

Completed.

~~~text
DOT32_INTEGRATION_ALIGNED_WITH_GITHUB = YES
WORKTREE_CLEAN_FOR_P2 = YES
~~~

### P2 — whole dual-arm collision model + self-filter + mutual-arm substrate

Pushed at:

~~~text
a4b3bac3ca8e099168cf26677d24656136406b8c
feat(perception): add whole dual-arm collision substrate
~~~

Result:

~~~text
ROBOT_COLLISION_OVERLAY_READY = YES
ARM_LINK_COLLISION_MODEL_READY = YES
GRIPPER_COLLISION_MODEL_READY = YES
WHOLE_ROBOT_COLLISION_MODEL_READY = YES
SELF_FILTER_READY = YES
INACTIVE_ARM_OBSTACLE_READY = YES
MUTUAL_ARM_COLLISION_CHECK_READY = YES
P3_ALLOWED = YES
~~~

## Active now

### P3 — residual environment cleanup → real obstacle cuRobo A↔B demo

Execute:

~~~text
docs/work_orders/2026-09-20_P3_PRODUCTION_POINTCLOUD_CUROBO_DEMO.md
~~~

Order inside P3:

~~~text
residual-cloud sparse-outlier cleanup
→ stable obstacle AABB extraction
→ inactive arm + table + real obstacle world
→ BODY target A/B contract
→ CLEAR planning-only
→ real-box AVOID planning-only
→ BLOCK planning-only
→ timing + visualization
→ supervised execution go/no-go
~~~

Do not execute a physical arm motion until planning-only results are reviewed and separately authorized.

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

P3 planning-only may capture the camera and read robot state.

AMR/arm/gripper motion still requires separate explicit authorization.
