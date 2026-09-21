# P3.1 Robot-adjacent Residual and Support/Object Decomposition

Date: 2026-09-21

Branch: `feat/e2e-v0-integration-20260917`
Scope: planning-only. No AMR, arm, or gripper motion; no push.

## Root cause and filter contract

The P3 `residual_009` was not demonstrated to be robot-owned. Its 212 observed
points were at least 30.01 mm outside the nearest P2 OBB (`right/link4`) and
20.52 mm outside the exact cuRobo planner sphere. The old inflated cluster AABB,
however, intersected that sphere by 27.40 mm. It filled unobserved empty space
between residual points and the robot. Fresh joint/tool revisions and a raw
overlay were checked; there was no basis to claim a stale joint state or wrong
TCP as the cause. The residual is retained as external/unknown occupancy.

`ROBOT_OWNED_FILTER` now records a revisioned union of the P2 mesh-derived OBBs
and the *same* circumscribed-cell spheres used by the active-arm planner. It
does not globally increase self-filter padding. In the attribution scan,
the union removed 97,017/1,993,058 raw ROI-input points; sphere-only removals
were zero. This is an interface/provenance improvement, **not** a claim that the
24.6 mm conflict disappeared through filtering. The conflict was resolved by
splitting only abstraction-induced AABB bridges while retaining every observed
point. A genuine point-level planner collision remains a collision.

Evidence: `worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/`
(`robot_adjacent_attribution.json`, `robot_adjacent_overlay.png`).

## Generic scene decomposition

The previous single-AABB path remains selectable and fail-closed. The new
planning-only `multi_primitive` path detects horizontal observed support levels,
assigns local height, separates protruding components, and tiles connected
structures/unknown occupancy into small observed primitives. It never labels
occluded volume as free. `TARGET_FREE_VOLUME` remains a future semantic
contract, not an occupied-space subtraction.

In the fresh box-removed CLEAR frame, the old pipeline generated 7 AABBs with
0.010413 m³ summed occupied volume. The multi-primitive comparison generated
167 pieces with 0.004288 m³ (41.2% of the old volume) and accounted for
9,992/9,992 cleaned observed points. The fresh P3.1 scene then selectively
refined robot-adjacent bridge primitives and compiled 190 total scene objects,
including table, inactive arm/tool and chassis.

In an earlier observed box-present diagnostic frame, the upright box became
its own `PROTRUDING_OBSTACLE` near BODY `[0.703,-0.216,0.962] m`, dimensions
`[0.209,0.089,0.206] m`, instead of being merged with the dock into a
`[0.209,0.586,0.274] m` monolith. The dock/support observations and unknown
points remain represented. This is geometric decomposition, not a guarantee
that every unseen dock pocket or cabinet opening is traversable.

Evidence: `worklog/evidence/2026-09-21-p3-1-residual-support/clear_ab/comparison/`
and `.../clear/scene_v3/support_decomposition.json`.

## Fresh current-base A/B planning-only evidence

The base moved after the initial box-removal scan. The earlier
`SCENE_7a40cdebeda64a5eaf8a89108548bdfd` CLEAR result is retained as
historical evidence only; it is **not** the current A/B comparator. Three new
Pixel Pro captures and read-only dual-arm joint/tool audits were used for
current-base CLEAR, observed-box AVOID and synthetic BLOCK respectively. Each
has its own point-cloud SHA, `SceneSnapshot` and cuRobo request. The A/B joint
contract is identical across the three scenarios, but the static A→B/B→A
previews start from *hypothetical* A/B joints, not the captured live joints;
they are explicitly non-executable.

| Case | Snapshot | A→B / B→A | Key result |
|---|---|---|---|
| CLEAR | `SCENE_3c23b74e20b74209a7781a743a7d378f` | SUCCESS / SUCCESS | Modeled global min +103.40 mm, limited by chassis proxy; 0.430 m TCP path. |
| AVOID | `SCENE_d5af7694fcef4e11a8e7205e0a05d1d6` | SUCCESS / SUCCESS | Observed box is the limiting object; +9.63 mm modeled path gap versus −21.78 mm joint-linear baseline. |
| BLOCK | `SCENE_3ce31fac5ff2459ba5213c5224bb0438` | FAILURE / FAILURE as expected | Explicit synthetic goal enclosure; no fallback trajectory; goal gap −112.04 mm. |

