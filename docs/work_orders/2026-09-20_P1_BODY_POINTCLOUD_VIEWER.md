# P1 — BODY point cloud transform and 3D viewer

## 0. Entry gate

P1 starts only after P0-B is pushed and the commissioned transform/revisions are present on the integration branch.

Expected source:

~~~text
config/system.json
epic_pointcloud.T_body_camera
epic_pointcloud.T_body_camera_revision
validation provenance from P0-B
~~~

No self-filter. No cuRobo planning. No AMR/arm/gripper motion.

Camera capture is allowed.

## 1. P1-A — one canonical runtime transform

Implement one canonical in-memory path:

~~~text
raw Pixel Pro points in CAMERA/mm
→ invalid removal
→ mm→m exactly once
→ fixed COMMISSIONED T_body_camera
→ BODY/m point cloud
~~~

Provide a reusable API, not a one-off script.

Requirements:

- explicit input frame and units;
- vectorized transform;
- output frame = BODY from config/robot_world.json;
- calibration revision attached to every artifact;
- no per-frame ICP;
- no table fitting used to alter T_body_camera;
- no alternate DEMO_ONLY transform.

Recommended module boundary:

~~~text
src/ares_r/perception/body_pointcloud.py
~~~

## 2. P1-A validation using evidence already available

Before asking the user to move anything, reuse current evidence and/or take a fresh stationary camera capture.

### V1 vendor board

Use the known board frame definition and SDK pose.

Display/record:

- board frame in BODY;
- board pointcloud patch if available;
- board origin BODY xyz;
- board +Z vs BODY +Z;
- calibration revision.

Do not refit T_body_camera to the board.

### V2 table

Fit the support table after CAMERA→BODY transform.

Report:

- table mean/median BODY z;
- normal angle to BODY +Z;
- frame-to-frame repeatability.

Physical reference:

~~~text
table top ≈ 0.750 m
~~~

Do not confuse table with ground.

### V3 existing robot/base sanity overlay

Show:

- BODY origin;
- left/right base frames from config/robot_world.json;
- CAMERA frame from commissioned T_body_camera;
- raw transformed pointcloud.

No self-filter yet. Robot-owned points are allowed to remain.

## 3. P1-A snapshot viewer

Implement:

~~~text
src/ares_r/visualization/body_cloud_viewer.py
~~~

Use Open3D first.

Viewer must display:

- BODY axes;
- CAMERA frame;
- left base frame;
- right base frame;
- vendor board frame when visible;
- table plane;
- BODY point cloud;
- optional point selection / coordinate readout;
- calibration state + transform revision.

Terminal commands:

~~~text
scene body-cloud capture
scene body-cloud show
scene body-cloud inspect
~~~

The viewer must consume the same BODY cloud object/artifact as later planning code, not a separately transformed display copy.

## 4. P1-B — one simple known-object hold-out

Only after P1-A works.

If no suitable existing object has independently known BODY position/dimensions, STOP and ask exactly one user action:

~~~text
USER ACTION 1
目的：用一个独立物体验证 BODY 点云的绝对位置。
你现在做：在桌面上放一个规则盒子，告诉我它相对 BODY 原点的大致中心 X/Y 和盒子长宽高；不需要移动机器人。
完成后回复：已放置，并给出 X/Y/尺寸。
安全边界：不移动底盘、机械臂或夹爪。
~~~

Then:

- fresh scan;
- transform to BODY;
- select/cluster the box without changing T_body_camera;
- compare AABB center/dims to manual hold-out measurement;
- record error.

## 5. P1-C — adjustable-rate viewer prototype

Only after snapshot validation is satisfactory.

Terminal:

~~~text
scene body-cloud live --interval 2.0
~~~

Requirements:

- manual Scan Once is always available;
- auto scan on/off;
- interval user-adjustable;
- camera acquisition frequency and GUI render frequency are separate;
- live viewer may retain the last cloud between scans;
- report actual achieved scan interval/latency;
- do not call it real-time perception if backend cannot sustain requested rate.

P1-C is still raw BODY cloud: no self-filter, no cuRobo.

## 6. Tests and artifacts

At minimum:

- unit tests for unit conversion + rigid transform;
- transform revision propagation test;
- regression test using current commissioned matrix;
- snapshot viewer smoke test without hardware;
- repo-local evidence under logs/worklog only.

## 7. Exit criteria

Report:

~~~text
BODY_POINTCLOUD_READY_FOR_SELF_FILTER = YES/NO
BODY_CLOUD_VIEWER_READY = YES/NO
LIVE_VIEWER_PROTOTYPE_READY = YES/NO
~~~

Include:

- board residuals;
- table residuals;
- known-object hold-out error if P1-B was run;
- snapshot screenshot;
- measured capture/transform/view latency;
- local commit SHA;
- tests.

## 8. Push policy

Commit locally on:

~~~text
feat/e2e-v0-integration-20260917
~~~

Then STOP.

Do not push P1 automatically. User will return to ChatGPT for review and explicit push instruction.
