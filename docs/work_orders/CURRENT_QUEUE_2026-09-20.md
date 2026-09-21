# CURRENT QUEUE — 2026-09-21

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed and pushed

### P0 — BODY-camera calibration
Completed.

### P1 — BODY pointcloud + viewer
Completed.

### P1.5 — .32 Git realignment
Completed.

### P2 — whole dual-arm collision model + self-filter + mutual-arm substrate
Completed.

### P3 checkpoint
GitHub integration branch currently includes:

~~~text
eafae083cc03f61c6b7162ea90130ce798b8cac6
feat(perception): add P3 production scene planning audit
~~~

## Current local checkpoint awaiting push

### P3.1 — residual attribution + support/object decomposition

Local .32 commit:

~~~text
7ae26aacb86222263d76490e3ec9cc55e9867de6
~~~

Before push:

- verify whether eafae083 is an ancestor of 7ae26aac;
- if yes, fast-forward push 7ae26aac;
- if not, replay only the P3.1 patch on top of eafae083 and test;
- no force-push;
- no unrelated AMR dirty work.

P3.1 planning-only result is successful:

~~~text
CLEAR_PLAN_READY = YES
AVOID_PLAN_READY = YES
BLOCK_PLAN_READY = YES
~~~

Physical execution remains blocked by unresolved tool/TCP physical semantics.

## Active after P3.1 push

### P3.2 — right-arm scan-before-each-leg A↔B demo, planning/commissioning stage

Execute:

~~~text
docs/work_orders/2026-09-21_P3_2_SUPERVISED_AB_SCAN_AVOID_DEMO.md
~~~

User-requested semantics:

~~~text
right TCP shuttles between A and B

before every leg:
  fresh scan + fresh robot/tool state

if straight corridor clear:
  true Cartesian TCP straight path

if blocked:
  cuRobo OVERHEAD bypass

after arrival:
  invalidate old scene and trajectory
  rescan before the next leg
~~~

User-requested A/B redesign:

- larger BODY-left/right span;
- lower endpoints;
- X/Z approximately equal;
- CLEAR visibly straight;
- AVOID visibly arcs upward.

## Tool/TCP physical-length note

Manual measurement on 2026-09-21:

~~~text
right flange mounting plane → approximate grasp center ≈ 145 mm
~~~

Existing controller TCP Z is about 184 mm; pinned gripper model distal extent is about 149 mm.

This discrepancy is recorded but explicitly deferred for the current P3.2 planning-only phase.

Therefore:

~~~text
TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED = YES
READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION = NO
~~~

P3.2 may redesign A/B, implement straight/overhead planning, classifier and demo state machine, but must not execute physical arm motion.

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

Physical arm motion is NOT authorized in the current phase.
