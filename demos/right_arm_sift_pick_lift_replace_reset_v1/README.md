# demo-3-branch-sift-graspreset · Golden 1.0.0

正式ID：`right_arm_sift_pick_lift_replace_reset_v1`。

SIFT完整取放任务的前半程分支。2026-10-29使用永久V4偏置，已自动完成：
ID6扫描 → cuRobo到预抓取 → 40%开爪接近 → 闭爪 → 连续抬升230mm →
延迟读回与场景并行验证 → 原路下降 → 松爪 → 原路退回 → center。
执行141.27秒，fresh扫描/规划及初始打包约43.39秒；不包括之前人工检查后的起点恢复。

## 准备条件

- 底盘在 `SIFT-BLC-GRSP` 已验收站位；此Demo不导航、不移动底盘。
- 筛网位于原夹具内，Epic Pro 5700已启动，`320,2,6,1,1,0`能识别。
- 右臂从本Demo补偿后的全局center开始，左臂保持当前；原夹具可原路放回。
- 现场监督、物理急停和完整运动空间具备。

`station.json`冻结了地图379上的记录：x=0.202325m、y=0.753431m、yaw=−4.836330°。
该值为AMR SLAM观测快照，保留原始置信度，不宣称毫米级到站或导航已经commission。
原PLACE/PICK等站位未删除。不能只凭SLAM数字相近就跨场景复用旧轨迹。

## 永久参数

每次检测后加BODY目标偏置 `[+2,+2,−7]mm`；Demo右臂姿态保持旧TCP局部Z轴−10°，
加BODY yaw逆时针2°、朝前端下俯1°。平移不会作用于center，姿态修正绕TCP中心。
不改controller tool；旧Golden Demo保持原参数。筛网暂用已授权旧料盘持物模型。
参数见 `source_parameters.json`，源码/配置hash见 `pinned_inputs.json`，Native/SDK hash见 `native_assets.json`。

## 入口

WebUI的 `/demo-console` 选择 **demo-3-branch-sift-graspreset**，核对准备条件后手动启动。
ART的 `demo list` / `demo select demo-3-branch-sift-graspreset` 与WebUI共用目录；
执行命令也可直接在现场普通Terminal运行：

```sh
cd /home/yikun/ARES-R-RC1-20261019
PYTHONPATH=src .venv/bin/python scripts/run_sift_pick_reset_demo.py --prepare
PYTHONPATH=src .venv/bin/python scripts/run_sift_pick_reset_demo.py --execute \
  --authorization 'RIGHT SHAIWANG STAGE1 PICK RESET' --onsite-observer-confirmed
```

`--prepare`只扫描规划；`--execute`默认重新fresh准备，不复用上次轨迹。
统一软件停止：

```sh
PYTHONPATH=src .venv/bin/python scripts/run_sift_pick_reset_demo.py --stop
```

刷新网页、选择Demo、服务重启、开机均不会自动运动；软件停止不替代物理急停。
Golden入口校验冻结参数和核心源码，发现变化时要求显式新版本复核。
新任务开发应保留此快照；没有复制第二套算法，仍使用已通过的任务执行实现。

## 证据与边界

成功运行：`worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793259072432485426/`。
底层执行ID为保留历史的 `right_arm_shaiwang_pick_reset_v1`，与正式Golden ID的映射写在demo.json中。
小型索引在evidence.json；原始日志/点云继续在worklog，源码快照不等于旧轨迹可重新执行。
该Golden仅覆盖固定夹具下筛网抓取、抬升、原位放回复位；新专机放置、AMR转场及完整SIFT main尚未验收。
