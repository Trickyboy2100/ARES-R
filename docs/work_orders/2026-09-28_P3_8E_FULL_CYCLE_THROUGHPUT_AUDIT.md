# P3.8E — Full-cycle throughput / continuity audit before optimization

Date: 2026-09-28
Mode: AUDIT ONLY
Goal: explain exactly why the customer Tray→Groove flow is slow and stop-go, then produce an implementation-ready acceleration plan. Do not change production behavior in this phase.

Read first:

~~~text
docs/research/2026-09-26_JAKA_FORCE_SENSOR_AND_FLOW_ACCELERATION.md
docs/work_orders/2026-09-26_P3_8D_FORCE_ASSISTED_FULL_FLOW_ACCELERATION.md
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
docs/decisions/2026-09-24_CONTACT_COLLISION_DEMO_POLICY.md
docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md
docs/reports/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT_REPORT.md
~~~

Also inspect the current integration branch, not only planning docs.

Current integration HEAD observed when this order was written:

~~~text
e470fd46e8d77ba4e24394401d5dadcd4e50ab1b
feat(terminal): prepare selected demo from ART
~~~

Do not assume this SHA is still current; verify first.

## 0. Audit boundary

This phase is deliberately broad but read-only/non-disruptive.

Allowed:

- inspect code/config/logs/evidence;
- read JAKA/AMR/gripper/camera status if needed;
- inspect current services/processes/sockets;
- run offline/replay benchmarks using frozen artifacts;
- start/stop local non-hardware benchmark services;
- run unit tests;
- create reports and planning documents.

Not allowed:

- arm motion;
- gripper motion;
- AMR motion;
- changing speed/acceleration/tracking thresholds;
- changing planner parameters in production;
- enabling force compliance;
- replacing current working Scheme behavior;
- deleting or rewriting successful first-pick evidence.

If a live nonmoving camera/5700 capture is useful, it may be taken, but do not make the audit depend on moving hardware.

## 1. Preserve the current successful state

Before analysis:

1. record .32 HEAD/branch/ahead-behind;
2. record GitHub integration HEAD;
3. list dirty/untracked files;
4. identify which successful first-pick / ART / Scheme changes are canonical vs only local;
5. preserve unrelated coworker AMR/gripper changes;
6. run full tests and record baseline.

Create:

~~~text
worklog/evidence/2026-09-28-full-cycle-throughput-audit/preservation/
~~~

## 2. Build one canonical end-to-end timeline from real evidence

Do not estimate from memory.

Use the successful real pick and the newest available Tray→Groove rehearsal/execution logs.

Extract timestamps for every stage that can be recovered:

~~~text
operator/task start
process/service startup
AMR request
AMR physical motion
AMR settle confirmation
5700 request/response
5000 trigger/download/decode/write
CAMERA→BODY
ROI/downsample
self-filter
scene decomposition
SceneSnapshot commit
planner request
world update
IK/goal search
cuRobo solve
dense validation
serialization/package
preflight
Servo enable
trajectory execution
Servo disable
gripper command
gripper wait/readback
pointcloud grasp verification
report/evidence writes
human/AI idle gaps between commands
~~~

Produce one exact waterfall for the first successful pick and, if enough evidence exists, one reconstructed full pick-place critical path.

Classify every interval as:

~~~text
COMPUTE
DEVICE_WAIT
MOTION
SERIALIZATION_IO
ORCHESTRATION_IDLE
OPERATOR_WAIT
REDUNDANT_WORK
UNKNOWN
~~~

Do not hide UNKNOWN time.

## 3. Critical-path / DAG audit

Draw the actual current dependency graph and a proposed pipelined graph.

For each stage answer:

- what must happen strictly before it?
- what can run concurrently?
- what can be prepared speculatively?
- what must be invalidated if the prior prediction was wrong?
- what hardware/resource lock does it need?

Explicitly audit these concurrency candidates:

