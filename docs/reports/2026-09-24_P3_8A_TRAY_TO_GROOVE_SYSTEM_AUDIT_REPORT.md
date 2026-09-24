# P3.8A — Tray→Groove system/interface audit report

Date: 2026-09-24  
Branch: `feat/e2e-v0-integration-20260917`  
Baseline: `d19cea78ffe3664fbf36423b6a6f80f371918de5`  
Scope: AMR and camera audit only; no JAKA/ServoJ or gripper motion.

## 1. Executive result

```text
HW_STATE_AUDIT = PASS
NO_ARM_MOTION_SENT = YES
NO_GRIPPER_MOTION_SENT = YES

AMR_EFFECTIVE_INTERFACE_VERIFIED = PARTIAL
PICK_BASE_POSE_V1_RECORDED = YES_RELATIVE_PROVENANCE
RIGHT_PICK_5700_MAPPING_VERIFIED = YES
RIGHT_PICK_DETECTION_REPEATABLE = YES
RIGHT_PICK_BODY_TARGET_READY = CANDIDATE_NOT_EPOCH_BOUND
PREGRASP_INTERFACE_READY = NO
CONTACT_TARGET_POLICY_AUDITED = YES_GAP_CONFIRMED
RIGHT_GRIPPER_PERCENT_MAPPING_READY = YES
LOCAL_TCP_SCENE_DELTA_READY = NO
ATTACHED_OBJECT_PIPELINE_READY = NO
LIFT_VISIBILITY_CLEAR_PLAN_READY = NO
PLACE_BASE_POSE_V1_RECORDED = YES_RELATIVE_PROVENANCE
RIGHT_PLACE_RIGHTMOST_5700_MAPPING_VERIFIED = NO
RIGHT_PLACE_RIGHTMOST_POSE_SEMANTICS_VERIFIED = NO
RIGHT_PLACE_RIGHTMOST_PROFILE_COMMISSIONABLE = NO
PLACEMENT_VERTICAL_PLAN_READY = NO
LEFT_HOLD_CURRENT_FEASIBLE = YES_PLANNING_ONLY
LEFT_CLEARANCE_UP_NEEDED = NO_FOR_FIRST_RIGHT_ONLY_DEMO
DUAL_ARM_CONCURRENT_EXECUTION_READY = NO
SKILL_SCHEME_AUDIT_READY = YES
READY_FOR_P3_8B_PLANNING_ONLY_SCHEME = NO
```

P3.8B is blocked by five production boundaries: reliable AMR completion, one-epoch 5700/pointcloud ingestion, exact rightmost-placement profile semantics, bounded target-contact planning, and carried-object collision geometry.

## 2. Baseline preservation and tests

- `.32` started and ended on integration HEAD `d19cea78`.
- GitHub queue identifies the same canonical HEAD.
- The pre-existing coworker changes were not reset, reverted or mixed into this audit. They include the AMR yaw degree fix and the Terminal-exit gripper-close fix.
- Preservation artifacts:
  - `worklog/evidence/2026-09-24-p3-8a-system-audit/preservation/status_before.txt`
  - `worklog/evidence/2026-09-24-p3-8a-system-audit/preservation/coworker_amr_gripper_exit.patch`
  - `worklog/evidence/2026-09-24-p3-8a-system-audit/preservation/git_baseline.txt`
- Full baseline test result: `460 tests OK (skipped=1)`.
- WebUI was listening on `0.0.0.0:8765`; persistent cuRobo worker process was present at `/tmp/ares_r_curobo_planner.sock`.

## 3. Read-only hardware snapshot

Evidence: `worklog/evidence/2026-09-24-p3-8a-system-audit/origin/hardware_state.json`.

