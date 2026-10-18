# Ubuntu GPU frozen replay — 首轮入口与证据状态

日期：2026-10-18，Asia/Shanghai。**GPU_CUROBO_REAL_REPLAY=NOT_RUN**。

## 1. 本轮边界

依据PRESITE工作单，首轮只做source custody和缺口盘点。没有远程安装依赖、启动GPU job、连接机器人端口或运行训练；没有用Mock替代真实cuRobo验收。

## 2. 连接实测

| 主机 | 实际检查 | 结果 | 尚不能知道 |
|---|---|---|---|
| .32 `172.28.172.210` | 只读SSH，8秒connect timeout，已通过本机网络权限检查 | timeout | 现场源码/原始数据/当前显存/loaded module |
| 首选 `172.25.24.190` | 本机alias错误指向175.25.24.190，命令显式指定正确172地址；保留StrictHostKeyChecking=yes | 未知ED25519 host key，停止于身份验证前 | GPU型号/占用/账号登录/环境 |
| 备用 `172.25.24.216` | 当前已配置andyee账号，只读SSH | 服务响应但认证失败 | GPU型号/占用/环境 |

未关闭主机密钥验证，未修改用户SSH配置，未自动写入未知host key，未尝试用户密码，未终止任何其他任务。历史“4x4090/3090”仅为待核实信息，不是本轮实测。

## 3. 环境pinned合同的当前缺口

- 机器人配置指向 pinned ARES `b978cbd669b5a3f6bc0bd19defcbe5256692f145`；本次Mac盘点没有实际URDF/STL本体，只有引用路径/配置及hash。
- 没有取回现场 cuRobo commit/patch、Torch/CUDA/Warp实际版本和Python依赖锁，不能用最新pip包代替。
- Mac有EpicEye/ATOM厂商SDK归档和一个历史CPU distance构建产物，**不等于**拿到了JAKA sender v5/v6_pick和它们的依赖动态库。
- 本地worker来源已保全但未集成；不能部署audit source_snapshot作为运行包。
- 必须先建立拒绝访问JAKA/AMR/夹爪/Epic真实端点的隔离策略，再启动任何离线adapter链。当前没有配置远程环境，因此不声称硬件隔离验收通过。

## 4. 真实失败fixtures需求与状态

| fixture | 目标 | 当前原始证据 | 本轮replay |
|---|---|---|---|
| P0A | 旧站位55mm接触IK失败曲线 | 缺失；只有聊天数值和源代码 | NOT_RUN |
| P0B | 新站位接触/100mm lift成功输入 | 缺失原始包/关节序列 | NOT_RUN |
| P0C | 37/37/37与added=.5204、removed=.6667 | 缺原始点云和采样时刻 | NOT_RUN |
| P0D | 持物后−62.26mm起点重叠 | 缺post-lift点云/scene/attachment绑定 | NOT_RUN |
| P0E | ID3+lower_middle+40mm preland | 任务参数在Mac；缺该次完整epoch | NOT_RUN |
| P0F | contact1439×80ms、lift约72s | 缺实际source/native path及反馈 | NOT_RUN |
| P0G | timeout迟到结果/OOM/恢复fault | 缺原始run/进程和显存轨迹 | NOT_RUN |
| P0H | 85cm route/真实AMR完成 | 定义完整；持物全链完成证据缺失 | NOT_RUN |

10月12日preland数据可以单独验证模型/scene兼容性，但不作为10月16日问题已复现或已修复的依据。

## 5. 下一轮真实回放顺序，非本轮执行结果

1. 登录一个空闲GPU可用的Ubuntu账号，记录driver/GPU/占用；只选一张经确认空闲GPU，不抢占研究任务。
2. 取回完整数据Bundle B和资产；按SHA核对，安装相容pinned环境并禁用真实硬件网络。
3. 先用原始失败版本重现P0A/C/D/F/G，记录queue/init/solve/validation/package/VRAM，不能只展示修复后的成功。
4. 在独立RC中逐项修复版本/FAST、deadline取消和cache、提前IK、attachment归属、验证时序、retimer、settle/resume。
5. 真实GPU跑FAST/FALLBACK、CLEAR/AVOID/BLOCK、10次warm请求、timeout无孤儿和OOM回收；19阶段10次离线adapter循环并故障恢复。
6. Ubuntu 24GB结果单独报告；.32约11.66GiB兼容性仍需无运动warm probe或受限显存测试，不能直接继承延迟/内存结论。

## 6. 当前验收旗标

```text
UBUNTU_GPU_ACCESS_READY=NO
PINNED_SITE_ENVIRONMENT_RETRIEVED=NO
OCT16_FROZEN_FIXTURES_COMPLETE=NO
GPU_CUROBO_REAL_REPLAY=NOT_RUN
EARLY_CONTACT_LIFT_PRECHECK=NOT_RUN
FAST_CANCEL_NO_ORPHAN=NOT_RUN
ATTACHED_WORLD_NO_DOUBLE_COUNT=NOT_RUN
GRASP_VERIFY_HOLD_VS_CONFIRMED=NOT_RUN
NATIVE_RETIMER_VALIDATED=NOT_RUN
ALL_19_STAGES_OFFLINE_E2E=NOT_RUN
FAULT_AND_RESUME_REPLAY=NOT_RUN
OFFSITE_MEMORY_COMPATIBILITY=UNVERIFIED
```

本轮没有消除软件故障，已消除的是“最新代码在哪里/两份FAST是否相同”的信息盲区。不得把保全完成写成生产修复完成。
