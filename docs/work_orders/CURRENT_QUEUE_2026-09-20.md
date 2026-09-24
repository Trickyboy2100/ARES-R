# CURRENT QUEUE — 2026-09-24

## Canonical field checkpoint

Integration branch contains the P3.8B live pregrasp checkpoint and fine gripper-collision work is in progress locally.

Current strategic override:

~~~text
DO NOT make the fine component-level gripper collision model a blocker for the first customer demo.
Preserve the work; defer its commissioning to post-demo hardening.
~~~

## Active now

### P3.8B1A — CONTACT_BYPASS_V1 first-pick path

Execute:

~~~text
docs/work_orders/2026-09-24_P3_8B1A_CONTACT_BYPASS_FIRST_PICK.md
~~~

Read policy:

~~~text
docs/decisions/2026-09-24_CONTACT_COLLISION_DEMO_POLICY.md
~~~

Future hardening TODO:

~~~text
docs/todo/2026-09-24_MANIPULATION_COLLISION_HARDENING_TODO.md
~~~

## V1 stage policy

Free-space motion remains full collision-aware:

~~~text
fresh LocalScene
→ SceneAwareMotionService
→ cuRobo
→ ordinary pointcloud avoidance
~~~

Only bounded contact stages use CONTACT_BYPASS_V1:

~~~text
pregrasp → grasp → close → initial BODY +Z lift 100 mm

preplace → vertical place → release → initial vertical retreat
~~~

During bypass:

~~~text
ignore only active right gripper/tool ↔ observed pointcloud world

keep hard:
  arm links ↔ environment
  self collision
  inactive left arm
  BODY central exclusion
  controller collision/limits/estop/fault
  native tracking/watchdog
~~~

CONTACT_BYPASS_V1 expires automatically after the bounded contact/escape segment.

## First physical checkpoint

Use the already successful 50 mm pregrasp.

Target package:

~~~text
FIRST_PICK_EXECUTION_PACKAGE

fresh atomic right_pick observation
→ cuRobo current→50 mm pregrasp
→ gripper 40%
→ CONTACT_BYPASS_V1 straight approach
→ close
→ delayed readback + local 15 cm scene delta
→ if verified: BODY +Z lift 100 mm
→ bypass OFF
→ coarse attached-object AABB
→ HOLD
~~~

Do not continue automatically to place in this first package.

## Fine component model status

The detailed EG2-4C2 component collision implementation is NOT discarded.

Keep it as optional diagnostics/tests and future SELECTIVE_CONTACT_COMPONENTS_V2.

Do not continue inflation sweeps or make its exact-contact clearance a V1 execution gate unless explicitly requested.

## After first real pick

Resume the existing P3.8B/P3.8C path:

~~~text
coarse attached object
→ full SceneAwareMotion transfer
→ z≈1.20 visibility clear
→ place base
→ right_place_rightmost
→ preplace
→ CONTACT_BYPASS_V1 place/release/retreat
→ full task verification
~~~

## Git

Do not revert the already implemented component model.
No force-push.
Keep coworker changes isolated.
Small commits.
Leave .32/GitHub aligned at reviewed checkpoints.