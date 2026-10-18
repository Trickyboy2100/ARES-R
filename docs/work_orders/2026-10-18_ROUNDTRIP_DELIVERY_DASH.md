# P0 Delivery Dash — Make the existing Tray→Groove roundtrip executable, fast and recoverable

Date: 2026-10-18
Status: actionable engineering work order; NOT physical execution authorization
Source branch: codex/audit-roundtrip-20261017 (audit archive, NOT a deployable release)

## 0. Deliverable and boundaries

Single objective: one button / one canonical task owner automatically completes:

GRASP fresh ID1 → pregrasp → controlled contact → close → verified hold → BODY +Z total 230mm → base route to PLACE → fresh ID3 → lower_middle offset → preland 40mm above slot → release → reverse base route to GRASP.

Use the reviewed 2026-10-16 V2 no-stow task semantics, with the latest on-site GRASP route revision (85cm lateral after an additional left 10cm relocation). Reconfirm route from effective site records; do not infer current robot location from Git history.

No artificial center/stow added, no concurrent arm+base motion, no new planner stack, no nvblox/ROS rewrite, no dual-arm motion, no uncommissioned force-control dependency.

Preserve the golden first-pick fallback and its original files. All physical commands still require current on-site supervision and a fresh authorization.

## 1. Required evidence to read

- docs/reports/2026-10-17_ROUNDTRIP_DEMO_FAILURE_AND_GATE_AUDIT.md
- docs/audits/2026-10-17_ROUNDTRIP_EXECUTION_REFERENCE.md
- docs/audits/2026-10-17_FAST_TIMEOUT_VERSION_SKEW_ADDENDUM.md
- docs/roadmaps/2026-10-17_ROUNDTRIP_1_2_DAY_DASH_PLAN.md
- worklog/audits/2026-10-17-roundtrip-offline/FUNCTION_INDEX.md
- worklog/audits/2026-10-17-roundtrip-offline/source_snapshot/

Snapshot is reference evidence only. DO NOT deploy this archive directly.

## P0 — Restore one reproducible runnable release BEFORE fixing algorithms

Actual GitHub integration HEAD at audit time: 7120c3f3... (2026-09-29). The October 16 runnable WebUI/backend/demo was split across local working copies and site dirty state.

Actions:

1. Capture effective `.32` and Mac workstation Git HEAD/status, service definitions, actual imported module paths and SHA256 of live scripts/configs, cuRobo worker/latency_solver, native sender binary, JAKA SDK, key geometry assets.
2. Compare two local code lines identified in version-skew addendum: offsets worker SHA6a706b... lacks solver_policy consumption, operations worker SHA3afcc9... implements single-pass FAST. Select the correct tested implementation by capability and replay, not filename/date alone.
3. Recover the complete October WebUI/backend/roundtrip launcher/demo/parameters/route/tests and freeze in a new non-destructive release-candidate branch/worktree. Never mix archived source snapshot with live code without diff review.
4. Build one immutable runtime manifest (code/config/service/binary hashes, imported module origin, schema versions, GPU state); show same build ID in ART/WebUI/health.
5. Preserve coworker dirty changes and raw site logs separately. Keep full raw pointcloud/site config evidence private if it contains sensitive environment details.
6. Freeze the original golden demo files unchanged; run all existing tests.

Exit: `ONE_CANONICAL_RUNNABLE_RELEASE=YES`, `EFFECTIVE_WORKER_VERIFIED=YES`, `GOLDEN_FALLBACK_UNCHANGED=YES`.

## P1 — Correct planning order (first few seconds, not after 160s)

Current path `scripts/run_grasp_place_roundtrip.py:Live._prepare_pick_once` runs pregrasp cuRobo BEFORE `build_first_pick_execution_package.py` validates final 55mm contact and initial 100mm lift.

Reorder the same existing Skills:

fresh ID1 / current joints → bounded NORMAL/FLIPPED orientation and multi-IK check for full 55mm contact and initial lift → discard unreachable grasp branch → top 1–2 pregrasp goals → persistent cuRobo free-space solve → create final package.

Precheck returns actual max position/orientation residual for the ENTIRE contact sequence, not only first failing knot. A no-grasp branch is NOT retried by running QUALITY.

Use current 230mm task goal and horizontal/yaw contract; avoid inventing old frozen joints or stale scene targets.

Exit: old-GRASP known-unreachable case rejects early; new-GRASP known-success data passes; neither consumes heavy cuRobo on a terminal contact IK invalidity.

## P2 — Real FAST/deadline/GPU closure

Inspect `planner_service_client.py:_call/plan`, `persistent_planner_service.py:serve`, `production_scene_worker.py:main`, `latency_solver.py`.

