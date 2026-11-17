# ROS Demo / 功能块与 Demo Console 只读盘点

日期：2026-11-17。范围：Mac当前工作树、现场RC1、ROS-BLOCK01、ROS-BUSINESS、Turbo独立目录及原jinyu_ws；跳过构建、venv、SDK和冻结重复源码。未启动ROS节点、相机或运动，未修改部署配置。

## 结论

现场Console共12项，其中ROS Demo01已有独立入口。当前11321 ROS Master只注册`/ares_r/center_restore`这一项ARES-R Action；11311本机地址连接拒绝。存在原jinyu工程roslaunch进程，但未据此推断其远端Master或可用性。

查到4条ROS Action实现：

| Action | 实现 | Console / 运行状态 |
|---|---|---|
| `/ares_r/return_center` | `ros1/ares_r_demo_bridge`；旧v0.2，仅回center | 对应`demo-0-return-center`已在Console，但没有ROS标签；当前Action不在线 |
| `/ares_r/center_restore` | `release/ros1-blocks-center-restore/ros/ares_r_center_restore` | 已交付，当前在线；Console alias=`block-01-center-restore-right` |
| `/ares_r/center_restore_turbo` | `release/demo01-turbo-physical-20261113/turbo_node.py` | 有独立实机成功记录，未加入Console，当前Action不在线；48.359秒记录只有一段实际运动，不能算完整往返或并行流水线验收 |
| `/ares_r/run_block` | `release/ros1-business-blocks/ros/ares_r_manipulation_blocks` | 已有通用Action和注册表；当前节点不在线，当前canonical也未加载BusinessConsole |

源码拷贝、旧版、加速补丁、离线预览不能重复计算为已交付独立ROS Demo。`ros1-speed-20261113`是原Action复用的提速补丁；`demo01-turbo-preview`是冻结数据预览，不是另一个可执行Action。

## 23项通用业务注册定义

现场与Mac注册表均有23项：U01辅助功能＋P01–P05抓取＋L01–L05放置＋烘干箱六泊位抓取6项＋放置6项。README仍写11项，文档落后。

U01已由原ROS Demo01覆盖；其余22项都没有作为ROS业务功能块加入当前Console。部分已有相似legacy Demo卡片，但原位抓放reset与ScanPick持物结束并不等价，也不等于ROS RunBlock验收通过。

| ID | 能力 | 现场注册状态 | 参数绑定 | Console中的ROS功能块入口 |
|---|---|---|---|---|
| U01 | 姿态往返 | ACCEPTED_SCOPE_LIMITED | 沿用既有Action | 已有ROS Demo01 |
| P01 | 称上筛网抓取并保持 | REACCEPT_REQUIRED | 已绑定 | 无 |
| P02 | 称上料盘抓取并保持 | REACCEPT_REQUIRED | 已绑定 | 无 |
| P03 | 除尘收料机筛网抓取并保持 | PLAN_ONLY | 未绑定独立执行参数 | 无 |
| P04 | 除尘收料机料盘抓取并保持 | PLAN_ONLY | 未绑定独立执行参数 | 无 |
| P05 | 烘干箱料盘抓取并保持 | PLAN_ONLY | 未绑定独立执行参数 | 无 |
| L01 | 除尘收料机筛网放置 | CANDIDATE | 已绑定 | 无 |
| L02 | 除尘收料机料盘放置 | CANDIDATE | 已绑定 | 无 |
| L03 | 烘干箱料盘放置 | CANDIDATE | 已绑定 | 无 |
| L04 | 称上筛网放置 | DISABLED_REQUIREMENT_PENDING | 未绑定独立执行参数 | 无 |
| L05 | 称上料盘放置 | DISABLED_REQUIREMENT_PENDING | 未绑定独立执行参数 | 无 |
| DRYER_PICK_UPPER_LEFT | 烘干箱上层左料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PICK_UPPER_MIDDLE | 烘干箱上层中料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PICK_UPPER_RIGHT | 烘干箱上层右料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PICK_LOWER_LEFT | 烘干箱下层左料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PICK_LOWER_MIDDLE | 烘干箱下层中料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PICK_LOWER_RIGHT | 烘干箱下层右料盘抓取 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_UPPER_LEFT | 烘干箱上层左料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_UPPER_MIDDLE | 烘干箱上层中料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_UPPER_RIGHT | 烘干箱上层右料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_LOWER_LEFT | 烘干箱下层左料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_LOWER_MIDDLE | 烘干箱下层中料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |
| DRYER_PLACE_LOWER_RIGHT | 烘干箱下层右料盘放置 | PENDING_SLOT_ACCEPTANCE | 未绑定独立执行参数 | 无 |

