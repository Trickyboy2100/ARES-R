# 现场 ROS 交付基线

2026-11-13 用户转述接收端已认可原 ROS 源码包，业务端 ROS 测试通过。该反馈记录为接收端验收信息。

现场只读核对确认以下服务均为 enabled / active。

- `ares-r-gateway.service` 负责机器人局域网路由，入口为 `/usr/local/sbin/ares-r-gateway`。
- `ares-ros.service` 启动 `/home/yikun/ares-11321-autostart.sh`，使用原 Demo01 工作空间和 `ares_r_center_restore center_restore.launch`。
- ROS Master 为 `http://192.168.99.32:11321`，ROS_IP 为 `192.168.99.32`。
- 自启动脚本包含 roscore 与 Demo01 ROS 节点。RC1 canonical/backend、planner、WebUI 由独立启动链提供，本次已恢复。

新功能块沿用现有 ROS Master 和原交付包的接口形式。原 CenterRestoreAction MD5 为 `604285c770a2394b3024a6fb532f8380`，本次现场编译核对一致。

新候选目录为 `/home/yikun/ARES-R-ROS-BUSINESS-20261113`。其中三个 ROS 包在现场 Noetic 编译通过，65 项纯离线 Python 测试通过。新 RunBlockAction MD5 为 `7b4edfbf807f9526b57393193f680fd1`。候选 ROS 节点与取放任务尚未启动，现有自启动服务保持原配置。
