# CURRENT QUEUE — 2026-09-21

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed and pushed

### P0 — BODY-camera calibration
Completed.

### P1 — BODY pointcloud + viewer
Completed and pushed.

### P1.5 — .32 Git realignment
Completed.

### P2 — whole dual-arm collision model + self-filter + mutual-arm substrate
Completed and pushed.

## Current local checkpoint awaiting push

### P3.1 — residual attribution + support/object decomposition

Local commit on .32:

~~~text
7ae26aacb86222263d76490e3ec9cc55e9867de6
~~~

Planning-only result:

~~~text
ROBOT_ADJACENT_RESIDUAL_EXPLAINED = YES
ROBOT_OWNED_FILTER_READY = YES
SUPPORT_OBJECT_DECOMPOSITION_READY = YES
MULTI_PRIMITIVE_OBSTACLE_WORLD_READY = YES
CLEAR_PLAN_READY = YES
AVOID_PLAN_READY = YES
BLOCK_PLAN_READY = YES

READY_FOR_SUPERVISED_CLEAR = NO
READY_FOR_SUPERVISED_AVOID = NO
~~~

Reason physical execution remains blocked:

~~~text
right controller TCP is ~35 mm beyond the pinned gripper collision envelope
observed-box modeled AVOID clearance is only ~9.63 mm
~~~

Push P3.1 after verifying it is a clean fast-forward from the current GitHub integration branch and excludes unrelated AMR dirty work.

## Active after P3.1 push

### P3.2 — supervised scan-before-each-leg A↔B demo commissioning

Execute:

~~~text
docs/work_orders/2026-09-21_P3_2_SUPERVISED_AB_SCAN_AVOID_DEMO.md
~~~

Desired demo semantics:

~~~text
right TCP at A or B
→ fresh scan before every leg

if straight corridor CLEAR:
    execute validated Cartesian straight line

if straight corridor BLOCKED:
    cuRobo OVERHEAD bypass around observed obstacle

arrive
→ invalidate old scene/trajectory
→ next leg rescans and re-decides
~~~

User-requested target redesign:

- larger left/right BODY span;
- both A/B lower;
- clear path visibly straight;
- obstacle-present path visibly arcs upward.

First gate in P3.2 is physical right-tool/TCP collision commissioning.

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

P3.2 planning/commissioning may capture camera and read robot state.

Physical arm motion requires a separate explicit one-time authorization after the P3.2 planning/commissioning gates pass.
