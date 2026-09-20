# ARES-R 底盘运动现状（2026-09-18）

## 结论

R300 底盘具备全向横移能力，物理手柄已验证可以左右平移。当前 ARES-R 已验证前后相对移动，但代码横移尚未 commission。主要问题不是底盘机构不支持横移，而是 ARES-R 发送的相对移动字段与厂商 `0.3.17` 接口文档不完全一致，需要先修正请求格式，再进行小范围实机验证。

`11378/twist` 当前不得用于横移：向该接口发送标准 ROS 嵌套 `Twist.linear.y` 后，底盘发生旋转而没有平移，说明该服务不是标准三自由度 Twist 接口，或使用了厂商私有载荷格式。

## 设备与接口

| 项目 | 当前信息 |
| --- | --- |
| 底盘型号 | R300 |
| 底盘软件 | `0.3.18` |
| Web 管理界面 | `http://192.168.99.30:3000/` |
| OpenAPI 基址 | `http://192.168.99.30:11375/openapi` |
| 相对移动 | `POST /control/move/relative` |
| 立即停止 | `GET /control/stop` |
| 状态读取 | `GET /robot/status` |
| 私有速度服务 | `POST http://192.168.99.30:11378/twist`，未 commission，禁止使用 |

## 已验证事实

1. `/control/move/relative` 的 `x` 方向曾成功执行约 `0.09 m` 平移；点云配准估计实际位移约 `0.08934 m`，返回后的残差约 `3.5 mm`。
2. 使用 ARES-R 当前请求格式测试 `y=-0.10 m` 和 `y=+0.10 m` 时，点云均未观察到可信横移。
3. 物理手柄的独立横移摇杆可以驱动底盘横移。一次人工右移的点云配准估计位移约 `0.07153 m`，证明麦克纳姆底盘和底层驱动具备横移能力。
4. 手柄的前后与旋转位于同一摇杆，左右横移位于另一摇杆，说明底层确实存在独立横向自由度。
5. MQTT 只读监听能够收到 `msg/status`、`msg/path`，但多次物理手柄横移期间没有收到控制主题。因此物理手柄控制不经过当前网页 MQTT 命令通道，不能通过监听 `command/robot/move` 反推出横移载荷。
6. AMR `robot/status.state` 可能持续显示 `IDLE`，而运行日志仍显示任务正在执行。相对运动完成判据不能只依赖 `state`，至少还要结合运行日志、停止反馈和外部位姿/点云观测。
7. 地图定位置信度曾处于约 30%～40%，静止时地图位姿也可能漂移。毫米到厘米级运动验证不得只使用地图 pose，应优先使用现场观察和 Pixel Pro 点云配准。

## 厂商文档与当前代码的差异

厂商 `0.3.17` 文档给出的相对移动 body 为：

```json
{
  "x": 0.0,
  "y": 0.02,
  "orientation": 0.0,
  "maxlinearspeed": 0.05,
  "maxangularspeed": 0.10,
  "collisiondetection": true,
  "timeout": 10000
}
```

文档明确说明：

- `x`：X 轴移动距离；
- `y`：Y 轴移动距离；
- `orientation`：旋转角度；
- `maxlinearspeed`：最大线速度；
- `maxangularspeed`：最大角速度；
- `collisiondetection`：是否开启碰撞检测；
- `timeout`：超时，文档默认值为 `10000`。

ARES-R 当前 `src/ares_r/adapters/amr_http.py` 使用：

```json
{
  "maxLinearspeed": 0.05,
  "maxAngularspeed": 0.10,
  "collisiondetection": 1,
  "timeout": 30
}
```

需要处理的差异：

1. `maxLinearspeed` 应核对并改为全小写 `maxlinearspeed`；
2. `maxAngularspeed` 应核对并改为全小写 `maxangularspeed`；
3. `collisiondetection` 应发送 JSON 布尔值 `true`；
4. `timeout` 的 `10000` 很可能是毫秒，而 ARES-R 当前按秒传入；在完成厂商确认前，应在适配器边界明确转换并记录原始载荷；
5. 图片对应 `0.3.17`，现场为 `0.3.18`。接口预计兼容，但仍必须以小范围实机结果为准。

上述字段差异是当前横移失败的首要排查方向。修正前不能再次以现有载荷判定 `y` 不受支持。

## `11378/twist` 试验结论

服务配置中存在独立 `twist: 11378`，且只有 `POST /twist` 路由。曾发送标准 ROS 风格载荷：

```json
{
  "linear": {"x": 0, "y": -0.01, "z": 0},
  "angular": {"x": 0, "y": 0, "z": 0}
}
```

现场确认结果为“发生旋转，没有平移”。因此：

- 不得把该接口当作 `geometry_msgs/Twist`；
- 不得继续用嵌套 `linear.y` 探测横移；
- 在取得厂商载荷定义或服务源码之前，ART 不应暴露该接口；
- 已使用 `/openapi/control/stop` 和零速请求停止试验。

## 当前安全状态

- 底盘、机械臂和夹爪没有持续运动任务。
- 本文档整理过程没有下发运动命令。
- 横移功能状态：`UNCOMMISSIONED`。
- `11378/twist` 状态：`BLOCKED_FOR_MOTION`。
- `/control/move/relative x`：已进行过小范围验证，但仍不等同于生产级导航。
- `/control/move/relative y`：等待修正载荷后的重新验证。

## 下一次最小验证流程

1. 仅修改 AMR 适配器的请求字段、布尔类型和超时单位，并补充单元测试；不立即运动。
2. 增加 dry-run/审计输出，完整打印即将发送的 URL、JSON body、单位和 BODY 方向，不包含密码。
3. 现场确认左右两侧净空、持续观察和物理急停可用后，只授权一次 `|y|=0.02 m` 的动作。
4. 使用低速、碰撞检测开启、短超时；每次请求结束后主动发送 `/control/stop`。
5. 同时记录现场目测、请求/响应、运行日志以及动作前后 Pixel Pro 点云。
6. 用点云配准确认是否横移、实际距离、旋转漂移和方向符号；地图 pose 只作为辅助信息。
7. 原路返回并再次采集，检查返回残差。
8. 只有 `+y/-y` 与 ARES-R BODY `+Y=左、-Y=右` 的映射通过验证后，才把横移加入 ART 正式指令。

## 现有证据

- 点云/底盘 sweep 会话：`logs/calibration/body_camera/20260917_163644_0dd5978e/`
- 人工横移观察：`translation_observations_v2.json`
- yaw 校验：`body_camera_rotation_z_validation.json`
- 错误 `twist.linear.y` 试验点云：`captures/twist_linear_y_validation_20260917_183140/`
- ARES-R 现有接口说明：`docs/AMR_API.md`

## 不应重复的操作

- 不再向 `11378/twist` 发送标准 ROS 嵌套 `linear/angular` 对象；
- 不使用地图定位漂移作为厘米级移动是否成功的唯一证据；
- 不在字段大小写、布尔类型和超时单位未修正前重复 `y` 横移试验；
- 不因 HTTP 200、任务 ID、`success: true` 或 `state=IDLE` 单独判定底盘确实执行了预期运动。
