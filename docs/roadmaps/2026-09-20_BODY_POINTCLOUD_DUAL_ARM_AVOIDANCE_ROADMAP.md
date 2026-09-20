# ARES-R 2026-09-20：BODY 点云 → 双臂避障 → GUI 总路线

## 0. 当前唯一总目标

把固定在机器人头部的 Pixel Pro 点云稳定转换到 ARES-R BODY 坐标系，并围绕这条几何主链逐步完成：

~~~text
Pixel Pro CAMERA cloud
→ production T_body_camera
→ BODY point cloud
→ 可视化验证
→ robot/self geometry
→ obstacle scene
→ cuRobo planning
→ supervised execution
→ WebUI/Terminal unified operation
~~~

不要再并行发散到 Skill Library / LLM / 复杂任务规划。

## 1. 最优先的新判断：先恢复 Epic Pro 已有手眼结果

Transfer / Epic Pro / ATOM 的输入链本身支持“手眼标定矩阵”，离线 runSpace.json 也明确支持 cam2Base / cam2baseMatrix。

如果现场 Epic Pro 之前确实分别对左/右 JAKA 做过手眼标定，那么这比重新用桌面、ICP 或底盘运动估外参更直接。

定义：

~~~text
B  = ARES-R BODY
L  = left arm base
R  = right arm base
C  = Pixel Pro CAMERA
~~~

如果 Epic 中恢复的是 camera→arm-base 变换：

~~~text
T_L_C
T_R_C

T_B_C_left  = T_B_L · T_L_C
T_B_C_right = T_B_R · T_R_C
~~~

其中 T_B_L/T_B_R 已在 config/robot_world.json 中定义。

左右两条链若能得到相近的 T_B_C，这是非常强的独立交叉验证。

注意：cam2Base 字段名字暗示 camera→base，但必须通过官方文档、项目 schema、板/桌面验证确认矩阵方向，禁止只按名字猜。

## 2. 当前已有基础

ARES-R 已有：

- BODY frame 定义；
- 左右臂 base 在 BODY 中的固定变换；
- world view；
- Pixel Pro 点云采集；
- 桌面主平面检测；
- WorldModel / ObservationEpoch / SceneSnapshot / SceneCompiler；
- cuRobo GPU 规划链；
- 右臂真实 cuRobo→ServoJ 执行证据；
- 原 ARES 中 JAKA MiniCobo/Mini2 接近机型的 URDF、STL mesh、collision spheres；
- cuRobo FK 已与现场 controller FK 做过毫米级核对；
- pointcloud→cuRobo planning-only FREE/AVOID/BLOCK 已证明软件合同可走通。

当前最大缺口：

1. production T_body_camera；
2. BODY cloud viewer；
3. 真实完整双臂 / gripper / tool collision model；
4. self-filter / inactive-arm obstacle；
5. production BODY cloud → cuRobo；
6. GUI/WebUI。

## 3. 固定阶段顺序

### P0 — Recover Epic hand-eye → production T_body_camera

先查现有手眼结果，不做新的复杂标定。

退出条件：

~~~text
T_body_camera = COMMISSIONED
或
明确证明 Epic 已有 hand-eye 不可恢复 / 不可信，进入 vendor-board fallback
~~~

用户仅在 Codex 明确要求时执行最少现场操作。

### P1 — BODY point cloud + 3D viewer

固定外参后：

~~~text
CAMERA cloud → BODY cloud
~~~

先不做 self-filter。

必须验证：

- vendor board；
- table z≈0.750m；
- known box / known object；
- left/right arm base positions。

完成 Open3D snapshot viewer；然后做可调刷新频率的 viewer prototype。

退出条件：

~~~text
BODY_POINTCLOUD_READY = YES
~~~

### P2 — Whole dual-arm collision model

不再把系统理解为两台独立单臂。

V0：

~~~text
active arm = cuRobo 6DoF planner
inactive arm = BODY-frame dynamic collision obstacle
~~~

补齐 Mini2 URDF/mesh、link1..6 collision spheres、base/housing、gripper、current tool、left/right base transforms、self-collision matrix、BODY central exclusion。

退出条件：

~~~text
WHOLE_ROBOT_COLLISION_MODEL_READY = YES
~~~

### P3 — Real obstacle A↔B cuRobo demo

每次从 A 或 B 出发：

~~~text
fresh scan
→ BODY cloud
→ self-filter
→ obstacle scene
→ fresh cuRobo plan
→ preview
~~~

先 planning-only，之后 supervised execution。

### P4 — WebUI frontend over ARES-R Terminal backend

UI 只做 frontend。

所有真实功能仍由 ARES-R backend/Terminal command registry 完成。

功能：

- 3D BODY world；
- pointcloud refresh interval；
- 手动“扫描一次”；
- obstacle on/off；
- left/right arm model；
- target 6DoF input；
- 若未输入 RPY，使用语义 orientation=BODY_FORWARD；
- plan / preview / execute；
- AMR forward/back/left/right/stop；
- embedded Terminal input/output。

### P5 — 性能优化 / scene watchdog

在功能闭环之后优化 frame fetch、self-filter、voxel、pipeline concurrency、future nvblox/MPC。不要提前做。

## 4. 用户需要参与的操作必须极简

Codex 每次需要用户配合时，只能输出：

~~~text
USER ACTION N
目的：
你现在做：
完成后回复：
安全边界：
~~~

一次最多要求一个现场动作。

## 5. Git / 数据原则

所有新代码、日志、配置、截图、manifest 都位于 /home/yikun/ARES-R。

禁止新建 ARES-R_AUDIT_*。

大文件不进 Git，保存于 repo-local logs，并提交 manifest、SHA256、摘要、关键截图。

当前现场 integration branch 有本地后续提交/dirty work 时，不允许 blanket reset。

## 6. 当前只执行 P0

当前唯一 Active Work Order：

~~~text
docs/work_orders/2026-09-20_P0_RECOVER_EPIC_HAND_EYE_TO_BODY.md
~~~

P0 完成并阶段汇报后，才进入 P1。
