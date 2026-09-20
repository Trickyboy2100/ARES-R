# P3 — Production pointcloud obstacle → cuRobo target planning demo

## 0. Entry gates

Require:

- production/CANDIDATE BODY cloud accepted for planning-only;
- whole-robot collision model ready;
- self-filter ready;
- SceneSnapshot/SceneCompiler active.

## 1. Target definition in BODY

Create a target-pose contract:

~~~text
position = [x,y,z] in BODY meters
orientation:
  explicit quaternion/RPY
  OR semantic BODY_FORWARD
~~~

If user omits orientation, do not invent arbitrary Euler angles. Resolve semantic BODY_FORWARD through a versioned per-arm/tool canonical orientation profile.

Terminal:

~~~text
target pose set right x y z [roll pitch yaw]
target pose set left  x y z [roll pitch yaw]
target pose show
~~~

## 2. Production A↔B demo

Each leg:

~~~text
robot settled
→ fresh camera scan
→ BODY transform
→ self-filter
→ table/known geometry
→ residual obstacle scene
→ SceneSnapshot
→ cuRobo plan
→ preview
~~~

Three scenes:

- CLEAR;
- AVOID with a real scanned obstacle;
- BLOCK expected failure.

No reuse of old trajectory after a new scan.

## 3. Planning-only first

Required visualization:

- whole robot;
- BODY cloud/AABB;
- A/B;
- TCP path;
- minimum clearance;
- active/inactive arm;
- scene revision.

Only after planning-only passes can supervised execution be separately authorized.

## 4. Execution gate

UI/Terminal execute must require:

- explicit operator confirmation;
- fresh start state;
- calibration revision match;
- tool/TCP revision match;
- speed profile commissioned;
- SafetyPermit;
- E-stop available.

## 5. Exit

Report:

~~~text
READY_FOR_SUPERVISED_CLEAR = YES/NO
READY_FOR_SUPERVISED_AVOID = YES/NO
~~~
