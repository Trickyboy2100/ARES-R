# Single continuous230mm lift checkpoint

Isolated RC1 only. No physical motion performed in this change.

Demo revision: `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_19_V9_SINGLE_LIFT230`.

## Execution semantics implemented

- Recipe contains one `LIFT230_CONTINUOUS` stage, calling `pick_segment('lift230')` once.
- Removed both `LIFT_INITIAL100` and `LIFT_TO_HOLD230` from the active recipe. Old frozen recipes retain the legacy branch when the explicit mode is absent.
- One116-knot BODY+Z230mm Cartesian/continuous-IK path, one full-path retiming, one native file, one sender invocation and one final arrival. No physical hold, rescan, replan, Servo restart or command boundary at100mm.
- Fixed Demo-only−10deg compensation remains applied; existing speed/acceleration/site/controller/tracking limits unchanged.
- Candidate gripper readback before lift; grasp confirmation and scene delta after the complete230mm arrival. Verifier explicitly expects230mm for this Demo, legacy default remains100mm.
- Initial100mm target contact permission is NOT widened. Beyond100mm the same continuous path receives full loaded-world collision validation with the provisional payload and exact bound-source target deduplication. Arm/world and non-adjacent self collision remain hard throughout. Mathematical validation regions do not create execution stages.
- Golden first-pick package and standalone script remain unchanged; new continuous points/native file are additive sidecars, bound to source package/scene/attachment.
- WebUI/backend now show20 stages and continuous lift mode. No automatic launch.

## Real frozen-scene result: NOT EXECUTION READY

Path generation succeeded, but loaded-world geometry validation failed before native package admission.

Evidence: `worklog/evidence/20261019-continuous-lift230-no-motion/FAULT.json`.

Limiting pair: attached-object model versus `observed_support_05_component_00_protruding`, minimum modeled overlap approximately34.823mm on the100–230mm suffix. This is a MODEL collision report, not evidence of physical contact. No obstacle or point was deleted, no limit enlarged, no collision condition ignored. Native execution file was not admitted and no physical lift attempted.

The production preparation validates the complete lift before any grasp-stage actuation. A failed full lift package faults in PICK_PREPARE, never after partially lifting100mm. This is implemented code, not a successful physical commissioning claim.

## Software regression

737 tests completed,1 skipped, remaining passed. Includes continuity/no100mm duplicate knot, active recipe contains one lift, legacy recipe compatibility,230mm grasp-verification distance and command reconciliation.
