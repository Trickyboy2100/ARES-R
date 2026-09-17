# 2026-09-17 下一控制点：BODY 配准、真实碰撞世界与 cuRobo Dry-Run

## 0. 本轮唯一目标

本轮不要继续 Skill Library / LLM / Qwen，不做新的架构扩张，也不要执行机械臂、夹爪或底盘运动。

当前 integration 分支已经具备：

- 经过审计的 Epic 5700 parser / candidates / metadata；
- per-arm Epic profile（当前均 UNCOMMISSIONED）；
- full-SE(3) tool/TCP 与 IK 修正；
- WorldModel / SceneSnapshot；
- DualArmSafetyKernel 与 fail-closed motion gateway；
- 4 帧 Pixel Pro 静态 EpicRaw / PLY；
- CAMERA-frame voxel / cluster / AABB pipeline；
- 当前 controller tool revision 与 speed profiles。

当前真正阻塞真实点云避障的是：

```text
T_body_camera 未恢复/未验收
→ CAMERA 点云不能进入 BODY
→ BODY ROI / robot self-filter 不能可信执行
→ 不能形成 planning-ready SceneSnapshot / cuRobo collision world
```

因此本轮唯一主线是：

```text
CAMERA cloud
→ support-plane / LEVEL candidate
→ recover or estimate T_body_camera candidate
→ BODY overlay
→ BODY ROI
→ robot/tool self-filter
→ table/known geometry separation
→ unknown residual AABB
→ SceneSnapshot / cuRobo world dry-run
```

最终目标不是“红框更多”，而是输出一个可审计的 BODY-frame collision-world control point。

---

# 1. 安全与边界

本轮允许：

- Pixel Pro / EpicEye SDK 只读或拍照采集；
- 读取 JAKA 左右臂 joints / TCP / tool data；
- 离线点云、URDF、cuRobo、Open3D、优化/可视化；
- cuRobo planning-only / IK-only / collision query；
- 生成候选标定、scene、trajectory、报告。

本轮禁止：

- JAKA `joint_move` / `servo_j` / ServoJ sender；
- 夹爪运动；
- AMR 运动；
- JAKA controller/App 写设置；
- 把自动估计得到的外参直接标记为 `COMMISSIONED`；
- 在 `T_body_camera` 未通过证据门前输出 `planning_ready=true`；
- 通过放宽安全门或修改 `execution_enabled=false` 来获得运动权限。

保持：

```text
execution_enabled = false
```

---

# 2. 输入证据

优先使用当前分支和服务器已保存证据：

```text
feat/e2e-v0-integration-20260917
/home/yikun/ARES-R_AUDIT_20260917/afternoon/captures/
/home/yikun/ARES-R_AUDIT_20260917/afternoon/pointcloud_pipeline/
/home/yikun/ARES-R_AUDIT_20260917/afternoon/jaka_readonly_state.json
```

重点文件：

```text
scripts/process_static_pointcloud.py
config/robot_world.json
config/jaka_tools.site.json
config/pointcloud_pipeline.site.json
src/ares_r/world/*
src/ares_r/safety_kernel.py
src/ares_r/motion/se3.py
当前 cuRobo robot YAML / URDF / collision sphere config
```

已有四帧静态 PLY 每帧约 1.897M valid points；10 mm voxel 后约 15.5k points。不要重新证明 voxel 能运行；把时间用于 frame / geometry / self-filter。

---

# 3. Phase A：多平面检测，先建立 LEVEL_FRAME_CANDIDATE

## A1. multi-plane RANSAC

在四帧新采集点云上实现/扩展离线工具：

```text
invalid / zero removal
→ mm → m
→ 10 mm voxel（默认，可同时保留 5 mm 对照）
→ iterative RANSAC plane segmentation
```

至少提取前 3–5 个主要平面；每个 plane 保存：

```text
plane_id
normal_camera
plane_d
inlier_count
inlier_ratio
AABB / extent
RMS residual
centroid_camera_m
```

不要写死“最大平面 = 桌面”。

## A2. support/table candidate ranking

