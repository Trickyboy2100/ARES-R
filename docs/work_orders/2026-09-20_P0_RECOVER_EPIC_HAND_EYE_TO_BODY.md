# P0 — Recover Epic hand-eye and derive production T_body_camera

## 0. Goal

Recover the hand-eye calibration already produced by Epic Pro / ATOM for the fixed Pixel Pro and the two JAKA arm bases, then derive one auditable CAMERA→BODY transform.

Do not begin a new external calibration unless the existing Epic result cannot be recovered or fails validation.

## 1. Why this is first

Epic Pro / ATOM supports hand-eye calibration matrices and runSpace.json can contain cam2Base or cam2baseMatrix. If the current project already contains the left/right hand-eye result, it is the strongest and fastest source.

BODY geometry is already defined in config/robot_world.json:

~~~text
BODY +X forward
BODY +Y left
BODY +Z up

left base  = [0.0, +0.2, 1.2] + configured yaw
right base = [0.0, -0.2, 1.2] + configured yaw
~~~

## 2. Phase P0-A — forensic recovery, read-only

Search the .32 host and all accessible Epic/ATOM project/export/cache locations for:

~~~text
runSpace.json
cam2Base
cam2baseMatrix
handEye
handeye
calibrationResult
space / camera / robot mapping
~~~

Also query read-only SDK APIs:

~~~text
get_handeye_calibration_data()
get_robot_library()
~~~

Do not write camera configuration.

For every candidate record, save under:

~~~text
/home/yikun/ARES-R/logs/calibration/body_camera/epic_import_<run_id>/
~~~

and record:

- source path / project;
- project revision if discoverable;
- camera serial and cameraID;
- spaceID / objectID if applicable;
- arm association left/right;
- installation mode ETH/EIH;
- raw matrix / pose;
- units;
- rotation representation;
- schema evidence;
- SHA256.

## 3. Phase P0-B — determine transform semantics

Do not assume matrix direction only from field name.

For each candidate, explicitly test both interpretations if needed:

~~~text
candidate A: p_armbase = T_armbase_camera · p_camera
candidate B: p_camera  = T_camera_armbase · p_armbase
~~~

Use vendor documentation/schema and geometric validation to resolve the convention.

Preferred canonical internal representation:

~~~text
T_leftbase_camera
T_rightbase_camera
~~~

meaning:

~~~text
p_leftbase  = T_leftbase_camera  · p_camera
p_rightbase = T_rightbase_camera · p_camera
~~~

## 4. Phase P0-C — derive BODY transform independently from both arms

Use config/robot_world.json:

~~~text
T_body_camera_left
  = T_body_leftbase · T_leftbase_camera

T_body_camera_right
  = T_body_rightbase · T_rightbase_camera
~~~

Report delta between the two independent estimates:

- translation norm mm;
- roll/pitch/yaw delta deg;
- SE(3) residual summary.

Do not average two contradictory transforms.

If one arm has no valid calibration, derive from the other and mark single-source.

## 5. Phase P0-D — validation with vendor board and table

Use the already verified vendor board SDK interface:

~~~text
get_calibration_board_pose()
~~~

Board frame definition is known:

- origin = white right-angle marker diagonal from printed label;
- +X short edge;
- +Y long edge;
- +Z board surface normal;
- right-handed;
- gridSize 35 mm.

Validate the imported T_body_camera without fitting to the validation data.

Checks:

1. transform board pose into BODY;
2. board is physically on table;
3. board plane and pointcloud board patch agree;
4. transformed support table is approximately z=0.750 m;
5. table normal approximately BODY +Z;
6. if left/right hand-eye estimates exist, both predict compatible board BODY poses.

Save screenshots and machine-readable residuals.

## 6. Phase P0-E — acceptance

Generate:

~~~text
config/body_camera_extrinsics.site.json
~~~

with:

~~~text
state = UNCOMMISSIONED | CANDIDATE | COMMISSIONED
source = epic_handeye_import
T_body_camera
source_left/source_right
camera_serial
project_revision
space_mapping
matrix_convention
validation_stats
revision/hash
~~~

Do not invent thresholds before seeing actual left/right and board/table residuals. Report the error budget first.

## 7. Fallback if hand-eye cannot be recovered

Only if P0-A proves existing project hand-eye unavailable/unusable:

1. keep vendor-board route as fallback;
2. derive T_body_board from a simple physical survey / later robot-contact method;
3. compute T_body_camera = T_body_board · inv(T_camera_board).

Do not return to free 6DoF ICP as production solver.

## 8. Terminal integration

Add/extend:

~~~text
calib body-camera epic scan
calib body-camera epic candidates
calib body-camera epic import <id>
calib body-camera epic compare-arms
calib body-camera board verify
calib body-camera validate
calib body-camera show
~~~

No motion commands in P0.

## 9. User interaction format

Only request user action when necessary.

Example:

~~~text
USER ACTION 1
目的：Epic project 当前未找到 runSpace/hand-eye 文件。
你现在做：在 Epic Pro 软件中打开当前右臂 Space，并执行“导出运行数据/项目”到 /home/yikun/ARES-R/logs/calibration/body_camera/manual_export/。
完成后回复：已导出。
安全边界：不移动机器人，不修改标定。
~~~

## 10. Exit report

Stop and report:

1. did an existing Epic hand-eye result exist?
2. exact files/API sources;
3. transform semantics;
4. T_body_camera from left;
5. T_body_camera from right;
6. left-right disagreement;
7. board/table validation error;
8. COMMISSIONED / CANDIDATE / FAIL;
9. exact blocker if not commissioned;
10. commit SHA and repo-local evidence paths.

No AMR, arm, or gripper motion.