| Item | Result |
|---|---|
| Left JAKA | Mini2 config, SDK V2.1.5, error 0, powered/enabled, no e-stop/limit/collision, tool 2 |
| Right JAKA | Mini2 config, SDK V2.1.5, error 0, powered/enabled, no e-stop/limit/collision, tool 1 |
| Right controller TCP | `[-3.013, -4.790, 184.380 mm, -0.04356, 0.00166, 1.54008 rad]` |
| Left gripper | raw `992,992,992` |
| Right gripper | raw `992,992,992` |
| AMR | map `831` / id `379`, battery 100%, charge false |
| Epic 5700 | reachable |
| Pixel Pro 5000 | reachable |

The first gripper read under system Python failed because `pyserial` is absent there. The commissioned `dope3.8` environment then returned stable read-only values. No `0x54` movement frame was sent.

Terminal cleanup was audited in `src/ares_r/cli.py`. Grippers are correctly absent from resource cleanup, so quitting Terminal does not invoke the motion-bearing `SerialGripper.close()` method. This fix remains in the preserved coworker dirty patch and is not yet part of canonical HEAD.

## 4. Effective AMR interface and field motion

Effective `.32` implementation:

```text
x+ = forward
x- = backward
y+ = left
y- = right
orientation = degrees
negative yaw = clockwise
maxAngularspeed = rad/s
collisiondetection = 1 (always)
stop = GET /control/stop
```

### 4.1 Critical completion-semantic finding

`POST /control/move/relative` returns an accepted task immediately (`status=3`). During real translation, `/robot/status.state.current.state` remained `IDLE` for every sample. Map localization also drifted by centimetres and roughly 0.2–1.0 degrees while stationary.

Therefore:

- `/task/state`, response `status=3`, and `/robot/status ... IDLE` are not arrival proofs;
- current `SceneAwareBase._motion()` marks `base_settled()` immediately after request acceptance, before physical completion;
- `base_stationarity()` can return `stationary=true` while `map_pose_stable=false` and cannot by itself establish precision arrival;
- future Scheme navigation requires an observation-based settle predicate, such as stable external landmark/pointcloud registration plus unchanged task/log marker.

The first audit request was immediately stopped after asynchronous acceptance and was correctly classified as not a valid pickup pose. Evidence: `pick_base_move.json`.

### 4.2 PICK_BASE_POSE_V1

Valid audit movement:

```text
relative command: x=0.00 m, y=+0.30 m, yaw=0 deg
linear speed: 0.10 m/s
collision detection: enabled
```

The AMR state label stayed `IDLE`, but the map observation changed by approximately 0.28 m laterally and the static Epic target shifted by approximately 0.255 m in the expected rigid direction. This is sufficient to record a relative, provenance-bound audit pose, but not a high-accuracy absolute map pose.

Evidence:

- `worklog/evidence/2026-09-24-p3-8a-system-audit/pick_base_move_v2.json`
- scene `SCENE_c5bc3ac071204ceca8f4c615e464b9a0`
- pointcloud SHA `b9bc6edd446919b859032d16d8a5371d1e738e7f9f1ee241abdfdcdfae836171`

### 4.3 PLACE_BASE_POSE_V1

Valid audit movement from the pickup-side pose:

```text
relative command: x=0.00 m, y=-0.40 m, yaw=0 deg
linear speed: 0.10 m/s
collision detection: enabled
```

Evidence:

- `worklog/evidence/2026-09-24-p3-8a-system-audit/place_base_move.json`
- scene `SCENE_9cd60a2a60674e099ea7ad10d8e1c2ef`
- pointcloud SHA `a083462c14e05c5e27fd4347b7071b7aa328b37347a11c9b5aa2bc64b2239e2e`

### 4.4 Return audit

The inverse net command `y=+0.10 m` was issued, stopped and rescanned. The final right-pick target remained approximately 45 mm from the original target position. Because AMR map localization is not precision-trusted, the report does not claim an exact return to origin.

Evidence:

