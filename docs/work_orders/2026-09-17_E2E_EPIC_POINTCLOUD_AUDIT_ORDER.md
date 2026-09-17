# ARES-R E2E / Epic / Pointcloud Audit Order — 2026-09-17

## 0. Why this order exists

Current project priority is no longer architecture expansion. The immediate delivery target is a supervised but real end-to-end demo:

```text
AMR move to pick station
→ confirmed arrival + settle
→ Epic perception
→ collision scene acquisition
→ arm plan
→ grasp
→ stow/transport
→ AMR move to place station
→ confirmed arrival + settle
→ Epic perception
→ collision scene acquisition
→ place
→ retreat/stow
→ COMPLETE
```

The school/server status described on 2026-09-17 is special:

- server repo: `/home/yikun/ARES-R`
- server branch: `main`
- committed HEAD is still `92a9c574...`
- the server worktree contains many uncommitted changes from the previous on-site session
- those changes reportedly include Epic 5700 parsing, grasp pose audit, IK, pregrasp generation, singularity checks, and right-arm native execution
- some config assertions are not yet justified by measurement (`pose_frame_verified=true`, Epic space/frame/orientation assumptions, etc.)
- left arm is reported by the operator as accurate, while right arm shows z/orientation error, but repository evidence must be reconciled before any conclusion

This order is intentionally **audit-first**. Do not reset, revert, stash away, commit all, or rewrite the dirty worktree before producing the evidence requested below.

The objective is to answer four questions:

1. Which parts of yesterday's work should be preserved, reworked, or rejected?
2. What exactly is the Epic Pro interface contract for this robot, and how do left/right arm spaces, object IDs, camera IDs, TCP/tool revisions, and pose conventions map together?
3. What pointcloud processing route should ARES-R use so that a single scan after AMR arrival becomes a compact, auditable cuRobo collision world limited to the actual manipulation workspace?
4. What is the shortest safe route from today's state to the first complete real end-to-end demo?

Do **not** continue Skill Library / LLM / Qwen work in this task.

---

# 1. Hard safety and preservation rules

Before changing any tracked or untracked file in `/home/yikun/ARES-R`, preserve the current worktree **outside the repository**.

Create an evidence directory such as:

```text
/home/yikun/ARES-R_AUDIT_20260917/
```

Record at minimum:

```text
git rev-parse HEAD
git branch --show-current
git status --short
git diff --stat
git diff --binary
list of all untracked files
```

Also create a safe copy/archive of untracked source/config/test files needed to reconstruct the current worktree. Do not include giant generated logs or pointclouds in Git unless explicitly justified; list them and preserve them outside Git if needed.

Rules for this audit:

- NO `git reset --hard`
- NO destructive `git checkout -- <file>` / `git restore` before classification
- NO blanket `git add -A`
- NO blanket commit of the dirty worktree
- NO hardware motion
- NO JAKA servo/move command
- NO AMR motion command
- NO gripper command
- camera/network read-only inspection is allowed only if it does not move robot hardware and is available; otherwise work from saved data
- do not edit `main` during the audit

The output of this phase must make it possible to reconstruct yesterday's exact code state even if later changes are made.

---

# 2. Forensic audit of yesterday's dirty worktree

Compare the server dirty worktree against committed `92a9c574...` file by file.

For every modified or untracked file, classify it into exactly one of:

```text
KEEP_CORE
    implementation is valuable and its semantics are evidence-independent

KEEP_WITH_GATES
    implementation is valuable, but must remain disabled/uncommissioned until a specific site measurement is passed

REWORK
    concept is valuable but current implementation/config embeds an unverified assumption or wrong abstraction

DROP_OR_GENERATED
    temporary experiment output, obsolete duplicated code, generated artifact, or unsafe shortcut
```

For each file record:

- path
- what changed
- why it was changed
- what test/log/run depended on it
- whether it was used in a real execution
- observed result
- hidden assumptions
- classification
- recommended target branch/file after review

Pay special attention to the reported changes in:

```text
config/system.json
src/ares_r/adapters/epic.py
src/ares_r/adapters/epic_protocol.py
src/ares_r/models.py
Epic pose audit utilities
pregrasp generation
cuRobo IK
pregrasp planning
singularity checking
right-arm native execution
associated tests / logs / generated plans
```

Do not automatically reject right-arm code because right-arm target accuracy is imperfect. Separate:

