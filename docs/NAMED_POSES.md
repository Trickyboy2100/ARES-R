# ARES-R 常用姿态库

统一姿态先在机器人 `BODY` 坐标系定义：`+X` 向前（北）、`+Y` 向左（西）、`+Z` 向上。左右目标分别经过 `BODY→BASE_left/right` 固定安装变换，再结合控制器当前 Tool/TCP 标定求解。不得把同一组 BASE 位姿或关节角复制给另一臂。

数据文件为 `config/named_poses.json`，包含 `zero`、`ready`、`forward`、`up`、`side`；每项始终同时定义左右臂，因此天然支持单臂或双臂选择。`commissioning` 状态不是备注，而是执行门禁：

- `design_target_uncommissioned`：只有 BODY 空间设计目标，禁止执行。
- `endpoint_verified_readonly_path_not_verified`：控制器 FK 已验证终点，路径未验证，禁止执行。
- `commissioned`：IK/FK、关节余量、TCP 中线禁区、整臂/工具/环境碰撞、实机低速试运行和留档全部通过后方可设置。

Terminal 当前可安全查看：

```text
pose list
pose show ready
pose show forward left
```

规划与执行的统一数据流：

```text
BODY 目标
  -> 左/右 BASE 目标
  -> 各自 TCP/法兰目标
  -> IK 与关节余量检查
  -> direct: JAKA joint_move（控制器插值）
  -> cuRobo: plan_cspace 完整轨迹 -> 8 ms 采样 -> JAKA servo_j
```

`direct` 仅适用于已验收的空旷转位，并且必须增加独立实际反馈、超时中止与逐臂确认；不提供避障保证。`curobo` 是默认的大范围转位路线，但只有夹爪、负载、另一机械臂、车体和场景碰撞模型齐备后，才能把规划结果视为实机避障轨迹。

## 2026-09-08 现场发现

- 初始 BODY TCP：左侧约 `(0.389,+0.084,1.156)m`，右侧约 `(0.369,-0.005,1.202)m`；右 TCP 位于 14 cm 身体中线禁区内。
- 首轮 BODY 目标经 JAKA 多初值 IK 检查，多数结果越过 J5 软限位；“上举”返回成功码但 FK 偏差约 0.5 m，全部拒绝执行。
- 右 J1 增加方向可使 TCP 向右退出禁区。一次 `+3°` 低速实机单步到达目标，但阻塞 SDK 调用未按预期返回，随后 TCP 查询短暂返回 `(-3)`；没有继续批量下发。
- 因 Tool 1/2 标定与安装关系不同，后续须建立“物理夹爪语义坐标系→各自 TCP”的显式标定，才可确认“水平、正对、夹指闭合方向垂直”的统一含义。
