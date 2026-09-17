# 2026-09-17 点云 → cuRobo 避障规划 Demo 与实时性基准工作单

## 0. 本轮唯一目标

今天剩余时间只做这一条链：

```text
Pixel Pro / EpicRaw
→ CAMERA 点云
→ support plane / LEVEL
→ DEMO_ONLY BODY candidate
→ manipulation ROI
→ robot/tool self-filter
→ table/known geometry separation
→ unknown residual AABB
→ SceneSnapshot / SceneCompiler
→ cuRobo planning-only
→ FREE / AVOID / BLOCK 对比
→ latency benchmark
```

本轮禁止：

- 机械臂、夹爪、AMR 运动；
- 关闭 SafetyKernel；
- 将 DEMO_ONLY 外参写成 COMMISSIONED；
- LLM / Skill Library / Qwen；
- 实时 3D UI / Isaac 可视化重构；
- nvblox / MPC；
- 为了出图伪造 planning-ready 状态。

当前目标是：**今天必须得到一个可展示、可复现、真实使用当前 Pixel Pro 数据的 cuRobo 点云避障规划 Demo，并测清楚整条在线链路的耗时。**

---

# 1. 当前已知事实

当前分支：

```text
feat/e2e-v0-integration-20260917
```

BODY registration 控制点：

- support plane 四帧稳定；
- LEVEL frame 已正确把桌面法向对齐到 +Z；
- 相机相对桌面的 pitch 与现场约 49° 观察一致；
- vendor cam2Base 未恢复；
- 单姿态右臂自动 registration 存在 yaw / XY 多解；
- 因此 production `T_body_camera` 仍为 `null`；
- production `planning_allowed=false` 与 `execution_enabled=false` 必须保持。

不要再重复做 support-plane 证明。下一步直接进入 Demo-only 配准、碰撞世界和规划。

---

# 2. 双轨外参策略：Production 与 Demo 严格分开

## 2.1 Production calibration

生产配置继续保持：

```text
state = UNCOMMISSIONED / INCONCLUSIVE
T_body_camera = null
planning_allowed = false
execution_allowed = false
```

除非获得可追溯 vendor 外参或通过多基准点 / 多姿态 commissioning，否则不改变。

## 2.2 Demo-only candidate

为了今天完成 planning-only 避障 Demo，允许生成一个单独的：

```text
T_body_camera_demo_candidate.json
```

必须显式包含：

```text
state = DEMO_ONLY_UNCOMMISSIONED
planning_scope = OFFLINE_ONLY
execution_allowed = false
source = level_plane + manual/known-body alignment
uncertainty / residual
created_at
source frame IDs / hashes
```

该文件不得被 production pointcloud pipeline 默认读取。

### 2.3 如何尽快补齐 LEVEL → BODY 的 yaw / XY

按优先级：

1. 若仓库 / 服务器能恢复任何真实 camera mount / Epic project / CAD / station 基准，优先使用。
2. 否则利用当前机器人几何与现场结构生成 **人工可审计 control-point / alignment candidate**，不再做无约束 ICP 搜索。
3. 可利用：
   - BODY 对称轴；
   - 左右臂 base 已知位置；
   - 右臂当前 joints 与 cuRobo geometry；
   - 桌面水平面；
   - CAMERA 图像中清晰可辨认的机器人/桌面结构；
   - 任何已有真实安装尺寸。
4. 不得把“看起来对”升级为 production calibration；只用于 Demo overlay / planning-only。

输出一张 `DEMO_ONLY_BODY_OVERLAY.png`，必须同时显示：

- BODY +X/+Y/+Z；
- support table；
- right arm collision geometry；
- central exclusion slab；
- raw / downsampled pointcloud；
- ROI；
- 明显的 `DEMO_ONLY / NOT FOR EXECUTION` 水印或标题。

---

# 3. 点云碰撞世界：今天必须真正跑通

基于 demo candidate：

