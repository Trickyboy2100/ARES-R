# Utility、测试分支与历史Demo

## 无工位Utility

| 原生 / ROS | 功能 | 现有入口 | 当前范围 |
|---|---|---|---|
| AAWU0-01 / RAWU0-01 | 当前位姿→右臂center | demo-0-return-center；/ares_r/return_center | 原生到位通过；旧v0.2桥接复用 |
| AAWU0-02 / RAWU0-02 | 当前→center→保存姿态 | block-01-center-restore-right；/ares_r/center_restore | 已交付Demo01；62.39s完整两段历史基线 |
| AAWU0-03 / RAWU0-03 | 姿态往返Turbo候选 | /ares_r/center_restore_turbo | 独立性能候选；48.359s样本只含一段实际运动 |
| AAWU0-04 / RAWU0-04 | 双臂center/保存姿态 | block-02-center-restore-dual | 11月17日完整ROS实机通过；待交付 |
| AAWU0-05 / RAWU0-05 | 镜像姿态准备与验证 | 现有镜像工具 | 目录预留；独立交付合同待确定 |

AW表示任务不绑定特定工位。实际执行仍使用当前工具、场景和保存姿态。Utility编号互不代替。

## 回center

扫描/读取状态 → cuRobo规划当前到全局right/center → native执行 → 新鲜关节与TCP到位回读 → AT_CENTER。使用既有 `right_arm_return_center_v1`。最近证据为11月17日到位，native运动8.16s；此数值只代表该次运动段。

## 已交付Demo01

绑定目标模式 → 当前到center规划执行与到位确认 → fresh场景重新规划center到保存目标 → 执行 → 双重到位回读 → CENTER_RESTORE_COMPLETED。

目标可以启动时保存当前姿态，也可以引用先前命名姿态；调用时明确模式和目标版本。既有右前高位目标为 `right/front_right_high_axes_aligned`，SHA256 `bbcd723fc83d1091b9065ed2636e6689e52987c9cfa8a8e3db5defac16a7499a`。原ROS Action字段和调用方式保持既有交付合同，名称映射在目录层维护。

## Turbo与双臂

Turbo优先复用准备、资源所有权及planner生命周期优化；速度与并行能力以独立实测记录。既有48.359s样本不能用于宣称完整两段都提速，也不能证明双线程已经起效。

双臂候选涉及左右共同场景、双执行器协调、互碰检查和双侧到位。最新并行版已取得 `DUAL_CENTER_RESTORE_COMPLETED`，run `a5a99dd2287341588ff2f24f1366898e`，总计约122.6s。第一段center基本到位、运动0.32s，第二段运动12.08s；左右到位和servo关闭均回读核验。Delivered=false。详见 `docs/reports/2026-11-17_DEMO02_PARALLEL_ACCELERATION.md`，不同起点样本不能直接用于宣称全部耗时差均来自并行。

## 原位抓放测试分支

| 原生 / ROS预留 | 来源 | 流程 | 状态 |
|---|---|---|---|
| AA0F0-02 / RA0F0-02 | demo-2-branch-grasprptspdup | ID1→抓→抬230mm→原位下降→松爪→预抓取→center | 历史Golden；最近回center故障 |
| AC0F0-02 / RC0F0-02 | demo-3-branch-sift-graspreset | ID6→抓→抬230mm→原位下降→松爪→退出→center | 11月6日完整通过 |
| AA0F0-03 / RA0F0-03 | demo-1-main-grasphold | ID1→抓→抬100mm→HOLD | 历史Golden保全 |

测试分支用于调偏置、抓取验证、计时和恢复路径验收。业务Fetch调用以持物结束，名称和末状态分别记录。

## 完整跨工位历史Demo

| Scheme建议编号 | 旧名称 | 功能 | 当前结论 |
|---|---|---|---|
| S-A0-B2-01 | demo-2-main-graspplace | 料盘天平取→底盘转场→烘干箱下中放→返回 | 保留历史接续完成；最新参数全链待绑定 |
| S-C0-D1-01 | demo-4-main-siftgrasp-dmpplace | 筛网天平取→底盘转场→专机放→恢复 | 当前base Console分派缺口须修复后验证 |

后一卡片的 `sift_dmp_roundtrip` 在已审源码中缺少明确分支，会进入通用roundtrip分派。该问题已记录在审计报告，目录命名工作不代表分派已经修好。
