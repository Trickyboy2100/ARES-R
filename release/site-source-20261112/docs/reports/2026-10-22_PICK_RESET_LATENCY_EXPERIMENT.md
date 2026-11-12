# Pick/reset latency experiment — 2026-10-22

## Outcome

Software preparation completed with real current-scene cuRobo, contact55mm,
continuous230mm loaded lift, exact reverse lowering/retreat and return-center
native files. Physical launch was attempted once. It stopped at GRIPPER40:
command400 was acknowledged but position remained992 and a real gripper internal
communication fault0x10 was subsequently read. **No arm trajectory was executed,
no object grasped, no230mm physical lift or reset completed.**
The task remains incomplete; prepared durations are not actual motion timings.
No base movement occurred in this experiment (the separately approved forward60
adjustment remains in effect). No push; golden first-pick entrypoint unchanged.

## Actual hardware block, not another planner rejection

Runtime-status response: `ee16010841041016e003e80342`.
Vendor EG2-4XX manual2.4.11 decodes: run_state4, fault0x10(bit4 internal
communication), temperature22C, position992, force setting1000g.
Position command400 ACK: `ee160102540158`.
Opening parameter read: `ee16010513e803000004` (max1000/min0).
This is not an opening-tolerance problem; increasing tolerance to accept992
would misrepresent the required40% geometry.

Official source:
https://inspire-robots.com/d/file/p/2023/08-24/%E5%9B%A0%E6%97%B6%E6%9C%BA%E5%99%A8%E4%BA%BA%E4%BC%BA%E6%9C%8D%E7%94%B5%E5%8A%A8%E5%A4%B9%E7%88%AA--%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8CV1.06cn.pdf

A one-time documented0x17 recovery was proposed, but execution review rejected
the separate hardware fault-reset operation without explicit operator approval.
**Fault-clear commands sent:0.** No workaround, error masking, force change or
automatic repeated clear was performed. Clearance can resume the previously
requested400 closing command, so on-site hands must remain clear.

Read-only `gripper_direct_once.py status` and fault-first preflight are now
implemented. Unknown fault/checksum/device responses reject rather than guess.
Future preparation should reject this fault before expensive scanning/planning.

## Implemented software corrections

1. Canonical opt-in observed OBB construction retains all measured source points
   and inflation, with WorldModel/SceneSnapshot/SceneCompiler provenance.
   Compiler now honors each object's own quaternion, not only arm-base rotation.
   Identity-object behavior remains geometrically unchanged. Encoding revisionV3.
2. Contact-only opt-in measured-protrusion occupancyV2 preserves every source
   point in2mm cells with the original inflation; it does not delete obstacles.
   This resolves empty-space bridges inside irregular support's solid envelope.
   Unknown/unmeasured volume and arm/inactive-arm checks remain hard.
   Actual first attributed hard-box contact had raw-point clearance about19.7mm
   after padding; lift-start pair about21.9mm. No default/global bypass enabled.
3. Contact endpoint was unnecessarily solved again at lift knot0, causing about
   0.0184rad joint discontinuity. It now reuses the already validated contact
   endpoint/result exactly; no continuity tolerance increased.
4. Explicit `initialize_only` planner request loads robot/GPU resources with
   **zero optimizer solves**, no trajectory and execution-disabled result.
5. Optional versioned request capacity floor keeps512/768 scene-count changes
   from recycling a hot planner. This experiment uses768; robot/world content
   and interpolation cadence are unchanged. Resource-budget checks still apply.
6. Reset native files reverse exactly the validated forward samples. Native
   hashes/endpoints are checked; dynamics are symmetric. Valid only for the same
   stationary scene, held payload during lower and released/open40 during retreat.
   No replanning or second cubic fit introduces a different return path.
7. Canonical backend owns the experimental subprocess and blocks concurrent
   base/arm operations. Existing Stop writes its cancellation latch and aborts
   motion; no auto-start/resume. Only one dispatch per prepared execution folder.
   Runtime sends prepared bytes, not a newly designed waypoint/trajectory.

## Timing evidence

All seconds below are measured software stages unless explicitly labeled planned.

