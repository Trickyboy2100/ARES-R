# P3.8C — Supervised physical Tray→Groove customer demo

Date: 2026-09-24
Entry: P3.8B must report READY_FOR_P3_8C_SUPERVISED_EXECUTION=YES and produce a reviewed SchemeExecutionPackage.

## 0. Goal

Execute the real right-arm customer demo from presentation posture through pickup, carry, placement and retreat using the audited Scheme/Skills.

First-demo policy:

~~~text
right arm = manipulation arm
left arm = HOLD_CURRENT live collision obstacle
dual-arm simultaneous execution = OFF
~~~

## 1. One operator authorization

Before any arm/gripper motion ask exactly one action:

~~~text
USER ACTION — P3.8C现场执行授权

目的：
启动右臂 Tray→Groove 分阶段真机 Demo。

你现在做：
确认电子秤料盘和放置凹槽处于预期位置；底盘移动区域和右臂扫掠区域无人、无临时障碍；左臂保持当前状态；物理急停可用；允许系统按已审阅 Scheme 自动执行，任一阶段 fault/UNKNOWN 即停止。

完成后回复：
批准P3.8C分阶段执行

安全边界：
只执行已冻结 SchemeExecutionPackage；不临时改变目标/profile/阈值；任何场景、检测、抓取验证或控制器故障都会停止，不自动跳过。
~~~

After confirmation, ordinary successful stages do not require repeated confirmation.

## 2. Physical sequence

### E0 — presentation preparation

- fresh LocalScene;
- scene-aware move right arm to reviewed presentation/up pose;
- command right gripper to 50%;
- verify pose + gripper readback.

### E1 — pickup base move

- execute registered/relative PICK_BASE_POSE_V1 transition;
- truthful BaseMotionObserver must reach SETTLED;
- LocalScene must become REQUIRED;
- fresh scan after settle.

### E2 — atomic pick observation

- execute ManipulationObservation transaction for right_pick;
- bind 5700 + 5000 + robot/tool state in one epoch;
- if detection/epoch validation fails, stop.

### E3 — pregrasp

- select frozen pregrasp_distance_m from SchemeExecutionPackage;
- scene-aware cuRobo plan/execute to pregrasp;
- command right gripper to 40%;
- verify readback.

### E4 — bounded contact approach

- execute the reviewed TargetContactPolicy segment only;
- preserve hard collision for arm links and non-target objects;
- reach detected grasp pose;
- no free-space fallback.

### E5 — grasp and local verification

- close gripper using frozen grasp command;
- delayed repeated readback;
- fresh local TCP-neighborhood observation;
- classify scene delta;
- if UNKNOWN/CHANGED_UNEXPECTED, stop before lift;
- if accepted, create attached object state/revision.

### E6 — lift + visibility clear

- execute vertical lift until TCP z≈1.20 m using attached-object geometry;
- then scene-aware free-space move to the reviewed right-front visibility-clear target;
- verify attached object remains valid.

### E7 — placement base move

- execute PLACE_BASE_POSE_V1 transition;
- BaseMotionObserver SETTLED required;
- old local scene invalid;
- fresh scan.

### E8 — atomic placement observation

- use commissioned right_place_rightmost profile;
- commit 5700 + 5000 + robot/tool/attachment state in one epoch;
- stop if profile/pose semantics mismatch.

### E9 — preplace transfer

- with attached-object geometry, scene-aware cuRobo plan/execute to reviewed preplace target above groove/rightmost placement point.

### E10 — vertical placement

- execute reviewed bounded vertical placement segment;
- final TCP stop = detected placement target + BODY +Z 0.005 m;
- no lateral free-space fallback inside final placement segment.

### E11 — release

- command gripper to 20%;
- verify readback and detach state;
- attachment revision changes; old plan invalid.

### E12 — retreat and base exit

- execute reviewed arm retreat;
- move right arm to safe posture if included in Scheme;
- execute reviewed base retreat;
- fresh observation / result verification.

### E13 — completion verification

- confirm gripper/object state as far as sensors allow;
- confirm object/scene at placement target;
- if result uncertain, report UNKNOWN, do not claim success.

## 3. Execution logging

Every stage records:

- Scheme run ID;
- Skill ID/version;
- timestamps;
- scene epoch/snapshot;
- 5700 raw response/detection ID when applicable;
- target/trajectory hash;
- attachment revision;
- AMR request/settle evidence;
- gripper command/readback;
- planner and execution timing;
- tracking/fault state;
- verification result.

## 4. Runtime stop behavior

Any of these stops the Scheme:

- controller fault/e-stop/collision/limit;
- AMR completion timeout;
- stale/mismatched scene or observation epoch;
- planning failure;
- hard collision validation failure;
- target-contact corridor violation;
- gripper command/readback failure;
- grasp verification UNKNOWN/CHANGED_UNEXPECTED;
- attached-object inconsistency;
- placement observation/profile mismatch;
- release verification UNKNOWN;
- explicit ART/UI stop.

No stage is silently skipped.

## 5. UI

During execution WebUI must show:

- current Scheme stage;
- current Scene status/epoch;
- pick/place target marker;
- planned/executing trajectory;
- attached-object state;
- AMR stage;
- gripper percentage/readback;
- last verification result;
- prominent Stop.

## 6. Acceptance

Report:

~~~text
PRESENTATION_POSE_EXECUTED
PICK_BASE_REACHED
PICK_OBSERVATION_VALID
PREGRASP_EXECUTED
CONTACT_APPROACH_EXECUTED
GRASP_VERIFIED
ATTACHMENT_ACTIVE
LIFT_EXECUTED
VISIBILITY_CLEAR_EXECUTED
PLACE_BASE_REACHED
PLACE_OBSERVATION_VALID
PREPLACE_EXECUTED
PLACE_DESCENT_EXECUTED
RELEASE_VERIFIED
RETREAT_EXECUTED
TASK_RESULT_VERIFIED
TRAY_TO_GROOVE_DEMO_COMPLETE
~~~

If any gate fails, report the exact last completed stage and smallest next action.

## 7. Git/report

After execution, preserve all evidence, run tests, commit report and only normal fast-forward push if clean.

Create:

~~~text
docs/reports/2026-09-24_P3_8C_TRAY_TO_GROOVE_EXECUTION_REPORT.md
~~~