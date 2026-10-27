# 分层性能与计时边界

本轮同一10/10原transit路径CPU回放：NUMPY_REFERENCE median 8.684631s → NATIVE_CPU_V1 0.585218s，含首轮3次各后端，所有301个dense samples、limiting object/component、gap与判决保持一致，gap容差1e−12m；不是历史431采样，也不是GPU加速。

本轮同一1814747点/235个bounds的局部inclusive查询：线性median 9.242724s → cKDTree含建树 0.426099s；返回数组（含顺序）逐一SHA一致，单轮返回合计256538点（不同查询可重复）。这是query kernel scope，不冒称完整contact artifact/pregrasp准备重测。三轮原始值均公开，未裁掉首轮开销。

历史10/21三项：17.023→1.125s独立CPU；15.176→0.830s完整接触几何；15.866→1.437s准备。来自6866106自带审计文档、不能离线重测的原study/cloud tar缺失。组成层可能重叠，不能叠加收益。历史冷/热GPU、100mm diagnostic与derived55mm case分开。

9/24 native-ready关键路径：六个事件窗口之和400.25s，显示保留分项求和：motion147.73s，non-motion252.52s。源报告aggregate motion为147.74s，有0.01s四舍五入差异，已披露。wait不能全归相机。没有完整scan→scene→GPU内部独占时间序列时，不伪造全链分段瀑布；本包瀑布从已知native-ready开始。

原606/395/255/205s是旧工程估算，非本轮实测或当前完整Demo周期。5700||5000并发采集仍需设备互斥/干扰审查，不能假称已产生现场收益。

GPU本轮OLD/NEW各一次、单次预算一致；OLD 5.328s solve wall / NEW6.994s，不绘制伪造P95与成功率。phase init约17.8s，两次均cold，持久worker价值不能仅根据这两次冷测折算现场收益。显存allocator峰值与整卡占用概念分开。

点云阶段2约1.47s、近机器人细化约1.34s仍占CPU主要时间。这里并未为画漂亮图降低体素精度或放宽膨胀。图像渲染、磁盘、源文件加载不计入算法计时；stage1预计算valid mask开销未计入且明确披露。
