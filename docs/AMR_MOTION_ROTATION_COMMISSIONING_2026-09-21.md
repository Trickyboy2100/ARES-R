# R300 底盘旋转（yaw）commissioning 记录（2026-09-21）

## 固化结论

ARES-R 当前原地旋转链路固定为：

```text
ART amr move-relative 0 0 -30
  -> AmrHttpBase.move_relative(x, y, yaw_deg)
  -> POST /openapi/control/move/relative   body.orientation = -30
  -> R300 v0.3.18 RelativeMove
```

单位与方向：

| 字段 | 单位 | 依据 |
| --- | --- | --- |
| `orientation` | **度** | 请求 `-30` → 实测 `-29.6°`，一比一 |
| `maxAngularspeed` | **rad/s** | `0.2 rad/s`，30° 约 6 s 转完 |
| `maxLinearspeed` | m/s | `0.2 m/s`，`y=-0.6` 横移任务约 14 s |
| `timeout` | 秒 | 同上；按秒使用可正常结束 |

底盘坐标系为右手系（`+X 前`、`+Y 左`、`+Z 上`），因此：

```text
orientation > 0  -> 逆时针
orientation < 0  -> 顺时针
```

该接口**角度用度、角速用弧度**，是厂商的有意混用，不是笔误。ART 不做轴交换、符号翻转或单位换算。

## 当日实测证据

工具：`scripts/probe_amr_rotation.py`（默认 dry-run；真机需 `--enable-hardware` 加屏幕显示的确认短语）。它先量 8 s 静置漂移作对照，再经**真实适配器路径**发一条相对移动，全程以约 4 Hz 轮询 `/openapi/robot/status` 的 `info.yawNumber`，偏转超过 `--abort-deg`（默认 35°）立即 `GET /control/stop`，并把测量结果写入 `logs/amr_rotation_probe_<时间戳>.json`。

```text
dry-run body: {"collisiondetection":1,"maxAngularspeed":0.2,"maxLinearspeed":0.2,
               "orientation":-30.0,"timeout":60,"x":0.0,"y":0.0}
静置基线 8 s：yaw 在 -13.44 ~ -14.45 之间游走，净漂移 +0.47°
POST -> {"taskid":"e733228b-248e-49ff-b2ef-9ff84f69dc98","status":3}
  t= 2.79s  delta= -1.775
  t= 3.81s  delta= -6.770
  ...
  t=34.76s  delta=-28.844
RESULT requested=-30.000  peak=-29.624  settled=-28.625  idle_drift=+0.4714
```

结论：请求 `-30` 得到 `-29.6°`（峰值）/ `-28.6°`（稳定），同期静置漂移仅 `+0.47°`，信号约为噪声的 60 倍。旋转耗时约 6 s，方向为顺时针。

对照试验：同日 `orientation = -10` 也产生了同符号的真实旋转。两条合起来排除了"字段被静默忽略"与"该字段按弧度解释"这两种可能。

## 单位交叉验证

`GET /openapi/position/list` 的位置点自带 `orientation` 字段，取值明显是度：

```text
posId 1059  name "1"      orientation -107.74199676513672
posId 1055  name "b"      orientation  -30.6476993560791
posId 1054  name "a"      orientation -122.5019989013672
```

`GET /openapi/robot/status` 的 `yaw` / `yawNumber` 同样是度（例如 `-8.35`）。三处一致，故 `move/relative` 的 `orientation` 用度不是孤证。

## 缺陷与修复

缺陷：适配器把 ART 的度数换算成弧度再发送，`-30` 实际发送 `-0.5236`，底盘只转 `0.52°`，宏观完全不可见；而端点对有效与无效请求同样返回 `status=3`，因此该缺陷不会自我暴露。

修复：

| 文件 | 改动 |
| --- | --- |
| `src/ares_r/adapters/amr_http.py` | `move_relative` 第三参数 `yaw_rad` → `yaw_deg`；旋转包络改读 `max_relative_rotation_deg`；注明单位混用 |
| `src/ares_r/terminal.py` | 去掉 `math.radians(yaw_deg)`，度数直传 |
| `config/system.json` | `base.max_relative_rotation_rad: 3.14159…` → `max_relative_rotation_deg: 180.0` |
| `tests/test_amr_http.py` | 断言度值原样上线、包络按度生效 |

注意配置文件改名是修复的**必要部分**：若沿用 `max_relative_rotation_rad = π`，则按度比较后任何输入都会被 π 拦下，等于永远只能转 `3.14°`。

回归结果：`PYTHONPATH=src:tests python3 -m unittest discover -s tests -p 'test_*.py'` → **405 tests OK**。

## 状态判定限制

- `status=3` 对**有效与无效**请求返回一致，不能作为"是否真的运动"的判据。
- `/task/state` 对近期任务返回脏数据：两个不同 `taskid` 返回了同一组 2020 年时间戳。**不得用它计算耗时或判定完成。**
- 地图 pose 不能用于小角度验收：本次静置 8 s 内 `yaw` 漂移约 `0.5°`、`x` 漂移约 `2 cm`；一次 30° 原地旋转过程中上报 `x` 漂移约 `12 cm`（定位置信度约 `41%`）。因此 `±1°` 级差异不能据此下结论。
- 急停路由是 **`GET /control/stop`**；`POST /control/stop` 返回 404。

## 禁止路线

`POST http://192.168.99.30:11378/twist` 仍未获得厂商载荷定义，保持 `BLOCKED_FOR_MOTION`。

## 回归保护

`tests/test_amr_http.py` 固定检查：

- 请求方法与 `/control/move/relative` URL；
- 当前 R300 兼容字段名、数值类型与默认值；
- `orientation` 以**度**原样传递，适配器不做任何单位换算；
- 旋转包络在 **±180°** 生效，`±180.0001°` 被拒绝。

任何协议字段或单位的再次修改都必须产生新的 commissioning 记录，不得静默替换本版本。

## 尚未验收

- **旋转精度**：本次 `-30` 得到 `-29.6°`，但测量依赖低置信度的地图 pose，`±1°` 级精度未验收。
- **未同步点云**：亚度级验收需动作前后 Pixel Pro 点云配准（`scene body-cloud capture` 配合 `scripts/analyze_body_camera_sweep.py`）。
- **碰撞检测**：`collisiondetection` 固定为 `1`，但旋转路径被占用时的实际行为未做遮挡试验。
- **`timeout` 超时行为**：按秒使用可正常结束，但未专门构造超时用例。
