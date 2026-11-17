# 参数、证据与旧入口索引

依据2026-11-17现场只读快照和已保存ROS报告。当前参数SHA与历史运行结果分别记录；缺少当次参数快照时，当前SHA不能代替历史绑定。现场证据根目录为 `/home/yikun/ARES-R-RC1-20261019`。

## 数据来源

`docs/reports/2026-11-17_DEMO_CONSOLE_TASK_TEMPLATE_AND_PHYSICAL_BASELINE.md`、`docs/reports/2026-11-17_ROS_DEMO_CONSOLE_INVENTORY.md`、`worklog/evidence/2026-11-17-demo-console-task-audit/demo-task-matrix.json`。原始私有快照另行归档。

## 已映射业务

### AA0F0 · 料盘天平取料并持稳

对应ROS `RA0F0`；原生状态 历史抓取成功；独立230mm HOLD配置待确认；ROS状态 P02适配已绑定；ROS独立持稳待验收。

旧Console入口 `demo-1-main-grasphold`。

执行Demo `right_arm_epic_pick_lift_v1`。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AA0P0 · 料盘放回天平

对应ROS `RA0P0`；原生状态 近期仅规划；完整放置待验证；ROS状态 L05待执行接线。

旧Console入口 `demo-1-liaopan-placeto-cheng`。

执行Demo `right_arm_liaopan_cheng_place_v1`。

当前参数 `demos/right_arm_liaopan_cheng_place_v1/parameters.json`。

revision `LIAOPAN_CHENG_PLACE_2026_11_13_V3_ID9_Z60_D60_WAIVER_SUPPORT02_CENTER_IKSEED`。

SHA256 `864918a9c37e840a9f427646f4dca4e8b203a5fe5f6b4be349a00540a7eac74d`。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AC0F0 · 筛网天平取料并持稳

对应ROS `RC0F0`；原生状态 原位抓放完整通过；独立HOLD待出口确认；ROS状态 P01适配已绑定；独立ROS持稳待验收。

旧Console入口 `demo-3-branch-sift-graspreset`。

执行Demo `right_arm_sift_pick_lift_replace_reset_v1`。

当前参数 `demos/right_arm_sift_pick_lift_replace_reset_v1/source_parameters.json`。

revision `SHAIWANG_STAGE1_ID6_20261106_V12_EXTRA_ALLOWED_CONTACT_PROTRUSION`。

SHA256 `0775f9bcc3700b5f05312e5c40fa5472cab5c0c45a9c5c6e4fc0476264fddc1c`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793947510916121152/execution/result.json`

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793945342269572096/execution/result.json`

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793775148331543459/execution/result.json`

### AC0P0 · 筛网放回天平

对应ROS `RC0P0`；原生状态 2026-11-13完整通过；ROS状态 L04本地适配回放通过；现场ROS待联调。

旧Console入口 `demo-7-shaiwang-placeto-cheng`。

执行Demo `right_arm_shaiwang_cheng_place_v1`。

当前参数 `demos/right_arm_shaiwang_cheng_place_v1/parameters.json`。

revision `SHAIWANG_CHENG_PLACE_2026_11_13_V3_ID8_Z100_D100_CENTER_IKSEED`。

SHA256 `adc0de0afc1d0e8654fe911476bc38ba708dc7938b67e378d80597340754ecc6`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_shaiwang_cheng_place_v1/run_1794554796221507249/result.json`

### AD1F0 · 除尘收料专机取筛网

对应ROS `RD1F0`；原生状态 需由成熟抓取链派生并验证接近/脱离；ROS状态 P03仅配置定义。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AD1P0 · 除尘收料专机放筛网

对应ROS `RD1P0`；原生状态 2026-11-09完整通过；ROS状态 L01已绑定；ROS完整调用待验收。

旧Console入口 `demo-5-main-dmpplace`。

执行Demo `right_arm_dmp_place_v1`。

当前参数 `demos/right_arm_dmp_place_v1/parameters.json`。

