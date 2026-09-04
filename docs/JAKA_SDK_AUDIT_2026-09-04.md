# JAKA SDK V2.1.5 只读审计

## 审计边界

本次范围仅包含 SDK 二进制、历史源码、配置、状态查询、离线轨迹门禁、Terminal 工具和文档。禁止调用底盘、双臂与夹爪的运动、上电、使能、复位、恢复和停止接口。

## 现场事实

| 项目 | 核实结果 |
|---|---|
| 工控机 | `192.168.99.32` |
| 左臂控制器 | `192.168.99.100:10000` |
| 右臂控制器 | `192.168.99.101:10000` |
| Python 模块 | `/home/yikun/ws/SDK V2.1.5/Linux/python3/x86_64-linux-gnu/jkrc.so` |
| 动态库 | `/home/yikun/JAKA/libjakaAPI.so` |
| SDK 版本 | `V2.1.5stable_linux` |
| 型号 | 站点配置暂记 `JAKA Mini2`；SDK 无可信型号查询，须用双臂铭牌和 JAKA APP 核实 |
| 工具号 | 只读快照中左臂为 1、右臂为 2；每次作业前仍须重新读取 |

现场目录未找到随安装包提供的 C/C++ 头文件。因此，当前接口契约证据仅由 SDK 实际返回值、二进制对象公开方法和旧代码交叉形成，不能代替对应版本的官方头文件。

## 已验证的只读契约

- `get_sdk_version()` 正常返回版本；`get_jaka_pymoudle_version()` 在现场 Python 环境触发 CPython `SystemError`，禁止作为健康检查。
- `get_robot_status()` 返回 `(状态码, RobotStatus)`；V2.1.5 的 `RobotStatus` 实测为 25 个字段。
- 状态字段 22 为 SDK socket 连接，字段 23 为急停。把字段 22 当急停会造成错误拦截。
- `get_tool_data(tool_id)` 实测返回 `(状态码, 工具号, 六维 TCP)`，不是单一二元组值。
- 已验证查询：关节位置、TCP、工具号、工具数据、软限位、碰撞状态、碰撞等级。
- 当前控制器工具配置可读：左臂工具 1 为 `[-11.682, 23.041, 113.927, -0.112766, 0.064315, 0.032777]`，右臂工具 2 为 `[1.538, -6.926, 189.138, -0.095173, -0.043337, 1.491611]`，单位为毫米和弧度。该结果与反算来源尚未独立复核。
- 只确认 `joint_move`、`linear_move`、`servo_move_enable`、`servo_j`、扩展接口和 `motion_abort` 在对象上存在；没有调用控制接口。

`src/ares_r/adapters/jaka_sdk.py` 是独立只读适配器，未包含任何可到达的运动实现。`jaka-readonly` 模式将相机、底盘和夹爪标为 `DISABLED`，并在命令分派前拒绝所有控制命令。

## 机身世界坐标定义

`config/robot_world.json` 采用 `+X` 车体前方、`+Y` 车体左侧、`+Z` 向上。左臂基座为 `(0,+0.200,1.200)m / JAKA yaw +135°`，右臂基座为 `(0,-0.200,1.200)m / JAKA yaw -135°`。两侧外壳“正面”按 JAKA 基坐标 `-X` 解释，因而分别指向右前和左前，互呈 90°。左臂 `q=0` 的 SDK 正解主要沿基坐标 `-Y`，经 `+135°` 变换后指向机身左前，与现场姿态一致。两基座水平间距 400 mm，安装高度 1.200 m。实时 TCP 经过固定基座变换后只用于 Terminal 显示；姿态显示暂按常规 RPY 组合，正式规划前须与 JAKA V2.1.5 姿态约定交叉验证。

现场 `get_dh_param()` 已只读采集到两台机械臂各自的制造校准参数，保存在 `config/jaka_mini2_kinematics.readonly.json`。V2.1.5 实际返回的 `alpha` 约为正负 90，表现为角度制；官网不同版本示例存在角度制与弧度制差异。因此原始值暂不直接代入自编 DH 正解。三视图继续使用控制器 `get_tcp_position()`；真实逐关节折线优先采用控制器正解交叉验证后的模型。

