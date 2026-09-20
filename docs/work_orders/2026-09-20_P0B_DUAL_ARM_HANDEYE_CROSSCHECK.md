# P0B — Dual-arm Epic hand-eye cross-check and BODY-camera final validation

## Context

Integration branch now contains commit:

~~~text
7ca1e1a feat(perception): preserve Epic calibration integration
~~~

with:

- left Epic hand-eye UI transcription;
- right Epic hand-eye UI transcription;
- right hand-eye evidence from 2026-09-18;
- commissioned-looking right-derived T_body_camera in config/system.json;
- body-camera commission scripts/tests.

This phase does NOT start over. It verifies the exact transform semantics, cross-checks left/right independently, validates against board/table evidence, and decides whether the current T_body_camera may remain COMMISSIONED.

## 1. Known matrices

From Epic Pro UI:

~~~text
LEFT
T? =
[-0.7351,  0.5425, -0.4066, -265.8925]
[ 0.6762,  0.5434, -0.4974,  135.9627]
[-0.0489, -0.6406, -0.7663,  365.7358]
[ 0,       0,       0,         1]

RIGHT
T? =
[-0.6776, -0.5341,  0.5056, 147.2561]
[-0.7333,  0.5429, -0.4093,  17.3677]
[-0.0559, -0.6481, -0.7595, 364.9768]
[ 0,       0,       0,         1]
~~~

Do not assume direction only from UI wording.

## 2. First decisive test: left/right semantic cross-check

Using config/robot_world.json, evaluate at least both candidate semantics:

### Hypothesis H1

~~~text
Epic matrix = T_armbase_camera
p_armbase = T_armbase_camera · p_camera
~~~

Compute:

~~~text
T_body_camera_left  = T_body_leftbase  · T_leftbase_camera
T_body_camera_right = T_body_rightbase · T_rightbase_camera
~~~

### Hypothesis H2

~~~text
Epic matrix = T_camera_armbase
~~~

Invert before composition.

For both hypotheses report:

- camera origin in BODY from left/right;
- translation disagreement mm;
- rotation disagreement deg;
- physical plausibility.

The correct semantic must be supported by the two independent arm calibrations. Do not average first.


## 2.1 Expected sanity values from the current UI evidence

Before implementation details drift, the current numbers already imply a strong sanity target.

Using the configured BODY arm-base transforms and interpreting the Epic matrices as `T_armbase_camera`:

~~~text
camera origin from LEFT  ≈ [+0.091874, -0.084155, +1.565736] m
camera origin from RIGHT ≈ [+0.091845, -0.083593, +1.564977] m

translation disagreement ≈ 0.94 mm
rotation disagreement    ≈ 0.72 deg
~~~

The UI matrices are rounded, so do not demand sub-0.1-deg agreement.

Under the inverse semantic hypothesis, the two BODY camera estimates disagree by roughly:

~~~text
translation ≈ 332 mm
rotation    ≈ 56.6 deg
~~~

Therefore H1 should be strongly preferred if Codex reproduces these values.

Using the 2026-09-20 vendor board pose with the RIGHT-derived BODY camera transform should place the board origin approximately at:

~~~text
BODY ≈ [1.064, 0.487, 0.752] m
~~~

and the board +Z normal should be about 1.1 deg from BODY +Z. This is an independent sanity target because the board is physically flat on the ≈0.750 m table.

These values are expectations for regression detection, not hard-coded calibration outputs.

## 3. Preserve raw screenshot rounding

UI matrix is shown at limited decimal precision.

Also reconstruct rotation from the UI rotation-vector fields where possible and compare against the displayed 4x4 matrix.

Report sensitivity caused by UI rounding.

Do not claim sub-mm rotational validation from a 4-decimal screenshot.

## 4. Validate the selected semantic with current vendor-board evidence

Use:

~~~text
worklog/evidence/2026-09-20-epic-board-frame/board_pose.json
~~~

Board frame definition:

- origin = white right-angle marker diagonal from printed label;
- +X short edge;
- +Y long edge;
- +Z surface normal toward camera;
- gridSize 35 mm.

Without fitting anything to the board:

~~~text
T_body_board = T_body_camera · T_camera_board
~~~

Check:

- board origin z vs physical table top ≈ 0.750 m;
- board normal vs BODY +Z / physical flat-board orientation;
- board x/y/yaw plausibility from the annotated image and site layout;
- left-derived and right-derived board BODY pose disagreement.

## 5. Validate with existing pointcloud evidence

Reuse existing camera capture(s). Do not move hardware.

Check:

- support plane tilt in BODY;
- table / ground physical height as appropriate for each selected plane;
- BODY pointcloud visual overlay;
- current camera origin plausibility.

Important: distinguish table plane at ≈0.750 m from ground at ≈0 m. Do not conflate the two.

## 6. Decide the production transform

Preferred hierarchy:

1. if H1 left/right independently agree strongly and right board/table checks pass, keep the existing right-derived T_body_camera as production candidate/commissioned;
2. do NOT numerically average left/right matrices unless the reason for residual rotation disagreement is understood;
3. left calibration may be used as an independent validation source rather than fused source if the current camera/arm geometry timing differs.

Write a machine-readable report under:

~~~text
worklog/evidence/2026-09-20-body-camera-dual-arm-crosscheck/
~~~

including:

- selected semantic;
- T_body_camera_left;
- T_body_camera_right;
- deltas;
- board predictions;
- table/ground checks;
- verdict;
- calibration revision.

## 7. Config gate

Only after cross-check:

~~~text
config/system.json
epic_pointcloud.T_body_camera
epic_pointcloud.T_body_camera_revision
~~~

must be either:

- preserved with a new validation reference, or
- downgraded to CANDIDATE / blocked if validation fails.

Do not silently overwrite with an average.

## 8. Terminal additions

Expose read-only commands:

~~~text
calib body-camera handeye compare
calib body-camera handeye board-check
calib body-camera show
~~~

No motion.

## 9. Exit report

Stop and report:

1. which transform semantic is correct;
2. left camera origin BODY;
3. right camera origin BODY;
4. translation delta mm;
5. rotation delta deg;
6. board BODY pose from each;
7. table/ground checks;
8. final T_body_camera source and revision;
9. state = COMMISSIONED / CANDIDATE / FAIL;
10. whether P1 BODY pointcloud viewer may begin.

No AMR, arm, or gripper motion.
