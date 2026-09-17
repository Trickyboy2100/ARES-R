# BODY–Camera registration control point（2026-09-17）

## 结论

`T_body_camera` 当前状态为 **INCONCLUSIVE**，不是 CANDIDATE，更不是 COMMISSIONED。没有矩阵获准进入 BODY ROI、self-filter、SceneSnapshot 或执行链。

## 桌面/support plane

四帧各迭代提取五个主要平面，再按跨帧重复性、法向/offset 稳定性、extent 和 inlier 数量排名；没有使用“最大平面必然是桌面”的规则。胜出的 `plane_track_00` 每帧均对应 `plane_00`：

| frame | 10 mm inliers | normal CAMERA | d (m) | RMS (mm) |
|---|---:|---|---:|---:|
| 716 | 5080 | `[.04622,.64685,.76122]` | -.820804 | 3.55 |
| 717 | 5071 | `[.04747,.64790,.76025]` | -.819902 | 3.21 |
| 718 | 5119 | `[.04559,.64686,.76124]` | -.820996 | 3.65 |
| 719 | 5103 | `[.04614,.64705,.76105]` | -.820799 | 3.52 |

平均法向 `[0.046354,0.647166,0.760939]`；最大法向偏差 `0.0862°`，offset 标准差 `0.425 mm`。相机光轴与support法向夹角 `40.453°`，等价于相对桌面向下约 `49.547°`。该事实只确定roll/pitch和support-relative高度；yaw与水平平移不可观。

`T_level_camera_candidate` 与完整plane tracks位于 `worklog/generated/support_plane_candidates.json`。四帧plane/LEVEL图位于：

```text
/home/yikun/ARES-R_AUDIT_20260917/body_registration/support_planes/
```

## Vendor hand-eye恢复

再次只读检查1316个项目/配置/缓存候选文件、Epic/ATOM路径和Pixel Pro SDK。相机 `get_handeye_calibration_data()` 的 `calibrationResult` 仍为空，没有找到与 `PP005901045`、cameraID 1和实际space绑定的 `cam2Base/cam2baseMatrix`。SDK文档和example不是现场标定证据。

## Robot + plane自动配准

从保存的只读右臂joints、真实cuRobo `robot.yml` collision spheres、已审计 `T_controller_model` 和 `T_body_rightbase` 生成28个collision spheres/1344个表面点。夹爪/tool mesh不完整，因此没有把它们宣称为可信配准几何。

比较了两种自动评分：完整非桌面云，以及明确记录的右侧可见机器人像素ROI。完整云最好局部解的模型表面中位/RMS为 `17.1/31.4 mm`，35 mm内点率79.0%；但四个全局初始化分裂为至少两个近似同分解，偏航差 `17.04°`、平移差 `0.233 m`。右侧像素ROI的多初值分裂更严重：`125.79°/0.911 m`。

四帧从同一个局部解细化时仅相差 `0.48°/6.6 mm`，说明静态采集重复性好，但不能消除全局多解；不能把“同一错误盆地内稳定”当成唯一标定。

诊断最佳矩阵只保留用于复盘，`config/generated/T_body_camera.candidate.json` 中正式 `T_body_camera=null`、`planning_allowed=false`。

## 下一步最小证据

需要以下任一项打破yaw/XY多解：恢复真实vendor矩阵；测量至少三个非共线BODY基准点；相机观测AprilTag/标定板BODY位姿；或在受监督条件下采集两个明显不同右臂姿态并进行多姿态联合配准。单一静态姿态和不完整collision spheres不足以commission。
