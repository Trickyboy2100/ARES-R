# P3.4 Deployment Acceleration Report

Date: 2026-09-23

Scope: right-arm A/B demo only. Coworker AMR changes were left untracked by all P3.4 commits.

## Result

```text
FAST_CAMERA_PATH_READY = YES
FAST_SCENE_PIPELINE_READY = YES
PERSISTENT_PLANNER_READY = YES
FAST_PLANNER_PROFILE_READY = YES
PLANNER_WARM_P50_S = 15.206 request wall; formal solve CLEAR 5.095 / AVOID 6.822
SCAN_TO_TRAJECTORY_P50_S = 23.05 CLEAR (8.270 scan-to-scene + 14.780 warm request)
AB_SPEED_PROFILE_COMMISSIONED = YES
AB_COMMISSIONED_SPEED_RAD_S = 0.20
AB_TRACKING_STOP_THRESHOLD_DEG = 1.5
AB_LEG_DURATION_S = 9.49
CLEAR_FAST_ROUNDTRIP_EXECUTED = YES
AVOID_FAST_ROUNDTRIP_EXECUTED = DEFERRED_TO_P3.5_RANDOM_SCENE_1
```

## Capture and scene pipeline

ONLINE_PLANNING uses the persistent EpicEye SDK worker and writes only a direct float32 XYZ NPY plus its manifest. It does not produce image8bit, depthGrey, alignedTexture or either colored PLY. Five consecutive live runs measured:

| Stage | p50 | observed max |
|---|---:|---:|
| Pixel Pro capture + NPY | 2.873 s | 2.880 s |
| scene build after capture | 3.417 s | 3.483 s |
| full fresh scan/state/scene | 8.270 s | 8.353 s |

Early voxel comparison retained 7.5 mm. The 5 mm path took 4.039 s after capture and generated 243 primitives. The 7.5 mm path took 3.191 s and generated 171 primitives while preserving the upright-box observation at approximately 85.8 x 199.0 x 204.6 mm. The 10 mm path was faster at 2.672 s but fragmented/lost the known object evidence and was rejected.

## Persistent cuRobo planner

The service imports CUDA/cuRobo once, constructs each static planner profile once, performs one warm-up per runtime, and then runs `update_world(fresh scene)` followed by exactly one formal solve per request. CLEAR→AVOID→CLEAR switching was verified; the returning CLEAR trajectory hash matched its original frozen request.

| Profile | representative warm solve | decision |
|---|---:|---|
| 8/8, no CUDA graph | about 9.7–19.5 s across retained baseline evidence | rejected |
| 4/4, no CUDA graph | 12.00 s p50 | rejected |
| 4/2, no CUDA graph | 5.06 s p50 | selected |
| 4/2, CUDA graph | 5.04 s p50 | no material gain; not selected |

For the final five-repeat frozen requests, full warm request p50 was 14.780 s for CLEAR and 17.759 s for AVOID. Formal solve p50 was 5.095 s for CLEAR and 6.822 s for AVOID. Remaining wall time is independent validation and post-processing, not a discarded per-request warm-up solve.

## A/B execution profile

`config/ab_demo_deployment_profile.json` revision `AB_DEPLOYMENT_PROFILE_2026_09_23_V2` explicitly scopes 0.20 rad/s and the 1.5 degree software tracking stop to `RIGHT_ARM_AB_DEMO_ONLY`. Generic JAKA site limits and all unrelated motion modes remain unchanged.

Commissioning evidence includes the 0.12/0.14/0.16/0.18/0.20 ladder, an independent bidirectional 0.20 run, and a subsequent 0.20 B→A→B round trip. The last round trip completed both legs in about 9.49 s; observed peak tracking error was about 0.77 degrees B→A and 1.07 degrees A→B, with normal arrival and ServoJ shutdown.

## Before and after

| Metric | Before | P3.4 |
|---|---:|---:|
| camera/BODY scene | about 15.2 s | 8.270 s p50 |
| cuRobo process/request | about 54–57 s | 14.780 s CLEAR warm request p50 |
| formal solve | about 19.25 s plus discarded solve | 5.095 s CLEAR; no per-request discarded solve |
| A/B execution | about 25 s | about 9.49 s |

P3.5 owns the remaining real-obstacle roundtrip because its first validation deliberately moves the box to an undisclosed arbitrary location and exercises the same optimized backend without historical obstacle input.