- `worklog/evidence/2026-09-24-p3-8a-system-audit/return_origin.json`
- `worklog/evidence/2026-09-24-epic-repeatability/p38a-right-pick-return-origin.json`
- final scene `SCENE_8d9e465724074f9ba457ae119760af4a`

## 5. Epic 5700 audit

### 5.1 Right material-pick profile

Verified mapping:

```text
profile: right_pick
command: 320,2,1,1,1,0
space=2, object=1, camera=1
frame: right_arm_base_candidate
orientation: ZYX
approach axis: +z
state: COMMISSIONED
```

At PICK_BASE_POSE_V1, three detections had maximum pairwise position difference `0.474 mm` and rotation difference `0.3745 deg`. The mean arm-base pose was:

```text
[0.619977, -0.341213, -0.212219 m,
 1.563830, -0.006148, 0.763408 rad]
```

Using the fixed right-arm base→BODY transform, the mean BODY position was:

```text
[0.679664, -0.002884, 0.987781] m
```

Evidence:

- `worklog/evidence/2026-09-24-epic-repeatability/p38a-right-pick-pick-base-v2.json`
- `worklog/evidence/2026-09-24-p3-8a-system-audit/pose_semantics_analysis.json`

Repeatability is verified. Execution readiness is not: the live 5700 request ID is not currently committed into the same `ObservationEpoch` as the Pixel Pro scene, and the detected pose's task-reference offset remains a semantic rather than surface-contact pose.

### 5.2 Rightmost placement candidate

Current configured `right_place` is `320,2,2,1,1,0`, but object 2 tracked the same high target family as the pick target and intermittently returned `000,3017`. It is not supported as “物料放置最右点”.

Object 3 (`320,2,3,1,1,0`) produced a stable lower candidate. At PLACE_BASE_POSE_V1 its mean was:

```text
arm base: [0.576155, -0.273826, -0.344792 m,
           1.568304, 3.133913, 0.789384 rad]
BODY xyz: [0.601027, 0.013779, 0.855208] m
```

This agrees with the separate 2026-09-21 50-sample object-3 evidence and is the stronger groove/rightmost candidate. However, 5700 does not expose the Epic project flow name. Euler/axis hypothesis testing can produce a near-vertical axis, but it cannot prove the vendor's intended orientation convention or contact axis. No profile was silently commissioned.

Evidence:

- `worklog/evidence/2026-09-24-p3-8a-system-audit/right_place_at_place_base.json`
- `worklog/evidence/2026-09-24-p3-8a-system-audit/pose_semantics_analysis.json`
- `worklog/evidence/2026-09-21-epic-grasp-probe/epic-object3-rot30-50.json`

Smallest next action: export/screenshot the Epic UI solution mapping proving “物料放置最右点 → space 2/object 3/camera 1”, then validate its pose axes against the board/tool chain and observed groove geometry.

## 6. Pregrasp and contact boundary

Requested commissioning candidates are `0.03 / 0.04 / 0.05 m`. Current `build_grasp_plan()` does not accept a task-level distance; it reads hidden profile value `right_pick.grasp.approach_m=0.06 m`. Consequently the three requested candidates cannot be compared through the production interface without changing code/config.

The larger blocker is provenance: `ObservationEpoch` has `detection_ids`, but `LocalSceneService.build_live_planning_scene()` currently commits the pointcloud scene without the live Epic detection. `grasp_plan.prepare()` correctly refuses direct Epic→cuRobo input. This prevents a truthful same-epoch pregrasp plan in P3.8A.

The current SceneCompiler moves every `TARGET` entirely out of collision cuboids for the whole free-space plan. That behavior is insufficient for final contact:

- target identity is retained only as metadata;
- there is no bounded final-approach corridor;
- there is no allowed tool-target contact pair;
- there is no guarantee that arm links remain hard against the target while only the tool pair is relaxed.

`CONTACT_TARGET_POLICY_AUDITED=YES` therefore means the boundary was inspected and the implementation gap was proven, not that contact execution is ready.

