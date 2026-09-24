> UPDATE 2026-09-24: implementation is now split into P3.8A audit → P3.8B planning-only Scheme → P3.8C supervised physical execution.
> First execute docs/work_orders/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT.md.
> Owner-confirmed physical sequence is recorded in docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md and supersedes generic placeholders in this older draft where they differ.

# P3.8 — Tray→Groove manipulation Skills + Scheme planning

Date: 2026-09-23

## 0. Entry condition

Do not begin physical pick/place implementation until P3.7 demonstrates arbitrary runtime target motion.

Before implementing, Codex on .32 MUST read the local source order:

~~~text
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

That file is currently a local .32 source and may contain details not present in GitHub planning docs. Preserve its exact semantics when reconciling this work order.

## 1. User-requested manipulation sequence

The next manipulation workflow is:

~~~text
scene-aware move to pregrasp
→ forward approach to grasp point
→ grasp
→ vertical lift
→ scene-aware move to above-place target
→ vertical descend to place target
→ release
→ retreat away
~~~

Key target coordinates/poses must be supplied through interfaces, not hard-coded.

## 2. Separate free-space motion from contact motion

Free-space phases use SceneAwareMotionService:

~~~text
current → pregrasp
lifted object → above-place
retreat / free-space reposition
~~~

Contact/approach phases need explicit manipulation semantics:

~~~text
pregrasp → grasp point
above-place → place point
post-release → retreat
~~~

Do not treat the target object/contact surface as an ordinary obstacle all the way to contact.

Introduce an explicit allowed-contact / target-geometry policy before physical contact execution.

## 3. Initial Skills

Design stable reusable Skills, with exact naming adapted to repo conventions.

Recommended V1:

~~~text
move_free(target, constraints)
approach_linear(target, axis, tolerance)
grasp(profile)
lift_vertical(distance_or_target_z)
move_above_place(target, constraints)
place_linear(target, axis, tolerance)
release(profile)
retreat(axis, distance)
~~~

Each Skill must have:

- typed/versioned inputs;
- preconditions;
- result/status;
- event log;
- failure behavior;
- no hidden hardware coordinates.

## 4. Manipulation target interface

Create a versioned interface that external modules can fill.

Concept:

~~~text
ManipulationTargets:
  pick:
    grasp_pose
    pregrasp_pose optional
    approach_axis
    approach_distance

  place:
    place_pose
    preplace_pose optional
    approach_axis
    approach_distance

  lift:
    distance or target_z

  retreat:
    axis
    distance

  provenance:
    source module
    timestamp
    confidence/revision
~~~

Potential producers later:

- Epic perception;
- 6D pose estimator;
- groove/layout module;
- manual UI;
- LLM/task module;
- learned policy.

P3.8 should define the interfaces even if the first test uses manual/offline target values.

## 5. Scheme

Create a declarative Scheme for the sequence, conceptually:

~~~text
RIGHT_ARM_TRAY_TO_GROOVE_V1:

1 ensure_scene
2 move_free(pregrasp)
3 approach_linear(grasp)
4 grasp
5 lift_vertical
6 move_free(preplace)
7 place_linear(place)
8 release
9 retreat
~~~

The Scheme owns ordering and failure transitions.

The Scheme must not implement:

- pointcloud filtering;
- cuRobo internals;
- JAKA raw commands;
- object-specific obstacle reconstruction.

## 6. Task

The Task selects the Scheme and provides context/targets.

Concept:

~~~text
Task:
  name: tray_to_groove
  arm: right
  scheme: RIGHT_ARM_TRAY_TO_GROOVE_V1
  targets: <ManipulationTargets>
  object/context metadata
~~~

Future long-horizon planning/LLM should compose Tasks/Schemes/Skills rather than generate raw motion code.

## 7. Planning-only simulation first

Before physical grasp:

- run the entire Scheme in planning/simulation mode;
- visualize every key target;
- validate free-space cuRobo legs;
- validate vertical approach/lift/place/retreat geometry;
- report scene reuse/rescan boundaries;
- verify attached-object collision model transition after grasp;
- verify target interfaces can be replaced without editing Scheme code.

## 8. Scene lifecycle across manipulation

Recommended:

~~~text
pregrasp free-space:
  ensure fresh scene

short approach/grasp:
  same bound scene + target/contact semantics

after grasp:
  attachment revision changes
  old trajectory invalid
  robot/tool collision model includes held object

lift:
  constrained motion

move to place:
  scene-aware free-space plan with attached object

after release:
  attachment removed
  motion model revision changes
  old plan invalid
~~~

If base moves between pick/place:

~~~text
base move
→ scene INVALID
→ base settles
→ next free-space move auto scans
~~~

## 9. UI/ART future interface

ART:

~~~text
skill list
skill inspect NAME
scheme list
scheme inspect NAME
task plan tray_to_groove --targets FILE
task preview
task run
task stop
~~~

WebUI:

- show Scheme steps;
- show current/next Skill;
- show supplied pick/place target markers;
- show attached-object state;
- show scene freshness and trajectory.

## 10. Acceptance for P3.8 planning stage

Report:

~~~text
MANIPULATION_TARGET_INTERFACE_READY = YES/NO
SKILL_INTERFACES_READY = YES/NO
TRAY_TO_GROOVE_SCHEME_READY = YES/NO
FREE_SPACE_SKILLS_USE_SCENE_AWARE_MOTION = YES/NO
CONTACT_PHASE_SEMANTICS_DEFINED = YES/NO
ATTACHMENT_LIFECYCLE_DEFINED = YES/NO
FULL_SCHEME_PLANNING_ONLY_PASS = YES/NO
TARGETS_REPLACEABLE_WITHOUT_SCHEME_EDIT = YES/NO
~~~

Do not physically grasp/place until a later explicit execution stage is reviewed.

## 11. Git policy

Small commits.
No force-push.
Keep unrelated AMR work separate.
