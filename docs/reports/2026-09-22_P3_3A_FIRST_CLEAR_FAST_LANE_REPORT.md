# P3.3A FIRST CLEAR fast lane — 2026-09-22

Status: planning-only; **no AMR, arm or gripper motion**; no WebUI; no push.

## Locked behavior and physical model

- CURRENT→A, A→B and B→A use one direct cuRobo start→goal request with the fresh collision world. Explicit waypoint list stays empty. Approved A/B BODY TCP positions `[0.710,-0.600,1.000]` and `[0.710,-0.130,1.000]` m are unchanged.
- The right-arm physical collision body is the pinned ARES EG2-4C2 gripper maximum-open mesh envelope plus 8 mm inflation, **not** an invented extension to the controller TCP. The measured flange→grasp centre ≈145 mm agrees with the pinned mesh distal extent ≈149 mm. Controller TCP Z≈184 mm remains the kinematic/task frame. `TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED=YES`; movement-only, no grasp certification.
- `supervised_path` is a distinct JAKA C++ mode, not `pregrasp`. Its parser enforces the 80 ms native format, ≤0.015 rad/s, ≤0.03 rad/s², 240 s and 150° limits before any login. `validate-supervised-path` tests files without opening a controller connection. Python packaging only time-dilates/resamples the exact cuRobo joint polyline and independently checks geometry preservation.
- ART backend owns `demo ab status|scan|plan-next|preview|preflight|execute-next|stop`. `execute-next` is hard blocked. `stop` currently invalidates the pending session and never sends a device command; future runner's Space/B abort callbacks are implemented and mock-tested but **not connected to live motion**. Neither keyboard action replaces the physical E-stop.

## Read-only site evidence and planning

The first complete fresh CLEAR SceneSnapshot was `SCENE_69e1fea1399b4ae1a0d134cbb95a37a9` from Pixel Pro and fresh bilateral JAKA FK audits. Left/right maximum FK position errors were ≈0.81/1.25 mm. Original pinned A/B and current actual right joints were used. Independent CPU/URDF dense checks (not merely the cuRobo optimizer score) gave:

| Leg | Independent dense modeled clearance | Threshold | Native duration at precision speed | Maximum speed | Maximum acceleration | Tracking prediction | Exact cuRobo trajectory hash |
|---|---:|---:|---:|---:|---:|---:|---|
| CURRENT→A | 103.397 mm | 30 mm | 104.72 s | 0.0149998 rad/s | 0.0082681 rad/s² | 0.10313° | `sha256:465fd59e1ec43741039e95b02c50cbdb702466e918160d9fb2e0e7d9dfb513ef` |
| A→B CLEAR | 93.387 mm | 50 mm | 183.36 s | 0.0149975 rad/s | 0.0064763 rad/s² | 0.10312° | `sha256:5b2078ef533a4054271b6e9845060b24138b1445e3f1188ef3e7bd8f07ce7e25` |
| B→A CLEAR | 93.387 mm | 50 mm | 183.36 s | 0.0149989 rad/s | 0.0064728 rad/s² | 0.10313° | `sha256:0c848a08d31cb5d7390de790aefc6082e0cb8bbcefc9a98eac0a7960d1154cf8` |

The A/B files are staged native previews, **not** execution-ready from the current physical start. Arrival at A/B must be confirmed and followed by a new scan, state read, SceneSnapshot, cuRobo plan, hash, native file, and lease. The snapshot-linked files expire in 300 s; an expired file is rejected by the C++ sender before login.

## Base stationarity attribution

`/robot/status.state=IDLE` alone is insufficient. AMR map localization confidence was only ≈31–36%, with apparent pose jitter as high as 33 mm and 0.95° over two seconds. An independent self-filtered CLEAR environment-cloud registration between two scans showed fitness 1.0, RMSE 0.896 mm, relative translation 0.463 mm and rotation 0.0059°. The alignment transform is **measurement-only** and never changes `T_body_camera`. P3.3A preflight requires AMR `IDLE` plus either stable map pose or a passing static-environment cloud cross-check; if both fail, `BASE_STATIONARY=FAIL`. This is operational evidence, not functional-safety certification.

