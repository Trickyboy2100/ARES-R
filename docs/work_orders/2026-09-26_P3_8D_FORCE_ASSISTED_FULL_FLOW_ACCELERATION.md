# P3.8D — Force-assisted full-flow acceleration and completion

Date: 2026-09-26
Goal: preserve the successful first real pick, integrate read-only force sensing, accelerate the successful pick stages, and extend HOLD to the complete customer pick-transfer-place demo.

Read first:

~~~text
docs/research/2026-09-26_JAKA_FORCE_SENSOR_AND_FLOW_ACCELERATION.md
docs/decisions/2026-09-24_CONTACT_COLLISION_DEMO_POLICY.md
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
docs/work_orders/2026-09-24_P3_8C_SUPERVISED_EXECUTION.md
~~~

## 0. Preserve the successful first-pick checkpoint first

The successful real pick evidence is currently the most valuable checkpoint.

Before new implementation:

1. record .32 HEAD/status/ahead-behind;
2. preserve all evidence under the successful live-pick directory;
3. create/update a concise execution report;
4. run the full test suite;
5. commit and fast-forward push the successful pick code/evidence if the remote is compatible;
6. keep unrelated coworker AMR/gripper changes isolated.

Do not overwrite the successful evidence.

## 1. Force sensor identity/readout audit — read-only

Do NOT enable force compliance yet.

Audit the current JAKA V2.1.5 Python object and controller state for:

- force/torque related methods;
- raw RobotStatus force fields;
- torq_sensor_monitor_data / actTorque availability;
- configured sensor state/model if any getter/config export is available;
- current force-control frame;
- zero/calibration state if readable;
- current sensor safety limit if readable.

Record a 10–20 s stationary six-axis wrench trace at the current HOLD only as a readout test; do not zero while holding the object.

Output:

~~~text
FORCE_SENSOR_READOUT_READY = YES/NO
FORCE_SENSOR_MODEL = verified model or UNVERIFIED
FORCE_SAMPLE_RATE_OBSERVED_HZ = value
FORCE_FRAME_SEMANTICS = verified / unknown
~~~

## 2. Exact model identification

Current strongest hypothesis from official JAKA specs:

~~~text
JK-SE-VI-200
reason: Mini2 payload 2 kg; JAKA recommends VI-200 for <=5 kg robot class
~~~

Do not silently commission the model from inference.

If controller/App does not expose the configured model, defer one physical USER ACTION until the next on-site opportunity:

~~~text
USER ACTION — 力传感器型号确认
请打开JAKA App的力控配置/关联传感器列表，截一张能看到传感器型号的图；若页面看不到，则拍传感器本体铭牌。
~~~

## 3. Tool-chain geometry correction preparation

Record the force-sensor stack in the tool-chain documentation/model:

~~~text
robot wrist flange
→ force sensor
→ sensor tool-side flange / adapter
→ gripper
→ grasp center / TCP
~~~

Mark the previous 145 mm tape measurement as SENSOR_TOOL_FLANGE_TO_GRASP_CENTER, not robot-flange-to-grasp-center, unless field evidence says otherwise.

Do not change the controller TCP automatically.

## 4. FORCE_MONITOR_V1

Implement a read-only force monitor service.

Concept:

~~~text
ForceSample:
  timestamp
  Fx Fy Fz
  Mx My Mz
  source_frame
  robot joints/TCP
  stage

ForceMonitor:
  start()
  stop()
  baseline(window_s)
  latest()
  window()
  transform_to_body()
~~~

Requirements:

- no force-compliance APIs in V1;
- timestamp force and robot feedback on the same monotonic clock;
- log raw and filtered channels;
- initially support 20–60 Hz software filtering as an experiment, while preserving raw samples;
- fail closed if force data disappears during a force-guarded contact segment.

## 5. Calibrate frame semantics

Before using force directions operationally, verify:

- which actTorque indices correspond to Fx/Fy/Fz/Mx/My/Mz;
- sign conventions;
- whether values are in sensor/tool/force-control frame;
- transform from sensor/tool frame to BODY.

Use read-only/static pose checks first.

Remember:

~~~text
right_pick tool +Z ≈ horizontal BODY +X approach
BODY/world Z = gravity axis
~~~

Therefore contact monitoring may use approach-axis force, while weight verification must use BODY/world vertical force.

## 6. Empty-gripper baseline protocol

At the next empty-gripper opportunity:

1. robot stationary and no external contact;
2. verify tool/load config;
3. zero the force sensor using the normal JAKA mechanism;
4. wait for zero completion;
5. record 1 s baseline;
6. rotate/move only if required by a later calibration subtask;
7. store mean/std/peak and zero-drift evidence.

Do not zero while carrying the object if weight verification is needed.

## 7. FORCE_GUARDED_CONTACT_V1

Keep the already successful CONTACT_BYPASS_V1 collision semantics.

Add physical wrench monitoring to the bounded contact segment:

~~~text
pregrasp
→ baseline
→ straight approach

monitor:
  force projected onto approach axis
  lateral force norm
  torque norm
  derivative/spike

unexpected contact
→ motion_abort
→ HOLD
~~~

Threshold commissioning:

- first record free-air approach traces at the intended speed;
- derive threshold from measured baseline/noise/inertial peaks;
- use a versioned threshold profile;
- do not copy the JAKA 3 N drag-warning value as a universal production threshold.

Controller collision/limit/estop/tracking remain active.

