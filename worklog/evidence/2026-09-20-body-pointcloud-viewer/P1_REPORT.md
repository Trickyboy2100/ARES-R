# P1 BODY point cloud viewer — completion report

## Exit status

```text
BODY_POINTCLOUD_READY_FOR_SELF_FILTER = YES
BODY_CLOUD_VIEWER_READY = YES
LIVE_VIEWER_PROTOTYPE_READY = YES
```

Scope remained P1 only.  No AMR, arm, or gripper command was issued.  No ICP,
extrinsic refit, robot self-filter, cuRobo planning, or WebUI was implemented.

## Canonical transform

The only runtime path is:

```text
Pixel Pro CAMERA/mm
-> remove non-finite and zero points
-> mm-to-m exactly once
-> fixed COMMISSIONED T_body_camera
-> BODY/m
```

- Transform revision: `sha256:ccb214ea13b7020528d98d7a532908427c25d61c3ce1d40bd0a833e61a7a4e6c`
- Validation revision: `sha256:23e44f93cb0b498792e8069628448f53813eed0b38a4951fb1b5e034764b7e11`
- Right-arm hand-eye is the production source; left-arm hand-eye remains an
  independent cross-check.  No averaging is performed.

## P1-A evidence

- Vendor-board origin in BODY: `[1.064357, 0.486970, 0.751948] m`.
- Board +Z versus BODY +Z: `1.082 deg`.
- Board origin/table-height residual: `+1.948 mm`.
- Three stationary table medians: `0.745427 / 0.745499 / 0.745511 m`.
- Table residual from 0.750 m: `-4.573 .. -4.489 mm`.
- Table median peak-to-peak repeatability: `0.084 mm`.
- Table normal-angle range: `0.684 .. 0.688 deg`; peak-to-peak `0.0042 deg`.

The Open3D snapshot includes the complete unfiltered BODY cloud plus BODY,
CAMERA, left/right arm-base and board frames and the table plane.  The image
legend records every frame origin, units, calibration state and transform
revision.  Interactive point picking prints BODY XYZ in metres.

Raw snapshot:

`logs/body_cloud/artifacts/20260920_150319_26820efb/body_cloud_snapshot.png`

## P1-B independent box hold-out

The box was rotated so that all three dimensions were visible.  A stationary
pre-placement BODY cloud was compared with a fresh hold-out cloud.  The
validation-only method was 3 mm voxel downsampling, current-to-baseline nearest
distance over 10 mm, and largest DBSCAN cluster.  It did not change
`T_body_camera`.

| quantity | manual | BODY cloud | error |
|---|---:|---:|---:|
| X dimension | 78 mm | 83.8 mm | +5.8 mm |
| Y dimension | 205 mm | 209.1 mm | +4.1 mm |
| Z dimension | 224 mm | 230.5 mm | +6.5 mm |
| center X | about 0.835 m | 0.8206 m | -14.4 mm |

Cloud center: `[0.8206, +0.1719, 0.9581] m`; the positive Y sign agrees with
the independently stated placement to the robot's left.  Cloud bottom:
`z=0.8429 m`, agreeing with the stated bottom height above 0.8 m.  The manual
X value was approximate, so the `14.4 mm` result is reported as a residual,
not an external metrology accuracy claim.

Evidence:

- `worklog/evidence/2026-09-20-body-pointcloud-viewer/p1b_holdout.json`
- `worklog/evidence/2026-09-20-body-pointcloud-viewer/p1b_holdout.png`

## P1-C native viewer prototype

ARES-R Terminal commands:

```text
scene body-cloud capture
scene body-cloud inspect
scene body-cloud show
scene body-cloud live --interval 2.0
```

The native Open3D live window provides `Scan Once`, auto-scan on/off and an
interval editor.  A dedicated camera scheduler/acquisition worker is separate
from the GUI render loop, and the last complete cloud remains visible during a
scan.  The site SSH session has no DISPLAY, so the native window was not
visually inspected in this run; the same geometry path was validated through
Open3D EGL snapshots and its scheduler was camera-benchmarked headlessly.

At a requested 2.0 s interval, three complete scan pipelines took
`5.636 / 5.652 / 5.984 s`; measured scan-start intervals were
`5.636 / 5.652 s`.  Therefore this is explicitly a **snapshot-rate viewer**,
not real-time perception.  GUI rendering is not rate-coupled to camera scans.

Benchmark:

`worklog/evidence/2026-09-20-body-pointcloud-viewer/live_benchmark.json`

## Latency summary

- Pixel Pro SDK capture: approximately `4.645 .. 4.657 s`.
- PLY load + invalid removal + unit/SE(3) transform: `0.195 .. 0.211 s`.
- EGL snapshot render, 2.03 million points: `2.524 s`.
- Live full scan/artifact pipeline: `5.636 .. 5.984 s`.

Self-filter and cuRobo remain deliberately `NOT_RUN`.  P1 output is ready to be
reviewed before starting the separate self-filter phase.
