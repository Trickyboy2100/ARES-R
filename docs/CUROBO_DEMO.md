# cuRobo 点到点轨迹 Demo

状态：开发中。当前实现规划与预览；实机执行入口尚未开放。规划失败不使用其他插值代替 cuRobo。

## 启动与设备隔离

仍保留两种启动模式：

```bash
# 不使能实机；可检查保存的请求和规划结果
./scripts/run_terminal.sh

# 使能实机入口，仅连接右臂，不连接左臂、相机或夹爪
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware --devices right-arm
```

`--devices` 选择连接范围，不是第三种模式。被排除的设备显示 DISABLED，不用模拟状态冒充实机。未连接左臂的姿态未知，不能在 world view 中用零姿态替代，也不能当成已知障碍。

## Terminal 命令

```text
curobo status
jaka joints right
curobo plan right J6 deg 0.5
curobo preview logs/curobo_时间_编号/trajectory.json
motion inspect logs/curobo_时间_编号/trajectory.json
motion validate logs/curobo_时间_编号/trajectory.json
```

`plan` 只读取右臂起点，随后启动独立 GPU 子进程。子进程没有 SDK、控制器连接或运动 API。`plan_cspace` 优化关节空间点到点轨迹，不对 TCP 施加直线运动约束；没有障碍的短距离轨迹可能接近直线，不会为了弯曲而人为添加绕行点。

`motion validate` 目前应报告 COLLISION 阻断：模型/现场世界尚未完成碰撞认证，导出文件明确保持 `collision_checked=false`。不得手动改成 true 以绕过检查。

纯离线起终点请求格式：

```json
{"arm":"right","start_rad":[0,0,0,0,0,0],"goal_rad":[0,0,0,0,0,0.008726646259971648]}
```

保存后执行 `curobo plan-file REQUEST.json`。该请求只用于接口演示，不代表当前实机姿态；模型处于碰撞或不可行状态时应失败。

## 数据与限制

- `logs/curobo_*/request.json`：起终点、只读现场快照和请求时间。
- `planner.log`：依赖错误、CUDA 编译和规划过程。
- `trajectory.json`：六关节角度、周期、持续时间、各关节峰值速度/加速度及最大偏移。
- 关节名显式映射：cuRobo `joint1..joint6` → 控制器 `J1..J6`，单位 rad；不使用隐式“前六列”。
- 请求目标限于每关节 0.5°。规划中间点也检查，超范围拒绝；目标误差超过 0.0001 rad 拒绝，不追加修正段。
- 通过增加采样周期放慢时间，不改动 cuRobo 生成的位置序列；周期向上取整为 8 ms 整数倍。峰值速度不超过 0.5°/s、有限差分加速度不超过 1°/s²，检查包含首尾静止段。仍需核验控制器插值与实际平滑性。
- 规划时限 240 s，轨迹时长上限 60 s；不执行自动回程。

## 隔离环境

工控机规划 Python：`/home/yikun/ares-r-curobo-venv/bin/python`，机器人预览配置：`/home/yikun/ares-r-curobo-assets/robot/robot.yml`。

`config/system.json` 可通过 `curobo.python`、`curobo.robot_yaml`、`curobo.timeout_s` 覆盖上述默认值。

- cuRobo 固定提交：`8e734f3ced1df898990bcd92de40abce475907db`。
- `scripts/fetch_curobo_source.py DIR` 下载官方代码/配置并校验 Git blob SHA，不下载无关大型机器人资产。
- `scripts/prepare_curobo_model.py DIR` 从固定 ARES 提交准备六轴预览模型；拒绝覆盖已有模型目录。
- `scripts/audit_curobo_fk.py URDF OUTPUT` 仅连接右臂，使用 SDK 纯 FK 与 URDF 核对；不发送运动。

现场验证：原 ARES URDF 经固定基座变换校正后，14 组右臂 SDK FK 对比最大位置误差约 1.3153 mm、姿态误差约 0.0001704°。该结果不是完整碰撞模型验证；原夹爪碰撞球为空、现场世界模型为空，后续需要补全。

## 后续执行门槛

安装完成并实际通过 GPU 规划测试后，再实现专用右臂 servo 执行器及故障注入测试。必须检查：现场新鲜起点和工具一致性、全轨迹幅度、控制器状态、发送时序、跟踪误差、停止和退出 servo 行为。已确认现场区域隔离与急停条件，但不得由此将任意轨迹视为安全。

参考：[cuRobo plan_cspace 源码](https://github.com/NVlabs/curobo/blob/8e734f3ced1df898990bcd92de40abce475907db/curobo/_src/motion/motion_planner.py)、[JAKA servo 接口](https://www.jaka.com/docs/en/guide/1.7.2/SDK/python.html)。
