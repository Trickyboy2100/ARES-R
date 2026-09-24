# R300 底盘横移固化记录（2026-09-20）

## 固化结论

ARES-R 当前底盘相对移动链路固定为：

```text
ART amr move-relative
  -> AmrHttpBase.move_relative()
  -> POST /openapi/control/move/relative
  -> R300 v0.3.18 RelativeMove
```

BODY/底盘方向约定：

```text
          +X 前
            ↑
            |
 +Y 左 ←----O----→ -Y 右
            |
            ↓
          -X 后
```

ART 输入的 `x/y` 不做交换或符号翻转。

> **本节关于 yaw 单位的说明已于 2026-09-21 被取代。** 当时记录的“`yaw` 由度转换为弧度后写入 `orientation`”正是导致 `-30` 只转 `0.52°` 的缺陷。实测确认 `orientation` 的单位是**度**，适配器现已改为直传，详见 `docs/AMR_MOTION_ROTATION_COMMISSIONING_2026-09-21.md`。

## 当日实机证据

证据文件：`logs/session-20260920-103024.jsonl`。

| 时间 | ART 参数 | 厂商任务 ID | 软件证据 |
| --- | --- | --- | --- |
| 10:40:23 | `x=0, y=-0.6, yaw=0` | `993336df-1a68-402f-b7cf-5b6343b9f148` | 接收 `status=3`；10:41:24 AMR 日志报告完成 |
| 10:41:31 | `x=0, y=+0.6, yaw=0` | `8e36728f-04b6-46b1-9871-d65eb9da9e92` | 接收 `status=3`；任务查询返回 `Done`，但时间字段异常 |

第一段用于向右横移，第二段用于向左原路返回。当前软件证据足以固化接口、方向符号和载荷兼容格式，但没有同步点云，不能据此宣称 0.6 m 距离精度或返回残差已经验收。

## 已固化的兼容请求体

```json
{
  "x": 0.0,
  "y": -0.6,
  "orientation": 0.0,
  "maxLinearspeed": 0.2,
  "maxAngularspeed": 0.2,
  "collisiondetection": 1,
  "timeout": 30.0
}
```

该格式是现场当前代码实际使用并由 R300 v0.3.18 接收的兼容格式。厂商 v0.3.17 截图使用全小写速度字段及 `timeout=10000`；在没有重新实机 commissioning 前，不改变当前字段大小写、布尔表示或超时单位。

## 状态判定限制

- HTTP 成功或 `status=3` 只说明请求被接受，不等于实际位移精确完成。
- `/task/state` 可返回陈旧或错误时间；第二个任务出现 2020 年时间戳。
- `/robot/status.state=IDLE` 不能单独证明某一任务已经正确完成。
- 地图定位置信度较低时存在漂移，不适合作为厘米级唯一验收依据。
- 后续精度验收应同步保存动作前后 Pixel Pro 点云、现场观察和 AMR 运行日志。

## 禁止路线

`POST http://192.168.99.30:11378/twist` 尚未获得厂商载荷定义。标准 ROS 嵌套 `linear.y` 的现场结果是旋转而非横移，因此该接口保持 `BLOCKED_FOR_MOTION`。

## 回归保护

`tests/test_amr_http.py` 固定检查：

- 请求方法和 `/control/move/relative` URL；
- 当前 R300 兼容字段名、数值类型和默认值；
- 横移 `y` 原样传递，不在适配器中交换坐标轴或反转符号；
- 位移、速度、转角和超时安全包络继续生效。

任何协议字段修改都必须产生新的 commissioning 记录，不得静默替换本版本。
