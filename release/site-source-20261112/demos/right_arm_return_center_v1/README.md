# demo-0 · 右臂任意位姿 → 全局 center

`demo_id: right_arm_return_center_v1`，控制台别名 `demo-0-return-center`。

用途：右臂被手动挪动、或在其它 demo 中断后停在任意位姿时，用 **cuRobo 规划**把它送回全局
named center（`task_contract.center_goal`，与 `check_center` 同一份合同）。

## 特性

| 项 | 行为 |
|---|---|
| 起点 | **任意静止位姿**；单段关节行程需 ≤150°（见下方限制） |
| 规划 | `/api/motion/plan`，`scene_policy=FORCE_RESCAN`（每轮强制新扫描），`FAST → QUALITY` 两轮 |
| 速度 | 站点上限固定 **0.2 rad/s**（`config/jaka_mini2_motion.site.json`），启动时断言；不是 0.2 直接拒绝，不静默跑慢 |
| 工具 | 工具号/工具位姿**实时读取**并记录，不写死 `tool_id` |
| IK 分支 | 目标种子来自 `parameters.json.ik_seeds_rad`（当前两个已验收 center 分支）；运行时不放宽目标 |
| 起点干涉 | `INVALID_START_COLLISION` 时**拒绝并打印穿透对象与深度**，不做任何运动 |
| 计划时效 | 规划后**当次派发**（计划 300 s 过期，绝不复用旧 plan） |
| 到位判定 | `center` 合同：位置 ≤ 3 mm、姿态 ≤ 3°（`parameters.json.arrival_tolerance`） |
| 已在该点 | 起点已在容差内 → 直接报 `ALREADY_AT_CENTER`，不规划不运动 |

## 用法

```bash
cd /home/yikun/ARES-R-RC1-20261019

# 只规划（默认，不运动）：打印 plan、时长、峰值速度、预测跟踪、计划终点 FK 校验
PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --prepare

# 实机：当次规划 + 当次派发 + 到位复核
PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --execute \
    --authorization 'RIGHT RETURN CENTER' --onsite-observer-confirmed

# 软件停止（不替代物理急停）
PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --stop
```

控制台：`http://192.168.99.32:8775/demo-console` → 选 `demo-0-return-center` →
授权短语 `RUN demo-0-return-center` → 运行。

## TCP 指令端口（外部程序接入）

外部程序（PLC/上位机/脚本）可通过 `scripts/run_demo_console_tcp.py` 接入同一个
demo 控制台，**不绕过**任何既有安全门：

```bash
# 与控制台 8775 同机运行；默认监听 127.0.0.1:8790
PYTHONPATH=src .venv/bin/python scripts/run_demo_console_tcp.py

# 需要局域网接入时必须给共享令牌（否则拒绝非回环绑定）
PYTHONPATH=src .venv/bin/python scripts/run_demo_console_tcp.py \
    --host 0.0.0.0 --port 8790 --token "$ARES_R_TCP_CONSOLE_TOKEN"
```

协议：一行一条命令，一行一个 JSON 应答（NDJSON）；同一连接可连续发送。

```jsonc
{"cmd":"ping"}
{"cmd":"status"}                     // 控制台 job + 最近一次 demo0 结论(last-run.json)
{"cmd":"run","demo":"demo-0",        // demo0 / demo-0-return-center 等简写均可
 "authorization":"RUN demo-0-return-center",
 "onsite_observer_confirmed":true,   // 必须由客户端显式给出，TCP 服务不会代填
 "prepared_environment_confirmed":true,
 "request_id":"plc-0001"}
{"cmd":"plan","demo":"demo-0"}       // 只读：跑 --prepare（cuRobo 规划，不运动）
{"cmd":"stop"}                       // 等价控制台“停止”（软件停止）
```

- `RUN` 只接受 JSON：本地先校验授权短语与两项现场确认，再转
  `POST /api/demo-console/start`；缺少/错误直接拒绝，不产生任何运动。
- `PLAN` 在控制台空闲时执行 `run_return_center_demo.py --prepare`，返回脚本最后
  一行 JSON；不会派发。
- 纯文本 `PING` / `HELP` / `STATUS` / `STOP` 可直接用 `nc` 调试；配置令牌后所有
  命令都需在 JSON 里带 `"token":"…"`。
- 复用控制台的资源隔离、单任务占用、planner 归属校验和 `last-run.json` 证据；
  TCP 层不自行规划、不自动重试、不清理控制器故障。
- 完整协议（命令、字段、错误码、其它 Demo 别名）：`docs/DEMO_TCP_COMMAND_PROTOCOL.md`。

## 授权与安全

1. 实机必须 `--execute` **且** `--onsite-observer-confirmed`（控制台侧为勾选现场确认）；
2. 每个输出目录只允许派发一次（`dispatched-once.json` 在派发**之前**落地，状态 `UNCERTAIN`）；
3. 控制器 `errcode` / 保护停 / 拖拽 / 软限位任一非零即拒绝；
4. 底盘必须静止（`base_stationarity`）；
5. 不动夹具、不夹取、不清任何控制器错误、不自动重试。

## 证据

每次运行写入 `worklog/evidence/demo-runs/right_arm_return_center_v1/run_<ns>/`：

```
script.json                本次参数
center-goal.json           center 合同（取自 config/named_poses.json）
site-ceiling.json          站点上限断言结果
run-status-before.json / telemetry-before.json / base-stationarity.json
start-error.json           起点与 center 的差（mm / deg）
attempt1.json …            每次规划尝试（模式、耗时、错误、起点碰撞明细）
plan_handle.json / plans.json
native-audit.json          原生包上限、时长、采样、峰值速度、预测跟踪
planned-endpoint.json      计划终点 FK 校验（应为 center，≤3 mm）
telemetry-dispatch.json / execute-request.json / execute-response.json
run-status.json / telemetry-after.json / center-check.json
result.json                最终结论（PREPARED / AT_CENTER / ALREADY_AT_CENTER / CENTER_NOT_CONFIRMED）
```

另在 `.../right_arm_return_center_v1/last-run.json` 保留最近一次结论，供控制台校验。

## 已知限制

- **单段关节行程上限 150°**：自由空间打包（`package_native_preview`）默认按
  `NATIVE_MAX_EXCURSION_RAD = 150°` 拒绝，而发送器本身允许 220°。若起点到 center 某个
  关节需要超过 150°，本轮会被拒绝，并打印逐关节行程（`excursion-report.json`）：

  ```
  {"reason":"NATIVE_EXCURSION_CAP", "joints":[{"joint":"joint1","travel_deg":160.54,"over_limit":true}, …]}
  ```

  处理方式：手动把超限关节转回 20–30°（或用 JAKA app 点动）后重跑；或把这一步拆成两段受监督运动。
- 不做持物碰撞建模：手里有东西时路径只按空爪验证，**必须由现场确认路径净空**。
- 起点与夹具干涉时只能人工挪开（脚本会给出穿透对象与毫米数），这是设计上的 fail-closed。
- `demo-0` 只是"回 center"的工具，不代表任何取放流程已验收。