设计明确的 ranking evidence：

- 多帧法向与 offset 稳定；
- 面积/extent 足够大；
- 距离相机符合工作区域；
- 位于当前机械臂/桌面可视区域；
- 与现场“约 1 m 附近大平面”的观察一致；
- 在四帧中可重复找到。

输出：

```text
support_plane_candidates.json
```

以及 4 帧 overlay。

## A3. LEVEL_FRAME_CANDIDATE

使用最可信 support plane 的 normal 只求：

```text
camera roll/pitch → level +Z
support plane → candidate vertical origin
```

生成：

```text
T_level_camera_candidate
```

但明确记录：

```text
yaw = UNOBSERVED_FROM_SINGLE_HORIZONTAL_PLANE
x/y translation = UNOBSERVED_FROM_SINGLE_HORIZONTAL_PLANE
state = LEVEL_ONLY_NOT_BODY
```

禁止把 LEVEL frame 伪装成 BODY。

输出可视化：

```text
01_camera_raw.png
02_camera_planes.png
03_level_frame_support_plane.png
```

第三张图中 support/table plane 必须真正水平，Z 轴向上。

---

# 4. Phase B：优先继续恢复真实 hand-eye / cam2Base

在不修改设备配置的前提下，再完整检查：

- Epic Pro project export / project directory；
- ATOM `runSpace.json`；
- space/project 配置；
- `cam2Base` / `cam2baseMatrix` / `handeye` / `calibrationResult`；
- 历史日志、vendor tool、缓存、用户目录；
- cameraID=1 与 Pixel Pro `PP005901045` 的实际项目绑定。

如果找到真实矩阵：

1. 记录来源、项目 revision、space、arm、camera serial；
2. 明确矩阵方向（camera→base 还是 base→camera）；
3. 与 `T_body_armbase` 组合得到 `T_body_camera`；
4. 左/右两套若都存在，独立换算到 BODY 并比较差异；
5. 仍先记为 `CANDIDATE_FROM_VENDOR_CALIBRATION`，需 Phase D overlay 验证后才能考虑 commissioning。

如果仍找不到，不要阻塞整个任务，进入 Phase C 自动 registration candidate。

---

# 5. Phase C：桌面平面 + 可见右臂模型自动估计 `T_body_camera_candidate`

当前相机能看到右臂和桌面。利用这一事实做**只读自动配准候选**。

## C1. 生成 BODY-frame robot reference geometry

从当前只读 JAKA joints + 当前 tool revision，使用**实际 cuRobo/URDF planning model**生成右臂当前姿态的参考几何：

```text
arm links
current tool/gripper proxy（只使用实际已知/可追溯几何）
right arm base
```

优先使用 mesh / collision geometry / collision spheres 采样成 surface/reference points。

禁止使用 `world view` 的 display DH polyline 作为配准几何。

如果夹爪 geometry 当前不完整：

- registration 先只使用稳定、可见、模型可信的 arm links；
- tool/gripper 区域从评分中 mask 掉；
- 报告中明确记录。

## C2. 估计策略

使用 support-plane 约束：

```text
plane normal → roll/pitch strong constraint
plane offset / known table relation → z candidate constraint
```

再使用右臂模型 vs camera cloud registration：

```text
coarse correspondence / global registration / ICP
```

主要补足：

```text
yaw
x translation
y translation
```

可以把现场“相机约 49°俯视、位于两臂中轴上方”作为 optimizer initial guess / sanity prior，**禁止作为 production calibration truth**。

至少比较多个初始化，避免局部最优。

## C3. 评分与 fail-closed

输出候选必须带：

```text
T_body_camera_candidate
method
support_plane_residual
robot_registration_rmse
fitness / inlier ratio
number_of_model_points
number_of_cloud_points
initialization
four-frame consistency
candidate_revision/hash
```

如果 registration 明显不稳定、多个解差异大或模型无法从点云中辨认：

```text
state = AUTO_REGISTRATION_INCONCLUSIVE
```

不要强行挑一个最好看的矩阵。

输出：

```text
config/generated/T_body_camera.candidate.json
```