## 7. Gripper audit

Effective mapping:

```text
0 raw = closed direction
1000 raw = open direction
percent -> round(min + percent/100 * (max-min))
50% = 500
40% = 400
closed = 0
20% = 200
```

Readback tolerance support exists at the Terminal command layer (target ±10), but `SerialGripper.has_object()` is only `position() > min_position`. It cannot distinguish a held object from an incompletely closed or stalled gripper.

`GRASP_VERIFICATION_GAP`: no current/force signal; future verification must combine post-close readback, delayed repeat stability, post-lift persistence and visual/pointcloud evidence.

Evidence: `worklog/evidence/2026-09-24-p3-8a-system-audit/gripper_readonly.json`.

## 8. Scene delta and attached-object audit

### Local TCP scene delta

No generic TCP-centered pre/post observation comparator exists. Existing pointcloud cleanup and decomposition can supply primitives, but there is no API producing `PASS / CHANGED_EXPECTED / CHANGED_UNEXPECTED / UNKNOWN` for a configurable `0.10–0.20 m` neighborhood.

### Attached object

`WorldModel` defines immutable `AttachedObject`, `attach()` and `detach()`, and attachment changes invalidate snapshots. This is a valid data-model foundation. The live planning path is incomplete:

- `MotionConstraints` passes only `attached_object_revision`;
- `PersistentCuroboPlanner` does not compile attached geometry into the moving robot model;
- SafetyKernel can require an `attached_object` geometry sample, but no complete production producer is connected here;
- a detected cluster is not yet converted into conservative `tcp_to_object + collision_geometry` with lineage.

Therefore simulated lift/transfer cannot claim carried-object collision safety.

## 9. Lift, placement and left-arm audit

- Generic BODY runtime goals and `LEVEL_YAW_FREE/TARGET` exist and can represent BODY `z≈1.20 m` plus a runtime `-45°` visibility-clear region.
- Exact lift/visibility planning was not accepted because attached geometry is not passed to cuRobo.
- Generic support/object decomposition preserves multiple primitives, but no verified groove semantic target/opening is bound to object 3. Vertical pre-place/descent is therefore not ready.
- Current left arm is collision-modeled and its live joints are included as the inactive-arm obstacle. Current geometry is not mutually colliding with the right-arm state, so holding it is feasible for planning-only.
- No production dual-arm coordinator provides atomic simultaneous planning, synchronized ServoJ start, shared lease or dual abort semantics. Concurrent left-UP/right-pregrasp is not ready.

## 10. Skill/Scheme interface matrix

| Scheme step | Skill ID | Existing implementation/backend | Missing before P3.8B/8C | Required input/effect |
|---|---|---|---|---|
| Pickup base move | `navigate.go_to_station` / registered relative move | `AmrHttpBase`, `SceneAwareBase`, LocalScene invalidation | truthful asynchronous completion + registered pose persistence | relative transform/station; effect `BASE_SETTLED, SCENE_REQUIRED` |
| Capture local scene | `observe.capture_scene` | `LocalSceneService.scan`, Pixel Pro, generic reconstruction | detection must join same epoch | camera/calibration/live joints → immutable scene |
| Detect resource | `observe.detect_resource` | `EpicClient`, 5700 parser/profile | typed detection artifact + epoch binding | profile → raw response + canonical target |
| Free-space motion | `manipulation.plan_to_pose` / `move_free` | `SceneAwareMotionService`, persistent cuRobo | accept manipulation target reference and attachment geometry | BODY goal + constraints → bound trajectory |
| Final approach | `manipulation.approach` | geometry helper only | CONTACT_TARGET corridor and allowed pair | target/axis/distance → precontact/contact state |
| Grasp | `manipulation.grasp` | serial move/read primitives, WorldModel attach contract | robust verification + attachment construction | grasp command → verified attachment |
| Lift/retreat | `manipulation.retreat` / `lift` | generic free-space goals | vertical/contact semantics + carried collision model | axis/distance/target-z → verified clearance |
| Release | `manipulation.release` | serial open primitive, detach contract | release verification and scene effect | attached object/destination → verified detach |
| Authorization | `execution.authorize` | SafetyKernel/lease infrastructure | manipulation/contact/attachment geometry samples | exact bound plan → one-shot permit |
| Execute | `execution.execute_trajectory` | native ServoJ packaging/execution | manipulation-mode contracts and reviewed gates | exact hash/lease → monitored execution |
| Composite pick | `manipulation.pick` | catalog contract only | Scheme implementation and recovery | resource + arm + scene → attached |
| Composite place | `manipulation.place` | catalog contract only | target/contact/release implementation | attached + slot → located/detached |
| Transfer | `manipulation.transfer_object` | catalog contract only | base/scene lifecycle and recovery | source/destination → lineage-preserved transfer |

