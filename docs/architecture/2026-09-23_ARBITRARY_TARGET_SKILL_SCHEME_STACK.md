# ARES-R Arbitrary-Target Scene-Aware Motion and Skill/Scheme Stack

Date: 2026-09-23

## 0. Clarification after P3.6 D1

P3.6 D1 proved that the ENVIRONMENT path is already fresh-scene-driven:

~~~text
fresh Pixel Pro scan
→ generic BODY scene reconstruction
→ new SceneSnapshot
→ generic SceneAwareMotionService
→ cuRobo
→ hard-only execution validation
→ real execution
~~~

The obstacle geometry came from the new pointcloud and no manual obstacle coordinate was supplied.

What is still temporary is the TARGET source: D1 used the fixed A/B endpoints as a regression client.

Therefore the next architectural step is target generalization:

~~~text
arbitrary visible scene + arbitrary reachable target pose/point
→ same SceneAwareMotionService
→ cuRobo
→ execute
~~~

A/B remains only a regression fixture.

## 1. Generic motion target contract

Free-space arm motion must not depend on A/B constants.

Canonical concept:

~~~text
MotionGoal:
  frame = BODY
  position_m = [x, y, z]

  orientation_constraint:
    mode = LEVEL_YAW_FREE | LEVEL_YAW_TARGET | CURRENT | EXPLICIT

    # LEVEL_YAW_FREE:
    # TCP remains level with the ground throughout the path.
    # Roll/pitch relative to the BODY horizontal plane are constrained.
    # Yaw about BODY +Z may vary as cuRobo optimizes the route.

    # LEVEL_YAW_TARGET:
    # same level constraint, but final yaw may be requested by an upper layer.

  tolerance
  metadata/source
~~~

The core planner should use rotation matrices/quaternions rather than Euler arithmetic internally.

## 2. Arbitrary two-point semantics

The low-level service plans from the actual live robot state to an arbitrary goal.

“Arbitrary two points” is therefore implemented as:

~~~text
current state → arbitrary target P
then
current state at P → arbitrary target Q
~~~

P/Q are runtime inputs, not config constants.

A task/UI may supply any reachable P/Q pair in the observed workspace.

The service must reject unreachable or collision-invalid targets without falling back to fixed A/B.

## 3. Scene lifecycle remains independent of target choice

Changing the goal does NOT define the scene.

Scene inputs remain only:

- fresh camera observation;
- robot/base/tool state;
- commissioned transforms;
- generic scene parameters.

Goal inputs remain only:

- target position/pose;
- generic planner constraints;
- speed/motion profile.

This separation is mandatory.

## 4. Mobile-manipulation lifecycle

After any AMR movement:

~~~text
BASE_MOVING
→ scene INVALID

BASE_SETTLED
→ scene REQUIRED

next free-space arm motion
→ automatic fresh scan
→ new SceneSnapshot
→ plan to arbitrary runtime goal
~~~

This behavior applies to all skills/tasks.

## 5. Skill layer

The SceneAwareMotionService is below Skills.

A Skill is a reusable manipulation primitive with explicit inputs/outputs, not a one-off task script.

Initial Skill candidates for the tray→groove workflow:

~~~text
skill.move_free
    input: target pose/position + constraints
    implementation: SceneAwareMotionService

skill.approach_linear
    input: target pose, approach axis, distance/tolerance
    semantics: constrained short contact-approach segment

skill.grasp
    input: gripper command/profile
    output: grasp verification

skill.lift_vertical
    input: distance or target height

skill.move_above_place
    input: place target + vertical clearance
    implementation: scene-aware free-space motion

skill.place_linear
    input: place target, vertical approach

skill.release
    input: gripper command/profile

skill.retreat
    input: retreat axis/distance
~~~

Not every primitive must become a Skill if it is purely an internal helper. A Skill should have stable semantics, reusable inputs and independent validation/logging.

## 6. Target/semantic interfaces for manipulation

The future pick/place task must not hard-code key coordinates.

External modules provide semantic target data through a versioned interface.

Conceptual object:

~~~text
ManipulationTargets:
  pick:
    grasp_pose
    pregrasp_pose optional
    approach_axis
    approach_distance

  place:
    place_pose
    preplace_pose optional
    approach_axis
    approach_distance

  lift:
    distance / target_z

  retreat:
    axis
    distance

  source:
    perception / manual / task planner / learned policy
~~~

The execution scheme consumes these values.

Perception owns target estimation.
Motion owns collision-aware movement.
Skills own manipulation semantics.
Task/Scheme owns ordering.

## 7. Scheme layer

A Scheme is a declarative composition of Skills.

The intended first tray→groove Scheme is:

~~~text
ensure local scene
→ move_free(pregrasp)
→ approach_linear(grasp_pose)
→ grasp
→ lift_vertical
→ move_free(preplace / above-target)
→ place_linear(place_pose)
→ release
→ retreat
~~~

Free-space moves use SceneAwareMotionService.

Contact/approach moves use explicit manipulation/contact semantics rather than pretending the target object is an ordinary obstacle all the way to contact.

## 8. Task layer

A Task selects a Scheme and supplies semantic targets/context.

Example:

~~~text
Task: tray_to_groove

inputs:
  pick target from perception
  place target from perception / layout module
  active arm
  object metadata

scheme:
  RIGHT_ARM_TRAY_TO_GROOVE_V1
~~~

The Task does not implement FK, pointcloud filtering, collision world construction or ServoJ.

## 9. UI implications

The normal Motion UI must support arbitrary runtime targets:

~~~text
BODY X
BODY Y
BODY Z

Orientation:
  LEVEL_YAW_FREE
  LEVEL_YAW_TARGET
  CURRENT
  EXPLICIT
~~~

A/B appears only under a demo/regression panel.

The 3D viewport should support selecting/previewing a target point without creating obstacle geometry.

Future manipulation UI may show externally supplied pick/place target markers and Scheme execution state.

## 10. Immediate order

~~~text
P3.7:
arbitrary runtime target + LEVEL_YAW_FREE scene-aware motion

then

P3.8:
tray→groove manipulation Skills + Scheme interfaces and planning-only sequence
~~~

Do not start P3.8 physical grasp/place execution before P3.7 arbitrary-target motion is demonstrated.
