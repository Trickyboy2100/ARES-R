# Configuration

后续建议按环境拆分以下配置，避免在代码中硬编码：

- `devices.yaml`：相机、双臂控制服务、底盘和夹爪设备地址。
- `frames.yaml`：机器人基座、相机、工具和工位坐标系。
- `stations.yaml`：取料工位、烘干炉及六个 dock 的相对位姿。
- `motion.yaml`：速度、加速度、关节限位和接近/退出距离。

不要把密码或 Token 提交到 Git；敏感值使用未跟踪的 `.env` 或现场密钥管理方式。
