# Demo01 Turbo 实机测试记录

ROS结果：`CENTER_RESTORE_COMPLETED`。Run `c313343191bd4b4db8b9011abc6daffe`。总用时 **48.359s**。

起点已在center容差内，center段连续三次回读后跳过运动；真正执行一段center→保存的右前高位。不能将本次记成完整往返，也不能与130秒两段运动直接比较。当前最终保持右前高位，底盘和左臂未发送运动。

|阶段|实测秒数|
|---|---:|
|启动、最初预检及未归属开销（差额）|5.848|
|center绑定、状态检查|4.423|
|center三次到位回读|2.345|
|右前高位准备：状态、fresh scan、scene、规划、打包|20.869|
|派发、实际运动、完成监控与最终回读|14.874|
|总计|48.359|

上述阶段基于事件墙钟边界，总计采用ROS任务monotonic计时。以下均为上表内部子项，不可再相加：

- motion/plan HTTP：16.460s。
- worker：7.154s；实际cuRobo planning_samples 3.594s。
- runtime未复用；CUDA import 0.673s、planner初始化 0.785s。
- independent NumPy dense validation 1.710s。
- native实际运动 9.604s，文件轨迹时长8.160s。
- 到位误差0.0316mm / 0.01175°，最大tracking 0.6161°。
- 实际峰值速度0.19896rad/s、加速度0.19959rad/s²。
- 最终BODY TCP XYZ：[0.437165, -0.383236, 1.607324]m。

## 实际启用范围

独立Turbo ROS节点，FAST单次请求、现有persistent planner服务、原有fresh scene/到位验证和ARC_LENGTH_EXACT_V1时标。初始50 iterations、4 IK/2 trajopt seeds、CUDA graph启用。本次实际independent validator仍为NUMPY_REFERENCE。离线预览已验证的Native CPU validator及跨任务预测准备未接入生产服务，不能把预览10.19秒准备时间宣传成本次实测。

共享源码替换/生产后端重启的部署方案被自动审批拒绝，未执行。改用独立ROS测试节点和既有canonical API；原Demo01、原ROS服务和全局配置未更改。此次仅证明这个独立测试入口成功运行，不能据单次结果宣称比48.71秒同起点历史测试显著提速。下一步应针对约20.87秒准备和重复状态绑定，而非再次提高运动速度。

## 证据

- 站点任务目录：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/demo01-turbo-physical/c313343191bd4b4db8b9011abc6daffe`。
- 规划：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/scene-aware-motion/PLAN_c1d6923935d745c4b9c84da2ca12b4ea`。
- Native feedback：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/operations-execution/1794560777221543027/live/native_supervised.jsonl`。
- Mac私有副本：`/Users/andyee/Documents/ChatGPT/local/site-private-demo01-turbo-20261113`，附SHA256SUMS.json。
- Git内摘要：`worklog/evidence/2026-11-13-demo01-turbo-physical/`。
- 轨迹hash：`sha256:1c216b78ff7aded452b3bd962cdb20a27f17120292a90e740183e2a65bb18ffe`。

本轮测试：Turbo instrumentation 2/2、原core 11/11；实机ROS一次成功。未自动push。
