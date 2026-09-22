# P3.3 — Execution hardening for the approved cuRobo-only A/B demo

Date: 2026-09-22

## 0. Canonical operator overrides

The following two operator overrides are FINAL for this demo and supersede older straight-line / explicit-waypoint requirements:

~~~text
1. Every point-to-point leg uses cuRobo:
   CURRENT→A, A→B, B→A all use cuRobo planning.

2. No explicit waypoint:
   cuRobo receives start + goal + fresh collision world and chooses its own smooth route.
~~~

The operator has visually approved the current P3.2 CLEAR/AVOID trajectory style.

P3.3 must NOT redesign the A/B pair or try to make the arc prettier unless a safety/feasibility issue forces a change.

Current A/B planning contract:

~~~text
A BODY TCP = [0.710, -0.600, 1.000] m
B BODY TCP = [0.710, -0.130, 1.000] m
lateral span = 0.470 m
~~~

## 0.1 Documentation consistency fix

The P3.2 report header still says "LOCAL COMMIT ONLY; NO PUSH" even though the integration branch is now pushed to d258c30476868b2789c1cd61ac5c402a93b5ebf6.

At the beginning of P3.3, correct only this stale status metadata and record the pushed commit. Do not alter the accepted P3.2 numeric results or override text.

## 1. Goal

Convert the approved planning-only P3.2 result into an execution-ready package without moving hardware yet.

P3.3 focuses on:

~~~text
tool/collision conservative execution envelope
→ repeatable clearance gate
→ deterministic/accepted cuRobo trajectory selection
→ ServoJ/native timing conversion
→ fresh-scene / fresh-start execution lease
→ dry-run SafetyKernel authorization report
→ one-time execution request readiness
~~~

No AMR, arm or gripper motion in P3.3.

## 2. Tool/TCP execution-envelope reconciliation

Known evidence:

~~~text
manual flange→grasp-center ≈ 145 mm
pinned ARES gripper distal extent ≈ 149 mm
controller active TCP Z ≈ 184 mm
~~~

Do NOT change the controller TCP and do NOT claim the 145 mm rough measurement commissions the TCP semantic.

For the A/B demo, build an EXECUTION_COLLISION_ENVELOPE that conservatively covers:

- the pinned ARES gripper body/fingers;
- the full current controller TCP ray/offset;
- a small explicit sensor/model safety inflation.

The envelope may extend beyond the physical gripper; over-conservatism is acceptable for this demo.

Record:

~~~text
TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED = YES
EXECUTION_TOOL_ENVELOPE_CONSERVATIVE = YES
~~~

The demo is movement-only, not a grasp/contact validation.

## 3. Planner clearance reproducibility

P3.2 observed the same frozen AVOID scene produce modeled minimum gap around:

~~~text
35.4 mm on one accepted run
9.3 mm on another repeat
~~~

This variability must be resolved before execution.

### 3.1 Parameter/repeat sweep

Using frozen P3.2 CLEAR and AVOID scenes, run repeated planning-only trials with a small sweep of relevant cuRobo settings, especially optimizer collision activation distance.

Suggested candidates, bounded by current code validation:

~~~text
10 mm
20 mm
30 mm
40 mm
~~~

For each candidate:

- fixed source/goal;
- same frozen SceneSnapshot;
- same collision geometry revision;
- >=3 repeated plans per direction;
- dense independent post-validation of every resulting trajectory.

Record per trial:

- success/failure;
- trajectory hash;
- minimum path clearance;
- limiting object;
- path length;
- max TCP Z;
- max joint step;
- smoothness metrics;
- planning time.

### 3.2 Acceptance rule

Do not accept one lucky safe-looking trajectory.

Choose one versioned planner profile only if repeated trajectories meet a conservative execution gate.

Initial engineering gate for the FIRST supervised demo:

~~~text
dense modeled clearance >= 30 mm
for every accepted repeat
~~~

If the conservative execution tool envelope makes 30 mm infeasible, STOP and report rather than lowering the gate silently.

The 30 mm value is a first-demo engineering margin, not a claim of functional-safety certification.

## 4. Deterministic execution-candidate selection

Create one deterministic selection policy for each leg:

~~~text
valid collision-free candidates
→ reject below clearance gate
→ reject dynamics/smoothness violations
→ rank by:
   1. higher minimum clearance
   2. lower path length / excessive detour
   3. smoother joint trajectory
→ freeze exact selected trajectory hash
~~~

Execution must use the exact trajectory that was previewed and selected.

Replanning produces a NEW trajectory/lease; it may not silently replace an already confirmed trajectory.

## 5. Fresh-scene semantics before every leg

Preserve the approved demo behavior:

~~~text
at endpoint
→ fresh Pixel Pro capture
→ fresh CAMERA→BODY
→ fresh dual-arm/tool state
→ fresh self-filter/decomposition
→ fresh SceneSnapshot
→ one cuRobo direct start→goal request
→ validate
→ preview
→ later confirmation/execute
~~~

No explicit waypoint and no stale scene reuse.

The straight corridor classifier remains diagnostic/reference-only. It does NOT select a different planner.

