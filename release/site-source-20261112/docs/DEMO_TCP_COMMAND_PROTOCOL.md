# Demo 控制台 TCP 指令协议

`scripts/run_demo_console_tcp.py` 在现有 RC1 Demo 控制台（HTTP `:8775`）之上提供一个
**TCP 指令端口**，供 PLC / 上位机 / 外部脚本触发不同 Demo。它只是控制台 API 的薄
适配层：不自行规划、不自动重试、不清控制器故障，所有运动安全门仍由控制台执行。

- 实现：`src/ares_r/demos/tcp_console.py`
- 入口：`scripts/run_demo_console_tcp.py`
- 测试：`tests/test_tcp_demo_console.py`

## 1. 启动

```bash
# 本机调试：默认监听 127.0.0.1:8790
PYTHONPATH=src .venv/bin/python scripts/run_demo_console_tcp.py

# 局域网接入：必须给共享令牌（令牌为空会拒绝启动）
export ARES_R_TCP_CONSOLE_TOKEN="$(openssl rand -hex 16)"
PYTHONPATH=src .venv/bin/python scripts/run_demo_console_tcp.py \
    --host 0.0.0.0 --port 8790 --token "$ARES_R_TCP_CONSOLE_TOKEN"
```

| 参数 / 环境变量 | 默认 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 非回环地址（如 `0.0.0.0`）**必须**配置令牌，否则直接拒绝启动 |
| `--port` | `8790` | TCP 指令端口（WebUI 仍是 `8775`） |
| `--base-url` / `ARES_R_ROUNDTRIP_API_URL` | `http://127.0.0.1:8775` | 所连接的 Demo 控制台 |
| `--token` / `ARES_R_TCP_CONSOLE_TOKEN` | 空 | 配置后**每一条**命令都要带 `"token"` |

启动成功打印一行：

```json
{"event":"LISTENING","server":"ares-r-demo-console-tcp/1","host":"127.0.0.1","port":8790,"base_url":"http://127.0.0.1:8775","token_required":false}
```

## 2. 报文格式

- 一行一条命令，UTF-8，以 `\n` 结束；一行一个 JSON 应答（NDJSON）。
- 同一个连接可连续发送多条命令；空闲 300 s 自动断开。
- 单行上限 16 KiB，超长返回 `LINE_TOO_LONG` 并关闭连接。
- `PING` / `HELP` / `STATUS` / `STOP` 可发纯文本；`RUN` / `PLAN` 必须发 JSON。
- 一旦配置了令牌，纯文本命令无法携带 `token`，因此所有命令都需改用 JSON。

## 3. 命令一览

| 命令 | 形式 | 作用 | 是否运动 |
|---|---|---|---|
| `PING` | 纯文本或 `{"cmd":"ping"}` | 连通性检查 | 否 |
| `HELP` | 纯文本或 `{"cmd":"help"}` | 返回命令列表 | 否 |
| `STATUS` | 纯文本或 `{"cmd":"status"}` | 控制台 job 状态 + demo-0 最近结论 | 否 |
| `RUN` | 仅 JSON | 启动指定 Demo（转发 `/api/demo-console/start`） | **是**（受控制台安全门约束） |
| `PLAN` / `PREPARE` | 仅 JSON | 只对 demo-0 跑 `--prepare`（cuRobo 规划） | 否 |
| `STOP` | 纯文本或 `{"cmd":"stop"}` | 控制台软件停止 | 否 |

### 3.1 `PING`

```json
{"cmd":"ping"}
```
```json
{"ok":true,"cmd":"ping","result":"PONG","server":"ares-r-demo-console-tcp/1","now_unix":1794368861.35}
```

### 3.2 `STATUS`

```json
{"cmd":"status"}
```
```json
{"ok":true,"cmd":"status",
 "console":{"state":"SUCCEEDED","alias":"demo-0-return-center","demo_id":"right_arm_return_center_v1","run_id":"…","…":"…"},
 "last_run":{"demo_id":"right_arm_return_center_v1","result":"AT_CENTER","position_mm":2.05,"…":"…"}}
```

