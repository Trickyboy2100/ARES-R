# Next Demo: verified placement contact and preparation

Scope: independent `/home/yikun/ARES-R-RC1-20261019`; original production tree and golden first-pick unchanged. This preparation authorizes only the empty right arm returning to center plus observation/planning. No new pick or full cycle is started.

## Placement change

`Live.place_descend()` in `scripts/run_grasp_place_roundtrip.py` now reuses the physically verified standalone 50mm placement method, rather than treating descent into the dock as a new free-space cuRobo target. It acquires a fresh attached scene and current arm state, solves a constant-orientation BODY -Z descent at 2mm knots, validates the source and retimed paths, packages the native supervised path, and requires `target_reached`, successful servo disable and stable arrival before permitting release.

`src/ares_r/manipulation/demo_place_contact.py` preserves the successful local contact treatment: split measured lower support boxes at the target-relative contact-region boundary; permit tool/payload contact only inside the registered region. Outside pieces, unknown obstacles and the original world for arm-link/self checks remain hard. This is NOT global shrinking of obstacles or deletion of all dock points. It is scoped to the 50mm descent at the fresh ID3 lower-middle preland; it does not affect free-space approach.

The already tested release readback and base return remain unchanged: raw 400 then confirm readback, detach, BODY back 0.32m, left 0.85m, forward 0.40m. No post-release arm stow. Demo-local TCP Z -10deg compensation remains enabled exactly once.

Parameters revision: `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_19_V13_VERIFIED_PLACE_CONTACT50`.

## Preparation evidence

Center: `worklog/evidence/operations-single/20261019-next-demo-center-fresh/`.

Fresh ID1, point cloud, pregrasp/contact/lift preparation: `worklog/evidence/20261019-next-demo-grasp-preparation/`. Its terminal `REPORT.json` or `FAULT.json` is authoritative; the existence of this report does not assert planning success.

Center was reached using fresh environment-ON cuRobo planning. Measured BODY TCP XYZ: `[0.3575627200, -0.0781063538, 1.0275696265]` m. Native elapsed 33.964s; max tracking error 0.324deg.

Tests: 754 run, one skipped, all others passed after motion completed. The initial parallel test run contended with the real sender's mutual-exclusion lock; it is retained in `20261019-next-demo-tests.log`, followed by the successful idle rerun `20261019-next-demo-tests-idle.log`. No lock was bypassed.

No claim that a new automatic complete cycle is physically commissioned: the last whole cycle faulted at generic place-descent planning and was completed by separately authorized actions. This revision integrates that successful completion method; a full automatic run still needs acceptance. The lower-middle dock now contains the last released tray and must be emptied before another placement.

## Completed preparation

Fresh ID1/point cloud preparation passed, including contact and continuous 230mm lift native validation. Total preparation 216.887s: FAST timed out, then QUALITY solved in 103.446s (133.609s request wall). This is not a sub-second preparation claim. New geometric cache is sealed at `worklog/evidence/demo-caches/right_arm_grasp_place_roundtrip_v1/center_pregrasp_minus10_next_20261019/manifest.json`, bound to base revision 13; next launch must still verify fresh detection/state and fresh collision world. No old execution lease is reusable.

Grasp target BODY XYZ: `[0.788011033, -0.197346363, 0.990523680]` m. Native trajectory durations: pregrasp 28.96s, contact 12.96s, continuous lift230 13.92s. These exclude preparation, evidence and settling overhead. Package SHA256: `1ce20e338f0764c8b27b04f58c9f58a96eab6f72078c5502856a280e26730735`.
