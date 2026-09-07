# cuRobo 接入审计与分阶段验证

日期：2026-09-07。本文为早期只读审计历史记录，不代表当日最终状态。后续在确认区域隔离后完成 GPU 规划与右臂微动尝试；实机反馈断连导致完整轨迹验证未通过，执行入口已锁定。最新结果见 [Demo 指南](CUROBO_DEMO.md)。

## 现场边界

- 右臂控制器：192.168.99.101。左臂控制器：192.168.99.100。
- 左臂存在实际运动测试。双臂尚无已验证的联合碰撞检查和运动互锁，因此本轮不发送右臂运动指令，不使能 servo，不修改左臂脚本，不启动会同时连接双臂的实机 Terminal。
- 右臂单独完成只读诊断并关闭连接。状态查询正常不等于具备碰撞安全条件。
- 实机测试需要左臂暂停的独占测试窗口、现场观察及物理急停准备；软件停止和碰撞保护不能替代物理急停。

## 现场读取结果

- SDK 输出：`V2.1.5stable_linux`。
- 右臂查询时上电、使能、到位、连接状态正常，错误码 0，未报告限位或碰撞保护，工具编号 2、用户坐标系编号 0。
- 右臂关节快照（rad）：`[0.6952934464, 0.0617904151, 0.7415348977, -3.7410345373, -0.4744426244, 1.7042094694]`。仅为审计时快照，禁止作为后续运动起点。
- 工具 2 偏置（mm、rad）：`[1.538, -6.926, 189.138, -0.0951728053, -0.0433365260, 1.4916106939]`。轨迹目标必须区分法兰、旧仿真夹爪 link 和现场 TCP，避免漏乘或重复乘工具变换。
- GPU：RTX 3060 12 GB，驱动 560.35.03；存在其他 GPU 进程，未停止或修改。
- 已检查系统 Python 及 calib、dope、dope3.8、foundationpose 环境，均未发现可导入的 cuRobo。foundationpose 的 torch 为 2.0.0+cu118，CUDA 可用。该结果不代表扫描了全部磁盘环境。
- 本轮没有安装依赖或运行 GPU 规划，以免占用共享 GPU、改变现有环境。后续使用独立环境，固定 cuRobo 提交、Python、Torch、CUDA 和 Warp 版本。

## SDK 关键问题

官方 Python 文档定义 `servo_j(joint_pos, move_mode, step_num)`：`move_mode=0` 为绝对位置，`1` 为增量；周期为 `step_num × 8 ms`。现场 SDK 的 `JAKAZuRobot.h` 同时声明两参数与三参数 C++ 重载，第二参数均为 `MoveMode`。Python 扩展的 docstring 没有给出有效签名；精确 Python 绑定仍需结合对应版本资料确认，不通过实机试错探测签名。

仓库 `b5_servo_move.py` 的 `servo_j(tgt, 1)` 存在把第二参数视为周期的危险歧义。如果 `tgt` 为绝对角度且绑定遵循上述定义，会成为增量命令。该脚本不得直接作为 cuRobo 执行器；正在进行的测试应核对实际运行文件。原脚本本轮未修改。

实验执行器 `src/ares_r/adapters/jaka_servo.py` 使用三参数绝对模式，但仍不是可投产的实机执行器：

- 尚缺双臂互锁、模型与现场环境修订核验、跟踪误差监控和到位确认。
- 周期内同步查询可能造成发送抖动，需测量延迟分布、丢周期与队列行为。
- `KeyboardInterrupt` 未纳入现有 `except Exception` 的 abort 路径；退出 servo 的错误尚未严格处理。
- `collision_checked=true` 只是文件声明，不是碰撞检测证据。
- 不应在失败后自动回起点、改用 MoveJ 或直线插值继续执行。

