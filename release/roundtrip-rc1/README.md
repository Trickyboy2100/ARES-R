# ARES-R Roundtrip RC1

RC分支：`codex/roundtrip-demo-rc1-20261018`；开发分支：`codex/ubuntu3080-roundtrip-replay-20261018`。

交付：正式 CycleRunner 单次入口连续执行19阶段，真实 RTX3080/cuRobo 参与 current→pregrasp、持物追加130mm及持物PLACE；contact/100mm lift经正式 native 打包及密集验证。设备、视觉和安装变换均明确标为 **SYNTHETIC**。部署包为 **CONDITIONAL**，不是实机已验收。

- [一键启动、Stop、checkpoint/resume及现场两天手册](OPERATIONS.md)
- [逐阶段输入输出、provider、时间、恢复与故障证据](RESULTS.json)
- [逐阶段耗时瀑布](stage_waterfall.svg)、[CSV](stage_timings.csv)
- [代码/配置/资产版本清单](manifest.json)
- [原始回放请求、GPU结果、SceneSnapshot、native轨迹与验证凭据](replay_evidence.tar.gz)

680项软件回归通过。10次完整GPU闭环全部19阶段完成；同时分别验证 LIFT100_ARRIVED、GRASP_CONFIRMED、HOLD230、BASE_AT_PLACE 的跨进程恢复。最终代码另做标准/640障碍整链复核。初始十次中的前三次在最终短动作插值优化前执行；新增Warp索引预分配保护后，正常小场景实际buffer仍为5000，最终版本GPU证据单独保存，不能混称所有日志同一源码哈希。

故障覆盖：实际超时及GPU求解中Stop后的子进程回收、实际CUDA allocator小预算OOM、注入OOD/IK失败/重复持物世界对象/抓取不确定/左臂暂不可用/末拍迟到/底盘完成后响应丢失/释放不确定。释放不确定时拒绝恢复、detach及返程；网络响应丢失有完成凭据才跳过，不重发。OOM实际测试用1% allocator上限触发198MiB分配失败，没有填满显卡。

同一合成原始路径、相同安全限制：contact 31.44→7.36秒，100mm lift 98.96→30.8秒。几何变化重新通过密集碰撞/水平姿态/单调方向/关节动态/跟踪门限验证。原10月16日115秒/72秒路径缺失，仍未复现。目标周期150秒仅为工程目标；实测软件墙钟、native时长及底盘名义29秒分开呈现，真实观测与设备延迟待现场测量。

P2正式路径贯通 source-observed ownership → LocalScene → 自体过滤 → SceneSnapshot → cuRobo/独立验证。代表场景每次移除343个被归属的持物点，保留1372个受保护结构点；精确对象ID不能同时进入attached和world。P3闭爪只成为HOLD_CANDIDATE，100mm受控抬升和证据合格后才GRASP_CONFIRMED。P5的统一job owner、command_id、防重发凭据、SETTLING→ARRIVED与WebUI/ART同一run_id均已接入正式入口。

现场专属待办：10月16日原始数据、commissioned模型/TCP/碰撞球、现场SDK/native新二进制、85cm载物扫掠、ID3 lower_middle偏置/+40mm释放、不收臂逆返回包络、实际视觉/服务并发10GB显存及真实Stop/恢复验收。离线小场景及640障碍通过不等于这些项目通过。NVML库/内核版本不匹配仅保留维护建议，CUDA正常期间未重装驱动或重启。

原golden first-pick两个文件保持基线哈希；每项修复小提交，原integration/source-delivery分支未改动。
