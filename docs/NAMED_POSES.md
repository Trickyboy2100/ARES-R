# ARES-R 常用姿态库

统一姿态先在机器人 `BODY` 坐标系定义：`+X` 向前（北）、`+Y` 向左（西）、`+Z` 向上。左右目标分别经过 `BODY→BASE_left/right` 固定安装变换，再结合控制器当前 Tool/TCP 标定求解。不得把同一组 BASE 位姿或关节角复制给另一臂。

数据文件为 `config/named_poses.json`，包含 `zero`、`ready`、`forward`、`up`、`side`、`folded`；每项始终同时定义左右臂，因此天然支持单臂或双臂选择。`commissioning` 状态不是备注，而是执行门禁：

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

## 2026-09-28 新增 `folded`（右臂收料避让）

首个**夹持物料时**验收的命名位姿：右臂把料盘收在身前，让出机身相机的视野，供后续底盘移动 → 识别 → 预放置 → 放置段使用。

| 项 | 值 |
|---|---|
| BODY TCP | `(0.24046081948236367, -0.17163989128810897, 1.20000) m` |
| BODY 姿态 (ZYX) | `(π/2, 0, π)` = `(90°, 0°, 180°)` |
| 工具轴（BODY） | X=`(-1,0,0)`，Y=`(0,0,1)`，Z=`(0,1,0)` |
| 右臂关节 | `[-3.455498892536459, 1.331083004008305, -2.100110381841644, -2.9634403896316264, 1.6001915371217963, -4.899765010805292] rad` |
| 料盘倾角 | `0.000°`（拖拽原始位姿为 `3.124°`） |
| IK 残差 | `6.0e-6 m` / `0.0034°` |
| 相对拖拽位姿行程 | `39.49°`（约束关节为 J1） |

**该朝向是唯一的。** 物料在工具系里的竖轴为 `u_tool = R_grasp^T · z_BODY`；本次抓取满足 `tool Z = BODY +X`、`tool Y = BODY +Z`，所以「料盘水平」⟺「tool Y 指向 BODY +Z」。同时满足「tool Z 指向 BODY +Y」和「料盘水平」的旋转只有一个绕竖轴的偏航，即 `Rz(+90°) · R_grasp`。注意它**不同于 `ready` 的右臂朝向**：`ready` 是空夹爪，其 `tool Y = BODY -Z`，同样「tool Z 指向 +Y」但料盘会翻倒。

**commissioning 范围**（右臂）：IK/FK、关节余量（`39.49°` vs 原生 `150°` 上限）、BODY 中线禁区（`y = -0.172 m`，禁区要求 `y <= -0.070 m`）、臂链接对机身的碰撞与非相邻自碰撞、2026-09-28 实机两次 `0.10 rad/s` 试运行——全部通过。**未验证**：cuRobo 点云级的工具/物料碰撞，以及左臂路径；`folded` 的左臂记录的是 2026-09-28 实测停放关节角（3 位小数），不属于本次 commissioning。

执行路线：`jaka_right_supervised_path_v6_pick`，先离线 `validate-supervised-path <native.txt>`，再 `supervised_path <native.txt> CONFIRMED_RIGHT_CLEAR`。

## 2026-09-28 新增 `center`（右臂持料居中）

`folded` 之后第二个夹持物料的姿态，仍属收料避让类，**不是放置点**：右臂把料盘停在机体中线右侧 `80 mm`、料盘水平。
`y = -0.080 m` 是能靠近中线的极限——中央隔离带要求 `y <= -0.070 m`，只剩 `10 mm` 余量。

| 项 | 值 |
|---|---|
| BODY TCP | `(0.3583093030168863, -0.080000000, 1.0278356006116391) m` |
| BODY 姿态 (ZYX) | `(π/2, 0, π)` = `(90°, 0°, 180°)` |
| 工具轴（BODY） | X=`(-1,0,0)`，Y=`(0,0,1)`，Z=`(0,1,0)` |
| 右臂关节 | `[-4.16054218920497, 0.12380159547135215, -1.6410621564086367, -5.609400696253764, -1.1920778258720994, -2.656972108297568] rad` |
| 料盘倾角 | `0.000°`（拖拽原始位姿为 `2.862°`） |
| 半径 / 方位 | `0.367110 m` / `-12.60°` |
| IK 残差 | `2.9e-7 m` / `1.7e-4°` |
| 独立 FK 复核 | 位置 `2.9e-7 m`，tool Z = `(0, 1, 0)`，料盘倾角 `8.0e-5°` |
| 相对 2026-09-28 实测起点的最大关节行程 | `7.39°`（原生上限 `150°`） |

来源是操作手 2026-09-28 的第二次手动拖拽（`worklog/evidence/2026-09-28-place/right_tcp_now_20260928T164258/`）。
规范化只做两件事：把 `y` 从 `-0.0550 m` 拉到 `-0.0800 m`（水平移动 `25.0 mm`），把姿态从 `2.862°` 倾角摆到 `0.000°`。
朝向沿用 `folded` 的「水平且朝左」唯一解，推导见上一节。高度保留拖拽值 `1.0278 m`，未采用合同里的 `1.20 m`。

**commissioning 状态：`commissioned`（仅右臂，2026-09-28 实机一次）。**
路线：`production_scene_worker`（cspace 规划 121 knot，路径余量 `0.0651 m`，随动料盘已声明为 attached collision object）→ `package_native_preview` → `jaka_right_supervised_path_v6_pick supervised_path`，`0.10 rad/s` / `0.20 rad/s²`，138 采样 / `10.96 s`，`target_reached`、`servo_disabled code=0`、无 abort。

实测端点回读：**六关节残差 `0.0000°`**；控制器报 TCP `(339.0395, -166.6447, -172.4692) mm`，即 BODY `(0.357573, -0.078098, 1.027531) m`，与标称目标差 **`2.06 mm`**——这是既有的「URDF 模型 vs 控制器」标定差（同一对读数在只读审计里是 `1.88 mm`），不是跟随误差。端点中央禁区余量 `+8.1 mm`，规划路径最差 `+10.0 mm`；料盘倾角 `3.587° → 0.000°` 且全程不变差；臂链-机身与非相邻自碰撞 `0`；夹爪全程保持（raw 39）。

**未验证**：左臂路径；`pose go ... curobo`（`obstacle_demo` 规划器）与 `pose go ... direct`（控制器 MoveJ）两条路线都没有在本姿态上跑过，因此 `commissioned_routes` 只登记实跑的那条，`pose go` 会拒绝这两条路线。
左臂记录的是实测停放关节角，不属于本次设计。

执行证据：`worklog/evidence/2026-09-28-place/center_exec_20260928T172814/`、`tmp/place_9.28/out/center_exec/`。
规划脚本：`tmp/place_9.28/plan_center_curobo.py`；剖面分析：`tmp/place_9.28/analyze_tilt_profile.py`。

目标文件：`tmp/place_9.28/out/vis_target3/visibility_clear_target.json`。
注意该文件里 `regularised.controller_tool_pose_mm_rad` 存的是**米**值，字段名又与站内「控制器工具坐标系（link6→TCP 偏置）」含义冲突，只能当数值参考；
脚本已改为输出 `controller_tcp_pose_m_rad` / `controller_tcp_pose_mm_rad`，重新生成即无歧义。
