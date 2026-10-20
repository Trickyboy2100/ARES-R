# Golden 取放任务保全：2026-10-19，归档于2026-10-20

本基线按现场确认标记为 GOLDEN_TASK_COMPLETED_WITH_RECOVERY。已完成取料、连续抬升230mm、转场、放置、释放、返回。它是成功任务及其恢复路径的保全基线；原全链在 PLACE 故障，修正持物模型后接续成功，尚不能称为同一脚本无人干预连续成功。

旧 `right_arm_epic_pick_lift_v1` / `scripts/run_first_pick_demo.py` 继续作为独立 golden，不替换。此分支只保存本地已存在的实现和文档，不部署、不运动、不改变生产参数。

## 可复刻内容及缺口

- `source-manifest.json`：1799个本地源码/配置文件的SHA256，来自有未提交改动的RC1 staging；基底18715bf。没有在线比对 .32，因此不声称是现场当前完整镜像。
- `private-data-manifest.json`：本地229个现场文件/归档的清单、大小和SHA256。原始点云、照片和大型归档未公开上传。
- `prepared-artifact-gaps.json`：最后预览包的绑定文件核验；未找到项不能由汇总报告替代。
- `evidence/`：完成结果、事件时间、历史测试结果。
- `historical_helpers/*.txt`：现场辅助脚本的原始源码保全；用txt封存，因为这些脚本包含固定运行ID、旧场景路径、一次性授权和物理动作，不能当作可重复入口直接运行。
- 完整现场运行目录、最终实际执行的planner request/result、native trajectory、sender二进制、源模型和点云需依照 `SITE_COLLECTION.md` 补齐。仅有SHA不等于数据可获得。

## 成功流程和参数

| 阶段 | 保存的实现/参数 | 成功状态 |
|---|---|---|
| GRASP检测 | Epic ID1 `320,2,1,1,1,0` | 前半程完成 |
| center→pregrasp | fresh scene/cuRobo或有绑定验证的缓存，55mm预抓取 | 完成 |
| 接近/抓取 | gripper400→contact→close0→验证 | 完成 |
| 抬升 | 一次连续230mm，Demo内TCP-local-Z −10°补偿 | 完成 |
| GRASP→PLACE | 后400mm、右810mm、前320mm，yaw=0 | 完成 |
| PLACE检测 | ID3，下层中间泊位，已存偏置、上方40mm | 完成 |
| preland | 修正持物模型后fresh scene/cuRobo | 接续完成 |
| 下降/释放 | 连续BODY Z−50mm，松爪400，延迟读回 | 接续完成 |
| 返回 | 后320mm、左810mm、前400mm；不收臂 | 接续完成 |

权威参数：`demos/right_arm_grasp_place_roundtrip_v1/parameters.json`；
路线：`config/grasp_place_base_route.json`；
相机/工具配置：`config/system.json`；
泊位和站位原始注册表继续保留在config内。
物理速度必须同时受任务profile、site ceiling和native sender约束，不能把名义0.2rad/s当作实际有效速度。

原始run `af491998a03e4ecaaa524a3504583889` 保留FAULT/MOVE_PRELAND历史。
接续执行plan `PLAN_fef112e7a5a04b368f26eda1794344ad`，
轨迹 `sha256:8f02bae69c6b1216e64678082ebd7c9ac01826957c12ac6093299b449abfe44a`。
接续约125.345秒。物体释放读回通过；没有额外视觉证据证明精确落座，也没有精密SLAM站位认证。

## 持物修正的边界

旧模型取了整个 protruding cluster：212×209×105mm，外加每侧4mm，显示约220×217×113mm。新模型主段160×100×原厚度，另保留夹持后段20mm；中心/旋转不变，同一几何用于规划和检查。没有删除周围真实障碍来让规划通过。

实现：`src/ares_r/manipulation/physical_payload.py:demo_exposed_payload_override`。
此次为明确物体尺寸的Demo限定修正；不能宣称已解决通用自动持物估计。
常规package构建仍有旧cluster推算入口，成功修正目前由历史接续脚本注入。下一开发分支必须把它接入正式任务状态后，才能承诺下一轮按钮自动得到同样模型。

## 入口和验收

- WebUI：`src/ares_r/webui/roundtrip_panel.js`、`server.py`
- backend：`src/ares_r/canonical_backend.py`
- launcher：`src/ares_r/demos/roundtrip_launcher.py`
- 全链：`scripts/run_grasp_place_roundtrip.py`
- 状态/阶段：`src/ares_r/manipulation/roundtrip_demo.py`、`roundtrip_job.py`
- 接触下降：`src/ares_r/manipulation/demo_place_contact.py`
- 连续抬升：`src/ares_r/manipulation/continuous_demo_lift.py`
- 独立验证/原生打包：`src/ares_r/motion/independent_path_validation.py`、`native_execution_package.py`

历史现场全测782项、1 skipped，证据已保留。此数值不是本次Mac重新跑出的测试。
复现前先补齐数据和依赖，在Ubuntu完成冻结回放，再用fresh现场状态重新规划。旧轨迹/lease不能因归档为golden而自动再次执行。

下一步工作见 `UBUNTU_REPLAY_ORDER.md` 和 `GENERALIZATION_AND_UI.md`。
