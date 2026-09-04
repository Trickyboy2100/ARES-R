# 2026-09-04 当日调试指导

## 当日目标

当日工作只完成三个闭环：

1. Epic Pro 检测结果形成可复现精度基线。
2. JAKA 执行链形成只读状态基线与离线轨迹验证结果。
3. Epic 路径与 cuRobo 路径形成统一交接格式，不执行完整抓放任务。

当日不以“抓取成功一次”为验收条件，不进行双臂同时运动，不进行带料盘全程运动，不绕过轨迹门禁。

## 开工前共同检查

### Git 状态

```bash
cd /home/yikun/ARES-R
git fetch origin
git status --short
git pull --ff-only origin main
git log -1 --oneline
```

记录实际 `git log -1 --oneline`，不要依赖文档中的历史提交号。

分别建立分支：

```bash
git switch -c vision/20260904-epic-baseline
```

```bash
git switch -c jaka/20260904-execution-baseline
```

同一工作目录不能同时切换两个分支。建议使用两个独立 clone 或 `git worktree`。禁止直接在 `main` 上调试和提交。

### 现场安全状态

- 急停位置可立即触达。
- 底盘停止并断开自主导航任务。
- 两条机械臂无残留运动程序。
- 夹爪内无工件。
- 工作空间无临时障碍。
- JAKA 速度倍率处于低速调试范围。
- 相机支架、法兰、夹爪和线缆无松动。
- Epic、JAKA、ARES-R 使用的 TCP 与坐标系名称已记录。

任一项目无法确认时，只允许离线工作和状态读取。

## 工作流 A：Epic Pro 感知基线

### A0：网络与算法图状态

启动只连接相机的 Terminal：

```bash
cd /home/yikun/ARES-R
./scripts/run_terminal.sh --mode camera-only
```

执行：

```text
epic status
epic detect pick
```

判定规则：

- `UNCHECKED`：尚未探测，不属于故障。
- `READY / reachable`：5700 端口可连接。
- 收到 `000,3020`：通信正常但无有效检测结果。
- 连接拒绝或超时：先检查 Epic 服务、端口、防火墙和算法图状态。

当前 `epic detect pick` 只发送检测命令，不发送机械臂、夹爪或底盘命令。

### A1：固定场景 30 帧

保持相机、料盘、光照和算法参数不变，连续执行 30 次：

```text
epic detect pick
```

保存以下信息：

- 30 条完整原始报文。
- 30 组 XYZ 与姿态。
- Epic 工程版本、空间 ID、物体 ID、模板版本。
- 相机参数、手眼标定版本、TCP 版本。
- 算法图启动时间和首帧状态。

统计结果：XYZ 均值、标准差、最大最小值、P95；姿态均值、标准差和候选方向切换次数。

### A2：九点与方向验证

工作区选择中心、四角、四边共九个位置。每个位置至少采集 5 帧。每个位置记录实测基准坐标与检测坐标。

两指夹爪候选至少保留：

- 正抓：原始抓取姿态。
- 反抓：绕接近轴旋转 180°。

候选输出不得提前删除。后续由 IK、整臂碰撞、关节余量、奇异性和路径长度共同评分。

### A3：Epic 规划准备

Epic 工程完成以下配置检查：

- JAKA Mini2 机器人模型与关节零位一致；型号以铭牌/JAKA APP 为准。
- 所有臂段均配置碰撞模型。
- 夹爪模型参与碰撞检测。
- 场景点云与匹配模型作为动态障碍。
- 台面、箱体、底盘和静止机械臂作为场景障碍。
- 返回位姿类型选择关节空间。
- 抓取路径包含起点、预抓取点、抓取点。
- 撤离路径包含抓取点、预撤离点、撤离终点。

仅修改 TCP 不能覆盖夹爪或料盘体积。夹取后的撤离路径必须绑定“夹爪+料盘”附着模型。

### A4：感知交接

交接字段：