此文件必须：

```text
state = UNCOMMISSIONED
planning_allowed = false
```

不要覆盖任何 site/production calibration。

---

# 6. Phase D：BODY overlay 是外参是否可信的第一道门

无论候选来自 Vendor calibration 还是自动 registration，都生成 BODY 可视化。

必须至少显示：

```text
BODY +X forward / +Y left / +Z up
right-arm base
right-arm actual model at live joints
current tool revision
central 14 cm slab
support/table plane
transformed raw/voxel cloud
candidate BODY ROI
```

输出：

```text
04_body_overlay_full.png
```

再单独输出 robot region zoom：

```text
05_body_overlay_right_arm_zoom.png
```

以及定量 residual：

```text
visible_robot_cloud ↔ robot_model distance distribution
support plane normal vs BODY +Z
support plane height/offset consistency
four-frame transform consistency
```

**仅视觉看着差不多不算通过。**

如果 BODY overlay 明显错位，回到 B/C，不进入 self-filter。

---

# 7. Phase E：BODY ROI + robot/tool self-filter

当且仅当 BODY candidate 能生成合理 overlay 时继续。

## E1. ROI

从现有 reach audit candidate 开始：

```text
global x [-0.62, 0.90]
y [-1.10, 0.99]
z [0.43, 1.97] m
```

但不要直接宣布 commissioned。

同时输出：

```text
GLOBAL_MANIPULATION_ROI
LEFT_MANIPULATION_ROI
RIGHT_MANIPULATION_ROI
```

并把当前站点可见操作区域与 reach ROI 求交，减少远处背景。

输出：

```text
06_body_roi.png
```

## E2. self-filter

从 live joints 生成双臂当前 collision geometry；至少把右臂（当前相机明确可见）正确剔除。

self-filter margin 必须显式记录，禁止魔法值散落。

必须输出：

```text
07_self_filter_before.png
08_self_filter_after.png
```

以及：

```text
removed_point_count
remaining_point_count
removed_distance_histogram / summary
```

验收重点：

- 右臂点云显著消失；
- 桌面不能一起被误删；
- 桌上/周围外物不能因 margin 过大被吞掉。

---

# 8. Phase F：桌面/已知几何与未知 residual 分离

不要继续把桌面切成几十个 AABB。

## F1. support table

已确认的 support plane 单独建模为：

```text
KnownSupportGeometry
```

V0 可使用保守 cuboid/slab 表达有限桌面区域。

如果桌面真实边界不能从单帧稳定恢复，使用点云 extent + ROI 截断，并明确 conservative margin。

## F2. robot / table removal 后再 cluster

残余点云：

```text
BODY ROI
- robot/tool self cloud
- known table/support geometry
- other known fixed geometry（若有）
```

然后：

```text
5–10 mm voxel
→ optional light outlier filter
→ DBSCAN / connected clusters
→ conservative BODY AABB
→ explicit inflation
```

抓取目标若能通过 Epic detection / model mask 对应出来，必须标成：

```text
TARGET
```

不要同时作为不可接近普通障碍封死抓取路径。

输出：

```text
09_residual_clusters.png
10_final_collision_world.png
```

最后一张图必须只展示真正计划使用的：

```text
robot model
support/table
known geometry
unknown AABBs
central safety slab
ROI
```

---

# 9. Phase G：WorldModel / SceneSnapshot / cuRobo dry-run

不要把 camera-frame AABB 直接 load cuRobo。

当 BODY candidate scene 已经形成后：

1. 将 capture/frameID/hash、calibration candidate revision、robot state、tool revision、known geometry、residual AABB 写入同一 ObservationEpoch；
2. freeze SceneSnapshot；
3. 使用当前 SceneCompiler / 若尚缺则实现最小 arm-local compiler；
4. 输出 arm-local cuRobo world；
5. `planning_ready` 仍由 calibration commissioning gate 决定。

本轮允许使用 `UNCOMMISSIONED candidate scene` 做**planning-only dry-run**，但输出必须明确：

```text
execution_allowed = false
```

