# 服务入口与 Epic 远程访问

## Epic Pro

ZeroTier 网页入口为 `http://172.28.172.210:5050/`。相机局域网入口为 `http://192.168.99.199:5050/`。

机器人主机通过用户级 `ares-epic-web.socket` 和 `ares-epic-web.service` 转发 TCP 字节流，包含 HTTP 与 WebSocket。监听地址限定为机器人 ZeroTier 地址。上游固定为相机 `192.168.99.199:5050`。机器人主机的用户 linger 已启用，socket 随用户服务管理器启动，FreeBind 支持 ZeroTier 地址稍后出现。

部署文件位于 `deploy/systemd/ares-epic-web.*`，现场安装位置为 `/home/yikun/.config/systemd/user/`。只启用 socket，service 在收到连接后启动。

5700 通信服务继续由 Epic Pro 网页手动启动。网页转发与相机检测端口分别管理。

2026-11-16 已在现场部署并启用 socket，Mac 经 ZeroTier 验证 HTTP 200、Blazor negotiate 成功、WebSocket 返回 101 Switching Protocols。现场说明副本位于 `/home/yikun/ARES-R-RC1-20261019/docs/2026-11-16_SERVICE_AND_EPIC_REMOTE_ACCESS.md`。

## ROS

上层业务作为 ROS Action client 调用机器人端 Action server。机器人端仍需运行一个接收请求、转发任务并返回反馈和结果的节点。现有 `ares-ros.service` 已管理 Demo01 ROS Master 与 `ares_r_center_restore` 节点。后续功能块可在同一 Master 注册各自的 Action server。

当前 Demo01 launch 的 `base_url` 为 `http://127.0.0.1:8775`，依赖 RC1 Demo 控制台。2026-11-16 检查发现 ROS 11321 未监听，启动日志存在地址占用及 run_id 冲突。现有 8765/8766 服务正常，8775/8776 未监听，ROS 调用完整链尚需恢复和验证。

## RC1

RC1 表示 release candidate。现场 `/home/yikun/ARES-R-RC1-20261019` 是 2026-10-19 建立的独立部署副本，后续多个已验证 Demo 使用其中的源码、配置、执行脚本和证据目录。它已经成为部分成功链路的实际运行依赖。ROS Demo01 overlay 位于 `/home/yikun/ARES-R-ROS-BLOCK01-20261112/`。

## Legacy TCP Demo

2026-11-16 起，`scripts/run_demo_console_tcp.py`、`src/ares_r/demos/tcp_console.py` 和 `docs/DEMO_TCP_COMMAND_PROTOCOL.md` 归为 legacy。旧端口为 8790。

现场检查未发现 TCP Demo 的系统级或用户级 systemd 自启项、检查范围内的 cron/登录启动引用及运行进程，8790 未监听。历史源码和协议保留用于追溯。业务调用使用 ROS 接口。