## Final fresh CURRENT→A preflight

Final fresh scan `SCENE_2984a3bfe23a49249c3ce9e363a84ee7` was captured under `art_scan_20260922T063610Z`. Exact candidate `sha256:78c6218e32d5100d4fa2fa24ce58e96a89b6b40271d89d6cd301c212b90e92bd` bound actual start, pointcloud SHA, calibration, whole-robot/inactive-arm/tool/envelope revisions, planner profile, exact geometric and native hashes, precision timing, sender binary SHA and 300 s expiry. The standalone C++ `validate-supervised-path` accepted its 1310-sample/104.72 s file **without controller login**. The pinned sender binary SHA is `7c760d2b913af068e7b85012ae520ca6e9eb7e254e15837969df583f933de337`.

In the final base check, AMR map pose drift was 34.1 mm/0.42° in two seconds despite `IDLE`. The independent static-scene cloud check (previous vs final CLEAR residual) had fitness 0.99875, RMSE 1.154 mm, relative translation 0.924 mm and rotation 0.0101°, so `BASE_STATIONARY` passed with provenance. This must be repeated with the live scene before any later motion; map-pose jitter is **not** silently treated as zero.

| SafetyKernel dry-run gate | Result |
|---|---|
| START_MATCH | PASS |
| SCENE_FRESH | PASS at preflight time; expires after 300 s |
| BASE_STATIONARY | PASS, IDLE + independent cloud check |
| INACTIVE_ARM_KNOWN | PASS |
| TOOL_REVISION_MATCH | PASS |
| TRAJECTORY_COLLISION_CHECKED | PASS, 103.397 mm dense modeled gap |
| CENTRAL_EXCLUSION | PASS |
| VELOCITY | PASS, max 0.0149998 rad/s |
| ACCELERATION | PASS, max 0.0082681 rad/s² |
| NATIVE_SENDER_LIMITS | PASS, 80 ms / 104.72 s / exact binary hash |
| TRACKING_PREDICTION | PASS, 0.10313° vs 0.15° engineering budget and 0.2° sender stop gate |
| EXECUTION_ENABLED | FAIL, deliberately disabled |
| SPEED_PROFILE_COMMISSIONED | FAIL, precision still UNCOMMISSIONED |

No permit was issued and no trajectory was sent. All machine-checkable gates passed at the recorded preflight; only the two deliberately withheld authorization gates failed. Candidate/native snapshot expiry means **the recorded file must not be reused after 300 s**. On a later authorization turn, a fresh `demo ab scan → plan-next → preview → preflight` and exact-hash review are mandatory before attempting motion.

## Gate definitions

`CURRENT_TO_A_EXECUTION_PACKAGE_READY` means a fresh, previewed, exact native file passes every machine-checkable gate, with only separate execution and precision-commissioning authorizations withheld. A→B/B→A package readiness requires arriving at its start and a fresh per-leg scene; old scene previews are insufficient.

`P3_3A_FIRST_CLEAR_READY` is therefore a request-readiness claim for the first CURRENT→A leg only, never permission to run all three stale files.

~~~text
CURRENT_TO_A_EXECUTION_PACKAGE_READY = YES (at recorded preflight; short-lived, refresh before use)
A_TO_B_CLEAR_PACKAGE_READY = NO (native preview exists; actual start at A + fresh scan not yet available)
B_TO_A_CLEAR_PACKAGE_READY = NO (native preview exists; actual start at B + fresh scan not yet available)
P3_3A_FIRST_CLEAR_READY = YES (request-ready for first leg only)
SAFETY_PREFLIGHT_READY = YES (dry-run, no permit)
~~~

The request-ready decision is **not** an instruction to move. Separate authorization is required for RIGHT CURRENT→A precision-speed supervised execution; any later scene, start, tool or sender change invalidates this candidate.

Raw artifacts: `/home/yikun/ARES-R/worklog/evidence/2026-09-22-p3-3a-clear-fastlane/`. No AVOID sweep or WebUI work was performed in this phase.
