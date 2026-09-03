# Prototype audit

来源目录：

`/home/yikun/yikun/jinyu_ws/src/jinyu_ros_pkg/nodes/code_finish`

复制日期：2026-09-03。

## 已复制文件

- `0_test.py`：Epic Pro、JAKA 和夹爪的最小集成原型。
- `jaka_driver.py`：JAKA WebSocket 控制封装。
- `jiazhua_control.py`：因时夹爪串口协议封装。
- `utility_function.py`：SE(3) 平均及 ArUco 跟踪工具。

这些文件作为基线原样保存，后续修复应在 `src/ares_r/` 中进行，或通过明确提交修改原型。

## 已知问题

1. 相机命令当前为 `320,1,1,1,1,0` 和 `320,1,2,1,1,0`，需要与现场的 `220/310` 说法核对。
2. `0_test.py` 使用 `move_mode=` 调用 `linear_move()`，但驱动形参名为 `mode`。
3. 原型调用 `servo_move_enable`、`servo_j`、`servo_p` 和 `logout`，复制的驱动未实现这些方法。
4. 相机协议只执行一次 `recv(1024)`，尚未处理 TCP 分包、粘包、多路径点和错误帧。
5. 当前运动层没有碰撞检查、关节限位预检或轨迹规划。
6. 真机执行前需要建立 dry-run、状态 Gate、停止和异常恢复机制。
