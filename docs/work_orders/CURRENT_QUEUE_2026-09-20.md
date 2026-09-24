# CURRENT QUEUE — 2026-09-24

## Established

P3.7 arbitrary-target scene-aware motion is complete and pushed on the integration branch.

Current integration GitHub HEAD:

~~~text
d19cea78ffe3664fbf36423b6a6f80f371918de5
docs(p3.7): record arbitrary target obstacle roundtrip
~~~

P3.7 established:

- fresh-scene generic obstacle world;
- arbitrary runtime BODY targets;
- LEVEL_YAW_FREE;
- ART + WebUI target input;
- real obstacle-crossing execution;
- no fixed A/B dependence in the low-level motion service.

## Active now

### P3.8A — Tray→Groove system/interface audit

Read:

~~~text
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
docs/work_orders/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT.md
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

Goal:

~~~text
prepare the real customer staged pickup/place demo
without moving either arm or either gripper
~~~

Allowed after one USER ACTION:

- bounded AMR relative movement;
- AMR stop;
- Epic 5700 detection;
- Pixel Pro 5000 pointcloud;
- ART/WebUI/backend services;
- read-only JAKA/gripper state;
- planning-only IK/cuRobo for either arm.

Forbidden in P3.8A:

- JAKA arm motion;
- ServoJ enable;
- gripper motion;
- physical grasp/lift/place.

## Owner-confirmed staged demo

~~~text
right arm presentation/up posture + gripper 50%
→ AMR ~0.30 m to pickup-side base pose
→ Epic 5700 物料抓取
→ configurable pregrasp 0.03–0.05 m
→ scene-aware move to pregrasp
→ contact approach to detected grasp pose
→ grasp
→ local 10–20 cm TCP-neighborhood rescan/change check
→ attach object model
→ lift to BODY z≈1.20 m
→ move to right-front visibility-clear region
→ AMR ~0.40 m toward robot-right
→ Epic 5700 物料放置最右点
→ scene-aware move above placement
→ vertical descent to detected target +5 mm
→ gripper 20%
→ retreat arm
→ retreat base
→ verify complete
~~~

Key coordinates/poses are interfaces, not Scheme literals.

## Important architecture

~~~text
Task
→ Scheme
→ Skills
→ SceneAwareMotionService
→ LocalSceneService + cuRobo
→ hard execution authority
→ robot
~~~

Obstacle avoidance is NOT a Skill.

Free-space Skills inherit fresh pointcloud avoidance from SceneAwareMotionService.

Contact approach/grasp/place need explicit target/contact semantics; do not globally delete the target obstacle just to reach the grasp point.

## USER ACTION 1 expected from Codex

~~~text
底盘和相机audit现场已就绪
~~~

After this single confirmation, Codex may run the bounded AMR + camera audit automatically until a fault/site-state change.

## Key audit questions

P3.8A must resolve:

- effective local AMR x/y/yaw semantics including the current dirty yaw fix;
- how to record PICK_BASE_POSE_V1 and PLACE_BASE_POSE_V1;
- exact 5700 mapping for right-arm 物料抓取;
- exact 5700 mapping/pose semantics for 物料放置最右点;
- configurable pregrasp distance 0.03/0.04/0.05 planning-only comparison;
- CONTACT_TARGET final approach semantics;
- gripper percentage/raw mapping and grasp-verification gap;
- post-grasp local scene-delta around TCP;
- attached-object collision pipeline;
- lift to z≈1.20 m + right-front visibility-clear planning;
- vertical placement geometry and +5 mm stop;
- whether left arm can remain current or needs a clearance-UP pose;
- whether concurrent dual-arm execution is actually ready;
- Skill/Scheme implementation matrix.

## Next after P3.8A

### P3.8B — planning-only full Scheme

Only after P3.8A report says READY_FOR_P3_8B_PLANNING_ONLY_SCHEME=YES.

Build and simulate the complete Scheme with replaceable target interfaces. No grasp execution yet.

### P3.8C — supervised physical customer demo

Only after P3.8B and explicit owner review.

Execute stages incrementally with real arm/gripper motion.

## UI

Keep current WebUI running as the scene/motion visualization frontend.

Later extend it with:

- Scheme step state;
- pick/place target markers;
- gripper/attachment state;
- AMR pickup/place base pose evidence;
- task start/stop controls.

Do not let UI bypass backend services.

## Git policy

No force-push.
Preserve coworker AMR/gripper changes.
Use small commits.
Do not mix unrelated dirty changes.
Leave .32 and GitHub aligned after reviewed subphases.