~~~text
5700 detection || Pixel Pro capture
pointcloud decode || 5700 parse/target construction
scene build || goal/constraint preparation
pregrasp execution || contact trajectory preparation
pregrasp execution || lift trajectory preparation
gripper close || force/readback monitoring
initial lift || grasp verification
arm visibility-clear move || placement-side service warmup
AMR move || right_place profile/service warmup
AMR settle window || camera/planner warmup
preplace execution || descent/release trajectory preparation
evidence/report rendering || next-stage execution
~~~

Mark each candidate:

~~~text
SAFE_NOW
SAFE_WITH_BINDING_CHECK
NOT_SAFE
NOT_IMPLEMENTED
~~~

## 4. Scheme orchestration audit

Inspect current:

~~~text
src/ares_r/manipulation/scheme_backend.py
src/ares_r/manipulation/tray_to_groove_scheme.py
ART task/scheme commands
WebUI task controls
~~~

Determine:

- whether a real native execution runner exists or the flow is still planning-only / externally orchestrated;
- where Codex/operator handoffs still sit on the critical path;
- how many Python processes/scripts are spawned per cycle;
- how many times JSON/files are written then immediately reread by the next stage;
- whether state transitions are event-driven or polling/conversation-driven;
- whether Stage N+1 can enter PREPARING while Stage N is EXECUTING;
- whether cancellation/abort semantics support pipelining safely.

Output:

~~~text
NATIVE_SCHEME_RUNNER_CURRENT_STATE
CONVERSATIONAL_STAGES_ON_CRITICAL_PATH = list
PROCESS_SPAWNS_PER_CYCLE = n
FILE_HANDOFFS_PER_CYCLE = n
~~~

## 5. Persistent-service audit

Inspect current persistent services:

~~~text
Pixel Pro capture service
persistent cuRobo planner
JAKA feedback reader
WebUI/ART backend
future ForceMonitor
~~~

For each report:

- persistent or one-shot?
- startup cost;
- request p50/p95 from existing logs if available;
- whether it survives the whole Scheme;
- whether it can accept concurrent preparation requests;
- resource/GPU/thread safety;
- restart/failure behavior.

Verify whether persistent cuRobo actually reuses the same MotionGen/runtime between Scheme stages or whether wrappers/processes still rebuild hidden state.

## 6. Perception / scene lifecycle audit

Count the number of full Pixel Pro scans and scene builds in the successful pick path and expected full Scheme.

For every scan answer WHY it is needed.

Use these target semantics:

Full fresh scene should normally be required after:

- AMR/base motion;
- explicit external scene change;
- unexpected contact/change;
- before a new free-space environment epoch if current scene is stale.

Full fresh scene should NOT automatically be required between:

- pregrasp;
- contact approach;
- gripper close;
- initial 100 mm lift;

when base/environment did not change and the bounded contact/attachment transition is known.

Audit:

- duplicate captures;
- duplicate pointcloud decode;
- unnecessary PLY/image artifacts in online path;
- scene rebuilds triggered only because robot moved;
- self-filter cost;
- voxel/downsample settings;
- synchronous hashing/NPY/JSON writes;
- whether scene construction can consume in-memory arrays rather than files.

Output current and minimum-required scan count for one full pick-place cycle.

## 7. 5700 + 5000 ObservationTransaction parallelism audit

Current transaction correctness must be preserved.

Determine whether the atomic observation currently does:

~~~text
robot-before → 5700 → 5000 → robot-after
~~~

strictly serially.

Design a safe concurrent form:

~~~text
robot-before
→ launch 5700 and 5000 together
→ await both
→ robot-after
→ validate robot stationary + capture time window
→ atomic commit
~~~

Measure expected/actual time saved using frozen or live nonmoving benchmark.

Do not implement in this audit.

## 8. Planner throughput audit

Inspect current persistent planner and all wrappers around it.

Measure/replay:

- service startup/warmup;
- update_world;
- IK/goal candidate generation;
- MotionGen solve;
- orientation/yaw candidate handling;
- dense validation;
- packaging/serialization;
- retries/fallbacks.

Audit these optimization candidates without changing production:

