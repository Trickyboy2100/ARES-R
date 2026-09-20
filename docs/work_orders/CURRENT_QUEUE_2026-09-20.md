# CURRENT QUEUE — 2026-09-20

This file is the only queue index for the 2026-09-20 BODY-cloud/dual-arm avoidance work.

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed / superseded today

### P0-A — recover Epic hand-eye evidence

The integration branch now contains:

~~~text
7ca1e1a feat(perception): preserve Epic calibration integration
~~~

with:

- left Epic hand-eye UI transcription;
- right Epic hand-eye UI transcription;
- earlier right hand-eye evidence;
- body-camera commissioning code/tests;
- a right-derived T_body_camera already written in config/system.json.

Therefore the generic recovery/search phase is no longer the active task.

Historical order retained:

~~~text
docs/work_orders/2026-09-20_P0_RECOVER_EPIC_HAND_EYE_TO_BODY.md
~~~

## Active now

### P0-B — dual-arm hand-eye semantic cross-check

Execute only:

~~~text
docs/work_orders/2026-09-20_P0B_DUAL_ARM_HANDEYE_CROSSCHECK.md
~~~

Purpose:

~~~text
left Epic hand-eye
+ right Epic hand-eye
+ BODY arm-base transforms
→ independently derive T_body_camera twice
→ prove matrix direction
→ board/table/pointcloud validation
→ decide final COMMISSIONED/CANDIDATE state
~~~

Do not start P1 before P0-B exits with a staged report.

## Recorded next phases

### P1

~~~text
docs/work_orders/2026-09-20_P1_BODY_POINTCLOUD_VIEWER.md
~~~

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

## Old calibration work

The earlier table-edge/base-sweep/targetless/vendor-board work orders remain historical evidence and fallback methods.

They are not active unless P0-B proves the existing Epic hand-eye chain cannot be trusted.

## User action rule

When user input is required, Codex must stop and ask for exactly one simple action using:

~~~text
USER ACTION N
目的：
你现在做：
完成后回复：
安全边界：
~~~

## Current motion boundary

P0-B requires no AMR, arm, or gripper motion.

Do not move hardware unless a later phase explicitly requests and receives authorization.
