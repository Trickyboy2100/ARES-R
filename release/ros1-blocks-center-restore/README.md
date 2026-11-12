# utility.center_restore.right.v1

功能：ACTUAL_CURRENT → GLOBAL_CENTER → PINNED_SAVED_POSE。只支持空手右臂；不移动底盘。

本目录是独立扩展，依赖现场有效RC1（2026-11-12）的canonical后端、scene-aware cuRobo、native sender和arrival helpers，不是第二套机械臂控制器。旧`/ares_r/return_center` v0.2及其MD5保持不变。

## 已验收范围

2026-11-12一个ROS Goal完成两腿真实运动，最终`CENTER_RESTORE_COMPLETED`且`return_to_saved_pose_verified=true`。第一腿从人工恢复后约偏离center数毫米的姿态回center；第二腿从新鲜center状态重新扫描/规划到已保存的右前高位。不是倒放轨迹，不是直接MoveJ。

`SAVED_POSE_REF`对本次保存目标通过实机验证；`CAPTURE_START`实现并通过逻辑测试，尚未单独执行实机往返。不能把任意新姿态、持物或任意工位宣称为已commission。

## 运行结构

- `center_restore/core.py`：目标解析、源SHA检查、两腿状态机。
- `center_restore/runner.py`：复用RC1的plan/dispatch/arrival；每个实际运动腿强制新scene。
- `center_restore/console.py`：同一个canonical job持有两腿；持久request_id、防重复、资源互斥、部分完成状态。
- `run_backend_overlay.py`：仅在独立进程中扩展原DemoConsole；不替换原源码。
- `recover_no_dispatch.py`：人工确认后，限定零派发故障的应用恢复；不清除控制器故障。
- `ros/ares_r_center_restore/`：独立catkin包和CenterRestore.action。

## 现场目录与启动

源码：`/home/yikun/ARES-R-ROS-BLOCK01-20261112/ros1-blocks-center-restore`。
ROS工作空间：`/home/yikun/ARES-R-ROS-BLOCK01-20261112/catkin_ws`。
canonical扩展仍使用原8776，WebUI/HTTP仍为8775，所有运动共享原执行所有者。启动文件变更已保全，未修改生产源码、旧Golden或开机自启。不要在后端已有任务时切换/重启。

每个SSH终端：

```bash
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-ROS-BLOCK01-20261112/catkin_ws/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321
export ROS_IP=127.0.0.1
```

节点如未运行：

```bash
roslaunch ares_r_center_restore center_restore.launch base_url:=http://127.0.0.1:8775
```

必须显式绑定base_url，避免同名ROS私有参数残留。测试节点使用独立节点名；不在正式节点占用同一个Action时启动假后端测试。

## Goal与结果

见[API合同](../../docs/integration/2026-11-12_CENTER_RESTORE_API_CONTRACT.md)。实际运动须现场确认空手、净空、设备健康和急停；新目标先规划。

两种模式：CAPTURE_START在运动前冻结真实起点；SAVED_POSE_REF严格使用命名记录和预期源SHA，不等同于开始时姿态。保存记录的工具/标定历史不完整时，使用当前FK+工具验证，超过3mm/3°拒绝，不默默重新解释目标。工具/模型/标定、左臂和底盘运动标记变化会拒绝接续。

取消只停止同一job。STOP_REQUESTED不等于停止完成；未能确认静止或Servo退出保留RECOVERY_REQUIRED。保护停不清错、不自动接着走。旧请求重发不重跑；首发回执丢失应先查询原request_id，不另建请求赌是否执行。

## 非运动测试

在仓库根目录：

```bash
PYTHONPATH=release/ros1-blocks-center-restore:release/site-source-20261112/src \
  python3 -m unittest discover -s release/ros1-blocks-center-restore/tests -p 'test_*.py' -q
```

现场独立工作空间编译后：`python3 tests/ros_fake_transport.py`（从本扩展目录执行，先停同名新Action节点）。假后端只绑定127.0.0.1，不连接JAKA；旧ReturnCenter节点可继续运行。

`run_block.py --goal goal.json --output 新目录`只准备，不执行。它依赖`ARES_R_SITE_ROOT`、原RC1 PYTHONPATH和ARES_R_PLANNER_SOCKET。非center起点的第二腿准备是SIMULATED rehearsal，不生成可用执行许可；实际到center后必定fresh replan。准备成功不等于可以跨次复用trajectory。

## 已知工程边界

- 本轮不添加通用RunBlock或ScanPick/ScanPlace实机实现。
- ROS/HTTP端口为现场网络接口，身份及网络隔离沿用现场配置，不向公网开放ROS master。
- 当前底盘绑定依赖IDLE和稳定运动log/queue标记；SLAM会漂移，不能把它当毫米级定位依据。
- 原始文件、SDK/模型二进制和精确目标位姿在私有包，公开仓库只保存代码和脱敏索引。
- SIMD/GPU回放环境未在另一台机器重建；需匹配cuRobo/Torch/CUDA/Warp并重定位现场绝对路径。
