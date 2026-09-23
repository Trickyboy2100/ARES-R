# P3.6 Scene-Aware Motion Control Report

Date: 2026-09-23  
Branch: `feat/e2e-v0-integration-20260917`

## Result

The point-cloud avoidance chain is now a shared backend rather than an A/B-only implementation:

`fresh Pixel Pro scan -> LocalSceneService -> SceneSnapshot -> generic collision world -> persistent cuRobo -> hard validation -> native ServoJ package -> supervised execution`

The preferred-clearance objective belongs to cuRobo planning policy. The independent validator remains fail-closed for actual collision/penetration, scene and state binding, central exclusion, dynamics, and controller limits. A collision-free path may leave a near-obstacle start under the explicit `START_NEAR_OBSTACLE` escape contract; a fixed 30 mm A/B margin is not used as a second planner.

## D0 backend integration

- `LocalSceneService` owns READY/STALE/REQUIRED lifecycle and persisted provenance.
- AMR motion start invalidates the scene; a settled AMR increments the base revision and marks a new scan required.
- `SceneAwareMotionService` accepts generic arm, target, orientation, scene, and clearance policies.
- A/B is a thin client that supplies only targets and constraints.
- ART and WebUI call the same dispatcher/backend.
- Generic candidates bind the exact scene, point-cloud SHA, robot/tool revisions, trajectory hash, sender hash, and expiry.

## D1 arbitrary-obstacle physical demonstration

No obstacle coordinate was entered and no box/dock-specific runtime rule was used. The operator placed an arbitrary visible object; the system captured a new scene, reconstructed generic primitives, updated the persistent cuRobo world, planned directly from start to goal, and executed the exact validated trajectory on the right arm.

| Item | Result |
|---|---:|
| Scene snapshot | `SCENE_a42e4b6526a34fc7a8282f7372890ecd` |
| Point-cloud SHA-256 | `9484d4804b28ff73c5b84ffff6a941dd9de5d98fcf1cf208d6a269907637a698` |
| Scene epoch | 3 |
| Generic primitives | 198 |
| Plan ID | `PLAN_d38ada9da9444b1fa70a1cb7858a83e1` |
| Trajectory SHA-256 | `43bfff8d65ac53147d36da3658b45daf754142a9755a3ccd3cc82e9b49a1f00d` |
| Limiting object | `observed_support_02_component_00_protruding` |
| Start / goal modeled gap | 8.09 mm / 103.40 mm |
| Start classification | `START_NEAR_OBSTACLE` |
| Escape validation | non-penetrating, non-decreasing, recovered |
| TCP path length | 216.36 mm |
| Start-goal distance | 200.00 mm |
| Maximum straight-line deviation | 32.62 mm |
| Persistent cuRobo solve | 3.08 s |
| Fresh scan pipeline | 8.08 s |
| Packaged trajectory duration | 10.88 s |
| Actual execution elapsed | 11.41 s |
| Tracking error max / p95 / RMS | 0.882 deg / 0.875 deg / 0.684 deg |
| Fault / abort | none |
| Arrival | reached |

After arrival, the consumed plan became stale and the scene was invalidated as `RIGHT_ARM_MOVED`; the next free-space request therefore requires a fresh scan and a new trajectory.

## Minimal shared WebUI

The dependency-free UI exposes BODY-frame point cloud, collision primitives, dual-arm geometry, target and trajectory, plus BASE/SCENE/PLANNER/EXECUTION status. It shares the same dispatcher as ART. Physical execution remains a supervised TTY action; the browser does not bypass that boundary.

Site URL: `http://172.28.172.210:8765/`

## Evidence

- Server execution evidence: `worklog/evidence/scene-aware-motion/D1_arbitrary_obstacle_execution_20260923T0753Z/`
- Server planning evidence: `worklog/evidence/scene-aware-motion/PLAN_d38ada9da9444b1fa70a1cb7858a83e1/`
- Server visualization: `worklog/evidence/scene-aware-motion/PLAN_d38ada9da9444b1fa70a1cb7858a83e1/d1_scene_trajectory.png`
- Workstation visualization: `/Users/andyee/Downloads/D1_scene_trajectory.png`
- WebUI log: `logs/scene_aware_webui.log`

## Acceptance

```text
LOCAL_SCENE_SERVICE_READY=YES
BASE_MOVE_INVALIDATES_SCENE=YES
AUTO_SCAN_BEFORE_ARM_MOTION=YES
GENERIC_SCENE_AWARE_MOTION_READY=YES
GENERIC_CONSTRAINT_INTERFACE_READY=YES
PLANNER_CLEARANCE_POLICY_IN_CUROBO=YES
HARD_VALIDATOR_NO_DEMO_MARGIN=YES
START_NEAR_OBSTACLE_ESCAPE_READY=YES
AB_DEMO_MIGRATED_TO_GENERIC_MOTION=YES
ARBITRARY_OBSTACLE_DEMO_EXECUTED=YES
MOVED_OBSTACLE_REPLAN_EXECUTED=NO
MINIMAL_SCENE_UI_READY=YES
WEBUI_BACKEND_PARITY=YES
WEBUI_LOCAL_SCENE_STATE=YES
WEBUI_GENERIC_MOTION_REQUEST=YES
WEBUI_PLAN_STALE_INVALIDATION=YES
WEBUI_ARBITRARY_SCENE_VISUALIZATION=YES
WEBUI_ART_EMBEDDED=YES
```

`MOVED_OBSTACLE_REPLAN_EXECUTED=NO` means only the first arbitrary placement was executed in D1; the architecture already forces a fresh scene and plan after every completed motion. A second moved-object run remains a separate physical validation, not a missing code path.