`console.state` 取值：`IDLE` / `PREPARING` / `RUNNING` / `SUCCEEDED` / `FAULT` /
`STOPPED` / `RECOVERY_REQUIRED`。`last_run` 读取
`worklog/evidence/demo-runs/right_arm_return_center_v1/last-run.json`，不存在时为 `null`。

### 3.3 `RUN`（调用不同 Demo）

```json
{"cmd":"run",
 "demo":"demo-0",
 "authorization":"RUN demo-0-return-center",
 "onsite_observer_confirmed":true,
 "prepared_environment_confirmed":true,
 "request_id":"plc-0001"}
```
```json
{"ok":true,"cmd":"run","demo":"demo-0-return-center","job":{"state":"PREPARING","run_id":"…"}}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `demo` | 是 | Demo 别名（见下表）；`demo-0` / `demo0` / `return-center` / `right_arm_return_center_v1` 等价于 `demo-0-return-center` |
| `authorization` | 是 | 必须**精确等于** `"RUN " + 标准化后的别名`；简写会先被还原成别名 |
| `onsite_observer_confirmed` | 是 | 必须为 `true`；TCP 服务**不会代填** |
| `prepared_environment_confirmed` | 是 | 必须为 `true`；TCP 服务**不会代填** |
| `historical_recovery_acknowledged` | 条件 | `demo-2-main-graspplace`（strategy=`roundtrip`）必须为 `true` |
| `request_id` | 否 | 相同 `request_id` 的重复请求会被控制台识别并返回 `duplicate_suppressed` |
| `token` | 配置令牌时必填 | 仅用于本层鉴权，不会转发给控制台 |

**可用别名**（来自 `demos/catalog_aliases.json`）：

| `demo` 字段 | demo_id | 策略 |
|---|---|---|
| `demo-0-return-center` | `right_arm_return_center_v1` | `return_center` |
| `demo-1-main-grasphold` | `right_arm_epic_pick_lift_v1` | `first_pick` |
| `demo-2-main-graspplace` | `right_arm_grasp_place_roundtrip_v1` | `roundtrip`（需 `historical_recovery_acknowledged`） |
| `demo-2-branch-grasprptspdup` | `right_arm_pick_lift_replace_reset_v1` | `pick_reset` |
| `demo-3-branch-sift-graspreset` | `right_arm_sift_pick_lift_replace_reset_v1` | `sift_pick_reset` |
| `demo-4-main-siftgrasp-dmpplace` | `right_arm_sift_dmp_roundtrip_v1` | `sift_dmp_roundtrip` |
| `demo-5-main-dmpplace` | `right_arm_dmp_place_v1` | `dmp_place` |
| `demo-6-liaopan-placetoDMP` | `right_arm_liaopan_dmp_place_v1` | `dmp_place` |
| `demo-2-liaopan-placeto-hongganxiang` | `right_arm_liaopan_hongganxiang_place` | `dmp_place` |

示例（demo-3）：

```json
{"cmd":"run","demo":"demo-3-branch-sift-graspreset",
 "authorization":"RUN demo-3-branch-sift-graspreset",
 "onsite_observer_confirmed":true,
 "prepared_environment_confirmed":true}
```

示例（demo-2，转场取放）：

```json
{"cmd":"run","demo":"demo-2-main-graspplace",
 "authorization":"RUN demo-2-main-graspplace",
 "onsite_observer_confirmed":true,
 "prepared_environment_confirmed":true,
 "historical_recovery_acknowledged":true}
```

> 每个 Demo 的现场准备条件（站位、夹具、可见目标、速度上限、tcp3 等）仍按其
> `demo.json` / `catalog_aliases.json` 中的 `preparation` 执行；TCP 层不做这些检查，
> 但控制台的资源隔离与单任务占用照常生效（同一时刻只允许一个 Demo 运行）。

### 3.4 `PLAN`（仅 demo-0，只规划不运动）

```json
{"cmd":"plan","demo":"demo-0","timeout_s":900}
```
```json
{"ok":true,"cmd":"plan","demo":"demo-0-return-center","physical_motion":false,
 "returncode":0,"result":{"result":"PREPARED","plan_id":"…","native_duration_s":20.4,"…":"…"},
 "log_tail":"…"}
