# P3.4 — Same-day deployment acceleration: fast scene → fast cuRobo → faster supervised A/B

Date: 2026-09-23

## 0. Goal

Today is not a research/architecture day. The goal is to make the already-working right-arm A/B obstacle demo feel like a deployable robot system:

~~~text
fresh scan
→ BODY scene
→ cuRobo plan
→ supervised execution
~~~

with much lower latency and a materially faster A/B motion.

Current measured baseline:

~~~text
camera / BODY scene preparation ≈ 15.2 s
cuRobo request→result          ≈ 54–57 s
  import                       ≈ 1.35 s
  planner init                 ≈ 1.09 s
  explicit world update        ≈ 0.08 s
  formal solve                 ≈ 19.25 s
  discarded warm-up solve      ≈ another ~18–20 s
A/B execution @ ~0.07 rad/s    ≈ 25 s / leg
~~~

Current field evidence:

- B→A at the faster A/B settings completed.
- A→B once stopped at the A/B demo tracking threshold.
- A/B-specific tracking hard-stop was later raised to 0.5 deg.
- B-point robot-adjacent residuals were treated as gripper-owned only after evidence and a targeted 40 mm self-filter expansion.
- Current integration GitHub branch does not yet contain every local field-speed experiment commit; preserve them before refactoring.

Desired same-day targets (engineering goals, not guaranteed promises):

~~~text
scene preparation target:       <= 8 s
warm cuRobo plan target:         <= 8–10 s
fresh scan → trajectory target:  <= 15–20 s
A/B physical leg target:         ~15–18 s if 0.10 rad/s proves trackable
~~~

Do not implement WebUI, nvblox, MPC, left-arm motion, grasping, or new A/B targets in P3.4.

## 1. P3.4-0 — preserve and consolidate current .32 field state

Before changing performance code:

1. record .32 branch/HEAD, git graph and dirty/untracked files;
2. preserve all local A/B execution/speed commits and evidence;
3. separate coworker AMR changes from this task;
4. make one clean local checkpoint containing only the right-arm A/B demo speed/tracking/self-filter/runtime changes that are intended to survive;
5. run the full test suite.

Do not lose the current working B→A execution evidence.

Do not force-push.

If the integration branch has diverged from GitHub, use the trusted relay/replay workflow already used earlier.

## 2. P3.4-A — instrument actual latency first

Add precise timing to the current online path so every leg records:

### Camera/scene

- process startup;
- EpicEye import;
- trigger_frame;
- get_frame_in_epicraw;
- raw-document load;
- pointcloud decode;
- PLY/NPY write;
- CAMERA→BODY;
- ROI;
- pre-voxel;
- self-filter;
- cleanup;
- support/object decomposition;
- primitive generation;
- SceneSnapshot / SceneCompiler.

### Planner

- process startup;
- torch/curobo import;
- planner construction;
- planner warm-up/capture;
- update_world;
- solve;
- interpolation;
- independent dense validation;
- serialization;
- request→result wall time.

### Execution

- packaging/resampling;
- execution wall time;
- p50/p95/max tracking error;
- deadline lag;
- final joint/TCP error.

Store one machine-readable timing record per leg and a rolling run counter.

## 3. P3.4-B — fast Pixel Pro planning capture path

The current vendor capture example performs work that the online planner does not need:

- image decode/write;
- depth grey write;
- pointcloud PLY write;
- texture alignment;
- aligned texture write;
- second colored PLY write.

Keep the existing evidence/debug capture path unchanged.

Add a separate ONLINE_PLANNING capture path.

### 3.1 Minimum online data

For planning, decode only what is needed:

~~~text
trigger_frame(pointcloud=True)
→ one get_frame_in_epicraw
→ one raw document
→ XYZ pointcloud
~~~

RGB is optional for the planning path.

Do not create image8bit/depthGrey/alignedTexture/colored PLY during ordinary A/B scans.

### 3.2 Persistent SDK runtime

Benchmark:

~~~text
A. current subprocess capture
B. persistent EpicEye worker with SDK imported once
~~~

The worker may communicate via a local Unix socket / pipe / small RPC contract.

It must return:

- frame ID;
- capture timestamp;
- XYZ array artifact/shared file;
- pointcloud SHA/hash;
- camera revision.

A worker crash must fail closed; no reuse of an old frame.

### 3.3 In-memory / binary artifact

Prefer a fast binary ndarray artifact for the online path (e.g. NPY/mmap) rather than PLY if this materially reduces time.

Evidence mode may still save PLY asynchronously or on demand.

## 4. P3.4-C — scene processing acceleration without losing obstacle fidelity

