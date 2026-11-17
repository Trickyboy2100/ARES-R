# Demo02 .20rad/s 重测

任务 f4daf8eafc70431591038b75d203890b。Demo02独立版本配置设速度/加速度 .20/.20，保持tracking 1.5°，不影响其他demo。10项本地测试通过。

扫描阶段约22.98s；扫描完成到双臂执行约39.90s，包含串行GPU求解、打包、双臂dense验证和执行前检查，尚不能把这39.90s全部归因于cuRobo。开始执行时累计66.02s。第一段打包10.48s；实际约5.81s右臂tracking error中断，左臂响应共享停止。两侧abort及servo_disabled均为0。完整往返未通过，不能标记Golden/Delivered或双臂速度commissioned。

修正上层STOP_REQUESTED掩盖native真实故障；新增首个故障归因、WAITING_PLANNER/SOLVING区分。最新错误显示修正尚未部署。

上一轮51ea43d34caf474b854b2ecb82debfaa完成center后因BASE_POSE_CHANGED_DURING_DUAL_EXECUTION中断；静止采样XY变化约12.6mm，仍需区分SLAM漂移与真实运动，不自动移除检查。

后续：分解capture/solve/pack/dense验证时长；从此次tracking日志测算可行速度并重新验收双臂，不把既往右臂单条轨迹的.20验证等同于任意双臂路径认证。
