# Current-base A/B obstacle experiment and dual TCP audit

Date: 2026-09-21. Branch: `feat/e2e-v0-integration-20260917`.
State: **planning-only; no AMR, arm or gripper motion; no execution approval**.

## Fresh baseline after the base moved

The previous P3.1 CLEAR cloud and A/B targets are historical evidence, not the
current experiment. A new static Pixel Pro scan was captured at 15:39 local
time: `logs/body_cloud/artifacts/20260921_153921_dd46678d/manifest.json`.
Fresh read-only left/right JAKA joint/tool audits and a whole-robot BODY
geometry snapshot accompany it under
`worklog/evidence/2026-09-21-p3-1-residual-support/current_base_clear/`.
The camera-to-BODY calibration is the commissioned fixed rigid mount; the base
change requires a new scene, not a new free-6DoF camera fit.

The scene contains a dock support near BODY z=0.833 m, observed across roughly
x=0.590–0.748 m and y=-0.455–0.162 m. The small upright experiment box is
**not** present. Conservative cleanup retained 12,839/12,839 cleaned observed
points in the multi-primitive world. Seven old AABBs become 248 observed
primitives (37.1% of the old summed occupied volume). This is an observed-point
model; occluded pockets are not declared free.

## Planning-only A/B contract

The right arm is the active arm; the left arm/tool, table, chassis and central
exclusion remain represented. Current actual joints were used only to construct
candidate targets and a separate current→A reposition preview. A→B and B→A
are **hypothetical-start** planning previews on the static scene; they are not
trajectories eligible for execution from the current actual joints.

| Point | BODY TCP xyz (m) | Right joints (rad) |
|---|---|---|
| A | `[0.704,-0.530,1.052]` | `[0.260,-0.426,0.894,-4.221,-0.807,-0.525]` |
| B | `[0.679,-0.117,1.125]` | `[0.260,0.174,1.094,-4.221,-0.807,-0.525]` |

The TCP endpoints are 0.420 m apart. In the box-free scene, current→A,
A→B and B→A all planned successfully; A→B/B→A TCP paths are about 0.430 m,
with 0.060 m maximum deviation from their straight chord. Each direction
took about 9.75 s of cuRobo planning after initialization. Reported minimum
clearance was +0.103 m in the *current modeled world*; that number is not a
physical clearance certificate, especially given the tool-model issue below.

Three-view layout:
`worklog/evidence/2026-09-21-p3-1-residual-support/current_base_clear/ab_preview_mid/ab_three_views.png`.
Green A, purple B; blue/red planning paths; gray observed BODY cloud. The
orange dashed box at approximate BODY center `[0.69,-0.32,0.945] m` is only a
**placement proposal**, not detected geometry. Proposed box orientation:
224 mm upright, 78 mm edge along BODY X, 205 mm edge along BODY Y. Stability
and actual dock edges override the approximate coordinates.

## Dual-controller TCP readback versus pinned gripper model

The controller UI screenshots supplied by the operator match the fresh SDK
readback. Active right tool ID 1 is `右臂校准1`; active left tool ID 2 is
`左臂校准1`. The old `右臂`/`左臂` entries remain in the controller but are not
the selected tool IDs in these audits.

| | Active TCP in link6/flange frame (mm) | Distance to assumed flange +Z axis | Tool +Z tilt | TCP beyond pinned gripper envelope |
|---|---|---:|---:|---:|
| Left | `[-1.313,+3.024,+180.605]` | 3.30 mm | 1.85° | 31.57 mm |
| Right | `[-3.013,-4.790,+184.380]` | 5.66 mm | 2.50° | 35.35 mm |

The pinned ARES gripper collision envelope extends from the link6 mounting
plane to z≈149.03 mm. The centerline agreement is much better than the old
controller tools (roughly 28–34 mm lateral offsets), but the new TCPs lie
about 32–35 mm ahead of that collision envelope. The two UI screenshots
confirm configured numbers; they are **not physical dimensional evidence**.
Possible explanations include a correct grasp center with an undersized or
mis-mounted digital gripper, or a TCP defined beyond the true contact center.
Neither possibility is resolved from the current scan: the camera view contains
essentially no robot-owned points at this arm pose, so point-cloud overlay
cannot measure the finger tips. The SDK-vs-URDF FK errors (left 0.81 mm, right
1.27 mm maximum over the audit poses) check model/controller consistency, not
physical contact-point accuracy.

