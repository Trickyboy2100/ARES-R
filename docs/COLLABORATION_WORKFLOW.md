# 并行调试与交接规范

## 工作包

| 工作包 | 分支前缀 | 可修改范围 | 必交产物 |
| --- | --- | --- | --- |
| Epic 感知 | `vision/` | 相机配置、模板、标定、检测解析、视觉数据集 | 原始报文、数据哈希、误差统计、候选位姿 |
| Epic 规划 | `epic-plan/` | Epic 场景、碰撞矩阵、工具模型、路径导出 | 关节路径、配置版本、规划失败样本 |
| cuRobo 规划 | `curobo/` | URDF、碰撞球、ESDF、规划桥接 | 统一轨迹、碰撞可视化、模型哈希 |
| JAKA 执行 | `jaka/` | 轨迹门禁、状态回读、伺服发送、故障恢复 | 空载日志、周期抖动、跟随误差、错误码 |
| 联合任务 | `integration/` | 状态机、模块编排、任务回归 | 完整运行编号、阶段结果、恢复验证 |

## 文件所有权

- `runs/`：运行产物，只提交小型元数据与报告；点云、视频和模型存放数据盘。
- `config/`：可复现配置；现场私有 IP 和凭证不得提交。
- `src/ares_r/adapters/`：设备边界；禁止跨设备隐式调用。
- `src/ares_r/motion/`：统一轨迹与门禁；规划器不得绕过。
- `docs/`：结论、操作步骤和已知限制。
- `worklog/`：每日留痕与事后补录。

同一配置文件避免并行修改。无法避免时，先拆分为设备独立配置，再进入合并流程。

## 交接契约

感知到规划：

```text
run_id, timestamp, frame_id, object_id, grasp_id,
position, orientation, orientation_convention,
confidence, calibration_revision, template_revision, raw_response
```

规划到执行：

```text
schema_version, planner, arm, joint_names, sample_period_s,
points, collision_checked, robot_model_revision, world_revision,
tool_revision, attached_object_revision
```

执行到回归：

```text
trajectory_hash, start_state, result, error_code,
max_following_error, max_queue, period_jitter,
limit_state, collision_state, abort_reason
```

字段缺失时交接失败，不采用口头单位或未命名坐标系。

## 每次调试流程

1. 从最新 `main` 创建短分支。
2. 建立运行编号并冻结配置副本。
3. 执行单模块测试，保存原始输入和原始输出。
4. 填写结果、失败原因、模型哈希和下一门禁。
5. 执行 `PYTHONPATH=src python3 -m unittest discover -s tests -v`。
6. 执行 `python3 scripts/check_traceability.py --mode staged`。
7. 添加 `worklog` 记录后提交 Pull Request。

## 合并条件

- 感知变更：固定场景 30 帧重复性与失败样本齐全。
- 规划变更：整臂、工具、附着物、自碰撞检查证据齐全。
- 执行变更：Mock 或假 SDK 测试通过；真机入口默认关闭。
- 真机变更：空载低速结果、停止验证、限位与碰撞状态记录齐全。
- 接口变更：旧数据兼容策略或迁移脚本齐全。

## 冲突处理

实验结论与代码分离提交。失败实验同样保留，禁止只留下成功轨迹。配置冲突以可复现证据和更严格安全门禁为合并依据。无法核实的历史工作使用 `Source: reconstructed` 补录，未知字段写明 `unconfirmed`。
