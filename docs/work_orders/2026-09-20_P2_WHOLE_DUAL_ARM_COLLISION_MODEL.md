# P2 — Whole dual-arm collision model and self-filter

## 0. Entry gate

Start only when P1 reports BODY_POINTCLOUD_READY_FOR_SELF_FILTER=YES.

## 1. Audit existing robot assets

Use current ARES-R + pinned ARES assets before downloading anything new.

Known existing assets include:

- ARES URDF with Link0..Link6 meshes;
- gripper meshes;
- cuRobo YAML with link1..6 collision spheres;
- current ARES-R FK audit;
- current BODY left/right base transforms.

Explicitly audit gaps:

- base_link collision spheres;
- gripper spheres currently empty in old YAML;
- actual current gripper model vs old 4C2;
- current tool/TCP;
- left/right model symmetry;
- chassis/housing geometry.

## 2. Produce one validated Mini2 arm model

Separate:

~~~text
kinematics
visual mesh
collision representation
tool/TCP
~~~

Do not replace validated kinematics only because a prettier online mesh exists.

If external/open Mini2 model is used, compare:

- joint origin;
- joint axis;
- link dimensions;
- flange;
- base mounting;
- mesh bounds.

## 3. Whole robot representation

V0 whole-robot policy:

~~~text
active arm:
  cuRobo 6DoF robot model

inactive arm:
  live joints → BODY collision geometry → planning world obstacle
~~~

This is preferred before 12DoF simultaneous planning.

Include:

- both arm bases;
- inactive arm live geometry;
- active tool;
- inactive tool;
- chassis/housing conservative geometry;
- BODY central exclusion.

## 4. Self-filter

Use the exact same validated robot collision geometry to remove robot-owned points from BODY cloud.

Required evidence:

- before cloud;
- robot geometry overlay;
- after cloud;
- removed point count;
- table/known external obstacle retained.

Do not use arbitrary hand-drawn masks as production self-filter.

## 5. cuRobo regression

Run offline:

- FK vs controller regression;
- self-collision;
- obstacle collision;
- inactive-arm collision;
- tool collision.

## 6. Exit

Report:

~~~text
WHOLE_ROBOT_COLLISION_MODEL_READY = YES/NO
SELF_FILTER_READY = YES/NO
~~~

No physical arm execution in P2.
