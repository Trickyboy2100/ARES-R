# 素材地图与原PPT提取要求

Source: reconstructed

## 1. 仓库中已存在且随本分支继承的素材

冻结目录：[20261028_rasc_curobo](../assets/20261028_rasc_curobo/README.md)。本轮读取其README与Git tree核对了下面入口，不声称已经逐张视觉检查。

| 主题 | 已存在入口/路径 | 建议用于旧稿页 | 使用限制 |
|---|---|---|---|
| 总图集 | [index.html](../assets/20261028_rasc_curobo/index.html)、[contact_sheet.png](../assets/20261028_rasc_curobo/contact_sheet.png) | 全部选图 | 先看manifest，不将总览图缩成整页主证据 |
| 六阶段 | [RASC_six_stages_16x9.png](../assets/20261028_rasc_curobo/composites/RASC_six_stages_16x9.png)、panels/rasc6/ | 2–4 | 总图集与GRASP V3是不同数据源；合集仅作导航 |
| OLD局部 | [old_boxes_zoom.png](../assets/20261028_rasc_curobo/panels/geometry_ab/old_boxes_zoom.png) | 6 | 32/235与3,747点组，不套9,992点统计 |
| NEW局部 | [new_primitives_zoom.png](../assets/20261028_rasc_curobo/panels/geometry_ab/new_primitives_zoom.png) | 6 | 保持与OLD同视角、同尺度 |
| 错误占据剖面 | [error_occupied_space_slice.png](../assets/20261028_rasc_curobo/panels/geometry_ab/error_occupied_space_slice.png) | 6 | OLD-only表示面积；不证明未观测空间自由 |
| 真实GPU轨迹 | [route_overlay.png](../assets/20261028_rasc_curobo/panels/planning/route_overlay.png)、panels/planning/ | 6/8 | 两者均成功；不是9/21 CURRENT_BASE CLEAR/AVOID图 |
| 本轮CPU等价核验 | [cpu_backend_comparison.png](../assets/20261028_rasc_curobo/panels/performance/cpu_backend_comparison.png) | 13 | 301采样；不是GPU加速，不替代10/21历史计时 |
| 本轮查询等价 | [contact_query_comparison.png](../assets/20261028_rasc_curobo/panels/performance/contact_query_comparison.png) | 13 | 235 bounds、数组一致；不当成完整抓放周期 |
| 历史模块计时 | [latency_module_before_after.png](../assets/20261028_rasc_curobo/panels/performance/latency_module_before_after.png) | 13 | 历史17.023→1.125等，模块收益不叠加 |
| 关键路径 | [latency_critical_path_waterfall.png](../assets/20261028_rasc_curobo/panels/performance/latency_critical_path_waterfall.png) | 13/14备选 | 400.25s事件窗口，不把所有等待归于视觉或GPU |
| 工程约束接入 | [aresr_constraint_integration.png](../assets/20261028_rasc_curobo/panels/runtime/aresr_constraint_integration.png) | 8 | 架构图不是实测；不把上游求解器当自研训练模型 |
| 场景状态契约 | [scene_state_contract.png](../assets/20261028_rasc_curobo/panels/runtime/scene_state_contract.png) | 7/9 | 状态变化后拒绝旧计划；重新准备属上层 |
| 持物与接续 | panels/attachments/ | 10 | 尺寸修正与恢复时间，不包含原几何净空结论 |
| ServoJ曲线 | panels/servo/case1/case2_* | 12诊断素材 | 两例均abort，必须在图注保留，不当成功Demo |
| V2剖切图 | [clarity_v2/README.md](../assets/20261028_rasc_curobo/clarity_v2/README.md)、[section_old_new_pair.png](../assets/20261028_rasc_curobo/clarity_v2/section_old_new_pair.png) | 6 | 显示剖切不等于实际移除障碍 |
| GRASP V3 | [grasp_v3/README.md](../assets/20261028_rasc_curobo/grasp_v3/README.md)、index.html、VISUAL_MANIFEST.json、details/、runlogs/ | 2–4；其余须先匹配条件 | 19→405、8,100点、68.6%这组；不得贴32→235统计 |
| GRASP自体归属 | [ownership_before.png](../assets/20261028_rasc_curobo/grasp_v3/details/ownership_before.png)、[ownership_after.png](../assets/20261028_rasc_curobo/grasp_v3/details/ownership_after.png) | 2 | 仅过滤模型声明owned的部件，不声称未知机器人部件也过滤 |

## 2. 大PPT末尾必须实际展开

原文件：`20261028-水分细度目标识别与场景自适应规划控制(1).pptx`。

文本索引中末尾连续页面只显示“3.1 水分细度检验目标识别与场景自适应规划控制”，**不意味着没有图片**。这批页面是用户特别要求优先使用的素材。由于本轮容器故障，尚未导出其页图/媒体，不在本文件捏造页号或图名。

在恢复文件环境后执行：

1. 读取presentation.xml中的sldId顺序，不按slide文件数字或media文件名猜页序。
2. 渲染全部页面，重点对末尾图片页制作每页带原页码的联系表。
3. 从每张slide的relationship解析嵌入图片、裁切区域、分组和视频关系；导出原始媒体，不截整个低分辨率PPT再放大。
4. 对每一项记录source_file、slide_number、shape_id、rel_id、media_path、image_sha256、caption、dataset、usage、verification_status。
5. 将每页与图集ASSET_MANIFEST、grasp_v3/VISUAL_MANIFEST比对，优先使用仓库同源高分辨率原图。
6. 保留视频文件/关键帧的真实用途说明。FK动画不是实机录像，快放不是实际耗时。

## 3. 指定模板

必须使用`生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂(1).pptx`原文件，不是旧16页重绘稿。

模板当前只有可读文本恢复，未导出母版/图片。先核对模板真实页面，再提取固定背景、页眉、标志和页脚等实际存在组件。不要依据文件名推定有某校徽、红蓝配色或进度条。

## 4. 9/21与10/23素材不要混淆

验收稿/方法稿“非凸结构分解与碰撞包络精化结果”页明确：上图为10/23现场模型示例，下表为9/21同帧净化点云对照。要么保留图注，分别承担示例/定量证明；要么从9/21证据目录找同源图，不能把二者标成同次前后复测。

## 5. 原文件找回与分片

见06_SOURCE_TRANSFER_STATUS.json。工具`tools/archive_reference_files.py`只做字节级分片与SHA256恢复，**不会生成可独立打开的按页PPT分册**。这种存储方式不丢母版、关系、备注、视频；恢复后才用PowerPoint打开。

建议每片40MiB是本包的保守归档设置，不是声称某平台的最新上传上限。生成后本地验证、检查敏感信息，再由用户授权的Git流程提交。
