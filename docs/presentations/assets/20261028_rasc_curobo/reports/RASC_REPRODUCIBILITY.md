# 同一真实scan的六阶段重放

状态：DONE（FROZEN_REPLAY几何子链）；不是现场commissioning。

真实调用：CAMERA validity/mm→m/固定矩阵；`deployment_prefilter`；`build_robot_owned_filter/filter_robot_owned`；`clean_and_cluster/decompose_support_objects`；`refine_robot_adjacent_primitives`；`WorldModel/compile_snapshot`。阶段6实际编译到right model frame；为了三视图可比较，图中将编译出的有向盒反投影回BODY，另叠加model frame轴。不是P5换色。

| 阶段 | 输入→输出点数 | 计时范围 |
|---|---|---|
| 1 | 2304000→1814747 | 已在内存的有效点选择、单位与TF；valid mask已预计算，**不包括mask计算**、文件加载与相机采集 |
| 2 | 1814747→16831 | 固定ROI + 每7.5mm格首点；ROI中1687974点 |
| 3 | 16831→15517 | 同帧已归属OBB/sphere并集；移除1314点 |
| 4 | 15517→3747 | 桌面高度带显式分离、5mm voxel、密度/连通清理、法向+支撑分组 |
| 5 | 3747→3747 | 多基元近机器人空包络细化；235个基元，不丢点 |
| 6 | 点证据3747沿用 | N/A geometry compile；235个观测基元+11个已知/非活动臂等=246障碍；仅编译计时 |

表中阶段4的点数下降来自前置清理，不是几何分组丢点；4/5分解表示的point accounting均为3747/3747。六阶段是展示分层，实际decompose函数在4内部同时产出初始基元；5为后续细化，未伪造六个独立生产API。

生产`filter_isolated_micro_primitives`额外移除24个基元，报告181个点（几何覆盖减少180点，因重叠可重复覆盖）。主A/B特意不运行该删除规则，保持全部点；该消融不是声称更改正式生产策略。

CPU i5-13400F、OMP/OpenBLAS=2；1次进程冷/5次热。表格和JSON给出每次数据、median、P95。冷启动包含首次Open3D算法初始化；不含import/原始文件读取/渲染。P95仅5次局部统计，不能代表部署SLA。

本轮清理3747点/32簇，历史同帧归档3736点/31簇；自体过滤1314点完全一致。Open3D本机0.19.0，但归档未冻结完整库版本，版本/边界差异根因尚未确定。保留差异，不填回历史数字。原始CAMERA→BODY数组完全一致，self-filter revision也一致。

ROI为X[0.22,1.30], Y[-0.76,0.76], Z[0.70,1.40]m，是工程工作区门限，不是逐点IK可达场。过滤仅覆盖冻结快照建模部件；未建模部件/现场误差尚未认证。桌面带从残余点云分离后，以known_support_table保留在世界中，没有移除碰撞保护。

三套panel相机和范围固定：ISO、TOP、FRONT。根据用户审查，ISO/FRONT统一从BODY −Y侧看向+Y（ISO elev24°/azim−110°，FRONT elev0°/azim−90°）；TOP保持−Y在下、+Y在上。没有翻转坐标或更改数据。原始百万点显示确定性抽样≤65000点，统计使用全部输入；固定BODY显示窗会裁掉远处点，图注已披露。颜色为几何角色，无RGB伪造或神经识别声明。