| Stage | Evidence | Seconds |
|---|---|---:|
| Cold resource initialization, no solve |R6, concurrent with scan|13.137|
| Fresh observation / scene, with opt-in OBB |R6|18.124|
| Contact geometry +IK |R6|2.433|
| First formal cuRobo request, including graph capture/validation |R6|10.170|
| First-pick package |R6|0.378|
|230mm loaded lift +reverse geometry checks |R6|9.015|
| Geometry preparation wall |R6|40.121|
| Subsequent formal pregrasp request |R3 frozen same stationary scene|4.478|
| All six native files |R6|32.827|
| Reverse lower native-file construction |R6|0.00170|
| Reverse retreat native-file construction |R6|0.00171|
| Reverse center native-file construction |R6|0.00266|
| Physical-launch failure before arm motion |R6 execution|4.530|

The initial13.137s span is overlapped by scanning, not added after18.124s.
The serial sum of those stages is a model, not an independent serial trial.
R4 independently retimed/revalidated all reverse paths: lower27.714s,
retreat3.312s, center3.365s. R6 reuses exact reverse samples in about6ms.
Different fresh epochs, so do not claim a controlled whole-cycle A/B comparison.
Forward loaded cubic verification remains costly (~26s native packaging).

### Planned native motion, not physically measured

| Segment | Duration(s) | Effective peak speed(rad/s) |
|---|---:|---:|
|Center→pregrasp|33.28|0.09981|
|Contact55mm|23.60|0.04838|
|Lift230mm|19.44|0.09703|
|Reverse lower230mm|19.44|0.09703|
|Release→retreat|23.60|0.04838|
|Return initial center|33.28|0.09981|

Sum152.64s excludes all verification/I/O/settle waits.
Named0.20 profile is limited by actual site/sender constraints to about0.10.
No site ceiling, tracking stop, controller collision/limit/estop was raised.
Contact remains the existing0.05 configured ceiling. Actual stage speed
commissioning and fastest successful physical cycle are still unmeasured.

## Two-thread findings and next acceleration order

Already demonstrated: camera/scene and zero-solve planner initialization overlap.
Implemented for the future execution: post-lift delayed gripper reads overlap
post-lift scene scan; **not physically reached**, so no measured saving claimed.
Evidence may write asynchronously, but command/stop/arrival records must remain
durable before dependent physical actions; do not blanket-background all logs.

Recommended next order once hardware is healthy:

1. Complete one unchanged-limit physical pick/replace/reset baseline and inspect
   tracking max/p95/RMS, actual payload verification, fixture arrival and TCPs.
2. Compare contact0.05 vs0.075/0.10 only within measured/current site limits,
   using isolated experiment profiles and unchanged fault protections.
3. Retain one initialized planner across scans; measure capacity-floor benefit
   on repeated fresh scenes and distinguish one-time graph capture.
4. Cache exact geometry proofs by path+scene+model+tool hash; reuse invariant
   source/reverse checks, but revalidate any geometrically altered cubic curve.
   Source lift and retimed lift currently repeat expensive raw occupancy work.
5. Replace full post-lift world rebuild with an audited local verification path
   if15cm scene-delta equivalence is proven; this is not yet implemented.
6. Maintain camera single ownership:5700/5000 share hardware; do not blindly
   parallel-trigger structured light. Do not start a physical next stage before
   its state/scene dependencies and cancellation behavior are satisfied.

Base+arm concurrent physical motion is unnecessary for this stationary test and
remains uncommissioned. Two threads cannot remove scan→scene→plan dependencies.

## Files, tests and preservation

- Branch:`codex/pick-reset-latency-20261022`; no push.
- Software commits:`a1f8811` geometry/seam;`07e4e38` runtime/timing/parallel init.
- Entry:`scripts/run_pick_reset_timing.py`; native prep:
  `scripts/package_pick_reset_timing.py`.
- Historical preparation harness:`scripts/studies/20261022-pick-reset/`.
  Its static initialization dependency is site-specific, not portable production.
- Actual evidence:`.32:/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261022-pick-reset-overlap-r6/`.
- Failure:`execution/status.json`,`execution/events.json`,gripper readbacks.
- Pre-edit backups:`worklog/preservation/20261022-canonical-obb/` in RC1.
- Site full suite798 tests passed,1 skip before last read-status addition;
  final local targeted28 tests passed after status parsing/runner guard addition.

Raw scene datasets remain private, outside Git. No original first-pick script,
station registry, base route, controller TCP or production parameter file was
modified. Actual physical acceptance remains blocked by the gripper fault.
