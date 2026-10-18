# 返场两天冲刺准备判定

日期：2026-10-18，Asia/Shanghai。

```text
READY_FOR_TWO_DAY_ONSITE=NO
DECISION=DEFER_PHYSICAL_DASH_UNTIL_OFFLINE_CLOSURE
```

## 1. 本轮已完成

- 读取两份最新planning工作单及10月17日故障/调用/FAST报告。
- 12个Mac ARES-R输入工作树逐文件盘点，23309项，包含dirty/untracked/ignored，保留source/data/dependencies归档及Git patch/history。
- 对GitHub integration与audit完整blob树计算字节SHA256并逐路径比较；确认最新WebUI/完整Demo不在正式integration，audit也不是完整可部署release。
- 找回完整19阶段代码、Demo参数、85cm路线、服务模板和测试；保留两份FAST实现并找到不能整文件覆盖的缓存修复差异。
- .32/GPU主机只读连接检查，记录真实阻塞；没有实机动作、没有修改现场/同事dirty/golden。
- 新建独立RC准备工作树/分支，仅保全报告与离线工具，尚未集成运行链路修复。

## 2. 未完成，不声称已修复

| 准入项 | 结果 | 缺什么 |
|---|---|---|
| ONE_CANONICAL_RUNNABLE_RELEASE | NO | 两份代码的选择/合并及真实依赖锁/原生二进制 |
| EFFECTIVE_WORKER_VERIFIED | NO | .32 loaded module和进程来源 |
| GOLDEN_FALLBACK_UNCHANGED | Mac字节核查；现场未核查 | .32对应文件hash |
| GPU_CUROBO_REAL_REPLAY | NOT_RUN | GPU登录、pinned模型/环境、原始输入 |
| EARLY_CONTACT_LIFT_PRECHECK | NOT_RUN | 旧fail/新pass完整输入 |
| FAST_CANCEL_NO_ORPHAN | NOT_RUN | 实际取消实现和GPU回放 |
| ATTACHED_WORLD_NO_DOUBLE_COUNT | NOT_RUN | 实际post-lift点云、target/attachment归属 |
| GRASP_VERIFY_HOLD_VS_CONFIRMED | NOT_RUN | 原始读回时刻、before/after点云 |
| NATIVE_RETIMER_VALIDATED | NOT_RUN | 实际source/native path与反馈 |
| ALL_19_STAGES_OFFLINE_E2E | NOT_RUN | 完整adapter闭环、10轮、故障/恢复 |
| WEBUI_ART_SAME_CANONICAL_JOB | NOT_RUN | 新release单owner/stop/resume测试 |
| .32显存与warm planner兼容 | UNVERIFIED | 无运动现场资源检查 |

## 3. 当前不能合理承诺“返场两天必交付”

两天计划可以暂留，但不应现在锁定为已经具备准入的实机dash。当前主要缺口是**实际GPU访问、真实失败原始数据、完整模型与现场依赖**，不是要再研究一个新架构。先把它们补齐，才能对修复工期作可信判断。

不把历史Mock19阶段 `RETURNED_GRASP`、10月12日preland规划或源码审计当作本次完整实机验收。

## 4. 离线准入后，现场只做这些物理验收

### 第一天

1. 核对部署源码/配置/SDK/sender哈希与release，检查真实站位/工具/当前载荷、base observer和GPU服务。
2. 当前现场fresh ID1→接触/初始lift预检；在监督下验收抓取→初始100mm→总230mm及水平约束、tracking和settling。
3. 监督验收持物GRASP→PLACE扫掠、fresh ID3+偏置/40mm直接释放、无收臂逆路线返回；正式runner自主推进，不现场写恢复脚本。
4. 保存一次完整真实timing waterfall与每阶段实际输出，必要时只针对具体实际fault修正。

### 第二天

1. 固定参数连续多轮全链，记录成功率与全部失败，不只挑成功一次。
2. 验证同事独立WebUI/ART一键启动、Stop、重启状态和从已验证checkpoint恢复，不重复不可逆命令。
3. 对离线已通过的retiming做实机tracking/到位/载荷验收；不静默提高控制器保护或其他motion mode速度。
4. 交付固定release、回退锚点、一页操作单和私有原始证据索引。

## 5. 下一步唯一需要补充的接入信息

提供一个可用且可信的Ubuntu GPU SSH入口（账号/现有密钥授权，以及190如需使用时的可信host-key fingerprint）；不要发送密码或私钥。本轮对216现有账号认证失败，对190未跳过未知主机密钥验证。

.32原始证据将在其网络恢复后只读收集；若只能先提供受控导出的完整10月16日数据包，同样可按manifest核验后继续。没有原始文件的case继续标INCOMPLETE，不用9月或10月12日场景替代。
