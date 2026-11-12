# Mac与本机VM：ROS取放功能块离线进展

## 范围与保全

全程未连接机器人服务器、未调用硬件接口、未修改Golden、生产参数或旧ROS Action。工作目录为现有独立分支codex/ros1-business-blocks-offline-20261113，未包含原Quickstart未提交修改与DS_Store。

计划、代码、证据统一放在release/ros1-business-blocks/。本轮不部署现场，不开放物理执行。

## 实现

- `blocks/runner.py`：注入式ScanPick/ScanPlace阶段编排。Pick在夹持前后验证和抬升完成后建立持物会话并结束，没有放回/松爪/center。Place必须先验证已有session，再扫描、预放置、下降、确认释放、退出，之后才可选center。
- SQLite持物会话保存物体类型、工具revision、几何revision、来源证据。跨进程重新打开后可读取；版本不匹配或状态不明拒绝Place。释放失败不detach、不退出/回center；释放已确认但退出失败保持RELEASED_CONFIRMED，不能重复放置。
- 两秒证据窗口用于离线适配器合同测试，并不是已commissioned的设备反馈时限。历史回放不把旧时间戳刷新为当前可执行证据。
- ROS节点增加显式OFFLINE回放适配器，默认仍拒绝物理执行；任务反馈、取消、BUSY与合成验证失败可经真实ROS Action收发。
- 原17项Python测试通过；新增33项Python测试通过。新测试中的阶段适配器没有SDK、socket或Native调用。

## VM验证

本机Parallels Ubuntu Linux 22.04，x86_64，独立目录`/root/ares-offline-20261113/`，工作空间`ws/`。

原VM没有ROS。Docker已安装，但Docker Hub访问超时；改用Ubuntu仓库ros-core-dev/python3-actionlib/libactionlib-dev/python3-rostest进行catkin构建。不混称现场Noetic环境，不代表现场二进制依赖已经验证。

三个包构建通过：ares_r_demo_bridge、ares_r_center_restore、ares_r_manipulation_blocks。

|Action|MD5|结果|
|---|---|---|
|ReturnCenterAction|842cf52f466bc1a27e437671197f32b6|原ABI未变|
|CenterRestoreAction|604285c770a2394b3024a6fb532f8380|原ABI未变|
|RunBlockAction|7b4edfbf807f9526b57393193f680fd1|新离线接口|

ROS Master限定127.0.0.1:12321；测试结束清理该Master，未接入现场ROS网络。

新5项实际ROS通信：物理Goal默认拒绝、Pick-HOLD合成成功、抬升后验证失败、额外Goal BUSY不抢占、取消后停止结果。旧Demo01 7项：缺确认拒绝、成功、center失败、恢复段失败、取消、Start回执丢失变UNCERTAIN、额外Goal BUSY。没有任何实物运动。

原始构建与测试日志：release/ros1-business-blocks/evidence/。消息MD5及日志SHA见该目录VALIDATION.json。

另对真实历史run c7d9107f7bbc48ceace753eb8e202054做Mac只读复核：center 15样本、restore149样本，均有到位/Servo退出/连续反馈。它是历史Demo01证据，不能算新增取放实机验收。

## 尚未完成，下一轮仍可离线继续

1. 新编排器尚未绑定旧脚本内部的真实阶段。现有run_task_pick_reset_timing.py把准备、执行、抬升后放回耦合在main闭包中，需要提取共享接口；不能通过提前杀脚本或动态改写源码实现HOLD。
2. Place真实执行函数stage_place已定位；其PLACED_AND_RELEASED并不保证RETREAT_CLEAR，因为退出配置可关闭。新适配器必须读取release.json、retreat-check.json及真实MoveL到位证据，不能只看返回字符串。
3. ROS节点仍是离线预览，不具备canonical job绑定、持久session交接、生产幂等及进程恢复。Python层事务测试不等同ROS端已实现这些能力。
4. 没有新增真实点云/cuRobo/IK规划测试；VM未安装GPU运行环境。现场Noetic复测、真实ScanPick/ScanPlace和跨业务机通信尚待完成。

不能声称“离线工作全部完成”或“已有新增可交付实机取放块”。本次完成的是阶段编排、持物状态和ROS传输层的明确增量；下一步只做canonical真实阶段适配。
