# 2026-09-17 下午：E2E 基座收敛、双臂统一控制与点云避障工作单

## 0. 当前唯一优先级

今天下午不继续 Skill Library / LLM / Qwen / S1B，不做新的抽象体系。

当前交付目标是把 ARES-R 收敛成一套可继续实机集成的统一基座，并为第一条完整 E2E V0 做准备：

```text
AMR 到取料位并确认停稳
→ Epic 视觉检测
→ 点云构建碰撞场景
→ 单臂规划/抓取
→ 双臂进入运输安全姿态
→ AMR 到放置位并确认停稳
→ Epic 再检测
→ 点云重建碰撞场景
→ 单臂规划/放置
→ 撤退/收拢
→ COMPLETE
```

本轮允许调用 Pixel Pro / EpicEye SDK 进行相机拍照、EpicRaw/PLY 采集和只读分析；允许读取 JAKA/AMR 状态。**禁止驱动机械臂、夹爪和底盘运动。**

输入证据优先使用：

```text
/home/yikun/ARES-R_AUDIT_20260917/
```

中的 01–05 审计报告、JSON 分类、保全补丁/归档，以及 GitHub 上：

```text
planning/e2e-epic-pointcloud-audit-20260917
```

中的上一轮审计工单。

---

# 1. 先整理昨天现场 dirty worktree，不允许 blanket merge

审计已经给出 64 个文件唯一分类：

```text
KEEP_CORE
KEEP_WITH_GATES
REWORK
DROP_OR_GENERATED
```

本轮先完成 Git 整理，再开始新代码。

## 1.1 建立不可合并的 preservation 分支

当前 `/home/yikun/ARES-R` dirty worktree 已经由外部审计包完整保全。再次核对外部保全 SHA 后：

1. 从当前 dirty worktree 建立本地分支：

```text
preserve/site-20260916
```

2. 该分支用于追溯现场原貌，不作为生产分支。
3. 可以把昨日源代码、配置、测试、文档和关键小型 evidence commit 到该分支；生成的 pregrasp case/target 可放 evidence/archive，不进入未来生产提交。
4. 先做 secret/large-file 检查，再决定 preservation 分支是否 push；外部 forensic archive 始终保留。
5. 不得改变原始失败证据或把 superseded 结论改写成成功。

## 1.2 新建正式集成分支

从干净的 `92a9c574...` 或当前正式 main 基线创建：

```text
feat/e2e-v0-integration-20260917
```

只选择性带入：

### 第一批：KEEP_CORE

必须优先集成并保持离线测试通过：

- `src/ares_r/adapters/epic_protocol.py`
- `src/ares_r/models.py` 中候选/meta 扩展
- `src/ares_r/motion/curobo_params.py`
- `src/ares_r/motion/feedback_audit.py`
- `src/ares_r/motion/preview.py`
- `src/ares_r/epic_frame_audit.py`
- `src/ares_r/motion/singularity.py`
- 对应 FK / benchmark / feedback / native / pregrasp / singularity 测试和只读脚本

### 第二批：KEEP_WITH_GATES

只在明确保留 gate 的情况下带入：

- `native_demo.py`
- `pregrasp.py`
- `pregrasp_worker.py`
- `terminal.py` 的 supervised/debug 入口
- `jaka_right_demo.cpp`

这些代码不得因为“曾经跑通过”就宣称 planning-ready / collision-safe / frame-verified。

### 第三批：REWORK

不得原样 cherry-pick：

- `config/system.json` 的 global right-arm / `pose_frame_verified=true`
- `epic.py` 的 global frame assumption
- `grasp.py`
- `grasp_plan.py`
- `ik.py`
- `ik_worker.py`
- Epic frame/touch 辅助脚本和相关 tests

重写要求见第 4 节。

### DROP_OR_GENERATED

不进入生产代码分支。保留在 forensic/evidence archive 即可。

---

# 2. 把控制架构正式收敛成“统一双臂金字塔”

左右 JAKA 是两个独立控制器/SDK endpoint，这个底层分开是合理的；但从运动授权开始，必须只有一个统一上层。

目标控制架构：

