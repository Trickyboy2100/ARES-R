# 现场准备与三项验收

当前新取放版本处于离线候选阶段。当前版本已接入物理委派和实时持物核验，运动发布前需完成现场功能块验收。生产主机使用独立候选目录，保存当前服务、参数和代码版本。

## 1. 查询与兼容性

在候选工作空间编译 `ares_r_manipulation_blocks`，核对原 ReturnCenter 与 CenterRestore 的 Action MD5。启动查询节点时只填写候选代码的绝对路径。

```bash
roslaunch ares_r_manipulation_blocks catalog.launch contract_root:=/绝对路径/release/ros1-business-blocks
rosservice call /ares_r/blocks/list '{}'
```

应返回 11 项能力及版本。当前所有新物理 Start 为 false。业务计算机用同一 ROS master 验证查询和 Action 反馈，记录双向地址解析、服务端版本与结果。

## 2. 静止扫描与规划准备

canonical 候选后端需加载 `run_backend_overlay.py`，通过 `ARES_R_SITE_ROOT` 指向有效现场根目录。沿用原后端启动参数和端口，在空闲维护窗口完成切换。

查询节点通过 `canonical_base_url` 指向该后端。准备服务接收以下字段。

```yaml
request_id: prepare-p01-unique-request
block_id: pick.scale.sieve.v1
expected_profile_revision: 从list结果复制当前值
stationary_environment_confirmed: true
```

```bash
rosservice call /ares_r/blocks/prepare '上面的字段'
rosservice call /ares_r/blocks/preparation_status "run_id: 返回的run_id"
```

准备过程复用已有扫描、规划和打包程序。PREPARING/RUNNING 是过程状态，SUCCEEDED 需同时查看 evidence_uri 与 preparation 日志。当前插件仅确认准备命令完成，尚未发布完整执行包认证。

同一个 request_id 重发应返回同一个 run_id。超时后保留原 request_id，先查后台状态。另一任务应返回 BUSY；后台重启后应进入恢复检查。

## 3. 独立取放验收

选择一个已准备工位进行有监督 ScanPick，验收扫描、抓取、230mm 抬升、原生 Servo 退出、实际到位和持物证据，最终应为 HELD_CONFIRMED。随后由新鲜持物 session 启动 ScanPlace，验证释放、退出接触区与配置要求的回 center。

每次保存 ROS Result、实际 joints/TCP、夹爪反馈、scene/轨迹/native SHA 和生效参数。新工位的偏置与接触配置需单独验收。transport_handoff_ready 在载物转场验收完成前保持 false。
