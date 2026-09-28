# ARES-R Realtime Skill/Task Runtime Architecture

Date: 2026-09-28
Status: implementation architecture for post-P3.8E

## 0. Why the next two workstreams must be implemented together

The next two priorities are:

1. cycle-time / realtime optimization;
2. Skill packaging + task/scheme organization for easy task changes and new tasks.

They should NOT be implemented as two separate codebases.

The throughput audit showed that the largest delay is orchestration, process/file handoff and non-motion idle. The current Skill architecture already defines stable semantic contracts, but the repository only has thin planning adapters and a planning-only Scheme. Therefore the same new runtime should solve both problems:

~~~text
Task
→ Scheme / DAG
→ SkillRuntime
→ Capability Providers
→ persistent Scene / Planner / JAKA / Gripper / AMR services
~~~

Speed comes from a native event-driven runner, persistent services, preparation overlap and less file/process handoff.

Extensibility comes from stable Skill contracts, typed parameters, providers and declarative Schemes.

## 1. Do not build a giant generic framework before the demo

Implement a vertical slice around the already successful Tray→Groove task.

Generalize contracts, not every possible behavior.

First executable Skill set:

~~~text
observe.capture_scene
observe.detect_resource
navigate.go_to_station / navigate.registered_relative
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

Composite skills:

~~~text
manipulation.pick
manipulation.place
manipulation.transfer_object
~~~

First Task:

~~~text
task.tray_to_groove
~~~

New tasks should normally be expressible by changing a Scheme and Resource/Affordance bindings rather than writing a new controller.

## 2. Layering

### L0 Hardware / motion primitives

Existing JAKA, gripper, AMR, camera and cuRobo services remain authoritative.

No new Skill code should duplicate:

- obstacle reconstruction;
- cuRobo integration;
- native ServoJ sender;
- gripper protocol;
- AMR HTTP protocol;
- camera protocol.

### L1 Skill providers

A provider wraps existing canonical services and exposes typed asynchronous operations.

Examples:

~~~text
SceneProvider.capture_scene
DetectionProvider.detect_resource
NavigationProvider.navigate
MotionProvider.plan_free
MotionProvider.execute_trajectory
ContactProvider.approach
GripperProvider.command
VerificationProvider.verify_grasp
AttachmentProvider.attach/detach
~~~

### L2 SkillRuntime

Owns:

- SkillInvocation / SkillPlan / SkillResult;
- preconditions;
- resource locks;
- cancellation;
- plan freshness;
- execution lease;
- event stream;
- timeout;
- verification/effect commit.

### L3 Scheme / DAG Runner

Owns ordering and concurrency:

~~~text
READY
PREPARING
PREPARED
EXECUTING
VERIFYING
SUCCEEDED / FAILED / CANCELLED
~~~

Stage N+1 may PREPARE while Stage N EXECUTES if their resource locks and binding rules allow it.

### L4 Task

A Task selects:

- Scheme;
- ResourceRefs;
- semantic target policies;
- task parameter revision;
- runtime policy.

The Task never contains joint/TCP trajectories.

## 3. Runtime objects

Minimal implementation types:

~~~text
SkillInvocation
  invocation_id
  skill_id
  version
  parameters
  trace_id
  task_id

SkillPlan
  plan_id
  invocation_id
  scene_snapshot_id
  planning_context_digest
  robot/tool/attachment revisions
  required locks
  expires_at
  provider_plan

SkillResult
  status
  failure_code
  verified_effects
  timings
  evidence_refs

StageNode
  node_id
  skill invocation template
  dependencies
  prepare_dependencies
  resource locks
  bindings from prior outputs

TaskRun
  run_id
  current stage
  prepared stages
  event stream
  cancel token
~~~

## 4. Concurrency model

Use two dependency concepts:

### execute_dependencies

The stage cannot execute until these stages have succeeded.

### prepare_dependencies

The stage may begin planning/preparation once these weaker prerequisites exist.

Example:

~~~text
MOVE_PREGRASP executes after PICK_OBSERVATION

CONTACT_APPROACH may PREPARE while MOVE_PREGRASP is EXECUTING
but final execution binds the actual pregrasp arrival joints.

LIFT may PREPARE from the expected grasp state
but executes only after GRASP verification and start-state rebind.
~~~

Prepared work is discarded on binding mismatch. It is never silently rebound.

## 5. Resource locks

Start with:

~~~text
ARM_RIGHT
GRIPPER_RIGHT
BASE
CAMERA_5700
CAMERA_5000
GPU_PLANNER
SCENE_EPOCH
FORCE_MONITOR
~~~

Important rule:

planning/preparation can often use GPU_PLANNER without locking ARM_RIGHT.

Execution must own the physical resource lock.

This separation enables plan-ahead.

## 6. Persistent services owned by runtime

Runtime startup should own long-lived:

~~~text
PixelProCaptureService
PersistentCuroboPlanner
JakaTelemetryService
WebUI/ART event backend
AsyncEvidenceWriter
future ForceMonitor
~~~

A Skill request should call an in-process/service API, not spawn a new process for every stage.

Legacy one-shot scripts remain fallback/debug tools.

## 7. ObservationTransactionV2

Preserve atomic correctness but parallelize sensors:

~~~text
read robot-before
→ concurrently:
    Epic 5700 detection
    Pixel Pro 5000 capture
→ pointcloud decode and target parse proceed concurrently
→ read robot-after
→ stationary/time-window validation
→ scene + target atomic commit
~~~