```text
L5 Mission / Protocol
    人/未来 LLM 提出任务意图

L4 Workflow / Task Executive
    操作员把已经验收的 Skill 组合成新任务流程
    例：取料→抓取→运输→放置

L3 Commissioned Skills
    可复用、可验证的动作块
    NavigateToStation / AcquireScene / Pick / Place / Press / LoadDevice ...

L2 Motion Coordination & Scene
    DualArmCoordinator
    WorldModel / SceneSnapshot
    SceneCompiler
    cuRobo planner
    shared-zone ownership
    inactive-arm obstacle
    attachment/payload model

L1 Safety Kernel & Motion Primitives
    永久不可绕过的硬门：
    joint limits
    speed/acceleration limits
    BODY center exclusion
    JAKA controller safety planes
    start-state gate
    tool/TCP revision gate
    base/arm interlock
    collision/estop state gate

L0 Hardware Adapters
    JAKA left/right
    grippers
    AMR
    Epic Pro / EpicEye
```

横跨各层的事实/证据平面：

```text
WorldModel + LabWorkspace + EventLog + evidence/provenance
```

要求：任务层、Skill、Terminal 都不得直接绕过 L1/L2 分别向两条机械臂发送运动命令。

V0 不需要 12-DoF 双臂同步规划。第一版采用：

```text
一次只授权一条臂运动
另一条臂必须处于已知状态并作为碰撞几何
共享区域必须有统一 ownership
底盘运动时两臂必须进入 transport-safe 姿态并锁定
```

---

# 3. 身体中线/中央 14 cm 禁区：确认现状并形成真正底层互锁

当前仓库 `world_geometry.py` 定义：

```text
BODY -0.070 <= Y <= +0.070 m
```

为中央 TCP 禁区。这比“不能跨 Y=0 中线”更严格：左右臂各自必须停在中央 14 cm slab 外。

当前问题：

- `world view` 能显示并检查 TCP clearance；
- right native demo 对整条 link path 有专门 workspace separation gate；
- 普通 joint target / 其他未来执行路径尚没有统一、不可绕过的双臂中线 SafetyKernel。

本轮不动机械臂，只做以下工作：

1. 查清所有真实运动入口：MoveJ / joint_move / ServoJ / native sender / named pose / future E2E executor。
2. 设计一个唯一的 `DualArmSafetyKernel` 或等价模块，所有运动入口在发送 SDK 前调用。
3. 中央禁区检查不能只检查终点 TCP；至少规划轨迹必须检查：
   - TCP 全路径；
   - 真实机器人 collision geometry / link envelope；
   - tool；
   - attached object；
   - 另一条臂。
4. 生成离线 tests，证明所有入口无法绕过该 gate。
5. 不要使用 display MDH joint polyline 作为生产碰撞模型。

## 3.1 JAKA 控制器 Safety Plane 审计

JAKA 官方控制器支持 TCP Position Limit / Safety Plane，并可配置多个安全平面；部分版本还可让 elbow/J3 同时受约束。

但不要假设当前 Python/C++ SDK 暴露了 safety-plane setter。

请在现场实际安装的 V2.1.5 / V2.2.2 SDK header、Python binding、示例中只读搜索：

```text
safety plane
safe plane
safety zone
cartesian limit
workspace limit
```

输出：

```text
JAKA_SAFETY_PLANE_API_AUDIT.md
```

结论必须是以下之一：

```text
A. SDK 可读写 safety plane，列出准确 API 和版本
B. SDK 只能读/不能写
C. 公共/现场 SDK 没有接口，只能通过 JAKA App/控制器安全设置
```

在没有正式 API 证据前，**不要向控制器写安全平面**。

如果最终通过 JAKA App 配置，计算并输出两臂对应的控制器基坐标安全平面参数，但只生成报告，不自动写入控制器：

```text
左臂：BODY Y = +0.070 m，安全侧为更大的 BODY Y
右臂：BODY Y = -0.070 m，安全侧为更小的 BODY Y
```

由 `config/robot_world.json` 的 `T_body_armbase` 将 BODY 平面转换到每条 JAKA base frame。

注意：如果 JAKA 安全区域存在“程序激活/开机激活”区别，必须确认 SDK-controlled motion 是否受约束；优先推荐始终对 SDK 有效的控制器安全模式，不要只依赖只对 JAKA 程序有效的模式。

---

# 4. Epic / TCP / IK：按审计结论整理，不能再全局写死右臂

依据 02/04/05 审计：

