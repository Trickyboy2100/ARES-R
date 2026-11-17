# 第一个ROS1 Demo：扫描 → center → 返回右前高位

通过 **ROS1 Action** 调用机械臂功能。流程为：环境扫描 → cuRobo规划并运动到center → 重新扫描 → cuRobo规划并返回已保存的右前高位。两段运动完成并通过实际状态回读后，才返回成功。

第一版已完成现场实机验证，仅限当前已验证的工具和保存姿态、空手且有人监督的试用；本Demo不移动底盘、不操作夹爪。

## 1. 连接SSH

```bash
ssh yikun@192.168.99.32
```


## 2. 启动ROS环境

```bash
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-ROS-BLOCK01-20261112/catkin_ws/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321
export ROS_IP=127.0.0.1
```

这一步加载ROS Noetic和功能包，并连接现场已有的ROS Master。每个新SSH终端都需执行一次；不要重复启动新的roscore。

检查ROS节点：

```bash
rosnode list
```

应看到`/ares_r_center_restore`。若提示无法连接master或缺少该节点，先恢复现场ROS服务，不要直接运行运动命令。

## 3. 测试第一个ROS Demo

不运动检查：

```bash
rosrun ares_r_center_restore center_restore_client.py
```

预期显示：`未启动运动。现场准备完成后加 --execute。` 这只检查客户端能否加载，不代表已经完成机器人动作。

确认右臂空手、底盘和左臂静止、两段完整路径净空，现场有人持续观察且物理急停可用后，执行：

```bash
rosrun ares_r_center_restore center_restore_client.py --execute
```

终端会显示扫描/规划、运动至center、重新扫描/规划、运动至右前高位等阶段。此前完整运行约62秒，仅供参考。

最终应返回：

```json
{"success": true, "state": "CENTER_RESTORE_COMPLETED", "restored": true, "run_id": "本次任务ID", "error": ""}
```

只有`success=true`且`restored=true`才表示整个Demo完成。本Demo使用ROS接口`/ares_r/center_restore`，类型为`ares_r_center_restore/CenterRestoreAction`，目标为已保存的`right/front_right_high_axes_aligned`。每次调用都会重新扫描规划，不复用旧轨迹。
