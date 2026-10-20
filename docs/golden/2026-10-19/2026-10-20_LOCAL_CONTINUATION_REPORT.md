# 本地保全后续实现报告

日期：2026-10-20。分支：`codex/golden-offline-workbench-20261020`。本轮没有push、没有连接机器人、没有运动。

Golden锚点仍为 `f97ab4c`；新候选分三个小提交：

- `1de673d`：离线工作台、模型四视图、共享草稿接口、ART只读入口。
- `5aaab3b`：持物几何不变时复用CUDA构建、cache原因日志、真实冻结请求GPU基准脚本。
- `a80d36e`：成功持物修正正式可选接入package准备，默认关闭。

## 结果与边界

| 要求 | 已完成 | 尚未完成 |
|---|---|---|
| 同场景复刻 | 源码、参数、路线、偏置来源、成功接续代码和哈希保全；本地候选实现 | .32最终执行原始依赖缺失，无法逐字节完整回放 |
| 分阶段调试 | 20阶段中文入口，函数/参数显示，真实接续时间条 | 实机阶段恢复和全链无人干预重复验收 |
| 模型可解释 | 3正交图+透视图、模型来源、尺寸、padding显示切换、LINK6/BODY明确区分 | 缺完整现场scene，尚未接入自动实时碰撞pair高亮 |
| 持物模型 | 将成功修正函数接入正式builder可选参数；旧默认不变 | 自动泛化物体分割、不同物体检测时机与遮挡质量验收 |
| 称前站/烘干机前站 | 现有GRASP/PLACE别名、当前40/81/32路线只读映射；旧注册表不删 | 新导航station registry的实机定位认证 |
| 五次放置/反向任务 | 同一后端生成不同泊位转移意图草稿；占用未知明确显示 | 转换为正式TaskRuntime Scheme、所有泊位标定、称台补料/清空机制 |
| 并行 | 依赖、资源冲突、联合扫掠与收益边界评估 | 没有启用base/arm并行，也没有50mm触发底盘运动 |
| FAST优化 | 定位并修复过宽runtime构建键；新增cache日志和真实数据基准入口 | GPU实测提速和p95、现场全链耗时验收 |

## 本次验证

针对性65项全部通过，5.158秒；包含工作台HTTP、未知泊位拒绝、无运动接口、草稿生成、持物策略兼容、缓存失效/复用、超时取消、原有roundtrip与绘图回归。
最终全量797项：2 errors、2 skipped，错误均为旧 `test_ab_clear_loop` 在Mac读取Linux `/proc/<pid>/stat`，并非本轮新增功能失败。没有改生产进程身份逻辑来让Mac测试变绿。
Mac环境Python3.14，不等同现场Python3.10/Torch/CUDA。完整日志见local-validation。
工作台JavaScript语法检查、浏览器页面/三视图人工检查通过；模型图默认是明确标记的历史尺寸示意。
生产参数JSON、路线、system.json以及旧 `run_first_pick_demo.py` 本轮无改动。
测试产生的4份模拟plan_handle移至忽略的 `worklog/runtime/offline-test-artifacts-20261020/`，没有当成现场证据提交。

## FAST为什么可能很慢

10月15日的热请求0.7–1.9秒是在指定冻结用例，包含一例10mm JOG，不能直接与持物PLACE等同。当前最后成功预览solve约3.12秒，说明FAST并非从未成功。
Demo在FAST失败后移除单轮solver策略，进入QUALITY，单次上限240秒且可尝试两轮。15+240+240秒是预算总和，不是单次FAST实际求解时间；扫描/准备另计。
新发现：整份attachment记录纳入runtime_key，使观测和ownership变化可能重建worker，即使真正构建球体使用的link6_aabb不变。候选修正只缩小构建key，完整revision校验、fresh world和执行绑定不变；几何变化仍失效。GPU收益尚待测量。
起终点被过大的持物模型判为碰撞时，更久优化不会使它变成几何可行。真实失败复现应先分清INVALID_START/GOAL、IK、NO_PATH、TIMEOUT、独立检查失败，避免把所有409都叫“cuRobo慢”。

## 下一次独立工作顺序

1. 网络恢复后按SITE_COLLECTION只读补齐现场数据；尤其最终执行plan、运行注册表和native文件。
2. Ubuntu按LOCAL_WORKBENCH中的命令验证manifest、运行FAST25/FAST50；QUALITY另作显式受控对照。
3. 用相同数据验证payload候选准备和全链离线回放，再启用候选开关。
4. 先使单次串行任务自动复现，再接多泊位Scheme；并行运动另做联合模型和现场验收。

入口：`http://127.0.0.1:8788/workbench`；标准启动与ART命令见LOCAL_WORKBENCH。
