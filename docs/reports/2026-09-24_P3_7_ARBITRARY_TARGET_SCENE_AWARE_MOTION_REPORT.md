# P3.7 Arbitrary-target Scene-Aware Motion Report

Date: 2026-09-24  
Branch: `feat/e2e-v0-integration-20260917`

## Outcome

The low-level motion path no longer requires A/B endpoints. A versioned `MotionGoal` accepts a runtime BODY-frame position and orientation policy. A/B remains only in `ABDemoClient` as a demo/regression preset.

The physical sequence used runtime coordinates:

| Label | BODY target XYZ (m) | Source |
|---|---|---|
| P | `[0.68, -0.55, 1.04]` | ART runtime input |
| Q | `[0.68, -0.50, 1.12]` | P3.7 runtime input |
| R | `[0.62, -0.60, 1.08]` | P3.7 runtime input |
| box-left | `[0.66, -0.18, 1.08]` | point-cloud-relative operator-approved runtime input |

None of these targets was loaded from the A/B configuration. The executed sequence was `current -> P -> Q -> R`, followed by the operator-requested obstacle crossing `R -> box-left -> R`. The latter superseded an additional fixed P/Q/R closure and directly tested the requested visible box crossing in both directions.

## MotionGoal and LEVEL_YAW_FREE

`MotionGoal` v1 contains BODY XYZ, orientation mode, tolerances and provenance. Supported modes are `LEVEL_YAW_FREE`, `LEVEL_YAW_TARGET`, `CURRENT`, `EXPLICIT`, plus legacy compatibility modes.

For `LEVEL_YAW_FREE`, runtime IK evaluates level yaw candidates without consulting A/B. cuRobo receives the current state, selected runtime goal candidates and fresh collision world. The commissioned level branch has TCP local Y vertical, so BODY +Z yaw is the released TCP-local-Y rotation; the other rotational components remain constrained. Independent dense validation checks both horizontal TCP axes, maximum level error, yaw range and final yaw.

## Fresh-scene provenance

Every successful physical leg consumed a different point-cloud SHA, SceneSnapshot and trajectory hash. Arrival invalidated the old plan and scene before the next request.

| Leg | Scene epoch | Minimum clearance | Max level error | Yaw range | Plan time | Execution | Tracking max |
|---|---:|---:|---:|---:|---:|---:|---:|
| current→P | 8 | 25.03 mm | 1.071° | 15.26° | 12.48 s | 11.97 s | 0.273° |
| P→Q | 11 | 33.20 mm | 0.275° | 0.03° | 5.93 s | 15.65 s | 0.634° |
| Q→R | 12 | 33.64 mm | 1.165° | 15.50° | 7.01 s | 14.37 s | 0.406° |
| box right→left | 15 | 28.72 mm | 0.659° | 45.00° | 11.31 s | 27.24 s | 0.369° |
| box left→right | 16 | 27.74 mm | 0.599° | 60.00° | 10.99 s | 25.64 s | 0.277° |

All five legs reached their requested target, reported no abort/fault and confirmed Servo disable after arrival.

The first P→Q send was rejected before movement by a transient controller status value (`4128769`); read-only state immediately reported controller error zero. The rejected plan was invalidated. A fresh scan, new snapshot and new plan were created, after which P→Q succeeded. No controller protection was bypassed.

## Arbitrary visible-box crossing

The fresh point cloud reconstructed the box as `observed_support_02_component_00_protruding`:

- center approximately `[0.663, -0.379, 0.961] m`;
- observed size approximately `209 x 58 x 202 mm`;
- inflated top approximately `z=1.070 m`.

The direct joint-linear baseline for the approved right-to-left target intersected the observed box (`clearance < 0`). The selected cuRobo path rose to `z=1.196 m`, with 28.72 mm independently modeled minimum clearance. The return used a new scan and rose to `z=1.150 m`, with 27.74 mm clearance. No obstacle coordinate was manually supplied to the collision world.

## Interfaces

ART:

```text
motion plan right --xyz X Y Z
motion plan right --xyz X Y Z --orientation LEVEL_YAW_TARGET --yaw DEG
motion preview [PLAN_ID]
motion execute PLAN_ID
motion stop
```

WebUI: `http://172.28.172.210:8765/`

The main panel now accepts BODY XYZ and orientation policy. A/B controls are under Demo/Regression. ART and WebUI use the same dispatcher and motion backend.

## Evidence

- `worklog/evidence/scene-aware-motion/P37_current_to_P_20260923T1653Z/`
- `worklog/evidence/scene-aware-motion/P37_P_to_Q_retry_20260924T1210Z/`
- `worklog/evidence/scene-aware-motion/P37_Q_to_R_20260924T1211Z/`
- `worklog/evidence/scene-aware-motion/P37_BOX_right_to_left_20260924T1226Z/`
- `worklog/evidence/scene-aware-motion/P37_BOX_left_to_right_20260924T1228Z/`

## Acceptance

```text
FRESH_SCENE_GENERIC_OBSTACLE_PATH = YES
ARBITRARY_RUNTIME_TARGET_READY = YES
NO_FIXED_AB_DEPENDENCE = YES
LEVEL_YAW_FREE_READY = YES
LEVEL_YAW_FREE_DENSE_VALIDATION = YES
ART_ARBITRARY_TARGET_READY = YES
UI_ARBITRARY_TARGET_READY = YES
ARBITRARY_POINT_PAIR_EXECUTED = YES
ARBITRARY_OBSTACLE_AVOID_EXECUTED = YES
BASE_MOVE_THEN_ARBITRARY_TARGET_AUTO_SCAN = YES (logical regression; no AMR motion in P3.7)
```

P3.7 remains free-space motion only. No grasp, contact approach or placement behavior was started.
