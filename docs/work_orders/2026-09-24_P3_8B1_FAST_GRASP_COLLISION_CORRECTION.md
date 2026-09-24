> STEERED 2026-09-24: the detailed component-level gripper collision path is no longer a blocking dependency for the first customer demo. Preserve already implemented/tested work, but continue the V1 demo through docs/work_orders/2026-09-24_P3_8B1A_CONTACT_BYPASS_FIRST_PICK.md. Fine contact collision is deferred to docs/todo/2026-09-24_MANIPULATION_COLLISION_HARDENING_TODO.md.

# P3.8B1 — Fast grasp collision-model correction and first real pick gate

Date: 2026-09-24
Priority: SPEED. Do not restart broad audit. Fix the modeling abstraction that is blocking the grasp endpoint, then move directly toward the first physical pick.

## 0. Current evidence

Known production state:

~~~text
CURRENT→50 mm pregrasp = cuRobo SUCCESS
dense minimum clearance ≈ 2.94 mm
central TCP margin ≈ 86.9 mm
right_pick target BODY ≈ [0.691, -0.188, 0.989] m
40% opening-aware union envelope already fixes the earlier full-open false block
~~~

Remaining exact-grasp failure:

- single gripper union envelope overlaps dock/support by about 17.2 mm;
- target deletion does not remove the collision;
- detailed pinned EG2-4C2 component geometry indicates the conflict is caused by the single union abstraction + duplicated inflation;
- with exact/component geometry and no extra tool inflation, the pinned components do not overlap the already-inflated support.

This is therefore a collision-fidelity problem, not a reason to move the base again or reject the grasp concept.

## 1. Do not use one gripper union box for manipulation contact

Retain the union envelope only for:

- unknown gripper opening;
- coarse free-space fail-closed fallback;
- legacy regression.

For manipulation planning, build `GripperComponentCollisionModel` from the pinned EG2-4C2 URDF/meshes.

At a commanded opening percent, evaluate the gripper linkage joints and transform each component into link6 coordinates.

Minimum components:

~~~text
4C2_baselink
4C2_Link1
4C2_Link2
4C2_Link3
4C2_Link4
4C2_Link5
4C2_Link6
~~~

Represent each component as a compact OBB and/or sphere set. Do not wrap all components back into one union AABB.

## 2. Opening-specific geometry

Support at least:

~~~text
50% prepare
40% pregrasp/contact
closed / grasped
20% release/retreat
~~~

Unknown opening still uses conservative full-opening fallback.

For each opening profile record a geometry revision/hash.

## 3. Stage-specific inflation instead of double-padding

The scene support primitives already carry scene inflation (current evidence: about 7 mm).

Do not blindly add the old 8 mm whole-tool inflation again to every contact-stage component.

Use versioned stage policies:

~~~text
FREE_SPACE:
  40% component geometry OR conservative opening-aware envelope
  normal planner clearance policy

PREGRASP_TERMINAL:
  40% component geometry
  component inflation benchmark 0 / 2 / 4 mm

CONTACT_APPROACH:
  40% component geometry
  smallest evidence-supported component inflation
  target tool-contact exemption only inside TargetContactPolicy corridor
  support/non-target objects remain hard
~~~

Select the smallest nonzero inflation that preserves model/pointcloud agreement. If 0 mm component inflation is the only geometry that matches the pinned physical mesh and the scene already carries 7 mm inflation, document it explicitly rather than adding duplicate padding.

Do not lower controller protections or central exclusion.

## 4. Planner/validator must share identical component geometry

Use the same component geometry/revision in:

- persistent cuRobo active tool spheres;
- independent dense validator;
- TargetContactPolicy validator;
- SafetyKernel geometry samples;
- WebUI preview.

Delete the current inconsistency where planner/validator reason about a single union tool box while diagnostic code reasons about components.

## 5. Contact endpoint semantics

Free-space segment:

