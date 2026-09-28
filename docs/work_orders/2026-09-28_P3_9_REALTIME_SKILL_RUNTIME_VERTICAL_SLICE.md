# P3.9 — Realtime Skill Runtime vertical slice + full Tray→Groove preparation

Date: 2026-09-28
Mode: IMPLEMENTATION
Goal: implement the two next workstreams together:

1. throughput / realtime continuity;
2. Skill packaging + Task/Scheme runtime;

and use the complete Tray→Groove task as the first reference vertical slice.

Read first:

~~~text
docs/architecture/2026-09-28_REALTIME_SKILL_TASK_RUNTIME.md
docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md
docs/roadmaps/2026-09-28_TRAY_TO_GROOVE_CYCLE_TIME_OPTIMIZATION_ROADMAP.md
docs/SKILL_CATALOG.md
docs/SKILL_LIBRARY_ARCHITECTURE.md
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
~~~

Verify current integration HEAD before coding.

## 0. Preserve current state

Before implementation:

- record .32 HEAD / GitHub HEAD / dirty files;
- preserve unrelated grasp.py/test/site changes;
- run current full tests;
- preserve P3.8E report/evidence;
- do not force-push.

## 1. Implement SkillRuntime core

Create a minimal runtime package, exact filenames may adapt:

~~~text
src/ares_r/skills/
  contracts.py
  registry.py
  runtime.py
  locks.py
  providers.py
  events.py
~~~

Minimum types:

~~~text
SkillDefinition
SkillInvocation
SkillPlan
SkillResult
SkillContext
SkillRegistry
CapabilityProvider
CancellationToken
ResourceLockManager
~~~

Do not copy the entire documentation model if not needed. Implement the minimum executable subset while preserving the documented semantics.

Normal failures must return typed SkillResult/failure_code, not leak arbitrary exceptions into Scheme control flow.

## 2. Implement event stream and timing first

Every runtime action emits monotonic events:

~~~text
TASK_ACCEPTED
STAGE_PREPARING
STAGE_PREPARED
STAGE_EXECUTING
STAGE_VERIFYING
STAGE_SUCCEEDED
STAGE_FAILED
LOCK_ACQUIRED/RELEASED
SCENE_BOUND/INVALIDATED
PLAN_READY/INVALIDATED
DEVICE_REQUEST/COMPLETE
STOP/FAULT
~~~

Each event includes trace_id, task_run_id, stage_id, skill_id, timestamp, revisions and optional timing.

Use this stream as the single source for cycle-time reports.

## 3. AsyncEvidenceWriter

Implement a background evidence queue.

Realtime path writes only compact append/event records.

Move these off the critical path where possible:

- pretty JSON;
- large hashes/file manifests;
- screenshots;
- plots;
- report generation.

Requirements:

- bounded queue;
- flush on task complete/fault;
- crash-safe minimal event log remains synchronous;
- tests for backpressure/failure.

## 4. Persistent service ownership

Runtime should own/reuse:

~~~text
PixelProCaptureService
PersistentCuroboPlanner
JAKA read-only telemetry service
WebUI/ART event backend
~~~

Legacy scripts may remain for debugging.

Production Scheme must not spawn the one-shot planner/capture worker per stage when persistent service is healthy.

Add service health/status and fallback-to-one-shot only when explicitly safe.

## 5. ObservationTransactionV2

Implement parallel 5700 + 5000 under one stationary bracket:

~~~text
read_before
→ launch Epic5700 + PixelPro5000 concurrently
→ parse/decode concurrently
→ await both
→ read_after
→ verify stationary/time window
→ atomic observation/scene commit
~~~

Preserve exact detection/pointcloud/calibration/tool provenance.

Benchmark against existing serial transaction using frozen/live-nonmoving evidence.

Exit target:

~~~text
OBSERVATION_V2_PARALLEL_READY = YES
normal p50 target <=10.5 s
~~~

## 6. Planner FAST/FALLBACK routing

Implement two planner profiles behind the same MotionProvider:

~~~text
FAST_PATH:
  persistent runtime
  4 IK seeds
  2 trajopt seeds
  one solve
  graph attempt OFF
  dense validation mandatory

FALLBACK:
  persistent runtime
  8/8
  graph attempt ON
~~~

Switch only after FAST failure/invalid result.

Do not change physical motion speed.

Record planner mode and timing in SkillResult.

## 7. Implement the first real Skill adapters

Wrap existing canonical services; do not duplicate algorithms.

Required first Skills:

~~~text
observe.capture_scene
observe.detect_resource
navigate.registered_relative
manipulation.move_free
manipulation.approach
manipulation.grasp
manipulation.lift
manipulation.move_above_place
manipulation.release
manipulation.retreat
execution.authorize
execution.execute_trajectory
~~~

Then composite:

~~~text
manipulation.pick
manipulation.place
manipulation.transfer_object
~~~

Use current successful semantics:

- free-space → SceneAwareMotionService;
- contact → CONTACT_BYPASS_V1;
- attachment → coarse attached object;
- left arm → HOLD_CURRENT.

Force-assisted verification is NOT required in P3.9.

## 8. Declarative Scheme format

Create a versioned Scheme definition under e.g.:

~~~text
schemes/tray_to_groove_v1.yaml or .json
~~~

It must reference Skill IDs, typed parameters/resource refs and dependencies.

Do not store joint trajectories in Scheme data.

Must support:

- execute dependencies;
- prepare dependencies;
- output bindings;
- failure action/recovery;
- stage timeout;
- resource locks.

