# JOG、抓取对称分支与冻结规划性能

## 本轮范围

只读设备状态、冻结场景 GPU 规划、网页预览、增量界面修复；未执行机械臂、夹爪或底盘运动，未清除控制器错误，未修改生产速度、碰撞或 planner 默认配置。

## 两指夹爪的 180° 等价

夹持等价不代表整臂运动等价。同一目标位置可对应不同腕部绕转、肘部 IK 分支、限位余量、奇异性和沿途碰撞。

严格区分：同一局部轴的 +180° 与 -180° 在 SO(3) 中是同一旋转，但关节路径可能不同；NORMAL 与围绕抓取 approach 轴翻转 180° 是两个可等价夹持的姿态。禁止将 BODY yaw 翻转、Euler 角加减或任意关节取模直接当成等价抓取。是否可绕转必须遵守真实关节范围。

已有正式入口：`manipulation.plan_transfer_chain`。`grasp_symmetry.py` 枚举 NORMAL / FLIPPED_180，`transfer_chain.py` 完成有界 multi-IK、动作链图评分、按 DP 排名调用 persistent cuRobo、碰撞与 hard orientation 验证。当前选择策略是**按评分找到第一条通过的分支**，不是穷举全部 cuRobo 轨迹后求全局最优。抓取后保持已选 symmetry；底盘移动后必须 fresh scene/rebind，不能原地翻转已持物体。

本轮未替换该算法，增加 `timing_s.branch_ik_graph_s`、`timing_s.curobo_validation_s`、`timing_s.total_s` 和明确的 `selection_policy`，便于区分 IK/图搜索慢还是 cuRobo 慢。下一步适合在同一真实抓取 frozen epoch 对两分支比较：全链成功率、关节连续性、最小 singular value/关节余量、碰撞、姿态误差、总规划耗时；不能依据仅一条 JOG 测试认定抓取性能。

## JOG 不动的实际证据

旧方向按钮只提交 cuRobo 规划，不立即运动，执行按钮位于页面其他区域，交互含义不清。

另一次真正执行请求的 native sender 在约 361ms 返回：

`controller safety gate errcode=4128769 power=1 enabled=1 estop=0 collision=0 limit=0 drag=0`

对应目录：`worklog/evidence/operations-execution/1792050443378513666/live/`，没有 sample 事件；原 `execution_result.json.reason=null` 隐藏了 native failed 原因。不能将启动 sender 进程等同于开始发送轨迹。后续只读 SDK 查询 errcode=0，powered/enabled=true，无急停/限位/保护停；错误的官方语义尚未确认，不能据此清错或绕过。

修复：原始失败原因进入 backend/UI；重启恢复最后完成记录但不恢复执行；runner 保存 native failed reason 与 sample_count。页面改为「①方向预览 → ②三维查看 → ③现场确认执行」，JOG 放在手动页首位，显示 BODY 前后左右、等待秒数、失败原因；本页执行仍为右臂，左臂明确仅预览。旧候选失效/消费后禁用按钮。不是按住连续 Servo JOG。

使用：访问 `/operations` → 手动操作/规划 → 选择右臂和步长 → 点击方向预览 → 查看三维轨迹 → 现场确认 → 执行本次。失败后不自动重发；状态恢复后重新扫描规划。停止按钮为软件中止，不代替物理急停。

网页端到端验证：点击「预览 后 X−」，10mm步进，fresh相机与当前状态构建epoch73，返回 `PLAN_656cf6628ea047368f0a3db093a55cbe`、`execution_package_ready=true`，等待44.1s；hard_min_gap约10.601mm。未勾选现场确认、未点击执行。截图保存于本地 `ares-r-jog-feedback-20261015.png`。该预览不是抓取/速度commissioning，过期后不可执行。

## 冻结性能对照

原始请求：`worklog/evidence/scene-aware-motion/PLAN_3ded5c936c7b427fa7ae89de1bf9b322/planner_request.json`，BODY 后退10mm、FIXED_ROTATION，原有环境/机器人模型和3°姿态容差保持不变。复用既有 worker，使用独立私有 socket/进程，生产服务未替换。每 profile 3次，第1次冷启动、后2次热运行；固定 random_seed=123，**不是统计独立随机成功率试验**。

| profile（trajopt/IK seeds） | 冷请求总时间 s | 热请求总时间中位数 s | 成功 |
|---|---:|---:|---|
| 当前 8/8 | 33.274 | 29.953 | 3/3 |
| 测试 4/4 | 19.126 | 15.748 | 3/3 |
| 测试 4/2 | 19.183 | 15.763 | 3/3 |

九条路径均通过现有独立 dense collision 和固定姿态校验；最小 modeled clearance 约13.779mm，最大姿态误差约0.2863°。4/4在该场景减少约47.4%总时间；4/2没有额外明显收益。未启用 CUDA graph，未改变优化器间隙、max_attempts=5、采样精度或环境障碍。

原现场请求已为 persistent reused=true、warmup=0；world update约0.075s、独立验证约0.214s，而 solve约28.608s。因此这次主要瓶颈是求解而非每次进程冷启动。新的测试证明降低 trajopt seeds 有收益，但15.75秒仍不是实时控制频率。

下一步优先：扩充同一 frozen CLEAR/AVOID/BLOCK 与真实 NORMAL/FLIPPED 抓取链矩阵，再对 4/4 FAST→8/8 FALLBACK、CUDA graph兼容性与初始化成本做有界对照。未通过多场景正确性和轨迹质量验证前，测试 profile 不写成已验收生产默认。

脚本：`scripts/benchmark_frozen_planner_profiles.py`。现场原始请求/结果/worker日志：`worklog/evidence/2026-10-15-jog-planner-benchmark/{baseline,seeds4_4,seeds4_2}/`；汇总：同目录 `report.json`（本地也保存汇总）。结果全部 execution_allowed=false，不产生执行候选。

## 验证与保全

现场隔离目录全量测试：597 tests，OK，1 skipped。Mac全测因历史 Linux `/proc` 相关用例等平台条件不通过；未为通过 Mac 测试修改无关机器人程序。新增反馈用例在 Mac 单独通过。

现场保全：`worklog/preservation/2026-10-15-jog-feedback/`。部署前比对目标文件 SHA256 与上轮基线完全一致，再增量部署；同事其他 dirty 文件未覆盖。网页 build：`2026.10.15-operations-v2-jog-feedback`。本轮不推送 GitHub。
