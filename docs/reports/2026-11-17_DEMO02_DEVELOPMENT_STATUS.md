# Demo02当前状态

2026-11-17，软件候选已扩展，未实机双臂运行，未交付。

已实现：独立ROS Action（Demo01字段ABI不变）、两阶段双臂编排、left/right共用场景与persistent cuRobo适配、统一80ms时序、逐同步采样的双臂互碰/环境/自碰复核、两个独立SDK原生进程、共同CLOCK_MONOTONIC放行屏障、共享故障停止锁存、父进程丢失停止、tool/scene/filehash绑定、双侧关节+TCP到位确认、Console ROS/Utility候选接线与重复请求抑制。Demo01未改。

本地8项任务合同与双native SDK替身测试通过，真实SDK头文件编译语法通过。前一版本独立ROS master的7项Action通信测试通过。新Linux native实际链接和真实场景规划尚未验证，因此执行入口仍保持不可用，delivered=false。

现场最后一轮上传和预检被网络阻断。172.28.172.210、192.168.1.112、192.168.99.32均SSH超时；Mac的ZeroTier feth4049与Wi-Fi en0到目标显示REJECT路由。上传审核最初引用昨晚仅本地准备而拒绝，附上今天返场及Demo02现场配置的最新授权重提已获允许，后续实际失败为网络超时。

剩余顺序：恢复连接→独立目录编译新native→fresh双侧scene与cuRobo planning-only→成对时序密集碰撞/动力学验证→两控制器ready但不写start gate的无运动检查→ROS测试→启用Demo Console测试入口。首次双臂真实运动后再验收，只有明确确认才加Delivered。

源码及安装/无运动检查脚本在release/ros1-demo02-dual-center-restore；本地完整候选包在site-ready-20261117/ARES-R_ROS_DEMO02_DEVELOPMENT_ONLY.zip。未push。