```

- 控制台 job 正在运行（`running=true`）时拒绝：`DEMO_BUSY`。
- 同一时刻只允许一个 `PLAN`，重复请求返回 `BUSY`。
- `timeout_s` 默认 900 s；超时返回 `PLAN_TIMEOUT`。
- 其它 Demo 返回 `UNSUPPORTED_DEMO`。

### 3.5 `STOP`

```json
{"cmd":"stop"}
```
```json
{"ok":true,"cmd":"stop","console":{"state":"STOPPED","stop_result":"…"}}
```

等价于控制台“停止”（`/api/demo-console/stop`），属软件停止，**不替代物理急停**。

## 4. 应答与错误码

成功应答都含 `ok:true` 与 `cmd`；失败应答形如：

```json
{"ok":false,"cmd":"run","code":"NOT_CONFIRMED","error":"onsite_observer_confirmed must be true (现场确认不能由 TCP 服务代填)"}
```

| `code` | 含义 |
|---|---|
| `BAD_REQUEST` | 空命令 / JSON 非法 / 缺少 `cmd` 或 `demo` |
| `UNKNOWN_COMMAND` | 未识别命令 |
| `UNAUTHORIZED` | 配置令牌后未提供或令牌不匹配 |
| `NOT_AUTHORIZED` | `authorization` 不等于 `RUN <别名>`（含纯文本 `RUN`） |
| `NOT_CONFIRMED` | 缺少现场确认 / 准备环境确认 |
| `UNSUPPORTED_DEMO` | `PLAN` 用在了 demo-0 以外的 Demo |
| `DEMO_BUSY` | 控制台已有任务在运行，拒绝并行 `PLAN` |
| `BUSY` | 另一个 `PLAN` 正在执行 |
| `PLAN_FAILED` / `PLAN_TIMEOUT` | `--prepare` 失败 / 超时（`error` 内含日志尾部） |
| `CONSOLE_HTTP_4xx` | 控制台拒绝（如未知别名、权限、任务占用；通常为 `CONSOLE_HTTP_409`） |
| `CONSOLE_UNAVAILABLE` | 控制台 `:8775` 未启动或连不上 |
| `LINE_TOO_LONG` | 单行超过 16 KiB |
| `INTERNAL` | 未预期异常 |

## 5. 客户端示例

Python（长连接，连续命令）：

```python
import json, socket

def call(stream, command):
    stream.write((json.dumps(command) + "\n").encode())
    stream.flush()
    return json.loads(stream.readline())

with socket.create_connection(("192.168.99.32", 8790), timeout=10) as sock:
    io = sock.makefile("rwb")
    print(call(io, {"cmd": "ping", "token": "…"}))
    print(call(io, {"cmd": "status", "token": "…"}))
    print(call(io, {"cmd": "run", "demo": "demo-0",
                    "authorization": "RUN demo-0-return-center",
                    "onsite_observer_confirmed": True,
                    "prepared_environment_confirmed": True,
                    "request_id": "plc-0001",
                    "token": "…"}))
```

命令行调试（未配置令牌时）：

```bash
printf 'PING\nSTATUS\n' | nc 127.0.0.1 8790
```

## 6. 安全约束（固定行为）

1. `RUN` 不会因为 TCP 调用而放宽任何条件：授权短语、现场确认、控制台资源
   隔离、单任务占用、`RECOVERY_REQUIRED` 不自动恢复，全部沿用控制台逻辑。
2. 服务端从不替客户端填写 `onsite_observer_confirmed` /
   `prepared_environment_confirmed`；纯文本 `RUN` 必然被拒。
3. 非回环绑定必须配置令牌；令牌只在本层校验，不写入控制台请求，也不落盘。
4. 不做自动重试；`STOP` 是软件停止，现场物理急停仍需人工可用。
