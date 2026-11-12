# ROS Demo 01：回center并返回右前高位

**第一版已实机验证，可现场试用。** 流程：环境扫描 → cuRobo到center并确认 → 重新扫描 → cuRobo回已保存右前高位并确认。

前提：右臂空手、底盘和左臂静止、全路径净空，现场有人观察且物理急停可用。仅适用于当前已验证的工具和保存姿态。

在机器人服务器终端执行：

```bash
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-ROS-BLOCK01-20261112/catkin_ws/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1
rosrun ares_r_center_restore center_restore_client.py --execute
```

终端显示阶段和结果。`success: true`且`restored: true`表示两段运动均已完成。

按 **Ctrl+C** 请求软件停止；未确认停止时应现场核查，软件停止不能代替物理急停。

接口：`/ares_r/center_restore`，类型`ares_r_center_restore/CenterRestoreAction`。目标固定为已保存的`right/front_right_high_axes_aligned`；每次重新扫描规划，不复用旧轨迹。此前完整运行约62秒。
