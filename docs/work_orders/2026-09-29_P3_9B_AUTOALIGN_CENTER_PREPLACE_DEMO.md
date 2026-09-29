# P3.9B — Auto-align pick/place, cuRobo-only free-space, center transfer, autostart UI, and physical run to preplace

Date: 2026-09-29
Mode: IMPLEMENT + SUPERVISED PHYSICAL COMMISSIONING

Read first:

- `docs/decisions/2026-09-29_P39B_MOTION_BASEALIGN_UI_POLICY.md`
- `docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md`
- `docs/architecture/2026-09-28_REALTIME_SKILL_TASK_RUNTIME.md`
- `schemes/commissioned/tray_to_groove_v1.json`
- `demos/right_arm_epic_pick_lift_v1/demo.json`

Current integration baseline to verify before coding:

`6075295f77418a9a171a8ceef0d436e2c13ca461`

## 0. Preserve rollback and coworker work

Before coding:

1. record `.32` HEAD, GitHub HEAD, status, ahead/behind;
2. preserve current dirty/untracked coworker files;
3. run full tests;
4. do not modify the golden legacy first-pick demo path;
5. use small commits; no force-push.

## 1. Audit and recover the teammate `center` pose first

Search the effective `.32` workspace and history for the teammate-created chest/stow/center posture.

Search tracked, untracked, preservation patches and Git history for:

`center`, `centre`, `chest`, `stow`, `收起`, `胸前`.

Record:

- source file/commit or dirty-file provenance;
- joint values and/or BODY TCP target;
- expected controller tool/TCP;
- read-only FK result;
- final gripper orientation.

Do NOT substitute `ready` if `center` cannot be found.

Exit:

`CENTER_POSE_SOURCE_VERIFIED = YES/NO`

## 2. Make central exclusion configurable and OFF for this demo

Historical band:

`|BODY Y| <= 0.07 m` = 7 cm each side = 14 cm total width.

Add an explicit config object, for example:

```json
{
  "central_exclusion": {
    "enabled": false,
    "half_width_m": 0.07
  }
}
```

Refactor all hard-coded central gates to consume this policy.

Audit at least:

- MotionConstraints/default request creation;
- planner request serialization;
- production scene worker/path metrics;
- independent dense validation;
- SafetyKernel;
- any fixed-body virtual exclusion primitive.

When disabled:

- no central-band rejection;
- actual arm/arm, self, robot/environment and controller protections remain active.

Add ON/OFF regression tests.

WebUI/ART system status must show `CENTRAL_EXCLUSION: OFF` for this run.

## 3. Enforce cuRobo for every non-contact arm point-to-point move

Create one runtime invariant:

`FREE_SPACE_ARM_MOTION_PROVIDER = SceneAwareMotionService/curobo`

Task/Scheme path must use cuRobo for:

- current → pregrasp;
- post-lift → center;
- center → preplace/above-place;
- any other normal pose-to-pose move.

Do not let named-pose/task nodes fall back to direct MoveJ.

Contact exceptions only:

- final grasp approach;
- initial contact-window vertical lift/escape;
- final placement descent/release in later demos.

Add tests that reject a free-space Skill plan if provider metadata is not cuRobo/scene-aware.

## 4. Implement `navigate.align_for_manipulation`

Add the Skill contract and RealProvider implementation.

Inputs:

- target profile/resource;
- arm = right;
- manipulation goal kind = PICK_PREGRASP or PLACE_PREPLACE;
- X total bound = ±0.15 m;
- Y total bound = ±0.40 m;
- yaw = 0;
- max corrections/retries;
- optional learned prior offset.

Algorithm:

1. quick Epic 5700 target detection at episode origin;
2. generate bounded candidate base translations;
3. predict target BODY pose after each candidate;
4. score with right-arm RuntimeGoalIK, joint margin/singularity and displacement cost;
5. choose best candidate;
6. issue AMR relative translation;
7. wait for truthful BaseMotionObserver SETTLED;
8. fresh atomic ObservationTransactionV2;
9. attempt the actual scene-aware cuRobo plan required by the next arm Skill;
10. if needed, bounded correction and repeat;
11. never exceed total X/Y bounds from episode origin.

Prefer one good predicted move + at most a small number of corrections rather than grid-walking.

Persist successful pick/place offsets as priors for future runs, with evidence and revision. Priors never bypass fresh detection/revalidation.

Required evidence:

- commanded offset;
- observed target BODY before/after;
- settle evidence;
- cuRobo feasibility result;
- cumulative displacement from alignment origin.

