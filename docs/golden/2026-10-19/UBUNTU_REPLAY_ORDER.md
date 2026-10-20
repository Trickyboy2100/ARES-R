# Ubuntu离线优化工作单：先复现，再修改

禁止连接机器人。新分支/独立环境，不改golden，不占用其他研究任务的GPU。先按SITE_COLLECTION补齐真实请求/点云；缺失时记录BLOCKED_REAL_REPLAY，不能用Mock冒充通过。

## 已确认的FAST差异

10月15日报告：10mm JOG solve0.525s、已验证规划0.696s、全请求9.693s；36–45cm冻结用例热请求中位1.655–1.906s。仅少数特定冻结请求，不能推导任意抓放任务2s必达。

目前 `latency_solver.solve_single_pass` 仍为 `finetune_attempts=0`。
Demo `Live.prepare` FAST设置2trajopt/4IK、CUDA graph、50迭代、1目标候选、15秒预算。它直接使用initial_iters，未按WebUI入口的orientation映射统一选取25/50。
QUALITY明确移除solver_policy，恢复system curobo planning，timeout240秒。任务允许FAST→QUALITY→QUALITY三次。因而200多秒不等于FAST求解200多秒；需按attempt分析。
当前序列最坏求解预算15+240+240=495秒，另加扫描/IK/包装/队列。预算不是实际运行耗时，原生调用是否及时取消仍需测量。

最后修正持物模型的预览：核心solve约3.120s，planner调用4.017s，请求约8.221s。最终接续fresh scan/plan整个阶段15.034s，不能把它全部算为cuRobo。

尚未证明的因素：GPU争用、缓存key导致重初始化、附着球数×障碍数放大、不可行起终点导致重复优化、姿态约束与IK branch、超时后GPU残留工作。逐项测量，不直接归因。

## 测试矩阵

真实冻结用例至少：旧快JOG/36cm/45cm；本轮pick/pregrasp；PLACE旧过大payload失败；同scene修正payload；最后成功PLACE；合成明确BLOCK。
每例固定start/goal、scene/calibration/tool/model hashes。每配置冷启动1次、热运行至少20次；另用多随机种子检查成功率。报告所有失败，不仅成功延迟。

对照因素一次只改一个：

1. 当前代码FAST与10月15日FAST；25/50迭代，固定2/4 seeds。
2. 无附着物/旧附着物/修正附着物仅作诊断对照；无附着物结果不得成为执行候选。
3. 原world数量、分解world数量；几何保真保持不变。
4. persistent cache命中/失效、初始化、warmup、update_world次数。
5. FAST超时→取消确认→后续请求，验证无遗留GPU作业、无迟到结果进入执行。
6. QUALITY预算与尝试次数，失败原因分类：INVALID_START/GOAL、IK、NO_PATH、TIMEOUT、VALIDATION。

每次输出：queue、capture、scene、IK、init、warmup、update_world、solve、dense validation、orientation、retime/native、证据写盘、总点击等待；GPU显存峰值/占用、sphere数、obstacle数、cache key/reason、trajectory hash、结果。p50/p95/最大值和成功率一起报告。

## 最小优化顺序

1. 统一FAST策略构造，入口差异可见且测试覆盖；检测确定无效起终点后停止重复同请求求解。
2. 正确payload ownership与几何绑定，避免把dock当持物；不能为提速删除实际障碍。
3. 持久服务、同一几何构建key复用、一次update_world/一次正式solve，关闭重复warmup。
4. profile化有界FAST/FALLBACK及可确认取消；只在不同seed/有效profile能提供价值时重试。
5. 证据写盘异步与静态模型预加载；完整真实回放验证后再讨论生产部署。

目标：支持场景热规划p95≤2s为期望，复杂case明确有界fallback；不能硬承诺所有路径2s成功。全链点击等待另设SLO，不混入solve。速度和controller保护不属于本轮优化变量。

## 全链验收

将此次接续模型处理并入正式Scheme的准备步骤；重复执行不能复用旧授权/lease。19/20阶段差异以当前runner阶段表为准，报告实际序列。
测试暂停、取消、planner超时、base未settled、目标变化、ID3失败、释放读回失败、attach/detach失步、断电重启；副作用阶段exact-once，故障恢复不能重复close/release/base命令。
最终输出自动离线完整replay、真实GPU用例对照、剩余现场验收项；不运行真实运动。