- 5700 structured parser、候选/meta/ACK/error 分支保留；
- 右臂“joint trajectory → JAKA execution”已有较强证据；
- 右臂 Epic target 的位置/姿态合同尚未 commission；
- 当前 translation-only tool correction 是错误的；
- Tool ID 不等于 tool revision；
- 左臂 Epic targeting 目前没有仓库级可复核证据。

本轮允许离线修代码，不允许运动：

1. 定义按臂/space/object/camera/tool-revision 的 `EpicTaskProfile`。
2. 所有 profile 默认 `UNCOMMISSIONED`；不允许 global `pose_frame_verified=true`。
3. 保存完整 `T_link6_tcp` SE(3) 并计算 hash。
4. 修复 IK：

```text
T_base_link6_goal = T_base_tcp_goal * inverse(T_link6_tcp)
```

不得只减 TCP translation。
5. 增加非零 tool rotation regression tests。
6. 多候选保留顺序和 provenance；后续才做 candidate ranking。
7. 不做任何真实执行。

---

# 5. 已做过手眼标定：优先“恢复和验证矩阵”，不要重新从零标定

当前 Pixel Pro 固定安装于机器人头部，属于 eye-to-hand/static camera 场景。

官方 Epic/ATOM 数据路径可携带：

```text
3D ROI
hand-eye calibration matrix
cam2Base / cam2baseMatrix
```

所以今天下午的优先级不是重新移动机械臂做手眼标定，而是：

1. 搜索 Epic Pro 项目、ATOM `runSpace.json`、导出配置、SDK/缓存目录中现有：
   - `cam2Base`
   - `cam2baseMatrix`
   - hand-eye matrix
   - 3D ROI
   - space/object/camera mapping
2. 明确该矩阵对应左臂 base、右臂 base、某 Epic space 还是其他 robot frame。
3. 若取得可信 `T_armbase_camera`，结合已知 `T_body_armbase` 自动推导：

```text
T_body_camera = T_body_armbase * T_armbase_camera
```

4. 如果左右两套独立 hand-eye 都存在，分别推导 `T_body_camera` 并检查两者一致性。
5. 只要相机/机器人基座相对位置没有发生变化且原标定有可追溯结果，不重新做完整手眼标定；先做静态 overlay verification。
6. 如果无法导出原矩阵，则明确 BLOCKED，不允许用目测 49° 俯角构造生产级 `T_body_camera`。

---

# 6. 今天允许调用相机 SDK：把点云链真正做成可调试工具

可以触发 Pixel Pro/EpicEye 相机采集；机器人和底盘保持静止。

## 6.1 采集

至少采集 3–5 帧当前静态场景，保存：

```text
EpicRaw
pointcloud.ply
RGB/depth
frameID
timestamp
sha256
camera serial/firmware
```

如 5700 服务不可用，不影响本阶段。

## 6.2 点云处理工具

基于已有 `epic_pointcloud.py`，实现或整理一个纯离线/相机-only 工具：

```text
invalid/zero removal
→ mm→m once
→ camera→BODY (仅在 T_body_camera 可追溯时)
→ BODY ROI crop
→ known floor/background handling
→ robot/base/arm/tool self-filter
→ 5/10 mm voxel
→ optional mild outlier filter
→ cluster
→ conservative AABB
→ inflation
→ save visualization + scene artifact
```

每个 stage 输出：

```text
point_count_before/after
bounds
runtime
parameters
source/output frame
hash/revision
```

已有离线实验表明 1.85M 有效点在 10 mm voxel 后约 22.8k 点、5 mm 后约 87.5k 点，因此不要把主要精力花在复杂 outlier 参数；优先解决 ROI、self-filter、frame 和 target/obstacle separation。

## 6.3 ROI

以 actual cuRobo robot/tool reach 为依据，不以整个相机 FOV 为 ROI。

审计得到的未 commission 候选 envelope 仅用于初始可视化：

```text
全局候选：x [-0.62, 0.90], y [-1.10, 0.99], z [0.43, 1.97] m
```

继续维护：

```text
GLOBAL_MANIPULATION_ROI
LEFT_MANIPULATION_ROI
RIGHT_MANIPULATION_ROI
station/task-specific intersection
```

最终数值必须经过 BODY overlay、当前 tool/payload 和现场 station 边界验证。

## 6.4 今天最重要的点云验收

当前相机能看到右臂和桌面时，今天至少产出一组可视证据：

