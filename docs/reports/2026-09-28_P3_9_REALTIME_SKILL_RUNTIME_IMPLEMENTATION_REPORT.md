# P3.9 — Realtime Skill/Task Runtime implementation report

Date: 2026-09-28

Mode: additive implementation, frozen replay and fault injection only. No AMR, arm or gripper motion; no speed/force/continuous-stream change.

Baseline / rollback anchor: `1b548882065dbec5a524c141cbf7141af7f1d9cc`.

## Result

```text
SKILL_RUNTIME_CORE_READY = YES
SKILL_REGISTRY_READY = YES
REAL_PROVIDER_VERTICAL_SLICE_READY = YES (delegating adapter; not physically executed)
OBSERVATION_V2_PARALLEL_READY = YES (interface + deterministic concurrency tests; live p50 modeled)
PERSISTENT_CAPTURE_OWNED_BY_RUNTIME = YES (lifecycle owner; disabled by default)
PERSISTENT_PLANNER_OWNED_BY_RUNTIME = YES (existing planner service client reused)
FAST_FALLBACK_PLANNER_READY = YES
ASYNC_EVIDENCE_READY = YES
DECLARATIVE_SCHEME_READY = YES
NATIVE_PIPELINED_SCHEME_RUNNER_READY = YES
TRAY_TO_GROOVE_REPLAY_PASS = YES
FAULT_INJECTION_PASS = YES
PHASE1_MODELED_TOTAL_CYCLE_S = 395.0
FULL_DEMO_RUNTIME_PACKAGE_READY = YES
READY_FOR_UNCHANGED_SPEED_FULL_SUPERVISED_CYCLE = YES_TO_REQUEST_SEPARATE_AUTHORIZATION

LEGACY_DEMO_UNCHANGED = YES
ROLLBACK_PATH_READY = YES
LEGACY_FIRST_PICK_FROZEN_REPLAY_PASS = YES
TASK_RUNTIME_DISABLE_FALLBACK_PASS = YES
ART_LOW_CODE_READY = YES
WEBUI_TASK_STUDIO_READY = YES
SCHEME_DRAFT_VERSIONING_READY = YES
ORIGINAL_SCHEME_UNCHANGED = YES
```

`task run` and package physical execution remain locked. “Ready” means the implementation/replay gates allow the next separately authorized unchanged-speed supervised cycle; it does not claim that P3.9 executed one.

## Compatibility gate

The two golden fallback files were not edited:

```text
demos/right_arm_epic_pick_lift_v1/demo.json
  sha256 25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056

scripts/run_first_pick_demo.py
  sha256 e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0
```

The new runtime is disabled by default in `config/task_runtime.json`, has its own `worklog/runtime/p39/` state tree, and does not read/write DemoRegistry state. Disabling it leaves the golden Demo Library/entrypoint unchanged. No old config key was removed or renamed.

## Implemented vertical slice

### Runtime spine

`src/ares_r/skills/` provides:

- immutable `SkillDefinition`, `SkillInvocation`, `SkillPlan`, `SkillResult`;
- typed `SkillStatus` and failure codes;
- schema validation;
- `SkillRegistry` and the 16 required primitive/composite definitions;
- ordered resource locks;
- cooperative cancellation;
- monotonic crash-readable event stream;
- bounded `AsyncEvidenceWriter` with backpressure/failure reporting;
- `SkillRuntime` prepare/bind/execute lifecycle.

`SkillPlan` binds provider plan, locks, live revision context, expiry and planner profile. A scene/start/base/attachment mismatch produces `BINDING_MISMATCH` and `PLAN_INVALIDATED`; it is never silently rebound.

### Real provider

`RealCapabilityProvider` is an additive adapter over injected canonical ARES-R services:

```text
ObservationTransactionV2
existing base bridge/observer
SceneAwareMotion/cuRobo
current contact policy
current gripper adapter
Safety authorization
current native trajectory executor
current verification service
```

It does not reproduce scene reconstruction, planning, ServoJ, gripper, AMR or contact algorithms. Scene/detection Skills share one cached Observation V2 result per profile rather than triggering two acquisitions.

### Observation V2

`ObservationTransactionV2` performs:

```text
robot-before
→ ThreadPool(5700 detect || 5000 capture/decode)
→ robot-after
→ joint stability + capture skew checks
→ scene commit
→ atomic observation_v2.json
```

It preserves detection ID, pointcloud SHA, scene ID/digest, calibration/tool revisions and before/after robot states. Robot motion or sensor-window skew fails closed.

Frozen evidence model:

| Metric | V1 | V2 Phase-1 model |
|---|---:|---:|
| Observation p50 | 12.2975 s measured | 9.9 s estimated |
| Target | — | ≤10.5 s |

A live nonmoving benchmark remains part of P3.9B commissioning; P3.9 does not relabel the estimate as measured.

### Planner policy and persistent ownership

One provider interface selects:

```text
FAST: 4 IK / 2 trajectory seeds, one attempt, graph off
FALLBACK: 8 / 8, graph on
```

