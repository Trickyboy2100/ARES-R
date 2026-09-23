# ARES-R Scene-Aware Motion Control Stack

Date: 2026-09-23

## 0. Why this redesign exists

The current A/B demo proved that fresh Pixel Pro pointclouds can change cuRobo trajectories. However, the current implementation still treats that capability as an A/B-demo pipeline and places a second task-specific clearance decision after cuRobo.

That layering is wrong for the long-term system.

cuRobo should be the canonical collision-aware arm planner for a fresh local scene. Independent validation remains valuable, but its role is to catch stale bindings, model/implementation disagreement, actual penetration, controller/dynamics violations, and other hard execution faults. It should not routinely reject an otherwise valid cuRobo trajectory solely because a demo-specific preferred clearance was not achieved.

The target architecture is:

~~~text
higher-level task / skill / LLM
        ↓ goal + semantic constraints only
Scene-Aware Motion Service
        ↓
fresh local SceneSnapshot when required
        ↓
cuRobo collision-aware planning
        ↓
hard execution validation / SafetyKernel
        ↓
JAKA ServoJ / controller protections
~~~

Obstacle avoidance is therefore a CONTROL-LAYER capability, not an A/B-demo skill.

## 1. Control hierarchy

### L0 — Hardware/controller protection

Owns controller estop, controller collision/limit/fault state, servo deadline/watchdog, native tracking abort, and power/enable state.

No software layer may bypass these.

### L1 — Robot state and frames

Owns BODY frame, AMR/base pose revision, dual-arm joints, tool/gripper revision, attachments and calibration revision.

Every scene and trajectory binds to these revisions.

### L2 — Local Scene Service

Owns the robot's current local geometric understanding.

Inputs:

- Pixel Pro pointcloud;
- commissioned CAMERA→BODY;
- current robot geometry/state.

Pipeline:

~~~text
fresh capture
→ CAMERA→BODY
→ ROI / downsample
→ robot-owned self-filter
→ residual cleanup
→ generic support/structure/protrusion/unknown decomposition
→ collision primitives
→ immutable SceneSnapshot
~~~

No object recognition is required for collision avoidance.

The Scene Service publishes scene_epoch, base_pose_revision, pointcloud_sha, scene_digest, obstacle_world, freshness and timings.

### L2.1 — Scene lifecycle authority

Scene invalidation is event driven.

Mandatory invalidation events:

- AMR/base movement begins;
- AMR/base pose revision changes;
- camera calibration changes;
- robot collision/tool revision changes;
- explicit operator scene invalidation;
- perception failure.

After a base move finishes:

~~~text
BASE_SETTLED
→ SCENE_REQUIRED
~~~

The first arm-motion request must call ensure_scene_fresh() before planning.

Task code does not manually decide whether pointcloud avoidance is enabled.

### L3 — Scene-Aware Motion Service

This is the only normal task-level entry point for free-space arm movement.

Canonical API concept:

~~~text
MotionRequest(
    arm,
    goal,
    constraints,
    speed_profile,
    scene_policy=AUTO_FRESH
)

plan_motion(request)
execute_plan(plan_handle)
move(request)
~~~

Responsibilities:

1. ensure a valid local SceneSnapshot;
2. bind current robot/tool/base state;
3. update persistent cuRobo world;
4. apply task constraints;
5. plan one collision-aware trajectory;
6. return trajectory + provenance + planner clearance;
7. bind exact trajectory to execution lease.

Every pick/place/inspection/task planner should call this service rather than calling JAKA free-space motion directly.

### L3.1 — Planning constraints interface

Constraints are generic planner inputs, not A/B hard-coded behavior.

Initial constraints:

- target TCP pose;
- fixed/free orientation;
- LEVEL_YAW_FREE (TCP level, yaw about BODY +Z planner-free);
- LEVEL_YAW_TARGET (TCP level, final yaw supplied);
- keep-out region;
- central BODY exclusion;
- speed profile;
- active arm;
- attached-object geometry;
- optional approach/contact mode.

Future task code may compose constraints without rewriting cuRobo integration.

### L3.2 — Clearance semantics

Separate three concepts.

1. HARD_COLLISION_VALIDITY
   - no penetration according to the bound collision model;
   - no stale scene/tool/robot state;
   - controller and central hard constraints satisfied.

2. PLANNER_CLEARANCE_POLICY
   - desired stand-off/inflation/collision activation used INSIDE cuRobo;
   - versioned per motion profile;
   - planner should search for a more comfortable route when possible.

3. EXECUTION_MONITOR
   - independently verifies collision/model binding and hard validity;
   - does not impose an unrelated demo-only preferred clearance after planning.

A preferred 30 mm margin is not a universal low-level law.

Important near-start case:

If an obstacle is already close to the current robot pose, the start state may have less than the preferred planner stand-off. The system must not reject every escape trajectory merely because t=0 cannot satisfy the preferred margin.

The planner/executor should distinguish:

~~~text
start state collision-free but close
→ allow a planned escape path that does not penetrate and increases/separates clearance

start state penetrating / invalid / stale
→ reject
~~~

Exact hard-floor and escape-policy parameters must be versioned and commissioned; do not hide them as demo literals.

### L4 — Execution Authority / SafetyKernel

Owns hard authorization only:

