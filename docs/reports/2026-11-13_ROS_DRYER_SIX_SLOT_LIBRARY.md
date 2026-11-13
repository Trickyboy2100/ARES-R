# 六泊位ROS交付库扩展

## 交付范围

新增十二个功能编号，分别绑定上层左中右、下层左中右的抓取和放置。原11项记录保留，总计23项注册记录，其中原P05/L03作为历史入口单独标记。客户端保持原RunBlock Action定义，新增ResolveDryerTarget服务。

新增代码位于 `release/ros1-business-blocks/blocks/dryer_slots.py`。canonical RPC为 `business_dryer_target`，ROS服务为 `/ares_r/blocks/resolve_dryer_target`。服务器读取自身站点根目录下的WebUI泊位注册表，解析实际参考点旋转与六维偏置，返回绑定版本、SHA和BODY变换。该调用只做查询与目标计算。

现场候选部署目录为 `/home/yikun/ARES-R-ROS-BUSINESS-20261113`。生产运行节点尚未加载这次扩展。

## 现场配置核对

只读获取RC1注册表revision 26，六项offset_frame均为DETECTION。平移单位为米，姿态三项均为0。

| 泊位 | X | Y | Z |
| --- | --- | --- | --- |
| 上层左 | 0.155 | -0.455 | 0.070 |
| 上层中 | 0.315 | -0.455 | 0.070 |
| 上层右 | 0.475 | -0.455 | 0.070 |
| 下层左 | 0.155 | -0.273 | 0.070 |
| 下层中 | 0.315 | -0.273 | 0.070 |
| 下层右 | 0.475 | -0.273 | 0.070 |

六项calibration_state均为CANDIDATE，occupancy均为UNKNOWN，anchor为空。实际参考点需要新的检测及绑定。上述值只归档作核对，运行解析继续读取实时注册表。

动作配置模板 `profiles/templates/ros_dryer_tasks.json` 为每个泊位分别保留取和放的TCP接触变换、接近、退出、夹爪参数。模板没有填入未经确认的默认动作。

## 测试

- Mac及现场Ubuntu均通过88项Python测试。
- 现场Noetic catkin编译通过，包含Node.js消息生成。
- 隔离Master 12431验证4项ROS服务用例，包括23项目录和目标查询服务。
- 客户端ZIP含12个文件，11个内容文件SHA校验通过。
- 传输附带的Mac AppleDouble元数据曾导致Node.js消息生成报解码错误，已转移到候选证据目录后重新编译通过。

客户端包为 `ARES-R-ROS-Manipulation-SixSlots-20261113.zip`，SHA256为 `92c744600f6da87d39cd799abbc341b8ced16be5ccd9c283335932f9d52065b9`。

## 当前能力边界与下一步

十二个入口的注册、共享目标解析、配置变更检测和源码接口交付已经完成。十二个入口的物理执行适配仍未完成，当前不会通过RunBlock启动运动。原L03固定偏置的历史入口继续保留，尚未改为实时注册表执行。

后续需要完成各槽动作参数绑定，把冻结的目标交给现有取放执行器，并逐槽验证接近、接触、退出及实际取放结果。六泊位不能仅以编号扩展获得原下层中间入口的实机验收状态。

本轮没有相机采集、机械臂、夹爪或底盘动作。
