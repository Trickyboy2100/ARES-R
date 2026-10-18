# P0 — Before the next field visit: Mac → Ubuntu GPU → .32 offline closure

Date: 2026-10-18
Priority: PRE-SITE; supersedes an immediate onsite implementation push
Working branch: planning/20261018-roundtrip-delivery-dash (documents only, not a runtime release)

## Decision

YES: use an Ubuntu x86_64 machine with a healthy NVIDIA/CUDA GPU for offline cuRobo and full adapter replay before returning onsite. An Intel macOS terminal is still useful for inventory, code preservation, reviewing contracts and orchestration, but cannot faithfully exercise the pinned CUDA/cuRobo solver path.

Prefer previously available GPU server 172.25.24.190 (reported 4x RTX4090/24GB, already used with cuRobo). 172.25.24.216 (reported 4x RTX3090/24GB) is the second option. Previously reported Ubuntu RTX3080/10GB workstation had driver/kernel-userspace incompatibility on 2026-10-12: do not waste the dash waiting for that setup until its GPU health is verified. All prior hardware and availability information must be re-audited before using it. Only reserve one GPU per isolated run; do not disrupt ongoing research GPU jobs.

IMPORTANT: a 24GB 4090/3090 replay does NOT prove the 11.66GB-class .32 RTX3060 hardware can use the same CUDA cache or meet the same latency. Reserve a final read-only/on-.32 no-motion warm planner resource test before the field visit if remotely accessible.

## Critical repository reality, verified via GitHub

Integration branch SHA: 7120c3f3aad17330d0af6ada1e39c60bc58fe7fb (2026-09-29).
Audit branch SHA: b2b44528ee1df0d0aeed657754bcfcdae3cbc2be (2026-10-17).

These files do NOT exist as runnable files at the integration root:

- scripts/run_grasp_place_roundtrip.py
- src/ares_r/demos/roundtrip_launcher.py
- src/ares_r/webui/roundtrip_panel.js
- config/grasp_place_base_route.json
- config/planner_latency_profiles.json
- demos/right_arm_grasp_place_roundtrip_v1/demo.json
- demos/right_arm_grasp_place_roundtrip_v1/parameters.json

On the audit branch, a subset of source files exists under `worklog/audits/2026-10-17-roundtrip-offline/source_snapshot/`, but the route/parameters and Oct16 physical run raw evidence are NOT all in that archive. The audit's 272-file inventory contains hashes and metadata, not all file bytes. Do not deploy audit snapshot as current source.

## Workstream 0 — Mac local source custody (no robot connection required)

Codex should inventory the following if present:

- ARES-R-offsets-20261016, local HEAD 9ff4517 observed in Oct17 audit;
- ARES-R-operations-20261015, local HEAD b3ab331 observed in Oct17 addendum;
- any other ARES-R worktrees/patches relevant to Oct16 WebUI/backend/demo;
- staged, dirty and untracked files, including those ignored by Git.

Capture relative path, byte SHA256, size, mtime, worktree Git HEAD, branch and whether tracked/modified/untracked/ignored. Include source files, config, launchers, frontend assets, tests, service files, native artifacts, package manifests, logs and scene evidence.

Do NOT coerce the two planner workers together blindly. The Oct17 addendum identified different `production_scene_worker.py` SHAs and different FAST behavior; compare exact modules and retain both for an explicit integration choice.

Output: `SOURCE_CUSTODY_MANIFEST.json`, `MAC_WORKTREE_DIFF_REPORT.md`, `UNRESOLVED_FILE_ORIGINS.md`.

## Workstream 1 — .32 read-only collection if currently reachable

Run no hardware-motion operations. Copy without modifying the site runtime:

