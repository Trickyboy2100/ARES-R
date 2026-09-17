# 双臂速度 profiles（离线设计）

site ceiling 来自 `config/jaka_mini2_motion.site.json`：所有关节最大 `0.10 rad/s`、最大 `0.20 rad/s²`。任何 profile 超过 ceiling 时加载即失败。

| profile | 最大速度 | 最大加速度 | 用途 | 状态 |
|---|---:|---:|---|---|
| precision | 0.015 rad/s | 0.03 rad/s² | fine approach、接触前 commissioning | UNCOMMISSIONED |
| slow | 0.030 rad/s | 0.06 rad/s² | 第一轮完整路径监督执行 | UNCOMMISSIONED |
| normal | 0.060 rad/s | 0.12 rad/s² | slow 验收后的自由空间段 | UNCOMMISSIONED |
| site_max | 0.100 rad/s | 0.20 rad/s² | 绝对上限，不作默认值 | UNCOMMISSIONED |

现场验证顺序固定为 `precision → slow → normal → site_max`，逐档记录 tracking error、振动、停止距离、Servo queue、保护停止和急停响应。precision 用于接近，运输段也不能自动继承更高档位。未通过的档位保持 `UNCOMMISSIONED`。
