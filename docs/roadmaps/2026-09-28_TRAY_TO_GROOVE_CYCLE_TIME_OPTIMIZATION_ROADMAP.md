# Tray→Groove cycle-time optimization roadmap

Date: 2026-09-28

Source: P3.8E audit. This document is a plan, not authorization to tune or move hardware.

## Baseline

```text
functional first pick: PASS
native full-cycle runner: ABSENT
full physical pick-place cycle time: UNKNOWN
modeled baseline: 606 s (580–640)
measured native-ready→100 mm HOLD: 400.25 s
measured motion inside that window: 147.74 s
measured non-motion inside that window: 252.52 s
```

## Phase 1 — low-risk deployment continuity

Target: ≤420 s modeled/first supervised full cycle without changing robot speed, acceleration, tracking thresholds, collision gates or AMR completion truthfulness.

Deliverables:

1. Native event-driven Scheme runner owns the full state machine; ART/WebUI are clients.
2. Pixel Pro and cuRobo services remain alive across the cycle.
3. `ObservationTransactionV2` runs 5700 and 5000 concurrently and commits only after stationary before/after validation.
4. FAST planner uses persistent `4_2_no_cuda_graph`, one solve and mandatory dense validation; 8/8 graph-enabled path is fallback only.
5. Next bounded stage may prepare during execution, but its manifest binds scene/start/tool/attachment revisions and is discarded on mismatch.
6. Separate ServoJ sessions remain; software handoff begins immediately after the required event.
7. Realtime logging is compact; large hashes/pretty JSON/screenshots/reports use an async writer.
8. UI shows current/next stage and cycle timer, but never gates progression.

Exit gates:

- frozen success/failure replay matches current behavior;
- observation p50 ≤10.5 s;
- persistent CLEAR request p50 ≤15 s and no per-request warmup solve;
- exactly one pickup scene and one placement scene on normal full path, excluding fallback;
- no conversational handoff inside an authorized Scheme;
- Stop revokes active and speculative leases;
- full tests and fault injection pass;
- one supervised full cycle ≤420 s with unchanged motion profiles.

Estimated saving: 186–246 s from current modeled cycle. Risk: LOW/MEDIUM. Effort: L.

## Phase 2 — pipelined motion and force-assisted verification

Target: ≤290 s, with visibly shorter stops.

Prerequisites: Phase 1 stable; exact force sensor/model/frame/zero/sample-rate commissioned.

Deliverables:

1. `FORCE_MONITOR_V1` is read-only, timestamped with Servo feedback and fails closed.
2. Force-first grasp/release verification; Pixel Pro scene delta remains fallback.
3. Supervised stage profiles: `FREE_SPACE_FAST`, `CONTACT_FORCE_GUARDED`, `VERTICAL_LIFT`, `TRANSFER_WITH_OBJECT`.
4. Commission contact/lift retiming from measured tracking/force data; no global speed changes.
5. Prepare contact/lift/place segments in parallel where binding permits.
6. Preserve distinct ServoJ segments initially; remove all non-required idle. Evaluate one stream with hold/event markers only after separate-session acceptance.
7. Warm place services during visibility-clear and AMR travel.

Exit gates:

- force axes/frame and empty/loaded baselines proven;
- contact abort latency and fallback tested;
- every stage tracking p95/max stays inside its versioned profile;
- no scene/trajectory reuse after base, tool, attachment or scene revision change;
- normal full cycle ≤290 s; vision fallback remains successful.

Estimated additional saving: 70–150 s. Risk: MEDIUM. Effort: L.

## Phase 3 — optional streaming scene/data plane

Target: ≤230 s only if Phase 2 cannot meet the customer continuity target.

Deliverables:

1. In-memory pointcloud array and digest handoff; disk is asynchronous evidence, not IPC.
2. In-memory planner request/result path and batched goalset/yaw candidates.
3. Incremental/streaming scene updates with immutable epoch barriers at motion-critical boundaries.
4. Optional cycle-long ServoJ stream with explicit hold/gripper/force event markers and proven abort semantics.
5. UI pointcloud serialization/render cadence fully separated from control cadence.

Exit gates:

- deterministic scene digest and replay equivalence with file path;
- no stale world after base/external scene change;
- bounded memory/backpressure behavior;
- Stop/E-stop/controller fault behavior unchanged;
- normal full cycle ≤230 s.

Risk: MEDIUM/HIGH. Effort: L. This phase is optional.

## Phase 4 — production hardening (after throughput target)

- exact gripper component/contact collision commissioning;
- force-sensor/tool-stack geometry closure;
- repeated-cycle reliability and recovery matrix;
- p50/p95 KPI telemetry over at least 30 cycles;
- customer demo packaging and operator runbook.

## Measurement contract

Every implementation phase must publish one monotonic event stream containing:

```text
task/stage transition
resource lock acquire/release
scene/trajectory/attachment revision
device request/ack/completion
planner update/solve/validate timings
Servo enable/first sample/last sample/disable
gripper and force events
async evidence queue depth
fault/abort/invalidation reason
```

Report p50/p95 and waterfall without mixing `MEASURED`, `REPLAY_BENCHMARKED`, `ESTIMATED` and `UNKNOWN`.

## First implementation recommendation

Start with Phase 1 as one vertical slice:

```text
native runner
→ persistent capture/planner ownership
→ concurrent atomic observation
→ async evidence
→ frozen replay/fault injection
→ one unchanged-speed supervised full cycle
```

Do not begin with stage speed increases. The measured 252.52 s non-motion window is the highest-return and lowest-physical-risk target.
