# ARES-R Skill Library Architecture

Status: S0 design specification. Target system: mobile, dual-arm laboratory assistant. All skills start at `SPECIFIED`; this document authorizes no hardware execution.

## 1. Architectural decision

ARES-R shall have three separate planes:

```text
Protocol / planner / approved LLM tools
                  |
           SkillRegistry
                  |
      Skill runtime + policy gates
       /          |            \
LabWorkspace   WorldModel    CapabilityProviders
(semantics)    (geometry)    (mock/sim/real I/O)
       \          |            /
        SkillPlan + ExecutionLease
```

The rule is strict:

```text
Perception -> ObservationEpoch -> WorldModel -> freeze SceneSnapshot -> planner
```

No `Epic -> cuRobo` shortcut is valid. A trajectory or manipulation plan must bind `scene_snapshot_id` and `planning_context_digest`.

## 2. Bounded contexts

### 2.1 WorldModel: geometric fact authority

Existing W0–W3 semantics remain unchanged. WorldModel owns SI/SE(3) geometry and time-coherent evidence:

- `RobotState`, including joints/TCP/grippers/base pose;
- `ObservationEpoch`, point-cloud identity/hash and calibration revisions;
- `EnvironmentRevision` and collision objects;
- attached collision geometry;
- safety constraints;
- immutable `SceneSnapshot`, lifecycle, digests and invalidation.

It answers “where and with what geometric evidence?” It does not decide that an object is a sample, that a slot is occupied, or that a balance is available.

### 2.2 LabWorkspace / ResourceGraph: semantic fact authority

The new semantic layer owns:

```text
LabWorkspace
  map_id / workspace_revision
  stations[]
    docking_pose_ref
    manipulation_frame_ref
    zones: shared | private
    devices[]
      holders[] -> slots[] / ports[]
  resources[]
    Station | Device | Container | Sample | Tool
    Consumable | Fixture | Holder | Slot | Port | Zone
  relations[]
  predicates[]
  occupancy[]
```

Every resource has immutable `resource_id`, type, human label, parent, capabilities, affordances, state revision and optional `object_id`. Relationships include `contains`, `mounted_at`, `occupies`, `located_at`, `loaded_in`, `connected_to`, `contains_sample`, `compatible_with`, `reserved_by` and `requires_tool`.

Semantic state is versioned and transactional. Examples:

```text
contains_sample(vial_7, sample_A)
located_at(vial_7, tray_1.slot_3)
occupancy(balance.pan) = EMPTY
door_state(furnace_1.door) = CLOSED
device_state(balance) = READY
```

### 2.3 Joining the two planes

`resource_id` is stable semantic identity. `object_id` is stable geometry identity. A versioned `GeometryBinding` joins them:

```text
GeometryBinding(
  resource_id="tray_1.slot_3",
  object_id="OBJ_slot_3",
  frame_ref="station_A/manipulation",
  geometry_revision="...",
  calibration_revision="..."
)
```

Resolution is one-way for a planning cycle:

1. resolve symbolic parameters (`sample_A`, `balance.pan`) in a fixed workspace revision;
2. check semantic predicates, ownership and occupancy;
3. resolve resource affordance frames through bindings;
4. require a compatible active `SceneSnapshot` or acquire a new observation;
5. compile the resolved geometry into an arm-specific planning scene;
6. put all revisions and digests in `SkillPlan`.

Updating WorldModel does not silently update inventory. Successful verification commits declared semantic effects in a workspace transaction. If physical effect is uncertain, mark the relevant predicate `UNKNOWN` and invalidate/reobserve; never guess.

## 3. Resource and affordance model

An affordance describes how a generic skill may interact with a resource:

```yaml
resource_id: furnace_1.door
type: Fixture
capabilities: [openable]
affordances:
  open:
    interaction_frame: furnace_1/door_handle
    handle_region: OBJ_furnace_handle
    articulation: {kind: hinge, axis: [0, 0, 1], limits_rad: [0, 1.75]}
    grasp: {kind: wrap, allowed_arms: [right]}
    constraints: {max_force_n: 25, keep_upright: false}
    success_predicate: door_angle_rad >= 1.40
```

The same `open_door(resource)` applies to:

1. furnace door: horizontal hinge, heat-zone invariant and cool-state precondition;
2. cabinet door: vertical hinge and bar-handle grasp;
3. microwave door: side hinge plus latch-release force profile;
4. refrigerator door: vertical hinge, larger swept volume and two-arm exclusion zone;
5. toaster-oven door: lower hinge and downward trajectory;
6. instrument safety door: interlock predicate and device-idle requirement.

Similarly, `press(control)`, `turn(control)`, `load_device(container, port)` and `open_drawer(resource)` are generic. A new device should normally add Resource/Affordance data and a device capability provider, not a new mechanically identical skill.

## 4. Skill contract

### 4.1 SkillDefinition

