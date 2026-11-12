# 2026-11-12 功能块01双腿与离场保全报告

## 结论

CURRENT_SITE_RUNTIME_VERIFIED = YES

SAVED_TARGET_CAPTURED_AND_PINNED = YES；SAVED_POSE_REF；right/front_right_high_axes_aligned。

ROS_CENTER_RESTORE_OFFLINE = PASS；17项core/ownership测试、7类真实ROS+假HTTP后端测试。

ROS_CENTER_RESTORE_PHYSICAL = BOTH_LEGS_PASS。

PRIVATE_HANDOFF_ARCHIVE_VERIFIED = YES；六个增量包，共约232MB（含包间重复），逐文件SHA通过。

PUBLIC_CODE_PUSHED：以本分支GitHub实际提交为准；分支codex/ros1-center-restore-20261112。

## 有效实施基线与部署

任务书位于planning/20261112-ros1-manipulation-block-delivery；本轮不切换现场生产工作树。实施基于现场有效RC1源与此前97bb2d7交付记录。

新增目录：`/home/yikun/ARES-R-ROS-BLOCK01-20261112/`，其中独立catkin_ws与代码扩展。原canonical后端在空闲后用插件入口重启，保持原8776/8775；插件仅在当前Python进程扩展DemoConsole，不替换RC1原源码。旧启动manifest与PID已保全，未配置开机自启。

旧ReturnCenter.action v0.2 MD5：842cf52f466bc1a27e437671197f32b6；新CenterRestore.action MD5：604285c770a2394b3024a6fb532f8380。两者独立包、独立Action，旧Golden和原接口未改。

## 真实两腿结果

单个ROS Goal、同一个canonical job：`c7d9107f7bbc48ceace753eb8e202054`。

业务请求：`supervised-center-restore-high-20261112-03`。

| 腿 | 新plan ID | 到位位置误差 | 姿态误差 | native耗时 | 采样 |
|---|---|---:|---:|---:|---:|
| current→center | PLAN_6f63ee87bbe243fb942dcb62e03afc3a | 2.05297mm | 0.01923° | 2.577s | 15 |
| center→保存右前高位 | PLAN_07105fb01a1342e3ad2762db17c56d2f | 0.00614mm | 0.000968° | 13.287s | 149 |

两腿都实际运动。第一腿开始时TCP略偏离center，因此没有使用ALREADY_AT_CENTER分支。两腿使用不同的新鲜scene，均经现有scene-aware cuRobo和native打包/验证；没有使用MoveJ、倒放、历史scene或碰撞阈值放宽。

scene分别为SCENE_158fd4816c7e4550b3625ac27afe3f25、SCENE_a2f0b74f8201456283d3620950ea7aa8。精确trajectory SHA见公开MANIFEST，原始请求/轨迹/native文件在私有包。

保存姿态返程六关节最大误差约0.000020°。两腿native均target_reached、servo_disabled_confirmed；各有3次独立新鲜静止回读，到位确认耗时分别2.124s和2.162s。任务总耗时62.395s，最终ROS success=true、terminal_state=CENTER_RESTORE_COMPLETED、return_to_saved_pose_verified=true。

当前位置停在已保存右前高位，不再自动执行其他动作。底盘未移动、夹爪未动作。

## 保存目标与版本

此前真实记录在arm_pose_registry中确认后绑定。源文件SHA256：bbcd723fc83d1091b9065ed2636e6689e52987c9cfa8a8e3db5defac16a7499a；目标规范化内容revision：46adb9b0d941eba8c9fe16af756a68609aa545a850e01c503069274a86305982。

实际关节、BODY SE(3)、tool3、左臂/底盘、源文件、校准与模型绑定原文在本次私有goal_binding.json和saved_pose_record.json，未重新编造目标。CAPTURE_START是单独实现/逻辑测试模式，不冒称该模式已独立实机验收，也不隐式代替SAVED_POSE_REF。

## 失败、恢复与已知边界

第一次真实Goal在预检读取983092/保护停，未出现任何dispatched-once标记，未派发运动。现场人员随后确认物理干扰已移除并再次授权。对三次健康静止读数和零派发核实后，仅解除应用RECOVERY_REQUIRED占用，旧错误/记录保留；未发controller clear。后续使用新request_id完成上述两腿，不把故障请求重写为成功。

另有测试节点私有base_url残留导致Connection refused，确认请求未到canonical；通过正式launch显式绑定8775和假节点独立名称修复。HTTP占用409也已保留，没有盲目重放。

执行版本的真实代码/ROS生成产物已保存在601文件私有包；实机后又补充launch安装项、模拟rehearsal的显式provenance标记和更完整的标定文件绑定，未修改运动几何、速度或控制器保护。这些整理不冒称又做了一轮实机。

取消/故障一律不自动继续第二腿；不能确认静止/Servo退出时保持RECOVERY_REQUIRED。零派发应用恢复只允许显式人工确认及精确run_id，不能用于曾运动的故障。

## 离场后工作

[资产索引](../integration/2026-11-12_ROS1_DELIVERY_ASSET_INDEX.md)列明六包、依赖与剩余缺口。当前资料可支持离线开发ScanPick/ScanPlace接口与回放准备；新取放块仍为REACCEPT_REQUIRED/CANDIDATE，不在本轮执行。未在另一台Ubuntu新建GPU环境，后续安装匹配Torch/CUDA/Warp并重定位路径后再验证冻结数据回放。
