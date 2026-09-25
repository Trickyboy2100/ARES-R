# Force sensor and full pipeline acceleration plan

Date: 2026-09-25
Status: Design record after first successful physical pick

## 1. Current milestone

The first physical pick checkpoint succeeded:

```text
fresh observation
→ CURRENT→50mm pregrasp
→ contact approach
→ gripper close
→ local verification
→ BODY +Z 100mm lift
→ HOLD
```

Observed execution:

- pregrasp tracking max error: 0.591 deg
- contact tracking max error: 0.036 deg
- lift tracking max error: 0.045 deg
- gripper close readback: about 44/1000
- local pointcloud verification: PASS

The current goal is no longer proving feasibility. The goal is shortening cycle time and improving verification quality.

## 2. Force sensor hypothesis

The robot appears to have a JAKA-compatible force/torque sensor mounted between wrist flange and gripper.

Important hypothesis:

The previous 14 cm vs 18 cm TCP/fixture measurement difference may be explained by measuring the wrist flange/interface instead of the actual end-effector/tool reference after the force sensor and gripper stack.

TODO:

- identify force sensor model;
- identify its coordinate frame;
- determine JAKA tool/TCP configuration;
- verify transform:

```text
robot flange
→ force sensor frame
→ gripper mounting frame
→ actual grasp TCP
```

Do not overwrite current commissioned TCP until verified.

## 3. Potential force sensor applications

### 3.1 Contact protection

Force sensor can complement pointcloud collision avoidance.

Potential use:

```text
planned motion
+ force anomaly detection
→ unexpected contact stop
```

It should not replace scene-aware planning.

### 3.2 Grasp verification

Current verification:

```text
post-grasp pointcloud delta
+ gripper readback
```

Force signal may provide faster confirmation:

During lift:

```text
before lift:
  gravity compensation baseline

lift:
  measure payload-induced wrench change

judge:
  object attached / missing / abnormal
```

Need calibration first:

- sensor bias;
- gravity compensation;
- tool mass;
- payload direction;
- filtering delay.

### 3.3 Contact approach

Force feedback may improve:

- final insertion;
- placement contact;
- avoiding excessive pushing.

Future skill:

```text
approach_until_force_threshold
```

## 4. Proposed acceleration work

### A. Planning speed

Measure and optimize:

- persistent cuRobo instance;
- no repeated warmup solve;
- smaller planning scene when possible;
- cached robot model/collision world;
- asynchronous perception/planning.

### B. Execution speed

Tune:

- A/B commissioning speed profiles;
- ServoJ streaming rate;
- acceleration limits;
- trajectory interpolation.

Keep controller protection unchanged.

### C. Perception speed

Optimize:

- pointcloud ROI;
- voxel resolution;
- only rescan when scene invalidated;
- separate grasp verification scan from full obstacle reconstruction.

## 5. Next physical task extension

Extend current successful pick to:

```text
pick
→ lift
→ move base
→ place
→ release
→ retreat
```

Implementation order:

1. speed up current pick cycle;
2. use force sensor audit in parallel;
3. implement attached-object transfer;
4. implement right_place_rightmost placement;
5. execute full customer demo.

## 6. Long-term architecture

Maintain:

```text
SceneAwareMotion
    handles free-space collision avoidance

Force/Contact Layer
    handles physical interaction verification

Skill Layer
    composes manipulation primitives

Scheme
    defines task order
```

Force sensing is an additional physical feedback channel, not a replacement for perception-based planning.
