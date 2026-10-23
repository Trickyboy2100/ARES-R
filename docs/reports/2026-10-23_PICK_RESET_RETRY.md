# Pick/reset retry — 2026-10-23

## Actual outcome

Connected to 192.168.99.32 at approximately 11:45 CST. No base, arm or gripper movement was dispatched. No gripper fault-clear command was sent.

Right gripper read-only status: fault=0, temperature=38 C, position=994. Yesterday's hardware fault was not present at this reading; its cause/resolution is not established.

Recovered the isolated RC1 services on ports 8775/8776. All three recorded old PIDs had exited; ports were free and the planner socket refused connections. Old service manifest and socket were renamed and retained, not deleted. Production services were not changed. Starting these services does not start/resume a demo.

Corrected indentation in `scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py`. Added a parse-only regression test, without importing/executing the hardware preparation entrypoint.

## Fresh observations and measured times

Evidence root on site: `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/`.

| Stage | r1 | r2 |
| --- | ---: | ---: |
| Gripper read-only preflight | 0.0214 s | 0.0326 s |
| Planner initialize-only, no solve | 15.4704 s | 0.4386 s |
| Observation attempt | 5.6721 s | 2.7804 s |
| Whole preparation attempt | 15.5005 s | 2.8159 s |

Directories: `20261023-pick-reset-r1`, `20261023-pick-reset-r2`.

Both ID1 detections returned exactly `000,3020` (no detected result), pose=null. The observation transaction correctly did not commit a scene. No planning solve, native packaging, grasp, lift or reset occurred. These times are NOT successful scan-to-trajectory times or motion times.

Planner initialization was already running concurrently with observation. The second initialize-only request reused the resident runtime. 0.4386 s measures readiness, not cuRobo solve latency. Since observation failed, it did not produce usable overlap-throughput or full-cycle evidence.

Read-only right TCP BODY position before preparation: `[0.354845519, -0.077534694, 1.021142417] m`; tool ID=1, controller error=0, enabled=true, in_position=true. No post-motion endpoint exists because no movement occurred. Base reported IDLE; its current SLAM reading differed from the previous day's record, so the current scene was not assumed equivalent and no old trajectory was reused.

## Next action / timing study boundary

Confirm a tray is seated at the pickup fixture and visible to Epic right-arm ID1. Obtain a successful fresh ID1 pose, then regenerate the full candidate, native proofs and hashes before starting the supervised stationary pick/reset trial. No additional base motion is authorized by this retry.

Actual physical stage timing, faster contact-speed commissioning, and post-lift readback/scan overlap remain unmeasured. The previous prepared native durations are predictions, not successful physical cycle results. The golden demo and production settings remain unchanged.

## Verification

Local preparation entrypoint compiles. The system Mac Python lacks numpy, so its authorization-suite import fails before tests run. In the existing site Python environment, the authorization and parse-regression suite passed: 3 tests, 0.004 s, OK. No motion was involved.
