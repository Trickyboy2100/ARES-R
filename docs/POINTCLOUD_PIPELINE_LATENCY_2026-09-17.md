# 点云避障链路延迟基准（2026-09-17）

## 基准边界

相机部分执行 3 帧 warm-up、20 帧 measured；每帧全部在内存中完成，不写 EpicRaw、PLY、PNG 或阶段 JSON。cuRobo 部分复用已经初始化的 planner，执行 1 次 warm-up、12 次 measured 固定查询。所有结果均为 `DEMO_OFFLINE_ONLY` 且 `execution_allowed=false`。

机器可读结果：

```text
/home/yikun/ARES-R_AUDIT_20260917/pointcloud_curobo_demo/latency/
├── perception_fast_path.json
├── curobo_benchmark_artifact.json
└── latency_benchmark.json
```

## Perception → SceneSnapshot / SceneCompiler

| 阶段 | p50 (ms) | p95 (ms) |
|---|---:|---:|
| camera trigger | 38.58 | 47.14 |
| frame fetch | 1328.50 | 1337.22 |
| EpicRaw document decode | 1.34 | 1.43 |
| pointcloud decode/build | 141.36 | 143.65 |
| CAMERA → DEMO BODY | 145.89 | 256.35 |
| BODY ROI | 93.42 | 121.87 |
| robot/tool self-filter | 1777.20 | 1997.60 |
| support removal | 12.67 | 12.93 |
| 10 mm voxel | 508.23 | 523.44 |
| cluster/AABB | 7.77 | 8.16 |
| WorldModel commit/freeze | 0.76 | 0.81 |
| SceneCompiler | 0.64 | 0.92 |
| **perception scene total** | **4084.98** | **4279.32** |

实际 perception scene update 的 p50 等效频率约 **0.245 Hz**。主要瓶颈是 self-filter、相机 frame fetch 和当前 NumPy voxel 实现；WorldModel/SceneCompiler 合计约 1–2 ms，不是瓶颈。

## cuRobo steady-state

| 阶段 | p50 (ms) | p95 (ms) |
|---|---:|---:|
| world update | 0.37 | 0.45 |
| collision query | 1.65 | 1.98 |
| planning | **1111.75** | **1144.23** |
| **capture→scene→plan total** | **5185.95** | **5316.40** |

规划统计排除了 CUDA/cuRobo import、planner 构造和第一次求解 warm-up；三组 Demo artifact 仍单独保留 cold orchestration timing，避免把两种指标混淆。

## 运行模式建议

| 模式 | 当前结论 |
|---|---|
| `STATIC_SNAPSHOT` | SUPPORTED |
| `CHECKPOINT_RESCAN` | SUPPORTED |
| `SCENE_WATCHDOG_1HZ` | NOT SUSTAINABLE |
| `SCENE_WATCHDOG_2HZ` | NOT SUSTAINABLE |
| `SCENE_WATCHDOG_5HZ` | NOT SUSTAINABLE |

当前路线适合“底盘停止 → 拍摄 → 冻结 snapshot → 规划 → 受监督执行前再验证”的检查点工作流，不应宣称实时 replan/MPC。

## 后续优化顺序

1. 将 47 个 sphere 的逐球全点云距离计算改为批量 GPU/CUDA 或空间索引 self-filter。
2. 以组织化 depth/pointcloud mask 直接做 ROI 与 self-filter，避免反复创建百万点中间数组。
3. 将 NumPy `unique` voxel 替换为持续驻留的 GPU voxel/hash pipeline。
4. 在不改变数据合同的前提下，把 camera capture、上一帧处理与 planner world update 做有界流水化。

任何优化后仍需保留相同的 provenance、snapshot binding 和 production calibration gate。
