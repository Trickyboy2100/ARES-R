# Codex V6增量修订执行令（直接复制）

目标：**以用户刚上传的10页 \`ARES-R_甲方研发工作量汇报_V5.pptx\`为母件，制作16页V6内容增强版。不得完全重做，也不能仅修改标题和字体。**

先阅读：
1. \`25_V6_INCREMENTAL_REDESIGN_AND_V5_AUDIT.md\`：实际V5页面问题与增量设计原则；
2. \`26_V6_STORYBOARD_16_SLIDES.md\`：16页逐页内容、可直接上屏文稿、素材、讲述脚本、证据边界、V5→V6页映射；
3. \`27_V6_MEDIA_ENRICHMENT_AND_CODEX_EXECUTION.md\`：repo和本机PPT素材索引、图片裁切规范、执行顺序和QA；
4. 继承的\`20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md\`、\`21_V5_PAGE_COPY_AND_LAYOUT.md\`、\`23_V5_EXPERIMENT_AND_QA.md\`，其中事实与实验边界继续有效。若V5旧页序与V6冲突，**V6页序优先**。

核心要求：

- V5的10页结构、证据、模板和已经写好的讲者备注是**保留资产**。先另存V6工作副本，使用REUSE、SPLIT、INSERT增量编辑，不从零建一个“类似风格”的PPT。
- **增加真实图片丰富度和讲述生动性**：重点提取20261028 60页大PPT的单个媒体（尤其45–60页），9/24周报，ARES-R GRASP V3六阶段点云、10/10旧新几何、9/21 CLEAR/AVOID/BLOCK、P3.3真实净空试验、ServoJ轨迹、P3.6 D1、P3.7实机和10/19 Golden恢复。真实图必须裁切ROI、放大主体、用原生文字标注；禁止贴整页低清图片凑图。
- 将V5第03页**11月16日DBSCAN九组结果**拆成独立主讲页。先找到本机\`dbscan/results.json\`和原始图；没有原始九图不能伪造点云图。不能把“保留点多”直接说成最佳。
- 将V5第07页拆成“cuRobo种子/Graph/常驻服务”和“JAKA ServoJ速度跟踪”，第08页拆成D1和五段运行时目标，第09页拆成“持物模型错误”与“Golden检查点恢复”。新增“10/10 CAMERA误占据的同源old/new”和“9/21 CLEAR/AVOID/BLOCK”的过程页。
- 每页正文**能直接看见真实研发证据**，而不是只有术语和一张配置表；用实际故障/调参/现场图片引出原因，再给对照和工程判断。
- 严格区分S21-GRASP-V3、S10-CAMERA、S21-ATTR、S21-CBASE、P3.3、P3.4、P3.6、P3.7、10/19 Golden和P3.8E/P3.9。不能跨数据组制造“前后增益”。
- 10/19的230mm抬升与约1.53m转运已经物理完成；PLACE故障后从检查点恢复，不是无人干预连续全链。P3.3 12/12未过30mm，planning-only，不是实机。独立world核验不等于独立self-collision认证。
- 原模板：20261030V0.95机械臂验收模板，必须继承V5中已经保留的BBMG标识、红线、页脚、16:9。字体：中文主黑体、英文数字主Arial、辅助宋体/Times New Roman、公式单独处理。美观和排版由Codex精雕，不能因塞字把图缩小。
- 不连接机器人/相机/底盘、不SSH、不更改生产代码或碰撞安全限制。制作只涉及离线已有素材；未经审核不向公共GitHub提交原件、视频、现场点云、私人绝对路径。

执行输出：
1. V5原件SHA/源媒体扫描和\`v5_to_v6_slide_map.csv\`；
2. \`source_media_manifest.csv\`、60页大PPT全部原图contact sheet（尤其后16页）；
3. 16页V6 PPTX/PDF和逐页PNG；
4. 完整speaker notes、slides来源账本、DBSCAN真实实验来源核验、已完成/待补证边界；
5. 两轮真实渲染QA与“甲方能否看见工作量”逐页检查。

交付应尽可能保留V5已有美观排版，提升真实图片和讲述的因果逻辑。即使某个备选媒体不存在，也继续用已有repo和PPT真实材料完成，不为了图片数量造图。完成后给出最终路径、素材使用清单和V5→V6主要差异。
