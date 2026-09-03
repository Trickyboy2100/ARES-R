# cuRobo 路线迁移与实物化

## 来源基线

旧 ARES 仓库基线：`Trickyboy2100/ARES@b978cbd669b5a3f6bc0bd19defcbe5256692f145`。

相关文件：

- `robot/jaka_minicobo_gripper.urdf`
- `robot/jaka_minicobo_curobo.yml`
- `isaac_sim/simforge/core/planning.py`
- `isaac_sim/simforge/demos/dual_arm_planning_api.py`
- `isaac_sim/simforge/demos/tray_grasp_cycle/_curobo_worker.py`

## 迁移审计

旧基线可复用：MiniCobo URDF、关节名称、cuRobo 配置结构、`MotionPlanner` 初始化、独立进程隔离、关节轨迹导出。

旧基线不可直接用于实物：

- YAML 含旧机器绝对路径。
- 夹爪各 link 的 `collision_spheres` 为空，无法证明夹爪实体避障。
- 场景主要由仿真 USD 包围盒生成，缺少 Epic 实时点云到实物基座坐标的生产链路。
- 轨迹末端追加 `fallback_path` 关节修正；追加段未在原逻辑中重新碰撞验证。
- 轨迹按仿真帧消费，缺少 JAKA `servo_j` 的 8 ms 整数倍时间参数化、状态监控和中止门禁。
- 抓取后缺少真实料盘附着碰撞模型切换。

因此，旧代码只作为模型和算法参考，不作为真机执行入口。

## 实物化结构

```text
Epic 深度/点云 ──> 坐标变换与机器人点云剔除 ──> cuRobo WorldBlox/ESDF
Epic 抓取候选 ──> 正抓/反抓候选生成 ──> cuRobo IK + MotionPlanner
JAKA 当前关节 ──> 起点状态 ──> 稠密关节轨迹 ──> ARES-R 门禁 ──> JAKA servo_j
夹取事件 ──> 附着料盘碰撞球 ──> 撤离与放置重新规划
```

## 实施顺序

1. 从旧提交复制 URDF 与 YAML 到独立实验分支，清除绝对路径。
2. 与实物 MiniCobo 型号和控制器软限位逐项核对 URDF。
3. 重新拟合全部机械臂、法兰、夹爪和相机支架碰撞球；可视化检查覆盖与过度膨胀。
4. 重新生成自碰撞矩阵；禁止照搬未经采样验证的 ignore 列表。
5. 建立 Epic 点云到基座坐标的变换链；先用保存点云离线生成 ESDF。
6. 删除未复核碰撞的末端关节修正；目标误差不合格时整条规划失败。
7. 为料盘建立附着球模型；夹取确认后调用附着接口，再规划撤离路径。
8. 将 cuRobo 最终插值轨迹写成 ARES-R 统一轨迹文件；记录模型和场景哈希。
9. 用 `motion validate` 完成静态门禁，再接入 JAKA 现场预检与 `servo_j`。

## 关键配置

- `self_collision_check=true`。
- 世界碰撞与自碰撞均启用。
- `interpolation_dt` 设为 8 ms 整数倍；首轮建议 80 ms。
- 碰撞激活距离从保守值开始，结合点云噪声与标定误差确定。
- 工具与附着物球体包含额外安全膨胀。
- 双臂场景中，静止臂必须作为动态机器人障碍更新；两臂同时运动需要联合规划或时空互锁，禁止分别规划后同时发送。

## 正抓与反抓评分

同一检测位姿生成绕接近轴相差 180° 的两组目标。每组目标运行多种子 IK 与完整路径规划，按以下顺序筛选：

1. 无世界碰撞、无自碰撞、无双臂碰撞。
2. 无软限位违规，整条路径无奇异阈值违规。
3. 附着料盘后的撤离和放置路径仍可解。
4. 最小碰撞距离最大。
5. 最小关节限位余量最大。
6. 轨迹时间、关节总位移和腕部旋转量最小。

## 官方依据

- cuRobo 自碰撞：`https://nvlabs.github.io/curobo/latest/reference/self_collision.html`
- cuRobo 深度相机：`https://nvlabs.github.io/curobo/v0.7.6/get_started/2d_nvblox_demo.html`
- cuRobo 机器人构建：`https://nvlabs.github.io/curobo/latest/api/curobo.robot_builder.html`
- cuRobo 附着物体：`https://nvlabs.github.io/curobo/latest/reference/sphere_fitting.html`
- cuRobo 运动规划：`https://nvlabs.github.io/curobo/latest/api/curobo.motion_planner.html`
