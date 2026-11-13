# Demo01 Turbo Preview

独立名称为 `demo01_turbo_preview_v1`。仅使用已保存的两份真实场景请求，验证center与restore规划、运行时复用、独立碰撞验证及Native打包。结果明确标记 `execution_allowed=false`、`physical_motion=false`、`live_scene_validated=false`。

当前版本未接ROS运动入口。脚本没有相机采集、SDK读写、夹爪、AMR或Native sender派发操作。Native文件内容只计算哈希，保存审计JSON，不输出可供派发的Native轨迹文件。原Demo01继续使用原ROS入口。

## 已完成的试验

2026-11-13在现场GPU上完成三轮center/restore，共六次规划与打包，全部通过。两段在同一进程交替执行，第一段之后五段全部复用runtime。

|阶段|规划耗时|打包耗时|预计运动时长|
|---|---|---|---|
|首次center冷请求|5.73秒|0.044秒|22.08秒|
|后续center热请求|1.22～1.23秒|约0.032秒|19.36秒|
|restore热请求|1.24秒左右|约0.007～0.009秒|13.28秒|

表中运动时长为规划值。试验没有实际运动。worker内六段总计约12.06秒，包含首次冷路径，外层进程启动及Torch导入时间另计。第一次与热运行的路径时长存在差异，应分别保留记录。两份冻结场景的起终点、姿态、机器人模型等来自成功运行的原始请求，不能代替当前现场到位后的fresh scene。

## 执行一次无运动试验

现场候选目录为 `/home/yikun/ARES-R-DEMO01-TURBO-PREVIEW-20261113`。以下命令在服务器终端执行；每次output须为新目录。

```bash
cd /home/yikun/ARES-R-RC1-20261019
/home/yikun/ares-r-curobo-venv/bin/python \
  /home/yikun/ARES-R-DEMO01-TURBO-PREVIEW-20261113/run_preview.py \
  --repository /home/yikun/ARES-R-RC1-20261019 \
  --output /home/yikun/ARES-R-DEMO01-TURBO-PREVIEW-20261113/runs/frozen-next \
  --repeats 3
```

参数位于 `parameters.json`。FAST50、2轨迹seed/4IK seed、CUDA graph、Native CPU独立验证、原同路径重采样均在候选请求内配置，不修改生产配置。GPU进程显存份额设置0.45。180秒仅为整次离线试验的进程取消边界。

## 结果

- `result.json` 保存六段结果与明确的离线状态。
- `progress.json` 保存已完成段。
- `worker.log` 保存原planner输出及异常。
- 各段目录含source SHA、scene ID、复制后的请求、planning结果及native审计。
- `frozen-first-result.json` 为首次真实GPU试验结果。

下一步如需验证在线总等待，应在独立候选中增加fresh观测和当前状态的planning-only接入，并分别测scan、scene、SDK和计划；现有冻结试验没有覆盖这些耗时，也不发布物理执行能力。

## Turbo Demo01 准备流水线 V1

新增独立入口 `run_pipeline_preview.py`，名称 `demo01_turbo_pipeline_preview_v1`。准备调度代码位于 `preparation_runtime.py`，复用现有Skill ResourceLockManager，并在prepare阶段获取资源。GPU单线程持有CUDA runtime，CPU准备最多两个线程；任务按依赖图预约资源，避免同GPU并发求解。参数和观测输入版本保存在PreparedArtifact中，版本不符拒绝绑定，预测状态产物要求实际状态验证后方可另行绑定。

当前回放依赖如下。

```text
GPU启动/预热 ─────────┐
CPU冻结点云重建 ──────┴→ center规划 → center打包
                                  └→ restore规划 → restore打包
```

并行模式中GPU启动与两份冻结场景重建重叠，center打包与restore规划重叠。串行模式采用相同运算与验证，只调整依赖顺序。Native内容仅在内存中生成并检查，审计JSON保存到证据目录。

实测每种模式各3次，包含交叉顺序。串行总耗时中位数16.416秒（16.389～16.729），并行10.185秒（10.146～10.201），中位数减少37.95%。具体时间轴、每阶段资源/等待/耗时和规划结果见 `pipeline-comparison.json`。

该对比包含两份已保存Pixel Pro点云的场景重建、GPU冷准备、两段热规划及Native打包。没有新拍照、SDK实时状态或真实运动。此百分比不能套用到完整实机周期。当前准备锁为候选进程内锁，跨ROS/脚本的全局所有权仍需通过canonical backend接入。

Mac与现场Linux均通过7项调度回归，覆盖并行启动、依赖、共享资源互斥、版本变化、预测状态绑定、失败阻断和取消后回收自身子进程。CUDA求解在阶段回调边界检查取消，不能承诺硬实时中断；CPU场景子进程支持有界终止并回收。

服务器终端运行新的无运动并行版本，每次指定新的output目录。

```bash
cd /home/yikun/ARES-R-RC1-20261019
/home/yikun/ares-r-curobo-venv/bin/python \
  /home/yikun/ARES-R-DEMO01-TURBO-PREVIEW-20261113/run_pipeline_preview.py \
  --repository /home/yikun/ARES-R-RC1-20261019 \
  --output /home/yikun/ARES-R-DEMO01-TURBO-PREVIEW-20261113/runs/pipeline-next \
  --mode parallel
```

新代码和证据已部署到独立候选目录。当前入口为Python无运动预览，真实扫描与ROS运动的正式接入仍待后续实现和验收。
