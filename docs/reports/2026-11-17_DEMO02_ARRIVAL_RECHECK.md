# Demo02 到位验收复查

## 实机记录

首次 ROS 请求 `demo02-first-live-20261117-01`，run ID `b37e96e7af884e5f935d6d932ff81f51`。双臂完成当前位姿到 center；两侧 native 均记录 target_reached 和 servo_disabled=0。第二运动段未执行，原 ROS FAULT 结果保持不变，不认定完整 Demo02 成功。

## 发现及本地修正

1. 修复到位首次失败永久污染后续采样的问题，要求连续三次新鲜回读合格。
2. 对齐已交付 Demo01 的分段合同：center 使用 TCP 3mm/3°；返回保存姿态除 TCP 外继续要求关节误差不超过0.05°。native 内部执行、跟踪及到位保护不变。
3. 所有采样保留实际 joints/T_body_tcp 和是否启用保存关节判据。此前右臂 TCP 误差小于0.6mm/0.1°，但个别关节回读约0.08°，因 center 额外关节门槛而失败。读数变化的物理原因尚未确认。

本地 release 测试：10/10 OK。最新分段合同修正尚未部署、尚未重新实机验证。

## 当前阻塞

2026-11-17 重连：172.28.172.210 SSH 超时；192.168.1.110 的 ED25519 指纹 `SHA256:4EUtMPMP/N1JX2aakGyySmZUPnvvVz/qJZhyWxSB2Ys` 与原已信任机器人密钥不一致。未修改 known_hosts，未跳过校验。等待现场从主机控制台核实。

自动审批曾拒绝首次 FAULT 后再次运动，要求知悉故障后重新授权；未发送重试 ROS goal。恢复身份核验后，先部署及只读复查，再请求一次运动重试授权。

Delivered=false；无新增 push。
