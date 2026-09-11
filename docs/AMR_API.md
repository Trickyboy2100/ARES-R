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

`orientation` 在 ART 输入端使用度，发送前转换为弧度。`x/y/orientation` 属于 AMR 厂商接口的相对运动约定；在现场用小位移确认轴向前，不得直接等同于 ARES-R BODY 坐标。碰撞检测固定为 `1`，Terminal 不提供关闭入口。

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