## 5. Pick-side auto-alignment commissioning

The current target is visible but right-arm unreachable.

Use `navigate.align_for_manipulation` to find a reachable/plannable pick base pose within:

- left/right total ±0.40 m;
- forward/back total ±0.15 m;
- no yaw.

Do not hard-code the old successful offset as the only solution. It may be used as a prior.

Stop alignment when a fresh-epoch `current→50 mm pregrasp` cuRobo plan succeeds.

## 6. Grasp and initial lift

Reuse the already successful semantics unchanged:

- fresh pick epoch;
- cuRobo to 50 mm pregrasp;
- gripper 40%;
- CONTACT_BYPASS_V1 approach;
- close;
- current grasp verification;
- bounded BODY +Z initial lift;
- activate coarse attached object.

Do not redesign the grasp in this work order.

## 7. cuRobo attached-object move to center

Immediately after the initial vertical lift:

- keep object attached;
- use full scene-aware cuRobo;
- move the right arm to the verified `center` posture;
- use horizontal/level transfer orientation semantics compatible with the recovered center definition;
- keep left arm as HOLD_CURRENT obstacle;
- central virtual band is OFF;
- actual collision checks remain ON.

This center/stow stage is mandatory before lateral base motion.

Exit:

`CENTER_TRANSFER_CUROBO_READY = YES`

## 8. Place-side auto-alignment

With the right arm holding the object at center:

1. attempt quick `right_place_rightmost` detection;
2. use `navigate.align_for_manipulation` with the same X/Y bounds;
3. AMR may move freely within total ±0.40 m lateral and ±0.15 m longitudinal;
4. wait for truthful settle;
5. fresh place ObservationTransactionV2;
6. require attached-object cuRobo feasibility to preplace/above-place.

If the place target is temporarily not visible, perform a bounded acquisition/search using the same total translation envelope. Do not rotate the base in P3.9B.

## 9. cuRobo center → above-place

Use the fresh place epoch and attached object.

Plan and execute with SceneAwareMotionService/curobo to:

- rightmost placement target;
- directly above/preplace according to current task parameter height;
- no contact descent;
- no release.

End state:

`HOLD_ABOVE_PLACE`

## 10. New Demo/Task

Create a new additive demo/task; do not alter the golden first-pick demo.

Demo ID:

`right_arm_autoalign_pick_center_preplace_v1`

Required stage list:

1. `AUTO_ALIGN_PICK_BASE`
2. `PICK_OBSERVATION`
3. `CUROBO_MOVE_PREGRASP`
4. `CONTACT_APPROACH`
5. `GRASP_VERIFY`
6. `INITIAL_VERTICAL_LIFT`
7. `ATTACH_OBJECT`
8. `CUROBO_MOVE_CENTER`
9. `AUTO_ALIGN_PLACE_BASE`
10. `PLACE_OBSERVATION`
11. `CUROBO_MOVE_ABOVE_PLACE`
12. `HOLD_ABOVE_PLACE`

Expose the same flow as a low-code Scheme in Task Studio.

## 11. WebUI/ART autostart on `.32`

Implement versioned deployment files and install/enable them on `.32`.

Required runtime architecture:

- one canonical ARES-R backend owner;
- WebUI as a client/front-end;
- ART/CLI connected to the same backend/state;
- persistent planner/capture services owned once.

If current ART is not a daemon, create/start the canonical backend daemon instead of creating two independent hardware owners.

Autostart requirements:

- start after network-online;
- backend before WebUI;
- restart on failure;
- journal logs;
- health endpoint;
- no robot/base/gripper motion at boot;
- task physical execution still requires explicit authorization.

Verify:

- service enabled;
- service active after restart;
- WebUI reachable at `http://172.28.172.210:8765/`;
- ART/CLI reports the same backend identity.

Do not reboot `.32` solely for this test unless the user separately approves a reboot. Service enable + restart + boot-order verification is sufficient for this phase.

## 12. WebUI/ART version and synchronization

Add shared backend system info containing:

- ARES-R version;
- Git SHA/short SHA;
- TaskRuntime version;
- WebUI build version;
- active Scheme/version;
- central-exclusion state;
- backend uptime/health.

WebUI header/footer must display it.

ART must expose the same data through `version` or `system info`.

Do not maintain separate hard-coded version strings.

## 13. Fix/check WebUI 3D left/right orientation

Current BODY semantics:

`+X forward, +Y left, +Z up`.

Audit the canvas projection and default camera preset.

