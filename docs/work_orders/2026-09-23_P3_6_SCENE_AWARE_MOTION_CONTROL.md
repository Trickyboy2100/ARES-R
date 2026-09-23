# P3.6 — Refactor obstacle avoidance into the low-level Scene-Aware Motion layer

Date: 2026-09-23

Read first:

~~~text
docs/architecture/2026-09-23_SCENE_AWARE_MOTION_STACK.md
~~~

## 0. Why P3.6 supersedes the old P3.5 execution path

P3.5 proved that a fresh random scene can be reconstructed and cuRobo can produce an avoidance path.

However, the current execution stack still contains an A/B-specific post-planning clearance gate. In S1 the planner found a collision-free route, but a fixed 30 mm demo gate rejected it because the obstacle was already close to the start pose.

That is a layering problem.

P3.6 must move collision avoidance and preferred clearance into the generic motion-planning layer, while leaving the execution layer responsible only for hard safety/binding validity.

P3.5 random-scene evidence is retained, but do not continue random-box experiments through the old gate.

## 1. Preserve current state first

Before refactoring:

1. verify integration GitHub HEAD;
2. record .32 HEAD/dirty/untracked state;
3. preserve current P3.4/P3.5 field evidence;
4. keep coworker AMR dirty changes isolated;
5. run current tests;
6. create a clean checkpoint if required.

No force-push.

## 2. Implement LocalSceneService

Create a canonical service module (exact filename may adapt to repo style), conceptually:

~~~text
LocalSceneService
  status()
  invalidate(reason)
  scan(force=False)
  ensure_fresh(reason, policy)
  snapshot()
~~~

Required state:

~~~text
INVALID
REQUIRED
SCANNING
READY
STALE
ERROR
~~~

Bind scene to:

- base pose revision;
- calibration revision;
- robot geometry revision;
- tool revision;
- pointcloud SHA;
- timestamp/epoch.

Existing fast Pixel Pro + generic decomposition from P3.4/P3.5 must be reused, not rewritten.

## 3. Base-motion invalidation

Wire AMR lifecycle into scene lifecycle.

Required semantics:

~~~text
AMR movement starts
→ scene.invalidate("BASE_MOVING")

AMR movement completes and settles
→ increment base_pose_revision
→ scene state = REQUIRED
~~~

Any subsequent free-space arm motion must automatically call ensure_fresh() before cuRobo planning.

Do not put this logic in pick/place/A-B task code.

Tests must prove an arm plan is rejected if it tries to reuse a scene from before the base move.

## 4. Implement generic SceneAwareMotionService

Create one generic arm-motion backend used by tasks.

Conceptual contract:

~~~text
MotionRequest(
    arm,
    goal,
    constraints,
    speed_profile,
    scene_policy
)

plan(request)
preview(plan_id)
execute(plan_id)
move(request)
stop()
status()
~~~

The service must:

1. obtain/freshen LocalScene;
2. bind live robot/tool/inactive-arm state;
3. update persistent cuRobo world;
4. apply generic constraints;
5. plan direct start→goal with cuRobo;
6. validate hard execution validity;
7. package/bind exact trajectory;
8. execute only through existing native/SafetyKernel route.

A/B demo must become a thin client of this service.

## 5. Generic planner constraints

Promote the current BODY-forward-horizontal override into a reusable constraint interface.

Minimum V1:

~~~text
orientation:
  FREE
  CURRENT
  BODY_FORWARD_HORIZONTAL
  EXPLICIT

keepout:
  BODY central exclusion

scene:
  AUTO_FRESH
  FORCE_RESCAN
  REUSE_IF_VALID

speed_profile:
  named/versioned
~~~

Do not write A/B-specific conditionals inside cuRobo worker for these constraints.

A future pick/place skill should be able to submit the same constraint object.

## 6. Correct clearance layering

Refactor current fixed demo clearance gate.

### 6.1 Planner-side preferred clearance

Desired obstacle stand-off belongs to the planner profile and collision geometry:

- obstacle/tool inflation;
- optimizer collision activation;
- cost weights;
- candidate selection.

This is where cuRobo should be encouraged to generate the farther route.

### 6.2 Hard execution validation

Independent validation remains mandatory but should answer:

~~~text
Is the trajectory bound to the correct fresh scene/state?
Does any collision geometry penetrate?
Are central exclusion/controller/dynamics/native limits valid?
Does the independent model materially disagree with the planner?
~~~