- `/home/yikun/ARES-R` current effective source/config diffs/SHAs and installed systemd unit files;
- actual Python interpreter/module/URDF/mesh/SDK/native-sender SHAs and environment metadata;
- `worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_*` Oct16 runs and logs;
- `confirmed_lift_*`, `finish_hold_*`, native text and sender JSONL and raw gripper readbacks;
- all Oct16 `PLAN_*` for the final 130mm failure and plan requests/results;
- source/clean camera pointcloud or original depth/color, scene_report/compiled_scene, snapshot, robot geometry, BODY/camera calibration, tool geometry, target identity, attachment;
- actual pick / post-close / after-initial-lift / place observation epochs if captured;
- AMR accepted/completed/settled status and route snapshots.

Do not export passwords, API tokens, private SSH keys, camera device credentials or site secrets into the GitHub repo. Keep bulky field evidence in separately controlled private storage, with a small redacted manifest/sha index in code.

If the .32 host is offline, explicitly mark SITE_RAW_EVIDENCE_MISSING; continue with Mac material without claiming a full production-fidelity replay.

Output: `SITE_EVIDENCE_MANIFEST.json`, `REPLAY_DATA_GAP_TABLE.md`.

## Workstream 2 — Create two separate immutable bundles

Bundle A: source/release-candidate code + dependency lock/pins + approved redacted configs + native binary digests; versioned in a dedicated release candidate branch, NO force-push and golden first-pick remains intact.

Bundle B: private replay dataset with real frozen Oct16 inputs, full SHA256 manifest and provenance. Use encrypted/shared private storage or direct host transfer; DO NOT push large pointclouds, private config, raw workplace images or SDK binaries to the public repository.

Each replay case binds code SHA + config revision + calibration/tool/model/scene revision + actual start robot joints + target + payload state.

At minimum prepare these fixtures:

- P0A: old unreachable grasp station, known 55mm contact terminal IK failure;
- P0B: adjusted reachability station, known successful 55mm contact and first 100mm lift;
- P0C: grasp readback 37/37/37 + before-lift scene delta with added_fraction≈0.5204, removed_fraction≈0.6667;
- P0D: attached payload after 100mm lift, start world overlap approximately -62.26mm; preserve all genuine support/dock obstacles;
- P0E: right_place ID3 + lower-middle offset, 40mm preland and observed/obstructed scene if available;
- P0F: native contact 1439 samples×80ms (115.04s), initial-lift ~72s and telemetry/retiming inputs;
- P0G: FAST socket timeout, late result, GPU OOM, and resume-after-LIFT100 faults;
- P0H: GRASP↔PLACE route revision (last reported lateral 0.85m), AMR completions and final base settle.

Some cases may need to be marked INCOMPLETE if their original raw files were never captured.

## Workstream 3 — Ubuntu GPU reproducible offline environment

Replicate the PINNED deployed cuRobo version/patches and exact robot model, geometry and calibration. Do not `pip install` the newest cuRobo main branch; its current public API may differ from the pinned ARES integration.

Build an isolated GPU conda/venv/container environment. Record:

- Ubuntu version, GPU/driver/CUDA, Python/Torch/Warp/cuRobo commit;
- actual model URDF/meshes/sphere definitions and tool/TCP revision;
- service/worker loaded SHA and effective solver config;
- GPU allocated/reserved/peak and host RAM peak;
- cold/warm init, queue, solve, validation, package time separately.

Disconnect/deny network access to real JAKA, gripper, AMR and Epic endpoints. Replace I/O providers with deterministic replay adapters. Production runner physical execution flag stays false.

Offline closed-loop levels:

Level 1: actual raw/frozen observation → scene reconstruction/attachment ownership;
Level 2: real cuRobo GPU from frozen start/world/goal → dense validate → package & native timing audit;
Level 3: 19-stage Task/CycleRunner through simulated state provider and physical-device emulators (no network/device action).

Isaac simulation is optional for assessing trajectories, not a prerequisite for cuRobo library replay or a replacement for actual JAKA/AMR commissioning.

## Workstream 4 — Fix integration defects against frozen data

