# P5 — Pointcloud throughput and scene watchdog optimization

## 0. Entry gate

Do not begin until P0-P4 functional chain is established.

Current known benchmark from earlier work:

~~~text
perception→scene p50 ≈ 4.085 s
cuRobo planning p50 ≈ 1.112 s
sense→plan p50 ≈ 5.186 s
~~~

Main observed bottlenecks:

- frame fetch;
- robot/tool self-filter;
- voxel.

WorldModel/SceneCompiler are not the bottleneck.

## 1. Separate frequencies

Do not tie together:

- camera capture rate;
- scene processing rate;
- GUI render rate;
- collision watchdog rate;
- replan rate;
- servo/control rate.

## 2. Optimization order

1. persistent camera acquisition / stream if SDK allows;
2. avoid file I/O in online path;
3. vectorized/GPU CAMERA→BODY transform;
4. GPU/spatial-index self-filter;
5. GPU/hash voxel;
6. bounded pipeline concurrency;
7. event-triggered replan;
8. only then evaluate nvblox/MPC.

## 3. UI behavior

WebUI scan interval must be user-adjustable but clamped to measured sustainable backend rate.

Always support:

~~~text
Manual Scan Once
~~~

even if auto scan is disabled.

## 4. Runtime modes

Based on measured latency select:

~~~text
STATIC_SNAPSHOT
CHECKPOINT_RESCAN
SCENE_WATCHDOG
REACTIVE_MPC
~~~

Do not label a mode supported until benchmark demonstrates it.

## 5. Exit

Report p50/p90/p95/max for:

- capture;
- decode;
- CAMERA→BODY;
- self-filter;
- obstacle extraction;
- scene compile;
- planning;
- total sense→plan.

Then recommend a default scan interval for WebUI.
