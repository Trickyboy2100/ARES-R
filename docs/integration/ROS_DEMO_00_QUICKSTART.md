# ROS demo 00 · 扫描 → center

右臂从当前静止位姿，经新扫描与cuRobo规划回全局center，并检查实际到位。

- Console：`http://172.28.172.210:8765/demo-console`，选择 **ROS demo 00 · 扫描 → center**。
- 标签：ROS / Utility。
- ROS Action：`/ares_r/return_center`，类型 `ares_r_demo_bridge/ReturnCenterAction`。
- 后端alias仍为`demo-0-return-center`，旧客户端兼容。
- 源码：`ros1/ares_r_demo_bridge/`。执行复用原回center能力，不创建第二套JAKA或cuRobo控制。

服务器终端加载环境后调用：

```bash
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-RC1-20261019/worklog/runtime/ros1_return_center_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.99.32:11321
export ROS_IP=192.168.99.32
rosrun ares_r_demo_bridge return_center_client.py --execute
```

执行前确认右臂全路径净空、底盘与左臂静止、现场监控及急停可用。不加`--execute`只验证未授权请求被拒绝，不运动。

2026-11-17已手动启动节点并验证Action连通、未确认请求返回NOT_CONFIRMED；本轮未执行运动、未新增开机自启。节点启动不自动运动；重启服务器后需重新启动节点：

```bash
roslaunch ares_r_demo_bridge return_center.launch base_url:=http://127.0.0.1:8765
```

ROS demo 01保持原CenterRestore接口及已保存右前高位目标不变。