所有现场注册项`physical_start_enabled=false`，RC1未发现`config/ros_business_release.json`。这意味着不能把它们全部标为Delivered或直接开放实机启动。U01这个false表示不通过新RunBlock重复委派，原CenterRestore Action仍独立可用。

P01/P02/L01/L02/L03这5项已绑定参数，现场文件存在且SHA256与现场注册表全部一致。其余17项没有独立profile_source，其中12项烘干箱泊位具备target resolver合同，执行适配与逐泊位验收仍待补齐。

## 最重要的Mac / 现场差异：L04

Mac的L04（秤上筛网放置）已推进为`DEMO_PHYSICAL_PASS_ADAPTER_REPLAY_PASS`，有参数绑定及canonical adapter replay；run_id=`049b636585df431ea42f83975dbabfc6`。现场Business注册表仍是`DISABLED_REQUIREMENT_PENDING`、`PROFILE_INPUT_REQUIRED`，无profile_source。

Mac成果位于`release/ros1-business-blocks/site-20261113-L04/`。其MANIFEST说明：成功运行记录没有冻结当时参数SHA，而依据文件mtime早于运行进行回溯绑定；不能把它当成完整的运行时哈希证据。Mac注册表仍`physical_start_enabled=false`，reason明确ROS dispatch仍待集成。因此是“legacy实机证据＋ROS适配离线回放已做”，不是“新ROS调用已经实机交付”。

当前Console的`demo-7-shaiwang-placeto-cheng`仍是legacy卡片，不能消除上述业务ROS封装差异。

## 为什么Console看不到

现场canonical实际进程从`/home/yikun/ARES-R-ROS-BLOCK01-20261112/ros1-blocks-center-restore/run_backend_overlay.py`启动，仅安装CenterRestoreConsole。

取放功能在另一目录：`/home/yikun/ARES-R-ROS-BUSINESS-20261113/release/ros1-business-blocks/`。其BusinessConsole才会生成`ros-prepare-P01` / `ros-run-P01`等入口，并且只生成已绑定profile的项；未绑定模板本来就不会出现在这个catalog实现中。不是简单漏加网页按钮：运行后端、Action节点、发布记录和展示metadata还未统一。

已有4个辅助ROS Service定义：`/ares_r/blocks/list`、`/ares_r/blocks/prepare`、`/ares_r/blocks/preparation_status`、`/ares_r/blocks/resolve_dryer_target`。当前11321没有注册这些服务。

## 原工程中额外找到的内容

`/home/yikun/yikun/jinyu_ws/src/jinyu_ros_pkg`还保存`GraspCmd.srv`、`GripperCmd.srv`、`StateCmd.srv`、`FloatData.srv`，以及底盘、语音、DOPE等包。这些属于先前设备/业务工程，不能直接计入ARES-R已交付Demo。本次RC1/tmp未找到额外ROS package/action/service/launch定义。

## 建议接入顺序（本轮未实施）

1. 给已有`demo-0-return-center`补ROS属性，并明确旧Action当前是否在线；保留已交付Demo01 ABI。
2. Turbo作为独立候选卡片展示，说明真实验证范围、非双线程完整流水线；不冒充Golden/Delivered。
3. 业务23项统一做目录查询，分别显示配置绑定、ROS在线、legacy实机、ROS实机、交付状态；未验收项先查询/准备，不统一开放启动。
4. 优先处理L04的Mac/现场版本差异，以及P01/P02、L01–L03这5项绑定参数的能力；不要另复制一套控制算法。
5. P03/P04/P05/L05和12泊位项作为待绑定/待验收能力列出，与可执行Demo分区。

## 证据

Git内只读摘要：`worklog/evidence/2026-11-17-ros-console-inventory/inventory-summary.json`。
现场原始接口/进程/注册表盘点的Mac私有副本：`/Users/andyee/Documents/ChatGPT/local/site-private-ros-inventory-20261117`。原始文件只读收集，本轮未push、未重启服务、未进行运动测试。