```text
CAMERA cloud
→ BODY candidate
→ per-arm manipulation ROI
→ table support plane separation
→ robot/tool self-filter
→ voxel 5 / 10 mm 两档
→ optional light outlier filter
→ residual DBSCAN / connected clusters
→ conservative AABB + inflation
```

### 3.1 Known vs unknown 必须分开

不要把桌面切成几十个 residual AABB。

最终世界至少分：

```text
KNOWN_SUPPORT
    table / support slab

KNOWN_ROBOT
    active arm
    inactive arm (if geometry available)
    tool / gripper proxy
    central exclusion

TARGET / ALLOWED_INTERACTION
    不作为普通 forbidden obstacle

UNKNOWN_RESIDUAL
    self-filter / table removal 后剩余点云 → AABB
```

若完整 gripper / inactive-arm geometry 仍不足，可以使用显式 conservative proxy，但必须记录 `proxy=true` 与尺寸来源。

### 3.2 输出必须有 before / after 证据

至少生成：

```text
01_camera_raw.png
02_level_table.png
03_demo_body_overlay.png
04_body_roi.png
05_self_filter_before_after.png
06_known_support_plus_robot.png
07_unknown_residual_clusters.png
08_final_collision_world.png
```

以及机器可读：

```text
pipeline.json
collision_world.json
```

每个阶段记录：

- point_count_before / after；
- runtime_ms；
- frame；
- parameters；
- calibration candidate revision；
- source EpicRaw / PLY SHA256。

---

# 4. SceneSnapshot / SceneCompiler：真实进入 planner，而不是只画图

Demo-only collision world 也必须通过正式数据合同：

```text
ObservationEpoch
→ EnvironmentRevision
→ WorldModel.freeze_snapshot()
→ SceneSnapshot
→ SceneCompiler
→ cuRobo World
```

允许 SceneSnapshot 标记：

```text
planning_scope = DEMO_OFFLINE_ONLY
execution_allowed = false
```

禁止新增一个 `pointcloud → cuRobo` 旁路。

trajectory / planning artifact 必须记录：

```text
scene_snapshot_id
scene/world digest
calibration candidate revision
robot/tool revision
```

---

# 5. 今天必须做的 cuRobo 三组规划 Demo

选择一个当前右臂可达、无接触、只用于 planning 的目标；优先复用已有 verified / benchmark target，禁止为了 Demo 发实机运动。

必须使用**同一起点、同一目标**做三组：

## D-A FREE

```text
只有 known world / 无额外 residual blocker
```

预期：规划成功，作为基线轨迹。

## D-B AVOID

使用真实点云 residual 中位于原直线路径附近的障碍；如果当前真实 residual 不构成明显阻挡，可在真实 collision world 上增加一个明确标记的 `DEMO_OBSTACLE_AUGMENTATION`，但必须与真实点云障碍分层显示。

预期：

```text
trajectory 与 FREE 明显不同
且 collision-free
```

## D-C BLOCK

构造完全堵塞的 planning-only obstacle。

预期：

```text
规划失败
或明确找不到安全路径
```

不得把 `DEMO_OBSTACLE_AUGMENTATION` 伪装成相机检测物。

### 输出

每组保存：

```text
request.json
scene.json / scene digest
trajectory.json (若成功)
planner result
preview.html / png
planning timing
```

最终再生成一个并排或统一 viewer：

```text
FREE vs AVOID vs BLOCK
```

能清楚看见：

- 整个双臂机器人 / 当前 active arm；
- collision objects；
- FREE trajectory；
- AVOID trajectory；
- BLOCK failure。

---

# 6. 实时性：必须测全链，而不是只测 voxel

今天同步新增一个**纯 benchmark，不写图片、不落 PLY**的 fast path。

目标在线链：

```text
camera trigger / frame fetch
→ EpicRaw decode
→ pointcloud/depth array
→ camera→BODY
→ ROI
→ self-filter
→ table removal
→ voxel
→ cluster/AABB (V1 route)
→ SceneSnapshot / compile
→ cuRobo world update
→ collision query / plan
```

