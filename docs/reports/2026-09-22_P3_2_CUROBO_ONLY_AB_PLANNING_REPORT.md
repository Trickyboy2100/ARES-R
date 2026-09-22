# P3.2 — cuRobo-only A/B planning checkpoint (2026-09-22)

Status: **PLANNING-ONLY; NO DEVICE MOTION; LOCAL COMMIT ONLY; NO PUSH.**

## Latest operator override

两条现场 override 原文：

> 明确override：从A到B或者反过来一直保持用curobo规划，而不是走真直线，这次demo中所有点到点运动都走curobo规划

> 小箱子已移走，请继续工作。我不希望有waypoint，我希望只是在避障状态下从A点到B点或者反过来运动进行curobo规划，动作还要相对平滑

Every point-to-point leg, including CURRENT→A, A→B and B→A, uses cuRobo. No true-Cartesian commanded path and **no explicit waypoint**, including for avoidance. The A–B Cartesian chord remains a *reference-only*, whole-arm-plus-gripper swept-corridor classifier; it is never sent to the controller. When the real observed box blocks that chord, cuRobo receives only start, goal and the fresh collision world and generates its own avoidance trajectory. This override supersedes the P3.2 order's straight-CLEAR and forced-OVERHEAD requirements. `validate_curobo_only_policy()` rejects explicit waypoint contracts.

The rough right flange-to-grasp-center measurement is ≈145 mm; pinned gripper distal extent ≈149 mm; controller active TCP Z≈184 mm. No tool revision was changed. `TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED = YES`, so `READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION = NO`. The new demo state machine's `execute_next` raises `PermissionError` unconditionally.

## Baseline and A/B

P3.1 `7ae26aacb86222263d76490e3ec9cc55e9867de6` was fast-forward pushed from `eafae083cc03f61c6b7162ea90130ce798b8cac6`; GitHub and `.32` then matched, ahead/behind 0/0. Unrelated AMR and coworker dirty files were excluded.

Offline full-SE3 FK/IK search selected candidate 1 from `worklog/evidence/2026-09-21-p3-2-ab-demo/search_v2.json`. Both endpoints have BODY X=0.710 m and Z=1.000 m; lateral Y span is 0.470 m.

| Endpoint | BODY TCP XYZ (m) | Right joints (rad) |
|---|---|---|
| A | `[0.710, -0.600, 1.000]` | `[0.20547, -0.18950, 0.53299, -4.44926, -0.85481, -1.52186]` |
| B | `[0.710, -0.130, 1.000]` | `[0.01732, 0.87368, 0.99965, -5.53286, -1.21730, 0.32357]` |

These are hypothetical planning endpoints, **not** claims that the physical arm was at A or B. CURRENT→A has a separate cuRobo-only planning preview (modeled gap 30.7 mm), not an executed reposition.

## Fresh scene results

Each leg used a separate Pixel Pro capture and fresh read-only dual-arm diagnostics, then CAMERA→BODY, whole-robot self-filter, conservative residual cleanup, support/object decomposition, fresh `SceneSnapshot`, inactive-left-arm geometry and cuRobo world. The observed box remains an independent protruding object, not a dock-wide AABB. The physically moved box was absent for CLEAR and present for AVOID. BLOCK adds a synthetic goal blocker to another fresh scan; it is a fail-closed regression, not a physical obstacle claim.

| Scenario | Fresh snapshot | Result | Minimum modeled gap | TCP path / max Z | cuRobo planning |
|---|---|---|---:|---:|---:|
| CLEAR A→B | `SCENE_89c322e75b684e01997a1dbd4379b77d` | SUCCESS, `STRAIGHT_CLEAR` reference | 103.4 mm | 0.480 m / 1.000 m | 21.40 s |
| CLEAR B→A | `SCENE_8cf0097bbbfc455599638a796468147c` | SUCCESS, `STRAIGHT_CLEAR` reference | 103.4 mm | 0.480 m / 1.000 m | 21.30 s |
| AVOID A→B | `SCENE_898df262207741fc9c0196a2f679eb3f` | SUCCESS, `STRAIGHT_BLOCKED` reference | 35.4 mm, real box | 0.642 m / 1.155 m | 21.33 s |
| AVOID B→A | `SCENE_7d2cf49f13b9463abf5aaf87b9cf1065` | SUCCESS, `STRAIGHT_BLOCKED` reference | 34.6 mm, real box | 0.645 m / 1.157 m | 21.08 s |
| BLOCK A→B | `SCENE_337a3a1f87a84165956ee211b27bb997` | EXPECTED FAILURE; no fallback trajectory | goal −117 mm | none | 5.42 s |

