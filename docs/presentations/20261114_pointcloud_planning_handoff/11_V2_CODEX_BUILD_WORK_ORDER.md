# Codex立即接手：原模板14＋2页验收“研发工作量”PPT制作任务书（2026-11-14 V2）

**目标**：完成可以给甲方阶段验收使用的PPTX，清楚回答“干了哪些研发工作、怎样比较、怎样定位失败、改哪里、如何复测”；突出点云重建和机械臂规划控制。不是再做9页算法科普，也不复制40页方法大稿，不追加大模型/强化学习的仿真作为实机成果。

## 0. 先定位仓库与本分支

```bash
git fetch origin
git switch docs/acceptance-workload-draft-20261113
git pull --ff-only origin docs/acceptance-workload-draft-20261113
git status --short
```

阅读顺序：本目录README→08_V2_NARRATIVE_AND_WORKPACKAGES→12_V2_PROVENANCE_AND_QA_GATES→09_V2_SLIDE_CONTRACT_14_PLUS_2→10_V2_MATERIAL_AND_LOCAL_PPT_LOCATOR→本文件→01–07历史材料。旧02的16页是文本恢复，遇冲突以新12和原始runlog为准。

**安全**：本任务是离线资料与PPT制作。不得以试验为名连接/移动JAKA、夹爪、AMR、相机或现场专机；不得重启或修改设备服务；不得运行未核查的online脚本/原生控制命令；不得切换/覆盖研究、生产分支，禁止强推。

## 1. 原始参考的硬性前置

先定位 `PPT-TEMPLATE`、`PPT-METHOD`、`PPT-LARGE`（名称及精确本机搜索见10）。逐一记录abs_path_private, bytes, SHA256, slide_count, slide_size, masters/layouts, notes_count, media_count。未找到原PPT时**停止“宣称模板继承的PPT定稿”**；但可继续整理源图索引/备注/原生表格数据，不应回到自制白底模板。

原模板以实际母版为准，保留页眉标志、固定分隔线、字号基准、页面比例和页脚；修改内容区的文字/图片/形状排布即可。中文黑体、英文与数值Arial为主，辅助中文宋体/英文Times New Roman；OOXML里东亚/Latin字体都核查。

原PPT可本地使用，不代表允许自动提交public repo；如需归档，先检查版权、隐私、专有研发信息，经确认再提交。不要向用户提供猜测的Mac路径。

## 2. 严格执行逐页合同

以09为唯一最新逐页内容合同；14正文＋2明确待执行的附页。画面以旧周报真实图片为主，所有模型生成图必须能绑定run ID/数据集，不能只因漂亮就替代清晰实证。

对于每页：
- 先写一句“需要评委带走的结论”。
- 选固定数据集ID，再按12选择结果，不跨场景拼证据。
- 画面：一个主证据＋小表/改动框；允许两张同视角old/new，禁止4–6张难辨认图拼墙。
- 备注：需求/失败表现→定位过程→代码修改点→复测条件→可说结论→不可说结论→原始文件路径。
- 作为过程图的箭头可用模板原生形状，不用AI虚构几何仿真实验或假“前后成功率”。
- 原始图片没有可读的局部关系时，直接裁出真实ROI，注明“显示裁切，不改变计算边界”。

## 3. 数据展示优先级

第3页：将cleanup_benchmark.json做成真正三组前置净化比较，明确ε/m是固定参数不是扫值结果；首组冷启动耗时不做纯性能对比。

第4–6页：用真实误碰撞归因图说明为什么不删212点，随后9/21 CLEAR同源7→167、−58.8%与点覆盖。10/10 CAMERA 32→235可作另场景补充，不写旧失败。

第7–12页：突出项目自己的接口一致性/工具模型修订/失效门禁/近障起点策略/执行反馈，而不是大量展示cuRobo数学原理。第11页planning-only不能与第12页实机数值合为单次对照。

第13页：三项CPU模块分别画原生对照条，文本标明不是GPU/整任务加速。

第14页：以真实跨工位取放证据收束，保留故障后恢复而非“无故障独立连续成功”。

第15–16页：仅附录，明显水印“补证方案 / 未执行”，无实测单元保持空白/待测。若Codex真的离线生成新测值，必须保存完整输入SHA、运行命令、环境、日志并单独标“2026-11-14之后的新复测”，不重写历史。

## 4. 必须检查源码/证据而不是相信旧稿

