# Configuration

后续建议按环境拆分以下配置，避免在代码中硬编码：

- `devices.yaml`：相机、双臂控制服务、底盘和夹爪设备地址。
- `frames.yaml`：机器人基座、相机、工具和工位坐标系。
- `stations.yaml`：取料工位、烘干炉及六个 dock 的相对位姿。
- `motion.yaml`：速度、加速度、关节限位和接近/退出距离。

不要把密码或 Token 提交到 Git；敏感值使用未跟踪的 `.env` 或现场密钥管理方式。

## JAKA Mini2 现场限位

`jaka_mini2_motion.site.json` 是纳入 Git 评审的现场安全配置，当前零上下限不是实机参数，且故意保持不可执行。旧 clone 缺少该文件时运行：

```bash
python3 scripts/init_site_config.py
```

脚本不会覆盖已有文件。只有在双臂铭牌/JAKA APP 核实型号、控制器软限位、关节顺序、TCP、负载和低速参数，并在 Pull Request 中附带证据后，才可把 `commissioning_confirmed` 改为 `true`。安全配置不得包含密码、Token 或其他凭证。`legacy/` 中的 MiniCobo 文件仅供理解旧仿真结构，不能用于 Mini2 真机。