Fallback occurs only after FAST raises or returns invalid through the canonical service. Dense validation remains provider-authoritative. `PersistentServiceOwner` reuses the existing Pixel Pro socket worker and `planner_service_client`; it does not launch services while `task_runtime.enabled=false`.

### Declarative Scheme and native runner

`schemes/commissioned/tray_to_groove_v1.json` contains 18 data-driven nodes from pickup base through result verification. It contains semantic targets/policies and SI parameters, never joints or trajectories.

Each node supports:

- `depends_on` execution dependencies;
- `prepare_after` plan-ahead dependencies;
- `$node.output` bindings;
- timeout, recovery action and resource locks.

`SchemeRunner` schedules eligible prepare futures while the current node executes, then verifies immutable binding before execution. It emits task/stage/lock/plan/fault events, flushes evidence on success/fault, and revokes pending work on Stop.

Normal replay scene policy is one pickup scene plus one placement scene; no post-grasp full scan is inserted on the normal path.

## Low-code Task Studio

ART uses the same `SceneAwareDispatcher` backend as WebUI:

```text
skill list
skill show SKILL_ID
scheme list
scheme show SCHEME_ID
scheme clone SOURCE NEW_ID
scheme validate SCHEME_ID
scheme preview SCHEME_ID
scheme save-draft SCHEME_ID
task list
task show TASK_ID
task prepare TASK_ID
task preview TASK_ID
task replay TASK_ID
task status [RUN_ID]
task stop [RUN_ID]
```

WebUI now contains a real Task Studio rather than a status-only panel:

- Skill Palette from `SkillRegistry`;
- Scheme Builder add/remove/reorder;
- schema-derived parameter inputs;
- edit `depends_on` / `prepare_after`;
- output binding syntax `$node.output`;
- timeout, recovery and resource-lock editing;
- Validate, Preview DAG, Save Draft, Compile/Prepare and Replay;
- Run Monitor with current Skill, next/prepared stage, planner mode, scene epoch, cycle timer and Stop.

The UI is a client. `ThreadingHTTPServer` routes to one cached TaskStudio backend; the runner owns progression.

### Required no-Python acceptance demonstration

`scripts/p39_low_code_acceptance.py` performed:

1. cloned `tray_to_groove_v1` to `tray_to_groove_lowcode_demo_20260928`;
2. changed contact standoff from 0.050 m to 0.045 m;
3. inserted `observe.verify_predicate` before transfer/base motion;
4. rewired the place-base dependency;
5. saved a versioned draft;
6. validated a 19-node DAG;
7. replayed successfully;
8. verified the source Scheme digest remained unchanged.

Evidence: `worklog/evidence/2026-09-28-p3-9/low_code_acceptance.json`.

## Replay and fault injection

The full 18-node reference Scheme replay passed. Deterministic injected cases all passed:

| Case | Expected result |
|---|---|
| FAST planner failure | use versioned FALLBACK |
| stale scene | binding invalidation |
| start-state mismatch | binding invalidation |
| base revision change | binding invalidation |
| attachment revision change | binding invalidation |
| gripper verification failure | typed `GRASP_NOT_VERIFIED`, stop |
| Stop during PREPARING | cancelled, no execute |
| Stop during EXECUTING | cancelled/provider stop |
| evidence queue failure | typed backpressure/write failure |
| persistent service restart | explicit fallback, no silent success |

Evidence: `worklog/evidence/2026-09-28-p3-9/replay_acceptance.json`.

## Immutable runtime package

`worklog/evidence/2026-09-28-p3-9/TRAY_TO_GROOVE_RUNTIME_PACKAGE.json` binds:

- Scheme body/version;
- every Skill version;
- provider revision;
- task parameters;
- FAST/FALLBACK profiles;
- pickup/placement scene lifecycle;
- `CONTACT_BYPASS_V1`;
- unchanged commissioned speed policy;
- authorization requirement;
- Phase-1 performance model.

Package digest: `sha256:a767135a29799c236bc2f534fd4645f31e511984e87119e718372d479bb4ccc1`.

## Phase-1 performance model

| Metric | Current | P3.9 model |
|---|---:|---:|
| Total cycle | 606 s | **395 s** |
| Process spawns | 20 for current pick | 5 modeled full cycle |
| Realtime file handoffs | ≥18 for current pick | 4 modeled full cycle |
| Observation p50 | 12.30 s | 9.9 s modeled |
| Persistent FAST request | — | 14.78 s retained evidence |
| Prepared-next replay hit rate | — | 1.0 |
| Async evidence hidden | 0 | 12 s modeled |

`395 <= 420`; the target is met without changing physical speed. The value remains a model until P3.9B runs one complete unchanged-speed supervised cycle.

## Tests and stop point

Site Python 3.8 full suite:

```text
531 tests OK, skipped=1
```

Additional acceptance scripts passed on `.32`. No physical adapter was opened by the replay scripts. P3.9 stops here: no full physical cycle, force control, speed tuning or continuous Servo stream was started.
