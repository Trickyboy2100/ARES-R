# P3 Production Point-cloud → cuRobo Planning-only Report

Date: 2026-09-21

Branch: `feat/e2e-v0-integration-20260917`

Execution: **BLOCKED** — no AMR, arm, or gripper command was sent.

## Result

| Gate | State | Evidence |
|---|---|---|
| `RESIDUAL_CLOUD_CLEANUP_READY` | `TRUE` | Conservative radius cleanup retained the hold-out region 100% with 0 mm AABB change. |
| `REAL_OBSTACLE_SCENE_READY` | `TRUE_WITH_CONSERVATIVE_AABB_LIMITATION` | Fresh Pixel Pro scenes bind calibration, point-cloud SHA, robot state, whole-robot geometry, inactive arm/tool, table, chassis and central TCP constraint. |
| `CLEAR_PLAN_READY` | `FALSE` | Fresh scene rejected at the actual start state because a robot-adjacent residual AABB still overlaps the active-arm collision model by 24.6 mm. |
| `AVOID_PLAN_READY` | `FALSE` | Fresh scene rejected safely; the dock and upright box merged into one solid AABB, and robot-adjacent residual remained. |
| `BLOCK_PLAN_READY` | `TRUE` | Fresh scene plus an explicitly labelled synthetic goal enclosure failed with no fallback. |
| `READY_FOR_SUPERVISED_CLEAR` | `FALSE` | Start-state environment collision must be resolved from geometry/self-filter evidence first. |
| `READY_FOR_SUPERVISED_AVOID` | `FALSE` | The obstacle representation must preserve support surfaces, dock cavities and cabinet openings before execution. |

The failure states are deliberate safety results, not planner fallbacks. A diagnostic scene proved that a 26.7 cm planning-only path can succeed when moving away from the residual (`J1 -0.6 rad`, minimum clearance 15.2 mm), but it is not promoted as final because it reused an exploratory scan and does not demonstrate avoidance of the box.

## Residual cleanup

Selected baseline: `radius_4_20mm`, 5 mm voxel, 12 mm cluster tolerance, minimum 12 voxels.

- self-filter input: 1,895,624 points;
- non-table ROI points: 625,288;
- voxel points: 12,791;
- radius outliers removed: 16;
- cluster noise removed: 21;
- small-cluster voxels removed: 10;
- retained: 12,744 voxels in 13 clusters;
- hold-out retention: 53/53 points (100%);
- hold-out AABB change: `[0, 0, 0] mm`;
- cleanup total: 100.5 ms after warm-up.

The final scenes used the already-audited 30 mm canonical whole-robot self-filter margin. A 50 mm exploratory margin was rejected as a production shortcut: it can hide nearby real obstacles and was not used for final evidence.

## Fresh planning-only runs

Every listed run used a new camera capture, a new point-cloud SHA, fresh read-only joint/tool diagnostics, a new `SceneSnapshot`, and a new planner request.

### CLEAR

- snapshot: `SCENE_ddbb97537dff49848f66ab080afec427`;
- candidate TCP separation: about 0.267 m;
- result: safe failure at start;
- start clearance: `-24.64 mm`;
- goal clearance: `+103.40 mm`;
- planning samples: `947.9 / 949.3 / 951.5 ms`;
- camera capture: `4.508 s`; capture + BODY artifact: `5.843 s`;
- CAMERA→BODY: `47.9 ms`; self-filter: `1.860 s`; cleanup/AABB: `1.193 s`; SceneCompiler: `1.77 ms`.

### AVOID

- snapshot: `SCENE_a568a7ec90f94bc0af6479278d68c1bd`;
- result: safe failure, no fallback;
- start clearance: `-24.17 mm`;
- goal clearance: `-42.89 mm`;
- planning samples: `955.0 / 957.1 / 957.1 ms`;
- camera capture: `4.536 s`; capture + BODY artifact: `5.869 s`;
- CAMERA→BODY: `47.5 ms`; self-filter: `1.871 s`; cleanup/AABB: `1.199 s`; SceneCompiler: `1.56 ms`.

The dominant merged residual is approximately `0.209 × 0.586 × 0.274 m`, centered near BODY `[0.703, 0.033, 0.928] m`. It contains the upright box and the irregular dock/support structure, so treating it as one solid AABB destroys free space that exists physically.

### BLOCK

- snapshot: `SCENE_5452ff90d3f149e8a78aec70471a6dc6`;
- explicit synthetic goal enclosure: present and provenance-labelled;
- expected/observed: `FAILURE / FAILURE`;
- no fallback trajectory;
- goal clearance to synthetic enclosure: `-141.73 mm`;
- planning samples: `964.0 / 965.4 / 965.4 ms`.

BLOCK also contains the robot-adjacent residual, so it proves fail-closed behavior but is not used to isolate the synthetic enclosure as the sole collision cause.

## Evidence

