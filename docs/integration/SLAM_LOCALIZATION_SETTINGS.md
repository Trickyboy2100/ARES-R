# 全局 SLAM 定位漂移容差

WebUI 主页面 → 场景设置 · SLAM定位 → 全局 yaw 漂移容差（°）→ 保存全局设置。yaw默认4°，平移默认50mm。平移按XY平面欧氏距离判断。

权威文件：config/slam_localization_policy.json；统一读取接口 ares_r.motion.slam_policy。GET/POST /api/scene/slam-settings。配置版本随保存更新，场景失效；运行中Console任务禁止修改。Demo02在准备时绑定配置哈希，修改后不能继续使用旧候选。

已接入：Demo02执行时底盘yaw监控、完整取放底盘停稳判断、通用BaseMotionObserver停稳yaw判断、取放恢复遥测yaw绑定、烘干机角点观测前后yaw绑定。导航目标角度的到站精度及检测真实旋转开始的门限保持各自语义，不使用SLAM漂移容差代替。历史证据与成功归档不重写。

平移与yaw统一来自同一份全局配置：translation_tolerance_m=0.05，yaw_tolerance_deg=4。WebUI平移输入单位mm，后端存储单位m。控制器、跟踪、底盘任务状态与map/task变化检查保留。

2026-11-17已部署，真实HTTP读取4.0及保存4.0通过；本地配置读写/非法数值/部分保存保留另一字段三项测试通过；Demo02十项回归通过。设置验证不等于完整Demo02实机验收。