Priority 1: release/version skew and effective FAST / single-pass / job deadline / cancel / GPU cache bounds.
Priority 2: early pregrasp+contact+lift IK feasibility check BEFORE expensive cuRobo; keep NORMAL/FLIPPED if useful.
Priority 3: attachment-aware self-filter and world identity; no blanket 200mm cloud deletion.
Priority 4: grasp verification timing as HOLD_CANDIDATE then after controlled small lift CONFIRMED.
Priority 5: retime contact and lift path; preserve actual geometry/horizontal bounds/dynamics, revalidate changed paths.
Priority 6: unify start/settle and left read-only telemetry, checkpoint/resume with one backend/UI state.

Classify fallback: invalid start/goal/scene or contact impossible => do NOT QUALITY retry; actual solver search failure => one bounded quality attempt, resource failure => recover resource then explicit retry.

## Workstream 5 — Offline acceptance before going onsite

Blocking acceptance:

1. RELEASE_MANIFEST_COMPLETE=YES; SOURCE_VERSION_SKEW_RESOLVED=YES; GOLDEN_DEMO_UNCHANGED=YES.
2. GPU_CUROBO_REAL_REPLAY=PASS on the actual chosen PINNED solver; not only Mock.
3. EARLY_CONTACT_LIFT_PRECHECK=PASS old fail/new pass;
4. FAST_CANCEL_NO_ORPHAN=PASS with queue/cache/memory accounting;
5. ATTACHED_WORLD_NO_DOUBLE_COUNT=PASS with genuine support preserved;
6. GRASP_VERIFY_HOLD_VS_CONFIRMED=PASS on Oct16 data;
7. NATIVE_RETIMER_VALIDATED=PASS (with actual timing report);
8. ALL_19_STAGES_OFFLINE_E2E=PASS at least 10 deterministic cycles;
9. FAULT_AND_RESUME_REPLAY=PASS for timeout/OOM/left read/failed grasp/after-LIFT100/release uncertainty;
10. WEBUI_ART_SAME_CANONICAL_JOB=PASS; one-click/Stop/status/restart tested without real devices.

On the Ubuntu GPU machine, `warm planner p50` is a functionality/performance benchmark for that machine only. Since the eventual field GPU has about half the per-card VRAM, OFFSITE_MEMORY_COMPATIBILITY remains CONDITIONAL until a .32 warm no-motion probe or equivalent limited-memory deployment test passes.

## Workstream 6 — 1–2 day field acceptance (only after offline exit)

Day 1 first hour: validate hashes, physical state, station contract, GPU resource / real services. Then one supervised PICK→HOLD230 followed by autonomous full roundtrip if validated; all movement only with on-site personnel/working emergency stop.

Day 1 remainder: end-to-end physical run, diagnose only a specific actual fault, no new framework or research. Preserve real timing waterfall.

Day 2: repeated full runs, compare time and success, verify Stop and bounded resume, commission validated retiming/speed adjustments only against real tracking evidence, deliver operator one-page runbook and rollback.

Cannot guarantee completion in two days unless the data bundle, latest runnable code, GPU planner replay, and real `.32` resource check are done beforehand. If one of these remains blocked, do NOT spend day 1 rediscovering it; reschedule field test or narrow the acceptance scope.

## Decision and reporting cadence

First Codex turn runs inventory/custody only and returns exact gaps; no code modification and no hardware movement.

Second Codex turn builds offline isolated Ubuntu replay package and makes source fixes in a new release branch, replay verified.

Only after these steps publish the 'READY_FOR_TWO_DAY_ONSITE' decision, with YES/NO/CONDITIONAL and explicit remaining site-only uncertainties.

Required reports:

- `docs/reports/2026-10-18_MAC_SITE_GITHUB_DATA_GAP.md`
- `docs/reports/2026-10-18_UBUNTU_GPU_FROZEN_REPLAY.md`
- `docs/reports/2026-10-18_READY_FOR_TWO_DAY_ONSITE.md`

Never call a frozen-data success a completed physical task; never claim deployment without `.32` version hashes and loaded-module proof.