```text
planner/executor correctness
```

from:

```text
perception → frame → target correctness
```

Likewise, do not automatically accept config flags because a run completed.

Explicitly audit these claims:

- `pose_frame_verified=true`
- Epic space `2` → right arm base
- Epic space `1` / other space → left arm base
- Euler angle order/convention
- sign/axis of the approach direction
- whether `+Z` or another local axis is the gripper approach axis
- controller Tool ID / TCP used during each run
- whether planned robot/tool model matches controller Tool/TCP
- any hard-coded offsets or magic z corrections

The reported site data says a right-arm Epic-vs-TCP position discrepancy of about 7.06 mm was observed against a 5 mm threshold, and orientation convention was not independently validated. Treat this as an audit hypothesis, not a final truth, until logs/data are checked.

Also reconcile the claim that the left-arm grasp chain was accurate. Search for:

- left-arm Epic packets
- left-arm target conversions
- left-arm pregrasp plans
- left-arm native execution logs
- left Tool ID/TCP evidence
- videos or filenames referenced in work logs

If the only stored executions are right arm, say exactly that. If left-arm evidence exists elsewhere in the worktree, identify it.

**Stop condition:** Do not decide branch preservation/destruction until the classification table is complete.

---

# 3. Epic Pro interface audit — make the interface explicit

Study all of the following, in priority order:

1. current server dirty-worktree Epic code and saved packets/logs
2. committed ARES-R Epic code
3. archived vendor SDK/docs under `vendor/`
4. the actual installed Epic Pro version / project settings if that information is recoverable from saved logs/config
5. official TransferTech documentation

Useful official references:

- Epic Pro 1.3.0.1 5700 interface:
  https://docs.transfertech.cn/tf_docs/zh/epic-pro/1.3.0.1/support/interface-instructions.html
- Epic Pro 1.3.0.1 release notes / changed shortcut commands:
  https://docs.transfertech.cn/tf_docs/zh/epic-pro/1.3.0.1/release-notes.html
- Epic path planning parameters:
  https://docs.transfertech.cn/tf_docs/zh/epic-pro/1.3.0.1/operations/pick-path-plan-parameters.html

The official 1.3.0.1 docs describe at least:

```text
110,cameraID
    trigger image

120,pose_count,0
    normal detection

120,grasp_path_count,0
    grasp-path planning

120,grasp_path_count,retract_path_count
    grasp + retract path

130,spaceID,objectID
    switch space/object

220,... / 320,...
    shortcut/combined forms whose exact parameter layout changed in 1.3.0.1
```

Success packets include pose type, returned pose count, object/grasp metadata, space/object IDs, grasp indices, ProStatus/reserved fields and pose payloads. Error packets use `000,...`.

Do not assume the running Epic version is 1.3.0.1 simply because ARES-R code/docs reference it. Determine or explicitly mark unknown.

Produce a command matrix for the **actual project**:

| purpose | command | actual configured IDs | expected response | pose type | units | frame | used by left/right/both | evidence |
|---|---|---|---|---|---|---|---|---|

At minimum resolve/mark unknown:

- camera ID(s)
- Epic space IDs
- object IDs
- pick/place object selection
- shortcut command currently configured (`320...` etc.)
- left-arm mapping
- right-arm mapping
- position unit
- orientation representation/unit
- pose frame
- Tool/TCP dependency
- grasp candidate semantics
- how multiple grasp candidates should be exposed to ARES-R

Do not encode one global Epic output frame for both arms unless evidence proves that is the actual project configuration.

Recommend a per-arm/per-task profile such as:

```text
EpicTaskProfile
  name
  camera_id
  space_id
  object_id
  request_mode
  expected_pose_type
  output_frame
  orientation_convention
  approach_axis
  correction_transform_revision
  robot_arm
  tool_id
  tcp_revision
```

but do not implement it in this audit unless a tiny offline parser-only change is required for evidence extraction.

## 3.1 Explicitly compare with yesterday's changes

For each Epic-related dirty-worktree change, answer:

```text
Does it correctly implement the actual protocol?
Does it preserve all metadata?
Does it distinguish ACK vs detection/path response?
Does it support multiple poses/candidates?
Does it assume one arm/frame globally?
Does it convert units exactly once?
Does it convert orientation exactly once?
Which part caused or could cause the right-arm target offset/orientation error?
```

