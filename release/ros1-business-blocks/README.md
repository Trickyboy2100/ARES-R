# ROS1 取放功能块：离线准备版

**本目录不是可运动的交付版本。** `/ares_r/run_block` 目前只提供 Action ABI 预览，所有物理 Goal 明确拒绝。已验收的 `/ares_r/center_restore` 保持独立，不迁移、不修改消息。

- `block_registry.json`：11项业务能力、5份有效参数文件及SHA、验收状态。与11月12日P0私有归档逐文件一致。
- `blocks/contracts.py`：离线准备及阶段回放。Pick停在持物确认；Place先释放确认、退出，再可选center。
- `blocks/replay_jobs.py`：离线幂等/取消合同测试，**不是第二个物理任务所有者**。
- `ros/ares_r_manipulation_blocks`：新的RunBlock Action及明确拒绝运动的节点。尚未catkin编译。
- `SOURCE_BINDINGS.json`：复用入口版本；`ARCHIVE_VERIFICATION.json`：私有包校验摘要，不包含原始数据。

在仓库根目录查询和测试：

```bash
python3 release/ros1-business-blocks/inspect_blocks.py
python3 -m unittest discover -s release/ros1-business-blocks/tests -q
```

新工位无偏置时显示 `PROFILE_NOT_BOUND`，不会借用其他工位的参数。归档核验覆盖整包字节SHA及tar可读性；第二份受控备份尚未核实。

下一项实施：在既有canonical执行器中增加受控的Pick-HOLD结束边界，随后接入新Action；不能直接调用现有完整pick-reset脚本，它会自动把物体放回。未实现真实执行适配器、payload session持久化和实机验收之前，不开放Start。

## 2026-11-13增量

`blocks/runner.py`提供注入式Pick/Place阶段编排及SQLite持物会话。它目前只接受明确的OFFLINE适配器，不包含物理SDK调用。不要将其状态机测试结果当成新工位验收。

本机Parallels Ubuntu22.04中三个ROS包catkin构建通过：新Action MD5 `7b4edfbf807f9526b57393193f680fd1`；两个旧ABI保持不变。新5项、原Demo01 7项真实ROS通信测试通过，均为合成后端。原始日志在`evidence/`。

默认节点继续拒绝物理Start。`~offline_replay=true`仅供测试，不是开启硬件执行的开关。测试用临时payload session不用于跨ROS任务生产交接；持久会话在Python runner层单独测试。ROS节点尚未对接canonical，也未具备生产级幂等/重启恢复，禁止作为客户运动交付包。

## canonical适配与持久ROS增量

`blocks/canonical.py`直接复用已存在的SIFT HOLD执行器和Place函数，原文件保持不变；提供工具ID缺参兼容及真实结果字段核验。`verify_canonical_imports.py`已在VM通过真实模块导入检查。源SHA在`CANONICAL_BINDINGS.json`。

OFFLINE ROS节点现已支持持久请求/终态缓存及跨Goal payload session；`ros_session_transport.py`实测4项通过（包括节点重启、重复请求不重复释放）。状态路径用`~offline_state_dir`指定。合成模式还需进程环境`ARES_R_OFFLINE_REPLAY=1`，仅ROS参数不能开启。此前关于“临时会话/ROS幂等尚未实现”的记录由此增量取代；**生产canonical适配和新鲜持物绑定仍未发布**。
