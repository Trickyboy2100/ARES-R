# cuRobo 右臂实机 20 cm Demo

状态：2026-09-07 已通过 Terminal 完成一次实机演示。仅限右臂、空载、全扫掠空间已确认净空、现场观察及物理急停可用。无自动回程，不连接左臂、底盘、相机或夹爪。

## 操作指令

在 `.32` 工控机执行：

```bash
cd /home/yikun/ARES-R
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware --devices right-arm
```

在 ARES-R Terminal 内输入：

```text
curobo demo plan20
curobo preview last
curobo demo run20 last
```

确认提示出现后输入：

```text
RUN RIGHT 20CM
```

- `plan20`：从右臂当前实际关节与 TCP 重新规划，不运动；输出轨迹路径和 HTML 预览。
- `preview last`：查看统计与浏览器预览路径；HTML 提供连杆/TCP/虚拟障碍的三视图、3D 投影、关节曲线及播放滑块，不连接机器人。
- `run20 last`：再次检查当前起点、工具、限位、队列和执行条件，确认后执行一次。`last` 仅指当前 Terminal 会话内最近生成的 Demo；也可传入明确的 `trajectory.json` 路径。
- 轨迹起点快照超过 5 分钟、关节起点偏差超过 0.02°、其他客户端占用、工具变更或模型/数值检查失败时拒绝执行。执行过的轨迹不得直接重复使用；需要再次 `plan20`。
- Ctrl+C 请求独立执行进程停止，随后检查停止/退出伺服日志；软件停止不是硬实时或物理急停的替代品。
- 原 `curobo execute-micro` 旧 Python 执行路径仍锁定。新路径使用独立 SDK V2.2.2 C++ 进程，不能混用原始 10004 读取通道。

不使能实机模式仍使用 `./scripts/run_terminal.sh`，可预览保存的轨迹，不能执行本 Demo。启动模式仍只有不使能实机／使能实机两种。

## 本次实机结果

| 项目 | 结果 |
|---|---:|
| cuRobo 规划 TCP 行程 | 193.869 mm |
| 实际 TCP 反馈采样折线行程 | 194.319 mm |
| 实际起终点直线距离 | 159.649 mm |
| 规划持续时间 / 周期 | 40.96 s / 80 ms |
| 执行采样点数 | 513 |
| 规划最大关节速度 | 0.788874°/s |
| 最大跟踪误差（实际反馈对前一指令） | 0.050748° |
| 最终最大关节误差 | 0.001373° |
| 规划模型对虚拟障碍最小间隙 | 9.847 mm |
| 实际 TCP 球代理采样对虚拟障碍最小间隙 | 8.842 mm |

日志包含 `target_reached`、`servo_disabled code=0`、`logout code=0`。机器人停在终点，没有自动回程。实际行程为离散反馈折线长度，不是起终点直线位移或高频测量的绝对真值。

此前同进程右 J6 +0.2° cuRobo 微动已完成 41 点测试，随后才进入该 20 cm 演示。更早的原始反馈断连失败记录保留，不覆盖历史。

## 规划与执行边界

1. 固定官方 cuRobo 提交 `8e734f3ced1df898990bcd92de40abce475907db`，真实 GPU `plan_cspace`；没有 TCP 直线约束。基准关节路径会穿过中途虚拟盒，cuRobo 通过多关节运动绕开。
2. 虚拟盒边长 25 mm；法兰到实际工具 TCP 之间增加半径 25 mm 的球串代理。代理不是经过测量认证的完整夹爪外形，不能直接用于真实狭窄避障。
3. 采用现场工具 2 的新鲜 TCP 偏移，URDF 到控制器变换使用已留档 FK 审计结果；起点 TCP 与 SDK 实测偏差超过 3 mm 时拒绝规划。
4. 在原 cuRobo 采样路径上放慢并重采样到 80 ms，重新检查碰撞、幅度、速度和加速度。不是规划失败后的插值替代，也不追加未验证修正段。
5. 原模型开启自碰撞检查，并独立检查所有有效碰撞球对虚拟盒的采样间隙。全路径及加密样本通过检查；这不是完整连续碰撞认证。
6. 规划关节点和 TCP 点保持在车体右侧 `Y ≤ -0.07 m`、高度 `Z ≥ 0.8 m`；该检查不是左臂实时碰撞模型。现场已确认的隔离和净空条件不可省略。
7. 执行限制：每关节相对起点不超过 20°，峰值不超过 1°/s、加速度不超过 2°/s²；规划 TCP 峰值不超过 20 mm/s、行程 180..220 mm。执行时实际 TCP 相对起点超过 250 mm、跟踪误差超过 0.2°或读取/发送超预算即停止。
8. SDK 2.2.2 的状态、实际关节、实际 TCP、工具检查与 `servo_j(ABS, 10)` 在同一个右臂进程中进行。没有上电、机器人使能、程序恢复或自动回程调用。已有运动队列、活动队列或伺服模式时拒绝接管。
9. 保持 `collision_checked=false`：现场世界、夹爪与负载模型没有整体认证。仅本次受限空载净空演示走显式确认通道，不开放任意轨迹执行。

## 文件与留痕

- 核心：`src/ares_r/motion/obstacle_demo*.py`、`native_demo.py`、`scripts/jaka_right_demo.cpp`。
- 现场独立程序：`/home/yikun/ares-r-curobo-assets/jaka_right_demo`，链接已有 V2.2.2 库，原 Terminal SDK 不覆盖。
- 源码更新后可执行 `bash scripts/build_jaka_right_demo.sh` 重编译，只编译、不连接机器人；不得在执行进程运行期间覆盖该二进制。
- 每次运行：`logs/curobo_obstacle_*/request.json`、`trajectory.json`、`trajectory.preview.html`、`native_execution_*.log`。
- 本次归档：`worklog/evidence/2026-09-07-demo20/`；历史快照禁止作为当前运动起点。
- 专项反馈排查：[反馈审计记录](RIGHT_FEEDBACK_AUDIT_2026-09-07.md)。
