# CURRENT QUEUE — 2026-09-24

## Current canonical integration baseline

~~~text
feat/e2e-v0-integration-20260917
GitHub HEAD = d19cea78ffe3664fbf36423b6a6f80f371918de5
~~~

P3.7 arbitrary-target scene-aware free-space motion is complete and physically demonstrated.

P3.8A system/interface audit is complete locally as an audit and must be cleanly preserved/pushed before blocker-closure refactoring.

## What P3.8A established

~~~text
HW_STATE_AUDIT = PASS
RIGHT_PICK_5700_MAPPING_VERIFIED = YES
RIGHT_PICK_DETECTION_REPEATABLE = YES
PICK_BASE_POSE_V1_RECORDED = YES_RELATIVE_PROVENANCE
PLACE_BASE_POSE_V1_RECORDED = YES_RELATIVE_PROVENANCE
LEFT_HOLD_CURRENT_FEASIBLE = YES_PLANNING_ONLY
DUAL_ARM_CONCURRENT_EXECUTION_READY = NO
SKILL_SCHEME_AUDIT_READY = YES
READY_FOR_P3_8B_PLANNING_ONLY_SCHEME = NO
~~~

Effective field facts:

~~~text
AMR:
  x+ forward
  x- backward
  y+ left
  y- right
  yaw degrees
  negative yaw clockwise

pickup audit move:
  y = +0.30 m

placement audit move from pickup pose:
  y = -0.40 m

right_pick:
  320,2,1,1,1,0
  space=2 object=1 camera=1
  COMMISSIONED

rightmost-place:
  object 3 / 320,2,3,1,1,0 is the strongest current candidate
  NOT YET COMMISSIONED
~~~

## Active now

### P3.8B0 — close production blockers

Execute:

~~~text
docs/work_orders/2026-09-24_P3_8B0_PRODUCTION_BLOCKER_CLOSURE.md
~~~

This phase is implementation, not another broad audit.

Close:

~~~text
1 truthful asynchronous AMR completion observer
2 atomic 5700 + 5000 + robot-state ObservationTransaction
3 right_place_rightmost exact mapping/pose semantics
4 bounded TargetContactPolicy
5 attached-object collision geometry through planner/validator/SafetyKernel
6 local TCP scene-delta + grasp verification
~~~

Also parameterize manipulation targets/gripper percentages and expose reusable Skill adapters.

AMR/camera may be used for evidence; arm/gripper physical movement waits for P3.8C.

Exit:

~~~text
READY_FOR_P3_8B_FULL_SCHEME_PLANNING = YES
~~~

## Next

### P3.8B — full planning-only Scheme rehearsal

~~~text
docs/work_orders/2026-09-24_P3_8B_FULL_SCHEME_PLANNING.md
~~~

Run the complete owner Scheme with live AMR/camera observations, simulated manipulation state, attached-object geometry and replaceable target interfaces.

Exit:

~~~text
READY_FOR_P3_8C_SUPERVISED_EXECUTION = YES
~~~

### P3.8C — supervised physical customer demo

~~~text
docs/work_orders/2026-09-24_P3_8C_SUPERVISED_EXECUTION.md
~~~

First-demo policy:

~~~text
right arm manipulates
left arm HOLD_CURRENT
no simultaneous dual-arm motion
~~~

Physical sequence:

~~~text
presentation + gripper50
→ pickup base
→ atomic right_pick observation
→ pregrasp + gripper40
→ bounded contact approach
→ grasp + local verification
→ attach
→ lift z≈1.20
→ visibility clear
→ placement base
→ atomic right_place_rightmost observation
→ preplace
→ vertical place to target+5mm
→ gripper20
→ detach
→ retreat arm/base
→ verify task
~~~

## Scheme source

Owner-confirmed Scheme:

~~~text
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
~~~

Historical/local source that Codex must also read:

~~~text
/home/yikun/ARES-R/docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
~~~

## Architecture

~~~text
Task
→ Scheme
→ Skills
→ SceneAwareMotionService
→ LocalSceneService + cuRobo
→ execution authority
→ robot
~~~

Obstacle avoidance is not a Skill.

Free-space manipulation Skills always inherit scene-aware pointcloud avoidance.

## Git policy

No force-push.
Preserve coworker AMR/gripper-exit work.
Small commits per blocker/subphase.
Do not mix unrelated dirty changes.
Leave .32 and GitHub aligned after reviewed subphases.