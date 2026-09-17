# Pixel Pro 点云 → cuRobo 避障规划 Demo（2026-09-17）

## 结论与安全边界

真实 Pixel Pro 点云已经通过正式合同进入 `ObservationEpoch → WorldModel → SceneSnapshot → SceneCompiler → cuRobo`，没有建立 `Epic → cuRobo` 旁路。FREE / AVOID / BLOCK 三组 planning-only 测试均符合预期。

本结果仅为 `DEMO_OFFLINE_ONLY`：

- production `T_body_camera` 仍为 `null / UNCOMMISSIONED`；
- `execution_allowed=false` 始终保持；
- 本轮机械臂、夹爪、AMR 运动次数为 **0**；
- 生成的轨迹不得发送到控制器。

## 输入与可追溯性

| 项目 | 值 |
|---|---|
| Pixel Pro frame | `719_56679b67-8d89-4c2b-9905-bdc1c8a5bd83` |
| PLY SHA-256 | `dae213cf40bd60bbef07165679e94c10d4ad4c52e99b36967f796eaa19187124` |
| calibration candidate | `DEMO_ONLY:da08e15b7643b5ebef2a58784fea5ac3203d77a3dccd8a5867a34b59a4aa7c63` |
| SceneSnapshot | `SCENE_5902d97af3de41daa685672e23b6b6c7` |
| compiled scene digest | `9a43645836b558f729ea2a0f51d847b56bb0a84193e4fd31876c71195c3d1de1` |
| cuRobo source | `8e734f3ced1df898990bcd92de40abce475907db`，manifest SHA 校验通过 |

完整证据位于：

```text
/home/yikun/ARES-R_AUDIT_20260917/pointcloud_curobo_demo/
├── frame716_pipeline_v2/       # 01–08 图、pipeline、collision world、snapshot
├── planning_v4/                # 三组 request/result/log/plot
└── latency/                    # 内存快路径与 cuRobo steady-state benchmark
```

目录名 `frame716_pipeline_v2` 是实验迭代名；机器可读的真实 frame ID 以上表及 `pipeline.json` 为准。

## 点云碰撞世界

流水线使用 1,896,659 个 CAMERA 有效点，经 DEMO BODY 变换后：

| 阶段 | 输入点 | 输出点 | 关键参数 |
|---|---:|---:|---|
| manipulation ROI | 1,896,659 | 1,817,343 | BODY `[-0.62,-1.10,0.43]` 到 `[0.90,0.99,1.97] m` |
| robot/tool self-filter | 1,817,343 | 1,725,694 | 47 spheres，25 mm margin |
| support separation | 1,725,694 | 894,663 | table `z=1.022783 m`，±35 mm removal band |
| 10 mm voxel | 894,663 | 7,965 | memory geometry |
| cluster/AABB | 7,965 | 7,946 | 16 AABB，25 mm inflation |

Known 与 unknown 已分开：

- `KNOWN_SUPPORT`：拟合桌面平面作为桌面上表面，实体只向下延伸 50 mm；
- `KNOWN_ROBOT`：右臂真实 cuRobo collision spheres；
- `proxy=true`：右工具 capsule 与未完整建模的左臂 conservative capsule；
- `UNKNOWN_RESIDUAL`：table/self-filter 后的真实点云聚类 AABB；
- BODY 中央 140 mm 禁区继续作为 SafetyConstraint，不伪装成点云物体。

## Demo-only BODY candidate 局限

candidate 来自稳定桌面法向与单姿态机器人几何对齐，不是生产 hand-eye：

- camera pose candidate：BODY `[-0.4018, +0.0677, 1.8434] m`，yaw `-102.87°`；
- registration median residual `18.86 mm`，RMS `37.78 mm`，p90 `69.48 mm`；
- 35 mm inlier ratio `77.9%`；
- 单姿态多解不确定性：yaw spread `17.04°`、translation spread `0.233 m`；
- 工具与左臂仍含 conservative proxy，self-filter 只能视为 demo-scope PASS。

因此图像可用于路线演示和软件合同验收，不能用于实机安全证明。

## cuRobo 三组同起终点规划

三组均使用保存的只读右臂关节状态作为起点，目标仅改变 J1 `+0.28 rad`，不读取或驱动实时控制器。

| 场景 | 碰撞世界 | 结果 | 证据 |
|---|---|---|---|
| FREE | known support，无额外 blocker | SUCCESS | 起点/路径最小模型间隙约 `2.33 mm` |
| AVOID | FREE + 25 mm `DEMO_OBSTACLE_AUGMENTATION` | SUCCESS | 直连基线碰撞 `-37.50 mm`；规划成功；相对 FREE 最大 TCP 偏离 `58.48 mm` |
| BLOCK | FREE + 100 mm goal enclosure | EXPECTED FAILURE | 起点 `+2.33 mm`，目标 `-75.00 mm`，失败原因是目标被阻塞 |

AVOID augmentation 位于由 FREE 查询产生的中间区域，明确独立于真实 residual 层；其用途是稳定证明规划器确实响应碰撞世界，不冒充相机检测到的实体。

## 可视化与录屏建议

建议依次展示：

1. `03_demo_body_overlay.png`：BODY 轴、桌面、机器人/工具代理与水印；
2. `05_self_filter_before_after.png`：self-filter 前后；
3. `07_unknown_residual_clusters.png` 与 `08_final_collision_world.png`；
4. `planning_free.png`、`planning_avoid.png`、`planning_block.png`；
5. `planning_free_avoid_comparison.png`：同起终点路径差异。

画面必须保留 `DEMO_ONLY / NOT FOR EXECUTION`，不要把当前 overlay 表述为 production calibration。

## 明日最少现场 blocker

1. 用多姿态或可追溯站点基准完成 production `T_body_camera` commissioning，并设定可验收 residual 阈值。
2. 用真实机器人点云逐臂验收 self-filter；补齐 gripper、工具和另一臂的真实 collision geometry，移除 conservative capsule 的不确定性。
3. 现场确认 BODY ROI、桌面上表面与目标/允许接触物语义，避免把目标错误编译为 forbidden obstacle。
4. 对 production snapshot 重跑 FREE/AVOID/BLOCK、起终点碰撞和 SafetyKernel/安全平面检查。
5. 只有上述条件全部通过后，才创建一次性 ExecutionLease，进入低速、现场急停可用的受监督执行 commissioning。
