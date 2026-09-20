# ARES-R 底盘 HTTP 接口

现场 AMR Web 管理界面为 `http://192.168.99.30:3000/`，OpenAPI 基址为：

```text
http://192.168.99.30:11375/openapi
```

## 已核验的只读接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/position/type/list` | 获取位置类型列表 |
| GET | `/map/current` | 获取当前地图 |
| GET | `/battery` | 获取电量与充电状态 |

2026-09-11 从工控机只读验证：三个接口均返回 HTTP 200 JSON；当时地图为 `831`（id 379），电量为 98%。这些值只是当时快照，不写入配置。

## 控制接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/control/stop` | AMR 停止 |
| POST | `/control/move/position` | 移动到地图位置点；`id`、`posName`、`retries` 同时写入查询参数和 JSON body |
| POST | `/control/move/relative` | AMR 原生相对坐标系移动 |
| GET | `/task/run?taskid=...` | 运行已配置任务 |

相对移动 body：

```json
{
  "x": 1.0,
  "y": 0.5,
  "orientation": 0.0,
  "maxLinearspeed": 0.2,
  "maxAngularspeed": 0.2,
  "collisiondetection": 1,
  "timeout": 30
}
```
> 底盘坐标系中，x方向为前后，y为左右：
>
> ```text
>           x+
>           ↑
>           |
>           |
> y+ ←------O------→ y-
>           |
>           |
>           ↓
>           x-
> ```

> `orientation` 在 ART 输入端使用度，发送前转换为弧度。`x/y/orientation` 属于 AMR 厂商接口的相对运动约定；在现场用小位移确认轴向前，不得直接等同于 ARES-R BODY 坐标。碰撞检测固定为 `1`，Terminal 不提供关闭入口。

### R300 v0.3.18 兼容载荷

2026-09-20 的实机测试使用当前适配器载荷成功下发横移动作。为保持现场兼容性，当前版本继续使用以下字段，不得在没有重新 commissioning 的情况下仅依据旧版文档改名或换算单位：

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

现场方向约定已经确认：`x+=前`、`x-=后`、`y+=左`、`y-=右`。ART 不进行轴交换或符号翻转，输入值原样进入厂商相对移动接口。

实机记录：

- `10:40:23` 下发 `x=0, y=-0.6, yaw=0`，任务 `993336df-1a68-402f-b7cf-5b6343b9f148`；AMR 于 `10:41:24` 报告“相对位置移动已完成”。
- `10:41:31` 下发 `x=0, y=+0.6, yaw=0`，任务 `8e36728f-04b6-46b1-9871-d65eb9da9e92`，用于原路返回。
- 第二个任务查询返回 `Done`，但控制器返回的任务时间错误地落在 2020 年，不能把该时间字段作为可信证据。
- 本轮没有同步采集起终点点云，因此“请求已执行”和“精确移动/返回 0.6 m”必须区分。厘米级精度仍需点云或高可信外部定位验收。

`http://192.168.99.30:11378/twist` 不属于本兼容接口。曾向其发送标准 ROS 嵌套 `Twist.linear.y`，现场结果为旋转而非横移；在获得厂商私有协议前禁止由 ART 调用。

## ART 命令

实机启动：

```bash
cd /home/yikun/ARES-R
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware
```

只读命令：

```text
amr status
amr battery
amr map
amr position-types
```

控制命令：

```text
amr move-position ID NAME [RETRIES]
amr move-relative X_M Y_M YAW_DEG
amr move-relative X_M Y_M YAW_DEG LINEAR_MPS ANGULAR_RADPS TIMEOUT_S
amr run-task TASK_ID
amr stop
```

位置、相对移动和任务执行均要求输入 Terminal 显示的精确确认短语。`amr stop` 为立即停止，不要求二次确认。相对移动受 `config/system.json` 中的位移、转角、速度、超时上限约束。

`nav pick|place` 使用 `base.positions` 中的命名位置。仓库不猜测现场地图位置 ID，因此默认字典为空；必须从 AMR 管理界面核实后按以下形式填写：

```json
"positions": {
  "pick_station": {"id": "实际ID", "posName": "实际名称", "retries": 1},
  "dryer_station": {"id": "实际ID", "posName": "实际名称", "retries": 1}
}
```

当前仅完成接口与只读连通性验证。运动接口尚未现场 commissioning，首次动作必须空载、低速、小位移、现场观察并可使用物理急停。