| 领域 | 源头 |
|---|---|
| 半径/统计滤波、DBSCAN默认参数 | src/ares_r/perception/residual_cloud.py + 9/21 cleanup_benchmark.json |
| 支撑层/凸起分解、碰撞桥接局部细分 | src/ares_r/perception/support_decomposition.py + 9/21 P3.1报告 |
| 自体归属 | src/ares_r/perception/robot_owned_filter.py |
| 当前关节映射修复 | 提交8fbd669 + 相关测试 |
| 目标IK/curobo接口 | src/ares_r/motion/runtime_goal_ik.py, production_scene_worker.py |
| 独立world距离和自碰边界 | src/ares_r/motion/independent_path_validation.py（self_collision_independently_checked=false） |
| D1实机 | docs/reports/2026-09-23_P3_6_SCENE_AWARE_MOTION_REPORT.md |
| P3.7任意目标运动 | docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md |
| 任务耗时真相 | docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md |
| RASC原图 | docs/presentations/assets/20261028_rasc_curobo/{README.md,INPUT_INDEX.md,ASSET_MANIFEST.json} |
| GRASP V3 | docs/presentations/assets/20261028_rasc_curobo/grasp_v3/{README.md,VISUAL_MANIFEST.json} |

## 5. 工作流程、产物及验收

### Phase A：原件与素材审计
输出：`output/source_ppt_manifest_public.json`（basename+SHA/slide count；绝不公开private Mac路径）、`output/source_media_index.csv`、三个contact sheet、每页媒体拆分文件。若原件找不到，缺口清单里明确写出，绝不用替代母版。

### Phase B：16页原模板初排
每页完成notes（不能只留一句）、证据脚注、真实图；不把备注中的“建议/注意”放成面向领导的结果。成稿至少包含14页正文＋2附页，共16页；如有封面，封面从原模板取、并另在QA报告写其是否计入16页。

### Phase C：逐页渲染审查（两轮）
使用PowerPoint/LibreOffice渲染（Mac优先PowerPoint实际渲染），导出每页PNG与PDF。首轮检查文字越界、内容密度、图表缺图、Logo、页边距、公式上下标、中文/英文字体；修订后第二轮按同样清单检查，并把before→after记录在QA日志。不得只看pptx能打开就算通过。

### Phase D：证据有效性自审
对每页图中数值追溯到runlog；检查dataset_id和camera_sha；将S21-CLEAN/S21-CLEAR7/S10-CAMERA/S21-GRASP-V3区分；确保9/21 planning-only与9/23/24物理执行分开；GPU内self-collision≠独立self-collision；两条abort ServoJ曲线不用成功证据。

### Phase E：交付与归档
- `output/点云场景重建与机械臂规划_研发工作量汇报_原模板14加2页.pptx`，真实可打开
- `output/preview/slide-01.png…slide-16.png`与完整联系表
- `output/点云场景重建与机械臂规划_研发工作量汇报.pdf`（环境支持）
- `output/speaker_notes.md`（所有16页）
- `output/slide_sources.csv` / `output/metric_source_ledger.json`
- `output/qa_report.md`，记录两轮问题、修改、仍存在缺件
- `output/source_media_index.csv`、`output/source_ppt_manifest_public.json`
- `output/asset_missing_or_proposed.md`：缺真实图、缺原始视频、未执行补证、无法量化的口径
- 提交文档与可公开的结果，按repo协作规范推送到**自己的文档分支**；回报完整commit与文件入口。

## 6. 质量门禁 / 退回制作的情况

- 使用新建主题而不是原模板；中文和英文被统一设成错误字体；页脚/Logo丢失。
- 主图来自Codex低清画框而未试原周报原嵌媒体；不同源图做统一统计。
- 把没执行的DBSCAN扫值/2×2消融用AI生成热力图“填满”，或把录音举例5次重试说成现场事实。
- 表达“cuRobo是项目原创/训练所得”；历史9/21 A/B被说成实机；10/10 OLD失败NEW成功；GRASP V3两世界硬拼。
- 无效计划/自碰判定说得比源码更强；模块加速当成整个Demo加速。
- 不写任何讲者备注；数值没有单位/源；未做逐页真实渲染就宣称完成视觉自审。

## 7. 上台讲述的关键转换

不要在每页重复“用到了DBSCAN、cuRobo”。应不断回答：
- “我们最初看到了什么错误/不足？”（真实截图+告警）
- “当时检查了哪些对象？”（同源点、robot-owned、AABB、TCP、场景SHA等）
- “我们写了/改了哪条规则或哪种数据合同？”（具体文件/接口）
- “复测用的输入是否与之前一致？”（是则A/B；否则注明不同工况）
- “结果支持什么、不支持什么？”（报告值与限定）

可将具体函数名/JSON路径/算法原理放Presenter Notes，面向领导的正文突出明确的研发判断与图表，不用硬塞公式提高“技术感”。

**成功定义**：用户无需二次解释就能让甲方看出“有问题、查证、编程、对照、复测、落地”的研发工作，而不是相信一组没有过程的最终数字。