The final recommendation should be expressed as:

```text
KEEP
KEEP BUT DISABLE UNTIL CALIBRATED
REWORK
DROP
```

not as an all-or-nothing rollback.

---

# 4. Pointcloud → ROI → cuRobo collision world audit

## 4.1 Start from what already exists

Do not restart this problem from zero.

Committed ARES-R already has:

- EpicEye SDK single-frame capture to `pointcloud.ply`
- manifest + SHA-256 + unit audit
- about 1920×1200 / 2.304 M raw points in the recorded site capture
- mm → m boundary
- an explicit statement that raw pointcloud is not yet planning-ready
- ATOM AABB handoff contract
- BODY → arm-base conservative AABB conversion
- a design document recommending `stop → scan → filter/ROI → boxes → cuRobo`

Read:

```text
src/ares_r/epic_pointcloud.py
src/ares_r/atom_obstacles.py
docs/EPIC_ATOM_CUROBO_ROUTES.md
vendor/epiceye_sdk_4.0.0/
vendor/atom_sdk_1.4.0/
```

The current EpicEye capture example itself triggers a new camera frame and then decodes image/depth/pointcloud from one EpicRaw document. Therefore it guarantees internal image/depth/cloud consistency for that SDK capture, but it does **not automatically prove that this is the same frame used by a separate 5700 detection request**. Audit this explicitly.

## 4.2 Recover actual geometry before choosing ROI

The operator states:

- camera is near the robot head, above the midpoint between arm bases
- camera optical view is approximately 49° downward toward the front
- arm reach is much smaller than the camera field of view
- the tool/TCP extends reach further
- carried objects may extend beyond the nominal TCP

Treat these as field notes until confirmed in configs/measurement.

Do not derive the manipulation ROI from `config/robot_world.json` display DH alone; that file explicitly says it is a display model and not a collision/planning model.

Use the actual cuRobo robot model/URDF/tool geometry used for planning on the server and compute/estimate a conservative reachable swept volume for:

```text
left arm + tool
right arm + tool
carried-object margin
safe approach/retract margin
```

Then define the ROI in **ARES-R BODY coordinates**, because the robot working volume is naturally defined there.

Propose:

```text
GLOBAL_MANIPULATION_ROI
LEFT_MANIPULATION_ROI
RIGHT_MANIPULATION_ROI
station-specific ROI overrides (only if justified)
```

Do not invent final numeric bounds without either model-derived evidence or site measurement. You may produce preliminary candidate bounds with clear `UNCOMMISSIONED` status for offline evaluation.

## 4.3 Recommended processing experiment

Build an offline evaluation plan, and if dependencies already exist, a non-hardware analysis utility, for this sequence:

```text
raw Epic pointcloud
→ remove zero/NaN/invalid points
→ mm → m
→ transform camera frame → BODY using commissioned/provisional T_body_camera
→ crop to manipulation ROI
→ remove floor / irrelevant background planes where justified
→ remove robot/base/arms/tool self points using robot collision geometry + current joints
→ optional target-object masking / allowed-interaction handling
→ voxel downsample
→ statistical/radius outlier filtering if needed
→ cluster remaining unknown obstacle points
→ fit conservative AABB first (OBB later only if needed)
→ inflate by explicit calibration + sensor + planning margin
→ merge with known static geometry
→ compile to arm-local cuRobo world
→ visualize / save audit artifact
```

For every stage record:

```text
point_count_before
point_count_after
bounds
runtime
parameters
source frame
output frame
hash/revision
```

Run parameter sweeps offline on existing saved PLY where possible instead of tuning by intuition. Compare at least a small set of voxel/outlier/cluster parameters and report geometry loss vs point-count reduction.

If Open3D is already available or can be isolated without disturbing the production environment, it provides standard voxel downsampling, AABB/OBB cropping, statistical outlier removal and radius outlier removal. Do not add a heavy runtime dependency to production merely to finish the audit.

Useful reference:
https://www.open3d.org/docs/latest/tutorial/geometry/pointcloud_outlier_removal.html

## 4.4 Prefer a hybrid modeled world for V0

The long-term idea of "fully model the station/device, then use perception to locate that model relative to the mobile robot" is valid and should be separated from "unknown obstacle cloud".

Recommend evaluating this architecture:

