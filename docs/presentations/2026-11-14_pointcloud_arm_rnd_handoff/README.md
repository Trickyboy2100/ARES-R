# 点云场景重建与机械臂规划：研发过程与工作量汇报｜交接包（2026-11-14）

> **状态：研究资料与演示素材已归档；精排版16页最终PPTX尚未完成。** 这是接手Codex/设计人员的完整交接入口，不是最终验收PPT。避免把「上一次已经生成但被指出不符合母版要求的PPT」当作最终成品。
>
> **内容边界：14页正文 + 2页尚未执行的补证附页。** 不重开提纲；正文以“发现具体问题→对照/诊断→我们实际修改了什么→如何复测及其边界”为主，若某模块是一次成形的工程开发，则按“需求/接口问题→逐模块实现→联调验证”表达，不强行捏造失败史。

## 一、为什么建立这个交接包

2026-11-13/14 的对话中，用户指出上一版14+2 PPT的框架逻辑基本可接受，但**版式没有忠实继承内部验收PPT，实际截图、素材及大PPT尾部备用页没有充分使用**。随后重制尝试中，文件运行容器持续返回 ClientError，不能完成原生母版克隆、二进制导出和终稿渲染。此前生成的14+2 PPTX及PDF在旧会话中曾提供下载链接，但**本次交接没有成功把这两个二进制文件重新读取或上传GitHub**，不得宣称已经push。

本包保存可直接继续的逐页编辑稿、讲述备注、数字出处、真实证据与待补实验边界、模板字体规范、素材筛选任务、执行工单，供在有本地PowerPoint源文件与正常Python环境的Codex继续完成。

## 二、当前仓库资产已找到——无需从零重画

本交接分支从已有真实证据分支 \`codex/rasc-presentation-evidence-20261028\` 的提交 \`8da63a6caf4d7d9ac17dc226362e43c77a6f21d5\` 派生，**完整继承该分支所有可复用素材**，包括：

- [素材README](../assets/20261028_rasc_curobo/README.md)（68张独立PNG、44张SVG、CSV/JSON、历史与冻结重放分类；另有真实GRASP V3和clarity V2）；
- [素材索引HTML](../assets/20261028_rasc_curobo/index.html)、[全量来源manifest](../assets/20261028_rasc_curobo/ASSET_MANIFEST.json)、[六阶段16:9概览](../assets/20261028_rasc_curobo/composites/RASC_six_stages_16x9.png)；
- [冻结真实点云六阶段](../assets/20261028_rasc_curobo/panels/rasc6/)、[非凸几何同帧OLD/NEW](../assets/20261028_rasc_curobo/panels/geometry_ab/)、[真实GPU规划](../assets/20261028_rasc_curobo/panels/planning/)；
- [性能比较](../assets/20261028_rasc_curobo/panels/performance/)、[ServoJ实测但中止的两例](../assets/20261028_rasc_curobo/panels/servo/)、[实际历史持物归属与恢复](../assets/20261028_rasc_curobo/panels/attachments/)；
- [规划/运行时图](../assets/20261028_rasc_curobo/panels/runtime/)、[大局部清晰剖切图](../assets/20261028_rasc_curobo/clarity_v2/)、[真实GRASP V3页面](../assets/20261028_rasc_curobo/grasp_v3/)；
- [证据状态](../assets/20261028_rasc_curobo/STATUS.md)、[输入来源](../assets/20261028_rasc_curobo/INPUT_INDEX.md)、[风险和缺口](../assets/20261028_rasc_curobo/reports/REVIEW_AND_LIMITATIONS.md)。

**重要**：素材分支的冻结GRASP输入是2026-10-10真实点云，历史7→167基元统计是2026-09-21另一帧。二者不能被合并成同一实验；同源几何OLD/NEW条件下两边GPU均规划成功，不能夸成“旧失败新成功”。

## 三、请先读这些文件（建议顺序）

1. [01_SLIDE_SCRIPT_14_PLUS_2.md](01_SLIDE_SCRIPT_14_PLUS_2.md)：16页编辑稿，每页“四段证据链”、画面和讲述备注；其中两页是明确标注「未执行」的补证设计；
2. [02_EVIDENCE_LEDGER.md](02_EVIDENCE_LEDGER.md)：参数/数字/物理实测/历史提取/冻结重放与不能使用的说法；
3. [03_TEMPLATE_AND_DESIGN_SPEC.md](03_TEMPLATE_AND_DESIGN_SPEC.md)：**必须直接用2026-10-30内部验收-机械臂.pptx当母版**；黑体+Arial主用，宋体+Times New Roman辅用；公式单算；版式验收；
4. [04_SOURCE_PPT_AND_MEDIA_INVENTORY.md](04_SOURCE_PPT_AND_MEDIA_INVENTORY.md)：3份参考源PPT、大小/角色/缺失情况及大PPT最后空素材页提取；
5. [05_RECORDING_ANALYSIS_AND_INTEGRITY.md](05_RECORDING_ANALYSIS_AND_INTEGRITY.md)：14分57秒录音的真实需求、工作量呈现和应避免的归属错误；
6. [06_CODEX_CONTINUATION_ORDER.md](06_CODEX_CONTINUATION_ORDER.md)：一步一步落地的执行/检查/输出顺序；
7. [scripts/extract_pptx_slide_media.py](scripts/extract_pptx_slide_media.py)：源PPTX在本地可用时，只读提取某些页关联的原始media及slide text，生成可追溯manifest；不自动把音视频push公开仓库。

## 四、来源PPT／旧半成品是否已经上传？

**没有。二进制文件上传本次受运行环境故障阻断。**详细名称和大小见04文档。所有素材说明中，\`[repo-existing]\` 表示本分支已有字节，\`[user-upload-only]\` 表示曾在ChatGPT对话上传、需在Codex本机取得原件，\`[prior-output-only]\` 表示旧会话链接或产生过但本次不能重新验证字节，\`[not-performed]\` 表示待执行实验。请不要把这四类混淆。

## 五、交付验收 Gate

- 14页正文、2页附页；两项补证**显著标注尚未执行**，不得进入已完成成果；
- 继承母版真正的主题、背景、校徽/固定组件、版心、标题横线与页脚；不是“相似风格重画”；
- 正文核心页面以**实际点云/模型/轨迹/执行截图和图表**为主；图与文字对应；
- 每页PowerPoint讲述备注含完整叙事、证据文件和数字统计口径；资料不足时明确「无数据」；
- 不声称“自研cuRobo原生优化器/训练cuRobo”；工程贡献为真实工业点云、几何编译、目标/持物/双臂约束、校验与安全执行接入；
- PDF逐页渲染并做16页抽检、文字溢出检测、封面/页脚/中文字体检查；交付PPTX+PDF+简短QA结果+可编辑素材清单；
- **不得直接修改生产机器人运动代码或驱动现场设备来凑展示数据**。

## 六、任务可交给Codex的最简提示词

“请以 \`docs/presentations/2026-11-14_pointcloud_arm_rnd_handoff/README.md\` 为唯一交接入口，按06执行，不重新提纲。以用户原始《生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx》为真正母版，复用本分支已存在真实素材与20261028大PPT末尾附图。黑体+Arial为主，宋体+Times New Roman为辅，公式独立；14+2页，并写备注与出处。不要制造未执行补证实验数据。输出PPTX、PDF、QA报告和素材来源manifest。”