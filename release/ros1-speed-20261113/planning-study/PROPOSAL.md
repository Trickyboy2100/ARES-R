# Demo01 总周期提速方案与冻结GPU基准

2026-11-13。仅进行冻结数据规划、验证与打包，无机械臂运动、无新扫描、未修改生产规划参数。当前提出实施方案，尚未将最快验证后端接入生产请求。

## 已确认的130秒开销

成功run为58df747107b04591a49fb0378db300a7，总130.38秒，实际运动29.01秒。center第一次FAST因新场景模型中的起点重叠约1.54mm失败，耗9.20秒，随后换场景和QUALITY请求耗51.93秒。QUALITY worker内部42.89秒，其中18.42秒为丢弃结果的预热solve，17.85秒为正式solve。返回段FAST worker7.73秒，runtime_reused=false，独立验证2.19秒。

当前runtime池最大1个，FAST和QUALITY配置是不同cache key，切换会回收CUDA worker。两次FAST请求的相关构造配置对照一致；当前观察到的冷启动主要与中间切换QUALITY相关。

## 相同场景、起终点、模型下实测

两份输入来自成功run的center和restore planner_request，各策略各3次，共24次，全部solver/碰撞验证成功。每组第1次为runtime冷启动，第2/3次为热请求。热值为两次中位数，不具备大样本p95意义。进程启动、外层Torch import、扫描、机器人SDK、HTTP、Native打包和实际运动不包含在worker耗时内。

| 策略 | center热worker秒 | restore热worker秒 |
|---|---:|---:|
| FAST50 + NumPy独立验证 |3.244|3.424|
| FAST100 + NumPy独立验证 |3.937|4.094|
| QUALITY，跳过请求内预热 |24.168|30.847|
| FAST50 + 既有Native CPU独立验证 |1.247|1.286|

FAST50+Native的runtime冷请求分别5.79/5.96秒，仍需服务准备阶段预热。Native验证仍检查相同模型/密集样本；代表轨迹与NumPy参考的最小距离差分别0及2.08e-17米，collision_free一致，并经过完整Native打包验证。没有通过删除验证或障碍获得提速。

## 应优化规划加运动总成本

代表热请求与同轨迹打包后时长相加如下，尚未计入扫描、状态、发送开销。

| 策略 | center秒 | restore秒 |
|---|---:|---:|
| FAST50+Native |20.60|14.57|
| FAST100+NumPy |23.30|17.37|
| QUALITY无预热 |35.79|42.98|

QUALITY的center轨迹预计12.72秒，FAST为19.36秒，但QUALITY多花的规划时间超过其运动收益。restore两者运动时间几乎一样。因此当前数据支持FAST50+Native常规入口。

## 第一批最小改动

1. 将现有independent_distance_backend=NATIVE_CPU_V1传入Demo01的规划请求，保留同等密集采样、关节/姿态/碰撞和Native检查。先对回放集验证结果一致，再逐Demo开放。
2. 固定常规FAST50 2轨迹seed/4IK seed/CUDA graph常驻runtime，准备阶段完成预热与运行版本校验。新的world通过update_world载入。准备产物不作为可执行旧scene。
3. 根据失败类别决定下一步。工具/模型/空采集/Native包错误直接报具体原因；INVALID_START/GOAL先诊断并按规则重新观测，同一非法scene切QUALITY无助于解决。只有真正求解不收敛才进入额外搜索。
4. 姿态的IK/2π分支先按限位、连续性和预计运动代价筛选，再求解，减少绕转和超Native excursion导致的无效重试。
5. 同一个有效SceneSnapshot中的有限重试可使用同一world和热runtime，执行前重新核对状态绑定。新的机械臂/底盘移动仍使scene失效；下一运动段使用新扫描。
6. 保留已经验证的ARC_LENGTH_EXACT_V1与LEGACY回退，速度/加速度上限0.2，跟踪阈值1.5度。
7. 输出scene、queue、cold/warm、solve、validation、package、SDK/arrival和实际运动分项，记录请求策略及实际worker source SHA。一个阶段失败不再只回RESTORE_CUROBO_PLAN_FAILED。

## FAST100、QUALITY和并行

本回放FAST100没有带来成功率或路径时长收益，所以不作为默认。当前cache key包含迭代policy，直接FAST50→FAST100也可能重建runtime；实施有界升级前需要让迭代预算与构造参数分离并验证CUDA graph复用，或准备独立已预热fallback runtime。

QUALITY保留为复杂场景搜索后备。单纯去掉warmup不足以达到2秒，实测仍24～31秒。若接入生产，要给出明确的搜索预算和取消语义，并单独测成功率收益。

当前GPU为RTX3060 Laptop 12GB，单路QUALITY求解时接近99%GPU利用率。双常驻worker容量可能允许，但FAST+QUALITY同时算会竞争GPU，且独立验证还有CPU成本。未进行竞速benchmark，不能宣称并行更快。若以后比较，必须测同一scene上的并行完成时间、显存峰值、结果验证、取消确认和轨迹唯一选择，生产只执行冻结的一个结果。

优先并行不争夺同一GPU的工作：独立CPU参数/哈希准备与相机传输、GPU runtime初始化与CPU场景构建、当前段执行与下一段静态任务准备。下一段完整world与轨迹在实际到位后绑定新观测，不能复用运动前的旧scene冒充新scene。

## 总周期模型与下一验收

两段离线FAST50+Native规划约2.53秒，预计路径发送时长合计32.64秒，二者合计约35.17秒；这是局部理论成本，未包含实时扫描、现场误检、IK预处理、机器人SDK、发送准备与到位确认。若这些外围阶段仍约20～35秒，整轮预估55～70秒。该范围是待实测模型，未作为承诺或现场验收结果。

先在相同起点和有效场景做新旧完整两段对照，达到较130秒显著下降；分别记录规划失败率和外部等待。每组仅两次热数据不足以证明最坏延迟，后续需补至少10次冻结重复和困难/无解场景，之后再汇报p95。当前两份回放的center modeled gap约1.10mm，说明场景模型鲁棒性仍是独立交付问题，不能由速度优化掩盖。

现场完整基准文件位于 /home/yikun/ARES-R-RC1-20261019/worklog/evidence/ros-planning-study-20261113/。benchmark.py仅调用production_scene_worker.main与Native包装器，不提供运动入口。
