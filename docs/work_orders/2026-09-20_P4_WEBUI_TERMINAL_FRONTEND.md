# P4 — WebUI frontend over ARES-R Terminal/backend

## 0. Principle

UI is frontend only.

No direct hardware API calls from browser/frontend code.

All actions route through the same ARES-R backend command/service layer used by Terminal.

## 1. Backend refactor

Extract Terminal command dispatch into reusable service functions if needed.

Required backend capabilities:

~~~text
execute_terminal_command(text) -> stream/events
get_world_snapshot()
get_body_cloud_snapshot()
trigger_scene_scan()
set_scene_scan_interval(seconds)
set_target_pose(...)
plan_target(...)
execute_planned_motion(...)
amr_move_relative(...)
amr_stop()
~~~

Terminal and WebUI must share these implementations.

## 2. 3D scene

Recommended first implementation:

- FastAPI backend;
- WebSocket event stream;
- Three.js frontend.

Display in BODY frame:

- BODY axes;
- camera frame;
- left/right base;
- dual-arm robot model;
- current TCPs;
- table/known geometry;
- pointcloud;
- obstacle AABB/OBB;
- target pose marker;
- planned TCP/robot trajectory.

## 3. Pointcloud controls

UI:

- Scan once button;
- Auto scan toggle;
- Scan interval numeric/slider control;
- Last scan timestamp;
- scene/calibration revision;
- show/hide raw cloud;
- show/hide obstacle boxes;
- show/hide robot points/model.

Rendering FPS is independent of scan rate.

## 4. Target pose controls

Fields:

~~~text
arm = left/right/auto
x y z BODY meters
roll pitch yaw optional
orientation preset:
  BODY_FORWARD
  CURRENT
  explicit
~~~

If RPY blank, default to BODY_FORWARD semantic profile.

Buttons:

~~~text
Set target
Preview
Plan
Execute
Stop
~~~

Execute remains backend-gated.

## 5. AMR controls

Buttons:

~~~text
Forward
Backward
Left
Right
Stop
~~~

Distance/speed inputs bounded by site limits.

UI may not bypass existing Terminal/backend motion authorization.

## 6. Embedded Terminal

Provide:

- input box;
- command history;
- stdout/stderr/event stream;
- same command parser as native Terminal.

No browser shell.

## 7. Exit

Report:

~~~text
WEBUI_BACKEND_PARITY = YES/NO
WEBUI_SCENE_READY = YES/NO
WEBUI_MOTION_CONTROLS_GATED = YES/NO
~~~