~~~text
persistent MotionGen reuse
single solve per request
CUDA graph ON
goalset/batched yaw candidates instead of Python serial loops
FAST planner profile (e.g. fewer seeds / 1 attempt)
SLOW fallback only after fast failure
skip graph attempt on easy cases
dense validator knot/subdivision cost
in-memory request/result path
~~~

For each estimate benefit and correctness risk from replay benchmarks.

Required recommendation:

~~~text
FAST_PATH planner config
FALLBACK planner config
switch condition
~~~

Do not change current production planner in this phase.

## 9. Motion execution continuity audit

Inspect current native ServoJ sender / trajectory packaging.

Determine exactly where the robot comes to zero velocity and why.

Audit:

- separate Servo enable/disable per segment;
- file/package handoff between segments;
- 80 ms vs planner interpolation sample periods;
- retiming cost;
- whether contact/lift trajectories can be prepared before pregrasp arrival;
- whether one Servo session can span free-space→hold→contact→lift safely;
- whether segments can be concatenated/blended while preserving force/gripper event synchronization;
- current velocity, acceleration, jerk, tracking thresholds by stage.

Do NOT assume JAKA blending API is automatically usable with current ServoJ trajectory streaming.

Classify options:

~~~text
A keep separate ServoJ segments but remove software idle gaps
B one continuous ServoJ stream with planned hold/event markers
C controller MoveJ/MoveL blending for selected non-curobo segments
~~~

Recommend the least risky option that produces visually continuous motion.

## 10. Stage-specific speed audit

Use real tracking data, not generic limits.

Collect from existing successful runs:

~~~text
pregrasp:
  duration
  peak/p95 tracking error
contact:
  duration
  peak/p95 tracking error
lift:
  duration
  peak/p95 tracking error
free-space obstacle demo:
  duration
  tracking
AMR:
  translation speed
  settle delay
~~~

Determine which stage is actually speed-limited by:

- velocity;
- acceleration;
- tracking threshold;
- trajectory length;
- conservative retiming;
- controller cadence;
- orchestration idle.

Recommend a commissioning ladder for:

~~~text
FREE_SPACE_FAST
CONTACT_FORCE_GUARDED
VERTICAL_LIFT
TRANSFER_WITH_OBJECT
BASE_TRANSLATION
~~~

But do NOT execute it in this audit.

## 11. Force-feedback acceleration audit

Use the existing force research note as hypothesis, then inspect current SDK/site capability.

Audit only:

- can six-axis force be read from current JAKA SDK/controller?
- estimated sampling rate / access path;
- can it run concurrently with Servo feedback?
- frame semantics known/unknown;
- zeroing requirements;
- whether force-first grasp verification can remove the post-grasp full pointcloud scan;
- whether force can monitor contact while CONTACT_BYPASS_V1 remains active;
- whether placement can use force event as early stop/verification.

Do not enable compliance or zero the sensor in this audit.

Estimate cycle-time savings for:

~~~text
FORCE_GRASP_VERIFY primary + pointcloud fallback
vs
always Pixel Pro post-grasp verification
~~~

## 12. Gripper timing audit

Measure from existing logs/code:

- command send latency;
- physical close/open duration if logged;
- readback polling interval;
- how many delayed reads are currently required;
- whether readback polling can overlap force/lift preparation;
- whether 50%→40% can occur while the arm is approaching pregrasp without physical interference.

Mark any safe overlap opportunities.

## 13. AMR movement / settle audit

Inspect current BaseMotionObserver and real field logs.

Quantify:

- request latency;
- physical 0.30/0.40 m travel duration;
- unnecessary settle wait;
- number and cost of pointcloud/landmark observations used to prove settled;
- whether camera service/planner can warm during base travel;
- whether 5700/5000 can start immediately after a robust stop event rather than an arbitrary delay.

Recommend a fast but truthful settle policy.

Do not weaken completion semantics back to accepted/IDLE.

## 14. Evidence/logging overhead audit

Profile synchronous evidence work:

- JSON pretty-print;
- hashing;
- NPY/PLY writes;
- screenshots;
- WebUI serialization;
- report generation;
- Git/worklog writes.

Identify which artifacts are required on the real-time path vs can be queued asynchronously after stage completion.

