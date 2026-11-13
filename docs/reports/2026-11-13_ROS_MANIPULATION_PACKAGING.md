# 2026-11-13 ROS取放功能块封装

本轮在独立候选目录完成封装和无运动验证。现场目录为 `/home/yikun/ARES-R-ROS-BUSINESS-20261113`，实际执行器仍引用 `/home/yikun/ARES-R-RC1-20261019` 的已核对版本。

## 已完成

- 新 RunBlock Action 委派到 canonical 同一任务所有者，提供反馈、结果、请求去重与按run_id取消。
- P01筛网使用原HOLD执行器；P02料盘以哈希锁定补丁增加持物结束选项，保留默认完整原位放回流程。
- L01/L02/L03复用Place函数，加入持物几何、实际释放与退出核验，再回center。
- 持物会话持久化，记录执行中、确认持物、确认释放与不确定状态；放置前复核当前工具定义、夹爪读数和原持物几何。
- 11项能力均登记，5项现有参数绑定，5个缺失工位提供参数模板，U01沿用原接口。
- 客户端源码包包含catkin定义、Action/Service、客户端和简短README，共10个文件，9个内容文件SHA逐一核验。

## 验证结果

现场Ubuntu20.04/Noetic构建通过。76项Python测试通过；隔离ROS Master 12431下14项通信测试通过，包括ROS→模拟HTTP canonical调用。Mac另完成原Demo01的17项回归。实际5份现场参数SHA全部匹配。原CenterRestoreAction MD5保持604285c770a2394b3024a6fb532f8380。

本轮使用模拟执行边界验证新接口，未扫描、未执行机械臂/夹爪/底盘运动。原ares-ros.service仍active。新节点未挂入生产自启动。

## 现场待办

新取放块尚未取得实机验收记录，physical_start_enabled保持false。先选择P01或P02进行一次静止准备与有监督独立HOLD验收，再以实际持物session验收对应Place。P03/P04/P05及L04/L05需要真实工位配置。新代码已具备统一接口与执行适配，未绑定工位会明确返回PROFILE_NOT_BOUND。

旧源快照、Golden与原ROS接口均保留。此次仅在独立候选目录部署新封装。
