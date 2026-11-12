# ARES-R Demo Library

每个可演示任务占用一个稳定目录：

```text
demos/<demo_id>/
├── demo.json          机器可读定义、版本、阶段、freshness 和执行入口
├── README.md          现场操作说明
└── evidence.json      已完成 commissioning 的小型证据索引
```

运行时生成的点云、轨迹和日志不得写进这里，而写入
`worklog/evidence/demo-runs/<demo_id>/<run_id>/`。`demo.json` 是流程定义，
不是可复用旧轨迹；所有标记为 `fresh` 的数据必须在每次运行重新生成。

ART 与 WebUI 共用 `ares_r.demos.DemoRegistry`，因此选择状态、版本和执行入口一致。

2026-10-29新增Golden branch `demo-3-branch-sift-graspreset`，正式ID `right_arm_sift_pick_lift_replace_reset_v1`，1.0.0。筛网ID6、V4永久偏置、SIFT-BLC-GRSP站位与141.27秒完整前半程成功证据已冻结；属于未来SIFT完整取放的branch，尚不包含新专机place或AMR转场。

2026-10-23 新增正式 `right_arm_pick_lift_replace_reset_v1`（1.0.0）：固定夹具下右臂抓取、连续230mm抬升、原路放回并回center，已完成热态及planner冷态无中断验收。范围不含底盘转场、六泊位或整机断电启动；详情及运行/停止命令见该目录README。原 `right_arm_epic_pick_lift_v1` golden不变。

2026-11-06 新增 `right_arm_dmp_place_v1`（`demo-5-main-dmpplace`，1.4.0）：从 DMP 抓取站起始，把 demo-4 的 `dmp_place`（检测→预放置点→规划→下降60mm→松爪）与 `return_center` 两段抽成独立 Demo；不含抓取与底盘转场（全程不动底盘），开工前强制校验站点速度上限 0.2 rad/s、控制器 TCP tool_id=3，下降段还要求横向偏移 ≤20 mm。两段组合尚未实机验收。

2026-11-09 新增 `right_arm_liaopan_dmp_place_v1`（`demo-6-liaopan-placetoDMP`，1.4.0）：demo-5 的**料盘专机拷贝**，链路与代码路径不变（共用 `scripts/run_dmp_place_demo.py`，用 `--demo-id` 选择自己的 `parameters.json` 与证据目录）。现场定的几何：预放置点 = 5700 检测返回点 **BODY y+5 mm**（x/z 不偏移）、末端 **yaw 固定 0°**，再控制器 MoveL 下降 **10 mm** 到放置点（预放置点下方 10 mm，与检测点无关）；夹持物为料盘；现场确认的**鬼影体素**按前缀**整族不参与碰撞判定**（名字取自当次场景净空表，未知名字仍 fail-closed；仍保留 5° 水平硬门限）。到预放置点的实机段已于 2026-11-09 验收（旧几何：7.0 s / 82 采样 / 到位 1.31 mm）；当前几何干跑首次 FAST 出图（水平 1.16°、yaw 0.001°）。

2026-11-11 新增 `right_arm_liaopan_hongganxiang_place`（`demo-2-liaopan-placeto-hongganxiang`，1.2.1）：demo-6 的**参数级拷贝**，脚本与链路完全不变（`--demo-id` 切换参数与证据目录），只改放置目标几何与检测配置：5700 抓取配置 **ID3**（`right_place_rightmost`，`320,2,3,1,1,0`）检测 → 放置点 = 控制台六泊位注册表 `lower_middle · CANDIDATE`（revision 21：检测坐标系 `[0.315,-0.273,0.070]` m → BODY `[+70,-315,+273]` mm）→ 预放置点 = 放置点上方 **30 mm**（BODY +Z，yaw 0，相对检测点 `[0.070,-0.315,0.303]` m）→ 控制器 MoveL 下降 **30 mm** 到泊位。放置腿按现场要求改为 **`EXPLICIT` + `hard_level_manifold`**（水平流形 IK 种子 + 显式姿态全程参与优化），仍保留 5° 事后硬校验。误检体素策略**沿用 demo-6 的碰撞后整族排除**；2026-11-11 曾把 `observed_support_01_component_01_protruding_obstacle_051` 当成误检并加了规划前预排除，后经现场更正为**看错、不是误检**，该家族与 `ignore_cuboid_prefixes` 机制已回退。旧偏置 `[60,-315,238]` mm 下 30 mm 下降会被 IK 裁到 24 mm 并落在 j3≈0 肘奇异面（雅可比 σ_min 0.0001），控制器 `linear_move` 接受命令但不运动；现场把检测 Y 改到 −0.273（BODY +35 mm 高）、Z 改到 0.070（+10 mm 前）后，新 place/preplace 在 yaw 0 下 IK 均精确可解（j3 −26.8°/−43.7°）。当前**无新版本干跑/实机证据**，必须先 `--stage all` 干跑。
