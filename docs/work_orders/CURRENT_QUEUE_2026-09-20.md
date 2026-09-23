# CURRENT QUEUE — 2026-09-23

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed / established

### P0 — BODY-camera calibration
Completed.

### P1 — BODY pointcloud + viewer
Completed.

### P1.5 — .32 Git realignment
Completed.

### P2 — whole dual-arm collision model + self-filter + mutual-arm substrate
Completed.

### P3 / P3.1 — production pointcloud planning substrate
Completed.

### P3.2 — cuRobo-only A/B planning checkpoint
Completed.

### P3.3 / P3.3A — execution hardening + first physical CLEAR evidence
Partially completed in the field.

Field results now include:

- real CURRENT→A execution;
- at least one successful B→A CLEAR leg;
- one A→B abort on A/B tracking threshold;
- A/B-specific self-filter adjustment for gripper residuals;
- A/B-specific tracking-stop adjustment experiments;
- bounded background CLEAR loop runner;
- current local field commits not all yet consolidated/pushed.

Do not restart P3.3 design work unless needed by P3.4.

## Active now

### P3.4 — same-day deployment acceleration

Execute:

~~~text
docs/work_orders/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION.md
~~~

Today's goal:

~~~text
reduce scan→scene latency
→ remove planner cold-start/redundant solve overhead
→ persistent cuRobo planner
→ benchmark/choose fast planner profile
→ commission faster A/B-only joint speed up to site ceiling
→ 2–3 fast CLEAR round trips
→ real-box fast AVOID round trip if stable
~~~

Target operating behavior remains:

- every leg fresh scan / fresh scene;
- every point-to-point leg uses cuRobo;
- no explicit waypoint;
- A/B unchanged unless a real feasibility issue requires change;
- right-arm only for this demo;
- inactive left arm remains part of collision world.

## Current measured bottlenecks

Approximate recent values:

~~~text
camera + scene prep: ~15.2 s
cuRobo request→result: ~54–57 s
  including one discarded warm-up solve + one formal solve
formal cuRobo solve: ~19 s
A/B motion around 0.07 rad/s: ~25 s / leg
~~~

P3.4 should attack these directly.

## Physical speed policy for P3.4

The site ceiling remains:

~~~text
max joint velocity = 0.10 rad/s
max joint acceleration = 0.20 rad/s²
~~~

P3.4 may commission an A/B-DEMO-ONLY faster profile up to this ceiling.

Tracking-stop threshold may be tuned only for the A/B demo and must remain an explicit logged setting. Do not alter controller estop/collision/limit protections or unrelated motion modes.

## User actions

Codex asks one physical action at a time using the format in the P3.4 work order.

First expected action:

~~~text
USER ACTION 1
“CLEAR速度测试现场已就绪”
~~~

After that confirmation Codex may run the predefined right-arm speed ladder automatically until a failure/abort condition.

## Recorded next

### P4 — WebUI / Terminal frontend
Do not start until P3.4 produces a responsive deployed backend.

### P5 — broader throughput/watchdog optimization
P3.4 may implement the highest-value same-day optimizations. P5 remains for deeper/general performance work.

## Git policy

P3.4 first preserves/consolidates the .32 local field state.

No force-push.
No unrelated AMR dirty changes.
Leave .32/GitHub aligned at the end of the day.
