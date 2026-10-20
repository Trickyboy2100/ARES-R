# Center / GRASP preparation checkpoint, 2026-10-19

Deployment: isolated `/home/yikun/ARES-R-RC1-20261019`, not original production checkout. No push performed.

## Physical actions completed

- Operator manually removed the previous physical contact and recovered the controller. A new read-only native snapshot passed before any new command.
- A fresh cuRobo trajectory reached the canonical right center with Demo-only TCP-local-Z −10° compensation. Measured BODY TCP approximately `[0.357571,-0.078098,1.027592]m`. New operation: `worklog/evidence/operations-single/20261019-center-after-manual-clear-fresh/`; no reuse of the interrupted trajectory.
- Base returned sequentially BODY X−0.32m, Y+0.85m, X+0.40m at0.1m/s; each leg confirmed SETTLED. Evidence: `worklog/evidence/base-routes/20261019-return-grasp-after-center-once/`. SLAM samples retained as observations, not precision certification.
- No grasp, closing, lift, placement or complete Demo execution was started after this return.

## Final Demo semantics

Revision `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_19_V8_PICK_CENTER_NO_POST_CENTER`,21 stages.

`empty center → fresh ID1 → pregrasp/contact/grasp → lift230mm → base40/85/32cm → fresh ID3+slot offset+40mm → preland → continuous BODY-Z descent50mm → release/detach → base32/85/40cm`

No post-release center stage. Debugging30+20mm does not enter the recipe. If already within center position3mm / orientation0.6deg, the initial center stage issues no redundant motion. Post-grasp carrying stages retain the3deg compensated physical-level check. Only this Demo enables the temporary−10deg local-Z correction. Original detection poses, calibration and controller tool data remain unchanged.

## Planning-only evidence and software fixes

- Fresh ID1 and scene capture succeeded at GRASP.
- Fixed contact/lift validators to use the same explicit Demo compensation reference without increasing3deg tolerance. Previously the applied10deg correction was incorrectly treated as tilt.
- Fixed a list-alias bug: normalizing an equivalent IK goal by2π mutated only the first prechecked contact knot, causing an artificial full-turn discontinuity. Goals now own separate lists and the full contact/lift branch receives a constant representation shift. Added regression tests.
- FAST exceeded15s and was cancelled/reaped. QUALITY cuRobo solve succeeded in127.585s; complete worker request164.964s. Performance is NOT solved.
- Corrected frozen replay/repack passes: `worklog/evidence/20261019-grasp-from-center-frozen-repack-fixed/REPORT.json`. Same collision world, actual start, tool/model revisions and pregrasp geometric trajectory verified unchanged. Only corrected branch metadata and short-stage packaging regenerated in a network-isolated sandbox. This is NOT a fresh executable candidate.
- Native preview durations: pregrasp28.56s, contact55mm13.84s, initial lift100mm7.76s. Native validate-only calls passed. No sender execute call was made for these files.
- Additional130mm lift with the new compensation has not been re-executed. Full new cycle remains uncommissioned.
- Full regression734 tests,1 skipped, others passed.

## Next-click readiness

After successful new center/return, no active physical job, a passing controller snapshot and IDLE base, the OLD global software stop was recoverably renamed to `worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop-preserved-before-new-click-1792393847453414662.request`. It predates the operator's manual recovery; no newly issued stop was cleared. Old interrupted run remains historical, not resumed. Controller errors were NOT cleared by software.

WebUI `http://192.168.99.32:8775/` reports no new-launch blockers. Next physical run requires a new explicit click/authorization, fresh observation and fresh plan; frozen preview must not be executed. The lower-middle placement slot must be emptied/confirmed before another full cycle because the preceding release was confirmed successful.
