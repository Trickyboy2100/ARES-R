# 专业性与真实性审查：初版→改版

可防守成果：真实CAMERA→BODY逐元素核验；实际六阶段几何算法；全部3747点统一padding A/B；真实cuRobo两种表示与独立world validator；CPU后端/索引输出等价；带来源的历史优化及实际界面。

仅离线/代码：本轮GPU路径与SceneCompiler、ReplayProvider任务/Stop、源码结构图。没有物理运动，也没有现场几何再commissioning。

实际负结果：OLD/NEW都成功；NEW更慢且最小净空略小，不宣称OLD不可达/NEW绕障获胜。两段真实微运动都abort，不称正常完整抓取曲线。原现场runtime YAML缺失；适配错误与关节映射缺陷保留。

初版撤回/改进：
- 主A/B不能混入production微小孤立基元删除：移除混杂后保留3747/3747，另报生产181点accounting/180点覆盖变化。
- 初版中文fallback缺字体：注册系统Noto Sans CJK JP，未分发字体；主图重新导出。
- 3D全局图主体过小：增加相同范围OLD/NEW局部图、剖面；不改变两种方法各自相机。
- 用户视角审查：所有本轮点云/规划/局部图统一BODY −Y→+Y，并同步UI点云截图、合集与图库；未重跑GPU或更改指标。
- 初版结构图跨行斜箭头干扰标签：改蛇形排列和贴边连线。
- 初版ServoJ同记录target/actual对齐不严谨：审查read-before-send后，分别保留原始曲线并改用previous-command误差；标abort。
- 初版stage6仅叠源BOX不足以证明编译：改为实际SceneCompiler输出的有向盒经逆TF显示，坐标轴仍标BODY以便可比。
- 9/28 motion分项147.73s与报告147.74s差0.01s，保留四舍五入披露，不拼凑数字。

没有证据的图位：seed中间候选、fresh物理持物三状态空间、PLACE原几何净空、正常完整抓取成对波形、原拖拽视频、全链scan→GPU内部细分时序。manifest列BLOCKED，不创建空图。

可读性：PNG长边至少2560，二维/框图保留SVG。640px审查缩略图供发现整体结构/标题，不适合读细密WebUI与完整六关节图；这些推荐全页/单独局部使用，不声称任意图缩到1/3宽仍可读全部日志。UI原图加独立caption，不修改实际按钮/状态。后续可针对具体页版裁选焦点，但不能裁掉失败区间。

进一步优化：补齐授权原输入后复现9/21和10/21；采集正常sender完整trace；增加多scene/seed统计，而非在单一冻结请求重复堆数量。不得把点稀疏区当作已观测free space，独立self collision缺口仍保留。