## 6.1 Debug path 与 fast path 分离

```text
DEBUG / EVIDENCE MODE
    save EpicRaw/PLY/PNG/JSON

FAST / ONLINE BENCHMARK MODE
    memory only
    no matplotlib
    no PLY write/read roundtrip
    only minimal metadata
```

不要用 DEBUG 模式耗时推断实时性能。

## 6.2 必须记录的 timing

至少：

```text
camera_trigger_ms
frame_fetch_ms
epicraw_decode_ms
pointcloud_build_ms
camera_to_body_ms
roi_ms
self_filter_ms
support_remove_ms
voxel_ms
cluster_aabb_ms
world_commit_ms
scene_compile_ms
curobo_world_update_ms
collision_query_ms
planning_ms
perception_scene_total_ms
full_plan_total_ms
```

对已经有相机硬件的部分至少跑：

```text
warm-up >= 3
measured >= 20 frames
```

规划可另外跑 10–20 次固定 query，以免把 planner cold start 混入每帧 perception latency。

报告：

```text
mean
median/p50
p90
p95
max
Hz equivalent
```

### 6.3 输出运行建议

基于真实测量自动给出：

```text
STATIC_SNAPSHOT
CHECKPOINT_RESCAN
SCENE_WATCHDOG_1HZ
SCENE_WATCHDOG_2HZ
SCENE_WATCHDOG_5HZ
```

哪些当前硬件能稳定满足。

不要直接实现实时 replan / MPC。

---

# 7. 明天周帅旭接手前需要形成的“基座”

今天结束必须至少有：

1. 一个 clean / pushed integration commit；
2. 点云处理脚本：debug + benchmark fast path；
3. DEMO-only BODY candidate 与明确生产隔离；
4. 一份 collision world artifact；
5. FREE / AVOID / BLOCK 三组 cuRobo planning-only Demo；
6. latency benchmark JSON + markdown；
7. Demo 录制提示：什么时候适合录屏、哪些画面能展示；
8. 明天的现场 blocker 清单（只列必须现场做的）。

### 今天不写完整明日手册

等本轮真实结果出来后，再根据结果生成明天逐步执行文档。

---

# 8. 验收标准

本轮 PASS 至少要求：

```text
support plane              PASS
LEVEL                       PASS
DEMO BODY overlay           PASS visually + residual recorded
ROI                         PASS in demo scope
robot/tool self-filter      PASS in demo scope
known table separation      PASS
unknown residual AABB       PASS
SceneSnapshot               PASS (DEMO_OFFLINE_ONLY)
SceneCompiler               PASS
FREE planner                PASS
AVOID planner               PASS with changed trajectory
BLOCK planner               PASS by explicit failure
latency benchmark           COMPLETE
execution_enabled           STILL FALSE
hardware motion             ZERO
```

如果 BODY demo candidate 仍无法稳定生成，则本轮退化验收为：

```text
LEVEL + camera-frame / manually aligned planning demonstration
```

但必须在所有输出上明确标注 `NOT BODY / NOT FOR EXECUTION`，不得阻塞 latency benchmark 本身。

---

# 9. 最终报告

输出：

```text
docs/POINTCLOUD_CUROBO_AVOIDANCE_DEMO_2026-09-17.md
docs/POINTCLOUD_PIPELINE_LATENCY_2026-09-17.md
```

最终总结只回答：

1. 真实点云是否已经进入 SceneSnapshot / cuRobo collision world？
2. FREE / AVOID / BLOCK 是否符合预期？
3. Demo-only BODY candidate 的误差 / 局限是什么？
4. perception scene update 实际能跑多少 Hz？
5. cuRobo planning p50/p95 多久？
6. 明天最少还要做哪 3–5 件现场工作才能进入第一次受监督实机避障规划执行？

然后停止，不执行机械臂。