# ARES-R cheatsheet：ROS回center与离线工作

## 现场ROS（Mac通过SSH，无需安装ROS）

```bash
ssh yikun@172.28.172.210
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-RC1-20261019/worklog/runtime/ros1_return_center_ws/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321
export ROS_IP=127.0.0.1
rosnode list
```

不运动测试：`rosrun ares_r_demo_bridge return_center_client.py`，预期NOT_CONFIRMED。

现场条件确认后回center（会运动）：`rosrun ares_r_demo_bridge return_center_client.py --execute`。

反馈：`rostopic echo /ares_r/return_center/feedback`。

结果：`rostopic echo /ares_r/return_center/result`。v0.2新增arm、pose_id、outcome和details_json（实际TCP、到位误差、控制器状态、native退出、耗时与证据）。更改Action消息后所有客户端需重新source同一工作空间，不要混用旧消息MD5。

取消：客户端Ctrl+C，或`rostopic pub -1 /ares_r/return_center/cancel actionlib_msgs/GoalID '{}'`。需确认STOPPED；杀进程不等于后端停止。

## 服务与端口

- ROS测试master：127.0.0.1:11321；没有修改11311。
- canonical backend：127.0.0.1:8776；Demo HTTP/WebUI：8775。
- 原始TCP：8790，需要私下交付的token；HTTP不能发到8790。
- 查询HTTP状态：`curl http://127.0.0.1:8775/api/demo-console/status`。
- 8775 Connection refused：后端没启动，不是ROS失效。先检查端口/原进程/现场服务manifest；不要盲目删文件或启动重复服务。
- 这些ROS/TCP服务没有新增开机自启，服务启动不自动运动。

## 姿态命名

统一使用`right/<name>`或`left/<name>`，BODY原点与轴不因命名而变化。

- `right/center`：引用已有右臂Cartesian目标，旧`center`保留兼容。它不表示左臂center，也不是BODY原点。
- `right/front_right_high_axes_aligned`：本次对正后实测右前高位，TCP X=-BODY Y、Y=BODY X、Z=BODY Z。BODY约[0.437159,-0.383267,1.607323]m。关节快照绑定tool3，不等于任意起点路径已commission。
- 暂不创建/执行left/center；旧center中的left读数是历史停放记录，不自动当成左臂目标。

## Mac离线（不连接硬件）

在仓库根目录：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p test_arrival_confirmation.py -q
```

ROS模拟测试需要Ubuntu+ROS Noetic，先catkin_make，再启动隔离roscore和`test_bridge_offline.py`；测试自带模拟HTTP，不访问硬件。运行时不要让正式桥接节点占用同名Action。

公开快照`release/site-source-20261112/`保留现场原结构；本地私有归档位于`site-private-20261112-offline-handoff/`，含精确场景和SDK/模型。离线分析优先从planner_request、planning、native_audit、native_supervised和arrival-confirmation读取，禁止把旧trajectory用于重新控制机器人。

GPU回放需另外安装匹配cuRobo/Torch/CUDA并适配现场绝对路径。本轮没有在Ubuntu GPU重跑，不能把代码/数据已归档当作GPU复现已通过。
