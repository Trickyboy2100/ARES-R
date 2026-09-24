# P3.8B1A — Fast contact-bypass path to first real pick

Date: 2026-09-24
Priority: FIRST REAL PICK TODAY

Read first:

~~~text
docs/decisions/2026-09-24_CONTACT_COLLISION_DEMO_POLICY.md
docs/todo/2026-09-24_MANIPULATION_COLLISION_HARDENING_TODO.md
docs/schemes/2026-09-24_RIGHT_ARM_TRAY_TO_GROOVE_STAGE_DEMO_V2.md
~~~

## 0. Steering instruction

STOP expanding the fine gripper component collision implementation for the first demo.

Do NOT revert already completed/tested component-geometry work.

Keep it compiled/tested as optional diagnostics / future V2 hardening, but remove it as a mandatory gate from the V1 first-pick path.

The active V1 runtime policy is CONTACT_BYPASS_V1.

## 1. Free-space remains unchanged

Use the already successful production path:

~~~text
fresh atomic right_pick observation
→ SceneAwareMotionService
→ cuRobo
→ CURRENT → 50 mm pregrasp
~~~

No ordinary free-space collision checks are disabled.

Keep:

- fresh pointcloud world;
- right-arm link collision;
- inactive left arm;
- central exclusion;
- controller/native protections.

## 2. Implement CONTACT_BYPASS_V1

Create a small explicit manipulation policy/API.

Concept:

~~~text
ContactBypassPolicy(
  policy_id = CONTACT_BYPASS_V1
  active_tool_world_collision = false
  arm_link_world_collision = true
  inactive_arm_collision = true
  self_collision = true
  central_exclusion = true
  bounded_cartesian_only = true
  automatic_expiry = true
)
~~~

It may only be created by reviewed manipulation Skills / Scheme stages.

Generic free-space SceneAwareMotion must reject attempts to use this bypass.

## 3. First pick contact segment

Use the existing 50 mm pregrasp.

Contact segment:

~~~text
PREGRASP
→ fixed-orientation straight Cartesian approach
→ Epic grasp pose
~~~

Requirements:

- start/end pose explicit;
- approach direction from the bound right_pick observation;
- length approximately 50 mm;
- dense IK / joint-limit validation;
- arm Link1–Link6 still checked against world;
- inactive left arm still hard;
- central exclusion still hard;
- active right gripper/tool vs observed pointcloud world ignored for this segment.

Do not delete pointcloud objects from LocalScene.
Do not mutate the underlying SceneSnapshot.
The bypass is an execution/planning policy scoped to this segment.

## 4. Grasp + initial escape

After contact approach:

~~~text
close gripper
→ delayed readback
→ local TCP scene delta
→ if grasp verification accepted:
     BODY +Z lift 100 mm
~~~

For this first 100 mm lift:

- CONTACT_BYPASS_V1 remains active for active gripper/tool vs observed pointcloud;
- arm links remain hard against world;
- lift is straight BODY +Z;
- no lateral motion;
- no ordinary free-space replanning during the bypass lift.

At +100 mm, CONTACT_BYPASS_V1 expires automatically.

## 5. Coarse attachment after escape

Do NOT block the first demo on fine object mesh.

Create a coarse attached-object collision representation from the bound target primitive:

- use target AABB/OBB;
- transform it to TCP/link6 local frame at grasp;
- retain source SceneObject / observation lineage;
- use a small explicit attachment inflation;
- revision/hash it.

After the +100 mm escape:

~~~text
fresh scene
→ target is no longer a static world obstacle
→ coarse attached object becomes moving collision geometry
→ resume full SceneAwareMotion + cuRobo
~~~

Planner, dense validator and SafetyKernel must share this coarse attached-object revision.

## 6. Symmetric placement policy

Implement the same V1 stage policy for the placement end:

~~~text
full SceneAwareMotion → preplace
→ CONTACT_BYPASS_V1 vertical descent
→ final TCP = detected placement target + BODY +Z 0.005 m
→ gripper 20%
→ detach
→ initial vertical retreat
→ CONTACT_BYPASS_V1 OFF
→ fresh scene
→ full collision mode
~~~

Do not yet execute physical placement in this subphase.

## 7. FIRST_PICK_EXECUTION_PACKAGE

Once planning-only checks pass, create an immutable package:

~~~text
FIRST_PICK_EXECUTION_PACKAGE

1 fresh atomic right_pick observation
2 cuRobo move to 50 mm pregrasp
3 gripper → 40%
4 CONTACT_BYPASS_V1 straight approach to grasp
5 close gripper
6 delayed readback + local 15 cm scene delta
7 if verified: straight BODY +Z lift 100 mm
8 expire CONTACT_BYPASS_V1
9 create coarse attached-object collision
10 HOLD / STOP
~~~

Bind package to:

- observation ID;
- SceneSnapshot;
- pointcloud SHA;
- right_pick detection ID;
- target pose;
- pregrasp distance;
- contact-bypass policy revision;
- gripper commands;
- trajectory hashes;
- controller/tool revisions.

## 8. Physical execution gate

After package is ready and tests pass, ask exactly once:

~~~text
USER ACTION — 首次真实抓取授权

确认料盘目标与现场状态未变化，右臂扫掠区无人，左臂保持不动，物理急停可用。

完成后回复：
批准首次真实抓取
~~~

After authorization:

- reacquire fresh atomic observation;
- rebuild exact package if provenance changed;
- execute once;
- stop after 100 mm lift / HOLD;
- do not continue to placement automatically.

## 9. Acceptance

~~~text
FINE_COMPONENT_MODEL_DEFERRED_TO_TODO = YES
CONTACT_BYPASS_V1_READY = YES/NO
GENERIC_FREE_SPACE_STILL_FULL_COLLISION = YES/NO
PREGRASP_TO_GRASP_BYPASS_PLAN_READY = YES/NO
GRASP_VERIFICATION_READY = YES/NO
INITIAL_100MM_BYPASS_LIFT_READY = YES/NO
COARSE_ATTACHED_OBJECT_READY = YES/NO
FIRST_PICK_EXECUTION_PACKAGE_READY = YES/NO
FIRST_REAL_PICK_EXECUTED = YES/NO
FIRST_100MM_LIFT_EXECUTED = YES/NO
~~~

## 10. Git

Do not revert the component model commits.
Keep optional V2 code/tests.
Make the V1 bypass policy explicit and versioned.
Small commits.
No force-push.