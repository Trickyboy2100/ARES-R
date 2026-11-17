# 放置功能与参数

## 共同流程

以已确认持物状态启动 → 确认目标工位与槽位 → 新鲜检测/场景 → 计算预放置位 → cuRobo自由空间运动 → 工装约束下进入或下降 → 松爪与释放回读 → 退出工装 → 按该功能合同回center → 完整结果。

当前共用实现为 `scripts/run_dmp_place_demo.py` 的 `detect_place_target()`、`stage_place()`、`stage_center()`，通过 `--demo-id` 选择任务参数与证据目录。部分历史下降/退出使用控制器MoveL，原生成功语义按版本保留。

## 当前实机参数对照

偏置为检测结果上的BODY平移，单位mm。下降列沿BODY Z−，退出按当前参数为BODY X−40mm。

| 原生 / ROS | 物体与工位 | 5700配置 | 预放置偏置[X,Y,Z] | 下降 | 实机状态 |
|---|---|---|---|---|---|
| AD1P0 / RD1P0 | 筛网→除尘收料专机 | 2 | [-23,-410,+100] | 60 | 11月9日完整成功 |
| AD2P0 / RD2P0 | 料盘→除尘收料专机 | 2 | [0,+5,+20] | 20 | 11月9日完整成功；表内当前V7与当次绑定待核对 |
| AB2P5 / RB2P5 | 料盘→烘干箱下中 | 3 | [+70,-315,+303] | 30 | 11月11日完整成功 |
| AC0P0 / RC0P0 | 筛网→天平 | 8 | [0,0,+100] | 100 | 11月13日完整成功 |
| AA0P0 / RA0P0 | 料盘→天平 | 9 | [0,0,+60] | 60 | 近期仅规划记录 |

以上数值是已读源参数，文档更新不会写回运动配置。每项姿态偏置、速度及工具选择以绑定的完整参数文件为准。

## AD1P0 筛网放专机

沿用 `right_arm_dmp_place_v1`、`demo-5-main-dmpplace`。检测ID2→预放[-23,-410,+100]mm→下降60mm→释放→退出40mm→center。完整结果为 PLACE_CENTER_COMPLETE。优先做现有执行器到ROS的接口适配及结果传播，复用原生成功链。

## AD2P0 料盘放专机

沿用 `right_arm_liaopan_dmp_place_v1`、`demo-6-liaopan-placetoDMP`。检测ID2→当前预放[0,+5,+20]mm→下降20mm→释放→退出40mm→center。旧卡片10mm描述已过时。原生11月9日成功可作基线，当前11月11日V7参数需与当次快照对齐。

## AC0P0 筛网放天平

沿用 `right_arm_shaiwang_cheng_place_v1`、`demo-7-shaiwang-placeto-cheng`。ID8→预放高100mm→下降100mm→释放→退出40mm→center。11月13日完整成功。本地L04适配回放已完成，现场ROS注册信息落后，应先同步映射再验收ROS完整调用。

## AA0P0 料盘放天平

沿用 `right_arm_liaopan_cheng_place_v1`、`demo-1-liaopan-placeto-cheng`。ID9→预放高60mm→下降60mm→释放→退出40mm→center。现存近期结果为PLANNED_ONLY，完整实机结果待补。旧“称/程”名称先映射为A0提案，现场工位名称与参数归属需要一次确认。

## 烘干箱六项放置

| 原生 / ROS | 泊位 | 参考识别 | 参数来源与工作 |
|---|---|---|---|
| AB1P1 / RB1P1 | 上左 | ID3参考点策略待该站确认 | 单独泊位偏置、上层交接与进入/退出参数 |
| AB2P2 / RB2P2 | 上中 | ID3参考点策略待该站确认 | 单独泊位偏置、上层交接与进入/退出参数 |
| AB3P3 / RB3P3 | 上右 | ID3参考点策略待该站确认 | 单独泊位偏置、上层交接与进入/退出参数 |
| AB1P4 / RB1P4 | 下左 | ID3参考点策略待该站确认 | 下层交接、上方隔板净空、该槽偏置 |
| AB2P5 / RB2P5 | 下中 | 已有ID3实机链 | 复用11月11日成功版本 |
| AB3P6 / RB3P6 | 下右 | ID3参考点策略待该站确认 | 下层交接、上方隔板净空、该槽偏置 |

AB2P5 当前 `berth_reference.slot_id=lower_middle`，放置偏置BODY[+70,-315,+273]mm，预放置再加30mm。完整成功包括放置释放和回center。

旧实现直接读取 `preplace_offset_body_m`，`berth_reference`仅记录来源。WebUI修改泊位注册表后，该旧脚本不会自动读取新值。后续统一解析时应一次性绑定解析结果和版本，防止重复叠加偏置。

新六槽能力的共同目标链为 `T_BODY_REFERENCE × T_REFERENCE_SLOT × T_SLOT_PLACE_TCP`；再按工装方向生成preplace/entry/exit。现有BODY offset实现保持原版本解释，只有经过一致性比较后才迁移矩阵链。

## Place完成定义

完整完成至少覆盖到位、释放回读和退出工装；需要回center的版本还须完成center到位回读。历史成功结果 `PLACED_AND_RELEASED` 与 `AT_CENTER` 同时存在时才记录该版本完整成功。到预放置点、规划通过、请求被接收各有单独状态。

当前读到的完整放置成功证据及参数版本见[证据索引](08-evidence.md)。
