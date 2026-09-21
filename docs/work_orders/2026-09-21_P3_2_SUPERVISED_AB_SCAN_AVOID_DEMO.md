# P3.2 — Supervised right-arm A↔B scan-before-each-leg avoidance demo

Date: 2026-09-21

## 0. Goal

Build the first physical demo exactly around this behavior:

~~~text
RIGHT ARM TCP at A or B
→ before every leg, fresh Pixel Pro scan + fresh dual-arm/tool state
→ rebuild BODY scene

if the straight A↔B TCP corridor is clear:
    execute a validated Cartesian straight-line TCP path

if the straight corridor is blocked by a real obstacle:
    run cuRobo and generate an ABOVE-obstacle bypass path
    then execute that planned path

arrive at the other endpoint
→ stop
→ next leg repeats the entire scan / classify / plan process
~~~

No stale scene/trajectory reuse between legs.

The intended visual demo is:

~~~text
A → B : no box    → straight line
B → A : box added → upward arc
A → B : box still present → upward arc
B → A : box removed → straight line
~~~

Each physical leg requires a separate operator confirmation until the demo is commissioned.

## 1. Entry gate

P3.1 must be pushed first.

Known P3.1 planning-only result:

- current same-A/B CLEAR succeeds;
- observed-box AVOID succeeds;
- path deviation vs CLEAR peaks around 46.6 mm;
- BLOCK fails with no fallback;
- active right controller TCP is about 35 mm beyond the pinned gripper collision envelope;
- observed-box AVOID modeled clearance is only about 9.63 mm.

Therefore physical execution is still blocked until tool/gripper collision extent is reconciled.

## 2. P3.2-A — right tool/TCP collision commissioning

First resolve the only physical-model blocker.

Current right controller TCP:

~~~text
approximately [-3.0, -4.8, +184.4] mm in link6/flange frame
~~~

Pinned ARES gripper collision envelope reaches only about:

~~~text
z ≈ +149.0 mm
~~~

Do not execute with the old envelope.

### Preferred user measurement

Ask exactly one physical action:

~~~text
USER ACTION 1
目的：确认右臂实际夹爪碰撞长度/TCP。
你现在做：用尺子测量“右臂 link6/法兰安装平面”到“两指实际夹持中心/指尖最前端”的轴向距离，单位 mm；若夹持中心和最前端不同，请给两个数。
完成后回复：夹持中心 xx mm，最前端 yy mm。
安全边界：机器人保持不动，不需要拆夹爪。
~~~

Also record approximate maximum lateral width of the fingers/body if easily available, but do not require a second user action unless necessary.

### Collision model update

Use pinned ARES gripper mesh/mount as the base model.

If the physical distal extent exceeds the mesh:

- extend the gripper collision model with a conservative distal box/capsule from the mesh tip to at least the measured finger-tip extent;
- bind it to the current right tool/TCP revision;
- keep provenance;
- render the new model against the physical geometry/TCP audit.

Require:

~~~text
RIGHT_TOOL_COLLISION_MODEL_COMMISSIONED = YES
~~~

before any physical motion.

## 3. P3.2-B — redesign A/B for a stronger visual demo

The user wants:

- larger BODY-left/right span;
- both endpoints lower;
- clear path visually close to a horizontal straight line;
- obstacle-present path visibly arcs upward.

Do NOT hard-code one arbitrary pair.

Search offline for a safe A/B contract subject to:

~~~text
right arm only
same/similar BODY X
same/similar BODY Z
larger |ΔY| than the current pair where feasible
both endpoints remain safely on the right-arm side of the central exclusion
target Z lower than current A/B
current→A reposition feasible
A→B and B→A straight Cartesian paths feasible in box-free scene
whole-arm / gripper / inactive-left-arm collision-free
~~~

Suggested search targets, not hard requirements:

~~~text
lateral span target: roughly 0.45–0.55 m if feasible
endpoint Z target: roughly 0.98–1.03 m
BODY X: roughly 0.68–0.74 m
~~~

The search must respect actual reach, central exclusion and table/dock geometry.

Output a versioned A/B contract with BODY TCP pose and right-arm joint solution for each endpoint.

## 4. P3.2-C — explicit straight-line CLEAR planner

The no-obstacle behavior must be geometrically straight in TCP space.

Do not use unconstrained cuRobo plan_cspace and merely call it "straight".

Implement a Cartesian straight-line path:

~~~text
TCP pose(s) = interpolate position from A to B
orientation = fixed demo orientation profile
→ solve continuous IK along samples
→ choose continuous joint branch
→ dense whole-robot collision validation
→ velocity/acceleration/time parameterization
→ ServoJ-ready joint trajectory
~~~

If the straight Cartesian path is infeasible, fail closed. Do not silently substitute a curved route when the scene is classified CLEAR.

The same applies to B→A.

## 5. P3.2-D — scan and straight-corridor classification

Before every leg:

~~~text
fresh camera capture
→ CAMERA→BODY
→ whole-robot self-filter
→ residual cleanup
→ support/object decomposition
→ multi-primitive obstacle world
→ fresh inactive-arm geometry
→ fresh SceneSnapshot
~~~

Construct a swept straight-corridor query around the intended TCP/tool trajectory.

The corridor must account for:

- TCP path;
- commissioned right gripper/tool envelope;
- safety inflation;
- whole active-arm path validation.

Decision:

