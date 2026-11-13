# Demo01 Turbo physical test V1

Independent ROS Action `/ares_r/center_restore_turbo`, same CenterRestore message ABI.
One empty-hand right-arm test: current → center → pinned saved right-front-high pose.
The accepted `/ares_r/center_restore` service and its clients are unchanged.

Uses current canonical HTTP motion APIs with FAST-only single pass, fresh scene, existing dense validation and ARC_LENGTH_EXACT_V1 native retiming. No shared backend files or global parameters were modified. There is no automatic start or resume. This isolated test runner is not yet the production shared task scheduler; concurrent callers must be excluded during testing.

The frozen-preview native CPU independent validator and speculative CPU/GPU pipeline are NOT enabled by this physical test. This run does not certify a full parallel Turbo pipeline.

Site directory: `/home/yikun/ARES-R-DEMO01-TURBO-PHYSICAL-20261113`.
ROS node: `turbo_node.py`; client: `turbo_client.py --execute`.
Original workspace message types must be sourced. Cancel through the ROS Action; software stop does not replace physical E-stop.

Evidence: `worklog/evidence/2026-11-13-demo01-turbo-physical/timing-summary.json`.
2026-11-13 result: CENTER_RESTORE_COMPLETED, 48.359 s, one actual movement because center was already reached. This is not a full two-movement roundtrip benchmark.
