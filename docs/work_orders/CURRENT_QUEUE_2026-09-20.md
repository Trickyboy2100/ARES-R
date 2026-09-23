# CURRENT QUEUE — 2026-09-23

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Established

P0–P3.4 have established the current physical substrate:

- commissioned CAMERA→BODY;
- BODY pointcloud and whole dual-arm geometry;
- robot-owned self-filter;
- generic support/object multi-primitive scene;
- fresh SceneSnapshot planning;
- persistent cuRobo runtime;
- real right-arm CLEAR execution;
- real A/B speed commissioning up to the current demo profile;
- P3.5 S0 fresh-scene planning-only and S1 random obstacle scan/planning evidence.

Current integration GitHub HEAD observed during redesign:

~~~text
d7c9428bf1b66b796eebe701bfbb846e4fba9621
~~~

## Architecture correction

The next step is NOT to continue adding random-box cases through the old A/B-specific post-planning gate.

Read:

~~~text
docs/architecture/2026-09-23_SCENE_AWARE_MOTION_STACK.md
~~~

Key correction:

~~~text
obstacle avoidance belongs to the low-level Scene-Aware Motion layer

task/skill/LLM
→ goal + constraints
→ ensure fresh local scene
→ cuRobo collision-aware planning
→ hard execution validation
→ JAKA
~~~

Planner preferred clearance belongs inside cuRobo/planner policy.

Independent/SafetyKernel validation remains for hard collision validity, stale binding, dynamics, controller state and execution authority; it must not act as a second demo-specific trajectory optimizer.

## Active now

### P3.6 — Scene-Aware Motion control-layer refactor

Execute:

~~~text
docs/work_orders/2026-09-23_P3_6_SCENE_AWARE_MOTION_CONTROL.md
~~~

Main order:

~~~text
preserve current field state
→ LocalSceneService
→ base-motion scene invalidation
→ generic SceneAwareMotionService
→ reusable planner constraints
→ correct planner-clearance vs hard-validation layering
→ start-near-obstacle escape semantics
→ migrate A/B demo to generic motion client
→ arbitrary-obstacle physical demo
→ minimal scene-aware UI
~~~

P3.5 is retained as evidence/test design but its old execution path is superseded by P3.6.

## Required mobile-manipulation behavior

~~~text
AMR starts moving
→ current local scene INVALID

AMR settles
→ base_pose_revision increments
→ SCENE REQUIRED

next arm motion request
→ automatic fresh Pixel Pro scan
→ generic local world
→ cuRobo plan
→ hard validation
→ execute
~~~

Higher-level tasks must not manually manage obstacle geometry.

## Demo after refactor

Use A/B only as convenient target poses.

The demo must prove:

~~~text
arbitrary visible obstacle placement
→ no coordinate given to software
→ fresh pointcloud scan
→ generic collision world
→ cuRobo avoidance
→ execute

move obstacle elsewhere
→ old scene/plan stale
→ fresh scan
→ different fresh plan
→ execute
~~~

No object-specific avoidance code.

## UI after backend correction

Use:

~~~text
docs/work_orders/2026-09-23_P4_SCENE_AWARE_WEBUI.md
~~~

The old 2026-09-20 P4 draft is superseded.

UI priorities:

- BODY 3D pointcloud + collision primitives + robot + target + trajectory;
- BASE/SCENE/PLANNER/EXECUTION state ribbon;
- scene epoch/base pose revision/freshness;
- generic MotionRequest panel;
- planner constraints panel;
- task/demo convenience clients;
- embedded ART using the same backend.

No browser hardware API.

## Git policy

No force-push.
Preserve coworker AMR dirty changes separately.
Use small commits.
After validated subphases, fast-forward only if remote HEAD remains compatible.
Leave .32 and GitHub aligned.
