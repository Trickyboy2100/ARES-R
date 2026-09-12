# ARES-R Skill Library S1 Implementation Plan

Status: proposed next iteration only. S1 is not implemented by this commit.

## Goal and starting point

S1 should establish contracts, a revisioned semantic workspace, registry/schema export and a deterministic mock runtime for the 14 Tier-A definitions. It must not alter existing JAKA, AMR, Epic, gripper or cuRobo execution behavior, and must not change WorldModel W0–W3 semantics.

Suggested starting branch after this S0 documentation commit:

```bash
git switch -c feat/skill-library-s1-contracts
```

S1 exit state: Tier-A contracts are `MOCK_VERIFIED`; no skill is `SIM_VERIFIED`, `REAL_DRYRUN` or `REAL_COMMISSIONED` merely because S1 passes.

## Work packages

### S1.1 Contract types and outcomes — fully offline

Create:

```text
src/ares_r/skills/
├── __init__.py
├── contracts.py          # SkillDefinition, parameter/resource requirements
├── invocation.py         # SkillInvocation
├── plan.py               # SkillPlan and planned steps
├── result.py             # status/failure/evidence/effects
├── context.py            # scoped dependency protocols
├── maturity.py           # maturity enum and evidence key
├── failures.py           # closed failure families/codes
└── serialization.py      # canonical JSON and digest helpers
```

Tests:

```text
tests/skills/test_contracts.py
tests/skills/test_invocation.py
tests/skills/test_plan_result_serialization.py
tests/skills/test_maturity.py
```

Acceptance:

- frozen/immutable records, explicit UTC and monotonic timestamps where relevant;
- closed schemas reject unknown fields, non-finite values and implicit units;
- normal failures serialize through `SkillResult`, not exceptions;
- canonical serialization is deterministic and digest-covered;
- plan includes workspace revision, snapshot ID/digest and resource-state digests when applicable.

### S1.2 LabWorkspace / ResourceGraph — fully offline

Create:

```text
src/ares_r/workspace/
├── __init__.py
├── resource.py           # Resource and ResourceType
├── affordance.py         # typed interaction affordances
├── relations.py          # typed semantic edges/predicates
├── occupancy.py          # holder/slot/port occupancy
├── geometry_binding.py   # resource_id <-> object_id/frame binding
├── resource_graph.py     # immutable revision/query API
├── transaction.py        # compare-and-swap semantic effects
├── resolver.py           # symbolic ref -> semantic/geometric resolution
└── fixtures.py           # test/demo workspace loading only
```

Add configuration examples (data only, explicitly uncommissioned):

```text
config/workspace/lab_workspace.example.yaml
config/workspace/affordances.example.yaml
```

Tests:

```text
tests/workspace/test_resource_graph.py
tests/workspace/test_occupancy.py
tests/workspace/test_transactions.py
tests/workspace/test_geometry_binding.py
tests/workspace/test_resolver.py
```

Acceptance:

- stable IDs and acyclic containment;
- unique occupancy and compatibility enforcement;
- explicit TRUE/FALSE/UNKNOWN predicates;
- stale revision transactions rejected;
- `sample_A`, `balance.pan`, `tray_1.slot_3` resolve deterministically;
- resolver requires a valid geometry binding for motion but never mutates WorldModel;
- WorldModel and LabWorkspace remain separate modules and authorities.

### S1.3 Capability provider contracts — fully offline

Create:

```text
src/ares_r/skills/providers/
├── __init__.py
├── base.py               # CapabilityProvider protocol and typed outcome
├── registry.py           # mode/version/capability resolution
└── mock.py               # deterministic virtual-time provider
```

Tests:

```text
tests/skills/providers/test_registry.py
tests/skills/providers/test_mock_provider.py
tests/skills/providers/test_fault_injection.py
```

Acceptance: the registry resolves capabilities, never semantic skill subclasses; mock provider supports scripted success/failure/hang/cancel and emits deterministic evidence. Define interfaces only for required Tier-A capabilities. Do not wrap real adapters yet.

### S1.4 Registry, policy and safe schema export — fully offline

Create:

```text
src/ares_r/skills/registry.py
src/ares_r/skills/schema_export.py
src/ares_r/skills/policy.py
src/ares_r/skills/catalog/tier_a.py
tests/skills/test_registry.py
tests/skills/test_schema_export.py
tests/skills/test_llm_policy.py
```

Acceptance:

- registry key is `(skill_id, implementation_version)`;
- catalog definitions correspond to `docs/SKILL_CATALOG.md` Tier-A;
- JSON/function schemas are closed, typed and resource-oriented;
- L0, raw coordinates/joints, safety reset and arbitrary device commands cannot be exported;
- maturity, mode and safety class filters are enforced after schema validation;
- LLM call creates an invocation proposal only, never direct execution.

### S1.5 Locking and runtime lifecycle — fully offline

Create:

```text
src/ares_r/skills/runtime.py
src/ares_r/skills/locks.py
src/ares_r/skills/cancellation.py
src/ares_r/skills/recovery.py
src/ares_r/skills/events.py
tests/skills/test_runtime_lifecycle.py
tests/skills/test_lock_ordering.py
tests/skills/test_cancellation_timeout.py
tests/skills/test_recovery_policy.py
tests/skills/test_replay.py
```

Acceptance:

- explicit PENDING/PLANNING/READY/RUNNING/VERIFYING/terminal transitions;
- globally ordered resource/zone locks and contention timeout;
- cooperative provider cancellation with bounded halt;
- retry is closed-code-specific and bounded; safety failures never auto-retry;
- replay gives the same terminal result/event digest;
- infrastructure exceptions are caught, safe-cancelled and translated to `INTERNAL_ERROR`.

