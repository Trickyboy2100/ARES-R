# V5 甲方验收研发工作量汇报重设计（2026-11-16）

**当前唯一有效的Codex执行入口：**

[20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md](20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md)

V5在重新审查甲方11/13录音、10/28讨论、用户上传的16页旧稿/PDF/讲者备注/来源表/指标台账/QA，以及ARES-R代码、实验报告、Golden任务和原始媒体索引后，重新组织为：

- 1页研发总览；
- 2页点云场景重建；
- 4页cuRobo适配、轨迹生成、参数调试与部署优化；
- 3页ARES-R运行时、实机执行、Golden恢复和性能审计。

## 关键事实修正

1. **10/19的230mm连续抬升和1.53m单程转运是真实物理阶段。** 原始全链在PLACE阶段发生故障，修订持物几何后从PLACE检查点接续恢复；不能写成“没有实际抬升”，也不能写成“不中断的无人值守完整循环”。
2. **10/17的多次失败数据需找到原始run/事件日志后才能使用。** 当前公开repo尚未找到对应原始审计报告，找不到则从PPT正文删除。
3. **DBSCAN ε×min_points历史敏感性矩阵尚未执行。** 已有S21-CLEAN仅比较前置密度滤波，DBSCAN 12mm/8点固定；有真实原始点云时才补9组离线对照。
4. cuRobo是成熟求解引擎；项目研发在JAKA/工具/场景/目标IK/种子/求解配置/独立核验/ServoJ与任务恢复适配，不能包装成重新发明cuRobo。
5. FAST单次求解、普通plan_cspace和图搜索尝试不是同一条路径；PRM不得写成每次规划都会执行。
6. 独立密集核验覆盖环境和工具几何；独立自碰撞核验未完成。
7. 10/10 CAMERA、9/21 CLEAR、10/21 GRASP V3等数据集必须分开标注；10/21 GRASP严格几何A/B端点碰撞，不能写成严格A/B规划成功。
8. P3.3是12次planning-only负结果；P3.6/P3.7才是相应的真实实机执行证据。P3.8E是AUDIT_ONLY关键路径审计，不是完整任务周期实测。

## 历史文件

- [20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md](20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md)：唯一执行令。
- [19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md](19_V4_10_SLIDE_REDESIGN_AND_CODEX_EXECUTION_ORDER.md)：历史版本，已标记SUPERSEDED；不得执行。
- [17_V3_OFFLINE_REPLAY_AND_EXPERIMENT_PROTOCOL.md](17_V3_OFFLINE_REPLAY_AND_EXPERIMENT_PROTOCOL.md)：离线补证方案参考。
- [16_V3_ASSET_AND_REFERENCE_CROSSWALK.md](16_V3_ASSET_AND_REFERENCE_CROSSWALK.md)：历史素材交叉索引。
- [14_V3_REAL_EVIDENCE_PRIORITY.md](14_V3_REAL_EVIDENCE_PRIORITY.md)：历史证据优先级参考。
- 原16页PPT、PDF、讲者备注、指标台账、slide_sources和QA文件只作为旧稿审计与数据追溯材料。

## 制作边界

不修改生产机器人代码或配置；不连接设备；不执行机械臂、夹爪或AMR运动；不自动SSH；不下载新私有数据。公开repo只提交经审核的任务书、无敏感索引和安全衍生材料。PPTX/PDF、私有原图、视频、原始点云和运行日志保留在本机交付目录。
