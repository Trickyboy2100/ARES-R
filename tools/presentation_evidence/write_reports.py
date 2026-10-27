"""Assemble source-indexed audit narrative from receipts; never fills missing data."""
import argparse,json,hashlib,subprocess,statistics,csv,re,zipfile
from pathlib import Path
from replay_rasc import load,save,sha
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args();o=a.output;(o/'reports').mkdir(exist_ok=True);(o/'math').mkdir(exist_ok=True);m=load(o/'runlogs/rasc_stage_metrics.json');gpu=load(o/'runlogs/compare_planning.json');cpu=load(o/'runlogs/cpu_backend_comparison.json');query=load(o/'runlogs/contact_query_comparison.json');servo=load(o/'runlogs/servo_trace_metrics.json')
def write(p,s):p=o/p;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(s.strip()+'\n')
def median(rows,key,val):return statistics.median(r['elapsed_s'] for r in rows if r[key]==val)
ref=median(cpu['runs'],'backend','NUMPY_REFERENCE');nat=median(cpu['runs'],'backend','NATIVE_CPU_V1');linear=median(query['runs'],'indexed',False);indexed=median(query['runs'],'indexed',True)
write(Path('INPUT_INDEX.md'),f'''# 输入与来源审计

执行基线：工作单21cd158；算法基底6866106；实际GPU worker关节映射修复8fbd669。独立工作树，未切换/修改原RC1。

| 输入 | 匿名化定位 | SHA256 / 核验 |
|---|---|---|
| 同源CAMERA原始NPY | 20261010_114817_fecbdf64 | `{m['source_camera_sha256']}`，实际读文件核验 |
| BODY NPZ | 20261010_114819_091f37ab | `{m['body_sha256']}`；原始NPY经过固定TF，float32逐元素一致 |
| 配套场景 | SCENE_133c1fca71484bd2abea0cb3e0b6af8d | 同目录whole_robot_geometry、双臂FK audit、scene_report、snapshot |
| 标定 | 固定T_BODY_CAMERA | `{m['transform_revision']}`；没有重新估计外参 |
| 双臂capture q摘要 | whole_robot_geometry | `{m['robot_state_hash']}` |
| 工具版本 | 同帧几何快照 | `{m['tool_calibration_revision']}` |
| 原历史transit规划request | Oct10 transit_plan | `{cpu['source_request_sha256']}` |
| 原历史transit规划result | Oct10 transit_plan | `{cpu['source_trajectory_sha256']}` |
| 机器人URDF | ARES@b978cbd… | `{cpu['urdf_sha256']}`，git对象取出并与请求asset_sha256一致 |
| cuRobo | pinned 8e734f3ced1df898990bcd92de40abce475907db | worker运行时核对整个源文件Git blob manifest |

原始点云、完整关节/设备记录及派生几何保留于忽略的私有运行目录，不提交。公开输出只有经过审查的渲染、标量、匿名摘要和源码。工具通过CLI接收受控数据根目录，禁止自动采集或现场下载。

原始输入是2026-10-10采集，不能称为9/21的7→167帧，不能称为10/21的401框/431采样实验。

关键状态边界：capture q用于原始点云自体过滤；历史transit request的规划q0与capture q不同（最大约177.75°），两种表示使用相同的规划q0与目标。该离线A/B是静态冻结世界表示消融，并不证明fresh ObservationEpoch到实机执行的状态绑定通过。原历史request缺attached revision元数据，本轮仅补充身份绑定；没有删除新世界的任何基元。

本地还有10/10 160941、172331两组真实原始NPY/BODY配套数据。本轮不将它们猜测为CLEAR/AVOID/BLOCK标签。9/21原始capture与10/21 tar不在已检查的工作区/本地素材目录；具体缺口见报告。
''')
write(Path('reports/RASC_REPRODUCIBILITY.md'),f'''# 同一真实scan的六阶段重放

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
''')
lines=[]
for r in gpu['rows']:
 v=r.get('independent_validation') or {};lines.append(f"| {r['representation'].upper()} | {r.get('result')} | {r['endpoints']['start']['min_clearance_m']*1000:.3f} | {r['endpoints']['goal']['min_clearance_m']*1000:.3f} | {v.get('min_clearance_m',0)*1000:.3f} | {r.get('timing_s',{}).get('planning_samples')} |")