```text
skill_id                  stable namespaced ID, e.g. manipulation.pick
schema_version            contract schema integer
implementation_version    semantic implementation version
description
layer/category            L0..L4 and category
parameter_schema          closed typed schema; SI units internally
required_capabilities     abstract capabilities, not concrete drivers
required_resources        symbolic selectors and cardinality
preconditions             named predicates with evidence requirements
invariants                monitored throughout RUNNING
expected_effects          candidate semantic/geometric postconditions
observation_requirements  modality, max age, confidence, calibration
resource_locks            shared/exclusive resource locks
zone_locks                swept/workspace zones
timeout_policy            planning, queue, execution, verification limits
failure_codes             closed codes owned by the definition
planner_exposure          INTERNAL | PLANNER | LLM
safety_class              S0_INFO | S1_REVERSIBLE | S2_MOTION | S3_PROCESS
maturity                  SPECIFIED..REAL_COMMISSIONED
```

Parameter schemas use logical resource references and explicit typed quantities. Free-form xyz/joints, implicit units, unknown keys, NaN/Inf and unbounded strings are invalid at the planner boundary.

### 4.2 Runtime records

**SkillInvocation** is immutable intent:

```text
invocation_id, skill_id, skill_version, parameters
requested_by, requested_at, idempotency_key
workspace_revision, requested_maturity_ceiling
approval_context, parent_plan_id, trace_id
```

**SkillPlan** is an immutable, inspectable proposal:

```text
plan_id, invocation_id, planner/version, created/expires
resolved_resources and affordances
precondition_evidence
steps[] with providers and verification gates
scene_snapshot_id, planning_context_digest
workspace_revision, resource_state_digests
robot/tool/attachment revisions
required locks and zones
rollback/compensation proposal
risk summary, operator confirmations
```

Planning has no physical effects. A plan becomes executable only after revalidation and lease acquisition.

**SkillResult** represents normal outcomes without exceptions:

```text
invocation_id, plan_id, status, failure_code, message
started_at, completed_at, attempt_count
observations/evidence/artifacts
verified_effects, uncertain_effects
world/workspace revisions before/after
provider_results, deterministic event-log digest
```

Statuses:

```text
ACCEPTED -> PLANNING -> READY -> RUNNING -> VERIFYING
                                  |           |
                                  v           v
                           CANCELLING     SUCCEEDED
                                  |       FAILED
                                  v       TIMED_OUT
                              CANCELLED   REJECTED
```

`REJECTED` means schema/policy/precondition rejection before motion. `FAILED` is an expected attempted-operation failure. `CANCELLED`, `TIMED_OUT` and `SUCCEEDED` are terminal. Python exceptions are reserved for programmer errors, corrupt contracts or infrastructure faults and are translated at the runtime boundary to `INTERNAL_ERROR` plus safe halt.

**SkillContext** contains only scoped dependencies:

```text
world_model (read/freeze/invalidate authority)
lab_workspace (revisioned query/transaction authority)
capability_registry
policy_engine and approval token
lock_manager / zone manager
clock, cancellation_token, event_log, artifact_store
execution_lease_manager
mode = MOCK | ISAAC_SIM | REAL_DRYRUN | REAL
```

No skill receives an unscoped controller object.

**SkillRegistry** stores immutable definitions and factories keyed by `(skill_id, version)`, checks compatibility, filters by maturity/policy, resolves providers and exports approved schemas. It refuses duplicate IDs, schema drift without version change, provider capability mismatch and LLM exposure of L0.

## 5. Lifecycle and effect discipline

Every executable skill follows:

```text
validate invocation
-> resolve resources at workspace revision
-> evaluate preconditions/evidence freshness
-> plan against frozen SceneSnapshot where motion is involved
-> acquire ordered resource + zone locks
-> obtain ExecutionLease
-> revalidate start state, snapshot and revisions
-> execute asynchronously with invariant monitoring
-> cancel/halt on violation or deadline
-> verify using independent evidence
-> atomically commit verified effects
-> release locks and emit deterministic result
```

Planning and execution are separate. Expected effects do not become facts merely because a command returned success. For `pick`, gripper command success is not grasp success; attachment is committed only after verification. For `place`, opening the gripper is not placement success; object location/occupancy must be observed or otherwise verified.

Scene invalidation remains governed by WorldModel. Arm/base motion, attach/detach, new observation, calibration change and timeout invalidate or stale the bound snapshot. A running skill must react according to its invariant policy; it may never silently rebind a trajectory to a new scene.

## 6. Capability-provider backend

One semantic skill uses capability interfaces:

```text
PickSkill
  requires: scene.observe, motion.plan_arm, motion.execute_trajectory,
            gripper.command, grasp.verify
                          |
              CapabilityRegistry.resolve(mode)
           /              |                 \
    MockProvider   IsaacCapabilityProvider   RealProvider
```

Provider contracts return typed provider results and publish evidence. Providers declare capability version, supported modes, safety/maturity ceiling, cancellation behavior and health. A `REAL` provider cannot raise a skill above its commissioned maturity.

- `MockCapabilityProvider`: deterministic fixtures, virtual clock and injectable failures.
- `IsaacCapabilityProvider`: future adapter around legacy ARES planning/gripper/scene knowledge; simulation observations must still enter WorldModel.
- `RealCapabilityProvider`: wraps existing ARES-R Epic/JAKA/gripper/AMR adapters and cuRobo pipeline without changing those drivers in S1.

