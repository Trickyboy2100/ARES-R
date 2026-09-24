# P3.8B — Full Tray→Groove Scheme planning-only rehearsal

Date: 2026-09-24
Entry: P3.8B0 must report READY_FOR_P3_8B_FULL_SCHEME_PLANNING=YES.

## 0. Goal

Run the complete customer Scheme end-to-end with live AMR/camera observations and real production interfaces, but without arm/gripper motion.

Use:

~~~text
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
~~~

## 1. Scheme inputs

All runtime targets/parameters come through versioned interfaces:

- PICK_BASE_POSE_V1 / relative station contract;
- epoch-bound right-pick observation;
- pregrasp_distance_m;
- gripper prepare/pregrasp/release percentages;
- contact approach policy;
- lift_target_z_m;
- visibility-clear semantic target;
- PLACE_BASE_POSE_V1 / relative station contract;
- epoch-bound right_place_rightmost observation;
- preplace_height_m;
- final_place_offset_m;
- retreat parameters.

No hidden XYZ or raw gripper values in Scheme code.

## 2. First-demo arm policy

For the first customer demo:

~~~text
manipulation_arm = right
left_arm_policy = HOLD_CURRENT
dual_arm_concurrent_execution = OFF
~~~

The left arm remains a live collision obstacle.

Do not block the first right-arm-only customer demo on simultaneous dual-arm execution.

## 3. Planning-only stage sequence

Execute the Scheme state machine logically:

~~~text
PREPARE
→ PICK_BASE_MOVE
→ PICK_DETECT + atomic scene observation
→ MOVE_PREGRASP
→ CONTACT_APPROACH
→ simulated GRASP/ATTACH
→ simulated LOCAL_SCENE_DELTA result
→ LIFT to BODY z≈1.20
→ VISIBILITY_CLEAR
→ PLACE_BASE_MOVE
→ PLACE_DETECT + atomic scene observation
→ MOVE_PREPLACE with attached geometry
→ PLACE_DESCEND to target +5mm
→ simulated RELEASE/DETACH
→ RETREAT
→ VERIFY_RESULT placeholder
→ COMPLETE_PLANNING_ONLY
~~~

AMR/camera may move/run. Arms/grippers remain stationary.

## 4. Digital execution context

For planning phases that logically occur after a simulated arm/gripper state change, use explicit simulated robot/attachment state objects. Do not lie that the physical robot has moved.

Static environment geometry may come from fresh scenes with actual robot self-filtered out, then be compiled against the simulated planning robot state.

Every artifact must state:

~~~text
physical_state = OBSERVED
or
physical_state = SIMULATED_FOR_SCHEME_REHEARSAL
~~~

## 5. Plan every motion segment

For every motion Skill save:

- start robot state source;
- target source/provenance;
- scene snapshot/environment revision;
- attachment revision;
- constraints;
- planner profile;
- trajectory hash;
- minimum hard clearance;
- preferred planner clearance;
- orientation validation;
- predicted duration;
- execution gate result.

## 6. Visualization

Extend current WebUI/Scheme view enough to display:

- current Scheme step;
- pickup/place semantic targets;
- pregrasp/preplace markers;
- contact approach segment;
- lift/visibility-clear targets;
- attached object model;
- cuRobo free-space trajectories;
- base pose stage;
- scene epoch.

Generate one complete planning storyboard/screenshot set.

## 7. Failure/recovery graph

Define explicit transitions:

~~~text
pick detection fail → reacquire observation
pregrasp plan fail → stop/reposition decision
contact validation fail → stop
grasp verification UNKNOWN → stop/reobserve
post-grasp scene unexpected → stop
attached-object transfer plan fail → stop/replan
placement detection fail → reacquire
vertical placement invalid → stop at preplace
release verification UNKNOWN → stop/reobserve
~~~

No blind automatic retries of contact/manipulation.

## 8. ART/Task interface

Implement or finalize:

~~~text
scheme list
scheme inspect RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2
task plan tray_to_groove
task preview
task status
task stop
~~~

`task run` remains locked in P3.8B.

## 9. Acceptance

Report:

~~~text
FULL_SCHEME_PLANNING_ONLY_PASS = YES/NO
PICK_OBSERVATION_EPOCH_BOUND = YES/NO
PREGRASP_FREE_SPACE_PLAN_READY = YES/NO
CONTACT_APPROACH_PLAN_READY = YES/NO
ATTACH_TRANSITION_READY = YES/NO
LIFT_PLAN_READY = YES/NO
VISIBILITY_CLEAR_PLAN_READY = YES/NO
PLACE_OBSERVATION_EPOCH_BOUND = YES/NO
PREPLACE_TRANSFER_PLAN_READY = YES/NO
PLACE_DESCENT_PLAN_READY = YES/NO
DETACH_RETREAT_PLAN_READY = YES/NO
SCHEME_RECOVERY_GRAPH_READY = YES/NO
WEBUI_SCHEME_PREVIEW_READY = YES/NO
READY_FOR_P3_8C_SUPERVISED_EXECUTION = YES/NO
~~~

## 10. Final handoff

If READY_FOR_P3_8C_SUPERVISED_EXECUTION=YES, generate one immutable SchemeExecutionPackage containing all parameters, profile revisions, Skill versions and expected user-facing stages.

Do not execute arms/grippers in this phase.

## 11. Git

Small commits.
No force-push.
Push cleanly after tests.
Leave .32/GitHub aligned.