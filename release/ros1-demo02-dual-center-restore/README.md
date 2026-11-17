# ROS Demo02 · 双臂center往返

2026-11-17完整ROS实机通过：`DUAL_CENTER_RESTORE_COMPLETED`，总计约122.6s，run `a5a99dd2287341588ff2f24f1366898e`。两臂两段joint/TCP到位及servo关闭均核验。标签ROS / Utility，**Delivered=false**，等待确认。

Action `/ares_r/dual_center_restore`，包 `ares_r_dual_center_restore`；字段与Demo01相同，独立接口。`CAPTURE_START`保存当前双臂起点，`SAVED_POSE_REF`使用已绑定的双臂命名目标。

每阶段fresh状态/scene → 左右规划线程（共享单GPU）→ GPU求解与另一侧CPU打包重叠 → 双臂同步路径验证 → 双Native共同放行 → 双臂连续到位回读。失败停止双方，不自动重启。底盘不移动。SLAM容差统一读config/slam_localization_policy.json，现场50mm/4°；运动请求0.20rad/s，受现场、Native及tracking限速，tracking门限1.5°。

本地11项测试通过。前半程本次45.56s，但center已基本到位（保持0.32s），不能把与历史63.02s的全部差值归因于线程。相机重复构建尚待优化。

现场Console提供“复位任务故障”，核实执行器停止与控制器健康后释放任务占用，不自动续跑，也不伪装清除控制器物理故障。
