# Center, scan, cache and lower-fixture registration correction

Runtime: `/home/yikun/ARES-R-RC1-20261019`. Original production checkout/golden Demo unchanged. No push performed.

## Physical preparation completed

After successful placement/release and32/81/40 return, the empty right arm physically returned to center using a fresh environment-ON cuRobo path, with the temporary TCP-local-Z -10deg compensation retained. Measured BODY TCP XYZ `[0.3575679572,-0.0781078163,1.0275684610]` m. Center evidence: `worklog/evidence/operations-single/20261019-route810-center-preparation/`.

Fresh ID1 and PixelPro observation committed at base revision26. Grasp target BODY XYZ `[0.7760898702,-0.1635500314,0.9907295800]` m. Pregrasp planning succeeded via QUALITY after FAST deadline. Independent pregrasp world validation passed; modeled gap99.69mm. Pregrasp native duration28.96s; contact native also validated. This was not a physical pick.

## Why lift230 initially failed

The lower-fixture departure policy used a fixed BODY association region registered in `SCENE_91e06fd3a1b64086b0a190253d60ca25`. A fresh lower-fixture cuboid extended2.812mm beyond the10mm association allowance. Increasing association to15mm correctly associated that first cuboid but exposed another excluded lower structure, so this change alone was NOT reported as success.

The deeper issue was fixed-coordinate association despite the newly detected grasp target changing. Retrieved the exact original source request, whose grasp XYZ was `[0.7940735755,-0.2068534628,0.9902503200]` m. The policy now translates the original registration region by current-target minus this reference, preserving its dimensions, with a maximum60mm registration shift. The current shift is approximately `[-17.984,+43.303,+0.479]` mm. Camera calibration and raw detections are unchanged.

This is source-bound lower-fixture association, not a global collision-gap relaxation. Only gripper/payload departure from the identified lower region is permitted, with non-deepening contact and final separation required. Full-path arm/world, nonadjacent self collision, nonfixture obstacles, monotonic230mm BODY+Z, physical horizontal limit3deg, joint limits and native dynamics/tracking protections remain checked. No world object or point cloud is deleted.

## Exact failure replay passed

Used the SAME failed scene `SCENE_0e2d3f510cbd4c93bbd366f036185efb` and SAME source230mm path, not a lucky new scan. Original and retimed geometry proofs both passed. Native format validated, expected native duration13.68s; full frozen revalidation/packaging wall43.27s. No lift was physically executed in this preparation.

Evidence: `worklog/evidence/20261019-route810-anchored-fixture-preflight/REPORT.json`, `geometry-proofs.json`, `native-audit.json`, `native-validate.log`.

Earlier failures remain preserved in `worklog/evidence/20261019-route810-grasp-preparation/FAULT.json` and `worklog/evidence/20261019-route810-association15mm-preflight/FAULT.json`. The anchored-fixture report supersedes those specific frozen-scene failures, rather than erasing them.

## Cache sealed and selected

`worklog/evidence/demo-caches/right_arm_grasp_place_roundtrip_v1/center_pregrasp_minus10_route810_anchored_20261019/manifest.json`

Manifest SHA256 `b4d9ffcc23322d71a4fb0e43d15b0e3fd711f6a0cbcb08afe56867129ee3fbcb`.

The Demo selects this new cache under parameters V17. Cached target matching remains10mm/3deg. Hash/model/tool/calibration/start/base checks, fresh scene dense validation and fresh short-contact/lift checks remain mandatory on launch; no stale execution lease is reusable. The cache is pregrasp geometric path, not an unconditional full-cycle motion recording. New camera/state acquisition is still required before execution.

Full suite after the anchored policy:770 tests, one skipped, remaining passed (`worklog/evidence/20261019-target-anchored-fixture-tests.log`). No claim that planning latency is fixed or the entire updated Demo has run uninterrupted.

Current robot: GRASP station, empty right gripper at center. No additional base/arm/gripper movement during this collision-rule correction. Before another full placement, the tray just released at lower-middle PLACE must be removed.
