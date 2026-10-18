# WebUI完整抓放启动入口

入口：`/` 右侧和 `/operations` 顶部。“完整抓放 Demo · 实机”提供现场确认、一次启动、停止、当前stage/计时/参数/日志。启动复用 `scripts/run_grasp_place_roundtrip.py`，不是第二套算法。

服务端在启动时校验并冻结参数、路线和泊位偏置；一次授权只批准该次隔离副本，生产参数review开关未永久打开。设备占用token仅存在本机runtime与子进程环境，不返回网页；不能用其他客户端插入物理运动。刷新、开机不会自动启动；已启动的后台进程不依赖网页保持连接。停止有锁存，不自动补走或恢复。

验证：新增5项Mock launcher测试通过；全量631 tests，OK，1 skipped。首次全量中旧native测试出现1秒快照期限时序失败，独立复核及再次全量通过；未放宽过期或碰撞保护。日志 `worklog/runtime/webstart-full-tests-20261016.log`。

现场API检查：IDLE，can_start=true，无资产blocker。`DENIED_TEST / onsite=false` 的负向启动返回409，前后running均false。浏览器确认复选框默认不勾选、启动按钮禁用；未点击有效启动，未运动机器人。WebUI版本 `2026.10.16-operations-v5-full-cycle-start`。

修改前八文件保全：`worklog/preservation/2026-10-16-web-start/before-source.tgz`；已逐文件diff确认没有覆盖同事其他dirty改动。未push。