### S1.6 WorldModel and ExecutionLease bridge — fully offline with existing fixtures

Create, without editing W0–W3 contracts:

```text
src/ares_r/skills/bridges/
├── __init__.py
├── world_model.py        # read/freeze/require-active adapter
└── execution_lease.py    # protocol seam; no new real executor
tests/skills/bridges/test_world_model_bridge.py
tests/skills/bridges/test_lease_bridge.py
```

Acceptance:

- motion planning refuses absent/stale/mismatched snapshots;
- plans carry `scene_snapshot_id` and `planning_context_digest`;
- any arm/base/attachment invalidation prevents stale plan execution;
- leases bind invocation, plan, arm/resources and deadline and are single-use;
- no call path reaches current real motion adapters in tests.

If ExecutionLease is not yet present in the codebase, define its protocol and mock in S1; implement production lease behavior only in the appropriate later world/execution milestone.

### S1.7 Tier-A semantic skeletons and mock flows — fully offline

Create:

```text
src/ares_r/skills/catalog/
├── observation.py
├── navigation.py
├── manipulation.py
├── device.py
└── laboratory.py
tests/skills/catalog/test_tier_a_contracts.py
tests/skills/scenarios/test_mock_pick_place.py
tests/skills/scenarios/test_mock_device_measure.py
tests/skills/scenarios/test_mock_failures.py
```

Implement contract-complete mock orchestration for the 14 Tier-A skills only. Keep provider calls minimal and semantic. Every flow must show precondition → plan → execute → verify → transactional effect/failure. No direct controller import is allowed under `src/ares_r/skills/catalog/`.

### S1.8 Terminal observability — fully offline

Add read-only commands by minimally extending the existing terminal command registration, without altering motion commands:

```text
skill list [--layer L1|L2|L3] [--exposed]
skill show <skill_id>
skill schema <skill_id>
skill validate <skill_id> '<json>'
workspace status
workspace show <resource_id>
workspace resolve <resource_id>
skill mock run <skill_id> '<json>'
```

Prefer new implementation files:

```text
src/ares_r/terminal_commands/skills.py
src/ares_r/terminal_commands/workspace.py
tests/test_terminal_skills.py
```

If the current terminal has no command-module mechanism, make only the smallest registration hook in `src/ares_r/terminal.py`. `skill mock run` must hard-bind mock mode and display invocation/plan/snapshot/workspace IDs, lifecycle, locks, evidence, effects and failure code.

## Offline test matrix

| Test family | Required in S1 |
|---|---|
| Contract/schema | every Tier-A definition, good/bad fixtures |
| Preconditions | TRUE/FALSE/UNKNOWN and stale evidence |
| State transitions | all legal transitions; illegal transition rejection |
| Fault injection | every provider boundary and verification gate |
| Cancellation | before planning, queued, RUNNING, VERIFYING |
| Timeout | lock, plan, execution, verification |
| Replay | canonical event stream/result digest |
| World binding | snapshot/digest/runtime/calibration mismatch |
| Workspace binding | revision/occupancy/resource-state mismatch |
| Lease | mismatch, expiry, consumption, conflicting arm/base movement |
| Parallel/dual-arm | disjoint success; shared/center zone rejection |
| LLM policy | allowlisted semantic calls; all raw controls rejected |

Recommended command gate:

```bash
pytest -q tests/skills tests/workspace tests/test_terminal_skills.py
git diff --check
```

## Explicitly deferred to S2+

### Can be done later without site access

- `IsaacCapabilityProvider` using reviewed legacy ARES simulation seams;
- simulated geometry bindings and affordance fixtures;
- MTC-like alternative plan-step visualization;
- L4 protocol engine and fault-injected mock pick/measure/clean protocols;
- richer quantity/uncertainty and sample-lineage domain model.

### Requires on-site evidence

- actual `T_body_camera`, tool/TCP, robot model and calibration revisions;
- real Epic observation quality/provenance and robot self-filter validation;
- station docking/manipulation frames and zone measurements;
- holder/slot/port geometry and occupancy-verifier validation;
- MiniCobo + gripper + carried-object collision-model validation;
- JAKA/AMR/gripper/device provider cancellation and timeout behavior;
- force/contact/grasp/release/seating/interlock verification thresholds;
- device command semantics, calibration, hazards and recovery;
- supervised `REAL_DRYRUN`, followed by revision-scoped commissioning evidence.

Nothing in S1 may manufacture these values or promote maturity based on mock success.

## Review gates

1. **Contract gate:** definitions, failures and lifecycle reviewed before implementations.
2. **Boundary gate:** no import from real adapter/controller modules in semantic skills.
3. **Truth gate:** semantic effects commit only after verification; uncertainty remains explicit.
4. **Safety gate:** raw APIs absent from schema export; locks/leases required for motion.
5. **Regression gate:** existing WorldModel tests and existing terminal/runtime tests remain unchanged and passing.
6. **Scope gate:** S1 stops at MOCK_VERIFIED contracts; provider commissioning is a separate change set.

## Proposed commit sequence

1. `feat(skills): add immutable skill contracts and outcomes`
2. `feat(workspace): add revisioned resource graph and affordances`
3. `feat(skills): add capability provider and safe registry`
4. `feat(skills): add lifecycle locks cancellation and replay`
5. `feat(skills): bridge snapshots and mock execution leases`
6. `feat(skills): specify and mock-verify tier-a catalog`
7. `feat(terminal): expose read-only skill and workspace inspection`

Each commit should be reviewable and keep all preceding tests green. Do not combine real-provider wiring or hardware commissioning with S1.