- exact live-start match;
- SceneSnapshot binding/freshness;
- base stationary;
- inactive arm state known;
- tool/attachment revision;
- full-path collision validity;
- central exclusion;
- dynamics;
- native sender limits;
- controller state;
- execution lease/trajectory hash.

SafetyKernel must not become a second trajectory optimizer.

### L5 — Skills

Examples: move_to_pregrasp, move_to_place, inspect_pose, move_named_pose, A/B demo.

A skill specifies goals and constraints.

It does NOT construct obstacle AABBs, know box/dock IDs for avoidance, call self-filter, call cuRobo internals directly, or bypass Scene-Aware Motion Service.

### L6 — Task planning / LLM

Owns task sequencing and semantic decisions only.

Examples:

~~~text
navigate to station
scan/detect target
pick object
navigate to destination
place object
~~~

After navigation, local scene invalidation/scan happens automatically below this layer.

## 2. Base-motion integration

The intended mobile-manipulation lifecycle is:

~~~text
Task asks AMR to navigate
→ base starts moving
→ Local Scene becomes INVALID immediately
→ arm free-space execution blocked

AMR reports settled
→ base pose revision increments
→ Local Scene state = SCENE_REQUIRED

Task asks arm to move
→ Scene-Aware Motion Service sees SCENE_REQUIRED
→ automatic fresh Pixel Pro scan
→ build SceneSnapshot
→ cuRobo plan
→ execute
~~~

If the task performs multiple arm motions without base/environment change, the same environment epoch may be reused only while the freshness policy allows it. Any explicit rescan creates a new epoch.

## 3. Generic arbitrary-scene behavior

Runtime obstacle avoidance must not depend on object class, object ID, current box, dock ID, fixed obstacle coordinate, fixed primitive ID, or historical SceneSnapshot.

The scene is simply observed occupied geometry.

A target may be task-specific; the collision world is not.

## 3.1 Target independence

The collision world and the target are independent inputs.

The long-term service must accept arbitrary runtime reachable BODY targets. A/B coordinates are not part of the Scene Service and are not required by the Motion Service.

The live start is the actual current robot state. A runtime target P or Q may come from UI, perception, a Skill, a Scheme or a Task.

The next default free-space orientation contract is LEVEL_YAW_FREE:

- TCP/gripper remains level relative to the BODY horizontal plane;
- roll/pitch level condition remains constrained along the trajectory;
- yaw about BODY +Z may change during cuRobo planning;
- an upper layer may instead request LEVEL_YAW_TARGET.

## 4. Revised A/B demo role

A/B is now only a test client of the generic motion service.

Demo:

~~~text
operator changes visible obstacles arbitrarily
→ fresh scan
→ generic collision world
→ MotionRequest(goal=A or B, orientation=BODY_FORWARD_HORIZONTAL)
→ cuRobo
→ execute
~~~

If there is no valid route, fail closed.

No A/B-only obstacle planner should exist.

## 5. UI architecture

The UI must expose the same backend contracts as ART. It must not control hardware directly.

### Main 3D viewport

Always show in BODY frame:

- live/current pointcloud;
- reconstructed collision primitives;
- robot + both arms/tools;
- current target;
- planned trajectory;
- current limiting collision object/clearance;
- camera frustum;
- optional raw/self-filter overlays.

### Global state ribbon

~~~text
BASE: MOVING / SETTLED
SCENE: INVALID / REQUIRED / SCANNING / READY / STALE
PLANNER: IDLE / PLANNING / READY / FAILED
EXECUTION: IDLE / ARMED / EXECUTING / STOPPED / FAULT
~~~

Also show base_pose_revision, scene_epoch, SceneSnapshot ID, pointcloud age and scan/scene/plan timings.

### Motion panel

Inputs:

~~~text
arm
goal pose / named target
orientation constraint
speed profile
scene policy: AUTO_FRESH / FORCE_RESCAN / REUSE_IF_VALID
~~~

Buttons:

~~~text
Scan
Plan
Preview
Execute
Stop
~~~

Normal mode must not expose manual obstacle boxes.

### Constraints panel

Generic planner constraints:

- BODY_FORWARD_HORIZONTAL;
- CURRENT_ORIENTATION;
- explicit RPY/quaternion;
- keep-out volumes;
- contact/approach mode;
- attached object;
- speed profile.

### Task panel

Runs skills/tasks.

Task UI never contains low-level obstacle handling.

### ART panel

Embedded ART command input/history/event stream, using the same backend dispatcher.

No browser shell and no direct browser JAKA/AMR API.

## 6. Backend service contracts for UI and ART

Target backend methods:

~~~text
scene.status()
scene.scan(force=False)
scene.invalidate(reason)
scene.ensure_fresh(reason)

motion.plan(request)
motion.preview(plan_id)
motion.execute(plan_id)
motion.stop()
motion.status()

nav.move(...)
nav.status(...)

task.run(...)
~~~

ART and WebUI call the exact same services.

## 7. Immediate implementation priority

Do not spend the next phase validating more random box placements through the old A/B-specific gate.

Implement the layer correction first:

~~~text
Scene lifecycle authority
→ generic Scene-Aware Motion Service
→ planner clearance policy inside cuRobo
→ hard-only independent execution validation
→ base-motion automatic scene invalidation
→ A/B demo migrated as a client
→ minimal scene-aware WebUI
~~~

Then use arbitrary scenes to demonstrate the corrected architecture.
