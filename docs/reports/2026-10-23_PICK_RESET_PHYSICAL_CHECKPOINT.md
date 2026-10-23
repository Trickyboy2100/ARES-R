# Stationary pick/reset physical checkpoint — 2026-10-23

## Outcome

ID1 detection succeeded after the operator adjusted the base. No base motion was commanded during these trials. The right arm executed pregrasp, contact, close and continuous 230 mm lift. The experiment then stopped at post-lift verification because parallel readbacks aged out while waiting for the scan. This is NOT a clean uninterrupted successful cycle.

After an explicit new instruction to return along the original path, the original validated reverse native geometry was used once: lower 230 mm, confirm original fixture TCP arrival within the existing 3 mm contract, release, retreat, return to the exact original center joints. Result: `RETURN_FROM_LIFT_COMPLETE`, reset complete. No new grasp, fresh collision-world validation, or general-purpose automatic fault recovery is claimed for this explicitly authorized original-path return.

Final BODY TCP: `[0.354850634, -0.077532529, 1.021135387] m`. Right controller error=0, in_position=true, Servo disable confirmed by each segment. Right gripper position=401, fault=0. The initial center position was `[0.354845519, -0.077534694, 1.021142417] m`.

## Attempts and software findings

- r3: fresh detection and all geometric/native preparation passed; native rejected before arm movement with transient controller error `4128769`. Later read-only status was zero. No clear-error command or controller gate change was made.
- r4: fresh scan/new trajectory. Pregrasp physically succeeded in 27.981 s, max/p95 tracking error 0.7274/0.7106 deg. Experimental arrival logging then failed because legacy `Live._settle` required an absent Scheme job. Fixed only the experimental runner: direct reuse of the unchanged arrival contract, with fault and cancellation checks. Golden runner unchanged.
- Recovered to the exact measured initial center through fresh-scene cuRobo, plan `PLAN_979d2f9512c0410b9eefd28a0a3cf698`; successful sender elapsed 30.292 s, max tracking 0.5968 deg. A preceding approximate Cartesian recovery request was abandoned; the named-pose orientation request failed hard validation. Neither of those rejected plans was executed.
- r5: successful physical pick/lift followed by verification timing failure. Gripper readbacks were all 36; scene delta removed 70.24% of the local source voxels; actual lift was 229.988 mm. Post-lift scene evidence passed. Timestamp freshness failed because the three samples preceded completion of the scan by more than five seconds. No freshness limit was relaxed. The acquisition scheduling issue remains to be fixed before another uninterrupted cycle.
- Explicit return-only entrypoint is restricted to the interrupted post-lift checkpoint, recorded lift arrival and Servo-disable proof, exact native hashes, current start match, unchanged inactive-arm joints/tool, active tool, stationary base, native controller/tracking protection, and fixture arrival before release. It has separate output/stop files and cannot rerun an existing return directory. It does not restart pick or clear faults. Backend owns the process and software stop.

## Preparation times (seconds)

| Stage | r3 | r4 | r5 |
| --- | ---: | ---: | ---: |
| Initialize-only, parallel with observation | 0.435 | 0.387 | 13.312 |
| Observation / scene | 18.886 | 15.373 | 16.225 |
| Contact geometry + IK | 1.857 | 1.789 | 1.878 |
| Pregrasp planner request | 8.660 | 2.885 | 8.263 |
| First-pick package | 0.250 | 0.261 | 0.249 |
| Lift + reverse geometry | 7.621 | 7.647 | 7.944 |
| Geometry preparation total | 37.306 | 27.986 | 34.590 |
| Native packaging (sum of segments) | 18.744 | 19.659 | 20.032 |

r4 reported cuRobo solve=1.1813 s, planning=1.2929 s, request-to-result=2.8503 s; independent validation=0.7425 s. r3/r5 planning samples were approximately 6.49/6.40 s, including first graph use after initialization. The generic recovery planner and this study use different runtime keys, so a resident process does not guarantee the task-specific graph is still warm. These are different fresh scenes, not a controlled same-scene parameter benchmark.

## Physical stage wall times

| Stage | r5 forward | Explicit original return |
| --- | ---: | ---: |
| Gripper status | 0.101 | 0.101 |
| Gripper 40% | 1.261 | — |
| Pregrasp / reset center | 31.370 | 31.366 |
| Contact / retreat | 15.834 | 15.829 |
| Close / release | 0.408 | 1.259 |
| Before-lift verification | 2.005 | — |
| Lift / lower 230 mm | 18.456 | 18.537 |

r5 stopped after 80.527 s. Explicit return elapsed 68.308 s, excluding the operator pause between the runs. Their sum is not an uninterrupted autonomous cycle benchmark. Prepared pure native motion durations totalled 99.52 s; per-stage orchestration/readback/settling added roughly five seconds to each arm stage. This is a measured optimization lead, not yet a proven breakdown of each individual overhead.

## Priorities for next speed study

1. Correct parallel readback scheduling: ensure a genuine fresh stable sample window is available when scene evidence completes; retain the five-second freshness rule. Do not pass an earlier timestamp as the current time.
2. Keep the task-specific planner and graph warm across requests; compare identical frozen scenes and separate core solve from end-to-end latency.
3. Profile the 15–19 s observation pipeline and 15–17 s forward lift native packaging. Native reverse reuse already costs only milliseconds.
4. Profile the recurring approximately five-second arm-stage overhead. Measure SDK connection/read/settle separately rather than removing arrival checks.
5. Scan/planner initialization overlap works; parallel readback/scene work exposed a real synchronization bug. Do not claim threads eliminate dependencies or authorize concurrent base/arm motion.

## Evidence and verification

Site roots: `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261023-pick-reset-r3`, `r4`, `r5` (each uses the full prefix). r5 `execution/` preserves the original failure; `return-execution/` preserves the later authorized successful return. The old failed records were not overwritten.

Experiment regression suite: 8 tests, 0.084 s, OK. No integration push. Golden first-pick script, roundtrip script, production configuration, route and controller protections were not modified.
