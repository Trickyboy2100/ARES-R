# P3.2 — Right-arm scan-before-each-leg A↔B demo, planning/commissioning stage

Date: 2026-09-21

## 0. Goal

Build the first right-arm A↔B demo around this exact behavior:

~~~text
RIGHT ARM TCP at A or B
→ before every leg, fresh Pixel Pro scan + fresh dual-arm/tool state
→ rebuild BODY scene

if the straight A↔B corridor is clear:
    generate/validate a true Cartesian TCP straight-line path

if the straight corridor is blocked:
    run cuRobo with OVERHEAD bypass policy
    generate a visibly upward arc around the obstacle

arrive at the other endpoint
→ stop
→ invalidate old scene/trajectory
→ next leg rescans and decides again
~~~

Desired presentation:

~~~text
no obstacle    → straight line
obstacle added → upward arc
obstacle kept  → upward arc on reverse leg
obstacle removed → straight line again
~~~

P3.2 is split into planning/commissioning first, physical execution later.

## 1. Current prerequisite / Git state

GitHub integration HEAD currently contains the P3 checkpoint:

~~~text
eafae083cc03f61c6b7162ea90130ce798b8cac6
~~~

P3.1 local commit awaiting safe push:

~~~text
7ae26aacb86222263d76490e3ec9cc55e9867de6
~~~

Before P3.2 work starts, verify whether eafae083 is an ancestor of 7ae26aac.

- If yes: fast-forward push 7ae26aac.
- If not: do not force push; replay only the P3.1 patch on top of GitHub eafae083, test, then fast-forward push.

No unrelated AMR dirty changes may enter the push.

## 2. Tool/TCP note — deferred for this planning-only phase

New manual measurement:

~~~text
right flange mounting plane → approximate grasp center ≈ 145 mm
~~~

Existing evidence:

~~~text
pinned ARES gripper collision envelope distal extent ≈ 149 mm
controller active TCP Z ≈ 184 mm
~~~

This means the controller TCP semantic and physical grasp/contact point are still not fully reconciled.

For this P3.2 planning-only phase:

- DO NOT block A/B redesign and planner development on this issue;
- DO NOT rewrite the tool model from the 145 mm rough measurement alone;
- keep the current validated/pinned gripper geometry for planning comparison;
- carry an explicit TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED flag in reports/artifacts;
- physical execution remains blocked until this flag is resolved.

The 145 mm measurement is evidence, not yet a commissioned tool revision.

## 3. P3.2-A — redesign A/B for a stronger demo

User requirements:

- larger BODY-left/right span than current;
- both endpoints lower;
- X and Z approximately equal;
- motion mainly along BODY Y;
- CLEAR path should visually be a straight horizontal traverse;
- AVOID path should be a visibly higher arc.

Search offline for a safe A/B pair.

Suggested exploration region only, not a hard contract:

~~~text
BODY X roughly 0.66–0.75 m
BODY Z roughly 0.96–1.03 m
lateral |ΔY| target roughly 0.45–0.60 m if feasible
~~~

Constraints:

- both endpoints reachable;
- no central exclusion violation;
- no table/dock/inactive-left-arm collision;
- current→A reposition is feasible planning-only;
- enough vertical headroom exists for an overhead bypass;
- keep the pair away from singular/near-limit joint configurations;
- prefer a larger visual span even if exact max span is slightly below the suggested target.

Output a versioned A/B contract:

~~~text
A BODY TCP pose
B BODY TCP pose
A right-arm joints
B right-arm joints
span_m
height_m
orientation profile
clearance summary
~~~

## 4. P3.2-B — true Cartesian straight CLEAR planner

No-obstacle mode must be truly straight in TCP space.

Do not use free plan_cspace and call it straight.

Implement:

~~~text
A→B Cartesian position interpolation
+ fixed demo orientation
→ continuous IK at sampled waypoints
→ continuous joint-branch selection
→ dense whole-arm + tool collision validation
→ velocity/acceleration/time parameterization
→ ServoJ-ready trajectory
~~~

Likewise for B→A.

Report maximum TCP deviation from the A-B chord.

Target:

~~~text
CLEAR straightness error as close to zero as practical
~~~

If a true straight path is infeasible, fail closed and search a different A/B pair.

## 5. P3.2-C — scan-before-each-leg scene/classifier

Before every future leg:

~~~text
fresh camera capture
→ CAMERA→BODY
→ whole-robot self-filter
→ residual cleanup
→ support/object decomposition
→ multi-primitive obstacle scene
→ fresh inactive-left-arm geometry
→ fresh SceneSnapshot
~~~

Then classify the intended straight swept corridor:

~~~text
STRAIGHT_CLEAR
STRAIGHT_BLOCKED
SCENE_INVALID
~~~

