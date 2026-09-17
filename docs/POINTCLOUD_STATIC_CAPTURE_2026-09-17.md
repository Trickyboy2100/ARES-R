# Pixel Pro 静态点云与 BODY 路线结果（2026-09-17）

## 手眼/ROI 恢复

相机只读 API `get_handeye_calibration_data(192.168.99.199:5000)` 返回：

```text
installationType = EIH
calibrationResult = null
calibrationPointDict = null
```

相机完整只读 config/内参、本机 Epic/ATOM 项目目录、`runSpace.json`、cam2Base/hand-eye/3D ROI 搜索均未得到可追溯外参。相机内记录的 EIH 还与现场固定 eye-to-hand 描述冲突，不能当作生产配置。

结论：`T_body_camera` 没有恢复成功，状态为 `BODY_TRANSFORM_BLOCKED`。不得使用目测 49° 俯角生成矩阵。原始只读结果：

`/home/yikun/ARES-R_AUDIT_20260917/afternoon/epiceye_readonly_config.json`

## 四帧新采集

相机 Pixel Pro `PP005901045`，固件 `3.4.9`，SDK `4.0.0`。每帧保存同一 EpicRaw 解码得到的 PLY/RGB/depth。

| frameID | EpicRaw SHA256 | PLY SHA256 | raw 顶点 | 有效点 |
|---|---|---|---:|---:|
| `716_40e510fd-097f-4466-a844-235ffd8c6b39` | `c1ae53fbbc04c9d6207109a44d1242d71f2d71069c01c75d5fd3483af7042ec2` | `69fc4757906ee095c442277a3f147c17bf5e0b19d4b6a9cdd397e4e86f7850f6` | 2,304,000 | 1,896,977 |
| `717_14672467-8b80-414e-b606-293cb146871a` | `2ecfa98f8263cf7e379534951302692d6236a7a7fb20a4e4fe6355ad00bf3d8c` | `f458ce3489cb4612188dd5b921d5a942b42508cc62c67459a7bd751c17732781` | 2,304,000 | 1,896,747 |
| `718_8c8eed98-2382-47f2-a1b5-2098e4c01041` | `ee586749d2905ba193fae6f4e3f3070dfbbe6cc15e8dd40b86bfaed87bb87bd3` | `7cd7fe4386cc4a35bf81264372ad588e8dd652c301d60c047a2d1439edf1dea4` | 2,304,000 | 1,896,581 |
| `719_56679b67-8d89-4c2b-9905-bdc1c8a5bd83` | `95e54320bbc6857583b37c4f19e7d536574c3785528966bdde6ada86193a5c0c` | `dae213cf40bd60bbef07165679e94c10d4ad4c52e99b36967f796eaa19187124` | 2,304,000 | 1,896,659 |

证据目录：`/home/yikun/ARES-R_AUDIT_20260917/afternoon/captures/`。

## 处理结果

10 mm voxel 后四帧分别为 15,517 / 15,576 / 15,556 / 15,560 点，单次 voxel 约 0.047–0.048 s；camera-frame DBSCAN 得到 28–31 个膨胀 20 mm 的实验 AABB。第一帧 5 mm voxel 为 56,664 点、31 个 AABB。

每帧生成：

- `01_raw_valid_camera.png`
- `05_voxel_clusters_aabb.png`
- `pipeline.json`（各 stage 前后点数、bounds、runtime、参数、frame、hash）

证据目录：`/home/yikun/ARES-R_AUDIT_20260917/afternoon/pointcloud_pipeline/`。

由于没有可信 `T_body_camera`：

- `camera→BODY`：BLOCKED；
- BODY ROI：BLOCKED；
- 基于真实机器人几何的 self-filter：BLOCKED；
- 当前 AABB 仅用于 camera-frame 算法调试，`planning_ready=false`，禁止直接加载 cuRobo。

未验收 ROI 候选仍来自真实 cuRobo reach audit：global `x[-0.62,0.90], y[-1.10,0.99], z[0.43,1.97] m`，左右臂候选见 `config/pointcloud_pipeline.site.json`。恢复外参后必须重新输出 raw→BODY→ROI→self-filter before/after→voxel→AABB overlay，并证明右臂被删除而桌面/外物未被误删。
