# Center / GRASP planning-speed study — 2026-10-21

## Status and boundaries

Local-only work; no push. Golden Demo and coworker worktrees unchanged.
Right-arm return to center succeeded; no grasp, lift, gripper or base movement
was sent during the following study. Base was already at the recorded GRASP
return mark, so its route was not repeated. SLAM confidence was insufficient
to certify centimeter-level absolute position. The payload was **not held**.
Known object dimensions: 100mm wide, 180mm overall length; do not derive a held
object from its surrounding fixture before verified grasp.

Runtime: `/home/yikun/ARES-R-RC1-20261019`; WebUI 8775/backend 8776 restored.
No production FAST/QUALITY deadline, controller protection, physical speed,
site limit, TCP calibration or base route was relaxed. Benchmark requests use
isolated explicit profiles and a 3500s hang watchdog, not the product deadline.
No whole pre-base-motion execution package is ready yet.

## Fresh evidence

Root: `worklog/evidence/20261021-center-grasp-planner-study/` under RC1.
Frozen snapshot: `SCENE_d9f27c83fc0949f1a709bd0c3e843b4a`.
Pointcloud SHA256: `62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6`.
Fresh 5700 ID1 target BODY XYZ: `[0.8386349004,-0.1115597295,0.9907505300]m`.
55mm pregrasp XYZ: `[0.7837068613,-0.1142428911,0.9915938358]m`.
Current controller tool and template transform match, including TCP Z184.38mm.
Existing Demo-local -10deg TCP-local-Z compensation retained, not recalibrated.
World: 401 cuboids; active component spheres: 1647; gripper model opening40%.

## Measured bottlenecks and implemented changes

| Scope | Before | After | Qualification |
|---|---:|---:|---|
| Independent dense check, exact same 431 samples | 17.023s | 1.125 / 1.118s | Same limiting object/component, gap and decision; double-precision native CPU backend |
| Observed contact geometry build | 15.176s | 0.925 / 0.830 / 0.836s | Entire artifact and revision equal; indexed inclusive point query |
| Pregrasp-only preparation | 15.866s | 1.437s | Same captured epoch, new output directory; no contact/lift certification |
| Original scene observation | 15.475s | Not optimized here | Still dominates scan-to-plan |

`independent_path_validation.py`: request opt-in `NATIVE_CPU_V1`; default
`NUMPY_REFERENCE` remains. No validation removal, sample reduction or margin change.
`observed_contact_geometry.py`: cKDTree candidate query followed by the exact old
inclusive bounds filter; reference `indexed=False` retained.
`collision_refinement.py`: thin SVD fixes an existing dense-cloud NxN allocation.
The first diagnostic exposed an OOM; after correction the same diagnostic used
about120MiB peak RSS and0.93s. Server recovered; unrelated processes not killed.

### Actual GPU optimizer measurements

Same frozen world, goal branch and collision representation; no second warm-up
solve per request. These are request/solver times, **not click-to-motion times**.

Initial optimizer comparisons needed a **100mm diagnostic standoff** because
the original55mm coarse goal was rejected before solve. This did not modify the
golden55mm task:

| Profile | Warm request | Warm core solve |
|---|---:|---:|
| 25 iterations,1 trajectory seed,4 IK seeds,CUDA graph | 3.727s | 1.271s |
| 25 iterations,2/4,graph | 4.952s | ~2.47s |
| 50 iterations,2/4,graph | 7.291s | ~4.80s |
| 25 iterations,2/4,no graph | 5.028s | ~2.47s |
| Native refined plan_cspace,2/4 | 58.81s | 38.17s |

CUDA graph is not the main cause of the large observed differences. Iterations,
seed count, extra refinement and slow CPU checks matter. Cold initialization is
about10s plus import/capture/solve; persistent planner ownership must be kept.
These small matrices establish candidate profiles, not general robustness.

## Proven coarse-geometry disagreement at the actual55mm goal

Limiting primitive `observed_support_00_component_01_protruding`:
BODY center `[.795271,-.172928,.924806]`, dims about138×110×104mm, padding7mm.
Original coarse geometry gave NORMAL -21.20mm / FLIPPED -11.38mm gap.
Against the raw measured points, component OBB gaps **after the same padding**
were +27.56mm / +29.93mm. This is evidence against that abstraction, not evidence
that all unseen space or all future scenes are safe.

