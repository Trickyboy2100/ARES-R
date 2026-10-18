# RC1 三维离线任务审查

**只需打开 [full_cycle_replay.html](full_cycle_replay.html)。** 单文件自包含，脚本、数据、指标图和MP4均内嵌，不需要服务、Python、网络或GPU。支持阶段切换、拖动时间轴、播放/暂停、TOP/FRONT/RIGHT/3D与拖拽旋转、原生/source序列切换、点云归属对比和近场案例。

所有画面均标注 **SYNTHETIC SCENE / REAL CUROBO TRAJECTORY / NO PHYSICAL MOTION**。这是一层基于 `387e510` 冻结证据的可观察结果，不是现场几何或实际执行认证。原 `replay_evidence.tar.gz`、`RESULTS.json`、`stage_timings.csv`、`manifest.json` 和golden两个文件均保持原字节。

## 可以直接打开的画面

|文件|内容|准确数据来源|
|---|---|---|
|[full_cycle_replay.html](full_cycle_replay.html)|完整19阶段、四视角、点云/碰撞体/夹爪/持物、图表、现场缺口；内嵌视频|原归档 `rc-final-normal`，运行ID `df571703cfe74d409d35ed2eee6b622f`；647个保存native关节样本、3段原GPU规划、19个完成快照|
|[full_cycle_replay.mp4](full_cycle_replay.mp4)|1600×1250，H.264，318帧/12fps，26.5秒|同一HTML渲染器；native每3个原始样本抽1帧并包含端点，底盘每段12个名义插值帧，其他阶段3帧；**非固定播放倍率、非实机时钟**，见 [video_sampling.json](video_sampling.json)|
|[01_pregrasp_four_views.png](keyframes/01_pregrasp_four_views.png)|预抓取四视图|`rc-final-normal/native/pregrasp.txt`，31点，2.40秒|
|[02_contact_four_views.png](keyframes/02_contact_four_views.png)|contact末端四视图|`native/contact.txt`，93点，7.36秒；source来自原P1预检IK，不伪称contact本身由cuRobo求解|
|[03_lift100_four_views.png](keyframes/03_lift100_four_views.png)|100mm初始抬升四视图|`native/lift.txt`，386点，30.80秒；HOLD_CANDIDATE尚非确认抓取|
|[04_hold230_four_views.png](keyframes/04_hold230_four_views.png)|230mm持物四视图|`native/HOLD230.txt`，105点，8.32秒；source为原真实cuRobo HOLD230规划|
|[05_base_at_place_four_views.png](keyframes/05_base_at_place_four_views.png)|三段名义转场后四视图|`job.json` 的三段 `base_pose` 完成快照，−30cm/−85cm/+30cm；仅名义位移，无里程反馈|
|[06_preland40_four_views.png](keyframes/06_preland40_four_views.png)|PLACE上方四视图|`native/PRELAND40.txt`，32点，2.48秒；原真实cuRobo规划；合成ID3、lower_middle偏置、+40mm|
|[07_release_four_views.png](keyframes/07_release_four_views.png)|模拟释放四视图|原 `RELEASE` 结果及PRELAND末端；物体停在释放位置，不模拟下落或落座|
|[08_return_four_views.png](keyframes/08_return_four_views.png)|不收臂名义返回四视图|原逆路线三段快照；关节维持原PRELAND末端，底盘返回0，不是扫掠净空证明|
|[hold230_top.png](hold230_top.png)、[hold230_3d.png](hold230_3d.png)|放大的TOP与3D|与HOLD230四视图完全同源|
|[point_ownership_3d.png](point_ownership_3d.png)、[point_ownership_top.png](point_ownership_top.png)|同视角抓取前/持物后/过滤后|原3个SceneSnapshot与clean_residual.npz、attachment_filter.json、point_ownership|
|[point_ownership_closeup.png](point_ownership_closeup.png)|全部343个删除点的近景|保存的owned点+同一pinned FK+原removed_indices重建；过滤mask逐点一致|
|[near_clear.png](near_clear.png)|近场CLEAR对照|新增真实cuRobo CLEAR输出，障碍相对中段扫掠中心移开200mm|
|[near_avoid.png](near_avoid.png)|真正绕过运动区中的障碍|新增真实cuRobo AVOID输出；原路径净空−25.69mm，新路径+5.18mm，最大偏离直线71.41mm|
|[near_block.png](near_block.png)|目标被占用的拒绝|真实GPU pipeline初始化后，独立端点检查净空−36.47mm，拒绝INVALID_GOAL_COLLISION；**优化器0次，不把搜索超时称作数学无解**|
|[near_legal_contact.png](near_legal_contact.png)|有实际几何相交的受限接触例|原contact native原样保留，新增合成终端目标；普通world净空−20.26mm、限定目标豁免及非目标工具碰撞检查通过。是实际CPU/URDF/policy验证，**无新增GPU求解、无物理接触反馈**|
|[stage_engineering_metrics.png](stage_engineering_metrics.png)、[SVG](stage_engineering_metrics.svg)|阶段耗时、GPU调用/solver、水平误差、世界净空、显存、TCP高度|原 `stage_timings.csv`、3个planning.json、gpu_calls.json、原native及其审计；N/A绝不填零|
|[native_retiming_comparison.png](native_retiming_comparison.png)、[SVG](native_retiming_comparison.svg)|31.44→7.36秒contact；98.96→30.8秒lift|原RESULTS.native_retiming：同一合成源路径、同一速度/加速度上限，非10月16日115秒/72秒实测复现|

