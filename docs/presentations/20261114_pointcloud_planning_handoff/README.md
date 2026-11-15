# V4 研发工作量汇报重设计：10页证据链方案（2026-11-15）

**当前唯一有效的执行入口：**
[19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md](19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md)

本轮已重新核对甲方11/13录音、10/27沟通纪要、10/28两次讨论、用户上传的20261030验收模板、20261028大稿/方法版、2025参考汇报、2026视觉汇报、历史周报、旧16页PPT/备注/来源表/QA，以及ARES-R中真实代码、实验报告、JSON、图片和执行记录。

## V4决定

- **交付10页正文，不增加封面**；唯一母版为20261030V0.95机械臂验收模板。
- 只围绕两项工作：点云场景重建与碰撞几何编译（RASC）；cuRobo机械臂规划适配、参数调试、独立核验和JAKA执行控制。
- 由“技术模块介绍＋最终结果”改为“工程问题→具体研发/参数试验→对照→验证与边界”。
- V2的14+2页和V3的12页故事板降级为历史资料；制作时必须以19号V4文件为准。
- DBSCAN ε×min_points实验是甲方明确点名的P0补证。必须先找回授权可用的真实原始点云；找到后执行9组离线对照；找不到则明确记录缺失，绝不从截图恢复点云或编造结果。
- 不修改生产机器人代码/配置，不连接设备，不执行机械臂、夹爪或AMR运动，不自动SSH，不下载新私有相机数据。
- 原始PPT二进制、私有点云、现场日志和最终PPTX/PDF保留在本机交付目录；公开仓库只保存经审核的任务书、可公开索引和安全衍生材料。

## 必须遵守的关键证据修正

1. **10/19不能写成完整自主取放闭环成功。** 10/17记录了多次失败、一次部分抓取/接近和人工干预后的100mm抬升，剩余130mm未执行；10/19有PLACE故障后的分段接续恢复，但不是不间断自主全流程。
2. 10/19的230mm连续抬升只有规划/执行前验证，没有实际运动，不得写成已实机完成。
3. S21-CLEAN、S21-SUPPORT/CLEAR7、10/10 CAMERA、10/21 GRASP V3、P3.3、P3.4、P3.6、P3.7等不同日期/不同输入的数据必须分开标注，不能拼成同一A/B。
4. 9/22 P3.3是同一AVOID A→B场景四档激活距离×3次，12/12未通过当时30mm门槛；这是planning-only负结果，不是硬件运动。
5. 10/10 CAMERA的32→235、3,747/3,747、体积和减少40.9%，与10/21 GRASP V3的19→405、8,100/8,100、体积和减少68.6%是两组独立数据。
6. 10/21 GRASP V3严格几何A/B端点碰撞，另一接触豁免world的GPU成功不能写成严格A/B规划成功。

## V4文件与历史参考

- **[19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md](19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md)**：唯一执行令；10页故事板、逐页素材/数据、DBSCAN离线协议、版式、QA和交付。
- [17_V3_OFFLINE_REPLAY_AND_EXPERIMENT_PROTOCOL.md](17_V3_OFFLINE_REPLAY_AND_EXPERIMENT_PROTOCOL.md)：原始点云定位与9组DBSCAN、支撑分解2×2离线协议；保留其可用技术细节，以19号文件为准。
- [16_V3_ASSET_AND_REFERENCE_CROSSWALK.md](16_V3_ASSET_AND_REFERENCE_CROSSWALK.md)：原PPT页/shape媒体索引和仓库图集索引。
- [14_V3_REAL_EVIDENCE_PRIORITY.md](14_V3_REAL_EVIDENCE_PRIORITY.md)：历史证据优先级，须按19号文件中的状态修正使用。
- [13_V3_RETHINK_FROM_CUSTOMER_RECORDING.md](13_V3_RETHINK_FROM_CUSTOMER_RECORDING.md)、[15_V3_REBUILT_STORYBOARD_12_PLUS.md](15_V3_REBUILT_STORYBOARD_12_PLUS.md)、[18_V3_CODEX_EXECUTION_AND_ACCEPTANCE.md](18_V3_CODEX_EXECUTION_AND_ACCEPTANCE.md)：历史分析/12页建议，不能再直接作为本轮页序。
- [09_V2_SLIDE_CONTRACT_14_PLUS_2.md](09_V2_SLIDE_CONTRACT_14_PLUS_2.md)、[11_V2_CODEX_BUILD_WORK_ORDER.md](11_V2_CODEX_BUILD_WORK_ORDER.md)：旧14+2方案，已废止。
- [WORKLOG.md](WORKLOG.md)：本轮重设计文档写入记录与未执行范围。

## 重要事实

V4重设计任务书已经写入repo；**新PPTX/PDF尚未制作**。原始PPT二进制和私有实验数据不因本README或历史媒体索引存在而自动进入GitHub。Codex必须在实际运行机器上定位原件、计算SHA并逐项复核。