1. Prove via effective runtime log the actual planner entrypoint, seed counts, iterations, CUDA graph state, loaded module SHA and profile revision.
2. One active GPU solve owner; queue policy explicit. FAST should be warm single-pass when effective code supports it; QUALITY once only after a real solver failure that benefits from it.
3. Socket timeout alone is not cancellation. Add job_id, end-to-end deadline, cancellation request/ack and disposal of late results; no old GPU job can continue blocking retry or become executable.
4. Bound runtime cache/VRAM and profile count. OOM → `RESOURCE_EXHAUSTED`, not two identical QUALITY retries. Do not kill coworker GPU processes.
5. Start and warm the selected planner service before Demo activation. Avoid cold-per-segment startup.
6. Endpoint in collision, wrong scene, stale model or contact IK mismatch MUST bypass QUALITY and report the classified cause.
7. Output queue/init/warmup/solve/validate/serialize timings separately.

Acceptance: no orphan solve after FAST timeout; no leak/OOM under 10 frozen sequential calls; FAST metadata equals actual effective call; canonical CLEAR/AVOID/BLOCK replays pass.

Do not promise 4s total response if cold start+validation are longer. Separate backend solve budget from end-to-end stage budget.

## P3 — Fix attached-object WORLD identity

Existing gap: `SceneAwareMotionService.plan → LocalSceneService.ensure_fresh(active_arm)` does not pass `attachment`; `live_scene.build_live_planning_scene` also lacks that input.

Create a single attachment-aware observation/scene overlay:

1. one object_id/source_revision owns target before grasp;
2. when grasp verified, target becomes ATTACHED and linked to TCP/link6 collision;
3. robot + attached geometry jointly mask pointcloud/self observations and explicit world target primitive is disabled;
4. support/table/dock/other obstacles stay hard and remain visible;
5. on release, detach and reacquire/reconcile object world state.

The 200mm TCP neighborhood may be a candidate region but never blindly delete the full sphere. Produce before/after point and object lists plus false-removal audit around dock/support.

Re-run frozen 130mm-after-100mm case: no ghost target overlap at start, external objects unchanged, attached object still checked against genuine structures.

Exit: `ATTACHED_WORLD_IDENTITY_CLOSED=YES`, `NO_DUPLICATE_PAYLOAD_AS_WORLD=YES`, `EXTERNAL_SUPPORT_PRESERVED=YES`.

## P4 — Fix grasp verification timing

`grasp_verification.py:classify_scene_delta` flags added_fraction > 0.50 before evaluating removed fraction; 2026-10-16 pre-lift sample had added≈0.5204, removed≈0.6667 and gripper raw37 stable.

Replace pre-lift task claim with `CLOSED_HOLD_CANDIDATE`: stable nonzero gripper closing + allowed visual evidence, not a requirement that the object has already disappeared.

Use controlled initial lift / load-or-vision check to produce `GRASP_CONFIRMED`. Force sensor optional later, NOT a dependency for this delivery.

Use each genuine gripper sample timestamp, not a reconstructed common now. Keep one source of delay/radius/voxel parameters.

Provide an explicit one-time supervised experimental confirmation event only when the vision result is ambiguous; record which verification it substitutes and what remains mandatory. Never silently turn every failed grasp into PASS.

## P5 — Make short motion short, with the current approved ceilings first

`native_execution_package.py:package_native_preview → native_demo.py:resample_for_native` dilates the piecewise-linear joint polyline to satisfy 80ms discrete acceleration and exact geometry preservation.

Measured: 55mm contact source 26 points → native1439 points, 115.04s; initial 100mm lift ~72s. These are separate from planning time.

Deliver a timing audit showing source polyline length/curvature, native duration, limiting joint/speed/acceleration, terminal velocity and stretch ratio.

Replace unnecessary whole-trajectory dilation with a bounded trajectory retimer / smoothness-aware path when mathematically valid; if the joint geometry changes, generate a new trajectory hash and re-run collision, horizontal-orientation, acceleration and tracking validation.

Preserve existing approved 0.05rad/s contact, 0.20rad/s lift ceilings for first acceptance; do not silently change controller protection.

Targets (engineering goals, not current measurements): contact <=25–35s and initial100mm lift <=20–30s if physical revalidation supports them. If not feasible, report the actual limiting geometry/controller condition rather than lowering a gate until it passes.

## P6 — Unify state binding, settling and formal resume

`run_grasp_place_roundtrip.py:Live.pick_segment` permits a 0.2deg live-start difference while native sender checks 0.02deg. Last-sample `final feedback mismatch` occurred despite a subsequent precise arrival.

Create one versioned start-state tolerance contract enforced before packaging, and controlled `EXECUTING→SETTLING→ARRIVED` transitions; use actual telemetry and bounded terminal convergence, not timestamp refresh to mask state mismatch.

