# 右臂实际反馈专项排查

状态：只读排查；cuRobo 实机执行锁保持。没有执行新的微动或 50 cm 运动，没有恢复已有机器人程序。

最新结果：SDK V2.2.2 单通道只读测试通过 600 秒、7501 帧，最大一轮全部查询耗时 18.510144 ms，退出登录返回 0。日志 `sdk222_feedback_20260907_140418.log`；归档见 `worklog/evidence/2026-09-07-feedback/`。这是反馈读取阶段通过，不是运动中跟踪、停止、SDK 内部重连或连续数据新鲜度的认证。

## 占用进程核实

- 初始发现 PID `229469`：`python3 -m ares_r.cli --enable-hardware`，同时连接 `.100` 和 `.101` 的 `10004`，未终止该进程，以免影响左臂。
- 13:22:26 与 13:36:51 检查时，旧进程已退出，`.32` 上未发现通往左右臂的 TCP 连接。未执行 kill，也未连接左臂。
- 无其他本机状态客户端时仍复现右臂断连，不能将旧 Terminal 认定为唯一根因。本机套接字检查不能排除其他主机的客户端，也不能避免检查后的连接竞争。

## 10004 对照结果

| 请求/选项 | 成功记录帧数 | 结束时间 | 结果 |
|---|---:|---:|---|
| 原固定请求（带换行） | 78 | 6.240 s | 对端关闭连接 |
| 与 SDK 字符串一致（不带换行） | 79 | 6.320 s | 对端关闭连接 |
| 本地 SO_KEEPALIVE 开启 | 76 | 6.081 s | 对端关闭连接 |

三次均无 SDK 登录、无控制指令、无运行中自动重连。不能将时间接近解释为已确认的控制器超时规则；报文格式、会话约束和控制器端原因仍未完全确定。

## 新增 Terminal 只读工具

在 `.32` 的 `/home/yikun/ARES-R` 中启动不使能实机的 Terminal：

```bash
./scripts/run_terminal.sh
```

```text
jaka feedback-audit right 600
```

这是显式的只读网络诊断例外：Terminal 不初始化硬件适配器，但该指令会读取 `.101:10004`。既有实机 Terminal 必须先退出；检测到已有本机右臂状态连接时，记录 BLOCKED，不新建机器人连接。默认 600 秒，允许 5..600 秒；固定 80 ms 周期，保留 40 ms 预算。Ctrl+C 退出读取，不发送运动或停止指令。

结果写入 `logs/feedback_audit_*/report.json` 和 `samples.jsonl`。`READ_ONLY_SOAK_PASSED` 仅表示读取测试通过，不能自动解锁运动；本地请求往返时间不等于控制器数据时间戳验证。当前原始通道仍会断连，不能用于实机执行。

## SDK V2.2.2 替代路径

- 已有完整安装：`/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/`。
- 测试库：`/home/yikun/JAKA/lib/libjakaAPI.so`，版本 `V2.2.2stable_linux`，与安装包库的 SHA-256 一致：`997f59139c9eff3c713825894e5e5ac171913fa7e3c72acd2457acbbf4342215`。
- C++ 公开 `get_actual_joint_position` 可调用；配套 Python 扩展未暴露该方法。使用配套 C++ 头文件，不猜测私有对象布局，不替换原 Terminal 的 V2.1.5 库。
- 独立程序 `scripts/audit_jaka_v222_feedback.cpp` 只包含登录、查询与退出调用，右臂地址固定；不包含运动、上电、使能、清错、程序恢复或配置写入。
- 初测全量 `get_robot_status` 耗时约 42.4 ms，实际关节查询约 1.0 ms。改用 `get_robot_status_simple`、`get_motion_status` 和工具/用户坐标系查询，未放宽 40 ms 门槛。
- 查询得到 `paused=1`，同时错误/急停/碰撞/限位为 0、上电使能为 1。暂停标志保留记录，不恢复程序。只读测试可以继续读取，运动前仍须核实暂停程序内容与执行队列。

专用二进制位于 `/home/yikun/ares-r-curobo-assets/audit_jaka_v222_feedback`，只有固定右臂只读 API。原始通道的 Terminal 诊断与该程序不能并行运行。复测前必须检查现有连接；缺少检查工具视为阻断：

```bash
cd /home/yikun/ARES-R
PYTHONPATH=src python3 -c 'from ares_r.motion.feedback_audit import status_connections; c=status_connections(); print(c); raise SystemExit(bool(c))' && \
  /home/yikun/ares-r-curobo-assets/audit_jaka_v222_feedback 600
```

该指令仅用于反馈复测，不是实机运动指令。默认原 Terminal SDK 不变；V2.2.2 保持独立进程、固定右臂端点，避免将未经验证的新 SDK 直接用于同时连接双臂的进程。

官方接口语义参考：[JAKA C++ 实际关节伺服反馈](https://www.jaka.com/docs/en/guide/V3/SDK/cpp.html)。现场可用性以 V2.2.2 配套头文件与实际只读结果为准，不将 V3 文档整体视为当前控制器能力。

## 后续通过条件

1. 单 SDK 连续反馈、数据新鲜度与异常通信行为验证完成。
2. 在同一 SDK 执行进程中验证反馈与 servo 共存、超时停止、退出伺服；未知暂停程序不得恢复。
3. 新鲜起点的小幅实机轨迹完整到位，再增加幅度；不自动回程。
4. 50 cm 路径必须重新核对 TCP、夹爪、负载、整臂扫掠空间和现场障碍。虚拟障碍场景只用于规划验证，不能证明实机环境无碰撞。
