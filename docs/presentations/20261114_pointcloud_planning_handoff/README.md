# ARES-R 点云场景重建与机械臂规划：验收工作量PPT接手包

**当前状态：已完成第二轮内容深化并推送；原始参考PPTX二进制仍未在本分支；尚未制成符合原模板的最终PPTX。** 本仓库为public，原始现场/专有材料需审查后上传。

## Codex立即开始（2026-11-14 V2，优先级高于旧文稿）

1. [11_V2_CODEX_BUILD_WORK_ORDER.md](11_V2_CODEX_BUILD_WORK_ORDER.md) —— 可直接执行的制作任务、模板纪律、证据检查、输出要求。
2. [09_V2_SLIDE_CONTRACT_14_PLUS_2.md](09_V2_SLIDE_CONTRACT_14_PLUS_2.md) —— **14页正文＋2页补证**逐页制作合同，具体哪张图、哪个实验、哪些数字、讲什么以及不能说什么。
3. [12_V2_PROVENANCE_AND_QA_GATES.md](12_V2_PROVENANCE_AND_QA_GATES.md) —— **13组实验数据严格分离**；防止9/21 CLEAR、10/10 CAMERA、10/21 GRASP等互相嫁接。
4. [10_V2_MATERIAL_AND_LOCAL_PPT_LOCATOR.md](10_V2_MATERIAL_AND_LOCAL_PPT_LOCATOR.md) —— 原始PPT精确文件名（Mac绝对路径当前未知）、macOS精确搜索命令、repo图集与旧周报可用素材、原媒体提取要求。
5. [08_V2_NARRATIVE_AND_WORKPACKAGES.md](08_V2_NARRATIVE_AND_WORKPACKAGES.md) —— 录音需求的研发工作量表达、7个项目工作包、三条真实故障/修复证据线。

**一句话要求**：围绕“发现问题—参数/模型/接口对照—代码与数据处理改动—可核查的复测—可交付的研发能力”，而不是复述DBSCAN或cuRobo基础算法原理，也不编造调参/训练/实机成功结果。

## 已在分支内的既有文件（可读，但遇冲突以V2为准）

- [01_DECISIONS_AND_REQUIREMENTS.md](01_DECISIONS_AND_REQUIREMENTS.md)：原模板、字体、证据纪律。
- [02_DRAFT_14_PLUS_2.md](02_DRAFT_14_PLUS_2.md)：旧16页文字/演讲备注恢复（**内容半成品，视觉不合格**；存在后续修正项）。
- [03_EVIDENCE_LEDGER.md](03_EVIDENCE_LEDGER.md)：第一次证据梳理与问题核查。
- [04_ASSET_MAP.md](04_ASSET_MAP.md)：第一次仓库资产索引。
- [05_CODEX_CONTINUE.md](05_CODEX_CONTINUE.md)：第一次接手指令；**已由11_V2_CODEX_BUILD_WORK_ORDER.md更新**。
- [06_SOURCE_TRANSFER_STATUS.json](06_SOURCE_TRANSFER_STATUS.json)：原始二进制转存状态（仍为缺失），不可把文字摘录说成原件。
- [07_RECORDING_REQUIREMENTS.md](07_RECORDING_REQUIREMENTS.md)：14分57秒沟通录音中与制作有关的摘要与时间定位。
- [references/](references/)：原验收模板/方法PPT/大PPT的**文字**恢复，非二进制。
- [tools/](tools/)：旧归档/校验工具源码，**尚未在本轮故障容器执行**。
- [WORKLOG.md](WORKLOG.md)：真实交接过程、未执行范围和追加提交记录。

## 仓库已经有的公开图集

- [RASC/cuRobo图集](../assets/20261028_rasc_curobo/README.md)
- [GRASP V3](../assets/20261028_rasc_curobo/grasp_v3/README.md)
- [清晰局部剖切V2](../assets/20261028_rasc_curobo/clarity_v2/README.md)

素材清晰度优先级：**原周报/PPT高清原图 > repo可追溯独立局部图 > 对原数据重绘的原生可编辑图 > 清晰标注的机制示意**。不要把不清楚的Codex合成图堆到最终PPT。

## 当前缺件和实情

1. 未知Mac实际绝对路径的原参考PPT：`生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx`、`20261028-水分细度目标识别与场景自适应规划控制-2.pptx`、`20261028-水分细度目标识别与场景自适应规划控制.pptx`；另有旧14＋2视觉半成品PPTX。具体见10。
2. 补证第15页DBSCAN ε×m扫值和第16页支撑层×局部细分消融**尚未执行**。只有完成新实验、归档数据才能变成实测结果。
3. 本次文档更新没有运行相机、GPU求解、JAKA运动、ROS业务软件或任何新实验；不能将整理工作当成研发实验完成。
4. 资料分支从冻结证据基点`8da63a6caf4d7d9ac17dc226362e43c77a6f21d5`衍生。不改生产代码、不覆盖main、不涉及另一研究分支。

## 新版PPT完成门槛

真实模板继承；所有14＋2页有讲者备注；每个实验图和统计具有源与数据组；两页未执行实验明确隔离；真实大PPT最后媒体逐页解包；两轮完整渲染检查；最终PPTX可打开；提交来源清单和QA日志。**不以交接文档替代PPT交付。**
