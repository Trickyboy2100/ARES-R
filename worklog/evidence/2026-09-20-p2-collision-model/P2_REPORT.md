# P2 whole dual-arm collision model result

No device movement was performed. P2 consumed read-only joint/tool diagnostics and the P1 commissioned BODY cloud.

## Exit gates

```text
ROBOT_COLLISION_OVERLAY_READY = YES
ARM_LINK_COLLISION_MODEL_READY = YES
GRIPPER_COLLISION_MODEL_READY = YES
WHOLE_ROBOT_COLLISION_MODEL_READY = YES
SELF_FILTER_READY = YES
INACTIVE_ARM_OBSTACLE_READY = YES
MUTUAL_ARM_COLLISION_CHECK_READY = YES
P3_ALLOWED = YES
```

`P3_ALLOWED` means the P2 geometry substrate may enter P3 planning work. It does not authorize motion and does not declare any P3 trajectory executable.

## Inputs and revisions

- BODY cloud: `logs/body_cloud/artifacts/20260920_152515_5c160c67/manifest.json` (2,005,529 valid points).
- Pinned model: `Trickyboy2100/ARES@b978cbd669b5a3f6bc0bd19defcbe5256692f145`.
- Geometry revision: `sha256:725a06f6b14173e8419923e6b49d977c0d790461c3dcb869cf992cb820805210`.
- Scene revision: `sha256:c35b68af1699cf1213348431cec39103f0b6cac97111768a5051e15ee3b2fc6b`.
- Snapshot: 20 boxes: 7 links + gripper envelope + TCP marker per arm, chassis proxy and central exclusion.

## Self-filter evidence

| Margin | Removed | Left arm | Left gripper/tool | Right arm | Right gripper/tool | Table retained | Known box retained |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 mm | 91,265 | 0 | 0 | 81,324 | 9,941 | 100% | 100% |
| 20 mm | 92,691 | 0 | 0 | 83,851 | 8,840 | 100% | 100% |
| 30 mm | 93,023 | 0 | 0 | 85,346 | 7,677 | 100% | 100% |

Zero left-arm deletions reflect camera occlusion/no returns inside its geometry in this fixed snapshot, not omission of the left model. Both left arm and gripper are present in the snapshot and inactive-arm obstacle.

The retained known-box raw AABB is `[83.763, 209.109, 230.491] mm` versus the independently measured `[78,205,224] mm`, an absolute extent difference of `[5.763,4.109,6.491] mm`. Filtering changes each detected extent by `0.000 mm`. All 601,087 selected table-band points remain for 10/20/30 mm.

## Offline dual-arm regression

- Current saved dual-arm state: clear in both active-right/inactive-left and active-left/inactive-right directions.
- Deliberate link overlap: detected in both directions.
- Deliberate gripper overlap: detected in both directions with `gripper_involved=true`.
- Inactive left J1 synthetic change by 0.1 rad: inactive obstacle revision changed.
- Inactive obstacle count: 10 for either active-arm direction, including inactive arm, gripper/tool, and central exclusion.
- No physical trajectory was planned or executed.

## Latency on `.32`

| Stage | Runs | p50 | p95 |
|---|---:|---:|---:|
| Whole geometry export | 100 | 1.033 ms | 1.157 ms |
| Both inactive-arm world conversions | 100 | 0.152 ms | 0.170 ms |
| Both-direction mutual collision queries | 100 | 0.955 ms | 0.986 ms |
| 2.01 M-point self-filter, 20 mm | 5 | 1.811 s | 1.870 s |

## Evidence

- `raw_body_cloud.png`
- `robot_collision_overlay.png`
- `self_filtered_20mm.png`
- `self_filter_report.json`
- `whole_robot_geometry.json`
- `mutual_collision_regression.json`
- `latency_benchmark.json`
- `left_fk_audit.json`, `right_fk_audit.json`

Full repository test result on `.32`: `399/399 OK` with `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

Recommended production default margin for P3 input is 20 mm; 10 and 30 mm remain available for explicit comparison.