~~~text
STRAIGHT_CLEAR
STRAIGHT_BLOCKED
SCENE_INVALID
~~~

Do not decide only from TCP centerline intersection.

## 6. P3.2-E — obstacle-present ABOVE bypass planner

If the fresh straight corridor is blocked:

1. identify obstacle primitives intersecting the straight corridor;
2. compute the highest observed/represented obstacle top relevant to the corridor;
3. generate one or more OVERHEAD waypoint candidates above that top:

~~~text
z_waypoint = obstacle_top
           + tool/gripper extent allowance
           + configured vertical safety clearance
~~~

4. keep the waypoint horizontally near the A/B corridor midpoint unless whole-arm geometry requires another safe location;
5. use cuRobo to plan:

~~~text
A → overhead waypoint → B
~~~

or the reverse;

6. validate the complete concatenated trajectory continuously against:
   - real multi-primitive obstacles;
   - table/dock/support;
   - inactive left arm/gripper;
   - chassis/body;
   - central exclusion.

Try a small bounded set of increasing overhead heights if needed.

No unconstrained side-bypass should be accepted for this demo unless explicitly labelled as a different mode. The desired demo mode is:

~~~text
BYPASS_POLICY = OVERHEAD
~~~

## 7. P3.2-F — stronger planning-only proof before execution

Using the new A/B and corrected tool model, regenerate fresh:

### CLEAR
- straight Cartesian A→B;
- straight Cartesian B→A;
- both succeed;
- TCP straightness error reported.

### AVOID
- observed physical box blocks straight corridor;
- overhead cuRobo A→B succeeds;
- overhead cuRobo B→A succeeds;
- path arc is visibly stronger than the current 46.6 mm comparison;
- positive modeled clearance with the corrected tool model.

### BLOCK
- expected fail, no fallback.

Required visualization:

- TOP / REAR / RIGHT;
- CLEAR straight line vs AVOID overhead arc;
- obstacle top and overhead waypoint;
- whole dual-arm robot;
- inactive arm;
- A/B;
- minimum clearance.

Do not proceed to motion unless these are accepted.

## 8. P3.2-G — supervised physical execution state machine

Implement backend/Terminal state machine:

~~~text
AB_DEMO_IDLE
AB_AT_A
AB_AT_B
SCANNING
SCENE_READY
STRAIGHT_CLEAR
BYPASS_REQUIRED
PLANNED
AWAITING_CONFIRMATION
EXECUTING
ARRIVED
STOPPED
FAULT
~~~

Commands may follow ART grammar, but should converge on something like:

~~~text
demo ab status
demo ab configure right <profile>
demo ab scan
demo ab plan-next
demo ab preview
demo ab execute-next
demo ab stop
~~~

Later one convenience command may chain scan+plan, but execution still requires confirmation until commissioned.

## 9. P3.2-H — execution semantics

Every physical leg:

~~~text
robot stationary at endpoint
→ fresh scan
→ fresh dual-arm/tool state
→ classify straight corridor
→ generate NEW trajectory
→ preview / summary
→ explicit one-time confirmation
→ execute at commissioned low speed
→ monitor actual joints / collision / stop conditions
→ verify arrival
→ invalidate old SceneSnapshot and trajectory
~~~

If obstacle is removed before the next leg, the next fresh scan must restore straight-line mode automatically.

No automatic retry.
No stale-plan execution.
No base motion during the demo.

## 10. Speed / initial execution

For the first physical CLEAR leg use a commissioned conservative speed profile.

Do not start with the final presentation speed.

After one CLEAR round-trip is validated, increase within the already defined site ceiling and revalidate before recording the final demo.

## 11. Exit gates

Planning/commissioning stage:

~~~text
RIGHT_TOOL_COLLISION_MODEL_COMMISSIONED = YES/NO
AB_TARGETS_COMMISSIONED = YES/NO
STRAIGHT_CARTESIAN_PLANNER_READY = YES/NO
STRAIGHT_CORRIDOR_CLASSIFIER_READY = YES/NO
OVERHEAD_BYPASS_PLANNER_READY = YES/NO
NEW_CLEAR_PLAN_READY = YES/NO
NEW_AVOID_PLAN_READY = YES/NO
NEW_BLOCK_PLAN_READY = YES/NO
READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION = YES/NO
~~~

After physical execution:

~~~text
CLEAR_ROUNDTRIP_EXECUTED = YES/NO
AVOID_ROUNDTRIP_EXECUTED = YES/NO
SCAN_BEFORE_EACH_LEG_VERIFIED = YES/NO
OBSTACLE_ADD_REMOVE_MODE_SWITCH_VERIFIED = YES/NO
~~~

## 12. Evidence

Record per leg:

- camera frame / pointcloud SHA;
- calibration revision;
- robot geometry revision;
- right tool/TCP revision;
- inactive-left-arm revision;
- SceneSnapshot ID;
- classification result;
- planner mode STRAIGHT/BYPASS;
- overhead waypoint if used;
- trajectory hash;
- minimum clearance;
- execution feedback;
- arrival result;
- timing.

Generate a final demo comparison graphic and terminal log.

## 13. Push/execution policy

Phase 1: tool model + A/B redesign + planners + planning-only validation.

Commit locally and STOP. Do not push automatically.

Only after ChatGPT review:

- push the planning/commissioning code;
- request explicit user authorization for one supervised CLEAR movement.

Physical arm motion is never implied by this work order.