```text
run_id
frame_id
space_id
object_id
grasp_id
position_mm
orientation_deg
orientation_convention
confidence
calibration_revision
template_revision
tcp_revision
raw_response
```

坐标系、单位或姿态顺序缺失时，交接结果无效。

## 工作流 B：JAKA 执行基线

### B0：代码边界

当天优先修改：

```text
src/ares_r/adapters/jaka_servo.py
src/ares_r/adapters/jaka_sdk.py
src/ares_r/motion/
tests/test_jaka_servo.py
tests/test_motion.py
docs/
worklog/
```

禁止把 `prototype/jaka_driver.py` 或 `prototype/0_test.py` 作为当天真机入口。原型中存在直接运动调用与历史参数，不具备当前轨迹门禁。

### B1：只读状态基线

启动只读入口并保存双臂基线：

```bash
./scripts/run_terminal.sh --mode jaka-readonly
```

```text
jaka status left
jaka status right
jaka baseline
```

内部只调用以下 JAKA SDK 查询：

```text
get_sdk_version()
get_robot_status()
get_joint_position()
get_tcp_position()
get_tool_id()
get_tool_data(tool_id)
is_on_limit()
is_in_collision()
```

状态基线必须包含：SDK 版本、控制器版本、左右臂 IP 标识、六关节角、TCP、当前工具 ID、软限位状态、碰撞保护状态、急停状态、使能状态。

只读阶段禁止调用：

```text
power_on
enable_robot
joint_move
linear_move
servo_move_enable
servo_j
collision_recover
```

### B2：现场限位配置

确认第二份现场配置存在：

```bash
test -f config/jaka_mini2_motion.site.json
```

在 JAKA 实验分支中，把 `config/system.json` 的 `motion.limits_file` 改为：

```json
"limits_file": "config/jaka_mini2_motion.site.json"
```

依次核对：

- 关节顺序与 `get_joint_position()` 一致。
- 上下限与当前 Mini2 型号、控制器软限位一致。
- 最大速度与最大加速度采用低速调试值。
- 软限位余量不得为零。
- 起点允许误差采用保守值。

核对完成前保持：

```json
"commissioning_confirmed": false
```

现场配置只保留可公开的关节限位、速度和加速度；IP、密码和内部网络信息不得写入该文件。

### B3：离线轨迹门禁

启动 Mock Terminal：

```bash
./scripts/run_terminal.sh --mode mock
```

执行：

```text
motion inspect examples/trajectory.example.json
motion validate examples/trajectory.example.json
jaka preflight left examples/trajectory.example.json
jaka preflight right examples/trajectory.example.json
```

预期结果必须为 `BLOCKED`，原因至少包括：

```text
UNCONFIRMED_LIMITS
COLLISION
```

随后复制轨迹样例形成实验文件，补齐真实模型版本、场景版本、工具版本、附着物版本和规划器碰撞证明。禁止修改原始样例伪造通过结果。

### B4：JAKA 伺服执行审查

`src/ares_r/adapters/jaka_servo.py` 当前包含：

- 显式 `armed=True` 门禁。
- 当前关节与轨迹首点比较。
- 软限位与碰撞状态预检。
- 8 ms 整数倍周期检查。
- 绝对关节模式 `servo_j`。
- 队列高水位阻断。
- 异常 `motion_abort`。
- 结束后退出伺服模式。

当天审查重点：

1. 本机 SDK V2.1.5 的 Python 返回值结构是否与骨架一致。
2. `servo_j` 的 `step_num` 参数签名是否一致。
3. 队列长度是否由返回值提供。
4. 状态查询耗时是否影响发送周期。
5. 双臂控制器是否需要独立线程、独立进程或独立时钟。

发现接口差异时，先增加假 SDK 单元测试，再修改执行骨架。禁止边试真机边修改发送循环。

### B5：首次空载动作条件

当前授权明确禁止进入动作阶段。下列条件仅作为未来独立审批清单，不构成当日动作许可：

