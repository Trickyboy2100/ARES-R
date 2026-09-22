# P3.3 execution hardening — fail-closed checkpoint (2026-09-22)

Status: **STOPPED AT 30 MM CLEARANCE GATE / PLANNING-ONLY / NO HARDWARE MOTION / NO PUSH**.

## Locked operator policy

All CURRENT→A, A→B and B→A point-to-point trajectories are planned by cuRobo. No explicit waypoint is passed; cuRobo receives start, goal and the frozen collision world. The A–B straight corridor is diagnostic only. Existing A/B `[0.710,-0.600,1.000]` and `[0.710,-0.130,1.000]` BODY metres are unchanged. The operator approved the P3.2 visual trajectory style; no aesthetic retuning was made.

## Completed offline substrate

- Conservative link6 execution envelope unions pinned ARES gripper bounds with the entire selected controller TCP ray, then adds 8 mm sensor/model inflation. With the observed selected tool translation `[-3.013,-4.790,184.380]` mm, link6 centre is approximately `[0,0,0.09219]` m and half-extents `[0.06254,0.02075,0.10019]` m. Revision: `sha256:22b33c1e60c03dd7b1910e7682e579f10421777cafef09c3c7af394eb44ad0ff`. Controller tool/TCP was not changed. `TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED=YES` remains.
- Separate CPU/URDF dense post-validator computes active-arm/tool collision spheres and signed distances to every frozen world cuboid without using cuRobo's collision query. It also checks BODY central TCP margin. This is a second model-based check, not physical certification or independent self-collision validation.
- Deterministic selector rejects any trial below 30 mm in either cuRobo or CPU dense check, and accepts a profile only when all three repeats pass in every required direction. Among accepted repeats it ranks larger minimum clearance, shorter path and lower joint jerk, then freezes the exact trajectory hash.
- Offline right-native file builder reuses the existing 80 ms `ARES_R_RIGHT_V1` contract, sender's 150°/240 s limits, site limits and the stricter tracking-derived speed ceiling `1.25°/s≈0.0218 rad/s`. The selected preview operating cap is lower still, `0.020 rad/s`. It changes only time sampling along the cuRobo joint polyline and verifies unchanged endpoints and near-zero polyline geometry error. An existing P3.2 AVOID path (not execution-envelope accepted) takes about 138.9 s at this cap, with predicted following error 0.1375° (0.0125° below the conservative 0.15° budget and 0.0625° below the native 0.2° stop threshold). This is a feasibility estimate, **not** an execution package.
- Candidate manifest binds actual-vs-planned start, snapshot/digest, cloud SHA, calibration, whole robot/inactive arm/tool/envelope revisions, planner profile, exact trajectory/native hashes, timing profile and expiry. Lease remains `DRY_RUN_UNISSUED`. SafetyKernel preflight reports all 13 required gates separately but never calls `authorize` or mints a permit. `execution_enabled=false` and `slow` speed profile `UNCOMMISSIONED` remain blockers.
- A/B session clears snapshot, trajectory, candidate and lease on stop/fault/arrival. P3.3 execute-next remains hard blocked.
- The installed JAKA native sender was rebuilt offline from the current source using the site SDK. Rebuilt and installed binaries had the same SHA-256: `87649366d9c83fd87841e755303fe2b39595e1c4f547347b1ea8e1696dc7aff5`. The candidate binder now includes that binary digest. The rebuild did not connect to the controller.

## First frozen-scene smoke check

AVOID A→B, original frozen snapshot `SCENE_898df262207741fc9c0196a2f679eb3f`, conservative envelope, 40 mm optimizer activation: cuRobo planned without waypoint. cuRobo dense gap `14.7865 mm`; independent CPU gap `14.7865 mm` (same observed box), central TCP margin `44.4 mm`, arc height `174.1 mm`, planning `23.0 s`. This **fails** the non-negotiable 30 mm acceptance gate. One failed profile/run does not establish whether any profile is reproducible; the full 10/20/30/40 mm × three-repeat sweep remains required.

## Frozen AVOID A→B repeat sweep and stop decision

