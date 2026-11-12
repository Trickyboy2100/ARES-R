# ARES-R 文档入口

- [甲方nodeapp参考工程与ROS封装对接说明](integration/2026-11-12_CLIENT_NODEAPP_ROS_INTEGRATION_REFERENCE.md)：任务动作、旧ROS服务桥和ARES-R Action的关系。

- [常用操作与离线开发cheatsheet](CHEATSHEET_OFFLINE.md)：ROS回center、状态、取消、环境与离线测试。
- [现场代码与本地差异、归档清单](reports/2026-11-12_OFFLINE_HANDOFF.md)：哪些内容已保存、哪些仍缺。
- [ROS1节点使用说明](../ros1/ares_r_demo_bridge/README.md)：运行参数、反馈、结果与模拟测试。
- [ROS首个功能块报告](reports/2026-11-12_ROS1_RETURN_CENTER_FIRST_BLOCK.md)：首轮到位误报及修复。
- [2026-11-12现场RC1完整源码快照](../release/site-source-20261112/OFFLINE_SNAPSHOT_README.md)：现场703份文件，保留原结构及SHA256。
- [分臂姿态注册表](../config/arm_pose_registry.json)：right/center兼容旧center；轴对正姿态快照。

历史内容按原目录保留：`docs/reports/`报告，`docs/work_orders/`工作单，`docs/architecture/`架构，`docs/decisions/`决策，`docs/roadmaps/`路线。最新现场接口文档位于独立快照的`docs/`，不要把历史分支说明直接视为现场当前状态。

- [功能块01 CenterRestore API](integration/2026-11-12_CENTER_RESTORE_API_CONTRACT.md)
- [双腿实机验收与交接报告](reports/2026-11-12_ONSITE_CENTER_RESTORE_AND_HANDOFF.md)
- [ROS离场资产索引](integration/2026-11-12_ROS1_DELIVERY_ASSET_INDEX.md)
