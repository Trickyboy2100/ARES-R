# 统一 Demo Console 入口

2026-11-16 已在现场部署。

- 主页面为 `http://172.28.172.210:8765/`，Demo 区域提供 Demo Console 跳转和当前任务摘要。
- Demo Console 为 `http://172.28.172.210:8765/demo-console`，沿用现场 RC1 的目录、参数和同事调试记录。
- 主页面旧 Demo Library 选择器、旧完整流程面板注入和 A/B 回归按钮已从该页面移除。
- `8775` 作为兼容地址转发到同一 `8765` 服务，供既有客户端和 ROS Demo01 使用。
- 主 WebUI 和 canonical backend 的工作目录统一为 `/home/yikun/ARES-R-RC1-20261019`。backend 监听 `127.0.0.1:8766`，通过原 CenterRestore overlay 启动。
- 两个客户端地址返回相同的 12 项 Demo 目录，catalog SHA256 为 `938931c43e5af0e8f5a63639506d9bf382949ed7e2957ab9fd79ff7818ced8a8`。
- `/api/operations` 当前读取 RC1 revision 26，六个泊位均有偏置。两份原始注册表的文件 SHA256 经复核保持一致。

同事近期使用记录位于 RC1 的 `worklog/evidence/demo-console/`。11月13日 `fb94f185fe9f46f88626af8d1c9c9529` 的 `execute.log` 包含回 center 实机 `AT_CENTER` 结果；`b3d7819afe3249c4847fbbfe0d9bce2d` 等记录包含加速抓放 Demo 的准备失败日志。运行记录的存在用于确认实际使用来源，各 Demo 的验收状态以自身结果为准。

现场备份位于 `/home/yikun/ARES-R-RC1-20261019/worklog/preservation/2026-11-16-unified-console/`，包含原页面、自启服务文件、两份注册表和 SHA256 manifest。

现场验收结果位于 `/home/yikun/ARES-R-RC1-20261019/worklog/runtime/unified-console-deploy/verification.json`。主页面、Console、目录、任务状态、操作注册表和 backend health 均返回 HTTP 200，旧 8775 入口与新入口目录相同。JavaScript 通过 `node --check`。浏览器工具连续超时，页面视觉验收待人工刷新确认。

服务定义副本位于 `deploy/systemd/site-20261116/`。WebUI 启动探测增加 `--retry-connrefused`，支持后端冷启动等待。服务开机启动只恢复入口和历史记录。

本次整合统一了运行目录和注册表来源。部分历史放置 Demo 仍从自身 parameters 读取固定偏置，逐 Demo 改用统一泊位目标解析器仍是后续工作。