The `.32` connection was restored. The same `SCENE_898df262207741fc9c0196a2f679eb3f` AVOID scene, A/B, active collision geometry and conservative tool envelope were used for three fresh cuRobo planning process calls at each optimizer collision activation distance. All paths had no explicit waypoint; CPU/URDF dense post-validation independently measured the limiting signed distance. Each repeat within a profile produced the same exact trajectory hash, so the result is reproducible but **not acceptable**.

| Activation | Dense modeled gap, all three repeats | Max BODY TCP Z | Path length | Mean planning | Result |
|---|---:|---:|---:|---:|---|
| 10 mm | 9.326 mm | 1.137 m | 0.612 m | 21.2 s | Reject |
| 20 mm | 14.787 mm | 1.149 m | 0.635 m | 21.3 s | Reject |
| 30 mm | 14.787 mm | 1.162 m | 0.668 m | 16.0 s | Reject |
| 40 mm | 14.787 mm | 1.174 m | 0.701 m | 21.3 s | Reject |

The limiting object in every run is `observed_support_03_component_01_protruding`. The 10/20/30/40 mm trajectories have distinct hashes in the machine-readable sweep summary; none is an execution-candidate hash. All 12/12 runs had both planner and independent dense clearance below the **30 mm** engineering acceptance gate. Thus no available profile can satisfy the required common profile across five cases. The sweep was deliberately stopped after this exhaustive failed case, before further directions; this is an **early stop**, not a completed 60-trial sweep. A partially launched B→A child was terminated without a recorded result. No incomplete artifact was selected.

Evidence: `worklog/evidence/2026-09-22-p3-3-execution-hardening/sweep_v2/sweep_summary.json` and `worklog/evidence/2026-09-22-p3-3-execution-hardening/visualization_final/p33_clearance_profile_sweep.png`. The underlying per-repeat `planning.json` and independent validation are retained under `sweep_v2/avoid_a_to_b/`. The chart omits unmeasured cases; it must not be read as CLEAR/BLOCK results.

Because the non-negotiable gate failed, **no native execution candidate, lease or package was generated**. CLEAR/BLOCK P3.3 reruns, exact native durations for accepted paths, tracking margin for accepted paths, and trajectory style comparison with conservative envelope remain unmeasured. The 138.9 s / 0.1375° values above are only an older P3.2 path packaging feasibility estimate, not an accepted P3.3 trajectory. The old P3.2 CLEAR/AVOID previews remain available for visual reference, but do not certify the new envelope. Resolving the gap requires explaining the limiting object/geometry and repeating planning-only validation; lowering the gate or silently changing the approved A/B is not authorized.

Site test result after the last code sync: `PYTHONPATH=src python3 -m unittest discover -s tests -q` → **419 OK, 1 skipped**. The remote worktree also contains unrelated coworker AMR changes; those are preserved and excluded from the P3.3 commit.

`CUROBO_ONLY_POLICY_LOCKED = YES`

`NO_EXPLICIT_WAYPOINT_POLICY_LOCKED = YES`

`EXECUTION_TOOL_ENVELOPE_READY = YES (model-level, not physical certification)`

`CLEARANCE_REPRODUCIBILITY_READY = NO (12/12 repeatable AVOID A→B trials below 30 mm)`

`EXECUTION_CANDIDATE_SELECTOR_READY = YES (offline tests; no accepted candidate)`

`NATIVE_TRAJECTORY_PACKAGING_READY = PARTIAL (offline method; no accepted conservative plan or package)`

`EXECUTION_LEASE_BINDING_READY = YES (dry-run draft only)`

`SAFETY_PREFLIGHT_READY = YES (dry-run only)`

`CURRENT_TO_A_EXECUTION_PACKAGE_READY = NO`

`A_TO_B_EXECUTION_PACKAGE_READY = NO`

`B_TO_A_EXECUTION_PACKAGE_READY = NO`

`READY_TO_REQUEST_FIRST_SUPERVISED_MOTION = NO`

No AMR, arm or gripper motion was commanded. No GitHub push was performed in P3.3.
