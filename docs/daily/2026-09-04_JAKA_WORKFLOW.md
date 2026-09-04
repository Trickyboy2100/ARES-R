# JAKA Mini2 分阶段调试工作流

## 已核实的现场基线

- 工控机：`192.168.99.32`，仓库 `/home/yikun/ARES-R`。
- 左臂 SDK 地址：`192.168.99.100:10000`；右臂：`192.168.99.101:10000`。
- 现场 SDK：JAKA SDK V2.1.5 stable Linux。
- Python 模块目录：`/home/yikun/ws/SDK V2.1.5/Linux/python3/x86_64-linux-gnu`。
- 动态库：`/home/yikun/JAKA/libjakaAPI.so`。
- 当前站点配置标记为 JAKA Mini2；SDK 状态查询未提供可信型号字段，仍须用双臂铭牌/JAKA APP 留证核实。
- 已只读观察到左工具 ID 1、右工具 ID 2；该值只是当时状态，每次调试仍须回读。
- SDK V2.1.5 `get_robot_status()` 实测返回 25 个字段；连接状态索引为 22，急停索引为 23。
- `get_tool_data()` 实测返回 `(状态码, 工具ID, 六维TCP)`，六维 TCP 单位为毫米和弧度。

当前代码只开放只读 SDK Adapter。`jaka_servo.py` 尚未注册进 Terminal，任何 `hardware` 模式都继续锁定。

## 今日门禁

### J0：离线检查

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
./scripts/run_terminal.sh --mode mock
```

用 `motion validate` 确认未核实 Mini2 限位时轨迹必然被阻断。不得用旧 MiniCobo 参数替代。

### J1：网络与只读基线

确认急停可达、双臂无任务、工作区清空后：

```bash
./scripts/run_terminal.sh --mode jaka-readonly
```

执行 `jaka status left`、`jaka status right`、`jaka baseline`。验收 SDK 版本、六关节、TCP、工具 ID/数据、限位、碰撞状态均能读取；全过程不得上电、使能、复位、恢复或运动。

### J2：Mini2 模型与配置

仓库内 `config/jaka_mini2_motion.site.json` 为第二份现场配置，安全占位值确保验证失败。

逐项核对双臂铭牌型号、JAKA APP、控制器软限位、关节顺序/正方向、TCP、负载、碰撞等级和速度倍率。现场安全参数通过 Pull Request 评审，凭证不得写入。证据齐全前保持 `commissioning_confirmed=false`。

### J3：轨迹契约

规划器输出必须携带机器人、世界、工具和附着物版本，内部单位为弧度和秒；重采样后重新做整臂碰撞检查。轨迹首点必须与实时关节位置处于现场阈值内，采样周期必须是 8 ms 的整数倍。

### J4：执行器台架审查

用 Fake SDK 覆盖登录失败、状态查询失败、起点错位、限位、碰撞、发送返回码异常和中途异常，确认异常总会停止发送、`motion_abort` 并退出伺服模式。先审查 JAKA V2.1.5 对 `servo_j` 返回值和缓存语义，不能把未经文档确认的返回字段当队列深度。

只读在线预检：

```text
jaka preflight left examples/trajectory.example.json
jaka preflight right examples/trajectory.example.json
```

该命令只组合实时状态与离线轨迹门禁，不调用任何控制 API。当前占位限位和示例轨迹必须产生 `BLOCKED`。

### J5：首次真机运动（当前禁止）

当前授权只覆盖 SDK 审计、状态查询、代码、测试、文档和同步。底盘、双臂及夹爪控制全部禁止，`jaka_servo.py` 继续不注册到 Terminal。未来动作必须取得新的明确批准，并重新完成现场安全检查。

## 当前在线环境边界

`.32`、`.100` 与 `.101` 当前可连通，仅允许 SDK 查询。Epic `.199:5700` 不属于本轮 JAKA SDK 审计范围。任何控制能力验证均留待新的明确批准。
