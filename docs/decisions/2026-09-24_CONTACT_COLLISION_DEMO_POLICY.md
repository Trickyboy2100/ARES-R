# Decision — Contact collision policy for the first Tray→Groove demo

Date: 2026-09-24
Status: OWNER OVERRIDE / DEMO DEFAULT

## Context

P3.8B1 proved that the detailed EG2-4C2 component model can be built and shared by planner/validator/contact/SafetyKernel. That work is useful, but the owner does NOT want fine component geometry to become a blocking dependency for the first customer demo.

Reason:

- current manipulation is already sensitive to pointcloud/support-model inflation;
- a high-fidelity multi-component contact model can create repeated near-contact false positives when calibration/pointcloud noise is comparable to millimetre-level clearances;
- the customer demo priority is robust staged execution, not perfect contact collision fidelity.

The detailed component model is preserved and moved to a hardening TODO. Do not revert already-tested code.

## V1 runtime policy

Use a stage-specific policy.

### FREE_SPACE

Normal SceneAwareMotionService:

~~~text
fresh LocalScene
→ cuRobo
→ ordinary full scene collision avoidance
~~~

The normal opening-aware coarse gripper envelope may be used.

### CONTACT_BYPASS_V1

Allowed only for short, reviewed manipulation segments:

~~~text
pregrasp → grasp
gripper close
initial BODY +Z lift / escape

preplace → placement
release
initial vertical retreat / escape
~~~

During CONTACT_BYPASS_V1:

~~~text
IGNORE:
  active right gripper/tool ↔ observed pointcloud collision geometry

KEEP HARD:
  right arm links ↔ environment
  self collision
  inactive left arm
  BODY central exclusion
  joint/controller limits
  controller collision/estop/fault
  native tracking/watchdog
~~~

The bypass is NOT available to ordinary free-space motion and is automatically cleared at the end of the bounded contact/escape segment.

## Initial pick behavior

For the first real pick:

~~~text
fresh atomic observation
→ cuRobo CURRENT→50 mm pregrasp
→ gripper 40%
→ CONTACT_BYPASS_V1 straight approach to Epic grasp pose
→ close
→ delayed gripper readback + local TCP scene delta
→ BODY +Z lift 100 mm under CONTACT_BYPASS_V1
→ CONTACT_BYPASS_V1 OFF
→ convert target primitive to coarse attached-object AABB
→ fresh scene
→ resume full SceneAwareMotion
~~~

## Initial placement behavior

~~~text
full SceneAwareMotion to preplace
→ CONTACT_BYPASS_V1 vertical descent
→ stop at detected target +5 mm
→ gripper 20%
→ detach
→ initial vertical retreat under CONTACT_BYPASS_V1
→ CONTACT_BYPASS_V1 OFF
→ fresh scene / ordinary motion
~~~

## Non-goals for V1

Do not block the first demo on:

- exact per-finger collision pair filtering;
- full articulated finger geometry at runtime;
- millimetre-scale contact inflation tuning;
- component-level gripper model commissioning.

Those belong to the future hardening TODO.

## Migration rule

The future precise contact model must be introduced behind a versioned policy, for example:

~~~text
CONTACT_COLLISION_POLICY:
  V1 = CONTACT_BYPASS_V1
  V2 = SELECTIVE_CONTACT_COMPONENTS
~~~

Switching to V2 must not require changing the Scheme or Task interfaces.
