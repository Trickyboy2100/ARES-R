# CURRENT QUEUE — 2026-09-22

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

### P3 / P3.1 — production pointcloud planning substrate
Completed and pushed.

### P3.2 — cuRobo-only A/B planning checkpoint
Completed and pushed.

GitHub integration HEAD:

~~~text
d258c30476868b2789c1cd61ac5c402a93b5ebf6
~~~

Canonical operator overrides now locked for this demo:

~~~text
1. CURRENT→A, A→B and B→A all use cuRobo.
2. No explicit waypoint is allowed.
3. CLEAR/AVOID both use one direct cuRobo start→goal request.
4. The operator visually approved the current trajectory style.
~~~

Current A/B:

~~~text
A BODY TCP = [0.710, -0.600, 1.000] m
B BODY TCP = [0.710, -0.130, 1.000] m
lateral span = 0.470 m
~~~

Planning-only checkpoint:

~~~text
CLEAR both directions = SUCCESS
AVOID both directions = SUCCESS
BLOCK = expected FAILURE / no fallback

AVOID path rises about 155 mm above endpoints.
CLEAR-vs-AVOID max TCP separation about 202–204 mm.
~~~

Physical execution remains disabled.

## Active now

### P3.3 — execution hardening for the approved cuRobo-only A/B demo

Execute:

~~~text
docs/work_orders/2026-09-22_P3_3_EXECUTION_HARDENING.md
~~~

Purpose:

~~~text
FAST LANE P3.3A:
  get first supervised CLEAR motion ready today
  CURRENT→A → fresh A→B CLEAR → fresh B→A CLEAR

then P3.3B:
  harden AVOID repeatability
~~~

Main hardening:
- preserve approved A/B and cuRobo-only/no-waypoint policy;
- reconcile physical gripper geometry;
- package selected path for native ServoJ;
- bind fresh scene/start/tool lease;
- SafetyKernel dry-run;
- request-readiness for first supervised CURRENT→A motion.

No hardware movement in P3.3.

## Tool/TCP note

Current evidence:

~~~text
manual flange→grasp center ≈ 145 mm
pinned ARES gripper distal extent ≈ 149 mm
controller active TCP Z ≈ 184 mm
~~~

Do not change controller TCP in P3.3.

The manual physical grasp-center measurement (~145 mm) agrees closely with the pinned ARES gripper distal extent (~149 mm). For this movement-only demo, the pinned gripper remains the physical collision body; the controller TCP at ~184 mm is treated as a task frame unless physical material is observed there.

Do not invent collision geometry solely to fill a virtual TCP offset. The semantic difference remains documented.

## Execution blocker observed in P3.2

Same frozen AVOID scene produced modeled minimum clearance ranging from about:

~~~text
35.4 mm
to
9.3 mm
~~~

Repeat planning success alone is not an execution certificate.

P3.3 must establish a repeatable modeled-clearance gate before any motion request.

## Recorded next

### First supervised physical demo
Only after P3.3 review and a separate explicit user authorization.

Expected order:

~~~text
CURRENT→A
→ fresh scan
→ A→B
→ fresh scan
→ B→A
~~~

Every leg uses new cuRobo planning and no explicit waypoint.

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

P3.3 may capture camera and read robot state.

AMR/arm/gripper motion is NOT authorized in P3.3.
