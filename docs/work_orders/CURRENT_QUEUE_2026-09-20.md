# CURRENT QUEUE — 2026-09-20

This file is the only queue index for the 2026-09-20 BODY-cloud / dual-arm avoidance work.

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed today

### P0-A — recover Epic hand-eye evidence

Integration branch evidence entered at:

~~~text
7ca1e1a feat(perception): preserve Epic calibration integration
~~~

### P0-B — dual-arm hand-eye semantic cross-check

Completed locally on .32:

~~~text
02a03f23 feat(calibration): cross-check dual-arm Epic hand-eye
~~~

Result:

~~~text
Epic matrix semantic = T_armbase_camera

left/right T_body_camera disagreement:
translation ≈ 0.944 mm
rotation    ≈ 0.722 deg

right-derived production transform retained
state = COMMISSIONED
P1_ALLOWED = YES
~~~

P0-B must be pushed to the integration branch before P1 implementation starts.

## Active now

### P1 — BODY point cloud transform and 3D viewer

Execute:

~~~text
docs/work_orders/2026-09-20_P1_BODY_POINTCLOUD_VIEWER.md
~~~

Purpose:

~~~text
fixed COMMISSIONED T_body_camera
→ CAMERA cloud → BODY cloud
→ board/table validation
→ Open3D BODY-frame snapshot viewer
→ optional adjustable-rate live viewer
→ BODY_POINTCLOUD_READY_FOR_SELF_FILTER
~~~

P1 must not perform self-filter or cuRobo planning.

## Recorded next phases

### P2
~~~text
docs/work_orders/2026-09-20_P2_WHOLE_DUAL_ARM_COLLISION_MODEL.md
~~~

### P3
~~~text
docs/work_orders/2026-09-20_P3_PRODUCTION_POINTCLOUD_CUROBO_DEMO.md
~~~

### P4
~~~text
docs/work_orders/2026-09-20_P4_WEBUI_TERMINAL_FRONTEND.md
~~~

### P5
~~~text
docs/work_orders/2026-09-20_P5_POINTCLOUD_THROUGHPUT_WATCHDOG.md
~~~

## Stage push policy

From P1 onward:

1. Codex finishes one phase;
2. run tests;
3. create a local commit on `feat/e2e-v0-integration-20260917`;
4. STOP and report the local commit SHA, test result, artifacts and blockers;
5. DO NOT push automatically;
6. user returns to ChatGPT for review;
7. only after ChatGPT gives the push instruction should Codex push that phase.

No force-push. No blanket reset/revert.

## User action rule

When physical user input is required, Codex must stop and ask for exactly one simple action:

~~~text
USER ACTION N
目的：
你现在做：
完成后回复：
安全边界：
~~~

One user action at a time.

## Current motion boundary

P1 requires no AMR, arm, or gripper motion.

Do not move hardware unless a later phase explicitly requests and receives authorization.
