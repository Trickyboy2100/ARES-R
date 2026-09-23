# P4 — Scene-Aware WebUI over ART/backend

Date: 2026-09-23

## 0. Principle

The UI is a frontend over LocalSceneService + SceneAwareMotionService + ART.

No browser code calls JAKA, Pixel Pro or AMR directly.

The UI must make the corrected control hierarchy visible.

## 1. Layout

### Top status ribbon

Always show:

~~~text
BASE       MOVING / SETTLED
SCENE      INVALID / REQUIRED / SCANNING / READY / STALE / ERROR
PLANNER    IDLE / PLANNING / READY / FAILED
EXECUTION  IDLE / ARMED / EXECUTING / STOPPED / FAULT
~~~

Also show:

- base pose revision;
- scene epoch;
- SceneSnapshot ID;
- pointcloud age;
- calibration revision;
- scan / scene-build / planner timing;
- current motion speed profile.

### Center 3D viewport

BODY-frame view with:

- raw/current pointcloud;
- filtered pointcloud toggle;
- reconstructed generic collision primitives;
- full dual-arm robot;
- current TCP;
- target pose;
- planned trajectory;
- trajectory clearance overlay;
- camera frustum;
- inactive arm.

Normal UI must NOT contain editable manual obstacle boxes.

### Left: Scene panel

~~~text
[Scan]
[Invalidate]
Auto fresh: ON
Scene policy:
  AUTO_FRESH
  FORCE_RESCAN
  REUSE_IF_VALID
~~~

Show why the scene is invalid/stale and what event invalidated it.

After base motion, visibly show:

~~~text
SCENE REQUIRED
next arm motion will trigger scan
~~~

### Right: Motion panel

Inputs:

~~~text
arm
target source:
  named target
  BODY XYZ
  full pose

orientation:
  FREE
  CURRENT
  BODY_FORWARD_HORIZONTAL
  EXPLICIT

speed profile
attached object / none
~~~

Buttons:

~~~text
Plan
Preview
Execute
Stop
~~~

The panel submits a generic MotionRequest.

### Constraints panel

Show versioned constraints sent to cuRobo:

- orientation;
- keepouts;
- central exclusion;
- collision policy;
- planner preferred clearance policy;
- attached-object envelope.

Do not display preferred planner clearance as if it were a second independent safety law.

### Task/Demo panel

Convenience clients only:

~~~text
A/B run next
A/B loop
pick
place
inspect
named pose
~~~

Each client must call SceneAwareMotionService.

### ART panel

Embedded ART command input, history and event stream.

No browser shell.

## 2. Backend API

Recommended FastAPI + WebSocket.

Required service APIs:

~~~text
GET  /api/system/status
GET  /api/scene/status
POST /api/scene/scan
POST /api/scene/invalidate

POST /api/motion/plan
GET  /api/motion/{plan_id}
POST /api/motion/{plan_id}/execute
POST /api/motion/stop

POST /api/task/ab/run-next

WS   /api/events
WS   /api/scene/stream
~~~

Endpoints call the same Python services ART uses.

## 3. 3D data contract

The UI scene payload should expose:

~~~text
scene_epoch
scene_snapshot_id
base_pose_revision
pointcloud
collision_primitives
robot_geometry
tcp_pose
target_pose
trajectory
trajectory_metrics
timings
~~~

Pointcloud rendering and backend scan rate are decoupled.

## 4. Execution interaction

Execute button is enabled only when backend returns an executable plan handle bound to the current scene/state.

If scene/base/tool changes:

- plan card becomes STALE;
- Execute disables;
- UI explains the invalidation reason.

During motion:

- show progress;
- show actual TCP/joints;
- show measured tracking error;
- prominent STOP.

Keyboard shortcuts may exist, but physical E-stop remains external.

## 5. Arbitrary-scene demo UI

The demo sequence should visibly show:

~~~text
place arbitrary obstacle
→ Scan
→ pointcloud appears
→ collision primitives appear
→ Plan
→ cuRobo trajectory appears around observed geometry
→ Execute
~~~

Then move the obstacle and scan again:

- old primitives disappear/change;
- new scene epoch appears;
- old plan becomes stale;
- new trajectory differs.

This is the primary visual proof of scene-aware motion.

## 6. Exit

Report:

~~~text
WEBUI_BACKEND_PARITY = YES/NO
WEBUI_LOCAL_SCENE_STATE = YES/NO
WEBUI_GENERIC_MOTION_REQUEST = YES/NO
WEBUI_PLAN_STALE_INVALIDATION = YES/NO
WEBUI_ARBITRARY_SCENE_VISUALIZATION = YES/NO
WEBUI_ART_EMBEDDED = YES/NO
~~~
