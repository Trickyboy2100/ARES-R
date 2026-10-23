# 抓取/复位流水线优化与首次不中断实测

## 验收结果

2026-10-23，独立RC1目录完成一次自动闭环：fresh observation → 预抓取 → 接近55mm → 闭爪 → 连续抬升230mm → 验证 → 原路下降 → 松爪 → 退出 → 回center。

运行：`20261023-pick-reset-r7-pipeline/execution`。

- `PICK_LIFT_REPLACE_RESET_COMPLETE`，`reset_complete=true`。
- 执行启动至回center：**134.536秒**，没有人工接续、故障恢复或跳过抓取验证。
- 抬升后5项gate全部PASS：真实样本时间有效、夹爪稳定、持物反馈、抬升到位、场景变化证据。
- 实测抬升相对目标参考点230.034mm。最终右TCP BODY `[0.354853703,-0.077536768,1.021136665] m`。
- 最终夹爪401，fault=0；各运动段有target_reached和Servo disable证据。
- 底盘、左臂没有执行运动。速度/加速度/跟踪上限、工具TCP、Demo补偿、持物尺寸及控制器保护未改变。

这是一轮成功，不等于多次稳定性或任意场景已commission。旧r5中断及单独返回不被改写为成功基线。

## 1. 实际代码修复

### 并行验证的数据过期

新增 `collect_during_scene()`：相机扫描期间持续读取真实夹爪反馈，保留最新窗口；扫描完成后再获取满足数量要求的新鲜窗口。采样间隔依据既有延时配置的最大相邻间隔，本次0.75秒，至少3个样本。不会提前采三次后空等，也不会修改采集时间或验证器时钟。

实机最后3个反馈为37/36/36，真实采样间隔约0.80秒。原有5秒新鲜度规则保持不变，最终 `GRASP_CONFIRMED`。读回进程与扫描独立，不共享 `Live.child` 子进程槽，避免并行操作互相覆盖进程引用。

### 每段外围等待

新增 `StationaryBaseMonitor`，整个实验保持只读轮询，保存至少2秒的真实IDLE+map+motion log/queue稳定窗口。每段使用新鲜窗口证明，而不是重新sleep两秒。窗口不足仍等待；过期、读失败、非IDLE、map或marker变化仍失败，并在运行期间触发停止检查。

到位仍按原有两次稳定反馈确认；第二次确认的完整telemetry直接作为arrival记录，取消随后重复读取一次全量双臂状态。没有取消起点/左臂/tool检查，没有缩短静止证明的时间跨度或放大到位容差。

每段新增 `*.phase-timings.json`，细分read_state、base_window、native_validate、scene_invalidate、native_send、settle。

### Native打包与下一段准备

1. 几何准备阶段已验证的原始lift路径，其通过证明绑定完整points/request/package哈希；打包时仅对完全相同的输入复用。改变scene、工具、持物或路径即拒绝复用。新拟合后的曲线仍执行原有完整验证。
2. 初始仅打包pregrasp/contact及其reverse，manifest明确记录pending lift230/lower230。
3. 预抓取执行期间，独立后台进程完成lift Native及反向lower Native准备。
4. 到达预抓取后、接触前，等待并检查后台结果、全部路径/参数/scene/package绑定及Native hashes。失败、超时或不完整就不进入接触阶段。
5. manifest通过临时文件原子发布；旧文件不覆盖；故障/取消会清理后台准备进程。

本轮预抓取期间的后台lift打包耗时9.675秒，后续 `NEXT_NATIVE_READY` 实际等待仅 **0.00674秒**。下一段准备已被当前段运动覆盖，而不是在接触或抬升前继续等待十几秒。

## 2. 准备与规划计时

| 项目 | r7实测/量模型，秒 |
| --- | ---: |
| planner初始化/就绪，与扫描并行 | 0.452 |
| 观察事务与场景生成 | 15.789 |
| contact几何与IK | 1.865 |
| cuRobo完整请求，外层 | 3.010 |
| first-pick package | 0.299 |
| lift/reverse几何检查 | 7.823 |
| 几何准备关键路径总量 | 28.811 |
| 初始4份Native打包，各段相加 | 3.442 |
| 启动前准备量模型 | **32.254** |
| 运动期间后台lift/lower打包，各段相加 | 9.676 |
| 后台准备完成后的额外等待 | **0.00674** |

“准备量模型”不含Codex工具调用间隙、独立命令之间的人工等待及少量进程启动开销，不是WebUI点击到运动的实测。准备加执行的内部量模型约166.79秒；当前准备/启动仍为独立调用，不能把该值当作已测得的单按钮端到端延迟。

r5启动前准备量模型54.622秒，r7为32.254秒，减少约22.37秒。但r5包含不同的冷/graph状态，且两次fresh场景和轨迹不完全相同，只作为现场前后对照。

## 3. 同一冻结输入的打包严格对照

另在机器人回center后，使用同一r7 scene/request/package/path，对比保全tar中的旧打包器与新打包器。该benchmark不采集、不控制硬件。

| 项目 | 旧 | 新 | 节省 |
| --- | ---: | ---: | ---: |
| 完整6份Native打包wall | 19.174s | 13.609s | **5.564s / 29.0%** |
| 其中lift Native几何/retime打包 | 15.585s | 9.787s | 5.798s |

