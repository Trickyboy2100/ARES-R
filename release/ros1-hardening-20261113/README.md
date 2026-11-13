# ROS Demo01 现场鲁棒性修复

2026-11-13 通过原 `/ares_r/center_restore` Action 实机验证成功，run_id 为 `9e532cd1cd0c4e6fbf48222800eca882`，返回 `CENTER_RESTORE_COMPLETED`，客户端耗时约51.2秒。

本次第一阶段已处于center，连续回读确认后跳过运动；第二阶段fresh扫描、cuRobo规划、Native执行、关节及TCP到位确认通过。保存目标工具为tcp3，最终最大关节误差约0.00001度。此前从其他位姿返回center的独立运动也已成功。

## 修复

- 保存目标在site软限位内选择最接近实际关节的2π等价分支，原目标记录及SHA保持原值。轨迹按所选分支重新规划、碰撞检查和实际到位核验。J4从约319度绕转缩短到约41度，J6从232度缩短到128度。
- 共用Native打包器读取site配置 `native_max_excursion_deg`，默认仍为150，现场显式设为220，受现有Native最大220度及关节/速度/加速度/跟踪等检查约束。
- 空残余点云的support检测返回空列表，继续输出已知几何和场景报告。原始采集失败不适用此处理。空残余测试通过。
- ROS runner保留每次plan_handle的execution_package_error，最终错误包含具体尝试，减少笼统规划失败回报。
- 先前已修复停止确认中controller_status为null的异常，并通过真实失败任务验证停止确认与任务锁释放。

补丁从现场修复前文件生成，应用前需要核对版本。完整before/after源码、参数、哈希及实机反馈在Mac私有归档 `/Users/andyee/Documents/ChatGPT/local/ares-ros-hardening-20261113.tar.gz`，SHA256为 `314219ce2d361b7560a23e3ff20812a1a39859df7882ee3406bce36df7ddcb03`。现场证据位于 `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/ros-hardening-20261113/`。

共用点云与打包修复可服务后续模块。新功能块仍需核验本工位参数及完整实机结果。本次修复未覆盖控制器故障恢复和所有网络中断情形。
