# cuRobo 点到点轨迹 Demo

最新状态：已用独立 SDK V2.2.2 路径完成右臂约 20 cm 实机 Demo，操作与结果见 [实机 20 cm 指南](CUROBO_REAL_DEMO20.md)。旧 Python/原始反馈执行入口仍锁定。下文保留早期接入和失败排查历史；规划失败不使用其他插值代替 cuRobo。

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
curobo plan right J6 deg 0.2
curobo preview logs/curobo_时间_编号/trajectory.json
motion inspect logs/curobo_时间_编号/trajectory.json
motion validate logs/curobo_时间_编号/trajectory.json
```

`plan` 只读取右臂起点，随后启动独立 GPU 子进程。子进程没有 SDK、控制器连接或运动 API。`plan_cspace` 优化关节空间点到点轨迹，不对 TCP 施加直线运动约束；没有障碍的短距离轨迹可能接近直线，不会为了弯曲而人为添加绕行点。

`preview` 输出统计并生成相邻的 `trajectory.preview.html`，包含六关节角度表、偏移/速度/加速度曲线和时间滑块。浏览器打开 HTML 即可离线回放，不会连接机器人。`curobo execute-micro FILE` 当前直接报阻断原因，不进入确认、不发送运动。

`motion validate` 目前应报告 COLLISION 阻断：模型/现场世界尚未完成碰撞认证，导出文件明确保持 `collision_checked=false`。不得手动改成 true 以绕过检查。

纯离线起终点请求格式：

```json
{"arm":"right","start_rad":[0,0,0,0,0,0],"goal_rad":[0,0,0,0,0,0.008726646259971648]}
```

保存后执行 `curobo plan-file REQUEST.json`。该请求只用于接口演示，不代表当前实机姿态；模型处于碰撞或不可行状态时应失败。

## 数据与限制

- `logs/curobo_*/request.json`：起终点、只读现场快照和请求时间。
- `planner.log`：依赖错误、CUDA 编译、规划过程及完整 `ARES_R_TIMING` 分阶段时间戳；Terminal 同步显示阶段耗时。
- `trajectory.json`：六关节角度、周期、持续时间、各关节峰值速度/加速度及最大偏移。
- 关节名显式映射：cuRobo `joint1..joint6` → 控制器 `J1..J6`，单位 rad；不使用隐式“前六列”。
- 请求目标限于每关节 0.5°。规划中间点也检查，超范围拒绝；目标误差超过 0.0001 rad 拒绝，不追加修正段。
- 通过增加采样周期放慢时间，不改动 cuRobo 生成的位置序列；周期向上取整为 8 ms 整数倍。峰值速度不超过 0.5°/s、有限差分加速度不超过 1°/s²，检查包含首尾静止段。仍需核验控制器插值与实际平滑性。
- 规划时限 240 s，轨迹时长上限 60 s；不执行自动回程。

## 隔离环境

工控机规划 Python：`/home/yikun/ares-r-curobo-venv/bin/python`，机器人预览配置：`/home/yikun/ares-r-curobo-assets/robot/robot.yml`。当前采用 Python 3.10.4 venv，通过 `--system-site-packages` 只读继承现有 dope 环境的 torch 2.5.1+cu124；新增依赖仅安装在新 venv。该环境不是完全独立的可移植环境，迁移时需重新建立并核验依赖。

实际通过 GPU 规划的组合：RTX 3060 Laptop GPU、驱动 560.35.03、warp-lang 1.13.0、numpy 1.26.4、cuRobo `0.0+ares.8e734f3`。官方源码共 444 个文件通过 Git blob SHA 检查；规划工作进程再次校验清单。早期 Python 3.11 安装尝试未用于最终规划。

`config/system.json` 可通过 `curobo.python`、`curobo.robot_yaml`、`curobo.timeout_s` 覆盖上述默认值。
规划耗时参数、锁定源码接口和固定请求基准见 [2026-09-08 规划耗时审计](CUROBO_PLANNING_TIME_AUDIT_2026-09-08.md)。

- cuRobo 固定提交：`8e734f3ced1df898990bcd92de40abce475907db`。
- `scripts/fetch_curobo_source.py DIR` 下载官方代码/配置并校验 Git blob SHA，不下载无关大型机器人资产。
- `scripts/prepare_curobo_model.py DIR` 从固定 ARES 提交准备六轴预览模型；拒绝覆盖已有模型目录。
- `scripts/audit_curobo_fk.py URDF OUTPUT` 仅连接右臂，使用 SDK 纯 FK 与 URDF 核对；不发送运动。

现场验证：原 ARES URDF 经固定基座变换校正后，14 组右臂 SDK FK 对比最大位置误差约 1.3153 mm、姿态误差约 0.0001704°。该结果不是完整碰撞模型验证；原夹爪碰撞球为空、现场世界模型为空，后续需要补全。

## 2026-09-07 实机结果与阻断

- 首次 J6 +0.5° 试验在第 14 个目标发送前触发跟踪误差保护，停止和退出伺服返回成功。SDK `get_joint_position()` 在该次测试中未提供有效实际跟踪反馈，不能据此认定机械臂没有移动。
- 审计发现 `.101:10004` 的压缩状态报文含 `joint_actual_position`（度）与 `joint_position` 两个不同字段。新增只读解码器，实际值统一转换成 rad；SDK 版本/接口名称不能替代反馈语义核验。
- 重新规划 J6 +0.2°：41 点、周期 80 ms、时长 3.2 s、规划峰值速度约 0.107832°/s、加速度约 0.160083°/s²。使用现场 `servo_j_extend(q, 0, 10)`，绝对模式、每步 10×8 ms。
- 第二段实际测试发送索引 0..16 后反馈连接关闭；`abort_accepted`、`servo_disabled` 均有日志，未记录 `target_reached`。停止后 J6 实际约 97.81635°，相对该段起点约 +0.06591°，并未完成 +0.2°。两次运动没有自动回程。
- 仅读取状态的连续测试也复现连接关闭。SDK 反馈连接竞争、其他客户端连接、服务端协议/会话限制仍需区分，不能把推测写成根因。
- 最后只读 SDK 检查：到位、已上电/使能，错误码 0，无急停、保护停、限位或碰撞标志。该检查不替代现场观察。
- 测试未连接左臂，也未操作底盘、相机或夹爪。右臂模型名来源仍是现场配置 `JAKA Mini2`，不是可信型号查询。

证据目录：[`worklog/evidence/2026-09-07-curobo`](../worklog/evidence/2026-09-07-curobo/)。规划结果与失败执行日志分开保存，规划曲线不代表实际完整执行。

## 下一阶段工作顺序

最新反馈排查、Terminal 只读诊断命令和 SDK V2.2.2 进展见 [右臂反馈专项记录](RIGHT_FEEDBACK_AUDIT_2026-09-07.md)。原始 10004 通道和新的单 SDK 路径分别验证，不混用结论。

1. 保持运动关闭，先核验实际反馈会话：固定频率连续读取至少 10 分钟，记录连接关闭时刻、读取次数和延迟；分别比较无 SDK 会话、SDK 登录会话及现场其他客户端状态。不得停止共享进程或改动左臂测试环境。
2. 查证当前控制器版本支持的官方实际关节反馈接口和多客户端约束，优先使用受支持的单一 SDK 通道。必要时准备独立版本验证环境，不覆盖现有 SDK；版本升级需要独立变更安排。
3. 增加断连、超时、跟踪误差、工具变化、控制命令失败和日志写入失败的故障注入测试。不得靠运行中自动重连继续发送、放宽保护阈值或去掉反馈恢复执行。
4. 稳定反馈与异常停止通过后再修改源码解除专用执行锁，重新进行现场净空确认和新鲜起点规划，仅右 J6 小幅低速一次测试；验证完整到位、实际速度和平滑性，不自动回程。
5. 完成夹爪/TCP/料盘碰撞体、现场障碍和左臂占用区域建模后，才扩展至多关节、较大距离和感知目标。当前 `link6` 模型目标是法兰，不等于工具 2 的标定 TCP。

执行器代码保留用于离线注入测试：新鲜起点、工具一致性、全轨迹幅度、状态、发送时序、跟踪误差及停止/退出伺服。当前终端和默认实际反馈执行路径均禁止实机重试，没有环境变量绕过入口。

参考：[cuRobo plan_cspace 源码](https://github.com/NVlabs/curobo/blob/8e734f3ced1df898990bcd92de40abce475907db/curobo/_src/motion/motion_planner.py)、[JAKA servo 接口](https://www.jaka.com/docs/en/guide/1.7.2/SDK/python.html)。
