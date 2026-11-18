# 功能控制台现场部署

2026-11-18，使用 `192.168.99.32` 直连，部署到 `/home/yikun/ARES-R-RC1-20261019`。本地基线为 `02e20f5`，现场原有两处复位提示文字合并保留。

## 已部署

- 默认大tile功能墙，30项包括20项取放、5项Utility、3项测试分支、2项完整流程。
- A/R编号、工位、对象、动作链、原生实机和ROS交付状态、阶段里程碑。
- 交付/开发模式，原生/ROS调用选择，开发草稿保存与导出。
- 取、放、Utility、完整流程、测试分支及工位/编号筛选。
- 保留运行监控与三维、资源曲线、事件、计时，原生启动成功后切换监控。
- 十章节功能手册与明日逐项调试清单。

ROS网页Action桥接仍为PENDING。选择ROS时展示已知Action、编号和状态；网页启动保持不可用。已有ROS客户端继续按原Action使用。

## 验证

部署前任务为SUCCEEDED、running=false。已备份所有被替换文件，逐文件核验上传包SHA256。WebUI重载后五条页面/资源/目录路由与现场文件逐字节一致，目录30项。

部署前后canonical backend PID均为1302，实际执行catalog相同。本次未派发机器人动作。

本地6项功能墙、8项手册、4项WebUI回归通过；昨晚另有3项部署包测试及桌面/窄屏浏览器验证。Mac直连页面HTTP 200，31344字节。现场无头浏览器在直连与临时转发下均未完成DOM输出，视觉验收待普通浏览器刷新确认；昨晚本地桌面/窄屏完整交互已通过。临时验收浏览器与转发已关闭。

## 路径

- 控制台 `http://192.168.99.32:8765/demo-console`。
- 手册 `http://192.168.99.32:8765/demo-handbook`。
- 备用地址 `172.28.172.210`，仅在首选连接失败时使用。
- 备份 `worklog/preservation/2026-11-18-capability-wall-1794964776113087665`。
- 现场校验 `worklog/runtime/capability-wall-deploy-20261118/verification.json`。
- Git证据 `worklog/evidence/2026-11-18-capability-wall-deploy/`。

## 后续工作

按 `docs/work_orders/2026-11-18_FUNCTION_CONSOLE_COMMISSIONING.md` 核对具体功能，优先原生成功基线的结果与ROS薄封装。功能墙部署本身不构成新功能的实机验收。
