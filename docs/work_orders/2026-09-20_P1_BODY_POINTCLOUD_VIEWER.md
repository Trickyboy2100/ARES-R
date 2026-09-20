# P1 — BODY point cloud transform and 3D viewer

## 0. Entry gate

P1 starts only after P0 has produced a CANDIDATE or COMMISSIONED T_body_camera with explicit revision.

No self-filter yet.

## 1. Runtime transform

Implement one canonical in-memory function:

~~~text
BODYCloud = transform_camera_cloud(points_camera, T_body_camera)
~~~

Requirements:

- input source units explicit;
- mm→m exactly once;
- homogeneous transform vectorized;
- output BODY convention from config/robot_world.json;
- calibration revision bound to every result;
- no per-frame ICP or re-calibration.

## 2. Validation sequence

### V1 vendor board

Transform board SDK pose and pointcloud patch into BODY.

Show:

- BODY board frame;
- board pointcloud patch;
- center / normal residual.

### V2 table

Fit support plane after BODY transform.

Report:

- mean z;
- normal angle to +Z;
- frame-to-frame std.

Expected physical reference: table top ≈ 0.750 m.

### V3 known obstacle

Put one simple box/object on table and measure its approximate BODY position and dimensions.

Compute pointcloud cluster/AABB and report center/dim error.

Do not use the measured box pose to refine T_body_camera; it is hold-out validation.

## 3. Snapshot viewer

Implement:

~~~text
src/ares_r/visualization/body_cloud_viewer.py
~~~

Use Open3D first.

Display:

- BODY axes and origin;
- CAMERA frame;
- left/right arm base frames;
- vendor board frame when visible;
- table plane;
- BODY point cloud;
- optional cluster/AABB;
- calibration status + revision overlay.

Terminal:

~~~text
scene body-cloud capture
scene body-cloud show
scene body-cloud inspect
~~~

## 4. Live viewer prototype

Only after snapshot works.

Terminal:

~~~text
scene body-cloud live --interval 2.0
~~~

Requirements:

- adjustable scan interval;
- manual scan trigger;
- rendering can stay responsive between scans;
- backend scan frequency and GUI rendering frequency are separate;
- do not claim “real-time perception” if camera acquisition is slow.

## 5. Exit

Report:

~~~text
BODY_POINTCLOUD_READY_FOR_SELF_FILTER = YES/NO
~~~

with board/table/box residuals and screenshots.

No cuRobo planning in P1.