```text
KNOWN STATIC / SEMI-STATIC GEOMETRY
  chassis / arm bases / fixed robot body
  table / station / device CAD or conservative cuboids
  known tray/bin/tool geometries
  known other arm geometry

POSE ESTIMATION
  use Epic / pointcloud matching to estimate station/device pose relative to BODY
  instantiate known geometry at the measured pose

UNKNOWN RESIDUAL GEOMETRY
  cropped, self-filtered pointcloud residual
  cluster → conservative AABB for V0

TARGET OBJECT
  represented separately from obstacles so grasp planning is not blocked by the target itself

ATTACHED OBJECT
  becomes part of robot/tool collision geometry after verified grasp
```

Do not convert the entire wide-FOV cloud into one giant obstacle set when most of it lies outside the reachable manipulation region.

## 4.5 cuRobo representation choice for the first real demo

For V0, prefer:

```text
known geometry + ROI-filtered AABB cuboids
```

before nvblox/ESDF.

Rationale to verify against the installed cuRobo version:

- cuRobo supports cuboid, mesh, voxel and nvblox world representations
- official cuRobo docs describe cuboids as common in real deployments and say the cuboid checker is substantially faster than mesh in their implementation
- official docs say camera-perception collision planning works better in sparse scenes, while denser scenes and occlusion can cause failures
- official depth-camera motion-generation demo updates the world between planning queries; obstacles appearing during execution can still cause collision
- Isaac ROS manipulation workflows explicitly restrict mapping to workspace bounds covering the arm operating volume to control computation

References:

- https://curobo.org/get_started/2c_world_collision.html
- https://curobo.org/get_started/2d_nvblox_demo.html
- https://curobo.org/get_started/6_known_issues.html
- https://nvidia-isaac-ros.github.io/v/release-4.6/robots/universal_robots/index.html

Therefore the first real ARES-R obstacle-aware route should be:

```text
AMR stops
→ arrival confirmed
→ settle
→ one coherent scene acquisition
→ scene frozen
→ plan
→ execute while the environment is assumed static
```

If base moves, another arm moves into the shared workspace, target/attachment state changes, calibration changes, or the scene is disturbed, invalidate and reacquire/replan.

## 4.6 Is "no obstacle avoidance, no arm motion" a reasonable rule?

Audit and document the distinction:

### For task-space manipulation in an unknown/partly known real scene

Yes: requiring a collision-checked scene before arbitrary cuRobo manipulation is a reasonable commissioning gate.

### But pointcloud avoidance is not a functional-safety system

It does not replace:

- E-stop / operator supervision
- joint/velocity/acceleration limits
- verified robot/tool collision model
- central/shared-zone rules
- low-speed initial execution
- known safe transport/stow envelopes
- trajectory start-state checks

Official Isaac/cuMotion examples explicitly warn that perception obstacle avoidance is not a safety function.

### Do not create a deadlock

Precommissioned transport/stow/recovery motions inside a known static safe envelope may need to remain available even when live pointcloud is unavailable; otherwise the system can become unable to move into the very pose required for scanning/navigation safety.

Define this distinction in the final plan:

```text
SAFE_PRECOMMISSIONED_MOTION
    narrow, verified envelope; static hard geometry; no arbitrary targets

TASK_MANIPULATION_MOTION
    requires a valid collision scene / snapshot
```

---

# 5. Epic detection frame vs pointcloud frame coherence

This is a critical integration question.

The current SDK `capture.py` does:

```text
trigger_frame(pointcloud=True)
→ frame_id
→ get_frame_in_epicraw(frame_id)
→ decode image/depth/pointcloud from that same EpicRaw
```

Epic 5700 detection can separately trigger/operate Epic Pro's project pipeline.

Determine whether ARES-R can obtain:

1. the exact EpicEye frame used by Epic Pro detection, or
2. an Epic Pro result identifier/timestamp that can be matched to SDK frame ID, or
3. only two separate captures.

If exact same-frame linkage is not available, propose a V0 sequence that is still auditable, for example:

```text
base/arms stationary
→ settle
→ pointcloud capture P
→ immediately run Epic detection D
→ verify no robot/base motion and bounded time delta
→ record P and D as one static-scene acquisition bundle with both timestamps/IDs
```

Do not silently call two unrelated captures "the same frame".

Explain how this should interact with the existing WorldModel/ObservationEpoch without redesigning WorldModel in this task.

---

