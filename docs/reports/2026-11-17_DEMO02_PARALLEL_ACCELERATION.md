# Demo02 准备阶段并行加速

## 状态

本地代码完成，11项回归通过，其中新增线程屏障测试证明左右SDK读取确实重叠并在返回前join。现场部署尝试因172.28.172.210间歇超时/Host is down未成功；不声称已经获得实机提速或完整验收。

## 原始基线

任务9d03773d66a1431a847cf33b6bc22645：SCANNING=3.12s；扫描后进入规划=23.49s；实际GPU工作区开始23.49/32.67s；EXECUTE_BOTH=49.41s；下一阶段SCANNING=63.02s。前半段约63s。GPU工作区原来还包含CPU结果检查和Native打包，所以不能直接将工作区时长称为cuRobo solve time。

## 已实现

1. 双臂只读SDK采样用ThreadPoolExecutor(2)，独立控制器连接；全部完成后才检查工具/底盘状态。
2. 原有双臂规划线程保留单GPU互斥，GPU调用完成立即释放锁，CPU硬有效性检查和Native retiming/packaging移出锁；允许右侧GPU solve与左侧CPU packaging重叠，反之亦然。
3. 全阶段仍有共同barrier：双臂计划全部返回→统一时序重采样→dense互碰/环境检查→双方ready→共享开始时刻→两侧到位回读；任一失败停止两臂。
4. 每次运动完成后的下一阶段仍重新观察/扫描。只允许下一阶段非场景相关资源预热与当前执行重叠，不能提前使用旧scene生成可执行的下一段。

## 后续有界优化

下一步验证现有reuse_capture接口，在同一阶段一次新拍照生成左右scene，保留同点云SHA与前后双臂状态绑定；尚未完成现场接口核对，因此本轮未盲目调用或更改相机pipeline。GPU仍一个owner，禁止无证据复制第二个GPU planner。

## 验收方法

对相同起点、相同目标、同一环境记录capture/build/GPU等待/solve/CPU打包/pair validation/execute/arrival各阶段；至少比较一组旧版与新版完整前半段总时长，目标低于63.02s。实际速度维持当前默认请求0.20，跟踪门限保持1.5°，SLAM共享50mm/4°配置；不能靠删检查或标记一次失败为成功得到提速。Golden/Delivered均不新增，待完整ROS实机通过。

## 现场重试结果（后续补充）

并行版已备份部署并完整通过ROS实机：run a5a99dd2287341588ff2f24f1366898e，终态DUAL_CENTER_RESTORE_COMPLETED，success=true / restored=true，总计约122.6s。两段左右target_reached、servo_disabled=0、连续三次实际joint/TCP到位均核验。Console标PHYSICALLY_VERIFIED，仍Delivered=false。

前半程45.56s，原记录63.02s；本次center段打包只有0.32s保持，原基线含实际运动，因此17.46s差值不能全部归因于并行。准备到EXECUTE_BOTH由49.41s降至40.71s，但同样不是严格同起点对照。日志证实PACKAGING_LEFT=31.0620s与SOLVING_RIGHT=31.0621s重叠。第二段12.08s，左右max tracking分别0.6925°/0.7020°，均小于1.5°。

后续优化仍应优先减少每阶段约20s的双场景构建，并做同起点冷热启动对照；本次没有声称相机共享采集已经实现。
