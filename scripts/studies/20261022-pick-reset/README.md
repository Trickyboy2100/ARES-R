# Stationary timing experiment, not a replacement golden Demo

`prepare_pick_reset_bundle.py` prepares only; it cannot send arm/gripper movement.
It retains explicit2026-10-22RC1 paths and an archived benchmark request used for
static planner initialization. Those dependencies must exist on the site host;
this is not yet a portable/general-task preparation entrypoint.
`--source-epoch` is frozen diagnostic replay, not fresh physical execution.

Native packaging: `scripts/package_pick_reset_timing.py --prepared DIR`.
Execution: canonical backend's explicitly authorized
`/api/operations/pick-reset-timing/start`; isolated candidate must be under
the canonical evidence root. No import, startup or browser refresh starts it.
Run-status: `/api/operations/run-status`; Stop: POST`/api/operations/stop`.
Physical emergency stop remains independent.

Current hardware blocker: right gripper fault0x10. No fault clear was sent.
See the implementation/timing report. No repeated automatic fault-clear/retry.