Propose:

~~~text
REALTIME_MINIMAL_LOG
ASYNC_EVIDENCE_WRITER
POST_RUN_REPORTER
~~~

## 15. WebUI / ART continuity audit

Inspect whether WebUI/ART:

- share one backend state machine;
- accidentally trigger duplicate work;
- poll expensive status endpoints too often;
- block the Scheme on UI rendering;
- expose stage preparation/next-plan status.

Propose one customer-demo view showing:

~~~text
current task stage
next stage preparing/ready
scene status
planner status
force/gripper status
cycle timer
one prominent Stop
~~~

UI must never sit on the critical path for robot progression.

## 16. Target architecture — event-driven pipelined Scheme runner

Produce a concrete design for:

~~~text
IDLE
→ PREPARING_STAGE_0
→ EXECUTING_STAGE_N
   while PREPARING_STAGE_N+1
→ VERIFYING event embedded/overlapped when possible
→ transition without conversation/manual script spawn
~~~

Define resource locks:

~~~text
ARM_RIGHT
GRIPPER_RIGHT
BASE
CAMERA_5700
CAMERA_5000
GPU_PLANNER
FORCE_MONITOR
SCENE_EPOCH
~~~

Define stale/invalidation conditions for speculative/prepared trajectories.

## 17. Quantitative optimization backlog

For every proposed optimization provide a table:

~~~text
ID
change
current cost
expected saved seconds
implementation effort S/M/L
risk LOW/MED/HIGH
dependencies
proof/benchmark needed
recommended phase
~~~

Rank by:

1. seconds removed from customer-visible critical path;
2. continuity / visible smoothness;
3. low implementation risk.

Do not rank by coding elegance.

## 18. Required target cycle-time model

Build at least three models:

~~~text
BASELINE_CURRENT
PHASE_1_LOW_RISK
PHASE_2_PIPELINED
PHASE_3_STREAMING_SCENE_OPTIONAL
~~~

Use measured numbers where available and explicitly label estimates.

Set proposed KPI targets for:

- command→pickup-base-settled;
- pickup observation;
- observation→pregrasp start;
- pregrasp→object lifted;
- lift→place-base-settled;
- placement observation→release;
- total task cycle time.

## 19. Required report

Create:

~~~text
docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md
~~~

Must include:

~~~text
CURRENT_TOTAL_CYCLE_TIME_KNOWN = YES/NO
CURRENT_PICK_CRITICAL_PATH_S = value/UNKNOWN
CURRENT_FULL_TASK_CRITICAL_PATH_S = value/ESTIMATE
REDUNDANT_FULL_SCANS_FOUND = n
SERIALIZABLE_ORCHESTRATION_GAPS_S = value
PARALLELIZABLE_STAGES = list
PERSISTENT_SERVICE_GAPS = list
PLANNER_FAST_PATH_RECOMMENDATION_READY = YES/NO
MOTION_CONTINUITY_RECOMMENDATION_READY = YES/NO
FORCE_ACCELERATION_OPPORTUNITY_READY = YES/NO
NATIVE_PIPELINED_SCHEME_DESIGN_READY = YES/NO
PHASE1_EXPECTED_TOTAL_CYCLE_S = value
PHASE2_EXPECTED_TOTAL_CYCLE_S = value
IMPLEMENTATION_PRIORITY_TOP10 = list
~~~

Also create:

~~~text
docs/roadmaps/2026-09-28_TRAY_TO_GROOVE_CYCLE_TIME_OPTIMIZATION_ROADMAP.md
~~~

The roadmap must convert the audit into 2–4 implementation phases with measurable exit gates.

## 20. End-of-audit behavior

STOP after report + roadmap + tests + local commit.

Do not implement the optimizations in P3.8E.
Do not execute hardware motion.
Do not push integration automatically; report the local commit and recommended next implementation phase.

## 21. USER ACTION policy

No physical USER ACTION should normally be necessary for this audit.

If exact force-sensor model cannot be found remotely, record it as a deferred follow-up rather than blocking this throughput audit.