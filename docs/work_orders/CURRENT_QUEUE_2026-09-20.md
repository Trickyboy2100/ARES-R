# CURRENT QUEUE — 2026-09-24

## Canonical field state

Integration branch currently includes P3.8B live pregrasp checkpoint:

~~~text
75b5c2c2e7962de86bba606ea7a938b1fa0c924a
~~~

Established:

- arbitrary-target fresh-scene motion physically executed;
- P3.8B0 production blockers closed;
- right_pick and right_place_rightmost mappings established;
- atomic 5700 + Pixel Pro manipulation observation exists;
- CURRENT→50 mm pregrasp real-scene cuRobo planning succeeds;
- 40% opening-aware gripper envelope implemented;
- pregrasp free-space path uses terminal orientation only, not whole-path lock.

## Current true blocker

Exact grasp endpoint is blocked by collision abstraction, not task reachability.

Evidence:

~~~text
single gripper union abstraction
+ old whole-tool inflation
+ already-inflated support scene
→ false dock/support overlap (~17.2 mm model overlap)
~~~

Detailed pinned EG2-4C2 component geometry shows that this should be resolved by a component-level opening-specific gripper model, not by moving the base again or deleting support geometry.

## Active now

### P3.8B1 — Fast grasp collision-model correction

Execute:

~~~text
docs/work_orders/2026-09-24_P3_8B1_FAST_GRASP_COLLISION_CORRECTION.md
~~~

Priority is SPEED:

~~~text
component gripper geometry
→ remove duplicate contact-stage inflation
→ validate exact grasp/contact segment
→ package FIRST REAL PICK
→ real grasp + 100 mm lift checkpoint
~~~

Do not restart broad audits.

Do not move the base again solely to hide the geometry abstraction issue.

## First physical checkpoint after B1

Once B1 produces an immutable accepted package, the first physical package is intentionally short:

~~~text
pregrasp
→ gripper 40%
→ bounded contact approach
→ close
→ delayed readback + local TCP scene delta
→ lift 100 mm
→ HOLD
~~~

This isolates grasp/contact correctness before the full transfer/place Scheme.

## After first pick succeeds

Immediately continue P3.8B full Scheme planning for:

~~~text
attached-object transfer
→ z≈1.20
→ visibility clear
→ place base
→ right_place_rightmost
→ preplace
→ vertical place +5 mm
→ release
→ retreat
~~~

Then enter P3.8C full customer demo.

## Architecture rule

Free-space motion:

~~~text
SceneAwareMotionService + cuRobo
~~~

Contact:

~~~text
TargetContactPolicy + component-level tool geometry
~~~

Do not globally delete TARGET or SUPPORT geometry.

Obstacle avoidance remains below Skills.

## Git

No force-push.
Small commits.
Keep coworker AMR/gripper changes isolated.
Leave .32 and GitHub aligned after reviewed checkpoints.