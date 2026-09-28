# CURRENT QUEUE — 2026-09-28

## Strategic convergence

The next two workstreams are now intentionally merged into one implementation program:

~~~text
A. cycle-time / realtime continuity
B. Skill packaging + Task/Scheme runtime
~~~

Do not optimize the old script-by-script flow and then rewrite it again into Skills.

Build one native Skill/Task runtime that removes orchestration latency while making new tasks composable.

## Read architecture

~~~text
docs/architecture/2026-09-28_REALTIME_SKILL_TASK_RUNTIME.md
~~~

## Active now

### P3.9 — Realtime Skill Runtime vertical slice

Execute:

~~~text
docs/work_orders/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_VERTICAL_SLICE.md
~~~

Current integration GitHub HEAD supplied by P3.8E completion:

~~~text
1b548882065dbec5a524c141cbf7141af7f1d9cc
~~~

Codex must verify current HEAD before coding because integration may have advanced.

## P3.9 implementation priorities

### Track 1 — realtime/throughput foundation

~~~text
native event-driven runner
persistent Pixel Pro + cuRobo services
ObservationTransactionV2: 5700 || 5000
FAST planner + FALLBACK
plan-ahead / PREPARING next stage
async evidence writer
no conversational handoff inside task
one pickup scene + one placement scene normal path
~~~

Phase-1 target from P3.8E:

~~~text
modeled total cycle <= 420 s
without changing physical motion speeds
~~~

### Track 2 — Skill / Task framework

Implement the minimum executable spine, not the whole catalog:

~~~text
SkillRegistry
SkillInvocation / SkillPlan / SkillResult
CapabilityProvider
resource locks
cancellation
event stream
declarative Scheme loader
native SchemeRunner
~~~

First real Skills wrap existing canonical services:

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

## Reference task

Tray→Groove is the first vertical-slice acceptance task:

~~~text
PICK_BASE
→ PICK_OBSERVATION
→ MOVE_PREGRASP
→ CONTACT_APPROACH
→ GRASP
→ VERIFY_GRASP
→ INITIAL_LIFT / ATTACH
→ VISIBILITY_CLEAR
→ PLACE_BASE
→ PLACE_OBSERVATION
→ MOVE_PREPLACE
→ PLACE_DESCEND
→ RELEASE
→ RETREAT
→ VERIFY_RESULT
~~~

Use the already successful contact/attachment semantics.

Do not redesign the grasp.

## Important implementation rule

Generalize contracts, not algorithms.

Skills must delegate to the current authoritative subsystems:

~~~text
free-space → SceneAwareMotionService
contact → current contact policy
scene → LocalScene / ObservationTransaction
planning → persistent cuRobo
execution → existing SafetyKernel/native sender
AMR → current base bridge/observer
gripper → current adapter
~~~

No second planner, no second scene system, no raw hardware calls in Scheme code.

## P3.9 stop point

P3.9 is implementation + replay/fault-injection only.

Do NOT:

- change physical speed profiles;
- start force-control implementation;
- execute the full hardware cycle without new approval;
- make continuous ServoJ/blending a dependency;
- build every Skill in SKILL_CATALOG.

Exit only when:

~~~text
NATIVE_PIPELINED_SCHEME_RUNNER_READY = YES
DECLARATIVE_SCHEME_READY = YES
TRAY_TO_GROOVE_REPLAY_PASS = YES
FAULT_INJECTION_PASS = YES
PHASE1_MODELED_TOTAL_CYCLE_S <= 420 or evidence-backed explanation
FULL_DEMO_RUNTIME_PACKAGE_READY = YES
READY_FOR_UNCHANGED_SPEED_FULL_SUPERVISED_CYCLE = YES
~~~

## After P3.9

Next expected sequence:

~~~text
P3.9B: one full supervised Tray→Groove cycle at unchanged commissioned speeds
→ measure real full-cycle waterfall

P3.10: force monitor + stage-specific speed commissioning
→ contact/lift/transfer acceleration
→ pointcloud verification fallback-only

P3.11 optional: continuous Servo stream / deeper pipelining / streaming scene
~~~

## Git

No force-push.
Small commits.
Keep unrelated dirty files isolated.
Report exact local/remote SHA at exit.