The cuRobo-generated AVOID arcs rise 154.7/156.5 mm above the endpoints without an imposed overhead point. Relative to matching-direction CLEAR paths, maximum TCP path separation is 202.4/204.1 mm; modeled minimum gap in those artifacts is 35.4/34.6 mm. A further AVOID A→B repeat with the final waypoint-rejection guard, on the same frozen scene, also succeeded but returned a **9.3 mm** minimum modeled gap and 121.0 mm arc. This exposes planner-solution variability: repeat planning success does not certify a stable clearance margin. It is model clearance, **not** certified physical clearance. CLEAR cuRobo paths happen to be nearly direct, but are not exact Cartesian lines.

人工看过本轮三视图与 CLEAR/AVOID 轨迹对比图后，已确认**同意这次轨迹看起来的效果**。这是对规划可视化表现的认可，不是对最小间隙、TCP 标定、平滑实机跟踪或实机执行安全性的验收；上述执行禁用状态不变。

Trajectory continuity was measured at 8 ms interpolation: CLEAR max joint step ≈0.0125 rad, AVOID ≈0.0116 rad. An *offline preview* time-scale factor ≈4.46 for CLEAR or ≈4.13 for AVOID would bound peak joint speed near 0.35 rad/s; it has not been applied to a real ServoJ executor. Smoothness and tracking remain uncommissioned.

Capture took approximately 5.6–7.8 s per scan, CAMERA→BODY 0.032–0.034 s, self-filter 2.3–2.9 s, cleanup 1.0–2.2 s, decomposition ≈1.7 s, SceneCompiler 0.012–0.020 s, and cuRobo planning ≈21 s for successful legs. The first AVOID A→B run preserved its raw capture after the host Python lacked Open3D, then compiled that same frame using `/home/yikun/anaconda3/envs/calib/bin/python3.9`; later runs explicitly used that environment. All artifacts bind to their own snapshot/revision. Old scenes and trajectories invalidate after arrival/stop/fault in the offline demo state machine.

## Implementation and evidence

- `scripts/search_p32_ab.py`: repeatable offline endpoint search.
- `src/ares_r/motion/ab_cartesian.py`: reference-only chord FK/IK and classification support.
- `scripts/p32_scan_scene.py`: fresh capture, read-only robot state and scene creation.
- `scripts/run_p32_ab_plan.py` and `src/ares_r/motion/production_scene_worker.py`: cuRobo-only planning and blocked-goal regression; explicit waypoints forbidden for P3.2.
- `src/ares_r/motion/ab_demo_state.py`: scene/trajectory-bound A/B lifecycle; execution hard blocked.
- `scripts/render_p32_ab_comparison.py`: matched-view three-view scene and TCP path plots.
- `tests/test_ab_demo_state.py`: policy/state-machine regression, including waypoint rejection.
- Scene/plan evidence: `worklog/evidence/2026-09-22-p3-2-ab-demo/{clear_leg_a_to_b,clear_leg_b_to_a,avoid_leg_a_to_b,avoid_leg_b_to_a,block_leg_a_to_b}/` (`plan_direct_v2/planning.json` in each). Final-guard repeat: `avoid_leg_a_to_b/plan_direct_no_waypoint_guard/planning.json`.
- Final visualization: `worklog/evidence/2026-09-22-p3-2-ab-demo/final_visual_no_waypoint/{p32_three_views.png,p32_path_comparison.png,comparison.json}`. Earlier forced-waypoint or historical-CLEAR images are exploratory only, not the accepted result.

Site test: `PYTHONPATH=src python3 -m unittest discover -s tests -q` → **412 tests OK, 1 skipped**. No arm, gripper or AMR movement was commanded. Camera capture and robot read-only diagnostics were used.

## Gate summary

`P31_PUSHED_AND_ALIGNED = YES`

`TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED = YES`

`AB_TARGETS_READY = YES (planning-only)`

`STRAIGHT_CARTESIAN_PLANNER_READY = SUPERSEDED_BY_USER_OVERRIDE`

`STRAIGHT_CORRIDOR_CLASSIFIER_READY = YES (reference-only)`

`OVERHEAD_BYPASS_PLANNER_READY = SUPERSEDED_BY_USER_OVERRIDE; NO WAYPOINT`

`NEW_CLEAR_PLAN_READY = YES (both directions, cuRobo)`

`NEW_AVOID_PLAN_READY = YES (both directions, cuRobo)`

`NEW_BLOCK_PLAN_READY = YES (expected failure)`

`AB_DEMO_STATE_MACHINE_READY = YES (offline; execution blocked)`
`READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION = NO`

Before any physical A↔B attempt, verify actual start-joint matching, tool/TCP physical semantics, geometry, **repeatable** clearance margin, ServoJ timing/tracking and live scene/lease gates. None is certified by this planning-only checkpoint.
