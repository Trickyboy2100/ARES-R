# 右臂回 center：TCP 启动接口

功能：从右臂当前静止位姿重新扫描、cuRobo规划并执行到全局 center 位姿。

## 连接

- 协议：TCP，UTF-8，逐行 JSON（NDJSON）。
- 地址：局域网 `192.168.99.32:8790`；ZeroTier `172.28.172.210:8790`。
- 每条请求以换行符 `\n` 结束；响应为一行 JSON。
- 鉴权：`token` 填入接口管理员提供的共享令牌。

## 启动请求

```json
{"cmd":"run","demo":"demo-0-return-center","authorization":"RUN demo-0-return-center","onsite_observer_confirmed":true,"prepared_environment_confirmed":true,"request_id":"return-center-001","token":"<共享令牌>"}
```

| 字段 | 说明 |
|---|---|
| `cmd` | 固定为 `run` |
| `demo` | 固定为 `demo-0-return-center` |
| `authorization` | 固定为 `RUN demo-0-return-center` |
| `onsite_observer_confirmed` | 现场持续观察已确认，必须为 `true` |
| `prepared_environment_confirmed` | 右臂及底盘静止、路径净空、控制器正常等准备条件已确认，必须为 `true` |
| `request_id` | 每次独立启动使用唯一值；同一次请求重发沿用原值，用于抑制重复启动 |
| `token` | 共享令牌 |

## 启动应答

```json
{"ok":true,"cmd":"run","demo":"demo-0-return-center","job":{"state":"PREPARING","run_id":"<任务ID>"}}
```

`ok=true` 表示启动请求已受理，不代表机器人已经到达 center。任务由后端自动推进，无需继续发送运动指令。

失败应答包含 `ok=false`、`code` 和 `error`：`UNAUTHORIZED` 为令牌错误；`NOT_AUTHORIZED` / `NOT_CONFIRMED` 为请求字段不满足；`CONSOLE_HTTP_409` 为后端拒绝（如已有任务占用）；`CONSOLE_UNAVAILABLE` 为后端不可用。