## 8. FORCE_GRASP_VERIFY_V1

Goal: replace the slow post-grasp Pixel Pro verification on ordinary successful cycles.

Keep gripper delayed readback.

Protocol:

~~~text
empty baseline wrench
→ close
→ lift 20–30 mm
→ short settle
→ measure BODY vertical force
→ estimate added weight
~~~

Decision:

~~~text
force confident + gripper readback stable
  → GRASP_VERIFIED_FORCE

force ambiguous
  → fallback to current 15 cm Pixel Pro scene-delta verification

force says no load
  → stop / grasp failed
~~~

Measure the real material/tray mass once and store an expected weight band.

Do not immediately apply payload compensation before this verification.

## 9. Lift/transfer force monitor

During lift and transfer:

- monitor BODY vertical load plateau;
- detect abrupt load loss (possible slip/drop);
- monitor unexpected lateral force/torque (possible snag/contact);
- log force with trajectory progress.

First implementation is monitor + abort only, not compliant control.

## 10. Force-assisted placement monitor

First full-flow version:

~~~text
cuRobo full-scene move to preplace
→ CONTACT_BYPASS_V1 vertical descent
→ force monitor
→ geometric target +5 mm remains nominal stop
→ stop earlier if a commissioned support-contact force event occurs
→ release
→ verify load force returns toward empty baseline
→ retreat
~~~

After this is reliable, placement may become force-terminated rather than geometry-terminated.

Do not enable constant-force compliance in this phase.

## 11. Flow acceleration architecture

Implement a native Scheme runner so the successful stages execute automatically rather than through conversational/manual script orchestration.

Keep these services persistent:

- ART/WebUI backend;
- Pixel Pro capture worker;
- persistent cuRobo planner;
- JAKA feedback reader;
- ForceMonitor.

Scene policy:

~~~text
full fresh scene:
  after every base movement
  before every new free-space plan
  after unexpected physical change

no full scene rescan:
  between pregrasp/contact/initial lift when force feedback is healthy
~~~

Pointcloud grasp verification becomes FALLBACK_ONLY after force verification is commissioned.

## 12. Stage-specific speed tuning

Do not use one speed profile for the entire Scheme.

Create explicit profiles:

~~~text
FREE_SPACE_FAST
CONTACT_FORCE_GUARDED
VERTICAL_LIFT
BASE_TRANSLATION
~~~

Use already successful execution data as the starting point.

Commission by measuring:

- execution duration;
- tracking p95/max;
- force noise/inertial peaks;
- target error;
- abort/fault rate.

The first-pick evidence suggests contact and lift tracking were much tighter than the long pregrasp segment, so those segments are candidates for controlled acceleration after force guard is active.

## 13. Extend HOLD to full task

Continue from successful/verified attachment:

~~~text
attached object active
→ scene-aware move to BODY z≈1.20 / right-front visibility-clear
→ AMR move to PLACE_BASE_POSE_V1
→ BaseMotionObserver SETTLED
→ fresh atomic right_place_rightmost observation
→ scene-aware transfer to preplace
→ force-guarded vertical placement
→ release
→ force/gripper release verification
→ retreat
→ base retreat
→ final result observation
~~~

Use coarse attached-object geometry for V1.

## 14. Time instrumentation

Every Scheme run records:

~~~text
base move time
base settle time
5700 detection time
5000 capture time
scene build time
cuRobo planning time
preflight/package time
free-space execution time
contact execution time
gripper command/readback time
force verification time
pointcloud fallback verification time
report/evidence write time
total task time
~~~

Produce a waterfall comparison:

~~~text
FIRST SUCCESSFUL PICK (~5 min)
vs
FORCE-ASSISTED OPTIMIZED PICK
vs
FULL PICK-PLACE
~~~

## 15. Exit gates

Report:

~~~text
FIRST_PICK_SUCCESS_CHECKPOINT_PRESERVED = YES/NO
FORCE_SENSOR_READOUT_READY = YES/NO
FORCE_SENSOR_MODEL_VERIFIED = YES/NO
FORCE_FRAME_VERIFIED = YES/NO
FORCE_MONITOR_V1_READY = YES/NO
FORCE_GUARDED_CONTACT_READY = YES/NO
FORCE_GRASP_VERIFY_READY = YES/NO
POINTCLOUD_GRASP_VERIFY_FALLBACK_ONLY = YES/NO
FORCE_TRANSFER_MONITOR_READY = YES/NO
FORCE_PLACEMENT_MONITOR_READY = YES/NO
NATIVE_SCHEME_RUNNER_READY = YES/NO
OPTIMIZED_PICK_EXECUTED = YES/NO
FULL_TRAY_TO_GROOVE_EXECUTED = YES/NO
TOTAL_TASK_TIME_S = value
~~~

## 16. User actions

Ask only when physically necessary.

Expected sensor-ID action only if remote configuration cannot identify the model:

~~~text
USER ACTION — 力传感器型号确认
~~~

Expected force baseline action when the gripper is empty and site is ready:

~~~text
USER ACTION — 力传感器空载校零与基线
~~~

Expected full-flow execution authorization only after planning/preflight:

~~~text
USER ACTION — 批准力反馈增强的完整取放流程
~~~

## 17. Git policy

Small commits by subsystem.
No force-push.
Preserve field evidence.
Keep unrelated coworker changes isolated.
Leave .32/GitHub aligned at reviewed checkpoints.