write(Path('reports/AABB_VS_RASC_AB_EXPERIMENT.md'),f'''# 同源几何/规划A/B

状态：DONE，FROZEN_REPLAY；没有得到OLD fail/NEW pass，不制造成功差异。

OLD：同一清理点云连通簇→32个AABB。NEW：同一3747点→235个多基元。两者逐点覆盖3747/3747；观测盒全部统一每侧7mm膨胀。已知桌面、非活动臂、机身保持相同。此处统一膨胀为因果消融，区别生产SUPPORT role最多4mm padding。

未膨胀体积之和 {m['old_sum_volume_m3']:.9f}→{m['new_sum_volume_m3']:.9f}m³；膨胀后 {m['old_inflated_sum_volume_m3']:.9f}→{m['new_inflated_sum_volume_m3']:.9f}m³。都是sum，不是union。剖面2mm网格显示OLD-only表示面积，并公开选择最大差异Z层的规则；不把没有点/遮挡区域称为传感器已证明空闲。

同一request来源、q0、目标T、link6/TCP、持物、夹爪/arm盒、安全限幅、random_seed=123、2轨迹/4IK、50 iterations、CUDA graph、single pass。安全摘要两行必须一致。runtime_motion_goal会对输入qgoal做微小目标投影，两种输出终点相同；不是手工绕障线。cuRobo原理图表示上游能力；本次solve_cspace的目标由ARES-R RuntimeGoalIK解析，配置4个IK seeds并不证明本次调用了上游GPU IK。A/B仅证明两表示使用相同派生运行限制，不证明与缺失的原site runtime YAML动态限幅等价。

| 表示 | 结果 | start gap mm | goal gap mm | independent path gap mm | 单次solve wall s |
|---|---|---:|---:|---:|---|
{chr(10).join(lines)}

两次都是冷worker请求，非P50/P95。OLD路径236.140mm，NEW231.706mm；OLD最小净空56.942mm，NEW54.982mm。几何更细并没有保证本例更大净空或更快求解；仅一组输入无法得出全局鲁棒性结论。

实际GPU均RTX3080，峰值allocator allocated852749312B / reserved989855744B；不代表整卡占用或10GB视觉共驻认证。独立world validator PASS；independent self collision=false，cuRobo内自碰撞仍启用。未把两者混为全套独立验证通过。

运行适配：原现场YAML缺失。由pinned ARES YAML保留六臂轴cspace参数，锁定非规划夹爪DOF为0、导出link6；URDF字节不改，夹爪/payload碰撞来自冻结request。导出原生finger frame、7DOF cspace不匹配、locked DOF七列输出的失败均在本地日志与runtime_adapter*摘要保留。最后一项暴露正式worker固定reshape缺陷，独立修复8fbd669，5项回归。不是偷偷换成preview模型并宣称现场几何通过。

原历史request缺attached revision字段，但exact attached object ID已不在旧world中。本轮仅补元数据；新多基元未删除任何障碍来通过。capture q与规划q0不一致见INPUT_INDEX，这是静态冻结世界表示实验，不是fresh epoch执行审批。

worker未导出中间seed轨迹，因此只画最终选中真实轨迹。candidate_paths不造假；图位记录BLOCKED_SEED_INTERMEDIATES_NOT_EXPORTED。没有有认证标签的真实CLEAR/AVOID/BLOCK三组scan，故该独立系列待补。
''')
servo_lines=[]
for i,s in enumerate(servo):servo_lines.append(f"| {i+1} | {s['samples']} | {s['logged_span_s']:.4f} | {s['max_error_deg']:.6f} | {s['rms_error_deg']:.6f} | {s['p95_abs_error_deg']:.6f} | ABORTED |")
write(Path('reports/SERVO_TRACE_AUDIT.md'),f'''# ServoJ真实成对日志审计

有真实成对target_rad、actual_rad与monotonic；没有本轮硬件动作。两个来源位于仓库9/7 cuRobo supervised micro目录，SHA见runlogs/servo_trace_metrics.json。字段/来源与当前jaka_micro_servo的telemetry语义交叉核对，未用FK代替实测。

两例均计划41个点，但实际只记录14/17个sample，随后abort_accepted、servo_disabled；没有target_reached，不是正常完成段。不能把截断曲线说成稳定成功或速度优化效果。中止根因在这两份日志中未完整记录，不能仅凭当前源码推断唯一原因。

关键对齐：current adapter在读取actual之后才发本条target，因此同一记录target/actual并不同步。target-vs-actual原样显示；跟随误差图使用actual[k]−target[k−1]，第0点以初始command参照。不移动时间轴来人为重合。实际反馈是dedicated telemetry joint_actual_position_rad，不是SDK FK或controller_reported_rad；某些历史字段不能据名称简单当同一种feedback。

| 例 | 成对样本 | 已记录span s | previous-command max° | RMS° | P95° | 完成状态 |
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(servo_lines)}

每例独立六关节目标/回读、六关节误差、J6速度/加速度图，保留全部样本。差分用np.gradient实际不规则monotonic，无滤波；记录稀疏且噪声显著，不报告jerk或动态安全认证。日志span不等于计划duration，也不等于完成运动耗时。

9/24正常pregrasp/contact/lift跟踪汇总仅历史报告可引用（0.591/0.036/0.045° max等），对应完整成对sender日志未在本地取得，故不重建正常完整任务波形，不把9/7微运动代替9/24抓取。需要原native_supervised.jsonl、原native文件、单调时间字段、样本周期、错误与settling/arrived读回。
''')
write(Path('reports/LATENCY_METHOD_AUDIT.md'),f'''# 分层性能与计时边界

本轮同一10/10原transit路径CPU回放：NUMPY_REFERENCE median {ref:.6f}s → NATIVE_CPU_V1 {nat:.6f}s，含首轮3次各后端，所有301个dense samples、limiting object/component、gap与判决保持一致，gap容差1e−12m；不是历史431采样，也不是GPU加速。

本轮同一1814747点/235个bounds的局部inclusive查询：线性median {linear:.6f}s → cKDTree含建树 {indexed:.6f}s；返回数组（含顺序）逐一SHA一致，单轮返回合计256538点（不同查询可重复）。这是query kernel scope，不冒称完整contact artifact/pregrasp准备重测。三轮原始值均公开，未裁掉首轮开销。

历史10/21三项：17.023→1.125s独立CPU；15.176→0.830s完整接触几何；15.866→1.437s准备。来自6866106自带审计文档、不能离线重测的原study/cloud tar缺失。组成层可能重叠，不能叠加收益。历史冷/热GPU、100mm diagnostic与derived55mm case分开。

9/24 native-ready关键路径：六个事件窗口之和400.25s，显示保留分项求和：motion147.73s，non-motion252.52s。源报告aggregate motion为147.74s，有0.01s四舍五入差异，已披露。wait不能全归相机。没有完整scan→scene→GPU内部独占时间序列时，不伪造全链分段瀑布；本包瀑布从已知native-ready开始。

原606/395/255/205s是旧工程估算，非本轮实测或当前完整Demo周期。5700||5000并发采集仍需设备互斥/干扰审查，不能假称已产生现场收益。

GPU本轮OLD/NEW各一次、单次预算一致；OLD 5.328s solve wall / NEW6.994s，不绘制伪造P95与成功率。phase init约17.8s，两次均cold，持久worker价值不能仅根据这两次冷测折算现场收益。显存allocator峰值与整卡占用概念分开。

点云阶段2约1.47s、近机器人细化约1.34s仍占CPU主要时间。这里并未为画漂亮图降低体素精度或放宽膨胀。图像渲染、磁盘、源文件加载不计入算法计时；stage1预计算valid mask开销未计入且明确披露。
''')
write(Path('reports/UI_AND_SKILL_EVIDENCE.md'),'''# 实际界面与技能框架

6张界面均使用仓库原HTML/JS，由Playwright将全部请求拦截并用本地API fixture响应；不启动生产server、CanonicalBackend或设备自动发现。浏览器外部请求不允许；QA pageerror=0。界面没有补画按钮。

主界面点云来自10/10 FROZEN_REPLAY显示，Task Studio状态来自真实TaskStudio + ReplayCapabilityProvider注入OFFLINE_INJECTED_PLANNER_FAILURE，属于OFFLINE_SYNTHETIC，不能证明GPU技能执行或实机任务。Stop记录为真实replay runner stop调用，不是物理急停。

workbench是实际源码内的无运动入口页面，展示历史Golden恢复与模型尺寸对比。模型解释器的默认示例为示意尺寸，不是新传感测量。界面截屏单独加外部caption注明状态，保持原屏内容。

四套小框图对应skills/registry/runtime、world/scene_snapshot、canonical_backend、roundtrip状态机等实际文件。源码图不代表全部通用技能都已现场commissioned。task_parameterization_matrix只列配置变更与已知状态，不填写泛化成功率。

8–12秒后续安全展示分镜：0–2s加载离线冻结scene；2–4s打开Skill Palette；4–6s选move_pregrasp查看depends/resource locks；6–8s查看注入失败日志和run_id；8–10s工作台导入已保存attachment；10–12s旋转三视图。所有按钮只在离线fixture中演示，不输出机器人动作。
''')
write(Path('reports/ONSITE_ONLY_BACKLOG.md'),'''# 最小缺口与现场分镜

1. 正常完整ServoJ成对反馈：取9/24 live_pick_authorized对应pregrasp/contact/lift的native_supervised.jsonl、native轨迹、sample dt、monotonic+wall anchor、控制器错误、settling/arrived和hash。画三段正常曲线，不补采危险动作只为画图。
2. 9/21六阶段原帧：current_base_avoid/capture_pointer指向20260921_161451_830b7857 manifest + CAMERA源；BODY TF、同帧双臂q、geometry、tool与SHA。没有这些不能复现7→167/9992锚点。
3. 10/21完整study：f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8；cloud tar 206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60（已与源报告逐字核对，归档名20261021-study-clouds.tar.gz）。需要frozen-pregrasp-only-request、pick-epoch、431采样result、旧新性能原JSON及原site runtime YAML。原路径与完整依赖清单见源报告；本轮未取得这些归档。
4. 10/19空间持物/PLACE：缺before.json bd954fef…、fresh-ID3 98d2e1d…、preland proof58f19d…、native-audit4090d29…、descent轨迹c7e5ee…及planner包86c29cd…，完整哈希在golden/prepared-artifact-gaps.json。现有尺寸/事件只能支持尺寸示意与恢复时序，place_clearance_case不伪造。
5. LOCAL_PPT_WITH_DRAGGING_DEMO_NOT_FOUND：已检查本地可读PPT媒体索引，找到三类PPT、均无嵌入视频；需要负责人指明含3D点云/包络框拖拽演示的周进度PPT。原视频许可未核准前只在本地提取，禁止公开上传。
6. 正常完整物理filmstrip：8帧 detect/pregrasp/contact/grasp/lift/transfer/place/return，保留PLACE旧故障与修正后接续标识；需要原视频授权、时间戳与run对应关系。不得拼接旧动作+新模板声称泛化成功。
7. 现场底盘固定路线/no-stow扫掠、筛网/新专机跨对象任务、精确落座、10GB视觉与规划共驻均未由本包认证。现场需带对象几何/站位、TF/tool、q/AMR实际里程、run_id、GPU峰值整卡采样和abort日志验证；本轮没有现场连接。
''')
# Replace one manually abbreviated cloud-tar digest with authoritative source report value.
pth=o/'reports/ONSITE_ONLY_BACKLOG.md';txt=pth.read_text();source=(ROOT/'docs/reports/2026-10-21_CENTER_GRASP_PLANNER_STUDY.md').read_text();correct=re.search(r'`(206e[0-9a-f]{60})`',source).group(1);txt=re.sub(r'206e[0-9a-f]+',correct,txt);pth.write_text(txt)
write(Path('reports/REVIEW_AND_LIMITATIONS.md'),'''# 专业性与真实性审查：初版→改版

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
''')
# Code map is generated from actual definitions and line ranges in this checkout.
entries=[('CPU dense FK/world','src/ares_r/motion/independent_path_validation.py','validate_dense_world'),('Double precision native SDF','src/ares_r/motion/cpu_distance.py','distances'),('Indexed inclusive query','src/ares_r/manipulation/observed_contact_geometry.py','_bounded_cloud'),('Contact artifact','src/ares_r/manipulation/observed_contact_geometry.py','build_observed_contact_geometry'),('Thin SVD','src/ares_r/manipulation/collision_refinement.py','observed_obb'),('Persistent ownership/cancel','src/ares_r/motion/persistent_planner_service.py','runtime_key'),('Native retiming','src/ares_r/motion/native_execution_package.py','package_native_preview'),('Locked-joint extraction fix','src/ares_r/motion/planner_joint_mapping.py','extract_arm_joint_positions')]
code=['# 优化与适配代码位置','', '| 层/机制 | 真实函数/行 | 文件SHA256 |','|---|---|---|']
for title,path,fn in entries:
 lines=(ROOT/path).read_text().splitlines();start=next(i+1 for i,v in enumerate(lines) if v.startswith('def '+fn+'('));ends=[i+1 for i,v in enumerate(lines) if i+1>start and (v.startswith('def ') or v.startswith('class '))];end=min(ends)-1 if ends else len(lines);code.append(f'| {title} | `{path}:{start}-{end}` `{fn}` | `{sha(ROOT/path)}` |')