Obstacle avoidance correctly remains below Skills in `SceneAwareMotionService`.

## 11. Blockers and smallest next actions

### BLOCKER 1 — AMR accepted response is not completion

Why: `SceneAwareBase` marks settled immediately while the real controller runs asynchronously; status remains `IDLE` during motion.  
Evidence: `pick_base_move_v2.json`, `place_base_move.json`.  
Smallest next action: add a commissioned completion observer based on task/log transition plus pointcloud/landmark stability; call `base_settled()` only after it passes.

### BLOCKER 2 — 5700 target and Pixel Pro scene are not one ObservationEpoch

Why: the domain supports `detection_ids`, but live scene construction does not ingest the raw detection artifact.  
Evidence: `world_model.py`, `local_scene_service.py`, `grasp_plan.prepare()` fail-closed contract.  
Smallest next action: add an ingestion transaction capturing joints→5700→5000→joints and commit both IDs/hashes together.

### BLOCKER 3 — rightmost placement profile is not proven

Why: object 3 is a strong geometric candidate, but solution name, Euler convention and approach axis are not obtainable from 5700 alone.  
Evidence: `right_place_at_place_base.json`, `pose_semantics_analysis.json`.  
Smallest next action: obtain Epic UI/project mapping and run board/tool/groove axis validation; only then add `right_place_rightmost` as COMMISSIONED.

### BLOCKER 4 — bounded contact policy absent

Why: current TARGET handling removes the target from collision globally.  
Evidence: `world/scene_compiler.py`.  
Smallest next action: define a short final corridor with tool-target pair relaxation only; keep all links and non-target geometry hard.

### BLOCKER 5 — attached geometry is not passed to cuRobo

Why: revision exists, moving collision geometry does not.  
Evidence: `scene_snapshot.py`, `scene_aware_planner.py`, `safety_kernel.py`.  
Smallest next action: convert the detected target primitive into a conservative TCP-local geometry and use the identical geometry in planner, dense validator and SafetyKernel.

### BLOCKER 6 — post-grasp verification absent

Why: gripper position is not object presence and no local scene-delta API exists.  
Evidence: `serial_gripper.py`; no TCP scene-delta implementation found.  
Smallest next action: implement the versioned local delta classifier and combine it with delayed gripper readback.

## 12. End-state declaration

```text
NO_ARM_MOTION_SENT = YES
NO_SERVOJ_ENABLE_SENT = YES
NO_GRIPPER_MOTION_SENT = YES
AMR_STOP_SENT_AFTER_EACH_AUDIT_LEG = YES
FRESH_PIXEL_PRO_SCENE_AFTER_EACH_BASE_LEG = YES
PROFILE_SILENTLY_COMMISSIONED = NO
REAL_GRASP_STARTED = NO
```

P3.8A is complete as an audit. P3.8B must not begin until the five planning-chain blockers above have concrete implementations or evidence-backed contracts. The current final base position is reported through the final fresh scene and 5700 target; it is not falsely labeled an exact map-origin return.