```text
raw cloud
BODY transformed cloud (若矩阵可恢复)
ROI cropped cloud
self-filter before/after
voxel cloud
cluster/AABB overlay
```

要求：

- 右臂自身点应被明显剔除；
- 桌面/真实外部物体不能被一起误删；
- 输出仍不得标记为 `planning_ready`，除非 T_body_camera 和 collision model gates 全部满足。

---

# 7. 双臂避障/互锁应该放在哪些层

不是所有安全都塞进 JAKA driver，但所有这些层都必须位于 Skill/Workflow 之下：

## Controller / hardware safety

- E-stop
- collision protection
- controller joint limits
- JAKA TCP safety plane / cube（如果版本支持并完成管理员配置）
- 可选 elbow/J3 safety region

## ARES-R SafetyKernel

- BODY central slab
- per-command joint/speed/acceleration gate
- full-link trajectory workspace gate
- tool/TCP revision match
- start-state match
- base-moving → arm-motion reject
- estop/collision/fault reject

## DualArmCoordinator

- 唯一 motion authority
- left/right arm ownership
- center/shared-zone ownership
- one-arm-at-a-time V0
- inactive arm state must be known
- other arm movement revokes current motion permission
- AMR move requires both arms transport-safe

## Planner / SceneCompiler

- self collision
- other arm as collision geometry
- gripper/tool geometry
- attached object geometry
- known station geometry
- ROI pointcloud residual obstacles

因此：两个 JAKA driver 分开没有问题；**双臂作为一个机器人系统的运动权限必须统一。**

---

# 8. 速度：从“固定慢速”改成可审计速度 profile

当前正式 site limits：

```text
max_velocity_rad_s = 0.1
max_acceleration_rad_s2 = 0.2
```

而 terminal/部分 demo 长期固定在约 `0.05 rad/s` / `3 deg/s` 附近，过于单一。

本轮只做配置与离线 gate，不动机械臂：

1. 将速度改为命名 profile，例如：

```text
precision
slow
normal
site_max
```

2. 所有 profile 必须受 `config/jaka_mini2_motion.site.json` 的 0.1 rad/s / 0.2 rad/s² ceiling 限制。
3. `precision/fine approach` 与 `transport/free-space` 分开。
4. 不要把未经实机跟踪验证的 profile 标记 commissioned。
5. 后续现场按低→高逐档验证 tracking、振动、停止距离和碰撞门，不能一次跳到高速度。

输出一个清晰的 speed-profile 表和测试计划。

---

# 9. 今天下午的结束状态

今天下午结束时，理想产出必须是“可见的工程推进”，不是又一轮架构文档：

```text
A. Git 已经整理：preservation 与正式 integration 分开
B. KEEP_CORE 已进入干净 integration branch
C. global Epic frame verified 已被废止/准备重构为 per-arm profile
D. full-SE3 TCP/IK 已离线修复并有 regression test
E. JAKA safety-plane API/APP 路径已明确，但没有写入控制器
F. 双臂统一控制层职责和所有运动入口清单明确
G. Pixel Pro 至少采集 3–5 帧新静态点云
H. 已尝试恢复现有 hand-eye / cam2Base / ROI
I. 至少生成 raw→ROI→self-filter→voxel→AABB 的可视化证据
J. 速度 profile 设计完成且不会超过当前 site ceilings
```

如果 hand-eye matrix 无法恢复，则 G/I 仍可在 camera frame 下用于算法调试，但必须明确 `BODY_TRANSFORM_BLOCKED`，不能生成 production scene。

完成后停止，不运行任何机械臂、夹爪或底盘动作，不开始 E2E 实机执行。

---

# 10. 最终回报格式

请最终给出：

1. Git 分支/提交整理结果；
2. KEEP_CORE / gated / rework 实际落地了什么；
3. JAKA safety plane 是否能通过当前 SDK 写入；若不能，App 如何配置；
4. 两臂中央 14 cm 禁区在各自 base frame 下的 plane 参数；
5. 所有真实运动入口是否都能被统一 SafetyKernel 覆盖；
6. hand-eye matrix / cam2Base 是否恢复成功；来源和 revision；
7. `T_body_camera` 是否可自动推导并验证；
8. 新采集点云的 frameID/hash/count；
9. ROI/self-filter/voxel/AABB 前后点数与可视化；
10. speed profiles；
11. 下一次允许实机运动前仍然存在的 blockers。