revision `DMP_PLACE_2026_11_09_V9`。

SHA256 `f29fd87828b3b90c452fa56950992dc51b16659031e6113fe72fcc4e5f27769e`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_dmp_place_v1/run_1794204348793064700/result.json`

### AD2F0 · 除尘收料专机取料盘

对应ROS `RD2F0`；原生状态 需由成熟抓取链派生并验证接近/脱离；ROS状态 P04仅配置定义。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AD2P0 · 除尘收料专机放料盘

对应ROS `RD2P0`；原生状态 2026-11-09完整通过；当前V7参数待回溯绑定；ROS状态 L02已绑定；ROS完整调用待验收。

旧Console入口 `demo-6-liaopan-placetoDMP`。

执行Demo `right_arm_liaopan_dmp_place_v1`。

当前参数 `demos/right_arm_liaopan_dmp_place_v1/parameters.json`。

revision `LIAOPAN_DMP_PLACE_2026_11_11_V7_Y5_Z20_D20`。

SHA256 `97e878c18af3c334e228221c61eb259e4037243bcecbcfb4e6e6380e5e8f2aa6`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_liaopan_dmp_place_v1/run_1794216841515922914/result.json`

### AB1F1 · 烘干箱上左取料盘

对应ROS `RB1F1`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB1P1 · 烘干箱上左放料盘

对应ROS `RB1P1`；原生状态 从下中成功放置派生；该槽偏置/高度待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB2F2 · 烘干箱上中取料盘

对应ROS `RB2F2`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB2P2 · 烘干箱上中放料盘

对应ROS `RB2P2`；原生状态 从下中成功放置派生；该槽偏置/高度待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB3F3 · 烘干箱上右取料盘

对应ROS `RB3F3`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB3P3 · 烘干箱上右放料盘

对应ROS `RB3P3`；原生状态 从下中成功放置派生；该槽偏置/高度待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB1F4 · 烘干箱下左取料盘

对应ROS `RB1F4`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB1P4 · 烘干箱下左放料盘

对应ROS `RB1P4`；原生状态 从下中成功放置派生；该槽偏置/高度待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB2F5 · 烘干箱下中取料盘

对应ROS `RB2F5`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB2P5 · 烘干箱下中放料盘

对应ROS `RB2P5`；原生状态 2026-11-11下中完整通过；ROS状态 下中原生可优先适配；六槽ROS联调待完成。

旧Console入口 `demo-2-liaopan-placeto-hongganxiang`。

执行Demo `right_arm_liaopan_hongganxiang_place`。

当前参数 `demos/right_arm_liaopan_hongganxiang_place/parameters.json`。

revision `LIAOPAN_HONGGANXIANG_PLACE_2026_11_11_V4_BERTH_Y273_Z70_MANIFOLD`。

SHA256 `27ed554de56d080d1d3024150b55f1ec9fe56724023d8818911d345f4801606a`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_liaopan_hongganxiang_place/run_1794383252441911735/result.json`

### AB3F6 · 烘干箱下右取料盘

对应ROS `RB3F6`；原生状态 配置/目标解析可复用；该槽取料实机待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AB3P6 · 烘干箱下右放料盘

对应ROS `RB3P6`；原生状态 从下中成功放置派生；该槽偏置/高度待验收；ROS状态 六槽RunBlock定义已有；执行适配待完成。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AAWU0-01 · 右臂回center

对应ROS `RAWU0-01`；原生状态 2026-11-17到位通过；ROS状态 旧return_center v0.2可复用；新目录名已登记。

旧Console入口 `demo-0-return-center`。

执行Demo `right_arm_return_center_v1`。

当前参数 `demos/right_arm_return_center_v1/parameters.json`。

revision `RETURN_CENTER_2026_11_06_V1`。

SHA256 `3a739978eb8f800f2d2228436e8e6e333a5ec67e86059ad20c5f4af7c1b53927`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_return_center_v1/run_1794878521308626121/result.json`

