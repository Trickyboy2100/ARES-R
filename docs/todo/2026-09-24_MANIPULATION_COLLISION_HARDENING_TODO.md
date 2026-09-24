# TODO — Manipulation collision hardening after first customer demo

Date: 2026-09-24
Priority: POST-DEMO HARDENING
Current runtime default: CONTACT_BYPASS_V1

## Why this is deferred

The detailed EG2-4C2 component collision implementation is useful and already partially implemented/tested, but it is not required to prove the first customer-facing Tray→Groove flow.

Near-contact geometry is currently sensitive to:

- pointcloud residuals;
- scene inflation;
- tool inflation;
- hand-eye/model error;
- gripper opening state;
- support-surface decomposition.

Making the fine component model a mandatory gate now risks repeated false positive contact failures.

## Preserve current work

Do NOT delete or revert the current component-level implementation.

Preserve:

- articulated/opening-specific EG2-4C2 component geometry;
- component revisions/hashes;
- planner integration;
- dense validator integration;
- TargetContactPolicy integration;
- SafetyKernel integration;
- frozen-scene contact sweep scripts/tests;
- diagnostic artifacts.

Keep it out of the V1 mandatory execution path unless explicitly selected.

## V2 target

Future policy:

~~~text
SELECTIVE_CONTACT_COMPONENTS_V2
~~~

Requirements:

1. per-component OBB/sphere geometry;
2. opening-specific transforms;
3. one source of geometry for planner/validator/SafetyKernel/UI;
4. calibrated scene-vs-tool inflation budget;
5. explicit allowed tool/finger ↔ target contact pairs;
6. target contact only within a bounded corridor;
7. support/non-target remains hard;
8. calibration/noise tolerance measured from real contact runs;
9. no recurring false-positive aborts in repeated pick/place tests;
10. switchable through a versioned contact policy without changing Scheme code.

## Commissioning dataset

After the V1 demo is working, collect at least:

- 20 successful pregrasp→grasp approaches;
- several different object/dock placements;
- pointcloud + raw geometry at contact;
- observed minimum model gaps;
- real contact success/failure;
- false positive collision blocks;
- gripper opening/readback;
- hand-eye/tool revisions.

Use this evidence to choose component inflation and contact pair semantics.

## Exit criteria

V2 may replace V1 only when:

~~~text
CONTACT_COMPONENT_MODEL_CALIBRATED = YES
FALSE_POSITIVE_CONTACT_BLOCK_RATE_ACCEPTABLE = YES
PLANNER_VALIDATOR_GEOMETRY_IDENTICAL = YES
REPEATED_PICK_PLACE_WITH_COMPONENT_MODEL = PASS
SCHEME_UNCHANGED_WHEN_SWITCHING_V1_TO_V2 = YES
~~~
