# ARES-R

ARES-R 是 BJUT-BBMG 团队用于双臂移动机器人视觉抓放任务的独立工作区。

目标流程：

1. 底盘到达取料工位并停稳。
2. Epic Pro 检测抓取对象。
3. 规划并执行到预抓取位。
4. 短距离直线接近、夹取并抬升。
5. 底盘到达放置工位并停稳。
6. Epic Pro 再次检测 dock。
7. 规划并执行到预放置位。
8. 垂直放置、释放并退出。

## 目录

- `prototype/`：从原项目复制的现场原型及其最小本地依赖，暂时保持原样。
- `src/ares_r/`：后续正式模块代码。
- `config/`：机器人、相机、工位、TCP 和运行参数。
- `scripts/`：启动与现场辅助脚本。
- `tests/`：不驱动真机的单元测试和协议解析测试。
- `docs/`：接口、架构和调试记录。
- `logs/`：本地运行日志，不提交 Git。
- `worklog/`：人工工作记录、事后补录和交接模板，随 Git 提交。

## 原型入口

当前基线入口为：

```bash
python3 prototype/0_test.py
```

警告：该脚本会连接并控制真实设备。当前原型尚未完成安全检查，也存在 API 不匹配；在修复并完成 dry-run 之前不要直接运行。

## 安全终端框架

新框架默认使用 Mock 设备，不会连接或驱动真机：

```bash
./scripts/run_terminal.sh
```

交互终端支持上下箭头浏览最近输入的命令，并在 `logs/.terminal_history` 中保留最近 500 条本机历史；该文件不会提交到 Git。

可在终端中依次执行：

```text
status
nav pick
detect pick
pick
nav place
detect place 1
place
```

也可以用 `cycle 1` 完成一次 Mock 流程。`camera-only` 模式只连接 Epic 相机，机械臂、夹爪和底盘仍为 Mock：

```bash
./scripts/run_terminal.sh --mode camera-only
```

`hardware` 模式目前有双重锁定，并且在真实设备 Adapter 完成验收前会拒绝启动。

当前站点配置标记为 JAKA Mini2（左臂 `.100`、右臂 `.101`）；SDK 无可信型号查询，型号仍须由双臂铭牌和 JAKA APP 留证确认。只读 SDK 模式只登录并查询状态，不上电、不使能、不运动：

```bash
./scripts/run_terminal.sh --mode jaka-readonly
```

```text
jaka status left
jaka status right
jaka baseline
jaka preflight left examples/trajectory.example.json
world view
```

仓库已经包含第二份现场配置：

```text
config/jaka_mini2_motion.site.json
```

当前上下限为安全占位值，故意保持 `commissioning_confirmed=false`。必须从机器人铭牌/JAKA APP 核实型号，并从控制器或对应型号官方资料核实关节限位后才能填写。该文件纳入 Git 评审；当前 Terminal 不注册 JAKA 运动执行器。

机身世界坐标定义保存在 `config/robot_world.json`：`+X` 为车体前方、`+Y` 为车体左侧、`+Z` 向上；左右臂基座分别位于 `(0,+0.200,0.120)m` 和 `(0,-0.200,0.120)m`。JAKA 基坐标偏航分别为 `+135°` 和 `-135°`；两侧外壳“正面”按 JAKA 基坐标 `-X` 解释，分别指向右前和左前。左臂零关节位姿的 SDK 正解验证了连杆沿机身左前伸展。`jaka-readonly` 每次刷新显示基座和实时 TCP 世界坐标；`world view` 额外显示三视 ASCII 投影和基座到 TCP 的点状空间连线。点状连线只是空间跨度示意，不代表 Mini2 各关节和连杆的真实正运动学姿态。

当前没有机械臂运动命令。`jaka-readonly` 会在 SDK 调用前拒绝 `pick`、`stop`、`arm` 等控制请求；实验性 `jaka_servo.py` 也未注册。只有取得新的明确运动授权、现场配置评审通过并完成执行器验收后，才允许设计独立的受控执行模式。

夹爪单独调试使用 `gripper-only`，此模式不会连接或移动机械臂和底盘：

```bash
./scripts/run_terminal.sh --mode gripper-only
```

工控机默认 Python 没有 pyserial，使用已有 `dope3.8` 环境启动：

```bash
ARES_R_PYTHON=/home/yikun/anaconda3/envs/dope3.8/bin/python \
  ./scripts/run_terminal.sh --mode gripper-only
```

启动脚本现在会在工控机上自动选择该环境，因此通常直接执行下面这一条即可：

```bash
./scripts/run_terminal.sh --mode gripper-only
```

不要省略 `--mode gripper-only`。不带模式启动的是 Mock 仿真，显示的 `simulated_position=1000` 不是实物读数，也不会控制实物。

夹爪位置范围为 `0–1000`。当前约定 `0` 为闭合方向、`1000` 为打开方向：

```text
gripper status right
gripper read right
gripper set right 500
gripper half right
gripper open right
gripper close right
```

所有真实夹爪移动都要求再次输入大写 `YES`，并在发送后等待回读值进入目标 ±10 的范围。

进入 `camera-only` 后，以下命令只触发 Epic 检测并显示抓取坐标，不会操作机械臂、夹爪或底盘：

```text
epic status
epic detect pick
```

保存的 Epic 5700 返回报文与规划轨迹可在任意机器离线检查：

```text
epic parse "220,1,2,..."
motion inspect examples/trajectory.example.json
motion validate examples/trajectory.example.json
```

视觉与运动联合调试入口见 `docs/COMMISSIONING_PLAYBOOK.md`；点云精度实验见 `docs/EPIC_VISION_VALIDATION.md`；cuRobo 迁移路线见 `docs/CUROBO_ROUTE.md`。

2026-09-04 当日现场工作入口见 `docs/daily/2026-09-04_WORK_GUIDE.md`，JAKA 分阶段流程见 `docs/daily/2026-09-04_JAKA_WORKFLOW.md`，V2.1.5 实测契约与 Servo 风险见 `docs/JAKA_SDK_AUDIT_2026-09-04.md`，结果记录使用 `docs/daily/2026-09-04_RESULT_TEMPLATE.md`。

状态含义：

- `UNCHECKED`：终端刚启动，尚未进行网络检查，不代表故障。
- `READY / reachable`：Epic TCP 服务可连接。
- `NOT READY / unreachable`：无法连接 Epic TCP 服务。

检测成功时终端显示 SI 单位坐标和 Epic 原始响应。检测失败但收到类似 `000,3020` 的短报文时，Epic 仍然是 `READY`，原始报文会保留供协议和算法图排查。

终端调试时可随手留痕：

```text
note Epic返回了6维抓取位姿，单位待核实
```

更完整的开发或事后补录使用：

```bash
./scripts/worklog add "完成内容" --author "姓名" --source manual \
  --files src/ares_r/example.py --tests "验证方式" --next "下一步"
```

详细规则见 `worklog/README.md` 和 `CONTRIBUTING.md`。

## 外部依赖

- ROS 1 / `rospy` / `std_msgs`
- JAKA SDK V2.1.5 的 `jkrc.so` 和 `libjakaAPI.so`
- NumPy、SciPy、OpenCV
- websockets
- pyserial
- keyboard

## GitHub 准备

本目录已初始化为 Git 仓库，默认分支为 `main`。创建远程仓库后再执行：

```bash
git remote add origin <repository-url>
git add .
git commit -m "Initial ARES-R workspace"
git push -u origin main
```

提交前必须检查配置和日志中是否包含密码、Token、设备序列号或现场敏感信息。
