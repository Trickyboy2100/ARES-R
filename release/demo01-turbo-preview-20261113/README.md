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