- `worklog/evidence/demo-runs/right_arm_return_center_v1/run_1794560970360981527/result.json`

### AAWU0-02 · 右臂center与保存姿态往返

对应ROS `RAWU0-02`；原生状态 两段实机成功；62.39s基线；ROS状态 ROS已验证且已交付。

旧Console入口 `block-01-center-restore-right`。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AAWU0-03 · 右臂姿态往返Turbo

对应ROS `RAWU0-03`；原生状态 有48.359s记录；当次仅一段实际运动；ROS状态 独立Action候选；完整双段提速验收待补。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AAWU0-04 · 双臂center与保存姿态往返

对应ROS `RAWU0-04`；原生状态 2026-11-17完整ROS实机通过；122.6s，第一段基本原位保持；ROS状态 ROS实机通过；Delivered=false。

旧Console入口 `block-02-center-restore-dual`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-console/a5a99dd2287341588ff2f24f1366898e/block/result.json`

### AAWU0-05 · 镜像姿态准备/验证

对应ROS `RAWU0-05`；原生状态 已有工具与回读测试；独立Demo合同待定；ROS状态 待定义独立交付范围。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AA0F0-02 · 料盘取抬升并原位放回center

对应ROS `RA0F0-02`；原生状态 历史Golden；11-13最近RESET_CENTER故障；ROS状态 测试分支可保留；ROS交付待需要时封装。

旧Console入口 `demo-2-branch-grasprptspdup`。

执行Demo `right_arm_pick_lift_replace_reset_v1`。

当前参数 `demos/right_arm_pick_lift_replace_reset_v1/source_parameters.json`。

revision `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_11_09_V23_SITE020_NOCOMP_TOOL3_QSEEDS4_ANCHOR_ROLLED_BACK_SKIPFAST`。

SHA256 `8baa66f958bceaa4d06c039a2df9fb6739587b5a583cd260fb41e61ea2ce7e2f`。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

### AC0F0-02 · 筛网取抬升并原位放回center

对应ROS `RC0F0-02`；原生状态 11-06完整成功；执行116.15s；ROS状态 测试分支可保留；ROS交付待需要时封装。

旧Console入口 `demo-3-branch-sift-graspreset`。

执行Demo `right_arm_sift_pick_lift_replace_reset_v1`。

当前参数 `demos/right_arm_sift_pick_lift_replace_reset_v1/source_parameters.json`。

revision `SHAIWANG_STAGE1_ID6_20261106_V12_EXTRA_ALLOWED_CONTACT_PROTRUSION`。

SHA256 `0775f9bcc3700b5f05312e5c40fa5472cab5c0c45a9c5c6e4fc0476264fddc1c`。

采集到的成功记录索引（包含各记录声明的阶段范围）

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793947510916121152/execution/result.json`

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793945342269572096/execution/result.json`

- `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793775148331543459/execution/result.json`

### AA0F0-03 · 历史料盘抓取抬升100mm并HOLD

对应ROS `RA0F0-03`；原生状态 历史Golden保全；ROS状态 保留原生基线；ROS映射为规划登记。

旧Console入口 `demo-1-main-grasphold`。

执行Demo `right_arm_epic_pick_lift_v1`。

完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。

## 关键完整成功结果

- 筛网专机 `right_arm_dmp_place_v1/run_1794204348793064700/result.json`，PLACE_CENTER_COMPLETE。

- 料盘专机 `right_arm_liaopan_dmp_place_v1/run_1794216841515922914/result.json`，PLACE_CENTER_COMPLETE。

- 料盘烘干箱下中 `right_arm_liaopan_hongganxiang_place/run_1794383252441911735/result.json`，PLACE_CENTER_COMPLETE。

- 筛网天平 `right_arm_shaiwang_cheng_place_v1/run_1794554796221507249/result.json`，PLACE_CENTER_COMPLETE。

以上路径位于现场 `worklog/evidence/demo-runs/` 下。最近一次运行、完整成功、当前接受版本分别维护。