It should NOT reject a valid path solely because a task-specific preferred margin such as 30 mm was missed.

### 6.3 Near-start / escape semantics

Implement an explicit state for:

~~~text
START_COLLISION
START_NEAR_OBSTACLE
NORMAL
~~~

If start is collision-free but closer than the planner's preferred clearance:

- allow cuRobo to plan away from the obstacle;
- validate that the initial escape does not decrease into penetration;
- require the path to recover toward the planner clearance where feasible;
- record the start gap and clearance evolution.

Do not silently permit penetration.

Do not encode a universal 30 mm hard floor.

Output planner policy and hard-validity results separately.

## 7. Remove A/B-specific obstacle logic

Audit runtime code.

A/B may retain:

- endpoint A/B goal poses;
- orientation/speed constraint presets;
- demo run counter.

A/B may NOT own:

- scene scanning implementation;
- obstacle decomposition;
- obstacle IDs;
- box/dock logic;
- clearance gate logic;
- cuRobo world management;
- generic execution validation.

Target:

~~~text
ABDemo.next_goal()
→ SceneAwareMotionService.move(MotionRequest(...))
~~~

## 8. ART redesign

Add generic commands:

~~~text
scene status
scene scan
scene invalidate

motion status
motion plan right --target ...
motion preview
motion execute
motion stop
~~~

Keep convenient task/demo commands:

~~~text
demo ab run-next
demo ab loop
~~~

but they call the generic motion service.

After AMR navigation, ART should display:

~~~text
SCENE REQUIRED — next arm motion will scan automatically
~~~

## 9. Demo for corrected hierarchy

Use the current A/B endpoints only as convenient target poses.

### Demo D0 — clear

~~~text
arbitrary clear scene
→ fresh scan
→ generic SceneSnapshot
→ generic motion request
→ cuRobo
→ execute
~~~

### Demo D1 — arbitrary obstacle

USER ACTION:

~~~text
目的：
验证底层 scene-aware motion 对任意可见障碍自动避障。

你现在做：
在相机可见的 A/B 工作区随意放一个障碍物，不告诉软件坐标；左臂和底盘不动。

完成后回复：
“任意障碍场景已放置”

安全边界：
物体放稳，保持当前机器人状态。
~~~

Then:

- no manual obstacle coordinates;
- fresh scan;
- generic world reconstruction;
- same generic motion API;
- cuRobo avoidance;
- execute if hard-valid.

### Demo D2 — move obstacle

Move same object to another position; fresh scene/trajectory must change.

### Demo D3 — base move invalidation

Perform a small commissioned AMR move/return or use a safe station transition.

After base settles:

- previous scene must be invalid;
- first arm request must automatically scan;
- then generic plan/execute.

If an AMR move is not appropriate at the site, demonstrate lifecycle with a read-only/simulated base-pose revision test first and leave physical D3 for later.

## 10. Minimal UI backend + prototype

Do not build a polished UI before backend parity.

After generic backend passes D0/D1, implement the minimal UI described in:

~~~text
docs/work_orders/2026-09-23_P4_SCENE_AWARE_WEBUI.md
~~~

The UI must visualize the same LocalScene and MotionService state, not a separate demo pipeline.

## 11. Acceptance

Report:

~~~text
LOCAL_SCENE_SERVICE_READY = YES/NO
BASE_MOVE_INVALIDATES_SCENE = YES/NO
AUTO_SCAN_BEFORE_ARM_MOTION = YES/NO
GENERIC_SCENE_AWARE_MOTION_READY = YES/NO
GENERIC_CONSTRAINT_INTERFACE_READY = YES/NO
PLANNER_CLEARANCE_POLICY_IN_CUROBO = YES/NO
HARD_VALIDATOR_NO_DEMO_MARGIN = YES/NO
START_NEAR_OBSTACLE_ESCAPE_READY = YES/NO
AB_DEMO_MIGRATED_TO_GENERIC_MOTION = YES/NO
ARBITRARY_OBSTACLE_DEMO_EXECUTED = YES/NO
MOVED_OBSTACLE_REPLAN_EXECUTED = YES/NO
MINIMAL_SCENE_UI_READY = YES/NO
~~~

Also report scan/scene/plan/execute latency and exact Git commit.

## 12. Push policy

Make small local commits.

Do not force-push.
Do not include coworker AMR dirty changes.

After tests + D0/D1 pass, normal fast-forward push is allowed if remote HEAD is unchanged; otherwise use relay/replay.

Leave .32 and GitHub aligned.
