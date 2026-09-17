# 双臂统一 SafetyKernel 与运动入口清单

## 已落地的控制点

`src/ares_r/motion/safety_kernel.py` 只接受真实规划模型输出的逐采样 BODY collision spheres，不使用 `world view` 的 display MDH 折线。授权条件包括：

- 一次只允许一条臂；
- 底盘静止，另一臂状态已知；
- controller 无 E-stop/collision/limit/fault；
- live start 与轨迹起点一致；
- 完整 tool/TCP revision 一致；
- trajectory 绑定 collision-checked SceneSnapshot；
- 每个采样都有 links、tool、inactive arm，持物时还有 attached object；
- 所有几何均不得接触 BODY 中央 14 cm slab；
- 命名 speed profile 的速度/加速度门通过。

只有上述检查才能生成与 arm、完整 trajectory digest、scene 和 speed profile 绑定的 `SafetyPermit`。

当前 `config/system.json` 明确设为：

```json
"execution_enabled": false
```

所以今天的 integration 分支不能生成实机运动许可。

## 正式入口覆盖

| 入口 | 底层 API | 当前状态 |
|---|---|---|
| `JakaSdkArm.move_joints_absolute` | `joint_move` | 必须带 full-path permit；旧 Terminal/命名姿态调用因没有 permit 而阻断 |
| `JakaServoExecutor.execute` | `servo_j` | 必须带 trajectory-matched permit |
| `jaka_micro_servo.execute_micro` | `servo_j_extend` | 必须带 permit，且现场反馈问题仍保持 suspended |
| `native_demo.execute` / pregrasp / demo20 | C++ `servo_j` | Python 启动前必须带 permit；旧调用链因此阻断 |
| `scripts/jaka_right_demo.cpp` | C++ `servo_j` | 保留本地 sender gates，但直接从 shell 启动属于管理员绕过，不是 ART 支持入口 |

离线测试证明：缺逐点几何、缺另一臂、tool/scene/start 不匹配、速度越界或任一 link/tool 球触碰 slab 均不能获得 permit。

## 尚未统一、因此阻止下次运动的入口

- 根目录 `b5_*.py` 与 `prototype/` 中的遗留直接 SDK 脚本；
- AMR HTTP motion 与双臂 transport-safe interlock；
- 夹爪动作与 attach/release 状态事务；
- C++ sender 被人工直接启动的管理员级绕过；
- planner 尚未输出完整双臂/夹爪/tool/payload BODY sphere samples。

因此当前不能回答“所有历史入口均已统一覆盖”。准确结论是：**正式 Python arm gateways 已 fail-closed；遗留脚本和 AMR/夹爪尚待隔离/接入，在完成前保持全局 execution disabled。**