## 6. Native/ServoJ execution packaging

Convert the selected cuRobo joint path to the existing right-arm native ServoJ format.

Important site limits:

~~~text
site ceiling:
  joint velocity <= 0.10 rad/s
  joint acceleration <= 0.20 rad/s²

first supervised profile target:
  slow <= 0.03 rad/s
  accel <= 0.06 rad/s²
~~~

Use existing native sender constraints as additional hard caps.

The current native sender/feedback audit also implies a conservative tracking-derived speed cap of about 1.25 deg/s ≈ 0.0218 rad/s (0.15 deg tracking budget / 0.12 s lag model), which is stricter than the nominal 0.03 rad/s slow profile. The first execution package must honor the strictest active cap unless new real tracking evidence commissions a higher value.

Do NOT reuse the P3.2 preview scaling target of 0.35 rad/s; that exceeds the site ceiling.

Implement/reuse time dilation/resampling so the exact geometric path is preserved while timing is slowed.

Verify offline:

- sample period expected by native sender;
- velocity;
- acceleration;
- predicted tracking gate;
- start/end exact preservation;
- max duration;
- no geometry change after time scaling.

Output a ServoJ-ready file for:

~~~text
CURRENT→A
A→B
B→A
~~~

but do not execute.

## 7. Scene/start/tool lease binding

Create an execution-candidate manifest binding:

- current actual start joints;
- SceneSnapshot ID/digest;
- camera/pointcloud SHA;
- T_body_camera revision;
- whole-robot geometry revision;
- inactive-left-arm revision;
- tool ID / TCP revision;
- execution-tool-envelope revision;
- planner profile revision;
- trajectory hash;
- speed/timing profile;
- creation timestamp / expiry;
- expected destination A or B.

Any change invalidates the candidate.

## 8. SafetyKernel dry-run

Do not enable global execution.

Add a dry-run/preflight path that evaluates every authorization requirement without sending motion.

It must report each gate separately:

~~~text
START_MATCH
SCENE_FRESH
BASE_STATIONARY
INACTIVE_ARM_KNOWN
TOOL_REVISION_MATCH
TRAJECTORY_COLLISION_CHECKED
CENTRAL_EXCLUSION
VELOCITY
ACCELERATION
NATIVE_SENDER_LIMITS
TRACKING_PREDICTION
EXECUTION_ENABLED
SPEED_PROFILE_COMMISSIONED
~~~

Expected remaining blockers may include execution_enabled and speed-profile commissioning.

Do not bypass them.

## 9. A/B state machine update

Keep the P3.2 cuRobo-only/no-waypoint policy.

Extend the state machine with an execution candidate / lease:

~~~text
AT_A / AT_B
→ SCANNING
→ SCENE_READY
→ CUROBO_PLANNED
→ VALIDATED
→ PREVIEWED
→ AWAITING_CONFIRMATION
→ future EXECUTING
→ ARRIVED
~~~

On arrival/stop/fault:

- invalidate scene;
- invalidate trajectory;
- invalidate execution lease.

The execute-next operation remains blocked in P3.3.

## 10. Required planning-only reruns

Using fresh or frozen reference scenes as appropriate:

### CLEAR
- both directions success;
- repeated clearance gate passes with conservative tool envelope;
- trajectory style remains close to operator-approved appearance.

### AVOID
- both directions success;
- observed box remains limiting/relevant obstacle;
- repeated clearance gate passes;
- no explicit waypoint;
- cuRobo chooses route;
- trajectory remains smooth and visually acceptable.

### BLOCK
- safe failure;
- no fallback.

If the more conservative tool envelope invalidates the old A/B plan, report that honestly.

## 11. Exit gates

Report:

~~~text
CUROBO_ONLY_POLICY_LOCKED = YES/NO
NO_EXPLICIT_WAYPOINT_POLICY_LOCKED = YES/NO
EXECUTION_TOOL_ENVELOPE_READY = YES/NO
CLEARANCE_REPRODUCIBILITY_READY = YES/NO
EXECUTION_CANDIDATE_SELECTOR_READY = YES/NO
NATIVE_TRAJECTORY_PACKAGING_READY = YES/NO
EXECUTION_LEASE_BINDING_READY = YES/NO
SAFETY_PREFLIGHT_READY = YES/NO
CURRENT_TO_A_EXECUTION_PACKAGE_READY = YES/NO
A_TO_B_EXECUTION_PACKAGE_READY = YES/NO
B_TO_A_EXECUTION_PACKAGE_READY = YES/NO
READY_TO_REQUEST_FIRST_SUPERVISED_MOTION = YES/NO
~~~

Also report:

- chosen planner profile;
- repeat clearance distribution;
- conservative tool envelope dimensions/revision;
- selected trajectory hashes;
- slow-profile durations;
- predicted tracking margins;
- remaining SafetyKernel blockers;
- tests;
- local commit SHA.

## 12. Push / motion policy

Commit locally and STOP.

Do not push automatically.
Do not execute hardware motion.

After ChatGPT review, push may be authorized.

Only after a separate explicit user authorization may the first supervised CURRENT→A physical motion be attempted.
