# 右臂原位抓取—230mm抬升—放回复位

当前版本：1.1.0（2026-11-09 契约变更，待现场重新验收）。Demo ID：`right_arm_pick_lift_replace_reset_v1`，控制台别名 `demo-2-branch-grasprptspdup`。

1.0.0 曾在固定夹具下完成两次无中断实机验收（热态134.54秒、RC1 planner冷态144.13秒），但那两次运行属于**旧契约**：控制器 `tool_id=2`、带 `TCP_LOCAL_Z -10°` 姿态补偿、有效速度约 0.10 rad/s。1.1.0 起按操作员要求改为站点 0.2 rad/s 上限、**取消 TCP 偏置**、控制器工具 `tool_id=3`（tcp3），因此抓取位姿与水平度必须在现场重新确认后才能引用本版本的实机结论。

## 2026-11-09 契约（运动前 fail-closed 校验）

执行器 `scripts/run_pick_reset_timing.py` 在**任何运动之前**执行 `preflight()`，任一项不满足即抛 `PREFLIGHT_FAILED` 并停止（不派发后端 STOP、不运动），同时把证据写入本次 run 目录：

| 项 | 要求 | 证据文件 |
| --- | --- | --- |
| 站点速度上限 | `config/jaka_mini2_motion.site.json` 的 `max_velocity_rad_s` 六个关节**都等于 0.2** | `site-ceiling.json` |
| 偏置 | `task_tcp_offset_m_rad` 六项全为 0，且 `demo_tcp_orientation_compensation.enabled=false`（角度为 0） | `zero-bias.json` |
| 工具 | 控制器右臂 `tool_id` == 原生包内冻结的 tool id == 契约 `required_tool_id=3`（tcp3） | `tool-binding.json` |

汇总结果写 `preflight.json`。注意：**泊位（slot）检测偏置不在本次取消范围内**，仍是只读的原注册表值。原生文件头里的 tool id 来自打包时解析出的控制器工具（`package_pick_reset_timing.py:resolve_tool_id`），代码中不再出现写死的 `tool_id=1`。

### 接触豁免（2026-11-09，取消偏置后的连带问题）

清掉 TCP 偏置并改用 tcp3 后，抓取位姿在 Y/Z 上各移动约 25 mm / 17 mm，首次运行在准备阶段被拒：

```
CONTACT_TOOL_NON_TARGET_WORLD_COLLISION: observed_support_02_component_00_protruding_obstacle_008
```

离线复算（`tmp/11.9/diagnose_lift_collision.py`，只用冻结文件、不连设备）显示：只有 35–40% 开度下的夹爪指根（`4C2_Link1`）与支撑面上两个实测凸起的 **7 mm 膨胀 AABB** 相碰，深度 **0.59 mm（25 点）** 与 **0.13 mm（19 点）**，且只发生在抬升最初 5 个密集采样点；实际夹持读数是 raw 36–37（约 4% 开度），那里完全不碰。

处理方式沿用操作员 2026-11-06 给 demo3 批准的同一方案（option C）：`parameters.json:contact_extra_allowed_protrusion_waivers` 按 **本体坐标中心 + 半径 10 mm + 点数 ≤30** 描述这两个凸起，经 `prepare_authorized_first_pick.py --contact-extra-allowed-protrusion-waivers` 匹配本帧扫描后，只把命中的 primitive 加入 `manipulation_contact_scope.target_object_ids` / `motion_constraints.ignore_cuboid_ids`，其余物体仍然全硬。扫描若没有这两个凸起，豁免不命中、门限照旧 fail-closed（不会静默放宽）。

离线用真实 `continuous_demo_lift.validate_path` 复核：无豁免 FAIL → 有豁免 PASS，前 100 mm 对实测体素的最小间隙 **5.36 mm**（`tmp/11.9/verify_protrusion_waiver.py`）。**未做实机验证。**

## 流程与范围

当前固定夹具和100mm宽料盘；右臂从验收center开始。左臂保持，底盘不动。

fresh ID1 + Pixel Pro → fresh scene → cuRobo到55mm预抓取 → 40%开度接近 → 闭爪 → 连续BODY+Z抬升230mm → 场景与新鲜滚动夹爪反馈验证 → 反向下降放回原位 → 松爪 → 反向退出 → 回本次初始center。

并行仅用于下一段Native准备、只读底盘观察及扫描/夹爪反馈，不包含底盘与机械臂同时运动。仍保留controller、tracking、scene/state绑定和到位检查。遇到fault不自动继续，不自动下降/松爪。

这不是跨站取放，不使用ID3或六泊位。`source_parameters.json`为现场继承配置快照，含旧roundtrip的PLACE等未使用字段；真实阶段由本Demo入口及后端定义，不能按那些旧字段推断本流程会移动底盘。

## 运行

仅在 `.32:/home/yikun/ARES-R-RC1-20261019`，使用既有 `.venv`。ID1通信服务、Pixel Pro、独立canonical backend/WebUI和planner必须已启动。相机标定、工具、持物模型和现场夹具应与验收一致，现场监督与物理急停可用。

只准备，不运动：

```bash
cd /home/yikun/ARES-R-RC1-20261019
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --prepare
```

新鲜准备后自动执行整轮（明确监督授权）：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --execute \
  --authorization 'RIGHT PICK RESET TIMING' --onsite-observer-confirmed
```

该入口是薄客户端，调用已验收的准备/打包工具和canonical `start` API，不复制机械臂执行算法。已准备候选可追加`--prepared <该Demo自己的run目录>`，超过原300秒新鲜度或已使用则拒绝，必须重新prepare。不能复用本目录中的验收轨迹。

停止：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --stop
```

等价于现有WebUI停止按钮/canonical `/api/operations/stop`；不能替代物理急停。开机、刷新页面、选择Demo或prepare均不会自动运动。

## ART和WebUI

共用DemoRegistry，ART `demo list` / `demo select right_arm_pick_lift_replace_reset_v1` / `demo prepare` 可查看版本和命令；WebUI的Demo目录显示同一新条目。当前不新增或声称已有该Demo的专属一键运行按钮，实机运行使用上述正式入口。

## 配置和证据

- `demo.json`：阶段、范围、正式入口和freshness合同。
- `source_parameters.json`：与验收一致的现场参数快照；不覆盖其他Demo。
- `pinned_inputs.json`：后端脚本及现场配置哈希；复现入口发现改变会要求明确版本审核，不影响独立实验入口。
- `evidence.json`：热态/冷态成功记录、pointcloud/package/native hashes及耗时。
- 新运行写入 `worklog/evidence/demo-runs/right_arm_pick_lift_replace_reset_v1/<run>/`。

本机/现场其他配置可能不同，不能为让校验通过而盲目覆盖生产配置。URDF、SDK、native sender、camera worker及既有初始化/几何模板仍为现场依赖；该定义不等于完整跨机器安装包。原始点云继续保留现场/private归档，不直接公开推送。

原golden `right_arm_epic_pick_lift_v1`、`scripts/run_first_pick_demo.py`及跨站roundtrip均不替换、不迁移。
