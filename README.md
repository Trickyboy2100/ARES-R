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

该文件现已写入 JAKA 官方 MiniCobo/Mini2 共用关节范围，并采用更保守的 ARES-R 速度和软限位裕量。控制器内的现场软限位仍然具有最终约束，执行前必须在 JAKA App 中复核。

机身世界坐标定义保存在 `config/robot_world.json`：`+X` 为北/车体前方、`+Y` 为西/车体左侧、`+Z` 向上，因而东为 `-Y`；左右臂基座分别位于 `(0,+0.200,1.200)m` 和 `(0,-0.200,1.200)m`。对外显示的安装 yaw 采用“北为 0°、俯视顺时针为正”：左臂 `-45°`（等价 `315°`），右臂 `+45°`。内部正运动学矩阵角与该方位角分开保存。双臂全零时左臂指向西北、右臂指向东北；J1 外壳归中朝向分别为东北和西北。`world view` 的 TOP 与从南向北观察的 REAR 均把西侧画在屏幕左方，因此 L 位于 R 左侧；RIGHT SIDE 中右臂后绘制，重合时 R 覆盖 L。三张图均提供上下横尺和左右纵尺。

显示模型来自公开的侧装 MiniCobo MDH 参数，并加入左右镜像的模型到控制器固定旋转。模型已用两台控制器合计 34 组 `kine_forward()` 样本验证：左臂 RMS/最大误差为 0.102/0.308 mm，右臂为 0.242/0.943 mm。该验证足以支持关节折线显示，但折线没有连杆、夹具、负载和环境包络，禁止把它单独用于碰撞判断。验证方法见 `docs/JAKA_DH_VALIDATION_2026-09-04.md`。

`jaka-readonly` 始终拒绝运动 API。独立的 `jaka-motion` 模式只连接双臂，提供受保护的低速 `joint_move`，不连接底盘、相机或夹爪；实验性 `jaka_servo.py` 仍不注册到 Terminal。

关节目标可以先在 `jaka-readonly` 中用 `jaka joints`、`jaka plan`、`jaka step`、`jaka home` 和 `jaka dual` 预览。明确切换到 `jaka-motion` 后，`jaka move` 与 `jaka move-step` 使用 JAKA 官方推荐的控制器插补 `joint_move` 执行附近目标；速度固定为 0.05 rad/s，单次变化限制为每关节 3°，并要求逐次精确确认。完整语法见 `docs/JAKA_JOINT_TERMINAL.md`。

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
