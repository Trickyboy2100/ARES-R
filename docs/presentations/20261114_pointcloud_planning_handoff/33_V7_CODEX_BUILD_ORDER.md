# V7 Codex正式执行任务令（可直接复制）

在本地ARES-R项目继续甲方研发工作量验收PPT。本轮的任务不是写论文、做技术路线科普，也不是从零重新设计PPT，而是以当前用户提供的16页
\`ARES-R_甲方研发工作量汇报_V6_丰富过程版.pptx\`
为**不可覆盖母件**，增加实测参数/代码/回归/实机调试证据，形成**19页正式陈述式研发工作量报告**。

## 必须先读的任务书（优先级顺序）

1. \`docs/presentations/20261114_pointcloud_planning_handoff/29_V7_WORKLOAD_EVIDENCE_MASTER.md\`
2. \`docs/presentations/20261114_pointcloud_planning_handoff/30_V7_SLIDE_BY_SLIDE_CONTRACT.md\`
3. \`docs/presentations/20261114_pointcloud_planning_handoff/31_V7_OFFLINE_EXPERIMENT_AND_EVIDENCE_PROTOCOL.md\`
4. \`docs/presentations/20261114_pointcloud_planning_handoff/32_V7_ASSET_CROSSWALK_AND_V6_REUSE.md\`

旧V5/V6任务书是历史参考：事实边界继续有效，但正文页序以本次V7为准。已上传的\`Recording 154(2).txt\`要求参照29号文件00:48/02:34/05:59/10:32/12:43等甲方要求；不可将原音频/转写推送到公开仓库。

## 不得再犯的错误

- 正式标题不能用问句。统一改成“实验对象＋研发动作＋试验/验证”形式。
- 不能把“点云→滤波→聚类→规划”这种**算法运行步骤**当成“进行了大量研发调试”的证据。
- 不能用无箱直线/有箱弧线一张结果图替代参数对照、限制障碍、工况设置和独立核验。
- 不能把cuRobo成熟GPU/IK/B样条/PRM能力说成本组从零发明；必须展示本组JAKA、工具、场景、规划参数、运行时、native ServoJ等实际开发工件。
- 不能用无源AI数字/伪历史运行、虚构训练轮次、生成的实机照片或伪造日志填充工作量。
- 不同数据组不能拼成同源“旧失败新成功”；不能将P3.3 12/12拒绝改写成成功。
- 不能把Golden恢复写成原脚本无人干预连续全链成功。
- 不能以“技术先进/显著提升”替代可追溯原始指标。
- 不能为了“图丰富”贴满小点云整图。必须精裁ROI、加大关键区域，且同源同视角。

## 强制执行顺序

### A. 审计V6原文件
1. 查找本机V6源PPTX，记录SHA和16页原notes、原shape/媒体映射；
2. 找不到先要求用户只补此文件，**不要直接用repo的V5文字重建PPT**；
3. 复制一份V7工作副本，永不覆盖V6；
4. 生成\`v6_to_v7_slide_map.csv\`，遵从30号文件reuse/split/insert映射；
5. 审阅原60页大PPT和V6全部图片，优先原图/照片、同源局部。

### B. 补最有价值的过程证据
1. **DBSCAN**：优先审计V6已有九格真实结果\`output/acceptance_v5/dbscan/results.json\`、环境与原图。若只有PPT截图，不能宣布原始实验已核验；
2. **支撑层分解**：利用repo\`support_decomposition.py\`与10/21公开原始BODY点云，离线尝试支撑带宽5/10/15mm、凸起阈值15/25/35mm固定输入敏感性实验；记录输入/代码SHA、运行日志、指标，不能提前填预期数。补证运行不了，按30号文件真实回退文稿制作；
3. **几何归因**：S10-CAMERA 32→235同源对照＋独立S21-ATTR 212点问题，两个数据组不得伪造连续前后；
4. **cuRobo**：P3.3 4×3失败扫值和限制对象；P3.4 4个候选配置、CUDA Graph、常驻worker重用与request/solve分开计量，找源码与报告；
5. **控制**：尽可能匹配同一次P3.4 ServoJ速度档位的控制器命令/读回曲线；无原日志则不编时序图；
6. **现场**：P3.6 D1单次、P3.7五段、Golden 10/19原物理阶段与PLACE检查点恢复，严格按原运行证据组织。

### C. 制作19页V7
- 严格按30号文件逐页中文正式标题和对应文稿；
- V6第04页拆为体素/离群滤波两页；第10页拆为候选求解/常驻服务两页；新增支撑层分解调试页；
- 保留V6有效照片与图，补同源局部/失败对照、源代码变更、回归记录、实机回执；
- 每页上屏必须看得见实际研发动作、输入工况、参数/代码对照和结果，而不仅是总结；
- 主图主体足够大，表格不占满整页，解释放speaker notes。

### D. 技术/视觉双轮QA
1. 检查所有数字逐字段匹配原source JSON/报告/真实新实验；
2. 检查“历史实机/冻结回放/新增离线/规划级/模块回归”标签正确；
3. 检查图片同数据集/同frame/同膨胀/同坐标/同视角；
4. 重点检查支撑层是不是只有结论而无过程、cuRobo是不是只有接口名称而无代码/性能/控制证据；
5. 检查所有标题无问句，语言正式，备注详实且能现场讲解；
6. 使用原V6继承的BBMG验收模板，保留Logo、页眉/红线/页脚、16:9、原组件；
7. 字体：中文主黑体、英文数字Arial；辅宋体/Times New Roman；公式另行排版。检查OOXML Latin与East Asian设置；
8. 实际导出PDF/逐页PNG，修正溢出、模糊和标注后再渲染一遍；
9. 不做没有依据的“全流程速度提升X倍”、不掩盖负结果和故障。

## 预期交付

在本机忽略目录：
\`\`\`
output/acceptance_v7/
  ARES-R_甲方研发工作量汇报_V7_调试试验证据版.pptx
  ARES-R_甲方研发工作量汇报_V7_调试试验证据版.pdf
  slides/slide-01.png ... slide-19.png
  contact_sheet.png
  speaker_notes.md
  v6_to_v7_slide_map.csv
  evidence_registry.csv
  source_media_manifest.csv
  claim_source_ledger.csv
  experiment/                       # 仅真实离线补证
  audit/
    technical_review.md
    visual_review_round1.md
    visual_review_round2.md
    customer_requirements_coverage.md
    unverified_claims_and_fallbacks.md
    build_log.md
\`\`\`

完成后需报告：
- 使用的V6母件真实文件与SHA；
- 19页每页从V6继承哪些内容、新增何种真实证据；
- DBSCAN原始结果是否找到和验证；
- 支撑层补充离线试验是否真实运行、结果与失败原因；
- cuRobo/ServoJ/Golden证据完整性；
- 所有未完成实验如何真实回退；
- 两轮视觉QA修复了什么；
- 最终PPTX/PDF/PNG与notes路径。

## 安全与公开仓库纪律
- 本次不操作任何真实机械臂、AMR、夹爪或相机；不自动SSH设备；
- 不更改生产代码默认参数或安全门槛；离线试验profile使用复制品；
- 不提交原始个人PPT、录音、非公开现场媒体、原始点云或私人绝对路径到公共GitHub；
- 不在没有核实情况下宣称“补做实验已完成”。如果缺件，说明缺什么并继续完成其余PPT。

**执行优先顺序：事实和工作量证据 > 讲述因果 > 真实媒体清晰度 > 精细排版 > 装饰性视觉。**
