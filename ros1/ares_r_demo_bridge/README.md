# ARES-R ROS1 回center节点 v0.2.0

## 功能与边界

ROS Noetic Action `/ares_r/return_center`，类型 `ares_r_demo_bridge/ReturnCenterAction`。
节点通过现有HTTP8775的Demo控制台启动 `demo-0-return-center`，与ART/WebUI/TCP共用同一任务占用与执行后端。不会自行实现规划或直接连接JAKA。节点启动不运动，不自动重试运动请求。

Goal：`request_id`、`onsite_observer_confirmed`、`prepared_environment_confirmed`。
Feedback：`state`、`stage`、`run_id`、单调时钟累计`elapsed_s`。
Result：`success`、`code`、`message`、`run_id`。

本版只封装回center，不开放目标/速度参数；center和物理速度沿用后端原配置。

## 当前部署

源码：`/home/yikun/ARES-R-RC1-20261019/ros1/ares_r_demo_bridge/`
工作空间：`/home/yikun/ARES-R-RC1-20261019/worklog/runtime/ros1_return_center_ws/`
测试与服务日志：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/2026-11-12-ros1-return-center/`

本次手动启动隔离ROS master `127.0.0.1:11321` 和回center节点。未使用11311，不修改现有ROS工程，不配置开机自启。
所有下面命令在服务器SSH终端中执行。Mac不用安装ROS。

## 1. 进入服务器并加载环境

```bash
ssh yikun@172.28.172.210
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-RC1-20261019/worklog/runtime/ros1_return_center_ws/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321
export ROS_IP=127.0.0.1
```

每个新SSH终端均需加载上述环境。

## 2. 检查节点（不运动）

```bash
rosnode list
rostopic list | grep /ares_r/return_center
rosmsg show ares_r_demo_bridge/ReturnCenterAction
```

应看到 `/ares_r_return_center` 以及 `/goal`、`/feedback`、`/result`、`/cancel`、`/status`等Action话题。

## 3. 不运动测试

```bash
rosrun ares_r_demo_bridge return_center_client.py
```

预期：`success: False`、`code: NOT_CONFIRMED`、`run_id: ''`。这验证ROS调用链和确认字段拒绝，不启动扫描/规划/运动，不代表完成真实运动验收。

## 4. 实机回center

确认现场准备、工作区净空且有持续观察和物理急停后执行：

```bash
rosrun ares_r_demo_bridge return_center_client.py --execute
```

客户端自动生成唯一request_id，发送两项现场确认，输出阶段/累计耗时/run_id，等待最终结果。`SUCCEEDED`并且`success: True`才代表后端成功；收到目标不是运动成功。

指定请求ID：

```bash
rosrun ares_r_demo_bridge return_center_client.py --execute --request-id ros-center-001
```

每次独立任务使用新ID；同一网络请求重发沿用原ID。启动超时后不要盲目新建ID重发，先查WebUI/后端任务是否已经启动。

## 5. 实时查看与取消

另开SSH终端并加载第1节环境：

```bash
rostopic echo /ares_r/return_center/feedback
```

客户端Ctrl+C会发送取消请求。也可从另一个同环境终端取消该Action：

```bash
rostopic pub -1 /ares_r/return_center/cancel actionlib_msgs/GoalID '{}'
```

桥接仅在后端run_id与本次任务一致时转发软件stop，并等待STOPPED；取消失败会返回错误，不能当作已经停止。软件停止不替代物理急停。直接杀节点或SSH断开不会保证后端停止，应先取消并检查后端状态。

## 6. 机器重启或手动服务退出后如何启动

先确认HTTP8775后端已启动。需要重新启动ROS时，三个终端分别执行；不要在服务已运行时重复启动。

终端A：

```bash
source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321
export ROS_IP=127.0.0.1
roscore -p 11321
```

终端B：加载第1节环境后执行：

```bash
roslaunch ares_r_demo_bridge return_center.launch
```

终端C：加载第1节环境，再按第3/4节测试。

HTTP地址可在launch传入：`base_url:=http://127.0.0.1:8775`。本接口无需TCP token。

## 7. 已完成验证

- 隔离catkin编译成功。
- 实际ROS Action传输+模拟HTTP：缺确认拒绝、任务占用、成功、失败、取消共5/5通过。
- 已启动实际桥接节点并通过缺确认不运动测试。
- 2026-11-12 ROS已派发完整164采样、13.04秒运动；ARES只读确认center误差2.056mm、控制器错误码0，现场确认运动完成。旧到位检查误报FAULT，原因及修复见随附报告；修复后完整实机回归尚未重复。

模拟测试脚本：`scripts/test_bridge_offline.py`。仅使用本机模拟HTTP后端；运行前停掉同一master上的实际桥接节点，避免同名Action冲突。

暂不推送GitHub；Golden Demo和原入口保持原样。

## v0.2实机回归（2026-11-12）

从right/front_right_high_axes_aligned经ROS回right/center已返回SUCCEEDED / ARRIVED_CONFIRMED。误差2.051mm / 0.00294°；3次新鲜到位读数通过，Servo退出确认。详见docs/reports/2026-11-12_OFFLINE_HANDOFF.md。

Result新增arm、pose_id、outcome、details_json。details_json包含actual_body_tcp、controller_status、position_mm、orientation_deg、confirmation_duration_s和native执行结果。Action消息MD5已变化，所有客户端需重新编译/source v0.2，不能继续使用旧生成消息。