~~~text
CURRENT → 50 mm pregrasp
``

remains the already successful cuRobo path.

Contact segment:

~~~text
50 mm pregrasp → Epic grasp pose
~~~

must be:

- straight / bounded along the verified approach axis;
- fixed terminal grasp orientation;
- component-level gripper collision checked;
- target contact allowed only for intended gripper/tool components inside the final contact corridor;
- arm links vs target remain hard;
- dock/support and all non-target obstacles remain hard.

No global target deletion.

## 6. Fast diagnostic matrix — stop as soon as a correct model passes

Do not run a large sweep.

Run only:

~~~text
A: current union model (reference expected fail)
B: component model + 4 mm extra tool inflation
C: component model + 2 mm extra tool inflation
D: component model + 0 mm extra tool inflation
~~~

For each evaluate exact grasp endpoint and the full 50 mm contact segment.

Record:

- limiting component;
- limiting scene primitive;
- endpoint signed gap;
- minimum segment gap;
- target-contact overlap only;
- support overlap yes/no;
- arm-link overlap yes/no.

As soon as the component model matches the physical mesh evidence and passes the hard non-target collision test, select it and stop benchmarking.

## 7. Grasp target support semantics

The detected pick target and its support/dock are different semantics.

Ensure the scene binding identifies:

~~~text
TARGET_OBJECT
SUPPORT_SURFACE
NON_TARGET_OBSTACLE
~~~

TargetContactPolicy may relax only TARGET_OBJECT vs allowed tool components.

It must never relax SUPPORT_SURFACE just because the grasp target is nearby.

## 8. Immediate planning closure

After component geometry is selected, produce:

~~~text
CURRENT→PREGRASP_50MM = PASS
PREGRASP→GRASP_CONTACT = PASS
GRASP_ENDPOINT_NON_TARGET_COLLISION = PASS
GRASP_ENDPOINT_TARGET_CONTACT = EXPECTED/VALID
~~~

Then simulate:

- gripper closure;
- attached-object creation;
- vertical lift first 100 mm;
- lift toward BODY z=1.20 m.

If these pass, do not wait for the full place Scheme to perform the first real pick stage.

## 9. Fast path to first physical pick

Once planning-only passes and full tests pass, generate one immutable `FIRST_PICK_EXECUTION_PACKAGE`:

~~~text
move to 50 mm pregrasp
→ gripper 40%
→ bounded contact approach
→ close gripper
→ delayed readback + local 15 cm scene delta
→ if verified, lift 100 mm
→ stop and hold
~~~

This is the first physical checkpoint.

Do NOT continue automatically to base movement/place in this package.

## 10. User action for physical pick

Only after the execution package is ready ask once:

~~~text
USER ACTION — 首次真实抓取授权

确认料盘目标与现场状态未变化、右臂扫掠区无人、左臂保持不动、物理急停可用。

完成后回复：批准首次真实抓取
~~~

After approval execute the immutable package; stop on any contact/verification/controller fault.

## 11. Exit report

Report:

~~~text
GRIPPER_COMPONENT_COLLISION_READY = YES/NO
OPENING_SPECIFIC_GRIPPER_GEOMETRY_READY = YES/NO
DOUBLE_INFLATION_REMOVED = YES/NO
CONTACT_COMPONENT_VALIDATION_READY = YES/NO
GRASP_ENDPOINT_HARD_VALID = YES/NO
PREGRASP_TO_GRASP_CONTACT_PLAN_READY = YES/NO
FIRST_PICK_EXECUTION_PACKAGE_READY = YES/NO
FIRST_REAL_PICK_EXECUTED = YES/NO
FIRST_100MM_LIFT_EXECUTED = YES/NO
~~~

Do not move the base again solely to hide the gripper/support modeling error.

## 12. Git

Small commits.
Run tests after each geometry/validator change.
No force-push.
Keep unrelated coworker changes separate.
Push clean fast-forward checkpoints when safe.