## G1. 两个 collision sanity tests

必须构造并通过：

### BLOCK TEST

人工/程序插入一个明确挡住已知路径的 cuboid：

```text
planner must reject / route around
```

### FREE TEST

一个已知净空目标：

```text
planner must find a trajectory
```

证明 scene 真正进入了 cuRobo collision checker，而不是只画了图。

---

# 10. Phase H（只有 A–G 成功后才做）：双臂 named-pose cuRobo planning-only

用户历史上已经有 `zero / ready / forward / up / side` 双臂 named pose；目前 direct MoveJ route 与右臂 cuRobo route 能力不对称。

本轮**不要执行**，但可以把 planner 做成 arm-parameterized，并至少离线生成：

```text
left current → up
right current → up
```

要求：

- 使用各自真实 current joints；
- 使用各自 tool revision；
- 使用同一个 BODY SceneSnapshot；
- inactive arm 作为 collision geometry；
- 中央 slab / SafetyKernel 全路径 gate；
- 分别输出 trajectory preview、minimum clearance、joint velocity/accel；
- 不允许简单把 `.101/right` 字符串替换成 `.100/left` 而绕过模型校正。

输出状态：

```text
PLANNING_ONLY
NOT EXECUTION_COMMISSIONED
```

如果左臂模型/worker 需要较大重构，本轮允许停在“精确差距报告”，不要为了赶进度复制一套 right-only 代码。

---

# 11. 不要做的事

本轮不要：

- 开始 E2E 真机 cycle；
- 让 agent 因用户临时授权就修改安全门并运动；
- commission `normal/site_max` 速度；
- 配置 JAKA Safety Plane；
- 自动重试；
- nvblox / ESDF；
- mesh reconstruction；
- 双臂同时运动；
- LLM / Skill runtime；
- 写最终“明天操作手册”。

今天先把事实和可重复软件链做完整，操作手册放到下一任务，根据本轮实际结果生成。

---

# 12. 必须产出的报告/机器可读结果

提交到 integration 分支：

```text
docs/BODY_CAMERA_REGISTRATION_2026-09-17.md
docs/POINTCLOUD_BODY_COLLISION_WORLD_2026-09-17.md
docs/CUROBO_COLLISION_DRYRUN_2026-09-17.md
```

建议机器可读：

```text
worklog/generated/support_plane_candidates.json
config/generated/T_body_camera.candidate.json
worklog/generated/body_registration_metrics.json
worklog/generated/body_collision_world.json
```

若大文件/点云不适合 Git，只提交 manifest/hash/相对 evidence path，不提交 PLY/EpicRaw 本体。

最终报告必须明确回答：

1. 四帧中哪个 plane 被识别为桌面/support plane？证据是什么？
2. 桌面法向是否稳定？推导出的 camera tilt/level rotation 是多少？
3. 真实 vendor hand-eye/cam2Base 是否最终恢复？
4. 如果没有，自动 robot+plane registration 是否得到唯一稳定的 `T_body_camera_candidate`？
5. BODY overlay 的 robot/table residual 是多少？
6. self-filter 删除了多少点？是否误删桌面/外物？
7. 最终 BODY residual 有多少 cluster/AABB？
8. collision world 是否真的影响了 cuRobo BLOCK/FREE planning test？
9. `T_body_camera` 当前状态应是 `COMMISSIONED / CANDIDATE / INCONCLUSIVE` 中哪一种？禁止默认 COMMISSIONED。
10. 明天进入首次受监督运动前还剩哪 3–5 个 blocker？
11. 是否已经能 offline 生成 left/right `current→up` cuRobo trajectory；若否，缺什么？

---

# 13. 测试与提交

至少运行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
git diff --check
```

所有自动 calibration / scene / planner 工具必须可在不连运动设备的情况下重放。

建议提交拆分：

```text
feat(perception): add support-plane and BODY registration analysis
feat(scene): compile BODY ROI and self-filtered collision world
feat(planning): validate collision world with cuRobo dry-runs
```

完成后 STOP，不执行机械臂运动，不提前写最终现场操作手册。