# ARES-R WorldModel v1（W0–W3）

ARES-R `0.2.0` 建立了第一版世界状态事实层。当前实现范围严格限定为 W0–W3：不可变数据合同、摘要、Observation Epoch、生命周期和纯离线 `WorldModel`；尚未接入真实 Epic、JAKA、夹爪、AMR、SceneCompiler 或 Trajectory V2 executor。

## 数据流边界

```text
Live observations
  ├─ RobotState
  ├─ ObservationEpoch(pointcloud + ATOM obstacles + calibration)
  └─ Attachments
          ↓
      WorldModel
          ↓ freeze
  immutable SceneSnapshot
          ↓
  SceneCompiler (W6 pending)
          ↓
  cuRobo + Trajectory V2 (W7 pending)
```

`Epic/ATOM → cuRobo` 直接加载已经阻断。旧 V1 commissioning/demo 只保留显式手工 `urdf_base_link` scene。

## 核心语义

- `PoseSE3` 使用米和 `quaternion_wxyz`；RPY 仅用于界面显示，不进入规划级核心几何。
- `SceneSnapshot` 及其所有嵌套对象永久不可变，不包含 `valid`、`invalid_reason` 等可变状态。
- `SnapshotLifecycle` 独立记录 `ACTIVE / STALE / EXPIRED / LEASED / INVALIDATED`。
- 正常机械臂运动、抓取和释放只令规划起点快照 `STALE`，可复用仍有效的环境版本重新 freeze。
- 底盘移动、新观测开始和标定变化会同时废止当前环境版本。
- 点云、ATOM 障碍、检测 ID 和标定必须属于同一个 `ObservationEpoch`；点云 ID 或 SHA-256 不一致时禁止 commit。
- 中央 14 cm TCP 禁区表示为 `SafetyConstraint`，不伪装成整臂碰撞 cuboid。
- 规划上下文分别记录 obstacle、scene、robot state、attachment 和最终 planning-context SHA-256。
- monotonic 时间只在同一 `runtime_id` 中判断 TTL；重启后的旧产物仅供回放。

## ART 显示

启动后标题显示版本号，状态区始终显示：

```text
WORLD MODEL env=... snapshot=... lifecycle=... planner-binding=... compiler=...
```

详细查看：

```text
world status
```

当前真实适配器尚未进入 WorldModel，因此正常初始状态是：

```text
env=EMPTY
snapshot=NONE
lifecycle=EMPTY
planner-binding=PENDING_W7
compiler=PENDING_W6
```

这不是设备故障，而是明确表示正式感知—规划链路尚未完成 W4–W8，禁止将空世界误报为可规划。

## 后续顺序

1. W4：Epic/ATOM fixture 与真实 observation provenance 接入。
2. W5：JAKA、夹爪、AMR 反馈编译为 `RobotState`。
3. W6：实现 `SceneCompiler(snapshot, arm)`，使用真实碰撞模型。
4. W7：新正式规划产生绑定 `snapshot_id + planning_context_digest` 的 Trajectory V2。
5. W8：实现资源型一次性 `ExecutionLease` 和冲突撤销。
6. W9：V2 executor dry-run；旧 V1 commissioning route 暂时保留。

W6 完成前，WorldModel 不会宣称场景已被 cuRobo 实际使用；W7 完成前，不会宣称轨迹已经绑定世界快照。
