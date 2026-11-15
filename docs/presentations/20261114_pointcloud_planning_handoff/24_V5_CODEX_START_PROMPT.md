# V5 Codex启动提示（直接复制给Codex）

请在本机ARES-R工作区执行甲方研发工作量汇报PPT制作。先完整阅读以下文件，尤其是20号V5主任务书；**V5是唯一有效制作依据，V4/V3均为历史参考，不得按旧页数执行。**

1. docs/presentations/20261114_pointcloud_planning_handoff/20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md
2. docs/presentations/20261114_pointcloud_planning_handoff/21_V5_PAGE_COPY_AND_LAYOUT.md
3. docs/presentations/20261114_pointcloud_planning_handoff/22_V5_ASSET_MAP_AND_MANUAL_PREP.md
4. docs/presentations/20261114_pointcloud_planning_handoff/23_V5_EXPERIMENT_AND_QA.md

**目标：10页正文，不另加封面。** 10页分别按21号文件制作：研发总览、点云场景重建、参数与几何保真、cuRobo工业适配、运行时目标到关节轨迹、P3.3碰撞参数负结果、P3.4求解器部署优化、P3.6/P3.7实机验证、10/19 Golden PLACE恢复、P3.8E/P3.9/CPU性能与交付边界。

执行顺序：
1. 先只读审计ARES-R、ARES、报告、JSON、runlog、代码、图集和原始媒体；
2. 在本机授权目录定位原母版、大PPT、方法PPT和周报；优先使用repo已有图集和历史媒体，不要先向用户索要新图；
3. 核对10/19 Golden的230mm真实物理抬升和1.53m转运，以及PLACE故障后恢复的准确边界；
4. 10/17失败数字必须找到原始run/event log、run ID、SHA和事件顺序才可使用；找不到就从正文删除；
5. DBSCAN ε×m历史敏感性矩阵没有现成结果。先找S21-CLEAN/S21-CBASE真实原始点云；若缺失，可用公开10/21 GRASP数据做新增离线研究，但必须标为新数据/新日期，不能冒充9/21历史实验。绝不编造九组结果；
6. 生成媒体索引、证据矩阵和讲者备注；
7. 严格按V5 10页文稿制作；
8. 完成两轮渲染和技术/视觉/甲方要求QA。

母版和字体要求：
- 必须继承原始“生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx”；
- 保留BBMG Logo、红色页眉、分隔线、页脚、页面比例和母版组件；
- 中文主字体黑体，英文/数字主字体Arial；
- 中文辅助宋体，英文辅助Times New Roman；
- 公式单独处理字体、上下标和符号；
- 检查OOXML的East Asian和Latin字体设置。
页面美观、精细排版、图文比例、对齐、留白、图表、字体字号和渲染由你负责，但内容和证据边界以V5为准。

绝对禁止：
- 按V4的14页或V3的12页制作；
- 另加封面挤掉10页正文；
- 把10/19的230mm抬升写成规划预览，或把PLACE恢复写成不中断无人干预全链；
- 把10/17聊天审计摘要数字写成原始运行证据；
- 把S21-CLEAN前置滤波说成DBSCAN ε×m参数寻优；
- 把不同数据集拼成同一次A/B；
- 把P3.3的12次负结果写成成功；
- 把P3.6/P3.7的模型gap写成物理测距；
- 把独立world核验说成独立自碰撞认证；
- 把P3.9的395s估计写成实测；
- 把P3.8E的400.25s写成完整取放周期；
- 把CPU模块加速倍数宣传成端到端加速；
- 把PRM/图搜索写成每次规划都会执行；
- 编造参数、失败、重试、成功率、耗时、训练过程或实机视频；
- 修改生产代码、设备配置、安全门限，连接相机/机械臂/夹爪/AMR或自动SSH。

用户手动准备原则：
- 不要求用户重新制作图片、录屏、截图或上传点云；
- 先从ARES-R repo和codex/data-grasp-20261021-public数据分支取材；
- 先在本机搜索原始模板、大PPT和方法PPT；
- 只有本机确实找不到上述核心PPTX时，才请求用户复制缺失文件到ARES-R/.local/acceptance_sources/（该目录必须gitignore）。

交付到本机output/acceptance_v5/：PPTX、PDF、10页PNG/contact sheet、speaker_notes.md、evidence_matrix.csv、slide_sources.csv、media_manifest.csv、metric_source_ledger.json、technical_qa.md、visual_qa.md、customer_requirement_check.md、missing_assets.md及DBSCAN_INPUT_STATUS.md。未经审核的原始PPT、点云、视频、录音和私人绝对路径不提交public GitHub。

若DBSCAN补证无法完成，使用V5规定的真实回退内容并明确边界，继续完成其余页面，不要停工或造数据。
