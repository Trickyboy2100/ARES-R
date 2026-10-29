# 筛网→新专机：阶段1候选 Demo

状态：CANDIDATE，不是Golden。整套任务通过分阶段实机验收后再提升为新的Golden main。

## 设计边界

- 完整流程来源：第二个Golden `right_arm_grasp_place_roundtrip_v1`。
- 本阶段执行机制来源：branch `right_arm_pick_lift_replace_reset_v1`。
- 本阶段仅右臂：ID6 fresh识别 → 预抓取 → 40%开度接近 → 闭爪验证 → 连续抬升230mm → 扫描/滚动读回并行验证 → 原路下降230mm → 到达校验 → 松爪 → 退回预抓取 → 返回起始center快照。
- 左臂HOLD_CURRENT，底盘不动，不进入新专机放置。
- 原Golden的四个固定核心文件不修改；同事两个tmp副本保留。
- 共用现有SceneAware/curobo、接触许可、持物几何、retiming、滚动抓取验证和到达组件；新增的是任务参数绑定、编排adapter和会话互斥，不是第二套规划算法。

## 新对象与偏置

2026-10-29明确确认ID6为筛网，并暂时沿用旧持物模型 `DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2`。此为暂用模型，不宣称筛网尺寸已新测量。
已有TCP_LOCAL_Z的−10°补偿从原参数只读引用，不修改controller tool。
本任务V3永久保存两类独立偏置：每次fresh检测位置加BODY `[+0.002,+0.002,−0.007]m`（原+5mm X叠加后撤3mm和左移2mm）；姿态先 `R_BODY_Z(+3°) × R_detected × R_TCP_Z(−10°)`，再围绕TCP中心、沿当前朝前端下俯1°。+3°来自原逆时针4°后右旋1°，不与local-Z的−10°混加。下俯绕BODY水平侧向轴，不导致TCP绕其他点公转。检测原始报文保持原样，目标平移不改变center位置，姿态补偿贯穿本任务右臂目标；不改变其他Golden或左臂。配置永久生效只针对本Demo，不写controller tool。
`inspection_stop_before_close=true`时执行仅到CONTACT_HOLD_BEFORE_CLOSE：夹爪40%开度保持、不闭爪、不抬升、不自动退回；用于人工核对。确认后必须明确切回完整流程模式并fresh准备，不能把该检查点当完整Demo成功。
当前已按人工认可切回 `inspection_stop_before_close=false`，下一轮是完整pick/lift/replace/reset；V3新偏置的整轮实机复测尚待下一次授权执行。当前机器仍停在开爪检查点，不自动回center或重新抓取。
站位 `SIFT-BLC-GRSP` 已追加到 `config/manipulation_stations.json`，原站位保留；SLAM记录是观测值而非高精度导航验收。
旧烘干机下层中间泊位偏置 `[0.315,-0.238,0.060,0,0,0]` 存储坐标系为DETECTION，状态CANDIDATE；其余五槽尚无偏置。旧偏置不等同于新专机偏置，本阶段不用。

## 准备和联调

在隔离RC1工作目录执行，首次运行先完成静止场景准备，不自动运动：

```sh
cd /home/yikun/ARES-R-RC1-20261019
PYTHONPATH=src .venv/bin/python scripts/build_shaiwang_sender.py
PYTHONPATH=src .venv/bin/python scripts/run_shaiwang_stage1.py --inspect
PYTHONPATH=src .venv/bin/python scripts/run_shaiwang_stage1.py --prepare
PYTHONPATH=src .venv/bin/python scripts/run_shaiwang_stage1.py --preflight --prepared <刚生成的目录>
```

5700必须已启动，筛网处于原夹具中，ID6可见。2026-10-29已选择全局named center（不是昨日偏离约32mm的起点）；已有−10°补偿只读带入，不改全局定义。
先运行 `scripts/plan_shaiwang_center.py`，仅规划并展示回center，不执行。获得单独授权、到位之后再prepare本阶段。
准备和执行前均核对实际起点与全局center；末段严格原路返回这一已确认center，不把任意起点误称为center。

只有取得新一次现场监督授权后，执行：

```sh
PYTHONPATH=src .venv/bin/python scripts/run_shaiwang_stage1.py --execute \
  --authorization 'RIGHT SHAIWANG STAGE1 PICK RESET' --onsite-observer-confirmed
```

默认执行会重新准备fresh候选，绝不复用昨天的scene/trajectory。不得把诊断冻结回放当实机候选。

统一停止：

```sh
PYTHONPATH=src .venv/bin/python scripts/run_shaiwang_stage1.py --stop
```

软件停止不替代物理急停。FAULT后不自动恢复、不重复抓取、不自动继续底盘或放置。

## 昨日问题的针对性修正

- profile只覆盖任务内配置，ID6贯穿采集和执行前复核，配置文件保留ID1。
- 状态页不再隐式登录SDK；显式只读批次、整次相机观测和Native对现有 `/tmp/ares-r-right-servo.lock` 串行持独占锁，避免两个读批次也互相干涉。
- 新task sender持独占锁，等待读批次退出，原native模式的0.02°不变；新task模式起点上限0.1°且额外检查初次采样动态，不放开controller fault/limit/collision/estop、速度/加速度、跟踪或deadline检查。
- 4.5°水平策略限于此候选任务，保留实际测量；普通shell的LEVEL环境变量不再污染其他Golden。
- 每个候选绑定任务参数、源码、ID6观测、scene、点云SHA、原偏置/参数和native build；改变后必须重新prepare。
- Source geometry、初始Native和lift/lower后台准备沿用branch流水线；后续Native完成并验证后才进入接触。

运行产物：`worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/`。
`native_sender.build.json` 为现场编译产物（含源码/库/二进制哈希），需重新构建，不携带个人凭据。
