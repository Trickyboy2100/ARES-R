# Epic Pro / ATOM 点云接入 cuRobo 可行路线

存在可行路线，而且比较适合当前 ARES-R 架构。但要先明确一个接口边界：

Epic Pro/ATOM 内部可以获得实时点云、手眼标定、ROI，并能生成机器人坐标系点云；公开的 5700 协议目前主要返回抓取位姿或规划路径点，没有公开说明可直接返回点云。因此不能仅靠现有 `320/120` 指令把点云送给 cuRobo，需要增加文件、ATOM 扩展或独立数据接口。[EpicPro 输入](https://docs.transfertech.cn/tf_docs/zh/atom/1.3.2/operator/epic_pro/EpicProDataInput.html)、[EpicPro 输出](https://docs.transfertech.cn/tf_docs/zh/atom/1.3.1.1/operator/epic_pro/EpicProOutput.html)、[5700 接口说明](https://docs.transfertech.cn/tf_docs/zh/epic-pro/1.3.0.1/support/interface-instructions.html)

## 方案一：完全使用 Epic Pro 内置规划

流程：

```text
底盘停止
→ Epic Pro 拍照
→ 检测抓取点
→ Epic Pro 内部碰撞检测/路径规划
→ 5700 返回关节路径点
→ ARES-R 校验、时间参数化
→ JAKA ServoJ 执行
```

官方文档支持返回笛卡尔或关节路径点，并可以配置机器人、工具、场景物体、抓取与回撤路径。[路径规划参数](https://docs.transfertech.cn/tf_docs/zh/epic-pro/1.3.0.1/operations/pick-path-plan-parameters.html)

优点：

- Epic 内部已经具备相机、手眼标定、检测和规划链路。
- 接入周期最短。
- 可以直接与当前 5700 客户端结合。
- Epic 界面便于调试抓取点和规划结果。

缺点：

- JAKA Mini2 是否属于 Epic 已适配的可规划机器人需要现场确认；官方说明自定义机器人可能只有碰撞检测能力。
- 官方资料没有明确证明“所有原始点云点”都会成为规划障碍。更明确的机制是场景模型、碰撞检测对、动态定位和工具绑定。
- 返回路径点没有直接对应 JAKA ServoJ 的实时周期、速度和加速度，需要 ARES-R 再时间参数化。
- Epic 内部碰撞模型、TCP、夹爪和携带料盘模型不容易由 ARES-R 独立审计。

适合：快速验证和作为 cuRobo 路线的对照基准。

## 方案二：ATOM 将点云简化成 OBB/AABB，再交给 cuRobo

这是当前最推荐的第一阶段路线。

### ARES-R 已落地的方案二接口（2026-09-08）

当前已打通以下可审计边界，全部命令本身不驱动机器人：

```text
epic pointcloud capture
  → logs/epic_captures/<capture-id>/{pointcloud.ply,image8bit.png,depthGrey.png,capture.log,manifest.json}

epic pointcloud inspect <pointcloud.ply>
  → 校验二进制 PLY、有效点比例、范围、SHA-256，并明确 mm → m

epic obstacles inspect <atom-obstacles.json>
  → 校验 ATOM 输出必须为 BODY 坐标、SI 米、AABB、时间戳和标定版本

epic obstacles convert <atom-obstacles.json> right <scene.json>
  → BODY AABB 转换为右臂 URDF base_link 下的保守包络 AABB

curobo scene load <scene.json>
  → 冻结带来源信息的 Epic/ATOM cuboid 场景，供下一次 cuRobo 规划使用
```

原始点云不能直接跨过这条边界。当前现场 PLY 为 `1920×1200`、230.4 万点、有效率约 81%，SDK 数据单位经官方说明和实值复核均为毫米；ARES-R 在清单中显式记录乘数 `0.001`。相机点云尚缺 `T_body_camera` 外参、自体/工具剔除和地面/ROI commissioning，因此只允许采集、审计，不标记为 planning-ready。

ATOM 输出示例见 `config/epic_atom_obstacles.example.json`。示例使用未标定占位版本，`inspect` 可检查格式，但 `convert` 会按预期阻断；现场标定验收后必须把版本号显式加入 `config/system.json` 的 `atom_obstacles.commissioned_calibration_revisions`。第一阶段只接收 AABB；BODY AABB 转入倾斜安装的机械臂基坐标时会取旋转后的轴对齐包络并叠加 `inflation_m`，几何更保守但不会因忽略朝向而缩小障碍。OBB 要在当前锁定 cuRobo 版本的旋转盒链路完成实测后再开放。

```text
Epic Pro 拍照
→ ATOM：ROI、滤波、降采样、聚类
→ 障碍点云分组
→ 每组生成 AABB/OBB
→ 输出障碍 JSON
→ 转换到 BODY/左右臂 cuRobo base_link
→ cuRobo Cuboid World
→ 规划、稠密碰撞复检
→ ServoJ 执行
```

ATOM 官方已有点云降采样、聚类、条件过滤以及 AABB/OBB 计算能力。[点云降采样](https://docs.transfertech.cn/tf_docs/zh/atom/1.3.2/operator/point_cloud/filter/DownSampleWithNormal.html)、[点云包围盒](https://docs.transfertech.cn/tf_docs/zh/atom/1.3.1.1/operator/point_cloud/feature/RectanglePlanePointsBbox.html)

优点：

- 与 ARES-R 当前 `scene_cuboids()` 和 cuRobo Cuboid 场景非常接近。
- 数据很小，容易记录、回放、比较和人工检查。
- cuRobo 官方称 cuboid 碰撞查询比 mesh 更快。
- 可以给包围盒增加安全膨胀量，处理点云缺失和标定误差。
- 特别适合料筐、托盘、桌面、车体等近似规则障碍。

缺点：

- 形状简化可能过于保守，窄通道容易被封死。
- 飞点可能生成巨大包围盒，必须先滤波和聚类。
- OBB 需要确认当前锁定的 cuRobo V2 是否支持动态旋转盒；ARES-R 目前只接受轴对齐 cuboid。
- 5700 不直接返回这些包围盒，需要新增 ATOM→ARES-R 数据通道。

建议初版数据：

```json
{
  "schema_version": 1,
  "source": "epic_atom",
  "capture_time": "...",
  "frame": "epic_robot_base",
  "calibration_revision": "...",
  "obstacles": [
    {
      "id": "tray",
      "type": "aabb",
      "center_m": [0.4, -0.2, 0.9],
      "dims_m": [0.6, 0.4, 0.2],
      "inflation_m": 0.02,
      "confidence": 0.98
    }
  ]
}
```

## 方案三：点云生成 Mesh/凸包后交给 cuRobo

流程：

```text
点云滤波
→ 分割
→ 表面重建或凸包
→ OBJ/mesh
→ cuRobo Mesh World
```

优点：

- 比包围盒更贴近不规则障碍。
- 对倾斜料箱、复杂支架和非矩形物体更准确。

缺点：

- 重建、简化和传输耗时更高。
- 动态更新 mesh 会增加 GPU 缓存管理复杂度。
- 点云孔洞、遮挡可能生成错误表面。
- cuRobo 官方资料指出 mesh 碰撞检查慢于 cuboid。
- 不适合作为第一版实时链路。

适合：少量固定、形状复杂且包围盒过于保守的障碍。[cuRobo 碰撞世界表示](https://curobo.org/get_started/2c_world_collision.html)

## 方案四：点云进入 Voxel/ESDF/nvblox

流程：

```text
深度图/点云连续输入
→ 体素融合
→ 占据栅格或 ESDF
→ cuRobo Voxel/nvblox Collision World
→ 持续更新场景
```

优点：

- 能表达未识别障碍，不要求每个物体都有模型。
- 适合密集、不规则环境。
- 可以融合多帧，减少单帧孔洞。
- cuRobo 官方支持 Voxel、ESDF 和 nvblox 深度图碰撞表示。

缺点：

- 当前 ARES-R 固定版本只接入了 cuboid，改造量最大。
- 需要获得稳定的原始点云或深度流，5700 不够。
- 必须处理机器人自身、夹爪、料盘、另一条机械臂和 AGV 的点云剔除。
- GPU 显存、体素分辨率、更新频率和 CUDA Graph 缓存都会影响性能。
- “实时更新点云+正在执行 ServoJ”不能天然保证安全；场景变化后至少需要停止、重新规划，或者建立连续 MPC/轨迹拼接机制。

适合：第二阶段或最终的未知障碍环境。

## 方案五：混合场景模型

这是长期最合理的路线：

```text
固定模型：
AGV、双臂基座、中央14cm禁区、工作台

动态已知物：
Epic识别料筐/托盘/工件 → OBB或已知Mesh+位姿

未知剩余点云：
Voxel/ESDF

执行状态：
夹爪、TCP、已抓料盘、另一机械臂扫掠体
```

优点：

- 规则物体用快速 cuboid。
- 复杂固定物体用 mesh。
- 未知剩余区域才使用 voxel。
- 可以明确表达夹取后 TCP 前伸和负载体积。
- cuRobo 检查的是整条机械臂碰撞球、工具和场景，不只是 TCP。

缺点：

- 坐标系、时间戳和对象生命周期管理要求最高。
- 必须防止同一障碍同时以 cuboid、mesh 和 voxel 重复出现。
- 需要可靠的另一机械臂状态与扫掠空间共享。

## 推荐实施顺序

建议先做“底盘停止后的单帧规划”，暂时不追求运动中的实时点云：

```text
1. 底盘到位并停止
2. 等待振动和机械臂状态稳定
3. Epic Pro触发拍照
4. ATOM输出抓取位姿、简化障碍盒、时间戳和标定版本
5. ARES-R冻结本次场景快照
6. 转换到BODY及对应机械臂cuRobo base_link
7. 加入固定车体、中央禁区、另一机械臂和工具/料盘模型
8. cuRobo规划
9. ARES-R稠密碰撞复检
10. ServoJ执行
11. 抬起后重新拍照、更新场景、重新规划放置段
```

第一版推荐采用“方案二 + 固定场景”，后续再升级成方案五。这样能最快复用当前 cuRobo cuboid 接口，又能保留完整日志和离线回放能力。

## 最大技术风险与结论

最大技术风险不是点云降采样，而是以下三点：

- Epic/ATOM 到 ARES-R 的点云或障碍模型输出接口；
- 相机、BODY、左右臂 base_link 之间的外参和时间同步；
- 从点云中剔除双臂、夹爪、已抓料盘及 AGV 自身。

结论：路线明确存在，5700 单独不够；当前最稳妥的是底盘停止后采集单帧，由 ATOM 输出膨胀后的 AABB/OBB 给 cuRobo，等这条链路验证可靠后再考虑 Voxel/ESDF 实时更新。