六份Native除capture timestamp以外逐行相同，包括关节采样、速度、加速度、时间间隔、工具和软限位头。`identical_native_except_capture_timestamp=true`。

这证明优化没有通过删碰撞检查、改变运动形状或提速改变Native轨迹。单次串行benchmark不代表p50/p95；实际流水线又将剩余打包时间放进运动窗口，所以关键路径收益不止CPU计算节省。

基线源码SHA256：`7c958914ee0904967ab6c94e158b1ecc30fa154b23dfab43472ef2c7af011656`。

## 4. 优化前后实机运动阶段

前值为r5 forward及其单独return，后值为r7一次成功完整运行。不同fresh目标产生的预抓取路径略有不同，因此同时比较sender时间和外围差值，避免把路径长度变化冒充外围优化。

| 段 | 旧阶段总时长 | 新阶段总时长 | 旧外围 | 新外围 |
| --- | ---: | ---: | ---: | ---: |
| 预抓取 | 31.370 | 30.472 | 4.83 | 2.246 |
| 接近55mm | 15.834 | 13.221 | 4.81 | 2.204 |
| 抬升230mm | 18.456 | 15.427 | 4.88 | 2.170 |
| 下降230mm | 18.537 | 15.422 | 4.95 | 2.160 |
| 退出55mm | 15.829 | 13.220 | 4.81 | 2.197 |
| 回center | 31.366 | 30.465 | 4.83 | 2.241 |
| 合计 | 131.391 | 118.227 | **29.107** | **13.218** |

外围开销平均由4.851秒降至2.203秒，六段节省 **15.889秒，约54.6%**。旧sender总计102.285秒，新sender总计105.009秒，说明收益不是依赖新的运动更短。

剩余每段开销已定位：完整双臂读取约0.601秒；两次到位采样合计约1.283秒；Native静态校验约0.101秒；scene invalidation约0.100秒；sender退出/轮询及文件处理等为余量。base_window查询本身约0.00002秒，但后台持续采样仍在运行，不能称底盘检查被取消。

下一步如继续优化，应优先研究只读SDK连接复用与遥测采样成本。当前没有把2.2秒全部去掉，也没有修改两次到位确认要求。

## 5. 完整成功循环的阶段表

| 阶段 | 秒 |
| --- | ---: |
| 夹爪runtime预检 | 0.101 |
| 夹爪40% | 1.261 |
| 预抓取 | 30.472 |
| 后台Native ready等待及绑定校验 | 0.00674 |
| 接近 | 13.221 |
| 闭爪 | 0.407 |
| 抬升前验证 | 2.005 |
| 连续230mm抬升 | 15.427 |
| 抬升后并行验证 | 8.188 |
| 原路下降 | 15.422 |
| 释放 | 1.259 |
| 退出 | 13.220 |
| 回center | 30.465 |
| 运行启动至完成，含未单列启动确认/校验 | **134.536** |

旧r5中断80.53秒加单独返回68.31秒，累计148.83秒，仅为分段参考，不能宣称与新134.54秒构成严格连续周期A/B对照。

各段max/p95 tracking error（deg）：pregrasp0.275/0.267，contact0.152/0.146，lift0.525/0.516，lower0.393/0.385，retreat0.286/0.278，center0.457/0.447。无fault/abort，原1.5度跟踪阈值未放大。

## 6. 文件、测试和保全

新增公共实验工具：`src/ares_r/manipulation/pick_reset_pipeline.py`，含滚动采样、连续静止观察、exact-input proof绑定。

实验入口：`scripts/run_pick_reset_timing.py`；打包入口：`scripts/package_pick_reset_timing.py`；准备入口：`scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py`；冻结benchmark：同目录`benchmark_native_packaging.py`。

启用当前流水线时，准备完成后打包 `--segments pregrasp,contact,retreat,center`。canonical现有 `POST /api/operations/pick-reset-timing/start` 启动同一实验runner；没有新建第二套物理执行器。该入口仍要求监督授权，不会开机/刷新自动运动。

现场成功目录：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261023-pick-reset-r7-pipeline/`。

现场冻结对照：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261023-native-packaging-frozen-r7/`。

现场旧源码保全：`worklog/preservation/20261023-pipeline-v2-before/source-before.tar.gz`。r6记录了一次无运动的证据编码兼容错误：已有planner证据含Infinity诊断哨兵，已修复为与现有序列化一致；修复后的r7重新fresh采集，没有沿用r6失败候选。

全量回归：**811项，0失败，1项跳过，12.091秒**；新增实验回归15项通过，覆盖慢扫描新鲜窗口、旧数据拒绝、取消/相机失败、输入绑定变化、完整静止窗口、分段Native追加与防覆盖。

已拉回本机证据包：`/Users/andyee/Documents/ChatGPT/local/site-private-20261023/20261023-pipeline-completed-checkpoint.tar.gz`。

SHA256：`906e99cba740da3c35f0982540bb59f2162a089c2ca4cde5029324a66b1c69bd`，两端一致。包内含请求、proof、Native、逐点反馈、阶段计时、manifest、旧源码和冻结对照；本次明确排除了PLY/NPZ/NPY/图片，不能称完整原始点云归档。原始数据继续留现场，不公开上传。

本轮仅保存独立实验改动，不修改golden、生产速度、底盘路线或工具定义，不自动push。
