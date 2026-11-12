# Runtime goal IK and pregrasp cache correction

Deployment: `/home/yikun/ARES-R-RC1-20261019`. No robot/base/gripper motion was issued during this correction. Original tree and golden Demo unchanged.

- Runtime BODY goal IK now uses the requested task tolerance, capped at 3mm/3deg. Existing short/contact IK calls retain the previous default 1.5mm/0.6deg. At most four endpoint seed attempts; these are numerical starting guesses, not waypoints. Failed diagnostics include residuals rather than claiming absolute physical unreachability.
- Demo parameters V14 set cached target-position matching to 10mm and target-orientation matching to 3deg. Base revision, start joints, tool/calibration/geometry/hash checks, fresh scene collision validation and fresh short contact/lift precheck remain required. Passing the 10mm eligibility rule alone does not force reuse if the resulting contact path is invalid.
- Demo HTTP failures now preserve the response body instead of reporting only 409.

Changed source: `src/ares_r/motion/runtime_goal_ik.py`, `src/ares_r/motion/production_scene_worker.py`, `scripts/run_grasp_place_roundtrip.py`, `demos/right_arm_grasp_place_roundtrip_v1/parameters.json`. Tests: `tests/test_runtime_goal_task_tolerance.py`, `tests/test_pregrasp_cache.py`.

Original failed PLACE request replay: IK now accepted with position error1.844766mm and orientation error0.796642deg, unchanged target.

Fresh current-to-same-preland validation: first FAST fresh scene rejected modeled start collision; second QUALITY fresh scene passed endpoint checks, entered actual cuRobo solve, generated a hard-valid path and native execution package. Scan-to-result two-attempt wall131.681s; not a latency improvement claim. The scan-to-scan start-collision inconsistency remains recorded, not silently fixed by tolerance changes.

Successful plan: `PLAN_367a64a91532466bb6540a4096e863fc`.

Exact trajectory SHA: `sha256:3b7b7ed11ec3210b3135be33155bdb7a9786dd6b6b38d3fbe6a6ce0128c6bb28`.

Hard modeled minimum gap5.165mm, start14.369mm. No collision margin was disabled. These are modeled checks, not a new physical commissioning claim.

Evidence: `worklog/evidence/20261019-place-ik3mm3deg-fresh-preflight/` and `worklog/evidence/scene-aware-motion/PLAN_367a64a91532466bb6540a4096e863fc/`.

Full suite:759 tests, one skipped, remaining passed; log `worklog/evidence/20261019-ik3mm3deg-cache10mm-tests.log`.

Demo remains stopped at PLACE holding the object. No automatic resume or execution authorization is inferred from this software-fix request. Newly prepared native packages retain expiry and scene/state binding.
