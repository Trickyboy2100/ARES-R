# P0-B dual-arm Epic hand-eye cross-check

## Verdict

`COMMISSIONED`; P1 may begin. No AMR, arm, or gripper command was issued.

The Epic Pro eye-to-hand matrices mean `T_armbase_camera`. Independent BODY
composition gives camera origins:

- left: `[0.091874243, -0.084154537, 1.565735800] m`;
- right: `[0.091844968, -0.083593395, 1.564976800] m`.

The H1 disagreement is `0.944 mm / 0.722 deg`. Inverting the Epic matrices
(H2) creates `332.186 mm / 56.574 deg` disagreement and is rejected.

The right-derived transform projects the captured board origin to
`[1.064357, 0.486970, 0.751948] m` in BODY. Its +Z normal is `1.082 deg` from
BODY +Z and its height is `1.948 mm` above the measured `0.750 m` table. The
left-derived board origin is `[1.054765, 0.483005, 0.738989] m`; the larger
`16.603 mm` point difference is consistent with applying the observed
`0.722 deg` calibration rotation residual across the approximately `1.3 m`
camera-to-board lever arm.

Existing pointcloud evidence independently reports a level support plane at
`0.417 deg` tilt and a ground band at BODY `z=-0.00743 m` from 44,043 points.
The support/table plane at about `z=0.750 m` and ground at `z=0 m` are treated
as separate physical surfaces.

`config/system.json` already contains the right H1 result and remains
unchanged numerically. Left is retained as an independent validation source;
the transforms are not averaged. See `report.json` for the machine-readable
matrices, rounding analysis, evidence links, and validation revision.
