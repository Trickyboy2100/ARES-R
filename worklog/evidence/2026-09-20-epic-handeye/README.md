# Epic dual-arm hand-eye calibration UI evidence

The two JSON files in this directory are faithful transcriptions of the Epic Pro
"view calibration result" screenshots. They preserve the per-arm reprojection
errors, translation, rotation vector, and 4x4 matrix while the original
vendor-exported configuration files remain unavailable.

Mapping confirmed by the ARES-R Epic profiles:

- `jaka左臂`: `space_id=1`, camera 1 (`PixelSerial`)
- `jaka右臂`: `space_id=2`, camera 1 (`PixelSerial`)

The right-arm values exactly match the earlier evidence file
`worklog/evidence/2026-09-18-epic-frame/handeye-right-20260918.json`.

These records are `EVIDENCE_ONLY`. Before writing either matrix into a
production transform chain, independently verify whether the Epic matrix is
`T_robot_base_camera` or its inverse and validate it with a board-pose chain.
