# PLACE preparation ready — awaiting new motion confirmation

No robot, gripper or base movement was dispatched in this preparation. The original failed Demo remains FAULT at MOVE_PRELAND; it was not reset, rewritten or automatically resumed.

## Scoped model correction

Operator-requested exposed payload dimensions: **160×100×105.491 mm**. Height, original object center and rotation, and existing 4 mm padding are retained. A separate 20×100×105.491 mm rear clamped segment remains in the shared collision enclosure; it was not silently removed from collision geometry. The visible main object dimensions are 160×100 mm, but the common collision enclosure also accounts for that clamped segment.

The original 212×209×105 mm cluster-derived model is preserved separately. The initial experimental grasp-axis reanchoring produced an invalid goal and remains preserved as a failed candidate; it is **not selected**. Selected V2 changes size while preserving the source center and rotation, as requested. The reported 20 mm rear grasp measurement is recorded; no new unrequested 80 mm center shift is applied.

This is a Demo-specific operator-sized correction, not a claim that generic perception segmentation or future arbitrary-object modeling is solved. The default/golden first-pick implementation, original .32 working tree, controller tool, calibration and physical speed limits are unchanged. Current Demo job parameters and historical package remain immutable; a separate recovery preview binds the new geometry.

## Planning and validation

- Fresh ID3 and fresh stationary pointcloud SceneSnapshot: `SCENE_6110421b0c1a4369b4a9c10b3c820594`.
- Current→preland: first FAST attempt succeeded, cuRobo direct start→goal, no waypoint and no environment-collision disable.
- Independent dense check: 267 samples, collision-free in the modeled scene; minimum modeled clearance approximately **16.13 mm**. This is modeled, not a measured real-world clearance guarantee.
- Demo horizontal/−10° compensation check passed.
- Continuous BODY Z−50 mm descent: geometry, contact-window policy, native retiming and sender format validation passed. Contact permissions remain bounded to the existing lower-middle placement corridor.
- Native preland duration **18.96 s**; native descent duration **7.12 s**. These are planned sender durations, not measured execution results.
- cuRobo reported solve **3.120 s**; GPU planner call **4.017 s**; request/result **8.221 s**; complete fresh preparation plus descent packaging **28.334 s**.
- Full tests: **782 tests, OK (1 skipped)**, 11.529 s.

Preland BODY XYZ: `[0.760529826, -0.016810318, 1.214012924]` m.

After descending 50 mm: approximately `[0.760529826, -0.016810318, 1.164012924]` m, with the validated endpoint tolerance and compensated orientation retained.

Prepared remaining sequence:

`current→preland → descend50mm → release400 → detach → base back320mm → left810mm → forward400mm → GRASP`.

No stow or second pick is included. Before any dispatch, a **new operator confirmation**, actual-start/tool/base/inactive-arm checks, and candidate expiry/state revalidation are required. An expired or changed-state candidate is not automatically reusable.

## Exact selected artifacts

Plan: `PLAN_632f7aae64444033b448dbb7786617cb`.

Trajectory: `sha256:4f00cf5c387c4828af17b24caf227423ed019cb4fd0cec7818acdfdc9cd63924`.

Attachment: `sha256:aaf7b8c837f334b377e741b88c1963877b72160e3a7594acc3332098f1549eec`.

Prepared manifest: `e78a3e7fea66c1204282c5492a1e2203f31e21b13bff78891dd8adff336262d9`.

Server directory: `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261019-v17-payload160x100-place-preparation-v2/`.

Local copies: `REPORT.json`, `attachment.json`, `descent-geometry-proof.json`, `prepared-placement-manifest.json`, `full-tests.log` alongside this report.
