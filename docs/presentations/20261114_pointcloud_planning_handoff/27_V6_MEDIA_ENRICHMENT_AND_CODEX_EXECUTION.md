# V6 素材利用深化、Codex执行顺序与质量验收

目标：**在V5文件基础上增量修到16页，保留其母版/数据/讲者备注，将先前上传的60页大稿、周报和ARES-R仓库真实媒体充分用起来。** 不是重新立项、重新制作一个“看起来相似”的PPT。

## 0. 首先找回V5母件和源PPT

用户2026-11-16在ChatGPT上传的实际V5母件：
- \`ARES-R_甲方研发工作量汇报_V5.pptx\`，**10页正文，约25.16MB**。
- V5正文已经包含11/16新增DBSCAN ε×m九组“净化保留点数”，不要回滚成旧V5任务书的“尚未执行”版本。
- V5 Speaker Notes列有来源，例如\`docs/presentations/20261114_pointcloud_planning_handoff/output/assets/extracted/large/slide-42/image69.jpg\`。这类\`output/\`通常是Codex本机工作产物，**本仓库当前文档分支未包含这些二进制文件**；应在本机查找原工作目录，不得把文档中的路径当作GitHub已存在的文件。

在本机Mac授权目录用\`mdfind -name\`优先寻找：

~~~bash
mdfind -name "ARES-R_甲方研发工作量汇报_V5"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制-2"
mdfind -name "生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂"
mdfind -name "金隅项目-周进度-20260924"
mdfind -name "金隅项目-周进度-20261023"
mdfind -name "金隅项目-周进度-20261016"
~~~

本机找不到V5母件时，**只让用户将本轮V5 PPTX复制进受控工作目录**；原始60页PPT等也先查找，不要要求用户重做截图。若另需原件，只索取确实不存在的个别文件。

必须备份V5原文件和记录SHA，创建**V6副本**，不要覆盖源文件；所有本机private路径写到gitignore目录，绝不push私人/现场原始二进制。

## 1. 资产利用：有图不等于已经用好图

### A. 原始20261028 60页大PPT：最容易被忽略的第一手媒体

过去已有媒体索引：
- \`docs/presentations/20261114_pointcloud_planning_handoff/16_V3_ASSET_AND_REFERENCE_CROSSWALK.md\`
- 大PPT的\`slide-02/image3.jpg\`双臂/工作台；
- \`slide-07/image12.jpeg\`秤台；
- \`slide-26/image42.jpg\`夹爪/料盘耳部；
- \`slide-44/image76.jpg\`专机入口；
- \`slide-47/image79.jpg\`夹爪/料盘实物；
- \`slide-42/image69.jpg\`、\`image70.jpg\`、\`image72.jpg\`、\`image73.jpg\`对应抓取、抬升、预放置/下降、释放关键帧。

进一步需从原PPTX提取而不是截图整个页面：
- slide11–14：原始点云→ROI→自体过滤→支撑；
- slide17–19：几何old/new与规划对照；
- slide27–32：求解配置、路径、实机跟踪；
- slide37：旧附着物和修订/恢复；
- slide40–41：CPU/任务时间；
- slide42：真实取放多帧；
- **slide45–60：必须全部逐页生成媒体contact sheet**，优先审查slide50(shape05,3240×1440)、slide51(shape04,3960×1260)、slide55(shape07,3298×2473)和slide59的多张高分辨率原媒体。

这些slide/shape为旧索引中历史定位线索，本机原PPT如果版本不同需实际解析OOXML并更新清单。**内容先看图，不能仅根据文件名强指定真实数据组。**

### B. 仓库现成高分辨率真实图：优先这些具体资源

根目录\`docs/presentations/assets/20261028_rasc_curobo/\`。

**图1 真实点云多阶段（V6-02）：**
- \`grasp_v3/panels/rasc6/01_raw_cloud_iso_focus.png\`
- \`grasp_v3/panels/rasc6/02_roi_iso_focus.png\`
- \`grasp_v3/panels/rasc6/03_robot_owned_filter_iso_focus.png\`
- \`grasp_v3/panels/rasc6/04_support_decomposition_iso_focus.png\`
- \`grasp_v3/panels/rasc6/06_curobo_world_iso_focus.png\`
- \`grasp_v3/details/ownership_before.png\`、\`ownership_removed.png\`。

**图2 同源几何修订（V6-03）：**
- \`panels/geometry_ab/old_boxes_zoom.png\`
- \`panels/geometry_ab/new_primitives_zoom.png\`
- \`panels/geometry_ab/error_occupied_space_slice.png\`
- \`clarity_v2/section_old_new_pair.png\`
- \`grasp_v3/geometry_ab/pair_section_z0.94.png\`（注意这属于10/21 GRASP另一数据组，不可直接配10/10 CAMERA数字）。
- 9/21的\`worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png\`可作独立案例。

**图3 规划对照（V6-08）：**
- \`worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/clear_vs_avoid_three_views.png\`；
- 9/24周报对应的A/B轨迹；
- \`panels/planning/route_overlay.png\`属于10/10 CAMERA另一组，可以用于“同一源OLD/NEW都可规划”的独立讨论，不得代替9/21 S21-CBASE无箱有箱轨迹。

**图4 P3.3与P3.4（V6-09/10）：**
- \`worklog/evidence/2026-09-22-p3-3-execution-hardening/visualization_final/p33_clearance_profile_sweep.png\`；
- \`worklog/evidence/2026-09-22-p3-3-execution-hardening/sweep_v2/sweep_summary.json\`；
- \`docs/reports/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION_REPORT.md\`和\`worklog/evidence/2026-09-23-p3-4/summary.json\`；
- \`panels/performance/fast_vs_quality_profiles.png\`需核查其数据组口径后再用。

**图5 实机（V6-11/12/13）：**
- 大PPTslide30–32真实运动/跟踪媒体；
- 9/11周报早期ServoJ图（虚拟障碍，独立数据组）；
- 9/24周报的P3.7场景图、视频；
- P3.6 \`D1_scene_trajectory.png\`实际文件位置应在本机用\`rg --files | rg D1_scene_trajectory\`定位，不要凭空写路径。
- 受监督实机运动必须有控制器反馈与源run对应；未能绑定精确图片到run的使用“同期现场配置图”，而非“该次执行截图”。

**图6 持物与恢复（V6-14/15）：**
- \`panels/attachments/payload_wrong_footprint.png\`；
- \`panels/attachments/payload_corrected.png\`；
- \`panels/attachments/place_recovery_stage_times.png\`；
- 大稿slide37、slide42原媒体；
- \`docs/golden/2026-10-19/evidence/v17-place-recovery-completed/COMPLETED.md\`；
- \`docs/golden/2026-10-19/README.md\`和\`REPORT.json\`。

**图7 性能（V6-16）：**
- \`panels/performance/latency_critical_path_waterfall.png\`；
- \`panels/performance/latency_module_before_after.png\`；
- \`panels/performance/cpu_backend_comparison.png\`；
- \`grasp_v3/metrics/historical_cpu.png\`；
- \`docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md\`；
- \`docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md\`。

### C. 已公开原始点云

\`codex/data-grasp-20261021-public\`分支
\`worklog/evidence/2026-10-21-grasp-source-data/\`

其中:
- \`20261021-study-clouds.tar.gz\`，SHA256 \`206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60\`；
- \`20261021-center-grasp-planner-study.tar.gz\`，SHA256 \`f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8\`。

含原始CAMERA/mm、BODY/m、双臂状态和场景manifest。可只读离线重放DBSCAN九格；**不要重新采集现场，不要将10/21重放冒充9/21历史选参**。

### D. V5新增实验原文件优先级

V5-03 Speaker Notes显示\`dbscan/results.json\`，这可能只在本机V5工作产物里。必须优先找到：
- results.json及源代码commit；
- 每组epsilon/minpts参数；
- 输入SHA和固定前置处理；
- stage计时/噪声/簇数；
- 每组真实点云图（若当时有绘制）；
- 在V5页03已经采用的九格数值应与JSON逐项一致。

如果没有原始九图，Codex可以从已核验的10/21冻结点云重算并以新日期登记；如果重算也不可行，**用V5九格真实记载做可编辑热力表，禁止生成假点云图**。

## 2. 数据与图片防串用的硬规则

| 数据组 | 已有真正可呈现的证据 | 一票否决 |
|---|---|---|
| S21-GRASP-V3 10/21 | 2,304,000→8,100；19→405；100%净化点覆盖；−68.6%体积和；11/16新DBSCAN九格（待原始JSON核验） | 不能说严格OLD/NEW GPU成功（严格端点均碰撞） |
| S21-ATTR 9/21 | 212点、OBB/球/旧AABB归因 | 不与10/10 CAMERA几何当同一帧 |
| S10-CAMERA 10/10 | 32→235；3747/3747；−40.9%；OLD/NEW均GPU可行 | 不说OLD失败NEW成功 |
| S21-CBASE 9/21 | CLEAR430.276mm、AVOID452.617mm、BLOCK合成拒绝；AVOID直接插值−21.78/优化+9.63mm | 规划级，不是实机 |
| P3.3 9/22 | 10/20/30/40激活×3次12次未过30mm | 不是60次，也不是实机 |
| P3.4 9/23 | 5/7.5/10体素；4/2 seed；solve/request；0.20rad/s A/B demo | 0.20不是全站速度，AVOID fast roundtrip本轮未做 |
| P3.6 D1 9/23 | 198基元、近障退出、solve3.08/exec11.41、0.882° | 不宣称普适成功率 |
| P3.7 9/24 | 运行时五段、每段fresh scene/trajectory hash | 自由空间绕箱≠完整抓放 |
| Golden 10/19 | 已实机取料、230mm、1.53m；PLACE故障后125.34s恢复 | 不是无干预连续全链；持物修订非通用 |
| P3.8E/P3.9/10.21 CPU | 400.25s事件审计；3个CPU模块加速；18节点Scheme软件回放 | 无整周期实测11×提速/395s实测结论 |

## 3. Codex应该怎么编辑V5，而不是重做

**Phase 0：固化母件**
1. 在本机找到用户上传的V5 PPTX，记录SHA和实际10页；
2. 使用PowerPoint或python-pptx只读检查slide layout/master/notes/embedded media；
3. 另存工作副本到本机 \`output/acceptance_v6/V6_working.pptx\`，源文件不得修改；
4. 先按26号文件建立 \`v5_to_v6_slide_map.csv\`，每个旧slide对应REUSE/SPLIT/INSERT，不丢失原source notes。

**Phase 1：素材审计**
1. 扫描原60页大PPT全部原生媒体，重点45–60页，并导出media manifest和contact sheet；
2. 扫描9/11、9/24、10/16、10/23周报（真实存在者）；
3. 检查ARES-R已经有的图集；选ROI清晰度足够的主图；
4. 对V6的每一页，先定“现场主图+对照图+数据图”三件材料，再布局；
5. 在V5制作输出目录找到11/16 DBSCAN原始results.json与九组视觉素材。

**Phase 2：真实图片精加工**
1. 复制原图到本地派生媒体目录（源图不改）；
2. 对同源old/new做相同投影/ROI/大小裁切，不能单边放大制造效果；
3. 遮挡原图微小caption时，保留原始媒体在manifest，用PPT原生大字重写标注；
4. 用线/圈指出212点、限制物体、料盘附着几何、起点与轨迹等具体ROI；
5. 高清照片优先，禁用网络无关图库和AI生成替代实测；
6. 每页显示源日期/数据ID/验证等级，notes里写精确出处。

**Phase 3：16页增量成稿**
1. 对V5 REUSE页保留绝大多数原文、数值、主题，只重排图文比例；
2. 对SPLIT页先复制原slide两次，再分别剪去一半内容并增配真实媒体；
3. 对INSERT页从V5原母版的对应layout复制，保持Logo红线/页脚一致；
4. 任何新图片不能无数据组标记；任何新数值要可复核；
5. 每页最终上屏文字量以现场可看清为界，说明文字尽量放备注，不把技术关键过程全藏起来。

**Phase 4：讲述节奏**
每页speaker notes用如下结构，且正文至少可见前3项：
- 开场一句现场问题（不虚构）；
- 现场/代码的真实旧状态；
- 实际改了什么、做了几个候选；
- 图片和数据如何解释；
- 形成什么工程判断/选择；
- 数据等级与不能推出什么；
- 来源路径/commit/run SHA。

不口号式写“极大提高”“先进”“安全无忧”；用“12次全部拒绝”“5段到位”“同源覆盖保持”“控制器读回”等证据形成说服力。

**Phase 5：最终QA与交付**
- PPTX 16页（允许另有1页被标记隐藏的技术备查，不算正文）；
- 保留原V5母版、BBMG Logo/红线/页脚、16:9；
- 中文主黑体，英文/数字Arial；辅宋体+Times New Roman；公式另算；核对OOXML Latin和East Asian字体；
- 输出PDF与逐页PNG，真实渲染2轮；
- 对每页进行3秒/30秒甲方测试；
- 比较V5与V6同一个旧主题，不仅要求文字未丢，还要有新增可见证据；
- 检查没有超出页面边界、矢量字被压扁、图例色与语义不一致、图片模糊、不同run混用；
- V5原始Speaker Notes完整归档，V6每页有自己的来源和讲解；
- 不把原始私有PPT、点云、视频/录音、绝对路径直接push到公开repo。

交付文件建议：

~~~text
output/acceptance_v6/
  ARES-R_甲方研发工作量汇报_V6_丰富过程版.pptx
  ARES-R_甲方研发工作量汇报_V6_丰富过程版.pdf
  previews/slide_01.png ... slide_16.png
  contact_sheet.png
  v5_to_v6_slide_map.csv
  source_media_manifest.csv
  slide_source_ledger.csv
  speaker_notes.md
  v5_vs_v6_content_audit.md
  qa_visual_round1.md
  qa_visual_round2.md
  qa_technical.md
  qa_customer.md
  dbscan_replay_or_source_status.md
  missing_assets.md
~~~

## 4. 素材丰富度的建议指标（不能为凑数制造图片）

- 至少12/16页以真实现场图、真实点云、真实规划轨迹或真实执行数据图为主要视觉；
- 纯文字流程和表格页不超过4页，且每个纯图表页都要有实际实验ID；
- 全篇优先使用来自**至少四个不同证据家族**的真实素材：20261028大稿现场照片、10/21 GRASP点云图集、9/21–9/24规划/实机、10/19 Golden恢复；
- 至少5处能直接看见局部ROI的前后/独立条件对照；严格同源，不能硬凑；
- 至少2处照片序列呈现真实物理阶段（ServoJ或Golden），不能只用一次大图复用多页；
- 所有重要图的主体能在正常投屏比例下被看见，不能依赖整页小字原图；
- 对V5中已经存在的真实主图，能证明更清晰就优先保留，不为增加图片而更换好图。

## 5. 真正的验收问题

发给甲方前，请以不认识项目的技术经理视角检查：
1. 看完第二、三页，是否知道“有点云”与“有可用自由空间”是两件不同的事？
2. 看完第四、五页，是否知道体素、前置离群滤波、DBSCAN是不同的三类实验？
3. 看完第六、七页，是否能说出项目具体适配cuRobo而非重造cuRobo的至少三项工作？
4. 看完第八至十一页，是否知道规划候选、净空失败、求解效率和实机跟踪分属不同验证阶段？
5. 看完第十二、十三页，是否能分辨同样是实机，D1单次和P3.7五段有什么不同？
6. 看完第十四、十五页，是否理解“实物已拿起→放置遇阻→持物几何修订→检查点恢复”的时间顺序？
7. 看完最后一页，是否能分辨哪部分是真实实测提速、哪部分仍未证实端到端收益？

任何一条回答不清，就继续补真实图和因果标注，不要只调整字号。
