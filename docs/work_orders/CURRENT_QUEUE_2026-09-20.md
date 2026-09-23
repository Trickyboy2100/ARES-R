# CURRENT QUEUE — 2026-09-23

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Established today

P3.6 has now demonstrated the corrected scene-aware control path in real execution:

~~~text
fresh Pixel Pro scan
→ generic scene reconstruction
→ new SceneSnapshot
→ SceneAwareMotionService
→ cuRobo
→ hard-only validation
→ real right-arm execution
~~~

D1 arbitrary-obstacle execution succeeded without manual obstacle coordinates or box/dock special cases.

Important distinction:

~~~text
ENVIRONMENT is already fresh-scene / generic.
TARGETS are still temporarily using the fixed A/B regression client.
~~~

The next task is therefore TARGET GENERALIZATION, not more fixed-A/B random-box testing.

## Architecture documents

Read:

~~~text
docs/architecture/2026-09-23_SCENE_AWARE_MOTION_STACK.md
docs/architecture/2026-09-23_ARBITRARY_TARGET_SKILL_SCHEME_STACK.md
~~~

Core hierarchy:

~~~text
Task / LLM
→ Scheme
→ Skills
→ SceneAwareMotionService
→ LocalSceneService + cuRobo
→ hard execution authority
→ JAKA
~~~

Obstacle avoidance is a low-level motion capability.

## Active now

### P3.7 — Arbitrary-target Scene-Aware Motion

Execute:

~~~text
docs/work_orders/2026-09-23_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION.md
~~~

Goal:

~~~text
after any base/scene change
→ fresh scan
→ generic local collision world
→ arbitrary runtime BODY target P/Q
→ cuRobo
→ execute
~~~

No fixed A/B dependence is allowed in the generic motion service.

A/B remains only a regression/demo preset.

Default orientation for the next demo:

~~~text
LEVEL_YAW_FREE

TCP/gripper remains level relative to the BODY horizontal plane.
Roll/pitch level condition remains constrained.
Yaw about BODY +Z may vary during planning.
~~~

Optional:

~~~text
LEVEL_YAW_TARGET
~~~

for an upstream-specified final yaw.

## P3.7 demo

Use runtime target points P/Q/R that are NOT loaded from A/B config.

At least one arbitrary obstacle scene must cause a meaningful cuRobo detour between runtime-selected targets.

The demo should prove:

~~~text
new scene + arbitrary target pair
not
new scene + fixed A/B
~~~

ART and minimal UI must both expose arbitrary target input.

## Next recorded step

### P3.8 — Tray→Groove manipulation Skills + Scheme

Execute only after P3.7 arbitrary-target motion passes:

~~~text
docs/work_orders/2026-09-23_P3_8_TRAY_TO_GROOVE_SKILL_SCHEME.md
~~~

Before implementing P3.8, Codex on .32 must read:

~~~text
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

That source file is local .32 material and is not currently available from the GitHub planning branch.

User-requested sequence to record now:

~~~text
scene-aware move to pregrasp
→ forward approach to grasp point
→ grasp
→ vertical lift
→ scene-aware move to above-place target
→ vertical descend
→ release
→ retreat
~~~

Key coordinates/poses must be supplied through interfaces by perception/task modules, not hard-coded in the Scheme.

Initial Skill candidates:

~~~text
move_free
approach_linear
grasp
lift_vertical
move_above_place
place_linear
release
retreat
~~~

The Scheme owns ordering.
Skills own reusable manipulation semantics.
SceneAwareMotionService owns free-space collision-aware motion.
Task/LLM supplies context and semantic targets.

## UI

Use:

~~~text
docs/work_orders/2026-09-23_P4_SCENE_AWARE_WEBUI.md
~~~

The main Motion UI must support arbitrary runtime BODY target points/poses and LEVEL_YAW_FREE / LEVEL_YAW_TARGET.

A/B belongs only in a Demo/Regression panel.

## Git policy

No force-push.
Preserve coworker AMR dirty changes separately.
Use small commits.
After validated subphases, fast-forward only if remote HEAD remains compatible.
Leave .32 and GitHub aligned.