逐关节模型审计发现：JAKA 官方 ROS 2 仓库的 MiniCobo URDF 关节尺寸约为 `187、210、210.5、159.3 mm`，官方 Mini2 产品页标称臂展 580 mm；现场左臂 `q=0` TCP 到控制器基坐标原点距离约 881 mm。直接套用官方 MiniCobo URDF 时，法兰位置与控制器正解相差约 350 mm。差异闭环前，Terminal 不显示伪造的 J1—J6 折线。

## Servo 执行审计结论

`src/ares_r/adapters/jaka_servo.py` 仍是未注册的实验骨架，不属于当前可用 Terminal 功能。进入真机阶段前必须关闭以下缺口：

1. 二进制 Python 扩展无法通过 `inspect.signature` 得到可信签名；须取得与现场 V2.1.5 完全一致的官方头文件或厂商接口说明。
2. `servo_j` 第二返回字段的缓存或队列语义尚未核实，禁止按队列深度解释。
3. 发送线程内逐点同步调用 `is_on_limit()` 与 `is_in_collision()` 会引入不可控抖动，可能破坏 `step_num × 8 ms` 节拍。执行发送、状态监测和看门狗须拆分，并记录最坏延迟。
4. Epic 或 cuRobo 的路径点不能直接发送。必须完成关节顺序、单位、首点连续性、限位、速度、加速度、全臂碰撞、附着物碰撞和时间参数化检查。
5. `joint_move` 适合由控制器完成点到点插补；`servo_j` 只适合已经规划并重定时的稠密关节轨迹。两种模式不得在同一伺服段混用。
6. 夹取料盘后必须切换附着物模型；TCP 只描述工具坐标，不能替代夹爪、料盘和整条机械臂的碰撞体。
7. 奇异点规避应在规划层通过关节空间代价、雅可比条件指标和候选抓取姿态处理，不能依赖控制器限位后恢复。

## 今日可执行任务

### A. 配置证据

- 拍摄双臂铭牌并导出 JAKA APP 型号页面。
- 只读抄录关节软限位、关节顺序、工具号、TCP、负载、碰撞等级和固件版本。
- 将证据来源写入 `config/jaka_mini2_motion.site.json` 和当日日志；证据不完整时保持 `commissioning_confirmed=false`。
- 禁止把旧 MiniCobo 参数复制到 Mini2 配置。旧文件仅保存在 `config/legacy/`。

### B. SDK 契约

- 向供应方取得 V2.1.5 Linux x86_64 的头文件、Python 示例和返回码表。
- 离线核对 `servo_j`、`servo_j_extend`、滤波接口、缓存字段、超时和断线行为。
- 用 Fake SDK 补齐登录失败、查询失败、返回结构变化、急停、限位、碰撞和节拍超时测试；禁止在实机上验证控制调用。

### C. 规划接口

- Epic 路线保存 5700 原始报文、坐标系、单位、关节序和时间信息。
- cuRobo 路线锁定机器人 URDF、关节映射、场景点云、夹爪碰撞体和料盘附着体版本。
- 两条路线统一输出 ARES-R `Trajectory`，仅进入 `motion validate` 与 `jaka preflight`。

### D. 只读验收

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
./scripts/run_terminal.sh --mode jaka-readonly
```

Terminal 中依次执行：

```text
jaka status left
jaka status right
jaka baseline
jaka preflight left examples/trajectory.example.json
```

占位限位未确认时，预检结果必须为 `BLOCKED`。`pick`、`stop`、`gripper open left` 等控制命令必须在 SDK 调用前被拒绝。

## 开启真机执行前的必要条件

- 新的明确运动授权；现场急停与监护流程已确认。
- 型号、软限位、TCP、负载、碰撞等级和工具几何均有证据且经过评审。
- 官方 SDK 契约齐全；伺服周期、返回值、断线和缓冲行为已在非实机环境验证。
- 轨迹发送器与监测器通过延迟、异常、断线和恢复测试。
- Epic 与 cuRobo 路径均通过整臂及附着物碰撞复核。

在上述条件全部完成前，`jaka_servo.py` 不得注册到 Terminal。
