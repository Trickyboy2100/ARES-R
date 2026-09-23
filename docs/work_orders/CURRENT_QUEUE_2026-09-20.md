# CURRENT QUEUE — 2026-09-23

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed / established

P0 through P3.3 are established sufficiently for the current right-arm A/B demo.

Current field state also includes:
- real CURRENT→A execution;
- real CLEAR A/B motion;
- A/B-specific self-filter handling for gripper residuals;
- A/B-specific tracking threshold experiments;
- successful 0.08 / 0.09 / 0.10 rad/s tests;
- successful 0.20 rad/s B→A and A→B tests with about 9.49 s/leg;
- A/B tracking stop currently tested at 1.5 deg;
- latest local field commit around this speed work is not yet guaranteed to be consolidated/pushed with all P3.4 code.

## Active now

### P3.4 — deployment acceleration

Execute/finish:

~~~text
docs/work_orders/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION.md
~~~

Remaining P3.4 goals:

~~~text
consolidate/push current field changes
→ finish fast camera path
→ finish fast scene pipeline
→ persistent cuRobo planner
→ remove per-request discarded solve
→ choose fast planner profile
→ reconcile A/B-demo-only 0.20 rad/s commissioned profile
→ run fast CLEAR/AVOID with scan-before-each-leg
~~~

P3.4 is not complete until it reports:

~~~text
FAST_CAMERA_PATH_READY
FAST_SCENE_PIPELINE_READY
PERSISTENT_PLANNER_READY
FAST_PLANNER_PROFILE_READY
PLANNER_WARM_P50_S
SCAN_TO_TRAJECTORY_P50_S
AB_SPEED_PROFILE_COMMISSIONED
AB_COMMISSIONED_SPEED_RAD_S
AB_TRACKING_STOP_THRESHOLD_DEG
AB_LEG_DURATION_S
CLEAR_FAST_ROUNDTRIP_EXECUTED
AVOID_FAST_ROUNDTRIP_EXECUTED
~~~

## Next after P3.4

### P3.5 — scene-agnostic fresh-scan obstacle avoidance

Execute:

~~~text
docs/work_orders/2026-09-23_P3_5_SCENE_AGNOSTIC_POINTCLOUD_AVOIDANCE.md
~~~

Purpose:

~~~text
prove runtime is not hard-coded to the current dock/box scene

fresh arbitrary visible scene
→ generic reconstruction
→ cuRobo
→ execute or fail closed
~~~

Validation includes:
- empty scene;
- same box at two NEW arbitrary placements with no coordinates given to software;
- different object;
- multiple objects;
- blocked scene.

A/B may remain fixed; the environment must not be fixed.

## Important demo policy

For the right-arm A/B demo:

~~~text
every leg uses a fresh scan
every point-to-point leg uses cuRobo
no explicit waypoint
no stale SceneSnapshot or trajectory reuse
inactive left arm remains in collision world
~~~

## Speed consistency

Field evidence has now tested 0.20 rad/s successfully for both directions, while older global site config still contains 0.10 rad/s.

Before general deployment, P3.4 must create an explicit RIGHT_AB_DEMO_ONLY versioned profile rather than leaving actual execution and config contradictory.

Do not silently raise unrelated motion modes.

## Recorded later

### P4 — WebUI / Terminal frontend
Start after P3.5 demonstrates scene-agnostic backend behavior.

### P5 — broader throughput/watchdog / reactive upgrades
Keep for deeper general performance work after the static scan-plan-execute demo is reliable.

## User action rule

One physical user action at a time, using the work-order templates.

## Git policy

No force-push.
No coworker AMR dirty changes in this task.
Consolidate .32 field state and leave .32/GitHub aligned.
