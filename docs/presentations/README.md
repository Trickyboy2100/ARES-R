# ARES-R 汇报素材任务入口（2026-10-28）

当前要执行的是**真实数据驱动的图像/曲线/架构图素材生产**，**不是**新PPT，也不是重写上一次汇报母稿。

**唯一核心方法命名**：RASC — Reachability-Aware Scene Compilation（机械臂可达空间约束下的自适应场景几何编译）。

为避免影响现场生产与旧Golden结果，完整任务书和后续成果放在独立分支：

- **任务书**：https://github.com/Trickyboy2100/ARES-R/blob/codex/rasc-presentation-evidence-20261028/docs/presentations/2026-10-28_CODEX_RASC_VISUAL_EVIDENCE_WORK_ORDER.md
- **工作分支**：`codex/rasc-presentation-evidence-20261028`
- **来源基座**：`codex/golden-offline-workbench-20261020`，`6866106cee971b08d8abb92523d2cc2dc0e204ca`。

离线Ubuntu Codex可先运行只读检查，确认本地工作树后，再切入新分支或使用独立worktree：

```bash
cd /path/to/ARES-R
git status --short
git fetch origin codex/rasc-presentation-evidence-20261028
# 建议在独立工作树开始，不覆盖正在进行的代码：
git worktree add /path/to/ARES-R-RASC-EVIDENCE -b local/rasc-evidence origin/codex/rasc-presentation-evidence-20261028
```

请Codex首先阅读任务书，再自行检查真实点云/日志输入，按P0/P1优先级产出**独立可插入PPT的子图、可选合集、源数据与脚本、审计报告、素材索引**。仅能在离线环境开展工作，**禁止硬件控制及连接现场IP**，原始现场点云或内部录像未经授权不提交到公开Git。

这份入口也说明用户对旧两份母稿的最新调整：**不采用大量英文缩写；无需专业答辩问答清单；离线Codex自己做素材而非把可离线完成的工作布置给用户。** 旧稿保留作研究背景，但与此任务书冲突时，以本任务书为准。