来源：[JAKA Python servo 接口](https://www.jaka.com/docs/en/guide/1.7.2/SDK/python.html)。现场头文件：`/home/yikun/ws/JAKA/SDK V2.1.5/Linux/c&c++/inc_of_c++/JAKAZuRobot.h`。

## 原 ARES 代码审计

审计提交：`b978cbd669b5a3f6bc0bd19defcbe5256692f145`。完整浅克隆因网络断开失败；以下结论来自固定提交的源码读取，不代表全仓库动态测试。

- `isaac_sim/simforge/core/planning.py` 使用 `curobo.motion_planner.MotionPlanner`、`MotionPlannerCfg` 和 `curobo.types.JointState`，属于新版 API 路线；不能直接按旧版 `MotionGen` 示例安装依赖。官方说明 V2 为重大重写，旧 API 应固定 v0.7.8。
- `init_curobo_planner()` 用 cuboid 场景初始化规划器。仿真障碍并非现场点云；旧世界模型不能当成当前工位。
- `plan_curobo_segments()` 在插值结果后拼接 `fallback_path()` 把末端关节角修正到目标，拼接段没有显示进行碰撞复核。规划失败后仍把下一段起点更新成未到达的目标。这两种行为都必须从实机链路排除。
- `demos/tray_grasp_cycle/_curobo_worker.py` 的独立进程与 JSON 作业协议可借鉴，但返回关节数组不能代替时间参数化轨迹；固定切片前六列也必须换成显式关节名称映射并验证顺序。
- 根目录 `robot/jaka_minicobo_curobo.yml` 含开发机绝对路径。工具几何、碰撞球和现场机型/安装转换需重新核对。world view 的 FK 验证不等于碰撞模型验证。

来源：[原规划实现](https://github.com/Trickyboy2100/ARES/blob/b978cbd669b5a3f6bc0bd19defcbe5256692f145/isaac_sim/simforge/core/planning.py)、[独立 worker](https://github.com/Trickyboy2100/ARES/blob/b978cbd669b5a3f6bc0bd19defcbe5256692f145/isaac_sim/simforge/demos/tray_grasp_cycle/_curobo_worker.py)、[NVIDIA cuRobo](https://github.com/NVlabs/curobo)。

## 接入顺序与验收门槛

1. 独立规划环境：锁定依赖及模型资源，先进行无 SDK 的官方 GPU smoke test，记录设备、版本、显存、耗时、成功状态。
2. 模型校准：按关节名称映射 J1–J6；对比 cuRobo FK 与现场 SDK FK；正确应用基座安装变换、工具 2 TCP 和夹爪/料盘几何。其他臂、车体、桌面、夹具都进入障碍模型。
3. 纯离线规划：从新鲜快照生成右臂候选轨迹；失败即终止。导出位置、时间、速度、加速度、模型/世界/工具修订和碰撞检查证据。重采样后再次检查限位、连续碰撞、速度、加速度及首尾静止条件。
4. Terminal 预览：未来增加规划、检查、预览、执行四个分离动作。规划不得自动执行；world view 展示整段扫掠范围。此阶段不新增实机入口。
5. 独占窗口执行：左臂停止且状态稳定，现场核验净空；初次仅右臂单关节不超过 0.5°、峰值速度不超过 0.5°/s 的候选验证，限值只是上限，不构成安全证明。以现场风险评估及更严格的配置限值为准。先完成发送器时序与停止机制验证，再执行已碰撞检查的轨迹。
6. 记录目标/反馈、发送与采样时间、队列、误差、停止原因；下一次运动必须重新采集起点。没有时空互锁前不进行双臂同时轨迹执行。

## 本轮离线回归

命令：`PYTHONPATH=src python3 -m unittest discover -s tests -q`。

修复轨迹检查中的零周期除零、空路径索引、非有限反馈/限值遗漏和字符串布尔值误判；增加四项回归测试。47 项测试通过，包含 FakeRobot 的绝对模式参数与限位阻断测试。该结果不是 GPU 规划成功、servo 时序合格或实机运动成功证明。
