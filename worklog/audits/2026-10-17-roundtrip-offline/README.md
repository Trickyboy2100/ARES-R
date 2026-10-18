# 完整抓放离线审计包

日期：2026-10-17。只读本地源码和已有证据，无机器人连接、无重新采集、无运动、无生产参数修改、无push。

## 建议阅读顺序

1. [故障和90项限制台账](../../../docs/reports/2026-10-17_ROUNDTRIP_DEMO_FAILURE_AND_GATE_AUDIT.md)
2. [19阶段执行与代码参考](../../../docs/audits/2026-10-17_ROUNDTRIP_EXECUTION_REFERENCE.md)
3. [返场1至2天冲刺计划](../../../docs/roadmaps/2026-10-17_ROUNDTRIP_1_2_DAY_DASH_PLAN.md)
4. [关键函数索引](FUNCTION_INDEX.md)
5. [完整静态索引](source_inventory.json)
6. [聊天工具证据账本](chat_evidence_ledger.json)
7. [FAST超时与版本分裂补充核查](../../../docs/audits/2026-10-17_FAST_TIMEOUT_VERSION_SKEW_ADDENDUM.md)：另一工作副本已有FAST实现，现场loaded版本尚待核实，不能将单副本静态发现直接当成现场已证实根因。

## 包含什么

- `source_inventory.json`：272份本地文件的SHA、1443个函数、2680处条件分支、1420处显式raise、149项等待/超时调用；静态候选不等于运行时全部经过的gate。
- `source_snapshot/`：66份关键源码冻结副本；不包含vendor SDK/URDF/STL/原始点云或完整现场配置明文。
- `SOURCE_SHA256SUMS`：本地源码与配置哈希。对只有哈希、没有副本的配置，应从同一版本原工作树获取，不把哈希误当数据已归档。
- `chat_evidence_ledger.json`：对话中曾读取的现场数值。**不是原始日志副本，不是10月17日实时机器人状态。**
- 生成器：`scripts/audit_roundtrip_offline_inventory.py`，仅AST/文件扫描和Git只读命令，不导入ARES设备服务或连接网络。

## 本轮检查

- 272份源文件与索引SHA一致。
- 66份冻结源码与原文件SHA一致；Python AST未发现parse_error。
- 三份主文档的本地Markdown链接全部可解析。
- 证据账本JSON可读，包含三次主任务及恢复/碰撞证据。
- golden first-pick脚本SHA仍为`e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0`。
- golden demo manifest SHA仍为`25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056`。
- 没有在缺少现场环境时运行全量实机adapter测试，也没有把静态扫描当commissioning。

## 关键审计决策

先修FAST真实调用、超时取消、显存预算、接触可行性前置、持物点云归属、终点SETTLING和正式恢复；再判断哪些限制应保留、参数化、改时机或移到异步诊断。人工确认应是有界、可追踪的状态迁移，不再靠现场临时恢复脚本。

压缩包若被转发，不代表现场原始日志/点云也随包交付；缺失清单见故障报告末尾。