code+=['','CPU与query本轮同输入等价收据见runlogs。历史三项不重复相加，见LATENCY_METHOD_AUDIT。gpu effective_config同时绑定worker SHA。未改生产安全限幅。','输入/输出散列：CPU original request/result、query output_hash、RASC CAMERA/BODY散列均在各JSON；完整路径/敏感原日志只在本地私有运行目录。']
write(Path('reports/optimization_code_map.md'),'\n'.join(code))
write(Path('math/planner_problem_formula.tex'),r'''% Explanatory decomposition, not an implemented single ARES-R CUDA objective.
\[ \min_{q_{0:H}} E_{\mathrm{goal}}+E_{\mathrm{collision}}+E_{\mathrm{smooth}}+E_{\mathrm{task}} \]
\[q_{\min}\le q_k\le q_{\max},\quad |\dot q_k|\le v_{\max},\quad |\ddot q_k|\le a_{\max},\quad d(q_k,\mathcal W)\ge0.\]
% cuRobo owns GPU seed/optimization costs. ARES-R builds the request and checks
% task orientation, phase limits, dense world collision and native packaging.
% Independent world validation does not independently certify self-collision.
''')
with (o/'tables/task_parameterization_matrix.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['task','object_template','grasp_pose','station_camera','payload','skills_and_constraints','evidence_status']);w.writerows([['old tray','existing ID1','recorded TCP-local compensation','GRASP/PLACE existing profiles','Demo exposed160x100+rear20','existing roundtrip; unchanged safety','HISTORICAL full task WITH RECOVERY'],['new screen','new measured template required','new grasp anchor required','profile commissioning required','measured thickness+ownership required','same interfaces; fresh calibration/validation','NOT PHYSICALLY VERIFIED'],['new machine berth','ID/berth transform required','placement target bound to epoch','new station/camera profile','same confirmed attachment','parameter changes require collision/route validation','CONFIGURATION/INTERFACE ONLY']])
write(Path('STATUS.md'),'''# 工作包状态

| 工作包 | 状态 | 证据等级/边界 |
|---|---|---|
| 同源真实点云六阶段 | DONE | FROZEN_REPLAY，18独立视图；235基元全点保留消融 |
| 同源OLD/NEW几何 | DONE | 32→235；同7mm padding；sum体积/剖面/全点核验 |
| 同源真实GPU规划 | DONE | 两者SUCCESS+独立world PASS；没有OLD-fail/NEW-pass效应 |
| cuRobo/ARES-R约束图 | DONE | SCHEMATIC，有代码位置，归属明确 |
| 真实ServoJ波形 | PARTIAL | PHYSICAL_MEASURED旧微动作，两个都abort；完整正常任务trace缺失 |
| CPU/查询性能本轮等价实验 | DONE | FROZEN_REPLAY，保留首轮；不冒充10/21实验 |
| 历史三项/关键路径 | DONE | HISTORICAL_EXTRACT，不造全链内部时序 |
| 四类框架图/真实UI源码fixture | DONE | SCHEMATIC / OFFLINE_SYNTHETIC；无设备连接 |
| 持物模型与恢复 | PARTIAL | 历史尺寸示意+真实恢复事件；原PLACE空间资产缺失 |
| 拖拽/完整物理视频、新对象现场 | BLOCKED_MISSING_DATA | 未编造，不阻塞已完成素材 |
''')
print('REPORTS_WRITTEN',flush=True)
