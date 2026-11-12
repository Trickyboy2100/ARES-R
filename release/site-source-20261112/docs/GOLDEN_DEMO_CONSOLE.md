# Golden Demo 控制台

入口：隔离 RC1 WebUI 的 `/demo-console`，现场地址为 `http://172.28.172.210:8775/demo-console`。
原场景页和操作台顶部均有入口。Golden 是验证类型，不是唯一 Demo 名称。

| 显示名称 | 保留的 canonical ID | 范围与结束状态 |
|---|---|---|
| demo-1-main-grasphold | right_arm_epic_pick_lift_v1 | 原版抓取、验证、抬升100mm后保持持物 |
| demo-2-main-graspplace | right_arm_grasp_place_roundtrip_v1 | 历史完整取放、底盘转场及返程；保留接续恢复来源，不冒称已连续验收 |
| demo-2-branch-grasprptspdup | right_arm_pick_lift_replace_reset_v1 | 提速版抓取、连续抬升230mm、反向原位放回、释放、退回预抓取、回center |

原 Demo ID、原 golden runner、参数、轨迹生成与控制器保护均不改名、不替换。
别名注册表为 `demos/catalog_aliases.json`；ART 的 `demo list/show/select` 同时保留原 ID 并兼容别名。

## 准备与启动

提速版：保持当前已验收底盘站位，或确保头部相机通过5700 ID1可识别同一夹具内料盘。
从静止状态开始；已验收起始姿态为center。夹具原位可放回，工作区净空，现场持续监督及物理急停可用。
无需手输目标坐标。不同站位虽可fresh检测规划，但不因此自动获得实机验收。

选中 Demo，阅读该卡片的准备条件，完成准备后勾选确认，点击“一键准备并运行一次”。
历史完整取放版另外确认其接续恢复验收范围；该版仍要求登记的GRASP/PLACE站、路线、空泊位与偏置。
按钮是实机启动入口，不是仅预览：准备通过后自动执行一次，不再逐段等待人工推进。
刷新、选卡、后台启动或开机绝不自动运行；关闭网页不代表停止。

启动顺序：新运行目录隔离 → 所属planner资源检查/复用或启动 → fresh观测及规划 → Native准备 → 原执行器 → 结束留痕。
“清理”指隔离旧run及已确认死亡的本目录planner遗留socket，不清点云证据、不杀他人GPU进程、不自动解除controller fault。
共享GPU被占用或planner忙时明确报告，不盲目腾空显存。

## 监控与停止

- 执行主线、并行Native准备/相机与读回验证工作线，显示实际阶段、耗时、调用脚本及结果；逻辑工作线不是OS线程数量。
- CPU、RAM、GPU、显存曲线；不可用数据不填0。
- BODY三维视图：环境点云、碰撞抽象、机械臂关节折线、TCP实际反馈及已生成的计划轨迹；支持旋转/缩放与三视角。
- 运行时优先读取原生sender的actual反馈和到位证据，不额外高频登录JAKA。左臂或未更新字段显示年龄，不将计划值当实际值。
- 此次不是完整CAD网格渲染，也不是新实现一套控制器。原生反馈的显示刷新约1.5秒，环境层约7秒。
- 最新提速版完整展示所有已生成段；原抓取保持版展示其package轨迹。历史取放版仍以原执行器阶段/日志为准，缺失轨迹不伪造。
- 停止按钮调用同一canonical backend软件停止。ART：`demo console status`、`demo console list`、`demo console stop`。
- 原 `demo stop` / `motion stop` 在控制台占用期间映射统一停止。软件停止不能替代物理急停。
- 后端重启发现未结束job时进入RECOVERY_REQUIRED，不自动重启，不因父进程消失而假定native已停止。

## TCP 指令端口

`scripts/run_demo_console_tcp.py` 在控制台 HTTP API 之上提供 NDJSON 指令端口
（默认 `127.0.0.1:8790`），供 PLC/上位机等外部程序接入；demo-0（`demo-0-return-center`）
可直接 `run` / `plan` / `status` / `stop`。非回环绑定必须配置
`ARES_R_TCP_CONSOLE_TOKEN`，且每帧都要带 `token`。`RUN` 必须由客户端显式提供
`authorization` 与两项现场确认，适配层不会代填，运动仍由既有控制台安全门把关。
完整命令、字段、错误码与各 Demo 别名见 `docs/DEMO_TCP_COMMAND_PROTOCOL.md`。

## 实现位置

- `src/ares_r/demos/console.py`：一次性启动、资源准备、旧执行器adapter、运行所有权。
- `src/ares_r/demos/tcp_console.py`：TCP 指令解析、本地授权/确认校验、控制台 API 转发。
- `src/ares_r/demos/console_monitor.py`：旁路只读监测、资源和反馈可视化。
- `src/ares_r/webui/demo_console.html`：统一选择/启动/监控界面。
- `src/ares_r/canonical_backend.py`：共享backend、ART和执行占用隔离。
- `tests/test_demo_console.py`：无运动测试，三种adapter使用mock，不宣称新网页入口已完成第三次实机验证。

新增run保存在 `worklog/evidence/demo-console/<run_id>/`；实际提速版产物仍保存在正式Demo目录下的独立console run。
任务事件、准备日志、原执行结果与实际反馈保留供复盘。服务更新只重启空闲的隔离8775/8776，不重启共享8765/8766或相机服务。