The corridor check must include:

- TCP centerline;
- active gripper/tool collision geometry;
- active-arm swept geometry;
- safety inflation;
- inactive left arm;
- table/dock/support;
- chassis/central exclusion.

Do not classify only from the TCP line.

## 6. P3.2-D — OVERHEAD cuRobo bypass planner

If the straight corridor is blocked by a real observed obstacle:

1. identify the obstacle primitives intersecting the straight swept corridor;
2. estimate the relevant obstacle top Z from observed/represented geometry;
3. generate a small bounded set of overhead waypoint candidates:

~~~text
z_waypoint = obstacle_top + vertical_clearance_candidate
~~~

4. keep XY near the A/B corridor midpoint when safe;
5. plan with cuRobo through the overhead waypoint;
6. dense-validate the whole resulting trajectory against:
   - observed multi-primitive obstacles;
   - table/dock/support;
   - inactive left arm/gripper;
   - chassis/body;
   - central exclusion.

The demo policy is explicitly:

~~~text
BYPASS_POLICY = OVERHEAD
~~~

Do not silently accept a side-bypass and present it as the requested demo.

Try a small ordered set of increasing overhead heights if needed.

## 7. P3.2-E — make the arc visually stronger

The current planning-only AVOID/CLEAR path separation peaks at about 46.6 mm.

For the new demo:

- lower A/B;
- enlarge lateral span;
- choose overhead waypoint height so the AVOID arc is visibly distinct;
- still maintain conservative whole-arm clearance.

Do not optimize only for aesthetics. Planning validity comes first.

Prefer a modeled obstacle clearance materially larger than the current ~9.63 mm planning-only result. If feasible, aim for roughly 40–60+ mm modeled clearance, but do not treat this as a physical execution certificate while the tool/TCP semantics remain unresolved.

## 8. P3.2-F — planning-only proof

Using the new A/B:

### CLEAR
- A→B straight Cartesian succeeds;
- B→A straight Cartesian succeeds;
- report straightness error;
- report minimum modeled clearance.

### AVOID
- real observed box blocks the straight corridor;
- A→B overhead cuRobo succeeds;
- B→A overhead cuRobo succeeds;
- path arc is visibly stronger than current result;
- report obstacle top, overhead waypoint and min clearance.

### BLOCK
- expected safe failure;
- no fallback.

Required visualization:

- TOP / REAR / RIGHT;
- CLEAR straight vs AVOID overhead arc;
- same A/B;
- obstacle;
- overhead waypoint;
- whole dual-arm model;
- minimum clearance;
- scene/calibration/geometry revisions.

## 9. P3.2-G — backend state machine, no motion yet

Implement the future demo state machine now:

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

Terminal/backend commands may converge on:

~~~text
demo ab status
demo ab configure right <profile>
demo ab scan
demo ab plan-next
demo ab preview
demo ab execute-next
demo ab stop
~~~

During this planning-only phase, execute-next must remain blocked.

## 10. Future physical execution semantics

Once tool/TCP physical semantics are later reconciled and ChatGPT/user explicitly authorize execution, every leg must be:

~~~text
stationary at endpoint
→ fresh scan
→ fresh robot/tool state
→ fresh SceneSnapshot
→ classify
→ generate NEW straight or overhead trajectory
→ preview
→ explicit one-time confirmation
→ execute low-speed
→ verify arrival
→ invalidate old scene/trajectory
~~~

No stale plan reuse.
No auto retry.
No base motion.

## 11. Exit gates for this planning-only phase

Report:

~~~text
P31_PUSHED_AND_ALIGNED = YES/NO
TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED = YES
AB_TARGETS_READY = YES/NO
STRAIGHT_CARTESIAN_PLANNER_READY = YES/NO
STRAIGHT_CORRIDOR_CLASSIFIER_READY = YES/NO
OVERHEAD_BYPASS_PLANNER_READY = YES/NO
NEW_CLEAR_PLAN_READY = YES/NO
NEW_AVOID_PLAN_READY = YES/NO
NEW_BLOCK_PLAN_READY = YES/NO
AB_DEMO_STATE_MACHINE_READY = YES/NO
READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION = NO
~~~

The last value must remain NO in this phase because the user explicitly deferred the tool/TCP physical-length issue.

Include:

- new A/B BODY coordinates;
- lateral span and height;
- CLEAR straightness error;
- AVOID maximum Z / arc height;
- CLEAR-vs-AVOID path separation;
- minimum modeled clearances;
- timing;
- screenshots;
- tests;
- local commit SHA.

## 12. Push policy

After finishing this planning-only phase:

- local commit;
- STOP;
- do not push automatically;
- return to ChatGPT for review.

No physical arm motion.