Current A/B BODY TCP endpoints are approximately A `[0.704,-0.530,1.052] m`
and B `[0.679,-0.117,1.125] m`, 0.420 m apart. The separate current→A
reposition candidate also planned successfully in the box-free scene; it is
not an authorized movement. With the box absent, A→B/B→A paths were each about
0.430 m; with the observed box, each became about 0.453 m, adding 22.3 mm.
Arc-normalized TCP path separation peaked at 46.6 mm and averaged 29.3 mm.
The box was separately detected near BODY `[0.697,-0.329,0.961] m`, observed
AABB `[0.085,0.211,0.207] m`; no dock-wide monolithic AABB was used.

The modeled AVOID margin of 9.63 mm does **not** authorize real motion. The
active controller TCP is 31–35 mm beyond the pinned gripper collision envelope
(see the current-base TCP audit), and the observed box bottom does not fully
capture its occluded contact with the dock. The model could underrepresent
physical finger reach. The two controller UI images confirm selected TCP
values, but not physical contact-center length.

Evidence and visualization:

- `worklog/evidence/2026-09-21-p3-1-residual-support/current_base_clear/`
- `worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/`
- `worklog/evidence/2026-09-21-p3-1-residual-support/current_base_block/`
- `current_base_avoid/clear_vs_avoid_three_views.png`: same-angle BODY TOP/REAR/RIGHT comparison, with the **observed** box AABB.
- `current_base_avoid/comparison/`: normalized XYZ path plots, separation and per-object clearance JSON.
- `docs/reports/2026-09-21_CURRENT_BASE_AB_TCP_EXPERIMENT.md`: detailed A/B contract and physical-tool gate.

The fresh current-base capture/processing times were: camera 4.37/5.07/4.31 s
for CLEAR/AVOID/BLOCK, CAMERA→BODY 34/55/33 ms, self-filter
2.34/2.37/2.68 s, cleanup 1.10/1.05/1.19 s, decomposition
1.86/1.76/2.00 s and SceneCompiler 13/12/13 ms. cuRobo planning-only
times were about 9.74 s (CLEAR), 14.5 s (AVOID), 5.4 s (BLOCK) per direction.

## Validation and status

`PYTHONPATH=src python3 -m unittest discover -s tests -q`:
408 tests OK, one Open3D-dependent test class skipped in system Python.
The two Open3D decomposition tests passed in the site `calib` environment.

| Gate | State |
|---|---|
| `ROBOT_ADJACENT_RESIDUAL_EXPLAINED` | TRUE: empty-volume AABB bridge, not confirmed robot-owned points |
| `ROBOT_OWNED_FILTER_READY` | TRUE as planning-only canonical/provenance geometry |
| `SUPPORT_OBJECT_DECOMPOSITION_READY` | TRUE for observed support + protrusion diagnostic; not a commissioned cabinet model |
| `MULTI_PRIMITIVE_OBSTACLE_WORLD_READY` | TRUE, planning-only, single-AABB baseline preserved |
| `CLEAR_PLAN_READY` | TRUE, planning-only on fresh current-base scene |
| `AVOID_PLAN_READY` | TRUE, observed independent box changes same-A/B paths; +9.63 mm modeled box clearance |
| `BLOCK_PLAN_READY` | TRUE, fresh synthetic goal block fails without fallback |
| `READY_FOR_SUPERVISED_CLEAR` | FALSE: new TCP length versus gripper collision geometry is not physically reconciled; hypothetical-start preview |
| `READY_FOR_SUPERVISED_AVOID` | FALSE: same model issue and only 9.63 mm modeled box margin |