- 现场限位配置已复核并提交审查。
- 当前关节与轨迹首点误差合格。
- 最终稠密轨迹经过整臂和工具碰撞检查。
- `motion validate` 无错误。
- 急停与 `motion_abort` 已单独验证。
- 另一机械臂位于已验证安全位。
- 路径不含料盘，不进入箱体，不接近台面。

禁止使用单条 `linear_move` 验证复杂空间路径。

## 工作流 C：两条规划路线对比

### 路线一：Epic Pro

输出 Epic 关节路径和原始 5700 报文。规划点先转换为统一轨迹，再执行时间参数化。Epic 路径点不具备 JAKA 伺服周期，禁止直接循环发送。

检查项：

- 路径是否覆盖起点、预抓取、抓取、预撤离、撤离终点。
- 每个路径点是否为六关节数据。
- 相邻关节是否跳变。
- 正抓和反抓是否均尝试规划。
- 机器人全臂、夹爪、料盘和场景是否参与碰撞检查。

### 路线二：cuRobo

旧 ARES 固定参考提交：

```text
Trickyboy2100/ARES@b978cbd669b5a3f6bc0bd19defcbe5256692f145
```

当天只完成离线迁移核对：

- 清除 YAML 绝对路径。
- 核对 URDF 关节限位和关节顺序。
- 重新拟合夹爪碰撞球；旧配置中的夹爪碰撞球为空。
- 保留世界碰撞与自碰撞。
- 删除未经重新碰撞验证的 `fallback_path` 末端修正。
- 规划结果导出为统一轨迹文件。
- 夹取后附着料盘碰撞球。

当天不把旧仿真 worker 直接接入真机。

## 联合交接会议输入

只讨论可复现文件，不讨论未记录的口头坐标：

1. Epic 30 帧原始报文与统计表。
2. 九点误差表和失败样本。
3. 正抓、反抓候选各一组。
4. JAKA 只读状态快照。
5. 现场限位配置草案。
6. Epic 与 cuRobo 各一份统一轨迹样例。
7. 所有阻断代码和失败原因。

## 当日验收

### Epic 感知

- [ ] 5700 连通状态已记录。
- [ ] 固定场景 30 帧已完成。
- [ ] XYZ 与姿态统计已完成。
- [ ] 九点数据至少完成首轮采集。
- [ ] 正抓与反抓候选均保留。
- [ ] 坐标系、单位和姿态顺序已明确。

### JAKA 执行

- [ ] SDK 与控制器版本已记录。
- [ ] 左右臂只读状态已保存。
- [ ] 关节顺序与限位来源已明确。
- [ ] 轨迹样例按预期被门禁阻断。
- [ ] SDK 返回结构已由假 SDK 测试覆盖。
- [ ] 真机入口仍保持默认关闭。

### 联合接口

- [ ] Epic 输出可转换为统一轨迹字段。
- [ ] cuRobo 旧配置风险已逐项确认。
- [ ] 模型、场景、工具和附着物版本可追踪。
- [ ] 失败实验与成功实验均已保存。

## 收工与提交

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

添加留痕：

```bash
./scripts/worklog add "20260904 Epic感知基线" \
  --author "姓名或工号" --source field-test \
  --files "相关文件" --tests "验证结果" --next "下一门禁"
```

```bash
./scripts/worklog add "20260904 JAKA执行基线" \
  --author "姓名或工号" --source field-test \
  --files "相关文件" --tests "验证结果" --next "下一门禁"
```

提交前检查：

```bash
git status --short
git diff --check
git diff --cached
python3 scripts/check_traceability.py --mode staged
```

提交信息建议：

```text
vision: record 20260904 epic baseline
jaka: verify 20260904 sdk trajectory gates
```

分支推送后通过 Pull Request 合并。大型点云、视频、日志、密码、Token、设备凭证和内部网络信息不得提交。

## 关联文档

- `docs/EPIC_VISION_VALIDATION.md`
- `docs/COMMISSIONING_PLAYBOOK.md`
- `docs/CUROBO_ROUTE.md`
- `docs/COLLABORATION_WORKFLOW.md`
