# RASC / cuRobo 技术汇报研发证据

新增：[真实GRASP完整V3](grasp_v3/index.html)（10月21日原始包；交互六阶段、独立大图、薄层对照及真实GPU预抓取FK动画）。

新增：[点云可读性V2试版](clarity_v2/index.html)（9张，独立于原68张；含显示剖切与薄层对照）。

先打开 **[离线素材总览 index.html](index.html)**；独立子图可直接下载，**没有制作最终PPT**。

本包含 **68张独立PNG**、**44张SVG**、六阶段16:9合集、CSV/JSON指标、源码与复现工具。所有原始点云/未经授权媒体留在本地私有目录。逐图来源见ASSET_MANIFEST.json，状态与缺口见STATUS.md。

| 素材组 | 独立路径 | 最适合讲什么 |
|---|---|---|
| 真实点云六阶段 | panels/rasc6/01..06_*_iso/top/front.png | 同一真实源帧、实际算法/计数/计时；18张 |
| 几何A/B | panels/geometry_ab/old_boxes/new_primitives + *_zoom + error_occupied_space_slice | 32簇框与235基元全点覆盖，统一7mm；sum体积降低约40.9%，不称union/已证空闲 |
| 真实GPU规划 | panels/planning/planning_old/new、route_overlay、gap_vs_path | 同一请求预算；两者都成功，独立world校验通过；无虚构候选 |
| cuRobo/ARES-R原理 | panels/runtime/curobo_native_principle、aresr_constraint_integration | 上游GPU能力与项目约束/验证分工 |
| 真实ServoJ | panels/servo/case1/case2_* | 六轴目标/实测、previous-command误差、差分动态；**两例均abort** |
| 性能分层 | panels/performance/* | 本轮CPU/查询等价实验 + 明确分开的历史三项、等待瀑布、GPU层次 |
| 框架/状态/界面 | panels/runtime/* | 四套独立代码图、ownership、真实HTML/fixture界面；不冒充设备任务 |
| 持物/恢复 | panels/attachments/* | 历史尺寸修正与故障后接续时间；无原几何净空结论 |

## 推荐优先使用的10张

1. [六阶段合集](composites/RASC_six_stages_16x9.png)：同源算法链；合集只作导航，正式汇报按需拆图。
2. [局部OLD](panels/geometry_ab/old_boxes_zoom.png) + [局部NEW](panels/geometry_ab/new_primitives_zoom.png)：同视角/全点覆盖；不能声称未观测空腔安全。
3. [占据剖面](panels/geometry_ab/error_occupied_space_slice.png)：OLD-only表示面积；最大差异Z层选择已公开。
4. [GPU路径并列](panels/planning/route_overlay.png)：真实保存的cuRobo结果；两者均成功，没有“旧失败新成功”。
5. [本轮CPU等价对照](panels/performance/cpu_backend_comparison.png)：301采样、同判决/净空，不能称GPU加速。
6. [本轮索引查询](panels/performance/contact_query_comparison.png)：相同235个bounds，输出数组一致；不是完整artifact scope。
7. [约束集成](panels/runtime/aresr_constraint_integration.png)：ARES-R工程贡献；结构图非实测。
8. [历史模块优化](panels/performance/latency_module_before_after.png)：历史17.023→1.125等，收益不叠加。
9. [关键路径](panels/performance/latency_critical_path_waterfall.png)：400.25s事件窗口，等待不能全归视觉。
10. [状态契约](panels/runtime/scene_state_contract.png)：scene/tool/payload/q如何使旧计划失效；现场ACK恢复仍有边界。

## 本轮验证

真实Oct10 CAMERA SHA `a9031515bada1c3859bec842d145f44d8ce407ac9af3c8fea95478d7ea463b8f`；BODY经固定TF重算逐元素一致；CPU1冷5热计时；GPU0 RTX3080 / pinned cuRobo；OLD/NEW均SUCCESS且独立world PASS。两次冷请求不是延迟分布。25项既有相关回归与5项新增关节映射回归通过。正式worker修复独立提交8fbd669。

几何235个基元保留3747/3747点；与历史同帧3736/31簇存在库/边界差异，未冒充9/21 7→167。capture q与transit规划q0不同，静态冻结世界A/B不能代替fresh实机状态绑定。原site runtime YAML不在本地，离线派生配置的区别已记录。independent self collision仍未实现；GPU内self collision启用。

复现：见[工具README](../../../../tools/presentation_evidence/README.md)，一键入口tools/presentation_evidence/run_all.sh。原始输入必须由有权限的数据盘提供；不会自动访问现场。先看[审查记录](reports/REVIEW_AND_LIMITATIONS.md)，最后看[最小现场/数据缺口](reports/ONSITE_ONLY_BACKLOG.md)。