The current self-filter runs over roughly two million points.

Benchmark an ONLINE_AB_DEMO pipeline that performs:

~~~text
invalid removal
→ CAMERA→BODY
→ task/reachable BODY ROI crop
→ early voxel downsample
→ whole-robot self-filter
→ sparse cleanup
→ support/object decomposition
→ obstacle primitives
~~~

Candidate voxel sizes:

~~~text
5 mm
7.5 mm
10 mm
~~~

Do not choose by speed alone.

Acceptance must preserve:

- the P1 known-box dimensions/position within the previous error scale;
- table/support structure;
- A/B obstacle classification;
- CLEAR/AVOID planner result;
- no new ghost obstacle from sparse points.

Use obstacle inflation to account for voxel resolution where appropriate.

Do not globally delete unseen space.

Select the fastest pipeline that preserves the above.

## 5. P3.4-D — persistent cuRobo planner service

This is the highest-priority planning optimization.

Refactor the current production planner into a long-lived runtime:

~~~text
process start
→ import torch/curobo once
→ load robot once
→ construct planner once
→ optional one-time warm-up
→ wait for requests

for every fresh leg:
    receive fresh compiled SceneSnapshot
    verify scene/revisions
    planner.update_world(new_world)
    solve ONCE
    independent dense validate
    return trajectory
~~~

Required properties:

- one persistent process for the right-arm A/B demo;
- no planner object rebuild per leg;
- no discarded full solve per request;
- exactly one formal solve per ordinary request;
- fresh update_world on every SceneSnapshot;
- old world cannot survive a CLEAR↔AVOID switch;
- crash/restart invalidates pending trajectory/lease;
- output binds to the new scene digest;
- existing one-shot worker remains available as fail-closed fallback/debug.

Expose backend/ART controls:

~~~text
planner service start
planner service status
planner service stop
planner service benchmark
~~~

Do not expose a generic shell.

## 6. P3.4-E — planner speed benchmark and fast profile

Use frozen CLEAR and AVOID requests first.

Benchmark:

~~~text
A current: new process + full warm-up solve + formal solve
B new process + single solve
C persistent planner + single solve
D persistent + single solve + CUDA graph if supported/stable
~~~

At least 5 measured requests per CLEAR/AVOID for C/D after initial warm-up.

Record:

- p50/p95 request latency;
- solve time;
- success rate;
- minimum dense clearance;
- trajectory path length;
- trajectory hash;
- planner memory;
- CLEAR→AVOID→CLEAR world-switch correctness.

### 6.1 Seed/profile reduction only if needed

If persistent single-solve is still above ~10 s, benchmark a small profile matrix:

~~~text
IK/trajopt seeds:
8/8 baseline
4/4
4/2
~~~

Also consider max_attempts / graph-attempt changes one variable at a time.

Select the fastest profile that preserves:

- CLEAR success;
- AVOID success;
- BLOCK failure;
- accepted clearance;
- visually acceptable trajectory.

Version this as an explicit A/B demo planner profile; do not silently overwrite global defaults.

## 7. P3.4-F — movement speed commissioning

The current ~25 s leg is too slow for the demo.

The site ceiling remains:

~~~text
max joint velocity = 0.10 rad/s
max joint acceleration = 0.20 rad/s²
~~~

P3.4 may commission a faster A/B-demo-only motion profile up to, but not above, the site ceiling.

Do not change unrelated robot modes.

### 7.1 Keep trajectory geometry fixed

For speed testing, use the same validated CLEAR cuRobo geometric path.

Only change time scaling / sample timing.

Do not simultaneously change A/B, scene geometry and speed.

### 7.2 Servo tracking threshold

The 0.2 deg/0.5 deg A/B-specific software tracking stop is an execution monitor, not a physical controller limit.

Make it an explicit versioned A/B-demo setting rather than a hidden literal.

The test may evaluate a larger A/B-demo tracking stop threshold, but:

- controller estop/collision/limit protections remain unchanged;
- native deadline/fault checks remain unchanged;
- the threshold must be logged per run;
- actual measured tracking error, not merely threshold value, determines whether a speed is commissioned.

Suggested maximum experiment range:

~~~text
A/B demo software tracking stop: up to 1.0 deg
site joint speed:                 up to 0.10 rad/s
~~~

Do not modify global safety behavior for other motion modes.

### 7.3 Speed ladder

Use a CLEAR environment and a path with comfortable modeled clearance.

Preferred ladder:

~~~text
0.07 rad/s  (existing evidence)
0.08 rad/s
0.09 rad/s
0.10 rad/s  (site ceiling)
~~~

