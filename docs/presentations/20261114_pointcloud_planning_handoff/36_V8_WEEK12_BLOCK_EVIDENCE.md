# V8 Week12事实台账｜现场适配、功能块定义和分级验收

**事实窗口：2026-11-16至2026-11-20**。输入：用户上传的\`week12-1.md\`、\`week12-2.md\`、\`week12-3.md\`，V7.1母件，以及ARES-R当前可读取远端分支。此文档不是“本周一切均成功”的宣传，而是Codex生成**可追溯的任务功能块证明**的依据。

## 1. 远端/本地新鲜度审计（非常重要）

已确认：
- \`main\`最新公开commit仍停留在2026-10-27，不能以main判断11月现场进展；
- GitHub可直接读到\`codex/ros1-business-blocks-offline-20261113\`，HEAD \`edba1bb13971e62dc11efc5c5ff819852552769f\`（2026-11-18），包含功能墙、手册、11/17 Demo02和11/18部署；
- \`codex/aa0f0-b-v15-performance-20261119\` HEAD \`f5fc8c15ba82fe74c9b119921d9da1157f9ba57a\`（2026-11-19），仅证实V1.5性能候选源码/测试提交；
- 用户上传的周记录对11/19晚、11/20取放/筛网/TCP3有更多结果，其中一些对应现场/本机未推送记录。**不得说GitHub远端已完整保存这些最新实机运行，需Codex在授权本地工作树验证。**

Codex查找顺序：
1. 现场工作树的只读本地副本\`ARES-R-ros1-return-center-20261112\`（位置由现场负责人指定，不自动SSH）；
2. 该目录\`docs/function-validation/records/\`的具体block结果；
3. \`docs/reports/2026-11-18_AA0F0_B_VERSIONING_AND_FROZEN_PERFORMANCE.md\`、\`2026-11-19_AA0P0_V12_TCP3_PLACE_RECOVERY.md\`、\`2026-11-17_DEMO02_PARALLEL_ACCELERATION.md\`等真实本机文档；
4. \`worklog/evidence/demo-console/\`、\`worklog/evidence/demo-runs/\`的\`result.json/events.json/native_package*.json\`，核准run ID/版本/终态/时间；
5. \`docs/demo-handbook/catalog.json\`、\`docs/demo-handbook/08-evidence.md\`等功能目录；
6. ROS源码交付归档\`ARES-R-ROS-RA0F0-V2.0-20261119.zip\`、\`ARES-R-ROS-RC0F0-V2.0-20261120.zip\`，存在且用户授权时核manifest与Action定义；
7. 若周总结与原始run不符，按真实run原始字段优先，并在\`evidence_conflicts.md\`注明。

> 原2026-11-17功能手册中AA0P0还是“近期仅规划”，不应覆盖11/18–19较新的V1.2三次原生成功；同样11/17功能墙里独立AA0F0/AC0F0未注册，不能据此否认11/19–20新正式源码和候选入口，但也不能自动提升为独立实机已验收。

## 2. “功能块”的专业定义与本周工作量

**业务级任务功能块（Task-level Operation Block）**：
\`Block = (站点,对象,动作类型,机械臂,检测配置,工具版本,执行参数,输入条件,阶段流程,末状态,异常结果,证据/版本)\`。

区分：
- 原子技能：Detect、Plan、Approach、Grip、Lift、Release、Retreat等，可跨任务复用；
- 业务功能块：\`AA0F0\`“天平料盘取料并持稳”，\`AA0P0\`“天平料盘放置退出center”，有完整任务边界；
- 功能目录：登记许多业务功能，但未必已经完成全部实机调试；
- ROS适配层：Action薄封装调用现有canonical执行器，**不是又训练了一套控制模型**。

### 状态设计为独立维度，不使用一个单一“已完成”
列：
\`CATALOG_REGISTERED\`、\`NATIVE_PHYSICAL_VERIFIED\`、\`NEW_ALIAS_INDEPENDENT_VERIFIED\`、\`ROS_PACKAGE_BUILT/DEPLOYED\`、\`ROS_PHYSICAL_VERIFIED\`、\`DELIVERED\`。
每个状态绑定版本、run_id与原始终态；可存在“源运行原生成功、正式别名尚未单独复测、ROS源码已部署”的组合。

## 3. 本周真实业务表（必须用原始记录再核）

| 编号/任务 | 本周证据 | 已验证边界 | 不得扩大 |
|---|---|---|---|
| RAWU0-02 / ROS Demo01 | 11/16 run\`81a9ce0bb0594a87a9fb55d74163a84b\`，77.86s、\`CENTER_RESTORE_COMPLETED\`；Native两段16.115/14.655s | 完整ROS实机两段到位；当前位→center→保存右前高位 | 不把两段运动时长相加当77.86s的全部构成；不能跨其他录制的62.4s算优化 |
| RAWU0-04 / ROS Demo02 | 11/17 run\`a5a99dd2287341588ff2f24f1366898e\`，约122.6s，\`DUAL_CENTER_RESTORE_COMPLETED\` | 两臂ROS实机完成、到位读回，GPU依旧互斥、部分CPU/GPU交叠 | \`Delivered=false\`；45.56 vs63.02前半不同起点不可算固定增益 |
| AA0F0-B V1.4 → AA0F0 V2.0 | 来源run\`e2ede7bef25a42faa2a24c81abb50cd6\`，TCP3/零偏置、ID1，约230.06mm抬升、\`HELD_CONFIRMED\` | 来源V1.4原生完整取料持稳；新正式别名与ROS源码包已经整理 | AA0F0 V2.0**正式别名独立实机未单独证实**；RA0F0 ROS完整/跨机实机待验收 |
| AA0P0 V1.2 | 11/18–19现场V1.2三次\`RELEASED_RETREATED_CENTER\`，run缩写\`dd5c55e/f891e66/5de2c83\`，其中一次168.10s | 原生料盘从持物状态放回天平，包含检测ID9、下降/释放、退出和center | V1.3“约省10s”为估算、无现场新速度实测；RA0P0 ROS未成功全链 |
| AC0F0-02 筛网原位抓放 | 11/20 run\`2c42d1fc7a09422ab0dc656d77d359f4\`，ID10（取代原ID6），156.63s、实际抬升230.34mm、六段Native到位 | 新TCP3与ID10配置下原位抓→抬→放→center现场实机完成 | 释放现场确认但机器字段未确认，不声称所有释放传感器验证均通过 |
| AC0F0 V2.0 / RC0F0 V2.0 | 从上条实机**已证明的取料前半程**形成独立HOLD出口；ROS1 Action\`/ares_r/ac0f0/fetch_hold\`构建部署、未授权请求拒绝测试 | 软件拆分与部署、上游步骤原生实机证据来源清楚 | 新独立入口自己的一次完整原生/ROS实机尚未登记 |
| AC0P0筛网天平放置 | 11/13旧版本完整原生成功；11/20新持物姿态ID8两次检测；一次后台规划3.29s、请求内部10.51s，客户端\`BrokenPipeError\`；另一轮QUALITY中断 | 本周**新的现场配置仅完成无运动预检部分**，未派发运动 | 不将11/13历史成功包装成11/20新配置已验收 |
| 烘干箱六泊位 | 功能目录六取六放，已有下中等历史具体成功 | 本周完成分类、站位命名与目录、参数/版本映射 | 12个条目不等于12个泊位实机通过 |
| A/R功能墙 | 11/18现场30项目录、交付/开发、Native/ROS切换、10章节手册 | 功能墙/交付清单上线，部分原生入口可读可启动 | ROS网页启动桥接待接；前端Development不等于获得硬件执行授权 |

## 4. 现场适配“问题→研发动作→回归状态”具体清单

| 现场新问题 | 定位证据 | 修改动作 | 当前能公开表述的结果 |
|---|---|---|---|
| 新环境右臂工具坐标变化 | 手眼重标、TCP3配置、工具签名不一致 | 重新绑定TCP3、任务偏置归零、统一任务工具版本 | AA0F0-B V1.4新工具源运行原生成功 |
| AA0F0接触阶段水平校验 | 3.0038°触及原3°门槛 | 核对姿态定义、候选/容差适配（具体部署6°作用范围看现场source） | 后续特定V1.4原生成功；不能说所有3°姿态误差已消失 |
| Native关节跨圈与软限位 | controller vs planner关节绕转差 | 关节命名、解圈和执行打包校验定位修订 | 版本V1.4具备真实到位记录，仍需按source确定哪个改动生效 |
| 读回到位门限 | 0.02798°超过原0.02° | 完善到位采样/settle与消息返回时序 | 正常V1.4源run成功；不能凭一次成功证明全局阈值最优 |
| 筛网旧检测ID不兼容 | Epic ID6报3017 \`ATOM set parameter failed\` | 新建ID10检测与现场工具参数绑定 | AC0F0-02 ID10完整原生实机通过 |
| 料盘持物对象与环境簇ID碰撞 | AA0P0冻结回放显示同名临时ID可排除真实障碍 | 修复点归属和碰撞绑定，拆分放置阶段故障码 | AA0P0 V1.2有原生成功；源码级差异另核 |
| 规划成功但客户端丢包 | AC0P0新ID8预检\`BrokenPipeError\` | 诊断网络传输/回包与请求结果状态 | 截至周末无新实机放置，不允许标“已修复” |
| 主站访问慢 | 本机约0.8ms，WiFi网页5.15→1.35s当时观测 | 排查WiFi自动切网、省电、路由和直连路径 | 网络可用性诊断；不是机械臂规划器性能 |
| ROS Demo02准备时序 | 原共享GPU工作区混入CPU验证与Native打包 | ThreadPoolExecutor并行readback、GPU互斥、CPU核验/打包出锁 | 实机Demo02完成；线程交叠有日志，端到端净增益尚需同起点实验 |

## 5. 可做直观图的本周数字（注明“用途”，不能乱算）

| 原始数据 | 正确图 | 错误用法 |
|---|---|---|
| 30目录项：20业务、5 Utility、3测试、2组合 | 分类面积比例图 | “30项机器人功能全部完成” |
| Demo01 77.86s，Native两段16.115/14.655s | 阶段事实卡＋两段实体运动位置 | 认为两段相加就是完整任务 |
| Demo02 122.6s | 同其自身五环节进度/到位图 | 和Demo01比谁更快 |
| 天平取料230.06mm抬升 | 视频关键帧+实际位移标尺 | 与筛网230.34mm算精度提升 |
| AA0P0 V1.2三次成功，其中168.10s | 三条独立run状态和一个完整流程时间 | 与不同对象156.63s比较“提速” |
| 筛网完整循环156.63s，准备52.48s，solve20.95s | 按真实事件的阶段时序；solve若在准备内需嵌套 | 将准备+solve重复相加 |
| 冻结同场景cold/first 10.302s与warm 3.805–3.901s，solve约1.55s | 同场景请求状态对照，分开外部观测 | 宣称现场全链从10s变3.8s |
| 旧TCP预热失配22.986s | 旁注异常历史卡 | 当成严格同条件old baseline |
| V1.3平移预计省约10s | “预计/待现场测量” | 画成实测时间下降 |
| 11/20 AC0P0 3.29s求解、10.51s请求但BrokenPipe | 失败阶段分解、无运动门禁 | 宣称完整放置成功 |

## 6. 本周图片及视频应突出什么

**需要优先用本地证据自动生成：**
- 真正的WebUI“功能墙”截图、对象/工位过滤、A/R编号与状态；
- AA0F0/AA0P0/AC0F0-02各自的阶段事件/源参数和运行回执；
- ROS Demo01/02事件图、GpuLock与CPU打包重叠区段；
- ID6 3017报错与ID10成功检测的真实界面局部；
- TCP3变更及旧工具签名错误；
- 本周\`RUN_ID → block version → native/ROS结果\`逐项状态矩阵；
- planner冻结同源首/热请求实测条形图；
- 网页访问延迟若展示，单独“网络通信”层面，不跟cuRobo合并。

**需要用户少量提供：** 新工位全景、料盘取料完整、料盘放置完整、筛网原位抓放完整视频。详见38号文件精确文件名与目录。

## 7. 源代码/报告索引

**已远端可读（11/18或更早）：**
- \`docs/integration/DEMO_CONSOLE_CAPABILITY_WALL.md\`；
- \`docs/reports/2026-11-18_CAPABILITY_CONSOLE_DEPLOYMENT.md\`；
- \`docs/demo-handbook/02-catalog.md\`、\`03-fetch.md\`、\`04-place.md\`、\`07-delivery.md\`、\`08-evidence.md\`；
- \`docs/reports/2026-11-17_DEMO02_PARALLEL_ACCELERATION.md\`；
- \`src/ares_r/webui/demo_console.html\`、\`demo_wall.js\`和\`scripts/build_demo_wall.py\`；
- \`release/ros1-business-blocks/ros/ares_r_manipulation_blocks/\`。

**以本地最新run为准：**
- \`docs/function-validation/records/AA0F0.md\`、\`AA0P0.md\`、\`AC0F0.md\`等；
- \`docs/reports/2026-11-19_AA0P0_V12_TCP3_PLACE_RECOVERY.md\`；
- \`worklog/evidence/demo-console/<run_id>/\`；
- \`release/ros1-ac0f0/\`和\`release/ros1-aa0f0/\`；
- 新功能版本的\`parameters.json\`、\`source_parameters.json\`及readback。

**验证阶梯**：
\`1 目录登记\` → \`2 本地源码/回放\` → \`3 原生实机\` → \`4 ROS实机\` → \`5 Delivered\`。
但是正式别名/新TCP/新ID引入新版本时，不能直接沿梯子自动继承其他版本状态。建议每个维度独立列而不是仅一个综合“完成”。
