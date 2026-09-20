# P2 — Whole dual-arm collision model, robot overlay and self-filter

## 0. Entry gate

P1 has passed and is pushed:

~~~text
integration HEAD:
c5ed44515cbe4d5e298f74117f4ac02bbccb3f20

BODY_POINTCLOUD_READY_FOR_SELF_FILTER = YES
BODY_CLOUD_VIEWER_READY = YES
LIVE_VIEWER_PROTOTYPE_READY = YES
~~~

Known P1 hold-out:

~~~text
box AABB cloud ≈ 83.8 × 209.1 × 230.5 mm
manual         ≈ 78 × 205 × 224 mm
center X cloud ≈ 0.8206 m
manual X       ≈ 0.835 m
~~~

P2 does not recalibrate T_body_camera.

No AMR, arm, or gripper motion.

## 1. P2-A — asset audit before changing geometry

Use current ARES-R and pinned ARES assets before downloading anything new.

Audit and report separately:

1. kinematics;
2. visual mesh;
3. collision representation;
4. tool/TCP;
5. gripper;
6. BODY mounting.

Known starting facts:

- ARES has Link0..Link6 STL meshes and URDF;
- old cuRobo YAML has collision spheres for link1..link6;
- old gripper 4C2 links have empty collision sphere lists;
- current ARES-R preview model intentionally removes visual/collision meshes;
- current FK has already been validated against controller FK;
- BODY left/right base transforms are already commissioned.

Do not replace validated kinematics merely because a prettier online model exists.

If an external/open Mini2 model is considered, first compare joint origins, axes, link lengths, flange, base mounting and mesh bounds.

Output:

~~~text
docs/ROBOT_COLLISION_MODEL_AUDIT_2026-09-20.md
~~~

and a machine-readable manifest.

## 2. P2-B — whole-robot geometry overlay BEFORE filtering

This is the first visual gate.

Create a reusable geometry exporter that takes live/read-only joint snapshots and returns BODY-frame robot geometry for BOTH arms.

Preferred first representation:

~~~text
validated link collision spheres
+ explicit conservative base/housing proxies
+ explicit tool/gripper proxies where exact geometry is not yet commissioned
~~~

Each proxy must be labelled:

~~~text
EXACT
VALIDATED_FROM_EXISTING_MODEL
CONSERVATIVE_PROXY
MISSING_BLOCKER
~~~

Do not silently pretend old 4C2 geometry equals the current physical gripper.

Extend the P1 BODY viewer to show:

- raw BODY pointcloud;
- left arm collision spheres;
- right arm collision spheres;
- left/right base frames;
- tool/gripper collision geometry;
- chassis/body conservative geometry if available;
- central BODY exclusion;
- current joint revision/timestamp.

Required screenshot:

~~~text
raw BODY cloud + dual-arm robot collision overlay
~~~

At this phase, do NOT remove points yet.

## 3. P2-C — self-filter using the SAME geometry

Only after the overlay is visually/plausibly correct.

Self-filter rule:

~~~text
for each BODY cloud point:
  remove only if inside commissioned/conservative robot-owned geometry
  plus an explicit filter margin
~~~

The geometry used for filtering must be the same source used later for planning collision.

No arbitrary image-space masks or hand-drawn BODY boxes as production self-filter.

Start with a conservative configurable margin. Benchmark at least a few values offline, e.g. around 10/20/30 mm, and show the effect.

Required evidence:

- raw cloud;
- geometry overlay;
- filtered cloud;
- removed point count / percentage;
- remaining table;
- remaining known box from P1;
- before/after known-box AABB so the box is proven not to be carved away;
- before/after table retention;
- per-arm removed counts if possible.

## 4. P2-D — inactive-arm obstacle representation

V0 dual-arm rule:

~~~text
active arm:
  cuRobo 6DoF robot model

inactive arm:
  live joints
  → BODY collision geometry
  → planning-world obstacle
~~~

Implement the data contract now, but do not run a motion plan in P2.

Show a viewer state for both:

~~~text
active=right, inactive=left
active=left,  inactive=right
~~~

The inactive arm must remain visible in the world.

## 5. P2-E — tool/gripper/base completeness decision

P2 may finish with staged readiness.

Allowed exit states:

~~~text
ARM_LINKS_READY
GRIPPER_PROXY_ONLY
BASE_PROXY_ONLY
WHOLE_ROBOT_READY
~~~

If the current physical gripper model cannot be identified precisely today, use a conservative proxy for self-filter/visualization and mark it explicitly. Do not block all progress if the arm links themselves are validated.

However, P3 supervised execution requires tool/gripper collision geometry to be adequate for the selected demo.

## 6. Offline regression only

Run offline/read-only:

- FK vs controller regression from existing evidence;
- collision sphere transform regression for both arms;
- left/right BODY base transform regression;
- self-filter synthetic tests;
- known-box retention test;
- inactive-arm scene export test;
- tool/base proxy provenance test.

Do NOT start the P3 A↔B cuRobo demo in this phase.

## 7. Terminal / viewer commands

Add read-only commands such as:

~~~text
robot collision inspect
robot collision show
scene body-cloud show --robot
scene body-cloud self-filter
scene body-cloud self-filter-show
~~~

Names may be adapted to current ART grammar, but one canonical backend path must be shared.

## 8. Exit criteria

Report:

~~~text
ROBOT_COLLISION_OVERLAY_READY = YES/NO
ARM_LINK_COLLISION_MODEL_READY = YES/NO
WHOLE_ROBOT_COLLISION_MODEL_READY = YES/NO
SELF_FILTER_READY = YES/NO
INACTIVE_ARM_OBSTACLE_READY = YES/NO
P3_ALLOWED = YES/NO
~~~

Include:

- asset audit summary;
- exact/proxy/missing geometry table;
- before/overlay/after screenshots;
- removed-point statistics;
- known-box retention error;
- table retention;
- latency of robot geometry export and self-filter;
- tests;
- local commit SHA.

## 9. Push policy

Commit locally on:

~~~text
feat/e2e-v0-integration-20260917
~~~

Then STOP.

Do not push P2 automatically. Return to ChatGPT for review and explicit push instruction.