A completed run at a lower level is not required to repeat if equivalent evidence already exists.

For each run record:

- requested cap;
- actual execution duration;
- max / p95 / RMS tracking error;
- deadline lag;
- abort/fault;
- final joint/TCP error;
- modeled path clearance;
- trajectory hash.

### 7.4 Speed acceptance

Commission the fastest level that:

- completes the leg;
- has no controller fault/collision/limit event;
- has no feedback/send deadline fault;
- final arrival is within existing acceptance;
- measured tracking remains below the chosen A/B-demo tracking threshold with useful margin;
- observed physical motion remains smooth.

Do not exceed 0.10 rad/s without a separate site-limit decision.

Desired demo outcome:

~~~text
A/B leg ≈ 15–18 s
~~~

If 0.10 rad/s still takes longer, report the geometric/joint-limited reason rather than increasing beyond the site ceiling.

## 8. USER ACTION policy

Codex must ask for only one physical action at a time.

### USER ACTION 1 — speed test readiness

~~~text
目的：
开始右臂 CLEAR 速度梯度测试。

你现在做：
确认右臂 A/B 扫掠空间没有外部障碍，左臂和底盘保持静止，现场有人观察且物理急停可用。

完成后回复：
“CLEAR速度测试现场已就绪”

安全边界：
本轮只测试右臂既有 CLEAR 路径，不移动底盘/左臂/夹爪。
~~~

After this single confirmation, Codex may run the predeclared speed ladder automatically, stopping on the first fault/abort or unacceptable tracking result.

Do not ask for repeated confirmation between every speed level unless the robot/site state changes.

### USER ACTION 2 — obstacle demo readiness

Only after fast CLEAR is commissioned:

~~~text
目的：
验证快速 fresh-scan → AVOID planning → execution chain。

你现在做：
把已验证的规则盒子放到 A/B 路径中；机器人、底盘、双臂不要移动。

完成后回复：
“AVOID盒子已放置”

安全边界：
只改变外部盒子。
~~~

## 9. P3.4-G — integrate into ART

The optimized system must remain backend-first.

Add/extend ART commands:

~~~text
demo ab status
demo ab start-clear-loop --cycles N
demo ab stop

planner service status
planner service start
planner service stop

scene fast-scan
scene timing

demo ab speed status
demo ab speed-test
~~~

Every run must expose:

- run index;
- leg index;
- mode CLEAR/AVOID;
- scan time;
- scene-build time;
- planning time;
- execution time;
- trajectory hash;
- minimum modeled clearance;
- speed cap;
- tracking threshold;
- measured max tracking error;
- result.

Do not implement WebUI in P3.4.

## 10. Today execution order

Execute in this order:

~~~text
0. preserve/consolidate local field state
1. timing instrumentation
2. fast camera capture benchmark
3. early-voxel/scene benchmark
4. persistent planner + remove per-request warm-up solve
5. persistent planner benchmark
6. choose fast planner profile
7. CLEAR speed ladder (USER ACTION 1)
8. commission fastest stable A/B speed <=0.10 rad/s
9. run 2–3 CLEAR round trips with scan-before-each-leg
10. if stable, USER ACTION 2
11. run observed-box AVOID round trip
~~~

If an earlier stage fails, fix that stage before moving on.

## 11. Same-day success targets

Report:

~~~text
FAST_CAMERA_PATH_READY = YES/NO
FAST_SCENE_PIPELINE_READY = YES/NO
PERSISTENT_PLANNER_READY = YES/NO
FAST_PLANNER_PROFILE_READY = YES/NO
PLANNER_WARM_P50_S = value
SCAN_TO_TRAJECTORY_P50_S = value

AB_SPEED_PROFILE_COMMISSIONED = YES/NO
AB_COMMISSIONED_SPEED_RAD_S = value
AB_TRACKING_STOP_THRESHOLD_DEG = value
AB_LEG_DURATION_S = value

CLEAR_FAST_ROUNDTRIP_EXECUTED = YES/NO
AVOID_FAST_ROUNDTRIP_EXECUTED = YES/NO
~~~

Also give before→after latency table.

## 12. Git policy

Make small local commits per major subphase.

Do not force-push.

Because .32 has local field changes not yet all present on GitHub:

- preserve them first;
- keep coworker AMR changes separate;
- after a major subphase passes tests, a normal fast-forward push is allowed ONLY if the remote integration HEAD has not changed and the pushed commit contains no unrelated dirty work;
- otherwise use the already established relay/replay workflow.

At the end of the day, leave .32 and GitHub aligned.