Never create `MockPickSkill`, `IsaacPickSkill` and `RealPickSkill`. Backend-specific strategy choices may exist inside providers, while the semantic contract and verification criteria remain one definition.

## 7. Locks, dual-arm and safety

Locks are deterministic and ordered to avoid deadlock:

```text
workspace -> station -> zone -> device -> holder/slot -> object -> arm/tool
```

Lock modes are `SHARED_READ`, `EXCLUSIVE_STATE`, `EXCLUSIVE_MOTION`. A skill declares both named resources and swept zones. Dual-arm parallel execution is allowed only when provider capabilities support it, lock sets are disjoint, center-zone constraints are satisfied, and the same WorldModel revision covers both plans. Lock acquisition timeout is a normal `RESOURCE_BUSY` result.

Cancellation is cooperative but mandatory: stop accepting new waypoints, request provider halt, wait bounded time, escalate to the existing safety layer, mark effects uncertain, invalidate snapshot and release locks only after controlled resources are quiescent.

Retries must be failure-code-specific, bounded and safe. `OBJECT_NOT_FOUND` may trigger reobserve; `GRASP_NOT_VERIFIED` may retreat/reobserve/replan; `SAFETY_INVARIANT_VIOLATED` is never automatically retried. Compensation is not rollback: spilled liquid or moved hardware cannot be “undone” in software.

## 8. LLM/Qwen exposure

The LLM sees a generated, allowlisted subset of `SkillRegistry`, never provider/controller APIs. Eligible definitions must be L1–L3, `planner_exposure=LLM`, meet deployment maturity policy, use closed schemas, accept resource IDs rather than coordinates and have bounded safety policy.

Example generated function:

```json
{
  "name": "place",
  "description": "Place a held resource into a named holder or slot.",
  "parameters": {
    "type": "object",
    "additionalProperties": false,
    "required": ["object", "destination"],
    "properties": {
      "object": {"type": "string", "x-resource-types": ["Container", "Tool"]},
      "destination": {"type": "string", "x-resource-types": ["Holder", "Slot"]}
    }
  }
}
```

Tool calls are only proposals. The runtime resolves current IDs, validates policy/preconditions/maturity, creates a plan and requests required operator approval. The following are permanently excluded: ServoJ, raw joints/TCP, raw base velocity, safety reset, unrestricted device command, arbitrary shell/ROS calls and free-form provider selection.

## 9. Maturity model

Maturity belongs to `(skill_id, implementation_version, provider family, robot/tool/config revision)`, not just the name.

| Level | Required evidence |
|---|---|
| `SPECIFIED` | reviewed contract, closed failures and tests planned |
| `MOCK_VERIFIED` | contract/state/fault/cancel/timeout/replay tests pass deterministically |
| `SIM_VERIFIED` | representative Isaac scenarios pass with collision, attachment and randomized-state evidence |
| `REAL_DRYRUN` | real providers read/plan/preflight under supervision; effects disabled or motionless |
| `REAL_COMMISSIONED` | bounded real execution, verification, recovery and revision-specific evidence accepted |

Promotion is explicit and cannot skip levels. Simulation does not imply real readiness. Changing robot model, TCP/tool, calibration, critical affordance or provider major version invalidates or scopes prior evidence.

## 10. Testing architecture

Every skill family must have:

- contract/schema and unknown-field tests;
- precondition truth/false/unknown tests;
- planned state-transition and verified-effect tests;
- provider fault injection at every step;
- cancellation before/while/after provider activity;
- queue, planning, execution and verification timeouts;
- event replay yielding identical `SkillResult` and state digest;
- deterministic structured logging with trace/invocation/plan/snapshot IDs;
- stale WorldModel digest, workspace revision and ExecutionLease tests;
- lock contention, deadlock ordering and dual-arm zone-conflict tests.

Mock can reach `MOCK_VERIFIED` for all Tier-A contracts. Isaac-supported motion/manipulation may reach `SIM_VERIFIED` only after simulation assets and validators are integrated. Device chemistry that lacks a faithful simulator remains `MOCK_VERIFIED` until on-site commissioning.

## 11. Non-goals and invariants

- L4 protocols compose skills; they are not hardware commands or giant skills.
- L0 remains internal and cannot be planner/LLM exposed.
- ResourceGraph is not a collision scene; WorldModel is not sample inventory.
- Coordinate frames are implementation evidence, not the normal user API.
- Normal failure is data, not an exception.
- No provider may bypass SceneSnapshot/ExecutionLease for autonomous motion.
- No document, mock or simulation run may label a skill `REAL_COMMISSIONED`.

## Research basis

This synthesis follows the pinned evidence and source links in [SKILL_REFERENCE_AUDIT.md](research/SKILL_REFERENCE_AUDIT.md), especially PyLabRobot resource/backend separation, XDL typed semantic steps, MTC planning stages, BehaviorTree.CPP async lifecycle, mobile manipulation decomposition in HomeRobot/Stretch, Isaac ROS action boundaries, and RoboCasa affordance/success coverage.
