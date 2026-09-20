# P1-A canonical BODY point cloud — stationary validation

Status: `P1-A PASS`.  See `P1_REPORT.md` for completed P1-B/P1-C results.

No AMR, arm, or gripper command was issued.  Three stationary Pixel Pro scans
were acquired through the ARES-R Terminal `calibration` device scope, where
both arms and both grippers are disabled.  No ICP, extrinsic fitting,
self-filter, or cuRobo path is present in this implementation.

## Canonical path

`CAMERA/mm PLY -> invalid/zero removal -> mm-to-m exactly once -> fixed
COMMISSIONED T_body_camera -> BODY/m`

- Transform revision: `sha256:ccb214ea13b7020528d98d7a532908427c25d61c3ce1d40bd0a833e61a7a4e6c`
- Validation revision: `sha256:23e44f93cb0b498792e8069628448f53813eed0b38a4951fb1b5e034764b7e11`
- Source arm: right; cross-check arm: left; fusion: none.

## Vendor board check reused from P0-B

- Right-derived board origin in BODY: `[1.064357, 0.486970, 0.751948] m`.
- Board origin height residual from 0.750 m table: `+1.948 mm`.
- Board +Z angle to BODY +Z: `1.082 deg`.
- Left-derived board origin in BODY: `[1.054765, 0.483005, 0.738989] m`.
- Left/right board-point disagreement: `16.603 mm`; this includes the
  independently measured `0.722 deg` hand-eye rotation residual over the long
  camera-to-board lever arm.  The viewer uses the commissioned right-derived
  board pose and does not average or refit it.

## Stationary table repeatability

| frame | valid points | median z (m) | error from 0.750 m (mm) | +Z angle (deg) | canonical transform (s) | camera capture (s) |
|---|---:|---:|---:|---:|---:|---:|
| 1060 | 2,031,980 | 0.745427 | -4.573 | 0.688 | 0.203 | 4.657 |
| 1061 | 2,031,368 | 0.745499 | -4.501 | 0.684 | 0.200 | 4.650 |
| 1062 | 2,031,973 | 0.745511 | -4.489 | 0.684 | 0.195 | 4.645 |

- Median-height peak-to-peak repeatability: `0.084 mm`.
- Normal-angle peak-to-peak repeatability: `0.0042 deg`.
- Table result is validation-only and never alters `T_body_camera`.

## Viewer and terminal

Commands:

```text
scene body-cloud capture
scene body-cloud inspect
scene body-cloud show
```

The Open3D viewer consumes the same compressed BODY cloud artifact returned by
the canonical API.  It contains BODY, CAMERA, left base, right base, board
frames, the table validation plane, and the complete unfiltered point cloud.
Interactive point-picking prints selected BODY XYZ in metres.  Headless mode
renders a labeled 1600x1000 snapshot using EGL.

Latest snapshot on the site host:

`logs/body_cloud/artifacts/20260920_150319_26820efb/body_cloud_snapshot.png`

Snapshot rendering of 2,031,973 points took `2.514 s`.  Interactive rendering
has not been measured over the headless SSH session.

## Gate

P1-A passed and the independent hold-out was subsequently completed.  See the
P1 completion report for the final gate.
