# E2E Integration Control Point（2026-09-17 下午）

## Git 整理

- forensic archive 保持在 `/home/yikun/ARES-R_AUDIT_20260917/`。
- `preserve/site-20260916`：64 个 dirty 文件原样提交，明确禁止 blanket merge。
- `feat/e2e-v0-integration-20260917`：从干净 `92a9c574` 建立，只选择性集成 core/gated，再独立完成返工。
- DROP/generated pregrasp case/target 只在 preservation/evidence 中，不进入 integration。

## 已保留

- Epic 5700 structured parser、ACK/error/meta、多候选；
- cuRobo profiles、feedback audit、preview、FK/benchmark、singularity；
- pregrasp/native/Terminal 仅保留为 gated 路线。

## 已返工

- `EpicTaskProfile` 按 arm/space/object/camera/tool revision 定义，四个 site profile 全部 `UNCOMMISSIONED`；不再存在 global `pose_frame_verified=true`。
- 当前只读 controller tool 完整 SE(3) 已保存并 SHA256 revision：左 Tool 3 `901e0a...d3a4`，右 Tool 2 `b69f75...948b`。
- IK 使用 `T_base_link6_goal = T_base_tcp_goal · inverse(T_link6_tcp)`，非零 tool rotation 回归测试覆盖；候选增加 TCP orientation endpoint gate。
- direct `Epic → cuRobo` 被阻断；grasp IK 必须接收已冻结 SceneSnapshot，并记录 snapshot/tool revision。
- `DualArmSafetyKernel`、中央 slab、inactive arm、SceneSnapshot、tool/start/dynamics gates 与命名 speed profiles 已加入。
- 正式 arm gateways 已 fail-closed；`execution_enabled=false`。

## 仍然阻止实机运动的项目

1. Epic 左右 profile 的 frame/orientation/approach/calibration 尚未 commission。
2. `T_body_camera` 未恢复；BODY ROI/self-filter/scene 尚不能生成。
3. gripper/chassis/payload/inactive-arm collision geometry 不完整。
4. planner 尚未输出 SafetyKernel 所需的逐采样完整 BODY spheres。
5. 历史 `b5_*`/prototype、AMR、夹爪尚未全部接入统一 motion authority。
6. JAKA Safety Plane 只能通过 App 管理员设置，尚未现场配置/留证。
7. 四个 speed profile 均为 UNCOMMISSIONED。
8. AMR 真实到站/定位/静止 API 与 transport-safe interlock 未完成。

在这些条件完成前，integration 分支只允许相机与只读状态，不允许开始 E2E 实机运动。
