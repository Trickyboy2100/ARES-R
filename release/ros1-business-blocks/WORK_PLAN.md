# 本机离线实施计划（2026-11-13）

唯一主线：现有成功执行能力 → 标准ROS取放功能块。禁止另建控制器、规划器、WebUI项目或移动机器人。

|顺序|交付|本轮结果|
|---|---|---|
|1|锁定Golden、现场参数和旧ABI|保留原文件，5个参数SHA对齐，旧两种Action MD5不变|
|2|独立Pick-HOLD / Place阶段编排|新增注入式编排器与持物session，纯离线适配器验证；真实canonical适配未接通|
|3|持物会话和失败状态|SQLite持久会话；工具/物体/几何版本绑定；释放前异常变UNCERTAIN，释放后退出失败保留已释放状态|
|4|Mac单元与真实证据复核|33项新测试、17项旧测试；两段历史Native/scene/readback证据复核通过|
|5|本机VM ROS编译与通信|三个包catkin编译；新5项、旧7项ROS通信测试通过|
|6|真实canonical阶段适配及独立业务ROS闭环|尚未完成。不是等待实机的理由，仍需离线开发|
|7|现场验收|只有前项完成后再验证新ScanPick/ScanPlace；当前不开放实机Start|

下一轮只做第6项：将旧脚本的内部阶段提取为共享可调用接口，保留Golden默认行为和所有原验证，不用runpy提前退出、AST改写或杀进程截断。先Pick-HOLD，再Place，不同时扩展新工位。

本机VM没有GPU/cuda cuRobo环境，本轮不承诺新的真实GPU规划性能验证。Ubuntu仓库ROS1并非现场Ubuntu20.04/Noetic完整同构环境；部署前仍需Noetic复测。

## 2026-11-13 canonical适配增量

已定位原有独立SIFT HOLD执行器`run_sift_lift_hold.py`；此前仅检查pick-reset入口，遗漏了该入口。本轮复用它，不再重复拆写。

- 新`blocks/canonical.py`锁定源SHA，在私有导入模块上补齐到位函数的工具ID参数，原文件不变。
- `execute_place()`直接调用原`stage_place()`，独立核验release及实际退出方向/距离后，才允许调用原`stage_center()`。
- 新`run_canonical_block.py`为尚未发布的受控子进程入口；所有注册表物理Start仍为false，不能单独拿它开实机。Place入口仍拒绝缺少新鲜持物绑定的请求，P02通用HOLD入口尚未实现。
- 源模块已在VM实际导入通过；44项新Python测试和17项旧测试通过。不是只有函数名映射，但也不代表物理委派/ROS会话生命周期全部接通。

下一步剩余：正式canonical console所有权插件、真实持物绑定、ROS端跨Goal持久session与永久幂等、P02独立HOLD及完整故障回放。它们仍可离线继续；不要把本次检查点标为“离线任务全部完成”。