Diagnostic derived world replaced only that primitive with a point-enclosing
OBB, retaining every source point and padding. Original scene was not overwritten.
NORMAL and FLIPPED endpoints became +3.706mm / +3.172mm.
No obstacle deletion or production hard-coded ID filter was introduced.

On this **derived55mm** scene the25-iteration1/4 graph profile achieved:

- 11/11 successes: one cold24.332s and10 warm requests.
- Warm request p50 **3.561s**, p95 **3.646s**; core solve p50 **1.257s**.
- Three additional distinct random seeds: 3/3 successes, cold request
  20.768 /20.980 /21.988s. Changing seed reconstructs this runtime and therefore
  these are not warm measurements.
- Same frozen seed repeats are not independent scene trials.
- Passing pregrasp planning is not a full contact/lift or execution approval.

## Remaining full-chain issue: separate from collision and solve speed

Full-contact precheck fails numerically at the detected grasp endpoint:
NORMAL24.513mm /6.564deg; FLIPPED23.281mm /6.055deg residual.
Additional bounded multi-initialization without seed regularization reproduced
the residual. Both tend toward straight-elbow branches. This is not a proof of
mathematical unreachability, nor a reason to relax endpoint accuracy to25mm.
The same orientation at grasp+230mm has valid endpoint IK in this diagnostic.
Intermediate230mm path, level validation and payload collision were not thereby
validated. Current full pick cannot honestly be labeled ready.

Next focused investigation: compare live controller FK against pinned FK at
center and archived successful grasp samples; verify target/task-frame semantics
and compensation order; test bounded multi-IK rather than serial QUALITY retries.
Do not reinterpret an IK failure as cloud collision or repeatedly burn minutes
running an optimizer whose endpoint precondition already failed.

The frozen center SDK-vs-model check has now completed: translation discrepancy
2.052mm, rotation0.00387deg. This excludes a large global FK error **at center**,
not configuration-dependent error at the extended grasp. Evidence:
`model-sdk-center-comparison.json`.

## Prepare-all-before-base-transfer contract

From a stationary center, capture a fresh epoch and bind live start/tool/inactive
arm/camera/base revisions. Derive targets from current BODY detections, not old
absolute SLAM coordinates. Centimeter drift or<2deg yaw must be measured through
fresh target pose; they do not justify replaying an old exact trajectory.

Prepare together: center→pregrasp cuRobo, contact55mm, close/readback/verification
conditions, continuous230mm lift and HOLD. Check every stage before opening the
physical run. Persist an immutable bundle of geometry, timing, hashes and
dependencies. Close/verify is a branch: do not attach a payload before successful
grasp. If verification or actual state differs, invalidate dependent plans.
Base transfer is a scene-rebind boundary: place-side trajectories require fresh
observation after settled arrival; pre-base old-scene plans cannot certify them.
This contract is the next integration task, not a completed package this turn.

## Two-thread / parallel assessment

1. Low-risk immediately useful architecture: one owner for camera, one persistent
   GPU planner; prepare static models/planner during capture; async evidence
   writing during execution. Predictable resource locks and cancellation needed.
2. Pipeline CPU scene processing and GPU execution preparation where dependencies
   permit; never launch5700 and5000 competing structured-light captures blindly.
3. Plan future stages only against their declared expected state; bind/invalidate
   after close/verification/arrival rather than silently reuse stale worlds.
4. Base retreat after50mm lift, or arm stow during base motion, is not ordinary
   two-threading: requires time-synchronized BODY→world trajectory, whole-robot
   swept collision and shared resource/abort policy. Not enabled or commissioned.

## Evidence custody and tests

Mac private directory: `/Users/andyee/Documents/ChatGPT/local/site-private-20261021/`.
Captured study tar SHA256:
`f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8`.
SHA verified after transfer. Raw cloud references outside the study directory
were subsequently copied in `20261021-study-clouds.tar.gz`, SHA256
`206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60`.
This contains CAMERA/mm source, BODY cloud and manifest; the CAMERA source hash
was independently verified against the SceneSnapshot source SHA after transfer.
Pinned model/runtime dependencies must still be resolved for a portable replay.
Local targeted regression suite:34 tests passed. Site initial full suite:
782 tests, OK,1 skip (before uploading new regression tests); follow-up full suite
**786 tests, OK,1 skip**,11.501s, recorded in `tests-with-regressions.log`.
No robot execution was used by the test suite.

Diagnostic tools are under `scripts/studies/20261021-planner/`; no production
golden launcher replacement. No push and no automatic grasp execution.
