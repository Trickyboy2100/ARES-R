# L04 称上筛网放置封装核对

成功运行编号为 `049b636585df431ea42f83975dbabfc6`，Demo为 `right_arm_shaiwang_cheng_place_v1`，结果为 `PLACE_CENTER_COMPLETE`。总耗时94.85秒，其中准备5.96秒、规划28.11秒、执行60.78秒。

证据确认下降100mm、松爪目标400实际399、BODY X−退出约40.01mm、回center位置误差2.022mm和姿态误差0.0161°。当前参数版本为 `SHAIWANG_CHENG_PLACE_2026_11_13_V3_ID8_Z100_D100_CENTER_IKSEED`，5700使用ID8。

原L04尚未绑定参数，本轮已补齐。公共放置适配器的对象类型也已修正，L04使用sieve持物会话。参数与当前执行脚本按SHA绑定，仍复用stage_place与stage_center。旧入口与现场运行服务保持原状态。

91项Python测试通过，包含真实释放/退出/回center证据回放、L04参数解析与筛网对象类型回归。本次没有重新运动。

本次WebUI成功可以作为相同执行链的物理验收依据。封装层的ROS实际派发尚未验证，不能将这次WebUI日志记为ROS实机调用成功。新适配位于候选库，生产发布仍待统一接入时间。

原运行未冻结源码及参数SHA。本轮记录的是当前文件SHA，已核对两文件修改时间均早于本次成功运行，运行记录中的参数路径和CLI覆盖项亦一致。

代码及证据位于 `release/ros1-business-blocks/site-20261113-L04/`。