`observe.capture_scene` and `observe.detect_resource` remain separate semantic Skills, but the RealProvider may optimize them through one shared ObservationTransactionV2 barrier when a Scheme requests both.

This avoids inventing a giant observation Skill while still gaining concurrency.

## 8. Planner policy

Phase-1 runtime uses:

~~~text
FAST_PATH
  persistent MotionGen
  4 IK seeds
  2 trajopt seeds
  one solve
  graph attempt off
  mandatory dense validation

FALLBACK
  persistent runtime
  8/8
  graph attempt on
~~~

Fallback only after FAST failure or invalid result.

Do not change physical speed profiles in Phase 1.

## 9. Scene lifecycle

Normal full Tray→Groove path should use:

~~~text
one pickup scene epoch
one placement scene epoch
~~~

Do not full-rescan between pregrasp/contact/grasp/initial lift when:

- base did not move;
- external environment did not change unexpectedly;
- the contact/attachment transition is known;
- verification is healthy.

Attachment is a semantic/world transition, not a reason by itself to reacquire the entire environment.

## 10. Motion continuity strategy

Phase 1:

- keep distinct commissioned ServoJ segments;
- remove software/conversation idle between them;
- prepare next native package before current segment ends where possible;
- start next segment immediately after the required event.

Do NOT make continuous ServoJ streaming or controller blending a Phase-1 dependency.

Phase 2 may evaluate one cycle-long Servo stream with explicit HOLD/gripper/force event markers.

## 11. Evidence and UI

Realtime path:

~~~text
append-only compact event log
critical hashes/revisions
telemetry/faults
~~~

Async path:

~~~text
pretty JSON
NPY/PLY
screenshots
waterfalls
reports
~~~

WebUI/ART are clients of TaskRuntime.

UI may show:

~~~text
current Skill
next Skill PREPARING/PREPARED
scene epoch
planner FAST/FALLBACK
gripper/force status
cycle timer
STOP
~~~

UI must never gate task progression.

## 12. Declarative Scheme

Move Tray→Groove ordering from Python control flow into a versioned declarative Scheme definition.

Concept:

~~~yaml
scheme_id: tray_to_groove_v1
nodes:
  - id: pick_observation
    skills: [observe.capture_scene, observe.detect_resource]
    execution: parallel_barrier

  - id: move_pregrasp
    skill: manipulation.move_free
    depends_on: [pick_observation]

  - id: contact
    skill: manipulation.approach
    depends_on: [move_pregrasp]
    prepare_after: [pick_observation]

  - id: grasp
    skill: manipulation.grasp
    depends_on: [contact]

  - id: lift
    skill: manipulation.lift
    depends_on: [grasp]
    prepare_after: [move_pregrasp]
~~~

The exact schema can adapt to current repo style, but it must be data-driven and versioned.

## 13. Task customization

To create a new task, the normal path becomes:

~~~text
1 define/choose Resources and Affordances
2 compose existing Skills in a Scheme
3 bind task parameters
4 dry-run / preview
5 commission only new physical semantics
~~~

Only create a new Skill when the semantic intent has new preconditions/effects, not merely because coordinates or device instances changed.

## 14. Tray→Groove as reference acceptance task

The first runtime must support the existing owner flow:

~~~text
pickup base
→ parallel atomic pick observation
→ free-space pregrasp
→ bounded contact approach
→ grasp verification
→ initial lift / attach
→ visibility clear
→ placement base
→ parallel atomic place observation
→ free-space preplace
→ bounded place descent
→ release
→ retreat
→ verify
~~~

Use current successful CONTACT_BYPASS_V1 and coarse attachment semantics for the first full demo.

Force-assisted verification is Phase 2, not required to build the runtime.

## 15. Implementation phases

### Phase A — Runtime spine + Skill contracts

- SkillRegistry;
- SkillInvocation/Plan/Result;
- CapabilityProvider contracts;
- resource locks/cancellation;
- event stream;
- AsyncEvidenceWriter;
- deterministic replay tests.

### Phase B — Real vertical slice

Wrap existing working services as providers and implement the minimum Skills needed for Tray→Groove.

### Phase C — Native pipelined Scheme runner

- declarative Scheme loader;
- prepare/execute dependency graph;
- plan-ahead;
- ObservationTransactionV2;
- persistent planner/capture ownership;
- FAST/FALLBACK planner.

### Phase D — Full unchanged-speed supervised demo

Run the complete pick→transfer→place once without changing current physical motion profiles.

This proves the framework before speed commissioning.

### Phase E — Realtime optimization

- force monitor/verification;
- stage-specific speed profiles;
- more aggressive plan-ahead;
- optional continuous Servo stream;
- optional streaming scene.

## 16. Quantitative Phase-1 target

Use the P3.8E audit as acceptance:

~~~text
current modeled full cycle: ~606 s
Phase-1 target: <=420 s
without changing robot motion speed
~~~

The first goal is to remove idle/orchestration, not to make the robot physically faster.

Phase 2 then targets <=290 s through force verification, retiming and deeper pipelining.

## 17. Non-goals

Do not:

- rewrite cuRobo;
- replace WorldModel;
- introduce ROS/BehaviorTree dependency just to get a task runner;
- expose raw motion APIs to LLM;
- build every Skill in the catalog;
- require precise gripper component collision for the first customer demo;
- tune all speeds before one full native task run exists.