- cleanup comparison: `worklog/evidence/2026-09-21-p3-production-demo/avoid_final/cleanup/`
- AVOID: `worklog/evidence/2026-09-21-p3-production-demo/avoid_final/`
- CLEAR: `worklog/evidence/2026-09-21-p3-production-demo/clear_final/`
- BLOCK: `worklog/evidence/2026-09-21-p3-production-demo/block_final/`
- exploratory diagnostics: `worklog/evidence/2026-09-21-p3-production-demo/avoid/`

Large raw PLY/NPZ capture products remain under `logs/body_cloud/` and are referenced by manifest/SHA rather than committed.

## Why one AABB is insufficient

The current representation is a useful fail-closed baseline, but connected point clusters are not equivalent to solid objects. A cabinet shell, shelf, tote, dock, or U-shaped fixture can be connected in the point cloud while containing free space that the TCP and carried object must enter. A single cluster AABB fills every cavity and opening.

The observed dock also contains multiple roughly 10 cm × 10 cm recessed berths. Those recesses must eventually be represented as target/free-space semantics, not filled by one collision box.

## Candidate routes after P3

### Route A — support-surface and object decomposition (recommended next increment)

Segment horizontal/vertical support planes first, maintain the dock/cabinet shell as known or reconstructed geometry, and cluster only points protruding from support surfaces. Use height slicing or connected components above the local support plane to isolate the upright box. Preserve dock recesses as named target volumes.

Advantages: works with the current AABB `SceneCompiler`, small change, fast, easy to validate.

Limitations: plane/edge thresholds need tuning; arbitrary curved or heavily occluded objects remain approximate.

### Route B — low-poly multi-OBB/convex decomposition

Keep raw connected surfaces, but replace one cluster-wide AABB with several oriented boxes or conservative convex pieces. Explicitly retain negative/free volumes such as cabinet mouths, shelf gaps and dock pockets. Planning-world output remains primitive geometry, so it can coexist with the current implementation.

Advantages: preserves openings while keeping fast primitive collision checking; visual output resembles the requested low-poly obstacle field.

Limitations: decomposition stability and temporal identity require additional work; an occluded back wall must not be inferred as free space.

### Route C — nvblox/ESDF voxel world

Integrate calibrated depth frames into a BODY-fixed nvblox map and query it through cuRobo `WorldBloxCollision`; use separate static, dynamic and interaction layers with decay. This is the closest route to the referenced cuRobo depth-camera demo. Keep known table/dock geometry and inactive-arm collision geometry in primitive layers.

Advantages: directly represents arbitrary shapes and openings; avoids forcing a connected object into one solid box; supports repeated scans and dynamic decay.

Limitations: adds `nvblox_torch`/ABI/GPU integration, self-filter and occlusion risks; cuRobo explicitly notes that perception-based collision-free planning is still difficult in dense/occluded scenes and voxel sizes below 1 cm can exhaust GPU memory.

### Route D — hybrid production route

Use known geometry for chassis, table, dock and cabinet; nvblox/ESDF for unknown residuals; compact multi-OBB output as a debug view and fallback. Define task-space `TARGET_FREE_VOLUME` for dock pockets/cabinet openings, but never subtract unobserved space from occupancy without visibility evidence. Bind every map to `SceneSnapshot`, robot/tool state, calibration revision and a short execution lease.

This is the recommended production architecture after Route A validates the data contracts. It keeps the current reliable AABB pipeline as a comparator rather than replacing it immediately.

## Required next gates

1. Explain or eliminate the repeatable robot-adjacent residual using raw overlay against the exact planning sphere model; do not enlarge self-filter padding blindly.
2. Implement Route A offline and prove that the upright box separates from the dock while table/dock points and all hold-out obstacles remain.
3. Add cabinet/dock fixtures with explicit opening and pocket tests: the shell must collide, the opening corridor must remain free, and unknown/occluded regions must remain conservative.
4. Only after CLEAR and AVOID pass on fresh snapshots may either supervised readiness flag become true.

## User override (verbatim)

> 已经摆放好，但是机器人移动过。实际上我不希望避障绑定固定场景，我希望在任意场景下机器人扫描并且进行了点云重建之后都可以对场景内的桌子、物体、不规则物体进行避障。就像curobo官方界面中'/Users/andyee/Desktop/Screenshot 2026-09-21 at 10.44.51.png'的演示，把手在点云重建空间中抽象成了low poly 方块形式的障碍物，在实时规划中进行避障[https://curobo.org/videos/reacher_voxel_clip.webm](https://curobo.org/videos/reacher_voxel_clip.webm)。倒是不用着急改变当前的点云-方框形式，现在看起来已经非常好。但是我这次的override说明，请在完成本轮工作结尾原样复述到报告中并且提出你的方案而不是直接改动现有已经比较好的表现结果

The current AABB visualization and planning baseline were therefore retained. The routes above are proposals only; no nvblox, low-poly, cavity subtraction, or semantic dock behavior was added in this P3 implementation.

## Validation

`PYTHONPATH=src python3 -m unittest discover -s tests -q` → **406/406 passed** in the final worktree state.
