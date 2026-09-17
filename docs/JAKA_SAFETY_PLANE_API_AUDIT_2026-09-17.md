# JAKA Safety Plane API 审计（2026-09-17）

## 结论

结论为 **C：现场公共 SDK 没有可证实的 Safety Plane 读写接口，只能通过 JAKA App/控制器安全设置进行管理员配置**。

本次只读检查覆盖：

- Linux/Windows SDK V2.1.5 `JAKAZuRobot.h`、示例、Python `jkrc.so`；
- Linux SDK V2.2.2 header 与 `libjakaAPI.so`；
- ROS V2.2 携带的三份 `JAKAZuRobot.h`；
- 已安装 V2.1.5/V2.2.2 `libjakaAPI.so` 导出符号；
- Python `dir(jkrc.RC)`。

搜索词包括 `safety plane`、`safe plane`、`safety zone`、`cartesian limit`、`workspace limit` 及中文同义词。660 个候选 header/source 文件、动态库符号和 Python binding 均未出现可调用接口。原始证据位于：

`/home/yikun/ARES-R_AUDIT_20260917/afternoon/jaka_safety_plane_search.txt`

因此本轮没有也不得向控制器写入安全平面。

## 中央 14 cm slab 对应的控制器基坐标平面

ARES-R BODY 定义：`+X` 向前，`+Y` 向左，`+Z` 向上；禁区为 `-0.070 <= BODY Y <= +0.070 m`。

下列参数统一表示：

```text
normal_base · point_base >= offset_m
```

| 臂 | base 位姿 | normal_base | offset | 安全侧 |
|---|---|---|---:|---|
| 左 | `(0,+0.200,1.200)`, yaw `+135°` | `[+0.70710678,-0.70710678,0]` | `-0.130 m` | BODY `Y>+0.070` |
| 右 | `(0,-0.200,1.200)`, yaw `+45°` | `[-0.70710678,-0.70710678,0]` | `-0.130 m` | BODY `Y<-0.070` |

边界上的参考点（arm-base frame）：左 `[-0.0919239,+0.0919239,0] m`，右 `[+0.0919239,+0.0919239,0] m`。

这些是从 `config/robot_world.json` 刚体变换计算得到的 **REPORT_ONLY** 候选，不是已经写入控制器的配置。JAKA App 配置时还必须确认：

1. App 对平面法向/正负安全侧的具体字段定义；
2. 单位是 mm 还是 m；
3. 是否同时约束 elbow/J3；
4. 选择开机始终激活、对 SDK 控制同样有效的安全模式，而不是仅在 JAKA 程序运行时激活；
5. 配置后用只读状态和人工边界检查留证，不能直接用机械臂试撞平面。

控制器平面只是最后一道冗余，不能替代 ARES-R 全轨迹碰撞几何 gate 与 cuRobo scene。
