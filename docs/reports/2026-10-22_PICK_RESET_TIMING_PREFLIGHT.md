# Pick / reverse-reset timing preflight — 2026-10-22

## Requested cycle and actual result

Requested: fresh ID1 observation → pregrasp → grasp → continuous230mm lift →
reverse lower → release in original fixture → retreat to pregrasp → center.
Reset policy explicitly confirmed. Base motion was not requested or sent.
No arm or gripper movement was dispatched: the full contact endpoint failed
before GPU planning. This is a partial preflight, **not an executed cycle**.
No physical stage durations, grasp success or fastest full-cycle result can
honestly be reported yet. Existing physical speed settings were not changed.

## Services and integration correction

Host192.168.99.32 connected; both arms repeatedly reported error0, enabled,
in-position, no collision/estop/limit. Right arm near center. ID1/5000 available.
Isolated RC1 services8775/8776 were stopped after restart and were restored with
no demo auto-start. Original production services were left unchanged.

First capture did acquire a frame but failed to find its output: a shared camera
worker was running in `/home/yikun/ARES-R`, while RC1 sent a relative output
directory. Source fix: `_fast_capture()` resolves the caller output root before
sending it to the worker. Regression verifies an absolute path is transmitted.
The previous module was preserved at
`worklog/preservation/20261022-camera-path/epic_pointcloud.before.py` in RC1.
No camera worker was killed, calibration changed or controller reset issued.
Retry uses a separate epoch, leaving the failure evidence intact.

## Measured timings, successful fresh observation

| Stage | Measured seconds | Result |
|---|---:|---|
| Full observation transaction, before/after states +5700 +scene |14.9926|COMMITTED|
| Camera capture +canonical BODY cloud |2.7145|PASS|
| Network settle |0.5006|PASS|
| Read-only joint/FK audits |1.0911|PASS|
| Whole-robot geometry export |0.0973|PASS|
| Scene reconstruction |4.4699|PASS|
| Contact100mm-lift feasibility preparation |2.5343|FAIL at contact IK|
| cuRobo full-task solve |Not run|Endpoint prerequisite failed|
| Native packaging / physical stages / reset |Not run|Not an execution result|

Scene timings are contained within the observation time, not additive on top of
it. The remaining observation time includes5700/state/process/serialization work;
no individual5700 duration was recorded, so do not invent one by subtraction.
This precheck covers the legacy100mm prefix; it does not validate the complete
continuous230mm lift or reverse/reset path.

Fresh ID1 target BODY XYZ `[.8387466798,-.1154860248,.9905177600]m`.
Pregrasp `[.7838338940,-.1185154225,.9911570626]m`.
Lift230 endpoint XYZ `[.8387466798,-.1154860248,1.2205177600]m`.
NORMAL compensated controller-frame target RPY
`[-1.5825850174,-.1673733805,-2.2991189133]rad`.
These are planned targets, not physically reached endpoints.

## Why movement was not dispatched

At the current detected grasp pose, NORMAL residual23.645mm/6.347deg and FLIPPED
22.237mm/5.774deg. First contact failure occurs around knots3/26 and5/26.
This precedes collision/path planning: longer FAST/QUALITY solves do not fix it.

Independent **read-only** JAKA `kine_inverse`/`kine_forward` crosscheck:
pregrasp and lift endpoints return FK-consistent solutions (<1e-8m error).
For the grasp endpoint some SDK inverse responses return code0 but FK differs
from target by roughly260mm or more with two seeds. These are rejected as
invalid solutions; code0 alone is not a success criterion. No SDK IK result
was sent as a movement. This observation does not establish mathematical
unreachability or assign a vendor root cause without further investigation.

Frozen numerical sensitivity (no base or object movement):

| Virtual change | NORMAL position error | FLIPPED position error |
|---|---:|---:|
| Current target |23.646mm|22.236mm|
| Target40mm nearer BODY-X |5.492mm|3.833mm|
| Target60mm nearer BODY-X |0.041mm|0.012mm|
| Remove -10deg compensation only |24.089mm|21.763mm|

60mm-nearer target passes endpoint IK for both branches. This is a candidate
for a fresh physical station/target test, **not authorization or collision/path
validation**. No station registry, base route, TCP compensation or target was
silently changed. A small real base-forward adjustment requires explicit approval
and a new stationary observation before reusing the result.

## Fastest stable strategy to test once the endpoint is resolved

Retain one camera owner and one persistent planner. Start from the existing
measured25-iteration1-trajectory/4-IK-seed graph profile; preserve fallbacks as
separate measurements. Yesterday's derived-scene warm core1.26s /request3.56s
is historical evidence, not a completed current-scene cycle measurement.

Before grasp dispatch, bind and prepare all forward and reset paths:
pregrasp cuRobo; contact; lift230; reverse lowering with the same held-object
transform; release; empty-gripper retreat; return-center cuRobo. Reverse joint
path alone is not approval: include payload/environment and endpoint state
checks. Release is only after verified fixture arrival; detach only after open
readback. If a segment or grasp verification fails, stop without auto-release.
Precomputing avoids an expensive surprise solve while holding the object.

Instrument monotonic stage begin/end for capture, detection, model build,
endpointIK, world update, GPU solve, independent check, retiming, sender validate,
each physical segment, delayed feedback, grasp verification, reset and evidence
flush. Separate warm/cold, CPU/GPU, successes/failures; report p50/p95 and actual
elapsed time rather than adding overlapping concurrent spans.

## Two-thread assessment

Necessary now: camera ownership/arbitration, nonblocking task/cancel handling,
and async evidence I/O. Useful overlap: planner import/init and static model
preparation during scanning; up to about10s cold initialization could be hidden
under a roughly15s observation, but this saving was not measured this run.
Warm runs will benefit less. Scene reconstruction and solve depend on scan
output; launching them simultaneously does not remove that dependency.

Do not run5700/5000 concurrent structured-light triggers without arbitration.
Do not execute a reverse descent until grasp/actual pose is confirmed. Base+arm
simultaneous physical motion is not needed for this stationary benchmark and
would require a moving-frame swept-world model, not just two Python threads.

## Evidence and code status

RC1 evidence: `worklog/evidence/20261022-pick-reset-timing/`.
Mac private copy: `/Users/andyee/Documents/ChatGPT/local/site-private-20261022/`.
Study archive SHA256:
`181be8fdc632fe143fcb55353ecf10a47363310c8d0900dce2acc5d4b9385d7d`.
Verified after transfer. Cloud binaries referenced by scene manifests are outside
this archive; this archive alone is not a portable whole-scene replay bundle.
Capture-path regression1/1 passed. No automatic push.