AVOID 的 +5.18mm 仅为该合成难例的硬碰撞通过，**未达到30mm偏好净空，不可直接用于现场执行**。新增案例的所有请求、实际GPU输出和独立证明均在 [near_obstacle_evidence/](near_obstacle_evidence/)。画面中的红色原路径是碰撞反例，绿色为新的真实cuRobo结果，没有把理想化TCP直线当作规划结果。

## 怎样读机器人和点云

- 右臂由保存的关节序列逐样本驱动；FK用pinned URDF的joint origin与axis计算。连杆形状使用实际碰撞盒，夹爪显示实际保守包络，raw开合只作示意；现场CAD外观/真实finger关节反馈缺失。显示关节舍入到1e−12 rad、点坐标到1e−6m，原文件与哈希仍保留全精度。
- 左臂用快照中合成只读q=0和配置名义安装矩阵，**其URDF→现场坐标映射没有commissioned**。规划真正使用的是另一个保守inactive-left-arm代理盒，不能根据这幅左臂外观判断真实双臂净空。
- 底盘仅按保存的相对位移作显示插值；没有真实里程/地图姿态。环境是BODY局部SceneSnapshot，PLACE场景按其名义采集底盘位置摆放；跨站世界配准未被证明。释放后物体固定，无落座证据。
- 抓取前8575点；持物后原始输入8575点；删除343点；过滤后8232点；受保护结构1372点。删除只根据保存的归属样本匹配，保留table/dock/partition/inactive-left代理。原始未过滤持物传感器帧未写入归档，图中明确标为**重建**，不能冒充新采集。
- [stress_scene_audit.json](stress_scene_audit.json) 显示640个障碍 **0/640** 与保存的机械臂+持物扫掠并集AABB相交，最近AABB间距809.38mm。它是规模压力测试，不是绕障证明。

## 正式Live检查、已修复和仍缺少的功能