## 9. Native pipelined SchemeRunner

Implement a real runner independent of ART/WebUI.

Required behavior:

~~~text
Stage N EXECUTING
while
Stage N+1 PREPARING
~~~

only when lock/binding rules allow it.

Prepared plans are immutable and include:

- expected start joints;
- scene epoch;
- tool revision;
- attachment revision;
- planner profile;
- expiration.

Before execute:

~~~text
revalidate binding
→ execute
or
invalidate prepared plan and replan
~~~

Stop must:

- cancel current stage;
- revoke prepared/speculative plans;
- halt controlled devices through existing providers;
- invalidate uncertain scene/effects.

## 10. Tray→Groove vertical slice

Compile the owner Scheme into the new runtime:

~~~text
PICK_BASE
→ PICK_OBSERVATION (5700 || 5000)
→ MOVE_PREGRASP
→ CONTACT_APPROACH
→ GRASP
→ VERIFY_GRASP
→ INITIAL_LIFT
→ ATTACH
→ VISIBILITY_CLEAR
→ PLACE_BASE
→ PLACE_OBSERVATION (5700 || 5000)
→ MOVE_PREPLACE
→ PLACE_DESCEND
→ RELEASE
→ RETREAT
→ VERIFY_RESULT
~~~

Do not require conversational/Codex handoff between these stages.

## 11. Phase-1 continuity policy

Keep separate ServoJ segments.

Do NOT yet implement continuous Servo stream/blending.

Remove software idle by:

- preparing contact/lift while pregrasp executes;
- preopening/preparing gripper command where safe;
- warming place services during visibility-clear/base motion;
- immediate event-driven next-stage launch;
- async evidence.

## 12. Scene policy

Normal full path target:

~~~text
pickup full scene = 1
placement full scene = 1
post-grasp full scene = 0 normal path
~~~

Post-grasp pointcloud verification may remain as fallback/manual evidence until force verification is implemented.

For P3.9 dry-run, verify the runner does not force a redundant full scan between contact/grasp/initial lift.

## 13. ART/WebUI integration

Add shared task commands:

~~~text
skill list
skill inspect ID
task list
task inspect tray_to_groove
task prepare tray_to_groove
task preview
task status
task stop
~~~

`task run` remains locked until the implementation/replay acceptance gates below pass.

WebUI must show:

- task run ID;
- current Skill;
- next stage PREPARING/PREPARED;
- scene epoch;
- planner FAST/FALLBACK;
- cycle timer;
- Stop.

UI never drives progression.

## 14. Replay and fault-injection acceptance

Before physical execution:

- replay the successful first-pick evidence through the new runtime;
- simulate full pick-place using existing pick/place epochs and planning artifacts;
- test planner FAST success and fallback;
- stale scene invalidation;
- start-state mismatch;
- base move invalidation;
- attachment revision mismatch;
- gripper verification failure;
- stop during PREPARING;
- stop during EXECUTING;
- evidence queue failure;
- persistent service restart/fallback.

All must produce deterministic SkillResults and leave resources quiescent.

## 15. Phase-1 performance benchmark

Run frozen/replay performance and report:

~~~text
observation V1 vs V2
persistent FAST planner vs current path
orchestration process spawn count
file handoff count
async evidence time hidden
prepared-next-stage hit rate in replay
modeled total cycle
~~~

Target model:

~~~text
PHASE1_MODELED_TOTAL_CYCLE_S <= 420
~~~

Do not fake the target if evidence says otherwise.

## 16. Full demo readiness package

At P3.9 exit, produce an immutable:

~~~text
TRAY_TO_GROOVE_RUNTIME_PACKAGE
~~~

containing:

- Scheme version;
- Skill versions;
- provider revisions;
- task parameters;
- planner profiles;
- scene/contact policy;
- speed profiles (unchanged current commissioned values);
- recovery graph;
- required user authorization;
- expected stage list.

Do not execute full hardware cycle in P3.9 unless separately authorized.

## 17. Exit report

Create:

~~~text
docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md
~~~

Report:

~~~text
SKILL_RUNTIME_CORE_READY = YES/NO
SKILL_REGISTRY_READY = YES/NO
REAL_PROVIDER_VERTICAL_SLICE_READY = YES/NO
OBSERVATION_V2_PARALLEL_READY = YES/NO
PERSISTENT_CAPTURE_OWNED_BY_RUNTIME = YES/NO
PERSISTENT_PLANNER_OWNED_BY_RUNTIME = YES/NO
FAST_FALLBACK_PLANNER_READY = YES/NO
ASYNC_EVIDENCE_READY = YES/NO
DECLARATIVE_SCHEME_READY = YES/NO
NATIVE_PIPELINED_SCHEME_RUNNER_READY = YES/NO
TRAY_TO_GROOVE_REPLAY_PASS = YES/NO
FAULT_INJECTION_PASS = YES/NO
PHASE1_MODELED_TOTAL_CYCLE_S = value
FULL_DEMO_RUNTIME_PACKAGE_READY = YES/NO
READY_FOR_UNCHANGED_SPEED_FULL_SUPERVISED_CYCLE = YES/NO
~~~

## 18. Stop point

Stop after:

- code;
- tests;
- replay benchmark;
- report;
- local small commits.

Do not change physical speed profiles.
Do not start force-control implementation.
Do not execute the complete physical cycle without explicit user approval.

## 19. Git

Small commits by subsystem.
No force-push.
Keep unrelated current dirty files isolated.
Leave a clear local/remote SHA report.