Regression conditions:

- left base `Y=+0.20` appears screen-left in default robot-forward/rear view;
- right base `Y=-0.20` appears screen-right;
- +Y axis label says LEFT;
- -Y direction says RIGHT;
- no underlying BODY data is sign-flipped to fix display.

Add projection/view tests.

Add explicit view presets if useful: Robot Forward/Rear, Front, Top.

## 14. WebUI polish

Refine Task Studio/Demo page for customer/operator use:

- product/version header;
- backend health;
- current Task/Demo and stage;
- current/next Skill;
- base alignment bounds and cumulative displacement;
- central exclusion ON/OFF;
- scene epoch;
- planner status;
- target BODY coordinates;
- visible pick/place target markers;
- center/stow marker/posture;
- HOLD_ABOVE_PLACE state;
- one prominent Stop;
- concise event log;
- keep low-code edit/clone/validate/replay functions.

ART commands and WebUI controls must update the same state immediately.

## 15. Pre-physical acceptance

Before moving hardware:

- full test suite;
- frozen replay of new Scheme;
- fault injection for auto-align bounds/timeout;
- central exclusion ON/OFF tests;
- cuRobo-only free-space provider tests;
- center pose source/FK verified;
- WebUI projection regression;
- service health/autostart tests;
- physical plan preview for pick alignment, center transfer and place preposition.

Required flags:

```text
CENTER_POSE_SOURCE_VERIFIED
CENTRAL_EXCLUSION_SWITCH_READY
CENTRAL_EXCLUSION_CURRENTLY_OFF
ALL_FREE_SPACE_ARM_P2P_VIA_CUROBO
AUTO_ALIGN_PICK_READY
AUTO_ALIGN_PLACE_READY
CENTER_TRANSFER_CUROBO_READY
WEBUI_ART_AUTOSTART_READY
WEBUI_LEFT_RIGHT_VERIFIED
NEW_DEMO_REPLAY_PASS
READY_FOR_P39B_SUPERVISED_RUN
```

## 16. One physical authorization

When and only when all pre-physical flags are YES, ask one action:

```text
USER ACTION — P3.9B自动对位并执行到放置上方

确认：
- 底盘左右±40cm、前后±15cm范围内无人和临时障碍；
- 右臂抓取与转位扫掠区无人；
- 左臂保持当前状态；
- 取料物和最右放置目标处于现场；
- 物理急停可用；
- 允许系统自动移动底盘寻找取/放可达位置，并执行新Demo直到HOLD_ABOVE_PLACE。

完成后回复：
批准P3.9B自动对位并执行到放置上方
```

After this single authorization, do not ask again during normal automatic pick/place base alignment or arm stages. Ask again only if a fault, unexpected site-state change, or manual intervention invalidates the run.

## 17. Physical run behavior

After approval:

- execute the new demo automatically;
- Codex may command AMR translations within the total bounds for both alignment episodes;
- stop on any failed settle, failed fresh epoch, cuRobo failure after bounded corrections, grasp verification failure, controller fault or explicit Stop;
- end at `HOLD_ABOVE_PLACE`;
- do not descend/release.

## 18. Report

Create:

`docs/reports/2026-09-29_P3_9B_AUTOALIGN_CENTER_PREPLACE_REPORT.md`

Report at least:

```text
PICK_ALIGNMENT_TOTAL_XY
PICK_ALIGNMENT_CORRECTIONS
PICK_TARGET_BODY_FINAL
PICK_PREGRASP_CUROBO_PASS
GRASP_PASS
INITIAL_LIFT_PASS
CENTER_POSE_SOURCE
CENTER_TRANSFER_PASS
PLACE_ALIGNMENT_TOTAL_XY
PLACE_ALIGNMENT_CORRECTIONS
PLACE_TARGET_BODY_FINAL
PREPLACE_CUROBO_PASS
HOLD_ABOVE_PLACE = YES/NO
CENTRAL_EXCLUSION_ENABLED = false
WEBUI_AUTOSTART = YES/NO
ART_BACKEND_AUTOSTART = YES/NO
WEBUI_LEFT_RIGHT_FIX = PASS/NO_CHANGE_NEEDED/FAIL
TOTAL_RUN_TIME_S
```

Preserve full timing/event evidence for the next speed-optimization round.

## 19. Git

Small commits by subsystem.
No force-push.
Keep legacy first-pick demo unchanged.
Keep unrelated coworker dirty files isolated.
After a successful supervised checkpoint, push only clean reviewed commits and report local/remote SHA.