|项目|本轮结果|边界/后续|
|---|---|---|
|不存在的`gripper_open_raw`|已修复，使用实际存在的`gripper_release_raw`及时间戳/上下限合同|真实raw不能独立证明物体仍被夹持；resume后的视觉复核仍缺少|
|释放状态与resume/detach|新增`preland_arrived`、`release_confirmed`持久化；确认释放后状态为RELEASE_CONFIRMED；无确认禁止detach|原生SDK/串口真实释放和物体落座SITE_PENDING；旧site checkpoint无新profile签名会拒绝自动恢复|
|ID1/ID3与配置版本|绑定右臂profile、object_id、完整命令、现有commissioning标记，并把profile签名绑定checkpoint|配置中的历史COMMISSIONED标签不是本轮现场新标定证据|
|Stop与晚到READY|正式client传递所属job取消，回收worker；generation锁拒绝晚到计划重新READY；真实GPU客户端取消已通过|真实native servo/AMR物理停止仍待现场验收；子进程退出不等于已物理静止|
|接触目标配对|原CONTACT_BYPASS不检查工具/world，新增正式roundtrip门禁只豁免明确目标、保留工具对非目标world检查；source拒绝不能由retiming fallback绕过|golden原文件未改；新的门禁须与正式Live一起部署。实际工具/物体几何仍待commissioning|
|持物与正式scene路径|直接调用Live合同，核对POST_LIFT、attached identity、AUTO_FRESH、230mm绝对目标及PLACE链路|mock I/O合同不等于真实相机/Epic/SDK端到端覆盖|
|左臂短暂不可用|修复离线故障别名；直接正式telemetry测试两次SystemError后第三次最小只读状态成功|原RC1`left_transient`与`left_read_transient`不匹配，原归档该案例**不能**作为故障注入通过证据；保留原报告，另附纠正|
|网络丢ACK后的现场恢复|不完整dispatch保持UNCERTAIN、拒绝盲重发|与离线有完整设备账本不同，真实native/gripper/AMR自动证据核对流程尚未完成，需要人工核对|
|自由空间独立自碰撞|cuRobo启用self-collision；另有独立world sphere/cuboid验证|其validator明确`self_collision_independently_checked=false`；不能称作独立自碰撞通过|
|初始100mm的候选持物外形|保持原受控抬升和后确认协议；新增工具非目标门禁已生效|尚未把未确认的candidate tray作为独立载荷包络检查全程，需补充软件安全覆盖；不能据当前pass推导真实持物任意净空|
|底盘转场/返回全身扫掠、落座、10GB并发|全部明确SITE_PENDING|全机器人/载物/释放后扫掠；现场SDK新binary、TCP/手眼/碰撞球、实际Epic帧与并发负载均需实测|

详见 [adapter_coverage.json](adapter_coverage.json)、[Live合同回归](live_contract_regression.txt)、[Stop晚到门禁](inflight_stop_regression.txt)、[正式client真实GPU取消凭据](site_planner_stop_receipt.json)、[原native新增目标范围检查](existing_native_scope_review.json)。这些修复并未把发布状态提升为现场可自动执行。

## 时钟与证据

GPU pipeline墙钟含IPC、初始化及独立校验；solver时间为CUDA同步后的调用墙钟，不是伪造的CUDA-event纯设备时间。native是所保存重定时序列的预计时长；底盘29秒是总距离÷0.1m/s。动画使用这些不同来源的展示混合轴，短事件最低展示0.15秒；实机总周期数据不存在。

[provenance.json](provenance.json) 保存原始归档/模型/native哈希，[source_catalog.json](source_catalog.json) 逐文件列出已读取的1585个归档成员，[replay_data.json](replay_data.json) 是HTML内嵌数据的同源独立副本。[browser_qa.json](browser_qa.json) 检查交互、无外部请求、无JS错误和视频，[fk_crosscheck.json](fk_crosscheck.json) 交叉检查15个native姿态、每姿态7个link的JS/Python FK。[review_manifest.json](review_manifest.json) 和 [SHA256SUMS](SHA256SUMS) 固定本层代码/资产/可视化版本。

## 重建和当前分支部署检查

无需重跑RC1或重新规划主任务：

```bash
.venv/bin/python scripts/visual_review/prepare_evidence.py
# 仅当preview模型缺失时，从原有离线source bundle重建，不覆盖已有模型：
.venv/bin/python scripts/prepare_curobo_model.py worklog/runtime/preview-model --source-directory release/roundtrip-rc1/assets/preview-source
MPLCONFIGDIR=worklog/runtime/cache/matplotlib .venv/bin/python scripts/visual_review/assemble_visuals.py
# 截图/视频重建需本机Playwright与Chrome，脚本可用ARES_VISUAL_PLAYWRIGHT、CHROME_BIN指定路径：
node scripts/visual_review/capture_replay.cjs --video
ffmpeg -framerate 12 -i worklog/runtime/visual-video-frames/%05d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart visuals-review.mp4
# 387e510原manifest作为历史快照保留；本层代码的部署校验显式选择新清单：
.venv/bin/python scripts/roundtrip_deploy_check.py --manifest release/roundtrip-rc1/visuals/review_manifest.json
```

保留原[两天现场手册](../OPERATIONS.md)，优先补齐上述软件缺口与实机证据。不能忽略历史manifest对新代码正确报告的版本差异，也不能根据这些合成画面批准现场自动运动。
