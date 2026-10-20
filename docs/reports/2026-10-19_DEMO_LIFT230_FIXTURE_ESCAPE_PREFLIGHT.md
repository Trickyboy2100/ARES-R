# Demo lift230 fixture escape preflight

Scope: isolated `/home/yikun/ARES-R-RC1-20261019` only. No physical motion,
no production repository/golden changes and no push.

Fresh Pixel Pro scene: `SCENE_91e06fd3a1b64086b0a190253d60ca25`.
Pointcloud SHA256: `c85ea31707a40c09026902c017a5d4c324e32d190fa83e4aca07e7bea892420a`.

## Corrections

SceneCompiler quaternion conversion encoded the inverse rotation. Active
rotation round-trip tests reproduced the error and now pass. The same BODY
snapshot was recompiled under `SCENE_COMPILER_ACTIVE_WXYZ_V2`, without editing
camera calibration, raw pointcloud or original evidence.

The remaining lift conflict was with the lower grasp fixture, not an overhead
object. The operator identified it from the overlay. Only this Demo's lift230
accepts tool/payload departure from observed fixture boxes wholly contained in
BODY bounds `[.89,-.30,.91]` to `[.97,-.08,.998]` m. Contact must not deepen and
must be fully separated at the end. No obstacle is deleted. Full link/world
and non-adjacent self checks remain hard, including against the fixture.
Other world/inactive-arm checks remain hard. The exception expires after lift;
free-space planning, place and other demos do not inherit it.

## Result

`LIFT230_DEMO_PRECHECK_PASS=YES`. BODY lift 229.99998 mm, one native stream.
Estimated duration 14.72 s at existing effective site ceilings. Compensated
physical-level reference maximum deviation 1.340 degrees (limit 3 degrees).
Installed sender `validate-supervised-path` passed, without sending motion.
Full regression: 750 tests, one skipped, all remaining passed.

Evidence: `worklog/evidence/20261019-lift230-fresh-rescan-audit-no-motion/rotation-corrected/fixture-escape-preflight-v2/REPORT.json`
and `native-audit.json`, `native-validate.log`, `lift230.native.txt` in the same
directory. These are diagnostic artifacts, not an execution lease.

`FULL_CYCLE_READY=NO`: this is lift-only validation, not a full-cycle replay or
commissioning. The prior cache start fault/stop latch has not been cleared.
The latest fresh target differed from the cached target by 3.784 mm, exceeding
the cache's 1.5 mm bound. No target tolerance or controller protection was raised.
