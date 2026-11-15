# V4 Codex启动提示（可直接复制）

请在本机ARES-R工作区执行V4甲方验收PPT制作。**先完整阅读以下四份任务书，再开始操作：**

1. docs/presentations/20261114_pointcloud_planning_handoff/19_V4_MASTER_TASKBOOK.md
2. docs/presentations/20261114_pointcloud_planning_handoff/20_V4_PAGE_COPY_AND_LAYOUT.md
3. docs/presentations/20261114_pointcloud_planning_handoff/21_V4_ASSET_MAP_AND_MANUAL_PREP.md
4. docs/presentations/20261114_pointcloud_planning_handoff/22_V4_EXPERIMENT_AND_QA_PROTOCOL.md

本次目标不是修改旧16页半成品，而是按20号文件重新制作：**1页封面＋14页正文＋最多3页技术附录**。甲方要看的是实际研发过程和工作量：点云参数实验、几何分解、规划参数比较、接口实现、GPU运行时优化、轨迹控制适配、实机验证、故障诊断与恢复。不能做成算法科普或最终成果图集。

执行顺序：
1. 审计ARES-R当前分支、ARES仓库、全部报告/JSON/runlog/代码和现有图集；
2. 按21号文件在本机查找原母版、大PPT、方法PPT和此前周报；先从repo提取素材，找不到才请求用户补缺；
3. 从codex/data-grasp-20261021-public分支取回两份已公开点云归档，核验SHA；
4. 按22号文件尝试完成DBSCAN ε×m九组真实离线实验。只改变DBSCAN两个参数，其他输入和上游处理固定；不连接任何硬件；
5. 形成逐页evidence_matrix、media_index和metric_source_ledger；
6. 严格按20号文件的页面标题、上屏文稿、数据和讲者备注制作PPT；
7. 完成PowerPoint/LibreOffice两轮真实渲染和技术/视觉/甲方要求三类QA。

**字体和模板要求不能偏离：**
- 必须继承原始“生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx”的母版、Logo、页面比例、页眉页脚和红色视觉元素；
- 中文主字体黑体，英文/数字主字体Arial；
- 中文辅助字体宋体，英文辅助字体Times New Roman；
- 公式单独处理字体、上下标和符号；
- 检查OOXML中的East Asian和Latin字体设置。
美观、图文比例、对齐、留白、图表和精细排版由你负责，但不得为了视觉效果改变事实或省略研发过程。

关键纪律：
- 不得把不同dataset拼成同一组A/B；
- 不得把planning-only写成实机；
- 不得把模型gap写成物理测距；
- 不得把P3.3的12次负结果改写成成功；
- 不得把10/19 Golden recovery写成无人干预一键全链；
- 不得把P3.8E模块时间或P3.9估计写成全任务实测；
- 不得编造参数、失败、重试次数、成功率、耗时或实验图片；
- 不得修改生产代码、生产配置、安全门限或连接机器人/相机/底盘；
- 私人PPT绝对路径和未经确认的原件不提交public GitHub。

如果某页的补证无法完成，使用任务书规定的真实回退文稿，明确区分“已完成”和“未执行”，不要停下整个制作，也不要造数据。若原母版在本机确实找不到，先完成素材审计和证据准备，向用户提出仅补充缺失的原PPTX，不要自制替代模板。

交付目录、文件名和QA要求按19号任务书第7–9节执行。完成后回报：
- 使用的母版文件SHA、页数和比例；
- 14页正文每页实际采用的source/media；
- DBSCAN补证是否完成及结果；
- 缺失的原始素材；
- PPTX/PDF/逐页PNG/notes/evidence matrix/QA报告路径；
- 两轮渲染发现并修复的问题；
- 仍然存在的证据边界。