Read-only audit figure and JSON:
`worklog/evidence/2026-09-21-p3-1-residual-support/current_base_clear/tcp_audit/`.
Before any physical A↔B experiment, measure flange mounting plane→actual
two-finger contact center on at least the right arm, confirm the selected tool
ID again, and reconcile the active-arm gripper collision extent/TCP with that
measurement. Do not infer a smaller clearance merely from the current cuRobo
number. Left-arm physical calibration should receive the same check before
left-arm execution.

## Next experiment stages

1. Place the box stably on the dock near the marked proposal, without moving
   the base, arms, grippers or camera. Capture a **new** Pixel Pro frame and
   read both arms again. Use the observed box AABB, not the proposed box, to
   judge actual overlap with the A–B chord and both endpoints.
2. In the box-present scene, run A→B and B→A planning-only with exactly the
   same joint A/B contract. Compare box AABB, scene revisions, TCP paths,
   minimum modeled clearance and whole-arm clearance with the box-free pair.
   If the box fails to lie in the planned swept region, reposition the box and
   reacquire; do not label an unchanged path “avoidance.”
3. Run a separate fresh-scan synthetic BLOCK scene. It must fail without
   fallback. Preserve the old single-AABB pipeline as a fail-closed comparator.
4. Only after physical tool geometry, collision model and live-start checks
   are accepted, request explicit one-time authorization for supervised
   current→A and each A↔B leg. Each physical leg requires a fresh scan,
   fresh dual-arm/base state, new SceneSnapshot and trajectory, monitored
   execution, and a stop on scene/state change. This stage has **not** started.

`READY_FOR_SUPERVISED_CLEAR=false` and `READY_FOR_SUPERVISED_AVOID=false`
until the above gates are satisfied. A successful planning-only image does not
override the tool-model discrepancy.

## Completed box-present and BLOCK observations

The operator placed the box without moving the robot. A new Pixel Pro frame
(`logs/body_cloud/artifacts/20260921_161451_830b7857/manifest.json`) gave
an independent `PROTRUDING_OBSTACLE` centered near BODY
`[0.697,-0.329,0.961] m`, observed AABB `[0.085,0.211,0.207] m`.
Its center differs from the proposed placement by about 7 mm in X and 9 mm
in Y. The support surface remained a separate structure. The 207 mm observed
height is shorter than the nominal 224 mm physical box: the lower contact
region is partly unobserved, so the AABB is not a full physical volume model.
All 14,926 cleaned observed points were represented; 9 old AABBs became 243
multi-primitives (25.8% of old summed occupied volume).

On that new scene, both A→B and B→A cuRobo plans succeeded. The observed
box was the **limiting collision object** in both directions. A straight
joint interpolation intersected the box model by 21.78 mm; the optimized
trajectories had +9.63 mm modeled clearance. Relative to the box-free pair,
each TCP path length increased from 0.430 m to 0.453 m; arc-normalized
trajectories diverged by up to 46.6 mm (mean 29.3 mm). This is a meaningful
planning-only avoidance result, not simply two identical paths in differently
named scenes.

Clear/avoid three-view overlay:
`worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/clear_vs_avoid_three_views.png`.
The solid blue/red paths are box-present forward/reverse, dashed green is the
box-free reference, and the solid orange rectangle is the **observed** box.
Numeric and normalized XYZ plots are in `current_base_avoid/comparison/`.

The separate fresh BLOCK capture is
`logs/body_cloud/artifacts/20260921_162925_8006443b/manifest.json`.
An explicitly tagged synthetic enclosure around B produced expected safe
FAILURE for both A→B and B→A, with no fallback trajectory. The goal was
112.04 mm inside the synthetic block model. BLOCK is a planning-only
fault-injection case, not a physical obstacle addition.

The next physical step is **not** immediate execution. First reconcile the
right controller TCP's 184.38 mm flange offset with the pinned gripper model's
149.03 mm extent using a real flange-to-contact-center measurement or a
calibrated touch-off. If the TCP is correct, extend/validate the active-arm
tool collision model. Then rerun CLEAR/AVOID with the corrected geometry and
an explicit supervised execution gate. The current +9.63 mm modeled margin
cannot absorb an unresolved 35 mm tool-extent discrepancy.