For inactive left arm, obtain minimal trustworthy joints/tool data through read-only provider with bounded retry; do not make one optional verbose SDK diagnostic cause automatic right task fault, and do not replace unknown left position with a fabricated value.

Implement `RESUME_FROM_VERIFIED_CHECKPOINT` in the canonical TaskRuntime / RoundtripLauncher. Do not create additional one-off recovery scripts.

Checkpoint examples: PREGRASP_ARRIVED, CLOSED_HOLD_CANDIDATE, GRASP_CONFIRMED, LIFT100_ARRIVED, HOLD230_ARRIVED, BASE_AT_PLACE, PRELAND_ARRIVED, RELEASE_CONFIRMED, BASE_RETURNED.

One job/one owner/one web state. Never replay an irreversible physical command just because a HTTP response or logger failed.

## P7 — Keep current customer demo flow and finish it

Read effective `config/grasp_place_base_route.json` and route revision from the October run. Latest communicated GRASP relative lateral change is 0.85m with unchanged PLACE; actual base current pose must be measured each run.

Release contract: ID3 → lower_middle slot offset in correct frame → TCP 40mm preland → release raw400, no descent, no right-arm stow on return. The user approved this particular drop/release mode; verify final placement as part of demo result.

The full script must autonomously progress through the existing 19 stages without Codex choosing intermediate waypoints or authoring recovery scripts during the run.

Base status needs one truthful completion observer; avoid duplicative extra stable loops that add seconds after canonical BaseMotionObserver has already established settled.

Do not introduce force, RL, streaming voxel map, new Skill framework or controller blending as dash prerequisites.

## P8 — Verification before next onsite run

Use the 10/16 real frozen scene/contact/gripper/lift/attachment/fault artifacts, NOT only historical September demos.

Mandatory no-motion tests:

- actual loaded source/binary/config SHA equals release manifest;
- before cuRobo, old unreachable contact fails early and updated reachable contact passes;
- FAST success/timeout/QUALITY failure/OOM tests with job cancellation and cleanup;
- 10 warm planner calls with bounded GPU memory;
- held payload scan no longer creates a duplicate world obstacle, actual support remains;
- pre-lift readback+scene-added example does not automatically claim grip failure;
- 0.03551deg seam is handled once at the correct boundary;
- terminal final settling has a distinct ARRIVED vs FAULT outcome;
- resume after LIFT100 executes only the remaining 130mm and later stages;
- fresh ID3/slot offset, base inverses, release + return 19-node replay;
- legacy golden first-pick continues to pass tests/sha.

Freeze package and produce one run sheet: stage, state owner, expected duration, expected GPU/CPU demand, fixed limits, Stop/fault behavior.

## P9 — 1–2 day on-site finish

All P0–P8 code fixes must be integrated and replayed OFFSITE BEFORE using the two day field window.

Day 1: loaded-hash/robot/base/scene verification → fresh contact precheck → one controlled full PICK-to-HOLD230 → one complete GRASP→PLACE→return cycle. No mid-run code authoring.

Day 2: 3–10 repeated end-to-end cycles, time waterfall, client-run/Stop/recovery and carefully commissioned retiming changes if needed. Report successes and failures, not only one lucky run.

Timing targets from audit are estimates, not promises: baseline 8–18min modeled, software closure 6–10min, retimed same caps 3.5–6min, later pipeline 3–5min. No full physical cycle has yet been measured.

Stop inventing new reasons to retry. Classify each failure as DEVICE_FAULT / ACTUAL_COLLISION / MODEL_OWNERSHIP / CONTACT_IK / PLANNER_RESOURCE / IMPLEMENTATION_STATE / VERIFICATION_AMBIGUOUS and issue a single concrete recovery action.

## Final deliverables

1. Reproducible isolated release candidate and manifest (source, config, native binary, SDK, loaded module SHAs).
2. Fix commits grouped by P1/P2/P3/P4/P5/P6, all tests and frozen replays.
3. `PICK_TO_HOLD230_READY`, `BASE_ROUTE_READY`, `PLACE_RELEASE_READY`, `RETURN_ROUTE_READY`, `FORMAL_CHECKPOINT_RESUME_READY` gate report.
4. One run via WebUI/ART, canonical state and Stop, with no Codex stage handoffs.
5. Real end-to-end timing waterfall and repeated-cycle reliability report.

## Git discipline

This file is on a PLANNING branch based on audit documents; that branch is NOT the runnable production release.
Build the production release in a separate new worktree/branch from the actual proven field code. Preserve old integration/golden and coworker dirty files. No force-push, no destructive reset, no public upload of private site raw captures.