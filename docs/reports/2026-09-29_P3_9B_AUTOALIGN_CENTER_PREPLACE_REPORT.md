# P3.9B Auto-align → Center → Preplace Report

## Scope and baseline

- Integration baseline: `6075295f77418a9a171a8ceef0d436e2c13ca461`.
- Golden fallback preserved unchanged: `right_arm_epic_pick_lift_v1` and
  `scripts/run_first_pick_demo.py`.
- New additive Demo: `right_arm_autoalign_pick_center_preplace_v1`.
- Endpoint: `HOLD_ABOVE_PLACE`; no descent and no gripper release.
- AMR yaw is fixed at zero. Each alignment episode is bounded to BODY X ±0.15 m
  and BODY Y ±0.40 m and requires the real completion observer plus a fresh
  ObservationEpoch before acceptance.

## Recovered center pose

`center` was recovered from the coworker site patch and 2026-09-28 execution
evidence; it is not an alias of `ready`.

- BODY TCP: `[0.3583093030, -0.0800000000, 1.0278356006, π/2, 0, π]`.
- right joints: `[-4.1605421892, 0.1238015955, -1.6410621564,
  -5.6094006963, -1.1920778259, -2.6569721083]` rad.
- Evidence: `worklog/evidence/2026-09-28-place/center_exec_20260928T172814/`.
- The recorded cuRobo/native execution contained 138 samples over 10.96 s and
  ended with zero joint endpoint residual while retaining a level carried tray.

## Motion and scene policy

- `current→pregrasp`, `initial-lift→center`, and `center→above-place` use a fresh
  pointcloud scene and cuRobo. No direct joint-move fallback is present.
- Only the already-commissioned pick contact window retains
  `CONTACT_BYPASS_V1`.
- The historical central exclusion is `|BODY Y| <= 0.07 m` (14 cm total). It is
  a versioned switch and is OFF for P3.9B. Real environment, inactive arm,
  self-collision, JAKA controller limits/collision/estop and tracking gates stay
  enabled.
- Attached-object geometry is carried through the center and preplace cuRobo
  requests.

## Fresh preflight

Artifact:
`worklog/evidence/2026-09-29-p3-9b/runs/preflight_20260929T104716/p39b_preflight_package.json`

- PICK target: `[0.706784, +0.233145, 0.995272] m`.
- Predicted PICK base correction: `(+0.006784, +0.400000) m`.
- PLACE target: `[0.706999, -0.188742, 0.957792] m` at the initial base station.
- Predicted PLACE correction from the PICK-aligned station:
  `(+0.000215, -0.338742) m`.
- Final corrections are never executed from these predictions alone. The live
  runner re-detects after each truthful settle and replans from the resulting
  fresh scene.

The place target binding bug was corrected generically: observed primitives are
first restricted by the 80 mm spatial gate, then purpose semantics and distance
select among those local candidates. A fresh place epoch bound to
`SUPPORT_SURFACE` at 13.1 mm instead of selecting a distant semantic object.

## Runtime, ART/WebUI, and autostart

- Canonical backend: `src/ares_r/canonical_backend.py`, port 8766.
- Supervised runner: `scripts/run_p39b_supervised.py`.
- WebUI: port 8765 and a client of the same backend.
- systemd user units are enabled and active; user lingering is enabled.
- Boot policy is `ARES_R_BOOT_NO_MOTION=YES`; services start at boot but no task
  starts without the exact supervised authorization.
- ART `system info` and WebUI report the same ARES-R version, Git SHA,
  TaskRuntime/Scheme version and central-exclusion state.
- Rear/robot-forward display invariant is tested: BODY +Y is left; left base
  Y=+0.20 renders screen-left of right base Y=-0.20. BODY data is not mirrored.

## Validation

- Declarative Scheme: 15 nodes, replay `SUCCEEDED`, final node
  `hold_above_place`; no release node.
- Golden fallback content hashes unchanged.
- Full repository regression before authorization: 554 tests OK, 1 skipped.
- Physical motion had not been sent when this pre-authorization checkpoint was
  written.

## Readiness checkpoint

```text
CENTER_POSE_SOURCE_VERIFIED=YES
CENTRAL_EXCLUSION_SWITCH_READY=YES
CENTRAL_EXCLUSION_CURRENTLY_OFF=YES
ALL_FREE_SPACE_ARM_P2P_VIA_CUROBO=YES
AUTO_ALIGN_PICK_READY=YES
AUTO_ALIGN_PLACE_READY=YES
CENTER_TRANSFER_CUROBO_READY=YES
WEBUI_ART_AUTOSTART_READY=YES
WEBUI_LEFT_RIGHT_VERIFIED=YES
NEW_DEMO_REPLAY_PASS=YES
READY_FOR_P39B_SUPERVISED_RUN=YES
```

The supervised checkpoint will append actual PICK/PLACE base displacement,
cuRobo trajectory evidence and final `HOLD_ABOVE_PLACE` result after execution.