# 6. First end-to-end arm choice

Do not decide "right arm only" merely because recent code was written for right arm.

For the first complete demo, choose the arm with the strongest real evidence after the audit.

Create a comparison:

| evidence | left | right |
|---|---:|---:|
| Epic target accuracy | | |
| frame mapping evidence | | |
| orientation validation | | |
| Tool/TCP match | | |
| cuRobo IK | | |
| collision planning | | |
| native execution | | |
| gripper verify | | |
| recorded runs | | |

If the left arm is truly already accurate and Epic-mapped while right arm still needs correction, recommend using left arm for the **first end-to-end demo**, while preserving and fixing right-arm infrastructure in parallel.

If the saved evidence proves the opposite, say so.

The first demo does not require automatic arm selection or simultaneous dual-arm motion. The inactive arm should be stowed and represented as collision geometry.

---

# 7. E2E V0 route to propose after the audit

Produce a minimal supervised workflow, not a general skill framework:

```text
PRECHECK
STOW_BOTH

NAV_PICK
WAIT_PICK_ARRIVAL
SETTLE_PICK

ACQUIRE_PICK_SCENE
EPIC_DETECT_PICK
VALIDATE_PICK_TARGET
COMPILE_PICK_COLLISION_WORLD
PLAN_PREGRASP
EXECUTE_PREGRASP
FINE_APPROACH
GRIPPER_CLOSE
VERIFY_GRASP
ATTACH_OBJECT
PLAN_LIFT_RETRACT
EXECUTE_LIFT_RETRACT
TRANSPORT_STOW

NAV_PLACE
WAIT_PLACE_ARRIVAL
SETTLE_PLACE

ACQUIRE_PLACE_SCENE
EPIC_DETECT_PLACE
VALIDATE_PLACE_TARGET
COMPILE_PLACE_COLLISION_WORLD_WITH_PAYLOAD
PLAN_PREPLACE
EXECUTE_PREPLACE
FINE_PLACE
GRIPPER_OPEN
VERIFY_RELEASE
DETACH_OBJECT
RETREAT
STOW_BOTH

COMPLETE
```

Every physical stage must be stoppable and logged.

For the first real version:

```text
confirm_each_stage = true
```

is acceptable and preferred.

Do not implement automatic retries in this audit. Failure should stop at the current stage and preserve evidence.

Also audit the AMR arrival semantics. Current committed AMR adapter sets the target station after sending the HTTP request; that is not sufficient evidence that the base has physically arrived and stopped. Identify the actual OpenAPI status/localization/velocity/task endpoint required for `navigate_and_wait()`.

---

# 8. Required audit outputs

Do not change production runtime in this audit.

Produce the following reports in the external evidence directory first; they may be copied into the repository only after review:

```text
01_YESTERDAY_WORKTREE_PRESERVATION_AUDIT.md
02_EPIC_INTERFACE_ARM_MAPPING_AUDIT.md
03_POINTCLOUD_ROI_CUROBO_AUDIT.md
04_E2E_V0_GAP_AND_SEQUENCE.md
05_RECOMMENDED_KEEP_REWORK_DROP_TABLE.md
```

Also produce machine-readable summaries if useful:

```text
changed_files_classification.json
epic_profile_candidates.json
pointcloud_pipeline_experiment.json
```

The final chat/report must answer, concisely and explicitly:

1. Should yesterday's worktree be committed as one preservation branch, or split? Why?
2. Exactly which files are KEEP_CORE / KEEP_WITH_GATES / REWORK / DROP_OR_GENERATED?
3. Is there real evidence that left-arm Epic targeting is accurate?
4. Is there real evidence that right-arm planner/executor is accurate even if perception target is not?
5. What is the actual Epic command/profile mapping for left and right arms?
6. How should the 2.3M-point wide-FOV cloud be reduced to the manipulation workspace?
7. What ROI should be derived from the actual cuRobo robot/tool reach, and what measurements are still missing?
8. Should V0 use known geometry + AABB residuals, mesh, or nvblox? Give one recommendation.
9. What pointcloud/self-filter/calibration blockers remain before the scene is safe enough for supervised arm planning?
10. Which arm should be used for the first full demo?
11. What exact 48–72 hour integration sequence should follow?

Then STOP.

Do not reset/revert/commit the dirty server worktree until the preservation recommendation is reviewed by the user and ChatGPT.
