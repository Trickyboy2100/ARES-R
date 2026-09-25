# CURRENT QUEUE — 2026-09-26

## Current milestone

The first real right-arm pick succeeded in one attempt and reached +100 mm lift HOLD.

Field result:

~~~text
CURRENT→50 mm pregrasp SUCCESS
contact approach SUCCESS
gripper close stable ~44–45 / 1000
15 cm local pointcloud grasp verification PASS
BODY +Z 100 mm lift SUCCESS
no fault/abort
left arm + AMR stationary
~~~

Primary problem now is speed/orchestration, not grasp correctness.

## Active engineering direction

Read:

~~~text
docs/research/2026-09-26_JAKA_FORCE_SENSOR_AND_FLOW_ACCELERATION.md
docs/work_orders/2026-09-26_P3_8D_FORCE_ASSISTED_FULL_FLOW_ACCELERATION.md
~~~

Goal:

~~~text
preserve successful pick
→ add JAKA force readout/monitoring
→ force-guard CONTACT_BYPASS_V1
→ force-first grasp verification
→ reduce unnecessary pointcloud scans
→ automate Scheme execution
→ extend HOLD through transfer + AMR + placement
→ optimize total cycle time
~~~

## Force sensor hypothesis

Current exact installed model is UNVERIFIED.

Strong candidate from official JAKA product matching:

~~~text
JK-SE-VI-200
~~~

Reason:

- JAKA Mini2 payload = 2 kg;
- JAKA recommends VI-200 for robot payload class <=5 kg;
- sensor appearance/round flange is consistent with JAKA VI-series.

Do not commit model identity until read from JAKA App/controller config or physical label.

## 145 mm vs 184 mm TCP hypothesis

The previous manual 145 mm measurement may have started from the force-sensor tool-side flange rather than the robot wrist flange.

Official VI-200/400/H mounting drawing includes an axial sensor dimension around 31.5 mm; sensor + adapter stack is plausibly of the same order as the observed ~39 mm discrepancy.

Record as hypothesis until physically verified.

## Force integration policy

First force integration is monitor-only:

~~~text
FORCE_MONITOR_V1
~~~

Do NOT enable constant-force compliance yet.

High-value uses:

1 contact guard during CONTACT_BYPASS_V1;
2 faster grasp verification via weight/load signal;
3 slip/drop monitoring during lift/transfer;
4 physical placement-contact monitoring;
5 release verification.

Important coordinate rule:

~~~text
tool +Z ≈ horizontal pick approach direction
BODY/world Z = gravity direction
~~~

Therefore tool-axis force is good for insertion/contact detection; grasped-object weight must be computed from the full force vector transformed into BODY/world vertical, not by blindly using raw Fz.

## Flow acceleration priorities

~~~text
1 native Scheme runner replaces conversational stage-by-stage launch
2 persistent Pixel Pro / cuRobo / telemetry / force services
3 full scene scans only at scene-lifecycle boundaries
4 force+gripper readback primary grasp verification
5 pointcloud grasp verification becomes fallback when force ambiguous
6 stage-specific motion speeds
7 asynchronous evidence/report generation
~~~

## Next implementation

Execute:

~~~text
docs/work_orders/2026-09-26_P3_8D_FORCE_ASSISTED_FULL_FLOW_ACCELERATION.md
~~~

First preserve/push the successful pick checkpoint if not yet canonical.

Then:

~~~text
force sensor readout audit
→ exact model identification if possible
→ force-frame calibration
→ empty-gripper baseline
→ FORCE_GUARDED_CONTACT_V1
→ FORCE_GRASP_VERIFY_V1
→ faster repeat pick
→ attached transfer
→ AMR move
→ right_place_rightmost
→ force-monitored place/release
→ full task timing optimization
~~~

## Existing contact collision policy

Keep:

~~~text
FREE_SPACE = full fresh-scene cuRobo collision avoidance
CONTACT = CONTACT_BYPASS_V1
~~~

Force monitoring augments CONTACT_BYPASS_V1; it does not replace free-space pointcloud avoidance.

Detailed gripper component collision remains post-demo hardening TODO and must not block the customer-flow acceleration.

## Git

No force-push.
Preserve the successful first-pick evidence.
Keep unrelated coworker changes separate.
Use small reviewed commits.
Leave .32/GitHub aligned after major checkpoints.