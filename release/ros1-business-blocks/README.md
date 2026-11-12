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
